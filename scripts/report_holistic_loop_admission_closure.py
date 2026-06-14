#!/usr/bin/env python3
"""Report holistic loop admission closure readiness.

Purpose: expose a read-only admission-closure summary for the holistic loop
kernel after candidate loop surfaces have been admitted into the default
registry.
Governance scope: default loop registry count, candidate admission state,
extension admission validation, proof witness integrity, and terminal-closure
separation.
Dependencies: holistic loop read model, candidate map reporter, extension
admission validator, and proof coverage matrix.
Invariants:
  - The report is read-only and deterministic.
  - The report does not register loops or execute loop behavior.
  - The report does not mutate proof, candidate, or registry state.
  - The report is not a terminal closure certificate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, TextIO


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
MCOI_ROOT = WORKSPACE_ROOT / "mcoi"
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from scripts.proof_coverage_matrix import (  # noqa: E402
    proof_coverage_matrix,
    witness_integrity_report,
)
from scripts.report_holistic_loop_candidate_map import (  # noqa: E402
    build_candidate_map,
    validate_candidate_map,
)
from scripts.report_holistic_loop_read_model import build_report  # noqa: E402
from scripts.validate_holistic_loop_extension_admission import (  # noqa: E402
    HOLISTIC_SURFACE_ID,
    REQUIRED_LOOP_IDS,
    validate_extension_admission,
)


REPORT_ID = "holistic_loop_admission_closure_report"
REPORT_VERSION = "holistic_loop_admission_closure_report.v1"


def _holistic_witness_integrity(matrix: dict[str, Any]) -> dict[str, Any]:
    """Return the witness integrity record for the holistic loop surface."""

    integrity = witness_integrity_report(matrix.get("surfaces", []))
    for record in integrity.get("surfaces", []):
        if isinstance(record, dict) and record.get("surface_id") == HOLISTIC_SURFACE_ID:
            return record
    return {
        "surface_id": HOLISTIC_SURFACE_ID,
        "runtime_witness_count": 0,
        "exact_test_anchor_count": 0,
        "unanchored_witness_count": 1,
        "unanchored_witnesses": [HOLISTIC_SURFACE_ID],
    }


def build_admission_closure_report() -> dict[str, Any]:
    """Build the non-terminal admission closure report."""

    read_model = build_report()
    candidate_map = build_candidate_map()
    matrix = proof_coverage_matrix()
    witness_record = _holistic_witness_integrity(matrix)
    registered_loop_ids = sorted(str(loop["loop_id"]) for loop in read_model["loops"])
    candidate_ids = sorted(str(candidate["candidate_id"]) for candidate in candidate_map["candidates"])
    pending_candidate_ids = sorted(
        str(candidate["candidate_id"])
        for candidate in candidate_map["candidates"]
        if candidate.get("admission_status") != "registered"
    )
    unregistered_candidate_ids = sorted(
        str(candidate["candidate_id"])
        for candidate in candidate_map["candidates"]
        if candidate.get("registered") is not True
    )
    candidate_errors = validate_candidate_map(candidate_map)
    extension_errors = validate_extension_admission(report=read_model, matrix=matrix)
    closure_conditions = {
        "all_expected_loops_registered": set(REQUIRED_LOOP_IDS).issubset(set(registered_loop_ids)),
        "candidate_map_verified": candidate_map.get("status") == "verified" and not candidate_errors,
        "no_pending_candidate_admissions": not pending_candidate_ids and not unregistered_candidate_ids,
        "extension_admission_valid": not extension_errors,
        "holistic_proof_labels_anchored": witness_record.get("unanchored_witness_count") == 0,
        "read_model_report_not_terminal_closure": (
            read_model.get("report_is_not_terminal_closure") is True
            and read_model.get("terminal_closure_required") is True
        ),
        "candidate_map_not_terminal_closure": (
            candidate_map.get("report_is_not_terminal_closure") is True
            and candidate_map.get("terminal_closure_required") is True
        ),
    }
    closure_blockers = [
        f"closure_condition_failed:{name}"
        for name, passed in closure_conditions.items()
        if not passed
    ]
    closure_blockers.extend(f"candidate_map:{error}" for error in candidate_errors)
    closure_blockers.extend(f"extension_admission:{error}" for error in extension_errors)
    report_status = "verified" if not closure_blockers else "blocked"
    return {
        "report_id": REPORT_ID,
        "report_version": REPORT_VERSION,
        "status": report_status,
        "read_only": True,
        "mutation_route": False,
        "runtime_behavior_change": False,
        "report_is_not_terminal_closure": True,
        "terminal_closure_required": True,
        "admission_closure_verified": report_status == "verified",
        "terminal_closure": False,
        "loop_count": read_model["loop_count"],
        "required_loop_count": len(REQUIRED_LOOP_IDS),
        "registered_loop_ids": registered_loop_ids,
        "candidate_count": candidate_map["candidate_count"],
        "registered_candidate_count": candidate_map["registered_candidate_count"],
        "blocked_candidate_count": candidate_map["blocked_candidate_count"],
        "candidate_ids": candidate_ids,
        "pending_candidate_ids": pending_candidate_ids,
        "unregistered_candidate_ids": unregistered_candidate_ids,
        "proof_surface_id": HOLISTIC_SURFACE_ID,
        "proof_witness_integrity": {
            "runtime_witness_count": witness_record.get("runtime_witness_count"),
            "exact_test_anchor_count": witness_record.get("exact_test_anchor_count"),
            "unanchored_witness_count": witness_record.get("unanchored_witness_count"),
            "unanchored_witnesses": witness_record.get("unanchored_witnesses", []),
        },
        "closure_conditions": closure_conditions,
        "closure_blockers": closure_blockers,
        "next_action": (
            "maintain_kernel_v1_freeze"
            if report_status == "verified"
            else "resolve_admission_closure_blockers"
        ),
    }


def validate_admission_closure_report(report: dict[str, Any] | None = None) -> list[str]:
    """Return validation errors for the admission closure report."""

    current_report = report or build_admission_closure_report()
    errors: list[str] = []
    if current_report.get("report_id") != REPORT_ID:
        errors.append("admission closure report_id is invalid")
    if current_report.get("report_version") != REPORT_VERSION:
        errors.append("admission closure report_version is invalid")
    for field_name, expected in (
        ("read_only", True),
        ("mutation_route", False),
        ("runtime_behavior_change", False),
        ("report_is_not_terminal_closure", True),
        ("terminal_closure_required", True),
        ("terminal_closure", False),
    ):
        if current_report.get(field_name) is not expected:
            errors.append(f"admission closure {field_name} must be {expected}")
    registered_loop_ids = current_report.get("registered_loop_ids")
    if not isinstance(registered_loop_ids, list) or not registered_loop_ids:
        errors.append("registered_loop_ids must be a non-empty list")
    else:
        if registered_loop_ids != sorted(registered_loop_ids):
            errors.append("registered_loop_ids must be deterministic and sorted")
        missing_required = sorted(set(REQUIRED_LOOP_IDS) - set(registered_loop_ids))
        if missing_required:
            errors.append("registered_loop_ids missing required loops: " + ", ".join(missing_required))
        if current_report.get("loop_count") != len(registered_loop_ids):
            errors.append("loop_count must match registered_loop_ids")
        if current_report.get("required_loop_count") != len(REQUIRED_LOOP_IDS):
            errors.append("required_loop_count must match required loop ids")
    candidate_ids = current_report.get("candidate_ids")
    if not isinstance(candidate_ids, list) or not candidate_ids:
        errors.append("candidate_ids must be a non-empty list")
    elif current_report.get("candidate_count") != len(candidate_ids):
        errors.append("candidate_count must match candidate_ids")
    if current_report.get("blocked_candidate_count") != 0:
        errors.append("blocked_candidate_count must remain zero after admission")
    if current_report.get("pending_candidate_ids") != []:
        errors.append("pending_candidate_ids must be empty after admission")
    if current_report.get("unregistered_candidate_ids") != []:
        errors.append("unregistered_candidate_ids must be empty after admission")
    witness = current_report.get("proof_witness_integrity")
    if not isinstance(witness, dict):
        errors.append("proof_witness_integrity must be present")
    elif witness.get("unanchored_witness_count") != 0:
        errors.append("proof_witness_integrity must have zero unanchored witnesses")
    closure_conditions = current_report.get("closure_conditions")
    if not isinstance(closure_conditions, dict) or not closure_conditions:
        errors.append("closure_conditions must be present")
    else:
        for name, passed in closure_conditions.items():
            if passed is not True:
                errors.append(f"closure condition must pass: {name}")
    closure_blockers = current_report.get("closure_blockers")
    if not isinstance(closure_blockers, list):
        errors.append("closure_blockers must be a list")
    elif closure_blockers:
        errors.append("closure_blockers must be empty after admission")
    expected_status = "verified" if not closure_blockers else "blocked"
    if current_report.get("status") != expected_status:
        errors.append("status must match closure blockers")
    if current_report.get("admission_closure_verified") is not (expected_status == "verified"):
        errors.append("admission_closure_verified must match status")
    if expected_status == "verified" and current_report.get("next_action") != "maintain_kernel_v1_freeze":
        errors.append("next_action must maintain kernel v1 freeze after admission")
    return errors


def render_admission_closure_report(report: dict[str, Any], output_stream: TextIO) -> None:
    """Render a short admission closure summary."""

    output_stream.write(
        "STATUS: {status}; loops={loop_count}; candidates={candidate_count}; "
        "blocked_candidates={blocked_candidate_count}; unanchored={unanchored}\n".format(
            status=report["status"],
            loop_count=report["loop_count"],
            candidate_count=report["candidate_count"],
            blocked_candidate_count=report["blocked_candidate_count"],
            unanchored=report["proof_witness_integrity"]["unanchored_witness_count"],
        )
    )
    output_stream.write(f"NEXT: {report['next_action']}\n")


def main(argv: list[str] | None = None) -> int:
    """Report and validate holistic loop admission closure readiness."""

    parser = argparse.ArgumentParser(description="Report holistic loop admission closure readiness.")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    report = build_admission_closure_report()
    errors = validate_admission_closure_report(report)
    if errors:
        for error in errors:
            sys.stderr.write(f"[BLOCKED] holistic-loop-admission-closure: {error}\n")
        sys.stderr.write("STATUS: blocked\n")
        return 1
    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    else:
        render_admission_closure_report(report, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
