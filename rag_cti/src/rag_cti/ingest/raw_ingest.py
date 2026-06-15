"""Route connector fetches through the versioned RawStore (ingestion §3/§6).

This is the wiring the ingestion doc calls for: every source's raw response is
persisted (append-only, versioned) **before** any projection, and a re-fetch
appends a new version instead of overwriting. Incremental fetch uses the store's
high-water mark as the connector's ``modified_since``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rag_cti._logging import get_logger
from rag_cti.connectors.base import BaseConnector
from rag_cti.store.raw_store import RawStore

logger = get_logger(__name__)


def fetch_to_raw(
    connector: BaseConnector,
    store: RawStore,
    fetched_at: str,
    source_id_fn: Callable[[dict[str, Any]], str] | None = None,
    **fetch_params: Any,
) -> int:
    """Persist every raw record a connector yields as a versioned RawStore entry.

    ``source_id_fn`` extracts the stable source id from a raw record (defaults to
    ``raw["id"]``). Records with no derivable id are skipped (counted in the log).
    Returns the number of records written. Idempotent: re-running with the same
    ``fetched_at`` and identical payloads is a no-op (RawStore dedupes).
    """
    id_fn = source_id_fn or (lambda raw: str(raw.get("id", "")))
    written = 0
    skipped = 0
    for raw in connector.fetch(**fetch_params):
        source_id = id_fn(raw)
        if not source_id:
            skipped += 1
            continue
        store.write(connector.source_name, source_id, raw, fetched_at)
        written += 1
    logger.info(
        "fetched to raw store",
        source=connector.source_name,
        fetched_at=fetched_at,
        written=written,
        skipped=skipped,
    )
    return written


def read_domains_from_index(index_path: Path, canonical_type: str = "domain") -> list[str]:
    """Read indicator values of a given canonical_type from an indicator index
    jsonl (scripts/build_indicator_index.py). Deduped, sorted. Empty if missing.

    This is how the field-source fetchers (VT/WHOIS) get their domain work list:
    the join discriminator (indicator type) routes which indicators each source
    enriches (domain → WHOIS/VT)."""
    if not index_path.exists():
        return []
    values: set[str] = set()
    with index_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("canonical_type") == canonical_type and rec.get("value"):
                values.add(str(rec["value"]))
    return sorted(values)
