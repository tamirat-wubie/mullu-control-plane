#!/usr/bin/env python3
"""Validate the umbrella resilience rehearsal report contract.

Purpose: bind ChaosRehearsalExecutionReport and InvariantFuzzExecutionReport
validation into one read-only resilience rehearsal witness.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, split report validators, SDLC artifact
validators, and SDLC security review validators.
Invariants:
  - Validation is deterministic and read-only.
  - Split chaos and invariant fuzz contracts remain canonical.
  - The umbrella contract grants no runtime, deployment, filesystem, connector,
    terminal-closure, or success authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts import validate_chaos_rehearsal_execution_report as chaos_validator  # noqa: E402
from scripts import validate_invariant_fuzz_execution_report as fuzz_validator  # noqa: E402
from scripts.validate_sdlc_artifact import load_json_object as load_sdlc_json_object  # noqa: E402
from scripts.validate_sdlc_artifact import validate_artifact_record  # noqa: E402
from scripts.validate_sdlc_security_review import (  # noqa: E402
    validate_required_security_checks,
    validate_security_review_record,
)


CHAOS_SCHEMA_PATH = chaos_validator.DEFAULT_SCHEMA_PATH
CHAOS_REPORT_PATH = chaos_validator.DEFAULT_REPORT_PATH
FUZZ_SCHEMA_PATH = fuzz_validator.DEFAULT_SCHEMA_PATH
FUZZ_REPORT_PATH = fuzz_validator.DEFAULT_REPORT_PATH
EXPECTED_CHAOS_VERSION = chaos_validator.EXPECTED_REPORT_VERSION
EXPECTED_FUZZ_VERSION = fuzz_validator.EXPECTED_REPORT_VERSION

SDLC_ARTIFACTS: tuple[tuple[str, Path, str], ...] = (
    (
        "requirement",
        WORKSPACE_ROOT / "examples" / "sdlc" / "requirement_resilience_rehearsal_reports_20260616.json",
        "resilience rehearsal reports requirement",
    ),
    (
        "design_decision",
        WORKSPACE_ROOT / "examples" / "sdlc" / "design_resilience_rehearsal_reports_20260616.json",
        "resilience rehearsal reports design",
    ),
    (
        "security_review",
        WORKSPACE_ROOT / "examples" / "sdlc" / "security_review_resilience_rehearsal_reports_20260616.json",
        "resilience rehearsal reports security review",
    ),
)


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk using the canonical split loader."""

    path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if path.name == CHAOS_REPORT_PATH.name:
        return chaos_validator.load_json_object(path, label)
    if path.name == FUZZ_REPORT_PATH.name:
        return fuzz_validator.load_json_object(path, label)
    return load_sdlc_json_object(path, label)


def validate_chaos_rehearsal_execution_report_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Validate one chaos rehearsal report through the canonical validator."""

    return chaos_validator.validate_chaos_rehearsal_execution_report_record(record, schema)


def validate_invariant_fuzz_execution_report_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Validate one invariant fuzz execution report through the canonical validator."""

    return fuzz_validator.validate_invariant_fuzz_execution_report_record(record, schema)


def build_mutated_chaos_rehearsal_execution_report(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the canonical chaos report."""

    return chaos_validator.build_mutated_chaos_rehearsal_execution_report(**updates)


def build_mutated_invariant_fuzz_execution_report(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the canonical invariant fuzz report."""

    return fuzz_validator.build_mutated_invariant_fuzz_execution_report(**updates)


def validate_resilience_rehearsal_reports(
    chaos_schema_path: Path = CHAOS_SCHEMA_PATH,
    chaos_report_path: Path = CHAOS_REPORT_PATH,
    fuzz_schema_path: Path = FUZZ_SCHEMA_PATH,
    fuzz_report_path: Path = FUZZ_REPORT_PATH,
) -> list[str]:
    """Validate the canonical split resilience rehearsal report pair."""

    errors: list[str] = []
    errors.extend(
        _prefix_errors(
            "chaos_rehearsal_execution_report",
            chaos_validator.validate_chaos_rehearsal_execution_report(
                chaos_schema_path,
                chaos_report_path,
            ),
        )
    )
    errors.extend(
        _prefix_errors(
            "invariant_fuzz_execution_report",
            fuzz_validator.validate_invariant_fuzz_execution_report(
                fuzz_schema_path,
                fuzz_report_path,
            ),
        )
    )
    return errors


def validate_resilience_sdlc_artifacts() -> list[str]:
    """Validate the umbrella SDLC evidence artifacts."""

    errors: list[str] = []
    for artifact_kind, artifact_path, artifact_label in SDLC_ARTIFACTS:
        record = load_sdlc_json_object(artifact_path, artifact_label)
        artifact_errors = validate_artifact_record(artifact_kind, record)
        if artifact_kind == "security_review":
            artifact_errors.extend(validate_security_review_record(record, strict=True))
            artifact_errors.extend(validate_required_security_checks(record, strict=True))
        errors.extend(_prefix_errors(artifact_label, artifact_errors))
    return errors


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative display path when possible."""

    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return resolved_path.resolve().relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _prefix_errors(label: str, errors: list[str]) -> list[str]:
    return [f"{label}: {error}" for error in errors]


def main(argv: list[str] | None = None) -> int:
    """Validate umbrella resilience rehearsal report evidence from the CLI."""

    parser = argparse.ArgumentParser(description="Validate resilience rehearsal report evidence.")
    parser.add_argument("--chaos-schema", type=Path, default=CHAOS_SCHEMA_PATH)
    parser.add_argument("--chaos-report", type=Path, default=CHAOS_REPORT_PATH)
    parser.add_argument("--fuzz-schema", type=Path, default=FUZZ_SCHEMA_PATH)
    parser.add_argument("--fuzz-report", type=Path, default=FUZZ_REPORT_PATH)
    parser.add_argument("--skip-sdlc", action="store_true", help="skip umbrella SDLC artifact validation")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    errors = validate_resilience_rehearsal_reports(
        args.chaos_schema,
        args.chaos_report,
        args.fuzz_schema,
        args.fuzz_report,
    )
    if not args.skip_sdlc:
        errors.extend(validate_resilience_sdlc_artifacts())

    if args.json:
        payload = {
            "receipt_id": "resilience_rehearsal_reports_validation",
            "status": "passed" if not errors else "failed",
            "chaos_schema_path": workspace_display_path(args.chaos_schema),
            "chaos_report_path": workspace_display_path(args.chaos_report),
            "fuzz_schema_path": workspace_display_path(args.fuzz_schema),
            "fuzz_report_path": workspace_display_path(args.fuzz_report),
            "sdlc_artifact_paths": [workspace_display_path(path) for _, path, _ in SDLC_ARTIFACTS],
            "errors": errors,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif errors:
        for error in errors:
            print(f"[FAIL] {error}")
    else:
        print("[PASS] resilience_rehearsal_reports")
        print("STATUS: passed")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
