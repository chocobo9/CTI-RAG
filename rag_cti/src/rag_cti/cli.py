from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from rag_cti._logging import configure_logging

app = typer.Typer(name="rag-cti", help="RAG-powered Cyber Threat Intelligence CLI")
console = Console()


@app.callback()
def main(
    log_level: str = typer.Option("INFO", "--log-level", "-l", help="Logging level"),
) -> None:
    configure_logging(log_level)


@app.command()
def query(
    text: str = typer.Argument(..., help="Query text or IOC string"),
    k: int = typer.Option(10, "--top-k", "-k", help="Number of results"),
) -> None:
    """Retrieve top-k CTI chunks for the given query."""
    raise NotImplementedError("query command: implement after Phase 4")


@app.command()
def ingest(
    source: str = typer.Argument(..., help="Source name: mitre | otx | vt | whois | pdns | pdf"),
) -> None:
    """Ingest a data source into the vector store."""
    raise NotImplementedError("ingest command: implement after Phase 1-2")


@app.command()
def refresh(
    since: str = typer.Option("24h", "--since", help="Refresh window, e.g. 24h or 7d"),
) -> None:
    """Refresh time-windowed data sources."""
    raise NotImplementedError("refresh command: implement after Phase 3")


@app.command()
def eval(
    suite: str = typer.Argument(
        "techniquerag",
        help="Eval suite: techniquerag",
    ),
    max_records: int = typer.Option(None, "--max-records", "-n", help="Limit dataset records for quick runs"),
    k: list[int] = typer.Option([1, 5, 10], "--k", help="Hit@k cutoffs (repeatable)"),
    config: str = typer.Option(
        "all",
        "--config",
        "-c",
        help="Retriever config: dense | hybrid | hybrid+hyde | all",
    ),
    split: str = typer.Option("train", "--split", help="Dataset split"),
    cache: Path = typer.Option(
        Path("data/eval/techniquerag_cache.jsonl"),
        "--cache",
        help="Path to JSONL cache file",
    ),
    dataset_id: str = typer.Option(
        "QCRI/TechniqueRAG-Datasets",
        "--dataset-id",
        help="HuggingFace dataset ID",
    ),
) -> None:
    """Run an evaluation suite against the retrieval pipeline."""
    if suite != "techniquerag":
        console.print(f"[red]Unknown suite: {suite!r}. Only 'techniquerag' is supported.[/red]")
        raise typer.Exit(code=1)

    if max_records is not None and max_records <= 0:
        console.print("[red]--max-records must be a positive integer.[/red]")
        raise typer.Exit(code=1)

    from rag_cti.config import get_settings
    from rag_cti.embeddings.embedder import Embedder
    from rag_cti.evaluation.retrieval_metrics import EvalResult, evaluate_retriever
    from rag_cti.evaluation.techniquerag import load_techniquerag
    from rag_cti.retrieval import build_pipeline
    from rag_cti.retrieval.bm25 import BM25SparseEncoder
    from rag_cti.store.qdrant_store import QdrantStore

    k_values = tuple(sorted(set(k)))
    configs_to_run: list[str] = (
        ["dense", "hybrid", "hybrid+hyde"] if config == "all" else [config]
    )

    console.print(f"Loading TechniqueRAG (split={split}, max={max_records or 'all'})...")
    dataset = load_techniquerag(
        dataset_id=dataset_id,
        split=split,
        cache_path=cache,
        max_records=max_records,
    )
    console.print(f"  [green]{len(dataset)} records loaded.[/green]")

    settings = get_settings()
    vocab_path = Path(__file__).parent.parent.parent / "data" / "sparse_vocab.json"

    store = QdrantStore(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        api_key=settings.qdrant_api_key.get_secret_value(),
    )
    embedder = Embedder(model_name=settings.embedding_model)
    encoder = (
        BM25SparseEncoder.load(vocab_path)
        if vocab_path.exists()
        else BM25SparseEncoder()
    )

    groq_client = None
    try:
        from groq import Groq  # type: ignore[import]
        api_key = settings.groq_api_key.get_secret_value()
        if api_key:
            groq_client = Groq(api_key=api_key)
    except ImportError:
        pass

    results: list[EvalResult] = []
    for cfg in configs_to_run:
        console.print(f"\nRunning config: [bold]{cfg}[/bold]")
        use_hyde = cfg == "hybrid+hyde"
        pipeline = build_pipeline(
            settings=settings,
            store=store,
            embedder=embedder,
            encoder=encoder,
            llm_client=groq_client if use_hyde else None,
            llm_provider="groq" if use_hyde and groq_client else "anthropic",
        )

        class _Retriever:
            def search(self, text: str, top_k: int) -> list:  # type: ignore[type-arg]
                return pipeline.run(text, top_k=top_k).results

        result = evaluate_retriever(
            retriever=_Retriever(),
            dataset=dataset,
            config=cfg,
            k_values=k_values,
        )
        results.append(result)

    table = Table(title="TechniqueRAG Evaluation Results")
    table.add_column("Config", style="cyan")
    for kv in k_values:
        table.add_column(f"Hit@{kv}", justify="right")
    table.add_column("MRR", justify="right")
    table.add_column("N", justify="right")

    for r in results:
        row = [r.config]
        for kv in k_values:
            row.append(f"{r.top_k.get(kv, 0.0):.4f}")
        row.append(f"{r.mrr:.4f}")
        row.append(str(r.n_queries))
        table.add_row(*row)

    console.print(table)


if __name__ == "__main__":
    app()
