from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from rag_cti.retrieval.hyde import HyDERetriever
from rag_cti.types import Chunk, RetrievalResult

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


def _make_result(score: float = 0.9) -> RetrievalResult:
    chunk = Chunk(
        id="abc123",
        parent_doc_id="doc1",
        source="mitre",
        content="APT group used spearphishing T1566.001",
        chunk_index=0,
        retrieved_at=datetime(2024, 1, 1),
        embedding_model="test-model",
    )
    return RetrievalResult(document=chunk, score=score, rank=0, retriever_source="qdrant_dense")


class _FakeSettings:
    def __init__(
        self,
        hyde_enabled: bool = True,
        hyde_min_query_tokens: int = 5,
        groq_query_model: str = "llama-3.1-8b-instant",
    ) -> None:
        self.hyde_enabled = hyde_enabled
        self.hyde_min_query_tokens = hyde_min_query_tokens
        self.groq_query_model = groq_query_model


class _FakeContent:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeMessagesResponse:
    def __init__(self, text: str) -> None:
        self.content = [_FakeContent(text)]


class _FakeLLMClient:
    def __init__(
        self, response_text: str | None = "Hypothetical CTI passage about the query."
    ) -> None:
        self.last_call: dict = {}
        self._response_text = response_text
        self.chat = SimpleNamespace(completions=self)

    def create(self, model: str, max_tokens: int, messages: list) -> object:
        self.last_call = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if self._response_text is None:
            raise RuntimeError("simulated LLM failure")
        message = SimpleNamespace(content=self._response_text)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class _FakeBaseRetriever:
    def __init__(self, results: list[RetrievalResult] | None = None) -> None:
        self.last_query: str = ""
        self.last_top_k: int = 0
        self.last_source_filter = None
        self.last_sparse_query: str | None = None
        self._results = results or []

    def search(
        self,
        query: str,
        top_k: int = 10,
        source_filter=None,
        sparse_query: str | None = None,
        constraint=None,
    ) -> list[RetrievalResult]:
        self.last_query = query
        self.last_top_k = top_k
        self.last_source_filter = source_filter
        self.last_sparse_query = sparse_query
        self.last_constraint = constraint
        return self._results


# ---------------------------------------------------------------------------
# Tests — bypass conditions
# ---------------------------------------------------------------------------


def test_bypasses_when_hyde_disabled() -> None:
    base = _FakeBaseRetriever()
    llm = _FakeLLMClient()
    retriever = HyDERetriever(base, llm, _FakeSettings(hyde_enabled=False))
    retriever.search("how does ransomware encrypt files on the network")
    assert base.last_query == "how does ransomware encrypt files on the network"
    assert llm.last_call == {}


def test_bypasses_when_query_too_short() -> None:
    base = _FakeBaseRetriever()
    llm = _FakeLLMClient()
    retriever = HyDERetriever(base, llm, _FakeSettings(hyde_min_query_tokens=5))
    retriever.search("ransomware lateral")  # 2 tokens
    assert base.last_query == "ransomware lateral"
    assert llm.last_call == {}


def test_bypasses_when_query_one_below_min() -> None:
    base = _FakeBaseRetriever()
    llm = _FakeLLMClient()
    retriever = HyDERetriever(base, llm, _FakeSettings(hyde_min_query_tokens=5))
    retriever.search("one two three four")  # 4 tokens, min=5
    assert llm.last_call == {}


def test_uses_hyde_when_query_meets_min_tokens() -> None:
    base = _FakeBaseRetriever()
    llm = _FakeLLMClient("Threat actor used T1566 for initial access via email.")
    retriever = HyDERetriever(base, llm, _FakeSettings(hyde_min_query_tokens=5))
    retriever.search("one two three four five")  # 5 tokens
    assert llm.last_call != {}
    assert base.last_query == "Threat actor used T1566 for initial access via email."


# ---------------------------------------------------------------------------
# Tests — LLM call correctness
# ---------------------------------------------------------------------------


def test_llm_called_with_correct_model() -> None:
    base = _FakeBaseRetriever()
    llm = _FakeLLMClient()
    retriever = HyDERetriever(base, llm, _FakeSettings())
    retriever.search("how does APT group use spearphishing for initial access")
    assert llm.last_call["model"] == "llama-3.1-8b-instant"


def test_llm_called_with_max_tokens_300() -> None:
    base = _FakeBaseRetriever()
    llm = _FakeLLMClient()
    retriever = HyDERetriever(base, llm, _FakeSettings())
    retriever.search("how does APT group use spearphishing for initial access")
    assert llm.last_call["max_tokens"] == 300


def test_llm_user_message_is_the_query() -> None:
    base = _FakeBaseRetriever()
    llm = _FakeLLMClient()
    retriever = HyDERetriever(base, llm, _FakeSettings())
    query = "how does APT group use spearphishing for initial access"
    retriever.search(query)
    assert llm.last_call["messages"][1]["content"] == query


def test_llm_system_prompt_is_set() -> None:
    base = _FakeBaseRetriever()
    llm = _FakeLLMClient()
    retriever = HyDERetriever(base, llm, _FakeSettings())
    retriever.search("how does APT group use spearphishing for initial access")
    assert llm.last_call["messages"][0]["role"] == "system"
    assert len(llm.last_call["messages"][0]["content"]) > 0


def test_llm_failure_falls_back_to_direct_query() -> None:
    base = _FakeBaseRetriever()
    llm = _FakeLLMClient(response_text=None)  # will raise
    retriever = HyDERetriever(base, llm, _FakeSettings())
    query = "how does APT group use spearphishing for initial access"
    retriever.search(query)
    assert base.last_query == query


# ---------------------------------------------------------------------------
# Tests — result passthrough
# ---------------------------------------------------------------------------


def test_returns_base_retriever_results() -> None:
    expected = [_make_result(0.9), _make_result(0.7)]
    base = _FakeBaseRetriever(expected)
    retriever = HyDERetriever(base, _FakeLLMClient(), _FakeSettings())
    assert retriever.search("how does APT group use credential dumping attacks") == expected


def test_passes_top_k_to_base() -> None:
    base = _FakeBaseRetriever()
    retriever = HyDERetriever(base, _FakeLLMClient(), _FakeSettings())
    retriever.search("how does APT group use credential dumping attacks", top_k=5)
    assert base.last_top_k == 5


def test_passes_source_filter_to_base() -> None:
    base = _FakeBaseRetriever()
    retriever = HyDERetriever(base, _FakeLLMClient(), _FakeSettings())
    retriever.search("how does APT group use credential dumping attacks", source_filter="mitre")
    assert base.last_source_filter == "mitre"


def test_bypass_passes_top_k_and_filter() -> None:
    base = _FakeBaseRetriever()
    retriever = HyDERetriever(base, _FakeLLMClient(), _FakeSettings(hyde_enabled=False))
    retriever.search("short query", top_k=3, source_filter=["mitre", "otx"])
    assert base.last_top_k == 3
    assert base.last_source_filter == ["mitre", "otx"]


# ---------------------------------------------------------------------------
# Groq provider stubs
# ---------------------------------------------------------------------------


class _FakeGroqMessage:
    def __init__(self, text: str) -> None:
        self.content = text


class _FakeGroqChoice:
    def __init__(self, text: str) -> None:
        self.message = _FakeGroqMessage(text)


class _FakeGroqResponse:
    def __init__(self, text: str) -> None:
        self.choices = [_FakeGroqChoice(text)]


class _FakeGroqCompletions:
    def __init__(self, response_text: str | None) -> None:
        self.last_call: dict = {}
        self._response_text = response_text

    def create(self, model: str, max_tokens: int, messages: list) -> _FakeGroqResponse:
        self.last_call = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if self._response_text is None:
            raise RuntimeError("simulated Groq failure")
        return _FakeGroqResponse(self._response_text)


class _FakeGroqClient:
    def __init__(self, response_text: str | None = "Groq CTI passage about the query.") -> None:
        self.chat = type("_Chat", (), {"completions": _FakeGroqCompletions(response_text)})()

    @property
    def _completions(self) -> _FakeGroqCompletions:
        return self.chat.completions  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Tests — Groq provider
# ---------------------------------------------------------------------------


def test_groq_provider_calls_chat_completions() -> None:
    base = _FakeBaseRetriever()
    groq = _FakeGroqClient()
    retriever = HyDERetriever(base, groq, _FakeSettings(), llm_provider="groq")
    retriever.search("how does APT group use spearphishing for initial access")
    assert groq._completions.last_call != {}


def test_groq_provider_uses_groq_query_model() -> None:
    base = _FakeBaseRetriever()
    groq = _FakeGroqClient()
    retriever = HyDERetriever(
        base, groq, _FakeSettings(groq_query_model="llama-3.1-8b-instant"), llm_provider="groq"
    )
    retriever.search("how does APT group use spearphishing for initial access")
    assert groq._completions.last_call["model"] == "llama-3.1-8b-instant"


def test_groq_provider_system_prompt_in_messages() -> None:
    base = _FakeBaseRetriever()
    groq = _FakeGroqClient()
    retriever = HyDERetriever(base, groq, _FakeSettings(), llm_provider="groq")
    retriever.search("how does APT group use spearphishing for initial access")
    msgs = groq._completions.last_call["messages"]
    assert msgs[0]["role"] == "system"
    assert len(msgs[0]["content"]) > 0
    assert msgs[1]["role"] == "user"


def test_groq_provider_failure_falls_back_to_direct_query() -> None:
    base = _FakeBaseRetriever()
    groq = _FakeGroqClient(response_text=None)
    retriever = HyDERetriever(base, groq, _FakeSettings(), llm_provider="groq")
    query = "how does APT group use spearphishing for initial access"
    retriever.search(query)
    assert base.last_query == query


# ---------------------------------------------------------------------------
# Tests — tracing integration
# ---------------------------------------------------------------------------


def test_search_result_unchanged_when_traced_decorator_active() -> None:
    expected = [_make_result(0.9), _make_result(0.7)]
    base = _FakeBaseRetriever(expected)
    groq = _FakeGroqClient("Hypothetical CTI passage about spearphishing.")
    retriever = HyDERetriever(base, groq, _FakeSettings(), llm_provider="groq")
    with patch("rag_cti.retrieval.hyde.traced", side_effect=lambda *a, **kw: lambda f: f):
        results = retriever.search("how does APT group use spearphishing for initial access")
    assert results == expected


def test_generate_hypothetical_doc_called_through_tracing_noop() -> None:
    base = _FakeBaseRetriever()
    groq = _FakeGroqClient("A hypothetical threat intelligence passage.")
    retriever = HyDERetriever(base, groq, _FakeSettings(), llm_provider="groq")
    retriever.search("how does APT group use spearphishing for initial access")
    assert base.last_query == "A hypothetical threat intelligence passage."


# ---------------------------------------------------------------------------
# Tests — HyDE query routing (sparse gets original query)
# ---------------------------------------------------------------------------


def test_hyde_passes_original_query_as_sparse_query() -> None:
    """BM25 must receive the original query, not the hypothetical document."""
    base = _FakeBaseRetriever()
    llm = _FakeLLMClient("Hypothetical passage about CVE exploitation in the wild.")
    query = "CVE-2023-34362 affected products and exploitation details"
    retriever = HyDERetriever(base, llm, _FakeSettings())
    retriever.search(query)
    assert base.last_sparse_query == query
    assert "CVE-2023-34362" in base.last_sparse_query


def test_hyde_passes_hypothetical_doc_as_main_query() -> None:
    """Dense retriever must receive the hypothetical document."""
    base = _FakeBaseRetriever()
    hypothetical = "The CVE-2023-34362 vulnerability in MOVEit Transfer allows unauthenticated RCE."
    llm = _FakeLLMClient(hypothetical)
    retriever = HyDERetriever(base, llm, _FakeSettings())
    retriever.search("CVE-2023-34362 affected products and exploitation details")
    assert base.last_query == hypothetical


def test_hyde_bypass_does_not_set_sparse_query() -> None:
    """When HyDE is disabled, sparse_query should not be set."""
    base = _FakeBaseRetriever()
    retriever = HyDERetriever(base, _FakeLLMClient(), _FakeSettings(hyde_enabled=False))
    retriever.search("how does ransomware encrypt files on the network")
    assert base.last_sparse_query is None


def test_hyde_fallback_on_llm_failure_does_not_set_sparse_query() -> None:
    """When LLM fails, search_query equals original query, so sparse_query is still passed."""
    base = _FakeBaseRetriever()
    llm = _FakeLLMClient(response_text=None)
    query = "APT28 commonly used TTPs for lateral movement"
    retriever = HyDERetriever(base, llm, _FakeSettings())
    retriever.search(query)
    assert base.last_query == query
    assert base.last_sparse_query == query
