"""Runtime conformance collector tests.

Purpose: verify live conformance certificate collection without network.
Governance scope: endpoint probing, certificate signature verification, and
structured persistence.
Dependencies: scripts.collect_runtime_conformance.
Invariants:
  - A complete signed certificate can be collected and verified.
  - Missing conformance secrets keep signature status explicit.
  - Expired certificates are rejected even when signature verification passes.
  - Written output preserves collection and certificate evidence.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from scripts.collect_runtime_conformance import (
    collect_runtime_conformance,
    main,
    write_runtime_conformance,
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


def test_collect_runtime_conformance_verifies_signed_certificate(monkeypatch) -> None:
    secret = "conformance-secret"
    certificate = _signed_certificate(secret=secret)

    def fake_urlopen(request, timeout):
        assert str(request).endswith("/runtime/conformance")
        return StubHttpResponse(status=200, payload=certificate)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    collection = collect_runtime_conformance(
        gateway_url="http://localhost:8001",
        conformance_secret=secret,
        expected_environment="pilot",
    )

    assert collection.endpoint_status == 200
    assert collection.certificate_status == "conformant_with_gaps"
    assert collection.signature_status == "verified"
    assert all(step.passed for step in collection.steps)


def test_collect_runtime_conformance_records_missing_secret(monkeypatch) -> None:
    certificate = _signed_certificate(secret="conformance-secret")

    def fake_urlopen(request, timeout):
        return StubHttpResponse(status=200, payload=certificate)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    collection = collect_runtime_conformance(
        gateway_url="http://localhost:8001",
        conformance_secret="",
    )

    assert collection.signature_status == "skipped:no_conformance_secret"
    assert collection.steps[-1].passed is False
    assert "runtime conformance signature was not verified" in collection.errors


def test_collect_runtime_conformance_rejects_expired_certificate(monkeypatch) -> None:
    secret = "conformance-secret"
    certificate = _signed_certificate(
        secret=secret,
        expires_at="2026-04-25T12:00:00+00:00",
    )

    def fake_urlopen(request, timeout):
        return StubHttpResponse(status=200, payload=certificate)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    collection = collect_runtime_conformance(
        gateway_url="http://localhost:8001",
        conformance_secret=secret,
        clock=lambda: "2026-04-25T12:30:00+00:00",
    )
    freshness_step = next(step for step in collection.steps if step.name == "runtime conformance freshness")

    assert collection.signature_status == "verified"
    assert freshness_step.passed is False
    assert "fresh=False" in freshness_step.detail
    assert "runtime conformance certificate was expired or malformed" in collection.errors


def test_write_runtime_conformance_persists_json(tmp_path, monkeypatch) -> None:
    certificate = _signed_certificate(secret="conformance-secret")

    def fake_urlopen(request, timeout):
        return StubHttpResponse(status=200, payload=certificate)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    collection = collect_runtime_conformance(
        gateway_url="http://localhost:8001",
        conformance_secret="conformance-secret",
    )
    output_path = tmp_path / "runtime_conformance_certificate.json"

    written = write_runtime_conformance(collection, output_path)
    loaded = json.loads(written.read_text(encoding="utf-8"))

    assert written == output_path
    assert loaded["collection_id"] == collection.collection_id
    assert loaded["certificate"]["certificate_id"] == "conf-0123456789abcdef"


def test_runtime_conformance_cli_writes_collection(tmp_path, monkeypatch, capsys) -> None:
    certificate = _signed_certificate(secret="conformance-secret")

    def fake_urlopen(request, timeout):
        return StubHttpResponse(status=200, payload=certificate)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    output_path = tmp_path / "runtime_conformance_certificate.json"

    exit_code = main([
        "--gateway-url", "http://localhost:8001",
        "--conformance-secret", "conformance-secret",
        "--output", str(output_path),
    ])
    captured = capsys.readouterr()
    loaded = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "runtime conformance certificate written" in captured.out
    assert loaded["signature_status"] == "verified"


def _signed_certificate(
    *,
    secret: str,
    expires_at: str = "2099-04-25T12:30:00+00:00",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "certificate_id": "conf-0123456789abcdef",
        "environment": "pilot",
        "issued_at": "2026-04-25T12:00:00+00:00",
        "expires_at": expires_at,
        "gateway_witness_valid": True,
        "runtime_witness_valid": True,
        "latest_anchor_valid": True,
        "command_closure_canary_passed": True,
        "capability_admission_canary_passed": True,
        "dangerous_capability_isolation_canary_passed": True,
        "streaming_budget_canary_passed": True,
        "lineage_query_canary_passed": True,
        "authority_obligation_canary_passed": True,
        "capsule_registry_certified": True,
        "proof_coverage_matrix_current": True,
        "known_limitations_aligned": False,
        "security_model_aligned": False,
        "open_conformance_gaps": ["known_limitations_documentation_drift"],
        "terminal_status": "conformant_with_gaps",
        "evidence_refs": ["gateway_witness:test"],
        "checks": [
            {
                "check_id": "gateway_witness_valid",
                "passed": True,
                "evidence_ref": "gateway_witness:test",
                "detail": "verified",
            }
        ],
        "signature_key_id": "runtime-conformance-test",
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    signature = hmac.new(secret.encode("utf-8"), digest.encode("utf-8"), hashlib.sha256).hexdigest()
    return {**payload, "signature": f"hmac-sha256:{signature}"}
