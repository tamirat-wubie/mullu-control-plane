"""Task decomposer for governed swarm goals.

Purpose: turn explicit goal task specs into typed swarm tasks without adding
implicit authority.
Governance scope: OCE, RAG, and CDCV across goal-to-task transitions.
Dependencies: swarm contracts.
Invariants: every task is caused by a goal spec and side effects remain denied.
"""

from __future__ import annotations

from .contracts import SwarmGoal, SwarmInvariantViolation, SwarmTask, SwarmTaskRisk


class TaskDecomposer:
    """Compile explicit task specifications into auditable tasks."""

    def decompose(self, goal: SwarmGoal) -> tuple[SwarmTask, ...]:
        """Return deterministic task objects for a goal."""

        tasks: list[SwarmTask] = []
        for index, spec in enumerate(goal.task_specs, start=1):
            task_id = str(spec.get("task_id") or f"{goal.goal_id}_task_{index:03d}")
            required_role = str(spec.get("required_role") or "")
            required_capabilities = tuple(str(value) for value in spec.get("required_capabilities", ()))
            input_refs = tuple(str(value) for value in spec.get("input_refs", ()))
            expected_output = str(spec.get("expected_output") or "")
            risk = SwarmTaskRisk(str(spec.get("risk") or SwarmTaskRisk.LOW.value))
            deadline_value = spec.get("deadline")
            deadline = str(deadline_value) if deadline_value is not None else None
            side_effects_allowed = bool(spec.get("side_effects_allowed", False))
            if side_effects_allowed:
                raise SwarmInvariantViolation("task decomposition cannot grant side effects")
            tasks.append(
                SwarmTask(
                    task_id=task_id,
                    goal_id=goal.goal_id,
                    tenant_id=goal.tenant_id,
                    required_role=required_role,
                    required_capabilities=required_capabilities,
                    input_refs=input_refs,
                    expected_output=expected_output,
                    risk=risk,
                    deadline=deadline,
                    requires_receipt=bool(spec.get("requires_receipt", True)),
                    side_effects_allowed=False,
                )
            )
        return tuple(tasks)
