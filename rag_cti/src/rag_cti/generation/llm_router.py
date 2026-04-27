from __future__ import annotations

from enum import Enum


class TaskType(Enum):
    HYDE = "hyde"
    ANALYSIS = "analysis"
    REPORT = "report"


class LLMRouter:
    """Config-driven model selector for the three Groq LLM tiers.

    HyDE     → groq_query_model   (fast, cheap: llama-3.1-8b-instant)
    Analysis → groq_analysis_model (capable: llama-3.3-70b-versatile)
    Report   → groq_report_model   (capable: llama-3.3-70b-versatile)
    """

    def __init__(self, settings: object) -> None:
        self._settings = settings

    def model_for(self, task: TaskType) -> str:
        if task == TaskType.HYDE:
            return self._settings.groq_query_model  # type: ignore[attr-defined]
        if task == TaskType.ANALYSIS:
            return self._settings.groq_analysis_model  # type: ignore[attr-defined]
        return self._settings.groq_report_model  # type: ignore[attr-defined]
