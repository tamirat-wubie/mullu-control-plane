"""Tests for live producer execution authority review intake preflight validation.

Purpose: prove the review intake preflight remains redacted, no-effect, and
blocked until live authority review inputs exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_live_producer_execution_authority_review_intake_preflight.
Invariants: live execution, connector calls, receipt append, runtime writes,
secret access, mutation routes, review submission, input collection, and
terminal closure remain denied.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_live_producer_execution_authority_review_intake_preflight import (  # noqa: E402
    DEFAULT_FIXTURE,
    PREFLIGHT_ID,
    REVIEW_INPUT_IDS,
    main,
    validate_live_producer_execution_authority_review_intake_preflight,
)


def _load_fixture() -> dict[str, object]:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def _write_fixture(tmp_path: Path, preflight: dict[str, object]) -> Path:
    path = tmp_path / "execution_authority_review_intake_preflight.json"
    path.write_text(json.dumps(preflight, indent=2), encoding="utf-8")
    return path


def test_live_producer_execution_authority_review_intake_preflight_accepts_default_fixture() -> None:
    validation, preflight = validate_live_producer_execution_authority_review_intake_preflight()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.preflight_id == PREFLIGHT_ID
    assert validation.preflight_status == "blocked_awaiting_redacted_live_authority_review_intake"
    assert validation.redacted_intake_requirement_count == len(REVIEW_INPUT_IDS)
    assert validation.missing_intake_requirement_count == len(REVIEW_INPUT_IDS)
    assert tuple(item["input_id"] for item in preflight["redacted_intake_requirements"]) == REVIEW_INPUT_IDS


def test_live_producer_execution_authority_review_intake_preflight_rejects_intake_acceptance(tmp_path: Path) -> None:
    preflight = _load_fixture()
    changed = copy.deepcopy(preflight)
    changed["redacted_intake_requirements"][0]["required_redacted_input_ref"] = "receipt://already-collected"
    changed["redacted_intake_requirements"][0]["status"] = "SolvedVerified"
    changed["redacted_intake_requirements"][0]["accepted_for_review"] = True
    changed["missing_intake_requirements"][0]["status"] = "SolvedVerified"

    validation, _ = validate_live_producer_execution_authority_review_intake_preflight(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "required_redacted_input_ref must stay future redacted" in serialized_errors
    assert "status must be AwaitingEvidence" in serialized_errors
    assert "accepted_for_review must be false" in serialized_errors


def test_live_producer_execution_authority_review_intake_preflight_rejects_authority_drift(tmp_path: Path) -> None:
    preflight = _load_fixture()
    changed = copy.deepcopy(preflight)
    changed["review_submitted"] = True
    changed["input_collection_started"] = True
    changed["authority_denials"]["connector_call_enabled"] = True
    changed["effect_boundary"]["network_policy"] = "egress-open"

    validation, _ = validate_live_producer_execution_authority_review_intake_preflight(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "review_submitted" in serialized_errors
    assert "input_collection_started" in serialized_errors
    assert "connector_call_enabled" in serialized_errors
    assert "network_policy must be none" in serialized_errors


def test_live_producer_execution_authority_review_intake_preflight_rejects_missing_input_id(tmp_path: Path) -> None:
    preflight = _load_fixture()
    changed = copy.deepcopy(preflight)
    changed["missing_intake_requirements"] = changed["missing_intake_requirements"][:-1]

    validation, _ = validate_live_producer_execution_authority_review_intake_preflight(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "missing_intake_requirements" in serialized_errors
    assert "temporal_lease_review_input" in serialized_errors
    assert "order mismatch" in serialized_errors


def test_live_producer_execution_authority_review_intake_preflight_rejects_route_and_credential_value(
    tmp_path: Path,
) -> None:
    preflight = _load_fixture()
    changed = copy.deepcopy(preflight)
    changed["next_action"] = "Never call POST /api/v1/harness/live-producer with access_token=abc123"

    validation, _ = validate_live_producer_execution_authority_review_intake_preflight(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "credential-like value" in serialized_errors
    assert "access_token=abc123" not in serialized_errors


def test_live_producer_execution_authority_review_intake_preflight_rejects_secret_bearing_key(tmp_path: Path) -> None:
    preflight = _load_fixture()
    changed = copy.deepcopy(preflight)
    changed["credential_digest_ref"] = "future://agentic-service-harness/live-producer/review-intake/redacted/value"

    validation, _ = validate_live_producer_execution_authority_review_intake_preflight(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "unexpected property 'credential_digest_ref'" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors


def test_live_producer_execution_authority_review_intake_preflight_rejects_live_claim_text(tmp_path: Path) -> None:
    preflight = _load_fixture()
    changed = copy.deepcopy(preflight)
    changed["next_action"] = "Do not claim input_collection_started=true before redacted intake evidence exists."

    validation, _ = validate_live_producer_execution_authority_review_intake_preflight(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "live authority claim denied" in serialized_errors
    assert "input_collection_started=true" not in serialized_errors


def test_live_producer_execution_authority_review_intake_preflight_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["preflight_id"] == PREFLIGHT_ID
    assert payload["redacted_intake_requirement_count"] == len(REVIEW_INPUT_IDS)
    assert payload["missing_intake_requirement_count"] == len(REVIEW_INPUT_IDS)
