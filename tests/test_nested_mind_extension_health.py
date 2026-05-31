"""Tests for nested-mind optional extension health posture.

Purpose: verify operator-safe health read models for nested-mind connector,
observation planning, and live observation submission wiring.
Governance scope: optional integration observability without host path, base
URL, or credential disclosure.
Dependencies: health router dependency container.
Invariants: missing bootstraps are explicit, configured bootstraps expose only
bounded booleans and state labels, and secrets never enter the read model.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers.health import extension_health


def _with_dependency_store(values: dict[str, Any]):
    original = dict(deps._store)
    deps._store.clear()
    deps._store.update(values)
    return original


def _restore_dependency_store(original: dict[str, Any]) -> None:
    deps._store.clear()
    deps._store.update(original)


def test_nested_mind_extension_health_reports_unregistered_posture() -> None:
    original = _with_dependency_store({})
    try:
        health = extension_health()
    finally:
        _restore_dependency_store(original)

    extensions = health["extensions"]
    assert extensions["nested_mind"]["registered"] is False
    assert extensions["nested_mind"]["state"] == "unregistered"
    assert extensions["nested_mind_observation_bridge"]["registered"] is False
    assert extensions["nested_mind_observation_submitter"]["registered"] is False


def test_nested_mind_extension_health_reports_safe_configured_posture() -> None:
    original = _with_dependency_store(
        {
            "nested_mind_bootstrap": SimpleNamespace(
                connector=object(),
                enabled=True,
                base_url="https://nested.example/api",
                credential_configured=True,
            ),
            "nested_mind_observation_bridge_bootstrap": SimpleNamespace(
                planner=object(),
                enabled=True,
            ),
            "nested_mind_observation_submitter_bootstrap": SimpleNamespace(
                submitter=object(),
                enabled=True,
                base_url="https://nested.example/api",
                credential_configured=True,
            ),
        }
    )
    try:
        health = extension_health()
    finally:
        _restore_dependency_store(original)

    extensions = health["extensions"]
    assert extensions["nested_mind"]["registered"] is True
    assert extensions["nested_mind"]["active"] is True
    assert extensions["nested_mind"]["base_url_configured"] is True
    assert extensions["nested_mind"]["credential_configured"] is True
    assert extensions["nested_mind_observation_bridge"]["planner_configured"] is True
    assert extensions["nested_mind_observation_submitter"]["active"] is True
    assert "nested.example" not in repr(health)
    assert "token" not in repr(health).lower()
