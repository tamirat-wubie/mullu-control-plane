"""Comprehensive tests for constraint / algorithm / solver runtime contracts.

Tests cover: enum membership, dataclass construction, validation failures,
frozen immutability, metadata freezing, to_dict() serialization, to_json_dict(),
to_json(), and edge cases for every contract type.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.constraint_runtime import (
    AlgorithmKind,
    AssignmentRecord,
    AssignmentStrategy,
    ConstraintClosureReport,
    ConstraintDefinition,
    ConstraintKind,
    ConstraintSnapshot,
    DependencyChain,
    GraphEdge,
    GraphNode,
    GraphTraversal,
    PriorityMode,
    ScheduleSlot,
    SolveStatus,
    SolverProblem,
    SolverSolution,
)


# ===================================================================
# Helpers: valid kwargs for each dataclass
# ===================================================================

TS = "2025-06-01T00:00:00+00:00"


def _constraint_definition_kw(**overrides):
    base = dict(
        constraint_id="c-1", tenant_id="t-1", kind=ConstraintKind.EQUALITY,
        expression="x + y == 10", variable_refs="x,y", priority=0,
        created_at=TS,
    )
    base.update(overrides)
    return base


def _solver_problem_kw(**overrides):
    base = dict(
        problem_id="p-1", tenant_id="t-1",
        algorithm=AlgorithmKind.CONSTRAINT_SAT,
        constraint_count=5, variable_count=3,
        status=SolveStatus.PENDING, created_at=TS,
    )
    base.update(overrides)
    return base


def _solver_solution_kw(**overrides):
    base = dict(
        solution_id="s-1", tenant_id="t-1", problem_ref="p-1",
        status=SolveStatus.SOLVED, objective_value=42.5,
        iterations=100, duration_ms=250.0, solved_at=TS,
    )
    base.update(overrides)
    return base


def _graph_node_kw(**overrides):
    base = dict(
        node_id="n-1", tenant_id="t-1", label="Start",
        weight=1.0, created_at=TS,
    )
    base.update(overrides)
    return base


def _graph_edge_kw(**overrides):
    base = dict(
        edge_id="e-1", tenant_id="t-1", from_node="n-1",
        to_node="n-2", weight=2.5, created_at=TS,
    )
    base.update(overrides)
    return base


def _schedule_slot_kw(**overrides):
    base = dict(
        slot_id="sl-1", tenant_id="t-1", resource_ref="r-1",
        start_at="2025-06-01T08:00:00+00:00",
        end_at="2025-06-01T09:00:00+00:00",
        priority=1, created_at=TS,
    )
    base.update(overrides)
    return base


def _assignment_record_kw(**overrides):
    base = dict(
        assignment_id="a-1", tenant_id="t-1", resource_ref="r-1",
        task_ref="task-1", strategy=AssignmentStrategy.GREEDY,
        cost=10.0, created_at=TS,
    )
    base.update(overrides)
    return base


def _dependency_chain_kw(**overrides):
    base = dict(
        chain_id="d-1", tenant_id="t-1", source_ref="src-1",
        target_ref="tgt-1", lag=0, created_at=TS,
    )
    base.update(overrides)
    return base


def _constraint_snapshot_kw(**overrides):
    base = dict(
        snapshot_id="snap-1", tenant_id="t-1",
        total_constraints=5, total_problems=3, total_solutions=2,
        total_nodes=10, total_edges=8, total_violations=1,
        captured_at=TS,
    )
    base.update(overrides)
    return base


def _constraint_closure_report_kw(**overrides):
    base = dict(
        report_id="rpt-1", tenant_id="t-1",
        total_constraints=5, total_problems=3, total_solutions=2,
        total_assignments=4, total_violations=1,
        created_at=TS,
    )
    base.update(overrides)
    return base


# ===================================================================
# Enum Tests
# ===================================================================


class TestEnums:
    def test_algorithm_kind_members(self):
        assert len(AlgorithmKind) == 6
        assert AlgorithmKind.GRAPH_SEARCH.value == "graph_search"
        assert AlgorithmKind.CONSTRAINT_SAT.value == "constraint_sat"

    def test_solve_status_members(self):
        assert len(SolveStatus) == 6
        assert SolveStatus.PENDING.value == "pending"
        assert SolveStatus.FAILED.value == "failed"

    def test_constraint_kind_members(self):
        assert len(ConstraintKind) == 6
        assert ConstraintKind.EQUALITY.value == "equality"
        assert ConstraintKind.TEMPORAL.value == "temporal"

    def test_priority_mode_members(self):
        assert len(PriorityMode) == 5
        assert PriorityMode.FIFO.value == "fifo"
        assert PriorityMode.COST.value == "cost"

    def test_graph_traversal_members(self):
        assert len(GraphTraversal) == 5
        assert GraphTraversal.BFS.value == "bfs"
        assert GraphTraversal.TOPOLOGICAL.value == "topological"

    def test_assignment_strategy_members(self):
        assert len(AssignmentStrategy) == 4
        assert AssignmentStrategy.GREEDY.value == "greedy"
        assert AssignmentStrategy.ROUND_ROBIN.value == "round_robin"


# ===================================================================
# ConstraintDefinition Tests
# ===================================================================


class TestConstraintDefinition:
    def test_valid_construction(self):
        c = ConstraintDefinition(**_constraint_definition_kw())
        assert c.constraint_id == "c-1"
        assert c.kind == ConstraintKind.EQUALITY

    def test_empty_constraint_id_rejected(self):
        with pytest.raises(ValueError):
            ConstraintDefinition(**_constraint_definition_kw(constraint_id=""))

    def test_invalid_kind_rejected(self):
        with pytest.raises(ValueError):
            ConstraintDefinition(**_constraint_definition_kw(kind="not_a_kind"))

    def test_negative_priority_rejected(self):
        with pytest.raises(ValueError):
            ConstraintDefinition(**_constraint_definition_kw(priority=-1))

    def test_frozen(self):
        c = ConstraintDefinition(**_constraint_definition_kw())
        with pytest.raises(FrozenInstanceError):
            c.constraint_id = "changed"

    def test_metadata_frozen(self):
        c = ConstraintDefinition(**_constraint_definition_kw(metadata={"key": "val"}))
        assert isinstance(c.metadata, MappingProxyType)

    def test_to_dict(self):
        c = ConstraintDefinition(**_constraint_definition_kw())
        d = c.to_dict()
        assert d["constraint_id"] == "c-1"
        assert d["kind"] == ConstraintKind.EQUALITY

    def test_to_json_dict(self):
        c = ConstraintDefinition(**_constraint_definition_kw())
        d = c.to_json_dict()
        assert d["kind"] == "equality"

    def test_to_json(self):
        c = ConstraintDefinition(**_constraint_definition_kw())
        j = c.to_json()
        parsed = json.loads(j)
        assert parsed["constraint_id"] == "c-1"

    def test_empty_variable_refs_allowed(self):
        c = ConstraintDefinition(**_constraint_definition_kw(variable_refs=""))
        assert c.variable_refs == ""


# ===================================================================
# SolverProblem Tests
# ===================================================================


class TestSolverProblem:
    def test_valid_construction(self):
        p = SolverProblem(**_solver_problem_kw())
        assert p.problem_id == "p-1"
        assert p.status == SolveStatus.PENDING

    def test_empty_problem_id_rejected(self):
        with pytest.raises(ValueError):
            SolverProblem(**_solver_problem_kw(problem_id=""))

    def test_negative_constraint_count_rejected(self):
        with pytest.raises(ValueError):
            SolverProblem(**_solver_problem_kw(constraint_count=-1))

    def test_to_json_dict(self):
        p = SolverProblem(**_solver_problem_kw())
        d = p.to_json_dict()
        assert d["algorithm"] == "constraint_sat"
        assert d["status"] == "pending"


# ===================================================================
# SolverSolution Tests
# ===================================================================


class TestSolverSolution:
    def test_valid_construction(self):
        s = SolverSolution(**_solver_solution_kw())
        assert s.solution_id == "s-1"
        assert s.objective_value == 42.5

    def test_negative_objective_value_allowed(self):
        s = SolverSolution(**_solver_solution_kw(objective_value=-10.0))
        assert s.objective_value == -10.0

    def test_bool_objective_value_rejected(self):
        with pytest.raises(ValueError):
            SolverSolution(**_solver_solution_kw(objective_value=True))

    def test_negative_iterations_rejected(self):
        with pytest.raises(ValueError):
            SolverSolution(**_solver_solution_kw(iterations=-1))

    def test_negative_duration_rejected(self):
        with pytest.raises(ValueError):
            SolverSolution(**_solver_solution_kw(duration_ms=-1.0))

    def test_to_json(self):
        s = SolverSolution(**_solver_solution_kw())
        j = s.to_json()
        parsed = json.loads(j)
        assert parsed["objective_value"] == 42.5


# ===================================================================
# GraphNode Tests
# ===================================================================


class TestGraphNode:
    def test_valid_construction(self):
        n = GraphNode(**_graph_node_kw())
        assert n.node_id == "n-1"
        assert n.weight == 1.0

    def test_negative_weight_rejected(self):
        with pytest.raises(ValueError):
            GraphNode(**_graph_node_kw(weight=-0.5))

    def test_frozen(self):
        n = GraphNode(**_graph_node_kw())
        with pytest.raises(FrozenInstanceError):
            n.label = "changed"


# ===================================================================
# GraphEdge Tests
# ===================================================================


class TestGraphEdge:
    def test_valid_construction(self):
        e = GraphEdge(**_graph_edge_kw())
        assert e.edge_id == "e-1"
        assert e.weight == 2.5

    def test_empty_from_node_rejected(self):
        with pytest.raises(ValueError):
            GraphEdge(**_graph_edge_kw(from_node=""))


# ===================================================================
# ScheduleSlot Tests
# ===================================================================


class TestScheduleSlot:
    def test_valid_construction(self):
        s = ScheduleSlot(**_schedule_slot_kw())
        assert s.slot_id == "sl-1"

    def test_invalid_start_at_rejected(self):
        with pytest.raises(ValueError):
            ScheduleSlot(**_schedule_slot_kw(start_at="not-a-date"))


# ===================================================================
# AssignmentRecord Tests
# ===================================================================


class TestAssignmentRecord:
    def test_valid_construction(self):
        a = AssignmentRecord(**_assignment_record_kw())
        assert a.assignment_id == "a-1"
        assert a.strategy == AssignmentStrategy.GREEDY

    def test_invalid_strategy_rejected(self):
        with pytest.raises(ValueError):
            AssignmentRecord(**_assignment_record_kw(strategy="bad"))

    def test_negative_cost_rejected(self):
        with pytest.raises(ValueError):
            AssignmentRecord(**_assignment_record_kw(cost=-1.0))


# ===================================================================
# DependencyChain Tests
# ===================================================================


class TestDependencyChain:
    def test_valid_construction(self):
        d = DependencyChain(**_dependency_chain_kw())
        assert d.chain_id == "d-1"
        assert d.lag == 0

    def test_negative_lag_rejected(self):
        with pytest.raises(ValueError):
            DependencyChain(**_dependency_chain_kw(lag=-1))


# ===================================================================
# ConstraintSnapshot Tests
# ===================================================================


class TestConstraintSnapshot:
    def test_valid_construction(self):
        s = ConstraintSnapshot(**_constraint_snapshot_kw())
        assert s.snapshot_id == "snap-1"
        assert s.total_constraints == 5

    def test_negative_total_rejected(self):
        with pytest.raises(ValueError):
            ConstraintSnapshot(**_constraint_snapshot_kw(total_constraints=-1))

    def test_to_json_dict(self):
        s = ConstraintSnapshot(**_constraint_snapshot_kw())
        d = s.to_json_dict()
        assert d["total_nodes"] == 10


# ===================================================================
# ConstraintClosureReport Tests
# ===================================================================


class TestConstraintClosureReport:
    def test_valid_construction(self):
        r = ConstraintClosureReport(**_constraint_closure_report_kw())
        assert r.report_id == "rpt-1"
        assert r.total_assignments == 4

    def test_negative_total_rejected(self):
        with pytest.raises(ValueError):
            ConstraintClosureReport(**_constraint_closure_report_kw(total_violations=-1))

    def test_to_json(self):
        r = ConstraintClosureReport(**_constraint_closure_report_kw())
        j = r.to_json()
        parsed = json.loads(j)
        assert parsed["report_id"] == "rpt-1"
