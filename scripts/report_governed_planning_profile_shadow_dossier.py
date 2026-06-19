#!/usr/bin/env python3
"""Report GovernedPlanningProfile shadow admission coverage.

Purpose: build a deterministic, read-only dossier of representative gateway
planning scenarios projected through the GovernedPlanningProfile admission
adapter.
Governance scope: OCE scenario completeness, RAG source-to-profile binding,
CDCV plan/simulation/report traceability, CQTE no-effect constraints, UWMA
evidence anchoring, SRCA bounded scenario enumeration, and PRS validation.
Dependencies: gateway goal compiler, causal simulator, governed planning
profile adapter, world-state projection, and canonical hashing.
Invariants:
  - The dossier is read-only and deterministic.
  - The dossier does not execute, dispatch, register, replan, promote, or close.
  - Every scenario remains AwaitingEvidence until separate promotion evidence
    exists.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from gateway.causal_simulator import CausalSimulator  # noqa: E402
from gateway.command_spine import canonical_hash  # noqa: E402
from gateway.goal_compiler import GoalCompiler  # noqa: E402
from gateway.governed_planning_profile_adapter import (  # noqa: E402
    PROFILE_ID,
    build_governed_planning_profile_admission_report,
)
from gateway.world_state import WorldState  # noqa: E402


DOSSIER_VERSION = "governed_planning_profile_shadow_dossier.v1"
GENERATED_AT = "2026-06-19T00:00:00Z"
TENANT_ID = "tenant-1"
IDENTITY_ID = "identity-1"
EXPECTED_PLAN_CLASSES = (
    "uncompiled_conversation",
    "read_only_search",
    "compound_search_notification",
    "high_risk_payment",
    "world_contradiction_search",
)


@dataclass(frozen=True, slots=True)
class ShadowScenario:
    """One deterministic local scenario for shadow admission reporting."""

    scenario_id: str
    plan_class: str
    message: str
    world_state_mode: str
    open_contradiction_count: int = 0


SCENARIOS = (
    ShadowScenario(
        scenario_id="scenario-uncompiled-conversation",
        plan_class="uncompiled_conversation",
        message="hello there",
        world_state_mode="none",
    ),
    ShadowScenario(
        scenario_id="scenario-read-only-search",
        plan_class="read_only_search",
        message="search knowledge docs",
        world_state_mode="bound",
    ),
    ShadowScenario(
        scenario_id="scenario-compound-search-notification",
        plan_class="compound_search_notification",
        message="search knowledge docs and send message to team",
        world_state_mode="bound",
    ),
    ShadowScenario(
        scenario_id="scenario-high-risk-payment",
        plan_class="high_risk_payment",
        message='/run financial.send_payment {"amount": "2500", "recipient": "vendor-a"}',
        world_state_mode="bound",
    ),
    ShadowScenario(
        scenario_id="scenario-world-contradiction-search",
        plan_class="world_contradiction_search",
        message="search knowledge docs",
        world_state_mode="open_contradiction",
        open_contradiction_count=1,
    ),
)


def build_shadow_dossier() -> dict[str, Any]:
    """Build the deterministic no-effect planning-profile shadow dossier."""

    compiler = GoalCompiler()
    simulator = CausalSimulator()
    scenario_summaries: list[dict[str, Any]] = []
    admission_reports: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        world_state = _world_state(scenario)
        compiled_plan = compiler.compile(
            message=scenario.message,
            tenant_id=TENANT_ID,
            identity_id=IDENTITY_ID,
            world_state=world_state,
        )
        simulation_receipt = simulator.simulate(compiled_plan, world_state=world_state)
        admission_report = build_governed_planning_profile_admission_report(
            compiled_plan=compiled_plan,
            simulation_receipt=simulation_receipt,
        )
        report_payload = _json_safe(admission_report.to_dict())
        admission_reports.append(report_payload)
        scenario_summaries.append({
            "scenario_id": scenario.scenario_id,
            "plan_class": scenario.plan_class,
            "message_hash": canonical_hash({"message": scenario.message}),
            "world_state_mode": scenario.world_state_mode,
            "source_plan_id": admission_report.source_plan_id,
            "simulation_receipt_id": admission_report.simulation_receipt_id,
            "admission_report_id": admission_report.report_id,
            "admission_decision": admission_report.admission_decision,
            "shadow_parity_status": admission_report.shadow_parity_status,
            "solver_outcome": admission_report.solver_outcome,
            "risk_tier": admission_report.projection.risk_tier,
            "step_count": admission_report.projection.step_count,
            "promotion_blocker_count": len(admission_report.promotion_blockers),
            "shadow_mismatch_count": len(admission_report.shadow_mismatches),
            "required_control_count": admission_report.projection.simulation_required_control_count,
            "failure_mode_count": admission_report.projection.simulation_failure_mode_count,
            "execution_allowed": admission_report.projection.execution_allowed,
            "dispatch_allowed": admission_report.projection.dispatch_allowed,
            "terminal_closure_allowed": admission_report.projection.terminal_closure_allowed,
            "success_claim_allowed": admission_report.projection.success_claim_allowed,
        })

    plan_classes_covered = tuple(sorted({summary["plan_class"] for summary in scenario_summaries}))
    missing_plan_classes = tuple(
        plan_class for plan_class in EXPECTED_PLAN_CLASSES if plan_class not in plan_classes_covered
    )
    blocker_count = sum(summary["promotion_blocker_count"] for summary in scenario_summaries)
    mismatch_count = sum(summary["shadow_mismatch_count"] for summary in scenario_summaries)
    blocked_report_count = sum(1 for report in admission_reports if report["admission_decision"] == "blocked")
    shadow_parity_ready_count = sum(
        1 for report in admission_reports if report["admission_decision"] == "shadow_parity_ready"
    )
    closure_conditions = {
        "all_expected_plan_classes_covered": not missing_plan_classes,
        "all_reports_read_only": all(report["projection"]["read_only"] is True for report in admission_reports),
        "no_execution_authority": all(
            report["projection"]["execution_allowed"] is False
            and report["projection"]["dispatch_allowed"] is False
            and report["projection"]["runtime_replanning_enabled"] is False
            for report in admission_reports
        ),
        "no_terminal_closure": all(
            report["projection"]["terminal_closure_allowed"] is False
            and report["projection"]["success_claim_allowed"] is False
            for report in admission_reports
        ),
        "all_reports_awaiting_evidence": all(
            report["solver_outcome"] == "AwaitingEvidence" for report in admission_reports
        ),
        "no_shadow_mismatches": mismatch_count == 0,
    }
    dossier_status = "verified" if all(closure_conditions.values()) else "blocked"
    payload = {
        "dossier_id": "pending",
        "dossier_version": DOSSIER_VERSION,
        "profile_id": PROFILE_ID,
        "generated_at": GENERATED_AT,
        "status": dossier_status,
        "solver_outcome": "AwaitingEvidence",
        "read_only": True,
        "mutation_route": False,
        "runtime_behavior_change": False,
        "execution_allowed": False,
        "dispatch_allowed": False,
        "runtime_replanning_enabled": False,
        "terminal_closure": False,
        "success_claim_allowed": False,
        "scenario_count": len(scenario_summaries),
        "report_count": len(admission_reports),
        "blocked_report_count": blocked_report_count,
        "shadow_parity_ready_count": shadow_parity_ready_count,
        "promotion_blocker_count": blocker_count,
        "shadow_mismatch_count": mismatch_count,
        "expected_plan_classes": list(EXPECTED_PLAN_CLASSES),
        "plan_classes_covered": list(plan_classes_covered),
        "missing_plan_classes": list(missing_plan_classes),
        "scenarios": scenario_summaries,
        "admission_reports": admission_reports,
        "closure_conditions": closure_conditions,
        "evidence_refs": [
            "scripts/report_governed_planning_profile_shadow_dossier.py",
            "gateway/governed_planning_profile_adapter.py",
            "schemas/governed_planning_profile_shadow_dossier.schema.json",
            "schemas/governed_planning_profile_admission_report.schema.json",
            "tests/test_report_governed_planning_profile_shadow_dossier.py",
        ],
        "next_action": "collect operator shadow-pilot evidence before runtime promotion",
        "dossier_hash": "",
    }
    dossier_hash = canonical_hash(payload)
    payload["dossier_id"] = f"governed-planning-profile-shadow-dossier-{dossier_hash[:16]}"
    payload["dossier_hash"] = dossier_hash
    return payload


def validate_shadow_dossier(dossier: dict[str, Any] | None = None) -> list[str]:
    """Return structural validation errors for the shadow dossier."""

    current = dossier or build_shadow_dossier()
    errors: list[str] = []
    if current.get("dossier_version") != DOSSIER_VERSION:
        errors.append("shadow dossier version is invalid")
    for field_name, expected in (
        ("read_only", True),
        ("mutation_route", False),
        ("runtime_behavior_change", False),
        ("execution_allowed", False),
        ("dispatch_allowed", False),
        ("runtime_replanning_enabled", False),
        ("terminal_closure", False),
        ("success_claim_allowed", False),
    ):
        if current.get(field_name) is not expected:
            errors.append(f"shadow dossier {field_name} must be {expected}")
    scenarios = current.get("scenarios")
    reports = current.get("admission_reports")
    if not isinstance(scenarios, list) or not scenarios:
        errors.append("shadow dossier scenarios must be a non-empty list")
    if not isinstance(reports, list) or not reports:
        errors.append("shadow dossier admission_reports must be a non-empty list")
    if isinstance(scenarios, list) and current.get("scenario_count") != len(scenarios):
        errors.append("shadow dossier scenario_count must match scenarios")
    if isinstance(reports, list) and current.get("report_count") != len(reports):
        errors.append("shadow dossier report_count must match admission_reports")
    if current.get("expected_plan_classes") != list(EXPECTED_PLAN_CLASSES):
        errors.append("shadow dossier expected_plan_classes changed")
    if current.get("missing_plan_classes") != []:
        errors.append("shadow dossier missing_plan_classes must be empty")
    closure_conditions = current.get("closure_conditions")
    if not isinstance(closure_conditions, dict) or not closure_conditions:
        errors.append("shadow dossier closure_conditions must be present")
    else:
        for name, passed in closure_conditions.items():
            if passed is not True:
                errors.append(f"shadow dossier closure condition must pass: {name}")
    if isinstance(reports, list):
        blocker_count = 0
        mismatch_count = 0
        blocked_count = 0
        shadow_ready_count = 0
        for report in reports:
            if not isinstance(report, dict):
                errors.append("shadow dossier admission report must be an object")
                continue
            projection = report.get("projection", {})
            if report.get("solver_outcome") != "AwaitingEvidence":
                errors.append("shadow dossier report solver_outcome must be AwaitingEvidence")
            if projection.get("read_only") is not True:
                errors.append("shadow dossier report projection must remain read_only")
            for field_name in (
                "execution_allowed",
                "dispatch_allowed",
                "runtime_replanning_enabled",
                "terminal_closure_allowed",
                "success_claim_allowed",
            ):
                if projection.get(field_name) is not False:
                    errors.append(f"shadow dossier report {field_name} must be false")
            blocker_count += len(report.get("promotion_blockers", []))
            mismatch_count += len(report.get("shadow_mismatches", []))
            blocked_count += 1 if report.get("admission_decision") == "blocked" else 0
            shadow_ready_count += 1 if report.get("admission_decision") == "shadow_parity_ready" else 0
        if current.get("promotion_blocker_count") != blocker_count:
            errors.append("shadow dossier promotion_blocker_count must match reports")
        if current.get("shadow_mismatch_count") != mismatch_count:
            errors.append("shadow dossier shadow_mismatch_count must match reports")
        if current.get("blocked_report_count") != blocked_count:
            errors.append("shadow dossier blocked_report_count must match reports")
        if current.get("shadow_parity_ready_count") != shadow_ready_count:
            errors.append("shadow dossier shadow_parity_ready_count must match reports")
    if current.get("status") != ("verified" if not errors else "blocked"):
        errors.append("shadow dossier status must match validation result")
    return errors


def _json_safe(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert nested tuples from dataclass payloads into JSON-shaped values."""

    return json.loads(json.dumps(payload, sort_keys=True))


def render_shadow_dossier(dossier: dict[str, Any], output_stream: TextIO) -> None:
    """Render a concise human-readable dossier summary."""

    output_stream.write(
        "STATUS: {status}; scenarios={scenario_count}; reports={report_count}; "
        "blockers={promotion_blocker_count}; mismatches={shadow_mismatch_count}\n".format(**dossier)
    )
    output_stream.write(f"NEXT: {dossier['next_action']}\n")


def _world_state(scenario: ShadowScenario) -> WorldState | None:
    if scenario.world_state_mode == "none":
        return None
    return WorldState(
        tenant_id=TENANT_ID,
        state_id=f"world-state-{scenario.plan_class}",
        entity_count=1,
        relation_count=0,
        event_count=0,
        claim_count=0,
        contradiction_count=scenario.open_contradiction_count,
        open_contradiction_count=scenario.open_contradiction_count,
        projected_at="2026-05-04T12:00:00Z",
        state_hash="world-state-hash-1",
    )


def main(argv: list[str] | None = None) -> int:
    """Build and validate the shadow admission dossier."""

    parser = argparse.ArgumentParser(description="Report GovernedPlanningProfile shadow admission coverage.")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    dossier = build_shadow_dossier()
    errors = validate_shadow_dossier(dossier)
    if errors:
        for error in errors:
            sys.stderr.write(f"[BLOCKED] governed-planning-profile-shadow-dossier: {error}\n")
        sys.stderr.write("STATUS: blocked\n")
        return 1
    if args.json:
        sys.stdout.write(json.dumps(dossier, indent=2, sort_keys=True) + "\n")
    else:
        render_shadow_dossier(dossier, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
