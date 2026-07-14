# Tool Boundary Trust Boundary

The learner needs tool calling taught as a trust boundary, not as a provider feature.

Teaching preference:
- Start from "model tool call is only an action proposal."
- Explain validation, admission, execution, observation, reducer as separate responsibilities.
- Use `invalid`, `rejected`, `error`, `ok`, `no_action` to teach diagnostic thinking.
- Code facts are supporting anchors; the main win is understanding why runtime must own the boundary.

Quality check:
- Exercises must explain why proposal is not execution.
- Feedback should distinguish bad args, policy rejection, tool exception, and no action.
