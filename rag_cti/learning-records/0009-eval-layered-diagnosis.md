# Eval Layered Diagnosis

The learner should treat eval as layered diagnosis, not a single quality score.

Teaching preference:
- Start every eval discussion by naming the measured layer.
- Retrieval eval, gathered evidence eval, answer eval, faithfulness/citation eval, and ops regression answer different questions.
- Metrics must come with "what this cannot prove."
- RAGAS-style eval should be tied to AgenticAnswer contexts and limitations.

Quality check:
- Exercises must force the learner to identify the layer a metric measures.
- Feedback should explain what to inspect next when a metric fails.
