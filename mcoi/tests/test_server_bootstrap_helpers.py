"""Purpose: verify bootstrap and context helper contracts for the governed server.
Governance scope: bootstrap helper validation tests only.
Dependencies: server bootstrap and context helpers with pytest support.
Invariants: bootstrap wiring remains deterministic, bounded, and auditable.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from mcoi_runtime.app import server_bootstrap
from mcoi_runtime.app import server_context


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
