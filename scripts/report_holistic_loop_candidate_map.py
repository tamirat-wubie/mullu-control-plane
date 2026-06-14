#!/usr/bin/env python3
"""Report candidate surfaces for future holistic loop registration.

Purpose: expose a read-only candidate map for existing loop-like surfaces that
may later be admitted into the holistic loop registry.
Governance scope: loop candidate discovery, non-registration boundary,
evidence-backed source refs, and terminal-closure separation.
Dependencies: holistic loop registry and repository-local candidate surfaces.
Invariants:
  - Candidate reporting is read-only and deterministic.
  - Candidate reporting does not register loops or execute loop behavior.
  - Unregistered candidates remain blocked until an explicit registration decision.
  - Registered candidates are reported as already admitted, not terminally closed.
  - The report is not a terminal closure certificate.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
MCOI_ROOT = WORKSPACE_ROOT / "mcoi"
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from mcoi_runtime.core.holistic_loop_registry import build_default_loop_registry  # noqa: E402


REPORT_ID = "holistic_loop_candidate_map"
REPORT_VERSION = "holistic_loop_candidate_map.v1"
NOT_REGISTERED_BLOCKER = "not_registered"
REGISTRATION_DECISION_BLOCKER = "requires_operator_registration_decision"


@dataclass(frozen=True, slots=True)
class LoopCandidate:
    """Candidate loop surface tracked before or after registry admission."""

    candidate_id: str
    name: str
    purpose: str
    owner: str
    risk_class: str
    existing_surfaces: tuple[str, ...]
    proposed_required_authority: tuple[str, ...]
    proposed_required_evidence: tuple[str, ...]
    proposed_closure_conditions: tuple[str, ...]
    proposed_rollback_policy: str
    proposed_learning_policy: str

    def to_json_dict(self, registered_loop_ids: set[str]) -> dict[str, Any]:
        """Return the read-only candidate projection."""

        registered = self.candidate_id in registered_loop_ids
        blockers = () if registered else (NOT_REGISTERED_BLOCKER, REGISTRATION_DECISION_BLOCKER)
        return {
            "candidate_id": self.candidate_id,
            "name": self.name,
            "purpose": self.purpose,
            "owner": self.owner,
            "risk_class": self.risk_class,
            "existing_surfaces": list(self.existing_surfaces),
            "proposed_required_authority": list(self.proposed_required_authority),
            "proposed_required_evidence": list(self.proposed_required_evidence),
            "proposed_closure_conditions": list(self.proposed_closure_conditions),
            "proposed_rollback_policy": self.proposed_rollback_policy,
            "proposed_learning_policy": self.proposed_learning_policy,
            "registered": registered,
            "admission_status": "registered" if registered else "blocked",
            "admission_blockers": list(blockers),
            "next_action": (
                "already_registered"
                if registered
                else "prepare_manifest_for_extension_admission"
            ),
            "read_only": True,
            "mutation_route": False,
            "terminal_closure": False,
            "behavior_rewrite": False,
        }


def candidate_loop_catalog() -> tuple[LoopCandidate, ...]:
    """Return deterministic candidate surfaces for later admission review."""

    return (
        LoopCandidate(
            candidate_id="audit_proof_verification_loop",
            name="Audit Proof Verification Loop",
            purpose="Describe audit, proof, trust-ledger anchor, and verification evidence.",
            owner="proof_governance",
            risk_class="proof_integrity",
            existing_surfaces=(
                "schemas/audit_verification_endpoint.schema.json",
                "schemas/proof_verification_endpoint.schema.json",
                "schemas/trust_ledger_anchor_verification_report.schema.json",
                "scripts/submit_trust_ledger_anchor_export.py",
                "tests/test_gateway/test_trust_ledger_anchor_receipt.py",
            ),
            proposed_required_authority=("proof_verifier_ref",),
            proposed_required_evidence=(
                "audit_verification_passed",
                "proof_verification_passed",
                "trust_ledger_anchor_verified",
            ),
            proposed_closure_conditions=(
                "audit_and_proof_lanes_consistent",
                "anchor_verification_report_valid",
            ),
            proposed_rollback_policy="invalidate_proof_claim_and_retain_failed_anchor",
            proposed_learning_policy="promote proof gaps into coverage matrix witnesses",
        ),
        LoopCandidate(
            candidate_id="authority_obligation_loop",
            name="Authority Obligation Loop",
            purpose="Describe overdue authority obligation detection, satisfaction, and closure evidence.",
            owner="governance",
            risk_class="authority_debt",
            existing_surfaces=(
                "scripts/satisfy_overdue_authority_obligations.py",
                "tests/test_satisfy_overdue_authority_obligations.py",
                "tests/test_gateway/test_authority_obligation_mesh.py",
            ),
            proposed_required_authority=("authority_operator_ref",),
            proposed_required_evidence=(
                "authority_obligation_inventory_current",
                "overdue_obligation_resolution_receipt",
                "authority_mesh_validator_passed",
            ),
            proposed_closure_conditions=(
                "no_overdue_authority_debt",
                "satisfaction_receipts_valid",
            ),
            proposed_rollback_policy="retain_obligation_debt_and_reopen_authority_review",
            proposed_learning_policy="promote repeated authority debt into preflight checks",
        ),
        LoopCandidate(
            candidate_id="governed_symbolic_loop",
            name="Governed Symbolic Loop",
            purpose=(
                "Describe canonical symbolic episode phases, action classes, deterministic "
                "kernel boundaries, effect-bearing guards, verification, rollback, and "
                "post-verification learning."
            ),
            owner="platform_governance",
            risk_class="platform_orchestration",
            existing_surfaces=(
                "schemas/governed_symbolic_loop_contract.schema.json",
                "examples/governed_symbolic_loop_contract.foundation.json",
                "examples/sdlc/requirement_governed_symbolic_loop_20260614.json",
                "examples/sdlc/design_governed_symbolic_loop_20260614.json",
                "scripts/validate_governed_symbolic_loop_contract.py",
                "tests/test_validate_governed_symbolic_loop_contract.py",
            ),
            proposed_required_authority=(
                "uao_policy_ref",
                "phi_gov_authority_ref",
                "life_meaning_judgment_ref",
                "operator_registration_decision_ref",
            ),
            proposed_required_evidence=(
                "problem_star_compilation_receipt",
                "action_classification_receipt",
                "capability_admission_receipt",
                "verification_receipt",
                "rollback_or_recovery_handoff_receipt",
                "learning_admission_receipt",
            ),
            proposed_closure_conditions=(
                "canonical_episode_phases_preserved",
                "deterministic_kernel_boundaries_preserved",
                "runtime_authority_denials_preserved",
                "post_verification_learning_preserved",
            ),
            proposed_rollback_policy="remove_registry_admission_and_restore_read_only_contract",
            proposed_learning_policy=(
                "promote loop guard regressions into validators only after verified evidence"
            ),
        ),
        LoopCandidate(
            candidate_id="universal_action_orchestration_loop",
            name="Universal Action Orchestration Loop",
            purpose="Describe effect-bearing action admission, receipt, replay, and no-bypass evidence.",
            owner="action_governance",
            risk_class="effect_bearing_action",
            existing_surfaces=(
                "schemas/universal_action_orchestration.schema.json",
                "schemas/universal_action_orchestration_validation_receipt.schema.json",
                "scripts/validate_universal_action_orchestration.py",
                "tests/test_validate_universal_action_orchestration.py",
            ),
            proposed_required_authority=("uao_policy_ref",),
            proposed_required_evidence=(
                "action_admission_receipt_valid",
                "no_bypass_detector_passed",
                "replay_or_rollback_ref_present",
            ),
            proposed_closure_conditions=(
                "effect_reconciled",
                "receipt_and_memory_deltas_recorded",
            ),
            proposed_rollback_policy="execute_recovery_handoff_or_mark_accepted_risk",
            proposed_learning_policy="promote rejected action causes into policy rules",
        ),
        LoopCandidate(
            candidate_id="workflow_execution_loop",
            name="Workflow Execution Loop",
            purpose="Describe workflow descriptor, run, orchestration, and replay evidence.",
            owner="workflow_governance",
            risk_class="workflow_execution",
            existing_surfaces=(
                "docs/21_workflow_runtime.md",
                "schemas/workflow.schema.json",
                "schemas/workflow_run.schema.json",
                "tests/test_gateway/test_workflow_orchestration.py",
            ),
            proposed_required_authority=("workflow_operator_ref",),
            proposed_required_evidence=(
                "workflow_descriptor_valid",
                "workflow_run_receipt_valid",
                "workflow_replay_boundary_passed",
            ),
            proposed_closure_conditions=(
                "workflow_run_reconciled",
                "workflow_wait_states_closed_or_blocked",
            ),
            proposed_rollback_policy="halt_workflow_and_retain_replay_cursor",
            proposed_learning_policy="promote workflow failures into descriptor validation rules",
        ),
    )


def build_candidate_map() -> dict[str, Any]:
    """Build the read-only holistic loop candidate map."""

    registered_loop_ids = set(build_default_loop_registry().manifests)
    candidates = [
        candidate.to_json_dict(registered_loop_ids)
        for candidate in candidate_loop_catalog()
    ]
    blocked_count = sum(1 for candidate in candidates if candidate["admission_status"] == "blocked")
    return {
        "report_id": REPORT_ID,
        "report_version": REPORT_VERSION,
        "status": "blocked" if blocked_count else "verified",
        "candidate_count": len(candidates),
        "registered_candidate_count": sum(1 for candidate in candidates if candidate["registered"]),
        "blocked_candidate_count": blocked_count,
        "read_only": True,
        "mutation_route": False,
        "report_is_not_terminal_closure": True,
        "terminal_closure_required": True,
        "candidates": candidates,
    }


def validate_candidate_map(report: dict[str, Any] | None = None) -> list[str]:
    """Return validation errors for the candidate map."""

    candidate_map = report or build_candidate_map()
    errors: list[str] = []
    if candidate_map.get("report_id") != REPORT_ID:
        errors.append("candidate map report_id is invalid")
    if candidate_map.get("report_version") != REPORT_VERSION:
        errors.append("candidate map report_version is invalid")
    if candidate_map.get("read_only") is not True:
        errors.append("candidate map must be read-only")
    if candidate_map.get("mutation_route") is not False:
        errors.append("candidate map must not expose a mutation route")
    if candidate_map.get("report_is_not_terminal_closure") is not True:
        errors.append("candidate map must not be terminal closure")
    if candidate_map.get("terminal_closure_required") is not True:
        errors.append("candidate map must require terminal closure")
    candidates = candidate_map.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return [*errors, "candidate map must include candidates"]
    registered_loop_ids = set(build_default_loop_registry().manifests)
    candidate_ids: list[str] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            errors.append(f"candidate {index} must be an object")
            continue
        candidate_id = str(candidate.get("candidate_id", "")).strip()
        candidate_ids.append(candidate_id)
        for field_name in (
            "name",
            "purpose",
            "owner",
            "risk_class",
            "proposed_rollback_policy",
            "proposed_learning_policy",
        ):
            if not str(candidate.get(field_name, "")).strip():
                errors.append(f"candidate {candidate_id} missing {field_name}")
        for field_name in (
            "existing_surfaces",
            "proposed_required_authority",
            "proposed_required_evidence",
            "proposed_closure_conditions",
        ):
            value = candidate.get(field_name)
            if not isinstance(value, list) or not value:
                errors.append(f"candidate {candidate_id} {field_name} must be a non-empty list")
        admission_blockers = candidate.get("admission_blockers")
        if not isinstance(admission_blockers, list):
            errors.append(f"candidate {candidate_id} admission_blockers must be a list")
        for surface in candidate.get("existing_surfaces", []):
            if not isinstance(surface, str) or not surface.strip():
                errors.append(f"candidate {candidate_id} has invalid surface ref")
                continue
            if not (WORKSPACE_ROOT / surface).exists():
                errors.append(f"candidate {candidate_id} missing surface: {surface}")
        expected_registered = candidate_id in registered_loop_ids
        if candidate.get("registered") is not expected_registered:
            errors.append(f"candidate {candidate_id} registered state must match default registry")
        if expected_registered:
            if candidate.get("admission_status") != "registered":
                errors.append(f"candidate {candidate_id} must report registered admission status")
            if candidate.get("admission_blockers") != []:
                errors.append(f"candidate {candidate_id} registered admission_blockers must be empty")
            if candidate.get("next_action") != "already_registered":
                errors.append(f"candidate {candidate_id} next_action must be already_registered")
        else:
            if candidate.get("admission_status") != "blocked":
                errors.append(f"candidate {candidate_id} must remain blocked until registration")
            if NOT_REGISTERED_BLOCKER not in candidate.get("admission_blockers", []):
                errors.append(f"candidate {candidate_id} missing not_registered blocker")
            if REGISTRATION_DECISION_BLOCKER not in candidate.get("admission_blockers", []):
                errors.append(f"candidate {candidate_id} missing registration decision blocker")
        for field_name, expected in (
            ("read_only", True),
            ("mutation_route", False),
            ("terminal_closure", False),
            ("behavior_rewrite", False),
        ):
            if candidate.get(field_name) is not expected:
                errors.append(f"candidate {candidate_id} {field_name} must be {expected}")
    if candidate_ids != sorted(candidate_ids):
        errors.append("candidate ids must be deterministic and sorted")
    if len(candidate_ids) != len(set(candidate_ids)):
        errors.append("candidate ids must be unique")
    if candidate_map.get("candidate_count") != len(candidates):
        errors.append("candidate_count must match candidates")
    registered_count = sum(
        1 for candidate in candidates if isinstance(candidate, dict) and candidate.get("registered") is True
    )
    blocked_count = sum(
        1 for candidate in candidates if isinstance(candidate, dict) and candidate.get("admission_status") == "blocked"
    )
    if candidate_map.get("registered_candidate_count") != registered_count:
        errors.append("registered_candidate_count must match registered candidates")
    if candidate_map.get("blocked_candidate_count") != blocked_count:
        errors.append("blocked_candidate_count must match blocked candidates")
    return errors


def render_candidate_map(report: dict[str, Any], output_stream: TextIO) -> None:
    """Render a short candidate map summary."""

    output_stream.write(
        "STATUS: {status}; candidates={candidate_count}; blocked={blocked_candidate_count}\n".format(
            **report
        )
    )
    for candidate in report["candidates"]:
        output_stream.write(
            "[{status}] {candidate_id}: surfaces={surface_count}; next={next_action}\n".format(
                status=candidate["admission_status"],
                candidate_id=candidate["candidate_id"],
                surface_count=len(candidate["existing_surfaces"]),
                next_action=candidate["next_action"],
            )
        )


def main(argv: list[str] | None = None) -> int:
    """Report and validate candidate loop surfaces."""

    parser = argparse.ArgumentParser(description="Report holistic loop candidate map.")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    report = build_candidate_map()
    errors = validate_candidate_map(report)
    if errors:
        for error in errors:
            sys.stderr.write(f"[BLOCKED] holistic-loop-candidate-map: {error}\n")
        sys.stderr.write("STATUS: blocked\n")
        return 1
    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    else:
        render_candidate_map(report, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
