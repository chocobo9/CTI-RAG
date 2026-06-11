from __future__ import annotations

from enum import Enum

from rag_cti.types import SettingsProto


class TaskType(Enum):
    HYDE = "hyde"
    ANALYSIS = "analysis"
    REPORT = "report"


class LLMRouter:
    """Config-driven model selector.

    When ``ollama_enabled``: one ``ollama_model`` for all tasks.
    When ``provider == "anthropic"``: ``llm_routing_model`` for all tasks —
    the Groq tier fields hold Groq model names an Anthropic client cannot use.
    Otherwise (Groq): tiered — HyDE uses ``groq_query_model`` (default
    ``llama-3.1-8b-instant``).
    """

    def __init__(self, settings: SettingsProto, provider: str = "") -> None:
        self._settings = settings
        self._provider = provider

    def model_for(self, task: TaskType) -> str:
        if self._settings.ollama_enabled:
            return self._settings.ollama_model
        if self._provider == "anthropic":
            return self._settings.llm_routing_model
        if task == TaskType.HYDE:
            return self._settings.groq_query_model
        if task == TaskType.ANALYSIS:
            return self._settings.groq_analysis_model
        return self._settings.groq_report_model
