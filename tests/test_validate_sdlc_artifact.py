"""Purpose: verify governed SDLC artifact validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_sdlc_artifact.
Invariants:
  - SDLC docs, schemas, and examples validate as one linked chain.
  - Raw private reasoning fields are rejected.
  - Cross-artifact drift is reported explicitly.
"""

from __future__ import annotations

import copy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from scripts import validate_sdlc_artifact as validator


def test_current_sdlc_contract_passes() -> None:
    errors = validator.validate_contract()
    records = validator.load_example_records()

    assert errors == []
    assert len(records) == 12
    assert all(spec.schema_path.exists() for spec in validator.ARTIFACT_SPECS)
    assert all(spec.example_path.exists() for spec in validator.ARTIFACT_SPECS)
    assert len(validator.CANONICAL_SCHEMA_REFS) == len(records)
    assert len(validator.CANONICAL_EXAMPLE_REFS) == len(records)
    assert "scripts/validate_sdlc_pr_enforcement.py" in validator.REQUIRED_VALIDATORS
    assert "implementation_receipt" in validator.GATE_BOUND_ARTIFACT_KINDS
    assert "change_request" in validator.GATE_BOUND_ARTIFACT_KINDS
    assert "recovery_handoff" in validator.GATE_BOUND_ARTIFACT_KINDS
    assert "workspace_governance_preflight" in validator.REQUIRED_VERIFICATION_COMMANDS
    assert validator.WORKSPACE_PREFLIGHT_RECEIPT_PATH == ".tmp/workspace-governance-preflight-receipt.json"
    assert validator.BRANCH_RULESET_WITNESS_PATH == "docs/main-protection-ruleset-witness.json"


def test_schema_artifacts_have_expected_identity() -> None:
    for spec in validator.ARTIFACT_SPECS:
        schema = validator._load_schema(spec.schema_path)
        errors = validator.validate_schema_artifact(schema, spec)

        assert errors == []
        assert schema["$id"] == spec.schema_id
        assert schema["title"] == spec.title
        assert schema["additionalProperties"] is False
        if spec.kind in validator.GATE_BOUND_ARTIFACT_KINDS:
            assert "uao_ref" in schema["required"]
            assert "causal_decision_trace_ref" in schema["required"]
            assert "receipt_ref" in schema["required"]


def test_example_chain_links_all_lifecycle_artifacts() -> None:
    records = validator.load_example_records()
    errors = validator.validate_example_chain(records)

    assert errors == []
    assert records["requirement"]["request_id"] == records["change_request"]["request_id"]
    assert records["work_plan"]["design_id"] == records["design_decision"]["design_id"]
    assert records["implementation_receipt"]["plan_id"] == records["work_plan"]["plan_id"]
    assert records["transition_receipt"]["change_id"] == records["change_request"]["request_id"]
    assert records["recovery_handoff"]["change_id"] == records["change_request"]["request_id"]
    assert records["recovery_handoff"]["terminal_closure_ref"] == records["closure_receipt"]["closure_id"]
    assert records["deployment_candidate"]["release_id"] == records["release_candidate"]["release_id"]
    assert records["change_request"]["receipt_ref"] in records["closure_receipt"]["receipts"]
    assert records["implementation_receipt"]["receipt_ref"] in records["closure_receipt"]["receipts"]
    assert records["transition_receipt"]["receipt_ref"] in records["closure_receipt"]["receipts"]
    assert records["recovery_handoff"]["receipt_ref"] in records["closure_receipt"]["receipts"]
    assert validator.WORKSPACE_PREFLIGHT_RECEIPT_REF in records["closure_receipt"]["receipts"]
    assert records["deployment_candidate"]["uao_ref"] in records["closure_receipt"]["uao_refs"]
    assert set(validator.CANONICAL_SCHEMA_REFS).issubset(set(records["design_decision"]["schema_changes"]))
    assert set(validator.CANONICAL_INVENTORY_REFS).issubset(set(records["work_plan"]["expected_artifacts"]))
    assert set(validator.CANONICAL_EXAMPLE_REFS).issubset(set(records["verification_receipt"]["coverage_refs"]))
    assert validator.WORKSPACE_PREFLIGHT_RECEIPT_PATH in records["verification_receipt"]["coverage_refs"]
    assert validator.BRANCH_RULESET_WITNESS_PATH in records["verification_receipt"]["coverage_refs"]
    assert validator.BRANCH_RULESET_WITNESS_PATH in records["implementation_receipt"]["documentation_changes"]
    assert set(validator.CANONICAL_INVENTORY_REFS).issubset(
        {changed_file["path"] for changed_file in records["implementation_receipt"]["changed_files"]}
    )
    assert validator.BRANCH_RULESET_WITNESS_PATH in {
        changed_file["path"] for changed_file in records["implementation_receipt"]["changed_files"]
    }


def test_raw_private_reasoning_field_is_rejected() -> None:
    records = validator.load_example_records()
    invalid_design = copy.deepcopy(records["design_decision"])
    invalid_design["raw_chain_of_thought"] = "private reasoning must not be serialized"

    errors = validator.validate_artifact_record("design_decision", invalid_design)

    assert any("raw_chain_of_thought is prohibited" in error for error in errors)
    assert len(errors) >= 1
    assert invalid_design["design_id"] == "sdlc_design_uao_validator_001"


def test_gate_decision_envelope_is_required_and_prefix_checked() -> None:
    records = validator.load_example_records()
    invalid_requirement = copy.deepcopy(records["requirement"])
    invalid_release = copy.deepcopy(records["release_candidate"])
    invalid_requirement.pop("uao_ref")
    invalid_release["receipt_ref"] = "trace://wrong/release/receipt"

    requirement_errors = validator.validate_artifact_record("requirement", invalid_requirement)
    release_errors = validator.validate_artifact_record("release_candidate", invalid_release)

    assert any("uao_ref" in error for error in requirement_errors)
    assert "release_candidate: receipt_ref must use receipt:// prefix" in release_errors
    assert "release_candidate: release_receipt must match receipt_ref" in release_errors


def test_closure_must_retain_upstream_gate_refs() -> None:
    records = validator.load_example_records()
    invalid_records = copy.deepcopy(records)
    invalid_records["closure_receipt"]["receipts"].remove(records["change_request"]["receipt_ref"])
    invalid_records["closure_receipt"]["uao_refs"].remove(records["requirement"]["uao_ref"])
    invalid_records["closure_receipt"]["causal_decision_trace_refs"].remove(
        records["deployment_candidate"]["causal_decision_trace_ref"]
    )
    invalid_records["closure_receipt"]["receipts"].remove(records["implementation_receipt"]["receipt_ref"])
    invalid_records["closure_receipt"]["receipts"].remove(records["transition_receipt"]["receipt_ref"])
    invalid_records["closure_receipt"]["receipts"].remove(records["recovery_handoff"]["receipt_ref"])
    invalid_records["closure_receipt"]["uao_refs"].remove(records["recovery_handoff"]["uao_ref"])
    invalid_records["closure_receipt"]["causal_decision_trace_refs"].remove(
        records["recovery_handoff"]["causal_decision_trace_ref"]
    )

    errors = validator.validate_example_chain(invalid_records)

    assert "example_chain: closure must include change_request receipt_ref" in errors
    assert "example_chain: closure must include requirement uao_ref" in errors
    assert "example_chain: closure must include implementation_receipt receipt_ref" in errors
    assert "example_chain: closure must include implementation receipt" in errors
    assert "example_chain: closure must include transition_receipt receipt_ref" in errors
    assert "example_chain: closure must include recovery_handoff receipt_ref" in errors
    assert "example_chain: closure must include recovery handoff receipt" in errors
    assert "example_chain: closure must include recovery_handoff uao_ref" in errors
    assert "example_chain: closure must include recovery_handoff causal_decision_trace_ref" in errors
    assert "example_chain: closure must include deployment_candidate causal_decision_trace_ref" in errors


def test_cross_artifact_request_drift_is_rejected() -> None:
    records = validator.load_example_records()
    invalid_records = copy.deepcopy(records)
    invalid_records["requirement"]["request_id"] = "wrong_request"

    errors = validator.validate_example_chain(invalid_records)

    assert "example_chain: requirement.request_id must match change request" in errors
    assert len(errors) >= 1
    assert invalid_records["change_request"]["request_id"] == "sdlc_req_uao_validator_001"


def test_work_plan_rejects_future_dependency_and_missing_validator() -> None:
    work_plan = copy.deepcopy(validator.load_example_records()["work_plan"])
    work_plan["steps"][0]["depends_on"] = [2]
    work_plan["required_validators"] = [
        item
        for item in work_plan["required_validators"]
        if item != "scripts/validate_sdlc_state_machine.py"
    ]

    errors = validator.validate_artifact_record("work_plan", work_plan)

    assert any("dependency 2 must be earlier" in error for error in errors)
    assert any("missing required validators" in error for error in errors)
    assert len(errors) >= 2


def test_inventory_closure_rejects_missing_canonical_refs() -> None:
    records = validator.load_example_records()
    invalid_design = copy.deepcopy(records["design_decision"])
    invalid_work_plan = copy.deepcopy(records["work_plan"])
    invalid_implementation = copy.deepcopy(records["implementation_receipt"])
    invalid_verification = copy.deepcopy(records["verification_receipt"])
    invalid_design["schema_changes"].remove("schemas/sdlc_recovery_handoff_receipt.schema.json")
    invalid_work_plan["expected_artifacts"].remove("examples/sdlc/closure_uao_validator.json")
    invalid_implementation["schema_changes"].remove("schemas/sdlc_transition_receipt.schema.json")
    invalid_implementation["changed_files"] = [
        changed_file
        for changed_file in invalid_implementation["changed_files"]
        if changed_file["path"] != "examples/sdlc/deployment_candidate_uao_validator.json"
    ]
    invalid_verification["coverage_refs"].remove("examples/sdlc/security_review_uao_validator.json")

    design_errors = validator.validate_artifact_record("design_decision", invalid_design)
    work_plan_errors = validator.validate_artifact_record("work_plan", invalid_work_plan)
    implementation_errors = validator.validate_artifact_record("implementation_receipt", invalid_implementation)
    verification_errors = validator.validate_artifact_record("verification_receipt", invalid_verification)

    assert any("design_decision: schema_changes missing canonical SDLC inventory refs" in error for error in design_errors)
    assert any("work_plan: expected_artifacts missing canonical SDLC inventory refs" in error for error in work_plan_errors)
    assert any("implementation_receipt: schema_changes missing canonical SDLC inventory refs" in error for error in implementation_errors)
    assert any("implementation_receipt: changed_files missing canonical SDLC inventory refs" in error for error in implementation_errors)
    assert any("verification_receipt: coverage_refs missing canonical SDLC inventory refs" in error for error in verification_errors)
    assert len(design_errors) + len(work_plan_errors) + len(implementation_errors) + len(verification_errors) >= 5


def test_design_and_verification_require_pr_enforcement_validator() -> None:
    records = validator.load_example_records()
    invalid_design = copy.deepcopy(records["design_decision"])
    invalid_verification = copy.deepcopy(records["verification_receipt"])
    invalid_design["validator_changes"] = [
        item
        for item in invalid_design["validator_changes"]
        if item != "scripts/validate_sdlc_pr_enforcement.py"
    ]
    invalid_verification["commands"] = [
        item
        for item in invalid_verification["commands"]
        if item["name"] != "sdlc_pr_enforcement_validation"
    ]
    invalid_verification["validator_outputs"] = [
        item
        for item in invalid_verification["validator_outputs"]
        if item["name"] != "sdlc_pr_enforcement_validation"
    ]

    design_errors = validator.validate_artifact_record("design_decision", invalid_design)
    verification_errors = validator.validate_artifact_record("verification_receipt", invalid_verification)

    assert any("design_decision: missing required validators" in error for error in design_errors)
    assert any("verification_receipt: missing command sdlc_pr_enforcement_validation" in error for error in verification_errors)
    assert any("verification_receipt: missing validator outputs" in error for error in verification_errors)
    assert len(design_errors) + len(verification_errors) >= 3


def test_snet_runtime_integration_gate_validates_as_design_decision() -> None:
    design_path = Path("examples/sdlc/design_snet_runtime_integration_gate_20260613.json")
    design_record = validator.load_json_object(design_path, "SNet runtime integration gate")

    errors = validator.validate_artifact_record("design_decision", design_record)

    assert errors == []
    assert design_record["requirement_id"] == "sdlc_reqspec_snet_rsim_01_20260613"
    assert set(validator.CANONICAL_SCHEMA_REFS).issubset(set(design_record["schema_changes"]))
    assert set(validator.REQUIRED_VALIDATORS).issubset(set(design_record["validator_changes"]))
    assert design_record["security_model"]["effect_bearing_requires_receipt"] is True
    assert "mcoi/mcoi_runtime/snet/engine.py" in design_record["affected_modules"]
    assert "scripts/validate_snet_mesh_receipt.py" in design_record["validator_changes"]
    assert any("run_workspace_governance_checks.py" in item for item in design_record["test_plan"])
    assert "Do not wire SNet into runtime routes" in design_record["architecture_summary"]


def test_implementation_receipt_rejects_path_escape_and_unlisted_refs() -> None:
    implementation = copy.deepcopy(validator.load_example_records()["implementation_receipt"])
    implementation["changed_files"][0]["path"] = "../outside.py"
    implementation["validator_changes"].append("scripts/not_listed_validator.py")
    implementation["rollback_refs"] = []

    errors = validator.validate_artifact_record("implementation_receipt", implementation)

    assert any("changed file path must stay workspace-relative" in error for error in errors)
    assert any("validator_changes ref is not listed in changed_files" in error for error in errors)
    assert "implementation_receipt: rollback_refs are required" in errors


def test_transition_and_verification_must_reference_implementation_receipt() -> None:
    records = validator.load_example_records()
    invalid_records = copy.deepcopy(records)
    invalid_records["transition_receipt"]["required_receipt_refs"].remove(
        records["implementation_receipt"]["receipt_ref"]
    )
    invalid_records["verification_receipt"]["coverage_refs"].remove(
        "examples/sdlc/implementation_uao_validator.json"
    )

    errors = validator.validate_example_chain(invalid_records)

    assert "example_chain: transition must require implementation receipt" in errors
    assert "example_chain: verification coverage must include implementation receipt artifact" in errors
    assert len(errors) >= 2


def test_recovery_handoff_rejects_unclosed_recovery_constraints() -> None:
    recovery_handoff = copy.deepcopy(validator.load_example_records()["recovery_handoff"])
    recovery_handoff["rollback_state"] = "partial"
    recovery_handoff["incident_handoff_required"] = False
    recovery_handoff["accepted_risk_refs"] = ["risk://sdlc/accepted/001"]
    recovery_handoff["rollback_refs"] = []
    recovery_handoff["effect_boundary_refs"].append(recovery_handoff["effect_boundary_refs"][0])

    errors = validator.validate_artifact_record("recovery_handoff", recovery_handoff)

    assert "recovery_handoff: partial or blocked rollback requires incident handoff" in errors
    assert "recovery_handoff: accepted risks require incident handoff" in errors
    assert "recovery_handoff: rollback refs are required unless rollback is not_required" in errors
    assert "recovery_handoff: effect_boundary_refs must not contain duplicates" in errors
    assert any("rollback_refs" in error for error in errors)


def test_verification_must_reference_recovery_handoff_receipt() -> None:
    records = validator.load_example_records()
    invalid_records = copy.deepcopy(records)
    invalid_records["verification_receipt"]["coverage_refs"].remove(
        "examples/sdlc/recovery_handoff_uao_validator.json"
    )

    errors = validator.validate_example_chain(invalid_records)

    assert "example_chain: verification coverage must include recovery handoff receipt artifact" in errors
    assert len(errors) >= 1
    assert invalid_records["recovery_handoff"]["receipt_ref"] in invalid_records["closure_receipt"]["receipts"]


def test_workspace_preflight_receipt_is_required_for_terminal_closure() -> None:
    records = validator.load_example_records()
    invalid_records = copy.deepcopy(records)
    invalid_records["verification_receipt"]["commands"] = [
        item
        for item in invalid_records["verification_receipt"]["commands"]
        if item["name"] != "workspace_governance_preflight"
    ]
    invalid_records["verification_receipt"]["validator_outputs"] = [
        item
        for item in invalid_records["verification_receipt"]["validator_outputs"]
        if item["name"] != "workspace_governance_preflight"
    ]
    invalid_records["verification_receipt"]["coverage_refs"].remove(validator.WORKSPACE_PREFLIGHT_RECEIPT_PATH)
    invalid_records["closure_receipt"]["receipts"].remove(validator.WORKSPACE_PREFLIGHT_RECEIPT_REF)

    verification_errors = validator.validate_artifact_record(
        "verification_receipt",
        invalid_records["verification_receipt"],
    )
    chain_errors = validator.validate_example_chain(invalid_records)

    assert "verification_receipt: missing command workspace_governance_preflight" in verification_errors
    assert any("workspace_governance_preflight" in error for error in verification_errors)
    assert (
        "example_chain: verification coverage must include workspace governance preflight receipt artifact"
        in chain_errors
    )
    assert "example_chain: closure must include workspace governance preflight receipt" in chain_errors
    assert len(verification_errors) + len(chain_errors) >= 4


def test_branch_ruleset_witness_is_required_for_pr_enforcement_closure() -> None:
    records = validator.load_example_records()
    invalid_implementation = copy.deepcopy(records["implementation_receipt"])
    invalid_verification = copy.deepcopy(records["verification_receipt"])
    invalid_implementation["changed_files"] = [
        changed_file
        for changed_file in invalid_implementation["changed_files"]
        if changed_file["path"] != validator.BRANCH_RULESET_WITNESS_PATH
    ]
    invalid_implementation["documentation_changes"].remove(validator.BRANCH_RULESET_WITNESS_PATH)
    invalid_verification["coverage_refs"].remove(validator.BRANCH_RULESET_WITNESS_PATH)

    implementation_errors = validator.validate_artifact_record(
        "implementation_receipt",
        invalid_implementation,
    )
    verification_errors = validator.validate_artifact_record(
        "verification_receipt",
        invalid_verification,
    )

    assert any("changed_files missing required branch ruleset witness refs" in error for error in implementation_errors)
    assert any(
        "documentation_changes missing required branch ruleset witness refs" in error
        for error in implementation_errors
    )
    assert any("coverage_refs missing required branch ruleset witness refs" in error for error in verification_errors)
    assert len(implementation_errors) + len(verification_errors) >= 3


def test_cli_json_receipt_reports_passed_contract() -> None:
    stdout_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer):
        exit_code = validator.main(["--json"])

    report = json.loads(stdout_buffer.getvalue())
    assert exit_code == 0
    assert report["receipt_id"] == "sdlc_artifact_validation_receipt"
    assert report["terminal_closure_required"] is True
    assert report["receipt_is_not_terminal_closure"] is True
    assert report["valid"] is True
    assert report["status"] == "passed"
    assert report["error_count"] == 0
    assert report["check_count"] == 11
    assert any(check["name"] == "sdlc_gate_decision_envelopes" for check in report["checks"])
    assert any(check["name"] == "sdlc_inventory_closure" for check in report["checks"])
    assert any(check["name"] == "sdlc_workspace_preflight_closure" for check in report["checks"])
    assert any(check["name"] == "sdlc_recovery_handoff_retention" for check in report["checks"])
    assert any(check["name"] == "sdlc_branch_ruleset_witness_closure" for check in report["checks"])


def test_cli_text_output_reports_all_receipt_checks() -> None:
    stdout_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer):
        exit_code = validator.main([])

    output = stdout_buffer.getvalue()
    assert exit_code == 0
    assert "[PASS] sdlc_workspace_preflight_closure" in output
    assert "[PASS] sdlc_recovery_handoff_retention" in output
    assert output.count("[PASS]") == validator.build_validation_report()["check_count"]
    assert output.endswith("STATUS: passed\n")


def test_load_json_object_rejects_non_object_json(tmp_path: Path) -> None:
    payload_path = tmp_path / "invalid-sdlc.json"
    payload_path.write_text(json.dumps(["not", "object"]), encoding="utf-8")

    with pytest.raises(ValueError):
        validator.load_json_object(payload_path, "payload")

    assert payload_path.exists()
    assert payload_path.suffix == ".json"
