"""Unit tests for indicator typing (ingestion §5, Rule 0 type preservation)."""

from __future__ import annotations

from rag_cti.preprocess.indicators import (
    CANONICAL_TYPES,
    IndicatorMention,
    canonical_indicator_type,
    indicator_mentions,
)


def test_known_otx_types_map_to_canonical():
    assert canonical_indicator_type("FileHash-SHA256") == "hash-sha256"
    assert canonical_indicator_type("FileHash-MD5") == "hash-md5"
    assert canonical_indicator_type("FileHash-SHA1") == "hash-sha1"
    assert canonical_indicator_type("domain") == "domain"
    assert canonical_indicator_type("URL") == "url"
    assert canonical_indicator_type("IPv4") == "ipv4"
    assert canonical_indicator_type("email") == "email"
    # hostname/URI join the same class as domain/url
    assert canonical_indicator_type("hostname") == "domain"
    assert canonical_indicator_type("URI") == "url"


def test_all_mapped_canonicals_are_in_controlled_set():
    for src in ("FileHash-SHA256", "domain", "URL", "IPv4", "email"):
        assert canonical_indicator_type(src) in CANONICAL_TYPES


def test_unmapped_types_preserved_verbatim_with_null_canonical():
    # These real OTX types have no canonical equivalent — kept, not dropped.
    for src in ("BitcoinAddress", "FilePath", "Mutex", "CVE", "YARA", "CIDR", "SSLCertFingerprint"):
        assert canonical_indicator_type(src) is None


def test_indicator_mentions_preserves_type_and_value():
    raw = [
        {"indicator": "evil.com", "type": "domain"},
        {"indicator": "abc123", "type": "FileHash-SHA256"},
        {"indicator": "host.evil.com", "type": "hostname"},
    ]
    mentions = indicator_mentions(raw)
    assert mentions == [
        IndicatorMention("evil.com", "domain", "domain"),
        IndicatorMention("abc123", "FileHash-SHA256", "hash-sha256"),
        IndicatorMention("host.evil.com", "hostname", "domain"),  # hostname joins domain class
    ]


def test_indicator_mentions_skips_empty_values():
    raw = [
        {"indicator": "", "type": "domain"},
        {"type": "domain"},  # no indicator key
        {"indicator": "keep.com", "type": "domain"},
    ]
    mentions = indicator_mentions(raw)
    assert [m.value for m in mentions] == ["keep.com"]


def test_indicator_mention_to_dict():
    m = IndicatorMention("host.x", "hostname", None)
    assert m.to_dict() == {"value": "host.x", "type": "hostname", "canonical_type": None}
