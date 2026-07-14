# Teaching Notes

- User wants an engineering route through Agentic RAG, not a generic survey.
- User prefers Chinese explanations with project vocabulary kept precise.
- Start from the user's mind map, then bind each concept to CTI-RAG source files.
- The first learning arc should prioritize runtime harness, state, tool calls, evidence ledger, supervisor, citation/grounding, and eval.
- User finds 3-question exercises too narrow. Future lessons should include at least 10 focused practice items when the concept has enough surface area, with coverage across the main judgment boundaries.
- User wants quiz feedback to explain concepts, not just restate the correct answer. Code facts should support the concept; the main teaching target is architectural understanding.
- User does not want lesson goals to make code the primary curriculum. Lessons should state the conceptual skill first, then use CTI-RAG code as a concrete example, anchor, or check.
- User currently lacks a systematic concept map and may ask "how much is in the map?" before diving into a lesson. Put the agent in the user's set first: start lessons from the whole picture, then show where the specific lesson sits.
- User wants lessons to function as detailed教材, not just slide-like notes. When a diagram is introduced, explain what abstraction it represents, what it is not, why it is useful, and give concrete examples.
- Avoid unexplained mnemonics. If a sentence is meant as a memory aid, first name the underlying concept and explain why the distinction matters.
- User finds supervisor positioning unclear unless concept role and project implementation are separated. Future lessons should explicitly distinguish production admission in runtime harness from supervisor coordination, and call out debug/eval legacy autonomous supervisor paths when relevant.
- Future lesson verification must follow these teaching notes, not just technical checks. Use a TDD-style behavior gate for observable lesson outcomes and a grill-with-docs pass for teaching-quality questions before final delivery.
- In goal mode, treat the work as owning the user's learning outcome, not merely generating HTML. Each lesson should be a reviewable learning product with one core conceptual win, concept-first structure, code as supporting evidence, reference assets, learning-record updates, and an explicit quality-gate report.
