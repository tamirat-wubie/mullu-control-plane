# Hosted Demo Sandbox

Purpose: define the read-only hosted sandbox surface for evaluators at
`sandbox.mullusi.com`.

Governance scope: public demo traces, lineage projections, and policy evaluation
examples. The sandbox is a read model and must not mutate tenant state.

## Routes

| Route | Method | Purpose |
|---|---|---|
| `/api/v1/sandbox/summary` | `GET` | Sandbox overview and lineage query examples |
| `/api/v1/sandbox/traces` | `GET` | Read-only demo traces |
| `/api/v1/sandbox/lineage/{trace_id}` | `GET` | Causal graph projection for one demo trace |
| `/api/v1/sandbox/policy-evaluations` | `GET` | Read-only policy evaluation examples |

## Rules

1. Sandbox routes MUST be read-only.
2. Sandbox routes MUST NOT invoke providers or mutate tenant, budget, policy, or audit state.
3. Every trace MUST expose a `lineage://` URI.
4. Every lineage document MUST include bounded node and edge verification counts.
5. Every policy evaluation MUST expose verdict, reason codes, and deterministic hash.
6. Missing trace lookups MUST fail closed with a governed 404 response.

## Demonstration Coverage

| Demo | Shows |
|---|---|
| `sandbox-trace-budget-cutoff` | Streaming budget reserve, cutoff, and proof path |
| `sandbox-trace-policy-shadow` | Active policy and shadow policy evaluation beside one another |
| `sandbox-policy-allow-read` | Read-only lineage query allowed |
| `sandbox-policy-deny-tool` | Missing tool permission denied |

STATUS:
  Completeness: 100%
  Invariants verified: read-only routes, deterministic demo hashes, bounded lineage projection, governed missing-trace response, policy evaluation reason codes
  Open issues: none
  Next action: deploy `sandbox.mullusi.com` against the read-only route set
