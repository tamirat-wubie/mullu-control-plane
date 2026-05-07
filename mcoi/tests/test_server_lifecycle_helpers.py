"""Purpose: verify server lifecycle helper contracts for the governed server.
Governance scope: lifecycle helper validation tests only.
Dependencies: server lifecycle helpers with pytest support.
Invariants: lifecycle registration and wrapper behavior stays bounded, deterministic, and auditable.
"""

from __future__ import annotations

from mcoi_runtime.app import server_lifecycle


def test_bootstrap_server_lifecycle_mounts_routes_and_registers_shutdown_hooks() -> None:
    captured: dict[str, object] = {"registered": []}

    class ShutdownManager:
        def register(self, name: str, handler, *, priority: int) -> None:
            captured["registered"].append((name, handler, priority))

    def fake_include_default_routers_fn(app) -> None:
        captured["app"] = app
        captured["routers_included"] = True

    def fake_restore_state_on_startup_impl(**kwargs):
        captured["restore_kwargs"] = kwargs
        return {"restored": True}

    bootstrap = server_lifecycle.bootstrap_server_lifecycle(
        app="app-object",
        shutdown_mgr=ShutdownManager(),
        tenant_budget_mgr="tenant-budget",
        state_persistence="state-persistence",
        audit_trail="audit-trail",
        cost_analytics="cost-analytics",
        platform_logger="platform-logger",
        log_levels="log-levels",
        append_bounded_warning="append-warning",
        governance_stores="governance-stores",
        primary_store="primary-store",
        include_default_routers_fn=fake_include_default_routers_fn,
        flush_state_on_shutdown_impl=lambda **kwargs: {"flushed": kwargs},
        restore_state_on_startup_impl=fake_restore_state_on_startup_impl,
        close_governance_stores_impl=lambda **kwargs: {"closed": kwargs},
    )

    registrations = captured["registered"]

    assert captured["routers_included"] is True
    assert captured["app"] == "app-object"
    assert bootstrap.startup_restored == {"restored": True}
    assert captured["restore_kwargs"]["tenant_budget_mgr"] == "tenant-budget"
    assert captured["restore_kwargs"]["append_bounded_warning"] == "append-warning"
    assert [name for name, _, _ in registrations] == [
        "save_state",
        "flush_metrics",
        "close_connections",
    ]
    assert [priority for _, _, priority in registrations] == [100, 90, 10]
    assert registrations[1][1]() == {"flushed": True}


def test_bootstrap_server_lifecycle_wrappers_preserve_state_and_store_bindings() -> None:
    captured: dict[str, object] = {}
    current = {
        "tenant_budget_mgr": "tenant-budget",
        "state_persistence": "state-persistence",
        "audit_trail": "audit-trail",
        "cost_analytics": "cost-analytics",
        "platform_logger": "platform-logger",
        "governance_stores": "governance-stores",
        "primary_store": "primary-store",
    }

    def fake_flush_state_on_shutdown_impl(**kwargs):
        captured["flush_kwargs"] = kwargs
        return {"status": "flushed"}

    def fake_restore_state_on_startup_impl(**kwargs):
        captured["restore_kwargs"] = kwargs
        return {"status": "restored"}

    def fake_close_governance_stores_impl(**kwargs):
        captured["close_kwargs"] = kwargs
        return {"status": "closed"}

    class ShutdownManager:
        def register(self, name: str, handler, *, priority: int) -> None:
            captured[name] = (handler, priority)

    bootstrap = server_lifecycle.bootstrap_server_lifecycle(
        app=object(),
        shutdown_mgr=ShutdownManager(),
        tenant_budget_mgr=lambda: current["tenant_budget_mgr"],
        state_persistence=lambda: current["state_persistence"],
        audit_trail=lambda: current["audit_trail"],
        cost_analytics=lambda: current["cost_analytics"],
        platform_logger=lambda: current["platform_logger"],
        log_levels="log-levels",
        append_bounded_warning="append-warning",
        governance_stores=lambda: current["governance_stores"],
        primary_store=lambda: current["primary_store"],
        include_default_routers_fn=lambda app: None,
        flush_state_on_shutdown_impl=fake_flush_state_on_shutdown_impl,
        restore_state_on_startup_impl=fake_restore_state_on_startup_impl,
        close_governance_stores_impl=fake_close_governance_stores_impl,
    )

    current["tenant_budget_mgr"] = "tenant-budget-updated"
    current["state_persistence"] = "state-persistence-updated"
    current["audit_trail"] = "audit-trail-updated"
    current["cost_analytics"] = "cost-analytics-updated"
    current["platform_logger"] = "platform-logger-updated"
    current["governance_stores"] = "governance-stores-updated"
    current["primary_store"] = "primary-store-updated"

    assert bootstrap.flush_state_on_shutdown() == {"status": "flushed"}
    assert bootstrap.restore_state_on_startup() == {"status": "restored"}
    assert bootstrap.close_governance_stores() == {"status": "closed"}
    assert captured["flush_kwargs"]["tenant_budget_mgr"] == "tenant-budget-updated"
    assert captured["flush_kwargs"]["state_persistence"] == "state-persistence-updated"
    assert captured["flush_kwargs"]["audit_trail"] == "audit-trail-updated"
    assert captured["flush_kwargs"]["cost_analytics"] == "cost-analytics-updated"
    assert captured["restore_kwargs"]["platform_logger"] == "platform-logger-updated"
    assert captured["close_kwargs"]["governance_stores"] == "governance-stores-updated"
    assert captured["close_kwargs"]["primary_store"] == "primary-store-updated"
    assert captured["close_kwargs"]["append_bounded_warning"] == "append-warning"
