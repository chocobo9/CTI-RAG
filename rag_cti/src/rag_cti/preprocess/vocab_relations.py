"""Summarize the controlled relation vocabulary from the built Fact table.

Data-grounded: instead of restating the design doc, this reads ``facts.jsonl`` and
reports the ``(predicate, subject_type, object_type)`` combinations that **actually
occur**, each with its source origins, Fact count, and a concrete example. It also
guards the controlled-vocabulary invariant: a predicate that did not map to a known
group (``CONTEXT.md §Fact``) is a defect (an un-sanctioned predicate leaked into the
corpus), so :func:`summarize_vocab` raises rather than silently listing it.

An optional ``names`` map (entity_id → readable name, assembled by the caller from
the entity registry / indicator index / ontology nodes) turns the hash-keyed example
ids (``indicator_0028ae27…``, ``location_orphan_069f…``) into readable values; an
example whose both endpoints resolve is preferred, and unresolved ids fall back to
the id verbatim.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

# Display order of the controlled groups (CONTEXT.md §Fact).
_GROUP_ORDER: dict[str, int] = {"ttp": 0, "infra": 1, "defensive": 2}
_GROUP_TITLE: dict[str, str] = {
    "ttp": "TTP / 归因 (attribution)",
    "infra": "基础设施 (infrastructure)",
    "defensive": "防御 (defensive)",
}


@dataclass(frozen=True)
class VocabRow:
    predicate: str
    subject_type: str
    object_type: str
    group: str
    origins: tuple[str, ...]
    fact_count: int
    example_subject: str
    example_object: str
    example_subject_name: str | None
    example_object_name: str | None


def summarize_vocab(
    facts: Iterable[dict[str, Any]], names: Mapping[str, str] | None = None
) -> list[VocabRow]:
    """One row per occurring (predicate, subject_type, object_type). Sorted, deterministic.

    *names* (entity_id → readable name) is used only to pick the most readable example
    (one whose both endpoints resolve) and to label it. Raises ``ValueError`` if any
    Fact carries an unknown ``group`` — a predicate outside the controlled set reached
    the corpus (invariant breach).
    """
    lookup = names or {}
    counts: dict[tuple[str, str, str], int] = {}
    origins: dict[tuple[str, str, str], set[str]] = {}
    groups: dict[tuple[str, str, str], str] = {}
    examples: dict[tuple[str, str, str], tuple[str, str]] = {}
    example_score: dict[tuple[str, str, str], int] = {}

    for fact in facts:
        key = (fact["predicate"], fact["subject_type"], fact["object_type"])
        counts[key] = counts.get(key, 0) + 1
        origins.setdefault(key, set()).update(fact.get("distinct_origins", []))
        groups[key] = fact["group"]
        subject, obj = fact["subject_id"], fact["object_id"]
        # prefer the most readable example: both endpoints named > subject named > first.
        score = int(subject in lookup) + int(obj in lookup)
        if key not in examples or score > example_score[key]:
            examples[key] = (subject, obj)
            example_score[key] = score

    unknown = sorted({p for (p, _s, _o), g in groups.items() if g == "unknown"})
    if unknown:
        raise ValueError(
            f"un-sanctioned predicate(s) in corpus (not in CONTEXT.md §Fact): {unknown}"
        )

    rows = [
        VocabRow(
            predicate=pred,
            subject_type=subj,
            object_type=obj,
            group=groups[(pred, subj, obj)],
            origins=tuple(sorted(origins[(pred, subj, obj)])),
            fact_count=counts[(pred, subj, obj)],
            example_subject=(ex := examples[(pred, subj, obj)])[0],
            example_object=ex[1],
            example_subject_name=lookup.get(ex[0]),
            example_object_name=lookup.get(ex[1]),
        )
        for (pred, subj, obj) in counts
    ]
    rows.sort(
        key=lambda r: (_GROUP_ORDER.get(r.group, 9), r.predicate, -r.fact_count, r.subject_type)
    )
    return rows


def _display(entity_id: str, name: str | None) -> str:
    """Readable name when resolved, else the id verbatim (with the id kept for joins)."""
    if name and name != entity_id:
        return f"{name} (`{entity_id}`)"
    return f"`{entity_id}`"


def render_markdown(rows: list[VocabRow]) -> str:
    """Render the vocab rows as a grouped Markdown document (deterministic, no timestamp)."""
    lines = [
        "# 词表关系清单 (Controlled Relation Vocabulary)",
        "",
        "> **数据驱动生成**自 `facts.jsonl`(M3 `build_facts` over the chunk corpus)。",
        "> 受控谓词的权威定义见 `docs/CONTEXT.md §Fact`;本表只列**实际出现**的",
        "> `(谓词, 主语类型, 宾语类型)` 组合 + 数据源 + Fact 计数 + 一个示例。",
        "> 示例显示可读名 + 括号内的 entity_id(join 键);MITRE 编号 id"
        "(`actor_G0016`/`technique_T1059`…)= 已解析到 ATT&CK,带 hash 的"
        "(`indicator_…`/`*_orphan_…`)= 无 MITRE 对象、按值/名哈希出的稳定 id。",
        "> 重新生成即可刷新(`scripts/build_vocab_relations.py`)。",
        "",
        f"合计 {len(rows)} 个关系模式,{sum(r.fact_count for r in rows)} 条 Fact。",
        "",
    ]
    current_group = None
    for row in rows:
        if row.group != current_group:
            current_group = row.group
            lines += [
                "",
                f"## {_GROUP_TITLE.get(row.group, row.group)}",
                "",
                "| 谓词 | 主语类型 | 宾语类型 | 数据源 | Fact 数 | 示例 |",
                "|---|---|---|---|---|---|",
            ]
        origins = ", ".join(row.origins) or "—"
        subject = _display(row.example_subject, row.example_subject_name)
        obj = _display(row.example_object, row.example_object_name)
        lines.append(
            f"| `{row.predicate}` | {row.subject_type} | {row.object_type} "
            f"| {origins} | {row.fact_count} | {subject} → {obj} |"
        )
    return "\n".join(lines) + "\n"
