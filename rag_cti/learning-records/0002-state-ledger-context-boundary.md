# State Ledger Context Boundary

The second lesson should reinforce that runtime state, EvidenceLedger, and prompt/context are different responsibilities:

- Runtime state explains how one run is progressing and why it continues or stops.
- EvidenceLedger remains the per-run evidence authority for chunks, facts, outlines, actions, and citable IDs.
- Prompt/context is a model-visible projection rebuilt from state and ledger, not the durable source of truth.

Future lessons on tool calls, evidence ledger, citation, supervisor, and eval should reuse this boundary before introducing new objects.
