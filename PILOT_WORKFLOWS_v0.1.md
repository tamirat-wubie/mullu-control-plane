# Pilot Workflows v0.1

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
