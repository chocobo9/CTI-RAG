from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from rag_cti._logging import get_logger
from rag_cti.connectors.base import BaseConnector
from rag_cti.store.raw_store import SENTINEL_FETCHED_AT
from rag_cti.types import Document

logger = get_logger(__name__)

_BUNDLE_PATH = Path("data/raw/mitre/enterprise-attack.json")

# Fact-edge subjects must be threat entities (decision 2026-06): intrusion-set,
# campaign, malware, tool. malware/tool were previously dropped, losing ~10.6k
# "malware/tool uses technique" edges. Defensive subjects (course-of-action for
# `mitigates`, data-component for `detects`) are excluded via _CTI_REL_TYPES:
# only `uses` / `attributed-to` are fact predicates here. `subtechnique-of` is an
# ontology edge (see ontology_edges loader), not a fact edge.
_CTI_SOURCE_TYPES = frozenset({"intrusion-set", "campaign", "malware", "tool"})
_CTI_REL_TYPES = frozenset({"uses", "attributed-to"})


class MitreRelationshipConnector(BaseConnector):
    """Parses MITRE ATT&CK STIX 2.1 bundle into per-edge relationship Documents."""

    source_name = "mitre"

    def __init__(
        self, bundle_path: Path = _BUNDLE_PATH, fetched_at: datetime | None = None
    ) -> None:
        self._bundle_path = bundle_path
        # retrieved_at = when WE fetched the bundle (RawStore fetched_at), not the
        # edge's STIX modified (that stays in metadata.last_modified).
        self._fetched_at = fetched_at or SENTINEL_FETCHED_AT
        self._index: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def _ensure_index(self) -> None:
        if self._loaded:
            return
        if not self._bundle_path.exists():
            raise FileNotFoundError(
                f"MITRE ATT&CK bundle not found at {self._bundle_path}. "
                "Download from https://github.com/mitre-attack/attack-stix-data"
            )
        with self._bundle_path.open(encoding="utf-8") as fh:
            bundle: dict[str, Any] = json.load(fh)
        self._index = {o["id"]: o for o in bundle.get("objects", []) if "id" in o}
        self._loaded = True
        logger.info("stix index built", n_objects=len(self._index))

    def _name_of(self, stix_id: str) -> str | None:
        obj = self._index.get(stix_id)
        if obj is None:
            return None
        return cast(str, obj.get("name", ""))

    @staticmethod
    def _attack_id_of(obj: dict[str, Any]) -> str:
        if obj.get("type") != "attack-pattern":
            return ""
        for ref in obj.get("external_references", []):
            if ref.get("source_name") == "mitre-attack":
                return str(ref.get("external_id", ""))
        return ""

    def fetch(self, **_: Any) -> Iterator[dict[str, Any]]:
        self._ensure_index()
        for obj in self._index.values():
            if obj.get("type") != "relationship":
                continue
            if obj.get("revoked", False):
                continue
            rel_type = obj.get("relationship_type", "")
            if rel_type not in _CTI_REL_TYPES:
                continue
            src_ref = obj.get("source_ref", "")
            src_obj = self._index.get(src_ref)
            if src_obj is None:
                continue
            if src_obj.get("type") not in _CTI_SOURCE_TYPES:
                continue
            yield obj

    def to_document(self, raw: dict[str, Any]) -> Document:
        src_ref = raw["source_ref"]
        tgt_ref = raw["target_ref"]

        src_name = self._name_of(src_ref)
        tgt_name = self._name_of(tgt_ref)
        if src_name is None or tgt_name is None:
            raise ValueError(f"unresolvable refs: src={src_ref}, tgt={tgt_ref}")

        tgt_obj = self._index[tgt_ref]
        attack_id = self._attack_id_of(tgt_obj)

        rel_type = raw["relationship_type"]
        description = raw.get("description", "").strip()

        # retrieval §5: embed the procedure *description* only. The templated first
        # line ("X uses Y (Tnnnn)") duplicates the Fact — which now lives in the
        # chunk's relations[] and the knowledge layer — so it is dropped. Only an
        # edge with no description (rare) falls back to the template, because an
        # empty chunk cannot be embedded.
        if description:
            content = description
        elif attack_id:
            content = f"{src_name} uses {tgt_name} ({attack_id})"
        elif rel_type == "attributed-to":
            content = f"{src_name} attributed-to {tgt_name}"
        else:
            content = f"{src_name} uses {tgt_name}"

        doc_id = hashlib.sha256(f"mitre-rel:{raw['id']}".encode()).hexdigest()[:16]

        return Document(
            id=doc_id,
            source=self.source_name,
            content=content,
            retrieved_at=self._fetched_at,
            metadata={
                "attack_id": attack_id,
                "relationship_type": rel_type,
                "source_name": src_name,
                "target_name": tgt_name,
                "stix_id": raw["id"],
                "last_modified": raw.get("modified", ""),
            },
        )
