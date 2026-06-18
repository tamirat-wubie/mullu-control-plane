#!/usr/bin/env python3
"""Validate Personal Assistant policy matrix receipts.

Purpose: gate the no-effect policy matrix receipt on schema, P0-P5 approval
semantics, blocked-action parity, hard invariant closure, connector payload
redaction policy, and no-effect boundaries.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: policy matrix schema, collector constants, and schema helpers.
Invariants:
  - P4/P5 actions require explicit approval or remain blocked.
  - Skill policy and approval matrix blocked-action sets must match.
  - The receipt may list blocked secret field names but never serialize values.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.collect_personal_assistant_policy_matrix import (  # noqa: E402
    DEFAULT_OUTPUT,
    NO_EFFECT_FLAGS,
    REQUIRED_RISK_LEVELS,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

POLICY_MATRIX_SCHEMA_PATH = REPO_ROOT / "schemas" / "personal_assistant_policy_matrix_receipt.schema.json"
DEFAULT_VALIDATION_OUTPUT = REPO_ROOT / ".change_assurance" / "personal_assistant_policy_matrix_validation.json"
RECEIPT_ID_PATTERN = re.compile(r"^personal-assistant-policy-matrix-[0-9a-f]{16}$")
BLOCKED_SECRET_VALUE_MARKERS = ("bearer ", "client_secret=", "password=", "-----begin private key-----")


@dataclass(frozen=True, slots=True)
class PersonalAssistantPolicyMatrixValidationStep:
    """One policy matrix validation step."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class PersonalAssistantPolicyMatrixValidation:
    """Structured validation report for one policy matrix receipt."""

    receipt_path: str
    valid: bool
    receipt_id: str
    solver_outcome: str
    policy_matrix_closed: bool
    steps: tuple[PersonalAssistantPolicyMatrixValidationStep, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable validation report."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def validate_personal_assistant_policy_matrix_receipt(
    *,
    receipt_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = POLICY_MATRIX_SCHEMA_PATH,
    require_closed: bool = False,
) -> PersonalAssistantPolicyMatrixValidation:
    """Validate one Personal Assistant policy matrix receipt."""
    payload = _read_receipt_payload(receipt_path)
    steps = (
        _check_schema_contract(payload, schema_path),
        _check_receipt_id(payload),
        _check_source_refs(payload),
        _check_risk_levels(payload),
        _check_blocked_action_parity(payload),
        _check_hard_invariants(payload),
        _check_connector_payload_policy(payload),
        _check_no_effect_boundary(payload),
        _check_policy_matrix_gate(payload),
        _check_secret_value_boundary(payload),
        _check_require_closed(payload, require_closed=require_closed),
    )
    summary = _object(payload.get("policy_matrix_summary"))
    return PersonalAssistantPolicyMatrixValidation(
        receipt_path=_bounded_receipt_path(receipt_path),
        valid=all(step.passed for step in steps),
        receipt_id=_bounded_receipt_id(payload),
        solver_outcome=_bounded_text(payload.get("solver_outcome")),
        policy_matrix_closed=summary.get("policy_matrix_closed") is True,
        steps=steps,
    )


def write_personal_assistant_policy_matrix_validation_report(
    validation: PersonalAssistantPolicyMatrixValidation,
    output_path: Path,
) -> Path:
    """Write one local policy matrix validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.to_json_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _read_receipt_payload(receipt_path: Path) -> dict[str, Any]:
    try:
        raw_text = receipt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError("failed to read Personal Assistant policy matrix receipt") from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Personal Assistant policy matrix receipt returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Personal Assistant policy matrix receipt was not a JSON object")
    return parsed


def _check_schema_contract(
    payload: dict[str, Any],
    schema_path: Path,
) -> PersonalAssistantPolicyMatrixValidationStep:
    try:
        schema = _load_schema(schema_path)
    except OSError:
        return PersonalAssistantPolicyMatrixValidationStep("schema contract", False, "schema-read-failed")
    errors = _validate_schema_instance(schema, payload)
    return PersonalAssistantPolicyMatrixValidationStep(
        "schema contract",
        not errors,
        "valid" if not errors else f"schema-errors={len(errors)}",
    )


def _check_receipt_id(payload: dict[str, Any]) -> PersonalAssistantPolicyMatrixValidationStep:
    receipt_id = payload.get("receipt_id")
    passed = RECEIPT_ID_PATTERN.fullmatch(str(receipt_id)) is not None
    return PersonalAssistantPolicyMatrixValidationStep("receipt id", passed, "valid" if passed else "invalid")


def _check_source_refs(payload: dict[str, Any]) -> PersonalAssistantPolicyMatrixValidationStep:
    sources = _list_of_objects(payload.get("source_refs"))
    kinds = {str(source.get("source_kind")) for source in sources if source.get("bound") is True}
    required = {
        "skill_policy",
        "approval_matrix",
        "capsule",
        "authority_coverage_receipt",
        "capsule_alignment_receipt",
    }
    passed = required <= kinds
    return PersonalAssistantPolicyMatrixValidationStep(
        "source refs",
        passed,
        f"bound={len(kinds)} required={len(required)}",
    )


def _check_risk_levels(payload: dict[str, Any]) -> PersonalAssistantPolicyMatrixValidationStep:
    records = _list_of_objects(payload.get("risk_level_records"))
    levels = {str(record.get("level")) for record in records}
    p4_p5_closed = all(
        record.get("approval_rule_consistent") is True
        and record.get("execute_without_approval_blocked") is True
        for record in records
        if record.get("level") in {"P4", "P5"}
    )
    p5_blocked = any(record.get("level") == "P5" and record.get("p5_blocked") is True for record in records)
    passed = set(REQUIRED_RISK_LEVELS) == levels and p4_p5_closed and p5_blocked
    return PersonalAssistantPolicyMatrixValidationStep(
        "risk levels",
        passed,
        f"levels={len(levels)} p4p5={p4_p5_closed} p5_blocked={p5_blocked}",
    )


def _check_blocked_action_parity(payload: dict[str, Any]) -> PersonalAssistantPolicyMatrixValidationStep:
    records = _list_of_objects(payload.get("blocked_action_records"))
    parity = all(
        record.get("in_approval_matrix") is True
        and record.get("in_skill_policy") is True
        and record.get("blocked_without_approval") is True
        for record in records
    )
    passed = bool(records) and parity
    return PersonalAssistantPolicyMatrixValidationStep(
        "blocked action parity",
        passed,
        f"actions={len(records)} parity={parity}",
    )


def _check_hard_invariants(payload: dict[str, Any]) -> PersonalAssistantPolicyMatrixValidationStep:
    records = _list_of_objects(payload.get("hard_invariant_records"))
    closed = all(record.get("closed") is True for record in records)
    passed = bool(records) and closed
    return PersonalAssistantPolicyMatrixValidationStep(
        "hard invariants",
        passed,
        f"invariants={len(records)} closed={closed}",
    )


def _check_connector_payload_policy(payload: dict[str, Any]) -> PersonalAssistantPolicyMatrixValidationStep:
    connector_policy = _object(payload.get("connector_payload_policy"))
    passed = (
        connector_policy.get("allowed_fields_are_redacted_evidence_only") is True
        and connector_policy.get("secret_values_blocked") is True
        and connector_policy.get("raw_private_payloads_blocked") is True
        and connector_policy.get("policy_closed") is True
    )
    return PersonalAssistantPolicyMatrixValidationStep(
        "connector payload policy",
        passed,
        "closed" if passed else "open",
    )


def _check_no_effect_boundary(payload: dict[str, Any]) -> PersonalAssistantPolicyMatrixValidationStep:
    boundary = _object(payload.get("effect_boundary"))
    summary = _object(payload.get("policy_matrix_summary"))
    flags_clear = all(boundary.get(flag) is False for flag in NO_EFFECT_FLAGS)
    passed = flags_clear and summary.get("production_ready") is False and summary.get("customer_ready") is False
    return PersonalAssistantPolicyMatrixValidationStep(
        "no-effect boundary",
        passed,
        f"flags_clear={flags_clear}",
    )


def _check_policy_matrix_gate(payload: dict[str, Any]) -> PersonalAssistantPolicyMatrixValidationStep:
    summary = _object(payload.get("policy_matrix_summary"))
    required_true = (
        "policy_matrix_closed",
        "authority_coverage_closed",
        "capsule_alignment_closed",
        "capsule_policy_refs_bound",
        "foundation_mode_required",
        "p4_p5_require_explicit_approval",
        "p5_execute_blocked",
        "blocked_actions_match_policy",
        "overclaim_blocks_closed",
        "hard_invariants_closed",
        "connector_payload_policy_closed",
        "no_effect_boundary_verified",
    )
    passed = all(summary.get(key) is True for key in required_true) and payload.get("solver_outcome") == "SolvedVerified"
    return PersonalAssistantPolicyMatrixValidationStep(
        "policy matrix gate",
        passed,
        "closed" if passed else "open",
    )


def _check_secret_value_boundary(payload: dict[str, Any]) -> PersonalAssistantPolicyMatrixValidationStep:
    serialized = json.dumps(payload, sort_keys=True).lower()
    leaked_markers = [marker for marker in BLOCKED_SECRET_VALUE_MARKERS if marker in serialized]
    return PersonalAssistantPolicyMatrixValidationStep(
        "secret value boundary",
        not leaked_markers,
        "clean" if not leaked_markers else f"blocked_markers={','.join(leaked_markers)}",
    )


def _check_require_closed(
    payload: dict[str, Any],
    *,
    require_closed: bool,
) -> PersonalAssistantPolicyMatrixValidationStep:
    summary = _object(payload.get("policy_matrix_summary"))
    closed = summary.get("policy_matrix_closed") is True
    passed = closed or not require_closed
    return PersonalAssistantPolicyMatrixValidationStep(
        "require closed",
        passed,
        "closed" if closed else "not-required" if not require_closed else "open",
    )


def _bounded_receipt_id(payload: dict[str, Any]) -> str:
    receipt_id = payload.get("receipt_id")
    return str(receipt_id) if isinstance(receipt_id, str) else ""


def _bounded_receipt_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return "provided_receipt"


def _bounded_text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_objects(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def main(argv: list[str] | None = None) -> int:
    """Run the Personal Assistant policy matrix receipt validator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--schema", type=Path, default=POLICY_MATRIX_SCHEMA_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_VALIDATION_OUTPUT)
    parser.add_argument("--require-closed", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print validation report JSON.")
    args = parser.parse_args(argv)

    validation = validate_personal_assistant_policy_matrix_receipt(
        receipt_path=args.receipt,
        schema_path=args.schema,
        require_closed=args.require_closed,
    )
    write_personal_assistant_policy_matrix_validation_report(validation, args.output)
    if args.json:
        print(json.dumps(validation.to_json_dict(), indent=2, sort_keys=True))
    else:
        print(f"validation_report: {_bounded_receipt_path(args.output)}")
        print(f"receipt: {_bounded_receipt_path(args.receipt)}")
        print(f"receipt_id: {validation.receipt_id}")
        print(f"valid: {validation.valid}")
        for step in validation.steps:
            print(f"step: {step.name} passed={step.passed} detail={step.detail}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
