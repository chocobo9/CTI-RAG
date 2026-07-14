# Citation Grounding Faithfulness Split

The learner needs citation, grounding, faithfulness, and sufficiency separated into distinct quality questions.

Teaching preference:
- Citation validation proves ID existence in the current ledger, not claim truth.
- Grounding asks whether claim can trace to evidence.
- Faithfulness asks whether the answer stays within evidence strength and scope.
- Sufficiency asks whether evidence covers the user's task enough to stop gathering.

Quality check:
- Exercises must include cases where citation validation passes but grounding fails.
- Feedback should name the layer that failed and the likely engineering fix.
