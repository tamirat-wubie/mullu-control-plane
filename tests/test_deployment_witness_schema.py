"""Tests for the public deployment witness schema.

Purpose: prove collected deployment witness artifacts have a public protocol
contract.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: schemas/deployment_witness.schema.json and schema validator.
Invariants:
  - Published witness artifacts validate against the public schema.
  - Required witness identity and probe steps fail closed when malformed.
  - The schema accepts failed not-published artifacts for operator review.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from scripts.validate_schemas import _load_schema, _validate_schema_instance


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "deployment_witness.schema.json"


def test_deployment_witness_schema_accepts_published_witness() -> None:
    schema = _load_schema(SCHEMA_PATH)
    witness = _deployment_witness()

    errors = _validate_schema_instance(schema, witness)

    assert errors == []
    assert schema["$id"] == "urn:mullusi:schema:deployment-witness:1"
    assert schema["title"] == "Deployment Witness"


def test_deployment_witness_schema_accepts_not_published_witness() -> None:
    schema = _load_schema(SCHEMA_PATH)
    witness = _deployment_witness()
    witness["deployment_claim"] = "not-published"
    witness["signature_status"] = "skipped:no_witness_secret"
    witness["conformance_signature_status"] = "skipped:no_conformance_secret"
    witness["steps"][1]["passed"] = False
    witness["errors"] = ["runtime witness signature was not verified"]

    errors = _validate_schema_instance(schema, witness)

    assert errors == []
    assert witness["deployment_claim"] == "not-published"
    assert witness["errors"] == ["runtime witness signature was not verified"]


def test_deployment_witness_schema_rejects_bad_witness_id() -> None:
    schema = _load_schema(SCHEMA_PATH)
    witness = _deployment_witness()
    witness["witness_id"] = "deployment-witness-local"

    errors = _validate_schema_instance(schema, witness)

    assert len(errors) == 1
    assert "$.witness_id" in errors[0]
    assert "does not match pattern" in errors[0]


def test_deployment_witness_schema_rejects_malformed_step() -> None:
    schema = _load_schema(SCHEMA_PATH)
    witness = _deployment_witness()
    del witness["steps"][0]["detail"]

    errors = _validate_schema_instance(schema, witness)

    assert len(errors) == 1
    assert "$.steps[0]" in errors[0]
    assert "detail" in errors[0]


def _deployment_witness() -> dict[str, Any]:
    return deepcopy(
        {
            "witness_id": "deployment-witness-0123456789abcdef",
            "collected_at": "2026-05-01T14:30:00Z",
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
                {
                    "name": "gateway health",
                    "passed": True,
                    "detail": "status=200 body_status=healthy",
                },
                {
                    "name": "gateway runtime witness",
                    "passed": True,
                    "detail": "status=200 runtime_status=healthy",
                },
                {
                    "name": "runtime conformance signature",
                    "passed": True,
                    "detail": "verified",
                },
            ],
            "errors": [],
        }
    )
