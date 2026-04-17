"""Purpose: verify bootstrap-layer helper contracts for the governed server.
Governance scope: bootstrap helper validation tests only.
Dependencies: server bootstrap, platform, foundation, and context helpers with pytest support.
Invariants: bootstrap wiring remains deterministic, bounded, and auditable.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from types import SimpleNamespace

from mcoi_runtime.app import server_bootstrap
from mcoi_runtime.app import server_context
from mcoi_runtime.app import server_foundation
from mcoi_runtime.app import server_platform


def test_utc_clock_returns_parseable_utc_timestamp() -> None:
    value = server_bootstrap.utc_clock()
    parsed = datetime.fromisoformat(value)

    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_init_field_encryption_from_env_without_key_is_disabled() -> None:
    encryptor, state = server_bootstrap.init_field_encryption_from_env(
        env={},
        bounded_bootstrap_warning=lambda context, exc: f"{context} failed ({type(exc).__name__})",
    )

    assert encryptor is None
    assert state == {
        "configured": False,
        "enabled": False,
        "aes_available": False,
        "warning": "",
    }


def test_init_field_encryption_from_env_bounds_invalid_key() -> None:
    def raise_invalid_key():
        raise ValueError("secret bootstrap detail")

    encryptor, state = server_bootstrap.init_field_encryption_from_env(
        env={"MULLU_ENCRYPTION_KEY": "c2hvcnQ="},
        bounded_bootstrap_warning=lambda context, exc: f"{context} failed ({type(exc).__name__})",
        key_provider_factory=raise_invalid_key,
    )

    assert encryptor is None
    assert state["configured"] is True
    assert state["enabled"] is False
    assert state["aes_available"] is False
    assert state["warning"] == "field encryption failed (ValueError)"


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


def test_bootstrap_foundation_services_wires_llm_certification_and_safety() -> None:
    captured: dict[str, object] = {}
    safety_chain = object()

    class FakeLLMConfig:
        @classmethod
        def from_env(cls) -> str:
            return "llm-config"

    class FakeBridge:
        def complete(self, prompt: str, budget_id: str) -> dict[str, str]:
            captured["llm_complete"] = {"prompt": prompt, "budget_id": budget_id}
            return {"prompt": prompt, "budget_id": budget_id}

    def fake_bootstrap_llm_fn(*, clock, config, ledger_sink):
        captured["llm_clock"] = clock
        captured["llm_config"] = config
        captured["llm_ledger_sink"] = ledger_sink
        return SimpleNamespace(bridge=FakeBridge())

    class FakeCertifier:
        def __init__(self, *, clock) -> None:
            self.clock = clock

    class FakeStreamingAdapter:
        def __init__(self, *, clock) -> None:
            self.clock = clock

    class FakeCertificationConfig:
        def __init__(self, *, interval_seconds: float, enabled: bool) -> None:
            self.interval_seconds = interval_seconds
            self.enabled = enabled

    class FakeCertificationDaemon:
        def __init__(self, **kwargs) -> None:
            captured["daemon_kwargs"] = kwargs
            self.kwargs = kwargs

    class FakePIIScanner:
        def __init__(self, *, enabled: bool) -> None:
            self.enabled = enabled

    class FakeProofBridge:
        def __init__(self, *, clock) -> None:
            self.clock = clock

    class FakeTenantLedger:
        def __init__(self, *, clock) -> None:
            self.clock = clock

    store = type(
        "Store",
        (),
        {
            "append_ledger": lambda self, *args: None,
            "query_ledger": lambda self, tenant_id: [tenant_id],
            "ledger_count": lambda self: 7,
        },
    )()

    bootstrap = server_foundation.bootstrap_foundation_services(
        clock=lambda: "2026-01-01T00:00:00Z",
        runtime_env={
            "MULLU_CERT_INTERVAL": "42",
            "MULLU_CERT_ENABLED": "false",
            "MULLU_PII_SCAN": "false",
        },
        store=store,
        llm_config_cls=FakeLLMConfig,
        bootstrap_llm_fn=fake_bootstrap_llm_fn,
        live_path_certifier_cls=FakeCertifier,
        streaming_adapter_cls=FakeStreamingAdapter,
        certification_config_cls=FakeCertificationConfig,
        certification_daemon_cls=FakeCertificationDaemon,
        pii_scanner_cls=FakePIIScanner,
        build_default_safety_chain_fn=lambda: safety_chain,
        proof_bridge_cls=FakeProofBridge,
        tenant_ledger_cls=FakeTenantLedger,
    )

    daemon_kwargs = captured["daemon_kwargs"]

    assert captured["llm_config"] == "llm-config"
    assert daemon_kwargs["config"].interval_seconds == 42.0
    assert daemon_kwargs["config"].enabled is False
    assert daemon_kwargs["api_handle_fn"]({}) == {"governed": True, "status": "ok"}
    assert daemon_kwargs["llm_invoke_fn"]("hello") == {
        "prompt": "hello",
        "budget_id": "default",
    }
    assert bootstrap.pii_scanner.enabled is False
    assert bootstrap.content_safety_chain is safety_chain
    assert bootstrap.proof_bridge.clock() == "2026-01-01T00:00:00Z"
    assert bootstrap.tenant_ledger.clock() == "2026-01-01T00:00:00Z"


def test_bootstrap_foundation_services_hashes_ledger_entries_and_state() -> None:
    captured: dict[str, object] = {}

    class FakeLLMConfig:
        @classmethod
        def from_env(cls) -> str:
            return "cfg"

    def fake_bootstrap_llm_fn(*, clock, config, ledger_sink):
        captured["llm_ledger_sink"] = ledger_sink
        return SimpleNamespace(
            bridge=type(
                "Bridge",
                (),
                {"complete": lambda self, prompt, budget_id: {"prompt": prompt, "budget_id": budget_id}},
            )()
        )

    class FakeCertificationConfig:
        def __init__(self, *, interval_seconds: float, enabled: bool) -> None:
            self.interval_seconds = interval_seconds
            self.enabled = enabled

    class FakeCertificationDaemon:
        def __init__(self, **kwargs) -> None:
            captured["daemon_kwargs"] = kwargs

    class FakeStore:
        def __init__(self) -> None:
            self.append_calls: list[tuple[object, ...]] = []
            self.query_calls: list[str] = []

        def append_ledger(self, *args) -> None:
            self.append_calls.append(args)

        def query_ledger(self, tenant_id: str) -> list[str]:
            self.query_calls.append(tenant_id)
            return [tenant_id]

        def ledger_count(self) -> int:
            return 11

    store = FakeStore()

    bootstrap = server_foundation.bootstrap_foundation_services(
        clock=lambda: "2026-01-01T00:00:00Z",
        runtime_env={},
        store=store,
        llm_config_cls=FakeLLMConfig,
        bootstrap_llm_fn=fake_bootstrap_llm_fn,
        live_path_certifier_cls=lambda **kwargs: object(),
        streaming_adapter_cls=lambda **kwargs: object(),
        certification_config_cls=FakeCertificationConfig,
        certification_daemon_cls=FakeCertificationDaemon,
        pii_scanner_cls=lambda **kwargs: object(),
        build_default_safety_chain_fn=lambda: object(),
        proof_bridge_cls=lambda **kwargs: object(),
        tenant_ledger_cls=lambda **kwargs: object(),
    )

    captured["llm_ledger_sink"]({"type": "tool", "tenant_id": "tenant-a", "value": 1})
    captured["daemon_kwargs"]["db_write_fn"]("tenant-b", {"step": 1})

    expected_llm_hash = hashlib.sha256(
        json.dumps({"type": "tool", "tenant_id": "tenant-a", "value": 1}, sort_keys=True).encode()
    ).hexdigest()
    expected_cert_hash = hashlib.sha256(
        json.dumps({"step": 1}, sort_keys=True).encode()
    ).hexdigest()
    state_digest, state_count = captured["daemon_kwargs"]["state_fn"]()

    assert bootstrap.llm_bootstrap_result.bridge is not None
    assert store.append_calls[0] == (
        "tool",
        "tenant-a",
        "tenant-a",
        {"type": "tool", "tenant_id": "tenant-a", "value": 1},
        expected_llm_hash,
    )
    assert store.append_calls[1] == (
        "certification",
        "certifier",
        "tenant-b",
        {"step": 1},
        expected_cert_hash,
    )
    assert captured["daemon_kwargs"]["db_read_fn"]("tenant-z") == ["tenant-z"]
    assert captured["daemon_kwargs"]["ledger_fn"]("tenant-y") == ["tenant-y"]
    assert store.query_calls == ["tenant-z", "tenant-y"]
    assert state_count == 11
    assert state_digest == hashlib.sha256(b"11").hexdigest()


def test_bootstrap_server_context_composes_env_store_foundation_and_governance() -> None:
    captured: dict[str, object] = {}
    store = object()
    foundation = object()
    field_encryptor = object()
    shell_policy = object()

    class FakeSurface:
        def __init__(self, manifest) -> None:
            self.manifest = manifest

    governance_bootstrap = SimpleNamespace(shell_policy=shell_policy)

    def fake_env_flag_fn(name: str, env: dict[str, str]) -> None:
        captured["flag_call"] = (name, env.copy())
        return None

    def fake_bootstrap_primary_store_fn(**kwargs):
        captured["primary_store_kwargs"] = kwargs
        return SimpleNamespace(db_backend="memory", warning="warn", store=store)

    def fake_foundation_bootstrap_fn(**kwargs):
        captured["foundation_kwargs"] = kwargs
        return foundation

    def fake_bootstrap_governance_runtime_fn(**kwargs):
        captured["governance_kwargs"] = kwargs
        return governance_bootstrap

    bootstrap = server_context.bootstrap_server_context(
        runtime_env={"MULLU_ENV": "test"},
        clock=lambda: "2026-01-01T00:00:00Z",
        env_flag_fn=fake_env_flag_fn,
        validate_db_backend_for_env=lambda backend, env: (backend, env),
        init_field_encryption_from_env_fn=lambda: (
            field_encryptor,
            {"enabled": True, "warning": "field warning"},
        ),
        deployment_manifests={"local_dev": "local-manifest", "test": "test-manifest"},
        production_surface_cls=FakeSurface,
        bootstrap_primary_store_fn=fake_bootstrap_primary_store_fn,
        bootstrap_foundation_services_fn=fake_foundation_bootstrap_fn,
        bootstrap_governance_runtime_fn=fake_bootstrap_governance_runtime_fn,
    )

    assert bootstrap.env == "test"
    assert bootstrap.surface.manifest == "test-manifest"
    assert bootstrap.tenant_allow_unknown is True
    assert bootstrap.store is store
    assert bootstrap.foundation_bootstrap is foundation
    assert bootstrap.field_encryptor is field_encryptor
    assert bootstrap.field_encryption_bootstrap["warning"] == "field warning"
    assert bootstrap.governance_bootstrap is governance_bootstrap
    assert bootstrap.shell_policy is shell_policy
    assert captured["primary_store_kwargs"]["env"] == "test"
    assert captured["foundation_kwargs"]["store"] is store
    assert captured["governance_kwargs"]["allow_unknown_tenants"] is True
