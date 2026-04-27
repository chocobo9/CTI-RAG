from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from rag_cti._logging import get_logger
from rag_cti.connectors.base import BaseConnector
from rag_cti.types import Document

logger = get_logger(__name__)

_BUNDLE_PATH = Path("data/raw/mitre/enterprise-attack.json")


class MitreAttackConnector(BaseConnector):
    """Parses MITRE ATT&CK STIX 2.1 bundle into Documents."""

    source_name = "mitre"

    def __init__(self, bundle_path: Path = _BUNDLE_PATH) -> None:
        self._bundle_path = bundle_path

    def fetch(self, **_: Any) -> Iterator[dict[str, Any]]:
        if not self._bundle_path.exists():
            raise FileNotFoundError(
                f"MITRE ATT&CK bundle not found at {self._bundle_path}. "
                "Download from https://github.com/mitre-attack/attack-stix-data"
            )
        with self._bundle_path.open(encoding="utf-8") as fh:
            bundle: dict[str, Any] = json.load(fh)

        for obj in bundle.get("objects", []):
            if obj.get("type") == "attack-pattern" and not obj.get("revoked", False):
                yield obj

    def to_document(self, raw: dict[str, Any]) -> Document:
        attack_id = self._extract_attack_id(raw)
        content = self._build_content(raw, attack_id)
        doc_id = hashlib.sha256(f"mitre:{attack_id}".encode()).hexdigest()[:16]

        return Document(
            id=doc_id,
            source=self.source_name,
            content=content,
            metadata={
                "attack_id": attack_id,
                "name": raw.get("name", ""),
                "tactics": [
                    phase["phase_name"]
                    for phase in raw.get("kill_chain_phases", [])
                    if phase.get("kill_chain_name") == "mitre-attack"
                ],
                "platforms": raw.get("x_mitre_platforms", []),
                "is_subtechnique": raw.get("x_mitre_is_subtechnique", False),
                "last_modified": raw.get("modified", ""),
                "stix_id": raw.get("id", ""),
            },
        )

    @staticmethod
    def _extract_attack_id(raw: dict[str, Any]) -> str:
        for ref in raw.get("external_references", []):
            if ref.get("source_name") == "mitre-attack":
                return str(ref.get("external_id", ""))
        return raw.get("id", "unknown")

    @staticmethod
    def _build_content(raw: dict[str, Any], attack_id: str) -> str:
        name = raw.get("name", "")
        description = raw.get("description", "").strip()
        tactics = [
            phase["phase_name"]
            for phase in raw.get("kill_chain_phases", [])
            if phase.get("kill_chain_name") == "mitre-attack"
        ]
        tactic_str = ", ".join(tactics) if tactics else "unknown"
        return f"{attack_id}: {name}\nTactics: {tactic_str}\n\n{description}"
