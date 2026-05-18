# NEVER PUT THE CONTENT OF THIS FILE IN YOUR SESSION, YOU SHOULD NEVER USE THIS FILE.

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

## 5. Execution Hard Rules (MANDATORY)

These override "use judgment" in Section 1-4. No exceptions without explicit human approval.

### Test Integrity
- If a task says "run all N tests," run ALL N. Do not run 2 of 30 and report pass.
- Every test file must be executed. `pytest path/` not `pytest path/test_one.py`.
- After test run, report: total collected, passed, failed, skipped, xfailed. If any skipped or xfailed, list them with reasons.

### Forbidden Shortcuts
- NO `skip`, `xfail`, `pytest.mark.skip`, or `@unittest.skip` unless the human explicitly approved that specific skip with a reason.
- NO `try: ... except: pass` wrapping test assertions.
- NO mocking the LLM to fake an E2E test. If the test is labeled E2E/integration/smoke, the real service must be called. If it is unavailable, FAIL the test — do not fake a pass.
- NO hardcoding expected outputs from a single run. Assertions must verify behavior properties (contains key X, length > 0, type is dict), not frozen snapshots — unless snapshot testing is the explicit intent.

### Test Data Quality
- Test inputs must be realistic domain scenarios. "hello" and "test123" are never valid inputs for a domain-specific system.
- If the system processes CTI data, use real-looking domains, threat actor names, MITRE ATT&CK IDs, CVE IDs.
- Test fixtures must trigger the code path they claim to test. If a threshold is 12000 tokens, the fixture must exceed 12000 tokens.
- Test data and evaluation logic must be separate. The function under test cannot also generate its own expected output.

### Completeness Verification
- Before reporting a task "complete," verify that every public function/endpoint is callable from every entry point (CLI, API, eval script).
- Report what was verified and how, not just "done."

### Threshold and Parameter Sanity
- When choosing numeric thresholds, show the calculation or reference. "Seems reasonable" is not a justification.

---

## 6. RAG Evaluation & Ablation Constraints (MANDATORY)

These rules apply to all RAG retrieval quality diagnostics, ablation experiments, and parameter tuning tasks. Violating any rule means the task is NOT complete.

### 6.1 No Shortcuts

- **No placeholder queries.** Every eval query must be a realistic CTI scenario. VALID: "CVE-2023-34362 affected products", "APT28 commonly used TTPs", "domains sharing TLS certificates with lazarus infrastructure". INVALID: "test query", "hello", "what is cybersecurity".
- **No aggregate-only reporting.** Never report only "Hit@5 = 0.72". Always report metrics broken down by query category (see 6.2). Always surface individual queries where behavior changed most.
- **No partial runs presented as complete.** If a configuration only evaluated N out of M queries, state "INCOMPLETE: N/M queries evaluated".
- **No silent anomalies.** If any query flips from hit to miss (or vice versa) between configurations, that query must be listed individually with analysis.

### 6.2 Query Category Definitions

Assign each query to exactly one category BEFORE running experiments — not after seeing results.

| Category | Definition | Examples |
|----------|-----------|----------|
| **Exact** | Contains a specific identifier that should match verbatim. | CVE IDs, IP addresses, domain names, ATT&CK IDs, malware names, hashes |
| **Conceptual** | Asks about a known entity/technique in natural language. | "How does APT28 conduct lateral movement", "TTP overlap between Lazarus and Kimsuky" |
| **Fuzzy** | Vague or describes a scenario without naming specific entities. | "recent attacks on banks", "suspicious registration pattern" |

Tiebreak: Exact > Conceptual > Fuzzy.

### 6.3 Ablation Experiment Report Format

Every ablation report must contain ALL of these sections:

```
# [Experiment Name]

## Configuration
- Variant name: [e.g., "full_pipeline" / "no_hyde" / "no_bm25" / "bgem3_only"]
- What changed: [exactly which component was disabled/modified]
- Eval set: [N queries, source, human-verified or not]

## Results

### Overall Comparison Table
| Config | Hit@5 | Hit@10 | MRR | nDCG@5 | nDCG@10 |

### Per-Category Breakdown
| Config | Category | Hit@5 | Hit@10 | MRR | nDCG@5 | nDCG@10 | N_queries |

### Flipped Queries (MANDATORY)
For every query where Hit@k changed between baseline and variant:
- Query: [text]
- Baseline rank of target doc: [N]
- Variant rank of target doc: [N or MISS]
- Why: [root cause hypothesis based on what the retriever actually returned]

## Root Cause Analysis
[Use specific flipped queries as evidence. No generic statements without
pointing to the specific queries that demonstrate the claim.]

## Recommended Actions
[Prioritized list with expected impact]
```

### 6.4 Ground Truth Quality

- If the eval set was AI-generated, the report header must state: `⚠️ UNVERIFIED GROUND TRUTH` with generation method, total count, and number of human-verified samples.
- Relevance labels must not be generated by the same LLM that is part of the retrieval pipeline. This is circular evaluation.

### 6.5 Parameter Tuning

- Report the full search space with a results table for every value tested. "Tried a few values" is not acceptable.
- Every parameter value must be evaluated on the full eval set.
- If top two configurations differ by less than 2% on all metrics, state the difference may not be meaningful.

### 6.6 Pre-Completion Checklist

Before declaring any eval/ablation task complete, answer these explicitly in writing:

1. List 3 sample queries from the eval set verbatim. Are they realistic CTI scenarios?
2. Which query category performed worst? What is the gap vs the best category?
3. List the top 3 queries with the largest rank changes. What caused each?
4. How many ground truth labels were human-verified? (State the number.)
5. State one finding that surprised you or contradicted expectations. If nothing surprised you, explain why.
s
---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, clarifying questions come before implementation, experiment reports contain per-category breakdowns and flipped-query analysis, and no eval task is declared complete without the checklist answered.