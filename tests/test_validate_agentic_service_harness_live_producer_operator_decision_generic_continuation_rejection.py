"""Tests for Agentic Service Harness generic continuation rejection witness.

Purpose: prove generic continuation cannot satisfy operator decision value
requirements or grant live producer authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_generic_continuation_rejection
and scripts.validate_agentic_service_harness_live_producer_operator_decision_generic_continuation_rejection.
Invariants:
  - The default rejection witness validates.
  - Generic continuation is rejected as a non-decision input.
  - Mutation route, credential, value, and authority drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.agentic_service_harness_live_producer_operator_decision_generic_continuation_rejection import (  # noqa: E402
    GENERIC_CONTINUATION_REJECTION_WITNESS_ID,
    REJECTION_RULE_IDS,
    project_value_intake_preflight_to_generic_continuation_rejection,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_operator_decision_generic_continuation_rejection import (  # noqa: E402
    DEFAULT_FIXTURE,
    main,
    validate_live_producer_operator_decision_generic_continuation_rejection,
)
from scripts.validate_agentic_service_harness_live_producer_operator_decision_value_intake_preflight import (  # noqa: E402
    validate_live_producer_operator_decision_value_intake_preflight,
)


def _default_witness() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_live_producer_operator_decision_generic_continuation_rejection_accepts_default_fixture() -> None:
    validation, produced_witness = validate_live_producer_operator_decision_generic_continuation_rejection()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.rejection_witness_id == GENERIC_CONTINUATION_REJECTION_WITNESS_ID
    assert validation.witness_status == "rejected_non_decision_input"
    assert validation.rejection_rule_count == len(REJECTION_RULE_IDS)
    assert validation.authority_denial_count == len(FALSE_AUTHORITY_FLAGS) + 1
    assert produced_witness["generic_continuation_rejected"] is True
    assert produced_witness["generic_continuation_accepted_as_decision"] is False
    assert produced_witness["operator_value_collected"] is False
    assert produced_witness["authority_granted"] is False


def test_live_producer_operator_decision_generic_continuation_rejection_projects_preflight() -> None:
    preflight_validation, preflight = validate_live_producer_operator_decision_value_intake_preflight()
    produced_witness = project_value_intake_preflight_to_generic_continuation_rejection(preflight)
    rules = produced_witness["rejection_rules"]

    assert preflight_validation.ok is True
    assert produced_witness["rejection_witness_id"] == GENERIC_CONTINUATION_REJECTION_WITNESS_ID
    assert tuple(entry["rule_id"] for entry in rules) == REJECTION_RULE_IDS
    assert all(entry["applies"] is True for entry in rules)
    assert all(entry["decision"] == "reject" for entry in rules)
    assert all(entry["grants_live_authority"] is False for entry in rules)
    assert produced_witness["effect_boundary"]["network_policy"] == "none"


def test_live_producer_operator_decision_generic_continuation_rejection_rejects_accepted_continuation(
    tmp_path: Path,
) -> None:
    witness = _default_witness()
    witness["generic_continuation_rejected"] = False
    witness["generic_continuation_accepted_as_decision"] = True
    witness_path = tmp_path / "generic-continuation-rejection.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validate_live_producer_operator_decision_generic_continuation_rejection(
        fixture_path=witness_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "generic_continuation_rejected" in serialized_errors
    assert "generic_continuation_accepted_as_decision" in serialized_errors
    assert produced_witness["generic_continuation_rejected"] is True
    assert produced_witness["generic_continuation_accepted_as_decision"] is False


def test_live_producer_operator_decision_generic_continuation_rejection_rejects_live_authority(
    tmp_path: Path,
) -> None:
    witness = _default_witness()
    witness["rejection_rules"][0]["grants_live_authority"] = True
    witness["authority_denials"]["live_execution_authorized"] = True
    witness_path = tmp_path / "generic-continuation-rejection.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validate_live_producer_operator_decision_generic_continuation_rejection(
        fixture_path=witness_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "grants_live_authority" in serialized_errors
    assert "live execution authority" in serialized_errors
    assert produced_witness["rejection_rules"][0]["grants_live_authority"] is False


def test_live_producer_operator_decision_generic_continuation_rejection_rejects_mutation_route_ref(
    tmp_path: Path,
) -> None:
    witness = _default_witness()
    witness["source_preflight_ref"] = "POST /api/v1/harness/live-producer/operator-decision"
    witness_path = tmp_path / "generic-continuation-rejection.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validate_live_producer_operator_decision_generic_continuation_rejection(
        fixture_path=witness_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert produced_witness["source_preflight_ref"].startswith("preflight://")


def test_live_producer_operator_decision_generic_continuation_rejection_rejects_secret_like_value(
    tmp_path: Path,
) -> None:
    witness = _default_witness()
    witness["next_action"] = "Provide ghp_forbiddencredential"
    witness_path = tmp_path / "generic-continuation-rejection.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validate_live_producer_operator_decision_generic_continuation_rejection(
        fixture_path=witness_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "ghp_forbiddencredential" not in serialized_errors
    assert produced_witness["effect_boundary"]["secret_mutation_enabled"] is False


def test_live_producer_operator_decision_generic_continuation_rejection_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["rejection_rule_count"] == len(REJECTION_RULE_IDS)
    assert payload["produced_witness"]["generic_continuation_rejected"] is True
    assert payload["produced_witness"]["authority_granted"] is False
