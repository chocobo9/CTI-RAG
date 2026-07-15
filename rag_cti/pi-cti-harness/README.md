# Pi-native CTI harness tracer bullet

This isolated package runs one headless CTI investigation through Pi's real
agent loop. It is not a port of the Python runtime harness and it does not cut
over `answer()`.

## Ownership and seam

`runInvestigation()` is the only harness interface. A caller supplies one Pi
`AgentTool`, a model, a prompt, and `isComplete`, the CTI-owned completion
policy. The tool implementation remains outside the loop; this tracer bullet
uses a narrow fake capability in integration tests because the repository has
no TypeScript transport to the existing Python CTI capabilities.

Pi owns the provider protocol, tool-call parsing and validation, tool
execution, tool-result messages, transcript, turn continuation, event stream,
and abort behavior. The harness only forwards three native lifecycle events:
`turn_end`, `tool_execution_start`, and `tool_execution_end`.

CTI owns semantic completion. The policy is installed directly as Pi's native
`shouldStopAfterTurn` hook. A normal assistant response with no tool call is
reported as `incomplete` unless that policy explicitly returns `true`.

## Current limitation and next seam

Pi 0.74.2 exposes `shouldStopAfterTurn` on the low-level native `agentLoop`, not
on its stateful `Agent` class, so this one-run tracer uses `agentLoop` and its
native `EventStream`. It does not yet persist an Investigation Case or connect
to a production CTI capability. The next safe seam is one concrete adapter for
one existing CTI capability. If later product work requires steering,
compaction, or durable sessions, wire Pi's native hooks/session machinery at
that point; do not add a second loop or generic Python-TypeScript contract.

## Verification

```sh
npm run typecheck
npm run build
npm test
```

The tests use Pi's public faux provider and public harness interface. They cover
the full tool round trip, policy stop, incomplete no-tool completion, provider
error, tool error, and abort.
