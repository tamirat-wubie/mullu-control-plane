"""Tests for Agentic Service Harness explicit operator decision value request.

Purpose: prove the request packet asks for explicit operator intent without
collecting a value or granting live producer authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_value_request
and scripts.validate_agentic_service_harness_live_producer_operator_decision_value_request.
Invariants:
  - The default value request validates.
  - The request records no operator value.
  - Mutation route, credential, value, and authority drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.agentic_service_harness_live_producer_operator_decision_record import (  # noqa: E402
    ACCEPTED_RECORD_KINDS,
    REQUIRED_DECISION_RECORD_FIELDS,
)
from gateway.agentic_service_harness_live_producer_operator_decision_value_intake_preflight import (  # noqa: E402
    FORBIDDEN_DECISION_VALUE_FIELDS,
)
from gateway.agentic_service_harness_live_producer_operator_decision_value_request import (  # noqa: E402
    OPERATOR_DECISION_VALUE_REQUEST_ID,
    project_generic_continuation_rejection_to_value_request,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_operator_decision_generic_continuation_rejection import (  # noqa: E402
    validate_live_producer_operator_decision_generic_continuation_rejection,
)
from scripts.validate_agentic_service_harness_live_producer_operator_decision_value_request import (  # noqa: E402
    DEFAULT_FIXTURE,
    main,
    validate_live_producer_operator_decision_value_request,
)


def _default_request() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_live_producer_operator_decision_value_request_accepts_default_fixture() -> None:
    validation, produced_request = validate_live_producer_operator_decision_value_request()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.request_id == OPERATOR_DECISION_VALUE_REQUEST_ID
    assert validation.request_status == "awaiting_explicit_operator_decision_value"
    assert validation.decision_value_requirement_count == len(ACCEPTED_RECORD_KINDS)
    assert validation.authority_denial_count == len(FALSE_AUTHORITY_FLAGS) + 1
    assert produced_request["operator_value_collected"] is False
    assert produced_request["explicit_operator_value_present"] is False
    assert produced_request["authority_granted"] is False
    assert produced_request["request_controls"]["freeform_continuation_allowed"] is False


def test_live_producer_operator_decision_value_request_projects_rejection_witness() -> None:
    rejection_validation, rejection_witness = validate_live_producer_operator_decision_generic_continuation_rejection()
    produced_request = project_generic_continuation_rejection_to_value_request(rejection_witness)
    requirements = produced_request["decision_value_requirements"]

    assert rejection_validation.ok is True
    assert produced_request["request_id"] == OPERATOR_DECISION_VALUE_REQUEST_ID
    assert tuple(entry["decision_kind"] for entry in requirements) == ACCEPTED_RECORD_KINDS
    assert all(tuple(entry["required_fields"]) == REQUIRED_DECISION_RECORD_FIELDS for entry in requirements)
    assert all(tuple(entry["forbidden_fields"]) == FORBIDDEN_DECISION_VALUE_FIELDS for entry in requirements)
    assert all(entry["scope_must_match_request"] is True for entry in requirements)
    assert all(entry["grants_live_authority"] is False for entry in requirements)
    assert produced_request["effect_boundary"]["network_policy"] == "none"


def test_live_producer_operator_decision_value_request_rejects_collected_value(tmp_path: Path) -> None:
    request = _default_request()
    request["operator_value_collected"] = True
    request["explicit_operator_value_present"] = True
    request_path = tmp_path / "operator-decision-value-request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation, produced_request = validate_live_producer_operator_decision_value_request(fixture_path=request_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "operator_value_collected" in serialized_errors
    assert "explicit_operator_value_present" in serialized_errors
    assert produced_request["operator_value_collected"] is False
    assert produced_request["explicit_operator_value_present"] is False


def test_live_producer_operator_decision_value_request_rejects_live_authority(tmp_path: Path) -> None:
    request = _default_request()
    request["decision_value_requirements"][0]["grants_live_authority"] = True
    request["request_controls"]["live_authority_on_request"] = True
    request["authority_denials"]["live_execution_authorized"] = True
    request_path = tmp_path / "operator-decision-value-request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation, produced_request = validate_live_producer_operator_decision_value_request(fixture_path=request_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "grants_live_authority" in serialized_errors
    assert "request_controls.live_authority_on_request" in serialized_errors
    assert "live execution authority" in serialized_errors
    assert produced_request["authority_denials"]["live_execution_authorized"] is False


def test_live_producer_operator_decision_value_request_rejects_mutation_route_ref(tmp_path: Path) -> None:
    request = _default_request()
    request["source_rejection_witness_ref"] = "POST /api/v1/harness/live-producer/operator-decision-value"
    request_path = tmp_path / "operator-decision-value-request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation, produced_request = validate_live_producer_operator_decision_value_request(fixture_path=request_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert produced_request["source_rejection_witness_ref"].startswith("rejection-witness://")


def test_live_producer_operator_decision_value_request_rejects_secret_like_value(tmp_path: Path) -> None:
    request = _default_request()
    request["next_action"] = "Provide sk-forbiddencredential"
    request_path = tmp_path / "operator-decision-value-request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation, produced_request = validate_live_producer_operator_decision_value_request(fixture_path=request_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "sk-forbiddencredential" not in serialized_errors
    assert produced_request["effect_boundary"]["secret_mutation_enabled"] is False


def test_live_producer_operator_decision_value_request_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["decision_value_requirement_count"] == len(ACCEPTED_RECORD_KINDS)
    assert payload["produced_request"]["operator_value_collected"] is False
    assert payload["produced_request"]["authority_granted"] is False
