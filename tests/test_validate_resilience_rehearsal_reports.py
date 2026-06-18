"""Purpose: verify umbrella resilience rehearsal report validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_resilience_rehearsal_reports and SDLC validators.
Invariants:
  - Split chaos and invariant fuzz validators remain canonical.
  - The umbrella validator grants no live runtime, deployment, write, terminal,
    or success authority.
  - Umbrella SDLC artifacts remain valid evidence, not execution authority.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_resilience_rehearsal_reports as validator


def test_resilience_rehearsal_reports_delegate_to_split_validators() -> None:
    errors = validator.validate_resilience_rehearsal_reports()
    chaos = validator.load_json_object(validator.CHAOS_REPORT_PATH, "ChaosRehearsalExecutionReport")
    fuzz = validator.load_json_object(validator.FUZZ_REPORT_PATH, "InvariantFuzzExecutionReport")

    assert errors == []
    assert chaos["report_version"] == validator.EXPECTED_CHAOS_VERSION
    assert chaos["execution_mode"]["mode"] == "deterministic_dry_run"
    assert chaos["authority_boundary"]["runtime_disruption_performed"] is False
    assert fuzz["report_version"] == validator.EXPECTED_FUZZ_VERSION
    assert fuzz["harness_mode"]["mode"] == "deterministic_dry_run"
    assert fuzz["authority_boundary"]["canonical_state_mutation_performed"] is False
    assert validator.validate_chaos_rehearsal_execution_report_record(chaos) == []
    assert validator.validate_invariant_fuzz_execution_report_record(fuzz) == []


def test_resilience_umbrella_surfaces_chaos_authority_drift() -> None:
    mutated = validator.build_mutated_chaos_rehearsal_execution_report(
        authority_boundary__live_chaos_execution_performed=True,
        authority_boundary__production_target_touched=True,
        authority_boundary__runtime_disruption_performed=True,
        authority_boundary__event_chain_mutation_performed=True,
        authority_boundary__terminal_closure_allowed=True,
        authority_boundary__success_claim_allowed=True,
    )

    errors = validator.validate_chaos_rehearsal_execution_report_record(mutated)

    assert any("authority_boundary.live_chaos_execution_performed" in error for error in errors)
    assert any("authority_boundary.production_target_touched" in error for error in errors)
    assert any("authority_boundary.runtime_disruption_performed" in error for error in errors)
    assert any("authority_boundary.event_chain_mutation_performed" in error for error in errors)
    assert any("authority_boundary.terminal_closure_allowed" in error for error in errors)
    assert any("authority_boundary.success_claim_allowed" in error for error in errors)


def test_resilience_umbrella_surfaces_invariant_fuzz_authority_drift() -> None:
    mutated = validator.build_mutated_invariant_fuzz_execution_report(
        authority_boundary__live_runtime_execution_performed=True,
        authority_boundary__production_target_touched=True,
        authority_boundary__canonical_state_mutation_performed=True,
        authority_boundary__event_chain_mutation_performed=True,
        authority_boundary__filesystem_write_performed=True,
        authority_boundary__terminal_closure_allowed=True,
    )

    errors = validator.validate_invariant_fuzz_execution_report_record(mutated)

    assert any("authority_boundary.live_runtime_execution_performed" in error for error in errors)
    assert any("authority_boundary.production_target_touched" in error for error in errors)
    assert any("authority_boundary.canonical_state_mutation_performed" in error for error in errors)
    assert any("authority_boundary.event_chain_mutation_performed" in error for error in errors)
    assert any("authority_boundary.filesystem_write_performed" in error for error in errors)
    assert any("authority_boundary.terminal_closure_allowed" in error for error in errors)


def test_resilience_sdlc_artifacts_validate() -> None:
    errors = validator.validate_resilience_sdlc_artifacts()
    paths = [path for _, path, _ in validator.SDLC_ARTIFACTS]
    loaded_records = [validator.load_json_object(path, path.name) for path in paths]

    assert errors == []
    assert Path("examples/sdlc/requirement_resilience_rehearsal_reports_20260616.json") in [
        path.relative_to(validator.WORKSPACE_ROOT) for path in paths
    ]
    assert loaded_records[0]["requirement_id"] == "REQ-resilience-rehearsal-reports-20260616"
    assert loaded_records[1]["requirement_id"] == loaded_records[0]["requirement_id"]
    assert loaded_records[2]["security_review_id"] == "SEC-resilience-rehearsal-reports-20260616"
    assert loaded_records[2]["release_blocked"] is False


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--chaos-schema",
            "schemas/chaos_rehearsal_execution_report.schema.json",
            "--chaos-report",
            "examples/chaos_rehearsal_execution_report.foundation.json",
            "--fuzz-schema",
            "schemas/invariant_fuzz_execution_report.schema.json",
            "--fuzz-report",
            "examples/invariant_fuzz_execution_report.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["chaos_schema_path"]).as_posix() == "schemas/chaos_rehearsal_execution_report.schema.json"
    assert Path(payload["fuzz_schema_path"]).as_posix() == "schemas/invariant_fuzz_execution_report.schema.json"
    assert payload["sdlc_artifact_paths"] == [
        "examples/sdlc/requirement_resilience_rehearsal_reports_20260616.json",
        "examples/sdlc/design_resilience_rehearsal_reports_20260616.json",
        "examples/sdlc/security_review_resilience_rehearsal_reports_20260616.json",
    ]
    assert payload["errors"] == []


def test_cli_json_can_skip_sdlc(capsys) -> None:
    exit_code = validator.main(["--skip-sdlc", "--json"])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["errors"] == []
    assert payload["chaos_report_path"] == "examples/chaos_rehearsal_execution_report.foundation.json"
    assert payload["fuzz_report_path"] == "examples/invariant_fuzz_execution_report.foundation.json"
