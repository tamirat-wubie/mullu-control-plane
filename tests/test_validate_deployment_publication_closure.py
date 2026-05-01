"""Tests for deployment publication closure validation.

Purpose: prove public deployment publication claims are tied to witness
evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_deployment_publication_closure.
Invariants:
  - Current not-published status passes without live witness evidence.
  - Published status requires a collected witness artifact.
  - Published witness artifacts must carry verified signatures and passing steps.
"""

from __future__ import annotations

from pathlib import Path

from scripts.validate_deployment_publication_closure import (
    validate_publication_closure,
)


def test_not_published_status_passes_without_witness() -> None:
    errors = validate_publication_closure(
        deployment_status_text=_deployment_status("not-published", "not-declared"),
        witness_payload=None,
    )

    assert errors == []
    assert len(errors) == 0
    assert "not-published" in _deployment_status("not-published", "not-declared")


def test_not_published_status_rejects_declared_health_endpoint() -> None:
    errors = validate_publication_closure(
        deployment_status_text=_deployment_status(
            "not-published",
            "https://gateway.example/health",
        ),
        witness_payload=None,
    )

    assert len(errors) == 1
    assert "not-published deployment" in errors[0]
    assert "not-declared" in errors[0]


def test_not_published_status_rejects_published_witness_conflict() -> None:
    errors = validate_publication_closure(
        deployment_status_text=_deployment_status("not-published", "not-declared"),
        witness_payload=_published_witness(),
        witness_path=Path(".change_assurance/deployment_witness.json"),
    )

    assert len(errors) == 1
    assert "published witness conflicts" in errors[0]
    assert "not-published status" in errors[0]


def test_published_status_requires_witness_artifact() -> None:
    errors = validate_publication_closure(
        deployment_status_text=_deployment_status(
            "published",
            "https://gateway.example/health",
        ),
        witness_payload=None,
        witness_path=Path(".change_assurance/deployment_witness.json"),
    )

    assert len(errors) == 1
    assert "published deployment requires witness artifact" in errors[0]
    assert "deployment_witness.json" in errors[0]


def test_published_status_accepts_verified_witness() -> None:
    errors = validate_publication_closure(
        deployment_status_text=_deployment_status(
            "published",
            "https://gateway.example/health",
        ),
        witness_payload=_published_witness(),
    )

    assert errors == []
    assert _published_witness()["deployment_claim"] == "published"
    assert _published_witness()["signature_status"] == "verified"


def test_published_status_rejects_health_endpoint_witness_mismatch() -> None:
    errors = validate_publication_closure(
        deployment_status_text=_deployment_status(
            "published",
            "https://other-gateway.example/health",
        ),
        witness_payload=_published_witness(),
        witness_path=Path(".change_assurance/deployment_witness.json"),
    )

    assert len(errors) == 1
    assert "public production health endpoint does not match" in errors[0]
    assert "https://other-gateway.example/health" in errors[0]
    assert "https://gateway.example/health" in errors[0]


def test_published_status_rejects_unverified_witness() -> None:
    witness = _published_witness()
    witness["signature_status"] = "failed:mismatch"
    witness["steps"][1]["passed"] = False

    errors = validate_publication_closure(
        deployment_status_text=_deployment_status(
            "published",
            "https://gateway.example/health",
        ),
        witness_payload=witness,
        witness_path=Path(".change_assurance/deployment_witness.json"),
    )

    assert len(errors) == 2
    assert "signature_status 'failed:mismatch' != 'verified'" in errors[0]
    assert "witness step failed" in errors[1]


def _deployment_status(state: str, public_health_endpoint: str) -> str:
    return "\n".join(
        (
            "# Deployment Status Witness",
            "",
            f"**Deployment witness state:** `{state}`",
            f"**Public production health endpoint:** `{public_health_endpoint}`",
            "",
        )
    )


def _published_witness() -> dict[str, object]:
    return {
        "witness_id": "deployment-witness-001",
        "gateway_url": "https://gateway.example",
        "deployment_claim": "published",
        "health_status": "healthy",
        "runtime_witness_status": "healthy",
        "signature_status": "verified",
        "conformance_status": "conformant",
        "conformance_signature_status": "verified",
        "latest_conformance_certificate_id": "conf-001",
        "latest_terminal_certificate_id": "terminal-001",
        "latest_command_event_hash": "event-hash-001",
        "runtime_witness_id": "runtime-witness-001",
        "runtime_environment": "pilot",
        "runtime_signature_key_id": "runtime-key-001",
        "steps": [
            {"name": "gateway health", "passed": True, "detail": "ok"},
            {"name": "gateway runtime witness", "passed": True, "detail": "ok"},
            {"name": "runtime conformance signature", "passed": True, "detail": "ok"},
        ],
    }
