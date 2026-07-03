"""Tests for live producer review submission receipt append admission preflight validation."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_live_producer_execution_authority_review_submission_receipt_append_admission_preflight import (  # noqa: E402
    DEFAULT_FIXTURE,
    PREFLIGHT_ID,
    PREFLIGHT_STATUS,
    REVIEW_INPUT_IDS,
    main,
    validate_live_producer_execution_authority_review_submission_receipt_append_admission_preflight,
)


def _load_fixture() -> dict[str, object]:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def _write_fixture(tmp_path: Path, preflight: dict[str, object]) -> Path:
    path = tmp_path / "execution_authority_review_submission_receipt_append_admission_preflight.json"
    path.write_text(json.dumps(preflight, indent=2), encoding="utf-8")
    return path


def test_accepts_default_fixture() -> None:
    validation, fixture = validate_live_producer_execution_authority_review_submission_receipt_append_admission_preflight()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.preflight_id == PREFLIGHT_ID
    assert validation.preflight_status == PREFLIGHT_STATUS
    assert validation.append_admission_requirement_count == len(REVIEW_INPUT_IDS)
    assert validation.missing_append_admission_requirement_count == len(REVIEW_INPUT_IDS)
    assert fixture["review_submission_receipt_append_admission_admitted"] is False
    assert fixture["review_submission_receipt_emitted"] is False
    assert fixture["review_submission_receipt_append_admitted"] is False
    assert fixture["live_execution_authorized"] is False


def test_rejects_receipt_append_admission(tmp_path: Path) -> None:
    changed = copy.deepcopy(_load_fixture())
    changed["receipt_append_admission_requirements"][0]["required_receipt_ref"] = "receipt://already-emitted"
    changed["receipt_append_admission_requirements"][0]["status"] = "SolvedVerified"
    changed["receipt_append_admission_requirements"][0]["receipt_append_admission_admissible"] = True
    changed["missing_receipt_append_admission_requirements"][0]["status"] = "SolvedVerified"

    validation, _ = validate_live_producer_execution_authority_review_submission_receipt_append_admission_preflight(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "required_receipt_ref" in serialized_errors
    assert "future://" in serialized_errors
    assert "status must be AwaitingEvidence" in serialized_errors
    assert "must not be admissible for receipt append admission" in serialized_errors


def test_rejects_authority_drift(tmp_path: Path) -> None:
    changed = copy.deepcopy(_load_fixture())
    changed["review_submission_receipt_append_admission_admitted"] = True
    changed["review_submission_receipt_emitted"] = True
    changed["authority_denials"]["receipt_store_append_enabled"] = True
    changed["effect_boundary"]["network_policy"] = "egress-open"

    validation, _ = validate_live_producer_execution_authority_review_submission_receipt_append_admission_preflight(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "review_submission_receipt_append_admission_admitted" in serialized_errors
    assert "review_submission_receipt_emitted" in serialized_errors
    assert "receipt_store_append_enabled" in serialized_errors
    assert "network_policy must be none" in serialized_errors


def test_rejects_missing_input_id(tmp_path: Path) -> None:
    changed = copy.deepcopy(_load_fixture())
    changed["missing_receipt_append_admission_requirements"] = changed["missing_receipt_append_admission_requirements"][:-1]

    validation, _ = validate_live_producer_execution_authority_review_submission_receipt_append_admission_preflight(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "temporal_lease_review_input" in serialized_errors
    assert "order mismatch" in serialized_errors


def test_rejects_route_and_credential_value(tmp_path: Path) -> None:
    changed = copy.deepcopy(_load_fixture())
    changed["next_action"] = "Never call POST /api/v1/harness/live-producer with access_token=abc123"

    validation, _ = validate_live_producer_execution_authority_review_submission_receipt_append_admission_preflight(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "credential-like value" in serialized_errors
    assert "access_token=abc123" not in serialized_errors


def test_rejects_secret_bearing_key(tmp_path: Path) -> None:
    changed = copy.deepcopy(_load_fixture())
    changed["credential_submission_ref"] = "future://agentic-service-harness/live-producer/review-submission/value"

    validation, _ = validate_live_producer_execution_authority_review_submission_receipt_append_admission_preflight(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "forbidden secret-bearing key" in serialized_errors


def test_rejects_live_claim_text(tmp_path: Path) -> None:
    changed = copy.deepcopy(_load_fixture())
    changed["next_action"] = "Do not claim review_submission_receipt_emitted=true before evidence exists."

    validation, _ = validate_live_producer_execution_authority_review_submission_receipt_append_admission_preflight(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "live authority claim denied" in serialized_errors
    assert "review_submission_receipt_emitted=true" not in serialized_errors


def test_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["preflight_id"] == PREFLIGHT_ID
    assert payload["preflight_status"] == PREFLIGHT_STATUS
    assert payload["append_admission_requirement_count"] == len(REVIEW_INPUT_IDS)
