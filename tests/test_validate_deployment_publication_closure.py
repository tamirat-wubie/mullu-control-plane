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

import json
from pathlib import Path

from scripts.validate_deployment_publication_closure import (
    load_witness_payload,
    main,
    validate_deployment_publication_closure_report,
    validate_publication_closure,
    write_deployment_publication_closure_validation_report,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def test_not_published_status_passes_without_witness() -> None:
    errors = validate_publication_closure(
        deployment_status_text=_deployment_status("not-published", "not-declared"),
        witness_payload=None,
    )

    assert errors == []
    assert len(errors) == 0
    assert "not-published" in _deployment_status("not-published", "not-declared")


def test_closure_validation_report_matches_public_schema_for_not_published(
    tmp_path: Path,
) -> None:
    deployment_status = tmp_path / "DEPLOYMENT_STATUS.md"
    witness_path = tmp_path / "deployment_witness.json"
    output_path = tmp_path / "deployment_publication_closure_validation.json"
    deployment_status.write_text(
        _deployment_status("not-published", "not-declared"),
        encoding="utf-8",
    )

    validation = validate_deployment_publication_closure_report(
        deployment_status_path=deployment_status,
        witness_path=witness_path,
    )
    write_deployment_publication_closure_validation_report(validation, output_path)
    schema = _load_schema(
        Path("schemas/deployment_publication_closure_validation.schema.json")
    )

    errors = _validate_schema_instance(
        schema,
        validation.to_json_dict(),
    )

    assert errors == []
    assert validation.valid is True
    assert validation.errors == ()
    assert output_path.exists()
    assert validation.deployment_status_path == "provided_deployment_status"
    assert validation.witness_path == "provided_witness"


def test_closure_validation_report_matches_public_schema_for_failed_closure(
    tmp_path: Path,
) -> None:
    deployment_status = tmp_path / "DEPLOYMENT_STATUS.md"
    witness_path = tmp_path / "deployment_witness.json"
    deployment_status.write_text(
        _deployment_status("published", "https://gateway.example/health"),
        encoding="utf-8",
    )

    validation = validate_deployment_publication_closure_report(
        deployment_status_path=deployment_status,
        witness_path=witness_path,
    )
    schema = _load_schema(
        Path("schemas/deployment_publication_closure_validation.schema.json")
    )

    errors = _validate_schema_instance(schema, validation.to_json_dict())

    assert errors == []
    assert validation.valid is False
    assert len(validation.errors) == 1
    assert "published deployment requires witness artifact" in validation.errors[0]
    assert str(witness_path) not in validation.errors[0]


def test_closure_validation_report_bounds_noncanonical_paths(
    tmp_path: Path,
) -> None:
    deployment_status = tmp_path / "secret-deployment-status.md"
    witness_path = tmp_path / "secret-deployment-witness.json"
    deployment_status.write_text(
        _deployment_status("published", "https://gateway.example/health"),
        encoding="utf-8",
    )

    validation = validate_deployment_publication_closure_report(
        deployment_status_path=deployment_status,
        witness_path=witness_path,
    )
    serialized = str(validation.to_json_dict())

    assert validation.deployment_status_path == "provided_deployment_status"
    assert validation.witness_path == "provided_witness"
    assert "secret-deployment-status" not in serialized
    assert "secret-deployment-witness" not in serialized


def test_closure_validation_report_bounds_witness_values(tmp_path: Path) -> None:
    deployment_status = tmp_path / "DEPLOYMENT_STATUS.md"
    witness_path = tmp_path / "deployment_witness.json"
    deployment_status.write_text(
        _deployment_status("published", "https://secret-public.example/health"),
        encoding="utf-8",
    )
    witness = _published_witness()
    witness["signature_status"] = "secret-signature-status"
    witness["public_health_endpoint"] = "https://secret-witness.example/health"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation = validate_deployment_publication_closure_report(
        deployment_status_path=deployment_status,
        witness_path=witness_path,
    )
    serialized = str(validation.to_json_dict())

    assert validation.valid is False
    assert any("signature_status mismatch" in error for error in validation.errors)
    assert "witness public health endpoint mismatch" in validation.errors
    assert "secret-signature-status" not in serialized
    assert "secret-public.example" not in serialized
    assert "secret-witness.example" not in serialized


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


def test_load_witness_payload_bounds_malformed_json_detail(tmp_path: Path) -> None:
    witness_path = tmp_path / "deployment_witness.json"
    witness_path.write_text('{"secret": "secret-witness-token",', encoding="utf-8")

    payload, errors = load_witness_payload(witness_path)

    assert payload is None
    assert errors == [f"{witness_path}: witness JSON parse failed"]
    assert all("secret-witness-token" not in error for error in errors)


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


def test_published_status_rejects_http_gateway_witness() -> None:
    witness = _published_witness()
    witness["gateway_url"] = "http://gateway.example"

    errors = validate_publication_closure(
        deployment_status_text=_deployment_status(
            "published",
            "http://gateway.example/health",
        ),
        witness_payload=witness,
        witness_path=Path(".change_assurance/deployment_witness.json"),
    )

    assert len(errors) == 1
    assert "published gateway_url must use https" in errors[0]
    assert "deployment_witness.json" in errors[0]


def test_published_status_rejects_missing_gateway_health_step() -> None:
    witness = _published_witness()
    witness["steps"][0]["name"] = "gateway status"

    errors = validate_publication_closure(
        deployment_status_text=_deployment_status(
            "published",
            "https://gateway.example/health",
        ),
        witness_payload=witness,
        witness_path=Path(".change_assurance/deployment_witness.json"),
    )

    assert len(errors) == 1
    assert "requires passing gateway health step" in errors[0]
    assert "deployment_witness.json" in errors[0]


def test_published_status_rejects_unproven_health_probe_receipt() -> None:
    witness = _published_witness()
    witness["public_health_endpoint"] = "https://other-gateway.example/health"
    witness["health_http_status"] = 503
    witness["health_response_digest"] = ""

    errors = validate_publication_closure(
        deployment_status_text=_deployment_status(
            "published",
            "https://gateway.example/health",
        ),
        witness_payload=witness,
        witness_path=Path(".change_assurance/deployment_witness.json"),
    )

    assert len(errors) == 3
    assert "health_http_status 503 != 200" in errors[0]
    assert "health_response_digest must be a sha256 digest" in errors[1]
    assert "witness public health endpoint does not match" in errors[2]


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


def test_published_status_rejects_authority_responsibility_debt() -> None:
    witness = _published_witness()
    witness["authority_responsibility_debt_clear"] = False
    witness["authority_overdue_obligation_count"] = 1

    errors = validate_publication_closure(
        deployment_status_text=_deployment_status(
            "published",
            "https://gateway.example/health",
        ),
        witness_payload=witness,
        witness_path=Path(".change_assurance/deployment_witness.json"),
    )

    assert len(errors) == 2
    assert "authority responsibility debt must be clear" in errors[0]
    assert "authority_overdue_obligation_count 1 != 0" in errors[1]


def test_published_status_rejects_runtime_responsibility_debt() -> None:
    witness = _published_witness()
    witness["runtime_responsibility_debt_clear"] = False

    errors = validate_publication_closure(
        deployment_status_text=_deployment_status(
            "published",
            "https://gateway.example/health",
        ),
        witness_payload=witness,
        witness_path=Path(".change_assurance/deployment_witness.json"),
    )

    assert len(errors) == 1
    assert "runtime responsibility debt must be clear" in errors[0]


def test_cli_accepts_current_not_published_status_without_witness(tmp_path, capsys) -> None:
    deployment_status = tmp_path / "DEPLOYMENT_STATUS.md"
    deployment_status.write_text(
        _deployment_status("not-published", "not-declared"),
        encoding="utf-8",
    )
    witness_path = tmp_path / "deployment_witness.json"

    exit_code = main(
        [
            "--deployment-status",
            str(deployment_status),
            "--witness",
            str(witness_path),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "DEPLOYMENT PUBLICATION CLOSURE OK" in captured.out
    assert not witness_path.exists()


def test_cli_writes_optional_closure_validation_report(tmp_path: Path) -> None:
    deployment_status = tmp_path / "DEPLOYMENT_STATUS.md"
    deployment_status.write_text(
        _deployment_status("not-published", "not-declared"),
        encoding="utf-8",
    )
    witness_path = tmp_path / "deployment_witness.json"
    output_path = tmp_path / "deployment_publication_closure_validation.json"

    exit_code = main(
        [
            "--deployment-status",
            str(deployment_status),
            "--witness",
            str(witness_path),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert output_path.exists()
    assert '"valid": true' in output_path.read_text(encoding="utf-8")


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
        "public_health_endpoint": "https://gateway.example/health",
        "health_http_status": 200,
        "health_response_digest": (
            "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        ),
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
        "runtime_responsibility_debt_clear": True,
        "authority_responsibility_debt_clear": True,
        "authority_pending_approval_chain_count": 0,
        "authority_overdue_approval_chain_count": 0,
        "authority_open_obligation_count": 0,
        "authority_overdue_obligation_count": 0,
        "authority_escalated_obligation_count": 0,
        "authority_unowned_high_risk_capability_count": 0,
        "steps": [
            {"name": "gateway health", "passed": True, "detail": "ok"},
            {"name": "gateway runtime witness", "passed": True, "detail": "ok"},
            {"name": "runtime conformance signature", "passed": True, "detail": "ok"},
        ],
        "errors": [],
    }
