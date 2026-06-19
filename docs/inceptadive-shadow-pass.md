# InceptaDive Shadow Pass

Purpose: define the applied Interrogated Backup Layer for Mullu interpretation,
planning, workflow, strict preflight, and post-outcome learning.
Governance scope: shadow interrogation is advisory and non-executing; final
approval, block, repair, escalation, scheduling, or execution remains owned by
Mullu governance.
Dependencies: `inceptadive_shadow_types`, `inceptadive_shadow_gate`,
`inceptadive_shadow_light`, `inceptadive_shadow_preflight`,
`inceptadive_shadow_scoring`, `inceptadive_shadow_receipt`, and the application
integration facade.
Invariants: shadow may ask what the normal path missed; it cannot directly
execute, approve, promote truth, or bypass governance.

## Applied path

Normal path:

- user request
- normal interpretation
- normal planning
- Mullu governance
- execution only if approved
- outcome recorded

Shadow path:

- user request or candidate action
- gate decides off, light, deep, or strict preflight
- light pass checks ambiguity, risky verbs, missing scope, evidence, and memory relevance
- strict preflight checks high-impact actions before execution governance
- shadow receipt records context hash, result id, finding ids, and verdict
- Mullu governance decides what can proceed

## Modes

| Mode | Use |
| --- | --- |
| `off` | Explicitly disabled by policy. |
| `light` | Cheap almost-always-on ambiguity and risk check. |
| `deep` | Required when ambiguity, memory contradiction, side effect, or high-impact verbs are present. |
| `strict_preflight` | Required before destructive, external, legal, financial, production, DNS, secret, or high-risk execution candidates. |

## Gate examples

| Request | Gate result | Reason |
| --- | --- | --- |
| `summarize release notes` | light | low-risk read-only request |
| `deploy it` | deep | ambiguous target and deployment verb |
| `continue the project` | deep | missing project/workflow scope |
| `delete old logs` | strict preflight | destructive action |
| `send contract` | strict preflight | external legal action |

## Safety rules

1. Shadow findings carry no execution authority.
2. Shadow receipts carry no execution authority.
3. A deep-required result is a routing signal, not an approval.
4. Strict preflight can recommend block, repair, or escalation, but Mullu governance owns the final verdict.
5. High-risk actions need explicit target, scope, and evidence before execution governance.
6. Ambiguous references such as `it`, `that`, or `this` cannot silently bind a target for side effects.
7. Memory contradictions create repair pressure before execution governance.
8. Scoring uses the production Mesh guard: `max(k - j, 1)`.

## Implemented v1 surfaces

- Shared dataclasses and bounded enums.
- Deterministic gate for off/light/deep/strict-preflight selection.
- Light interrogation pass.
- Strict preflight pass.
- Suppression scoring with Mesh denominator guard.
- Deterministic shadow receipts.
- Feature-flagged application integration facade.
- Read-only `POST /api/v1/shadow/inspect` route with a dedicated contract in
  `docs/INCEPTADIVE_SHADOW_INSPECTION_CONTRACT.md`.
- Replay fixture in
  `mcoi/tests/fixtures/inceptadive_shadow_inspect_replay.json` proving redacted
  response and receipt-count behavior.
- Live non-streaming assistant response embedding through
  `mcoi_runtime.app.inceptadive_assistant_response_embedding`, covering
  `POST /api/v1/chat` and `POST /api/v1/chat/workflow` with a dedicated
  contract in `docs/INCEPTADIVE_ASSISTANT_RESPONSE_EMBEDDING.md`.
- Focused tests covering gate, light pass, preflight, receipts, scoring, and disabled integration.
- Phi-GPS v3 bridge report in `mcoi_runtime.core.phi_inceptadive_bridge` that
  projects `ProblemStar` fields into Concept Boxes, runs bounded axis
  traversal, scores findings through the public InceptaMesh guard, and returns
  solver-mode suggestions without execution approval.

## Phi-GPS bridge boundary

The Phi-GPS bridge is an advisory structure-discovery pass:

```text
ProblemStar
-> Concept Boxes
-> InceptaDive axis findings
-> InceptaMesh scores
-> proof gaps, hidden assumptions, solver-mode suggestions
-> Phi-GPS governance and solver routing
```

The bridge may recommend diagnosis, proof construction, risk containment, or
design synthesis. It may not execute actions, approve actions, promote a truth
claim, bypass `Phi_gov`, or replace the Phi-GPS proof receipt.

## Deferred surfaces

The full external-effect InceptaDive-M engine remains a dedicated later module.
The current integration deliberately returns `deep_required` when the gate
selects deep mode outside the repository-local bridge instead of silently
pretending the full deep engine has run.
Streaming assistant response embedding remains deferred because SSE event
envelopes need a separate compatibility contract.

STATUS:
  Completeness: v1 foundation complete; repository-local Phi-GPS bridge added
  Invariants verified: no execution authority, strict preflight separation, deterministic receipts, denominator guard
  Open issues: external-effect deep engine integration is intentionally deferred
  Next action: merge after CI confirms focused and repository-wide tests
