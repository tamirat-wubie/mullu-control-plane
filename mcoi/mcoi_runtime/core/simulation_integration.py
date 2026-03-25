"""Purpose: simulation integration bridge — connects simulation engine to graph decision points.
Governance scope: simulation invocation for goals, incidents, and approvals.
Dependencies: simulation engine, simulation contracts, operational graph, graph contracts.
Invariants:
  - Bridge methods are stateless static helpers.
  - Each method builds a SimulationRequest from graph context, runs full_simulation, returns results.
  - No graph mutation. No side effects beyond simulation.
  - All options must be non-empty tuples.
"""

from __future__ import annotations

from mcoi_runtime.contracts.simulation import (
    RiskLevel,
    SimulationComparison,
    SimulationOption,
    SimulationRequest,
    SimulationVerdict,
)
from .invariants import stable_identifier
from .operational_graph import OperationalGraph
from .simulation import SimulationEngine


class SimulationBridge:
    """Static methods bridging graph decision points to the simulation engine.

    Each method constructs a SimulationRequest from graph context, delegates
    to the SimulationEngine, and returns the comparison and verdict.
    """

    @staticmethod
    def simulate_before_goal(
        engine: SimulationEngine,
        graph: OperationalGraph,
        goal_id: str,
        workflow_options: list[SimulationOption],
    ) -> tuple[SimulationComparison, SimulationVerdict]:
        """Simulate workflow options before committing to a goal execution path.

        Args:
            engine: The simulation engine instance.
            graph: The operational graph for context.
            goal_id: The goal node ID to simulate against.
            workflow_options: The workflow options to compare.

        Returns:
            A tuple of (comparison, verdict).
        """
        goal_node = graph.get_node(goal_id)
        description = f"Goal simulation for {goal_id}"
        if goal_node is not None:
            description = f"Goal simulation: {goal_node.label}"

        request_id = stable_identifier("sim-req-goal", {"goal_id": goal_id})
        request = SimulationRequest(
            request_id=request_id,
            context_type="goal",
            context_id=goal_id,
            description=description,
            options=tuple(workflow_options),
        )
        return engine.full_simulation(request)

    @staticmethod
    def simulate_before_recovery(
        engine: SimulationEngine,
        graph: OperationalGraph,
        incident_id: str,
        recovery_options: list[SimulationOption],
    ) -> tuple[SimulationComparison, SimulationVerdict]:
        """Simulate recovery options before acting on an incident.

        Args:
            engine: The simulation engine instance.
            graph: The operational graph for context.
            incident_id: The incident node ID.
            recovery_options: The recovery paths to compare.

        Returns:
            A tuple of (comparison, verdict).
        """
        incident_node = graph.get_node(incident_id)
        description = f"Recovery simulation for incident {incident_id}"
        if incident_node is not None:
            description = f"Recovery simulation: {incident_node.label}"

        request_id = stable_identifier("sim-req-recovery", {"incident_id": incident_id})
        request = SimulationRequest(
            request_id=request_id,
            context_type="incident",
            context_id=incident_id,
            description=description,
            options=tuple(recovery_options),
        )
        return engine.full_simulation(request)

    @staticmethod
    def simulate_before_approval(
        engine: SimulationEngine,
        graph: OperationalGraph,
        action_id: str,
        approval_options: list[SimulationOption],
    ) -> tuple[SimulationComparison, SimulationVerdict]:
        """Simulate approval paths before deciding on an action.

        Compares approval vs reject vs escalate paths.

        Args:
            engine: The simulation engine instance.
            graph: The operational graph for context.
            action_id: The action node ID awaiting approval.
            approval_options: The approval path options to compare.

        Returns:
            A tuple of (comparison, verdict).
        """
        action_node = graph.get_node(action_id)
        description = f"Approval simulation for action {action_id}"
        if action_node is not None:
            description = f"Approval simulation: {action_node.label}"

        request_id = stable_identifier("sim-req-approval", {"action_id": action_id})
        request = SimulationRequest(
            request_id=request_id,
            context_type="approval",
            context_id=action_id,
            description=description,
            options=tuple(approval_options),
        )
        return engine.full_simulation(request)
