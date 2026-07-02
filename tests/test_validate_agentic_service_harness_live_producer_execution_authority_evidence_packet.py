"""Tests for live producer execution authority evidence packet validation.

Purpose: prove the execution authority evidence packet remains no-effect and
blocked until all live authority evidence exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_live_producer_execution_authority_evidence_packet.
Invariants: live execution, connector calls, receipt append, runtime writes,
secret access, mutation routes, and terminal closure remain denied.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_live_producer_execution_authority_evidence_packet import (  # noqa: E402
    DEFAULT_FIXTURE,
    PACKET_ID,
    REQUIRED_EVIDENCE_IDS,
    main,
    validate_live_producer_execution_authority_evidence_packet,
)


def _load_fixture() -> dict[str, object]:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def _write_fixture(tmp_path: Path, packet: dict[str, object]) -> Path:
    path = tmp_path / "execution_authority_evidence_packet.json"
    path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    return path


def test_live_producer_execution_authority_evidence_packet_accepts_default_fixture() -> None:
    validation, packet = validate_live_producer_execution_authority_evidence_packet()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.packet_id == PACKET_ID
    assert validation.packet_status == "blocked_awaiting_live_execution_authority_evidence"
    assert validation.required_evidence_count == len(REQUIRED_EVIDENCE_IDS)
    assert validation.missing_evidence_count == len(REQUIRED_EVIDENCE_IDS)
    assert tuple(item["evidence_id"] for item in packet["required_evidence"]) == REQUIRED_EVIDENCE_IDS


def test_live_producer_execution_authority_evidence_packet_rejects_evidence_satisfaction(tmp_path: Path) -> None:
    packet = _load_fixture()
    changed = copy.deepcopy(packet)
    changed["required_evidence"][0]["required_ref"] = "receipt://already-satisfied"
    changed["required_evidence"][0]["status"] = "SolvedVerified"
    changed["missing_evidence"][0]["status"] = "SolvedVerified"

    validation, _ = validate_live_producer_execution_authority_evidence_packet(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "required_ref must stay future://" in serialized_errors
    assert "status must be AwaitingEvidence" in serialized_errors
    assert "AwaitingEvidence" in serialized_errors


def test_live_producer_execution_authority_evidence_packet_rejects_authority_drift(tmp_path: Path) -> None:
    packet = _load_fixture()
    changed = copy.deepcopy(packet)
    changed["live_execution_authorized"] = True
    changed["authority_denials"]["connector_call_enabled"] = True
    changed["effect_boundary"]["network_policy"] = "egress-open"

    validation, _ = validate_live_producer_execution_authority_evidence_packet(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "live_execution_authorized" in serialized_errors
    assert "connector_call_enabled" in serialized_errors
    assert "network_policy must be none" in serialized_errors


def test_live_producer_execution_authority_evidence_packet_rejects_missing_evidence_id(tmp_path: Path) -> None:
    packet = _load_fixture()
    changed = copy.deepcopy(packet)
    changed["missing_evidence"] = changed["missing_evidence"][:-1]

    validation, _ = validate_live_producer_execution_authority_evidence_packet(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "missing_evidence" in serialized_errors
    assert "temporal_lease_ref" in serialized_errors
    assert "order mismatch" in serialized_errors


def test_live_producer_execution_authority_evidence_packet_rejects_route_and_credential_value(tmp_path: Path) -> None:
    packet = _load_fixture()
    changed = copy.deepcopy(packet)
    changed["next_action"] = "Never call POST /api/v1/harness/live-producer with access_token=abc123"

    validation, _ = validate_live_producer_execution_authority_evidence_packet(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "credential-like value" in serialized_errors
    assert "access_token=abc123" not in serialized_errors


def test_live_producer_execution_authority_evidence_packet_rejects_secret_bearing_key(tmp_path: Path) -> None:
    packet = _load_fixture()
    changed = copy.deepcopy(packet)
    changed["api_key_ref"] = "future://agentic-service-harness/live-producer/not-a-value"

    validation, _ = validate_live_producer_execution_authority_evidence_packet(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "unexpected property 'api_key_ref'" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors


def test_live_producer_execution_authority_evidence_packet_rejects_live_claim_text(tmp_path: Path) -> None:
    packet = _load_fixture()
    changed = copy.deepcopy(packet)
    changed["next_action"] = "Do not claim live_execution_authorized=true before evidence exists."

    validation, _ = validate_live_producer_execution_authority_evidence_packet(
        fixture_path=_write_fixture(tmp_path, changed)
    )
    serialized_errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "live authority claim denied" in serialized_errors
    assert "live_execution_authorized=true" not in serialized_errors


def test_live_producer_execution_authority_evidence_packet_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["packet_id"] == PACKET_ID
    assert payload["required_evidence_count"] == len(REQUIRED_EVIDENCE_IDS)
    assert payload["missing_evidence_count"] == len(REQUIRED_EVIDENCE_IDS)
