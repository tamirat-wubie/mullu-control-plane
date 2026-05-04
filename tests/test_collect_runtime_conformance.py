"""Runtime conformance collector tests.

Purpose: verify live conformance certificate collection without network.
Governance scope: endpoint probing, certificate signature verification, and
structured persistence.
Dependencies: scripts.collect_runtime_conformance.
Invariants:
  - A complete signed certificate can be collected and verified.
  - Missing conformance secrets keep signature status explicit.
  - Expired certificates are rejected even when signature verification passes.
  - Degraded or non-conformant terminal status is rejected.
  - Certificates with invalid embedded runtime or gateway witness state are rejected.
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

    monkeypatch.setattr("urllib.request.urlopen", _urlopen_for_certificate(certificate))

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

    monkeypatch.setattr("urllib.request.urlopen", _urlopen_for_certificate(certificate))

    collection = collect_runtime_conformance(
        gateway_url="http://localhost:8001",
        conformance_secret="",
    )
    signature_step = next(step for step in collection.steps if step.name == "runtime conformance signature")

    assert collection.signature_status == "skipped:no_conformance_secret"
    assert signature_step.passed is False
    assert "runtime conformance signature was not verified" in collection.errors


def test_collect_runtime_conformance_rejects_expired_certificate(monkeypatch) -> None:
    secret = "conformance-secret"
    certificate = _signed_certificate(
        secret=secret,
        expires_at="2026-04-25T12:00:00+00:00",
    )

    monkeypatch.setattr("urllib.request.urlopen", _urlopen_for_certificate(certificate))

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


def test_collect_runtime_conformance_rejects_degraded_status(monkeypatch) -> None:
    secret = "conformance-secret"
    certificate = _signed_certificate(secret=secret, terminal_status="degraded")

    monkeypatch.setattr("urllib.request.urlopen", _urlopen_for_certificate(certificate))

    collection = collect_runtime_conformance(
        gateway_url="http://localhost:8001",
        conformance_secret=secret,
    )
    status_step = next(step for step in collection.steps if step.name == "runtime conformance terminal status")

    assert collection.certificate_status == "degraded"
    assert collection.signature_status == "verified"
    assert status_step.passed is False
    assert "terminal_status=degraded" in status_step.detail
    assert "runtime conformance terminal status was not acceptable" in collection.errors


def test_collect_runtime_conformance_rejects_invalid_embedded_witness(monkeypatch) -> None:
    secret = "conformance-secret"
    certificate = _signed_certificate(
        secret=secret,
        gateway_witness_valid=False,
        runtime_witness_valid=True,
    )

    monkeypatch.setattr("urllib.request.urlopen", _urlopen_for_certificate(certificate))

    collection = collect_runtime_conformance(
        gateway_url="http://localhost:8001",
        conformance_secret=secret,
    )
    witness_step = next(
        step for step in collection.steps
        if step.name == "runtime conformance witness validity"
    )

    assert collection.certificate_status == "conformant_with_gaps"
    assert collection.signature_status == "verified"
    assert witness_step.passed is False
    assert "gateway_witness_valid=False" in witness_step.detail
    assert "runtime_witness_valid=True" in witness_step.detail
    assert "runtime conformance embedded witness validity failed" in collection.errors


def test_collect_runtime_conformance_rejects_failed_core_canary(monkeypatch) -> None:
    secret = "conformance-secret"
    certificate = _signed_certificate(
        secret=secret,
        overrides={"command_closure_canary_passed": False},
    )

    monkeypatch.setattr("urllib.request.urlopen", _urlopen_for_certificate(certificate))

    collection = collect_runtime_conformance(
        gateway_url="http://localhost:8001",
        conformance_secret=secret,
    )
    canary_step = next(
        step for step in collection.steps
        if step.name == "runtime conformance core canaries"
    )

    assert collection.certificate_status == "conformant_with_gaps"
    assert collection.signature_status == "verified"
    assert canary_step.passed is False
    assert "command_closure_canary_passed" in canary_step.detail
    assert "runtime conformance core canaries did not all pass" in collection.errors


def test_collect_runtime_conformance_rejects_unclear_responsibility_debt(monkeypatch) -> None:
    secret = "conformance-secret"
    certificate = _signed_certificate(
        secret=secret,
        authority_responsibility_debt_clear=False,
        authority_overdue_obligation_count=1,
    )

    monkeypatch.setattr("urllib.request.urlopen", _urlopen_for_certificate(certificate))

    collection = collect_runtime_conformance(
        gateway_url="http://localhost:8001",
        conformance_secret=secret,
    )
    debt_step = next(
        step for step in collection.steps
        if step.name == "runtime conformance authority responsibility debt"
    )

    assert debt_step.passed is False
    assert "overdue_obligation_count=1" in debt_step.detail
    assert "runtime conformance authority responsibility debt was not clear" in collection.errors


def test_collect_runtime_conformance_rejects_invalid_mcp_manifest(monkeypatch) -> None:
    secret = "conformance-secret"
    certificate = _signed_certificate(
        secret=secret,
        mcp_capability_manifest_configured=True,
        mcp_capability_manifest_valid=False,
    )

    monkeypatch.setattr("urllib.request.urlopen", _urlopen_for_certificate(certificate))

    collection = collect_runtime_conformance(
        gateway_url="http://localhost:8001",
        conformance_secret=secret,
    )
    manifest_step = next(
        step for step in collection.steps
        if step.name == "runtime conformance mcp capability manifest"
    )

    assert manifest_step.passed is False
    assert "configured=True" in manifest_step.detail
    assert "valid=False" in manifest_step.detail
    assert "runtime conformance MCP capability manifest was not valid" in collection.errors


def test_collect_runtime_conformance_rejects_missing_plan_bundle_witness(monkeypatch) -> None:
    secret = "conformance-secret"
    certificate = _signed_certificate(
        secret=secret,
        capability_plan_bundle_canary_passed=False,
    )

    monkeypatch.setattr("urllib.request.urlopen", _urlopen_for_certificate(certificate))

    collection = collect_runtime_conformance(
        gateway_url="http://localhost:8001",
        conformance_secret=secret,
    )
    bundle_step = next(
        step for step in collection.steps
        if step.name == "runtime conformance capability plan evidence bundle"
    )

    assert bundle_step.passed is False
    assert "passed=False" in bundle_step.detail
    assert "bundle_count=0" in bundle_step.detail
    assert "runtime conformance capability plan evidence bundle was not witnessed" in collection.errors


def test_collect_runtime_conformance_records_authority_read_model_failures(monkeypatch) -> None:
    secret = "conformance-secret"
    certificate = _signed_certificate(secret=secret)
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _urlopen_for_certificate(certificate, authority_status=404),
    )

    collection = collect_runtime_conformance(
        gateway_url="http://localhost:8001",
        conformance_secret=secret,
    )
    approval_step = next(
        step for step in collection.steps
        if step.name == "authority overdue approval chain read model"
    )
    obligation_step = next(
        step for step in collection.steps
        if step.name == "authority overdue obligation read model"
    )
    ownership_step = next(
        step for step in collection.steps
        if step.name == "authority ownership read model"
    )
    policy_step = next(
        step for step in collection.steps
        if step.name == "authority policy read model"
    )
    responsibility_step = next(
        step for step in collection.steps
        if step.name == "authority responsibility cockpit read model"
    )

    assert approval_step.passed is False
    assert obligation_step.passed is False
    assert ownership_step.passed is False
    assert policy_step.passed is False
    assert responsibility_step.passed is False
    assert "status=404" in approval_step.detail
    assert "status=404" in obligation_step.detail
    assert "status=404" in ownership_step.detail
    assert "status=404" in policy_step.detail
    assert "status=404" in responsibility_step.detail
    assert "authority overdue approval chain read model was not available" in collection.errors
    assert "authority overdue obligation read model was not available" in collection.errors
    assert "authority ownership read model was not available" in collection.errors
    assert "authority policy read model was not available" in collection.errors
    assert "authority responsibility cockpit read model was not available" in collection.errors


def test_collect_runtime_conformance_records_malformed_responsibility_read_model(monkeypatch) -> None:
    secret = "conformance-secret"
    certificate = _signed_certificate(secret=secret)
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _urlopen_for_certificate(certificate, responsibility_payload={"authority_witness": {}}),
    )

    collection = collect_runtime_conformance(
        gateway_url="http://localhost:8001",
        conformance_secret=secret,
    )
    responsibility_step = next(
        step for step in collection.steps
        if step.name == "authority responsibility cockpit read model"
    )

    assert responsibility_step.passed is False
    assert "debt_clear=missing" in responsibility_step.detail
    assert "authority responsibility cockpit read model was not available" in collection.errors


def test_write_runtime_conformance_persists_json(tmp_path, monkeypatch) -> None:
    certificate = _signed_certificate(secret="conformance-secret")

    monkeypatch.setattr("urllib.request.urlopen", _urlopen_for_certificate(certificate))
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

    monkeypatch.setattr("urllib.request.urlopen", _urlopen_for_certificate(certificate))
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


def _urlopen_for_certificate(
    certificate: dict[str, Any],
    *,
    authority_status: int = 200,
    responsibility_payload: dict[str, Any] | None = None,
) -> Any:
    def fake_urlopen(request, timeout):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        if url.endswith("/runtime/conformance"):
            return StubHttpResponse(status=200, payload=certificate)
        if "/authority/approval-chains?overdue=true&limit=1" in url:
            return StubHttpResponse(
                status=authority_status,
                payload={"approval_chains": [], "count": 0} if authority_status == 200 else {},
            )
        if "/authority/obligations?overdue=true&limit=1" in url:
            return StubHttpResponse(
                status=authority_status,
                payload={"obligations": [], "count": 0} if authority_status == 200 else {},
            )
        if "/authority/ownership?limit=1" in url:
            return StubHttpResponse(
                status=authority_status,
                payload={"ownership": [], "count": 0} if authority_status == 200 else {},
            )
        if "/authority/policies?limit=1" in url:
            return StubHttpResponse(
                status=authority_status,
                payload={
                    "approval_policies": [],
                    "escalation_policies": [],
                    "approval_count": 0,
                    "escalation_count": 0,
                } if authority_status == 200 else {},
            )
        if "/authority/responsibility?limit=1" in url:
            return StubHttpResponse(
                status=authority_status,
                payload=responsibility_payload if responsibility_payload is not None else {
                    "responsibility_debt_clear": True,
                    "authority_witness": {},
                    "ownership_count": 0,
                    "approval_policy_count": 0,
                    "escalation_policy_count": 0,
                    "pending_approval_chain_count": 0,
                    "unresolved_obligation_count": 0,
                    "escalation_event_count": 0,
                    "priority_approval_chains": [],
                    "priority_obligations": [],
                    "priority_escalation_events": [],
                    "limit": 1,
                    "evidence_refs": ["authority:witness"],
                } if authority_status == 200 else {},
            )
        return StubHttpResponse(status=404, payload={})

    return fake_urlopen


def _signed_certificate(
    *,
    secret: str,
    expires_at: str = "2099-04-25T12:30:00+00:00",
    terminal_status: str = "conformant_with_gaps",
    gateway_witness_valid: bool = True,
    runtime_witness_valid: bool = True,
    authority_responsibility_debt_clear: bool = True,
    authority_overdue_obligation_count: int = 0,
    mcp_capability_manifest_configured: bool = False,
    mcp_capability_manifest_valid: bool = True,
    capability_plan_bundle_canary_passed: bool = True,
    capability_plan_bundle_count: int = 0,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "certificate_id": "conf-0123456789abcdef",
        "environment": "pilot",
        "issued_at": "2026-04-25T12:00:00+00:00",
        "expires_at": expires_at,
        "gateway_witness_valid": gateway_witness_valid,
        "runtime_witness_valid": runtime_witness_valid,
        "latest_anchor_valid": True,
        "command_closure_canary_passed": True,
        "capability_admission_canary_passed": True,
        "dangerous_capability_isolation_canary_passed": True,
        "streaming_budget_canary_passed": True,
        "lineage_query_canary_passed": True,
        "authority_obligation_canary_passed": True,
        "authority_responsibility_debt_clear": authority_responsibility_debt_clear,
        "authority_pending_approval_chain_count": 0,
        "authority_overdue_approval_chain_count": 0,
        "authority_open_obligation_count": authority_overdue_obligation_count,
        "authority_overdue_obligation_count": authority_overdue_obligation_count,
        "authority_escalated_obligation_count": 0,
        "authority_unowned_high_risk_capability_count": 0,
        "authority_directory_sync_receipt_valid": True,
        "mcp_capability_manifest_configured": mcp_capability_manifest_configured,
        "mcp_capability_manifest_valid": mcp_capability_manifest_valid,
        "mcp_capability_manifest_capability_count": 1 if mcp_capability_manifest_configured else 0,
        "capability_plan_bundle_canary_passed": capability_plan_bundle_canary_passed,
        "capability_plan_bundle_count": capability_plan_bundle_count,
        "capsule_registry_certified": True,
        "proof_coverage_matrix_current": True,
        "known_limitations_aligned": False,
        "security_model_aligned": False,
        "open_conformance_gaps": ["known_limitations_documentation_drift"],
        "terminal_status": terminal_status,
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
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    signature = hmac.new(secret.encode("utf-8"), digest.encode("utf-8"), hashlib.sha256).hexdigest()
    return {**payload, "signature": f"hmac-sha256:{signature}"}
