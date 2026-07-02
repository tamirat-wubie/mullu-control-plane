"""Tests for live producer rollback proof packet validation.

Purpose: lock the rollback proof packet as AwaitingEvidence without rollback
execution, recovery verification, destructive operations, mutation routes, or live authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_live_producer_rollback_proof_packet.
Invariants: packet validation rejects satisfied evidence, rollback execution, secret values,
mutation routes, and live claims.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_live_producer_rollback_proof_packet import (  # noqa: E402
    DEFAULT_FIXTURE,
    REQUIRED_COMPONENT_IDS,
    main,
    validate_live_producer_rollback_proof_packet,
)


def _load_fixture() -> dict[str, object]:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def _write_fixture(tmp_path: Path, packet: dict[str, object]) -> Path:
    packet_path = tmp_path / "rollback_proof_packet.json"
    packet_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    return packet_path


def test_live_producer_rollback_proof_packet_accepts_default_fixture() -> None:
    validation, packet = validate_live_producer_rollback_proof_packet()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.packet_id == "agentic-service-harness-live-producer-rollback-proof-packet"
    assert validation.packet_status == "blocked_awaiting_rollback_proof_components"
    assert validation.required_component_count == 7
    assert validation.missing_evidence_count == 7
    assert tuple(entry["component_id"] for entry in packet["required_components"]) == REQUIRED_COMPONENT_IDS


def test_live_producer_rollback_proof_packet_rejects_component_satisfaction(tmp_path: Path) -> None:
    packet = _load_fixture()
    changed_packet = copy.deepcopy(packet)
    changed_packet["required_components"][0]["required_ref"] = "rollback-proof://already-collected"
    changed_packet["required_components"][0]["status"] = "SolvedVerified"
    changed_packet["missing_evidence"][0]["status"] = "SolvedVerified"
    packet_path = _write_fixture(tmp_path, changed_packet)

    validation, _observed = validate_live_producer_rollback_proof_packet(fixture_path=packet_path)

    serialized_errors = "\n".join(validation.errors)
    assert validation.ok is False
    assert "required_ref must stay future://" in serialized_errors
    assert "rollback_proof_ref status must be AwaitingEvidence" in serialized_errors
    assert "AwaitingEvidence" in serialized_errors


def test_live_producer_rollback_proof_packet_rejects_execution_and_authority_drift(tmp_path: Path) -> None:
    packet = _load_fixture()
    changed_packet = copy.deepcopy(packet)
    changed_packet["rollback_executed"] = True
    changed_packet["recovery_verified"] = True
    changed_packet["authority_denials"]["destructive_operation_enabled"] = True
    changed_packet["authority_denials"]["live_execution_authorized"] = True
    changed_packet["effect_boundary"]["network_policy"] = "egress-open"
    packet_path = _write_fixture(tmp_path, changed_packet)

    validation, _observed = validate_live_producer_rollback_proof_packet(fixture_path=packet_path)

    serialized_errors = "\n".join(validation.errors)
    assert validation.ok is False
    assert "rollback_executed" in serialized_errors
    assert "recovery_verified" in serialized_errors
    assert "destructive_operation_enabled" in serialized_errors
    assert "live_execution_authorized" in serialized_errors
    assert "network_policy must be none" in serialized_errors


def test_live_producer_rollback_proof_packet_rejects_route_and_credential_value(tmp_path: Path) -> None:
    packet = _load_fixture()
    changed_packet = copy.deepcopy(packet)
    changed_packet["next_action"] = "DELETE /api/v1/harness/live-producer/rollback access_token=abc123"
    packet_path = _write_fixture(tmp_path, changed_packet)

    validation, _observed = validate_live_producer_rollback_proof_packet(fixture_path=packet_path)

    serialized_errors = "\n".join(validation.errors)
    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_live_producer_rollback_proof_packet_rejects_secret_bearing_key(tmp_path: Path) -> None:
    packet = _load_fixture()
    changed_packet = copy.deepcopy(packet)
    changed_packet["api_key_ref"] = "future://agentic-service-harness/live-producer/not-a-value"
    packet_path = _write_fixture(tmp_path, changed_packet)

    validation, _observed = validate_live_producer_rollback_proof_packet(fixture_path=packet_path)

    serialized_errors = "\n".join(validation.errors)
    assert validation.ok is False
    assert "unexpected property 'api_key_ref'" in serialized_errors
    assert "forbidden secret-bearing key" in serialized_errors


def test_live_producer_rollback_proof_packet_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["packet_id"] == "agentic-service-harness-live-producer-rollback-proof-packet"
    assert payload["required_component_count"] == 7
    assert payload["missing_evidence_count"] == 7
