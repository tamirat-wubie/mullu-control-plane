<!--
Purpose: define the evidence boundary for a future live task/run producer before implementation.
Governance scope: planning-only evidence contract for task intake, run projection, approval, receipt, sandbox, rollback, and status-route publication.
Dependencies: MULLUSI_AGENTIC_SERVICE_HARNESS_READ_MODEL_BINDING_PLAN.md, MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md, schemas/agentic_service_harness.schema.json, schemas/agentic_service_harness_live_task_run_producer_evidence.schema.json, schemas/agentic_service_harness_live_producer_admission_gate.schema.json, schemas/agentic_service_harness_live_producer_witness_requirements.schema.json, schemas/agentic_service_harness_live_producer_operator_approval_request.schema.json, schemas/agentic_service_harness_live_producer_operator_response_witness.schema.json, schemas/agentic_service_harness_live_producer_operator_decision_evidence.schema.json, schemas/agentic_service_harness_live_producer_operator_decision_record.schema.json, schemas/agentic_service_harness_live_producer_operator_decision_value_absence.schema.json, schemas/agentic_service_harness_live_producer_operator_decision_pending_status.schema.json, examples/agentic_service_harness.read_only.json, examples/agentic_service_harness_live_task_run_producer_evidence.local.json, examples/agentic_service_harness_live_producer_admission_gate.local.json, examples/agentic_service_harness_live_producer_witness_requirements.local.json, examples/agentic_service_harness_live_producer_operator_approval_request.local.json, examples/agentic_service_harness_live_producer_operator_response_witness.local.json, examples/agentic_service_harness_live_producer_operator_decision_evidence.local.json, examples/agentic_service_harness_live_producer_operator_decision_record.local.json, examples/agentic_service_harness_live_producer_operator_decision_value_absence.local.json, examples/agentic_service_harness_live_producer_operator_decision_pending_status.local.json, gateway/agentic_service_harness_live_task_run_producer.py, gateway/agentic_service_harness_live_producer_admission.py, gateway/agentic_service_harness_live_producer_witness_requirements.py, gateway/agentic_service_harness_live_producer_operator_approval.py, gateway/agentic_service_harness_live_producer_operator_response.py, gateway/agentic_service_harness_live_producer_operator_decision.py, gateway/agentic_service_harness_live_producer_operator_decision_record.py, gateway/agentic_service_harness_live_producer_operator_decision_value_absence.py, gateway/agentic_service_harness_live_producer_operator_decision_pending_status.py, scripts/validate_agentic_service_harness_live_task_run_producer_rehearsal.py, scripts/validate_agentic_service_harness_live_producer_admission_gate.py, scripts/validate_agentic_service_harness_live_producer_witness_requirements.py, scripts/validate_agentic_service_harness_live_producer_operator_approval_request.py, scripts/validate_agentic_service_harness_live_producer_operator_response_witness.py, scripts/validate_agentic_service_harness_live_producer_operator_decision_evidence.py, scripts/validate_agentic_service_harness_live_producer_operator_decision_record.py, scripts/validate_agentic_service_harness_live_producer_operator_decision_value_absence.py, scripts/validate_agentic_service_harness_live_producer_operator_decision_pending_status.py, docs/FOUNDATION_MODE.md.
Invariants: planning_only=true; live_producer_implemented=false; ui_created=false; mutation_endpoints_admitted=false; external_adapter_integrated=false; branch_write_enabled=false; pull_request_creation_enabled=false; deployment_enabled=false; dns_mutation_enabled=false; secret_mutation_enabled=false; destructive_operation_enabled=false.
-->

# Mullusi Agentic Service Harness Live Task/Run Producer Evidence

## Objective

Define the minimum evidence a future live task/run producer must emit before it can replace the runtime-local contract projection. This artifact includes a local dry-run rehearsal boundary, but does not implement a live producer.

Solver outcome: `SolvedVerified` for evidence-contract definition, local evidence fixture, local producer rehearsal, read-only rehearsal status projection, blocked live producer admission gate, live producer witness requirements packet, operator approval request packet, operator response witness packet, operator decision evidence boundary, operator decision record intake boundary, operator decision value absence witness, operator decision pending status, operator decision value intake preflight, generic continuation rejection witness, operator decision value request packet, operator decision value template packet, operator decision value collection gate, and operator decision value record path; `AwaitingEvidence` for live producer implementation and an actual explicit operator approval or rejection value.

## Scope

The future producer may only be admitted after it proves the following read-only evidence surfaces:

| Surface | Required evidence | Admission result |
| --- | --- | --- |
| `TaskIntakeEvidence` | task id, requester ref, tenant id, project id, requested mode, risk level, policy refs | required before run projection |
| `RunProjectionEvidence` | run id, task ref, sandbox ref, adapter ref, approval refs, receipt refs, evidence bundle refs | required before status-route publication |
| `ApprovalEvidence` | approval gate id, approver role, approval required flag, self-approval denial, external-effect denial | required for branch-write and pull-request modes |
| `ReceiptEvidence` | non-terminal receipt id, command refs, test refs, changed-file refs, policy result, next action | required for every produced run |
| `SandboxEvidence` | path allowlist, command allowlist, timeout, network policy, cleanup ref, redaction requirement | required before any dry-run or later effect-bearing mode |
| `RollbackEvidence` | rollback boundary, replay refs, cleanup refs, denied-effect refs | required before producer admission |
| `StatusPublicationEvidence` | read-only status-route source update ref, validator refs, no terminal closure claim | required before route consumes live output |

## Producer State Boundary

Allowed planning states:

```text
producer_contract_defined
-> evidence_fixture_ready
-> local_dry_run_ready
-> awaiting_approval_for_effects
-> blocked_high_risk
```

No state in this evidence contract executes a live adapter, writes a branch, opens a pull request, merges, deploys, mutates DNS, mutates secrets, sends external communication, moves money, or runs destructive operations.

## Required Guards

Every future live task/run producer admission must prove:

1. Tenant and project scope exist before any task or run record is emitted.
2. All task, run, approval, receipt, evidence, and result-summary records are append-only.
3. All command output, test logs, diffs, and provider details are represented as refs or hashes.
4. Secret values are never serialized.
5. External adapter execution remains blocked until a separate adapter evidence gate passes.
6. Branch write and pull-request creation remain approval-gated and disabled by default.
7. High-risk actions remain blocked by default: merge, deploy, DNS mutation, secret mutation, destructive operation.
8. Status-route publication is read-only and non-terminal.
9. Rollback and cleanup refs exist before local dry-run admission.
10. Missing evidence produces `AwaitingEvidence`, not a success claim.

## Forbidden Authority

The evidence contract does not create:

1. Dashboard UI.
2. Mutation endpoints.
3. Live external adapter integration.
4. GitHub branch creation.
5. Pull request creation.
6. Merge authority.
7. Deployment authority.
8. DNS mutation.
9. Secret mutation.
10. Destructive operation authority.
11. Terminal closure certificate.

Hard false flags:

```text
planning_only=true
live_producer_implemented=false
ui_created=false
mutation_endpoints_admitted=false
external_adapter_integrated=false
branch_write_enabled=false
pull_request_creation_enabled=false
deployment_enabled=false
dns_mutation_enabled=false
secret_mutation_enabled=false
destructive_operation_enabled=false
terminal_closure=false
```

## Acceptance Gates

| Gate | Required state |
| --- | --- |
| Contract validation | `python scripts/validate_agentic_service_harness_contract.py --strict` passes. |
| Read-model validation | `python scripts/validate_agentic_service_harness_read_models.py --strict` passes. |
| Runtime-local route validation | `python scripts/validate_agentic_service_harness_read_only_status_route.py` passes. |
| Evidence contract validation | `python scripts/validate_agentic_service_harness_live_task_run_producer_evidence.py` passes. |
| Evidence fixture validation | `schemas/agentic_service_harness_live_task_run_producer_evidence.schema.json` validates `examples/agentic_service_harness_live_task_run_producer_evidence.local.json`. |
| Local producer rehearsal | `python scripts/validate_agentic_service_harness_live_task_run_producer_rehearsal.py` passes. |
| Read-only rehearsal status projection | `GET /api/v1/harness/status` includes `producer_rehearsal` without granting live authority. |
| Live producer admission gate | `python scripts/validate_agentic_service_harness_live_producer_admission_gate.py` passes and returns `admission_decision=blocked`. |
| Live producer witness requirements | `python scripts/validate_agentic_service_harness_live_producer_witness_requirements.py` passes and keeps every witness at `AwaitingEvidence`. |
| Operator approval request | `python scripts/validate_agentic_service_harness_live_producer_operator_approval_request.py` passes and keeps approval uncollected and non-authorizing. |
| Operator response witness | `python scripts/validate_agentic_service_harness_live_producer_operator_response_witness.py` passes and keeps explicit response evidence missing and non-authorizing. |
| Operator decision evidence | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_evidence.py` passes and proves generic continuation does not satisfy approval. |
| Operator decision record | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_record.py` passes and proves generic continuation records no decision. |
| Operator decision value absence | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_absence.py` passes and proves no explicit approval or rejection value is present. |
| Operator decision pending status | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_pending_status.py` passes and proves the platform-facing decision gate remains blocked. |
| Operator decision value intake preflight | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_intake_preflight.py` passes and defines the future explicit value contract without collecting a value. |
| Generic continuation rejection witness | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_generic_continuation_rejection.py` passes and proves generic continuation is rejected as a non-decision input. |
| Operator decision value request | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_request.py` passes and asks for explicit approval or rejection without collecting a value. |
| Operator decision value template | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_template.py` passes and provides template-only approval/rejection shapes that are not accepted as values. |
| Operator decision value collection gate | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_collection_gate.py` passes and blocks collection route admission until an actual explicit value exists. |
| Operator decision value record path | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_record_path.py` passes and defines the future value-record path while keeping record creation blocked until an actual explicit value exists. |
| Operator decision value record | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_record.py` passes and records explicit approval as satisfying only the operator witness while every remaining witness stays `AwaitingEvidence`. |
| Effect receipt preflight | `python scripts/validate_agentic_service_harness_live_producer_effect_receipt_preflight.py` passes and keeps effect receipt collection blocked until admitted action, effect hash, reconciliation, rollback link, and redaction evidence exist. |
| External adapter evidence preflight | `python scripts/validate_agentic_service_harness_live_producer_external_adapter_evidence_preflight.py` passes and keeps adapter evidence blocked until adapter identity, sandbox proof, signed dispatch, live receipt, tenant scope, revocation path, and recovery evidence exist. |
| Secret handoff preflight | `python scripts/validate_agentic_service_harness_live_producer_secret_handoff_preflight.py` passes and keeps secret handoff blocked, redacted, and non-serializing until scoped lease, custodian, revocation, rotation, and no-raw-secret evidence exist. |
| Rollback proof preflight | `python scripts/validate_agentic_service_harness_live_producer_rollback_proof_preflight.py` passes and keeps rollback proof blocked until snapshot, rollback command, rehearsal result, effect link, recovery verification, and incident handoff refs exist. |
| Evidence packet intake | `python scripts/validate_agentic_service_harness_live_producer_evidence_packet_intake.py` passes and bundles the four remaining witness preflights into one read-only `AwaitingEvidence` packet without granting live producer authority. |
| Effect receipt packet | `python scripts/validate_agentic_service_harness_live_producer_effect_receipt_packet.py` passes and defines the admitted action, effect receipt, effect hash, reconciliation, rollback link, and redaction refs while keeping the actual effect receipt `AwaitingEvidence`. |
| External adapter evidence packet | `python scripts/validate_agentic_service_harness_live_producer_external_adapter_evidence_packet.py` passes and defines external adapter evidence, provider identity, adapter descriptor, capability scope, egress policy, redaction proof, signed dispatch evidence, and effect receipt linkage while keeping adapter evidence `AwaitingEvidence`. |
| Authority transition validation | `python scripts/validate_agentic_service_harness_authority_transitions.py` passes. |
| Workspace preflight | Full workspace governance preflight receipt passes. |

## Next Implementation Boundary

The next implementation layer may collect the remaining non-operator witness evidence into separate governed packets, continuing from the external adapter evidence packet into secret handoff and rollback proof packets. It must still avoid UI, mutation routes, live adapters, branch writes, pull-request creation, deployment, DNS mutation, secret mutation, and destructive operations until all witness requirements pass separately.

STATUS:
  Completeness: 100% for local live-producer evidence fixture, local producer rehearsal, read-only rehearsal status projection, blocked live producer admission gate, live producer witness requirements packet, operator approval request packet, operator response witness packet, operator decision evidence boundary, operator decision record intake boundary, operator decision value absence witness, operator decision pending status, operator decision value intake preflight, generic continuation rejection witness, operator decision value request packet, operator decision value template packet, operator decision value collection gate, operator decision value record path, operator decision value record, effect receipt preflight, external adapter evidence preflight, secret handoff preflight, rollback proof preflight, evidence packet intake, effect receipt packet, and external adapter evidence packet
  Invariants verified: planning_only=true, local_rehearsal_only=true, live_producer_implemented=false, producer_rehearsal route projection read-only, admission_decision=blocked, witness_status=AwaitingEvidence, approval_status=Satisfied, response_status=AwaitingEvidence, response_kind=operator_response_missing, decision_status=AwaitingEvidence, record_status=Satisfied, absence_status=AwaitingEvidence, pending_status=blocked_pending_operator_decision_value, intake_status=AwaitingEvidence, packet_status=blocked_awaiting_external_adapter_evidence_components, request_status=awaiting_explicit_operator_decision_value, template_status=template_only_awaiting_operator_value, gate_status=blocked_awaiting_explicit_operator_value, path_status=ready_blocked_awaiting_explicit_operator_value, effect_receipt_status=AwaitingEvidence, external_adapter_evidence_status=AwaitingEvidence, secret_handoff_status=AwaitingEvidence, rollback_proof_status=AwaitingEvidence, schema_ready=true, record_contract_ready=true, collection_route_admitted=false, record_path_admitted=false, collection_gate_satisfied=false, template_accepted_as_value=false, decision_gate_state=blocked, generic_continuation_rejected=true, authority_granted=false, ui_created=false, mutation_endpoints_admitted=false, external_adapter_integrated=false, adapter_credentials_present=false, adapter_credentials_serialized=false, branch_write_enabled=false, pull_request_creation_enabled=false, deployment_enabled=false, dns_mutation_enabled=false, secret_mutation_enabled=false, destructive_operation_enabled=false, runtime_state_written=false, live_execution_authorized=false
  Open issues: live producer implementation, effect receipt, external adapter evidence, secret handoff, rollback proof, dashboard UI, mutation endpoints, external adapter integration
  Next action: collect secret handoff and rollback proof as separate governed evidence packets before any live producer implementation
