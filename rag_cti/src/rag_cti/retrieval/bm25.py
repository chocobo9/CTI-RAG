"""BM25 sparse encoder with an IOC-preserving tokenizer.

Vocabulary and IDF weights are persisted under data/processed/sparse_vocab/ after
fitting; load at query time via BM25SparseEncoder.load(path).
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from pathlib import Path

from rag_cti._logging import get_logger

logger = get_logger(__name__)

_K1: float = 1.5
_B: float = 0.75

# Prose-only guard (IOC/hash/domain regex captures are exempt).
_MAX_TOKEN_LEN: int = 64

# Strict IPv4 octets (reject e.g. 1.866.320.478); mask /0–/32 only.
_IPV4_OCTET = r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)"
_IPV4_ADDR = rf"{_IPV4_OCTET}\.{_IPV4_OCTET}\.{_IPV4_OCTET}\.{_IPV4_OCTET}"
_IPV4_CIDR_MASK = r"(?:/(?:3[0-2]|[12]\d|[0-9])(?!\d))?"

# NFKC collapses many compatibility ligatures; explicit map catches leftovers.
_LIGATURE_TRANSLATIONS = str.maketrans(
    {
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\ufb06": "st",
    }
)


def _normalize_text(text: str) -> str:
    """NFKC plus explicit ligature folding for tokenizer stability."""
    s = unicodedata.normalize("NFKC", text)
    return s.translate(_LIGATURE_TRANSLATIONS)


# Ordered most-specific first to avoid partial matches.
# IPv4 fragment is an f-string; the rest must be a plain raw string so `{2}` etc.
# are not interpreted as f-string interpolation.
_IOC_RE = re.compile(
    rf"""
    (?:
      {_IPV4_ADDR}{_IPV4_CIDR_MASK}                         # IPv4 / CIDR
    """
    + r"""
    | (?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}                   # MAC address
    | CVE-\d{4}-\d{4,7}                                       # CVE ID
    | MS\d{2}-\d{3,4}                                         # MS bulletin
    | T\d{4}(?:\.\d{3})?                                      # ATT&CK technique
    | [0-9a-fA-F]{64}                                         # SHA-256
    | [0-9a-fA-F]{40}                                         # SHA-1
    | [0-9a-fA-F]{32}                                         # MD5
    | (?:[A-Za-z0-9\-]+\.)+(?:com|net|org|io|gov|edu|mil|int|ru|cn|uk|de|fr|jp|info|biz|co)
                                                              # domain
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _split_prose(text: str) -> list[str]:
    """Whitespace/punctuation split; drop single-char and overlong prose tokens."""
    out: list[str] = []
    for t in re.split(r"[\s\W]+", text):
        if len(t) < 2:
            continue
        if len(t) > _MAX_TOKEN_LEN:
            continue
        out.append(t.lower())
    return out


def tokenize(text: str) -> list[str]:
    """IOC-preserving tokenizer.

    Extracts IOC patterns as single lowercased tokens before falling back to
    standard prose tokenization for the surrounding text. Ensures that
    '1.2.3.4' is never split into ['1','2','3','4'], that 'CVE-2021-44228'
    survives as one token, etc.

    NFKC and ligature folding apply only to prose segments between IOC matches
    so structured IDs (CVE, ATT&CK) still match ASCII-oriented regexes.
    """
    tokens: list[str] = []
    pos = 0
    for match in _IOC_RE.finditer(text):
        tokens.extend(_split_prose(_normalize_text(text[pos : match.start()])))
        tokens.append(match.group().lower())
        pos = match.end()
    tokens.extend(_split_prose(_normalize_text(text[pos:])))
    return tokens


class BM25SparseEncoder:
    """Two-pass BM25 encoder with a persistent vocabulary.

    fit()              -- first pass: build vocab + IDF from a corpus list
    encode_document()  -- BM25 weights for a single document
    encode_query()     -- IDF-weighted sparse vector for a query string
    save() / load()    -- persist to / restore from data/processed/sparse_vocab/
    """

    def __init__(self) -> None:
        self.vocab: dict[str, int] = {}
        self.idf: dict[int, float] = {}
        self.avgdl: float = 0.0
        self.num_docs: int = 0

    def _term_id(self, term: str) -> int:
        if term not in self.vocab:
            self.vocab[term] = len(self.vocab)
        return self.vocab[term]

    def fit(self, corpus: list[str]) -> None:
        """Build vocab + IDF from corpus texts (first pass)."""
        tokenized = [tokenize(text) for text in corpus]
        self.num_docs = len(tokenized)
        self.avgdl = sum(len(t) for t in tokenized) / max(self.num_docs, 1)

        df: dict[str, int] = {}
        for tokens in tokenized:
            for term in set(tokens):
                df[term] = df.get(term, 0) + 1

        for term, freq in df.items():
            idx = self._term_id(term)
            self.idf[idx] = math.log((self.num_docs - freq + 0.5) / (freq + 0.5) + 1)

        logger.info(
            "BM25 encoder fitted",
            vocab_size=len(self.vocab),
            num_docs=self.num_docs,
            avgdl=round(self.avgdl, 1),
        )

    def encode_document(self, text: str) -> tuple[list[int], list[float]]:
        tokens = tokenize(text)
        dl = len(tokens)
        tf: dict[str, int] = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1

        indices: list[int] = []
        values: list[float] = []
        for term, freq in tf.items():
            if term not in self.vocab:
                continue
            idx = self.vocab[term]
            idf = self.idf.get(idx, 0.0)
            numerator = freq * (_K1 + 1)
            denominator = freq + _K1 * (1 - _B + _B * dl / max(self.avgdl, 1))
            score = idf * numerator / denominator
            if score > 0.0:
                indices.append(idx)
                values.append(float(score))
        return indices, values

    def encode_query(self, text: str) -> tuple[list[int], list[float]]:
        """IDF-weighted sparse vector for retrieval queries."""
        seen: dict[int, float] = {}
        for token in tokenize(text):
            if token in self.vocab:
                idx = self.vocab[token]
                seen[idx] = self.idf.get(idx, 0.0)
        return list(seen.keys()), list(seen.values())

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "vocab": self.vocab,
                    "idf": {str(k): v for k, v in self.idf.items()},
                    "avgdl": self.avgdl,
                    "num_docs": self.num_docs,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        logger.info("vocabulary saved", path=str(path), vocab_size=len(self.vocab))

    @classmethod
    def load(cls, path: Path) -> BM25SparseEncoder:
        data = json.loads(path.read_text(encoding="utf-8"))
        enc = cls()
        enc.vocab = data["vocab"]
        enc.idf = {int(k): v for k, v in data["idf"].items()}
        enc.avgdl = data["avgdl"]
        enc.num_docs = data["num_docs"]
        return enc
