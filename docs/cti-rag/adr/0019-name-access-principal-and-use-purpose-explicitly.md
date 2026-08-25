---
status: accepted
---

# Name access principal and use purpose explicitly

CTI-RAG uses `AccessPrincipalBinding` and `principalRef` for the trusted user,
group or service identity exercising access, because `actor` is irreducibly
ambiguous with CTI Threat Actor and Agent/runtime actors. Data-use authorization
is named `usePurpose`: it records why that principal may use an exact data
version and is distinct from Case mandate, task objective, context consumer and
operation intent. Trusted Workspace workflow supplies this binding; neither the
user-facing model context nor the model may set or modify it.

Existing access-authorization fields named `actor`, `actorRef` or `purpose`
must migrate by semantic ownership rather than global string replacement.
Threat Actor terminology remains unchanged. Pi context-selection purposes become
`contextConsumer`; task/goal purposes become `taskObjective`; Tool execution
continues to use `operationIntent`.
