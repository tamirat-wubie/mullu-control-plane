# First Usable Demo Packet — Governed Personal Assistant

Purpose: compress the Mullu Govern / Mullu Control Plane platform into one reviewable first product slice that a non-technical operator can understand and a developer can build toward without promoting unsupported live-execution claims.

Governance scope: product compression, personal-assistant demo sequencing, approval boundary, evidence references, no-effect authority, deployment/readiness claim separation, and next implementation gates.

Dependencies: `docs/explain/PLAIN_ENGLISH.md`, `docs/PERSONAL_ASSISTANT_SKILL_ARCHITECTURE.md`, `docs/63_finance_approval_packet_pilot.md`, `STATUS.md`, `DEPLOYMENT_STATUS.md`, `examples/first_usable_demo_packet.json`, `scripts/validate_first_usable_demo_packet.py`, and `scripts/render_first_usable_demo_operator_page.py`.

Invariants:
- The first demo is **draft-only / no-effect** until later evidence promotes a narrower action.
- It must not send email, move money, create calendar events, mutate connectors, write memory, deploy, publish, or claim customer readiness.
- It must expose a clear operator result: what was requested, what was checked, what was blocked, what was approved for review, what evidence exists, and what remains missing.
- Public-health or deployment evidence must not be converted into customer-readiness, live-agent, paid-use, or legal/business readiness.
- Every demo step must preserve receipts, evidence references, blocked-action records, and rollback/recovery notes.

## One-sentence product compression

Mullu Govern becomes understandable when the first demo is this:

```text
A user asks for one consequential assistant task;
the control plane turns it into a bounded proposal;
policy, authority, budget, evidence, and approval gates decide what is allowed;
the system produces only a safe draft/receipt/read-model;
no live external effect occurs until a later witness allows it.
```

## Canonical first demo

**Name:** Governed Personal Assistant First Usable Demo

**User story:**

```text
As an operator, I ask the assistant to review one invoice-related request and prepare a vendor email draft.
The system must classify the request, check policy and approval requirements, show whether it is blocked or reviewable, produce a redacted draft handoff receipt, export proof, and show an operator read model.
It must not send the email, pay the invoice, mutate Gmail, mutate accounting records, or claim customer readiness.
```

## Demo lane

| Step | Surface | Output | Authority |
| --- | --- | --- | --- |
| 1 | Personal Assistant intake | Structured request object | No effect |
| 2 | WHQR / missing-binding review | Missing entity, evidence, action, or approval bindings | No effect |
| 3 | Skill router | Inbox / finance / document / planning lane selection | No effect |
| 4 | Policy and risk classifier | P-level risk, approval requirement, blocked action list | No effect |
| 5 | Draft plan builder | Preview-only action plan | No effect |
| 6 | Approval review packet | Operator-facing review packet | Approval is not execution |
| 7 | Receipt and proof export | Redacted receipt, evidence refs, proof-ready status | No external effect |
| 8 | Operator read model | Clear status: blocked, awaiting evidence, reviewable, proof-ready | Read-only |

## Required visible result

The first usable demo is successful only when an operator can answer these questions from one page or command output:

1. What did the assistant understand the user wanted?
2. Which exact action is proposed?
3. What is blocked by policy or missing evidence?
4. What approval would be required before any external effect?
5. What draft or preview was produced?
6. What actions were explicitly not taken?
7. What receipt and proof references were generated?
8. What is the next safe action?

## Operator render

The packet now has a read-only renderer that emits a deterministic operator read model and static HTML page without opening any live authority:

```bash
python scripts/render_first_usable_demo_operator_page.py \
  --generated-at 2026-06-22T00:00:00Z \
  --read-model-output .change_assurance/first_usable_demo_operator_read_model.json \
  --html-output .change_assurance/first_usable_demo_operator_page.html \
  --json
```

The renderer is intentionally local and no-effect. It does not call connectors, create provider drafts, send email, move money, write memory, mutate deployments, or claim customer readiness.

## Promotion gates

| Gate | Required before promotion |
| --- | --- |
| Read-only demo | Static packet validates and renders without raw private payloads. |
| Draft-only demo | Draft projection proves no connector mutation and no external send. |
| Approval-review demo | Approval packet exists but `approval_is_execution=false`. |
| Dry-run adapter demo | UAO admission, dry-run adapter evidence, redaction, rollback plan, and effect receipt schema exist. |
| Live connector demo | Explicit operator approval, connector authority proof, signed effect receipt, rollback/recovery evidence, and terminal closure certificate exist. |
| Customer pilot | Separate customer-readiness witness, support boundary, legal/business review, data boundary, and incident/recovery procedure exist. |

## Constructive deltas applied

- Adds a single named product slice so future work does not scatter across unrelated platform surfaces.
- Separates deployment/public-health evidence from customer readiness and live assistant authority.
- Converts “first product” into an auditable demo packet with a validator and expected no-effect authority fields.
- Adds a static read-only operator render that turns the packet into an operator page/read model.
- Gives the next implementation sequence: read-only → draft-only → approval-review → dry-run adapter → live connector → customer pilot.

## Fracture deltas still open

- This packet does not create a live UI, connector, Gmail call, payment call, memory write, deployment mutation, or customer-facing service.
- README, plain-English, status, and deployment surfaces still need a later synchronization pass so public-health evidence and Foundation Mode language do not conflict.
- The rendered operator page is static/local; a live API route remains a later bounded promotion.
- The finance approval pilot and personal-assistant packet still need one shared end-to-end walkthrough before live use can be considered.

## Next implementation order

1. Bind the packet to the existing personal-assistant console read model.
2. Add a draft-only invoice/email walkthrough that emits no external effect.
3. Add an approval-review packet that proves approval is not execution.
4. Add a dry-run adapter witness only after UAO, redaction, rollback, and receipt gates exist.
5. Reconcile README / plain-English / `STATUS.md` / `DEPLOYMENT_STATUS.md` claim language in one later claim-synchronization PR.

## Audit and refinement result

Judgment: `SolvedReviewable`.

Reason: this packet closes the product-compression gap at the planning and evidence layer while preserving the current no-effect boundary. It is intentionally not a live execution claim.
