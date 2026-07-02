"""Tests for Agentic Service Harness live producer evidence packet intake.

Purpose: prove the evidence packet intake blocks live producer work until the
required governed witness packets exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_live_producer_evidence_packet_intake.
Invariants:
  - Default intake fixture validates.
  - Required witness packets remain future evidence.
  - Authority, mutation route, and credential drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_live_producer_evidence_packet_intake import (  # noqa: E402
    DEFAULT_FIXTURE,
    PACKET_ID,
    REQUIRED_WITNESS_KINDS,
    main,
    validate_live_producer_evidence_packet_intake,
)


def _default_packet() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_live_producer_evidence_packet_intake_accepts_default_fixture() -> None:
    validation, packet = validate_live_producer_evidence_packet_intake()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.packet_id == PACKET_ID
    assert validation.source_preflight_count == len(REQUIRED_WITNESS_KINDS)
    assert validation.witness_packet_requirement_count == len(REQUIRED_WITNESS_KINDS)
    assert validation.missing_evidence_count == len(REQUIRED_WITNESS_KINDS)
    assert packet["solver_outcome"] == "AwaitingEvidence"
    assert (
        packet["operator_response_collection_binding"]["binding_id"]
        == "binding.evidence_packet_intake.operator_response_collection"
    )
    assert (
        packet["operator_response_collection_binding"]["source_approval_request_collection_binding_id"]
        == "binding.operator_response.approval_request_collection"
    )
    assert packet["operator_response_collection_binding"]["source_response_record_collected"] is False
    assert packet["operator_response_collection_binding"]["witness_packets_collected"] is False
    assert packet["authority_granted"] is False
    assert packet["terminal_closure"] is False


def test_live_producer_evidence_packet_intake_rejects_authority_drift(tmp_path: Path) -> None:
    packet = _default_packet()
    packet["authority_granted"] = True
    packet["authority_denials"]["live_execution_authorized"] = True
    packet["effect_boundary"]["network_policy"] = "public"
    packet_path = tmp_path / "evidence-packet-intake.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation, observed = validate_live_producer_evidence_packet_intake(fixture_path=packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority_granted" in serialized_errors
    assert "live_execution_authorized" in serialized_errors
    assert "network_policy" in serialized_errors
    assert observed["authority_granted"] is True


def test_live_producer_evidence_packet_intake_rejects_witness_packet_closure_drift(tmp_path: Path) -> None:
    packet = _default_packet()
    packet["witness_packet_requirements"][0]["required_packet_ref"] = (
        "examples/agentic_service_harness_live_producer_effect_receipt_preflight.local.json"
    )
    packet["witness_packet_requirements"][0]["status"] = "SolvedVerified"
    packet["missing_evidence"][0]["status"] = "SolvedVerified"
    packet_path = tmp_path / "evidence-packet-intake.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation, observed = validate_live_producer_evidence_packet_intake(fixture_path=packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "required_packet_ref must stay future://" in serialized_errors
    assert "effect_receipt status must be AwaitingEvidence" in serialized_errors
    assert "effect_receipt_packet status must be AwaitingEvidence" in serialized_errors
    assert observed["witness_packet_requirements"][0]["status"] == "SolvedVerified"


def test_live_producer_evidence_packet_intake_rejects_operator_response_binding_drift(tmp_path: Path) -> None:
    packet = _default_packet()
    binding = packet["operator_response_collection_binding"]
    binding["source_response_witness_ref"] = "examples/drifted-response-witness.json"
    binding["source_approval_request_collection_binding_id"] = "binding.drifted"
    binding["source_response_status"] = "SolvedVerified"
    binding["source_response_record_collected"] = True
    binding["source_approval_satisfied"] = True
    binding["source_authority_granted"] = True
    binding["source_live_execution_authorized"] = True
    binding["witness_packets_collected"] = True
    binding["authority_granted"] = True
    binding["live_execution_authorized"] = True
    packet_path = tmp_path / "evidence-packet-intake.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation, observed = validate_live_producer_evidence_packet_intake(fixture_path=packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "operator_response_collection_binding.source_response_witness_ref" in serialized_errors
    assert "operator_response_collection_binding.source_approval_request_collection_binding_id" in serialized_errors
    assert "operator_response_collection_binding.source_response_status" in serialized_errors
    assert "operator_response_collection_binding.source_response_record_collected" in serialized_errors
    assert "operator_response_collection_binding.source_approval_satisfied" in serialized_errors
    assert "operator_response_collection_binding.source_authority_granted" in serialized_errors
    assert "operator_response_collection_binding.source_live_execution_authorized" in serialized_errors
    assert "operator_response_collection_binding.witness_packets_collected" in serialized_errors
    assert "operator_response_collection_binding.authority_granted" in serialized_errors
    assert "operator_response_collection_binding.live_execution_authorized" in serialized_errors
    assert observed["operator_response_collection_binding"]["source_response_record_collected"] is True


def test_live_producer_evidence_packet_intake_rejects_route_and_secret_drift(tmp_path: Path) -> None:
    packet = _default_packet()
    packet["next_action"] = "POST /api/v1/live-producer with ghp_forbiddencredential"
    packet_path = tmp_path / "evidence-packet-intake.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation, observed = validate_live_producer_evidence_packet_intake(fixture_path=packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "credential-like value" in serialized_errors
    assert "ghp_forbiddencredential" in observed["next_action"]
    assert observed["effect_boundary"]["network_policy"] == "none"


def test_live_producer_evidence_packet_intake_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["packet_id"] == PACKET_ID
    assert payload["fixture"]["packet_status"] == "blocked_awaiting_witness_packets"
    assert payload["fixture"]["operator_response_collection_binding"]["blocks_live_producer"] is True
    assert payload["fixture"]["live_producer_implemented"] is False
