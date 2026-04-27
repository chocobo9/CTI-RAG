from __future__ import annotations

from enum import Enum


class TaskType(Enum):
    HYDE = "hyde"
    ANALYSIS = "analysis"
    REPORT = "report"


class LLMRouter:
    """Config-driven model selector.

    Priority: Ollama (single model for all tasks) > Groq (tiered) > Anthropic.
    HyDE     → ollama_model / groq_query_model    (fast)
    Analysis → ollama_model / groq_analysis_model (capable)
    Report   → ollama_model / groq_report_model   (capable)
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
