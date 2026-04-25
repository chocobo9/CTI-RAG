from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterator

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from rag_cti._logging import get_logger
from rag_cti.types import Document

logger = get_logger(__name__)

_RETRY_KWARGS: dict[str, Any] = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=2, max=30),
    "reraise": True,
}


class BaseConnector(ABC):
    """Protocol for all CTI data source connectors."""

    source_name: str

    @abstractmethod
    def fetch(self, **params: Any) -> Iterator[dict[str, Any]]:
        """Yield raw records from the data source."""

    @abstractmethod
    def to_document(self, raw: dict[str, Any]) -> Document:
        """Convert a raw record to a canonical Document."""

    def fetch_documents(self, **params: Any) -> Iterator[Document]:
        """Fetch and convert all records, skipping malformed ones."""
        for raw in self.fetch(**params):
            try:
                yield self.to_document(raw)
            except Exception as exc:
                logger.warning(
                    "skipping malformed record",
                    source=self.source_name,
                    error=str(exc),
                )


class HttpConnector(BaseConnector):
    """Base for connectors that call HTTP APIs with retry logic."""

    def __init__(self, base_url: str, api_key: str = "", timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            timeout=timeout,
        )

    @retry(**_RETRY_KWARGS)
    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        url = f"{self._base_url}/{path.lstrip('/')}"
        response = self._client.get(url, params=params)
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpConnector:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
