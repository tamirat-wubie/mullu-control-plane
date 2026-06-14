"""Tests for Agentic Service Harness live producer operator decision evidence.

Purpose: prove generic continuation is not operator approval and no live
producer authority is granted by the decision evidence boundary.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision
and scripts.validate_agentic_service_harness_live_producer_operator_decision_evidence.
Invariants:
  - The default decision evidence validates.
  - Generic continuation never satisfies approval.
  - Mutation route, credential, approval, and authority drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.agentic_service_harness_live_producer_operator_decision import (  # noqa: E402
    ACCEPTED_DECISION_KINDS,
    OPERATOR_DECISION_EVIDENCE_ID,
    project_operator_response_witness_to_decision_evidence,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_operator_decision_evidence import (  # noqa: E402
    DEFAULT_FIXTURE,
    main,
    validate_live_producer_operator_decision_evidence,
)
from scripts.validate_agentic_service_harness_live_producer_operator_response_witness import (  # noqa: E402
    validate_live_producer_operator_response_witness,
)


def _default_evidence() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_live_producer_operator_decision_evidence_accept_default_fixture() -> None:
    validation, produced_evidence = validate_live_producer_operator_decision_evidence()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.fixture_path == "examples/agentic_service_harness_live_producer_operator_decision_evidence.local.json"
    assert validation.schema_path == "schemas/agentic_service_harness_live_producer_operator_decision_evidence.schema.json"
    assert validation.evidence_boundary_id == OPERATOR_DECISION_EVIDENCE_ID
    assert validation.decision_status == "AwaitingEvidence"
    assert validation.accepted_decision_count == len(ACCEPTED_DECISION_KINDS)
    assert validation.authority_denial_count == len(FALSE_AUTHORITY_FLAGS) + 1
    assert produced_evidence["observed_input_kind"] == "generic_continuation"
    assert produced_evidence["generic_continuation_satisfies_approval"] is False
    assert produced_evidence["approval_satisfied"] is False


def test_live_producer_operator_decision_evidence_projects_response_witness() -> None:
    response_validation, response_witness = validate_live_producer_operator_response_witness()
    produced_evidence = project_operator_response_witness_to_decision_evidence(response_witness)
    accepted = produced_evidence["accepted_decision_evidence"]

    assert response_validation.ok is True
    assert produced_evidence["evidence_boundary_id"] == OPERATOR_DECISION_EVIDENCE_ID
    assert tuple(entry["decision_kind"] for entry in accepted) == ACCEPTED_DECISION_KINDS
    assert all(entry["status"] == "AwaitingEvidence" for entry in accepted)
    assert produced_evidence["generic_continuation_satisfies_approval"] is False
    assert produced_evidence["authority_denials"]["live_execution_authorized"] is False
    assert produced_evidence["effect_boundary"]["network_policy"] == "none"


def test_live_producer_operator_decision_evidence_rejects_generic_approval(tmp_path: Path) -> None:
    evidence = _default_evidence()
    evidence["generic_continuation_satisfies_approval"] = True
    evidence["approval_satisfied"] = True
    evidence_path = tmp_path / "operator-decision-evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    validation, produced_evidence = validate_live_producer_operator_decision_evidence(fixture_path=evidence_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "generic_continuation_satisfies_approval" in serialized_errors
    assert "approval_satisfied" in serialized_errors
    assert produced_evidence["approval_satisfied"] is False


def test_live_producer_operator_decision_evidence_rejects_live_authority(tmp_path: Path) -> None:
    evidence = _default_evidence()
    evidence["authority_denials"]["live_execution_authorized"] = True
    evidence_path = tmp_path / "operator-decision-evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    validation, produced_evidence = validate_live_producer_operator_decision_evidence(fixture_path=evidence_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "live execution authority" in serialized_errors
    assert produced_evidence["authority_denials"]["live_execution_authorized"] is False


def test_live_producer_operator_decision_evidence_rejects_mutation_route_ref(tmp_path: Path) -> None:
    evidence = _default_evidence()
    evidence["source_response_witness_ref"] = "POST /api/v1/harness/live-producer/decision"
    evidence_path = tmp_path / "operator-decision-evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    validation, produced_evidence = validate_live_producer_operator_decision_evidence(fixture_path=evidence_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert produced_evidence["source_response_witness_ref"].startswith("response-witness://")


def test_live_producer_operator_decision_evidence_rejects_secret_like_value(tmp_path: Path) -> None:
    evidence = _default_evidence()
    evidence["next_action"] = "Collect ghp_forbiddencredential"
    evidence_path = tmp_path / "operator-decision-evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    validation, produced_evidence = validate_live_producer_operator_decision_evidence(fixture_path=evidence_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "ghp_forbiddencredential" not in serialized_errors
    assert produced_evidence["effect_boundary"]["secret_mutation_enabled"] is False


def test_live_producer_operator_decision_evidence_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["accepted_decision_count"] == len(ACCEPTED_DECISION_KINDS)
    assert payload["produced_evidence"]["approval_satisfied"] is False
