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
- Focused tests covering gate, light pass, preflight, receipts, scoring, and disabled integration.

## Deferred surfaces

The deep InceptaDive-M engine remains a dedicated later module. The current
integration deliberately returns `deep_required` when the gate selects deep mode
instead of silently pretending the full deep engine has run.

STATUS:
  Completeness: v1 foundation complete
  Invariants verified: no execution authority, strict preflight separation, deterministic receipts, denominator guard
  Open issues: deep axis traversal integration is intentionally deferred
  Next action: merge after CI confirms focused and repository-wide tests
