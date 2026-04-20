"""Purpose: verify server context helper contracts for the governed server.
Governance scope: context composition validation tests only.
Dependencies: server context helpers with pytest support.
Invariants: context wiring remains deterministic, bounded, and auditable.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from mcoi_runtime.app import server_context


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


def test_bootstrap_server_context_rejects_unencrypted_production_postgres() -> None:
    with pytest.raises(
        RuntimeError,
        match="^Production PostgreSQL deployments require field encryption to be enabled\\.$",
    ):
        server_context.bootstrap_server_context(
            runtime_env={"MULLU_ENV": "production"},
            clock=lambda: "2026-01-01T00:00:00Z",
            env_flag_fn=lambda name, env: False,
            validate_db_backend_for_env=lambda backend, env: None,
            init_field_encryption_from_env_fn=lambda: (
                None,
                {"configured": False, "enabled": False, "warning": ""},
            ),
            deployment_manifests={"local_dev": "local-manifest", "production": "prod-manifest"},
            production_surface_cls=lambda manifest: SimpleNamespace(manifest=manifest),
            bootstrap_primary_store_fn=lambda **kwargs: SimpleNamespace(
                db_backend="postgresql",
                warning=None,
                store=object(),
            ),
            bootstrap_foundation_services_fn=lambda **kwargs: object(),
            bootstrap_governance_runtime_fn=lambda **kwargs: SimpleNamespace(shell_policy=object()),
        )
