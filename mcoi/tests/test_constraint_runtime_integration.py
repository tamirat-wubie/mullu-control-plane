"""Comprehensive tests for ConstraintRuntimeIntegration.

Tests cover: construction, surface-specific solve methods, memory mesh attachment,
graph attachment, multi-tenant, event emission, and end-to-end workflows.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.constraint_runtime import (
    AlgorithmKind,
    AssignmentStrategy,
    ConstraintKind,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.constraint_runtime import ConstraintRuntimeEngine
from mcoi_runtime.core.constraint_runtime_integration import ConstraintRuntimeIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
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
def mem():
    return MemoryMeshEngine()


@pytest.fixture()
def constraint_engine(es, clock):
    return ConstraintRuntimeEngine(es, clock=clock)


@pytest.fixture()
def integration(constraint_engine, es, mem):
    return ConstraintRuntimeIntegration(constraint_engine, es, mem)


# ===================================================================
# Construction Tests
# ===================================================================


class TestConstruction:
    def test_valid_construction(self, constraint_engine, es, mem):
        integ = ConstraintRuntimeIntegration(constraint_engine, es, mem)
        assert integ is not None

    def test_invalid_constraint_engine_rejected(self, es, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            ConstraintRuntimeIntegration("not_engine", es, mem)

    def test_invalid_event_spine_rejected(self, constraint_engine, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            ConstraintRuntimeIntegration(constraint_engine, "not_es", mem)

    def test_invalid_memory_engine_rejected(self, constraint_engine, es):
        with pytest.raises(RuntimeCoreInvariantError):
            ConstraintRuntimeIntegration(constraint_engine, es, "not_mem")

    def test_none_constraint_engine_rejected(self, es, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            ConstraintRuntimeIntegration(None, es, mem)

    def test_none_event_spine_rejected(self, constraint_engine, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            ConstraintRuntimeIntegration(constraint_engine, None, mem)

    def test_none_memory_engine_rejected(self, constraint_engine, es):
        with pytest.raises(RuntimeCoreInvariantError):
            ConstraintRuntimeIntegration(constraint_engine, es, None)


# ===================================================================
# Orchestration Tests
# ===================================================================


class TestOrchestration:
    def test_solve_for_orchestration(self, integration):
        result = integration.solve_for_orchestration("t-1", "plan-1")
        assert isinstance(result, dict)
        assert result["source_type"] == "orchestration"
        assert result["status"] == "solved"
        assert result["tenant_id"] == "t-1"

    def test_orchestration_creates_problem(self, integration, constraint_engine):
        integration.solve_for_orchestration("t-1", "plan-1")
        assert constraint_engine.problem_count == 1

    def test_orchestration_creates_constraint(self, integration, constraint_engine):
        integration.solve_for_orchestration("t-1", "plan-1")
        assert constraint_engine.constraint_count == 1

    def test_orchestration_creates_solution(self, integration, constraint_engine):
        integration.solve_for_orchestration("t-1", "plan-1")
        assert constraint_engine.solution_count == 1

    def test_orchestration_emits_event(self, integration, es):
        before = es.event_count
        integration.solve_for_orchestration("t-1", "plan-1")
        assert es.event_count > before


# ===================================================================
# Service Routing Tests
# ===================================================================


class TestServiceRouting:
    def test_solve_for_service_routing(self, integration):
        result = integration.solve_for_service_routing("t-1", "svc-1")
        assert result["source_type"] == "service_routing"
        assert result["status"] == "solved"


# ===================================================================
# Workforce Assignment Tests
# ===================================================================


class TestWorkforceAssignment:
    def test_solve_for_workforce_assignment(self, integration):
        result = integration.solve_for_workforce_assignment("t-1", "wf-1")
        assert result["source_type"] == "workforce_assignment"
        assert result["status"] == "solved"


# ===================================================================
# Release Planning Tests
# ===================================================================


class TestReleasePlanning:
    def test_solve_for_release_planning(self, integration):
        result = integration.solve_for_release_planning("t-1", "rel-1")
        assert result["source_type"] == "release_planning"
        assert result["status"] == "solved"


# ===================================================================
# Factory Scheduling Tests
# ===================================================================


class TestFactoryScheduling:
    def test_solve_for_factory_scheduling(self, integration):
        result = integration.solve_for_factory_scheduling("t-1", "fac-1")
        assert result["source_type"] == "factory_scheduling"
        assert result["status"] == "solved"


# ===================================================================
# Continuity Recovery Tests
# ===================================================================


class TestContinuityRecovery:
    def test_solve_for_continuity_recovery(self, integration):
        result = integration.solve_for_continuity_recovery("t-1", "cont-1")
        assert result["source_type"] == "continuity_recovery"
        assert result["status"] == "solved"


# ===================================================================
# Memory Mesh Attachment Tests
# ===================================================================


class TestMemoryMeshAttachment:
    def test_attach_to_memory_mesh(self, integration):
        record = integration.attach_constraint_state_to_memory_mesh("scope-1")
        assert isinstance(record, MemoryRecord)
        assert record.title == "Constraint state"
        assert "scope-1" not in record.title
        assert "constraint" in record.tags
        assert "algorithm" in record.tags
        assert "solver" in record.tags

    def test_memory_content(self, integration, constraint_engine):
        # Populate some state first
        integration.solve_for_orchestration("t-1", "plan-1")
        record = integration.attach_constraint_state_to_memory_mesh("scope-1")
        content = dict(record.content)
        assert content["total_constraints"] == 1
        assert content["total_problems"] == 1
        assert content["total_solutions"] == 1

    def test_memory_emits_event(self, integration, es):
        before = es.event_count
        integration.attach_constraint_state_to_memory_mesh("scope-1")
        assert es.event_count > before


# ===================================================================
# Graph Attachment Tests
# ===================================================================


class TestGraphAttachment:
    def test_attach_to_graph(self, integration):
        result = integration.attach_constraint_state_to_graph("scope-1")
        assert isinstance(result, dict)
        assert "total_constraints" in result
        assert result["scope_ref_id"] == "scope-1"

    def test_graph_content_reflects_state(self, integration):
        integration.solve_for_orchestration("t-1", "plan-1")
        result = integration.attach_constraint_state_to_graph("scope-1")
        assert result["total_constraints"] == 1
        assert result["total_problems"] == 1
        assert result["total_solutions"] == 1


# ===================================================================
# Multi-Tenant Tests
# ===================================================================


class TestMultiTenant:
    def test_multiple_tenants(self, integration):
        r1 = integration.solve_for_orchestration("t-1", "plan-1")
        r2 = integration.solve_for_orchestration("t-2", "plan-2")
        assert r1["tenant_id"] == "t-1"
        assert r2["tenant_id"] == "t-2"
        assert r1["problem_id"] != r2["problem_id"]


# ===================================================================
# End-to-End Workflow Tests
# ===================================================================


class TestEndToEnd:
    def test_full_workflow(self, integration, constraint_engine, mem):
        # Solve multiple surfaces
        integration.solve_for_orchestration("t-1", "plan-1")
        integration.solve_for_service_routing("t-1", "svc-1")
        integration.solve_for_workforce_assignment("t-1", "wf-1")

        # Attach to memory
        record = integration.attach_constraint_state_to_memory_mesh("full-scope")
        content = dict(record.content)
        assert content["total_constraints"] == 3
        assert content["total_problems"] == 3
        assert content["total_solutions"] == 3

        # Attach to graph
        graph_data = integration.attach_constraint_state_to_graph("full-scope")
        assert graph_data["total_constraints"] == 3
