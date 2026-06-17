from __future__ import annotations

from rag_cti.retrieval.query_normalize import (
    is_pure_ioc,
    prepare,
    protect_iocs,
    refang,
    restore_iocs,
)

_SHA256 = "a" * 64


def test_refang_restores_canonical_forms() -> None:
    assert refang("hxxps://evil[.]com") == "https://evil.com"
    assert refang("hxxp://bad[.]net/x") == "http://bad.net/x"
    assert refang("user[at]evil[dot]com") == "user@evil.com"
    assert refang("1[.]2[.]3[.]4") == "1.2.3.4"


def test_protect_restore_round_trip_keeps_ioc_verbatim() -> None:
    text = f"what malware drops {_SHA256} on 1.2.3.4"
    protected, mapping = protect_iocs(text)
    # the hash and ip are gone from the text the LLM sees
    assert _SHA256 not in protected
    assert "1.2.3.4" not in protected
    assert len(mapping) == 2
    # restoring brings them back exactly (a "corrected" hash would be silently wrong)
    assert restore_iocs(protected, mapping) == text


def test_prepare_refangs_then_protects_the_canonical_ioc() -> None:
    protected, mapping = prepare("c2 at evil[.]com and hash " + _SHA256)
    assert "evil.com" in mapping.values()  # refanged before protect
    assert _SHA256 in mapping.values()
    assert "<IOC_1>" in protected
    assert "<IOC_2>" in protected


def test_prepare_uppercases_attack_ids() -> None:
    # t1566 -> T1566 (then protected, since _IOC_RE matches T####)
    _, mapping = prepare("how is t1566 used")
    assert "T1566" in mapping.values()


def test_is_pure_ioc() -> None:
    assert is_pure_ioc("1.2.3.4") is True
    assert is_pure_ioc("evil[.]com") is True  # refanged then all-IOC
    assert is_pure_ioc(_SHA256) is True
    assert is_pure_ioc("what does evil.com resolve to") is False
    assert is_pure_ioc("lateral movement techniques") is False


def test_restore_is_noop_without_placeholders() -> None:
    assert restore_iocs("plain query", {}) == "plain query"
