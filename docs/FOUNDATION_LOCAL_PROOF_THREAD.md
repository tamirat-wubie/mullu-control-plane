<!--
Purpose: define the first local proof thread for solo-founder Foundation Mode.
Governance scope: local workflow composition, approval boundary, receipt evidence, rollback note, and deployment/customer-access restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, examples/foundation_local_proof_thread.workflow.json, scripts/validate_foundation_local_proof_thread.py, scripts/run_foundation_local_proof_thread.py.
Invariants: local-only execution, no customer access claim, no deployment claim, no real payment, no live credential, no external endpoint dependency.
-->

# Foundation Local Proof Thread

<!-- TYPE: Tutorial -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** the first proof thread is one harmless local workflow that
> proves the control shape before anything public or costly happens. It takes a
> local request, classifies it, checks policy, asks for local approval, produces
> a small local result, writes receipt evidence, verifies the result, and records
> a rollback note.

This is not deployment. This is not a pilot. This is not customer access. This
is the smallest proof that the work can move through governed stages.

Descriptor: [`../examples/foundation_local_proof_thread.workflow.json`](../examples/foundation_local_proof_thread.workflow.json)

Local runner:

```powershell
python scripts/run_foundation_local_proof_thread.py
```

Default local evidence:

```text
.change_assurance/foundation_local_proof_thread_result.json
.change_assurance/foundation_local_proof_thread_receipt.json
```

## Goal

Prove this local chain:

```text
local request
  -> intent classification
  -> policy and authority check
  -> local approval gate
  -> harmless local action
  -> receipt evidence
  -> verification
  -> rollback note
  -> closure
```

## Stage Contract

| Stage | Type | Purpose | Evidence |
| --- | --- | --- | --- |
| `stage_intake` | `observation` | Capture one local request and the forbidden effects. | Local request reference. |
| `stage_classify_intent` | `skill_execution` | Classify the request as local-only, reversible, and non-external. | Intent classification result. |
| `stage_policy_authority_check` | `skill_execution` | Check policy, authority, and Foundation Mode boundaries. | Policy decision result. |
| `stage_local_approval` | `approval_gate` | Require the operator to approve the harmless local action. | Approval reference or timeout. |
| `stage_create_local_result` | `skill_execution` | Produce a small local document or JSON result. | Local result reference. |
| `stage_verify_local_result` | `observation` | Verify the result exists and contains no external-effect claim. | Verification result. |
| `stage_record_rollback_note` | `skill_execution` | Record how to undo, delete, or ignore the local result. | Rollback note reference. |
| `stage_close_receipt` | `observation` | Close with pass/fail, evidence refs, and open issues. | Closure receipt reference. |

## Forbidden Effects

The first proof thread must not:

1. call public endpoints;
2. use live credentials;
3. move money;
4. send messages to outside people;
5. publish, deploy, or mutate DNS;
6. open customer, beta, waitlist, or pilot access;
7. claim legal, company, patent, compliance, or production readiness.

Rule: No customer access or deployment claim.

## Success Criteria

The proof thread is locally complete only when:

1. the workflow descriptor validates;
2. every stage has a stable id and type;
3. every binding references existing stages;
4. the graph is acyclic;
5. an `approval_gate` exists before the harmless local action;
6. rollback/recovery is named before closure;
7. validation can run without external network, secrets, or paid services.

## Expected Outcome

Current status is `EvidenceLocal` after the descriptor, validator, and local
runner pass. The default receipt is local evidence only; it is not a deployment,
pilot, customer, legal, or production-readiness witness.

---

## Go deeper / where to go next

| You now want to... | Go to |
| --- | --- |
| See why this is the next step | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Understand the current posture | [Foundation Mode](FOUNDATION_MODE.md) |
| Understand workflow runtime rules | [Workflow Runtime](21_workflow_runtime.md) |
| Start from the front door | [Start Here](START_HERE.md) |

STATUS:
  Completeness: 100%
  Invariants verified: local-only, approval-gated, receipt-bound, rollback-named, no deployment claim, no customer access claim
  Open issues: external deployment, customer, pilot, legal, and runtime witnesses remain AwaitingEvidence
  Next action: review the local receipt, then choose the next Foundation Mode prerequisite
