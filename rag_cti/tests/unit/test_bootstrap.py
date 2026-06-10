from __future__ import annotations

import pytest

from rag_cti.bootstrap import (
    ALPHA_MAP,
    DATA_DIR,
    EVAL_DIR,
    PROJECT_ROOT,
    VOCAB_PATH,
    FixedRouter,
    build_deepseek_client,
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
    assert VOCAB_PATH == DATA_DIR / "sparse_vocab.json"


def test_fixed_router_returns_same_model_for_every_task() -> None:
    router = FixedRouter("deepseek-chat")
    assert router.model_for("hyde") == "deepseek-chat"
    assert router.model_for(object()) == "deepseek-chat"


def test_build_deepseek_client_requires_key() -> None:
    class _Secret:
        def get_secret_value(self) -> str:
            return ""

    class _Settings:
        deepseek_api_key = _Secret()

    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        build_deepseek_client(_Settings())
