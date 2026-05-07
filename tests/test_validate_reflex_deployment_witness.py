"""Tests for Reflex deployment witness validation.

Purpose: prove signed Reflex deployment witnesses are replayable outside the
gateway and fail closed on tampering.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_reflex_deployment_witness and Reflex core.
Invariants:
  - Valid signed witnesses pass.
  - Tampered witnesses fail.
  - CLI JSON output carries deterministic validation status.
"""

from __future__ import annotations

import hmac
import json
from hashlib import sha256
from pathlib import Path

from mcoi_runtime.core.reflex import reflex_deployment_witness_seed
from scripts.validate_reflex_deployment_witness import (
    main,
    validate_reflex_deployment_witness,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


DT = "2026-05-04T12:00:00+00:00"
SECRET = "reflex-witness-secret"


def test_validate_reflex_deployment_witness_accepts_signed_witness(tmp_path: Path) -> None:
    witness_path = _write_witness(tmp_path / "reflex-witness.json")

    validation = validate_reflex_deployment_witness(
        witness_path,
        signing_secret=SECRET,
        expected_environment="canary",
        expected_candidate_id="candidate:diag-001",
    )

    assert validation.valid is True
    assert validation.status == "passed"
    assert validation.witness_id.startswith("reflex-deployment-witness-")
    assert validation.candidate_id == "candidate:diag-001"
    assert validation.target_environment == "canary"
    assert validation.detail == "reflex deployment witness verified"
    assert validation.witness_id not in validation.detail
    assert validation.blockers == ()


def test_validate_reflex_deployment_witness_accepts_export_envelope(tmp_path: Path) -> None:
    witness_path = _write_witness(
        tmp_path / "reflex-witness-envelope.json",
        envelope=True,
    )

    validation = validate_reflex_deployment_witness(witness_path, signing_secret=SECRET)

    assert validation.valid is True
    assert validation.status == "passed"
    assert validation.witness_id.startswith("reflex-deployment-witness-")
    assert validation.blockers == ()


def test_reflex_deployment_witness_envelope_schema_accepts_fixture(tmp_path: Path) -> None:
    witness_path = _write_witness(
        tmp_path / "schema-envelope.json",
        envelope=True,
    )
    schema = _load_schema(Path("schemas/reflex_deployment_witness_envelope.schema.json"))
    payload = json.loads(witness_path.read_text(encoding="utf-8"))

    errors = _validate_schema_instance(schema, payload)

    assert errors == []
    assert payload["format"] == "reflex_deployment_witness_validator_envelope_v1"
    assert payload["validator"] == "scripts/validate_reflex_deployment_witness.py"


def test_validate_reflex_deployment_witness_rejects_tampering(tmp_path: Path) -> None:
    witness_path = _write_witness(tmp_path / "tampered-witness.json")
    payload = json.loads(witness_path.read_text(encoding="utf-8"))
    payload["target_environment"] = "production"
    witness_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_reflex_deployment_witness(witness_path, signing_secret=SECRET)

    assert validation.valid is False
    assert validation.status == "failed"
    assert validation.blockers == ("reflex_witness_invalid",)
    assert "replay_signature_mismatch" in validation.detail


def test_validate_reflex_deployment_witness_rejects_schema_violation(tmp_path: Path) -> None:
    witness_path = _write_witness(tmp_path / "schema-bad-witness.json")
    payload = json.loads(witness_path.read_text(encoding="utf-8"))
    payload.pop("health_refs")
    witness_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_reflex_deployment_witness(witness_path, signing_secret=SECRET)

    assert validation.valid is False
    assert validation.blockers == ("reflex_witness_invalid",)
    assert "schema:" in validation.detail
    assert "health_refs_missing" in validation.detail


def test_validate_reflex_deployment_witness_cli_outputs_json(tmp_path: Path, capsys) -> None:
    witness_path = _write_witness(tmp_path / "cli-witness.json")

    exit_code = main(
        [
            "--witness",
            str(witness_path),
            "--signing-secret",
            SECRET,
            "--expected-environment",
            "canary",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["status"] == "passed"
    assert payload["target_environment"] == "canary"
    assert payload["blockers"] == []


def test_validate_reflex_deployment_witness_cli_requires_secret(tmp_path: Path, capsys) -> None:
    witness_path = _write_witness(tmp_path / "missing-secret-witness.json")

    exit_code = main(["--witness", str(witness_path), "--signing-secret", "", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["valid"] is False
    assert payload["blockers"] == ["reflex_witness_signing_secret_missing"]
    assert "signing secret required" in payload["detail"]


def test_validate_reflex_deployment_witness_missing_path_is_bounded(tmp_path: Path) -> None:
    witness_path = tmp_path / "secret-reflex-witness-path.json"

    validation = validate_reflex_deployment_witness(witness_path, signing_secret=SECRET)
    serialized = json.dumps(validation.as_dict(), sort_keys=True)

    assert validation.valid is False
    assert validation.detail == "reflex deployment witness file not found"
    assert validation.witness_path == "<provided>"
    assert "secret-reflex-witness-path" not in serialized


def test_validate_reflex_deployment_witness_missing_file_error_is_bounded(tmp_path: Path) -> None:
    witness_path = tmp_path / "secret-witness-path.json"

    validation = validate_reflex_deployment_witness(witness_path, signing_secret=SECRET)
    serialized = json.dumps(validation.as_dict(), sort_keys=True)

    assert validation.valid is False
    assert validation.detail == "reflex deployment witness file not found"
    assert validation.witness_path == "<provided>"
    assert "secret-witness-path" not in serialized


def test_validate_reflex_deployment_witness_json_error_is_bounded(tmp_path: Path) -> None:
    witness_path = tmp_path / "reflex-witness.json"
    witness_path.write_text('{"witness_id": "secret-json-token"', encoding="utf-8")

    validation = validate_reflex_deployment_witness(witness_path, signing_secret=SECRET)
    serialized = json.dumps(validation.as_dict(), sort_keys=True)

    assert validation.valid is False
    assert validation.detail == "reflex deployment witness unreadable"
    assert validation.witness_path == "<provided>"
    assert "secret-json-token" not in serialized


def _write_witness(path: Path, *, envelope: bool = False) -> Path:
    witness = {
        "witness_id": "",
        "candidate_id": "candidate:diag-001",
        "certificate_id": "cert-001",
        "promotion_decision_id": "decision:candidate:diag-001",
        "target_environment": "canary",
        "canary_status": "planned",
        "health_refs": [
            {
                "kind": "runtime_witness",
                "ref_id": "runtime-witness-001",
                "evidence_hash": "a" * 64,
            }
        ],
        "rollback_plan_ref": "rollback:provider_routing",
        "signed_at": DT,
        "signature_key_id": "reflex-deployment-witness-local",
        "signature": "",
        "production_mutation_applied": False,
    }
    seed = reflex_deployment_witness_seed(witness)
    witness["witness_id"] = f"reflex-deployment-witness-{sha256(seed.encode()).hexdigest()[:16]}"
    witness["signature"] = "hmac-sha256:" + hmac.new(
        SECRET.encode("utf-8"),
        seed.encode("utf-8"),
        sha256,
    ).hexdigest()
    payload = (
        {
            "witness": witness,
            "validator": "scripts/validate_reflex_deployment_witness.py",
            "format": "reflex_deployment_witness_validator_envelope_v1",
        }
        if envelope
        else witness
    )
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
