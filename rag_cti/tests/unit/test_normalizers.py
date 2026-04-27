from __future__ import annotations

import pytest

from rag_cti.preprocess.chunking import ChunkStrategy
from rag_cti.preprocess.normalizers import source_to_strategy, validate_content


@pytest.mark.parametrize(("source", "expected"), [
    ("whois", ChunkStrategy.STRUCTURED),
    ("pdns", ChunkStrategy.STRUCTURED),
    ("virustotal", ChunkStrategy.STRUCTURED),
    ("mitre", ChunkStrategy.SEMANTIC),
    ("otx", ChunkStrategy.SEMANTIC),
    ("pdf", ChunkStrategy.SEMANTIC),
    ("unknown_source", ChunkStrategy.SEMANTIC),
])
def test_source_to_strategy(source: str, expected: ChunkStrategy) -> None:
    assert source_to_strategy(source) == expected


def test_validate_content_strips_whitespace() -> None:
    assert validate_content("  hello world  ", "mitre", "doc-001") == "hello world"


def test_validate_content_collapses_internal_whitespace() -> None:
    result = validate_content("hello   world\t\there", "otx", "doc-002")
    assert "  " not in result
    assert "\t" not in result


def test_validate_content_preserves_paragraph_breaks() -> None:
    result = validate_content("paragraph one.\n\nparagraph two.", "mitre", "doc-003")
    assert "\n\n" in result


def test_validate_content_collapses_excess_newlines() -> None:
    result = validate_content("line one.\n\n\n\nline two.", "mitre", "doc-004")
    assert "\n\n\n" not in result


def test_validate_content_raises_on_empty_string() -> None:
    with pytest.raises(ValueError, match="Empty content"):
        validate_content("", "mitre", "doc-005")


def test_validate_content_raises_on_whitespace_only() -> None:
    with pytest.raises(ValueError, match="Empty content"):
        validate_content("   \n\t  ", "otx", "doc-006")
