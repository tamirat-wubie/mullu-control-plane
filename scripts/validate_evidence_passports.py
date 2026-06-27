#!/usr/bin/env python3
"""Validate evidence passports.

Purpose: prove every capability has a standardized proof packet covering
evidence, approval, blocked actions, replay, rollback, and continuation safety.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/evidence_passports.schema.json,
examples/evidence_passports.foundation.json, capability passports, and gate
template registry.
Invariants:
  - Every capability passport has exactly one evidence passport.
  - Evidence passports are read models and never execution authority.
  - Missing proof, approval, replay, rollback, and blocked actions are explicit.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from mcoi_runtime.app.capability_passports import build_capability_passports  # noqa: E402
from mcoi_runtime.app.evidence_passports import build_evidence_passports  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "evidence_passports.schema.json"
DEFAULT_EVIDENCE_PASSPORTS = REPO_ROOT / "examples" / "evidence_passports.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "evidence_passports_validation.json"

REQUIRED_VALIDATOR_COMMANDS = {
    "evidence_passports_validator": "python scripts/validate_evidence_passports.py",
    "evidence_passports_tests": "python -m pytest tests/test_validate_evidence_passports.py -q",
}


@dataclass(frozen=True, slots=True)
class EvidencePassportValidation:
    """Validation report for evidence passports."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    evidence_passports_path: str
    evidence_passport_count: int
    capability_count: int
    missing_evidence_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_evidence_passports(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    evidence_passports_path: Path = DEFAULT_EVIDENCE_PASSPORTS,
) -> EvidencePassportValidation:
    """Validate evidence passports against schema and runtime projections."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "evidence passports schema", errors)
    evidence_passports = _load_json_object(evidence_passports_path, "evidence passports example", errors)
    runtime_evidence_passports = build_evidence_passports() if not errors else {}
    runtime_passports = build_capability_passports() if not errors else {}

    if schema and evidence_passports:
        errors.extend(
            f"{_path_label(evidence_passports_path)}: {error}"
            for error in _validate_schema_instance(schema, evidence_passports)
        )
        if evidence_passports != runtime_evidence_passports:
            errors.append(f"{_path_label(evidence_passports_path)}: example does not match runtime projection")
    if evidence_passports:
        _validate_evidence_passport_set(evidence_passports, runtime_passports, errors, _path_label(evidence_passports_path))

    summary = evidence_passports.get("summary", {}) if isinstance(evidence_passports, dict) else {}
    entries = evidence_passports.get("evidence_passports", ()) if isinstance(evidence_passports, dict) else ()
    runtime_entries = runtime_passports.get("passports", ()) if isinstance(runtime_passports, dict) else ()
    return EvidencePassportValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        evidence_passports_path=_path_label(evidence_passports_path),
        evidence_passport_count=len(entries) if isinstance(entries, list) else 0,
        capability_count=len(runtime_entries) if isinstance(runtime_entries, list) else 0,
        missing_evidence_count=int(summary.get("missing_evidence_count", 0)) if isinstance(summary, dict) else 0,
    )


def write_evidence_passport_validation(
    validation: EvidencePassportValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic evidence passport validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_evidence_passport_set(
    evidence_passports: dict[str, Any],
    runtime_passports: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if evidence_passports.get("evidence_passport_set_is_not_execution_authority") is not True:
        errors.append(f"{label}: evidence_passport_set_is_not_execution_authority must be true")
    if evidence_passports.get("live_execution_enabled") is not False:
        errors.append(f"{label}: live_execution_enabled must be false")
    _validate_validators(evidence_passports, errors, label)

    evidence_entries = _list_of_objects(evidence_passports.get("evidence_passports"))
    passport_entries = _list_of_objects(runtime_passports.get("passports"))
    evidence_by_capability: dict[str, dict[str, Any]] = {}
    for evidence_passport in evidence_entries:
        capability_id = str(evidence_passport.get("capability_id", ""))
        if capability_id in evidence_by_capability:
            errors.append(f"{label}: duplicate evidence passport for {capability_id}")
        evidence_by_capability[capability_id] = evidence_passport
        _validate_evidence_passport(evidence_passport, errors, label)

    passport_ids = {str(passport.get("capability_id", "")) for passport in passport_entries}
    evidence_ids = set(evidence_by_capability)
    missing = sorted(passport_ids - evidence_ids)
    extra = sorted(evidence_ids - passport_ids)
    if missing:
        errors.append(f"{label}: registered capabilities missing evidence passports {missing}")
    if extra:
        errors.append(f"{label}: evidence passports for unknown capabilities {extra}")

    summary = evidence_passports.get("summary")
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return
    if summary.get("capability_count") != len(passport_entries):
        errors.append(f"{label}: summary.capability_count must match runtime capabilities")
    if summary.get("evidence_passport_count") != len(evidence_entries):
        errors.append(f"{label}: summary.evidence_passport_count must match evidence passports")
    if summary.get("missing_evidence_count") != sum(1 for passport in evidence_entries if passport.get("missing_evidence")):
        errors.append(f"{label}: summary.missing_evidence_count must match evidence passports")
    if summary.get("approval_required_count") != sum(
        1 for passport in evidence_entries if _mapping(passport.get("approval")).get("approval_required") is True
    ):
        errors.append(f"{label}: summary.approval_required_count must match evidence passports")
    if summary.get("safe_for_live_action_count") != sum(
        1 for passport in evidence_entries if _mapping(passport.get("continuation")).get("safe_for_live_action") is True
    ):
        errors.append(f"{label}: summary.safe_for_live_action_count must match evidence passports")


def _validate_evidence_passport(
    evidence_passport: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    capability_id = str(evidence_passport.get("capability_id", "<missing>"))
    if evidence_passport.get("evidence_passport_is_not_execution_authority") is not True:
        errors.append(f"{label}: {capability_id} evidence_passport_is_not_execution_authority must be true")

    evidence_exists = _mapping(evidence_passport.get("evidence_exists"))
    present_refs = _string_list(evidence_exists.get("present_evidence_refs"))
    if evidence_exists.get("present_evidence_count") != len(present_refs):
        errors.append(f"{label}: {capability_id} present_evidence_count must match refs")

    required_evidence = _string_list(evidence_passport.get("required_evidence"))
    missing_evidence = _string_list(evidence_passport.get("missing_evidence"))
    if not required_evidence:
        errors.append(f"{label}: {capability_id} required_evidence must be non-empty")
    outcome = evidence_passport.get("outcome")
    proof_state = evidence_passport.get("proof_state")
    if missing_evidence and outcome != "AwaitingEvidence":
        errors.append(f"{label}: {capability_id} missing evidence must produce AwaitingEvidence")
    if outcome == "SolvedVerified" and proof_state != "Pass":
        errors.append(f"{label}: {capability_id} SolvedVerified must have Pass proof state")
    if outcome == "GovernanceBlocked" and proof_state != "Fail":
        errors.append(f"{label}: {capability_id} GovernanceBlocked must have Fail proof state")

    approval = _mapping(evidence_passport.get("approval"))
    if approval.get("approval_required") is True and approval.get("missing_approval") is not True:
        errors.append(f"{label}: {capability_id} required approval must be marked missing in foundation mode")
    if approval.get("approval_required") is False and approval.get("approval_state") != "not_required":
        errors.append(f"{label}: {capability_id} non-required approval must have not_required state")
    if approval.get("approved") is not False:
        errors.append(f"{label}: {capability_id} approved must remain false in foundation projection")

    blocked = _mapping(evidence_passport.get("blocked"))
    blocked_actions = _string_list(blocked.get("blocked_actions"))
    if blocked.get("blocked_action_count") != len(blocked_actions):
        errors.append(f"{label}: {capability_id} blocked_action_count must match blocked actions")

    replay = _mapping(evidence_passport.get("replay"))
    if replay.get("replay_required") is True and not replay.get("replay_refs") and replay.get("missing_replay_evidence") is not True:
        errors.append(f"{label}: {capability_id} missing replay refs must mark missing_replay_evidence")
    if replay.get("replayable") is True and replay.get("missing_replay_evidence") is True:
        errors.append(f"{label}: {capability_id} replayable cannot have missing replay evidence")

    rollback = _mapping(evidence_passport.get("rollback"))
    if rollback.get("rollback_status") == "missing" and rollback.get("rollback_or_compensation_available") is True:
        errors.append(f"{label}: {capability_id} missing rollback cannot be available")

    continuation = _mapping(evidence_passport.get("continuation"))
    if continuation.get("safe_for_live_action") is True and continuation.get("live_action_disabled") is not False:
        errors.append(f"{label}: {capability_id} live-ready continuation must not be disabled")
    if continuation.get("safe_for_live_action") is False and continuation.get("live_action_disabled") is not True:
        errors.append(f"{label}: {capability_id} non-live continuation must be disabled")


def _validate_validators(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    validators = payload.get("validators")
    if not isinstance(validators, list):
        errors.append(f"{label}: validators must be a list")
        return
    validator_by_id = {
        str(validator.get("validator_id", "")): validator
        for validator in validators
        if isinstance(validator, dict)
    }
    for validator_id, expected_command in REQUIRED_VALIDATOR_COMMANDS.items():
        validator = validator_by_id.get(validator_id)
        if validator is None:
            errors.append(f"{label}: missing validator {validator_id}")
            continue
        if validator.get("command") != expected_command:
            errors.append(f"{label}: validator {validator_id} command must be {expected_command!r}")
        if validator.get("required_for_closure") is not True:
            errors.append(f"{label}: validator {validator_id} must be required_for_closure")


def _list_of_objects(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {_path_label(path)}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse evidence passport validation arguments."""

    parser = argparse.ArgumentParser(description="Validate evidence passports.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--evidence-passports", default=str(DEFAULT_EVIDENCE_PASSPORTS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for evidence passport validation."""

    args = parse_args(argv)
    validation = validate_evidence_passports(
        schema_path=Path(args.schema),
        evidence_passports_path=Path(args.evidence_passports),
    )
    write_evidence_passport_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("EVIDENCE PASSPORTS VALID")
    else:
        print(f"EVIDENCE PASSPORTS INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
