"""Tests for Agentic Service Harness live producer external adapter evidence packet.

Purpose: prove the external adapter evidence packet remains blocked until all
required adapter evidence components exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_live_producer_external_adapter_evidence_packet.
Invariants:
  - Default packet validates.
  - Component satisfaction, authority drift, mutation routes, and credential-like values fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_live_producer_external_adapter_evidence_packet import (  # noqa: E402
    DEFAULT_FIXTURE,
    PACKET_ID,
    REQUIRED_COMPONENT_IDS,
    main,
    validate_live_producer_external_adapter_evidence_packet,
)


def _default_packet() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_live_producer_external_adapter_evidence_packet_accepts_default_fixture() -> None:
    validation, packet = validate_live_producer_external_adapter_evidence_packet()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.packet_id == PACKET_ID
    assert validation.packet_status == "blocked_awaiting_external_adapter_evidence_components"
    assert validation.required_component_count == len(REQUIRED_COMPONENT_IDS)
    assert validation.missing_evidence_count == len(REQUIRED_COMPONENT_IDS)
    assert packet["solver_outcome"] == "AwaitingEvidence"
    assert packet["external_adapter_integrated"] is False
    assert packet["network_egress_opened"] is False


def test_live_producer_external_adapter_evidence_packet_rejects_component_satisfaction(
    tmp_path: Path,
) -> None:
    packet = _default_packet()
    packet["required_components"][0]["required_ref"] = "evidence://agentic-service-harness/live-adapter"
    packet["required_components"][0]["status"] = "SolvedVerified"
    packet["missing_evidence"][0]["status"] = "SolvedVerified"
    packet_path = tmp_path / "external-adapter-evidence-packet.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation, observed = validate_live_producer_external_adapter_evidence_packet(fixture_path=packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "required_ref must stay future://" in serialized_errors
    assert "external_adapter_evidence_ref status must be AwaitingEvidence" in serialized_errors
    assert observed["required_components"][0]["status"] == "SolvedVerified"


def test_live_producer_external_adapter_evidence_packet_rejects_authority_drift(
    tmp_path: Path,
) -> None:
    packet = _default_packet()
    packet["authority_granted"] = True
    packet["external_adapter_integrated"] = True
    packet["network_egress_opened"] = True
    packet["authority_denials"]["live_execution_authorized"] = True
    packet["effect_boundary"]["runtime_state_written"] = True
    packet_path = tmp_path / "external-adapter-evidence-packet.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation, observed = validate_live_producer_external_adapter_evidence_packet(fixture_path=packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority_granted" in serialized_errors
    assert "external_adapter_integrated" in serialized_errors
    assert "network_egress_opened" in serialized_errors
    assert "runtime_state_written" in serialized_errors
    assert observed["authority_denials"]["live_execution_authorized"] is True


def test_live_producer_external_adapter_evidence_packet_rejects_route_and_secret_drift(
    tmp_path: Path,
) -> None:
    packet = _default_packet()
    packet["next_action"] = "POST /api/v1/live-producer/external-adapter with ghp_forbiddencredential"
    packet_path = tmp_path / "external-adapter-evidence-packet.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation, observed = validate_live_producer_external_adapter_evidence_packet(fixture_path=packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "credential-like value" in serialized_errors
    assert "ghp_forbiddencredential" in observed["next_action"]


def test_live_producer_external_adapter_evidence_packet_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["packet_id"] == PACKET_ID
    assert payload["fixture"]["packet_status"] == "blocked_awaiting_external_adapter_evidence_components"
    assert payload["fixture"]["external_adapter_integrated"] is False
