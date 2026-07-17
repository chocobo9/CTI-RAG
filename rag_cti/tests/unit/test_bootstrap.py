from __future__ import annotations

import pytest

from rag_cti.bootstrap import (
    ALPHA_MAP,
    DATA_DIR,
    EVAL_DIR,
    PROJECT_ROOT,
    VOCAB_DIR,
    VOCAB_PATH,
    FixedRouter,
    build_deepseek_client,
    vocab_path_for,
)


def test_alpha_map_configs() -> None:
    assert ALPHA_MAP["dense"] == 1.0
    assert ALPHA_MAP["hybrid"] == 0.5
    assert ALPHA_MAP["hybrid+hyde"] == 0.5


def test_paths_anchor_at_project_root() -> None:
    # bootstrap.py lives at src/rag_cti/bootstrap.py under the project root.
    assert (PROJECT_ROOT / "src" / "rag_cti" / "bootstrap.py").exists()
    assert DATA_DIR == PROJECT_ROOT / "data"
    assert EVAL_DIR == DATA_DIR / "eval"
    assert VOCAB_DIR == DATA_DIR / "processed" / "sparse_vocab"
    assert VOCAB_PATH == VOCAB_DIR / "sparse_vocab.json"


def test_fixed_router_returns_same_model_for_every_task() -> None:
    router = FixedRouter("deepseek-chat")
    assert router.model_for("hyde") == "deepseek-chat"
    assert router.model_for(object()) == "deepseek-chat"


def test_vocab_path_for_pairs_per_collection(tmp_path) -> None:
    # No collection-specific file => fall back to the shared default vocab.
    assert vocab_path_for("cti_chunks_v2", base=tmp_path) == VOCAB_PATH
    # A collection-specific vocab present => use it (keeps doc/query vocab paired).
    specific = tmp_path / "sparse_vocab_cti_chunks_v3.json"
    specific.write_text("{}", encoding="utf-8")
    assert vocab_path_for("cti_chunks_v3", base=tmp_path) == specific


def test_build_deepseek_client_requires_key() -> None:
    class _Secret:
        def get_secret_value(self) -> str:
            return ""

    class _Settings:
        deepseek_api_key = _Secret()

    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        build_deepseek_client(_Settings())
