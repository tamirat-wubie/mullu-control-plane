"""Purpose: verify foundation helper contracts for the governed server.
Governance scope: foundation helper validation tests only.
Dependencies: server foundation helpers with deterministic bootstrap wiring.
Invariants: foundation wiring remains deterministic, bounded, and auditable.
"""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from mcoi_runtime.app import server_foundation
from mcoi_runtime.contracts.receipt_store import JsonlReceiptStore


def test_receipt_store_from_env_returns_none_without_jsonl_path() -> None:
    assert server_foundation.receipt_store_from_env({}) is None
    assert (
        server_foundation.receipt_store_from_env(
            {"MULLU_RECEIPT_STORE_JSONL_PATH": "   "}
        )
        is None
    )
    assert server_foundation.receipt_store_from_env({"OTHER_SETTING": "x"}) is None


def test_receipt_store_from_env_builds_jsonl_store(tmp_path) -> None:
    receipt_path = tmp_path / "receipts" / "proof.jsonl"

    receipt_store = server_foundation.receipt_store_from_env(
        {"MULLU_RECEIPT_STORE_JSONL_PATH": str(receipt_path)}
    )

    assert isinstance(receipt_store, JsonlReceiptStore)
    assert receipt_store.path == receipt_path
    assert receipt_store.sync_on_write is True
    assert receipt_path.parent.exists()


def test_receipt_store_from_env_allows_sync_disable(tmp_path) -> None:
    receipt_path = tmp_path / "receipts" / "proof.jsonl"

    receipt_store = server_foundation.receipt_store_from_env(
        {
            server_foundation.RECEIPT_STORE_JSONL_ENV: str(receipt_path),
            server_foundation.RECEIPT_STORE_JSONL_SYNC_ENV: "false",
        }
    )

    assert isinstance(receipt_store, JsonlReceiptStore)
    assert receipt_store.sync_on_write is False
    assert receipt_store.path == receipt_path


def test_receipt_store_from_env_rejects_invalid_sync_flag(tmp_path) -> None:
    receipt_path = tmp_path / "receipts" / "proof.jsonl"

    with pytest.raises(server_foundation.FoundationConfigurationError) as exc_info:
        server_foundation.receipt_store_from_env(
            {
                server_foundation.RECEIPT_STORE_JSONL_ENV: str(receipt_path),
                server_foundation.RECEIPT_STORE_JSONL_SYNC_ENV: "sometimes",
            }
        )

    assert server_foundation.RECEIPT_STORE_JSONL_SYNC_ENV in str(exc_info.value)
    assert "boolean" in str(exc_info.value)
    assert not receipt_path.exists()


def test_receipt_store_from_env_rejects_directory_path(tmp_path) -> None:
    receipt_directory = tmp_path / "receipts"
    receipt_directory.mkdir()

    with pytest.raises(server_foundation.FoundationConfigurationError) as exc_info:
        server_foundation.receipt_store_from_env(
            {
                server_foundation.RECEIPT_STORE_JSONL_ENV: str(
                    receipt_directory
                )
            }
        )

    assert server_foundation.RECEIPT_STORE_JSONL_ENV in str(exc_info.value)
    assert "JSONL file path" in str(exc_info.value)
    assert receipt_directory.is_dir()


def test_receipt_store_from_env_rejects_control_character_path(tmp_path) -> None:
    unsafe_path = f"{tmp_path}\nreceipts.jsonl"

    with pytest.raises(server_foundation.FoundationConfigurationError) as exc_info:
        server_foundation.receipt_store_from_env(
            {server_foundation.RECEIPT_STORE_JSONL_ENV: unsafe_path}
        )

    assert server_foundation.RECEIPT_STORE_JSONL_ENV in str(exc_info.value)
    assert "control characters" in str(exc_info.value)
    assert "receipts.jsonl" in unsafe_path


def test_receipt_store_from_env_wraps_malformed_jsonl_replay(tmp_path) -> None:
    receipt_path = tmp_path / "receipts.jsonl"
    receipt_path.write_text("{not-json}\n", encoding="utf-8")

    with pytest.raises(server_foundation.FoundationConfigurationError) as exc_info:
        server_foundation.receipt_store_from_env(
            {server_foundation.RECEIPT_STORE_JSONL_ENV: str(receipt_path)}
        )

    assert server_foundation.RECEIPT_STORE_JSONL_ENV in str(exc_info.value)
    assert "could not initialize receipt store" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, ValueError)


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


def test_bootstrap_foundation_services_wires_configured_receipt_store() -> None:
    configured_receipt_store = object()

    class FakeLLMConfig:
        @classmethod
        def from_env(cls) -> str:
            return "cfg"

    def fake_bootstrap_llm_fn(*, clock, config, ledger_sink):
        return SimpleNamespace(
            bridge=type(
                "Bridge",
                (),
                {"complete": lambda self, prompt, budget_id: {"prompt": prompt}},
            )()
        )

    class FakeCertificationConfig:
        def __init__(self, *, interval_seconds: float, enabled: bool) -> None:
            self.interval_seconds = interval_seconds
            self.enabled = enabled

    class FakeCertificationDaemon:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class FakeProofBridge:
        def __init__(self, *, clock, store) -> None:
            self.clock = clock
            self.store = store

    store = type(
        "Store",
        (),
        {
            "append_ledger": lambda self, *args: None,
            "query_ledger": lambda self, tenant_id: [tenant_id],
            "ledger_count": lambda self: 3,
        },
    )()

    bootstrap = server_foundation.bootstrap_foundation_services(
        clock=lambda: "2026-01-01T00:00:00Z",
        runtime_env={"MULLU_RECEIPT_STORE_JSONL_PATH": "ignored-by-fake"},
        store=store,
        llm_config_cls=FakeLLMConfig,
        bootstrap_llm_fn=fake_bootstrap_llm_fn,
        live_path_certifier_cls=lambda **kwargs: object(),
        streaming_adapter_cls=lambda **kwargs: object(),
        certification_config_cls=FakeCertificationConfig,
        certification_daemon_cls=FakeCertificationDaemon,
        pii_scanner_cls=lambda **kwargs: object(),
        build_default_safety_chain_fn=lambda: object(),
        proof_bridge_cls=FakeProofBridge,
        receipt_store_from_env_fn=lambda runtime_env: configured_receipt_store,
        tenant_ledger_cls=lambda **kwargs: object(),
    )

    assert bootstrap.proof_bridge.store is configured_receipt_store
    assert bootstrap.proof_bridge.clock() == "2026-01-01T00:00:00Z"
    assert bootstrap.cert_daemon.kwargs["config"].interval_seconds == 300.0


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
