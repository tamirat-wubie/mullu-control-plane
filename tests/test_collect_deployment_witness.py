"""Tests for live deployment witness collection.

Purpose: verify bounded gateway deployment witness collection without network.
Governance scope: [OCE, CDCV, UWMA, PRS]
Dependencies: scripts.collect_deployment_witness.
Invariants:
  - Published claims require health, runtime witness, conformance certificate,
    and signature proof.
  - Missing signature secrets keep the witness in not-published state.
  - CLI writes structured witness JSON for operator review.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.collect_deployment_witness import (
    collect_deployment_witness,
    main,
    write_deployment_witness,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOYMENT_WITNESS_SCHEMA_PATH = REPO_ROOT / "schemas" / "deployment_witness.schema.json"


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
    conformance_secret = "conformance-secret"
    witness_payload = _signed_runtime_witness(secret=secret)
    conformance_payload = _signed_conformance_certificate(secret=conformance_secret)

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        if str(url).endswith("/runtime/conformance"):
            return StubHttpResponse(status=200, payload=conformance_payload)
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    witness = collect_deployment_witness(
        gateway_url="https://gateway.example",
        witness_secret=secret,
        conformance_secret=conformance_secret,
        expected_environment="pilot",
        clock=lambda: "2026-04-25T00:00:00+00:00",
    )

    assert witness.deployment_claim == "published"
    assert witness.signature_status == "verified"
    assert witness.latest_terminal_certificate_id == "terminal-1"
    assert witness.latest_conformance_certificate_id == "conf-0123456789abcdef"
    assert witness.conformance_signature_status == "verified"
    assert witness.runtime_environment == "pilot"
    assert witness.runtime_responsibility_debt_clear is True
    assert witness.authority_responsibility_debt_clear is True
    assert witness.authority_overdue_obligation_count == 0
    assert witness.authority_unowned_high_risk_capability_count == 0
    assert all(step.passed for step in witness.steps)


def test_collect_deployment_witness_fails_closed_without_secret(monkeypatch) -> None:
    witness_payload = _signed_runtime_witness(secret="runtime-secret")
    conformance_payload = _signed_conformance_certificate(secret="conformance-secret")

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        if str(url).endswith("/runtime/conformance"):
            return StubHttpResponse(status=200, payload=conformance_payload)
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    witness = collect_deployment_witness(
        gateway_url="https://gateway.example",
        witness_secret="",
        clock=lambda: "2026-04-25T00:00:00+00:00",
    )

    assert witness.deployment_claim == "not-published"
    assert witness.signature_status == "skipped:no_witness_secret"
    assert witness.conformance_signature_status == "skipped:no_conformance_secret"
    assert "runtime witness signature was not verified" in witness.errors
    assert "runtime conformance signature was not verified" in witness.errors
    assert any(step.name == "runtime witness signature" for step in witness.steps)


def test_collect_deployment_witness_rejects_expired_conformance_certificate(monkeypatch) -> None:
    witness_secret = "runtime-secret"
    conformance_secret = "conformance-secret"
    witness_payload = _signed_runtime_witness(secret=witness_secret)
    conformance_payload = _signed_conformance_certificate(
        secret=conformance_secret,
        expires_at="2026-04-25T00:00:00+00:00",
    )

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        if str(url).endswith("/runtime/conformance"):
            return StubHttpResponse(status=200, payload=conformance_payload)
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    witness = collect_deployment_witness(
        gateway_url="https://gateway.example",
        witness_secret=witness_secret,
        conformance_secret=conformance_secret,
        expected_environment="pilot",
        clock=lambda: "2026-04-25T00:30:00+00:00",
    )
    conformance_step = next(step for step in witness.steps if step.name == "runtime conformance certificate")

    assert witness.deployment_claim == "not-published"
    assert witness.conformance_signature_status == "verified"
    assert conformance_step.passed is False
    assert "fresh=False" in conformance_step.detail


def test_collect_deployment_witness_rejects_responsibility_debt(monkeypatch) -> None:
    witness_secret = "runtime-secret"
    conformance_secret = "conformance-secret"
    witness_payload = _signed_runtime_witness(secret=witness_secret)
    conformance_payload = _signed_conformance_certificate(
        secret=conformance_secret,
        authority_responsibility_debt_clear=False,
    )

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        if str(url).endswith("/runtime/conformance"):
            return StubHttpResponse(status=200, payload=conformance_payload)
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    witness = collect_deployment_witness(
        gateway_url="https://gateway.example",
        witness_secret=witness_secret,
        conformance_secret=conformance_secret,
        expected_environment="pilot",
        clock=lambda: "2026-04-25T00:00:00+00:00",
    )
    conformance_step = next(step for step in witness.steps if step.name == "runtime conformance certificate")

    assert witness.deployment_claim == "not-published"
    assert witness.conformance_signature_status == "verified"
    assert conformance_step.passed is False
    assert "responsibility_debt_clear=False" in conformance_step.detail
    assert "runtime conformance certificate is missing acceptable production evidence" in witness.errors


def test_collect_deployment_witness_rejects_runtime_responsibility_debt(monkeypatch) -> None:
    witness_secret = "runtime-secret"
    conformance_secret = "conformance-secret"
    witness_payload = _signed_runtime_witness(
        secret=witness_secret,
        responsibility_debt_clear=False,
    )
    conformance_payload = _signed_conformance_certificate(secret=conformance_secret)

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        if str(url).endswith("/runtime/conformance"):
            return StubHttpResponse(status=200, payload=conformance_payload)
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    witness = collect_deployment_witness(
        gateway_url="https://gateway.example",
        witness_secret=witness_secret,
        conformance_secret=conformance_secret,
        expected_environment="pilot",
        clock=lambda: "2026-04-25T00:00:00+00:00",
    )
    runtime_step = next(step for step in witness.steps if step.name == "gateway runtime witness")
    conformance_step = next(step for step in witness.steps if step.name == "runtime conformance certificate")

    assert witness.deployment_claim == "not-published"
    assert witness.runtime_responsibility_debt_clear is False
    assert runtime_step.passed is False
    assert conformance_step.passed is False
    assert "responsibility_debt_clear=False" in runtime_step.detail
    assert "runtime conformance certificate is missing acceptable production evidence" in witness.errors


def test_collect_deployment_witness_rejects_failed_core_canary(monkeypatch) -> None:
    witness_secret = "runtime-secret"
    conformance_secret = "conformance-secret"
    witness_payload = _signed_runtime_witness(secret=witness_secret)
    conformance_payload = _signed_conformance_certificate(
        secret=conformance_secret,
        overrides={"dangerous_capability_isolation_canary_passed": False},
    )

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        if str(url).endswith("/runtime/conformance"):
            return StubHttpResponse(status=200, payload=conformance_payload)
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    witness = collect_deployment_witness(
        gateway_url="https://gateway.example",
        witness_secret=witness_secret,
        conformance_secret=conformance_secret,
        expected_environment="pilot",
        clock=lambda: "2026-04-25T00:00:00+00:00",
    )
    conformance_step = next(step for step in witness.steps if step.name == "runtime conformance certificate")

    assert witness.deployment_claim == "not-published"
    assert witness.conformance_signature_status == "verified"
    assert conformance_step.passed is False
    assert "dangerous_capability_isolation_canary_passed" in conformance_step.detail
    assert "runtime conformance certificate is missing acceptable production evidence" in witness.errors


def test_collect_deployment_witness_rejects_invalid_mcp_manifest(monkeypatch) -> None:
    witness_secret = "runtime-secret"
    conformance_secret = "conformance-secret"
    witness_payload = _signed_runtime_witness(secret=witness_secret)
    conformance_payload = _signed_conformance_certificate(
        secret=conformance_secret,
        mcp_capability_manifest_configured=True,
        mcp_capability_manifest_valid=False,
    )

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        if str(url).endswith("/runtime/conformance"):
            return StubHttpResponse(status=200, payload=conformance_payload)
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    witness = collect_deployment_witness(
        gateway_url="https://gateway.example",
        witness_secret=witness_secret,
        conformance_secret=conformance_secret,
        expected_environment="pilot",
        clock=lambda: "2026-04-25T00:00:00+00:00",
    )
    conformance_step = next(step for step in witness.steps if step.name == "runtime conformance certificate")

    assert witness.deployment_claim == "not-published"
    assert witness.conformance_signature_status == "verified"
    assert conformance_step.passed is False
    assert "mcp_manifest_configured=True" in conformance_step.detail
    assert "mcp_manifest_valid=False" in conformance_step.detail
    assert "runtime conformance certificate is missing acceptable production evidence" in witness.errors


def test_collect_deployment_witness_rejects_missing_plan_bundle_witness(monkeypatch) -> None:
    witness_secret = "runtime-secret"
    conformance_secret = "conformance-secret"
    witness_payload = _signed_runtime_witness(secret=witness_secret)
    conformance_payload = _signed_conformance_certificate(
        secret=conformance_secret,
        capability_plan_bundle_canary_passed=False,
    )

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        if str(url).endswith("/runtime/conformance"):
            return StubHttpResponse(status=200, payload=conformance_payload)
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    witness = collect_deployment_witness(
        gateway_url="https://gateway.example",
        witness_secret=witness_secret,
        conformance_secret=conformance_secret,
        expected_environment="pilot",
        clock=lambda: "2026-04-25T00:00:00+00:00",
    )
    conformance_step = next(step for step in witness.steps if step.name == "runtime conformance certificate")

    assert witness.deployment_claim == "not-published"
    assert witness.conformance_signature_status == "verified"
    assert conformance_step.passed is False
    assert "plan_bundle_passed=False" in conformance_step.detail
    assert "runtime conformance certificate is missing acceptable production evidence" in witness.errors


def test_write_deployment_witness_persists_json(tmp_path, monkeypatch) -> None:
    witness_payload = _signed_runtime_witness(secret="runtime-secret")
    conformance_payload = _signed_conformance_certificate(secret="conformance-secret")

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        if str(url).endswith("/runtime/conformance"):
            return StubHttpResponse(status=200, payload=conformance_payload)
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    witness = collect_deployment_witness(
        gateway_url="https://gateway.example",
        witness_secret="runtime-secret",
        conformance_secret="conformance-secret",
        clock=lambda: "2026-04-25T00:00:00+00:00",
    )
    output_path = tmp_path / "deployment_witness.json"

    written = write_deployment_witness(witness, output_path)
    loaded = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert loaded["deployment_claim"] == "published"
    assert loaded["witness_id"] == witness.witness_id
    assert loaded["latest_conformance_certificate_id"] == "conf-0123456789abcdef"
    assert loaded["runtime_responsibility_debt_clear"] is True
    assert loaded["authority_responsibility_debt_clear"] is True
    assert loaded["authority_overdue_approval_chain_count"] == 0
    assert loaded["authority_overdue_obligation_count"] == 0
    assert loaded["steps"][0]["name"] == "gateway health"
    assert _validate_schema_instance(_load_schema(DEPLOYMENT_WITNESS_SCHEMA_PATH), loaded) == []


def test_cli_writes_not_published_witness_without_secret(tmp_path, monkeypatch, capsys) -> None:
    witness_payload = _signed_runtime_witness(secret="runtime-secret")
    conformance_payload = _signed_conformance_certificate(secret="conformance-secret")

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        if str(url).endswith("/runtime/conformance"):
            return StubHttpResponse(status=200, payload=conformance_payload)
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
    assert loaded["conformance_signature_status"] == "skipped:no_conformance_secret"
    assert _validate_schema_instance(_load_schema(DEPLOYMENT_WITNESS_SCHEMA_PATH), loaded) == []


def _signed_runtime_witness(
    *,
    secret: str,
    responsibility_debt_clear: bool = True,
) -> dict[str, Any]:
    payload = {
        "witness_id": "runtime-witness-test",
        "environment": "pilot",
        "runtime_status": "healthy",
        "gateway_status": "healthy",
        "responsibility_debt_clear": responsibility_debt_clear,
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


def _signed_conformance_certificate(
    *,
    secret: str,
    expires_at: str = "2026-04-25T00:30:00+00:00",
    authority_responsibility_debt_clear: bool = True,
    mcp_capability_manifest_configured: bool = True,
    mcp_capability_manifest_valid: bool = True,
    capability_plan_bundle_canary_passed: bool = True,
    capability_plan_bundle_count: int = 0,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "certificate_id": "conf-0123456789abcdef",
        "environment": "pilot",
        "issued_at": "2026-04-25T00:00:00+00:00",
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
        "authority_responsibility_debt_clear": authority_responsibility_debt_clear,
        "mcp_capability_manifest_configured": mcp_capability_manifest_configured,
        "mcp_capability_manifest_valid": mcp_capability_manifest_valid,
        "mcp_capability_manifest_capability_count": (
            1 if mcp_capability_manifest_configured else 0
        ),
        "capability_plan_bundle_canary_passed": capability_plan_bundle_canary_passed,
        "capability_plan_bundle_count": capability_plan_bundle_count,
        "authority_pending_approval_chain_count": 0,
        "authority_overdue_approval_chain_count": 0,
        "authority_open_obligation_count": 0,
        "authority_overdue_obligation_count": 0,
        "authority_escalated_obligation_count": 0,
        "authority_unowned_high_risk_capability_count": 0,
        "authority_directory_sync_receipt_valid": True,
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
    if overrides:
        payload.update(overrides)
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
