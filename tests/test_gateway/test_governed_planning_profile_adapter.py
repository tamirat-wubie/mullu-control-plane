"""Tests for the GovernedPlanningProfile read-only adapter.

Purpose: verify compiled gateway plans can be projected into planning-profile
admission evidence without registering a planner or granting execution
authority.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: gateway.goal_compiler, gateway.causal_simulator,
gateway.governed_planning_profile_adapter, and the admission report schema.
Invariants: projection is deterministic, non-executable, shadow mismatches are
explicit, and the goal compiler import boundary remains intact.
"""

from __future__ import annotations

import ast
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from gateway.causal_simulator import CausalSimulator
from gateway.goal_compiler import GoalCompiler
from gateway.governed_planning_profile_adapter import (
    build_governed_planning_profile_admission_report,
)
from gateway.world_state import WorldState
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "governed_planning_profile_admission_report.schema.json"


def test_planning_profile_adapter_projects_high_risk_plan_without_authority() -> None:
    compiled = GoalCompiler().compile(
        message='/run financial.send_payment {"amount": "2500", "recipient": "vendor-a"}',
        tenant_id="tenant-1",
        identity_id="identity-1",
        world_state=_world_state(),
    )
    receipt = CausalSimulator().simulate(compiled, world_state=_world_state())

    report = build_governed_planning_profile_admission_report(
        compiled_plan=compiled,
        simulation_receipt=receipt,
    )
    payload = _json_object(report.to_dict())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), payload)
    blocker_categories = {finding.category for finding in report.promotion_blockers}

    assert errors == []
    assert report.admission_decision == "blocked"
    assert report.solver_outcome == "AwaitingEvidence"
    assert report.shadow_parity_status == "matched"
    assert report.projection.execution_allowed is False
    assert report.projection.dispatch_allowed is False
    assert report.projection.runtime_replanning_enabled is False
    assert {"authority", "evidence", "closure"}.issubset(blocker_categories)
    assert report.shadow_mismatches == ()
    assert report.report_id.startswith("governed-planning-profile-admission-")
    assert len(report.report_hash) == 64


def test_planning_profile_adapter_detects_identity_mismatch() -> None:
    compiled = GoalCompiler().compile(
        message="search knowledge docs",
        tenant_id="tenant-1",
        identity_id="identity-1",
        world_state=_world_state(),
    )
    receipt = CausalSimulator().simulate(compiled, world_state=_world_state())
    mismatched_receipt = replace(receipt, tenant_id="tenant-2")

    report = build_governed_planning_profile_admission_report(
        compiled_plan=compiled,
        simulation_receipt=mismatched_receipt,
    )
    mismatch_categories = {finding.category for finding in report.shadow_mismatches}
    mismatch_observed = {finding.observed_ref for finding in report.shadow_mismatches}

    assert report.admission_decision == "blocked"
    assert report.shadow_parity_status == "blocked"
    assert "identity" in mismatch_categories
    assert "tenant-2" in mismatch_observed
    assert any(ref.startswith("missing://governed-planning-profile/identity/") for ref in report.missing_evidence_refs)
    assert report.projection.tenant_id == "tenant-1"


def test_planning_profile_adapter_detects_topology_drift() -> None:
    compiled = GoalCompiler().compile(
        message="search knowledge docs and send message to team",
        tenant_id="tenant-1",
        identity_id="identity-1",
        world_state=_world_state(),
    )
    drifted_plan_dag = replace(compiled.plan_dag, step_ids=("step-1",))
    drifted_compiled = replace(compiled, plan_dag=drifted_plan_dag)
    receipt = CausalSimulator().simulate(compiled, world_state=_world_state())

    report = build_governed_planning_profile_admission_report(
        compiled_plan=drifted_compiled,
        simulation_receipt=receipt,
    )
    mismatch_categories = {finding.category for finding in report.shadow_mismatches}
    topology_findings = [finding for finding in report.shadow_mismatches if finding.category == "topology"]

    assert report.shadow_parity_status == "blocked"
    assert "topology" in mismatch_categories
    assert len(topology_findings) >= 1
    assert report.projection.step_count == 2
    assert report.projection.dag_step_count == 1
    assert any("dag_step_ids:1" in finding.observed_ref for finding in topology_findings)


def test_planning_profile_adapter_blocks_uncompiled_plan() -> None:
    compiled = GoalCompiler().compile(
        message="hello there",
        tenant_id="tenant-1",
        identity_id="identity-1",
    )
    receipt = CausalSimulator().simulate(compiled)

    report = build_governed_planning_profile_admission_report(
        compiled_plan=compiled,
        simulation_receipt=receipt,
    )
    blocker_categories = {finding.category for finding in report.promotion_blockers}

    assert report.admission_decision == "blocked"
    assert report.projection.step_count == 0
    assert report.projection.simulation_would_execute is False
    assert "simulation" in blocker_categories
    assert any(finding.observed_ref == "blocked_plan" for finding in report.promotion_blockers)
    assert "unknown://governed-planning-profile/operator-shadow-pilot" in report.missing_evidence_refs


def test_planning_profile_adapter_preserves_goal_compiler_import_boundary() -> None:
    adapter_path = ROOT / "gateway" / "governed_planning_profile_adapter.py"
    tree = ast.parse(adapter_path.read_text(encoding="utf-8"), filename=str(adapter_path))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        elif isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)

    assert "gateway.goal_compiler" not in imported_modules
    assert "gateway.causal_simulator" not in imported_modules
    assert "gateway.plan_executor" not in imported_modules
    assert "gateway.command_spine" in imported_modules
    assert SCHEMA_PATH.exists()


def _world_state() -> WorldState:
    return WorldState(
        tenant_id="tenant-1",
        state_id="world-state-1",
        entity_count=1,
        relation_count=0,
        event_count=0,
        claim_count=0,
        contradiction_count=0,
        open_contradiction_count=0,
        projected_at="2026-05-04T12:00:00Z",
        state_hash="world-state-hash-1",
    )


def _json_object(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload))
