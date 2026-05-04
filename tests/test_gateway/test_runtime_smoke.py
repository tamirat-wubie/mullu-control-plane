"""Gateway runtime smoke probe tests.

Tests: live-probe orchestration without real network calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.capability_isolation import sign_capability_payload  # noqa: E402
from scripts.gateway_runtime_smoke import main, run_probe  # noqa: E402


class StubHttpResponse:
    """Context-managed urllib response fixture."""

    def __init__(self, *, status: int, payload: dict[str, Any], headers: dict[str, str] | None = None) -> None:
        self.status = status
        self._body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return self._body


def test_gateway_runtime_smoke_passes_with_signed_worker_response(monkeypatch) -> None:
    secret = "worker-secret"

    def fake_urlopen(request, timeout):
        url = request if isinstance(request, str) else request.full_url
        if url.endswith("/health") and ":8001" in url:
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if url.endswith("/gateway/witness"):
            return StubHttpResponse(
                status=200,
                payload={
                    "witness_id": "runtime-witness-test",
                    "gateway_status": "healthy",
                    "latest_command_event_hash": "hash-test",
                    "latest_terminal_certificate_id": "terminal-1",
                    "signature_key_id": "runtime-witness-test",
                    "signature": "hmac-sha256:test",
                },
            )
        if url.endswith("/health") and ":8010" in url:
            return StubHttpResponse(status=200, payload={"status": "healthy", "worker_id": "worker-1"})
        if url.endswith("/capability/execute"):
            body = request.data
            payload = {
                "request_id": json.loads(body.decode("utf-8"))["request_id"],
                "status": "succeeded",
                "result": {"receipt_status": "settled", "response": "ok"},
                "receipt": {
                    "receipt_id": "capability-receipt-test",
                    "capability_id": "financial.send_payment",
                    "execution_plane": "isolated_worker",
                    "isolation_required": True,
                    "worker_id": "worker-1",
                    "input_hash": "input-hash",
                    "output_hash": "output-hash",
                    "evidence_refs": ["restricted_worker:test"],
                },
            }
            raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            return StubHttpResponse(
                status=200,
                payload=payload,
                headers={"X-Mullu-Capability-Response-Signature": sign_capability_payload(raw, secret)},
            )
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    results = run_probe(
        gateway_url="http://localhost:8001",
        worker_url="http://localhost:8010/capability/execute",
        worker_secret=secret,
    )

    assert len(results) == 4
    assert all(result.passed for result in results)
    assert results[-1].step == "signed capability execution"


def test_gateway_runtime_smoke_fails_on_bad_worker_signature(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        url = request if isinstance(request, str) else request.full_url
        if url.endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if url.endswith("/gateway/witness"):
            return StubHttpResponse(
                status=200,
                payload={
                    "witness_id": "runtime-witness-test",
                    "gateway_status": "healthy",
                    "latest_command_event_hash": "hash-test",
                    "latest_terminal_certificate_id": "terminal-1",
                    "signature_key_id": "runtime-witness-test",
                    "signature": "hmac-sha256:test",
                },
            )
        if url.endswith("/capability/execute"):
            body = request.data
            payload = {
                "request_id": json.loads(body.decode("utf-8"))["request_id"],
                "status": "succeeded",
                "result": {"receipt_status": "settled"},
                "receipt": {
                    "receipt_id": "capability-receipt-test",
                    "capability_id": "financial.send_payment",
                    "execution_plane": "isolated_worker",
                    "isolation_required": True,
                    "worker_id": "worker-1",
                    "input_hash": "input-hash",
                    "output_hash": "output-hash",
                    "evidence_refs": ["restricted_worker:test"],
                },
            }
            return StubHttpResponse(
                status=200,
                payload=payload,
                headers={"X-Mullu-Capability-Response-Signature": "hmac-sha256:bad"},
            )
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    results = run_probe(
        gateway_url="http://localhost:8001",
        worker_url="http://localhost:8010/capability/execute",
        worker_secret="worker-secret",
    )

    assert results[-1].passed is False
    assert "signature_valid=False" in results[-1].detail


def test_gateway_runtime_smoke_exception_detail_is_bounded(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        raise RuntimeError("secret-runtime-url-token")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    results = run_probe(
        gateway_url="http://localhost:8001/secret-gateway-path",
        worker_url="http://localhost:8010/capability/execute",
        worker_secret="worker-secret",
    )
    serialized_results = json.dumps([result.detail for result in results], sort_keys=True)

    assert len(results) == 4
    assert all(result.passed is False for result in results)
    assert all(result.detail == "unhandled_probe_error" for result in results)
    assert "secret-runtime-url-token" not in serialized_results
    assert "secret-gateway-path" not in serialized_results


def test_gateway_runtime_smoke_cli_requires_worker_secret(capsys) -> None:
    exit_code = main([
        "--gateway-url", "http://localhost:8001",
        "--worker-url", "http://localhost:8010/capability/execute",
    ])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "worker-secret is required" in captured.err
