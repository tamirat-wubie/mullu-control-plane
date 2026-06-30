#!/usr/bin/env python3
"""Run repository-local workspace governance checks.

Purpose: provide one deterministic preflight command for the control-plane
checkout without depending on the broader parent workspace script surface.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: Python standard library and repository-local validation scripts.
Invariants:
  - Default checks are read-only and deterministic.
  - Every check emits an explicit command receipt.
  - Long preflights emit progress witnesses without corrupting JSON stdout.
  - Full unsharded preflights use a workspace-local lock.
  - Saved canonical receipts require full unsharded preflight execution.
  - The process returns nonzero when any required check fails.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from types import TracebackType
from typing import TextIO


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_RETURN_CODE = 124
PREFLIGHT_LOCK_RETURN_CODE = 125
CHECK_EXCEPTION_RETURN_CODE = 126
PREFLIGHT_LOCK_ID = "workspace_governance_preflight_lock"
DEFAULT_PREFLIGHT_LOCK_PATH = WORKSPACE_ROOT / ".tmp" / "workspace-governance-preflight.lock"
CANONICAL_PREFLIGHT_RECEIPT_EXAMPLE_NAME = "workspace_governance_preflight_receipt_example"
CANONICAL_PREFLIGHT_RECEIPT_EXAMPLE_PATH = (
    WORKSPACE_ROOT / "docs" / "workspace-governance-preflight-receipt-example.json"
)
DEFAULT_MAX_WORKERS = 8


class PreflightLockError(RuntimeError):
    """Raised when a full governance preflight is already active."""


@dataclass(frozen=True, slots=True)
class CheckCommand:
    """One deterministic governance check command."""

    name: str
    args: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Observed result for one governance check command."""

    name: str
    args: tuple[str, ...]
    return_code: int
    stdout: str
    stderr: str
    termination_reason: str = "completed"
    termination_signal: int | None = None

    @property
    def passed(self) -> bool:
        """Return whether the check completed successfully."""

        return self.return_code == 0


@dataclass(frozen=True, slots=True)
class ProcessExecution:
    """Observed subprocess execution result before governance wrapping."""

    return_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class PreflightLock:
    """Workspace-local exclusive lock for full preflight execution."""

    def __init__(self, lock_path: Path = DEFAULT_PREFLIGHT_LOCK_PATH) -> None:
        self.lock_path = lock_path
        self._file_descriptor: int | None = None

    def __enter__(self) -> "PreflightLock":
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            self._file_descriptor = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            if not _remove_stale_preflight_lock(self.lock_path):
                raise PreflightLockError(f"workspace governance preflight is already running: {self.lock_path}") from exc
            try:
                self._file_descriptor = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError as retry_exc:
                raise PreflightLockError(
                    f"workspace governance preflight is already running: {self.lock_path}"
                ) from retry_exc

        payload = {
            "lock_id": PREFLIGHT_LOCK_ID,
            "pid": os.getpid(),
            "created_at_epoch": time.time(),
        }
        os.write(self._file_descriptor, (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8"))
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._file_descriptor is not None:
            os.close(self._file_descriptor)
            self._file_descriptor = None
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass


def build_check_commands(python_executable: str = sys.executable) -> tuple[CheckCommand, ...]:
    """Build the fixed repository-local governance check command list."""

    return (
        CheckCommand(
            "local_assurance_plan",
            (python_executable, "scripts/refresh_local_assurance.py", "--dry-run", "--json"),
        ),
        CheckCommand("agents_policy", (python_executable, "scripts/validate_agents_governance.py")),
        CheckCommand(
            "trusted_local_control_studio",
            (python_executable, "scripts/validate_trusted_local_control_studio.py"),
        ),
        CheckCommand("foundation_mode", (python_executable, "scripts/validate_foundation_mode.py")),
        CheckCommand(
            "foundation_source_control_boundary",
            (python_executable, "scripts/validate_foundation_source_control_boundary.py"),
        ),
        CheckCommand(
            "foundation_source_control_review_checklist_boundary",
            (python_executable, "scripts/validate_foundation_source_control_review_checklist_boundary.py"),
        ),
        CheckCommand(
            "foundation_local_release_packet_rehearsal_boundary",
            (python_executable, "scripts/validate_foundation_local_release_packet_rehearsal_boundary.py"),
        ),
        CheckCommand(
            "foundation_python_dependency_visibility_rehearsal_boundary",
            (python_executable, "scripts/validate_foundation_python_dependency_visibility_rehearsal_boundary.py"),
        ),
        CheckCommand(
            "agentic_service_harness_contract",
            (python_executable, "scripts/validate_agentic_service_harness_contract.py"),
        ),
        CheckCommand(
            "agentic_service_harness_read_models",
            (python_executable, "scripts/validate_agentic_service_harness_read_models.py"),
        ),
        CheckCommand(
            "agentic_service_harness_read_model_projections",
            (python_executable, "scripts/validate_agentic_service_harness_read_model_projections.py"),
        ),
        CheckCommand(
            "agentic_service_harness_read_model_integrity",
            (python_executable, "scripts/validate_agentic_service_harness_read_model_integrity.py"),
        ),
        CheckCommand(
            "agentic_service_harness_read_model_persistence",
            (python_executable, "scripts/validate_agentic_service_harness_read_model_persistence.py"),
        ),
        CheckCommand(
            "agentic_service_harness_read_model_binding_plan",
            (python_executable, "scripts/validate_agentic_service_harness_read_model_binding_plan.py"),
        ),
        CheckCommand(
            "agentic_service_harness_github_repo_task_service",
            (python_executable, "scripts/validate_agentic_service_harness_github_repo_task_service.py"),
        ),
        CheckCommand(
            "agentic_service_harness_github_repo_task_intake",
            (python_executable, "scripts/validate_agentic_service_harness_github_repo_task_intake.py"),
        ),
        CheckCommand(
            "agentic_service_harness_dashboard_data_contract",
            (python_executable, "scripts/validate_agentic_service_harness_dashboard_data_contract.py"),
        ),
        CheckCommand(
            "agentic_service_harness_adapter_registry_contract",
            (python_executable, "scripts/validate_agentic_service_harness_adapter_registry_contract.py"),
        ),
        CheckCommand(
            "agentic_service_harness_evidence_bundle_projection",
            (python_executable, "scripts/validate_agentic_service_harness_evidence_bundle_projection.py"),
        ),
        CheckCommand(
            "agentic_service_harness_receipt_evidence_read_models",
            (python_executable, "scripts/validate_agentic_service_harness_receipt_evidence_read_models.py"),
        ),
        CheckCommand(
            "agentic_service_harness_loopstatus_projection",
            (python_executable, "scripts/validate_agentic_service_harness_loopstatus_projection.py"),
        ),
        CheckCommand(
            "agentic_service_harness_receipt_projection",
            (python_executable, "scripts/validate_agentic_service_harness_receipt_projection.py"),
        ),
        CheckCommand(
            "agentic_service_harness_task_creation_admission_preflight",
            (python_executable, "scripts/validate_agentic_service_harness_task_creation_admission_preflight.py"),
        ),
        CheckCommand(
            "agentic_service_harness_github_task_receipt_emitter_dry_run",
            (python_executable, "scripts/validate_agentic_service_harness_github_task_receipt_emitter_dry_run.py"),
        ),
        CheckCommand(
            "agentic_service_harness_temporary_branch_workspace_preflight",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_temporary_branch_workspace_preflight.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_workspace_sandbox_preflight",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_workspace_sandbox_preflight.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_approved_branch_workspace_creation_preflight",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_approved_branch_workspace_creation_preflight.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_approved_branch_workspace_creation_authority_binding",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_approved_branch_workspace_creation_authority_binding.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_approved_branch_workspace_creation_observation_receipt",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_approved_branch_workspace_creation_observation_receipt.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_dry_run_test_runner_plan_receipt",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_dry_run_test_runner_plan_receipt.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_dry_run_test_execution_observation_receipt",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_dry_run_test_execution_observation_receipt.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_task_record_write_uao_admission_preflight",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_task_record_write_uao_admission_preflight.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_receipt_store_append_preflight",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_receipt_store_append_preflight.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_executed_test_receipt_admission_preflight",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_executed_test_receipt_admission_preflight.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_planned_file_change_collection_preflight",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_planned_file_change_collection_preflight.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_actual_file_change_summary_receipt",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_actual_file_change_summary_receipt.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_actual_diff_collection_admission_preflight",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_actual_diff_collection_admission_preflight.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_actual_diff_collection_receipt",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_actual_diff_collection_receipt.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_non_empty_diff_receipt_admission_preflight",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_non_empty_diff_receipt_admission_preflight.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_filesystem_write_admission_preflight",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_filesystem_write_admission_preflight.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_concrete_filesystem_write_evidence_candidate",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_concrete_filesystem_write_evidence_candidate.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_actual_filesystem_write_receipt_admission",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_actual_filesystem_write_receipt_admission.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_redacted_filesystem_write_execution_receipt",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_redacted_filesystem_write_execution_receipt.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_actual_non_empty_diff_receipt_binding",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_actual_non_empty_diff_receipt_binding.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_non_empty_diff_file_summary_receipt",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_non_empty_diff_file_summary_receipt.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_admission_preflight",
            (python_executable, "scripts/validate_agentic_service_harness_github_pr_admission_preflight.py"),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_creation_dry_run_receipt",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_creation_dry_run_receipt.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_creation_execution_admission",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_creation_execution_admission.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_creation_command_preview",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_creation_command_preview.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_operator_approval_request",
            (python_executable, "scripts/validate_agentic_service_harness_github_pr_operator_approval_request.py"),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_operator_approval_request_command_preview_binding",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_operator_approval_request_command_preview_binding.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_operator_response_witness",
            (python_executable, "scripts/validate_agentic_service_harness_github_pr_operator_response_witness.py"),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_operator_response_command_preview_binding",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_operator_response_command_preview_binding.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_branch_write_authority_binding",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_branch_write_authority_binding.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_uao_admission_witness",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_uao_admission_witness.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_repository_effect_rollback_plan_witness",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_repository_effect_rollback_plan_witness.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_ci_gate_before_ready_for_review_witness",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_ci_gate_before_ready_for_review_witness.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_effect_reconciliation_witness",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_effect_reconciliation_witness.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_effect_reconciliation_evidence_contract",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_effect_reconciliation_evidence_contract.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_effect_reconciliation_live_evidence",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_effect_reconciliation_live_evidence.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_terminal_closure_certificate_candidate",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_terminal_closure_certificate_candidate.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_terminal_closure_operator_approval_gate",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_terminal_closure_operator_approval_gate.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_terminal_closure_operator_decision_contract",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_contract.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_terminal_closure_generic_continuation_rejection",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_terminal_closure_generic_continuation_rejection.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_terminal_closure_certificate_minting",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_terminal_closure_certificate_minting.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_terminal_closure_certificate_read_model",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_terminal_closure_certificate_read_model.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_github_pr_terminal_closure_certificate_witness",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_github_pr_terminal_closure_certificate_witness.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_read_only_status_route_design",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_read_only_status_route_design.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_read_only_status_route",
            (python_executable, "scripts/validate_agentic_service_harness_read_only_status_route.py"),
        ),
        CheckCommand(
            "agentic_service_harness_authority_transitions",
            (python_executable, "scripts/validate_agentic_service_harness_authority_transitions.py"),
        ),
        CheckCommand(
            "channel_approval_strength_policy",
            (python_executable, "scripts/validate_channel_approval_strength_policy.py"),
        ),
        CheckCommand(
            "component_registry",
            (python_executable, "scripts/validate_component_registry.py"),
        ),
        CheckCommand(
            "component_lifecycle_transition_receipts",
            (python_executable, "scripts/validate_component_lifecycle_transition_receipts.py"),
        ),
        CheckCommand(
            "component_authority_envelope_witnesses",
            (python_executable, "scripts/validate_component_authority_envelope_witnesses.py"),
        ),
        CheckCommand(
            "component_router_inventory",
            (python_executable, "scripts/validate_component_router_inventory.py"),
        ),
        CheckCommand(
            "component_proof_binding",
            (python_executable, "scripts/validate_component_proof_binding.py"),
        ),
        CheckCommand(
            "component_route_family_ownership",
            (python_executable, "scripts/validate_component_route_family_ownership.py"),
        ),
        CheckCommand(
            "component_route_family_promotion_preflight",
            (python_executable, "scripts/validate_component_route_family_promotion_preflight.py"),
        ),
        CheckCommand(
            "component_route_family_promotion_witness_requirements",
            (python_executable, "scripts/validate_component_route_family_promotion_witness_requirements.py"),
        ),
        CheckCommand(
            "component_route_family_promotion_witness_evidence",
            (python_executable, "scripts/validate_component_route_family_promotion_witness_evidence.py"),
        ),
        CheckCommand(
            "component_route_family_promotion_approval_candidates",
            (python_executable, "scripts/validate_component_route_family_promotion_approval_candidates.py"),
        ),
        CheckCommand(
            "component_route_family_promotion_approval_intake",
            (python_executable, "scripts/validate_component_route_family_promotion_approval_intake.py"),
        ),
        CheckCommand(
            "component_route_family_promotion_submitted_evidence_verifier",
            (python_executable, "scripts/validate_component_route_family_promotion_submitted_evidence_verifier.py"),
        ),
        CheckCommand(
            "component_route_family_promotion_submitted_evidence_records",
            (python_executable, "scripts/validate_component_route_family_promotion_submitted_evidence_records.py"),
        ),
        CheckCommand(
            "component_route_family_promotion_submitted_evidence_payload_examples",
            (python_executable, "scripts/validate_component_route_family_promotion_submitted_evidence_payload_examples.py"),
        ),
        CheckCommand(
            "component_route_family_promotion_operator_submitted_evidence_records",
            (
                python_executable,
                "scripts/validate_component_route_family_promotion_operator_submitted_evidence_records.py",
            ),
        ),
        CheckCommand(
            "component_route_family_promotion_gate_satisfaction_evaluator",
            (
                python_executable,
                "scripts/validate_component_route_family_promotion_gate_satisfaction_evaluator.py",
            ),
        ),
        CheckCommand(
            "component_route_family_promotion_authority_decision_report",
            (
                python_executable,
                "scripts/validate_component_route_family_promotion_authority_decision_report.py",
            ),
        ),
        CheckCommand(
            "component_route_family_promotion_route_binding_decision_report",
            (
                python_executable,
                "scripts/validate_component_route_family_promotion_route_binding_decision_report.py",
            ),
        ),
        CheckCommand(
            "component_route_family_promotion_lifecycle_transition_decision_report",
            (
                python_executable,
                "scripts/validate_component_route_family_promotion_lifecycle_transition_decision_report.py",
            ),
        ),
        CheckCommand(
            "component_route_family_promotion_authority_upgrade_witness_decision_report",
            (
                python_executable,
                "scripts/validate_component_route_family_promotion_authority_upgrade_witness_decision_report.py",
            ),
        ),
        CheckCommand(
            "component_route_family_promotion_product_ownership_decision_report",
            (
                python_executable,
                "scripts/validate_component_route_family_promotion_product_ownership_decision_report.py",
            ),
        ),
        CheckCommand(
            "component_route_family_promotion_terminal_closure_denial_report",
            (
                python_executable,
                "scripts/validate_component_route_family_promotion_terminal_closure_denial_report.py",
            ),
        ),
        CheckCommand(
            "component_route_family_promotion_missing_evidence_ledger",
            (
                python_executable,
                "scripts/validate_component_route_family_promotion_missing_evidence_ledger.py",
            ),
        ),
        CheckCommand(
            "component_route_family_promotion_router_inventory_delta_candidate",
            (
                python_executable,
                "scripts/validate_component_route_family_promotion_router_inventory_delta_candidate.py",
            ),
        ),
        CheckCommand(
            "component_route_family_promotion_router_inventory_delta_witness_requirements",
            (
                python_executable,
                "scripts/validate_component_route_family_promotion_router_inventory_delta_witness_requirements.py",
            ),
        ),
        CheckCommand(
            "component_route_family_promotion_router_inventory_delta_witness_minting_preflight",
            (
                python_executable,
                "scripts/validate_component_route_family_promotion_router_inventory_delta_witness_minting_preflight.py",
            ),
        ),
        CheckCommand(
            "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report",
            (
                python_executable,
                "scripts/validate_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report.py",
            ),
        ),
        CheckCommand(
            "component_route_family_promotion_router_inventory_delta_witness_remediation_plan",
            (
                python_executable,
                "scripts/validate_component_route_family_promotion_router_inventory_delta_witness_remediation_plan.py",
            ),
        ),
        CheckCommand(
            "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request",
            (
                python_executable,
                "scripts/validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request.py",
            ),
        ),
        CheckCommand(
            "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger",
            (
                python_executable,
                "scripts/validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger.py",
            ),
        ),
        CheckCommand(
            "component_read_model",
            (python_executable, "scripts/validate_component_read_model.py"),
        ),
        CheckCommand(
            "component_autopsy",
            (python_executable, "scripts/validate_component_autopsy.py"),
        ),
        CheckCommand(
            "component_request_simulation",
            (python_executable, "scripts/validate_component_request_simulation.py"),
        ),
        CheckCommand(
            "component_bundle_compiler",
            (python_executable, "scripts/validate_component_bundle_compiler.py"),
        ),
        CheckCommand(
            "component_evidence_request_queue",
            (python_executable, "scripts/validate_component_evidence_request_queue.py"),
        ),
        CheckCommand(
            "component_evidence_submission_intake",
            (python_executable, "scripts/validate_component_evidence_submission_intake.py"),
        ),
        CheckCommand(
            "component_evidence_postmerge_audit",
            (python_executable, "scripts/validate_component_evidence_postmerge_audit.py"),
        ),
        CheckCommand(
            "component_graph",
            (python_executable, "scripts/validate_component_graph.py"),
        ),
        CheckCommand(
            "component_dead_detector",
            (python_executable, "scripts/validate_component_dead_detector.py"),
        ),
        CheckCommand(
            "read_only_first_worker_path",
            (python_executable, "scripts/validate_read_only_first_worker_path.py"),
        ),
        CheckCommand(
            "read_only_document_worker_path",
            (python_executable, "scripts/validate_read_only_document_worker_path.py"),
        ),
        CheckCommand(
            "read_only_search_worker_path",
            (python_executable, "scripts/validate_read_only_search_worker_path.py"),
        ),
        CheckCommand(
            "worker_failure_receipt",
            (python_executable, "scripts/validate_worker_failure_receipt.py"),
        ),
        CheckCommand(
            "agentic_service_harness_live_task_run_producer_evidence",
            (python_executable, "scripts/validate_agentic_service_harness_live_task_run_producer_evidence.py"),
        ),
        CheckCommand(
            "agentic_service_harness_live_task_run_producer_rehearsal",
            (python_executable, "scripts/validate_agentic_service_harness_live_task_run_producer_rehearsal.py"),
        ),
        CheckCommand(
            "agentic_service_harness_live_producer_admission_gate",
            (python_executable, "scripts/validate_agentic_service_harness_live_producer_admission_gate.py"),
        ),
        CheckCommand(
            "agentic_service_harness_live_producer_witness_requirements",
            (python_executable, "scripts/validate_agentic_service_harness_live_producer_witness_requirements.py"),
        ),
        CheckCommand(
            "agentic_service_harness_live_producer_operator_approval_request",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_live_producer_operator_approval_request.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_live_producer_operator_response_witness",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_live_producer_operator_response_witness.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_live_producer_operator_decision_evidence",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_live_producer_operator_decision_evidence.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_live_producer_operator_decision_record",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_live_producer_operator_decision_record.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_live_producer_operator_decision_value_absence",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_live_producer_operator_decision_value_absence.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_live_producer_operator_decision_pending_status",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_live_producer_operator_decision_pending_status.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_live_producer_operator_decision_value_intake_preflight",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_live_producer_operator_decision_value_intake_preflight.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_live_producer_operator_decision_generic_continuation_rejection",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_live_producer_operator_decision_generic_continuation_rejection.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_live_producer_operator_decision_value_request",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_live_producer_operator_decision_value_request.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_live_producer_operator_decision_value_template",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_live_producer_operator_decision_value_template.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_live_producer_operator_decision_value_collection_gate",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_live_producer_operator_decision_value_collection_gate.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_live_producer_operator_decision_value_record_path",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_live_producer_operator_decision_value_record_path.py",
            ),
        ),
        CheckCommand(
            "agentic_service_harness_live_producer_operator_decision_value_record",
            (
                python_executable,
                "scripts/validate_agentic_service_harness_live_producer_operator_decision_value_record.py",
            ),
        ),
        CheckCommand(
            "foundation_operator_readiness_boundary",
            (python_executable, "scripts/validate_foundation_operator_readiness_boundary.py"),
        ),
        CheckCommand(
            "foundation_solo_daily_loop_boundary",
            (python_executable, "scripts/validate_foundation_solo_daily_loop_boundary.py"),
        ),
        CheckCommand(
            "foundation_learning_path_boundary",
            (python_executable, "scripts/validate_foundation_learning_path_boundary.py"),
        ),
        CheckCommand(
            "foundation_learning_loop_rehearsal_boundary",
            (python_executable, "scripts/validate_foundation_learning_loop_rehearsal_boundary.py"),
        ),
        CheckCommand(
            "foundation_concept_glossary_rehearsal_boundary",
            (python_executable, "scripts/validate_foundation_concept_glossary_rehearsal_boundary.py"),
        ),
        CheckCommand(
            "foundation_life_meaning_doctrine_rehearsal_boundary",
            (python_executable, "scripts/validate_foundation_life_meaning_doctrine_rehearsal_boundary.py"),
        ),
        CheckCommand(
            "foundation_architecture_map_boundary",
            (python_executable, "scripts/validate_foundation_architecture_map_boundary.py"),
        ),
        CheckCommand(
            "foundation_system_boundary_inventory_boundary",
            (python_executable, "scripts/validate_foundation_system_boundary_inventory_boundary.py"),
        ),
        CheckCommand(
            "foundation_module_inventory_boundary",
            (python_executable, "scripts/validate_foundation_module_inventory_boundary.py"),
        ),
        CheckCommand(
            "foundation_component_contract_boundary",
            (python_executable, "scripts/validate_foundation_component_contract_boundary.py"),
        ),
        CheckCommand(
            "foundation_interface_map_boundary",
            (python_executable, "scripts/validate_foundation_interface_map_boundary.py"),
        ),
        CheckCommand(
            "foundation_dependency_graph_boundary",
            (python_executable, "scripts/validate_foundation_dependency_graph_boundary.py"),
        ),
        CheckCommand(
            "foundation_invariant_map_boundary",
            (python_executable, "scripts/validate_foundation_invariant_map_boundary.py"),
        ),
        CheckCommand(
            "foundation_hazard_map_boundary",
            (python_executable, "scripts/validate_foundation_hazard_map_boundary.py"),
        ),
        CheckCommand(
            "foundation_proof_reference_boundary",
            (python_executable, "scripts/validate_foundation_proof_reference_boundary.py"),
        ),
        CheckCommand(
            "foundation_gap_register_boundary",
            (python_executable, "scripts/validate_foundation_gap_register_boundary.py"),
        ),
        CheckCommand(
            "foundation_diff_review_boundary",
            (python_executable, "scripts/validate_foundation_diff_review_boundary.py"),
        ),
        CheckCommand(
            "foundation_change_handoff_boundary",
            (python_executable, "scripts/validate_foundation_change_handoff_boundary.py"),
        ),
        CheckCommand(
            "foundation_local_workstation_boundary",
            (python_executable, "scripts/validate_foundation_local_workstation_boundary.py"),
        ),
        CheckCommand(
            "foundation_documentation_boundary",
            (python_executable, "scripts/validate_foundation_documentation_boundary.py"),
        ),
        CheckCommand(
            "foundation_plain_language_status_boundary",
            (python_executable, "scripts/validate_foundation_plain_language_status_boundary.py"),
        ),
        CheckCommand(
            "foundation_accessibility_language_boundary",
            (python_executable, "scripts/validate_foundation_accessibility_language_boundary.py"),
        ),
        CheckCommand(
            "foundation_claim_boundary",
            (python_executable, "scripts/validate_foundation_claim_boundary.py"),
        ),
        CheckCommand(
            "foundation_website_posture_boundary",
            (python_executable, "scripts/validate_foundation_website_posture_boundary.py"),
        ),
        CheckCommand(
            "foundation_research_notebook_boundary",
            (python_executable, "scripts/validate_foundation_research_notebook_boundary.py"),
        ),
        CheckCommand(
            "foundation_evidence_ledger_boundary",
            (python_executable, "scripts/validate_foundation_evidence_ledger_boundary.py"),
        ),
        CheckCommand(
            "evidence_ledger_foundation_source",
            (python_executable, "scripts/validate_evidence_ledger_foundation_source.py"),
        ),
        CheckCommand(
            "foundation_decision_journal_boundary",
            (python_executable, "scripts/validate_foundation_decision_journal_boundary.py"),
        ),
        CheckCommand(
            "foundation_next_action_boundary",
            (python_executable, "scripts/validate_foundation_next_action_boundary.py"),
        ),
        CheckCommand(
            "foundation_test_evidence_boundary",
            (python_executable, "scripts/validate_foundation_test_evidence_boundary.py"),
        ),
        CheckCommand(
            "foundation_local_proof_thread",
            (python_executable, "scripts/validate_foundation_local_proof_thread.py"),
        ),
        CheckCommand(
            "foundation_private_recovery_boundary",
            (python_executable, "scripts/validate_foundation_private_recovery_boundary.py"),
        ),
        CheckCommand(
            "foundation_private_recovery_rehearsal_boundary",
            (python_executable, "scripts/validate_foundation_private_recovery_rehearsal_boundary.py"),
        ),
        CheckCommand(
            "foundation_secrets_credentials_boundary",
            (python_executable, "scripts/validate_foundation_secrets_credentials_boundary.py"),
        ),
        CheckCommand(
            "foundation_security_baseline_boundary",
            (python_executable, "scripts/validate_foundation_security_baseline_boundary.py"),
        ),
        CheckCommand(
            "foundation_cost_budget_boundary",
            (python_executable, "scripts/validate_foundation_cost_budget_boundary.py"),
        ),
        CheckCommand(
            "foundation_payment_provider_boundary",
            (python_executable, "scripts/validate_foundation_payment_provider_boundary.py"),
        ),
        CheckCommand(
            "foundation_runtime_environment_boundary",
            (python_executable, "scripts/validate_foundation_runtime_environment_boundary.py"),
        ),
        CheckCommand(
            "foundation_backup_export_boundary",
            (python_executable, "scripts/validate_foundation_backup_export_boundary.py"),
        ),
        CheckCommand(
            "foundation_deployment_deferral_boundary",
            (python_executable, "scripts/validate_foundation_deployment_deferral_boundary.py"),
        ),
        CheckCommand(
            "foundation_external_infrastructure_boundary",
            (python_executable, "scripts/validate_foundation_external_infrastructure_boundary.py"),
        ),
        CheckCommand(
            "foundation_runtime_secret_handoff_rehearsal_boundary",
            (python_executable, "scripts/validate_foundation_runtime_secret_handoff_rehearsal_boundary.py"),
        ),
        CheckCommand(
            "foundation_runtime_witness_deferral_boundary",
            (python_executable, "scripts/validate_foundation_runtime_witness_deferral_boundary.py"),
        ),
        CheckCommand(
            "foundation_production_dependency_evidence_rehearsal_boundary",
            (
                python_executable,
                "scripts/validate_foundation_production_dependency_evidence_rehearsal_boundary.py",
            ),
        ),
        CheckCommand(
            "foundation_external_evidence_acceptance_rehearsal_boundary",
            (
                python_executable,
                "scripts/validate_foundation_external_evidence_acceptance_rehearsal_boundary.py",
            ),
        ),
        CheckCommand(
            "foundation_deployment_upstream_api_gate_rehearsal_boundary",
            (
                python_executable,
                "scripts/validate_foundation_deployment_upstream_api_gate_rehearsal_boundary.py",
            ),
        ),
        CheckCommand(
            "foundation_gateway_dns_target_binding_rehearsal_boundary",
            (
                python_executable,
                "scripts/validate_foundation_gateway_dns_target_binding_rehearsal_boundary.py",
            ),
        ),
        CheckCommand(
            "foundation_gateway_dns_publication_rehearsal_boundary",
            (
                python_executable,
                "scripts/validate_foundation_gateway_dns_publication_rehearsal_boundary.py",
            ),
        ),
        CheckCommand(
            "foundation_gateway_dns_resolution_receipt_rehearsal_boundary",
            (
                python_executable,
                "scripts/validate_foundation_gateway_dns_resolution_receipt_rehearsal_boundary.py",
            ),
        ),
        CheckCommand(
            "foundation_gateway_endpoint_reachability_rehearsal_boundary",
            (
                python_executable,
                "scripts/validate_foundation_gateway_endpoint_reachability_rehearsal_boundary.py",
            ),
        ),
        CheckCommand(
            "foundation_gateway_endpoint_evidence_receipt_rehearsal_boundary",
            (
                python_executable,
                "scripts/validate_foundation_gateway_endpoint_evidence_receipt_rehearsal_boundary.py",
            ),
        ),
        CheckCommand(
            "foundation_public_health_declaration_rehearsal_boundary",
            (
                python_executable,
                "scripts/validate_foundation_public_health_declaration_rehearsal_boundary.py",
            ),
        ),
        CheckCommand(
            "foundation_deployment_witness_input_boundary",
            (python_executable, "scripts/validate_foundation_deployment_witness_input_boundary.py"),
        ),
        CheckCommand(
            "foundation_deployment_witness_preflight_rehearsal_boundary",
            (python_executable, "scripts/validate_foundation_deployment_witness_preflight_rehearsal_boundary.py"),
        ),
        CheckCommand(
            "foundation_deployment_witness_dispatch_rehearsal_boundary",
            (python_executable, "scripts/validate_foundation_deployment_witness_dispatch_rehearsal_boundary.py"),
        ),
        CheckCommand(
            "foundation_deployment_witness_artifact_validation_rehearsal_boundary",
            (
                python_executable,
                "scripts/validate_foundation_deployment_witness_artifact_validation_rehearsal_boundary.py",
            ),
        ),
        CheckCommand(
            "foundation_deployment_witness_evidence_handoff_boundary",
            (python_executable, "scripts/validate_foundation_deployment_witness_evidence_handoff_boundary.py"),
        ),
        CheckCommand(
            "foundation_deployment_witness_evidence_ledger_routing_boundary",
            (
                python_executable,
                "scripts/validate_foundation_deployment_witness_evidence_ledger_routing_boundary.py",
            ),
        ),
        CheckCommand(
            "foundation_domain_email_boundary",
            (python_executable, "scripts/validate_foundation_domain_email_boundary.py"),
        ),
        CheckCommand(
            "foundation_legal_business_boundary",
            (python_executable, "scripts/validate_foundation_legal_business_boundary.py"),
        ),
        CheckCommand(
            "foundation_legal_business_question_rehearsal_boundary",
            (python_executable, "scripts/validate_foundation_legal_business_question_rehearsal_boundary.py"),
        ),
        CheckCommand(
            "foundation_legal_review_deferral_boundary",
            (python_executable, "scripts/validate_foundation_legal_review_deferral_boundary.py"),
        ),
        CheckCommand(
            "foundation_company_formation_deferral_boundary",
            (python_executable, "scripts/validate_foundation_company_formation_deferral_boundary.py"),
        ),
        CheckCommand(
            "foundation_patent_disclosure_deferral_boundary",
            (python_executable, "scripts/validate_foundation_patent_disclosure_deferral_boundary.py"),
        ),
        CheckCommand(
            "foundation_product_scope_boundary",
            (python_executable, "scripts/validate_foundation_product_scope_boundary.py"),
        ),
        CheckCommand(
            "foundation_capability_roadmap_boundary",
            (python_executable, "scripts/validate_foundation_capability_roadmap_boundary.py"),
        ),
        CheckCommand(
            "foundation_agentic_management_boundary",
            (python_executable, "scripts/validate_foundation_agentic_management_boundary.py"),
        ),
        CheckCommand(
            "foundation_operations_runbook_boundary",
            (python_executable, "scripts/validate_foundation_operations_runbook_boundary.py"),
        ),
        CheckCommand(
            "foundation_market_research_boundary",
            (python_executable, "scripts/validate_foundation_market_research_boundary.py"),
        ),
        CheckCommand(
            "foundation_pilot_deferral_boundary",
            (python_executable, "scripts/validate_foundation_pilot_deferral_boundary.py"),
        ),
        CheckCommand(
            "foundation_pilot_deferral_rehearsal_boundary",
            (python_executable, "scripts/validate_foundation_pilot_deferral_rehearsal_boundary.py"),
        ),
        CheckCommand(
            "foundation_reassessment_gate_boundary",
            (python_executable, "scripts/validate_foundation_reassessment_gate_boundary.py"),
        ),
        CheckCommand(
            "foundation_support_readiness_boundary",
            (python_executable, "scripts/validate_foundation_support_readiness_boundary.py"),
        ),
        CheckCommand(
            "foundation_support_triage_rehearsal_boundary",
            (python_executable, "scripts/validate_foundation_support_triage_rehearsal_boundary.py"),
        ),
        CheckCommand(
            "foundation_intake_onboarding_boundary",
            (python_executable, "scripts/validate_foundation_intake_onboarding_boundary.py"),
        ),
        CheckCommand(
            "foundation_intake_questionnaire_rehearsal_boundary",
            (python_executable, "scripts/validate_foundation_intake_questionnaire_rehearsal_boundary.py"),
        ),
        CheckCommand(
            "foundation_customer_access_boundary",
            (python_executable, "scripts/validate_foundation_customer_access_boundary.py"),
        ),
        CheckCommand(
            "foundation_customer_access_policy_rehearsal_boundary",
            (python_executable, "scripts/validate_foundation_customer_access_policy_rehearsal_boundary.py"),
        ),
        CheckCommand(
            "foundation_github_app_token_format_boundary",
            (python_executable, "scripts/validate_foundation_github_app_token_format_boundary.py"),
        ),
        CheckCommand(
            "foundation_public_ci_window_boundary",
            (python_executable, "scripts/validate_foundation_public_ci_window_boundary.py"),
        ),
        CheckCommand(
            "foundation_privacy_data_boundary",
            (python_executable, "scripts/validate_foundation_privacy_data_boundary.py"),
        ),
        CheckCommand(
            "foundation_privacy_minimization_rehearsal_boundary",
            (python_executable, "scripts/validate_foundation_privacy_minimization_rehearsal_boundary.py"),
        ),
        CheckCommand(
            "foundation_funding_team_boundary",
            (python_executable, "scripts/validate_foundation_funding_team_boundary.py"),
        ),
        CheckCommand(
            "foundation_funding_team_obligation_rehearsal_boundary",
            (python_executable, "scripts/validate_foundation_funding_team_obligation_rehearsal_boundary.py"),
        ),
        CheckCommand(
            "foundation_community_network_boundary",
            (python_executable, "scripts/validate_foundation_community_network_boundary.py"),
        ),
        CheckCommand(
            "foundation_community_network_no_outreach_rehearsal_boundary",
            (python_executable, "scripts/validate_foundation_community_network_no_outreach_rehearsal_boundary.py"),
        ),
        CheckCommand("protocol_manifest", (python_executable, "scripts/validate_protocol_manifest.py")),
        CheckCommand(
            "simple_assistant_ui_boundary",
            (python_executable, "scripts/validate_simple_assistant_ui_boundary.py"),
        ),
        CheckCommand(
            "logic_governance_application",
            (python_executable, "scripts/validate_logic_governance_application.py"),
        ),
        CheckCommand(
            "life_meaning_governance",
            (python_executable, "scripts/validate_life_meaning_governance.py"),
        ),
        CheckCommand(
            "phi_gps_v3_platform_spec",
            (python_executable, "scripts/validate_phi_gps_v3_platform_spec.py"),
        ),
        CheckCommand(
            "governance_normalization_map",
            (python_executable, "scripts/validate_governance_normalization_map.py"),
        ),
        CheckCommand(
            "holistic_loop_reasoning_admission_binding",
            (python_executable, "scripts/validate_holistic_loop_reasoning_admission_binding.py"),
        ),
        CheckCommand(
            "public_repository_surface",
            (python_executable, "scripts/validate_public_repository_surface.py", "--local-only"),
        ),
        CheckCommand("proprietary_boundary", (python_executable, "scripts/validate_proprietary_boundary.py")),
        CheckCommand(
            "company_boundary_kernel",
            (python_executable, "scripts/validate_foundation_company_boundary_kernel.py"),
        ),
        CheckCommand("release_status", (python_executable, "scripts/validate_release_status.py")),
        CheckCommand(
            "workspace_governance_preflight_receipt_contract",
            (python_executable, "scripts/validate_workspace_governance_preflight_receipt_contract.py"),
        ),
        CheckCommand(
            "workspace_governance_preflight_receipt_example",
            (python_executable, "scripts/validate_workspace_governance_preflight_receipt.py"),
        ),
        CheckCommand(
            "workspace_governance_witness_contract",
            (python_executable, "scripts/validate_workspace_governance_witness.py"),
        ),
        CheckCommand(
            "workspace_governance_inventory_report",
            (python_executable, "scripts/report_workspace_governance_inventory.py"),
        ),
        CheckCommand(
            "workspace_governance_inventory_report_contract",
            (python_executable, "scripts/validate_workspace_governance_inventory_report_contract.py"),
        ),
        CheckCommand(
            "workspace_governance_integrity_report",
            (python_executable, "scripts/report_workspace_governance_integrity.py"),
        ),
        CheckCommand(
            "workspace_governance_integrity_report_contract",
            (python_executable, "scripts/validate_workspace_governance_integrity_report_contract.py"),
        ),
        CheckCommand(
            "governed_code_change_loop_sandbox_probe_example",
            (
                python_executable,
                "scripts/validate_governed_code_change_loop_sandbox_probe.py",
                "--probe",
                "docs/governed-code-change-loop-sandbox-probe-example.json",
            ),
        ),
        CheckCommand(
            "governed_code_change_loop_sandbox_readiness_runbook",
            (
                python_executable,
                "scripts/validate_governed_code_change_loop_sandbox_readiness_runbook.py",
            ),
        ),
        CheckCommand(
            "code_change_physics_packet",
            (python_executable, "scripts/validate_code_change_physics_packet.py"),
        ),
        CheckCommand(
            "search_decision_receipt",
            (python_executable, "scripts/validate_search_decision_receipt.py"),
        ),
        CheckCommand(
            "intelligence_coordination_episode_receipt",
            (
                python_executable,
                "scripts/validate_intelligence_coordination_episode_receipt.py",
            ),
        ),
        CheckCommand(
            "engineering_puzzle_universality_witness",
            (
                python_executable,
                "scripts/validate_engineering_puzzle_universality_witness.py",
                "--output",
                ".tmp/engineering-puzzle-universality-witness.json",
            ),
        ),
        CheckCommand(
            "mil_audit_runbook_operator_checklist",
            (
                python_executable,
                "scripts/validate_mil_audit_runbook_operator_checklist.py",
                "--checklist",
                "examples/mil_audit_runbook_operator_checklist.json",
                "--json",
            ),
        ),
        CheckCommand(
            "general_agent_promotion_handoff_packet",
            (
                python_executable,
                "scripts/validate_general_agent_promotion_handoff_packet.py",
                "--packet",
                "examples/general_agent_promotion_handoff_packet.json",
                "--json",
            ),
        ),
        CheckCommand(
            "general_agent_promotion_operator_checklist",
            (
                python_executable,
                "scripts/validate_general_agent_promotion_operator_checklist.py",
                "--checklist",
                "examples/general_agent_promotion_operator_checklist.json",
                "--json",
            ),
        ),
        CheckCommand(
            "general_agent_promotion_environment_bindings",
            (
                python_executable,
                "scripts/validate_general_agent_promotion_environment_bindings.py",
                "--contract",
                "examples/general_agent_promotion_environment_bindings.json",
                "--checklist",
                "examples/general_agent_promotion_operator_checklist.json",
                "--json",
            ),
        ),
        CheckCommand(
            "general_agent_promotion_handoff_preflight",
            (
                python_executable,
                "scripts/preflight_general_agent_promotion_handoff.py",
                "--output",
                ".tmp/general-agent-promotion-handoff-preflight.json",
                "--json",
            ),
        ),
        CheckCommand(
            "general_agent_promotion_closure_chain",
            (
                python_executable,
                "scripts/run_general_agent_promotion_closure_chain.py",
                "--output-dir",
                ".tmp/general-agent-promotion-closure-chain",
                "--adapter-evidence",
                "examples/capability_adapter_evidence_blocked.json",
                "--json",
                "--strict",
            ),
        ),
        CheckCommand(
            "finance_approval_live_handoff_closure_run",
            (
                python_executable,
                "scripts/run_finance_approval_live_handoff_closure.py",
                "--output",
                ".tmp/finance-approval-live-handoff-closure-run.json",
                "--json",
            ),
        ),
        CheckCommand(
            "finance_approval_live_handoff_chain",
            (
                python_executable,
                "scripts/run_finance_approval_live_handoff_chain.py",
                "--output-dir",
                ".tmp/finance-approval-live-handoff-chain",
                "--json",
            ),
        ),
        CheckCommand(
            "route_receipt_coverage",
            (python_executable, "scripts/validate_receipt_coverage.py", "--strict"),
        ),
        CheckCommand(
            "route_guard_chain_coverage",
            (python_executable, "scripts/validate_guard_chain_coverage.py", "--strict"),
        ),
        CheckCommand(
            "reflective_contract_guard",
            (python_executable, "scripts/validate_reflective_contracts.py"),
        ),
        CheckCommand(
            "doc_code_consistency",
            (python_executable, "scripts/validate_doc_code_consistency.py"),
        ),
        CheckCommand(
            "tenant_scope_coverage",
            (python_executable, "scripts/validate_tenant_scope_coverage.py"),
        ),
        CheckCommand(
            "persistence_tenant_guard_coverage",
            (python_executable, "scripts/validate_persistence_tenant_guard_coverage.py"),
        ),
        CheckCommand(
            "mcp_capability_manifest",
            (
                python_executable,
                "scripts/validate_mcp_capability_manifest.py",
                "--manifest",
                "examples/mcp_capability_manifest.json",
                "--json",
            ),
        ),
        CheckCommand(
            "capability_success_contract_registry",
            (python_executable, "scripts/validate_capability_success_contract_registry.py"),
        ),
        CheckCommand(
            "capability_debt_report",
            (python_executable, "scripts/validate_capability_debt_report.py"),
        ),
        CheckCommand(
            "capability_passports",
            (python_executable, "scripts/validate_capability_passports.py"),
        ),
        CheckCommand(
            "capability_passport_dashboard",
            (python_executable, "scripts/validate_capability_passport_dashboard.py"),
        ),
        CheckCommand(
            "capability_friction_control",
            (python_executable, "scripts/validate_capability_friction_control.py"),
        ),
        CheckCommand(
            "forge_write_spine_bridge",
            (python_executable, "scripts/validate_forge_write_spine_bridge.py"),
        ),
        CheckCommand(
            "forge_state_write_admission_packet",
            (python_executable, "scripts/validate_forge_state_write_admission_packet.py"),
        ),
        CheckCommand(
            "forge_live_runtime_readiness_gate",
            (python_executable, "scripts/validate_forge_live_runtime_readiness_gate.py"),
        ),
        CheckCommand(
            "forge_live_runtime_evidence_collection_packet",
            (
                python_executable,
                "scripts/validate_forge_live_runtime_evidence_collection_packet.py",
            ),
        ),
        CheckCommand(
            "forge_live_runtime_local_evidence_bundle",
            (python_executable, "scripts/validate_forge_live_runtime_local_evidence_bundle.py"),
        ),
        CheckCommand(
            "forge_live_runtime_evidence_acceptance_gate",
            (python_executable, "scripts/validate_forge_live_runtime_evidence_acceptance_gate.py"),
        ),
        CheckCommand(
            "forge_live_runtime_signed_evidence_receipt",
            (python_executable, "scripts/validate_forge_live_runtime_signed_evidence_receipt.py"),
        ),
        CheckCommand(
            "forge_live_runtime_probe_admission_packet",
            (python_executable, "scripts/validate_forge_live_runtime_probe_admission_packet.py"),
        ),
        CheckCommand(
            "forge_live_runtime_approved_probe_output_packet",
            (python_executable, "scripts/validate_forge_live_runtime_approved_probe_output_packet.py"),
        ),
        CheckCommand(
            "forge_live_runtime_post_probe_reconciliation_packet",
            (python_executable, "scripts/validate_forge_live_runtime_post_probe_reconciliation_packet.py"),
        ),
        CheckCommand(
            "forge_live_runtime_signed_receipt_population_gate",
            (python_executable, "scripts/validate_forge_live_runtime_signed_receipt_population_gate.py"),
        ),
        CheckCommand(
            "forge_live_runtime_evidence_chain_read_model",
            (python_executable, "scripts/validate_forge_live_runtime_evidence_chain_read_model.py"),
        ),
        CheckCommand(
            "forge_live_runtime_operator_evidence_request",
            (python_executable, "scripts/validate_forge_live_runtime_operator_evidence_request.py"),
        ),
        CheckCommand(
            "forge_live_runtime_operator_evidence_submission_packet",
            (python_executable, "scripts/validate_forge_live_runtime_operator_evidence_submission_packet.py"),
        ),
        CheckCommand(
            "forge_live_runtime_operator_evidence_verification_gate",
            (python_executable, "scripts/validate_forge_live_runtime_operator_evidence_verification_gate.py"),
        ),
        CheckCommand(
            "forge_live_runtime_operator_evidence_acceptance_handoff_packet",
            (
                python_executable,
                "scripts/validate_forge_live_runtime_operator_evidence_acceptance_handoff_packet.py",
            ),
        ),
        CheckCommand(
            "operator_plan_receipt_bundle_read_model",
            (python_executable, "scripts/validate_operator_plan_receipt_bundle_read_model.py"),
        ),
        CheckCommand(
            "worker_receipt_ledger_read_model",
            (python_executable, "scripts/validate_worker_receipt_ledger_read_model.py"),
        ),
        CheckCommand(
            "mcp_operator_checklist",
            (
                python_executable,
                "scripts/validate_mcp_operator_checklist.py",
                "--checklist",
                "examples/mcp_operator_handoff_checklist.json",
                "--json",
            ),
        ),
        CheckCommand(
            "public_naming_readiness",
            (python_executable, "scripts/validate_public_naming_readiness.py"),
        ),
        CheckCommand(
            "public_demo_surfaces",
            (
                python_executable,
                "scripts/validate_public_demo_surfaces.py",
                "--output",
                ".tmp/public-demo-surface-validation.json",
            ),
        ),
        CheckCommand(
            "snet_episode_replay",
            (
                python_executable,
                "scripts/validate_snet_episode_replay.py",
                "--episode",
                "examples/snet_episode_seed_dependency.json",
            ),
        ),
        CheckCommand(
            "strict_schema_validation",
            (python_executable, "scripts/validate_schemas.py", "--strict"),
        ),
        CheckCommand(
            "strict_artifact_validation",
            (python_executable, "scripts/validate_artifacts.py", "--strict"),
        ),
        CheckCommand(
            "terminal_closure_certificate",
            (
                python_executable,
                "scripts/validate_terminal_closure_certificate.py",
                "--json",
            ),
        ),
        CheckCommand(
            "universal_action_orchestration_contract",
            (python_executable, "scripts/validate_universal_action_orchestration.py"),
        ),
        CheckCommand(
            "universal_action_orchestration_validation_receipt_contract",
            (python_executable, "scripts/validate_universal_action_orchestration_receipt_contract.py"),
        ),
        CheckCommand(
            "universal_action_orchestration_validation_receipt_example",
            (python_executable, "scripts/validate_universal_action_orchestration_receipt.py"),
        ),
        CheckCommand(
            "universal_symbol_runtime_admission_policy",
            (python_executable, "scripts/validate_universal_symbol_runtime_admission_policy.py"),
        ),
        CheckCommand(
            "universal_symbol_runtime_admission_evidence_receipt",
            (python_executable, "scripts/validate_universal_symbol_runtime_admission_evidence_receipt.py"),
        ),
        CheckCommand(
            "universal_symbol_runtime_live_witness_input_receipt",
            (python_executable, "scripts/validate_universal_symbol_runtime_live_witness_input_receipt.py"),
        ),
        CheckCommand(
            "universal_symbol_lane_runtime_authority_evidence_receipt",
            (python_executable, "scripts/validate_universal_symbol_lane_runtime_authority_evidence_receipt.py"),
        ),
        CheckCommand(
            "universal_symbol_runtime_authority_witness",
            (python_executable, "scripts/validate_universal_symbol_runtime_authority_witness.py"),
        ),
        CheckCommand(
            "universal_symbol_runtime_authority_read_model",
            (python_executable, "scripts/validate_universal_symbol_runtime_authority_read_model.py"),
        ),
        CheckCommand(
            "universal_symbol_skill_runtime_authority_witness",
            (python_executable, "scripts/validate_universal_symbol_skill_runtime_authority_witness.py"),
        ),
        CheckCommand(
            "universal_symbol_adapter_receipt_persistence_policy",
            (python_executable, "scripts/validate_universal_symbol_adapter_receipt_persistence_policy.py"),
        ),
        CheckCommand(
            "universal_symbol_append_audit_witness",
            (python_executable, "scripts/validate_universal_symbol_append_audit_witness.py"),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_operator_approval_witness",
            (python_executable, "scripts/validate_universal_symbol_receipt_store_operator_approval_witness.py"),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_operator_identity_witness",
            (python_executable, "scripts/validate_universal_symbol_receipt_store_operator_identity_witness.py"),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_operator_approval_decision_witness",
            (
                python_executable,
                "scripts/validate_universal_symbol_receipt_store_operator_approval_decision_witness.py",
            ),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_operator_reapproval_expiry_witness",
            (
                python_executable,
                "scripts/validate_universal_symbol_receipt_store_operator_reapproval_expiry_witness.py",
            ),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_operator_revocation_witness",
            (python_executable, "scripts/validate_universal_symbol_receipt_store_operator_revocation_witness.py"),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_replacement_decision_receipt",
            (python_executable, "scripts/validate_universal_symbol_receipt_store_replacement_decision_receipt.py"),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness",
            (
                python_executable,
                "scripts/validate_universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness.py",
            ),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_reapproval_revocation_witness",
            (python_executable, "scripts/validate_universal_symbol_receipt_store_reapproval_revocation_witness.py"),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_lifecycle_evidence_receipt",
            (python_executable, "scripts/validate_universal_symbol_receipt_store_lifecycle_evidence_receipt.py"),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_lifecycle_audit_receipt",
            (python_executable, "scripts/validate_universal_symbol_receipt_store_lifecycle_audit_receipt.py"),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_tenant_scope_witness",
            (python_executable, "scripts/validate_universal_symbol_receipt_store_tenant_scope_witness.py"),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_writer_duty_scope_witness",
            (python_executable, "scripts/validate_universal_symbol_receipt_store_writer_duty_scope_witness.py"),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_path_confinement_witness",
            (python_executable, "scripts/validate_universal_symbol_receipt_store_path_confinement_witness.py"),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_write_path_idempotency_witness",
            (python_executable, "scripts/validate_universal_symbol_receipt_store_write_path_idempotency_witness.py"),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_durability_replay_witness",
            (python_executable, "scripts/validate_universal_symbol_receipt_store_durability_replay_witness.py"),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_recovery_witness",
            (python_executable, "scripts/validate_universal_symbol_receipt_store_recovery_witness.py"),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_writer_identity_witness",
            (python_executable, "scripts/validate_universal_symbol_receipt_store_writer_identity_witness.py"),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_writer_registration_witness",
            (python_executable, "scripts/validate_universal_symbol_receipt_store_writer_registration_witness.py"),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_path_custody_witness",
            (python_executable, "scripts/validate_universal_symbol_receipt_store_path_custody_witness.py"),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_write_path_witness",
            (python_executable, "scripts/validate_universal_symbol_receipt_store_write_path_witness.py"),
        ),
        CheckCommand(
            "universal_symbol_receipt_store_authority_witness",
            (python_executable, "scripts/validate_universal_symbol_receipt_store_authority_witness.py"),
        ),
        CheckCommand("universal_symbol_kernel", (python_executable, "scripts/validate_universal_symbol_kernel.py")),
        CheckCommand(
            "inceptadive_external_effect_adapter_readiness",
            (python_executable, "scripts/validate_inceptadive_external_effect_adapter_readiness.py"),
        ),
        CheckCommand("sdlc_artifact_validation", (python_executable, "scripts/validate_sdlc_artifact.py")),
        CheckCommand("sdlc_route_validation", (python_executable, "scripts/validate_sdlc_route.py")),
        CheckCommand("sdlc_state_machine_validation", (python_executable, "scripts/validate_sdlc_state_machine.py")),
        CheckCommand(
            "sdlc_release_readiness_validation",
            (python_executable, "scripts/validate_sdlc_release_readiness.py", "--strict"),
        ),
        CheckCommand(
            "sdlc_security_review_validation",
            (python_executable, "scripts/validate_sdlc_security_review.py", "--strict"),
        ),
        CheckCommand("sdlc_pr_enforcement_validation", (python_executable, "scripts/validate_sdlc_pr_enforcement.py")),
    )


def run_check(
    command: CheckCommand,
    workspace_root: Path = WORKSPACE_ROOT,
    timeout_seconds: float | None = None,
) -> CheckResult:
    """Run one governance check command from the workspace root."""

    if timeout_seconds is not None and timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive when provided")
    try:
        completed = run_command_process(command, workspace_root, timeout_seconds)
    except OSError as exc:
        return CheckResult(
            command.name,
            command.args,
            CHECK_EXCEPTION_RETURN_CODE,
            "",
            f"[EXCEPTION] {command.name} could not start: {exc}\n",
            termination_reason="exception",
        )
    if completed.timed_out:
        return CheckResult(
            command.name,
            command.args,
            TIMEOUT_RETURN_CODE,
            completed.stdout,
            completed.stderr,
            termination_reason="timeout",
        )
    return_code = int(completed.return_code)
    return CheckResult(
        command.name,
        command.args,
        return_code,
        completed.stdout,
        completed.stderr,
        termination_reason=_termination_reason(return_code),
        termination_signal=_termination_signal(return_code),
    )


def run_command_process(
    command: CheckCommand,
    workspace_root: Path = WORKSPACE_ROOT,
    timeout_seconds: float | None = None,
) -> ProcessExecution:
    """Run one command and terminate its process tree on timeout."""

    process = subprocess.Popen(
        command.args,
        cwd=workspace_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=os.name != "nt",
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        cleanup_stderr = terminate_process_tree(process.pid)
        stdout = _normalize_timeout_output(exc.stdout)
        stderr = _normalize_timeout_output(exc.stderr)
        try:
            remaining_stdout, remaining_stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            remaining_stdout = ""
            remaining_stderr = "[TIMEOUT-CLEANUP] process tree did not exit after termination request\n"
        stdout += _normalize_timeout_output(remaining_stdout)
        stderr += _normalize_timeout_output(remaining_stderr)
        if cleanup_stderr:
            if stderr and not stderr.endswith("\n"):
                stderr += "\n"
            stderr += cleanup_stderr
        if stderr and not stderr.endswith("\n"):
            stderr += "\n"
        stderr += f"[TIMEOUT] {command.name} exceeded {timeout_seconds} seconds: {' '.join(command.args)}\n"
        return ProcessExecution(TIMEOUT_RETURN_CODE, stdout, stderr, timed_out=True)
    return ProcessExecution(int(process.returncode), stdout, stderr)


def terminate_process_tree(pid: int) -> str:
    """Best-effort termination for a timed-out validator process tree."""

    if pid <= 0:
        return f"[TIMEOUT-CLEANUP] invalid process id for timeout cleanup: {pid}\n"
    if os.name == "nt":
        completed = subprocess.run(
            ("taskkill", "/PID", str(pid), "/T", "/F"),
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            return ""
        diagnostic = (completed.stdout or "") + (completed.stderr or "")
        diagnostic = diagnostic.strip() or f"taskkill exited with {completed.returncode}"
        return f"[TIMEOUT-CLEANUP] failed to terminate process tree {pid}: {diagnostic}\n"
    try:
        os.killpg(pid, signal.SIGTERM)
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if not _process_is_active(pid):
                return ""
            time.sleep(0.05)
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return ""
    except OSError as exc:
        return f"[TIMEOUT-CLEANUP] failed to terminate process tree {pid}: {exc}\n"
    return ""


def run_checks(
    commands: tuple[CheckCommand, ...],
    workspace_root: Path = WORKSPACE_ROOT,
    max_workers: int = 1,
    timeout_seconds: float | None = None,
    progress_stream: TextIO | None = None,
) -> tuple[CheckResult, ...]:
    """Run governance checks and preserve the declared result order."""

    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")
    if timeout_seconds is not None and timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive when provided")
    if max_workers == 1:
        results: list[CheckResult] = []
        total = len(commands)
        for index, command in enumerate(commands, start=1):
            _emit_progress(progress_stream, "RUN", index, total, command)
            result = run_check(command, workspace_root, timeout_seconds)
            _emit_progress(progress_stream, "PASS" if result.passed else "FAIL", index, total, command, result)
            results.append(result)
        return tuple(results)

    results_by_index: list[CheckResult | None] = [None] * len(commands)
    total = len(commands)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_by_index = {}
        for index, command in enumerate(commands):
            _emit_progress(progress_stream, "RUN", index + 1, total, command)
            future_by_index[executor.submit(run_check, command, workspace_root, timeout_seconds)] = index
        for future in as_completed(future_by_index):
            index = future_by_index[future]
            result = future.result()
            results_by_index[index] = result
            _emit_progress(
                progress_stream,
                "PASS" if result.passed else "FAIL",
                index + 1,
                total,
                commands[index],
                result,
            )
    return tuple(result for result in results_by_index if result is not None)


def run_checks_for_canonical_receipt_refresh(
    commands: tuple[CheckCommand, ...],
    receipt_path: Path,
    workspace_root: Path = WORKSPACE_ROOT,
    max_workers: int = 1,
    timeout_seconds: float | None = None,
    progress_stream: TextIO | None = None,
) -> tuple[CheckResult, ...]:
    """Run checks while safely refreshing the self-validating receipt example."""

    receipt_indexes = [
        index for index, command in enumerate(commands) if command.name == CANONICAL_PREFLIGHT_RECEIPT_EXAMPLE_NAME
    ]
    if len(receipt_indexes) != 1:
        raise ValueError("canonical receipt refresh requires exactly one receipt example check")

    receipt_index = receipt_indexes[0]
    receipt_command = commands[receipt_index]
    non_receipt_commands = tuple(
        command for command in commands if command.name != CANONICAL_PREFLIGHT_RECEIPT_EXAMPLE_NAME
    )
    non_receipt_results = run_checks(
        non_receipt_commands,
        workspace_root,
        max_workers=max_workers,
        timeout_seconds=timeout_seconds,
        progress_stream=progress_stream,
    )
    if not all(result.passed for result in non_receipt_results):
        placeholder_result = CheckResult(
            receipt_command.name,
            receipt_command.args,
            1,
            "",
            "STATUS: skipped\ncanonical receipt refresh skipped because prior checks failed\n",
        )
        return _insert_check_result(non_receipt_results, receipt_index, placeholder_result)

    provisional_result = CheckResult(receipt_command.name, receipt_command.args, 0, "STATUS: passed\n", "")
    provisional_results = _insert_check_result(non_receipt_results, receipt_index, provisional_result)
    write_receipt(build_receipt(provisional_results), receipt_path, workspace_root)

    _emit_progress(progress_stream, "RUN", receipt_index + 1, len(commands), receipt_command)
    receipt_result = run_check(receipt_command, workspace_root, timeout_seconds)
    _emit_progress(
        progress_stream,
        "PASS" if receipt_result.passed else "FAIL",
        receipt_index + 1,
        len(commands),
        receipt_command,
        receipt_result,
    )
    final_results = _insert_check_result(non_receipt_results, receipt_index, receipt_result)
    write_receipt(build_receipt(final_results), receipt_path, workspace_root)
    return final_results


def select_check_commands(
    commands: tuple[CheckCommand, ...],
    selected_names: tuple[str, ...] = (),
    shard_count: int = 1,
    shard_index: int = 0,
) -> tuple[CheckCommand, ...]:
    """Select a deterministic bounded subset of governance checks."""

    if shard_count < 1:
        raise ValueError("shard-count must be at least 1")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError("shard-index must be in [0, shard-count)")

    command_names = {command.name for command in commands}
    unknown_names = sorted(set(selected_names) - command_names)
    if unknown_names:
        raise ValueError(f"unknown check name: {', '.join(unknown_names)}")

    selected = (
        tuple(command for command in commands if command.name in set(selected_names))
        if selected_names
        else commands
    )
    sharded = tuple(command for index, command in enumerate(selected) if index % shard_count == shard_index)
    if not sharded:
        raise ValueError("selected check set is empty")
    return sharded


def requires_full_preflight_lock(selected_names: tuple[str, ...], shard_count: int) -> bool:
    """Return whether this run needs the workspace-level preflight lock."""

    return not selected_names and shard_count == 1


def allows_saved_canonical_receipt(selected_names: tuple[str, ...], shard_count: int) -> bool:
    """Return whether this run can persist a canonical preflight receipt."""

    return not selected_names and shard_count == 1


def is_canonical_receipt_refresh_path(receipt_path: Path, workspace_root: Path = WORKSPACE_ROOT) -> bool:
    """Return whether a receipt path targets the self-validating canonical example."""

    return resolve_receipt_path(receipt_path, workspace_root) == CANONICAL_PREFLIGHT_RECEIPT_EXAMPLE_PATH.resolve()


@contextmanager
def maybe_full_preflight_lock(lock_required: bool, lock_path: Path = DEFAULT_PREFLIGHT_LOCK_PATH):
    """Acquire the full-preflight lock only when a full preflight is requested."""

    if not lock_required:
        yield
        return
    with PreflightLock(lock_path):
        yield


def render_results(results: tuple[CheckResult, ...], output_stream: TextIO, error_stream: TextIO) -> None:
    """Render governance check results with command witness output."""

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        output_stream.write(f"[{status}] {result.name}: {' '.join(result.args)}\n")
        if result.stdout:
            output_stream.write(result.stdout)
            if not result.stdout.endswith("\n"):
                output_stream.write("\n")
        if result.stderr:
            error_stream.write(result.stderr)
            if not result.stderr.endswith("\n"):
                error_stream.write("\n")


def _emit_progress(
    progress_stream: TextIO | None,
    status: str,
    index: int,
    total: int,
    command: CheckCommand,
    result: CheckResult | None = None,
) -> None:
    """Emit a non-JSON progress witness for long-running preflights."""

    if progress_stream is None:
        return
    result_suffix = "" if result is None else f" return_code={result.return_code} termination={result.termination_reason}"
    progress_stream.write(f"[{status}] preflight {index}/{total} {command.name}{result_suffix}\n")
    progress_stream.flush()


def build_receipt(results: tuple[CheckResult, ...], generated_at_epoch: float | None = None) -> dict[str, object]:
    """Build a machine-readable governance preflight receipt."""

    emitted_at = time.time() if generated_at_epoch is None else generated_at_epoch
    if isinstance(emitted_at, bool) or not isinstance(emitted_at, (int, float)) or emitted_at <= 0:
        raise ValueError("generated_at_epoch must be a positive epoch timestamp")
    checks: list[dict[str, object]] = []
    for result in results:
        payload = asdict(result)
        payload["args"] = list(result.args)
        payload["passed"] = result.passed
        checks.append(payload)
    return {
        "receipt_id": "workspace_governance_preflight_receipt",
        "terminal_closure_required": True,
        "receipt_is_not_terminal_closure": True,
        "status": "passed" if all(result.passed for result in results) else "failed",
        "generated_at_epoch": emitted_at,
        "check_count": len(results),
        "checks": checks,
    }


def _insert_check_result(
    non_receipt_results: tuple[CheckResult, ...],
    receipt_index: int,
    receipt_result: CheckResult,
) -> tuple[CheckResult, ...]:
    """Insert the receipt example result back into the canonical result order."""

    ordered_results = list(non_receipt_results)
    ordered_results.insert(receipt_index, receipt_result)
    return tuple(ordered_results)


def resolve_receipt_path(receipt_path: Path, workspace_root: Path = WORKSPACE_ROOT) -> Path:
    """Resolve a workspace-local JSON receipt path and reject path escapes."""

    if receipt_path.suffix.lower() != ".json":
        raise ValueError("receipt path must use .json suffix")
    resolved_root = workspace_root.resolve()
    resolved_path = (workspace_root / receipt_path).resolve() if not receipt_path.is_absolute() else receipt_path.resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError(f"receipt path must stay under workspace root: {receipt_path}")
    return resolved_path


def write_receipt(
    receipt: dict[str, object],
    receipt_path: Path,
    workspace_root: Path = WORKSPACE_ROOT,
) -> Path:
    """Persist one machine-readable receipt under the workspace root."""

    resolved_path = resolve_receipt_path(receipt_path, workspace_root)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return resolved_path


def main(argv: list[str] | None = None) -> int:
    """Run the workspace governance preflight."""

    parser = argparse.ArgumentParser(description="Run repository-local workspace governance checks.")
    parser.add_argument("--check", action="append", default=[], help="run only the named check; repeatable")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable preflight receipt")
    parser.add_argument("--receipt-path", type=Path, help="write the JSON receipt to this workspace-local path")
    parser.add_argument(
        "--max-workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help=f"maximum parallel check workers; use 1 for sequential debugging (default: {DEFAULT_MAX_WORKERS})",
    )
    parser.add_argument("--per-check-timeout-seconds", type=float, help="timeout for each check")
    parser.add_argument("--shard-count", type=int, default=1, help="number of deterministic shards")
    parser.add_argument("--shard-index", type=int, default=0, help="zero-based shard index")
    args = parser.parse_args(argv)

    selected_names = tuple(str(name) for name in args.check)
    shard_count = int(args.shard_count)
    shard_index = int(args.shard_index)
    try:
        commands = select_check_commands(
            build_check_commands(),
            selected_names=selected_names,
            shard_count=shard_count,
            shard_index=shard_index,
        )
    except ValueError as exc:
        sys.stderr.write(f"[FAIL] check-selection: {exc}\nSTATUS: failed\n")
        return 1
    if args.receipt_path is not None and not allows_saved_canonical_receipt(selected_names, shard_count):
        sys.stderr.write(
            "[FAIL] receipt-path: saved workspace governance preflight receipts require "
            "a full unsharded preflight run\nSTATUS: failed\n"
        )
        return 1

    try:
        canonical_receipt_refresh = (
            args.receipt_path is not None and is_canonical_receipt_refresh_path(args.receipt_path)
        )
        with maybe_full_preflight_lock(requires_full_preflight_lock(selected_names, shard_count)):
            if canonical_receipt_refresh:
                results = run_checks_for_canonical_receipt_refresh(
                    commands,
                    args.receipt_path,
                    WORKSPACE_ROOT,
                    max_workers=int(args.max_workers),
                    timeout_seconds=args.per_check_timeout_seconds,
                    progress_stream=sys.stderr,
                )
            else:
                results = run_checks(
                    commands,
                    WORKSPACE_ROOT,
                    max_workers=int(args.max_workers),
                    timeout_seconds=args.per_check_timeout_seconds,
                    progress_stream=sys.stderr,
                )
    except PreflightLockError as exc:
        sys.stderr.write(f"[FAIL] preflight-lock: {exc}\nSTATUS: failed\n")
        return PREFLIGHT_LOCK_RETURN_CODE
    except ValueError as exc:
        sys.stderr.write(f"[FAIL] check-execution: {exc}\nSTATUS: failed\n")
        return 1

    receipt = build_receipt(results)
    if args.receipt_path is not None:
        try:
            write_receipt(receipt, args.receipt_path)
        except ValueError as exc:
            sys.stderr.write(f"[FAIL] receipt-path: {exc}\nSTATUS: failed\n")
            return 1

    if args.json:
        sys.stdout.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    else:
        render_results(results, sys.stdout, sys.stderr)
        sys.stdout.write(f"STATUS: {receipt['status']}\n")
    return 0 if receipt["status"] == "passed" else 1


def _normalize_timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _termination_reason(return_code: int) -> str:
    if return_code < 0:
        return "terminated"
    return "completed"


def _termination_signal(return_code: int) -> int | None:
    if return_code < 0:
        return abs(return_code)
    return None


def _process_is_active(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        completed = subprocess.run(
            ("tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"),
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return True
        return f'"{pid}"' in completed.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_preflight_lock_payload(lock_path: Path) -> dict[str, object] | None:
    try:
        raw_payload = lock_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise PreflightLockError(f"cannot inspect existing preflight lock {lock_path}: {exc}") from exc
    try:
        parsed_payload = json.loads(raw_payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return parsed_payload if isinstance(parsed_payload, dict) else {}


def _preflight_lock_payload_is_stale(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return True
    if payload.get("lock_id") != PREFLIGHT_LOCK_ID:
        return True
    pid = payload.get("pid")
    created_at_epoch = payload.get("created_at_epoch")
    if isinstance(pid, bool) or not isinstance(pid, int):
        return True
    if isinstance(created_at_epoch, bool) or not isinstance(created_at_epoch, (int, float)):
        return True
    return not _process_is_active(pid)


def _remove_stale_preflight_lock(lock_path: Path) -> bool:
    observed_payload = _read_preflight_lock_payload(lock_path)
    if not _preflight_lock_payload_is_stale(observed_payload):
        return False
    if _read_preflight_lock_payload(lock_path) != observed_payload:
        return False
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise PreflightLockError(f"cannot remove stale preflight lock {lock_path}: {exc}") from exc
    return True


if __name__ == "__main__":
    raise SystemExit(main())
