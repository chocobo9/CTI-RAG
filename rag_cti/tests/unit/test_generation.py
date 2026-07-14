from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from rag_cti.generation.context_builder import build_context_messages, extract_cited_ids
from rag_cti.generation.generator import (
    DEFAULT_CANDIDATE_K,
    Generator,
    _extract_text,
    _format_candidates,
    parse_actor_name,
    parse_technique_ids,
)
from rag_cti.generation.llm_router import LLMRouter, TaskType
from rag_cti.generation.prompts import (
    ACTOR_ATTRIBUTION_SYSTEM,
    TECHNIQUE_ANNOTATION_SYSTEM,
)
from rag_cti.types import Chunk, GeneratedAnswer, QueryResult, RetrievalResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(chunk_id: str = "abc12345", source: str = "mitre") -> Chunk:
    return Chunk(
        id=chunk_id,
        parent_doc_id="doc1",
        source=source,
        content=f"APT group used T1566 spearphishing. chunk={chunk_id}",
        chunk_index=0,
        retrieved_at=datetime(2024, 1, 1),
        embedding_model="bge-m3",
    )


def _make_result(chunk_id: str = "abc12345", score: float = 0.9, rank: int = 0) -> RetrievalResult:
    return RetrievalResult(
        document=_make_chunk(chunk_id),
        score=score,
        rank=rank,
        retriever_source="rrf",
    )


def _make_query_result(results: list[RetrievalResult] | None = None) -> QueryResult:
    r = results if results is not None else [_make_result()]
    return QueryResult(
        query="how does APT29 use spearphishing",
        results=r,
        total_retrieved=len(r),
        retrieval_ms=12.5,
    )


class _FakeSettings:
    ollama_enabled: bool = False
    ollama_model: str = "qwen2.5"
    groq_query_model: str = "llama-3.1-8b-instant"
    groq_analysis_model: str = "llama-3.3-70b-versatile"
    groq_report_model: str = "llama-3.3-70b-versatile"
    generation_max_tokens: int = 512


class _FakeMessage:
    def __init__(self, content: str | None) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str | None) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str | None = "Answer citing [abc12345] for detail.") -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(
        self, response_content: str | None = "Answer citing [abc12345] for detail."
    ) -> None:
        self.last_kwargs: dict[str, Any] = {}
        self._response_content = response_content

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.last_kwargs = kwargs
        if self._response_content is None:
            raise RuntimeError("simulated LLM failure")
        return _FakeResponse(self._response_content)


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeClient:
    def __init__(
        self, response_content: str | None = "Answer citing [abc12345] for detail."
    ) -> None:
        self._completions = _FakeCompletions(response_content)
        self.chat = _FakeChat(self._completions)


# ---------------------------------------------------------------------------
# LLMRouter
# ---------------------------------------------------------------------------


def test_router_hyde_returns_groq_query_model() -> None:
    router = LLMRouter(_FakeSettings())
    assert router.model_for(TaskType.HYDE) == "llama-3.1-8b-instant"


def test_router_analysis_returns_groq_analysis_model() -> None:
    router = LLMRouter(_FakeSettings())
    assert router.model_for(TaskType.ANALYSIS) == "llama-3.3-70b-versatile"


def test_router_report_returns_groq_report_model() -> None:
    router = LLMRouter(_FakeSettings())
    assert router.model_for(TaskType.REPORT) == "llama-3.3-70b-versatile"


def test_router_all_task_types_return_non_empty_string() -> None:
    router = LLMRouter(_FakeSettings())
    for task in TaskType:
        model = router.model_for(task)
        assert isinstance(model, str)
        assert len(model) > 0




# ---------------------------------------------------------------------------
# build_context_messages
# ---------------------------------------------------------------------------


def test_build_context_messages_returns_two_messages() -> None:
    msgs = build_context_messages("test query", [_make_result()])
    assert len(msgs) == 2


def test_build_context_messages_first_is_system() -> None:
    msgs = build_context_messages("test query", [_make_result()])
    assert msgs[0]["role"] == "system"
    assert len(msgs[0]["content"]) > 0


def test_build_context_messages_second_is_user() -> None:
    msgs = build_context_messages("test query", [_make_result()])
    assert msgs[1]["role"] == "user"


def test_build_context_messages_user_contains_query() -> None:
    msgs = build_context_messages("my cti query", [_make_result()])
    assert "my cti query" in msgs[1]["content"]


def test_build_context_messages_user_contains_chunk_id() -> None:
    msgs = build_context_messages("query", [_make_result("deadbeef")])
    assert "deadbeef" in msgs[1]["content"]


def test_build_context_messages_chunk_id_in_json() -> None:
    msgs = build_context_messages("query", [_make_result("deadbeef")])
    user_content = msgs[1]["content"]
    context_json_str = user_content.split("Context chunks:\n", 1)[1]
    data = json.loads(context_json_str)
    assert data[0]["chunk_id"] == "deadbeef"


def test_build_context_messages_empty_results() -> None:
    msgs = build_context_messages("query", [])
    user_content = msgs[1]["content"]
    context_json_str = user_content.split("Context chunks:\n", 1)[1]
    assert json.loads(context_json_str) == []


def test_build_context_messages_multiple_results_all_present() -> None:
    results = [_make_result(f"id{i}") for i in range(3)]
    msgs = build_context_messages("query", results)
    user_content = msgs[1]["content"]
    context_json_str = user_content.split("Context chunks:\n", 1)[1]
    data = json.loads(context_json_str)
    assert len(data) == 3
    assert [d["chunk_id"] for d in data] == ["id0", "id1", "id2"]


def test_build_context_messages_score_rounded_to_4_places() -> None:
    msgs = build_context_messages("query", [_make_result(score=0.123456789)])
    user_content = msgs[1]["content"]
    context_json_str = user_content.split("Context chunks:\n", 1)[1]
    data = json.loads(context_json_str)
    assert data[0]["score"] == round(0.123456789, 4)


def test_build_context_messages_custom_system_prompt() -> None:
    msgs = build_context_messages("query", [], system_prompt="Custom system")
    assert msgs[0]["content"] == "Custom system"


# ---------------------------------------------------------------------------
# extract_cited_ids
# ---------------------------------------------------------------------------


def test_extract_cited_ids_single() -> None:
    assert extract_cited_ids("See [abc123] for details.") == ["abc123"]


def test_extract_cited_ids_multiple() -> None:
    assert extract_cited_ids("[a1] and [b2] confirm this.") == ["a1", "b2"]


def test_extract_cited_ids_deduplicates() -> None:
    assert extract_cited_ids("[x1] repeated [x1] again") == ["x1"]


def test_extract_cited_ids_preserves_order() -> None:
    assert extract_cited_ids("[c3] then [a1] then [b2]") == ["c3", "a1", "b2"]


def test_extract_cited_ids_empty_when_no_citations() -> None:
    assert extract_cited_ids("no citations here") == []


def test_extract_cited_ids_handles_hyphens_and_underscores() -> None:
    assert extract_cited_ids("[chunk-1] and [chunk_2]") == ["chunk-1", "chunk_2"]


def test_extract_cited_ids_handles_markdown_code_links() -> None:
    assert extract_cited_ids("[`fact_abc123`] and [`chunk-1`]") == ["fact_abc123", "chunk-1"]


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


def test_generator_returns_generated_answer() -> None:
    gen = Generator(
        client=_FakeClient(), router=LLMRouter(_FakeSettings()), settings=_FakeSettings()
    )
    result = gen.generate("APT29 spearphishing", _make_query_result())
    assert isinstance(result, GeneratedAnswer)


def test_generator_query_preserved() -> None:
    gen = Generator(
        client=_FakeClient(), router=LLMRouter(_FakeSettings()), settings=_FakeSettings()
    )
    result = gen.generate("APT29 spearphishing", _make_query_result())
    assert result.query == "APT29 spearphishing"


def test_generator_uses_groq_analysis_model() -> None:
    client = _FakeClient()
    gen = Generator(client=client, router=LLMRouter(_FakeSettings()), settings=_FakeSettings())
    gen.generate("APT29 spearphishing", _make_query_result())
    assert client._completions.last_kwargs["model"] == "llama-3.3-70b-versatile"


def test_generator_answer_text_populated() -> None:
    gen = Generator(
        client=_FakeClient("Threat actor used [abc12345] for initial access."),
        router=LLMRouter(_FakeSettings()),
        settings=_FakeSettings(),
    )
    result = gen.generate("query", _make_query_result())
    assert "Threat actor" in result.answer


def test_generator_cited_ids_extracted() -> None:
    gen = Generator(
        client=_FakeClient("Based on [abc12345] and [deadbeef], the actor used T1566."),
        router=LLMRouter(_FakeSettings()),
        settings=_FakeSettings(),
    )
    result = gen.generate("query", _make_query_result())
    assert "abc12345" in result.cited_chunk_ids
    assert "deadbeef" in result.cited_chunk_ids


def test_generator_generation_ms_non_negative() -> None:
    gen = Generator(
        client=_FakeClient(), router=LLMRouter(_FakeSettings()), settings=_FakeSettings()
    )
    result = gen.generate("query", _make_query_result())
    assert result.generation_ms >= 0.0


def test_generator_model_in_result() -> None:
    gen = Generator(
        client=_FakeClient(), router=LLMRouter(_FakeSettings()), settings=_FakeSettings()
    )
    result = gen.generate("query", _make_query_result())
    assert result.model == "llama-3.3-70b-versatile"


def test_generator_query_result_preserved() -> None:
    qr = _make_query_result()
    gen = Generator(
        client=_FakeClient(), router=LLMRouter(_FakeSettings()), settings=_FakeSettings()
    )
    result = gen.generate("query", qr)
    assert result.query_result is qr


def test_generator_llm_failure_returns_error_message() -> None:
    gen = Generator(
        client=_FakeClient(response_content=None),
        router=LLMRouter(_FakeSettings()),
        settings=_FakeSettings(),
    )
    result = gen.generate("query", _make_query_result())
    assert "Unable to generate answer" in result.answer
    assert result.cited_chunk_ids == []


def test_generator_empty_llm_content_returns_error_message() -> None:
    gen = Generator(
        client=_FakeClient(response_content=""),
        router=LLMRouter(_FakeSettings()),
        settings=_FakeSettings(),
    )
    result = gen.generate("query", _make_query_result())
    assert "Unable to generate answer" in result.answer
    assert result.cited_chunk_ids == []


def test_generator_passes_two_messages_to_llm() -> None:
    client = _FakeClient()
    gen = Generator(client=client, router=LLMRouter(_FakeSettings()), settings=_FakeSettings())
    gen.generate("query", _make_query_result())
    assert len(client._completions.last_kwargs["messages"]) == 2


def test_generator_first_message_is_system() -> None:
    client = _FakeClient()
    gen = Generator(client=client, router=LLMRouter(_FakeSettings()), settings=_FakeSettings())
    gen.generate("query", _make_query_result())
    msgs = client._completions.last_kwargs["messages"]
    assert msgs[0]["role"] == "system"


def test_generator_passes_max_tokens_from_settings() -> None:
    client = _FakeClient()
    settings = _FakeSettings()
    settings.generation_max_tokens = 256
    gen = Generator(client=client, router=LLMRouter(settings), settings=settings)
    gen.generate("query", _make_query_result())
    assert client._completions.last_kwargs["max_tokens"] == 256


def test_generator_second_message_is_user_with_query() -> None:
    client = _FakeClient()
    gen = Generator(client=client, router=LLMRouter(_FakeSettings()), settings=_FakeSettings())
    gen.generate("my specific query", _make_query_result())
    msgs = client._completions.last_kwargs["messages"]
    assert msgs[1]["role"] == "user"
    assert "my specific query" in msgs[1]["content"]


# ---------------------------------------------------------------------------
# _extract_text
# ---------------------------------------------------------------------------


def test_extract_text_returns_content() -> None:
    response = _FakeResponse("hello world")
    assert _extract_text(response) == "hello world"


def test_extract_text_returns_empty_string_when_content_is_none() -> None:
    response = _FakeResponse(None)
    assert _extract_text(response) == ""


# ---------------------------------------------------------------------------
# GeneratedAnswer type
# ---------------------------------------------------------------------------


def test_generated_answer_is_frozen() -> None:
    qr = _make_query_result()
    ga = GeneratedAnswer(
        query="q",
        answer="a",
        cited_chunk_ids=["x"],
        query_result=qr,
        generation_ms=10.0,
        model="llama-3.3-70b-versatile",
    )
    with pytest.raises(ValidationError):
        ga.answer = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Tests — tracing integration
# ---------------------------------------------------------------------------


def test_generate_calls_add_trace_metadata_with_expected_keys() -> None:
    client = _FakeClient("Answer citing [abc12345].")
    gen = Generator(client=client, router=LLMRouter(_FakeSettings()), settings=_FakeSettings())
    with patch("rag_cti.generation.generator.add_trace_metadata") as mock_meta:
        gen.generate("APT29 spearphishing", _make_query_result())
    mock_meta.assert_called_once()
    kwargs = mock_meta.call_args.kwargs
    assert "model" in kwargs
    assert "cited_chunk_ids" in kwargs
    assert "generation_ms" in kwargs
    assert "context_chunk_ids" in kwargs


def test_generate_result_unchanged_when_tracing_active() -> None:
    client = _FakeClient("Answer citing [abc12345] for detail.")
    gen = Generator(client=client, router=LLMRouter(_FakeSettings()), settings=_FakeSettings())
    with patch("rag_cti.generation.generator.add_trace_metadata"):
        result = gen.generate("test query", _make_query_result())
    assert result.query == "test query"
    assert "abc12345" in result.cited_chunk_ids
    assert result.generation_ms >= 0.0


# ---------------------------------------------------------------------------
# Phase B — parse_technique_ids (real LLM output styles)
# ---------------------------------------------------------------------------


def test_parse_technique_ids_clean_comma_list() -> None:
    assert parse_technique_ids("T1059.001,T1027") == ["T1059.001", "T1027"]


def test_parse_technique_ids_from_prose_noise() -> None:
    out = "The passage describes PowerShell (T1059.001) and Obfuscated Files T1027."
    assert parse_technique_ids(out) == ["T1059.001", "T1027"]


def test_parse_technique_ids_none_reply_is_empty() -> None:
    assert parse_technique_ids("NONE") == []


def test_parse_technique_ids_empty_output_is_empty() -> None:
    assert parse_technique_ids("") == []


def test_parse_technique_ids_order_preserving_dedupe() -> None:
    # Exact duplicates dropped; parent (T1059) and sub (T1059.001) are distinct IDs.
    assert parse_technique_ids("T1059, T1059.001, T1059, T1071.001") == [
        "T1059",
        "T1059.001",
        "T1071.001",
    ]


def test_parse_technique_ids_ignores_failure_sentinel_text() -> None:
    # _call_llm's failure sentinel has no T-id, so parsing yields nothing.
    assert parse_technique_ids("Unable to generate answer: LLM call failed.") == []


# ---------------------------------------------------------------------------
# Phase B — parse_actor_name (real LLM output styles)
# ---------------------------------------------------------------------------


def test_parse_actor_name_with_spaces_preserved() -> None:
    assert parse_actor_name("Cozy Bear") == "Cozy Bear"


def test_parse_actor_name_strips_quotes_and_markdown() -> None:
    assert parse_actor_name("**Lazarus Group**") == "Lazarus Group"
    assert parse_actor_name('"APT29"') == "APT29"


def test_parse_actor_name_strips_trailing_period() -> None:
    assert parse_actor_name("APT29.") == "APT29"


def test_parse_actor_name_takes_first_nonempty_line() -> None:
    assert parse_actor_name("\n  Sandworm Team  \nalso known as Voodoo Bear") == "Sandworm Team"


def test_parse_actor_name_none_reply_is_empty() -> None:
    assert parse_actor_name("NONE") == ""
    assert parse_actor_name("unknown") == ""


def test_parse_actor_name_empty_output_is_empty() -> None:
    assert parse_actor_name("") == ""


# ---------------------------------------------------------------------------
# Phase B — _format_candidates
# ---------------------------------------------------------------------------


def _make_result_with(
    content: str, attack_id: str | None, source: str, rank: int
) -> RetrievalResult:
    metadata = {"attack_id": attack_id} if attack_id else {}
    chunk = Chunk(
        id=f"c{rank}",
        parent_doc_id="doc1",
        source=source,
        content=content,
        chunk_index=0,
        metadata=metadata,
        retrieved_at=datetime(2024, 1, 1),
        embedding_model="bge-m3",
    )
    return RetrievalResult(
        document=chunk, score=0.9 - rank * 0.1, rank=rank, retriever_source="rrf"
    )


def test_format_candidates_includes_attack_id_and_content() -> None:
    results = [
        _make_result_with("Aquatic Panda uses PowerShell (T1059.001)", "T1059.001", "mitre", 0)
    ]
    out = _format_candidates(results, candidate_k=10)
    assert "attack_id=T1059.001" in out
    assert "source=mitre" in out
    assert "Aquatic Panda" in out


def test_format_candidates_respects_candidate_k() -> None:
    results = [_make_result_with(f"chunk {i} content", "T1059", "mitre", i) for i in range(5)]
    out = _format_candidates(results, candidate_k=2)
    assert out.count("attack_id=") == 2
    assert "[1]" in out
    assert "[2]" in out
    assert "[3]" not in out


def test_format_candidates_missing_attack_id_shown_as_dash() -> None:
    results = [_make_result_with("APT29 phishing campaign", None, "otx", 0)]
    out = _format_candidates(results, candidate_k=10)
    assert "attack_id=-" in out


def test_format_candidates_empty_results() -> None:
    assert _format_candidates([], candidate_k=10) == "(no candidates retrieved)"


# ---------------------------------------------------------------------------
# Phase B — annotate_techniques / attribute_actor methods (mocked client)
# ---------------------------------------------------------------------------


def test_annotate_techniques_returns_parsed_ids() -> None:
    gen = Generator(
        client=_FakeClient("T1059.001, T1027"),
        router=LLMRouter(_FakeSettings()),
        settings=_FakeSettings(),
    )
    ids = gen.annotate_techniques(
        "GLASSTOKEN web shell executes encoded PowerShell", _make_query_result()
    )
    assert ids == ["T1059.001", "T1027"]


def test_annotate_techniques_uses_technique_system_prompt() -> None:
    client = _FakeClient("T1059")
    gen = Generator(client=client, router=LLMRouter(_FakeSettings()), settings=_FakeSettings())
    gen.annotate_techniques("some cti text", _make_query_result())
    msgs = client._completions.last_kwargs["messages"]
    assert msgs[0]["content"] == TECHNIQUE_ANNOTATION_SYSTEM
    assert "some cti text" in msgs[1]["content"]


def test_annotate_techniques_raises_on_llm_failure() -> None:
    gen = Generator(
        client=_FakeClient(response_content=None),
        router=LLMRouter(_FakeSettings()),
        settings=_FakeSettings(),
    )
    with pytest.raises(RuntimeError, match="annotate_techniques"):
        gen.annotate_techniques("cti text", _make_query_result())


def test_attribute_actor_returns_parsed_name() -> None:
    gen = Generator(
        client=_FakeClient("APT29"),
        router=LLMRouter(_FakeSettings()),
        settings=_FakeSettings(),
    )
    actor = gen.attribute_actor(
        "Cozy Bear spearphishing of government entities", _make_query_result()
    )
    assert actor == "APT29"


def test_attribute_actor_uses_actor_system_prompt() -> None:
    client = _FakeClient("Lazarus Group")
    gen = Generator(client=client, router=LLMRouter(_FakeSettings()), settings=_FakeSettings())
    actor = gen.attribute_actor("DPRK financial heist", _make_query_result())
    assert actor == "Lazarus Group"
    assert client._completions.last_kwargs["messages"][0]["content"] == ACTOR_ATTRIBUTION_SYSTEM


def test_attribute_actor_raises_on_llm_failure() -> None:
    gen = Generator(
        client=_FakeClient(response_content=None),
        router=LLMRouter(_FakeSettings()),
        settings=_FakeSettings(),
    )
    with pytest.raises(RuntimeError, match="attribute_actor"):
        gen.attribute_actor("cti text", _make_query_result())


def test_default_candidate_k_is_ten() -> None:
    # SPEC §B.1: inject top-10 reranked candidates.
    assert DEFAULT_CANDIDATE_K == 10
