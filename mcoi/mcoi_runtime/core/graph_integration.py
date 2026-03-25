"""Purpose: bridge between platform events and the operational graph.
Governance scope: graph wiring logic only.
Dependencies: contracts.graph, core.operational_graph.
Invariants:
  - Each link method ensures both endpoint nodes exist before creating an edge.
  - No network I/O. No mutation of non-graph state.
  - Idempotent: re-linking existing nodes does not raise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcoi_runtime.contracts.graph import (
    EdgeType,
    NodeType,
    ObligationLink,
    OperationalEdge,
)

if TYPE_CHECKING:
    from mcoi_runtime.core.operational_graph import OperationalGraph


class GraphBridge:
    """Static methods that wire platform events into graph edges.

    Every ``link_*`` helper follows the same contract:
    1. Ensure both endpoint nodes exist (add with the correct ``NodeType`` if missing).
    2. Create a typed ``OperationalEdge`` via ``graph.add_edge``.
    3. Return the edge.
    """

    # ------------------------------------------------------------------
    # Goal / Workflow / Skill / Provider chain
    # ------------------------------------------------------------------

    @staticmethod
    def link_goal_to_workflow(
        graph: OperationalGraph,
        goal_id: str,
        workflow_id: str,
    ) -> OperationalEdge:
        """Link a goal node to a workflow node."""
        graph.ensure_node(goal_id, NodeType.GOAL)
        graph.ensure_node(workflow_id, NodeType.WORKFLOW)
        return graph.add_edge(EdgeType.DEPENDS_ON, goal_id, workflow_id)

    @staticmethod
    def link_workflow_to_skill(
        graph: OperationalGraph,
        workflow_id: str,
        skill_id: str,
    ) -> OperationalEdge:
        """Link a workflow node to a skill node."""
        graph.ensure_node(workflow_id, NodeType.WORKFLOW)
        graph.ensure_node(skill_id, NodeType.SKILL)
        return graph.add_edge(EdgeType.DEPENDS_ON, workflow_id, skill_id)

    @staticmethod
    def link_skill_to_provider(
        graph: OperationalGraph,
        skill_id: str,
        provider_action_id: str,
    ) -> OperationalEdge:
        """Link a skill node to a provider-action node."""
        graph.ensure_node(skill_id, NodeType.SKILL)
        graph.ensure_node(provider_action_id, NodeType.PROVIDER_ACTION)
        return graph.add_edge(EdgeType.DEPENDS_ON, skill_id, provider_action_id)

    @staticmethod
    def link_action_to_verification(
        graph: OperationalGraph,
        action_id: str,
        verification_id: str,
    ) -> OperationalEdge:
        """Link a provider-action to its verification node."""
        graph.ensure_node(action_id, NodeType.PROVIDER_ACTION)
        graph.ensure_node(verification_id, NodeType.VERIFICATION)
        return graph.add_edge(EdgeType.VERIFIED_BY, action_id, verification_id)

    # ------------------------------------------------------------------
    # Verification / Incident / Escalation
    # ------------------------------------------------------------------

    @staticmethod
    def link_verification_to_incident(
        graph: OperationalGraph,
        verification_id: str,
        incident_id: str,
    ) -> OperationalEdge:
        """Link a verification failure to an incident node."""
        graph.ensure_node(verification_id, NodeType.VERIFICATION)
        graph.ensure_node(incident_id, NodeType.INCIDENT)
        return graph.add_edge(EdgeType.CAUSED_BY, verification_id, incident_id)

    @staticmethod
    def link_incident_to_escalation(
        graph: OperationalGraph,
        incident_id: str,
        escalation_target_id: str,
    ) -> OperationalEdge:
        """Link an incident to an escalation target."""
        graph.ensure_node(incident_id, NodeType.INCIDENT)
        graph.ensure_node(escalation_target_id, NodeType.PERSON)
        return graph.add_edge(EdgeType.ESCALATED_TO, incident_id, escalation_target_id)

    # ------------------------------------------------------------------
    # Job / Owner / Function / Thread
    # ------------------------------------------------------------------

    @staticmethod
    def link_job_to_owner(
        graph: OperationalGraph,
        job_id: str,
        owner_id: str,
    ) -> OperationalEdge:
        """Link a job to its owning identity."""
        graph.ensure_node(job_id, NodeType.JOB)
        graph.ensure_node(owner_id, NodeType.PERSON)
        return graph.add_edge(EdgeType.OWNS, job_id, owner_id)

    @staticmethod
    def link_job_to_function(
        graph: OperationalGraph,
        job_id: str,
        function_id: str,
    ) -> OperationalEdge:
        """Link a job to the function it executes."""
        graph.ensure_node(job_id, NodeType.JOB)
        graph.ensure_node(function_id, NodeType.FUNCTION)
        return graph.add_edge(EdgeType.PRODUCED, job_id, function_id)

    @staticmethod
    def link_thread_to_job(
        graph: OperationalGraph,
        thread_id: str,
        job_id: str,
    ) -> OperationalEdge:
        """Link a conversation thread to its associated job."""
        graph.ensure_node(thread_id, NodeType.COMMUNICATION_THREAD)
        graph.ensure_node(job_id, NodeType.JOB)
        return graph.add_edge(EdgeType.COMMUNICATES_VIA, thread_id, job_id)

    # ------------------------------------------------------------------
    # Approval / Action
    # ------------------------------------------------------------------

    @staticmethod
    def link_approval_to_action(
        graph: OperationalGraph,
        approval_id: str,
        action_id: str,
    ) -> OperationalEdge:
        """Link an approval decision to the action it authorises."""
        graph.ensure_node(approval_id, NodeType.APPROVAL)
        graph.ensure_node(action_id, NodeType.PROVIDER_ACTION)
        return graph.add_edge(EdgeType.DECIDED_BY, approval_id, action_id)

    # ------------------------------------------------------------------
    # Obligations
    # ------------------------------------------------------------------

    @staticmethod
    def add_obligation_for_job(
        graph: OperationalGraph,
        job_id: str,
        owner_id: str,
        description: str,
        deadline: str | None = None,
    ) -> ObligationLink:
        """Create an obligation linking a job to an owner with a description."""
        graph.ensure_node(job_id, NodeType.JOB)
        graph.ensure_node(owner_id, NodeType.PERSON)
        return graph.add_obligation(job_id, owner_id, description, deadline=deadline)
