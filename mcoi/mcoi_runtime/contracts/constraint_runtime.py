"""Purpose: constraint / algorithm / solver runtime contracts.
Governance scope: typed descriptors for constraint definitions, solver problems,
    solver solutions, graph nodes, graph edges, schedule slots, assignment records,
    dependency chains, snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - SolveStatus transitions are explicit.
  - objective_value may be any finite float (including negative).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_finite_float,
    require_non_empty_text,
    require_non_negative_float,
    require_non_negative_int,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AlgorithmKind(Enum):
    """Category of algorithm used by the solver."""
    GRAPH_SEARCH = "graph_search"
    MATCHING = "matching"
    ROUTING = "routing"
    SCHEDULING = "scheduling"
    PACKING = "packing"
    CONSTRAINT_SAT = "constraint_sat"


class SolveStatus(Enum):
    """Lifecycle status of a solver problem or solution."""
    PENDING = "pending"
    RUNNING = "running"
    SOLVED = "solved"
    INFEASIBLE = "infeasible"
    TIMEOUT = "timeout"
    FAILED = "failed"


class ConstraintKind(Enum):
    """Category of constraint."""
    EQUALITY = "equality"
    INEQUALITY = "inequality"
    RANGE = "range"
    EXCLUSION = "exclusion"
    DEPENDENCY = "dependency"
    TEMPORAL = "temporal"


class PriorityMode(Enum):
    """Scheduling priority strategy."""
    FIFO = "fifo"
    LIFO = "lifo"
    PRIORITY = "priority"
    DEADLINE = "deadline"
    COST = "cost"


class GraphTraversal(Enum):
    """Graph traversal algorithm."""
    BFS = "bfs"
    DFS = "dfs"
    DIJKSTRA = "dijkstra"
    ASTAR = "astar"
    TOPOLOGICAL = "topological"


class AssignmentStrategy(Enum):
    """Strategy for resource assignment."""
    GREEDY = "greedy"
    BALANCED = "balanced"
    MIN_COST = "min_cost"
    ROUND_ROBIN = "round_robin"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConstraintDefinition(ContractRecord):
    """A constraint definition within a solver problem."""

    constraint_id: str = ""
    tenant_id: str = ""
    kind: ConstraintKind = ConstraintKind.EQUALITY
    expression: str = ""
    variable_refs: str = ""
    priority: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraint_id", require_non_empty_text(self.constraint_id, "constraint_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.kind, ConstraintKind):
            raise ValueError("kind must be a ConstraintKind")
        object.__setattr__(self, "expression", require_non_empty_text(self.expression, "expression"))
        # variable_refs may be empty
        object.__setattr__(self, "priority", require_non_negative_int(self.priority, "priority"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SolverProblem(ContractRecord):
    """A solver problem definition."""

    problem_id: str = ""
    tenant_id: str = ""
    algorithm: AlgorithmKind = AlgorithmKind.CONSTRAINT_SAT
    constraint_count: int = 0
    variable_count: int = 0
    status: SolveStatus = SolveStatus.PENDING
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "problem_id", require_non_empty_text(self.problem_id, "problem_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.algorithm, AlgorithmKind):
            raise ValueError("algorithm must be an AlgorithmKind")
        object.__setattr__(self, "constraint_count", require_non_negative_int(self.constraint_count, "constraint_count"))
        object.__setattr__(self, "variable_count", require_non_negative_int(self.variable_count, "variable_count"))
        if not isinstance(self.status, SolveStatus):
            raise ValueError("status must be a SolveStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SolverSolution(ContractRecord):
    """A solution produced by a solver."""

    solution_id: str = ""
    tenant_id: str = ""
    problem_ref: str = ""
    status: SolveStatus = SolveStatus.SOLVED
    objective_value: float = 0.0
    iterations: int = 0
    duration_ms: float = 0.0
    solved_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "solution_id", require_non_empty_text(self.solution_id, "solution_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "problem_ref", require_non_empty_text(self.problem_ref, "problem_ref"))
        if not isinstance(self.status, SolveStatus):
            raise ValueError("status must be a SolveStatus")
        # objective_value may be any finite float (including negative)
        object.__setattr__(self, "objective_value", require_finite_float(self.objective_value, "objective_value"))
        object.__setattr__(self, "iterations", require_non_negative_int(self.iterations, "iterations"))
        object.__setattr__(self, "duration_ms", require_non_negative_float(self.duration_ms, "duration_ms"))
        require_datetime_text(self.solved_at, "solved_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class GraphNode(ContractRecord):
    """A node in a constraint graph."""

    node_id: str = ""
    tenant_id: str = ""
    label: str = ""
    weight: float = 1.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", require_non_empty_text(self.node_id, "node_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "label", require_non_empty_text(self.label, "label"))
        object.__setattr__(self, "weight", require_non_negative_float(self.weight, "weight"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class GraphEdge(ContractRecord):
    """An edge in a constraint graph."""

    edge_id: str = ""
    tenant_id: str = ""
    from_node: str = ""
    to_node: str = ""
    weight: float = 1.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "edge_id", require_non_empty_text(self.edge_id, "edge_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "from_node", require_non_empty_text(self.from_node, "from_node"))
        object.__setattr__(self, "to_node", require_non_empty_text(self.to_node, "to_node"))
        object.__setattr__(self, "weight", require_non_negative_float(self.weight, "weight"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ScheduleSlot(ContractRecord):
    """A time slot in a schedule."""

    slot_id: str = ""
    tenant_id: str = ""
    resource_ref: str = ""
    start_at: str = ""
    end_at: str = ""
    priority: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "slot_id", require_non_empty_text(self.slot_id, "slot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "resource_ref", require_non_empty_text(self.resource_ref, "resource_ref"))
        require_datetime_text(self.start_at, "start_at")
        require_datetime_text(self.end_at, "end_at")
        object.__setattr__(self, "priority", require_non_negative_int(self.priority, "priority"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AssignmentRecord(ContractRecord):
    """A resource-to-task assignment."""

    assignment_id: str = ""
    tenant_id: str = ""
    resource_ref: str = ""
    task_ref: str = ""
    strategy: AssignmentStrategy = AssignmentStrategy.GREEDY
    cost: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assignment_id", require_non_empty_text(self.assignment_id, "assignment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "resource_ref", require_non_empty_text(self.resource_ref, "resource_ref"))
        object.__setattr__(self, "task_ref", require_non_empty_text(self.task_ref, "task_ref"))
        if not isinstance(self.strategy, AssignmentStrategy):
            raise ValueError("strategy must be an AssignmentStrategy")
        object.__setattr__(self, "cost", require_non_negative_float(self.cost, "cost"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DependencyChain(ContractRecord):
    """A dependency link between two references."""

    chain_id: str = ""
    tenant_id: str = ""
    source_ref: str = ""
    target_ref: str = ""
    lag: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "chain_id", require_non_empty_text(self.chain_id, "chain_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "source_ref", require_non_empty_text(self.source_ref, "source_ref"))
        object.__setattr__(self, "target_ref", require_non_empty_text(self.target_ref, "target_ref"))
        object.__setattr__(self, "lag", require_non_negative_int(self.lag, "lag"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConstraintSnapshot(ContractRecord):
    """Point-in-time snapshot of constraint runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_constraints: int = 0
    total_problems: int = 0
    total_solutions: int = 0
    total_nodes: int = 0
    total_edges: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_constraints", require_non_negative_int(self.total_constraints, "total_constraints"))
        object.__setattr__(self, "total_problems", require_non_negative_int(self.total_problems, "total_problems"))
        object.__setattr__(self, "total_solutions", require_non_negative_int(self.total_solutions, "total_solutions"))
        object.__setattr__(self, "total_nodes", require_non_negative_int(self.total_nodes, "total_nodes"))
        object.__setattr__(self, "total_edges", require_non_negative_int(self.total_edges, "total_edges"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConstraintClosureReport(ContractRecord):
    """Final closure report for constraint runtime lifecycle."""

    report_id: str = ""
    tenant_id: str = ""
    total_constraints: int = 0
    total_problems: int = 0
    total_solutions: int = 0
    total_assignments: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_constraints", require_non_negative_int(self.total_constraints, "total_constraints"))
        object.__setattr__(self, "total_problems", require_non_negative_int(self.total_problems, "total_problems"))
        object.__setattr__(self, "total_solutions", require_non_negative_int(self.total_solutions, "total_solutions"))
        object.__setattr__(self, "total_assignments", require_non_negative_int(self.total_assignments, "total_assignments"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
