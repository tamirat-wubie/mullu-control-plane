"""Tests for Agentic Service Harness explicit operator decision value templates.

Purpose: prove approval/rejection templates remain non-authorizing and are not
accepted as operator decision values.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_value_template
and scripts.validate_agentic_service_harness_live_producer_operator_decision_value_template.
Invariants:
  - The default template packet validates.
  - Templates are not accepted as values.
  - Mutation route, credential, value, and authority drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.agentic_service_harness_live_producer_operator_decision_record import ACCEPTED_RECORD_KINDS  # noqa: E402
from gateway.agentic_service_harness_live_producer_operator_decision_value_template import (  # noqa: E402
    OPERATOR_DECISION_VALUE_TEMPLATE_ID,
    project_value_request_to_value_template,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_operator_decision_value_request import (  # noqa: E402
    validate_live_producer_operator_decision_value_request,
)
from scripts.validate_agentic_service_harness_live_producer_operator_decision_value_template import (  # noqa: E402
    DEFAULT_FIXTURE,
    main,
    validate_live_producer_operator_decision_value_template,
)


def _default_template() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_live_producer_operator_decision_value_template_accepts_default_fixture() -> None:
    validation, produced_template = validate_live_producer_operator_decision_value_template()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.template_packet_id == OPERATOR_DECISION_VALUE_TEMPLATE_ID
    assert validation.template_status == "template_only_awaiting_operator_value"
    assert validation.decision_value_template_count == len(ACCEPTED_RECORD_KINDS)
    assert validation.authority_denial_count == len(FALSE_AUTHORITY_FLAGS) + 1
    assert produced_template["template_controls"]["template_only"] is True
    assert produced_template["template_accepted_as_value"] is False
    assert produced_template["operator_value_collected"] is False
    assert produced_template["authority_granted"] is False


def test_live_producer_operator_decision_value_template_projects_request() -> None:
    request_validation, value_request = validate_live_producer_operator_decision_value_request()
    produced_template = project_value_request_to_value_template(value_request)
    templates = produced_template["decision_value_templates"]

    assert request_validation.ok is True
    assert produced_template["template_packet_id"] == OPERATOR_DECISION_VALUE_TEMPLATE_ID
    assert tuple(entry["decision_kind"] for entry in templates) == ACCEPTED_RECORD_KINDS
    assert all(entry["template_only"] is True for entry in templates)
    assert all(entry["accepted_as_value"] is False for entry in templates)
    assert all(entry["grants_live_authority"] is False for entry in templates)
    assert all(entry["field_templates"]["decision_kind"] == entry["decision_kind"] for entry in templates)
    assert produced_template["effect_boundary"]["network_policy"] == "none"


def test_live_producer_operator_decision_value_template_rejects_template_as_value(tmp_path: Path) -> None:
    template = _default_template()
    template["template_accepted_as_value"] = True
    template["decision_value_templates"][0]["accepted_as_value"] = True
    template_path = tmp_path / "operator-decision-value-template.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")

    validation, produced_template = validate_live_producer_operator_decision_value_template(fixture_path=template_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "template_accepted_as_value" in serialized_errors
    assert "accepted_as_value" in serialized_errors
    assert produced_template["template_accepted_as_value"] is False
    assert produced_template["decision_value_templates"][0]["accepted_as_value"] is False


def test_live_producer_operator_decision_value_template_rejects_collected_value(tmp_path: Path) -> None:
    template = _default_template()
    template["operator_value_collected"] = True
    template["explicit_operator_value_present"] = True
    template_path = tmp_path / "operator-decision-value-template.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")

    validation, produced_template = validate_live_producer_operator_decision_value_template(fixture_path=template_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "operator_value_collected" in serialized_errors
    assert "explicit_operator_value_present" in serialized_errors
    assert produced_template["operator_value_collected"] is False
    assert produced_template["explicit_operator_value_present"] is False


def test_live_producer_operator_decision_value_template_rejects_live_authority(tmp_path: Path) -> None:
    template = _default_template()
    template["decision_value_templates"][0]["grants_live_authority"] = True
    template["template_controls"]["live_authority_on_template"] = True
    template["authority_denials"]["live_execution_authorized"] = True
    template_path = tmp_path / "operator-decision-value-template.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")

    validation, produced_template = validate_live_producer_operator_decision_value_template(fixture_path=template_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "grants_live_authority" in serialized_errors
    assert "template_controls.live_authority_on_template" in serialized_errors
    assert "live execution authority" in serialized_errors
    assert produced_template["authority_denials"]["live_execution_authorized"] is False


def test_live_producer_operator_decision_value_template_rejects_mutation_route_ref(tmp_path: Path) -> None:
    template = _default_template()
    template["source_value_request_ref"] = "POST /api/v1/harness/live-producer/operator-decision-value"
    template_path = tmp_path / "operator-decision-value-template.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")

    validation, produced_template = validate_live_producer_operator_decision_value_template(fixture_path=template_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert produced_template["source_value_request_ref"].startswith("value-request://")


def test_live_producer_operator_decision_value_template_rejects_secret_like_value(tmp_path: Path) -> None:
    template = _default_template()
    template["next_action"] = "Provide github_pat_forbiddencredential"
    template_path = tmp_path / "operator-decision-value-template.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")

    validation, produced_template = validate_live_producer_operator_decision_value_template(fixture_path=template_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "github_pat_forbiddencredential" not in serialized_errors
    assert produced_template["effect_boundary"]["secret_mutation_enabled"] is False


def test_live_producer_operator_decision_value_template_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["decision_value_template_count"] == len(ACCEPTED_RECORD_KINDS)
    assert payload["produced_template"]["template_accepted_as_value"] is False
    assert payload["produced_template"]["authority_granted"] is False
