"""Forge state-write admission adapter.

Purpose: evaluate proposed Forge write-spine state transitions as a
    repository-local reference admission packet before any runtime commit path
    exists.
Governance scope: Phi_gov certificate binding, H_lineage attestation ordering,
    service-boundary constraints, production authority denial, and receipt
    hashing for state-write admission.
Dependencies: dataclasses, datetime, hashlib, JSON serialization, and regex.
Invariants:
  - The adapter never mutates live state or calls an external service.
  - Commit authority is always false in Foundation Mode.
  - Production state-changing authority is always blocked.
  - Prepared transition modeling requires ordered write-spine evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
import hashlib
import json
import re
from typing import Any


FORGE_STATE_WRITE_ADMISSION_ADAPTER_ID = "forge-state-write-admission.v1"
FORGE_STATE_WRITE_ADMISSION_PACKET_SCHEMA_REF = (
    "urn:mullusi:schema:forge-state-write-admission-packet:1"
)
FORGE_LIVE_RUNTIME_READINESS_GATE_SCHEMA_REF = (
    "urn:mullusi:schema:forge-live-runtime-readiness-gate:1"
)
FORGE_LIVE_RUNTIME_EVIDENCE_COLLECTION_PACKET_SCHEMA_REF = (
    "urn:mullusi:schema:forge-live-runtime-evidence-collection-packet:1"
)
FORGE_LIVE_RUNTIME_LOCAL_EVIDENCE_BUNDLE_SCHEMA_REF = (
    "urn:mullusi:schema:forge-live-runtime-local-evidence-bundle:1"
)
FORGE_LIVE_RUNTIME_EVIDENCE_ACCEPTANCE_GATE_SCHEMA_REF = (
    "urn:mullusi:schema:forge-live-runtime-evidence-acceptance-gate:1"
)
FORGE_LIVE_RUNTIME_SIGNED_EVIDENCE_RECEIPT_SCHEMA_REF = (
    "urn:mullusi:schema:forge-live-runtime-signed-evidence-receipt:1"
)
FORGE_LIVE_RUNTIME_PROBE_ADMISSION_PACKET_SCHEMA_REF = (
    "urn:mullusi:schema:forge-live-runtime-probe-admission-packet:1"
)
FORGE_LIVE_RUNTIME_APPROVED_PROBE_OUTPUT_PACKET_SCHEMA_REF = (
    "urn:mullusi:schema:forge-live-runtime-approved-probe-output-packet:1"
)
FORGE_LIVE_RUNTIME_POST_PROBE_RECONCILIATION_PACKET_SCHEMA_REF = (
    "urn:mullusi:schema:forge-live-runtime-post-probe-reconciliation-packet:1"
)
FORGE_LIVE_RUNTIME_SIGNED_RECEIPT_POPULATION_GATE_SCHEMA_REF = (
    "urn:mullusi:schema:forge-live-runtime-signed-receipt-population-gate:1"
)
FORGE_LIVE_RUNTIME_EVIDENCE_CHAIN_READ_MODEL_SCHEMA_REF = (
    "urn:mullusi:schema:forge-live-runtime-evidence-chain-read-model:1"
)
FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_REQUEST_SCHEMA_REF = (
    "urn:mullusi:schema:forge-live-runtime-operator-evidence-request:1"
)
FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_SUBMISSION_PACKET_SCHEMA_REF = (
    "urn:mullusi:schema:forge-live-runtime-operator-evidence-submission-packet:1"
)
FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_VERIFICATION_GATE_SCHEMA_REF = (
    "urn:mullusi:schema:forge-live-runtime-operator-evidence-verification-gate:1"
)
FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_ACCEPTANCE_HANDOFF_PACKET_SCHEMA_REF = (
    "urn:mullusi:schema:forge-live-runtime-operator-evidence-acceptance-handoff-packet:1"
)
FORGE_WRITE_SPINE_BRIDGE_ID = "forge_write_spine_bridge.v1"
FORGE_LIVE_RUNTIME_READINESS_GATE_ID = "forge-live-runtime-readiness-gate.v1"
FORGE_LIVE_RUNTIME_EVIDENCE_COLLECTION_PACKET_ID = "forge-live-runtime-evidence-collection-packet.v1"
FORGE_LIVE_RUNTIME_LOCAL_EVIDENCE_BUNDLE_ID = "forge-live-runtime-local-evidence-bundle.v1"
FORGE_LIVE_RUNTIME_EVIDENCE_ACCEPTANCE_GATE_ID = "forge-live-runtime-evidence-acceptance-gate.v1"
FORGE_LIVE_RUNTIME_SIGNED_EVIDENCE_RECEIPT_ID = "forge-live-runtime-signed-evidence-receipt.v1"
FORGE_LIVE_RUNTIME_PROBE_ADMISSION_PACKET_ID = "forge-live-runtime-probe-admission-packet.v1"
FORGE_LIVE_RUNTIME_APPROVED_PROBE_OUTPUT_PACKET_ID = "forge-live-runtime-approved-probe-output-packet.v1"
FORGE_LIVE_RUNTIME_POST_PROBE_RECONCILIATION_PACKET_ID = (
    "forge-live-runtime-post-probe-reconciliation-packet.v1"
)
FORGE_LIVE_RUNTIME_SIGNED_RECEIPT_POPULATION_GATE_ID = "forge-live-runtime-signed-receipt-population-gate.v1"
FORGE_LIVE_RUNTIME_EVIDENCE_CHAIN_READ_MODEL_ID = "forge-live-runtime-evidence-chain-read-model.v1"
FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_REQUEST_ID = "forge-live-runtime-operator-evidence-request.v1"
FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_SUBMISSION_PACKET_ID = (
    "forge-live-runtime-operator-evidence-submission-packet.v1"
)
FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_VERIFICATION_GATE_ID = (
    "forge-live-runtime-operator-evidence-verification-gate.v1"
)
FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_ACCEPTANCE_HANDOFF_PACKET_ID = (
    "forge-live-runtime-operator-evidence-acceptance-handoff-packet.v1"
)
FORGE_CERTIFICATE_PROFILE = "forge_dev3_phigov_state_write"
FORGE_ADMISSION_ENVIRONMENTS = (
    "dev_offline",
    "staging_shadow",
    "production_read_only",
    "production_state_changing",
)
FORGE_PREPARE_MODEL_ENVIRONMENTS = ("dev_offline", "staging_shadow")
FORGE_STATE_WRITE_CANDIDATES = ("governed_scoped_edit", "state_write_reference")
EXPECTED_STAGE_IDS = (
    "conditional_decision",
    "fenced_snapshot",
    "phigov_certificate",
    "prepared_transition",
    "lineage_authorization_attestation",
    "fenced_commit",
    "lineage_completion_attestation",
)
EXPECTED_STAGE_AUTHORITY_BOUNDARIES = {
    "conditional_decision": "uao_decision",
    "fenced_snapshot": "distributed_lease_boundary",
    "phigov_certificate": "phigov_certificate",
    "prepared_transition": "transition_model",
    "lineage_authorization_attestation": "h_lineage",
    "fenced_commit": "fenced_persistence",
    "lineage_completion_attestation": "h_lineage",
}
EXPECTED_CERTIFICATE_FIELDS = (
    "certificate_id",
    "issuer",
    "request_id",
    "decision_receipt_hash",
    "mesh_id",
    "snapshot_id",
    "before_state_hash",
    "after_state_hash",
    "delta_hash",
    "policy_hash",
    "evaluation_context_hash",
    "execution_scope_hash",
    "issued_at",
    "expires_at",
    "key_id",
    "trust_epoch",
    "nonce",
    "signature",
)
BASE_REQUIRED_CONTROLS = (
    "reference_only_bridge",
    "conditional_decision",
    "fencing_token",
    "immutable_snapshot",
    "signed_phigov_certificate",
    "prepared_transition_model",
    "lineage_authorization_attestation",
    "commit_denied_in_foundation_mode",
    "lineage_completion_attestation",
    "terminal_closure_required",
)
SHA256_REF_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS = (
    "managed_key_custody",
    "confidential_transport",
    "persistent_nonce_replay_store",
    "independent_persistence_store",
    "independent_worm_lineage",
    "tenant_scope_guard",
    "uao_no_bypass_runtime_proof",
    "rollback_replay_recovery_plan",
    "pb01_pb02_pb03_write_spine_closure",
    "pb04_pb11_runtime_operational_closure",
)
LIVE_RUNTIME_REQUIRED_CONTROLS = (
    "foundation_mode_runtime_block",
    "managed_key_custody_required",
    "confidential_transport_required",
    "persistent_nonce_replay_store_required",
    "independent_persistence_required",
    "independent_worm_lineage_required",
    "tenant_scope_guard_required",
    "uao_no_bypass_runtime_proof_required",
    "rollback_replay_recovery_required",
    "pb01_pb11_evidence_required",
)
LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS = {
    "managed_key_custody": "evidence://forge/live-runtime/managed-key-custody",
    "confidential_transport": "evidence://forge/live-runtime/confidential-transport",
    "persistent_nonce_replay_store": "evidence://forge/live-runtime/persistent-nonce-replay-store",
    "independent_persistence_store": "evidence://forge/live-runtime/independent-persistence-store",
    "independent_worm_lineage": "evidence://forge/live-runtime/independent-worm-lineage",
    "tenant_scope_guard": "evidence://forge/live-runtime/tenant-scope-guard",
    "uao_no_bypass_runtime_proof": "evidence://forge/live-runtime/uao-no-bypass-runtime-proof",
    "rollback_replay_recovery_plan": "evidence://forge/live-runtime/rollback-replay-recovery-plan",
    "pb01_pb02_pb03_write_spine_closure": "evidence://forge/live-runtime/pb01-pb03-write-spine-closure",
    "pb04_pb11_runtime_operational_closure": "evidence://forge/live-runtime/pb04-pb11-operational-closure",
}
LIVE_RUNTIME_EVIDENCE_COLLECTION_CONTROLS = (
    "readiness_gate_source_required",
    "local_collection_only",
    "evidence_refs_not_yet_collected",
    "no_runtime_registration",
    "no_commit_authority",
    "no_production_authority",
    "no_external_effects",
    "terminal_closure_not_claimed",
)
LIVE_RUNTIME_LOCAL_EVIDENCE_ARTIFACT_KINDS = {
    "managed_key_custody": "key_custody_design",
    "confidential_transport": "transport_boundary_design",
    "persistent_nonce_replay_store": "nonce_replay_store_design",
    "independent_persistence_store": "persistence_store_design",
    "independent_worm_lineage": "worm_lineage_design",
    "tenant_scope_guard": "tenant_scope_guard_design",
    "uao_no_bypass_runtime_proof": "uao_no_bypass_proof_design",
    "rollback_replay_recovery_plan": "rollback_replay_recovery_design",
    "pb01_pb02_pb03_write_spine_closure": "pb01_pb03_closure_design",
    "pb04_pb11_runtime_operational_closure": "pb04_pb11_operational_design",
}
LIVE_RUNTIME_LOCAL_EVIDENCE_ARTIFACT_REFS = {
    evidence_id: f"artifact://forge/live-runtime/local-design/{evidence_id.replace('_', '-')}"
    for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS
}
LIVE_RUNTIME_LOCAL_EVIDENCE_ACCEPTANCE_CRITERIA = {
    "managed_key_custody": (
        "managed_signing_key_identity_defined",
        "custody_operator_boundary_defined",
        "rotation_and_revocation_path_defined",
    ),
    "confidential_transport": (
        "service_transport_boundary_defined",
        "request_expiry_and_audience_binding_defined",
        "plaintext_secret_transport_forbidden",
    ),
    "persistent_nonce_replay_store": (
        "nonce_scope_defined",
        "replay_rejection_path_defined",
        "persistence_durability_requirement_defined",
    ),
    "independent_persistence_store": (
        "state_store_boundary_defined",
        "fenced_commit_requirement_defined",
        "snapshot_basis_requirement_defined",
    ),
    "independent_worm_lineage": (
        "append_only_lineage_boundary_defined",
        "authorization_completion_attestation_defined",
        "reconciliation_pending_path_defined",
    ),
    "tenant_scope_guard": (
        "tenant_identity_binding_defined",
        "cross_tenant_write_denial_defined",
        "scope_hash_binding_defined",
    ),
    "uao_no_bypass_runtime_proof": (
        "uao_admission_required_before_runtime_write",
        "unorchestrated_effect_denial_defined",
        "decision_receipt_hash_binding_defined",
    ),
    "rollback_replay_recovery_plan": (
        "rollback_snapshot_requirement_defined",
        "replay_cursor_requirement_defined",
        "failed_completion_recovery_path_defined",
    ),
    "pb01_pb02_pb03_write_spine_closure": (
        "conditional_decision_evidence_required",
        "phigov_certificate_evidence_required",
        "lineage_attestation_evidence_required",
    ),
    "pb04_pb11_runtime_operational_closure": (
        "operational_monitoring_evidence_required",
        "runtime_recovery_evidence_required",
        "production_witness_evidence_required",
    ),
}
LIVE_RUNTIME_LOCAL_EVIDENCE_CONTROLS = (
    "source_collection_packet_required",
    "local_design_artifacts_only",
    "live_evidence_not_collected",
    "blockers_remain_open",
    "no_runtime_registration",
    "no_commit_authority",
    "no_production_authority",
    "no_external_effects",
    "terminal_closure_not_claimed",
)
LIVE_RUNTIME_EVIDENCE_ACCEPTANCE_CONTROLS = (
    "source_local_evidence_bundle_required",
    "signed_live_receipts_required",
    "local_design_artifacts_not_sufficient",
    "credential_and_dependency_evidence_required",
    "recovery_evidence_required",
    "production_witness_required",
    "no_runtime_registration",
    "no_commit_authority",
    "no_production_authority",
    "no_external_effects",
    "terminal_closure_not_claimed",
)
LIVE_RUNTIME_SIGNED_EVIDENCE_RECEIPT_CONTROLS = (
    "source_acceptance_gate_required",
    "signed_live_receipt_refs_required_for_presence",
    "dependency_or_credential_probe_refs_required_for_presence",
    "recovery_or_revocation_refs_required_for_presence",
    "trusted_signing_key_required_for_presence",
    "foundation_fixture_contains_no_live_evidence",
    "no_runtime_registration",
    "no_commit_authority",
    "no_production_authority",
    "no_external_effects",
    "terminal_closure_not_claimed",
)
LIVE_RUNTIME_PROBE_ADMISSION_CONTROLS = (
    "source_signed_evidence_receipt_required",
    "operator_approval_required_before_probe",
    "probe_inputs_required_before_execution",
    "signed_receipt_writer_required_before_population",
    "recovery_or_revocation_required_before_population",
    "foundation_fixture_blocks_probe_execution",
    "no_runtime_registration",
    "no_commit_authority",
    "no_production_authority",
    "no_external_effects",
    "terminal_closure_not_claimed",
)
LIVE_RUNTIME_PROBE_REQUIRED_INPUTS = (
    "operator_approval",
    "dependency_or_credential_probe",
    "recovery_or_revocation_path",
    "signed_receipt_writer",
    "sandbox_or_isolation_boundary",
)
LIVE_RUNTIME_APPROVED_PROBE_OUTPUT_CONTROLS = (
    "source_probe_admission_packet_required",
    "operator_approval_evidence_required",
    "approved_probe_output_required",
    "dependency_or_credential_probe_output_required",
    "recovery_or_revocation_output_required",
    "signed_receipt_writer_required",
    "sandbox_or_isolation_boundary_required",
    "foundation_fixture_contains_no_probe_outputs",
    "no_runtime_registration",
    "no_commit_authority",
    "no_production_authority",
    "no_external_effects",
    "terminal_closure_not_claimed",
)
LIVE_RUNTIME_POST_PROBE_RECONCILIATION_CONTROLS = (
    "source_approved_probe_output_packet_required",
    "approved_probe_output_required",
    "probe_output_validation_required",
    "signed_receipt_update_requires_verified_output",
    "runtime_authority_not_granted_by_reconciliation",
    "foundation_fixture_blocks_reconciliation",
    "no_runtime_registration",
    "no_commit_authority",
    "no_production_authority",
    "no_external_effects",
    "terminal_closure_not_claimed",
)
LIVE_RUNTIME_SIGNED_RECEIPT_POPULATION_CONTROLS = (
    "source_post_probe_reconciliation_packet_required",
    "reconciled_probe_output_required",
    "signed_receipt_update_ref_required",
    "trusted_signing_key_required",
    "signature_verification_required",
    "receipt_population_denied_in_foundation_fixture",
    "no_runtime_registration",
    "no_commit_authority",
    "no_production_authority",
    "no_external_effects",
    "terminal_closure_not_claimed",
)
LIVE_RUNTIME_EVIDENCE_CHAIN_READ_MODEL_CONTROLS = (
    "source_signed_receipt_population_gate_required",
    "read_model_only",
    "all_stage_hashes_required",
    "downstream_continuation_refs_exclude_hashes_to_avoid_cycle",
    "blocked_status_preserved",
    "awaiting_evidence_preserved",
    "no_runtime_registration",
    "no_commit_authority",
    "no_production_authority",
    "no_external_effects",
    "terminal_closure_not_claimed",
)
LIVE_RUNTIME_OPERATOR_EVIDENCE_REQUEST_CONTROLS = (
    "source_evidence_chain_read_model_required",
    "operator_approval_required",
    "live_evidence_refs_required",
    "secret_values_forbidden",
    "request_is_not_execution",
    "no_runtime_registration",
    "no_commit_authority",
    "no_production_authority",
    "no_external_effects",
    "terminal_closure_not_claimed",
)
LIVE_RUNTIME_OPERATOR_EVIDENCE_SUBMISSION_CONTROLS = (
    "source_operator_evidence_request_required",
    "submitted_ref_slots_required",
    "secret_values_forbidden",
    "placeholder_refs_not_live_evidence",
    "submission_does_not_grant_runtime_authority",
    "signature_verification_required_before_acceptance",
    "no_runtime_registration",
    "no_commit_authority",
    "no_production_authority",
    "no_external_effects",
    "terminal_closure_not_claimed",
)
LIVE_RUNTIME_OPERATOR_EVIDENCE_VERIFICATION_CONTROLS = (
    "source_operator_evidence_submission_packet_required",
    "independent_verification_required",
    "submitted_refs_are_not_verification",
    "signature_verification_required",
    "secret_values_forbidden",
    "verification_does_not_grant_runtime_authority",
    "signed_receipt_population_still_separate",
    "no_runtime_registration",
    "no_commit_authority",
    "no_production_authority",
    "no_external_effects",
    "terminal_closure_not_claimed",
)
LIVE_RUNTIME_OPERATOR_EVIDENCE_ACCEPTANCE_HANDOFF_CONTROLS = (
    "source_operator_evidence_verification_gate_required",
    "verified_refs_required_before_handoff",
    "handoff_does_not_accept_evidence",
    "signed_receipt_population_still_separate",
    "runtime_promotion_still_separate",
    "secret_values_forbidden",
    "no_runtime_registration",
    "no_commit_authority",
    "no_production_authority",
    "no_external_effects",
    "terminal_closure_not_claimed",
)
LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES = (
    "operator_approval_ref",
    "dependency_or_credential_probe_ref",
    "sandbox_or_isolation_evidence_ref",
    "recovery_or_revocation_ref",
    "signed_receipt_writer_ref",
    "signed_live_receipt_ref",
    "trusted_signing_key_ref",
    "signature_verification_ref",
)


@dataclass(frozen=True, slots=True)
class ForgeStateWriteAdmissionPolicy:
    """Policy bounds for local Forge state-write admission."""

    policy_id: str = "forge-state-write-admission.foundation.v1"
    bridge_id: str = FORGE_WRITE_SPINE_BRIDGE_ID
    allowed_prepare_environments: tuple[str, ...] = FORGE_PREPARE_MODEL_ENVIRONMENTS
    max_certificate_lifetime_seconds: int = 900
    require_development_certificate: bool = True
    production_state_changing_status: str = "NO_GO"


@dataclass(frozen=True, slots=True)
class ForgeStateWriteStageEvidence:
    """Evidence for one ordered Forge write-spine stage."""

    stage_id: str
    order: int
    receipt_ref: str
    receipt_hash: str
    authority_boundary: str
    satisfied: bool


@dataclass(frozen=True, slots=True)
class ForgeStateWriteCertificateEvidence:
    """Phi_gov certificate evidence for a prepared state-write model."""

    profile: str
    development_only: bool
    required_fields: list[str]
    issued_at: str
    expires_at: str
    key_id: str
    trust_epoch: str
    nonce: str
    signature: str
    certificate_hash: str


@dataclass(frozen=True, slots=True)
class ForgeStateWriteServiceBoundaryEvidence:
    """Signed service-boundary controls required by the Forge reference."""

    signed_rpc: bool
    caller_audience_binding: bool
    request_expiry: bool
    persistent_nonce_replay_guard: bool
    pinned_phigov_trust_root: bool
    pinned_lineage_identity: bool
    local_development_keys: bool
    transport_confidentiality: bool
    production_authorized: bool


@dataclass(frozen=True, slots=True)
class ForgeStateWriteAdmissionRequest:
    """One proposed state-write transition for non-mutating admission."""

    request_id: str
    tenant_id: str
    actor_id: str
    mesh_id: str
    operation_id: str
    bridge_ref: str
    requested_environment: str
    decision_status: str
    selected_candidate_id: str
    mutation_performed: bool
    before_state_hash: str
    after_state_hash: str
    delta_hash: str
    policy_hash: str
    evaluation_context_hash: str
    execution_scope_hash: str
    stages: list[ForgeStateWriteStageEvidence]
    certificate: ForgeStateWriteCertificateEvidence
    service_boundary: ForgeStateWriteServiceBoundaryEvidence
    evidence_refs: list[str]
    requested_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ForgeStateWriteAdmissionReceipt:
    """Schema-backed receipt for Forge state-write admission."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    mesh_id: str
    operation_id: str
    bridge_ref: str
    packet_schema_ref: str
    requested_environment: str
    status: str
    solver_outcome: str
    admission_decision: str
    external_effects_allowed: bool
    state_write_runtime_registered: bool
    production_authorized: bool
    commit_allowed: bool
    live_mutation_allowed: bool
    prepared_transition_model_allowed: bool
    terminal_closure_required: bool
    blocked_reasons: list[str]
    required_controls: list[str]
    evidence_refs: list[str]
    stage_hash: str
    certificate_hash: str
    receipt_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)


def evaluate_forge_state_write_admission(
    request: ForgeStateWriteAdmissionRequest,
    policy: ForgeStateWriteAdmissionPolicy | None = None,
) -> ForgeStateWriteAdmissionReceipt:
    """Evaluate a Forge state-write request without mutating live state."""

    active_policy = policy or ForgeStateWriteAdmissionPolicy()
    blocked_reasons = list(_request_blockers(request, active_policy))
    prepared_model_allowed = not blocked_reasons and (
        request.requested_environment in active_policy.allowed_prepare_environments
    )
    status = "reference_prepare_admitted" if prepared_model_allowed else "blocked"
    solver_outcome = "SolvedVerified" if prepared_model_allowed else "GovernanceBlocked"
    admission_decision = "allow_prepare_model" if prepared_model_allowed else "block"
    stage_hash = f"sha256:{canonical_hash({'stages': [asdict(stage) for stage in request.stages]})}"
    certificate_hash = request.certificate.certificate_hash

    receipt = ForgeStateWriteAdmissionReceipt(
        receipt_id="pending",
        request_id=request.request_id,
        tenant_id=request.tenant_id,
        actor_id=request.actor_id,
        mesh_id=request.mesh_id,
        operation_id=request.operation_id,
        bridge_ref=request.bridge_ref,
        packet_schema_ref=FORGE_STATE_WRITE_ADMISSION_PACKET_SCHEMA_REF,
        requested_environment=request.requested_environment,
        status=status,
        solver_outcome=solver_outcome,
        admission_decision=admission_decision,
        external_effects_allowed=False,
        state_write_runtime_registered=False,
        production_authorized=False,
        commit_allowed=False,
        live_mutation_allowed=False,
        prepared_transition_model_allowed=prepared_model_allowed,
        terminal_closure_required=True,
        blocked_reasons=blocked_reasons,
        required_controls=list(BASE_REQUIRED_CONTROLS),
        evidence_refs=list(request.evidence_refs),
        stage_hash=stage_hash,
        certificate_hash=certificate_hash,
        receipt_hash="",
        metadata={
            "policy_id": active_policy.policy_id,
            "production_state_changing_status": active_policy.production_state_changing_status,
            "mutation_route": "not_registered",
            "adapter_mode": "non_mutating_reference_admission",
        },
    )
    receipt_hash = canonical_hash(asdict(receipt))
    return replace(
        receipt,
        receipt_id=f"forge-state-write-admission-receipt-{receipt_hash[:16]}",
        receipt_hash=receipt_hash,
    )


def build_forge_state_write_admission_packet(
    request: ForgeStateWriteAdmissionRequest,
    policy: ForgeStateWriteAdmissionPolicy | None = None,
) -> dict[str, Any]:
    """Build a deterministic schema-backed admission packet."""

    receipt = evaluate_forge_state_write_admission(request, policy)
    packet = {
        "packet_id": f"forge-state-write-admission-packet-{receipt.receipt_hash[:16]}",
        "packet_schema_ref": FORGE_STATE_WRITE_ADMISSION_PACKET_SCHEMA_REF,
        "adapter_id": FORGE_STATE_WRITE_ADMISSION_ADAPTER_ID,
        "bridge_ref": FORGE_WRITE_SPINE_BRIDGE_ID,
        "source_bridge_ref": "examples/forge_write_spine_bridge.foundation.json",
        "request": asdict(request),
        "receipt": asdict(receipt),
        "invariants": {
            "reference_only": True,
            "mutation_performed": False,
            "live_mutation_allowed": False,
            "commit_allowed": False,
            "production_authorized": False,
            "state_write_runtime_registered": False,
            "external_effects_allowed": False,
            "terminal_closure_required": True,
        },
        "validators": [
            {
                "validator_id": "forge-state-write-admission-packet",
                "command": "python scripts/validate_forge_state_write_admission_packet.py",
                "required_for_closure": True,
            }
        ],
    }
    packet["packet_hash"] = canonical_hash(packet)
    return packet


def build_foundation_forge_state_write_request() -> ForgeStateWriteAdmissionRequest:
    """Build the canonical Foundation Mode Forge admission request fixture."""

    request_id = "forge-state-write-admission-dev-offline-1"
    stages = [
        ForgeStateWriteStageEvidence(
            stage_id=stage_id,
            order=index + 1,
            receipt_ref=f"receipt://forge/{stage_id}/{request_id}",
            receipt_hash=_fixture_hash({"stage_id": stage_id, "request_id": request_id}),
            authority_boundary=EXPECTED_STAGE_AUTHORITY_BOUNDARIES[stage_id],
            satisfied=True,
        )
        for index, stage_id in enumerate(EXPECTED_STAGE_IDS)
    ]
    return ForgeStateWriteAdmissionRequest(
        request_id=request_id,
        tenant_id="foundation-local",
        actor_id="operator-local",
        mesh_id="mesh://foundation/forge-write-spine/dev-offline",
        operation_id="operation://forge/write-spine/reference-prepare",
        bridge_ref=FORGE_WRITE_SPINE_BRIDGE_ID,
        requested_environment="dev_offline",
        decision_status="conditional_accept",
        selected_candidate_id="governed_scoped_edit",
        mutation_performed=False,
        before_state_hash=_fixture_hash({"state": "before", "request_id": request_id}),
        after_state_hash=_fixture_hash({"state": "after", "request_id": request_id}),
        delta_hash=_fixture_hash({"delta": "prepared-transition", "request_id": request_id}),
        policy_hash=_fixture_hash({"policy": "foundation", "request_id": request_id}),
        evaluation_context_hash=_fixture_hash({"context": "dev-offline", "request_id": request_id}),
        execution_scope_hash=_fixture_hash({"scope": "non-mutating", "request_id": request_id}),
        stages=stages,
        certificate=ForgeStateWriteCertificateEvidence(
            profile=FORGE_CERTIFICATE_PROFILE,
            development_only=True,
            required_fields=list(EXPECTED_CERTIFICATE_FIELDS),
            issued_at="2026-06-27T12:00:00+00:00",
            expires_at="2026-06-27T12:10:00+00:00",
            key_id="dev-phigov-key-1",
            trust_epoch="foundation-epoch-1",
            nonce="forge-state-write-dev-offline-nonce-1",
            signature="ed25519:development-reference-signature",
            certificate_hash=_fixture_hash({"certificate": "phigov", "request_id": request_id}),
        ),
        service_boundary=ForgeStateWriteServiceBoundaryEvidence(
            signed_rpc=True,
            caller_audience_binding=True,
            request_expiry=True,
            persistent_nonce_replay_guard=True,
            pinned_phigov_trust_root=True,
            pinned_lineage_identity=True,
            local_development_keys=True,
            transport_confidentiality=False,
            production_authorized=False,
        ),
        evidence_refs=[
            "docs/FORGE_WRITE_SPINE_BRIDGE.md",
            "examples/forge_write_spine_bridge.foundation.json",
            "scripts/validate_forge_write_spine_bridge.py",
        ],
        requested_at="2026-06-27T12:00:00+00:00",
        metadata={"foundation_mode": True, "source_runtime": "mullu-forge-runtime-v0.1.0-dev3"},
    )


def build_foundation_forge_live_runtime_readiness_gate() -> dict[str, Any]:
    """Build the blocked live-runtime readiness gate for Foundation Mode."""

    required_evidence = [
        {
            "evidence_id": evidence_id,
            "required": True,
            "present": False,
            "evidence_ref": "",
            "blocker_reason": f"{evidence_id}_missing",
        }
        for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS
    ]
    gate = {
        "gate_id": FORGE_LIVE_RUNTIME_READINESS_GATE_ID,
        "schema_ref": FORGE_LIVE_RUNTIME_READINESS_GATE_SCHEMA_REF,
        "schema_version": 1,
        "bridge_ref": FORGE_WRITE_SPINE_BRIDGE_ID,
        "source_bridge_ref": "examples/forge_write_spine_bridge.foundation.json",
        "source_admission_packet_ref": "examples/forge_state_write_admission_packet.foundation.json",
        "evaluated_at": "2026-06-27T12:30:00+00:00",
        "foundation_mode": True,
        "readiness_status": "blocked_awaiting_evidence",
        "solver_outcome": "AwaitingEvidence",
        "admission_decision": "block_live_runtime",
        "live_runtime_authorized": False,
        "state_write_runtime_registered": False,
        "production_authorized": False,
        "external_effects_allowed": False,
        "commit_allowed": False,
        "required_evidence": required_evidence,
        "blocked_reasons": [item["blocker_reason"] for item in required_evidence],
        "required_controls": list(LIVE_RUNTIME_REQUIRED_CONTROLS),
        "next_allowed_action": "collect_local_evidence_without_registering_runtime_authority",
        "validators": [
            {
                "validator_id": "forge-live-runtime-readiness-gate",
                "command": "python scripts/validate_forge_live_runtime_readiness_gate.py",
                "required_for_closure": True,
            }
        ],
    }
    gate["gate_hash"] = canonical_hash(gate)
    return gate


def build_foundation_forge_live_runtime_evidence_collection_packet() -> dict[str, Any]:
    """Build a local-only collection packet for missing live-runtime evidence."""

    readiness_gate = build_foundation_forge_live_runtime_readiness_gate()
    collection_items = [
        {
            "evidence_id": evidence_id,
            "collection_status": "not_collected",
            "source_blocker_reason": f"{evidence_id}_missing",
            "target_evidence_ref": LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS[evidence_id],
            "allowed_collection_mode": "local_design_or_rehearsal_only",
            "authority_effect": False,
            "collected": False,
        }
        for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS
    ]
    packet = {
        "packet_id": FORGE_LIVE_RUNTIME_EVIDENCE_COLLECTION_PACKET_ID,
        "schema_ref": FORGE_LIVE_RUNTIME_EVIDENCE_COLLECTION_PACKET_SCHEMA_REF,
        "schema_version": 1,
        "bridge_ref": FORGE_WRITE_SPINE_BRIDGE_ID,
        "source_readiness_gate_ref": "examples/forge_live_runtime_readiness_gate.foundation.json",
        "source_readiness_gate_hash": readiness_gate["gate_hash"],
        "collection_mode": "local_evidence_planning_only",
        "solver_outcome": "AwaitingEvidence",
        "collection_status": "not_started",
        "evidence_items": collection_items,
        "blocked_reasons": list(readiness_gate["blocked_reasons"]),
        "required_controls": list(LIVE_RUNTIME_EVIDENCE_COLLECTION_CONTROLS),
        "disallowed_authority": {
            "live_runtime_authorized": False,
            "state_write_runtime_registered": False,
            "production_authorized": False,
            "external_effects_allowed": False,
            "commit_allowed": False,
            "terminal_closure": False,
        },
        "next_allowed_action": "write_local_evidence_artifacts_without_registering_runtime_authority",
        "validators": [
            {
                "validator_id": "forge-live-runtime-evidence-collection-packet",
                "command": "python scripts/validate_forge_live_runtime_evidence_collection_packet.py",
                "required_for_closure": True,
            }
        ],
    }
    packet["packet_hash"] = canonical_hash(packet)
    return packet


def build_foundation_forge_live_runtime_local_evidence_bundle() -> dict[str, Any]:
    """Build local design artifacts for Forge live-runtime evidence blockers."""

    collection_packet = build_foundation_forge_live_runtime_evidence_collection_packet()
    local_evidence_items = [
        {
            "evidence_id": evidence_id,
            "source_target_evidence_ref": LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS[evidence_id],
            "local_artifact_ref": LIVE_RUNTIME_LOCAL_EVIDENCE_ARTIFACT_REFS[evidence_id],
            "local_artifact_kind": LIVE_RUNTIME_LOCAL_EVIDENCE_ARTIFACT_KINDS[evidence_id],
            "local_artifact_status": "design_artifact_available",
            "live_evidence_status": "not_collected",
            "blocker_status": "open",
            "authority_effect": False,
            "promotion_effect": False,
            "acceptance_criteria": list(LIVE_RUNTIME_LOCAL_EVIDENCE_ACCEPTANCE_CRITERIA[evidence_id]),
        }
        for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS
    ]
    bundle = {
        "bundle_id": FORGE_LIVE_RUNTIME_LOCAL_EVIDENCE_BUNDLE_ID,
        "schema_ref": FORGE_LIVE_RUNTIME_LOCAL_EVIDENCE_BUNDLE_SCHEMA_REF,
        "schema_version": 1,
        "bridge_ref": FORGE_WRITE_SPINE_BRIDGE_ID,
        "source_collection_packet_ref": (
            "examples/forge_live_runtime_evidence_collection_packet.foundation.json"
        ),
        "source_collection_packet_hash": collection_packet["packet_hash"],
        "bundle_mode": "local_design_rehearsal_only",
        "bundle_status": "local_design_artifacts_available",
        "solver_outcome": "AwaitingEvidence",
        "readiness_status": "blocked_awaiting_live_evidence",
        "local_evidence_items": local_evidence_items,
        "blocked_reasons": list(collection_packet["blocked_reasons"]),
        "required_controls": list(LIVE_RUNTIME_LOCAL_EVIDENCE_CONTROLS),
        "disallowed_authority": {
            "live_runtime_authorized": False,
            "state_write_runtime_registered": False,
            "production_authorized": False,
            "external_effects_allowed": False,
            "commit_allowed": False,
            "terminal_closure": False,
        },
        "next_allowed_action": "replace_design_artifacts_with_validated_live_evidence_after_approval",
        "validators": [
            {
                "validator_id": "forge-live-runtime-local-evidence-bundle",
                "command": "python scripts/validate_forge_live_runtime_local_evidence_bundle.py",
                "required_for_closure": True,
            }
        ],
    }
    bundle["bundle_hash"] = canonical_hash(bundle)
    return bundle


def build_foundation_forge_live_runtime_evidence_acceptance_gate() -> dict[str, Any]:
    """Build the blocked gate for accepting future signed live evidence."""

    local_bundle = build_foundation_forge_live_runtime_local_evidence_bundle()
    local_items_by_id = {
        item["evidence_id"]: item for item in local_bundle["local_evidence_items"]
    }
    acceptance_items = [
        {
            "evidence_id": evidence_id,
            "source_local_artifact_ref": local_items_by_id[evidence_id]["local_artifact_ref"],
            "required_live_evidence_ref": LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS[evidence_id],
            "required_witnesses": [
                "signed_live_receipt",
                "dependency_or_credential_probe",
                "recovery_or_revocation_path",
            ],
            "live_evidence_status": "missing",
            "acceptance_status": "blocked",
            "blocker_reason": f"{evidence_id}_signed_live_evidence_missing",
            "local_artifact_sufficient": False,
            "authority_effect": False,
        }
        for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS
    ]
    gate = {
        "gate_id": FORGE_LIVE_RUNTIME_EVIDENCE_ACCEPTANCE_GATE_ID,
        "schema_ref": FORGE_LIVE_RUNTIME_EVIDENCE_ACCEPTANCE_GATE_SCHEMA_REF,
        "schema_version": 1,
        "bridge_ref": FORGE_WRITE_SPINE_BRIDGE_ID,
        "source_local_evidence_bundle_ref": "examples/forge_live_runtime_local_evidence_bundle.foundation.json",
        "source_local_evidence_bundle_hash": local_bundle["bundle_hash"],
        "acceptance_mode": "signed_live_evidence_required",
        "acceptance_status": "blocked_awaiting_signed_live_evidence",
        "solver_outcome": "AwaitingEvidence",
        "admission_decision": "block_live_runtime_promotion",
        "acceptance_items": acceptance_items,
        "blocked_reasons": [item["blocker_reason"] for item in acceptance_items],
        "required_controls": list(LIVE_RUNTIME_EVIDENCE_ACCEPTANCE_CONTROLS),
        "disallowed_authority": {
            "live_runtime_authorized": False,
            "state_write_runtime_registered": False,
            "production_authorized": False,
            "external_effects_allowed": False,
            "commit_allowed": False,
            "terminal_closure": False,
        },
        "next_allowed_action": "collect_signed_live_evidence_under_operator_approval",
        "validators": [
            {
                "validator_id": "forge-live-runtime-evidence-acceptance-gate",
                "command": "python scripts/validate_forge_live_runtime_evidence_acceptance_gate.py",
                "required_for_closure": True,
            }
        ],
    }
    gate["gate_hash"] = canonical_hash(gate)
    return gate


def build_foundation_forge_live_runtime_signed_evidence_receipt() -> dict[str, Any]:
    """Build the Foundation Mode shape for future signed live evidence."""

    acceptance_gate = build_foundation_forge_live_runtime_evidence_acceptance_gate()
    receipt_items = [
        {
            "evidence_id": evidence_id,
            "required_live_evidence_ref": LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS[evidence_id],
            "acceptance_blocker_reason": f"{evidence_id}_signed_live_evidence_missing",
            "signed_live_receipt_status": "not_present",
            "signed_live_receipt_ref": "",
            "signed_live_receipt_hash": "",
            "dependency_or_credential_probe_ref": "",
            "recovery_or_revocation_ref": "",
            "signing_key_id": "",
            "trust_epoch": "",
            "signature": "",
            "verification_status": "not_verified",
            "authority_effect": False,
            "promotion_effect": False,
        }
        for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS
    ]
    receipt = {
        "receipt_id": FORGE_LIVE_RUNTIME_SIGNED_EVIDENCE_RECEIPT_ID,
        "schema_ref": FORGE_LIVE_RUNTIME_SIGNED_EVIDENCE_RECEIPT_SCHEMA_REF,
        "schema_version": 1,
        "bridge_ref": FORGE_WRITE_SPINE_BRIDGE_ID,
        "source_acceptance_gate_ref": "examples/forge_live_runtime_evidence_acceptance_gate.foundation.json",
        "source_acceptance_gate_hash": acceptance_gate["gate_hash"],
        "receipt_mode": "signed_live_evidence_shape",
        "receipt_status": "awaiting_signed_live_evidence",
        "solver_outcome": "AwaitingEvidence",
        "evidence_receipts": receipt_items,
        "blocked_reasons": list(acceptance_gate["blocked_reasons"]),
        "required_controls": list(LIVE_RUNTIME_SIGNED_EVIDENCE_RECEIPT_CONTROLS),
        "disallowed_authority": {
            "live_runtime_authorized": False,
            "state_write_runtime_registered": False,
            "production_authorized": False,
            "external_effects_allowed": False,
            "commit_allowed": False,
            "terminal_closure": False,
        },
        "next_allowed_action": "populate_signed_live_receipt_refs_after_operator_approved_probe",
        "validators": [
            {
                "validator_id": "forge-live-runtime-signed-evidence-receipt",
                "command": "python scripts/validate_forge_live_runtime_signed_evidence_receipt.py",
                "required_for_closure": True,
            }
        ],
    }
    receipt["receipt_hash"] = canonical_hash(receipt)
    return receipt


def build_foundation_forge_live_runtime_probe_admission_packet() -> dict[str, Any]:
    """Build the blocked admission packet for future live evidence probes."""

    signed_receipt = build_foundation_forge_live_runtime_signed_evidence_receipt()
    probe_items = [
        {
            "evidence_id": evidence_id,
            "target_signed_evidence_ref": LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS[evidence_id],
            "probe_ref": f"probe://forge/live-runtime/{evidence_id.replace('_', '-')}",
            "required_inputs": list(LIVE_RUNTIME_PROBE_REQUIRED_INPUTS),
            "operator_approval_status": "not_approved",
            "probe_admission_status": "blocked",
            "probe_execution_allowed": False,
            "external_effects_requested": False,
            "signed_receipt_population_allowed": False,
            "blocker_reason": f"{evidence_id}_operator_approved_probe_missing",
            "authority_effect": False,
        }
        for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS
    ]
    packet = {
        "packet_id": FORGE_LIVE_RUNTIME_PROBE_ADMISSION_PACKET_ID,
        "schema_ref": FORGE_LIVE_RUNTIME_PROBE_ADMISSION_PACKET_SCHEMA_REF,
        "schema_version": 1,
        "bridge_ref": FORGE_WRITE_SPINE_BRIDGE_ID,
        "source_signed_evidence_receipt_ref": "examples/forge_live_runtime_signed_evidence_receipt.foundation.json",
        "source_signed_evidence_receipt_hash": signed_receipt["receipt_hash"],
        "admission_mode": "operator_approved_live_probe_required",
        "admission_status": "blocked_awaiting_operator_approval",
        "solver_outcome": "AwaitingEvidence",
        "probe_items": probe_items,
        "blocked_reasons": [item["blocker_reason"] for item in probe_items],
        "required_controls": list(LIVE_RUNTIME_PROBE_ADMISSION_CONTROLS),
        "disallowed_authority": {
            "live_runtime_authorized": False,
            "state_write_runtime_registered": False,
            "production_authorized": False,
            "external_effects_allowed": False,
            "commit_allowed": False,
            "terminal_closure": False,
        },
        "next_allowed_action": "request_operator_approval_for_bounded_live_probe_inputs",
        "validators": [
            {
                "validator_id": "forge-live-runtime-probe-admission-packet",
                "command": "python scripts/validate_forge_live_runtime_probe_admission_packet.py",
                "required_for_closure": True,
            }
        ],
    }
    packet["packet_hash"] = canonical_hash(packet)
    return packet


def build_foundation_forge_live_runtime_approved_probe_output_packet() -> dict[str, Any]:
    """Build the blocked intake packet for future approved live probe outputs."""

    probe_admission_packet = build_foundation_forge_live_runtime_probe_admission_packet()
    probe_outputs = [
        {
            "evidence_id": evidence_id,
            "source_probe_ref": f"probe://forge/live-runtime/{evidence_id.replace('_', '-')}",
            "target_signed_evidence_ref": LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS[evidence_id],
            "operator_approval_ref": "",
            "dependency_or_credential_probe_output_ref": "",
            "recovery_or_revocation_output_ref": "",
            "sandbox_or_isolation_evidence_ref": "",
            "signed_receipt_writer_ref": "",
            "approved_probe_output_ref": "",
            "approved_probe_output_hash": "",
            "output_status": "missing",
            "intake_status": "blocked",
            "verification_status": "not_verified",
            "blocker_reason": f"{evidence_id}_approved_probe_output_missing",
            "authority_effect": False,
            "promotion_effect": False,
        }
        for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS
    ]
    packet = {
        "packet_id": FORGE_LIVE_RUNTIME_APPROVED_PROBE_OUTPUT_PACKET_ID,
        "schema_ref": FORGE_LIVE_RUNTIME_APPROVED_PROBE_OUTPUT_PACKET_SCHEMA_REF,
        "schema_version": 1,
        "bridge_ref": FORGE_WRITE_SPINE_BRIDGE_ID,
        "source_probe_admission_packet_ref": "examples/forge_live_runtime_probe_admission_packet.foundation.json",
        "source_probe_admission_packet_hash": probe_admission_packet["packet_hash"],
        "output_intake_mode": "approved_probe_outputs_required",
        "output_intake_status": "blocked_awaiting_approved_probe_outputs",
        "solver_outcome": "AwaitingEvidence",
        "approved_probe_outputs_present": False,
        "signed_receipt_population_allowed": False,
        "runtime_authority_effect": False,
        "probe_outputs": probe_outputs,
        "blocked_reasons": [item["blocker_reason"] for item in probe_outputs],
        "required_controls": list(LIVE_RUNTIME_APPROVED_PROBE_OUTPUT_CONTROLS),
        "disallowed_authority": {
            "live_runtime_authorized": False,
            "state_write_runtime_registered": False,
            "production_authorized": False,
            "external_effects_allowed": False,
            "commit_allowed": False,
            "terminal_closure": False,
        },
        "next_allowed_action": "collect_operator_approved_probe_outputs_under_isolation",
        "validators": [
            {
                "validator_id": "forge-live-runtime-approved-probe-output-packet",
                "command": "python scripts/validate_forge_live_runtime_approved_probe_output_packet.py",
                "required_for_closure": True,
            }
        ],
    }
    packet["packet_hash"] = canonical_hash(packet)
    return packet


def build_foundation_forge_live_runtime_post_probe_reconciliation_packet() -> dict[str, Any]:
    """Build the blocked reconciliation packet for approved future probe outputs."""

    approved_probe_output_packet = build_foundation_forge_live_runtime_approved_probe_output_packet()
    reconciliation_items = [
        {
            "evidence_id": evidence_id,
            "source_probe_ref": f"probe://forge/live-runtime/{evidence_id.replace('_', '-')}",
            "target_signed_evidence_ref": LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS[evidence_id],
            "probe_output_status": "missing",
            "probe_output_ref": "",
            "probe_output_hash": "",
            "signed_receipt_update_status": "blocked",
            "signed_receipt_update_ref": "",
            "reconciliation_status": "blocked",
            "blocker_reason": f"{evidence_id}_approved_probe_output_missing",
            "authority_effect": False,
            "promotion_effect": False,
        }
        for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS
    ]
    packet = {
        "packet_id": FORGE_LIVE_RUNTIME_POST_PROBE_RECONCILIATION_PACKET_ID,
        "schema_ref": FORGE_LIVE_RUNTIME_POST_PROBE_RECONCILIATION_PACKET_SCHEMA_REF,
        "schema_version": 1,
        "bridge_ref": FORGE_WRITE_SPINE_BRIDGE_ID,
        "source_approved_probe_output_packet_ref": (
            "examples/forge_live_runtime_approved_probe_output_packet.foundation.json"
        ),
        "source_approved_probe_output_packet_hash": approved_probe_output_packet["packet_hash"],
        "reconciliation_mode": "approved_probe_output_reconciliation_required",
        "reconciliation_status": "blocked_awaiting_approved_probe_outputs",
        "solver_outcome": "AwaitingEvidence",
        "probe_outputs_present": False,
        "signed_receipt_updates_allowed": False,
        "runtime_authority_effect": False,
        "reconciliation_items": reconciliation_items,
        "blocked_reasons": [item["blocker_reason"] for item in reconciliation_items],
        "required_controls": list(LIVE_RUNTIME_POST_PROBE_RECONCILIATION_CONTROLS),
        "disallowed_authority": {
            "live_runtime_authorized": False,
            "state_write_runtime_registered": False,
            "production_authorized": False,
            "external_effects_allowed": False,
            "commit_allowed": False,
            "terminal_closure": False,
        },
        "next_allowed_action": "reconcile_approved_probe_outputs_after_validation",
        "validators": [
            {
                "validator_id": "forge-live-runtime-post-probe-reconciliation-packet",
                "command": "python scripts/validate_forge_live_runtime_post_probe_reconciliation_packet.py",
                "required_for_closure": True,
            }
        ],
    }
    packet["packet_hash"] = canonical_hash(packet)
    return packet


def build_foundation_forge_live_runtime_signed_receipt_population_gate() -> dict[str, Any]:
    """Build the blocked gate for populating signed live evidence receipts."""

    reconciliation_packet = build_foundation_forge_live_runtime_post_probe_reconciliation_packet()
    population_items = [
        {
            "evidence_id": evidence_id,
            "source_reconciliation_ref": f"reconciliation://forge/live-runtime/{evidence_id.replace('_', '-')}",
            "target_signed_evidence_ref": LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS[evidence_id],
            "signed_receipt_update_ref": "",
            "signed_live_receipt_ref": "",
            "signing_key_id": "",
            "trust_epoch": "",
            "signature": "",
            "verification_status": "not_verified",
            "population_status": "blocked",
            "blocker_reason": f"{evidence_id}_reconciled_probe_output_missing",
            "authority_effect": False,
            "promotion_effect": False,
        }
        for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS
    ]
    gate = {
        "gate_id": FORGE_LIVE_RUNTIME_SIGNED_RECEIPT_POPULATION_GATE_ID,
        "schema_ref": FORGE_LIVE_RUNTIME_SIGNED_RECEIPT_POPULATION_GATE_SCHEMA_REF,
        "schema_version": 1,
        "bridge_ref": FORGE_WRITE_SPINE_BRIDGE_ID,
        "source_post_probe_reconciliation_packet_ref": (
            "examples/forge_live_runtime_post_probe_reconciliation_packet.foundation.json"
        ),
        "source_post_probe_reconciliation_packet_hash": reconciliation_packet["packet_hash"],
        "population_mode": "signed_receipt_population_requires_reconciled_probe_outputs",
        "population_status": "blocked_awaiting_reconciled_probe_outputs",
        "solver_outcome": "AwaitingEvidence",
        "receipt_population_allowed": False,
        "signed_receipt_refs_populated": False,
        "runtime_authority_effect": False,
        "population_items": population_items,
        "blocked_reasons": [item["blocker_reason"] for item in population_items],
        "required_controls": list(LIVE_RUNTIME_SIGNED_RECEIPT_POPULATION_CONTROLS),
        "disallowed_authority": {
            "live_runtime_authorized": False,
            "state_write_runtime_registered": False,
            "production_authorized": False,
            "external_effects_allowed": False,
            "commit_allowed": False,
            "terminal_closure": False,
        },
        "next_allowed_action": "populate_signed_receipts_after_reconciliation_and_signature_verification",
        "validators": [
            {
                "validator_id": "forge-live-runtime-signed-receipt-population-gate",
                "command": "python scripts/validate_forge_live_runtime_signed_receipt_population_gate.py",
                "required_for_closure": True,
            }
        ],
    }
    gate["gate_hash"] = canonical_hash(gate)
    return gate


def build_foundation_forge_live_runtime_evidence_chain_read_model() -> dict[str, Any]:
    """Build a read-only projection of the Forge live-runtime evidence chain."""

    readiness_gate = build_foundation_forge_live_runtime_readiness_gate()
    collection_packet = build_foundation_forge_live_runtime_evidence_collection_packet()
    local_bundle = build_foundation_forge_live_runtime_local_evidence_bundle()
    acceptance_gate = build_foundation_forge_live_runtime_evidence_acceptance_gate()
    signed_receipt = build_foundation_forge_live_runtime_signed_evidence_receipt()
    probe_admission_packet = build_foundation_forge_live_runtime_probe_admission_packet()
    approved_probe_output_packet = build_foundation_forge_live_runtime_approved_probe_output_packet()
    reconciliation_packet = build_foundation_forge_live_runtime_post_probe_reconciliation_packet()
    population_gate = build_foundation_forge_live_runtime_signed_receipt_population_gate()
    stage_items = [
        {
            "stage_id": "live_runtime_readiness_gate",
            "artifact_ref": "examples/forge_live_runtime_readiness_gate.foundation.json",
            "artifact_hash": readiness_gate["gate_hash"],
            "stage_status": readiness_gate["readiness_status"],
            "solver_outcome": readiness_gate["solver_outcome"],
            "authority_effect": False,
        },
        {
            "stage_id": "live_runtime_evidence_collection_packet",
            "artifact_ref": "examples/forge_live_runtime_evidence_collection_packet.foundation.json",
            "artifact_hash": collection_packet["packet_hash"],
            "stage_status": collection_packet["collection_status"],
            "solver_outcome": collection_packet["solver_outcome"],
            "authority_effect": False,
        },
        {
            "stage_id": "live_runtime_local_evidence_bundle",
            "artifact_ref": "examples/forge_live_runtime_local_evidence_bundle.foundation.json",
            "artifact_hash": local_bundle["bundle_hash"],
            "stage_status": local_bundle["readiness_status"],
            "solver_outcome": local_bundle["solver_outcome"],
            "authority_effect": False,
        },
        {
            "stage_id": "live_runtime_evidence_acceptance_gate",
            "artifact_ref": "examples/forge_live_runtime_evidence_acceptance_gate.foundation.json",
            "artifact_hash": acceptance_gate["gate_hash"],
            "stage_status": acceptance_gate["acceptance_status"],
            "solver_outcome": acceptance_gate["solver_outcome"],
            "authority_effect": False,
        },
        {
            "stage_id": "live_runtime_signed_evidence_receipt",
            "artifact_ref": "examples/forge_live_runtime_signed_evidence_receipt.foundation.json",
            "artifact_hash": signed_receipt["receipt_hash"],
            "stage_status": signed_receipt["receipt_status"],
            "solver_outcome": signed_receipt["solver_outcome"],
            "authority_effect": False,
        },
        {
            "stage_id": "live_runtime_probe_admission_packet",
            "artifact_ref": "examples/forge_live_runtime_probe_admission_packet.foundation.json",
            "artifact_hash": probe_admission_packet["packet_hash"],
            "stage_status": probe_admission_packet["admission_status"],
            "solver_outcome": probe_admission_packet["solver_outcome"],
            "authority_effect": False,
        },
        {
            "stage_id": "live_runtime_approved_probe_output_packet",
            "artifact_ref": "examples/forge_live_runtime_approved_probe_output_packet.foundation.json",
            "artifact_hash": approved_probe_output_packet["packet_hash"],
            "stage_status": approved_probe_output_packet["output_intake_status"],
            "solver_outcome": approved_probe_output_packet["solver_outcome"],
            "authority_effect": False,
        },
        {
            "stage_id": "live_runtime_post_probe_reconciliation_packet",
            "artifact_ref": "examples/forge_live_runtime_post_probe_reconciliation_packet.foundation.json",
            "artifact_hash": reconciliation_packet["packet_hash"],
            "stage_status": reconciliation_packet["reconciliation_status"],
            "solver_outcome": reconciliation_packet["solver_outcome"],
            "authority_effect": False,
        },
        {
            "stage_id": "live_runtime_signed_receipt_population_gate",
            "artifact_ref": "examples/forge_live_runtime_signed_receipt_population_gate.foundation.json",
            "artifact_hash": population_gate["gate_hash"],
            "stage_status": population_gate["population_status"],
            "solver_outcome": population_gate["solver_outcome"],
            "authority_effect": False,
        },
    ]
    continuation_items = [
        {
            "continuation_id": "live_runtime_operator_evidence_request",
            "artifact_ref": "examples/forge_live_runtime_operator_evidence_request.foundation.json",
            "continuation_status": "blocked_awaiting_operator_live_evidence_refs",
            "solver_outcome": "AwaitingEvidence",
            "hash_included": False,
            "hash_exclusion_reason": "downstream_artifact_depends_on_read_model_hash",
            "authority_effect": False,
        },
        {
            "continuation_id": "live_runtime_operator_evidence_submission_packet",
            "artifact_ref": "examples/forge_live_runtime_operator_evidence_submission_packet.foundation.json",
            "continuation_status": "blocked_awaiting_operator_live_evidence_refs",
            "solver_outcome": "AwaitingEvidence",
            "hash_included": False,
            "hash_exclusion_reason": "downstream_artifact_depends_on_read_model_hash",
            "authority_effect": False,
        },
        {
            "continuation_id": "live_runtime_operator_evidence_verification_gate",
            "artifact_ref": "examples/forge_live_runtime_operator_evidence_verification_gate.foundation.json",
            "continuation_status": "blocked_awaiting_operator_evidence_verification",
            "solver_outcome": "AwaitingEvidence",
            "hash_included": False,
            "hash_exclusion_reason": "downstream_artifact_depends_on_read_model_hash",
            "authority_effect": False,
        },
        {
            "continuation_id": "live_runtime_operator_evidence_acceptance_handoff_packet",
            "artifact_ref": "examples/forge_live_runtime_operator_evidence_acceptance_handoff_packet.foundation.json",
            "continuation_status": "blocked_awaiting_verified_operator_evidence",
            "solver_outcome": "AwaitingEvidence",
            "hash_included": False,
            "hash_exclusion_reason": "downstream_artifact_depends_on_read_model_hash",
            "authority_effect": False,
        },
    ]
    read_model = {
        "read_model_id": FORGE_LIVE_RUNTIME_EVIDENCE_CHAIN_READ_MODEL_ID,
        "schema_ref": FORGE_LIVE_RUNTIME_EVIDENCE_CHAIN_READ_MODEL_SCHEMA_REF,
        "schema_version": 1,
        "bridge_ref": FORGE_WRITE_SPINE_BRIDGE_ID,
        "source_signed_receipt_population_gate_ref": (
            "examples/forge_live_runtime_signed_receipt_population_gate.foundation.json"
        ),
        "source_signed_receipt_population_gate_hash": population_gate["gate_hash"],
        "read_model_mode": "foundation_live_runtime_evidence_chain_projection",
        "read_model_status": "blocked_awaiting_live_runtime_evidence",
        "solver_outcome": "AwaitingEvidence",
        "stage_items": stage_items,
        "stage_count": len(stage_items),
        "blocked_stage_count": len(stage_items),
        "continuation_items": continuation_items,
        "continuation_count": len(continuation_items),
        "live_evidence_present": False,
        "runtime_authority_effect": False,
        "required_controls": list(LIVE_RUNTIME_EVIDENCE_CHAIN_READ_MODEL_CONTROLS),
        "disallowed_authority": {
            "live_runtime_authorized": False,
            "state_write_runtime_registered": False,
            "production_authorized": False,
            "external_effects_allowed": False,
            "commit_allowed": False,
            "terminal_closure": False,
        },
        "next_allowed_action": "inspect_read_model_or_collect_live_evidence_after_operator_approval",
        "validators": [
            {
                "validator_id": "forge-live-runtime-evidence-chain-read-model",
                "command": "python scripts/validate_forge_live_runtime_evidence_chain_read_model.py",
                "required_for_closure": True,
            }
        ],
    }
    read_model["read_model_hash"] = canonical_hash(read_model)
    return read_model


def build_foundation_forge_live_runtime_operator_evidence_request() -> dict[str, Any]:
    """Build the non-executing operator request for Forge live-runtime evidence refs."""

    evidence_chain_read_model = build_foundation_forge_live_runtime_evidence_chain_read_model()
    required_inputs = [
        {
            "evidence_id": evidence_id,
            "target_evidence_ref": LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS[evidence_id],
            "required_evidence_classes": list(LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES),
            "current_state": "missing",
            "operator_action_required": "supply_refs_without_secret_values",
            "secret_values_allowed": False,
            "execution_allowed_after_input": False,
            "blocker_reason": f"{evidence_id}_operator_live_evidence_refs_missing",
        }
        for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS
    ]
    request = {
        "request_id": FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_REQUEST_ID,
        "schema_ref": FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_REQUEST_SCHEMA_REF,
        "schema_version": 1,
        "bridge_ref": FORGE_WRITE_SPINE_BRIDGE_ID,
        "source_evidence_chain_read_model_ref": "examples/forge_live_runtime_evidence_chain_read_model.foundation.json",
        "source_evidence_chain_read_model_hash": evidence_chain_read_model["read_model_hash"],
        "request_mode": "operator_live_evidence_refs_required",
        "request_status": "blocked_awaiting_operator_live_evidence_refs",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "required_inputs": required_inputs,
        "required_input_count": len(required_inputs),
        "blocked_reasons": [item["blocker_reason"] for item in required_inputs],
        "execution_allowed": False,
        "external_effect_performed": False,
        "secret_values_serialized": False,
        "production_ready_claimed": False,
        "runtime_authority_effect": False,
        "required_controls": list(LIVE_RUNTIME_OPERATOR_EVIDENCE_REQUEST_CONTROLS),
        "disallowed_authority": {
            "live_runtime_authorized": False,
            "state_write_runtime_registered": False,
            "production_authorized": False,
            "external_effects_allowed": False,
            "commit_allowed": False,
            "terminal_closure": False,
        },
        "next_allowed_action": "supply_operator_approved_live_evidence_refs_without_secret_values",
        "validators": [
            {
                "validator_id": "forge-live-runtime-operator-evidence-request",
                "command": "python scripts/validate_forge_live_runtime_operator_evidence_request.py",
                "required_for_closure": True,
            }
        ],
    }
    request["request_hash"] = canonical_hash(request)
    return request


def build_foundation_forge_live_runtime_operator_evidence_submission_packet() -> dict[str, Any]:
    """Build the blocked intake packet for operator-supplied evidence refs."""

    operator_request = build_foundation_forge_live_runtime_operator_evidence_request()
    submission_items = []
    for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS:
        submitted_refs = [
            {
                "evidence_class": evidence_class,
                "evidence_ref": "",
                "ref_hash": "",
                "submitted": False,
                "secret_value_present": False,
                "validation_status": "missing",
                "blocker_reason": f"{evidence_id}_{evidence_class}_missing",
            }
            for evidence_class in LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES
        ]
        submission_items.append(
            {
                "evidence_id": evidence_id,
                "target_evidence_ref": LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS[evidence_id],
                "requested_input_ref": (
                    f"request://forge/live-runtime/operator-evidence/{evidence_id.replace('_', '-')}"
                ),
                "submitted_refs": submitted_refs,
                "submitted_ref_count": 0,
                "required_ref_count": len(LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES),
                "all_required_refs_present": False,
                "secret_values_present": False,
                "submission_status": "blocked_missing_required_refs",
                "blocker_reason": f"{evidence_id}_submitted_refs_missing",
            }
        )
    packet = {
        "packet_id": FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_SUBMISSION_PACKET_ID,
        "schema_ref": FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_SUBMISSION_PACKET_SCHEMA_REF,
        "schema_version": 1,
        "bridge_ref": FORGE_WRITE_SPINE_BRIDGE_ID,
        "source_operator_evidence_request_ref": "examples/forge_live_runtime_operator_evidence_request.foundation.json",
        "source_operator_evidence_request_hash": operator_request["request_hash"],
        "submission_mode": "operator_live_evidence_ref_intake",
        "submission_status": "blocked_awaiting_operator_live_evidence_refs",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "submission_items": submission_items,
        "submission_item_count": len(submission_items),
        "submitted_ref_count": 0,
        "required_ref_count": (
            len(submission_items) * len(LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES)
        ),
        "all_required_refs_present": False,
        "secret_values_present": False,
        "runtime_authority_effect": False,
        "acceptance_allowed": False,
        "blocked_reasons": [item["blocker_reason"] for item in submission_items],
        "required_controls": list(LIVE_RUNTIME_OPERATOR_EVIDENCE_SUBMISSION_CONTROLS),
        "disallowed_authority": {
            "live_runtime_authorized": False,
            "state_write_runtime_registered": False,
            "production_authorized": False,
            "external_effects_allowed": False,
            "commit_allowed": False,
            "terminal_closure": False,
        },
        "next_allowed_action": "submit_redacted_operator_evidence_refs_for_validation",
        "validators": [
            {
                "validator_id": "forge-live-runtime-operator-evidence-submission-packet",
                "command": "python scripts/validate_forge_live_runtime_operator_evidence_submission_packet.py",
                "required_for_closure": True,
            }
        ],
    }
    packet["packet_hash"] = canonical_hash(packet)
    return packet


def build_foundation_forge_live_runtime_operator_evidence_verification_gate() -> dict[str, Any]:
    """Build the blocked gate for independently verifying submitted evidence refs."""

    submission_packet = build_foundation_forge_live_runtime_operator_evidence_submission_packet()
    verification_items = []
    for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS:
        verification_slots = [
            {
                "evidence_class": evidence_class,
                "source_evidence_ref": "",
                "source_ref_hash": "",
                "verification_ref": "",
                "verifier_identity_ref": "",
                "verification_status": "not_submitted",
                "verification_passed": False,
                "authority_effect": False,
                "blocker_reason": f"{evidence_id}_{evidence_class}_verification_missing",
            }
            for evidence_class in LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES
        ]
        verification_items.append(
            {
                "evidence_id": evidence_id,
                "target_evidence_ref": LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS[evidence_id],
                "source_submission_ref": (
                    f"submission://forge/live-runtime/operator-evidence/{evidence_id.replace('_', '-')}"
                ),
                "verification_slots": verification_slots,
                "submitted_ref_count": 0,
                "verified_ref_count": 0,
                "required_verification_count": len(LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES),
                "all_slots_verified": False,
                "verification_status": "blocked_awaiting_submitted_refs",
                "blocker_reason": f"{evidence_id}_verification_missing",
            }
        )
    gate = {
        "gate_id": FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_VERIFICATION_GATE_ID,
        "schema_ref": FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_VERIFICATION_GATE_SCHEMA_REF,
        "schema_version": 1,
        "bridge_ref": FORGE_WRITE_SPINE_BRIDGE_ID,
        "source_operator_evidence_submission_packet_ref": (
            "examples/forge_live_runtime_operator_evidence_submission_packet.foundation.json"
        ),
        "source_operator_evidence_submission_packet_hash": submission_packet["packet_hash"],
        "verification_mode": "operator_evidence_refs_require_independent_verification",
        "verification_status": "blocked_awaiting_operator_evidence_verification",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "verification_items": verification_items,
        "verification_item_count": len(verification_items),
        "submitted_ref_count": 0,
        "verified_ref_count": 0,
        "required_verification_count": (
            len(verification_items) * len(LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES)
        ),
        "all_submitted_refs_verified": False,
        "promotion_allowed": False,
        "signed_receipt_population_allowed": False,
        "runtime_authority_effect": False,
        "secret_values_present": False,
        "blocked_reasons": [item["blocker_reason"] for item in verification_items],
        "required_controls": list(LIVE_RUNTIME_OPERATOR_EVIDENCE_VERIFICATION_CONTROLS),
        "disallowed_authority": {
            "live_runtime_authorized": False,
            "state_write_runtime_registered": False,
            "production_authorized": False,
            "external_effects_allowed": False,
            "commit_allowed": False,
            "terminal_closure": False,
        },
        "next_allowed_action": "verify_submitted_operator_evidence_refs_before_acceptance",
        "validators": [
            {
                "validator_id": "forge-live-runtime-operator-evidence-verification-gate",
                "command": "python scripts/validate_forge_live_runtime_operator_evidence_verification_gate.py",
                "required_for_closure": True,
            }
        ],
    }
    gate["gate_hash"] = canonical_hash(gate)
    return gate


def build_foundation_forge_live_runtime_operator_evidence_acceptance_handoff_packet() -> dict[str, Any]:
    """Build the blocked handoff from verified operator refs to acceptance review."""

    verification_gate = build_foundation_forge_live_runtime_operator_evidence_verification_gate()
    handoff_items = [
        {
            "evidence_id": evidence_id,
            "target_evidence_ref": LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS[evidence_id],
            "source_verification_ref": (
                f"verification://forge/live-runtime/operator-evidence/{evidence_id.replace('_', '-')}"
            ),
            "verification_status": "missing",
            "verified_ref_count": 0,
            "required_verification_count": len(LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES),
            "ready_for_acceptance_review": False,
            "acceptance_authority_effect": False,
            "signed_receipt_population_allowed": False,
            "blocker_reason": f"{evidence_id}_verified_operator_evidence_missing",
        }
        for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS
    ]
    packet = {
        "packet_id": FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_ACCEPTANCE_HANDOFF_PACKET_ID,
        "schema_ref": FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_ACCEPTANCE_HANDOFF_PACKET_SCHEMA_REF,
        "schema_version": 1,
        "bridge_ref": FORGE_WRITE_SPINE_BRIDGE_ID,
        "source_operator_evidence_verification_gate_ref": (
            "examples/forge_live_runtime_operator_evidence_verification_gate.foundation.json"
        ),
        "source_operator_evidence_verification_gate_hash": verification_gate["gate_hash"],
        "handoff_mode": "verified_operator_evidence_to_acceptance_review",
        "handoff_status": "blocked_awaiting_verified_operator_evidence",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "handoff_items": handoff_items,
        "handoff_item_count": len(handoff_items),
        "ready_item_count": 0,
        "required_item_count": len(handoff_items),
        "all_items_ready_for_acceptance_review": False,
        "acceptance_review_allowed": False,
        "acceptance_authority_effect": False,
        "signed_receipt_population_allowed": False,
        "runtime_authority_effect": False,
        "secret_values_present": False,
        "blocked_reasons": [item["blocker_reason"] for item in handoff_items],
        "required_controls": list(LIVE_RUNTIME_OPERATOR_EVIDENCE_ACCEPTANCE_HANDOFF_CONTROLS),
        "disallowed_authority": {
            "live_runtime_authorized": False,
            "state_write_runtime_registered": False,
            "production_authorized": False,
            "external_effects_allowed": False,
            "commit_allowed": False,
            "terminal_closure": False,
        },
        "next_allowed_action": "route_verified_operator_evidence_to_acceptance_review",
        "validators": [
            {
                "validator_id": "forge-live-runtime-operator-evidence-acceptance-handoff-packet",
                "command": "python scripts/validate_forge_live_runtime_operator_evidence_acceptance_handoff_packet.py",
                "required_for_closure": True,
            }
        ],
    }
    packet["packet_hash"] = canonical_hash(packet)
    return packet


def _request_blockers(
    request: ForgeStateWriteAdmissionRequest,
    policy: ForgeStateWriteAdmissionPolicy,
) -> tuple[str, ...]:
    blockers: list[str] = []
    _require_non_empty(request.request_id, "request_id", blockers)
    _require_non_empty(request.tenant_id, "tenant_id", blockers)
    _require_non_empty(request.actor_id, "actor_id", blockers)
    _require_non_empty(request.mesh_id, "mesh_id", blockers)
    _require_non_empty(request.operation_id, "operation_id", blockers)
    if request.bridge_ref != policy.bridge_id:
        blockers.append("bridge_ref_invalid")
    if request.requested_environment not in FORGE_ADMISSION_ENVIRONMENTS:
        blockers.append("requested_environment_invalid")
    elif request.requested_environment not in policy.allowed_prepare_environments:
        blockers.append("production_or_read_only_environment_not_admitted")
    if request.requested_environment == "production_state_changing":
        blockers.append("production_state_changing_no_go")
    if request.decision_status != "conditional_accept":
        blockers.append("conditional_decision_not_accepted")
    if request.selected_candidate_id not in FORGE_STATE_WRITE_CANDIDATES:
        blockers.append("selected_candidate_not_admitted")
    if request.mutation_performed:
        blockers.append("mutation_performed_before_admission")
    for field_name in (
        "before_state_hash",
        "after_state_hash",
        "delta_hash",
        "policy_hash",
        "evaluation_context_hash",
        "execution_scope_hash",
    ):
        if not _is_sha256_ref(str(getattr(request, field_name))):
            blockers.append(f"{field_name}_invalid")
    if not request.evidence_refs or any(not str(ref).strip() for ref in request.evidence_refs):
        blockers.append("evidence_refs_required")
    _validate_stages(request.stages, blockers)
    _validate_certificate(request.certificate, policy, blockers)
    _validate_service_boundary(request.service_boundary, blockers)
    return tuple(dict.fromkeys(blockers))


def _validate_stages(stages: list[ForgeStateWriteStageEvidence], blockers: list[str]) -> None:
    if len(stages) != len(EXPECTED_STAGE_IDS):
        blockers.append("write_spine_stage_count_invalid")
        return
    stage_ids = tuple(stage.stage_id for stage in stages)
    orders = tuple(stage.order for stage in stages)
    if stage_ids != EXPECTED_STAGE_IDS:
        blockers.append("write_spine_stage_order_invalid")
    if orders != tuple(range(1, len(EXPECTED_STAGE_IDS) + 1)):
        blockers.append("write_spine_stage_order_fields_invalid")
    for stage in stages:
        expected_boundary = EXPECTED_STAGE_AUTHORITY_BOUNDARIES.get(stage.stage_id)
        if not stage.satisfied:
            blockers.append(f"{stage.stage_id}_not_satisfied")
        if not stage.receipt_ref:
            blockers.append(f"{stage.stage_id}_receipt_ref_required")
        if not _is_sha256_ref(stage.receipt_hash):
            blockers.append(f"{stage.stage_id}_receipt_hash_invalid")
        if stage.authority_boundary != expected_boundary:
            blockers.append(f"{stage.stage_id}_authority_boundary_invalid")


def _validate_certificate(
    certificate: ForgeStateWriteCertificateEvidence,
    policy: ForgeStateWriteAdmissionPolicy,
    blockers: list[str],
) -> None:
    if certificate.profile != FORGE_CERTIFICATE_PROFILE:
        blockers.append("certificate_profile_invalid")
    if policy.require_development_certificate and certificate.development_only is not True:
        blockers.append("certificate_must_be_development_only")
    if tuple(certificate.required_fields) != EXPECTED_CERTIFICATE_FIELDS:
        blockers.append("certificate_required_fields_invalid")
    for field_name in ("key_id", "trust_epoch", "nonce", "signature"):
        _require_non_empty(str(getattr(certificate, field_name)), f"certificate_{field_name}", blockers)
    if not _is_sha256_ref(certificate.certificate_hash):
        blockers.append("certificate_hash_invalid")
    issued_at = _parse_instant(certificate.issued_at)
    expires_at = _parse_instant(certificate.expires_at)
    if issued_at is None:
        blockers.append("certificate_issued_at_invalid")
    if expires_at is None:
        blockers.append("certificate_expires_at_invalid")
    if issued_at is not None and expires_at is not None:
        lifetime_seconds = int((expires_at - issued_at).total_seconds())
        if lifetime_seconds <= 0:
            blockers.append("certificate_expiry_not_after_issued")
        if lifetime_seconds > policy.max_certificate_lifetime_seconds:
            blockers.append("certificate_lifetime_exceeds_policy")


def _validate_service_boundary(
    service_boundary: ForgeStateWriteServiceBoundaryEvidence,
    blockers: list[str],
) -> None:
    required_true = (
        "signed_rpc",
        "caller_audience_binding",
        "request_expiry",
        "persistent_nonce_replay_guard",
        "pinned_phigov_trust_root",
        "pinned_lineage_identity",
        "local_development_keys",
    )
    for field_name in required_true:
        if getattr(service_boundary, field_name) is not True:
            blockers.append(f"service_boundary_{field_name}_required")
    if service_boundary.transport_confidentiality is not False:
        blockers.append("service_boundary_transport_confidentiality_not_available")
    if service_boundary.production_authorized is not False:
        blockers.append("service_boundary_production_authorized_forbidden")


def _fixture_hash(payload: dict[str, Any]) -> str:
    return f"sha256:{canonical_hash(payload)}"


def canonical_hash(payload: dict[str, Any]) -> str:
    """Return a deterministic SHA-256 hash for a JSON-compatible payload."""

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_sha256_ref(value: str) -> bool:
    return bool(SHA256_REF_PATTERN.fullmatch(value))


def _require_non_empty(value: str, field_name: str, blockers: list[str]) -> None:
    if not value.strip():
        blockers.append(f"{field_name}_required")


def _parse_instant(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
