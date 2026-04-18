"""Purpose: verify bootstrap, foundation, and context helper contracts for the governed server.
Governance scope: bootstrap helper validation tests only.
Dependencies: server bootstrap, foundation, and context helpers with pytest support.
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
