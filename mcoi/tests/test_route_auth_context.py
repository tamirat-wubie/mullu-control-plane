"""Route authenticated-actor binding tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers.auth_context import bind_claimed_actor
from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers.ops.config import (
    ConfigRollbackRequest,
    ConfigUpdateRequest,
    rollback_config,
    update_config,
)


def _request(context: dict[str, Any] | None = None) -> Any:
    return SimpleNamespace(
        state=SimpleNamespace(governance_context=context if context is not None else {})
    )


def test_bind_claimed_actor_replaces_default_with_authenticated_subject() -> None:
    request = _request({"authenticated_subject": "operator-a"})

    actor = bind_claimed_actor(request, "api", default_claims=("api",))

    assert actor == "operator-a"


def test_bind_claimed_actor_rejects_explicit_mismatch() -> None:
    request = _request({"authenticated_subject": "operator-a"})

    with pytest.raises(HTTPException) as exc_info:
        bind_claimed_actor(request, "operator-b")

    detail = exc_info.value.detail
    assert exc_info.value.status_code == 403
    assert detail["governed"] is True
    assert detail["error_code"] == "actor_identity_mismatch"
    assert "operator-b" not in str(detail)


def test_config_update_uses_authenticated_actor_for_default_applied_by() -> None:
    original_store = dict(deps._store)
    metrics = _Metrics()
    config_manager = _ConfigManager()
    audit_trail = _AuditTrail()
    event_bus = _EventBus()
    deps._store.clear()
    deps._store.update(
        {
            "metrics": metrics,
            "config_manager": config_manager,
            "audit_trail": audit_trail,
            "event_bus": event_bus,
        }
    )
    try:
        result = update_config(
            ConfigUpdateRequest(changes={"feature": True}),
            _request({"authenticated_subject": "operator-a"}),
        )
    finally:
        deps._store.clear()
        deps._store.update(original_store)

    assert result["success"] is True
    assert config_manager.updated_by == "operator-a"
    assert audit_trail.records[0]["actor_id"] == "operator-a"
    assert event_bus.events[0]["event_type"] == "config.updated"
    assert metrics.counts["requests_governed"] == 1


def test_config_update_rejects_authenticated_actor_mismatch() -> None:
    original_store = dict(deps._store)
    deps._store.clear()
    deps._store.update(
        {
            "metrics": _Metrics(),
            "config_manager": _ConfigManager(),
            "audit_trail": _AuditTrail(),
            "event_bus": _EventBus(),
        }
    )
    try:
        with pytest.raises(HTTPException) as exc_info:
            update_config(
                ConfigUpdateRequest(changes={"feature": True}, applied_by="operator-b"),
                _request({"authenticated_subject": "operator-a"}),
            )
    finally:
        deps._store.clear()
        deps._store.update(original_store)

    detail = exc_info.value.detail
    assert exc_info.value.status_code == 403
    assert detail["error_code"] == "config_actor_identity_mismatch"
    assert detail["governed"] is True


def test_config_rollback_uses_authenticated_actor_for_default_applied_by() -> None:
    original_store = dict(deps._store)
    metrics = _Metrics()
    config_manager = _ConfigManager()
    audit_trail = _AuditTrail()
    deps._store.clear()
    deps._store.update(
        {
            "metrics": metrics,
            "config_manager": config_manager,
            "audit_trail": audit_trail,
            "event_bus": _EventBus(),
        }
    )
    try:
        result = rollback_config(
            ConfigRollbackRequest(to_version=1),
            _request({"authenticated_subject": "operator-a"}),
        )
    finally:
        deps._store.clear()
        deps._store.update(original_store)

    assert result["success"] is True
    assert config_manager.rolled_back_by == "operator-a"
    assert audit_trail.records[0]["actor_id"] == "operator-a"
    assert metrics.counts["requests_governed"] == 1


class _Metrics:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def inc(self, name: str, value: int = 1) -> None:
        self.counts[name] = self.counts.get(name, 0) + value


class _ConfigResult:
    def __init__(self, *, version: int = 2, previous_version: int = 1) -> None:
        self.success = True
        self.version = version
        self.previous_version = previous_version
        self.error = ""


class _ConfigManager:
    def __init__(self) -> None:
        self.updated_by = ""
        self.rolled_back_by = ""

    def update(
        self,
        changes: dict[str, Any],
        *,
        applied_by: str,
        description: str = "",
    ) -> _ConfigResult:
        assert changes == {"feature": True}
        assert isinstance(description, str)
        self.updated_by = applied_by
        return _ConfigResult()

    def rollback(self, to_version: int, *, applied_by: str) -> _ConfigResult:
        assert to_version == 1
        self.rolled_back_by = applied_by
        return _ConfigResult(version=3, previous_version=2)


class _AuditTrail:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(self, **kwargs: Any) -> None:
        self.records.append(kwargs)


class _EventBus:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def publish(self, event_type: str, *, source: str, payload: dict[str, Any]) -> None:
        self.events.append(
            {"event_type": event_type, "source": source, "payload": payload}
        )
