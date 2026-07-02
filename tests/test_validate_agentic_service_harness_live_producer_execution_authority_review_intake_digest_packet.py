"""Tests for live producer execution authority review intake digest packet validation."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_live_producer_execution_authority_review_intake_digest_packet import (  # noqa: E402
    DEFAULT_FIXTURE,
    PACKET_ID,
    PACKET_STATUS,
    REVIEW_INPUT_IDS,
    main,
    validate_live_producer_execution_authority_review_intake_digest_packet,
)


def _load_fixture() -> dict[str, object]:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def _write_fixture(tmp_path: Path, packet: dict[str, object]) -> Path:
    path = tmp_path / "execution_authority_review_intake_digest_packet.json"
    path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    return path


def test_accepts_default_fixture() -> None:
    validation, fixture = validate_live_producer_execution_authority_review_intake_digest_packet()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.packet_id == PACKET_ID
    assert validation.packet_status == PACKET_STATUS
    assert validation.digest_requirement_count == len(REVIEW_INPUT_IDS)
    assert validation.missing_digest_requirement_count == len(REVIEW_INPUT_IDS)
    assert fixture["digest_collection_started"] is False
    assert fixture["review_submitted"] is False
    assert fixture["live_execution_authorized"] is False


def test_rejects_digest_acceptance(tmp_path: Path) -> None:
    changed = copy.deepcopy(_load_fixture())
    changed["digest_requirements"][0]["required_digest_ref"] = "receipt://already-digested"
    changed["digest_requirements"][0]["status"] = "SolvedVerified"
    changed["digest_requirements"][0]["accepted_for_review"] = True
    changed["digest_requirements"][0]["digest_material_present"] = True
    changed["missing_digest_requirements"][0]["status"] = "SolvedVerified"

    validation, _ = validate_live_producer_execution_authority_review_intake_digest_packet(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "required_digest_ref" in serialized_errors
    assert "future://" in serialized_errors
    assert "status must be AwaitingEvidence" in serialized_errors
    assert "must not be accepted for review" in serialized_errors
    assert "digest material must not be present" in serialized_errors


def test_rejects_authority_drift(tmp_path: Path) -> None:
    changed = copy.deepcopy(_load_fixture())
    changed["review_submitted"] = True
    changed["digest_collection_complete"] = True
    changed["authority_denials"]["connector_call_enabled"] = True
    changed["effect_boundary"]["network_policy"] = "egress-open"

    validation, _ = validate_live_producer_execution_authority_review_intake_digest_packet(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "review_submitted" in serialized_errors
    assert "digest_collection_complete" in serialized_errors
    assert "connector_call_enabled" in serialized_errors
    assert "network_policy must be none" in serialized_errors


def test_rejects_missing_input_id(tmp_path: Path) -> None:
    changed = copy.deepcopy(_load_fixture())
    changed["missing_digest_requirements"] = changed["missing_digest_requirements"][:-1]

    validation, _ = validate_live_producer_execution_authority_review_intake_digest_packet(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "missing_digest_requirements" in serialized_errors
    assert "temporal_lease_review_input" in serialized_errors
    assert "order mismatch" in serialized_errors


def test_rejects_route_and_credential_value(tmp_path: Path) -> None:
    changed = copy.deepcopy(_load_fixture())
    changed["next_action"] = "Never call POST /api/v1/harness/live-producer with access_token=abc123"

    validation, _ = validate_live_producer_execution_authority_review_intake_digest_packet(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "credential-like value" in serialized_errors
    assert "access_token=abc123" not in serialized_errors


def test_rejects_secret_bearing_key(tmp_path: Path) -> None:
    changed = copy.deepcopy(_load_fixture())
    changed["credential_digest_ref"] = "future://agentic-service-harness/live-producer/review-intake/value"

    validation, _ = validate_live_producer_execution_authority_review_intake_digest_packet(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "unexpected property 'credential_digest_ref'" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors


def test_rejects_live_claim_text(tmp_path: Path) -> None:
    changed = copy.deepcopy(_load_fixture())
    changed["next_action"] = "Do not claim review_submitted=true before evidence digest review exists."

    validation, _ = validate_live_producer_execution_authority_review_intake_digest_packet(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "live authority claim denied" in serialized_errors
    assert "review_submitted=true" not in serialized_errors


def test_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["packet_id"] == PACKET_ID
    assert payload["packet_status"] == PACKET_STATUS
    assert payload["digest_requirement_count"] == len(REVIEW_INPUT_IDS)
