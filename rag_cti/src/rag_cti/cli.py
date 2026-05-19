from __future__ import annotations

from datetime import UTC
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
    import rag_cti

    result = rag_cti.query(text, top_k=k)

    tbl = Table(title=f"Top-{k} results", show_lines=True)
    tbl.add_column("Rank", justify="right", style="dim")
    tbl.add_column("Score", justify="right")
    tbl.add_column("Source", style="cyan")
    tbl.add_column("Chunk ID", style="dim")
    tbl.add_column("Snippet")

    for i, r in enumerate(result.results, 1):
        snippet = r.document.content[:120].replace("\n", " ")
        tbl.add_row(str(i), f"{r.score:.4f}", r.document.source, r.document.id[:12], snippet)

    console.print(tbl)


@app.command()
def ingest(
    source: str = typer.Argument(..., help="Source name: mitre | otx | vt | whois | pdns | pdf"),
) -> None:
    """Ingest a data source into the vector store."""
    console.print("[yellow]'ingest' is not available in this release — use the scripts/ connectors directly.[/yellow]")
    raise typer.Exit(code=1)


@app.command()
def refresh(
    since: str = typer.Option("24h", "--since", help="Refresh window, e.g. 24h or 7d"),
) -> None:
    """Refresh time-windowed data sources."""
    console.print("[yellow]'refresh' is not available in this release — use the scripts/ connectors directly.[/yellow]")
    raise typer.Exit(code=1)


@app.command()
def metrics(
    input: Path = typer.Argument(
        Path("data/eval/retrieval_results.json"),
        help="retrieval_results.json produced by 'rag-cti eval retrieval'",
    ),
    strict: bool = typer.Option(False, "--strict", help="Exit code 1 when thresholds violated"),
) -> None:
    """Display retrieval metrics from a saved evaluation run."""
    from rag_cti.cli_metrics import check_thresholds, load_results, render_summary_table

    try:
        data = load_results(input)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    render_summary_table(data, console)

    warnings = check_thresholds(data)
    for w in warnings:
        console.print(f"[yellow]WARNING: {w}[/yellow]")

    if strict and warnings:
        raise typer.Exit(code=1)


@app.command()
def eval(
    suite: str = typer.Argument(
        "techniquerag",
        help="Eval suite: techniquerag | retrieval | ragas",
    ),
    max_records: int = typer.Option(None, "--max-records", "-n", help="Limit dataset records for quick runs"),
    k: list[int] = typer.Option([1, 5, 10], "--k", help="Hit@k cutoffs (repeatable)"),
    config: str = typer.Option(
        "all",
        "--config",
        "-c",
        help="Retriever config: dense | hybrid | hybrid+hyde | all",
    ),
    split: str = typer.Option("train", "--split", help="Dataset split (techniquerag only)"),
    cache: Path = typer.Option(
        Path("data/eval/techniquerag_cache.jsonl"),
        "--cache",
        help="Path to JSONL cache file (techniquerag only)",
    ),
    dataset_id: str = typer.Option(
        "QCRI/TechniqueRAG-Datasets",
        "--dataset-id",
        help="HuggingFace dataset ID (techniquerag only)",
    ),
    query_set: Path = typer.Option(
        Path("data/eval/query_set.jsonl"),
        "--query-set",
        help="Query set JSONL path (retrieval only)",
    ),
    output: Path = typer.Option(
        Path("data/eval/retrieval_results.json"),
        "--output",
        "-o",
        help="Output JSON path (retrieval only)",
    ),
) -> None:
    """Run an evaluation suite against the retrieval pipeline."""
    if suite not in ("techniquerag", "retrieval", "ragas"):
        console.print(f"[red]Unknown suite: {suite!r}. Choose 'techniquerag', 'retrieval', or 'ragas'.[/red]")
        raise typer.Exit(code=1)

    # -------------------------------------------------------------------------
    # ragas suite — generation quality via faithfulness + answer_relevancy
    # -------------------------------------------------------------------------
    if suite == "ragas":
        import json
        from dataclasses import asdict

        from rag_cti.config import get_settings
        from rag_cti.embeddings.embedder import Embedder
        from rag_cti.evaluation.query_set import load_query_set
        from rag_cti.evaluation.ragas_eval import run_ragas_eval
        from rag_cti.generation.client import build_llm_client
        from rag_cti.generation.generator import Generator
        from rag_cti.generation.llm_router import LLMRouter
        from rag_cti.retrieval import build_pipeline
        from rag_cti.retrieval.bm25 import BM25SparseEncoder
        from rag_cti.store.qdrant_store import QdrantStore
        from rag_cti.types import GeneratedAnswer

        n_queries = max_records or 10
        configs_to_run = ["hybrid"] if config == "all" else [config]
        vocab_path = Path(__file__).parent.parent.parent / "data" / "sparse_vocab.json"
        ALPHA_MAP = {"dense": 1.0, "hybrid": 0.5, "hybrid+hyde": 0.5}

        console.print(f"Loading query set from [bold]{query_set}[/bold] ...")
        records = load_query_set(query_set)
        records = records[:n_queries]
        console.print(f"  [green]{len(records)} records selected[/green]")

        settings = get_settings()
        store = QdrantStore(
            url=settings.qdrant_url,
            collection=settings.qdrant_collection,
            api_key=settings.qdrant_api_key.get_secret_value(),
        )
        embedder = Embedder(model_name=settings.embedding_model)
        encoder = BM25SparseEncoder.load(vocab_path) if vocab_path.exists() else BM25SparseEncoder()

        deepseek_key = settings.deepseek_api_key.get_secret_value()
        if deepseek_key:
            from openai import OpenAI as _OpenAI

            llm_client = _OpenAI(
                api_key=deepseek_key,
                base_url="https://api.deepseek.com/v1",
            )
            llm_provider = "deepseek"
            console.print("LLM provider: [bold]deepseek[/bold]")
        else:
            llm_provider, llm_client = build_llm_client(settings)
            console.print(f"LLM provider: [bold]{llm_provider}[/bold]")

        class _DeepSeekRouter:
            def model_for(self, task: object) -> str:
                return "deepseek-chat"

        router = _DeepSeekRouter() if llm_provider == "deepseek" else LLMRouter(settings)
        generator = Generator(client=llm_client, router=router, settings=settings)

        for cfg in configs_to_run:
            console.print(f"\nRunning RAGAS eval config: [bold]{cfg}[/bold] ...")
            alpha = ALPHA_MAP.get(cfg, 0.5)
            use_hyde = cfg == "hybrid+hyde"
            pipeline = build_pipeline(
                settings=settings,
                store=store,
                embedder=embedder,
                encoder=encoder,
                llm_client=llm_client if use_hyde else None,
                llm_provider=llm_provider if use_hyde else "anthropic",
                hybrid_alpha_override=alpha,
            )

            answers: list[GeneratedAnswer] = []
            for i, rec in enumerate(records):
                console.print(f"  [{i+1}/{len(records)}] {rec.query[:60]}...")
                qr = pipeline.run(rec.query)
                ans = generator.generate(rec.query, qr)
                answers.append(ans)

            console.print(f"  Running RAGAS evaluation ({len(answers)} answers)...")
            ragas_result = run_ragas_eval(answers, config=cfg, settings=settings)

            tbl = Table(title=f"RAGAS Results — {cfg}")
            tbl.add_column("Metric", style="cyan")
            tbl.add_column("Score", justify="right")
            tbl.add_row("Faithfulness", f"{ragas_result.faithfulness:.4f}")
            tbl.add_row("Answer Relevancy", f"{ragas_result.answer_relevancy:.4f}")
            tbl.add_row("N Queries", str(ragas_result.n_queries))
            console.print(tbl)

            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(asdict(ragas_result), indent=2),
                encoding="utf-8",
            )
            console.print(f"\n[green]Saved → {output}[/green]")

        return

    # -------------------------------------------------------------------------
    # retrieval suite — evaluates against data/eval/query_set.jsonl
    # -------------------------------------------------------------------------
    if suite == "retrieval":
        import json
        from dataclasses import asdict
        from datetime import datetime

        from rag_cti.config import get_settings
        from rag_cti.embeddings.embedder import Embedder
        from rag_cti.evaluation.query_set import load_query_set
        from rag_cti.evaluation.retrieval_metrics import QuerySetEvalResult, evaluate_on_query_set
        from rag_cti.generation.client import build_llm_client
        from rag_cti.retrieval import build_pipeline
        from rag_cti.retrieval.bm25 import BM25SparseEncoder
        from rag_cti.store.qdrant_store import QdrantStore

        k_values = tuple(sorted(set(k)))
        configs_to_run = ["dense", "hybrid", "hybrid+hyde"] if config == "all" else [config]
        vocab_path = Path(__file__).parent.parent.parent / "data" / "sparse_vocab.json"

        console.print(f"Loading query set from [bold]{query_set}[/bold] ...")
        records = load_query_set(query_set)
        cats = ("precise", "semantic", "fuzzy")
        cat_counts = {c: sum(1 for r in records if r.category.value == c) for c in cats}
        console.print(f"  [green]{len(records)} records[/green]  " + "  ".join(f"{c}={cat_counts[c]}" for c in cats))

        settings = get_settings()
        store = QdrantStore(
            url=settings.qdrant_url,
            collection=settings.qdrant_collection,
            api_key=settings.qdrant_api_key.get_secret_value(),
        )
        embedder = Embedder(model_name=settings.embedding_model)
        encoder = BM25SparseEncoder.load(vocab_path) if vocab_path.exists() else BM25SparseEncoder()

        llm_provider, llm_client = build_llm_client(settings)
        console.print(f"LLM provider: [bold]{llm_provider}[/bold]")

        ALPHA_MAP = {"dense": 1.0, "hybrid": 0.5, "hybrid+hyde": 0.5}

        eval_results: list[QuerySetEvalResult] = []
        for cfg in configs_to_run:
            console.print(f"\nRunning config: [bold]{cfg}[/bold] ...")
            use_hyde = cfg == "hybrid+hyde"
            alpha = ALPHA_MAP.get(cfg, 0.5)
            pipeline = build_pipeline(
                settings=settings,
                store=store,
                embedder=embedder,
                encoder=encoder,
                llm_client=llm_client if use_hyde else None,
                llm_provider=llm_provider if use_hyde else "anthropic",
                hybrid_alpha_override=alpha,
            )

            class _Retriever:
                def __init__(self, p: object) -> None:
                    self._p = p

                def search(self, text: str, top_k: int) -> list:  # type: ignore[type-arg]
                    return self._p.run(text, top_k=top_k).results  # type: ignore[union-attr]

            result = evaluate_on_query_set(
                retriever=_Retriever(pipeline),
                records=records,
                config=cfg,
                k_values=k_values,
            )
            eval_results.append(result)
            console.print(f"  MRR=[green]{result.overall.mrr:.4f}[/green]  Hit@10=[green]{result.overall.top_k.get(10, 0.0):.4f}[/green]")

        for cat in ("overall", *cats):
            tbl = Table(title=f"Retrieval Results — {cat.upper()}", show_lines=True)
            tbl.add_column("Config", style="cyan")
            for kv in k_values:
                tbl.add_column(f"Hit@{kv}", justify="right")
            tbl.add_column("MRR", justify="right")
            for kv in k_values:
                tbl.add_column(f"nDCG@{kv}", justify="right")
            tbl.add_column("N", justify="right")
            for r in eval_results:
                m = r.overall if cat == "overall" else r.by_category.get(cat)
                if m is None:
                    continue
                row = [r.config]
                for kv in k_values:
                    row.append(f"{m.top_k.get(kv, 0.0):.4f}")
                row.append(f"{m.mrr:.4f}")
                for kv in k_values:
                    row.append(f"{m.ndcg.get(kv, 0.0):.4f}")
                row.append(str(m.n_queries))
                tbl.add_row(*row)
            console.print(tbl)

        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "query_set": str(query_set),
            "k_values": list(k_values),
            "results": [asdict(r) for r in eval_results],
        }
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        console.print(f"\n[green]Saved → {output}[/green]")
        return

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

    ALPHA_MAP = {"dense": 1.0, "hybrid": 0.5, "hybrid+hyde": 0.5}

    results: list[EvalResult] = []
    for cfg in configs_to_run:
        console.print(f"\nRunning config: [bold]{cfg}[/bold]")
        use_hyde = cfg == "hybrid+hyde"
        alpha = ALPHA_MAP.get(cfg, 0.5)
        pipeline = build_pipeline(
            settings=settings,
            store=store,
            embedder=embedder,
            encoder=encoder,
            llm_client=groq_client if use_hyde else None,
            llm_provider="groq" if use_hyde and groq_client else "anthropic",
            hybrid_alpha_override=alpha,
        )

        class _Retriever:
            def __init__(self, p: object) -> None:
                self._p = p

            def search(self, text: str, top_k: int) -> list:  # type: ignore[type-arg]
                return self._p.run(text, top_k=top_k).results  # type: ignore[union-attr]

        result = evaluate_retriever(
            retriever=_Retriever(pipeline),
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
