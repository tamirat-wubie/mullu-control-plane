"""Gateway worker tests.

Tests: worker configuration, bounded single-pass dispatch, and validation.
"""

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.router import GatewayResponse  # noqa: E402
from gateway.worker import (  # noqa: E402
    GatewayWorker,
    GatewayWorkerConfig,
    config_from_env,
    parse_args,
)


class StubWorkerRouter:
    """Router stub that records worker claim parameters."""

    def __init__(self, response_count: int = 1) -> None:
        self.calls: list[dict[str, object]] = []
        self.anchor_calls: list[dict[str, str]] = []
        self._response_count = response_count

    def process_ready_commands(
        self,
        *,
        worker_id: str = "gateway-worker",
        limit: int = 10,
        lease_seconds: int = 300,
    ) -> list[GatewayResponse]:
        self.calls.append({
            "worker_id": worker_id,
            "limit": limit,
            "lease_seconds": lease_seconds,
        })
        return [
            GatewayResponse(
                message_id=f"resp-{index}",
                channel="test",
                recipient_id="user-1",
                body="ok",
            )
            for index in range(self._response_count)
        ]

    def anchor_command_events(
        self,
        *,
        signing_secret: str,
        signature_key_id: str = "local",
    ):
        self.anchor_calls.append({
            "signing_secret": signing_secret,
            "signature_key_id": signature_key_id,
        })
        return None


def test_worker_run_once_uses_bounded_config():
    router = StubWorkerRouter(response_count=2)
    worker = GatewayWorker(
        router,
        GatewayWorkerConfig(
            worker_id="worker-a",
            batch_size=3,
            lease_seconds=45,
            poll_seconds=0,
            run_once=True,
        ),
    )

    processed = worker.run_once()

    assert processed == 2
    assert len(router.calls) == 1
    assert router.calls[0]["worker_id"] == "worker-a"
    assert router.calls[0]["limit"] == 3
    assert router.calls[0]["lease_seconds"] == 45
    assert router.anchor_calls == []


def test_worker_run_once_anchors_when_secret_configured():
    router = StubWorkerRouter(response_count=0)
    worker = GatewayWorker(
        router,
        GatewayWorkerConfig(
            worker_id="worker-a",
            batch_size=3,
            lease_seconds=45,
            poll_seconds=0,
            run_once=True,
            anchor_signing_secret="anchor-secret",
            anchor_signature_key_id="anchor-key",
        ),
    )

    processed = worker.run_once()

    assert processed == 0
    assert len(router.calls) == 1
    assert router.anchor_calls == [{
        "signing_secret": "anchor-secret",
        "signature_key_id": "anchor-key",
    }]


def test_worker_config_from_env(monkeypatch):
    monkeypatch.setitem(os.environ, "MULLU_ENV", "local_dev")
    monkeypatch.delenv("MULLU_REQUIRE_COMMAND_ANCHOR", raising=False)
    monkeypatch.setitem(os.environ, "MULLU_GATEWAY_WORKER_ID", "worker-env")
    monkeypatch.setitem(os.environ, "MULLU_GATEWAY_WORKER_BATCH_SIZE", "7")
    monkeypatch.setitem(os.environ, "MULLU_GATEWAY_WORKER_LEASE_SECONDS", "120")
    monkeypatch.setitem(os.environ, "MULLU_GATEWAY_WORKER_POLL_SECONDS", "0.25")
    monkeypatch.setitem(os.environ, "MULLU_GATEWAY_WORKER_RUN_ONCE", "true")
    monkeypatch.setitem(os.environ, "MULLU_COMMAND_ANCHOR_SECRET", "anchor-secret")
    monkeypatch.setitem(os.environ, "MULLU_COMMAND_ANCHOR_KEY_ID", "anchor-key")

    config = config_from_env()

    assert config.worker_id == "worker-env"
    assert config.batch_size == 7
    assert config.lease_seconds == 120
    assert config.poll_seconds == 0.25
    assert config.run_once is True
    assert config.anchor_signing_secret == "anchor-secret"
    assert config.anchor_signature_key_id == "anchor-key"
    assert config.require_command_anchor is False


def test_worker_config_requires_anchor_secret_when_explicit(monkeypatch):
    monkeypatch.setitem(os.environ, "MULLU_REQUIRE_COMMAND_ANCHOR", "true")
    monkeypatch.delenv("MULLU_COMMAND_ANCHOR_SECRET", raising=False)

    config = config_from_env()

    assert config.require_command_anchor is True
    with pytest.raises(ValueError, match="^command anchor signing secret is required$"):
        GatewayWorker(StubWorkerRouter(), config)


def test_worker_config_requires_anchor_secret_in_production(monkeypatch):
    monkeypatch.setitem(os.environ, "MULLU_ENV", "production")
    monkeypatch.delenv("MULLU_REQUIRE_COMMAND_ANCHOR", raising=False)
    monkeypatch.delenv("MULLU_COMMAND_ANCHOR_SECRET", raising=False)

    config = config_from_env()

    assert config.require_command_anchor is True
    with pytest.raises(ValueError, match="^command anchor signing secret is required$"):
        GatewayWorker(StubWorkerRouter(), config)


def test_worker_config_allows_local_without_anchor_secret(monkeypatch):
    monkeypatch.setitem(os.environ, "MULLU_ENV", "local_dev")
    monkeypatch.delenv("MULLU_REQUIRE_COMMAND_ANCHOR", raising=False)
    monkeypatch.delenv("MULLU_COMMAND_ANCHOR_SECRET", raising=False)

    config = config_from_env()
    worker = GatewayWorker(StubWorkerRouter(response_count=0), config)

    assert config.require_command_anchor is False
    assert worker.run_once() == 0


def test_worker_parse_args_overrides_env(monkeypatch):
    monkeypatch.setitem(os.environ, "MULLU_GATEWAY_WORKER_ID", "worker-env")

    config = parse_args([
        "--worker-id", "worker-cli",
        "--batch-size", "4",
        "--lease-seconds", "60",
        "--poll-seconds", "0",
        "--once",
    ])

    assert config.worker_id == "worker-cli"
    assert config.batch_size == 4
    assert config.lease_seconds == 60
    assert config.poll_seconds == 0
    assert config.run_once is True


def test_worker_rejects_invalid_config():
    with pytest.raises(ValueError):
        GatewayWorker(StubWorkerRouter(), GatewayWorkerConfig(worker_id=""))
    with pytest.raises(ValueError):
        GatewayWorker(StubWorkerRouter(), GatewayWorkerConfig(batch_size=0))
    with pytest.raises(ValueError):
        GatewayWorker(StubWorkerRouter(), GatewayWorkerConfig(lease_seconds=0))
