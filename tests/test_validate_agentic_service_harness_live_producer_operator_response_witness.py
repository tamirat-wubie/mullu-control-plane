"""Tests for Agentic Service Harness live producer operator response witness.

Purpose: prove the operator response witness remains missing, non-authorizing,
and explicit before live producer implementation work begins.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_response
and scripts.validate_agentic_service_harness_live_producer_operator_response_witness.
Invariants:
  - The default response witness validates.
  - Operator response remains `AwaitingEvidence` and uncollected.
  - Mutation route, credential, approval satisfaction, and authority drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.agentic_service_harness_live_producer_operator_response import (  # noqa: E402
    OPERATOR_RESPONSE_MISSING_KIND,
    OPERATOR_RESPONSE_WITNESS_ID,
    project_operator_approval_request_to_operator_response_witness,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import (  # noqa: E402
    FALSE_AUTHORITY_FLAGS,
    REQUIRED_WITNESS_KINDS,
)
from scripts.validate_agentic_service_harness_live_producer_operator_approval_request import (  # noqa: E402
    validate_live_producer_operator_approval_request,
)
from scripts.validate_agentic_service_harness_live_producer_operator_response_witness import (  # noqa: E402
    DEFAULT_FIXTURE,
    main,
    validate_live_producer_operator_response_witness,
)


def _default_witness() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_live_producer_operator_response_witness_accept_default_fixture() -> None:
    validation, produced_witness = validate_live_producer_operator_response_witness()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.fixture_path == "examples/agentic_service_harness_live_producer_operator_response_witness.local.json"
    assert validation.schema_path == "schemas/agentic_service_harness_live_producer_operator_response_witness.schema.json"
    assert validation.response_witness_id == OPERATOR_RESPONSE_WITNESS_ID
    assert validation.response_kind == OPERATOR_RESPONSE_MISSING_KIND
    assert validation.witness_count == len(REQUIRED_WITNESS_KINDS)
    assert validation.authority_denial_count == len(FALSE_AUTHORITY_FLAGS) + 1
    assert produced_witness["response_status"] == "AwaitingEvidence"
    assert produced_witness["response_record_collected"] is False
    assert produced_witness["approval_satisfied"] is False


def test_live_producer_operator_response_witness_projects_approval_request() -> None:
    request_validation, approval_request = validate_live_producer_operator_approval_request()
    produced_witness = project_operator_approval_request_to_operator_response_witness(approval_request)
    witnesses = produced_witness["witnesses_after_response"]

    assert request_validation.ok is True
    assert produced_witness["response_witness_id"] == OPERATOR_RESPONSE_WITNESS_ID
    assert produced_witness["response_kind"] == OPERATOR_RESPONSE_MISSING_KIND
    assert tuple(witness["witness_kind"] for witness in witnesses) == REQUIRED_WITNESS_KINDS
    assert all(witness["status"] == "AwaitingEvidence" for witness in witnesses)
    assert all(witness["authority_granted"] is False for witness in witnesses)
    assert all(witness["blocks_live_producer"] is True for witness in witnesses)
    assert produced_witness["operator_response"]["observed_response_kind"] == OPERATOR_RESPONSE_MISSING_KIND
    assert produced_witness["operator_response"]["response_record_collected"] is False
    assert produced_witness["operator_response"]["live_execution_authorized_after_response"] is False
    assert produced_witness["authority_denials"]["live_execution_authorized"] is False


def test_live_producer_operator_response_witness_rejects_collected_response(tmp_path: Path) -> None:
    witness = _default_witness()
    witness["response_record_collected"] = True
    witness["operator_response"]["response_record_collected"] = True
    witness_path = tmp_path / "operator-response-witness.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validate_live_producer_operator_response_witness(fixture_path=witness_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "response_record_collected" in serialized_errors
    assert produced_witness["response_record_collected"] is False
    assert produced_witness["operator_response"]["response_record_collected"] is False


def test_live_producer_operator_response_witness_rejects_approval_satisfied(tmp_path: Path) -> None:
    witness = _default_witness()
    witness["approval_satisfied"] = True
    witness["response_kind"] = "record_operator_approval_witness"
    witness["operator_response"]["observed_response_kind"] = "record_operator_approval_witness"
    witness_path = tmp_path / "operator-response-witness.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validate_live_producer_operator_response_witness(fixture_path=witness_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "approval_satisfied" in serialized_errors
    assert "operator_response.observed_response_kind" in serialized_errors
    assert produced_witness["approval_satisfied"] is False
    assert produced_witness["response_kind"] == OPERATOR_RESPONSE_MISSING_KIND


def test_live_producer_operator_response_witness_rejects_live_authority(tmp_path: Path) -> None:
    witness = _default_witness()
    witness["authority_denials"]["live_execution_authorized"] = True
    witness["operator_response"]["live_execution_authorized_after_response"] = True
    witness_path = tmp_path / "operator-response-witness.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validate_live_producer_operator_response_witness(fixture_path=witness_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "live execution authority" in serialized_errors
    assert "live_execution_authorized_after_response" in serialized_errors
    assert produced_witness["authority_denials"]["live_execution_authorized"] is False
    assert produced_witness["operator_response"]["live_execution_authorized_after_response"] is False


def test_live_producer_operator_response_witness_rejects_mutation_route_ref(tmp_path: Path) -> None:
    witness = _default_witness()
    witness["operator_response"]["response_record_ref"] = "POST /api/v1/harness/live-producer/approval"
    witness_path = tmp_path / "operator-response-witness.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validate_live_producer_operator_response_witness(fixture_path=witness_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert produced_witness["operator_response"]["response_record_ref"] == "approval://operator-live-producer-approval-required"
    assert produced_witness["terminal_closure"] is False


def test_live_producer_operator_response_witness_rejects_secret_like_value(tmp_path: Path) -> None:
    witness = _default_witness()
    witness["witnesses_after_response"][3]["evidence_ref"] = "secret-handoff://ghp_forbiddencredential"
    witness_path = tmp_path / "operator-response-witness.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validate_live_producer_operator_response_witness(fixture_path=witness_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "ghp_forbiddencredential" not in serialized_errors
    assert produced_witness["effect_boundary"]["secret_mutation_enabled"] is False


def test_live_producer_operator_response_witness_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["witness_count"] == len(REQUIRED_WITNESS_KINDS)
    assert payload["produced_witness"]["approval_satisfied"] is False
