# Personal Assistant MVP Roadmap

Purpose: stage the personal-assistant capability layer into reversible, evidence-backed PRs.
Governance scope: Foundation Mode delivery sequencing, no live connector overreach, approval-gated escalation, receipt continuity, and memory staging.
Dependencies: personal-assistant schemas, policies, validators, capability pack, UAO, WHQR, existing communication capability pack, TeamOps shared-inbox gates, and Nested Mind staging validators.
Invariants: each PR has one bounded authority increase; live execution and public/customer claims require later evidence.

## Build Order

| PR | Scope | Explicit non-goals |
| --- | --- | --- |
| 1 | Architecture, schemas, policies, examples, capability pack, validators, tests | No runtime execution |
| 2 | Skill registry loader and validator integration | No live connector calls |
| 3 | Request intake and WHQR missing-binding emission | No execution |
| 4 | Read-only inbox and calendar summaries | No send, delete, archive, create, move, cancel, invite |
| 5 | Draft-only assistant artifacts | No external communication |
| 6 | Approval queue read/preview projection | No approval auto-grant; no execution after approval |
| 7 | Memory observations | No raw chat-log storage; no live Nested Mind activation |
| 8 | TeamOps shared inbox planning and handoff | No mailbox mutation without approval evidence |
| 9 | User-facing assistant console | No customer/SaaS readiness claim |

## PR 1 Acceptance Criteria

1. Documentation names the assistant as a governed user-intent interpreter.
2. Schemas validate request, skill, plan, approval, receipt, and memory-observation records.
3. Skill policy and approval matrix preserve P0-P5 boundaries.
4. Capability pack grants planning and governance authority only.
5. Examples cover inbox summary, calendar brief, registry, approval packet, and draft-only receipt.
6. Validators reject read-only mutation, draft-only send, missing P4/P5 approval, receipt under-reporting, raw private payloads, secret-like values, and under-specified memory observations.
7. Tests prove all required boundary cases.

## Future Authority Ladder

```text
schema witness
-> registry witness
-> intake witness
-> read-only connector witness
-> draft witness
-> approval witness
-> internal write witness
-> external communication witness
-> TeamOps shared-inbox witness
-> console witness
```

No stage may skip UAO admission, approval classification, receipt emission, and rollback or compensation planning where effect-bearing action exists.

## PR 6 Acceptance Criteria

1. Approval queue projections validate against `schemas/personal_assistant_approval_queue.schema.json`.
2. Queue records embed schema-valid approval packets and personal-assistant receipts.
3. Pending, approved, rejected, and revised decisions remain evidence records only.
4. Public routes expose read/preview projections without persistence claims or connector mutation.
5. `approval_is_execution`, `execution_allowed`, `external_send_allowed`, and `connector_mutation_allowed` remain false.
6. Raw private connector payloads, raw message bodies, credentials, tokens, and secret-like values are rejected.
7. Proof coverage classifies approval queue routes under the assistant planning surface.

## Handoff Risks

| Boundary | Risk | Control |
| --- | --- | --- |
| Product to engineering | Assistant becomes broad instead of governed | Keep PR scope one lane at a time |
| Design to engineering | Chat surface hides approval gates | Approval packet and receipt viewer are required UI surfaces later |
| Engineering to operations | Live connector read/write overclaim | Treat live provider calls as `AwaitingEvidence` until witness exists |
| Engineering to memory | Raw conversation storage | Store only typed memory observations with receipt refs |
| Engineering to public surface | Customer readiness overclaim | Keep Foundation Mode language until named witnesses exist |

## Verification Ladder

PR 1 should run static validators and tests only. Later PRs add runtime validators after each lane has capability evidence.
