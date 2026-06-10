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
| [Mullusi Ask-to-Receipt Flow Map](MULLUSI_ASK_TO_RECEIPT_FLOW_MAP.md) | End-to-end flow from a user message to answer, clarification, denial, governed plan, execution, and receipt. |
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
