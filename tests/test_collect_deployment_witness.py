"""Tests for live deployment witness collection.

Purpose: verify bounded gateway deployment witness collection without network.
Governance scope: [OCE, CDCV, UWMA, PRS]
Dependencies: scripts.collect_deployment_witness.
Invariants:
  - Published claims require health, runtime witness, and signature proof.
  - Missing signature secrets keep the witness in not-published state.
  - CLI writes structured witness JSON for operator review.
"""

from __future__ import annotations

import json
from typing import Any

from scripts.collect_deployment_witness import (
    collect_deployment_witness,
    main,
    write_deployment_witness,
)


class StubHttpResponse:
    """Context-managed urllib response fixture."""

    def __init__(self, *, status: int, payload: dict[str, Any]) -> None:
        self.status = status
        self._body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return self._body


def test_collect_deployment_witness_publishes_with_verified_signature(monkeypatch) -> None:
    secret = "runtime-secret"
    witness_payload = _signed_runtime_witness(secret=secret)

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    witness = collect_deployment_witness(
        gateway_url="https://gateway.example",
        witness_secret=secret,
        expected_environment="pilot",
        clock=lambda: "2026-04-25T00:00:00+00:00",
    )

    assert witness.deployment_claim == "published"
    assert witness.signature_status == "verified"
    assert witness.latest_terminal_certificate_id == "terminal-1"
    assert witness.runtime_environment == "pilot"
    assert all(step.passed for step in witness.steps)


def test_collect_deployment_witness_fails_closed_without_secret(monkeypatch) -> None:
    witness_payload = _signed_runtime_witness(secret="runtime-secret")

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    witness = collect_deployment_witness(
        gateway_url="https://gateway.example",
        witness_secret="",
        clock=lambda: "2026-04-25T00:00:00+00:00",
    )

    assert witness.deployment_claim == "not-published"
    assert witness.signature_status == "skipped:no_witness_secret"
    assert "runtime witness signature was not verified" in witness.errors
    assert any(step.name == "runtime witness signature" for step in witness.steps)


def test_write_deployment_witness_persists_json(tmp_path, monkeypatch) -> None:
    witness_payload = _signed_runtime_witness(secret="runtime-secret")

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    witness = collect_deployment_witness(
        gateway_url="https://gateway.example",
        witness_secret="runtime-secret",
        clock=lambda: "2026-04-25T00:00:00+00:00",
    )
    output_path = tmp_path / "deployment_witness.json"

    written = write_deployment_witness(witness, output_path)
    loaded = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert loaded["deployment_claim"] == "published"
    assert loaded["witness_id"] == witness.witness_id
    assert loaded["steps"][0]["name"] == "gateway health"


def test_cli_writes_not_published_witness_without_secret(tmp_path, monkeypatch, capsys) -> None:
    witness_payload = _signed_runtime_witness(secret="runtime-secret")

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    output_path = tmp_path / "deployment_witness.json"

    exit_code = main(["--gateway-url", "https://gateway.example", "--output", str(output_path)])
    captured = capsys.readouterr()
    loaded = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert "deployment witness written" in captured.out
    assert loaded["deployment_claim"] == "not-published"
    assert loaded["signature_status"] == "skipped:no_witness_secret"


def _signed_runtime_witness(*, secret: str) -> dict[str, Any]:
    payload = {
        "witness_id": "runtime-witness-test",
        "environment": "pilot",
        "runtime_status": "healthy",
        "gateway_status": "healthy",
        "latest_command_event_hash": "event-hash",
        "latest_anchor_id": "anchor-1",
        "latest_terminal_certificate_id": "terminal-1",
        "open_case_count": 0,
        "active_accepted_risk_count": 0,
        "unresolved_reconciliation_count": 0,
        "last_change_certificate_id": None,
        "signed_at": "2026-04-25T00:00:00+00:00",
        "signature_key_id": "runtime-witness-test",
    }
    import hashlib
    import hmac

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature_payload = hashlib.sha256(canonical).hexdigest()
    signature = hmac.new(
        secret.encode("utf-8"),
        signature_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {**payload, "signature": f"hmac-sha256:{signature}"}
