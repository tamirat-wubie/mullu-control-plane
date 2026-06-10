"""Shared production readiness checks for operator read models.

Purpose: expose one deterministic readiness-check source for readiness,
spatial governance, and console dashboard projections.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: application dependency registry.
Invariants:
  - Readiness checks are read-only.
  - Each subsystem check returns a boolean.
  - Dashboard and route projections cannot drift by using separate check sets.
"""

from __future__ import annotations

from mcoi_runtime.app.routers.deps import deps


def production_readiness_checks() -> dict[str, bool]:
    """Return bounded subsystem readiness checks used by operator read models."""
    return {
        "llm_bridge": deps.llm_bridge.invocation_count >= 0,
        "store": deps.store.ledger_count() >= 0,
        "audit_trail": deps.audit_trail.entry_count >= 0,
        "event_bus": deps.event_bus.event_count >= 0,
        "metrics": deps.metrics.counter("requests_total") >= 0,
        "config": deps.config_manager.version >= 1,
        "tool_registry": deps.tool_registry.tool_count >= 1,
        "model_router": deps.model_router.model_count >= 1,
        "plugins": deps.plugin_registry.count >= 1,
        "health_agg": deps.health_agg.component_count >= 1,
        "schema_validator": deps.schema_validator.count >= 1,
        "guard_chain": deps.guard_chain.guard_count >= 1,
    }
