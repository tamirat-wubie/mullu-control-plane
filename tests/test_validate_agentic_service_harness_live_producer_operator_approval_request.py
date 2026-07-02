"""Tests for Agentic Service Harness live producer operator approval request.

Purpose: prove the operator approval request is explicit, uncollected, and
non-authorizing before live producer implementation work begins.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_approval
and scripts.validate_agentic_service_harness_live_producer_operator_approval_request.
Invariants:
  - The default approval request validates.
  - Operator approval remains `AwaitingEvidence` and uncollected.
  - Mutation route, credential, approval collection, and authority drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.agentic_service_harness_live_producer_operator_approval import (  # noqa: E402
    OPERATOR_APPROVAL_REQUEST_ID,
    OPERATOR_APPROVAL_WITNESS_KIND,
    REMAINING_WITNESS_KINDS,
    project_witness_requirements_to_operator_approval_request,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import (  # noqa: E402
    FALSE_AUTHORITY_FLAGS,
)
from scripts.validate_agentic_service_harness_live_producer_operator_approval_request import (  # noqa: E402
    DEFAULT_FIXTURE,
    main,
    validate_live_producer_operator_approval_request,
)
from scripts.validate_agentic_service_harness_live_producer_witness_requirements import (  # noqa: E402
    validate_live_producer_witness_requirements,
)


def _default_request() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_live_producer_operator_approval_request_accept_default_fixture() -> None:
    validation, produced_request = validate_live_producer_operator_approval_request()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.fixture_path == "examples/agentic_service_harness_live_producer_operator_approval_request.local.json"
    assert validation.schema_path == "schemas/agentic_service_harness_live_producer_operator_approval_request.schema.json"
    assert validation.request_id == OPERATOR_APPROVAL_REQUEST_ID
    assert validation.witness_kind == OPERATOR_APPROVAL_WITNESS_KIND
    assert validation.remaining_witness_count == len(REMAINING_WITNESS_KINDS)
    assert validation.authority_denial_count == len(FALSE_AUTHORITY_FLAGS) + 1
    assert produced_request["approval_status"] == "AwaitingEvidence"
    assert produced_request["approval_collected"] is False
    assert produced_request["authority_granted"] is False
    assert produced_request["governed_collection_binding"]["collection_id"] == "collection.operator_approval"
    assert produced_request["governed_collection_binding"]["binding_status"] == "AwaitingEvidence"
    assert produced_request["governed_collection_binding"]["authority_granted"] is False


def test_live_producer_operator_approval_request_projects_witness_requirements() -> None:
    requirements_validation, witness_requirements = validate_live_producer_witness_requirements()
    produced_request = project_witness_requirements_to_operator_approval_request(witness_requirements)
    remaining_witnesses = produced_request["remaining_witnesses"]

    assert requirements_validation.ok is True
    assert produced_request["request_id"] == OPERATOR_APPROVAL_REQUEST_ID
    assert produced_request["witness_kind"] == OPERATOR_APPROVAL_WITNESS_KIND
    assert produced_request["requested_evidence_ref"] == "approval://operator-live-producer-approval-required"
    assert (
        produced_request["governed_collection_binding"]["requirements_evidence_ref"]
        == produced_request["requested_evidence_ref"]
    )
    assert (
        produced_request["governed_collection_binding"]["governed_artifact_ref"]
        == "examples/agentic_service_harness_live_producer_operator_approval_request.local.json"
    )
    assert produced_request["governed_collection_binding"]["approval_collected"] is False
    assert produced_request["governed_collection_binding"]["live_execution_authorized"] is False
    assert tuple(witness["witness_kind"] for witness in remaining_witnesses) == REMAINING_WITNESS_KINDS
    assert all(witness["status"] == "AwaitingEvidence" for witness in remaining_witnesses)
    assert all(witness["blocks_live_producer"] is True for witness in remaining_witnesses)
    assert produced_request["approval_request"]["response_record_collected"] is False
    assert produced_request["approval_request"]["live_execution_authorized_after_response"] is False
    assert produced_request["authority_denials"]["live_execution_authorized"] is False
    assert produced_request["effect_boundary"]["network_policy"] == "none"


def test_live_producer_operator_approval_request_rejects_collected_approval(tmp_path: Path) -> None:
    request = _default_request()
    request["approval_collected"] = True
    request["approval_request"]["response_record_collected"] = True
    request_path = tmp_path / "operator-approval-request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation, produced_request = validate_live_producer_operator_approval_request(fixture_path=request_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "approval_collected" in serialized_errors
    assert "response_record_collected" in serialized_errors
    assert produced_request["approval_collected"] is False
    assert produced_request["approval_request"]["response_record_collected"] is False


def test_live_producer_operator_approval_request_rejects_live_authority(tmp_path: Path) -> None:
    request = _default_request()
    request["authority_denials"]["live_execution_authorized"] = True
    request["approval_request"]["live_execution_authorized_after_response"] = True
    request_path = tmp_path / "operator-approval-request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation, produced_request = validate_live_producer_operator_approval_request(fixture_path=request_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "live execution authority" in serialized_errors
    assert "live_execution_authorized_after_response" in serialized_errors
    assert produced_request["authority_denials"]["live_execution_authorized"] is False
    assert produced_request["approval_request"]["live_execution_authorized_after_response"] is False


def test_live_producer_operator_approval_request_rejects_collection_binding_drift(tmp_path: Path) -> None:
    request = _default_request()
    request["governed_collection_binding"]["requirements_evidence_ref"] = (
        "approval://operator-live-producer-untracked"
    )
    request["governed_collection_binding"]["governed_artifact_ref"] = (
        "examples/agentic_service_harness_live_producer_effect_receipt_preflight.local.json"
    )
    request["governed_collection_binding"]["binding_status"] = "SolvedVerified"
    request["governed_collection_binding"]["authority_granted"] = True
    request["governed_collection_binding"]["approval_collected"] = True
    request["governed_collection_binding"]["live_execution_authorized"] = True
    request_path = tmp_path / "operator-approval-request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation, produced_request = validate_live_producer_operator_approval_request(fixture_path=request_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "governed_collection_binding.requirements_evidence_ref mismatch" in serialized_errors
    assert "governed_collection_binding.governed_artifact_ref mismatch" in serialized_errors
    assert "governed_collection_binding.binding_status mismatch" in serialized_errors
    assert "governed_collection_binding.authority_granted mismatch" in serialized_errors
    assert "governed_collection_binding.approval_collected mismatch" in serialized_errors
    assert "governed_collection_binding.live_execution_authorized mismatch" in serialized_errors
    assert produced_request["governed_collection_binding"]["authority_granted"] is False
    assert produced_request["governed_collection_binding"]["approval_collected"] is False
    assert produced_request["governed_collection_binding"]["live_execution_authorized"] is False


def test_live_producer_operator_approval_request_rejects_mutation_route_ref(tmp_path: Path) -> None:
    request = _default_request()
    request["requested_evidence_ref"] = "POST /api/v1/harness/live-producer/approval"
    request_path = tmp_path / "operator-approval-request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation, produced_request = validate_live_producer_operator_approval_request(fixture_path=request_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert produced_request["requested_evidence_ref"] == "approval://operator-live-producer-approval-required"
    assert produced_request["terminal_closure"] is False


def test_live_producer_operator_approval_request_rejects_secret_like_value(tmp_path: Path) -> None:
    request = _default_request()
    request["remaining_witnesses"][2]["evidence_ref"] = "secret-handoff://ghp_forbiddencredential"
    request_path = tmp_path / "operator-approval-request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation, produced_request = validate_live_producer_operator_approval_request(fixture_path=request_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "ghp_forbiddencredential" not in serialized_errors
    assert produced_request["effect_boundary"]["secret_mutation_enabled"] is False


def test_live_producer_operator_approval_request_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["remaining_witness_count"] == len(REMAINING_WITNESS_KINDS)
    assert payload["produced_request"]["approval_collected"] is False
    assert payload["produced_request"]["governed_collection_binding"]["blocks_live_producer"] is True
