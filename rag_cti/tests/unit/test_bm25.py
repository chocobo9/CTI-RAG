from __future__ import annotations

import json
from pathlib import Path

import pytest

from rag_cti.retrieval.bm25 import BM25SparseEncoder, tokenize

# ---------------------------------------------------------------------------
# tokenize
# ---------------------------------------------------------------------------

def test_tokenize_preserves_ipv4() -> None:
    tokens = tokenize("Traffic from 192.168.1.1 detected")
    assert "192.168.1.1" in tokens


def test_tokenize_preserves_cidr() -> None:
    tokens = tokenize("block subnet 10.0.0.0/8 now")
    assert "10.0.0.0/8" in tokens


def test_tokenize_preserves_cve() -> None:
    tokens = tokenize("exploiting CVE-2021-44228 in the wild")
    assert "cve-2021-44228" in tokens


def test_tokenize_preserves_attck_technique() -> None:
    tokens = tokenize("technique T1566.001 phishing")
    assert "t1566.001" in tokens


def test_tokenize_preserves_sha256() -> None:
    sha = "a" * 64
    tokens = tokenize(f"hash {sha} found")
    assert sha in tokens


def test_tokenize_preserves_domain() -> None:
    tokens = tokenize("beacon to evil.com observed")
    assert "evil.com" in tokens


def test_tokenize_splits_prose() -> None:
    tokens = tokenize("malware used lateral movement")
    assert "malware" in tokens
    assert "lateral" in tokens
    assert "movement" in tokens


def test_tokenize_drops_single_chars() -> None:
    tokens = tokenize("a b c malware")
    assert "a" not in tokens
    assert "b" not in tokens
    assert "malware" in tokens


def test_tokenize_lowercases_prose() -> None:
    tokens = tokenize("Ransomware Attack")
    assert "ransomware" in tokens
    assert "attack" in tokens


def test_tokenize_empty_string() -> None:
    assert tokenize("") == []


@pytest.mark.parametrize(
    "ip_token",
    [
        "0.0.0.0",
        "192.168.1.254",
        "255.255.255.255",
        "10.0.0.0/8",
        "172.16.0.0/32",
    ],
)
def test_tokenize_ipv4_strict_octets_accepted(ip_token: str) -> None:
    tokens = tokenize(f"src {ip_token} dst")
    assert ip_token.lower() in tokens


@pytest.mark.parametrize(
    "bogus_ip",
    [
        "256.1.2.3",
        "1.866.320.478",
        "999.1.2.3",
        "192.168.300.1",
    ],
)
def test_tokenize_ipv4_strict_octets_rejected_as_single_token(bogus_ip: str) -> None:
    tokens = tokenize(f"x {bogus_ip} y")
    assert bogus_ip.lower() not in tokens


def test_tokenize_ipv4_invalid_mask_splits_remainder() -> None:
    """Mask >32 must not attach to IPv4 IOC token."""
    tokens = tokenize("route 10.0.0.0/33 blocked")
    assert "10.0.0.0" in tokens
    assert "10.0.0.0/33" not in tokens


def test_tokenize_ligature_confi_maps_to_ascii_word() -> None:
    tokens = tokenize("remain con\uFB01dent under pressure")
    assert "confident" in tokens


def test_tokenize_accent_preservation_french() -> None:
    tokens = tokenize("discussion au café ce matin")
    assert any("caf" in t for t in tokens)


def test_tokenize_prose_drops_overlong_token_keeps_sha256() -> None:
    long_word = "a" * 65
    sha = "f" * 64
    tokens = tokenize(f"{long_word} hash {sha} end")
    assert long_word.lower() not in tokens
    assert sha in tokens


# ---------------------------------------------------------------------------
# BM25SparseEncoder.fit
# ---------------------------------------------------------------------------

def test_fit_sets_num_docs() -> None:
    enc = BM25SparseEncoder()
    enc.fit(["hello world", "foo bar"])
    assert enc.num_docs == 2


def test_fit_builds_vocab() -> None:
    enc = BM25SparseEncoder()
    enc.fit(["malware ransomware", "ransomware lateral"])
    assert "malware" in enc.vocab
    assert "ransomware" in enc.vocab
    assert "lateral" in enc.vocab


def test_fit_computes_avgdl() -> None:
    enc = BM25SparseEncoder()
    enc.fit(["one two", "three four five"])
    # doc lengths: 2, 3 → avg 2.5
    assert enc.avgdl == pytest.approx(2.5)


def test_fit_empty_corpus() -> None:
    enc = BM25SparseEncoder()
    enc.fit([])
    assert enc.num_docs == 0
    assert enc.avgdl == 0.0


# ---------------------------------------------------------------------------
# BM25SparseEncoder.encode_document
# ---------------------------------------------------------------------------

def _fitted_encoder(corpus: list[str] | None = None) -> BM25SparseEncoder:
    enc = BM25SparseEncoder()
    enc.fit(corpus or ["malware ransomware lateral movement", "phishing credential theft"])
    return enc


def test_encode_document_returns_nonempty_for_known_term() -> None:
    enc = _fitted_encoder()
    indices, values = enc.encode_document("malware detected")
    assert len(indices) > 0
    assert len(values) == len(indices)


def test_encode_document_ignores_oov_terms() -> None:
    enc = _fitted_encoder()
    indices, values = enc.encode_document("xyzzy_not_in_vocab")
    assert indices == []
    assert values == []


def test_encode_document_scores_are_positive() -> None:
    enc = _fitted_encoder()
    _, values = enc.encode_document("malware ransomware")
    assert all(v > 0 for v in values)


def test_encode_document_empty_string() -> None:
    enc = _fitted_encoder()
    indices, values = enc.encode_document("")
    assert indices == []
    assert values == []


# ---------------------------------------------------------------------------
# BM25SparseEncoder.encode_query
# ---------------------------------------------------------------------------

def test_encode_query_returns_idf_weights() -> None:
    enc = _fitted_encoder()
    indices, values = enc.encode_query("malware")
    assert len(indices) == 1
    assert values[0] > 0


def test_encode_query_deduplicates_repeated_terms() -> None:
    enc = _fitted_encoder()
    indices, _ = enc.encode_query("malware malware malware")
    assert len(indices) == len(set(indices))


def test_encode_query_oov_returns_empty() -> None:
    enc = _fitted_encoder()
    indices, values = enc.encode_query("completely_unknown_xyzzy")
    assert indices == []
    assert values == []


# ---------------------------------------------------------------------------
# BM25SparseEncoder.save / load roundtrip
# ---------------------------------------------------------------------------

def test_save_load_roundtrip(tmp_path: Path) -> None:
    vocab_path = tmp_path / "sparse_vocab.json"
    enc = _fitted_encoder()
    enc.save(vocab_path)

    loaded = BM25SparseEncoder.load(vocab_path)
    assert loaded.vocab == enc.vocab
    assert loaded.num_docs == enc.num_docs
    assert loaded.avgdl == pytest.approx(enc.avgdl)
    assert set(loaded.idf.keys()) == set(enc.idf.keys())


def test_save_creates_parent_dirs(tmp_path: Path) -> None:
    vocab_path = tmp_path / "nested" / "dir" / "vocab.json"
    enc = _fitted_encoder()
    enc.save(vocab_path)
    assert vocab_path.exists()


def test_save_writes_valid_json(tmp_path: Path) -> None:
    vocab_path = tmp_path / "vocab.json"
    enc = _fitted_encoder()
    enc.save(vocab_path)
    data = json.loads(vocab_path.read_text(encoding="utf-8"))
    assert "vocab" in data
    assert "idf" in data
    assert "avgdl" in data
    assert "num_docs" in data


def test_load_restores_encode_query_output(tmp_path: Path) -> None:
    vocab_path = tmp_path / "vocab.json"
    enc = _fitted_encoder()
    enc.save(vocab_path)

    loaded = BM25SparseEncoder.load(vocab_path)
    idx_orig, val_orig = enc.encode_query("malware")
    idx_load, val_load = loaded.encode_query("malware")
    assert idx_orig == idx_load
    assert val_orig == pytest.approx(val_load)
