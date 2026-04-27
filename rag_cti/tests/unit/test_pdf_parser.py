from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from rag_cti.connectors.pdf_reports import PDFReportsConnector
from rag_cti.preprocess.pdf_parser import (
    _clean,
    _is_boilerplate_title,
    _is_footer,
    _is_toc,
    _postprocess_sections,
    parse_pdf,
)
from rag_cti.types import Document

# ---------------------------------------------------------------------------
# _clean helper
# ---------------------------------------------------------------------------

def test_clean_collapses_extra_blank_lines() -> None:
    raw = "line one\n\n\n\nline two"
    assert _clean(raw) == "line one\n\nline two"


def test_clean_strips_bare_page_numbers() -> None:
    raw = "paragraph text\n   42   \nmore text"
    result = _clean(raw)
    assert "42" not in result
    assert "paragraph text" in result
    assert "more text" in result


def test_clean_collapses_horizontal_whitespace() -> None:
    raw = "word1   word2\t\tword3"
    assert _clean(raw) == "word1 word2 word3"


def test_clean_preserves_meaningful_numbers_in_text() -> None:
    raw = "CVE-2023-1234 affects Windows 11"
    assert _clean(raw) == "CVE-2023-1234 affects Windows 11"


# ---------------------------------------------------------------------------
# parse_pdf — via mocked parsers
# ---------------------------------------------------------------------------

def test_parse_pdf_returns_sections_from_unstructured(tmp_path: Path) -> None:
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    expected = [
        {"text": "A" * 60, "section_title": "Introduction", "page": 1},
        {"text": "B" * 60, "section_title": "Findings", "page": 2},
    ]

    with patch("rag_cti.preprocess.pdf_parser._parse_with_unstructured", return_value=expected):
        sections = parse_pdf(pdf)

    assert len(sections) == 2
    assert sections[0]["section_title"] == "Introduction"
    assert sections[1]["section_title"] == "Findings"


def test_parse_pdf_falls_back_to_pymupdf_on_unstructured_failure(tmp_path: Path) -> None:
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    with (
        patch(
            "rag_cti.preprocess.pdf_parser._parse_with_unstructured",
            side_effect=ImportError("unstructured not installed"),
        ),
        patch(
            "rag_cti.preprocess.pdf_parser._parse_with_pymupdf",
            return_value=[{"text": "C" * 60, "section_title": "", "page": 1}],
        ),
    ):
        sections = parse_pdf(pdf)

    assert len(sections) == 1
    assert sections[0]["page"] == 1


def test_parse_pdf_returns_empty_list_when_both_parsers_fail(tmp_path: Path) -> None:
    pdf = tmp_path / "bad.pdf"
    pdf.write_bytes(b"not a pdf")

    with (
        patch(
            "rag_cti.preprocess.pdf_parser._parse_with_unstructured",
            side_effect=RuntimeError("parse error"),
        ),
        patch(
            "rag_cti.preprocess.pdf_parser._parse_with_pymupdf",
            side_effect=RuntimeError("parse error"),
        ),
    ):
        sections = parse_pdf(pdf)

    assert sections == []


# ---------------------------------------------------------------------------
# Rule 1: TOC filtering
# ---------------------------------------------------------------------------

def test_is_toc_true_when_four_or_more_dot_leaders() -> None:
    text = (
        "Introduction..........1\n"
        "Background..........3\n"
        "Findings..........7\n"
        "Indicators..........12\n"
    )
    assert _is_toc(text) is True


def test_is_toc_false_when_fewer_than_four_dot_leaders() -> None:
    text = "See section 2.1...... for details. Also note...... the following."
    assert _is_toc(text) is False


def test_is_toc_false_for_normal_cti_prose() -> None:
    assert _is_toc("APT29 uses spearphishing emails with malicious PDF attachments.") is False


def test_postprocess_drops_toc_section() -> None:
    sections = [
        {
            "text": "Intro..........1\nFindings..........4\nIOCs..........8\nMitigation..........11\n",
            "section_title": "Table of Contents",
            "page": 1,
        },
        {"text": "A" * 200, "section_title": "Introduction", "page": 2},
    ]
    result = _postprocess_sections(sections)
    assert len(result) == 1
    assert result[0]["section_title"] == "Introduction"


# ---------------------------------------------------------------------------
# Rule 2: Boilerplate title filtering
# ---------------------------------------------------------------------------

def test_is_boilerplate_title_matches_all_five_names() -> None:
    for title in ("Notes", "References", "Acknowledgements", "Disclaimer", "Reporting"):
        assert _is_boilerplate_title(title) is True


def test_is_boilerplate_title_strips_surrounding_whitespace() -> None:
    assert _is_boilerplate_title("  Notes  ") is True


def test_is_boilerplate_title_false_for_cti_section_names() -> None:
    assert _is_boilerplate_title("Executive Summary") is False
    assert _is_boilerplate_title("Indicators of Compromise") is False
    assert _is_boilerplate_title("") is False


def test_postprocess_drops_boilerplate_titled_sections() -> None:
    sections = [
        {"text": "A" * 200, "section_title": "Findings", "page": 1},
        {"text": "B" * 200, "section_title": "References", "page": 5},
        {"text": "C" * 200, "section_title": "Disclaimer", "page": 6},
        {"text": "D" * 200, "section_title": "Conclusion", "page": 7},
    ]
    result = _postprocess_sections(sections)
    titles = [s["section_title"] for s in result]
    assert "References" not in titles
    assert "Disclaimer" not in titles
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Rule 3: Footer filtering
# ---------------------------------------------------------------------------

def test_is_footer_true_for_short_page_marker() -> None:
    assert _is_footer("Page 3 of 12") is True
    assert _is_footer("page 1 of 5 — Confidential") is True


def test_is_footer_false_when_text_exceeds_150_chars() -> None:
    assert _is_footer("Page 1 of 5. " + "A" * 200) is False


def test_is_footer_false_without_page_pattern() -> None:
    assert _is_footer("Short text without page marker.") is False


def test_postprocess_drops_footer_chunks() -> None:
    sections = [
        {"text": "A" * 200, "section_title": "Overview", "page": 1},
        {"text": "Page 2 of 8", "section_title": "", "page": 2},
        {"text": "B" * 200, "section_title": "Analysis", "page": 3},
    ]
    result = _postprocess_sections(sections)
    assert len(result) == 2
    assert all("Page" not in s["text"] for s in result)


# ---------------------------------------------------------------------------
# Rule 4: Merge short sections with next
# ---------------------------------------------------------------------------

def test_postprocess_merges_short_section_into_next() -> None:
    short_text = "A" * 150
    long_text = "B" * 300
    sections = [
        {"text": short_text, "section_title": "Key Finding", "page": 2},
        {"text": long_text, "section_title": "Technical Details", "page": 3},
    ]
    result = _postprocess_sections(sections)
    assert len(result) == 1
    assert short_text in result[0]["text"]
    assert long_text in result[0]["text"]


def test_postprocess_merge_carries_page_of_first_section() -> None:
    sections = [
        {"text": "A" * 150, "section_title": "Intro", "page": 2},
        {"text": "B" * 300, "section_title": "Body", "page": 3},
    ]
    result = _postprocess_sections(sections)
    assert result[0]["page"] == 2


def test_postprocess_merge_uses_next_section_title() -> None:
    sections = [
        {"text": "A" * 150, "section_title": "Short Lead-in", "page": 2},
        {"text": "B" * 300, "section_title": "Main Analysis", "page": 3},
    ]
    result = _postprocess_sections(sections)
    assert result[0]["section_title"] == "Main Analysis"


def test_postprocess_keeps_short_section_when_it_is_last() -> None:
    # A short section >= 100 chars with no successor is kept as-is
    sections = [{"text": "A" * 150, "section_title": "Solo Section", "page": 1}]
    result = _postprocess_sections(sections)
    assert len(result) == 1
    assert result[0]["section_title"] == "Solo Section"


def test_postprocess_does_not_merge_section_at_200_chars() -> None:
    # Exactly 200 chars is not "short" — must not trigger merge
    sections = [
        {"text": "A" * 200, "section_title": "First", "page": 1},
        {"text": "B" * 200, "section_title": "Second", "page": 2},
    ]
    result = _postprocess_sections(sections)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Rule 5: Discard very short chunks (< 100 chars)
# ---------------------------------------------------------------------------

def test_postprocess_discards_chunks_under_100_chars() -> None:
    sections = [
        {"text": "A" * 99, "section_title": "Artifact", "page": 1},
        {"text": "B" * 200, "section_title": "Real Content", "page": 2},
    ]
    result = _postprocess_sections(sections)
    assert len(result) == 1
    assert result[0]["section_title"] == "Real Content"


def test_postprocess_keeps_chunk_at_exactly_100_chars() -> None:
    sections = [{"text": "A" * 100, "section_title": "Borderline", "page": 1}]
    result = _postprocess_sections(sections)
    assert len(result) == 1


def test_postprocess_empty_input_returns_empty() -> None:
    assert _postprocess_sections([]) == []


# ---------------------------------------------------------------------------
# Regression: issue 1 — Wingdings bullet U+F0A7 replaced in _clean
# ---------------------------------------------------------------------------

def test_clean_replaces_wingdings_bullet_with_hyphen() -> None:
    assert _clean(" Lateral movement via SMB") == "- Lateral movement via SMB"


def test_clean_replaces_multiple_wingdings_bullets() -> None:
    raw = " First indicator\n Second indicator"
    result = _clean(raw)
    assert "" not in result
    assert result.count("-") >= 2


def test_clean_strips_trailing_inline_page_footer() -> None:
    raw = "APT29 used spearphishing emails to gain initial access.\nPage 6 of 31 | Product ID: AA24-109A TLP:CLEAR"
    result = _clean(raw)
    assert "Page 6 of 31" not in result
    assert "APT29 used spearphishing" in result


def test_clean_strips_multiple_trailing_footer_lines() -> None:
    raw = "Defenders should enable MFA on all remote access portals.\nPage 2 of 14\nPage 2 of 14 | TLP:CLEAR"
    result = _clean(raw)
    assert "Page 2 of 14" not in result
    assert "Defenders should enable MFA" in result


def test_clean_does_not_strip_footer_pattern_mid_text() -> None:
    # Footer pattern not on the last line — real content after it must be preserved
    raw = "See Page 3 of 8 for details.\nAPT group leveraged zero-day vulnerabilities."
    result = _clean(raw)
    assert "APT group leveraged zero-day" in result


# ---------------------------------------------------------------------------
# Regression: issue 2 — _is_footer must not drop real CTI content
# ---------------------------------------------------------------------------

def test_is_footer_false_when_page_pattern_embedded_in_cti_prose() -> None:
    text = (
        "See Page 3 of 8 for a detailed breakdown of APT29 lateral movement "
        "techniques and associated indicators of compromise."
    )
    assert _is_footer(text) is False


def test_is_footer_false_when_substantial_text_precedes_page_marker() -> None:
    # Non-page portion is well over 50 chars — must not be classified as a footer
    assert _is_footer(
        "Executive Summary: threat landscape overview and key findings. Page 1 of 12."
    ) is False


def test_is_footer_still_true_for_standalone_page_marker() -> None:
    assert _is_footer("Page 5 of 20") is True


def test_is_footer_still_true_with_short_label_alongside_marker() -> None:
    # Short confidentiality label (< 50 extra chars) still qualifies as a footer
    assert _is_footer("CONFIDENTIAL — Page 4 of 14") is True


# ---------------------------------------------------------------------------
# PDFReportsConnector
# ---------------------------------------------------------------------------

def test_connector_yields_nothing_for_missing_directory(tmp_path: Path) -> None:
    connector = PDFReportsConnector(pdf_dir=tmp_path / "nonexistent")
    docs = list(connector.fetch_documents())
    assert docs == []


def test_connector_yields_nothing_when_no_pdfs(tmp_path: Path) -> None:
    connector = PDFReportsConnector(pdf_dir=tmp_path)
    docs = list(connector.fetch_documents())
    assert docs == []


def test_connector_produces_documents_from_sections(tmp_path: Path) -> None:
    pdf = tmp_path / "apt29.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    sections = [
        {"text": "X" * 80, "section_title": "Overview", "page": 1},
        {"text": "Y" * 80, "section_title": "Indicators", "page": 2},
    ]

    with patch("rag_cti.connectors.pdf_reports.parse_pdf", return_value=sections):
        docs = list(PDFReportsConnector(pdf_dir=tmp_path).fetch_documents())

    assert len(docs) == 2
    assert all(isinstance(d, Document) for d in docs)
    assert docs[0].metadata["section_title"] == "Overview"
    assert docs[1].metadata["page"] == 2


def test_connector_document_ids_are_deterministic(tmp_path: Path) -> None:
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    sections = [{"text": "Z" * 80, "section_title": "Exec", "page": 1}]

    with patch("rag_cti.connectors.pdf_reports.parse_pdf", return_value=sections):
        docs1 = list(PDFReportsConnector(pdf_dir=tmp_path).fetch_documents())
        docs2 = list(PDFReportsConnector(pdf_dir=tmp_path).fetch_documents())

    assert docs1[0].id == docs2[0].id


def test_connector_source_is_pdf(tmp_path: Path) -> None:
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    with patch(
        "rag_cti.connectors.pdf_reports.parse_pdf",
        return_value=[{"text": "A" * 80, "section_title": "", "page": 1}],
    ):
        docs = list(PDFReportsConnector(pdf_dir=tmp_path).fetch_documents())

    assert docs[0].source == "pdf"


def test_connector_skips_pdf_with_no_sections(tmp_path: Path) -> None:
    pdf = tmp_path / "empty.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    with patch("rag_cti.connectors.pdf_reports.parse_pdf", return_value=[]):
        docs = list(PDFReportsConnector(pdf_dir=tmp_path).fetch_documents())

    assert docs == []


def test_connector_filename_in_metadata(tmp_path: Path) -> None:
    pdf = tmp_path / "threat_intel_q1.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    with patch(
        "rag_cti.connectors.pdf_reports.parse_pdf",
        return_value=[{"text": "B" * 80, "section_title": "Summary", "page": 1}],
    ):
        docs = list(PDFReportsConnector(pdf_dir=tmp_path).fetch_documents())

    assert docs[0].metadata["filename"] == "threat_intel_q1.pdf"
