<!--
Purpose: define the Foundation Mode boundary for rehearsing issue #330 runtime secret handoff gates without recording secret values, binding secrets, mounting workflow secrets, or claiming secret presence.
Governance scope: issue #330, runtime witness secret handoff rehearsal, runtime conformance secret handoff rehearsal, deployment witness secret handoff rehearsal, local handoff labels, secret-value blocking, secret-presence blocking, repository-secret binding blocking, runtime secret-store binding blocking, workflow blocking, publication blocking, and deployment restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md, examples/foundation_runtime_secret_handoff_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_runtime_secret_handoff_rehearsal_boundary.py.
Invariants: no runtime witness secret-name claim, no runtime conformance secret-name claim, no deployment witness secret-name claim, no secret value, no ignored local handoff path, no secret-manager target, no operator identity, no dual-control verification, no secret-presence attestation, no rotation claim, no revocation claim, no workflow secret mount claim, no runtime env binding claim, no preflight secret-gate pass claim, no repository-secret binding, no runtime secret-store binding, no workflow dispatch, no artifact publication, no readiness claim, no customer access, no personal-data collection, no money movement, no legal/company/patent claim, no external publication, and no deployment claim.
-->

# Foundation Runtime Secret Handoff Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** runtime secret handoff rehearsal means naming the future gates
> for moving runtime witness, runtime conformance, and deployment witness secret
> material into the correct runtime secret manager. It does not record secret
> values, record private file paths, bind repository secrets, bind runtime
> secret stores, mount workflow secrets, claim secret presence, dispatch
> workflows, publish artifacts, open access, move money, make legal/business
> claims, publish externally, or deploy.

Witness packet: [`../examples/foundation_runtime_secret_handoff_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_runtime_secret_handoff_rehearsal_witness.awaiting_evidence.json)

Rule: Runtime secret handoff rehearsal is a local gate-label map for future
operator-owned secret handoff. It is not secret storage, not secret presence
proof, not repository secret binding, not runtime secret-store binding, not
workflow secret mounting, not preflight pass evidence, and not deployment
readiness.

No runtime witness secret-name claim, runtime conformance secret-name claim,
deployment witness secret-name claim, secret value, ignored local handoff path,
secret-manager target, operator identity, dual-control verification,
secret-presence attestation, rotation claim, revocation claim, workflow secret
mount claim, runtime env binding claim, preflight secret-gate pass claim,
repository-secret binding, runtime secret-store binding, workflow dispatch,
artifact publication, readiness claim, customer access, personal-data
collection, money movement, legal/company/patent claim, external publication, or
deployment claim is permitted by this boundary.

## What This Boundary Solves

Issue #330 requires runtime witness and runtime conformance secrets to exist in
the deployed gateway runtime before a deployment witness can be collected. In
Foundation Mode, the correct local action is not to read or move secrets. The
correct local action is to prepare the public-safe handoff gates that will later
protect that external operation.

Use it when the question is:

1. Which runtime secret handoff gates must exist before witness dispatch?
2. Which secret-related facts must stay out of Git and public artifacts?
3. Which handoff checks are labels today, not real secret-presence proof?
4. Which gates prevent a secret handoff rehearsal from becoming readiness
   evidence?
5. Which reassessment gate keeps this work local until operator-owned secret
   receipts exist?

## Current State

```text
runtime_secret_handoff_rehearsal_state=AwaitingEvidence
runtime_witness_secret_name_recorded=false
runtime_conformance_secret_name_recorded=false
deployment_witness_secret_name_recorded=false
secret_value_recorded=false
ignored_local_handoff_path_recorded=false
secret_manager_target_recorded=false
operator_identity_recorded=false
dual_control_verified=false
secret_presence_attestation_claimed=false
secret_rotation_claimed=false
secret_revocation_claimed=false
workflow_secret_mount_claimed=false
runtime_env_binding_claimed=false
preflight_secret_gate_pass_claimed=false
repository_secret_binding_allowed=false
runtime_secret_store_binding_allowed=false
workflow_dispatch_allowed=false
artifact_publication_allowed=false
readiness_claimed=false
customer_access_allowed=false
personal_data_collection_allowed=false
money_movement_allowed=false
legal_clearance_claimed=false
company_formation_claimed=false
patent_claimed=false
external_publication_allowed=false
deployment_allowed=false
```

## Public-Safe Handoff Labels

These labels are handoff gates only. They are not secret names, secret values,
private file paths, secret-manager targets, operator identities, repository
secret bindings, runtime secret-store bindings, workflow mounts, preflight pass
ids, approvals, or proof that a secret exists.

| Label | Later handoff class | Boundary |
| --- | --- | --- |
| `runtime_witness_secret_name_label` | Future runtime witness secret-name gate. | Do not record or claim the secret name. |
| `runtime_conformance_secret_name_label` | Future runtime conformance secret-name gate. | Do not record or claim the secret name. |
| `deployment_witness_secret_name_label` | Future deployment witness secret-name gate. | Do not record or claim the secret name. |
| `runtime_secret_manager_target_label` | Future runtime secret-manager target gate. | Do not record target values. |
| `ignored_local_handoff_file_label` | Future ignored-file handoff gate. | Do not record private paths. |
| `handoff_operator_identity_label` | Future operator identity gate. | Do not record identities. |
| `dual_control_gate_label` | Future dual-control gate. | Do not claim dual-control proof. |
| `secret_value_absence_gate_label` | Future no-value gate. | Do not record secret values. |
| `secret_presence_attestation_label` | Future presence attestation gate. | Do not claim secret presence. |
| `secret_rotation_gate_label` | Future rotation gate. | Do not claim rotation. |
| `secret_revocation_gate_label` | Future revocation gate. | Do not claim revocation. |
| `workflow_secret_mount_gate_label` | Future workflow mount gate. | Do not claim workflow secret mount. |
| `runtime_env_binding_gate_label` | Future runtime env binding gate. | Do not claim runtime env binding. |
| `preflight_secret_gate_label` | Future preflight secret gate. | Do not claim preflight pass. |
| `operator_reassessment_gate` | Future reassessment gate. | Do not approve readiness or deployment. |

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Runtime witness secret | Record the gate label only. | Do not record or claim secret names or values. |
| Runtime conformance secret | Record the gate label only. | Do not record or claim secret names or values. |
| Deployment witness secret | Record the gate label only. | Do not record or claim secret names or values. |
| Secret-manager target | Record the gate label only. | Do not record target values. |
| Ignored handoff file | Record the gate label only. | Do not record private paths. |
| Operator identity | Record the gate label only. | Do not record identities. |
| Dual control | Record the gate label only. | Do not claim dual-control proof. |
| Value absence | Record the gate label only. | Do not record secret values. |
| Secret presence | Record the gate label only. | Do not claim secret presence. |
| Rotation | Record the gate label only. | Do not claim rotation. |
| Revocation | Record the gate label only. | Do not claim revocation. |
| Workflow mount | Record the gate label only. | Do not claim workflow secret mount. |
| Runtime env binding | Record the gate label only. | Do not claim runtime env binding. |
| Preflight secret gate | Record the gate label only. | Do not claim preflight pass. |
| Operator reassessment | Record the gate label only. | Do not approve readiness or deployment. |

## Operator Procedure

1. Treat this boundary as a runtime secret handoff rehearsal, not as a secret
   receipt.
2. Keep only public-safe labels and blocked-gate notes in Git.
3. Do not place secret names, secret values, private file paths, secret-manager
   targets, operator identities, repository secret ids, workflow run ids,
   artifact ids, approval references, timestamps, hashes, personal data,
   customer data, payment details, or provider account details in this witness.
4. Stop if the next step requires reading secrets, moving secrets, binding
   repository secrets, binding runtime secret stores, mounting workflow secrets,
   claiming secret presence, running preflight as ready, dispatching workflows,
   publishing artifacts, opening customer access, payment, legal/business
   action, external publication, or deployment.
5. Keep the rehearsal in `AwaitingEvidence` until operator-owned secret handoff
   receipts exist and the preflight, gateway publication, deployment witness,
   evidence acceptance, and public health gates can each pass their own
   validators.

## Validation

Run:

```powershell
python scripts/validate_foundation_runtime_secret_handoff_rehearsal_boundary.py
```

The validator checks that the runtime secret handoff rehearsal witness:

1. keeps every handoff surface in `AwaitingEvidence`;
2. keeps secret names, secret values, private handoff paths, secret-manager
   targets, operator identities, dual-control proof, secret-presence proof,
   rotation, revocation, workflow secret mounts, runtime env binding, preflight
   pass claims, repository-secret binding, runtime secret-store binding,
   workflow dispatch, artifact publication, readiness, customer access, money,
   legal/business claims, publication, and deployment blocked;
3. allows only public-safe handoff labels and blocked-gate notes;
4. rejects URLs, host-looking values, IP-looking values, timestamps, private
   paths, email-like identifiers, secret/key material, hash-like values, and
   assignment shapes for secret facts; and
5. rejects secret-presence, secret-binding, workflow-mount, preflight-pass,
   readiness, approval, publication, and deployment promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Prepare general secret/credential questions | [Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md) |
| Rehearse production dependency labels | [Foundation Production Dependency Evidence Rehearsal Boundary](FOUNDATION_PRODUCTION_DEPENDENCY_EVIDENCE_REHEARSAL_BOUNDARY.md) |
| Rehearse deployment witness preflight labels | [Foundation Deployment Witness Preflight Rehearsal Boundary](FOUNDATION_DEPLOYMENT_WITNESS_PREFLIGHT_REHEARSAL_BOUNDARY.md) |
| Rehearse evidence acceptance gates | [Foundation External Evidence Acceptance Rehearsal Boundary](FOUNDATION_EXTERNAL_EVIDENCE_ACCEPTANCE_REHEARSAL_BOUNDARY.md) |
| Reassess without promotion | [Foundation Reassessment Gate Boundary](FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: runtime witness secret-name claim blocked, runtime conformance secret-name claim blocked, deployment witness secret-name claim blocked, secret values blocked, private handoff paths blocked, secret-manager targets blocked, operator identities blocked, dual-control proof blocked, secret-presence attestation blocked, rotation claim blocked, revocation claim blocked, workflow secret mount claim blocked, runtime env binding claim blocked, preflight secret-gate pass blocked, repository-secret binding blocked, runtime secret-store binding blocked, workflow dispatch blocked, artifact publication blocked, readiness not claimed, customer access blocked, money movement blocked, legal/company/patent claims blocked, external publication blocked, deployment blocked
  Open issues: all runtime secret handoff surfaces remain AwaitingEvidence
  Next action: validate this runtime secret handoff rehearsal before any future secret handoff, gateway publication, deployment witness, or public health work
