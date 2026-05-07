"""Dependency container helpers for the governed server.

Purpose: isolate dependency registration and late subsystem wiring from HTTP bootstrap.
Governance scope: [OCE, CDCV, UWMA]
Dependencies: router dependency container and already-built subsystem instances.
Invariants: registered dependency keys remain stable, late-bound runtime bridges remain deterministic.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def register_dependency_groups(deps: Any, *groups: Mapping[str, Any]) -> None:
    """Register one or more dependency groups into the shared deps container."""
    for group in groups:
        for name, value in group.items():
            deps.set(name, value)


def wire_runtime_dependencies(
    *,
    guard_chain: Any,
    audit_trail: Any,
    scheduler: Any,
    connector_framework: Any,
    policy_sandbox: Any,
    explanation_engine: Any,
) -> None:
    """Wire late-bound runtime bridges that depend on the final guard chain."""
    scheduler._guard_chain = guard_chain
    scheduler._audit_trail = audit_trail
    connector_framework._guard_chain = guard_chain
    connector_framework._audit_trail = audit_trail
    policy_sandbox._guard_chain = guard_chain
    explanation_engine._audit_trail = audit_trail
    explanation_engine._guard_chain = guard_chain
