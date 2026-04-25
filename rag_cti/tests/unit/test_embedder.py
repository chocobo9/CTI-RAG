from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from rag_cti.embeddings.embedder import Embedder


@pytest.fixture
def mock_st_module() -> MagicMock:
    """Install a fake sentence_transformers module and yield the SentenceTransformer mock class."""
    fake_module = types.ModuleType("sentence_transformers")
    fake_cls = MagicMock(name="SentenceTransformer")
    fake_module.SentenceTransformer = fake_cls  # type: ignore[attr-defined]
    with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
        yield fake_cls


def _make_model_instance(dim: int = 384) -> MagicMock:
    model = MagicMock()
    model.get_sentence_embedding_dimension.return_value = dim

    def encode(texts: list[str], **_: object) -> np.ndarray:
        return np.ones((len(texts), dim), dtype=np.float32)

    model.encode.side_effect = encode
    return model


def test_encode_returns_float32_array_with_expected_shape(mock_st_module: MagicMock) -> None:
    mock_st_module.return_value = _make_model_instance(dim=384)
    embedder = Embedder("fake-model")

    vectors = embedder.encode(["alpha", "beta", "gamma"])

    assert vectors.shape == (3, 384)
    assert vectors.dtype == np.float32


def test_encode_empty_list_returns_zero_rows(mock_st_module: MagicMock) -> None:
    mock_st_module.return_value = _make_model_instance(dim=384)
    embedder = Embedder("fake-model")

    vectors = embedder.encode([])

    assert vectors.shape == (0, 384)


def test_encode_one_returns_1d_vector(mock_st_module: MagicMock) -> None:
    mock_st_module.return_value = _make_model_instance(dim=384)
    embedder = Embedder("fake-model")

    vector = embedder.encode_one("single query")

    assert vector.shape == (384,)
    assert vector.dtype == np.float32


def test_model_is_loaded_only_once(mock_st_module: MagicMock) -> None:
    mock_st_module.return_value = _make_model_instance(dim=384)
    embedder = Embedder("fake-model")

    embedder.encode(["a"])
    embedder.encode(["b"])
    embedder.encode_one("c")

    assert mock_st_module.call_count == 1


def test_dimension_reflects_model(mock_st_module: MagicMock) -> None:
    mock_st_module.return_value = _make_model_instance(dim=768)
    embedder = Embedder("fake-model")

    assert embedder.dimension == 768


def test_encode_passes_normalize_true_by_default(mock_st_module: MagicMock) -> None:
    model = _make_model_instance(dim=384)
    mock_st_module.return_value = model
    embedder = Embedder("fake-model")

    embedder.encode(["hello"])

    _, kwargs = model.encode.call_args
    assert kwargs["normalize_embeddings"] is True


def test_encode_can_disable_normalization(mock_st_module: MagicMock) -> None:
    model = _make_model_instance(dim=384)
    mock_st_module.return_value = model
    embedder = Embedder("fake-model", normalize=False)

    embedder.encode(["hello"])

    _, kwargs = model.encode.call_args
    assert kwargs["normalize_embeddings"] is False


def test_encode_passes_batch_size(mock_st_module: MagicMock) -> None:
    model = _make_model_instance(dim=384)
    mock_st_module.return_value = model
    embedder = Embedder("fake-model", batch_size=32)

    embedder.encode(["a", "b", "c"])

    _, kwargs = model.encode.call_args
    assert kwargs["batch_size"] == 32


def test_model_name_is_passed_to_loader(mock_st_module: MagicMock) -> None:
    mock_st_module.return_value = _make_model_instance(dim=384)
    embedder = Embedder("BAAI/bge-small-en-v1.5")

    embedder.encode(["ping"])

    args, _ = mock_st_module.call_args
    assert args[0] == "BAAI/bge-small-en-v1.5"


def test_dimension_raises_when_model_returns_non_int(mock_st_module: MagicMock) -> None:
    bad_model = MagicMock()
    bad_model.get_sentence_embedding_dimension.return_value = None
    mock_st_module.return_value = bad_model
    embedder = Embedder("broken-model")

    with pytest.raises(RuntimeError, match="non-int dimension"):
        _ = embedder.dimension
