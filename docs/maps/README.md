# Mullusi Govern System Mapbook

Status: Foundation Mode
Scope: private, local-first architecture mapping. This mapbook does not claim deployment readiness, customer readiness, support readiness, legal readiness, commercial readiness, or production operation readiness.

## Purpose

The mapbook records how user communication, interpretation, governance, execution, evidence, and response surfaces connect across Mullu Govern and the Mullu Control Plane.

The primary system spine is:

```text
User request
-> communication gateway
-> interpretation
-> governance
-> approval or denial
-> execution when allowed
-> evidence receipt
-> user response
```

## Maps

| Map | Purpose |
| --- | --- |
| [Mullusi Total System Map](MULLUSI_TOTAL_SYSTEM_MAP.md) | Whole-system node, edge, layer, state, and component contract map. |
| [Mullusi User Journey Map](MULLUSI_USER_JOURNEY_MAP.md) | Product journey map for first ask, clarification, plan review, approval, current task, and receipt review. |
| [Mullusi Ask-to-Receipt Flow Map](MULLUSI_ASK_TO_RECEIPT_FLOW_MAP.md) | End-to-end flow from a user message to answer, clarification, denial, governed plan, execution, and receipt. |
| [Mullusi Communication Gateway Map](MULLUSI_COMMUNICATION_GATEWAY_MAP.md) | Channel, identity, tenant, deduplication, response, and channel trust map. |
| [Mullusi Interpretation Layer Map](MULLUSI_INTERPRETATION_LAYER_MAP.md) | Deterministic and LLM-assisted interpretation boundary, slots, clarification, confidence, and interpretation receipts. |
| [Mullusi Governance Layer Map](MULLUSI_GOVERNANCE_LAYER_MAP.md) | Policy, budget, approval, command ledger, plan ledger, and causal closure map. |
| [Mullusi Search Layer Map](MULLUSI_SEARCH_LAYER_MAP.md) | Search need, freshness, cache, source, budget, retrieval safety, answer, and search receipt map. |
| [Mullusi Worker Layer Map](MULLUSI_WORKER_LAYER_MAP.md) | Worker contract matrix for code, browser, document, search, email/calendar, deployment, notification, and financial workers. |
| [Mullusi Evidence Receipt Map](MULLUSI_EVIDENCE_RECEIPT_MAP.md) | Receipt taxonomy, state transition evidence, terminal certificate, denial, blocker, and audit trail map. |
| [Mullusi Admin Console Map](MULLUSI_ADMIN_CONSOLE_MAP.md) | Admin screen map for tenants, policies, budgets, approvals, workers, connectors, and receipts. |
| [Mullusi Deployment Readiness Map](MULLUSI_DEPLOYMENT_READINESS_MAP.md) | Foundation Mode deployment deferral and evidence gates for future readiness promotion. |
| [Mullusi Missing Component Gap Register](MULLUSI_GAP_REGISTER.md) | Missing, partial, blocked, or deferred components that must be tracked before product or deployment claims. |

## Mapbook rules

```text
Map every component.
Give every component a status.
Give every transition a receipt, denial, blocker, or clarification.
Give every risky action a gate.
Give every missing part a gap ID.
Do not promote a local map into readiness, launch, support, or legal claims.
```

## Status vocabulary

```text
missing
partial
implemented
tested
pilot-ready
production-ready
deferred
blocked
```

Use `pilot-ready` or `production-ready` only when evidence exists and the relevant boundary documents permit that claim.
