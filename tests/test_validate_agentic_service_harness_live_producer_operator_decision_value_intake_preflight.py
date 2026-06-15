"""Tests for Agentic Service Harness operator decision value intake preflight.

Purpose: prove future explicit operator decision values have a governed intake
contract before any value is collected or live authority is granted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_value_intake_preflight
and scripts.validate_agentic_service_harness_live_producer_operator_decision_value_intake_preflight.
Invariants:
  - The default intake preflight validates.
  - The preflight records no operator value.
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
    OPERATOR_DECISION_VALUE_INTAKE_PREFLIGHT_ID,
    project_pending_status_to_value_intake_preflight,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_operator_decision_pending_status import (  # noqa: E402
    validate_live_producer_operator_decision_pending_status,
)
from scripts.validate_agentic_service_harness_live_producer_operator_decision_value_intake_preflight import (  # noqa: E402
    DEFAULT_FIXTURE,
    main,
    validate_live_producer_operator_decision_value_intake_preflight,
)


def _default_preflight() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_live_producer_operator_decision_value_intake_preflight_accepts_default_fixture() -> None:
    validation, produced_preflight = validate_live_producer_operator_decision_value_intake_preflight()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.preflight_boundary_id == OPERATOR_DECISION_VALUE_INTAKE_PREFLIGHT_ID
    assert validation.intake_status == "AwaitingEvidence"
    assert validation.accepted_value_contract_count == len(ACCEPTED_RECORD_KINDS)
    assert validation.authority_denial_count == len(FALSE_AUTHORITY_FLAGS) + 1
    assert produced_preflight["schema_ready"] is True
    assert produced_preflight["operator_value_collected"] is False
    assert produced_preflight["explicit_operator_value_present"] is False
    assert produced_preflight["authority_granted"] is False


def test_live_producer_operator_decision_value_intake_preflight_projects_pending_status() -> None:
    pending_validation, pending_status = validate_live_producer_operator_decision_pending_status()
    produced_preflight = project_pending_status_to_value_intake_preflight(pending_status)
    contracts = produced_preflight["accepted_value_contracts"]

    assert pending_validation.ok is True
    assert produced_preflight["preflight_boundary_id"] == OPERATOR_DECISION_VALUE_INTAKE_PREFLIGHT_ID
    assert tuple(entry["decision_kind"] for entry in contracts) == ACCEPTED_RECORD_KINDS
    assert all(tuple(entry["required_fields"]) == REQUIRED_DECISION_RECORD_FIELDS for entry in contracts)
    assert all(tuple(entry["forbidden_fields"]) == FORBIDDEN_DECISION_VALUE_FIELDS for entry in contracts)
    assert all(entry["witness_ref_required"] is True for entry in contracts)
    assert all(entry["records_operator_intent_only"] is True for entry in contracts)
    assert all(entry["grants_live_authority"] is False for entry in contracts)
    assert produced_preflight["effect_boundary"]["network_policy"] == "none"


def test_live_producer_operator_decision_value_intake_preflight_rejects_collected_value(
    tmp_path: Path,
) -> None:
    preflight = _default_preflight()
    preflight["operator_value_collected"] = True
    preflight["explicit_operator_value_present"] = True
    preflight_path = tmp_path / "operator-decision-value-intake-preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")

    validation, produced_preflight = validate_live_producer_operator_decision_value_intake_preflight(
        fixture_path=preflight_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "operator_value_collected" in serialized_errors
    assert "explicit_operator_value_present" in serialized_errors
    assert produced_preflight["operator_value_collected"] is False
    assert produced_preflight["explicit_operator_value_present"] is False


def test_live_producer_operator_decision_value_intake_preflight_rejects_live_authority(
    tmp_path: Path,
) -> None:
    preflight = _default_preflight()
    preflight["accepted_value_contracts"][0]["grants_live_authority"] = True
    preflight["authority_denials"]["live_execution_authorized"] = True
    preflight_path = tmp_path / "operator-decision-value-intake-preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")

    validation, produced_preflight = validate_live_producer_operator_decision_value_intake_preflight(
        fixture_path=preflight_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "grants_live_authority" in serialized_errors
    assert "live execution authority" in serialized_errors
    assert produced_preflight["accepted_value_contracts"][0]["grants_live_authority"] is False


def test_live_producer_operator_decision_value_intake_preflight_rejects_mutation_route_ref(
    tmp_path: Path,
) -> None:
    preflight = _default_preflight()
    preflight["source_pending_status_ref"] = "POST /api/v1/harness/live-producer/operator-decision-value"
    preflight_path = tmp_path / "operator-decision-value-intake-preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")

    validation, produced_preflight = validate_live_producer_operator_decision_value_intake_preflight(
        fixture_path=preflight_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert produced_preflight["source_pending_status_ref"].startswith("pending-status://")


def test_live_producer_operator_decision_value_intake_preflight_rejects_secret_like_value(
    tmp_path: Path,
) -> None:
    preflight = _default_preflight()
    preflight["next_action"] = "Provide github_pat_forbiddencredential"
    preflight_path = tmp_path / "operator-decision-value-intake-preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")

    validation, produced_preflight = validate_live_producer_operator_decision_value_intake_preflight(
        fixture_path=preflight_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "github_pat_forbiddencredential" not in serialized_errors
    assert produced_preflight["effect_boundary"]["secret_mutation_enabled"] is False


def test_live_producer_operator_decision_value_intake_preflight_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["accepted_value_contract_count"] == len(ACCEPTED_RECORD_KINDS)
    assert payload["produced_preflight"]["operator_value_collected"] is False
    assert payload["produced_preflight"]["authority_granted"] is False
