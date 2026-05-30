"""The four teammate agent loops: lead, certifier, gold_builder, eval_gate.

Each function is the body of one long-lived thread. Every loop polls its drain-on-read
inbox and reacts to messages; concrete work (running the certified cert script, building
gold with the certified annotator, applying the acceptance checklist) happens inside the
loop and its results flow back onto the bus. No mock LLM anywhere — the real DeepSeek
annotator is invoked through the unchanged certified code paths.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from common import CERT_SUBPROCESS_TIMEOUT_S, MAX_WALL_S, POLL_INTERVAL_S, TeamContext

# ===========================================================================
# lead — coordinator. Holds the board, runs the Phase C hard gate, reports.
# ===========================================================================

def run_lead(ctx: TeamContext) -> None:
    log = ctx.log
    board = ctx.board
    bus = ctx.bus

    board.create("cert-consolidate", "Phase C: run new cert passes + consolidate >=3 points", "certifier", "pending", "C")
    board.create("phase-c-gate", "Phase C HARD GATE: Enterprise Micro-F1 mean >= threshold", "lead", "pending", "C")
    board.create("gold-build-sample", "Phase D: certified-annotator technique gold (relationship_direct sample)", "gold_builder", "blocked", "D")
    board.create("eval-gate-check", "Phase D: independent acceptance gate", "eval_gate", "blocked", "D")
    log("lead", "task board initialized; dispatching certification task")
    bus.send("lead", "certifier", "start_cert", {})

    state: dict[str, Any] = {
        "decision": None, "cert": None, "gold": None, "evalgate": None,
        "gold_done": False, "evalgate_done": False, "fatal": None,
    }
    start = time.time()

    while not ctx.stop.is_set():
        for msg in bus.drain("lead"):
            _lead_handle(ctx, msg, state)
        decision = state["decision"]
        if state["fatal"] is not None:
            break
        if decision == "rejected" and state["gold_done"]:
            break
        if decision == "approved" and state["gold_done"] and state["evalgate_done"]:
            break
        if time.time() - start > MAX_WALL_S:
            state["fatal"] = "lead wall-clock timeout"
            break
        time.sleep(POLL_INTERVAL_S)

    _write_final_report(ctx, state)
    ctx.done.set()
    ctx.stop.set()


def _lead_handle(ctx: TeamContext, msg: Any, state: dict[str, Any]) -> None:
    log = ctx.log
    if msg.type == "cert_result":
        state["cert"] = msg.body
        stats = msg.body["stats"]
        mean = stats["mean"]
        decision = "approved" if mean >= ctx.gate_threshold else "rejected"
        state["decision"] = decision
        ctx.board.update(
            "phase-c-gate", state=decision,
            note=f"mean={mean:.4f} vs threshold={ctx.gate_threshold} -> {decision}",
            result={"decision": decision, "threshold": ctx.gate_threshold, **stats,
                    "points": msg.body["points"]},
        )
        log("lead", f"HARD GATE: Enterprise Micro-F1 mean={mean:.4f} min={stats['min']:.4f} "
                    f"stdev={stats['stdev']:.4f} n={stats['n']} (threshold {ctx.gate_threshold}) -> {decision.upper()}")
        ctx.bus.send("lead", "gold_builder", "gate_decision",
                     {"decision": decision, "mean": mean, "points": msg.body["points"]})
        ctx.bus.send("lead", "eval_gate", "gate_decision", {"decision": decision})
    elif msg.type == "gold_result":
        state["gold"] = msg.body
        state["gold_done"] = True
    elif msg.type == "gold_skipped":
        state["gold"] = msg.body
        state["gold_done"] = True
        state["evalgate_done"] = True
    elif msg.type == "eval_gate_result":
        state["evalgate"] = msg.body
        state["evalgate_done"] = True
    elif msg.type == "role_error":
        log("lead", f"role_error from {msg.frm}: {msg.body.get('error')}")
        if msg.frm == "certifier":
            state["fatal"] = f"certifier failed: {msg.body.get('error')}"
        elif msg.frm == "gold_builder":
            state["gold"] = {"error": msg.body.get("error")}
            state["gold_done"] = True
            state["evalgate_done"] = True
        elif msg.frm == "eval_gate":
            state["evalgate"] = {"verdict": "ERROR", "error": msg.body.get("error")}
            state["evalgate_done"] = True


# ===========================================================================
# certifier — runs the certified cert script N times, consolidates >=3 points.
# ===========================================================================

def run_certifier(ctx: TeamContext) -> None:
    while not ctx.stop.is_set():
        for msg in ctx.bus.drain("certifier"):
            if msg.type == "start_cert":
                try:
                    _do_cert(ctx)
                except Exception as exc:  # noqa: BLE001 - report, don't crash the thread
                    ctx.board.update("cert-consolidate", state="error", note=str(exc))
                    ctx.log("certifier", f"ERROR\n{traceback.format_exc()}")
                    ctx.bus.send("certifier", "lead", "role_error", {"error": str(exc)})
        time.sleep(POLL_INTERVAL_S)


def _do_cert(ctx: TeamContext) -> None:
    log = ctx.log
    board = ctx.board

    existing = board.get("cert-consolidate")
    if existing and existing["state"] == "done" and existing.get("result", {}).get("points"):
        log("certifier", "recovery: cert-consolidate already done; republishing saved result")
        ctx.bus.send("certifier", "lead", "cert_result", existing["result"])
        return

    board.update("cert-consolidate", state="in_progress", note=f"loading {ctx.point_kind} points")
    points: list[dict[str, Any]] = []
    for p in ctx.historical_json:
        data = json.loads(p.read_text(encoding="utf-8"))
        f1 = float(data["technique"]["enterprise"]["micro_f1"])
        points.append({"f1": f1, "source": p.name, "kind": ctx.point_kind,
                       "model": data.get("annotator_model"), "candidate_k": data.get("candidate_k")})
        log("certifier", f"{ctx.point_kind} point f1={f1:.4f} ({data.get('annotator_model')}, k={data.get('candidate_k')}) <- {p.name}")

    for r in range(1, ctx.new_runs + 1):
        log("certifier", f"running NEW cert pass {r}/{ctx.new_runs}: certify_annotator.py "
                         "--provider deepseek --skip-actor --candidate-k 40 (real DeepSeek)")
        board.update("cert-consolidate", note=f"running new cert pass {r}/{ctx.new_runs}")
        out_path, f1 = _run_cert_subprocess(ctx)
        points.append({"f1": f1, "source": out_path.name, "kind": "new_run",
                       "model": "deepseek-chat", "candidate_k": 40})
        log("certifier", f"NEW run {r} Enterprise Micro-F1 = {f1:.4f}  <- {out_path.name}")

    f1s = [pt["f1"] for pt in points]
    stats = {
        "mean": statistics.mean(f1s),
        "min": min(f1s),
        "max": max(f1s),
        "stdev": statistics.stdev(f1s) if len(f1s) > 1 else 0.0,
        "n": len(f1s),
    }
    result = {"points": points, "stats": stats}
    board.update("cert-consolidate", state="done",
                 note=f"n={stats['n']} mean={stats['mean']:.4f} min={stats['min']:.4f} stdev={stats['stdev']:.4f}",
                 result=result)
    log("certifier", f"consolidated {stats['n']} points -> mean={stats['mean']:.4f} "
                     f"min={stats['min']:.4f} stdev={stats['stdev']:.4f}; reporting to lead")
    ctx.bus.send("certifier", "lead", "cert_result", result)


def _run_cert_subprocess(ctx: TeamContext) -> tuple[Path, float]:
    """Run the UNCHANGED certified cert script; locate + parse its saved record."""
    out_dir = ctx.repo_root / "data" / "eval"
    before = {p.name for p in out_dir.glob("certification_full_deepseek_*.json")}
    cmd = [sys.executable, "scripts/certify_annotator.py",
           "--provider", "deepseek", "--skip-actor", "--candidate-k", "40"]
    proc = subprocess.run(cmd, cwd=str(ctx.repo_root), timeout=CERT_SUBPROCESS_TIMEOUT_S)  # noqa: S603 - fixed argv
    if proc.returncode != 0:
        raise RuntimeError(f"cert subprocess returned rc={proc.returncode}")
    after = sorted(out_dir.glob("certification_full_deepseek_*.json"), key=lambda p: p.stat().st_mtime)
    new_files = [p for p in after if p.name not in before]
    if not new_files:
        raise RuntimeError("cert subprocess produced no new certification record")
    out_path = new_files[-1]
    data = json.loads(out_path.read_text(encoding="utf-8"))
    return out_path, float(data["technique"]["enterprise"]["micro_f1"])


# ===========================================================================
# gold_builder — blocked until approved; then builds gold with certified annotator.
# ===========================================================================

def run_gold_builder(ctx: TeamContext) -> None:
    while not ctx.stop.is_set():
        for msg in ctx.bus.drain("gold_builder"):
            if msg.type == "gate_decision":
                if msg.body.get("decision") == "approved":
                    try:
                        _build_gold(ctx, msg.body)
                    except Exception as exc:  # noqa: BLE001
                        ctx.board.update("gold-build-sample", state="error", note=str(exc))
                        ctx.log("gold_builder", f"ERROR\n{traceback.format_exc()}")
                        ctx.bus.send("gold_builder", "lead", "role_error", {"error": str(exc)})
                else:
                    ctx.board.update("gold-build-sample", state="blocked",
                                     note="Phase C gate REJECTED — no gold generated (命门 honored)")
                    ctx.log("gold_builder", "gate REJECTED -> standing down; generating NO gold")
                    ctx.bus.send("gold_builder", "lead", "gold_skipped", {"reason": "phase_c_gate_rejected"})
        time.sleep(POLL_INTERVAL_S)


def _build_gold(ctx: TeamContext, gate_body: dict[str, Any]) -> None:
    log = ctx.log
    board = ctx.board

    existing = board.get("gold-build-sample")
    if existing and existing["state"] == "done" and existing.get("result", {}).get("artifact"):
        log("gold_builder", "recovery: gold already built; republishing")
        ctx.bus.send("gold_builder", "eval_gate", "gold_artifact", existing["result"])
        ctx.bus.send("gold_builder", "lead", "gold_result", existing["result"])
        return

    board.update("gold-build-sample", state="in_progress", note="building certified annotator")
    log("gold_builder", "gate APPROVED -> building certified annotator (identical locked config)")

    # Reuse the EXACT certified build() from the cert script — zero config divergence.
    sys.path.insert(0, str(ctx.repo_root / "scripts"))
    import certify_annotator as cert  # noqa: E402

    from rag_cti.config import get_settings  # noqa: E402
    from rag_cti.evaluation.set_metrics import normalize_set  # noqa: E402
    from rag_cti.generation.generator import TECHNIQUE_RETRIEVE_K  # noqa: E402

    settings = get_settings()
    collection = settings.qdrant_collection
    gen, pipeline, model = cert.build(settings, collection, None, "deepseek", None)
    log("gold_builder", f"annotator ready: model={model} collection={collection} retrieve_k={TECHNIQUE_RETRIEVE_K} candidate_k=40")

    v2 = ctx.repo_root / "data" / "eval" / "query_set_v2.jsonl"
    entries = [json.loads(ln) for ln in v2.read_text(encoding="utf-8").splitlines() if ln.strip()]
    rd = [e for e in entries if e.get("category") == "relationship_direct"]
    sample = rd[: ctx.sample_size]
    cert_runs = [pt["source"] for pt in gate_body.get("points", [])]
    log("gold_builder", f"relationship_direct entries={len(rd)}; expanding gold for sample n={len(sample)}")

    new_entries: list[dict[str, Any]] = []
    for e in sample:
        text = e["query"]
        qr = pipeline.run(text, top_k=TECHNIQUE_RETRIEVE_K)
        preds = gen.annotate_techniques(text, qr, candidate_k=40)  # certified path, raises on LLM fail
        expanded = sorted(set(normalize_set(preds, "technique")) | set(normalize_set(e["gold_attack_ids"], "technique")))
        new_entries.append({
            **e,
            "gold_attack_ids": expanded,
            "original_gold_attack_ids": e["gold_attack_ids"],
            "annotator_pred": preds,
            "gold_provenance": {
                "method": "certified_annotator",
                "annotator_model": model,
                "candidate_k": 40,
                "retrieve_k": TECHNIQUE_RETRIEVE_K,
                "certified_by_runs": cert_runs,
                "gate_mean_micro_f1": gate_body.get("mean"),
            },
        })
        log("gold_builder", f"  {e['query_id']} ({e.get('gold_actor')}): {e['gold_attack_ids']} -> {expanded}")

    out = ctx.repo_root / "data" / "eval" / "query_set_v3_sample.jsonl"
    out.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in new_entries) + "\n", encoding="utf-8")

    before = sum(len(e["original_gold_attack_ids"]) for e in new_entries)
    after = sum(len(e["gold_attack_ids"]) for e in new_entries)
    result = {
        "artifact": str(out.relative_to(ctx.repo_root)).replace("\\", "/"),
        "count": len(new_entries),
        "category": "relationship_direct",
        "annotator_model": model,
        "candidate_k": 40,
        "retrieve_k": TECHNIQUE_RETRIEVE_K,
        "gold_size_before": before,
        "gold_size_after": after,
        "certified_by_runs": cert_runs,
        "gate_mean_micro_f1": gate_body.get("mean"),
        "sample": new_entries,
    }
    board.update("gold-build-sample", state="done",
                 note=f"built {len(new_entries)} gold entries ({before}->{after} technique labels) -> {out.name}",
                 result=result)
    log("gold_builder", f"wrote {out.name}: {len(new_entries)} entries, gold labels {before}->{after}; notifying eval_gate + lead")
    ctx.bus.send("gold_builder", "eval_gate", "gold_artifact", result)
    ctx.bus.send("gold_builder", "lead", "gold_result", result)


# ===========================================================================
# eval_gate — independent acceptance gate (separate from the producer).
# ===========================================================================

def run_eval_gate(ctx: TeamContext) -> None:
    while not ctx.stop.is_set():
        for msg in ctx.bus.drain("eval_gate"):
            if msg.type == "gold_artifact":
                try:
                    _run_gate(ctx, msg.body)
                except Exception as exc:  # noqa: BLE001
                    ctx.board.update("eval-gate-check", state="error", note=str(exc))
                    ctx.log("eval_gate", f"ERROR\n{traceback.format_exc()}")
                    ctx.bus.send("eval_gate", "lead", "role_error", {"error": str(exc)})
            elif msg.type == "gate_decision" and msg.body.get("decision") == "rejected":
                ctx.board.update("eval-gate-check", state="blocked", note="Phase C rejected — nothing to accept")
        time.sleep(POLL_INTERVAL_S)


def _run_gate(ctx: TeamContext, artifact: dict[str, Any]) -> None:
    log = ctx.log
    board = ctx.board
    board.update("eval-gate-check", state="in_progress", note="independent §D acceptance checks")
    checks: list[dict[str, Any]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "pass": bool(ok), "detail": detail})
        log("eval_gate", f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    # Independently re-read the artifact from disk — do NOT trust the message body.
    out = ctx.repo_root / artifact["artifact"]
    entries = [json.loads(ln) for ln in out.read_text(encoding="utf-8").splitlines() if ln.strip()]

    # 1) gold comes from the certified annotator, not hand-written.
    prov_ok = len(entries) > 0 and all(
        e.get("gold_provenance", {}).get("method") == "certified_annotator"
        and e["gold_provenance"].get("annotator_model") == "deepseek-chat"
        and e["gold_provenance"].get("candidate_k") == 40
        and e["gold_provenance"].get("certified_by_runs")
        and "annotator_pred" in e and "original_gold_attack_ids" in e
        for e in entries
    )
    record("gold_from_certified_annotator_not_handwritten", prov_ok,
           f"{len(entries)} entries; each carries certified-annotator provenance "
           f"(deepseek-chat, k=40) + annotator_pred + original seed, linked to cert runs")

    # 2) multi-label gold uses set semantics (deduped lists), expansion really happened.
    multilabel = [e for e in entries if len(e["gold_attack_ids"]) > 1]
    set_ok = all(
        isinstance(e["gold_attack_ids"], list)
        and len(set(e["gold_attack_ids"])) == len(e["gold_attack_ids"])
        for e in entries
    ) and len(multilabel) > 0
    record("multilabel_uses_set_metrics", set_ok,
           f"all gold are deduped lists; {len(multilabel)}/{len(entries)} expanded to multi-label sets")

    # 3) no actor_in_content backdoor residue (active code, not comments).
    ea = ctx.repo_root / "scripts" / "eval_attribution.py"
    backdoor_lines = []
    if ea.exists():
        for i, line in enumerate(ea.read_text(encoding="utf-8").splitlines(), start=1):
            if "actor_in_content" in line and not line.lstrip().startswith("#"):
                backdoor_lines.append(i)
    record("no_actor_in_content_backdoor", not backdoor_lines,
           "no active actor_in_content matching in eval_attribution.py"
           if not backdoor_lines else f"actor_in_content in active lines {backdoor_lines}")

    # 4) no averaging of capabilities into one total (artifact carries per-capability data only).
    avg_keys = [k for k in ("overall_score", "average_score", "combined_score", "total_score", "avg") if k in artifact]
    record("no_capability_averaging", not avg_keys,
           "artifact reports per-entry/per-capability data; no single averaged total"
           if not avg_keys else f"forbidden averaged keys present: {avg_keys}")

    verdict = "PASS" if all(c["pass"] for c in checks) else "FAIL"
    result = {"verdict": verdict, "checks": checks, "artifact": artifact["artifact"]}
    board.update("eval-gate-check", state="done", note=f"verdict={verdict}", result=result)
    log("eval_gate", f"VERDICT = {verdict}")
    ctx.bus.send("eval_gate", "lead", "eval_gate_result", result)


# ===========================================================================
# Final report (lead)
# ===========================================================================

def _write_final_report(ctx: TeamContext, state: dict[str, Any]) -> None:
    lines: list[str] = []
    a = lines.append
    cert = state.get("cert") or {}
    decision = state.get("decision")
    stats = cert.get("stats", {})
    points = cert.get("points", [])

    a("# CTI-RAG Agent Team — Phase C Consolidation + Phase D First Step")
    a("")
    a(f"环境: collection=cti_chunks_v2, annotator=deepseek-chat (provider=deepseek), "
      f"retrieve_k=300, candidate_k=40, dedup-in-generator. Gate threshold (USER) = {ctx.gate_threshold}")
    if state.get("fatal"):
        a("")
        a(f"## ⚠️ FATAL: {state['fatal']}")
    a("")
    a("## Phase C — 标注器认证(Enterprise Micro-F1,坐实)")
    a("")
    a("| # | source | kind | Enterprise Micro-F1 | model | k |")
    a("|---|--------|------|--------------------|-------|---|")
    for i, pt in enumerate(points, start=1):
        a(f"| {i} | {pt['source']} | {pt['kind']} | {pt['f1']:.4f} | {pt.get('model')} | {pt.get('candidate_k')} |")
    if stats:
        a("")
        a(f"**n={stats['n']}  mean={stats['mean']:.4f}  min={stats['min']:.4f}  "
          f"max={stats['max']:.4f}  stdev={stats['stdev']:.4f}**")
        a("")
        a(f"硬 gate(命门): Enterprise Micro-F1 均值 {stats['mean']:.4f} "
          f"{'≥' if stats['mean'] >= ctx.gate_threshold else '<'} {ctx.gate_threshold} "
          f"→ **{(decision or 'n/a').upper()}**")
        if decision == "approved" and stats["min"] < ctx.gate_threshold:
            a("")
            a(f"⚠️ 薄边警示: 最小单点 {stats['min']:.4f} < {ctx.gate_threshold} — 均值过线但单次采样可能跌破,"
              "n 小(Enterprise=47)CI 宽,仅作校准锚,不支撑强声明。")

    a("")
    if decision == "rejected":
        a("## 结论:停在 Phase C(gate 未过)")
        a("")
        a("technique 标注器未坐实 → **不准生成自建 gold**;Phase D 未启动。按命门,team 停在 Phase C。")
    elif decision == "approved":
        gold = state.get("gold") or {}
        a("## Phase D(第一步)— 用已认证标注器程序化标 technique gold")
        a("")
        if gold.get("error"):
            a(f"gold_builder ERROR: {gold['error']}")
        else:
            a(f"产物: `{gold.get('artifact')}`  (category={gold.get('category')}, n={gold.get('count')})")
            a(f"gold 规模(technique 标签数): {gold.get('gold_size_before')} → {gold.get('gold_size_after')} "
              "(单 attack_id 假低 → 认证标注器扩成多标签集)")
            a("")
            a("### 能力分项表(独立报,绝不平均)")
            a("")
            a("| 能力 | 指标 | 数据/split | 分数 | 外部锚 |")
            a("|------|------|-----------|------|--------|")
            a(f"| technique 抽取 | Micro-F1(tech) | CTI-ATE-Ent n=47 (认证锚) | "
              f"mean={stats.get('mean', float('nan')):.4f} (n={stats.get('n')}) | 论文 RAG-no-ft 0.65–0.79 |")
            a(f"| technique 自建 gold 扩充 | gold-set size | query_set_v3_sample relationship_direct n={gold.get('count')} | "
              f"{gold.get('gold_size_before')}→{gold.get('gold_size_after')} 标签 | 由上行认证背书 |")
            a("")
            a("### 抽样新 gold")
            for e in (gold.get("sample") or [])[:5]:
                a(f"- **{e['query_id']}** ({e.get('gold_actor')}): "
                  f"{e['original_gold_attack_ids']} → {e['gold_attack_ids']}")
        a("")
        eg = state.get("evalgate") or {}
        a("### eval-gate(独立验收,与生产者分离)")
        a("")
        a(f"**VERDICT = {eg.get('verdict', 'n/a')}**")
        for c in eg.get("checks", []):
            a(f"- [{'PASS' if c['pass'] else 'FAIL'}] {c['check']} — {c['detail']}")
    else:
        a("## 结论:未达成 gate 决策(见 FATAL)")

    a("")
    a("### 小样本警示")
    a("CTI-ATE Enterprise n=47,置信区间宽;DeepSeek run-to-run 方差 ≈0.015 与过线边际同量级。仅作校准锚。")
    a("")
    a("### 任务板最终状态")
    for t in ctx.board.all():
        a(f"- `{t['id']}` [{t['state']}] {t['title']}")

    report = "\n".join(lines) + "\n"
    (ctx.team_dir / "final_report.md").write_text(report, encoding="utf-8")
    ctx.log("lead", "final report written to .team/final_report.md")
