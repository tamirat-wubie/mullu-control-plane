# Pilot Workflows v0.1

> **In one box:** Three concrete, controlled end-to-end workflows that prove
> Mullu works as a whole system — good worked examples to follow after the
> [Tutorial](docs/tutorials/01_first_governed_task.md). New here? →
> [Plain-English Overview](docs/explain/PLAIN_ENGLISH.md); unknown word? →
> [Glossary](docs/GLOSSARY.md). *(Doc type: How-to.)*

Three controlled pilot workflows that prove the platform works as a system.

## Pilot 1: Approval-Gated Command

**Purpose:** Prove the full trust loop — autonomy blocks execution until explicit approval.

**Steps:**
1. Autonomy engine evaluates EXECUTE_WRITE in approval_required mode -> BLOCKED_PENDING_APPROVAL
2. System generates correlated approval request email
3. Inbound approval email is parsed with correlation matching
4. Approval decision unlocks execution
5. Skill executes through governed runtime path
6. Run report surfaces autonomy mode and provider IDs

**Config:** `examples/pilots/approval_gated_command/config.json` (autonomy_mode: approval_required)
**Request:** `examples/pilots/approval_gated_command/request.json`

**Expected outcomes:**
- Without approval: execution blocked, typed decision surfaced
- With approval: execution proceeds, report shows approved status
- Console shows autonomy_mode in rendered output

---

## Pilot 2: Document-to-Action

**Purpose:** Prove holistic automation — document drives skill selection and execution.

**Steps:**
1. JSON document ingested with deterministic fingerprint
2. Fields extracted from structured content
3. Extraction verified against expected values
4. Verification mismatch fails closed (no false success)
5. Verified task routes to correct skill by ID
6. Completion notice generated with execution correlation

**Config:** `examples/pilots/document_to_action/config.json` (autonomy_mode: bounded_autonomous)
**Input:** `examples/pilots/document_to_action/input_document.json`

**Expected outcomes:**
- Extracted fields match document content exactly
- Value mismatch produces FAIL verification status
- Skill executes and completion email carries correlation IDs

---

## Pilot 3: Failure-Escalation

**Purpose:** Prove operational resilience — failures update confidence and trigger escalation.

**Steps:**
1. Skill execution fails (nonexistent route)
2. Skill confidence decreases from outcome
3. Meta-reasoning detects degraded capability (below threshold)
4. Escalation email generated with failure context and goal linkage
5. Run report surfaces provider IDs, autonomy mode, and degraded state

**Config:** `examples/pilots/failure_escalation/config.json` (autonomy_mode: bounded_autonomous)

**Expected outcomes:**
- Failed skill has lower confidence after execution
- Degraded capability appears in meta-reasoning
- Escalation email carries correct correlation and goal IDs
- Report includes all provider identity and autonomy fields

---

## Pilot 4: Governed Private Pilot Story

**Purpose:** Prove the organization-to-dashboard governance path in read-only
mode before a live tenant pilot is executed.

**Steps:**
1. OrgOS department request surfaces tenant-scoped department registry and authority map refs.
2. UAO envelope binds approved, blocked, and simulated decision branches with traces.
3. Governor chain links policy, decision, design, coding, quality, release, and runtime review.
4. SDLC gate projects change, stage, blocker, evidence, receipt, and closure continuity.
5. Receipt closure collects UAO, causal trace, SDLC, and closure receipt refs.
6. Dashboard view exposes read-only OrgOS and SDLC operator surfaces.

**Read model:** `/software/receipts/private-pilot/story`

**Expected outcomes:**
- The story grants no execution authority and invokes no live capability.
- Approved, blocked, and read-only rehearsal UAO branches remain visible.
- OrgOS, governor-chain, SDLC, receipt, trace, and dashboard refs are linked.
- Live product claims remain blocked until a tenant-bound pilot rehearsal runs.
