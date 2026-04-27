from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

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

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr = SecretStr("")
    qdrant_collection: str = "cti_chunks"

    # Embedding
    embedding_model: str = "bge-m3"

    # Retrieval
    retrieval_top_k: int = 10
    hybrid_alpha: float = 0.5  # weight for dense vs sparse (1.0 = pure dense)

    # Generation
    generation_max_tokens: int = 1024

    # LLM tiers (Anthropic — used by HyDE when ANTHROPIC_API_KEY is set)
    llm_routing_model: str = "claude-haiku-4-5-20251001"

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
        has_anthropic = bool(self.anthropic_api_key.get_secret_value())
        has_groq = bool(self.groq_api_key.get_secret_value())
        if not has_anthropic and not has_groq:
            raise ValueError("At least one of ANTHROPIC_API_KEY or GROQ_API_KEY is required")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
