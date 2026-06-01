# SDLC Governance Policy

Purpose: define the admission gates for governed software-delivery artifacts.
Governance scope: OCE required fields, RAG artifact links, CDCV stage causes, CQTE decidable gate rules, UWMA receipt references, and PRS closure.
Dependencies: `docs/SDLC.md`, `docs/SDLC_STATE_MACHINE.md`, `schemas/sdlc_*.schema.json`, and `scripts/validate_sdlc_artifact.py`.
Invariants: gates are read-only validation rules; they do not execute code, merge branches, deploy services, or publish external claims.

## Gates

| Gate | Required evidence | Reject condition |
| --- | --- | --- |
| Intake | request id, owner, source, change type, target surfaces, risk | missing owner, unknown target, unbounded scope, no source |
| Requirement | problem statement, success criteria, non-goals, constraints, acceptance tests | generic improvement with no measurable target |
| Design | affected modules, schema impact, security model, rollback plan, validation plan | no rollback, no validation, unknown security impact |
| Work plan | ordered steps, dependencies, validators, tests, expected artifacts | medium/high risk without ordered plan |
| Implementation | constructive deltas, fracture deltas, tests changed, docs changed when public behavior changes | silent behavior change or unchecked schema change |
| Verification | tests, validators, proof coverage when relevant, failed checks, warnings | changed behavior without required verification |
| Security | impact classification, threat model, findings, mitigations, residual risk | unresolved critical or high finding |
| Release | release notes, known limitations, migration notes, evidence-bound claims | production, legal, or compliance overclaim |
| Deployment | runtime conformance, health check, rollback, deployment witness | production claim without witness |
| Closure | outcome, receipts, blockers, learning notes | closure while blockers remain unclassified |

## Effect Boundary

Effect-bearing SDLC actions must pass through Universal Action Orchestration before execution. Non-executing documentation, schema, fixture, and validator checks may be simulated or validated without side effects.

Required effect-bearing bindings:

```text
effect_bearing_sdlc_action
-> uao_ref
-> causal_decision_trace_ref
-> receipt_ref
-> closure_ref
```

## Decision Outcomes

Use the existing solver outcome taxonomy:

| Outcome | SDLC meaning |
| --- | --- |
| `SolvedVerified` | artifact validates, required checks pass, and preflight accepts it |
| `SolvedUnverified` | artifact validates but live runtime evidence is intentionally unavailable |
| `AwaitingEvidence` | hard evidence is missing before a gate can advance |
| `GovernanceBlocked` | a hard gate rejected the artifact |
| `SafeHalt` | runtime safety floor triggered and execution stopped |
| `ModelInvalidated` | observed evidence contradicts the release or deployment claim |
