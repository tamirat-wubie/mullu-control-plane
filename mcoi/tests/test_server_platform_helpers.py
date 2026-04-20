"""Purpose: verify platform helper contracts for the governed server.
Governance scope: platform helper validation tests only.
Dependencies: server platform helpers.
Invariants: platform wiring remains deterministic, bounded, and auditable.
"""

from __future__ import annotations

from mcoi_runtime.app import server_platform


def test_bootstrap_primary_store_applies_sqlite_migrations() -> None:
    class MigrationEngine:
        def apply_all(self, conn):
            assert conn == "sqlite-conn"
            return [
                type("Result", (), {"name": "001-init", "success": True})(),
                type("Result", (), {"name": "002-skip", "success": False})(),
            ]

    warnings_seen: list[tuple[str, int]] = []

    bootstrap = server_platform.bootstrap_primary_store(
        env="local_dev",
        runtime_env={
            "MULLU_DB_BACKEND": "sqlite",
            "MULLU_DB_URL": "sqlite:///govern.db",
        },
        clock=lambda: "2026-01-01T00:00:00Z",
        validate_db_backend_for_env=lambda backend, env: None,
        create_store_fn=lambda **kwargs: type("Store", (), {"_conn": "sqlite-conn"})(),
        create_platform_migration_engine_fn=lambda **kwargs: MigrationEngine(),
        warnings_module=type(
            "Warnings",
            (),
            {"warn": lambda self, message, stacklevel=1: warnings_seen.append((message, stacklevel))},
        )(),
    )

    assert bootstrap.db_backend == "sqlite"
    assert bootstrap.warning is None
    assert bootstrap.migrations_applied == ("001-init",)
    assert warnings_seen == []


def test_bootstrap_governance_runtime_wires_services_and_local_policy() -> None:
    class BudgetManager:
        def __init__(self, *, clock, store):
            self.clock = clock
            self.store = store

    class MetricsEngine:
        def __init__(self, *, clock):
            self.clock = clock

    class RateLimitConfig:
        def __init__(self, *, max_tokens, refill_rate):
            self.max_tokens = max_tokens
            self.refill_rate = refill_rate

    class RateLimiter:
        def __init__(self, *, default_config, store):
            self.default_config = default_config
            self.store = store

    class AuditTrail:
        def __init__(self, *, clock, store):
            self.clock = clock
            self.store = store

    class TenantGating:
        def __init__(self, *, clock, store, allow_unknown_tenants):
            self.clock = clock
            self.store = store
            self.allow_unknown_tenants = allow_unknown_tenants

    stores = {
        "budget": object(),
        "rate_limit": object(),
        "audit": object(),
        "tenant_gating": object(),
    }
    local_policy = object()

    bootstrap = server_platform.bootstrap_governance_runtime(
        env="local_dev",
        runtime_env={},
        db_backend="memory",
        clock=lambda: "2026-01-01T00:00:00Z",
        field_encryptor=None,
        allow_unknown_tenants=True,
        create_governance_stores_fn=lambda **kwargs: stores,
        tenant_budget_manager_cls=BudgetManager,
        governance_metrics_engine_cls=MetricsEngine,
        rate_limiter_cls=RateLimiter,
        rate_limit_config_cls=RateLimitConfig,
        audit_trail_cls=AuditTrail,
        tenant_gating_registry_cls=TenantGating,
        sandboxed_policy=object(),
        local_dev_policy=local_policy,
        pilot_prod_policy=object(),
    )

    assert bootstrap.governance_stores is stores
    assert bootstrap.tenant_budget_mgr.store is stores["budget"]
    assert bootstrap.metrics.clock() == "2026-01-01T00:00:00Z"
    assert bootstrap.rate_limiter.store is stores["rate_limit"]
    assert bootstrap.rate_limiter.default_config.max_tokens == 60
    assert bootstrap.audit_trail.store is stores["audit"]
    assert bootstrap.tenant_gating.store is stores["tenant_gating"]
    assert bootstrap.tenant_gating.allow_unknown_tenants is True
    assert bootstrap.jwt_authenticator is None
    assert bootstrap.shell_policy is local_policy


def test_bootstrap_governance_runtime_builds_jwt_authenticator() -> None:
    captured = {}

    class Config:
        def __init__(self, **kwargs):
            captured["config"] = kwargs

    class Authenticator:
        def __init__(self, config):
            self.config = config

    bootstrap = server_platform.bootstrap_governance_runtime(
        env="production",
        runtime_env={
            "MULLU_JWT_SECRET": "c2VjcmV0",
            "MULLU_JWT_ISSUER": "issuer-a",
            "MULLU_JWT_AUDIENCE": "aud-a",
            "MULLU_JWT_TENANT_CLAIM": "tenant",
        },
        db_backend="postgresql",
        clock=lambda: "2026-01-01T00:00:00Z",
        field_encryptor=None,
        allow_unknown_tenants=False,
        create_governance_stores_fn=lambda **kwargs: {
            "budget": object(),
            "rate_limit": object(),
            "audit": object(),
            "tenant_gating": object(),
        },
        tenant_budget_manager_cls=lambda **kwargs: object(),
        governance_metrics_engine_cls=lambda **kwargs: object(),
        rate_limiter_cls=lambda **kwargs: object(),
        rate_limit_config_cls=lambda **kwargs: object(),
        audit_trail_cls=lambda **kwargs: object(),
        tenant_gating_registry_cls=lambda **kwargs: object(),
        sandboxed_policy=object(),
        local_dev_policy=object(),
        pilot_prod_policy=object(),
        jwt_authenticator_cls=Authenticator,
        oidc_config_cls=Config,
    )

    assert isinstance(bootstrap.jwt_authenticator, Authenticator)
    assert captured["config"]["issuer"] == "issuer-a"
    assert captured["config"]["audience"] == "aud-a"
    assert captured["config"]["signing_key"] == b"secret"
    assert captured["config"]["tenant_claim"] == "tenant"
