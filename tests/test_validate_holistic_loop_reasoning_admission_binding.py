"""Purpose: verify holistic loop reasoning admission binding validation.
Governance scope: read-only admission, runtime authority denial, evidence
requirements, source digest anchoring, SDLC sidecar links, and CLI behavior.
Dependencies: scripts.validate_holistic_loop_reasoning_admission_binding.
Invariants:
  - Runtime reasoning authority remains denied.
  - Required runtime promotion evidence remains unsatisfied.
  - Source artifact digests and contract counts cannot drift silently.
  - SDLC sidecars validate and remain linked.
"""

from __future__ import annotations

import copy
import json

from scripts import validate_holistic_loop_reasoning_admission_binding as validator


def _load_valid_binding() -> dict[str, object]:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    binding = validator.load_json_object(
        validator.DEFAULT_FIXTURE_PATH,
        "holistic loop reasoning admission binding",
    )
    assert validator.validate_binding_payload(binding, schema) == []
    return binding


def test_holistic_loop_reasoning_admission_binding_passes() -> None:
    report = validator.validation_report()
    binding = _load_valid_binding()

    assert report["valid"] is True
    assert report["status"] == "passed"
    assert binding["solver_outcome"] == "AwaitingEvidence"
    assert binding["contract_summary"]["runtime_claim_count"] == 0


def test_holistic_loop_reasoning_admission_rejects_authority_drift() -> None:
    binding = _load_valid_binding()
    invalid_binding = copy.deepcopy(binding)
    denied_authority = invalid_binding["authority_boundary"]["denied_authority"]
    denied_authority[0]["allowed"] = True

    errors = validator.validate_authority_denials(invalid_binding)

    assert "runtime_reasoning_allowed must remain denied" in errors
    assert denied_authority[0]["allowed"] is True
    assert denied_authority[0]["authority_id"] == "runtime_reasoning_allowed"


def test_holistic_loop_reasoning_admission_rejects_scope_and_evidence_drift() -> None:
    binding = _load_valid_binding()
    invalid_binding = copy.deepcopy(binding)
    invalid_binding["solver_outcome"] = "SolvedVerified"
    invalid_binding["admission_scope"]["runtime_reasoning_claimed"] = True
    invalid_binding["runtime_promotion_blockers"] = invalid_binding["runtime_promotion_blockers"][1:]

    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    errors = validator.validate_binding_payload(invalid_binding, schema)

    assert "solver_outcome must remain AwaitingEvidence" in errors
    assert "admission_scope.runtime_reasoning_claimed must be false" in errors
    assert "runtime_promotion_blockers must match required runtime promotion evidence" in errors


def test_holistic_loop_reasoning_admission_rejects_receipt_and_gap_drift() -> None:
    binding = _load_valid_binding()
    invalid_binding = copy.deepcopy(binding)
    invalid_binding["admission_requirements"][0]["satisfied"] = True
    invalid_binding["admission_requirements"][0]["execution_allowed"] = True
    invalid_binding["contract_summary"]["satisfied_runtime_requirement_count"] = 0

    errors = validator.validate_runtime_promotion_requirements(invalid_binding)
    summary_errors = validator.validate_contract_summary(invalid_binding)

    assert "evidence://wholistic-reasoning/uao-admission execution_allowed must be false" in errors
    assert "evidence://wholistic-reasoning/uao-admission satisfied must remain false" in errors
    assert "contract_summary.satisfied_runtime_requirement_count must be 1" in summary_errors


def test_holistic_loop_reasoning_admission_rejects_digest_and_summary_drift() -> None:
    binding = _load_valid_binding()
    invalid_binding = copy.deepcopy(binding)
    invalid_binding["source_artifacts"][0]["sha256"] = "0" * 64
    invalid_binding["contract_summary"]["source_artifact_count"] = 0

    digest_errors = validator.validate_source_artifacts(invalid_binding)
    summary_errors = validator.validate_contract_summary(invalid_binding)

    assert "source artifact digest map must match expected source artifacts" in digest_errors
    assert "contract_summary.source_artifact_count must be 13" in summary_errors
    assert invalid_binding["source_artifacts"][0]["path"] == "docs/reasoning/MULLU_REASONING_INTEGRITY_MESH.md"


def test_holistic_loop_reasoning_admission_rejects_requirement_drift() -> None:
    binding = _load_valid_binding()
    invalid_binding = copy.deepcopy(binding)
    invalid_binding["admission_requirements"].reverse()

    errors = validator.validate_runtime_promotion_requirements(invalid_binding)

    assert "admission_requirements must match required runtime promotion evidence" in errors
    assert invalid_binding["admission_requirements"][0]["requirement_ref"] == (
        "evidence://wholistic-reasoning/terminal-closure-review"
    )
    assert len(invalid_binding["admission_requirements"]) == 6


def test_sdlc_requirement_design_and_security_validate_for_holistic_loop_reasoning_admission() -> None:
    errors = validator.validate_sdlc_sidecars()
    requirement = validator.load_json_object(
        validator.REQUIREMENT_PATH,
        "holistic loop reasoning requirement",
    )
    design = validator.load_json_object(
        validator.DESIGN_PATH,
        "holistic loop reasoning design",
    )
    security = validator.load_json_object(
        validator.SECURITY_REVIEW_PATH,
        "holistic loop reasoning security review",
    )

    assert errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert security["release_blocked"] is False
    assert security["receipt_ref"] in security["security_receipts"]


def test_cli_passes(capsys) -> None:
    exit_code = validator.main([])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[PASS] holistic_loop_reasoning_admission_binding_schema_valid" in captured.out
    assert "STATUS: passed" in captured.out


def test_cli_blocks_invalid_binding_fixture(tmp_path, capsys) -> None:
    binding = _load_valid_binding()
    invalid_binding = copy.deepcopy(binding)
    invalid_binding["solver_outcome"] = "SolvedVerified"
    fixture_path = tmp_path / "holistic_loop_reasoning_admission_binding.json"
    fixture_path.write_text(json.dumps(invalid_binding, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    exit_code = validator.main(["--fixture", str(fixture_path)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "solver_outcome must remain AwaitingEvidence" in captured.err
    assert "STATUS: blocked" in captured.err
