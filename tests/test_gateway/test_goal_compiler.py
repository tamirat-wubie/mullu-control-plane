"""Gateway goal compiler tests.

Purpose: verify that user intent compiles into governed goals, plan DAGs,
    step controls, evidence obligations, approval requirements, rollback paths,
    and deterministic plan certificates.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: gateway.goal_compiler, gateway.world_state, and schemas/goal.schema.json.
Invariants:
  - No executable steps exist when no capability plan can be built.
  - High-risk steps carry approval and rollback or compensation obligations.
  - World-state binding is recorded as a precondition.
  - Compiled goal plans validate against the public schema.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from gateway.goal_compiler import GoalCompiler
from gateway.world_state import WorldState
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "goal.schema.json"


def test_goal_compiler_compiles_high_risk_payment_with_controls() -> None:
    compiler = GoalCompiler()

    compiled = compiler.compile(
        message='/run financial.send_payment {"amount": "2500", "recipient": "vendor-a"}',
        tenant_id="tenant-1",
        identity_id="identity-1",
        world_state=_world_state(),
    )
    step = compiled.steps[0]
    precondition_types = {precondition.condition_type for precondition in step.preconditions}
    evidence_types = {evidence.evidence_type for evidence in step.required_evidence}

    assert compiled.goal.status == "compiled"
    assert compiled.goal.risk_tier == "high"
    assert compiled.plan_dag.state_hash == "world-state-hash-1"
    assert compiled.certificate.certificate_id.startswith("goal-plan-cert-")
    assert compiled.certificate.step_count == 1
    assert step.capability_id == "financial.send_payment"
    assert step.approval.required is True
    assert step.approval.authority_required == ("financial_admin",)
    assert step.rollback.required is True
    assert step.rollback.capability_id == "financial.refund"
    assert step.side_effects_bounded is True
    assert "world_state_bound" in precondition_types
    assert {"transaction_id", "amount", "currency", "recipient_hash", "ledger_hash"}.issubset(evidence_types)


def test_goal_compiler_blocks_message_without_capability_plan() -> None:
    compiler = GoalCompiler()

    compiled = compiler.compile(
        message="hello there",
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert compiled.goal.status == "blocked"
    assert compiled.goal.success_criteria == ("typed_capability_plan_exists",)
    assert compiled.steps == ()
    assert compiled.subgoals == ()
    assert compiled.certificate.status == "blocked"
    assert compiled.certificate.reason == "no_capability_plan"
    assert compiled.plan_dag.step_ids == ()


def test_goal_compiler_projects_dependencies_into_plan_dag() -> None:
    compiler = GoalCompiler()

    compiled = compiler.compile(
        message="search knowledge docs and send message to team",
        tenant_id="tenant-1",
        identity_id="identity-1",
        world_state=_world_state(),
    )

    assert compiled.plan_dag.step_ids == ("step-1", "step-2")
    assert compiled.plan_dag.edges == (("step-1", "step-2"),)
    assert compiled.steps[1].depends_on == ("step-1",)
    assert compiled.subgoals[1].depends_on == ("step-1",)
    assert compiled.steps[1].approval.required is True
    assert compiled.terminal_conditions[-1].scope == "goal"
    assert compiled.terminal_conditions[-1].condition == "all_step_terminal_certificates_present"


def test_goal_schema_accepts_compiled_goal_plan() -> None:
    schema = _load_schema(SCHEMA_PATH)
    compiled = GoalCompiler().compile(
        message="search knowledge docs and send message to team",
        tenant_id="tenant-1",
        identity_id="identity-1",
        world_state=_world_state(),
    )
    payload = _compiled_payload(compiled)

    errors = _validate_schema_instance(schema, payload)

    assert errors == []
    assert schema["$id"] == "urn:mullusi:schema:goal:1"
    assert payload["goal"]["goal_id"].startswith("goal-")
    assert payload["plan_dag"]["edges"] == [["step-1", "step-2"]]
    assert payload["certificate"]["certificate_id"].startswith("goal-plan-cert-")
    assert payload["steps"][0]["preconditions"]


def test_goal_schema_rejects_step_without_preconditions() -> None:
    schema = _load_schema(SCHEMA_PATH)
    compiled = GoalCompiler().compile(
        message="search knowledge docs",
        tenant_id="tenant-1",
        identity_id="identity-1",
        world_state=_world_state(),
    )
    payload = _compiled_payload(compiled)
    payload["steps"][0]["preconditions"] = []

    errors = _validate_schema_instance(schema, payload)

    assert len(errors) == 1
    assert "$.steps[0].preconditions" in errors[0]
    assert "at least 1 item" in errors[0]
    assert payload["steps"][0]["capability_id"] == "enterprise.knowledge_search"
    assert payload["certificate"]["step_count"] == 1


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


def _compiled_payload(compiled: Any) -> dict[str, Any]:
    return json.loads(
        json.dumps(
            {
                "goal": asdict(compiled.goal),
                "subgoals": [asdict(subgoal) for subgoal in compiled.subgoals],
                "plan_dag": asdict(compiled.plan_dag),
                "steps": [asdict(step) for step in compiled.steps],
                "terminal_conditions": [
                    asdict(condition) for condition in compiled.terminal_conditions
                ],
                "certificate": asdict(compiled.certificate),
            }
        )
    )
