"""Sandbox patch readiness registry.

Purpose: define reusable no-effect readiness projections for sandbox patch
    progression from validation through next scope admission.
Governance scope: local developer workflow readiness summaries and status
    receipt source references only.
Dependencies: typing.
Invariants:
  - Registry entries are observational and side-effect free.
  - No registry entry grants execution, connector, deployment, or external
    authority.
  - Projection helpers return defensive payload copies.
"""

from __future__ import annotations

from typing import Any, Mapping


SANDBOX_PATCH_READINESS_REGISTRY: tuple[tuple[str, Mapping[str, Any], str], ...] = (
    (
        "operator_sandbox_patch_validation_readiness_summary",
        {
            "summary_id": "operator_sandbox_patch_validation_readiness.foundation",
            "validation_status": "blocked_missing_bundle",
            "bundle_path": "developer_workflow_sandbox_receipt_bundle.collected.json",
            "validator_command": (
                "python scripts/validate_developer_workflow_sandbox_receipt_bundle.py "
                "--bundle developer_workflow_sandbox_receipt_bundle.collected.json"
            ),
            "required_before_validation": [
                "sandbox_patch_receipt_bundle_generated",
                "sandbox_patch_receipt_attached",
            ],
            "missing_prerequisite_count": 2,
            "validation_performed": False,
            "terminal_review_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Sandbox patch validation blocked until the collected bundle exists and receipt is attached"
            ),
        },
        "docs/21_workflow_runtime.md sandbox_patch_receipt validation readiness",
    ),
    (
        "operator_sandbox_patch_terminal_review_summary",
        {
            "summary_id": "operator_sandbox_patch_terminal_review.foundation",
            "review_status": "blocked_until_validation",
            "review_target": "sandbox_patch_receipt",
            "required_before_review": [
                "sandbox_patch_receipt_bundle_generated",
                "sandbox_patch_receipt_attached",
                "sandbox_patch_bundle_validated",
            ],
            "missing_prerequisite_count": 3,
            "review_command": (
                "python scripts/validate_developer_workflow_sandbox_receipt_bundle.py "
                "--bundle developer_workflow_sandbox_receipt_bundle.collected.json"
            ),
            "review_performed": False,
            "approval_request_allowed": False,
            "pr_creation_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Sandbox patch terminal review blocked until bundle generation, attachment, and validation complete"
            ),
        },
        "docs/21_workflow_runtime.md sandbox_patch_receipt terminal review readiness",
    ),
    (
        "operator_sandbox_patch_approval_readiness_summary",
        {
            "summary_id": "operator_sandbox_patch_approval_readiness.foundation",
            "approval_status": "blocked_until_terminal_review",
            "approval_target": "sandbox_patch_receipt",
            "required_before_approval": [
                "sandbox_patch_receipt_bundle_generated",
                "sandbox_patch_receipt_attached",
                "sandbox_patch_bundle_validated",
                "sandbox_patch_terminal_review_complete",
            ],
            "missing_prerequisite_count": 4,
            "approval_request_allowed": False,
            "approval_request_performed": False,
            "pr_preparation_allowed": False,
            "pr_creation_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Sandbox patch approval blocked until terminal review closes with validated evidence"
            ),
        },
        "docs/21_workflow_runtime.md sandbox_patch_receipt approval readiness",
    ),
    (
        "operator_sandbox_patch_pr_preparation_readiness_summary",
        {
            "summary_id": "operator_sandbox_patch_pr_preparation_readiness.foundation",
            "preparation_status": "blocked_until_approval",
            "preparation_target": "local_pr_candidate_packet",
            "required_before_preparation": [
                "sandbox_patch_receipt_bundle_generated",
                "sandbox_patch_receipt_attached",
                "sandbox_patch_bundle_validated",
                "sandbox_patch_terminal_review_complete",
                "operator_approval_recorded",
            ],
            "missing_prerequisite_count": 5,
            "preparation_performed": False,
            "pr_preparation_allowed": False,
            "branch_push_allowed": False,
            "pr_creation_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "PR preparation blocked until sandbox patch approval is recorded with validated evidence"
            ),
        },
        "docs/21_workflow_runtime.md sandbox_patch_receipt PR preparation readiness",
    ),
    (
        "operator_sandbox_patch_pr_creation_readiness_summary",
        {
            "summary_id": "operator_sandbox_patch_pr_creation_readiness.foundation",
            "creation_status": "blocked_until_pr_preparation",
            "creation_target": "github_pull_request",
            "required_before_creation": [
                "local_pr_candidate_packet_prepared",
                "local_pr_candidate_packet_validated",
                "external_pr_execution_approval_recorded",
                "branch_push_authority_bound",
                "github_pr_admission_passed",
            ],
            "missing_prerequisite_count": 5,
            "creation_performed": False,
            "branch_push_allowed": False,
            "pr_creation_allowed": False,
            "connector_call_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "PR creation blocked until local PR preparation and external PR approval evidence are complete"
            ),
        },
        "docs/21_workflow_runtime.md sandbox_patch_receipt PR creation readiness",
    ),
    (
        "operator_sandbox_patch_pr_ci_readiness_summary",
        {
            "summary_id": "operator_sandbox_patch_pr_ci_readiness.foundation",
            "ci_status": "blocked_until_pr_creation",
            "ci_target": "github_pr_ci_checks",
            "required_before_ci": [
                "github_pull_request_created",
                "pr_metadata_packet_recorded",
                "ci_gate_before_ready_for_review_witness_bound",
                "github_check_read_authority_bound",
                "pr_effect_reconciliation_pending",
            ],
            "missing_prerequisite_count": 5,
            "ci_observation_performed": False,
            "github_poll_allowed": False,
            "check_update_allowed": False,
            "ready_for_review_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "PR CI readiness blocked until PR creation evidence and CI observation authority are complete"
            ),
        },
        "docs/21_workflow_runtime.md sandbox_patch_receipt PR CI readiness",
    ),
    (
        "operator_sandbox_patch_merge_readiness_summary",
        {
            "summary_id": "operator_sandbox_patch_merge_readiness.foundation",
            "merge_status": "blocked_until_ci_pass",
            "merge_target": "protected_branch_merge",
            "required_before_merge": [
                "github_pull_request_created",
                "ci_checks_passed",
                "review_approval_recorded",
                "rollback_plan_verified",
                "merge_approval_recorded",
            ],
            "missing_prerequisite_count": 5,
            "merge_performed": False,
            "merge_allowed": False,
            "branch_write_allowed": False,
            "github_call_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Merge readiness blocked until CI pass, review approval, rollback, and merge approval evidence are complete"
            ),
        },
        "docs/21_workflow_runtime.md sandbox_patch_receipt merge readiness",
    ),
    (
        "operator_sandbox_patch_release_handoff_readiness_summary",
        {
            "summary_id": "operator_sandbox_patch_release_handoff_readiness.foundation",
            "handoff_status": "blocked_until_terminal_closure",
            "handoff_target": "release_handoff_packet",
            "required_before_handoff": [
                "merge_execution_receipt_recorded",
                "terminal_closure_certificate_minted",
                "effect_reconciliation_witness_bound",
                "rollback_retention_verified",
                "release_notes_prepared",
            ],
            "missing_prerequisite_count": 5,
            "handoff_performed": False,
            "release_publication_allowed": False,
            "deployment_allowed": False,
            "public_claim_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Release handoff blocked until terminal closure, reconciliation, rollback, and release-note evidence are complete"
            ),
        },
        "docs/21_workflow_runtime.md sandbox_patch_receipt release handoff readiness",
    ),
    (
        "operator_sandbox_patch_deployment_publication_readiness_summary",
        {
            "summary_id": "operator_sandbox_patch_deployment_publication_readiness.foundation",
            "publication_status": "blocked_until_release_handoff",
            "publication_target": "deployment_publication_closure_plan",
            "required_before_publication": [
                "release_handoff_packet_prepared",
                "deployment_publication_closure_plan_verified",
                "production_evidence_witness_bound",
                "dns_target_binding_verified",
                "operator_deployment_approval_recorded",
            ],
            "missing_prerequisite_count": 5,
            "publication_performed": False,
            "deployment_allowed": False,
            "dns_change_allowed": False,
            "production_claim_allowed": False,
            "public_endpoint_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Deployment publication blocked until release handoff, production evidence, DNS binding, and deployment approval evidence are complete"
            ),
        },
        "docs/21_workflow_runtime.md sandbox_patch_receipt deployment publication readiness",
    ),
    (
        "operator_sandbox_patch_production_monitoring_readiness_summary",
        {
            "summary_id": "operator_sandbox_patch_production_monitoring_readiness.foundation",
            "monitoring_status": "blocked_until_publication",
            "monitoring_target": "production_monitoring_witness",
            "required_before_monitoring": [
                "deployment_publication_witness_recorded",
                "public_health_witness_bound",
                "runtime_conformance_certificate_available",
                "telemetry_monitoring_plan_verified",
                "incident_rollback_recovery_plan_verified",
            ],
            "missing_prerequisite_count": 5,
            "monitoring_activation_performed": False,
            "monitor_activation_allowed": False,
            "alert_routing_allowed": False,
            "production_claim_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Production monitoring blocked until deployment publication, health, runtime conformance, telemetry, and incident recovery evidence are complete"
            ),
        },
        "docs/21_workflow_runtime.md sandbox_patch_receipt production monitoring readiness",
    ),
    (
        "operator_sandbox_patch_incident_response_readiness_summary",
        {
            "summary_id": "operator_sandbox_patch_incident_response_readiness.foundation",
            "incident_status": "blocked_until_monitoring",
            "incident_target": "incident_response_runbook",
            "required_before_incident_response": [
                "production_monitoring_witness_recorded",
                "incident_response_runbook_verified",
                "rollback_execution_receipt_template_bound",
                "containment_evidence_contract_bound",
                "operator_incident_authority_recorded",
            ],
            "missing_prerequisite_count": 5,
            "incident_response_performed": False,
            "containment_allowed": False,
            "rollback_execution_allowed": False,
            "paging_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Incident response blocked until monitoring, runbook, rollback, containment, and operator authority evidence are complete"
            ),
        },
        "docs/21_workflow_runtime.md sandbox_patch_receipt incident response readiness",
    ),
    (
        "operator_sandbox_patch_recovery_closure_readiness_summary",
        {
            "summary_id": "operator_sandbox_patch_recovery_closure_readiness.foundation",
            "recovery_status": "blocked_until_incident_response",
            "recovery_target": "recovery_closure_packet",
            "required_before_recovery_closure": [
                "incident_containment_evidence_recorded",
                "rollback_or_replay_receipt_recorded",
                "post_incident_verification_passed",
                "operator_recovery_closure_approval_recorded",
                "terminal_recovery_closure_packet_prepared",
            ],
            "missing_prerequisite_count": 5,
            "recovery_closure_performed": False,
            "closure_certification_allowed": False,
            "replay_promotion_allowed": False,
            "post_incident_publication_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Recovery closure blocked until containment, rollback or replay, verification, approval, and terminal recovery packet evidence are complete"
            ),
        },
        "docs/21_workflow_runtime.md sandbox_patch_receipt recovery closure readiness",
    ),
    (
        "operator_sandbox_patch_trust_ledger_readiness_summary",
        {
            "summary_id": "operator_sandbox_patch_trust_ledger_readiness.foundation",
            "ledger_status": "blocked_until_recovery_closure",
            "ledger_target": "trust_ledger_anchor_packet",
            "required_before_trust_ledger_anchor": [
                "terminal_recovery_closure_packet_prepared",
                "trust_ledger_bundle_export_prepared",
                "evidence_artifact_hashes_recorded",
                "operator_trust_ledger_anchor_approval_recorded",
                "remote_submission_preflight_passed",
            ],
            "missing_prerequisite_count": 5,
            "ledger_anchor_performed": False,
            "remote_submission_allowed": False,
            "verification_publication_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Trust ledger anchoring blocked until recovery closure, export, hash, approval, and remote submission preflight evidence are complete"
            ),
        },
        "docs/21_workflow_runtime.md sandbox_patch_receipt trust ledger readiness",
    ),
    (
        "operator_sandbox_patch_terminal_audit_export_readiness_summary",
        {
            "summary_id": "operator_sandbox_patch_terminal_audit_export_readiness.foundation",
            "audit_export_status": "blocked_until_trust_ledger_anchor",
            "audit_export_target": "terminal_audit_export_package",
            "required_before_terminal_audit_export": [
                "trust_ledger_anchor_receipt_recorded",
                "trust_ledger_anchor_verification_passed",
                "audit_bundle_integrity_report_recorded",
                "operator_audit_export_approval_recorded",
                "export_retention_boundary_verified",
            ],
            "missing_prerequisite_count": 5,
            "audit_export_performed": False,
            "archive_submission_allowed": False,
            "external_publication_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Terminal audit export blocked until trust ledger anchor, verification, integrity, approval, and retention evidence are complete"
            ),
        },
        "docs/21_workflow_runtime.md sandbox_patch_receipt terminal audit export readiness",
    ),
    (
        "operator_sandbox_patch_foundation_closure_readiness_summary",
        {
            "summary_id": "operator_sandbox_patch_foundation_closure_readiness.foundation",
            "foundation_closure_status": "blocked_until_terminal_audit_export",
            "foundation_closure_target": "foundation_closure_certificate",
            "required_before_foundation_closure": [
                "terminal_audit_export_package_prepared",
                "operator_final_closure_approval_recorded",
                "all_no_effect_denials_preserved",
                "open_gap_register_reviewed",
                "next_iteration_handoff_recorded",
            ],
            "missing_prerequisite_count": 5,
            "foundation_closure_certified": False,
            "promotion_allowed": False,
            "handoff_publication_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Foundation closure blocked until terminal audit export, final approval, denial preservation, gap review, and next-iteration handoff evidence are complete"
            ),
        },
        "docs/21_workflow_runtime.md sandbox_patch_receipt foundation closure readiness",
    ),
    (
        "operator_sandbox_patch_iteration_resume_readiness_summary",
        {
            "summary_id": "operator_sandbox_patch_iteration_resume_readiness.foundation",
            "iteration_resume_status": "blocked_until_foundation_closure",
            "iteration_resume_target": "next_iteration_intake_packet",
            "required_before_iteration_resume": [
                "foundation_closure_certificate_recorded",
                "next_iteration_scope_declared",
                "next_iteration_risk_boundary_reviewed",
                "next_iteration_evidence_queue_seeded",
                "operator_resume_intent_recorded",
            ],
            "missing_prerequisite_count": 5,
            "next_iteration_started": False,
            "automatic_resume_allowed": False,
            "authority_carryover_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Iteration resume blocked until foundation closure, next scope, risk boundary, evidence queue, and operator resume intent evidence are complete"
            ),
        },
        "docs/21_workflow_runtime.md sandbox_patch_receipt iteration resume readiness",
    ),
    (
        "operator_sandbox_patch_next_scope_admission_readiness_summary",
        {
            "summary_id": "operator_sandbox_patch_next_scope_admission_readiness.foundation",
            "next_scope_admission_status": "blocked_until_iteration_resume",
            "next_scope_target": "next_scope_admission_packet",
            "required_before_next_scope_admission": [
                "next_iteration_intake_packet_prepared",
                "next_scope_boundaries_declared",
                "next_scope_acceptance_criteria_recorded",
                "next_scope_risk_review_recorded",
                "next_scope_rollback_expectations_recorded",
            ],
            "missing_prerequisite_count": 5,
            "scope_admitted": False,
            "execution_allowed": False,
            "authority_promotion_allowed": False,
            "external_effects_allowed": False,
            "operator_message": (
                "Next scope admission blocked until intake, boundaries, acceptance criteria, risk review, and rollback expectation evidence are complete"
            ),
        },
        "docs/21_workflow_runtime.md sandbox_patch_receipt next scope admission readiness",
    ),
)


def copy_readiness_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a defensive copy of one readiness payload."""
    return {key: list(value) if isinstance(value, list) else value for key, value in payload.items()}


def sandbox_patch_readiness_receipt_entries() -> dict[str, dict[str, Any]]:
    """Return status receipt entries keyed by readiness summary id."""
    return {
        summary_key: copy_readiness_payload(payload)
        for summary_key, payload, _source_ref in SANDBOX_PATCH_READINESS_REGISTRY
    }


def sandbox_patch_readiness_source_refs() -> dict[str, str]:
    """Return source reference map keyed by readiness summary id."""
    return {
        summary_key: source_ref
        for summary_key, _payload, source_ref in SANDBOX_PATCH_READINESS_REGISTRY
    }


def _first_key_with_suffix(payload: Mapping[str, Any], suffix: str) -> str:
    for key in payload:
        if key.endswith(suffix):
            return key
    return ""


def _first_key_with_prefix(payload: Mapping[str, Any], prefix: str) -> str:
    for key in payload:
        if key.startswith(prefix):
            return key
    return ""


def sandbox_patch_readiness_compact_summary() -> dict[str, Any]:
    """Return the first blocked sandbox patch readiness stage."""
    for summary_key, payload, source_ref in SANDBOX_PATCH_READINESS_REGISTRY:
        missing_count = int(payload.get("missing_prerequisite_count") or 0)
        if missing_count <= 0:
            continue
        status_key = _first_key_with_suffix(payload, "_status")
        target_key = _first_key_with_suffix(payload, "_target")
        required_key = _first_key_with_prefix(payload, "required_before_")
        required_before = payload.get(required_key, ())
        if not isinstance(required_before, list):
            required_before = []
        return {
            "summary_id": "operator_sandbox_patch_readiness_compact.foundation",
            "blocked_stage_summary_key": summary_key,
            "blocked_stage_summary_id": str(payload.get("summary_id") or ""),
            "blocked_stage_status": str(payload.get(status_key) or "unknown"),
            "blocked_stage_target": str(payload.get(target_key) or payload.get("bundle_path") or ""),
            "next_evidence_id": str(required_before[0] if required_before else ""),
            "missing_prerequisite_count": missing_count,
            "required_before_unlock": list(required_before),
            "external_effects_allowed": payload.get("external_effects_allowed") is True,
            "operator_message": str(payload.get("operator_message") or ""),
            "source_ref": source_ref,
        }
    return {
        "summary_id": "operator_sandbox_patch_readiness_compact.foundation",
        "blocked_stage_summary_key": "",
        "blocked_stage_summary_id": "",
        "blocked_stage_status": "unblocked",
        "blocked_stage_target": "",
        "next_evidence_id": "",
        "missing_prerequisite_count": 0,
        "required_before_unlock": [],
        "external_effects_allowed": False,
        "operator_message": "Sandbox patch readiness registry has no blocked stage",
        "source_ref": "",
    }
