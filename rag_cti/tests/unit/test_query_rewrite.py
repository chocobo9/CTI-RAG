from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from rag_cti.retrieval.query_rewrite import LLMQueryRewriter, QueryRewriteRetriever
from rag_cti.types import Chunk, RetrievalResult

_SHA256 = "b" * 64


def _settings(**over: Any) -> Any:
    base = {"query_rewrite_enabled": True, "query_rewrite_max_subqueries": 4}
    base.update(over)
    return SimpleNamespace(**base)


def _rewriter(
    canned: str | None, settings: Any | None = None
) -> tuple[LLMQueryRewriter, list[str]]:
    """A rewriter whose LLM returns ``canned``; captures the user prompts it saw."""
    rw = LLMQueryRewriter(llm_client=object(), settings=settings or _settings())
    seen: list[str] = []

    def fake_generate(system: str, user: str) -> str | None:
        seen.append(user)
        return canned

    rw._generate_raw = fake_generate  # type: ignore[method-assign]
    return rw, seen


def test_disabled_returns_original_without_llm() -> None:
    rw, seen = _rewriter('["should not be used"]', _settings(query_rewrite_enabled=False))
    assert rw.rewrite("messy quary") == ["messy quary"]
    assert seen == []  # LLM not called


def test_pure_ioc_skips_llm_and_refangs() -> None:
    rw, seen = _rewriter('["nope"]')
    assert rw.rewrite("evil[.]com") == ["evil.com"]
    assert seen == []  # bare IOC lookup never hits the LLM


def test_single_query_passthrough() -> None:
    rw, _ = _rewriter('["what persistence does APT29 use"]')
    assert rw.rewrite("waht persistnce APT 29") == ["what persistence does APT29 use"]


def test_compound_query_decomposes() -> None:
    rw, _ = _rewriter('["techniques APT29 uses", "who does APT29 target"]')
    out = rw.rewrite("what does APT29 use and who do they target")
    assert out == ["techniques APT29 uses", "who does APT29 target"]


def test_history_is_included_in_prompt() -> None:
    rw, seen = _rewriter('["who does APT29 target"]')
    rw.rewrite("and who do they target", history=["what techniques does APT29 use"])
    assert "what techniques does APT29 use" in seen[0]
    assert "Conversation so far" in seen[0]


def test_ioc_placeholder_restored() -> None:
    rw, _ = _rewriter('["malware dropping <IOC_1>"]')
    out = rw.rewrite(f"waht malware drops {_SHA256}")
    assert out == [f"malware dropping {_SHA256}"]  # hash verbatim, not LLM-mangled


def test_dropped_ioc_placeholder_falls_back() -> None:
    # query had an IOC but the model dropped the placeholder -> can't reinsert -> fallback
    rw, _ = _rewriter('["generic malware question"]')
    q = f"what drops {_SHA256}"
    assert rw.rewrite(q) == [q]


def test_json_parse_failure_falls_back() -> None:
    rw, _ = _rewriter("this is not json at all")
    assert rw.rewrite("some query") == ["some query"]


def test_markdown_fence_is_stripped() -> None:
    rw, _ = _rewriter('```json\n["clean query"]\n```')
    assert rw.rewrite("dirty") == ["clean query"]


def test_empty_llm_output_falls_back() -> None:
    rw, _ = _rewriter(None)
    assert rw.rewrite("q") == ["q"]


def test_max_subqueries_cap() -> None:
    rw, _ = _rewriter('["a","b","c","d","e","f"]', _settings(query_rewrite_max_subqueries=3))
    assert rw.rewrite("multi") == ["a", "b", "c"]


# --- QueryRewriteRetriever wrapper (fanout + RRF fusion) ---


def _res(cid: str, rank: int, score: float) -> RetrievalResult:
    chunk = Chunk(id=cid, parent_doc_id="d", source="s", content="c", chunk_index=0)
    return RetrievalResult(document=chunk, score=score, rank=rank, retriever_source="x")


class _FakeBase:
    def __init__(self, by_query: dict[str, list[RetrievalResult]]) -> None:
        self._by_query = by_query
        self.calls: list[str] = []

    def search(self, query: str, top_k: int = 10, **_: Any) -> list[RetrievalResult]:
        self.calls.append(query)
        return self._by_query.get(query, [])


class _FakeRewriter:
    def __init__(self, subs: list[str]) -> None:
        self._subs = subs
        self.history_seen: list[str] | None = "unset"  # type: ignore[assignment]

    def rewrite(self, query: str, history: list[str] | None = None) -> list[str]:
        self.history_seen = history
        return self._subs


def test_single_subquery_is_passthrough() -> None:
    base = _FakeBase({"clean q": [_res("A", 0, 0.9)]})
    wrap = QueryRewriteRetriever(base, _FakeRewriter(["clean q"]))  # type: ignore[arg-type]
    out = wrap.search("dirty q", top_k=10)
    assert [r.document.id for r in out] == ["A"]
    assert base.calls == ["clean q"]  # base saw the rewritten query


def test_multi_subquery_fans_out_and_fuses() -> None:
    base = _FakeBase(
        {
            "q1": [_res("A", 0, 0.9), _res("B", 1, 0.5)],
            "q2": [_res("B", 0, 0.8), _res("C", 1, 0.4)],
        }
    )
    wrap = QueryRewriteRetriever(base, _FakeRewriter(["q1", "q2"]))  # type: ignore[arg-type]
    out = wrap.search("compound", top_k=10)
    ids = [r.document.id for r in out]
    assert set(ids) == {"A", "B", "C"}  # deduped union
    assert ids[0] == "B"  # B ranked in both -> highest fused score
    assert base.calls == ["q1", "q2"]


def test_history_passed_to_rewriter() -> None:
    base = _FakeBase({"q": [_res("A", 0, 0.9)]})
    rw = _FakeRewriter(["q"])
    wrap = QueryRewriteRetriever(base, rw)  # type: ignore[arg-type]
    wrap.search("follow up", top_k=5, history=["prior turn"])
    assert rw.history_seen == ["prior turn"]
