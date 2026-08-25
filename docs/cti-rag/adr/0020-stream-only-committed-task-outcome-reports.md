# ADR 0020: Stream only committed Task Outcome Reports

**Status:** Accepted

## Decision

Task Outcome Report Provider deltas and private candidates remain non-public.
Workspace must first complete composition, deterministic validation, required
Evidence Audit, deterministic rendering and the atomic output-plus-receipt
publication commit.

Public streaming may then deliver deterministic chunks read only from that
immutable committed output. Disconnect and resume use the committed report
identity and cursor; they never resume, splice or replay a Provider stream.

## Rationale

Users need progressive delivery, but model streaming and product publication
have different trust boundaries. Streaming a Provider candidate before
validation would disclose text that may later fail citation, authorization or
semantic-support checks.

Committing the whole qualified report first preserves the existing
publish-or-none safety decision. Chunked delivery then becomes a transport
concern: a disconnect may expose only a prefix, while the authoritative public
output remains complete, immutable and recoverable.

## Consequences

- Publication remains atomic even though network delivery is incremental.
- Chunk boundaries and resume positions are deterministic committed evidence.
- Authorization is revalidated for first delivery and resume, and invalidation
  can stop future chunks.
- The current whole-output Publication protocol requires a versioned amendment;
  its raw-delta isolation and atomic-commit rules remain unchanged.
