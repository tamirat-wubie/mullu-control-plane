"""Tests for live producer execution authority review input contract validation.

Purpose: prove the review input contract remains no-effect and blocked until
all live authority review inputs exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_live_producer_execution_authority_review_input_contract.
Invariants: live execution, connector calls, receipt append, runtime writes,
secret access, mutation routes, review submission, and terminal closure remain denied.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_live_producer_execution_authority_review_input_contract import (  # noqa: E402
    CONTRACT_ID,
    DEFAULT_FIXTURE,
    REVIEW_INPUT_IDS,
    main,
    validate_live_producer_execution_authority_review_input_contract,
)


def _load_fixture() -> dict[str, object]:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def _write_fixture(tmp_path: Path, contract: dict[str, object]) -> Path:
    path = tmp_path / "execution_authority_review_input_contract.json"
    path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
    return path


def test_live_producer_execution_authority_review_input_contract_accepts_default_fixture() -> None:
    validation, contract = validate_live_producer_execution_authority_review_input_contract()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.contract_id == CONTRACT_ID
    assert validation.contract_status == "blocked_awaiting_live_authority_review_inputs"
    assert validation.review_input_count == len(REVIEW_INPUT_IDS)
    assert validation.missing_review_input_count == len(REVIEW_INPUT_IDS)
    assert tuple(item["input_id"] for item in contract["review_inputs"]) == REVIEW_INPUT_IDS


def test_live_producer_execution_authority_review_input_contract_rejects_review_acceptance(tmp_path: Path) -> None:
    contract = _load_fixture()
    changed = copy.deepcopy(contract)
    changed["review_inputs"][0]["required_input_ref"] = "receipt://already-reviewed"
    changed["review_inputs"][0]["status"] = "SolvedVerified"
    changed["review_inputs"][0]["accepted_for_review"] = True
    changed["missing_review_inputs"][0]["status"] = "SolvedVerified"

    validation, _ = validate_live_producer_execution_authority_review_input_contract(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "required_input_ref must stay future://" in serialized_errors
    assert "status must be AwaitingEvidence" in serialized_errors
    assert "must not be accepted for review" in serialized_errors


def test_live_producer_execution_authority_review_input_contract_rejects_authority_drift(tmp_path: Path) -> None:
    contract = _load_fixture()
    changed = copy.deepcopy(contract)
    changed["review_submitted"] = True
    changed["review_denials"]["connector_call_enabled"] = True
    changed["effect_boundary"]["network_policy"] = "egress-open"

    validation, _ = validate_live_producer_execution_authority_review_input_contract(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "review_submitted" in serialized_errors
    assert "connector_call_enabled" in serialized_errors
    assert "network_policy must be none" in serialized_errors


def test_live_producer_execution_authority_review_input_contract_rejects_missing_input_id(tmp_path: Path) -> None:
    contract = _load_fixture()
    changed = copy.deepcopy(contract)
    changed["missing_review_inputs"] = changed["missing_review_inputs"][:-1]

    validation, _ = validate_live_producer_execution_authority_review_input_contract(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "missing_review_inputs" in serialized_errors
    assert "temporal_lease_review_input" in serialized_errors
    assert "order mismatch" in serialized_errors


def test_live_producer_execution_authority_review_input_contract_rejects_route_and_credential_value(
    tmp_path: Path,
) -> None:
    contract = _load_fixture()
    changed = copy.deepcopy(contract)
    changed["next_action"] = "Never call POST /api/v1/harness/live-producer with access_token=abc123"

    validation, _ = validate_live_producer_execution_authority_review_input_contract(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "credential-like value" in serialized_errors
    assert "access_token=abc123" not in serialized_errors


def test_live_producer_execution_authority_review_input_contract_rejects_secret_bearing_key(tmp_path: Path) -> None:
    contract = _load_fixture()
    changed = copy.deepcopy(contract)
    changed["api_key_ref"] = "future://agentic-service-harness/live-producer/review-input/not-a-value"

    validation, _ = validate_live_producer_execution_authority_review_input_contract(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "unexpected property 'api_key_ref'" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors


def test_live_producer_execution_authority_review_input_contract_rejects_live_claim_text(tmp_path: Path) -> None:
    contract = _load_fixture()
    changed = copy.deepcopy(contract)
    changed["next_action"] = "Do not claim accepted_for_review=true before review input evidence exists."

    validation, _ = validate_live_producer_execution_authority_review_input_contract(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "live authority claim denied" in serialized_errors
    assert "accepted_for_review=true" not in serialized_errors


def test_live_producer_execution_authority_review_input_contract_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["contract_id"] == CONTRACT_ID
    assert payload["review_input_count"] == len(REVIEW_INPUT_IDS)
    assert payload["missing_review_input_count"] == len(REVIEW_INPUT_IDS)
