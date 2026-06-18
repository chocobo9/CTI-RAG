from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Ollama (local OpenAI-compatible API). Default off — use GROQ_API_KEY / ANTHROPIC_API_KEY for hosted LLMs.
    ollama_enabled: bool = False
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.1:8b"

    # Anthropic
    anthropic_api_key: SecretStr = SecretStr("")

    # DeepSeek
    deepseek_api_key: SecretStr = SecretStr("")

    # Groq
    groq_api_key: SecretStr = SecretStr("")
    groq_query_model: str = "llama-3.1-8b-instant"
    groq_analysis_model: str = "llama-3.3-70b-versatile"
    groq_report_model: str = "llama-3.3-70b-versatile"

    # Data source API keys
    otx_api_key: SecretStr = SecretStr("")
    # Reserved for the experimental VirusTotal connector — no fetch script
    # consumes it yet (connectors/virustotal.py takes the key directly).
    vt_api_key: SecretStr = SecretStr("")
    whoxy_api_key: SecretStr = SecretStr("")

    # LangSmith
    langsmith_api_key: SecretStr = SecretStr("")
    langsmith_project: str = "rag-cti"
    langchain_tracing_v2: bool = True

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr = SecretStr("")
    qdrant_collection: str = "cti_chunks"

    # Neo4j — CTI-RAG's OWN isolated instance (port 7689), NOT the cti-agent graph
    # on 7687. M4 consumption-layer knowledge-graph backend (DM4-1). See
    # docs/M4_consumption_design.md. Empty password => Neo4j features disabled.
    neo4j_uri: str = "bolt://localhost:7689"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("")
    neo4j_database: str = "neo4j"

    # Embedding (must be a HF repo id or local path; bare "bge-m3" is not valid on the Hub)
    embedding_model: str = "BAAI/bge-m3"

    # Retrieval
    retrieval_top_k: int = 10
    # Dense weight in the weighted-RRF fusion (sparse gets 1 - alpha).
    # 0.5 = symmetric fusion; >= 1.0 skips the sparse retriever (pure dense).
    hybrid_alpha: float = 0.5
    rrf_candidate_multiplier: int = 3

    # Generation — pinned to DeepSeek (same endpoint/key), model-downgrade chain:
    # try generation_models[0] first, fall to the next on a backend failure. Primary
    # deepseek-v4-flash is a reasoning model (spends tokens on reasoning_content), so
    # generation_max_tokens must stay generous. Append more entries to extend the chain.
    generation_max_tokens: int = 1024
    generation_models: list[str] = ["deepseek-v4-flash", "deepseek-chat"]

    # Model for the Anthropic provider: HyDE's Anthropic branch (hyde.py) and
    # LLMRouter when provider == "anthropic". Groq/Ollama use their own fields.
    llm_routing_model: str = "claude-haiku-4-5-20251001"

    # Reranker (hybrid+reranker is the recommended config — see README eval results)
    reranker_enabled: bool = True
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_candidates_k: int = 50
    # 512 truncates 11.4% of chunks (42% of OTX) against the chunker's
    # 600-token target, BUT it is the CERTIFIED value: the 2026-06-11 A/B
    # measured 640 as retrieval-neutral (hit@k unchanged on query_set_v3)
    # while dropping the technique annotator's CTI-ATE Micro-F1 from the
    # 0.653-0.670 band to 0.564 — the truncated tails hurt CrossEncoder
    # ranking more than they help. Keep 512 unless re-certifying.
    reranker_max_length: int = 512

    # Feature flags
    hyde_enabled: bool = True
    hyde_min_query_tokens: int = 5
    hyde_max_tokens: int = 300
    hyde_output_max_chars: int = 2000

    # LLM query rewrite (normalize/decompose/contextualize). Default ON: the
    # four-quadrant A/B (2026-06-16) showed rewrite+HyDE >= HyDE-only on BOTH clean
    # and adversarial technique queries (the clean-set top-1 regression appeared only
    # in the no-HyDE quadrant, which is not the default). Costs one Groq-8b call/query.
    query_rewrite_enabled: bool = True
    query_rewrite_max_subqueries: int = 4
    query_rewrite_max_tokens: int = 300

    # Constraint routing (soft boost). Reuses the query-rewrite LLM call to extract
    # named entities, plus deterministic technique-id / source-type signals, into a
    # PayloadConstraint that *boosts* (never filters) matching results. Decoupled from
    # query_rewrite_enabled: the deterministic signals still route when rewrite is off.
    constraint_routing_enabled: bool = True
    constraint_boost_weight: float = 0.5
    constraint_boost_fetch_multiplier: int = 1

    @field_validator("hybrid_alpha")
    @classmethod
    def validate_alpha(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("hybrid_alpha must be between 0.0 and 1.0")
        return v

    @model_validator(mode="after")
    def validate_required_secrets(self) -> Settings:
        """HyDE / query-rewrite / generation need an LLM; pure retrieval does not."""
        if not self.hyde_enabled and not self.query_rewrite_enabled:
            return self
        has_ollama = self.ollama_enabled
        has_anthropic = bool(self.anthropic_api_key.get_secret_value())
        has_groq = bool(self.groq_api_key.get_secret_value())
        if not has_ollama and not has_anthropic and not has_groq:
            raise ValueError(
                "HyDE/query-rewrite is enabled but no LLM provider is configured: "
                "set GROQ_API_KEY, ANTHROPIC_API_KEY, or OLLAMA_ENABLED=true for local Ollama, "
                "or disable HYDE_ENABLED / QUERY_REWRITE_ENABLED for retrieval-only."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
