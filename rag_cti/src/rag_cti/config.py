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

    # Groq
    groq_api_key: SecretStr = SecretStr("")
    groq_query_model: str = "llama-3.1-8b-instant"
    groq_analysis_model: str = "llama-3.3-70b-versatile"
    groq_report_model: str = "llama-3.3-70b-versatile"

    # Data source API keys
    otx_api_key: SecretStr = SecretStr("")
    vt_api_key: SecretStr = SecretStr("")

    # LangSmith
    langsmith_api_key: SecretStr = SecretStr("")
    langsmith_project: str = "rag-cti"
    langchain_tracing_v2: bool = True

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr = SecretStr("")
    qdrant_collection: str = "cti_chunks"

    # Embedding (must be a HF repo id or local path; bare "bge-m3" is not valid on the Hub)
    embedding_model: str = "BAAI/bge-m3"

    # Retrieval
    retrieval_top_k: int = 10
    hybrid_alpha: float = 0.5  # weight for dense vs sparse (1.0 = pure dense)
    rrf_candidate_multiplier: int = 3

    # Generation
    generation_max_tokens: int = 1024

    # LLM tiers (Anthropic — used by HyDE when ANTHROPIC_API_KEY is set)
    llm_routing_model: str = "claude-haiku-4-5-20251001"

    # Reranker
    reranker_enabled: bool = False
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_candidates_k: int = 50

    # Feature flags
    hyde_enabled: bool = True
    hyde_min_query_tokens: int = 5

    @field_validator("hybrid_alpha")
    @classmethod
    def validate_alpha(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("hybrid_alpha must be between 0.0 and 1.0")
        return v

    @model_validator(mode="after")
    def validate_required_secrets(self) -> Settings:
        """HyDE / generation need an LLM; pure retrieval (query) does not when HyDE is off."""
        if not self.hyde_enabled:
            return self
        has_ollama = self.ollama_enabled
        has_anthropic = bool(self.anthropic_api_key.get_secret_value())
        has_groq = bool(self.groq_api_key.get_secret_value())
        if not has_ollama and not has_anthropic and not has_groq:
            raise ValueError(
                "HyDE is enabled but no LLM provider is configured: "
                "set GROQ_API_KEY, ANTHROPIC_API_KEY, or OLLAMA_ENABLED=true for local Ollama, "
                "or set HYDE_ENABLED=false for retrieval-only."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
