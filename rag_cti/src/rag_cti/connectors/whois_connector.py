from __future__ import annotations

import hashlib
from typing import Any, Iterator

from rag_cti._logging import get_logger
from rag_cti.connectors.base import BaseConnector
from rag_cti.preprocess.whois_template import render_whois
from rag_cti.types import Document

logger = get_logger(__name__)


class WHOISConnector(BaseConnector):
    """Converts pre-fetched WHOIS records into Documents via prose templating."""

    source_name = "whois"

    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self._records = records or []

    def fetch(self, **_: Any) -> Iterator[dict[str, Any]]:
        yield from self._records

    def to_document(self, raw: dict[str, Any]) -> Document:
        domain: str = raw.get("domain", "")
        if not domain:
            raise ValueError("WHOIS record missing required 'domain' field")

        content = render_whois(raw)
        doc_id = hashlib.sha256(f"whois:{domain}".encode()).hexdigest()[:16]

        return Document(
            id=doc_id,
            source=self.source_name,
            content=content,
            metadata={
                "domain": domain,
                "registrar": raw.get("registrar", ""),
                "iana_id": raw.get("iana_id", ""),
                "created": raw.get("created", ""),
                "expires": raw.get("expires", ""),
                "registrant_email": raw.get("registrant_email", ""),
                "name_servers": raw.get("name_servers", []),
            },
        )
