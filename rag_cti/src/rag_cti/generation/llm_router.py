from __future__ import annotations

from enum import Enum
from typing import Protocol

from rag_cti.types import SettingsProto


class TaskType(Enum):
    HYDE = "hyde"
    ANALYSIS = "analysis"
    REPORT = "report"


class ModelRouter(Protocol):
    """Anything that maps a task to a model name."""

    def model_for(self, task: TaskType) -> str: ...


class LLMRouter:
    """Config-driven model selector for Ollama and Groq."""

    def __init__(self, settings: SettingsProto, provider: str = "") -> None:
        self._settings = settings
        self._provider = provider

    def model_for(self, task: TaskType) -> str:
        if self._settings.ollama_enabled:
            return self._settings.ollama_model
        if task == TaskType.HYDE:
            return self._settings.groq_query_model
        if task == TaskType.ANALYSIS:
            return self._settings.groq_analysis_model
        return self._settings.groq_report_model
