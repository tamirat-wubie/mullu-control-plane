"""Gateway causal simulator tests.

Purpose: verify governed goal plans dry-run before execution and produce
schema-compatible simulation receipts.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: gateway.causal_simulator, gateway.goal_compiler, and
schemas/simulation_receipt.schema.json.
Invariants:
  - Blocked plans do not simulate as executable.
  - High-risk plans project required controls before execution.
  - Open world contradictions block execution.
  - Simulation receipts validate against the public schema.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from gateway.causal_simulator import CausalSimulator
from gateway.goal_compiler import GoalCompiler
from gateway.world_state import WorldState
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "simulation_receipt.schema.json"


def test_causal_simulator_blocks_uncompiled_goal() -> None:
    compiled = GoalCompiler().compile(
        message="hello there",
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    receipt = CausalSimulator().simulate(compiled)

    assert receipt.would_execute is False
    assert receipt.reason == "no_capability_plan"
    assert receipt.required_controls == ("typed_capability_plan",)
    assert receipt.failure_modes == ("plan_compilation_blocked",)
    assert receipt.step_results == ()


def test_causal_simulator_projects_high_risk_controls() -> None:
    compiled = GoalCompiler().compile(
        message='/run financial.send_payment {"amount": "2500", "recipient": "vendor-a"}',
        tenant_id="tenant-1",
        identity_id="identity-1",
        world_state=_world_state(),
    )

    receipt = CausalSimulator().simulate(compiled, world_state=_world_state())
    step = receipt.step_results[0]

    assert receipt.would_execute is False
    assert receipt.reason == "required_controls_pending"
    assert "financial_admin_approval" in receipt.required_controls
    assert "approval_pending" in receipt.failure_modes
    assert receipt.compensation_path == "financial.refund"
    assert step.compensation_path == "financial.refund"


def test_causal_simulator_blocks_open_world_contradictions() -> None:
    world_state = _world_state(open_contradiction_count=1)
    compiled = GoalCompiler().compile(
        message="search knowledge docs",
        tenant_id="tenant-1",
        identity_id="identity-1",
        world_state=world_state,
    )

    receipt = CausalSimulator().simulate(compiled, world_state=world_state)

    assert receipt.would_execute is False
    assert receipt.reason == "open_world_contradictions"
    assert "resolve_world_contradictions" in receipt.required_controls
    assert "world_state_contradiction" in receipt.failure_modes
    assert receipt.state_hash == "world-state-hash-1"


def test_simulation_receipt_schema_accepts_dry_run_receipt() -> None:
    schema = _load_schema(SCHEMA_PATH)
    compiled = GoalCompiler().compile(
        message="search knowledge docs",
        tenant_id="tenant-1",
        identity_id="identity-1",
        world_state=_world_state(),
    )
    receipt = CausalSimulator().simulate(compiled, world_state=_world_state())
    payload = _json_object(asdict(receipt))

    errors = _validate_schema_instance(schema, payload)

    assert errors == []
    assert schema["$id"] == "urn:mullusi:schema:simulation-receipt:1"
    assert payload["simulation_id"].startswith("sim-")
    assert payload["receipt_hash"]
    assert payload["step_results"][0]["step_id"] == "step-1"


def _world_state(*, open_contradiction_count: int = 0) -> WorldState:
    return WorldState(
        tenant_id="tenant-1",
        state_id="world-state-1",
        entity_count=1,
        relation_count=0,
        event_count=0,
        claim_count=0,
        contradiction_count=open_contradiction_count,
        open_contradiction_count=open_contradiction_count,
        projected_at="2026-05-04T12:00:00Z",
        state_hash="world-state-hash-1",
    )


def _json_object(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload))
