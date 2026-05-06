#!/usr/bin/env python3
"""Validate the MIL audit runbook operator checklist artifact.

Purpose: keep MIL audit runbook promotion machine-readable and drift-checked.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: examples/mil_audit_runbook_operator_checklist.json.
Invariants:
  - The checklist has a stable schema version and checklist id.
  - Every required step has a command and evidence list.
  - Commands preserve the implemented MIL audit CLI surface.
  - Response and provenance witness fields are named explicitly.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_CHECKLIST = Path("examples") / "mil_audit_runbook_operator_checklist.json"
REQUIRED_ENVIRONMENT_VARIABLES = frozenset({
    "MULLU_MIL_AUDIT_STORE",
    "MULLU_MIL_TRACE_STORE",
    "MULLU_MIL_REPLAY_STORE",
    "MULLU_MIL_RUNBOOK_STORE",
    "MULLU_MIL_AUDIT_RECORD_ID",
    "MULLU_MIL_RUNBOOK_ID",
})
REQUIRED_STEP_IDS = frozenset({
    "inspect_mil_audit_record",
    "project_observation_replay",
    "admit_persisted_runbook",
    "read_persisted_runbook",
    "list_persisted_runbooks",
})
REQUIRED_RESPONSE_FIELDS = frozenset({
    "operation",
    "record_id",
    "program_id",
    "goal_id",
    "execution_id",
    "verification_passed",
    "replay_id",
    "trace_ids",
    "runbook_id",
    "runbook_status",
    "runbook_persisted",
    "provenance",
})
REQUIRED_PROVENANCE_FIELDS = frozenset({
    "execution_id",
    "verification_id",
    "replay_id",
    "trace_id",
    "learning_admission_id",
})
REQUIRED_BLOCKING_REASONS = frozenset({
    "MIL audit store unavailable",
    "MIL audit runbook admission rejected",
    "MIL audit runbook unavailable",
    "runbook_persisted=false",
})
REQUIRED_STEP_COMMAND_TOKENS = {
    "inspect_mil_audit_record": ("mcoi mil-audit get", "--store", "--json"),
    "project_observation_replay": ("mcoi mil-audit replay", "--store", "--json"),
    "admit_persisted_runbook": (
        "mcoi mil-audit admit-runbook",
        "--trace-store",
        "--replay-store",
        "--runbook-store",
        "--runbook-id",
        "--json",
    ),
    "read_persisted_runbook": ("mcoi mil-audit runbook-get", "--runbook-store", "--json"),
    "list_persisted_runbooks": ("mcoi mil-audit runbook-list", "--runbook-store", "--json"),
}
REQUIRED_STEP_EVIDENCE = {
    "inspect_mil_audit_record": frozenset({
        "operation=get",
        "record_id=$MULLU_MIL_AUDIT_RECORD_ID",
        "verification_passed=true",
        "program_id non-empty",
    }),
    "project_observation_replay": frozenset({
        "operation=replay",
        "replay_mode=observation_only",
        "trace_entries count>=6",
        "source_hash non-empty",
    }),
    "admit_persisted_runbook": frozenset({
        "operation=admit-runbook",
        "runbook_status=admitted",
        "runbook_persisted=true",
        "provenance.verification_id=$MULLU_MIL_AUDIT_RECORD_ID",
        "provenance.replay_id non-empty",
    }),
    "read_persisted_runbook": frozenset({
        "operation=runbook-get",
        "count=1",
        "runbooks[0].runbook_id=$MULLU_MIL_RUNBOOK_ID",
        "runbooks[0].provenance.verification_id=$MULLU_MIL_AUDIT_RECORD_ID",
    }),
    "list_persisted_runbooks": frozenset({
        "operation=runbook-list",
        "count>=1",
        "runbooks contains $MULLU_MIL_RUNBOOK_ID",
    }),
}


@dataclass(frozen=True, slots=True)
class MILAuditRunbookChecklistValidation:
    """Validation result for the MIL audit runbook checklist."""

    checklist_path: Path
    checklist_id: str
    valid: bool
    step_count: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready validation output."""
        return {
            "valid": self.valid,
            "checklist_path": str(self.checklist_path),
            "checklist_id": self.checklist_id,
            "step_count": self.step_count,
            "errors": list(self.errors),
        }


def validate_mil_audit_runbook_operator_checklist(
    checklist_path: Path = DEFAULT_CHECKLIST,
) -> MILAuditRunbookChecklistValidation:
    """Validate one MIL audit runbook operator checklist artifact."""
    errors: list[str] = []
    payload = _load_json_object(checklist_path, errors)
    checklist_id = str(payload.get("checklist_id", ""))
    steps = payload.get("required_commands", [])
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if checklist_id != "mil-audit-runbook-operator-v1":
        errors.append("checklist_id must be mil-audit-runbook-operator-v1")
    if payload.get("status") != "ready_for_handoff":
        errors.append("status must be ready_for_handoff")

    _require_superset(payload, "required_environment_variables", REQUIRED_ENVIRONMENT_VARIABLES, errors)
    _require_superset(payload, "required_response_fields", REQUIRED_RESPONSE_FIELDS, errors)
    _require_superset(payload, "required_provenance_fields", REQUIRED_PROVENANCE_FIELDS, errors)
    _require_superset(payload, "blocking_failure_codes", REQUIRED_BLOCKING_REASONS, errors)
    _validate_steps(steps, errors)
    return MILAuditRunbookChecklistValidation(
        checklist_path=checklist_path,
        checklist_id=checklist_id,
        valid=not errors,
        step_count=len(steps) if isinstance(steps, list) else 0,
        errors=tuple(errors),
    )


def _load_json_object(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        errors.append("checklist could not be read")
        return {}
    except json.JSONDecodeError:
        errors.append("checklist must be JSON")
        return {}
    if not isinstance(parsed, dict):
        errors.append("checklist root must be an object")
        return {}
    return parsed


def _require_superset(
    payload: dict[str, Any],
    field: str,
    required: frozenset[str],
    errors: list[str],
) -> None:
    observed = payload.get(field, [])
    if not isinstance(observed, list):
        errors.append(f"{field} must be a list")
        return
    observed_set = {str(item) for item in observed}
    missing = sorted(required - observed_set)
    if missing:
        errors.append(f"{field} missing {missing}")


def _validate_steps(steps: Any, errors: list[str]) -> None:
    if not isinstance(steps, list):
        errors.append("required_commands must be a list")
        return
    step_ids: set[str] = set()
    for step in steps:
        if not isinstance(step, dict):
            errors.append("required_commands entries must be objects")
            continue
        step_id = str(step.get("step_id", ""))
        if step_id in step_ids:
            errors.append(f"duplicate required_commands step_id {step_id}")
        step_ids.add(step_id)
        command = str(step.get("command", "")).strip()
        if not command:
            errors.append(f"{step_id or 'unnamed'} command is required")
        for token in REQUIRED_STEP_COMMAND_TOKENS.get(step_id, ()):
            if token not in command:
                errors.append(f"{step_id or 'unnamed'} command missing token {token}")
        evidence = step.get("required_evidence", [])
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{step_id or 'unnamed'} required_evidence must be a non-empty list")
            continue
        evidence_set = {str(item) for item in evidence}
        missing_evidence = sorted(REQUIRED_STEP_EVIDENCE.get(step_id, frozenset()) - evidence_set)
        if missing_evidence:
            errors.append(f"{step_id or 'unnamed'} required_evidence missing {missing_evidence}")
    missing_steps = sorted(REQUIRED_STEP_IDS - step_ids)
    if missing_steps:
        errors.append(f"required_commands missing steps {missing_steps}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse MIL audit runbook checklist validation CLI arguments."""
    parser = argparse.ArgumentParser(description="Validate MIL audit runbook operator checklist.")
    parser.add_argument("--checklist", default=str(DEFAULT_CHECKLIST))
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON validation output.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for MIL audit runbook checklist validation."""
    args = parse_args(argv)
    result = validate_mil_audit_runbook_operator_checklist(Path(args.checklist))
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"mil audit runbook operator checklist ok steps={result.step_count}")
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
