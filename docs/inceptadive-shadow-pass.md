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
- Read-only `POST /api/v1/shadow/external-effect/advisory` route exposing
  redacted authority/evidence obligation status for operator visibility.
- Replay fixture in
  `mcoi/tests/fixtures/inceptadive_shadow_inspect_replay.json` proving redacted
  response and receipt-count behavior.
- Live assistant response embedding through
  `mcoi_runtime.app.inceptadive_assistant_response_embedding`, covering
  `POST /api/v1/chat`, `POST /api/v1/chat/workflow`, and
  `POST /api/v1/chat/stream` with a dedicated contract in
  `docs/INCEPTADIVE_ASSISTANT_RESPONSE_EMBEDDING.md`. Streaming chat carries
  the advisory as a side SSE event named `inceptadive_shadow_advisory`.
- Bounded external-effect preflight supplementation through
  `InceptaDiveShadowRuntime.preflight_action`: when the deep engine is
  explicitly enabled, strict preflight can append bounded deep advisory findings
  for external-effect, high-risk, or memory-contradicted candidate actions.
  The returned result remains `strict_preflight` and does not gain execution
  authority.
- External-effect boundary advisory through
  `mcoi_runtime.core.inceptadive_external_effect_boundary` and
  `InceptaDiveShadowRuntime.external_effect_advisory`. This derives missing
  evidence and authority obligations for effect-bearing candidates without
  dispatching connectors, approving execution, writing memory, or replacing a
  governance verdict.
- Redacted external-effect advisory history through the shadow receipt store.
  The console evidence route can aggregate missing authority and evidence
  obligation counts without exposing raw request text, raw evidence refs, raw
  authority refs, private memory, or execution handles.
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

The live external-effect InceptaDive-M adapter engine remains a dedicated later
module for effect-bearing integration. The current integration applies bounded
repository-local deep advisory findings to strict preflight only when the deep
engine is explicitly enabled, and now exposes a redacted external-effect
boundary advisory for authority/evidence obligations. It still returns
  `deep_required` when the gate selects deep mode and the bounded deep engine is
  unavailable, instead of silently pretending that a full live adapter engine has
  run. Redacted advisory history improves operator evidence visibility but does
  not add live adapter execution.

STATUS:
  Completeness: v1 foundation complete; repository-local Phi-GPS bridge, bounded preflight deep advisory, external-effect boundary advisory, redacted advisory history, and route projection added
  Invariants verified: no execution authority, strict preflight separation, deterministic receipts, denominator guard, no connector dispatch authority, no raw external-effect refs in advisory history
  Open issues: live external-effect adapter engine remains intentionally deferred
  Next action: keep full effect-bearing integration behind explicit governance and live adapter evidence
