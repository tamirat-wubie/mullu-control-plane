"""Tests for Agentic Service Harness live producer witness requirements.

Purpose: prove required live-producer witnesses remain explicit, missing, and
authority-denying before implementation work begins.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_witness_requirements
and scripts.validate_agentic_service_harness_live_producer_witness_requirements.
Invariants:
  - The default witness requirements validate.
  - Witnesses remain `AwaitingEvidence` and grant no authority.
  - Mutation route, credential, and authority drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.agentic_service_harness_live_producer_witness_requirements import (  # noqa: E402
    FALSE_AUTHORITY_FLAGS,
    GOVERNED_WITNESS_COLLECTION,
    REQUIRED_WITNESS_KINDS,
    WITNESS_REQUIREMENTS_ID,
    project_admission_gate_to_witness_requirements,
)
from scripts.validate_agentic_service_harness_live_producer_admission_gate import (  # noqa: E402
    validate_live_producer_admission_gate,
)
from scripts.validate_agentic_service_harness_live_producer_witness_requirements import (  # noqa: E402
    DEFAULT_FIXTURE,
    main,
    validate_live_producer_witness_requirements,
)


def _default_requirements() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_live_producer_witness_requirements_accept_default_fixture() -> None:
    validation, produced_requirements = validate_live_producer_witness_requirements()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.fixture_path == "examples/agentic_service_harness_live_producer_witness_requirements.local.json"
    assert validation.schema_path == "schemas/agentic_service_harness_live_producer_witness_requirements.schema.json"
    assert validation.requirements_id == WITNESS_REQUIREMENTS_ID
    assert validation.witness_count == len(REQUIRED_WITNESS_KINDS)
    assert validation.governed_collection_count == len(REQUIRED_WITNESS_KINDS)
    assert validation.authority_denial_count == len(FALSE_AUTHORITY_FLAGS) + 1
    assert produced_requirements["solver_outcome"] == "AwaitingEvidence"
    assert produced_requirements["admission_decision"] == "blocked"
    assert produced_requirements["live_producer_implemented"] is False
    assert tuple(
        entry["witness_kind"] for entry in produced_requirements["governed_witness_collection"]
    ) == REQUIRED_WITNESS_KINDS


def test_live_producer_witness_requirements_project_admission_gate() -> None:
    admission_validation, admission_gate = validate_live_producer_admission_gate()
    produced_requirements = project_admission_gate_to_witness_requirements(admission_gate)
    witnesses = produced_requirements["witnesses"]

    assert admission_validation.ok is True
    assert tuple(witness["witness_kind"] for witness in witnesses) == REQUIRED_WITNESS_KINDS
    assert all(witness["status"] == "AwaitingEvidence" for witness in witnesses)
    assert all(witness["authority_granted"] is False for witness in witnesses)
    assert all(witness["admission_effect"] == "blocks_live_producer" for witness in witnesses)
    assert produced_requirements["governed_witness_collection"][0]["governed_artifact_ref"] == (
        GOVERNED_WITNESS_COLLECTION[0]["governed_artifact_ref"]
    )
    assert all(entry["status"] == "AwaitingEvidence" for entry in produced_requirements["governed_witness_collection"])
    assert all(entry["authority_granted"] is False for entry in produced_requirements["governed_witness_collection"])
    assert all(entry["blocks_live_producer"] is True for entry in produced_requirements["governed_witness_collection"])
    assert produced_requirements["authority_denials"]["live_execution_authorized"] is False
    assert produced_requirements["effect_boundary"]["network_policy"] == "none"
    assert all(produced_requirements["effect_boundary"][flag_name] is False for flag_name in FALSE_AUTHORITY_FLAGS)


def test_live_producer_witness_requirements_rejects_authority_grant(tmp_path: Path) -> None:
    requirements = _default_requirements()
    requirements["witnesses"][0]["authority_granted"] = True
    requirements_path = tmp_path / "witness-requirements.json"
    requirements_path.write_text(json.dumps(requirements), encoding="utf-8")

    validation, produced_requirements = validate_live_producer_witness_requirements(fixture_path=requirements_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority_granted" in serialized_errors
    assert produced_requirements["witnesses"][0]["authority_granted"] is False
    assert produced_requirements["admission_decision"] == "blocked"


def test_live_producer_witness_requirements_rejects_mutation_route_ref(tmp_path: Path) -> None:
    requirements = _default_requirements()
    requirements["witnesses"][1]["evidence_ref"] = "POST /api/v1/harness/live-producer"
    requirements_path = tmp_path / "witness-requirements.json"
    requirements_path.write_text(json.dumps(requirements), encoding="utf-8")

    validation, produced_requirements = validate_live_producer_witness_requirements(fixture_path=requirements_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert produced_requirements["witnesses"][1]["status"] == "AwaitingEvidence"
    assert produced_requirements["terminal_closure"] is False


def test_live_producer_witness_requirements_rejects_secret_like_value(tmp_path: Path) -> None:
    requirements = _default_requirements()
    requirements["witnesses"][3]["evidence_ref"] = "secret-handoff://ghp_forbiddencredential"
    requirements_path = tmp_path / "witness-requirements.json"
    requirements_path.write_text(json.dumps(requirements), encoding="utf-8")

    validation, produced_requirements = validate_live_producer_witness_requirements(fixture_path=requirements_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "ghp_forbiddencredential" not in serialized_errors
    assert produced_requirements["effect_boundary"]["secret_mutation_enabled"] is False


def test_live_producer_witness_requirements_rejects_solved_witness(tmp_path: Path) -> None:
    requirements = _default_requirements()
    requirements["witnesses"][4]["status"] = "SolvedVerified"
    requirements_path = tmp_path / "witness-requirements.json"
    requirements_path.write_text(json.dumps(requirements), encoding="utf-8")

    validation, produced_requirements = validate_live_producer_witness_requirements(fixture_path=requirements_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "AwaitingEvidence" in serialized_errors
    assert produced_requirements["witnesses"][4]["status"] == "AwaitingEvidence"
    assert produced_requirements["live_producer_implemented"] is False


def test_live_producer_witness_requirements_rejects_governed_collection_drift(tmp_path: Path) -> None:
    requirements = _default_requirements()
    requirements["governed_witness_collection"][1]["requirements_evidence_ref"] = "receipt://other"
    requirements["governed_witness_collection"][2]["governed_artifact_ref"] = "examples/other.local.json"
    requirements["governed_witness_collection"][3]["status"] = "SolvedVerified"
    requirements["governed_witness_collection"][4]["authority_granted"] = True
    requirements["governed_witness_collection"][4]["blocks_live_producer"] = False
    requirements_path = tmp_path / "witness-requirements.json"
    requirements_path.write_text(json.dumps(requirements), encoding="utf-8")

    validation, produced_requirements = validate_live_producer_witness_requirements(fixture_path=requirements_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "effect_receipt requirements_evidence_ref must match witness evidence_ref" in serialized_errors
    assert "external_adapter_evidence governed_artifact_ref mismatch" in serialized_errors
    assert "secret_handoff collection status must be AwaitingEvidence" in serialized_errors
    assert "rollback_proof collection authority_granted must be false" in serialized_errors
    assert "rollback_proof collection must block live producer" in serialized_errors
    assert produced_requirements["governed_witness_collection"][4]["authority_granted"] is False


def test_live_producer_witness_requirements_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["witness_count"] == len(REQUIRED_WITNESS_KINDS)
    assert payload["governed_collection_count"] == len(REQUIRED_WITNESS_KINDS)
    assert payload["produced_requirements"]["admission_decision"] == "blocked"
