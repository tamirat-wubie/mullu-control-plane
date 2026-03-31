"""Policy simulation endpoints — dry-run governance scenario testing."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


class SimulateRequest(BaseModel):
    simulation_id: str = ""
    scenario: str = "policy_change"
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    test_actions: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/api/v1/simulate")
def run_simulation(req: SimulateRequest):
    """Run a policy simulation — shows what would change without modifying state."""
    from mcoi_runtime.core.policy_sandbox import SimulationRequest, SimulationScenario
    from hashlib import sha256
    deps.metrics.inc("requests_governed")

    sim_id = req.simulation_id or f"sim-{sha256(req.description.encode()).hexdigest()[:8]}"
    try:
        scenario = SimulationScenario(req.scenario)
    except ValueError:
        scenario = SimulationScenario.CUSTOM

    request = SimulationRequest(
        simulation_id=sim_id,
        scenario=scenario,
        description=req.description or f"{scenario.value} simulation",
        parameters=req.parameters,
        test_actions=tuple(req.test_actions),
    )
    result = deps.policy_sandbox.simulate(request)

    deps.audit_trail.record(
        action="simulation.run",
        actor_id="api",
        tenant_id="system",
        target=sim_id,
        outcome="success",
        detail={
            "scenario": result.scenario,
            "actions_tested": result.actions_tested,
            "actions_changed": result.actions_changed,
            "newly_blocked": result.newly_blocked,
        },
    )

    return {
        "simulation_id": result.simulation_id,
        "scenario": result.scenario,
        "description": result.description,
        "actions_tested": result.actions_tested,
        "actions_changed": result.actions_changed,
        "newly_blocked": result.newly_blocked,
        "newly_allowed": result.newly_allowed,
        "results": [
            {
                "action_type": r.action_type,
                "target": r.target,
                "current": r.current_decision,
                "simulated": r.simulated_decision,
                "changed": r.changed,
                "reason": r.reason,
            }
            for r in result.action_results
        ],
        "summary": result.summary,
        "simulated_at": result.simulated_at,
        "governed": True,
    }


@router.get("/api/v1/simulate/history")
def simulation_history(limit: int = 20):
    """Recent simulation history."""
    deps.metrics.inc("requests_governed")
    sims = deps.policy_sandbox.recent_simulations(limit=limit)
    return {
        "simulations": [
            {
                "simulation_id": s.simulation_id,
                "scenario": s.scenario,
                "actions_tested": s.actions_tested,
                "actions_changed": s.actions_changed,
                "newly_blocked": s.newly_blocked,
                "simulated_at": s.simulated_at,
                "impact": s.summary.get("impact", "unknown"),
            }
            for s in sims
        ],
        "count": len(sims),
        "governed": True,
    }


@router.get("/api/v1/simulate/summary")
def simulation_summary():
    """Simulation engine summary."""
    deps.metrics.inc("requests_governed")
    return {**deps.policy_sandbox.summary(), "governed": True}
