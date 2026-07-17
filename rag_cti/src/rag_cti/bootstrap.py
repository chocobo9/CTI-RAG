"""Shared construction helpers for eval scripts and the CLI.

Every eval entrypoint needs the same stack: settings -> QdrantStore -> Embedder
-> BM25 sparse encoder -> build_pipeline, plus the config-name -> alpha mapping
and (sometimes) a DeepSeek client with a fixed-model router. This module is the
single home for those pieces so scripts stop copy-pasting them.

Path constants assume the repo layout (``src/rag_cti/bootstrap.py`` under the
``rag_cti/`` project root) — the same assumption every script already made.
Heavy dependencies (qdrant-client, sentence-transformers, openai) are imported
lazily inside the builders so importing this module stays cheap.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
EVAL_DIR = DATA_DIR / "eval"
VOCAB_DIR = DATA_DIR / "processed" / "sparse_vocab"
VOCAB_PATH = VOCAB_DIR / "sparse_vocab.json"
ONTOLOGY_NODES_PATH = DATA_DIR / "processed" / "ontology_nodes.jsonl"

# Retriever config name -> dense weight in the weighted-RRF fusion.
# 1.0 = pure dense (sparse retriever skipped); 0.5 = symmetric hybrid.
ALPHA_MAP: dict[str, float] = {"dense": 1.0, "hybrid": 0.5, "hybrid+hyde": 0.5}

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"


class FixedRouter:
    """Minimal LLMRouter substitute: returns one model for every task.

    Used when generation runs on a provider/model other than the
    settings-derived Groq tiers (e.g. DeepSeek). Generator only calls
    ``.model_for(task) -> str``.
    """

    def __init__(self, model: str) -> None:
        self._model = model

    def model_for(self, task: object) -> str:
        return self._model


@dataclass(frozen=True)
class RetrievalStack:
    """The shared retrieval components every eval/CLI entrypoint builds."""

    store: Any
    embedder: Any
    encoder: Any
    collection: str


def load_sparse_encoder(vocab_path: Path = VOCAB_PATH) -> Any:
    """Load the persisted BM25 vocabulary, or a fresh encoder when absent."""
    from rag_cti.retrieval.bm25 import BM25SparseEncoder

    return BM25SparseEncoder.load(vocab_path) if vocab_path.exists() else BM25SparseEncoder()


def load_ontology_nodes(path: Path = ONTOLOGY_NODES_PATH) -> list[dict[str, Any]]:
    """Load ontology nodes (name/alias -> id) for query-time entity routing.

    Returns ``[]`` when the file is absent so the pipeline degrades to
    deterministic-only constraint routing rather than failing.
    """
    import json

    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def vocab_path_for(collection: str, base: Path = VOCAB_DIR) -> Path:
    """The BM25 vocab paired with a collection.

    Returns ``data/processed/sparse_vocab/sparse_vocab_{collection}.json`` when present — so a
    collection's doc and query sparse vectors share one vocab space — else the
    shared default (``data/processed/sparse_vocab/sparse_vocab.json``). Ingest
    writes a per-collection vocab; eval/query auto-pair on it via this function.
    """
    specific = base / f"sparse_vocab_{collection}.json"
    return specific if specific.exists() else VOCAB_PATH


def build_retrieval_stack(
    settings: Any,
    collection: str | None = None,
    device: str | None = None,
    vocab_path: Path | None = None,
) -> RetrievalStack:
    """Build store + embedder + sparse encoder from settings.

    When ``vocab_path`` is None the BM25 vocab is auto-paired to the collection
    (:func:`vocab_path_for`), keeping query sparse vectors in the same space as
    the collection's doc sparse vectors.
    """
    from rag_cti.embeddings.embedder import Embedder
    from rag_cti.store.qdrant_store import QdrantStore

    coll = collection or settings.qdrant_collection
    store = QdrantStore(
        url=settings.qdrant_url,
        collection=coll,
        api_key=settings.qdrant_api_key.get_secret_value(),
    )
    embedder = Embedder(model_name=settings.embedding_model, device=device)
    resolved_vocab = vocab_path if vocab_path is not None else vocab_path_for(coll)
    encoder = load_sparse_encoder(resolved_vocab)
    return RetrievalStack(store=store, embedder=embedder, encoder=encoder, collection=coll)


def build_eval_pipeline(
    stack: RetrievalStack,
    settings: Any,
    config_name: str,
    llm_client: Any | None = None,
    llm_provider: str = "groq",
) -> Any:
    """build_pipeline wired for a named eval config (dense / hybrid / hybrid+hyde).

    HyDE only engages for ``hybrid+hyde`` AND when ``llm_client`` is provided —
    the same convention every eval script used.
    """
    from rag_cti.retrieval import build_pipeline

    use_hyde = config_name == "hybrid+hyde"
    return build_pipeline(
        settings=settings,
        store=stack.store,
        embedder=stack.embedder,
        encoder=stack.encoder,
        llm_client=llm_client if use_hyde else None,
        llm_provider=llm_provider if use_hyde else "groq",
        hybrid_alpha_override=ALPHA_MAP.get(config_name, 0.5),
        ontology_nodes=load_ontology_nodes(),
    )


def build_deepseek_client(
    settings: Any, max_retries: int | None = None, timeout: float | None = None
) -> Any:
    """OpenAI-compatible DeepSeek client. Raises when DEEPSEEK_API_KEY is unset.

    ``max_retries=1`` keeps this a fast-fail client: generation wraps it in
    ``FallbackChatClient`` (model-downgrade is the cross-call retry authority) and the
    judge fails closed rather than hang, so a high per-call retry count only amplifies a
    429. ``timeout`` defaults to ``settings.deepseek_request_timeout`` (bounds one request)."""
    from openai import OpenAI

    key = settings.deepseek_api_key.get_secret_value()
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY not set — cannot build a DeepSeek client")
    request_timeout = (
        timeout if timeout is not None else getattr(settings, "deepseek_request_timeout", 60.0)
    )
    retries = max_retries if max_retries is not None else getattr(settings, "llm_max_retries", 1)
    return OpenAI(
        base_url=DEEPSEEK_BASE_URL, api_key=key, max_retries=retries, timeout=request_timeout
    )


def build_qwen_client(
    settings: Any, max_retries: int | None = None, timeout: float | None = None
) -> Any:
    """OpenAI-compatible Qwen (Alibaba DashScope) client. Raises when QWEN_API_KEY is unset.

    Used for the independent sufficiency judge (a different model family from the DeepSeek
    gatherer). Base URL is region-specific (see ``Settings.qwen_base_url``). ``max_retries=1``
    /``timeout`` mirror :func:`build_deepseek_client` — fast-fail so a 429 cannot hang the
    judge."""
    from openai import OpenAI

    key = settings.qwen_api_key.get_secret_value()
    if not key:
        raise RuntimeError("QWEN_API_KEY not set — cannot build a Qwen client")
    request_timeout = (
        timeout if timeout is not None else getattr(settings, "deepseek_request_timeout", 60.0)
    )
    retries = max_retries if max_retries is not None else getattr(settings, "llm_max_retries", 1)
    return OpenAI(
        base_url=settings.qwen_base_url,
        api_key=key,
        max_retries=retries,
        timeout=request_timeout,
    )
