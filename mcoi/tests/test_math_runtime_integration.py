"""Purpose: focused bounded-title tests for MathRuntimeIntegration.

Governance scope: verifies memory-mesh attachment does not reflect scope ids
through public titles while preserving separate scope witness state.
Dependencies: math runtime integration, event spine, memory mesh, fixed clock.
Invariants: memory title is bounded; scope_ref_id remains preserved.
"""

from __future__ import annotations

from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.math_runtime import MathRuntimeEngine
from mcoi_runtime.core.math_runtime_integration import MathRuntimeIntegration
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine


def test_attach_math_state_to_memory_mesh_title_is_bounded():
    spine = EventSpineEngine()
    engine = MathRuntimeEngine(spine, clock=FixedClock("2026-01-01T00:00:00+00:00"))
    memory = MemoryMeshEngine()
    integration = MathRuntimeIntegration(engine, spine, memory)

    record = integration.attach_math_state_to_memory_mesh("scope-1")

    assert record.title == "Math state"
    assert "scope-1" not in record.title
    assert record.scope_ref_id == "scope-1"
    assert memory.memory_count >= 1
