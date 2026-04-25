"""PDF parsing with unstructured (primary) and pymupdf (fallback).

Returns a list of section dicts so section titles propagate into chunk metadata.
Post-processing filters TOC, boilerplate, footers and merges short sections.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from rag_cti._logging import get_logger

logger = get_logger(__name__)

_MIN_SECTION_CHARS = 50      # early filter inside parsers
_MIN_CHUNK_CHARS = 100       # rule 5: discard artifacts below this threshold
_SHORT_SECTION_CHARS = 200   # rule 4: merge sections shorter than this with next

_BOILERPLATE_TITLES: frozenset[str] = frozenset({
    "Notes", "References", "Acknowledgements", "Disclaimer", "Reporting"
})

_TOC_DOT_RE = re.compile(r"\.{5,}")
_FOOTER_RE = re.compile(r"Page \d+ of \d+", re.IGNORECASE)


def parse_pdf(path: Path) -> list[dict[str, Any]]:
    """Parse a PDF into section dicts: {"text": str, "section_title": str, "page": int}.

    Tries unstructured first; falls back to pymupdf on failure.
    Returns empty list (with a warning) rather than raising, so a bad
    PDF does not abort a batch ingest.
    """
    try:
        return _parse_with_unstructured(path)
    except Exception as exc:
        logger.warning(
            "unstructured failed, trying pymupdf fallback",
            path=str(path),
            error=str(exc),
        )

    try:
        return _parse_with_pymupdf(path)
    except Exception as exc:
        logger.error("pdf parsing failed entirely, skipping", path=str(path), error=str(exc))
        return []


# ---------------------------------------------------------------------------
# Post-processing helpers
# ---------------------------------------------------------------------------

def _is_toc(text: str) -> bool:
    """Rule 1: 4+ dot-leader sequences indicate a table-of-contents chunk."""
    return len(_TOC_DOT_RE.findall(text)) >= 4


def _is_boilerplate_title(title: str) -> bool:
    """Rule 2: exact match against known non-CTI section titles."""
    return title.strip() in _BOILERPLATE_TITLES


def _is_footer(text: str) -> bool:
    """Rule 3: pure page-footer chunk.

    Only matches when 'Page N of M' is essentially the entire content.
    Up to 50 chars of surrounding text (e.g. a confidentiality label) is
    tolerated; beyond that the chunk is treated as substantive CTI content.
    """
    stripped = text.strip()
    match = _FOOTER_RE.search(stripped)
    if not match:
        return False
    non_page = (stripped[: match.start()] + stripped[match.end() :]).strip()
    return len(non_page) < 50


def _postprocess_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter noise and merge short sections.

    Pass 1 — drop (rules 1–3, 5):
        1. TOC chunks with 4+ dot-leader sequences.
        2. Sections whose title exactly matches a boilerplate name.
        3. Pure footer chunks (Page N of M with < 50 chars surrounding text).
        5. Chunks < 100 chars after cleaning (unrecoverable artifacts).

    Pass 2 — merge (rule 4):
        Short sections (100–199 chars) are prepended to the next section
        rather than discarded, preserving CTI content split at boundaries.
        The merged section keeps the next section's title and the earlier page.
    """
    # Pass 1: noise filters
    filtered: list[dict[str, Any]] = []
    for s in sections:
        if _is_toc(s["text"]):
            continue
        if _is_boilerplate_title(s.get("section_title", "")):
            continue
        if _is_footer(s["text"]):
            continue
        if len(s["text"]) < _MIN_CHUNK_CHARS:
            continue
        filtered.append(s)

    # Pass 2: merge short sections forward
    result: list[dict[str, Any]] = []
    i = 0
    while i < len(filtered):
        s = filtered[i]
        if len(s["text"]) < _SHORT_SECTION_CHARS and i + 1 < len(filtered):
            next_s = filtered[i + 1]
            # Prepend short section text to the next; carry the earlier page number
            filtered[i + 1] = {
                "text": s["text"] + " " + next_s["text"],
                "section_title": next_s["section_title"],
                "page": s["page"],
            }
            i += 1
            continue
        result.append(s)
        i += 1

    return result


# ---------------------------------------------------------------------------
# Parser backends
# ---------------------------------------------------------------------------

def _parse_with_unstructured(path: Path) -> list[dict[str, Any]]:
    from unstructured.partition.pdf import partition_pdf  # type: ignore[import]

    elements = partition_pdf(filename=str(path), strategy="fast")

    sections: list[dict[str, Any]] = []
    current_title = ""
    current_parts: list[str] = []
    current_page = 1

    for el in elements:
        el_type = type(el).__name__
        page = getattr(el.metadata, "page_number", current_page) or current_page
        text = str(el).strip()

        if not text:
            continue

        if el_type in ("Title", "Header"):
            if current_parts:
                body = _clean(" ".join(current_parts))
                if len(body) >= _MIN_SECTION_CHARS:
                    sections.append({
                        "text": body,
                        "section_title": current_title,
                        "page": current_page,
                    })
            current_title = text
            current_parts = []
            current_page = page
        else:
            current_parts.append(text)
            current_page = page

    if current_parts:
        body = _clean(" ".join(current_parts))
        if len(body) >= _MIN_SECTION_CHARS:
            sections.append({
                "text": body,
                "section_title": current_title,
                "page": current_page,
            })

    return _postprocess_sections(sections)


def _parse_with_pymupdf(path: Path) -> list[dict[str, Any]]:
    import pymupdf  # type: ignore[import]

    sections: list[dict[str, Any]] = []
    with pymupdf.open(str(path)) as doc:
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text("text")
            if not text or not text.strip():
                continue
            body = _clean(text)
            if len(body) >= _MIN_SECTION_CHARS:
                sections.append({"text": body, "section_title": "", "page": page_num})

    return _postprocess_sections(sections)


def _clean(text: str) -> str:
    """Normalize whitespace, strip artifacts, and replace known bad codepoints."""
    text = text.replace("", "-")        # Wingdings bullet (U+F0A7) → ASCII hyphen
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [ln for ln in text.splitlines() if not re.fullmatch(r"\s*\d{1,4}\s*", ln)]
    # Strip trailing footer lines that unstructured appends to section text
    # e.g. "Page 6 of 31 | Product ID: AA24-109A TLP:CLEAR"
    while lines and _FOOTER_RE.search(lines[-1]):
        lines.pop()
    return "\n".join(lines).strip()
