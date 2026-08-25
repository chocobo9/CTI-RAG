# DeepSeek Report Composer Fit

Date: 2026-07-22  
Status: Planner research; non-normative

## Question

Which current DeepSeek model profile is suitable for a bounded CTI
investigation report composer, and can the same model be treated as an
independent hallucination checker?

## Primary-source findings

- DeepSeek's current API models are `deepseek-v4-pro` and
  `deepseek-v4-flash`. Both support thinking/non-thinking modes, JSON Output,
  Tool Calls, a one-million-token context window and large output limits.
  Source:
  [DeepSeek Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/).
- The legacy `deepseek-chat` and `deepseek-reasoner` names are scheduled to be
  unavailable after 2026-07-24 15:59 UTC. During the transition they map to
  non-thinking and thinking modes of V4 Flash. New product contracts must not
  freeze either legacy alias.
  Sources:
  [DeepSeek V4 release](https://api-docs.deepseek.com/news/news260424/),
  [DeepSeek change log](https://api-docs.deepseek.com/updates/).
- JSON Output guarantees syntactically valid JSON when the request selects
  `json_object` and the prompt explicitly requests JSON. DeepSeek also warns
  that JSON mode may occasionally return empty content and that output can be
  truncated at the token limit; both require closed application handling.
  Source:
  [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/).
- Thinking mode is available on V4 Pro/Flash, defaults to enabled, and does not
  honor temperature/top-p controls. Tool-call conversations have additional
  reasoning-content continuity rules.
  Source:
  [DeepSeek Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/).

## Product recommendation

Use a logical Workspace model profile rather than exposing a vendor model name
through business contracts:

```text
report_composer/deepseek-v1
  provider model: deepseek-v4-pro
  mode: non-thinking
  response: JSON Output
  tools: none
```

Reasons:

- report composition is a bounded transformation of settled evidence, not an
  Agent Tool loop;
- non-thinking mode avoids retaining or transporting reasoning content;
- JSON Output can carry a closed report/claim/citation structure before final
  deterministic rendering; and
- V4 Pro is the conservative quality-oriented product choice, while V4 Flash
  remains a candidate for later cost/latency evaluation.

This is a product selection candidate, not evidence that V4 Pro is best at CTI
report writing. Activation requires a project-local benchmark comparing
groundedness, citation faithfulness, omission, structure, language quality,
latency and cost against at least one alternative.

## Reviewer independence

The Report Composer must not review its own result as the sole semantic safety
gate. A reviewer receives a fresh context containing only:

- the closed report candidate;
- exact qualified evidence excerpts/facts and citation references;
- the review rubric; and
- no composer conversation, reasoning, Workspace history or hidden Agent state.

Using DeepSeek V4 Pro thinking mode may provide a useful secondary critique, but
it is not model-family independence. High-assurance review should use a
different qualified model/provider profile and measure correlated misses.
Regardless of model choice, the reviewer is advisory: deterministic
source-existence, authorization, version and citation checks remain mandatory,
and an unsupported/contradicted/not-verifiable claim is withheld rather than
made true by reviewer approval.
