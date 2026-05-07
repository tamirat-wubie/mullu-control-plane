"""Comprehensive tests for the ConstraintRuntimeEngine.

Tests cover: construction, constraint CRUD, problem lifecycle, solutions,
graph nodes/edges, shortest path, topological sort, schedule slots,
assignments, dependencies, critical path, violation detection,
snapshots, state_hash, and replay determinism.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.constraint_runtime import (
    AlgorithmKind,
    AssignmentRecord,
    AssignmentStrategy,
    ConstraintDefinition,
    ConstraintKind,
    ConstraintSnapshot,
    DependencyChain,
    GraphEdge,
    GraphNode,
    ScheduleSlot,
    SolveStatus,
    SolverProblem,
    SolverSolution,
)
from mcoi_runtime.core.constraint_runtime import ConstraintRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture()
def clock():
    return FixedClock("2026-01-01T00:00:00+00:00")


@pytest.fixture()
def es():
    return EventSpineEngine()


@pytest.fixture()
def engine(es, clock):
    return ConstraintRuntimeEngine(es, clock=clock)


# ===================================================================
# Construction Tests
# ===================================================================


class TestEngineConstruction:
    def test_valid_construction(self, es, clock):
        eng = ConstraintRuntimeEngine(es, clock=clock)
        assert eng.constraint_count == 0

    def test_construction_without_clock(self, es):
        eng = ConstraintRuntimeEngine(es)
        assert eng.constraint_count == 0

    def test_invalid_event_spine_rejected(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ConstraintRuntimeEngine("not_an_es")

    def test_initial_counts_zero(self, engine):
        assert engine.constraint_count == 0
        assert engine.problem_count == 0
        assert engine.solution_count == 0
        assert engine.node_count == 0
        assert engine.edge_count == 0
        assert engine.slot_count == 0
        assert engine.assignment_count == 0
        assert engine.dependency_count == 0
        assert engine.violation_count == 0


# ===================================================================
# Constraint Tests
# ===================================================================


class TestConstraints:
    def test_add_constraint(self, engine):
        c = engine.add_constraint("c-1", "t-1", ConstraintKind.EQUALITY, "x == 5")
        assert isinstance(c, ConstraintDefinition)
        assert c.constraint_id == "c-1"
        assert engine.constraint_count == 1

    def test_get_constraint(self, engine):
        engine.add_constraint("c-1", "t-1", ConstraintKind.EQUALITY, "x == 5")
        c = engine.get_constraint("c-1")
        assert c.constraint_id == "c-1"

    def test_get_unknown_constraint_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.get_constraint("unknown")

    def test_duplicate_constraint_raises(self, engine):
        engine.add_constraint("c-1", "t-1", ConstraintKind.EQUALITY, "x == 5")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.add_constraint("c-1", "t-1", ConstraintKind.EQUALITY, "x == 5")

    def test_constraints_for_tenant(self, engine):
        engine.add_constraint("c-1", "t-1", ConstraintKind.EQUALITY, "x == 5")
        engine.add_constraint("c-2", "t-2", ConstraintKind.INEQUALITY, "y > 0")
        result = engine.constraints_for_tenant("t-1")
        assert len(result) == 1
        assert result[0].constraint_id == "c-1"


# ===================================================================
# Problem Lifecycle Tests
# ===================================================================


class TestProblemLifecycle:
    def test_create_problem(self, engine):
        p = engine.create_problem("p-1", "t-1", AlgorithmKind.GRAPH_SEARCH)
        assert isinstance(p, SolverProblem)
        assert p.status == SolveStatus.PENDING
        assert engine.problem_count == 1

    def test_start_problem(self, engine):
        engine.create_problem("p-1", "t-1", AlgorithmKind.GRAPH_SEARCH)
        p = engine.start_problem("p-1")
        assert p.status == SolveStatus.RUNNING

    def test_start_non_pending_raises(self, engine):
        engine.create_problem("p-1", "t-1", AlgorithmKind.GRAPH_SEARCH)
        engine.start_problem("p-1")
        with pytest.raises(RuntimeCoreInvariantError, match="^problem must be pending before start$") as exc_info:
            engine.start_problem("p-1")
        assert SolveStatus.RUNNING.value not in str(exc_info.value)

    def test_solve_problem(self, engine):
        engine.create_problem("p-1", "t-1", AlgorithmKind.GRAPH_SEARCH)
        engine.start_problem("p-1")
        sol = engine.solve_problem("s-1", "t-1", "p-1", objective_value=42.0)
        assert isinstance(sol, SolverSolution)
        assert sol.status == SolveStatus.SOLVED
        assert engine.solution_count == 1

    def test_fail_problem(self, engine):
        engine.create_problem("p-1", "t-1", AlgorithmKind.GRAPH_SEARCH)
        p = engine.fail_problem("p-1")
        assert p.status == SolveStatus.FAILED

    def test_timeout_problem(self, engine):
        engine.create_problem("p-1", "t-1", AlgorithmKind.GRAPH_SEARCH)
        p = engine.timeout_problem("p-1")
        assert p.status == SolveStatus.TIMEOUT

    def test_duplicate_problem_raises(self, engine):
        engine.create_problem("p-1", "t-1", AlgorithmKind.GRAPH_SEARCH)
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.create_problem("p-1", "t-1", AlgorithmKind.GRAPH_SEARCH)
        assert "p-1" not in str(exc_info.value)

    def test_solve_unknown_problem_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.solve_problem("s-1", "t-1", "unknown")
        assert "unknown" not in str(exc_info.value)


# ===================================================================
# Graph Node/Edge Tests
# ===================================================================


class TestGraph:
    def test_add_node(self, engine):
        n = engine.add_graph_node("n-1", "t-1", "Start")
        assert isinstance(n, GraphNode)
        assert engine.node_count == 1

    def test_add_edge(self, engine):
        engine.add_graph_node("n-1", "t-1", "Start")
        engine.add_graph_node("n-2", "t-1", "End")
        e = engine.add_graph_edge("e-1", "t-1", "n-1", "n-2")
        assert isinstance(e, GraphEdge)
        assert engine.edge_count == 1

    def test_add_edge_missing_from_node_raises(self, engine):
        engine.add_graph_node("n-2", "t-1", "End")
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.add_graph_edge("e-1", "t-1", "missing", "n-2")
        assert "missing" not in str(exc_info.value)

    def test_add_edge_missing_to_node_raises(self, engine):
        engine.add_graph_node("n-1", "t-1", "Start")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.add_graph_edge("e-1", "t-1", "n-1", "missing")

    def test_duplicate_node_raises(self, engine):
        engine.add_graph_node("n-1", "t-1", "Start")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.add_graph_node("n-1", "t-1", "Start")

    def test_duplicate_edge_raises(self, engine):
        engine.add_graph_node("n-1", "t-1", "A")
        engine.add_graph_node("n-2", "t-1", "B")
        engine.add_graph_edge("e-1", "t-1", "n-1", "n-2")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.add_graph_edge("e-1", "t-1", "n-1", "n-2")


# ===================================================================
# Shortest Path Tests
# ===================================================================


class TestShortestPath:
    def test_simple_path(self, engine):
        engine.add_graph_node("a", "t-1", "A")
        engine.add_graph_node("b", "t-1", "B")
        engine.add_graph_node("c", "t-1", "C")
        engine.add_graph_edge("e1", "t-1", "a", "b")
        engine.add_graph_edge("e2", "t-1", "b", "c")
        path = engine.find_shortest_path("t-1", "a", "c")
        assert path == ["a", "b", "c"]

    def test_unreachable_returns_empty(self, engine):
        engine.add_graph_node("a", "t-1", "A")
        engine.add_graph_node("b", "t-1", "B")
        path = engine.find_shortest_path("t-1", "a", "b")
        assert path == []

    def test_unknown_node_returns_empty(self, engine):
        path = engine.find_shortest_path("t-1", "missing", "also_missing")
        assert path == []

    def test_weighted_dijkstra_path(self, engine):
        engine.add_graph_node("a", "t-1", "A")
        engine.add_graph_node("b", "t-1", "B")
        engine.add_graph_node("c", "t-1", "C")
        # Direct path a->c with high weight
        engine.add_graph_edge("e1", "t-1", "a", "c", weight=10.0)
        # Indirect path a->b->c with lower total weight
        engine.add_graph_edge("e2", "t-1", "a", "b", weight=2.0)
        engine.add_graph_edge("e3", "t-1", "b", "c", weight=3.0)
        path = engine.find_shortest_path("t-1", "a", "c")
        assert path == ["a", "b", "c"]

    def test_same_start_and_end(self, engine):
        engine.add_graph_node("a", "t-1", "A")
        path = engine.find_shortest_path("t-1", "a", "a")
        assert path == ["a"]


# ===================================================================
# Topological Sort Tests
# ===================================================================


class TestTopologicalSort:
    def test_simple_topo_sort(self, engine):
        engine.add_graph_node("a", "t-1", "A")
        engine.add_graph_node("b", "t-1", "B")
        engine.add_graph_node("c", "t-1", "C")
        engine.add_graph_edge("e1", "t-1", "a", "b")
        engine.add_graph_edge("e2", "t-1", "b", "c")
        result = engine.topological_sort("t-1")
        assert result.index("a") < result.index("b") < result.index("c")

    def test_cycle_raises(self, engine):
        engine.add_graph_node("a", "t-1", "A")
        engine.add_graph_node("b", "t-1", "B")
        engine.add_graph_edge("e1", "t-1", "a", "b")
        engine.add_graph_edge("e2", "t-1", "b", "a")
        with pytest.raises(RuntimeCoreInvariantError, match="Cycle"):
            engine.topological_sort("t-1")

    def test_empty_graph_returns_empty(self, engine):
        result = engine.topological_sort("t-1")
        assert result == ()


# ===================================================================
# Schedule Slot Tests
# ===================================================================


class TestScheduleSlots:
    def test_create_slot(self, engine):
        s = engine.create_schedule_slot(
            "sl-1", "t-1", "r-1",
            "2025-06-01T08:00:00+00:00", "2025-06-01T09:00:00+00:00",
        )
        assert isinstance(s, ScheduleSlot)
        assert engine.slot_count == 1

    def test_duplicate_slot_raises(self, engine):
        engine.create_schedule_slot(
            "sl-1", "t-1", "r-1",
            "2025-06-01T08:00:00+00:00", "2025-06-01T09:00:00+00:00",
        )
        with pytest.raises(RuntimeCoreInvariantError):
            engine.create_schedule_slot(
                "sl-1", "t-1", "r-1",
                "2025-06-01T10:00:00+00:00", "2025-06-01T11:00:00+00:00",
            )


# ===================================================================
# Assignment Tests
# ===================================================================


class TestAssignments:
    def test_assign_resource(self, engine):
        a = engine.assign_resource("a-1", "t-1", "r-1", "task-1")
        assert isinstance(a, AssignmentRecord)
        assert a.strategy == AssignmentStrategy.GREEDY
        assert engine.assignment_count == 1

    def test_assign_with_strategy(self, engine):
        a = engine.assign_resource(
            "a-1", "t-1", "r-1", "task-1",
            strategy=AssignmentStrategy.MIN_COST, cost=5.0,
        )
        assert a.strategy == AssignmentStrategy.MIN_COST
        assert a.cost == 5.0

    def test_duplicate_assignment_raises(self, engine):
        engine.assign_resource("a-1", "t-1", "r-1", "task-1")
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.assign_resource("a-1", "t-1", "r-1", "task-2")
        assert "a-1" not in str(exc_info.value)


# ===================================================================
# Dependency / Critical Path Tests
# ===================================================================


class TestDependencies:
    def test_add_dependency(self, engine):
        d = engine.add_dependency("d-1", "t-1", "src-1", "tgt-1", lag=2)
        assert isinstance(d, DependencyChain)
        assert engine.dependency_count == 1

    def test_duplicate_dependency_raises(self, engine):
        engine.add_dependency("d-1", "t-1", "src-1", "tgt-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.add_dependency("d-1", "t-1", "src-1", "tgt-1")

    def test_critical_path_simple(self, engine):
        engine.add_dependency("d-1", "t-1", "A", "B", lag=1)
        engine.add_dependency("d-2", "t-1", "B", "C", lag=2)
        engine.add_dependency("d-3", "t-1", "A", "C", lag=0)
        path = engine.critical_path("t-1")
        # The A->B->C path has total weight 1+1+2+1 = 5 vs A->C = 0+1 = 1
        assert "d-1" in path
        assert "d-2" in path

    def test_critical_path_empty(self, engine):
        path = engine.critical_path("t-1")
        assert path == ()


# ===================================================================
# Violation Detection Tests
# ===================================================================


class TestViolationDetection:
    def test_unsolved_problem_violation(self, engine):
        engine.create_problem("p-1", "t-1", AlgorithmKind.GRAPH_SEARCH)
        violations = engine.detect_constraint_violations("t-1")
        assert len(violations) == 1
        assert violations[0]["operation"] == "unsolved_problem"
        assert violations[0]["reason"] == "Problem has no solution"
        assert "p-1" not in violations[0]["reason"]

    def test_unsolved_problem_idempotent(self, engine):
        engine.create_problem("p-1", "t-1", AlgorithmKind.GRAPH_SEARCH)
        v1 = engine.detect_constraint_violations("t-1")
        v2 = engine.detect_constraint_violations("t-1")
        assert len(v1) == 1
        assert len(v2) == 0  # idempotent

    def test_solved_problem_no_violation(self, engine):
        engine.create_problem("p-1", "t-1", AlgorithmKind.GRAPH_SEARCH)
        engine.start_problem("p-1")
        engine.solve_problem("s-1", "t-1", "p-1")
        violations = engine.detect_constraint_violations("t-1")
        assert len(violations) == 0

    def test_cycle_violation(self, engine):
        engine.add_dependency("d-1", "t-1", "A", "B")
        engine.add_dependency("d-2", "t-1", "B", "A")
        violations = engine.detect_constraint_violations("t-1")
        cycle_violations = [v for v in violations if v["operation"] == "cycle_in_dependencies"]
        assert len(cycle_violations) == 1
        assert cycle_violations[0]["reason"] == "Circular dependency detected"
        assert "t-1" not in cycle_violations[0]["reason"]

    def test_schedule_conflict_violation(self, engine):
        engine.create_schedule_slot(
            "sl-1", "t-1", "r-1",
            "2025-06-01T08:00:00+00:00", "2025-06-01T10:00:00+00:00",
        )
        engine.create_schedule_slot(
            "sl-2", "t-1", "r-1",
            "2025-06-01T09:00:00+00:00", "2025-06-01T11:00:00+00:00",
        )
        violations = engine.detect_constraint_violations("t-1")
        conflict_violations = [v for v in violations if v["operation"] == "schedule_conflict"]
        assert len(conflict_violations) == 1
        assert conflict_violations[0]["reason"] == "Schedule conflict detected for resource"
        assert "sl-1" not in conflict_violations[0]["reason"]
        assert "r-1" not in conflict_violations[0]["reason"]

    def test_no_conflict_for_different_resources(self, engine):
        engine.create_schedule_slot(
            "sl-1", "t-1", "r-1",
            "2025-06-01T08:00:00+00:00", "2025-06-01T10:00:00+00:00",
        )
        engine.create_schedule_slot(
            "sl-2", "t-1", "r-2",
            "2025-06-01T08:00:00+00:00", "2025-06-01T10:00:00+00:00",
        )
        violations = engine.detect_constraint_violations("t-1")
        conflict_violations = [v for v in violations if v["operation"] == "schedule_conflict"]
        assert len(conflict_violations) == 0


# ===================================================================
# Snapshot / State Hash Tests
# ===================================================================


class TestSnapshotAndHash:
    def test_constraint_snapshot(self, engine):
        engine.add_constraint("c-1", "t-1", ConstraintKind.EQUALITY, "x == 5")
        snap = engine.constraint_snapshot("snap-1", "t-1")
        assert isinstance(snap, ConstraintSnapshot)
        assert snap.total_constraints == 1

    def test_engine_snapshot(self, engine):
        engine.add_constraint("c-1", "t-1", ConstraintKind.EQUALITY, "x == 5")
        snap = engine.snapshot()
        assert "constraints" in snap
        assert "_state_hash" in snap

    def test_state_hash_deterministic(self, engine):
        engine.add_constraint("c-1", "t-1", ConstraintKind.EQUALITY, "x == 5")
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_state_hash_changes_on_mutation(self, engine):
        h1 = engine.state_hash()
        engine.add_constraint("c-1", "t-1", ConstraintKind.EQUALITY, "x == 5")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_collections(self, engine):
        cols = engine._collections()
        assert "constraints" in cols
        assert "problems" in cols
        assert "solutions" in cols
        assert "nodes" in cols
        assert "edges" in cols
        assert "slots" in cols
        assert "assignments" in cols
        assert "dependencies" in cols
        assert "violations" in cols


# ===================================================================
# Event Emission Tests
# ===================================================================


class TestEventEmission:
    def test_add_constraint_emits_event(self, engine, es):
        before = es.event_count
        engine.add_constraint("c-1", "t-1", ConstraintKind.EQUALITY, "x == 5")
        assert es.event_count > before

    def test_problem_lifecycle_emits_events(self, engine, es):
        before = es.event_count
        engine.create_problem("p-1", "t-1", AlgorithmKind.GRAPH_SEARCH)
        engine.start_problem("p-1")
        engine.solve_problem("s-1", "t-1", "p-1")
        assert es.event_count >= before + 3
