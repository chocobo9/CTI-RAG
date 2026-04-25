from __future__ import annotations

import typer
from rich.console import Console

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
        "retrieval",
        help="Eval suite: techniquerag | retrieval | ragas | baseline | ablation",
    ),
) -> None:
    """Run an evaluation suite."""
    raise NotImplementedError("eval command: implement after Phase 6")


if __name__ == "__main__":
    app()
