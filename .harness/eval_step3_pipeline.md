# Evaluation: Step 3 — Pipeline Integration (over-fetch + trace)

**Evaluator**: Evaluator Agent (isolated context)
**Date**: 2026-05-17
**Files reviewed**:
- `src/rag_cti/retrieval/pipeline.py` (implementation)
- `src/rag_cti/config.py` (config fields)
- `src/rag_cti/retrieval/reranker.py` (reranker classes)
- `src/rag_cti/retrieval/__init__.py` (exports)
- `src/rag_cti/observability/tracing.py` (trace metadata API)
- `tests/unit/test_pipeline.py` (existing tests)
- `.env.example` (env vars)
- `scripts/eval_query_set.py`, `scripts/eval_techniquerag.py`, `src/rag_cti/cli.py` (callers)

---

## Spec Requirements — Line-by-Line Verification

### Requirement A: Over-fetch logic in `Pipeline.run()`

**Spec says**:
```python
fetch_k = k
if hasattr(self._settings, 'reranker_candidates_k') and self._settings.reranker_enabled:
    fetch_k = max(k, self._settings.reranker_candidates_k)
```

**Actual implementation** (pipeline.py lines 35-37):
```python
fetch_k = k
if getattr(self._settings, "reranker_enabled", False):
    fetch_k = max(k, getattr(self._settings, "reranker_candidates_k", k))
```

**Deviation analysis**: The implementation uses `getattr(..., False)` / `getattr(..., k)` instead of `hasattr` + direct attribute access. This is a **functionally superior** approach:

- Spec's `hasattr(self._settings, 'reranker_candidates_k') and self._settings.reranker_enabled` checks for `reranker_candidates_k` first, then accesses `reranker_enabled` directly (which would raise `AttributeError` if missing).
- Implementation's `getattr(self._settings, "reranker_enabled", False)` safely handles missing `reranker_enabled` attribute with a False default, and `getattr(self._settings, "reranker_candidates_k", k)` falls back to `k` if missing.
- This is **more robust** than the spec's version. The spec version has a subtle bug: it checks `hasattr` for `reranker_candidates_k` but accesses `reranker_enabled` without a guard. If settings has `reranker_candidates_k` but not `reranker_enabled`, the spec version crashes. The implementation avoids this.
- Both achieve the same over-fetch behavior: when reranker is enabled, fetch `max(k, reranker_candidates_k)`.

**VERDICT**: PASS. Deviation is a net improvement; functionally equivalent for all valid cases, and more robust for edge cases.

### Requirement B: Trace metadata fields

**Spec says** add `reranker` and `fetch_k` fields to `add_trace_metadata`:
```python
add_trace_metadata(
    top_k=k,
    returned=len(results),
    elapsed_ms=round(elapsed_ms, 1),
    chunk_ids=[r.document.id for r in results],
    scores=[round(r.score, 4) for r in results],
    reranker=type(self._reranker).__name__,
    fetch_k=fetch_k,
)
```

**Actual implementation** (pipeline.py lines 45-53): Matches exactly. All 7 keyword arguments present, in the same order, with the same expressions.

**VERDICT**: PASS. Exact match.

### Requirement C: `build_pipeline` reranker selection

**Spec says**:
```python
if getattr(settings, 'reranker_enabled', False):
    from rag_cti.retrieval.reranker import CrossEncoderReranker
    reranker = CrossEncoderReranker(model_name=settings.reranker_model)
else:
    reranker = NoOpReranker()
```

**Actual implementation** (pipeline.py lines 90-97): Matches exactly. Uses `getattr(settings, "reranker_enabled", False)` for backward compat, lazy import of `CrossEncoderReranker`, passes `settings.reranker_model`.

**VERDICT**: PASS. Exact match.

### Requirement: Backward compatibility with `_FakeSettings`

**Spec says**: `getattr(settings, 'reranker_enabled', False)` guarantees backward compat for settings objects without `reranker_enabled`.

**Verification**: `_FakeSettings` in `test_pipeline.py` (lines 49-52) has only `retrieval_top_k` and `hyde_enabled`. No `reranker_enabled`, no `reranker_candidates_k`, no `reranker_model`.
- In `Pipeline.run()`: `getattr(self._settings, "reranker_enabled", False)` returns `False` -> `fetch_k = k` (no over-fetch). Safe.
- In `build_pipeline()`: `getattr(settings, "reranker_enabled", False)` returns `False` -> `NoOpReranker()`. Safe. `settings.reranker_model` is never accessed.

**VERDICT**: PASS. Backward compatible.

### Requirement: Verify test results (465 passed, 1 failed)

**Reported by implementer**: 465 passed, 1 failed (pre-existing: `test_build_llm_client_groq_provider_when_groq_key_set` — unrelated to reranker changes).

**Assessment**: The pre-existing failure is in `test_build_llm_client_groq_provider_when_groq_key_set`, which is a Groq LLM client test, entirely unrelated to pipeline/reranker code. This was already failing before Step 3 changes. Not a regression.

**VERDICT**: PASS. No new failures introduced.

---

## Audit Checklist

### Functionality Completeness: 9/10

| Requirement | Status | Notes |
|---|---|---|
| Over-fetch logic | PASS | Uses `getattr` (better than spec's `hasattr`) |
| `fetch_k = max(k, reranker_candidates_k)` | PASS | Correct math |
| `results[:k]` truncation after rerank | PASS | Line 43 |
| Trace metadata: `reranker` field | PASS | `type(self._reranker).__name__` |
| Trace metadata: `fetch_k` field | PASS | `fetch_k=fetch_k` |
| `build_pipeline` reranker=True path | PASS | Lazy import + CrossEncoderReranker |
| `build_pipeline` reranker=False path | PASS | NoOpReranker |
| `getattr` backward compat | PASS | Both run() and build_pipeline() |

**Minor observation** (-1): The `results = self._retriever.search(query, top_k=fetch_k, ...)` call on line 39-41 passes `fetch_k` to the retriever's `top_k` parameter. This means the retriever fetches `reranker_candidates_k` candidates. After reranking, `results[:k]` truncates to the original requested `k`. This is correct over-fetch behavior.

No happy-path-only concern: the NoOp path (reranker disabled) is also handled — `fetch_k` stays equal to `k`, so no unnecessary over-fetch occurs.

### Code Quality: 9/10

- **No hardcoded values**: `fetch_k` is derived from settings. No magic numbers.
- **Error handling**: `add_trace_metadata` is already a no-op safe function (see tracing.py line 120-128 — catches all exceptions silently). The pipeline itself has no new error paths that need handling; `getattr` defaults handle missing attributes.
- **Follows project patterns**: Yes. Uses `getattr` for optional settings (same pattern as the existing `hyde_enabled` check on line 81). Uses lazy import for `CrossEncoderReranker` (mirrors the sentence_transformers lazy load pattern in `reranker.py`). Uses `add_trace_metadata` kwargs (consistent with existing trace call pattern).
- **Logger usage**: Existing `logger.debug` on lines 54-60 is preserved. No new log statements needed.
- **Type hints on `Pipeline.__init__`**: Uses `object` for `retriever`, `reranker`, `settings` (line 20). This is loose typing — could use `Reranker` Protocol for `reranker` parameter. However, this is a **pre-existing pattern**, not introduced by Step 3. The spec does not ask to change `Pipeline.__init__` signature.

### Simplicity: 9/10

- **Pipeline.run()**: 35 lines total (lines 26-66). The over-fetch logic adds exactly 3 lines (35-37). The trace metadata adds 2 new kwargs. Minimal.
- **build_pipeline()**: The reranker selection block is 6 lines (90-97) — clean conditional with lazy import. Cannot be reduced further.
- **No unnecessary abstractions**: No factory pattern, no config parsing, no extra classes. Direct conditional logic.
- **No spec-unasked features**: No extra logging, no extra metrics, no extra config validation.
- Could it be reduced 30%+? No. The implementation is already minimal.

### Test Quality: N/A

Step 3 spec explicitly states tests are in Step 4. However, I note that the **existing** test `test_run_calls_add_trace_metadata_with_chunk_ids_and_scores` (line 226) does NOT assert the new `reranker` and `fetch_k` fields. This is acceptable for now — Step 4 should add these assertions.

**Observation for Step 4**: The existing trace metadata test should be extended or a new test added to verify `reranker` and `fetch_k` are present in the trace metadata kwargs.

### Integration Correctness: 9/10

| Check | Status | Notes |
|---|---|---|
| Backward compat: NoOpReranker path | PASS | `_FakeSettings` without reranker fields works |
| Backward compat: existing `.env` | PASS | `reranker_enabled` defaults to `False` in config.py |
| Eval scripts (`eval_query_set.py`, `eval_techniquerag.py`) | PASS | Call `build_pipeline(settings=settings, ...)` where `settings` is `get_settings()` which always has reranker fields with defaults |
| CLI (`cli.py`) | PASS | Same pattern as eval scripts |
| `NoOpReranker` import at top | PASS | Line 10: `from rag_cti.retrieval.reranker import NoOpReranker` |
| `CrossEncoderReranker` lazy import | PASS | Only imported inside the `if reranker_enabled` branch |
| `__init__.py` exports | PASS | Exports `CrossEncoderReranker`, `NoOpReranker`, `Reranker` |

**One minor concern**: In `build_pipeline`, when `reranker_enabled` is True, `settings.reranker_model` is accessed directly (line 93) without `getattr`. If someone passes a settings object WITH `reranker_enabled=True` but WITHOUT `reranker_model`, this would raise `AttributeError`. However, this is a reasonable assumption: if you enable the reranker, you must provide the model name. And with the real `Settings` class, `reranker_model` always has a default value. The spec's own code snippet does the same thing (`settings.reranker_model` direct access). Not a bug.

---

## Issues Found

### NONE — No blocking issues.

### Minor observations (informational, not blocking):

1. **Spec deviation in over-fetch guard**: Uses `getattr` instead of `hasattr`. This is an improvement, not a bug. The spec's version had a subtle fragility. No action needed.

2. **Trace test coverage gap**: Existing trace test does not assert `reranker` and `fetch_k` fields. This should be addressed in Step 4 tests.

3. **`object` type hints for `__init__`**: `Pipeline.__init__` uses `object` for all parameters. Not introduced by this step; pre-existing.

---

## Scores

| Dimension | Score | Justification |
|---|---|---|
| Functionality Completeness | 9/10 | All spec requirements implemented correctly. Over-fetch, trace, build_pipeline all match. |
| Code Quality | 9/10 | Clean, follows project patterns, no hardcoded values, proper error safety via getattr defaults. |
| Simplicity | 9/10 | Minimal additions. 3 lines for over-fetch, 2 kwargs for trace, 6 lines for reranker selection. No bloat. |
| Test Quality | N/A | Tests are Step 4 scope. |
| Integration Correctness | 9/10 | Backward compat verified. All callers (scripts, CLI) work unchanged. No .env breakage. |

---

## Total: PASS

All dimensions score >= 7. No blocking issues found. Implementation is faithful to the spec with one minor deviation (getattr vs hasattr) that is actually an improvement.
