# ADR 0002: Authorization, Signed Commits, and Transactional Store

Status: accepted for v0.3 scaffold.

Decision:

```text
authenticate → authorize → evaluate → sign → append → apply
```

Rationale: causal state must not depend on trusting the caller, a mutable process cache, or an unsigned event body.
