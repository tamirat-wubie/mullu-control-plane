"""Tests for live deployment witness collection.

Purpose: verify bounded gateway deployment witness collection without network.
Governance scope: [OCE, CDCV, UWMA, PRS]
Dependencies: scripts.collect_deployment_witness.
Invariants:
  - Published claims require health, runtime witness, conformance certificate,
    and signature proof.
  - Missing signature secrets keep the witness in not-published state.
  - Live physical capability claims require safety evidence; sandbox physical
    claims remain non-production.
  - CLI writes structured witness JSON for operator review.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.collect_deployment_witness import (
    REQUIRED_PHYSICAL_LIVE_EVIDENCE_FIELDS,
    collect_deployment_witness,
    main,
    write_deployment_witness,
    _evaluate_physical_capability_policy,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOYMENT_WITNESS_SCHEMA_PATH = REPO_ROOT / "schemas" / "deployment_witness.schema.json"
CAPABILITY_EVIDENCE_SCHEMA_PATH = REPO_ROOT / "schemas" / "capability_evidence_endpoint.schema.json"
PRODUCTION_EVIDENCE_SCHEMA_PATH = REPO_ROOT / "schemas" / "production_evidence_witness.schema.json"


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


def test_collect_deployment_witness_requires_production_evidence_plane(monkeypatch) -> None:
    secret = "runtime-secret"
    conformance_secret = "conformance-secret"
    deployment_secret = "deployment-secret"
    witness_payload = _signed_runtime_witness(secret=secret)
    conformance_payload = _signed_conformance_certificate(secret=conformance_secret)
    production_payload = _signed_production_evidence_witness(secret=deployment_secret)

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        if str(url).endswith("/runtime/conformance"):
            return StubHttpResponse(status=200, payload=conformance_payload)
        if str(url).endswith("/deployment/witness"):
            return StubHttpResponse(status=200, payload=production_payload)
        if str(url).endswith("/capabilities/evidence"):
            return StubHttpResponse(
                status=200,
                payload={
                    "runtime_env": "pilot",
                    "commit_sha": "abc123",
                    "deployment_id": "dep_001",
                    "enabled": True,
                    "capability_count": 1,
                    "capability_evidence": {"rag.query": "production"},
                    "live_capabilities": ["rag.query"],
                    "sandbox_only_capabilities": [],
                    "checks": [
                        {
                            "check_id": "capability_registry_configured",
                            "passed": True,
                            "detail": "capability_count=1",
                        }
                    ],
                },
            )
        if str(url).endswith("/audit/verify"):
            return StubHttpResponse(
                status=200,
                payload={
                    "valid": True,
                    "reason": "verified",
                    "entries_checked": 3,
                    "latest_anchor_id": "cmd-anchor-1",
                    "last_hash": "a" * 16,
                    "unanchored_event_count": 0,
                    "governed": True,
                },
            )
        if str(url).endswith("/proof/verify"):
            return StubHttpResponse(
                status=200,
                payload={
                    "valid": True,
                    "runtime_env": "pilot",
                    "deployment_id": "dep_001",
                    "commit_sha": "abc123",
                    "checks": [
                        {
                            "check_id": "audit_anchor_verification",
                            "passed": True,
                            "detail": "verified",
                        }
                    ],
                    "checks_passed": ["audit_anchor_verification"],
                    "checks_missing": [],
                    "terminal_status": "verified",
                    "governed": True,
                },
            )
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    witness = collect_deployment_witness(
        gateway_url="https://gateway.example",
        witness_secret=secret,
        conformance_secret=conformance_secret,
        deployment_witness_secret=deployment_secret,
        expected_environment="pilot",
        require_production_evidence=True,
        clock=lambda: "2026-04-25T00:00:00+00:00",
    )

    assert witness.deployment_claim == "published"
    assert all(step.passed for step in witness.steps)
    assert any(step.name == "production evidence witness" for step in witness.steps)
    assert any(step.name == "capability evidence endpoint" for step in witness.steps)
    assert any(step.name == "audit verification endpoint" for step in witness.steps)
    assert any(step.name == "proof verification endpoint" for step in witness.steps)


def test_collect_deployment_witness_rejects_live_physical_capability_without_safety_evidence(
    monkeypatch,
) -> None:
    secret = "runtime-secret"
    conformance_secret = "conformance-secret"
    deployment_secret = "deployment-secret"
    witness_payload = _signed_runtime_witness(secret=secret)
    conformance_payload = _signed_conformance_certificate(secret=conformance_secret)
    production_payload = _signed_production_evidence_witness(
        secret=deployment_secret,
        overrides={
            "capability_evidence": {"physical.unlock_door": "production"},
            "live_capabilities": ["physical.unlock_door"],
            "sandbox_only_capabilities": [],
        },
    )
    capability_payload = _capability_evidence_endpoint_payload(
        capability_evidence={"physical.unlock_door": "production"},
        live_capabilities=["physical.unlock_door"],
        sandbox_only_capabilities=[],
    )
    _install_production_evidence_urlopen(
        monkeypatch,
        witness_payload=witness_payload,
        conformance_payload=conformance_payload,
        production_payload=production_payload,
        capability_payload=capability_payload,
    )

    witness = collect_deployment_witness(
        gateway_url="https://gateway.example",
        witness_secret=secret,
        conformance_secret=conformance_secret,
        deployment_witness_secret=deployment_secret,
        expected_environment="pilot",
        require_production_evidence=True,
        clock=lambda: "2026-04-25T00:00:00+00:00",
    )
    production_step = next(step for step in witness.steps if step.name == "production evidence witness")
    capability_step = next(step for step in witness.steps if step.name == "capability evidence endpoint")

    assert witness.deployment_claim == "not-published"
    assert production_step.passed is False
    assert capability_step.passed is False
    assert "physical.unlock_door:physical_live_safety_evidence_required" in production_step.detail
    assert "physical.unlock_door:physical_live_safety_evidence_required" in capability_step.detail
    assert "production evidence witness includes live physical capability without safety evidence" in witness.errors
    assert "capability evidence endpoint includes live physical capability without safety evidence" in witness.errors


def test_collect_deployment_witness_allows_sandbox_physical_capability_without_live_claim(
    monkeypatch,
) -> None:
    secret = "runtime-secret"
    conformance_secret = "conformance-secret"
    deployment_secret = "deployment-secret"
    witness_payload = _signed_runtime_witness(secret=secret)
    conformance_payload = _signed_conformance_certificate(secret=conformance_secret)
    production_payload = _signed_production_evidence_witness(
        secret=deployment_secret,
        overrides={
            "capability_evidence": {
                "rag.query": "production",
                "physical.sandbox_replay": "sandbox",
            },
            "live_capabilities": ["rag.query"],
            "sandbox_only_capabilities": ["physical.sandbox_replay"],
        },
    )
    capability_payload = _capability_evidence_endpoint_payload(
        capability_evidence={
            "rag.query": "production",
            "physical.sandbox_replay": "sandbox",
        },
        live_capabilities=["rag.query"],
        sandbox_only_capabilities=["physical.sandbox_replay"],
    )
    _install_production_evidence_urlopen(
        monkeypatch,
        witness_payload=witness_payload,
        conformance_payload=conformance_payload,
        production_payload=production_payload,
        capability_payload=capability_payload,
    )

    witness = collect_deployment_witness(
        gateway_url="https://gateway.example",
        witness_secret=secret,
        conformance_secret=conformance_secret,
        deployment_witness_secret=deployment_secret,
        expected_environment="pilot",
        require_production_evidence=True,
        clock=lambda: "2026-04-25T00:00:00+00:00",
    )
    capability_step = next(step for step in witness.steps if step.name == "capability evidence endpoint")

    assert witness.deployment_claim == "published"
    assert capability_step.passed is True
    assert "sandbox_physical_capabilities=['physical.sandbox_replay']" in capability_step.detail
    assert "physical_policy_passed=True" in capability_step.detail
    assert not witness.errors


def test_collect_deployment_witness_allows_live_physical_capability_with_safety_evidence(
    monkeypatch,
) -> None:
    secret = "runtime-secret"
    conformance_secret = "conformance-secret"
    deployment_secret = "deployment-secret"
    physical_evidence = _physical_live_evidence()
    witness_payload = _signed_runtime_witness(secret=secret)
    conformance_payload = _signed_conformance_certificate(secret=conformance_secret)
    production_payload = _signed_production_evidence_witness(
        secret=deployment_secret,
        overrides={
            "capability_evidence": {"physical.unlock_door": physical_evidence},
            "live_capabilities": ["physical.unlock_door"],
            "sandbox_only_capabilities": [],
        },
    )
    capability_payload = _capability_evidence_endpoint_payload(
        capability_evidence={"physical.unlock_door": physical_evidence},
        live_capabilities=["physical.unlock_door"],
        sandbox_only_capabilities=[],
    )
    _install_production_evidence_urlopen(
        monkeypatch,
        witness_payload=witness_payload,
        conformance_payload=conformance_payload,
        production_payload=production_payload,
        capability_payload=capability_payload,
    )

    witness = collect_deployment_witness(
        gateway_url="https://gateway.example",
        witness_secret=secret,
        conformance_secret=conformance_secret,
        deployment_witness_secret=deployment_secret,
        expected_environment="pilot",
        require_production_evidence=True,
        clock=lambda: "2026-04-25T00:00:00+00:00",
    )
    production_step = next(step for step in witness.steps if step.name == "production evidence witness")
    capability_step = next(step for step in witness.steps if step.name == "capability evidence endpoint")

    assert witness.deployment_claim == "published"
    assert production_step.passed is True
    assert capability_step.passed is True
    assert "live_physical_capabilities=['physical.unlock_door']" in production_step.detail
    assert "physical_policy_passed=True" in capability_step.detail
    assert _validate_schema_instance(_load_schema(PRODUCTION_EVIDENCE_SCHEMA_PATH), production_payload) == []
    assert _validate_schema_instance(_load_schema(CAPABILITY_EVIDENCE_SCHEMA_PATH), capability_payload) == []


def test_collect_deployment_witness_rejects_missing_production_evidence_secret(monkeypatch) -> None:
    secret = "runtime-secret"
    conformance_secret = "conformance-secret"
    deployment_secret = "deployment-secret"
    witness_payload = _signed_runtime_witness(secret=secret)
    conformance_payload = _signed_conformance_certificate(secret=conformance_secret)
    production_payload = _signed_production_evidence_witness(secret=deployment_secret)

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        if str(url).endswith("/runtime/conformance"):
            return StubHttpResponse(status=200, payload=conformance_payload)
        if str(url).endswith("/deployment/witness"):
            return StubHttpResponse(status=200, payload=production_payload)
        if str(url).endswith("/capabilities/evidence"):
            return StubHttpResponse(
                status=200,
                payload={
                    "runtime_env": "pilot",
                    "commit_sha": "abc123",
                    "deployment_id": "dep_001",
                    "enabled": True,
                    "capability_count": 1,
                    "capability_evidence": {"rag.query": "production"},
                    "live_capabilities": ["rag.query"],
                    "sandbox_only_capabilities": [],
                    "checks": [{"check_id": "capability_registry_configured", "passed": True, "detail": "ok"}],
                },
            )
        if str(url).endswith("/audit/verify"):
            return StubHttpResponse(
                status=200,
                payload={
                    "valid": True,
                    "reason": "verified",
                    "entries_checked": 3,
                    "latest_anchor_id": "cmd-anchor-1",
                    "unanchored_event_count": 0,
                    "governed": True,
                },
            )
        if str(url).endswith("/proof/verify"):
            return StubHttpResponse(
                status=200,
                payload={
                    "valid": True,
                    "runtime_env": "pilot",
                    "deployment_id": "dep_001",
                    "commit_sha": "abc123",
                    "checks": [{"check_id": "audit_anchor_verification", "passed": True, "detail": "verified"}],
                    "checks_passed": ["audit_anchor_verification"],
                    "checks_missing": [],
                    "terminal_status": "verified",
                    "governed": True,
                },
            )
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    witness = collect_deployment_witness(
        gateway_url="https://gateway.example",
        witness_secret=secret,
        conformance_secret=conformance_secret,
        deployment_witness_secret="",
        expected_environment="pilot",
        require_production_evidence=True,
        clock=lambda: "2026-04-25T00:00:00+00:00",
    )
    production_step = next(step for step in witness.steps if step.name == "production evidence witness")

    assert witness.deployment_claim == "not-published"
    assert production_step.passed is False
    assert "signature=skipped:no_deployment_witness_secret" in production_step.detail
    assert "production evidence witness is missing required closure" in witness.errors


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


def test_collect_deployment_witness_rejects_unclassified_proof_routes(monkeypatch) -> None:
    witness_secret = "runtime-secret"
    conformance_secret = "conformance-secret"
    witness_payload = _signed_runtime_witness(secret=witness_secret)
    conformance_payload = _signed_conformance_certificate(
        secret=conformance_secret,
        overrides={
            "proof_coverage_declared_routes_classified": False,
            "proof_coverage_declared_route_count": 301,
            "proof_coverage_unclassified_route_count": 237,
        },
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
    assert conformance_step.passed is False
    assert "proof_coverage_declared_routes_classified" in conformance_step.detail
    assert "proof_route_unclassified_count=237" in conformance_step.detail
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


def test_collect_deployment_witness_rejects_missing_physical_worker_canary(monkeypatch) -> None:
    witness_secret = "runtime-secret"
    conformance_secret = "conformance-secret"
    witness_payload = _signed_runtime_witness(secret=witness_secret)
    conformance_payload = _signed_conformance_certificate(
        secret=conformance_secret,
        overrides={
            "physical_worker_canary_passed": False,
            "physical_worker_canary_evidence_count": 0,
        },
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
    assert "physical_worker_canary_passed=False" in conformance_step.detail
    assert "physical_worker_canary_evidence_count=0" in conformance_step.detail
    assert "runtime conformance certificate is missing acceptable production evidence" in witness.errors


def test_physical_capability_policy_allows_sandbox_only_physical_capability() -> None:
    policy = _evaluate_physical_capability_policy(
        {
            "live_capabilities": ["rag.query"],
            "sandbox_only_capabilities": ["physical.arm.move", "iot.sensor.read"],
            "checks": [],
        }
    )

    assert policy.passed is True
    assert policy.live_physical_capabilities == ()
    assert policy.sandbox_physical_capabilities == ("physical.arm.move", "iot.sensor.read")
    assert policy.blockers == ()


def test_physical_capability_policy_blocks_live_physical_without_safety_evidence() -> None:
    policy = _evaluate_physical_capability_policy(
        {
            "live_capabilities": ["physical.arm.move"],
            "sandbox_only_capabilities": ["physical.arm.simulate"],
            "checks": [],
        }
    )

    assert policy.passed is False
    assert policy.live_physical_capabilities == ("physical.arm.move",)
    assert policy.sandbox_physical_capabilities == ("physical.arm.simulate",)
    assert policy.blockers == ("physical.arm.move:physical_live_safety_evidence_required",)


def test_physical_capability_policy_accepts_live_physical_with_passed_safety_checks() -> None:
    policy = _evaluate_physical_capability_policy(
        {
            "live_capabilities": ["robotics.gripper.close"],
            "sandbox_only_capabilities": [],
            "capability_evidence": {
                "robotics.gripper.close": {
                    "maturity": "production",
                    "effect_mode": "live",
                    "production_admissible": True,
                    "physical_action_receipt_schema_ref": "urn:mullusi:schema:physical-action-receipt:1",
                    **{field_name: f"{field_name}:ref" for field_name in REQUIRED_PHYSICAL_LIVE_EVIDENCE_FIELDS},
                }
            },
        }
    )

    assert policy.passed is True
    assert policy.live_physical_capabilities == ("robotics.gripper.close",)
    assert policy.sandbox_physical_capabilities == ()
    assert policy.blockers == ()


def test_collect_deployment_witness_reports_health_body_by_digest_only(monkeypatch) -> None:
    witness_secret = "runtime-secret"
    conformance_secret = "conformance-secret"
    witness_payload = _signed_runtime_witness(secret=witness_secret)
    conformance_payload = _signed_conformance_certificate(secret=conformance_secret)

    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(
                status=200,
                payload={"status": "healthy", "internal_secret": "health-secret"},
            )
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
    health_step = next(step for step in witness.steps if step.name == "gateway health")
    serialized_witness = json.dumps(witness.to_json_dict(), sort_keys=True)

    assert witness.deployment_claim == "published"
    assert witness.health_response_digest.startswith("sha256:")
    assert "response_digest=sha256:" in health_step.detail
    assert "health-secret" not in serialized_witness
    assert "internal_secret" not in serialized_witness


def test_collect_deployment_witness_omits_raw_conformance_evidence(monkeypatch) -> None:
    witness_secret = "runtime-secret"
    conformance_secret = "conformance-secret"
    witness_payload = _signed_runtime_witness(secret=witness_secret)
    conformance_payload = _signed_conformance_certificate(
        secret=conformance_secret,
        overrides={
            "evidence_refs": ["proof://private-conformance-evidence"],
            "checks": [
                {
                    "check_id": "private_check",
                    "passed": True,
                    "evidence_ref": "proof://private-check-evidence",
                    "detail": "private-check-detail",
                }
            ],
        },
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
    serialized_witness = json.dumps(witness.to_json_dict(), sort_keys=True)

    assert witness.deployment_claim == "published"
    assert witness.latest_conformance_certificate_id == "conf-0123456789abcdef"
    assert "private-conformance-evidence" not in serialized_witness
    assert "private-check-evidence" not in serialized_witness
    assert "private-check-detail" not in serialized_witness


def test_collect_deployment_witness_signature_mismatch_details_are_bounded(monkeypatch) -> None:
    witness_payload = _signed_runtime_witness(secret="runtime-payload-secret")
    conformance_payload = _signed_conformance_certificate(secret="conformance-payload-secret")

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
        witness_secret="runtime-collector-secret",
        conformance_secret="conformance-collector-secret",
        expected_environment="pilot",
        clock=lambda: "2026-04-25T00:00:00+00:00",
    )
    runtime_signature_step = next(step for step in witness.steps if step.name == "runtime witness signature")
    conformance_signature_step = next(
        step for step in witness.steps
        if step.name == "runtime conformance signature"
    )
    serialized_witness = json.dumps(witness.to_json_dict(), sort_keys=True)

    assert witness.deployment_claim == "not-published"
    assert witness.signature_status == "failed:mismatch"
    assert witness.conformance_signature_status == "failed:mismatch"
    assert runtime_signature_step.detail == "failed:mismatch"
    assert conformance_signature_step.detail == "failed:mismatch"
    assert "runtime-payload-secret" not in serialized_witness
    assert "runtime-collector-secret" not in serialized_witness
    assert "conformance-payload-secret" not in serialized_witness
    assert "conformance-collector-secret" not in serialized_witness


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
        "physical_worker_canary_passed": True,
        "physical_worker_canary_id": "physical-worker-canary-0123456789abcdef",
        "physical_worker_canary_artifact_hash": "1" * 64,
        "physical_worker_canary_evidence_count": 3,
        "authority_pending_approval_chain_count": 0,
        "authority_overdue_approval_chain_count": 0,
        "authority_open_obligation_count": 0,
        "authority_overdue_obligation_count": 0,
        "authority_escalated_obligation_count": 0,
        "authority_unowned_high_risk_capability_count": 0,
        "authority_directory_sync_receipt_valid": True,
        "capsule_registry_certified": True,
        "proof_coverage_matrix_current": True,
        "proof_coverage_declared_routes_classified": True,
        "proof_coverage_declared_route_count": 301,
        "proof_coverage_unclassified_route_count": 0,
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


def _signed_production_evidence_witness(
    *,
    secret: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "deployment_id": "dep_001",
        "commit_sha": "abc123",
        "runtime_env": "pilot",
        "version": "1.0.0",
        "gateway_health": "pass",
        "api_health": "pass",
        "db_health": "pass",
        "policy_engine": "pass",
        "audit_store": "pass",
        "proof_store": "pass",
        "capability_evidence": {"rag.query": "production"},
        "live_capabilities": ["rag.query"],
        "sandbox_only_capabilities": [],
        "checks": [
            {"check_id": "gateway_health", "passed": True, "detail": "healthy"},
            {"check_id": "audit_anchor", "passed": True, "detail": "cmd-anchor-1"},
            {"check_id": "proof_store", "passed": True, "detail": "terminal_certificates=1"},
        ],
        "checks_passed": ["gateway_health", "audit_anchor", "proof_store"],
        "checks_missing": [],
        "runtime_conformance_certificate_id": "conf-0123456789abcdef",
        "signed_at": "2026-04-25T00:00:00+00:00",
        "witness": "mullu_gateway_production_evidence_v1",
        "signature_key_id": "deployment-witness-test",
    }
    if overrides:
        payload.update(overrides)
    import hashlib
    import hmac

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    claim_hash = hashlib.sha256(canonical).hexdigest()
    signature = hmac.new(
        secret.encode("utf-8"),
        claim_hash.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {**payload, "claim_hash": claim_hash, "signature": f"hmac-sha256:{signature}"}


def _capability_evidence_endpoint_payload(
    *,
    capability_evidence: dict[str, Any] | None = None,
    live_capabilities: list[str] | None = None,
    sandbox_only_capabilities: list[str] | None = None,
) -> dict[str, Any]:
    evidence = capability_evidence or {"rag.query": "production"}
    return {
        "runtime_env": "pilot",
        "commit_sha": "abc123",
        "deployment_id": "dep_001",
        "enabled": True,
        "capability_count": len(evidence),
        "capability_evidence": evidence,
        "live_capabilities": live_capabilities if live_capabilities is not None else ["rag.query"],
        "sandbox_only_capabilities": (
            sandbox_only_capabilities
            if sandbox_only_capabilities is not None
            else []
        ),
        "checks": [
            {
                "check_id": "capability_registry_configured",
                "passed": True,
                "detail": f"capability_count={len(evidence)}",
            }
        ],
    }


def _physical_live_evidence() -> dict[str, Any]:
    return {
        "maturity": "production",
        "effect_mode": "live",
        "production_admissible": True,
        "physical_action_receipt_schema_ref": "urn:mullusi:schema:physical-action-receipt:1",
        "physical_action_receipt_ref": "physical-action-receipt-0123456789abcdef",
        "simulation_ref": "proof://physical/simulation-pass",
        "operator_approval_ref": "approval:physical-live",
        "manual_override_ref": "manual-override:physical-live",
        "emergency_stop_ref": "emergency-stop:physical-live",
        "sensor_confirmation_ref": "sensor-confirmation:physical-live",
        "deployment_witness_ref": "deployment-witness:physical-live",
    }


def _install_production_evidence_urlopen(
    monkeypatch,
    *,
    witness_payload: dict[str, Any],
    conformance_payload: dict[str, Any],
    production_payload: dict[str, Any],
    capability_payload: dict[str, Any],
) -> None:
    def fake_urlopen(url, timeout):
        if str(url).endswith("/health"):
            return StubHttpResponse(status=200, payload={"status": "healthy"})
        if str(url).endswith("/gateway/witness"):
            return StubHttpResponse(status=200, payload=witness_payload)
        if str(url).endswith("/runtime/conformance"):
            return StubHttpResponse(status=200, payload=conformance_payload)
        if str(url).endswith("/deployment/witness"):
            return StubHttpResponse(status=200, payload=production_payload)
        if str(url).endswith("/capabilities/evidence"):
            return StubHttpResponse(status=200, payload=capability_payload)
        if str(url).endswith("/audit/verify"):
            return StubHttpResponse(
                status=200,
                payload={
                    "valid": True,
                    "reason": "verified",
                    "entries_checked": 3,
                    "latest_anchor_id": "cmd-anchor-1",
                    "last_hash": "a" * 16,
                    "unanchored_event_count": 0,
                    "governed": True,
                },
            )
        if str(url).endswith("/proof/verify"):
            return StubHttpResponse(
                status=200,
                payload={
                    "valid": True,
                    "runtime_env": "pilot",
                    "deployment_id": "dep_001",
                    "commit_sha": "abc123",
                    "checks": [
                        {
                            "check_id": "audit_anchor_verification",
                            "passed": True,
                            "detail": "verified",
                        }
                    ],
                    "checks_passed": ["audit_anchor_verification"],
                    "checks_missing": [],
                    "terminal_status": "verified",
                    "governed": True,
                },
            )
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
