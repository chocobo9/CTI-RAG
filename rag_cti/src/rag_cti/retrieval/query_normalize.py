"""Deterministic query IOC guard (query-rewrite §1).

The LLM rewriter must never touch an exact indicator — a 64-hex hash or an IP it
"corrects" is silently wrong, and LLMs do not preserve long opaque strings
reliably. So this runs *before* the LLM: refang defanged forms to canonical, then
replace every exact IOC with a ``<IOC_n>`` placeholder the rewriter is told to keep
verbatim and restores afterward.

Reuses ``bm25._IOC_RE`` (the index-side IOC-preserving tokenizer's pattern) so the
query side and index side agree on what counts as an IOC.
"""

from __future__ import annotations

import re

from rag_cti.retrieval.bm25 import _IOC_RE

# hxxp -> http (also turns hxxps -> https); defanged separators -> canonical form.
_REFANG: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"hxxp", re.IGNORECASE), "http"),
    (re.compile(r"\[\s*\.\s*\]|\(\s*\.\s*\)|\{\s*\.\s*\}|\[dot\]", re.IGNORECASE), "."),
    (re.compile(r"\[\s*://\s*\]"), "://"),
    (re.compile(r"\[\s*:\s*\]"), ":"),
    (re.compile(r"\[\s*(?:@|at)\s*\]", re.IGNORECASE), "@"),
]

# ATT&CK-family ids — uppercased so BM25 (exact token) matches the indexed form.
_ATTACK_ID = re.compile(
    r"\b(?:T\d{4}(?:\.\d{3})?|S\d{4}|G\d{4}|M\d{4}|TA\d{4}|DET\d{4})\b", re.IGNORECASE
)


def refang(text: str) -> str:
    """Restore defanged indicators (``hxxp``, ``[.]``, ``[at]``) to canonical form."""
    for pattern, repl in _REFANG:
        text = pattern.sub(repl, text)
    return text


def _upper_attack_ids(text: str) -> str:
    return _ATTACK_ID.sub(lambda m: m.group().upper(), text)


def protect_iocs(text: str) -> tuple[str, dict[str, str]]:
    """Replace each exact IOC with a ``<IOC_n>`` placeholder.

    Returns ``(protected_text, mapping)`` where mapping is ``{placeholder: ioc}``.
    """
    mapping: dict[str, str] = {}

    def _repl(match: re.Match[str]) -> str:
        placeholder = f"<IOC_{len(mapping) + 1}>"
        mapping[placeholder] = match.group()
        return placeholder

    return _IOC_RE.sub(_repl, text), mapping


def restore_iocs(text: str, mapping: dict[str, str]) -> str:
    """Put the verbatim IOCs back where their placeholders are."""
    for placeholder, value in mapping.items():
        text = text.replace(placeholder, value)
    return text


def prepare(text: str) -> tuple[str, dict[str, str]]:
    """Refang + uppercase attack ids + protect IOCs (the full deterministic pass).

    Returns ``(protected_text, mapping)`` ready to hand to the LLM rewriter.
    """
    return protect_iocs(_upper_attack_ids(refang(text)))


def is_pure_ioc(text: str) -> bool:
    """True when the query is only indicator(s) + punctuation, no prose.

    Such queries skip the LLM (it can only mangle a bare IOC lookup); they still
    get deterministic refang.
    """
    without_iocs = _IOC_RE.sub(" ", refang(text))
    return not re.sub(r"[\s\W_]+", "", without_iocs)
