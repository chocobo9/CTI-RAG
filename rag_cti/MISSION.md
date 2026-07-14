# Mission: Agentic RAG Engineering for CTI-RAG

## Why
Build enough engineering intuition to read, explain, and critique CTI-RAG's Agentic RAG runtime: runtime harness, state management, tool calls, evidence ledger, supervisor routing, citation/grounding, and evaluation design.

## Success looks like
- Trace `answer()` from query understanding through single-agent or supervisor execution.
- Explain the difference between runtime state, memory, context, prompt, and evidence ledger.
- Evaluate whether a tool call path is bounded, validated, observable, and grounded.
- Judge whether citations, grounding, and evals prove the right thing rather than merely existing.
- Read a proposed refactor and identify which boundary it belongs to: runtime harness, knowledge layer, retrieval layer, supervisor, or eval harness.

## Constraints
- Teach in Chinese, with English technical terms preserved when they are the project vocabulary.
- Use the mind map at `D:\agentic_rag_mindmap.html` as the primary concept map.
- Use the local CTI-RAG codebase as supporting evidence, concrete examples, and audit practice, not as the first source of conceptual order.
- Keep each lesson reviewable later as HTML, but allow enough detail for it to function as a real study text.
- Prefer project docs and source code when grounding a concept in this codebase, while keeping the conceptual skill first.

## Out of scope
- General LLM theory unless it explains a concrete CTI-RAG design decision.
- Broad RAG product comparisons.
- Code changes to CTI-RAG unless explicitly requested.
