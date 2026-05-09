from __future__ import annotations

from enum import Enum


class TaskType(Enum):
    HYDE = "hyde"
    ANALYSIS = "analysis"
    REPORT = "report"


class LLMRouter:
    """Config-driven model selector.

    When ``ollama_enabled``: one ``ollama_model`` for all tasks.
    Otherwise (Groq): tiered — HyDE uses ``groq_query_model`` (default ``llama-3.1-8b-instant``).
    """

    def __init__(self, settings: object) -> None:
        self._settings = settings

    def model_for(self, task: TaskType) -> str:
        if self._settings.ollama_enabled:  # type: ignore[attr-defined]
            return self._settings.ollama_model  # type: ignore[attr-defined]
        if task == TaskType.HYDE:
            return self._settings.groq_query_model  # type: ignore[attr-defined]
        if task == TaskType.ANALYSIS:
            return self._settings.groq_analysis_model  # type: ignore[attr-defined]
        return self._settings.groq_report_model  # type: ignore[attr-defined]
