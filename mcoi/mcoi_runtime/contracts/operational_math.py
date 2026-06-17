"""Purpose: operational mathematics loop contracts.
Governance scope: typed records for turning math principles into executable
    roles, controls, bounded loop iterations, and proof-bearing outcomes.
Dependencies: shared contract base helpers and Python standard dataclasses.
Invariants:
  - Every principle maps to at least one executable role and control.
  - Verified loop completion requires every final control to have a verified binding.
  - Loop targets carry a positive iteration ceiling.
  - Iteration records preserve tension movement and applied deltas.
  - Loop results are immutable and expose unresolved gaps explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence, cast

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_finite_float,
    require_non_empty_text,
    require_positive_int,
)


class OperationalMathPriority(Enum):
    """Priority lane for operational mathematics principles."""

    P0 = "p0"
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"


class OperationalMathRole(Enum):
    """Executable role a mathematics principle must serve."""

    CONSTRAINT = "constraint"
    TRANSFORMATION = "transformation"
    INVARIANT = "invariant"
    UNCERTAINTY_MODEL = "uncertainty_model"
    OPTIMIZER = "optimizer"
    STABILITY_CONTROLLER = "stability_controller"
    COMPLEXITY_BOUND = "complexity_bound"
    RESOURCE_BOUND = "resource_bound"
    ERROR_BOUND = "error_bound"
    DECISION_RULE = "decision_rule"
    TEMPORAL_MODEL = "temporal_model"
    ADVERSARIAL_GUARD = "adversarial_guard"
    PHYSICAL_FEASIBILITY = "physical_feasibility"
    VERIFICATION_GATE = "verification_gate"


class OperationalMathControl(Enum):
    """Control surface required to make a math principle executable."""

    EXECUTABLE_SOLVER = "executable_solver"
    BOUNDED_APPROXIMATION = "bounded_approximation"
    COMPLEXITY_CLASSIFICATION = "complexity_classification"
    RESOURCE_BUDGET = "resource_budget"
    NUMERICAL_STABILITY_BOUND = "numerical_stability_bound"
    SEQUENTIAL_DECISION_RULE = "sequential_decision_rule"
    ADVERSARIAL_STRESS_CASE = "adversarial_stress_case"
    BELIEF_SPACE_METRIC = "belief_space_metric"
    TEMPORAL_TERMINATION = "temporal_termination"
    PHYSICAL_CONSERVATION_CHECK = "physical_conservation_check"
    PROOF_RECEIPT = "proof_receipt"


class OperationalMathLoopStatus(Enum):
    """Terminal status for the autonomous operational math loop."""

    SATURATED = "saturated"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class OperationalMathControlBinding(ContractRecord):
    """Executable verifier binding for one operational math control."""

    control: OperationalMathControl = OperationalMathControl.PROOF_RECEIPT
    verifier_id: str = ""
    verified: bool = False
    evidence_refs: tuple[str, ...] = ()
    failure_reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.control, OperationalMathControl):
            raise ValueError("control must be an OperationalMathControl")
        object.__setattr__(self, "verifier_id", require_non_empty_text(self.verifier_id, "verifier_id"))
        if not isinstance(self.verified, bool):
            raise ValueError("verified must be a bool")
        object.__setattr__(
            self,
            "evidence_refs",
            _freeze_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=not self.verified),
        )
        if self.verified:
            object.__setattr__(self, "failure_reason", str(self.failure_reason or ""))
        else:
            object.__setattr__(
                self,
                "failure_reason",
                require_non_empty_text(self.failure_reason, "failure_reason"),
            )


def _freeze_enum_tuple(
    values: Sequence[Enum],
    field_name: str,
    enum_type: type[Enum],
    *,
    allow_empty: bool = False,
) -> tuple[Any, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    if not values and not allow_empty:
        raise ValueError(f"{field_name} must contain at least one item")
    for value in values:
        if not isinstance(value, enum_type):
            raise ValueError(f"{field_name} must contain only {enum_type.__name__} values")
    return cast(tuple[Any, ...], freeze_value(list(values)))


def _freeze_text_tuple(
    values: Sequence[str],
    field_name: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    if not values and not allow_empty:
        raise ValueError(f"{field_name} must contain at least one item")
    normalized: list[str] = []
    for value in values:
        normalized.append(require_non_empty_text(value, field_name))
    return cast(tuple[str, ...], freeze_value(normalized))


@dataclass(frozen=True, slots=True)
class OperationalMathPrinciple(ContractRecord):
    """A math principle bound to executable symbolic intelligence machinery."""

    principle_id: str = ""
    priority: OperationalMathPriority = OperationalMathPriority.P0
    title: str = ""
    math_area: str = ""
    operational_definition: str = ""
    required_roles: tuple[OperationalMathRole, ...] = ()
    required_controls: tuple[OperationalMathControl, ...] = ()
    failure_prevented: str = ""
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "principle_id", require_non_empty_text(self.principle_id, "principle_id"))
        if not isinstance(self.priority, OperationalMathPriority):
            raise ValueError("priority must be an OperationalMathPriority")
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "math_area", require_non_empty_text(self.math_area, "math_area"))
        object.__setattr__(
            self,
            "operational_definition",
            require_non_empty_text(self.operational_definition, "operational_definition"),
        )
        object.__setattr__(
            self,
            "required_roles",
            _freeze_enum_tuple(self.required_roles, "required_roles", OperationalMathRole),
        )
        object.__setattr__(
            self,
            "required_controls",
            _freeze_enum_tuple(self.required_controls, "required_controls", OperationalMathControl),
        )
        object.__setattr__(
            self,
            "failure_prevented",
            require_non_empty_text(self.failure_prevented, "failure_prevented"),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _freeze_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True),
        )


@dataclass(frozen=True, slots=True)
class OperationalMathTarget(ContractRecord):
    """A system surface receiving operational math loop application."""

    target_id: str = ""
    title: str = ""
    problem_class: str = ""
    current_roles: tuple[OperationalMathRole, ...] = ()
    current_controls: tuple[OperationalMathControl, ...] = ()
    max_iterations: int = 16
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "problem_class", require_non_empty_text(self.problem_class, "problem_class"))
        object.__setattr__(
            self,
            "current_roles",
            _freeze_enum_tuple(
                self.current_roles,
                "current_roles",
                OperationalMathRole,
                allow_empty=True,
            ),
        )
        object.__setattr__(
            self,
            "current_controls",
            _freeze_enum_tuple(
                self.current_controls,
                "current_controls",
                OperationalMathControl,
                allow_empty=True,
            ),
        )
        object.__setattr__(self, "max_iterations", require_positive_int(self.max_iterations, "max_iterations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class OperationalMathLoopIteration(ContractRecord):
    """One bounded application pass of the operational math loop."""

    iteration_index: int = 0
    applied_principle_ids: tuple[str, ...] = ()
    unresolved_principle_ids: tuple[str, ...] = ()
    added_roles: tuple[OperationalMathRole, ...] = ()
    added_controls: tuple[OperationalMathControl, ...] = ()
    tension_before: float = 0.0
    tension_after: float = 0.0
    proof_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "iteration_index", require_positive_int(self.iteration_index, "iteration_index"))
        object.__setattr__(
            self,
            "applied_principle_ids",
            _freeze_text_tuple(self.applied_principle_ids, "applied_principle_ids", allow_empty=True),
        )
        object.__setattr__(
            self,
            "unresolved_principle_ids",
            _freeze_text_tuple(self.unresolved_principle_ids, "unresolved_principle_ids", allow_empty=True),
        )
        object.__setattr__(
            self,
            "added_roles",
            _freeze_enum_tuple(self.added_roles, "added_roles", OperationalMathRole, allow_empty=True),
        )
        object.__setattr__(
            self,
            "added_controls",
            _freeze_enum_tuple(
                self.added_controls,
                "added_controls",
                OperationalMathControl,
                allow_empty=True,
            ),
        )
        object.__setattr__(self, "tension_before", require_finite_float(self.tension_before, "tension_before"))
        object.__setattr__(self, "tension_after", require_finite_float(self.tension_after, "tension_after"))
        object.__setattr__(self, "proof_refs", _freeze_text_tuple(self.proof_refs, "proof_refs", allow_empty=True))


@dataclass(frozen=True, slots=True)
class OperationalMathLoopResult(ContractRecord):
    """Final proof record for one autonomous operational math loop run."""

    result_id: str = ""
    target_id: str = ""
    status: OperationalMathLoopStatus = OperationalMathLoopStatus.BLOCKED
    iterations: tuple[OperationalMathLoopIteration, ...] = ()
    applied_principle_ids: tuple[str, ...] = ()
    unresolved_principle_ids: tuple[str, ...] = ()
    final_roles: tuple[OperationalMathRole, ...] = ()
    final_controls: tuple[OperationalMathControl, ...] = ()
    control_bindings: tuple[OperationalMathControlBinding, ...] = ()
    unverified_control_ids: tuple[str, ...] = ()
    proof_refs: tuple[str, ...] = ()
    solver_outcome: str = ""
    started_at: str = ""
    completed_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", require_non_empty_text(self.result_id, "result_id"))
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        if not isinstance(self.status, OperationalMathLoopStatus):
            raise ValueError("status must be an OperationalMathLoopStatus")
        if isinstance(self.iterations, (str, bytes)) or not isinstance(self.iterations, (tuple, list)):
            raise ValueError("iterations must be an array")
        for iteration in self.iterations:
            if not isinstance(iteration, OperationalMathLoopIteration):
                raise ValueError("iterations must contain only OperationalMathLoopIteration values")
        object.__setattr__(self, "iterations", freeze_value(list(self.iterations)))
        object.__setattr__(
            self,
            "applied_principle_ids",
            _freeze_text_tuple(self.applied_principle_ids, "applied_principle_ids", allow_empty=True),
        )
        object.__setattr__(
            self,
            "unresolved_principle_ids",
            _freeze_text_tuple(self.unresolved_principle_ids, "unresolved_principle_ids", allow_empty=True),
        )
        object.__setattr__(
            self,
            "final_roles",
            _freeze_enum_tuple(self.final_roles, "final_roles", OperationalMathRole, allow_empty=True),
        )
        object.__setattr__(
            self,
            "final_controls",
            _freeze_enum_tuple(self.final_controls, "final_controls", OperationalMathControl, allow_empty=True),
        )
        if isinstance(self.control_bindings, (str, bytes)) or not isinstance(self.control_bindings, (tuple, list)):
            raise ValueError("control_bindings must be an array")
        for binding in self.control_bindings:
            if not isinstance(binding, OperationalMathControlBinding):
                raise ValueError("control_bindings must contain only OperationalMathControlBinding values")
        object.__setattr__(self, "control_bindings", freeze_value(list(self.control_bindings)))
        object.__setattr__(
            self,
            "unverified_control_ids",
            _freeze_text_tuple(self.unverified_control_ids, "unverified_control_ids", allow_empty=True),
        )
        object.__setattr__(self, "proof_refs", _freeze_text_tuple(self.proof_refs, "proof_refs", allow_empty=True))
        object.__setattr__(self, "solver_outcome", require_non_empty_text(self.solver_outcome, "solver_outcome"))
        require_datetime_text(self.started_at, "started_at")
        require_datetime_text(self.completed_at, "completed_at")
