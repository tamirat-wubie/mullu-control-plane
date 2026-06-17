"""Purpose: autonomous operational mathematics loop engine.
Governance scope: converting the Mullu core-math audit into deterministic
    executable roles, controls, loop deltas, and proof receipts.
Dependencies: operational_math contracts, event_spine, and invariant helpers.
Invariants:
  - Every audit principle compiles into at least one role and one control.
  - SolvedVerified requires a verified binding for every final control.
  - The loop is bounded by target.max_iterations and never recurses.
  - Missing principles remain explicit in the final result.
  - Every applied delta can emit a correlated proof event.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable, Sequence

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.operational_math import (
    OperationalMathControl,
    OperationalMathControlBinding,
    OperationalMathLoopIteration,
    OperationalMathLoopResult,
    OperationalMathLoopStatus,
    OperationalMathPrinciple,
    OperationalMathPriority,
    OperationalMathRole,
    OperationalMathTarget,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _priority_rank(priority: OperationalMathPriority) -> int:
    ranks = {
        OperationalMathPriority.P0: 0,
        OperationalMathPriority.P1: 1,
        OperationalMathPriority.P2: 2,
        OperationalMathPriority.P3: 3,
    }
    return ranks[priority]


def _principle_number(principle_id: str) -> int:
    if principle_id.startswith("F") and principle_id[1:].isdigit():
        return int(principle_id[1:])
    return 10_000


def _ordered_unique_roles(values: Sequence[OperationalMathRole]) -> tuple[OperationalMathRole, ...]:
    seen: set[OperationalMathRole] = set()
    ordered: list[OperationalMathRole] = []
    for value in values:
        if value not in seen:
            ordered.append(value)
            seen.add(value)
    return tuple(ordered)


def _ordered_unique_controls(values: Sequence[OperationalMathControl]) -> tuple[OperationalMathControl, ...]:
    seen: set[OperationalMathControl] = set()
    ordered: list[OperationalMathControl] = []
    for value in values:
        if value not in seen:
            ordered.append(value)
            seen.add(value)
    return tuple(ordered)


def _ordered_unique_text(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            ordered.append(value)
            seen.add(value)
    return tuple(ordered)


def default_operational_math_principles() -> tuple[OperationalMathPrinciple, ...]:
    """Return the canonical F1-F10 operational math audit catalog."""

    principles = (
        OperationalMathPrinciple(
            principle_id="F1",
            priority=OperationalMathPriority.P0,
            title="math as operational structure management",
            math_area="constraints transformations invariants",
            operational_definition=(
                "Mathematics must govern structure, constraints, transformations, "
                "uncertainty, optimization, stability, and propagation."
            ),
            required_roles=(
                OperationalMathRole.CONSTRAINT,
                OperationalMathRole.TRANSFORMATION,
                OperationalMathRole.INVARIANT,
            ),
            required_controls=(OperationalMathControl.PROOF_RECEIPT,),
            failure_prevented="symbolic decoration without operational effect",
            evidence_refs=("audit:F1",),
        ),
        OperationalMathPrinciple(
            principle_id="F2",
            priority=OperationalMathPriority.P0,
            title="executable computational mathematics",
            math_area="incremental solvers streaming optimization online inference",
            operational_definition=(
                "Each math topic must compile to a solver, bounded approximation, "
                "dynamic graph update, scheduler, or propagation routine."
            ),
            required_roles=(
                OperationalMathRole.OPTIMIZER,
                OperationalMathRole.VERIFICATION_GATE,
            ),
            required_controls=(
                OperationalMathControl.EXECUTABLE_SOLVER,
                OperationalMathControl.BOUNDED_APPROXIMATION,
            ),
            failure_prevented="beautiful but computationally unusable symbolic machinery",
            evidence_refs=("audit:F2",),
        ),
        OperationalMathPrinciple(
            principle_id="F3",
            priority=OperationalMathPriority.P0,
            title="complexity awareness",
            math_area="tractability approximation branching factors",
            operational_definition=(
                "Search and reasoning must classify tractability, branching growth, "
                "and approximation limits before execution expands."
            ),
            required_roles=(OperationalMathRole.COMPLEXITY_BOUND,),
            required_controls=(
                OperationalMathControl.COMPLEXITY_CLASSIFICATION,
                OperationalMathControl.BOUNDED_APPROXIMATION,
            ),
            failure_prevented="unbounded exhaustive reasoning and search explosion",
            evidence_refs=("audit:F3",),
        ),
        OperationalMathPrinciple(
            principle_id="F4",
            priority=OperationalMathPriority.P1,
            title="numerical stability",
            math_area="error propagation convergence conditioning",
            operational_definition=(
                "Forecasting, optimization, simulation, and probabilistic propagation "
                "must carry explicit error and convergence bounds."
            ),
            required_roles=(OperationalMathRole.ERROR_BOUND,),
            required_controls=(OperationalMathControl.NUMERICAL_STABILITY_BOUND,),
            failure_prevented="silent precision loss and unstable iteration",
            evidence_refs=("audit:F4",),
        ),
        OperationalMathPrinciple(
            principle_id="F5",
            priority=OperationalMathPriority.P0,
            title="decision theory",
            math_area="utility bounded rationality regret partial observability",
            operational_definition=(
                "Planning must select actions through bounded utility, evidence, "
                "regret, and exploration rules under incomplete state."
            ),
            required_roles=(
                OperationalMathRole.DECISION_RULE,
                OperationalMathRole.UNCERTAINTY_MODEL,
            ),
            required_controls=(OperationalMathControl.SEQUENTIAL_DECISION_RULE,),
            failure_prevented="reasoning without bounded action selection",
            evidence_refs=("audit:F5",),
        ),
        OperationalMathPrinciple(
            principle_id="F6",
            priority=OperationalMathPriority.P2,
            title="adversarial mathematics",
            math_area="minimax robustness worst case attack surfaces",
            operational_definition=(
                "Governed execution must evaluate worst-case strategic pressure, "
                "attack surfaces, deception, and robustness before promotion."
            ),
            required_roles=(OperationalMathRole.ADVERSARIAL_GUARD,),
            required_controls=(OperationalMathControl.ADVERSARIAL_STRESS_CASE,),
            failure_prevented="fragile governance under strategic pressure",
            evidence_refs=("audit:F6",),
        ),
        OperationalMathPrinciple(
            principle_id="F7",
            priority=OperationalMathPriority.P3,
            title="information geometry",
            math_area="belief-space topology uncertainty manifolds landscapes",
            operational_definition=(
                "Belief evolution and method routing should expose state-space "
                "distance, curvature, and uncertainty flow when advanced routing is used."
            ),
            required_roles=(OperationalMathRole.UNCERTAINTY_MODEL,),
            required_controls=(OperationalMathControl.BELIEF_SPACE_METRIC,),
            failure_prevented="opaque belief-space movement and unstable method arbitration",
            evidence_refs=("audit:F7",),
        ),
        OperationalMathPrinciple(
            principle_id="F8",
            priority=OperationalMathPriority.P1,
            title="temporal mathematics",
            math_area="discrete event systems temporal logic stochastic processes",
            operational_definition=(
                "Planning, memory, governance, and execution pipelines must carry "
                "temporal constraints, event ordering, decay, and termination."
            ),
            required_roles=(OperationalMathRole.TEMPORAL_MODEL,),
            required_controls=(OperationalMathControl.TEMPORAL_TERMINATION,),
            failure_prevented="unbounded planning and ungoverned time evolution",
            evidence_refs=("audit:F8",),
        ),
        OperationalMathPrinciple(
            principle_id="F9",
            priority=OperationalMathPriority.P0,
            title="resource mathematics",
            math_area="queueing scheduling bandwidth latency load balancing",
            operational_definition=(
                "All symbolic intelligence execution must model queueing, scheduling, "
                "latency, capacity, and budget consumption."
            ),
            required_roles=(OperationalMathRole.RESOURCE_BOUND,),
            required_controls=(OperationalMathControl.RESOURCE_BUDGET,),
            failure_prevented="autonomy that ignores bounded runtime resources",
            evidence_refs=("audit:F9",),
        ),
        OperationalMathPrinciple(
            principle_id="F10",
            priority=OperationalMathPriority.P1,
            title="embodied and physical constraint mathematics",
            math_area="conservation feasibility geometry energy cost",
            operational_definition=(
                "Execution claims must be checked against conservation, spatial, "
                "energy, feasibility, and resource-cost constraints when reality is touched."
            ),
            required_roles=(OperationalMathRole.PHYSICAL_FEASIBILITY,),
            required_controls=(OperationalMathControl.PHYSICAL_CONSERVATION_CHECK,),
            failure_prevented="symbolic elegance detached from feasible execution",
            evidence_refs=("audit:F10",),
        ),
    )
    return tuple(sorted(principles, key=lambda item: (_priority_rank(item.priority), _principle_number(item.principle_id))))


def default_operational_math_control_bindings() -> tuple[OperationalMathControlBinding, ...]:
    """Return canonical verifier bindings for operational math controls."""

    return tuple(
        OperationalMathControlBinding(
            control=control,
            verifier_id=f"operational_math_control_verifier:{control.value}",
            verified=True,
            evidence_refs=(f"operational-math-control:{control.value}",),
        )
        for control in OperationalMathControl
    )


def _binding_map(
    bindings: Sequence[OperationalMathControlBinding],
) -> dict[OperationalMathControl, OperationalMathControlBinding]:
    bound: dict[OperationalMathControl, OperationalMathControlBinding] = {}
    for binding in bindings:
        if not isinstance(binding, OperationalMathControlBinding):
            raise RuntimeCoreInvariantError("control_bindings must contain OperationalMathControlBinding values")
        if binding.control in bound:
            raise RuntimeCoreInvariantError("control_bindings must contain unique controls")
        bound[binding.control] = binding
    return bound


def _unverified_controls(
    controls: Sequence[OperationalMathControl],
    bindings: dict[OperationalMathControl, OperationalMathControlBinding],
) -> tuple[OperationalMathControl, ...]:
    unverified: list[OperationalMathControl] = []
    for control in controls:
        binding = bindings.get(control)
        if binding is None or not binding.verified:
            unverified.append(control)
    return tuple(unverified)


def _missing_roles(
    principle: OperationalMathPrinciple,
    roles: Sequence[OperationalMathRole],
) -> tuple[OperationalMathRole, ...]:
    available = set(roles)
    return tuple(role for role in principle.required_roles if role not in available)


def _missing_controls(
    principle: OperationalMathPrinciple,
    controls: Sequence[OperationalMathControl],
) -> tuple[OperationalMathControl, ...]:
    available = set(controls)
    return tuple(control for control in principle.required_controls if control not in available)


def _unresolved_principles(
    principles: Sequence[OperationalMathPrinciple],
    roles: Sequence[OperationalMathRole],
    controls: Sequence[OperationalMathControl],
) -> tuple[OperationalMathPrinciple, ...]:
    unresolved: list[OperationalMathPrinciple] = []
    for principle in principles:
        if _missing_roles(principle, roles) or _missing_controls(principle, controls):
            unresolved.append(principle)
    return tuple(unresolved)


def _tension_score(
    principles: Sequence[OperationalMathPrinciple],
    roles: Sequence[OperationalMathRole],
    controls: Sequence[OperationalMathControl],
) -> float:
    total_required = 0
    missing_required = 0
    for principle in principles:
        total_required += len(principle.required_roles) + len(principle.required_controls)
        missing_required += len(_missing_roles(principle, roles))
        missing_required += len(_missing_controls(principle, controls))
    if total_required == 0:
        return 0.0
    return missing_required / total_required


def _emit_event(
    event_spine: EventSpineEngine | None,
    action: str,
    correlation_id: str,
    payload: dict[str, Any],
    clock: Callable[[], str],
) -> EventRecord | None:
    if event_spine is None:
        return None
    now = clock()
    event_payload = dict(payload)
    event_payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier(
            "evt-omath",
            {"action": action, "cid": correlation_id, "payload": event_payload, "ts": now},
        ),
        event_type=EventType.CUSTOM,
        source=EventSource.SIMULATION_ENGINE,
        correlation_id=correlation_id,
        payload=event_payload,
        emitted_at=now,
    )
    return event_spine.emit(event)


class OperationalMathLoopEngine:
    """Bounded autonomous loop for applying operational math principles."""

    def __init__(
        self,
        *,
        event_spine: EventSpineEngine | None = None,
        principles: Sequence[OperationalMathPrinciple] | None = None,
        control_bindings: Sequence[OperationalMathControlBinding] | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        if event_spine is not None and not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock = clock or _now_iso
        self._principles = tuple(principles or default_operational_math_principles())
        if not self._principles:
            raise RuntimeCoreInvariantError("principles must contain at least one item")
        for principle in self._principles:
            if not isinstance(principle, OperationalMathPrinciple):
                raise RuntimeCoreInvariantError("principles must contain OperationalMathPrinciple values")
        self._control_bindings = (
            default_operational_math_control_bindings()
            if control_bindings is None
            else tuple(control_bindings)
        )
        self._control_binding_map = _binding_map(self._control_bindings)

    @property
    def principles(self) -> tuple[OperationalMathPrinciple, ...]:
        return self._principles

    def apply_all(self, target: OperationalMathTarget) -> OperationalMathLoopResult:
        """Apply all missing operational math principles within a bounded loop."""

        if not isinstance(target, OperationalMathTarget):
            raise RuntimeCoreInvariantError("target must be an OperationalMathTarget")

        started_at = self._clock()
        roles = _ordered_unique_roles(target.current_roles)
        controls = _ordered_unique_controls(target.current_controls)
        iterations: list[OperationalMathLoopIteration] = []
        applied_ids: list[str] = []
        proof_refs: list[str] = []

        for iteration_index in range(1, target.max_iterations + 1):
            unresolved_before = _unresolved_principles(self._principles, roles, controls)
            if not unresolved_before:
                break

            principle = unresolved_before[0]
            added_roles = _missing_roles(principle, roles)
            added_controls = _missing_controls(principle, controls)
            tension_before = _tension_score(self._principles, roles, controls)

            roles = _ordered_unique_roles((*roles, *added_roles))
            controls = _ordered_unique_controls((*controls, *added_controls))
            tension_after = _tension_score(self._principles, roles, controls)
            proof_ref = (
                f"operational_math:{target.target_id}:"
                f"{principle.principle_id}:iteration:{iteration_index}"
            )
            proof_refs.append(proof_ref)
            applied_ids.append(principle.principle_id)

            unresolved_after = _unresolved_principles(self._principles, roles, controls)
            iteration = OperationalMathLoopIteration(
                iteration_index=iteration_index,
                applied_principle_ids=(principle.principle_id,),
                unresolved_principle_ids=tuple(item.principle_id for item in unresolved_after),
                added_roles=added_roles,
                added_controls=added_controls,
                tension_before=tension_before,
                tension_after=tension_after,
                proof_refs=(proof_ref,),
            )
            iterations.append(iteration)
            _emit_event(
                self._events,
                "operational_math_principle_applied",
                target.target_id,
                {
                    "target_id": target.target_id,
                    "principle_id": principle.principle_id,
                    "priority": principle.priority.value,
                    "added_roles": tuple(role.value for role in added_roles),
                    "added_controls": tuple(control.value for control in added_controls),
                    "tension_before": tension_before,
                    "tension_after": tension_after,
                    "proof_ref": proof_ref,
                },
                self._clock,
            )

        unresolved_final = _unresolved_principles(self._principles, roles, controls)
        unverified_controls = _unverified_controls(controls, self._control_binding_map)
        final_bindings = tuple(
            self._control_binding_map[control]
            for control in controls
            if control in self._control_binding_map
        )
        status = (
            OperationalMathLoopStatus.SATURATED
            if not unresolved_final and not unverified_controls
            else OperationalMathLoopStatus.BLOCKED
            if not unresolved_final and unverified_controls
            else OperationalMathLoopStatus.MAX_ITERATIONS_REACHED
        )
        solver_outcome = "SolvedVerified" if status is OperationalMathLoopStatus.SATURATED else "AwaitingEvidence"
        completed_at = self._clock()
        result_id = stable_identifier(
            "omath-result",
            {
                "target_id": target.target_id,
                "status": status.value,
                "iterations": len(iterations),
                "applied": tuple(applied_ids),
                "unresolved": tuple(item.principle_id for item in unresolved_final),
                "unverified_controls": tuple(control.value for control in unverified_controls),
            },
        )

        result = OperationalMathLoopResult(
            result_id=result_id,
            target_id=target.target_id,
            status=status,
            iterations=tuple(iterations),
            applied_principle_ids=_ordered_unique_text(applied_ids),
            unresolved_principle_ids=tuple(item.principle_id for item in unresolved_final),
            final_roles=roles,
            final_controls=controls,
            control_bindings=final_bindings,
            unverified_control_ids=tuple(control.value for control in unverified_controls),
            proof_refs=_ordered_unique_text(proof_refs),
            solver_outcome=solver_outcome,
            started_at=started_at,
            completed_at=completed_at,
        )
        _emit_event(
            self._events,
            "operational_math_loop_completed",
            target.target_id,
            {
                "target_id": target.target_id,
                "result_id": result.result_id,
                "status": result.status.value,
                "solver_outcome": result.solver_outcome,
                "applied_principle_ids": result.applied_principle_ids,
                "unresolved_principle_ids": result.unresolved_principle_ids,
                "unverified_control_ids": result.unverified_control_ids,
            },
            self._clock,
        )
        return result

    def state_hash(self) -> str:
        """Return a deterministic hash of the loaded principle catalog."""

        digest = sha256()
        for principle in self._principles:
            digest.update(principle.to_json().encode("utf-8"))
        return digest.hexdigest()
