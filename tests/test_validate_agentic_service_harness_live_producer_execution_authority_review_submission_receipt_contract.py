"""Tests for live producer execution authority review submission receipt contract validation."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_live_producer_execution_authority_review_submission_receipt_contract import (  # noqa: E402
    DEFAULT_FIXTURE,
    CONTRACT_ID,
    CONTRACT_STATUS,
    REVIEW_INPUT_IDS,
    main,
    validate_live_producer_execution_authority_review_submission_receipt_contract,
)


def _load_fixture() -> dict[str, object]:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def _write_fixture(tmp_path: Path, admission: dict[str, object]) -> Path:
    path = tmp_path / "execution_authority_review_submission_receipt.json"
    path.write_text(json.dumps(admission, indent=2), encoding="utf-8")
    return path


def test_accepts_default_fixture() -> None:
    validation, fixture = validate_live_producer_execution_authority_review_submission_receipt_contract()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.contract_id == CONTRACT_ID
    assert validation.contract_status == CONTRACT_STATUS
    assert validation.submission_requirement_count == len(REVIEW_INPUT_IDS)
    assert validation.missing_submission_requirement_count == len(REVIEW_INPUT_IDS)
    assert fixture["review_submission_admitted"] is False
    assert fixture["review_submitted"] is False
    assert fixture["live_execution_authorized"] is False


def test_rejects_submission_receipt(tmp_path: Path) -> None:
    changed = copy.deepcopy(_load_fixture())
    changed["submission_receipt_requirements"][0]["required_digest_ref"] = "receipt://already-digested"
    changed["submission_receipt_requirements"][0]["status"] = "SolvedVerified"
    changed["submission_receipt_requirements"][0]["review_submission_admissible"] = True
    changed["missing_submission_receipt_requirements"][0]["status"] = "SolvedVerified"

    validation, _ = validate_live_producer_execution_authority_review_submission_receipt_contract(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "required_digest_ref" in serialized_errors
    assert "future://" in serialized_errors
    assert "status must be AwaitingEvidence" in serialized_errors
    assert "must not be admissible for review submission" in serialized_errors


def test_rejects_authority_drift(tmp_path: Path) -> None:
    changed = copy.deepcopy(_load_fixture())
    changed["review_submission_admitted"] = True
    changed["review_submitted"] = True
    changed["authority_denials"]["connector_call_enabled"] = True
    changed["effect_boundary"]["network_policy"] = "egress-open"

    validation, _ = validate_live_producer_execution_authority_review_submission_receipt_contract(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "review_submission_admitted" in serialized_errors
    assert "review_submitted" in serialized_errors
    assert "connector_call_enabled" in serialized_errors
    assert "network_policy must be none" in serialized_errors


def test_rejects_missing_input_id(tmp_path: Path) -> None:
    changed = copy.deepcopy(_load_fixture())
    changed["missing_submission_receipt_requirements"] = changed["missing_submission_receipt_requirements"][:-1]

    validation, _ = validate_live_producer_execution_authority_review_submission_receipt_contract(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "temporal_lease_review_input" in serialized_errors
    assert "order mismatch" in serialized_errors


def test_rejects_route_and_credential_value(tmp_path: Path) -> None:
    changed = copy.deepcopy(_load_fixture())
    changed["next_action"] = "Never call POST /api/v1/harness/live-producer with access_token=abc123"

    validation, _ = validate_live_producer_execution_authority_review_submission_receipt_contract(
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

    validation, _ = validate_live_producer_execution_authority_review_submission_receipt_contract(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "forbidden secret-bearing key" in serialized_errors


def test_rejects_live_claim_text(tmp_path: Path) -> None:
    changed = copy.deepcopy(_load_fixture())
    changed["next_action"] = "Do not claim review_submission_admitted=true before evidence exists."

    validation, _ = validate_live_producer_execution_authority_review_submission_receipt_contract(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "live authority claim denied" in serialized_errors
    assert "review_submission_admitted=true" not in serialized_errors


def test_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["contract_id"] == CONTRACT_ID
    assert payload["contract_status"] == CONTRACT_STATUS
    assert payload["submission_requirement_count"] == len(REVIEW_INPUT_IDS)
