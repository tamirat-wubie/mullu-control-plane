#!/usr/bin/env python3
"""Validate read-only worker runtime enablement promotion decisions.

Purpose: consume the runtime enablement admission gate and issue a governed
Foundation Mode promotion denial without enabling runtime.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: runtime enablement admission gate and schema validation helpers.
Invariants:
  - Promotion decision is not runtime activation.
  - Runtime promotion, admission, enablement, dispatch, worker invocation,
    receipt emission, receipt append, terminal closure, connector authority,
    filesystem writes, network access, and secret serialization remain denied.
  - Re-entry evidence is explicit.
  - Mfidel atomicity is preserved.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_read_only_worker_runtime_enablement_admission_gate import (  # noqa: E402
    build_runtime_enablement_admission_gate,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "read_only_worker_runtime_enablement_promotion_decision.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "read_only_worker_runtime_enablement_promotion_decision.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "read_only_worker_runtime_enablement_promotion_decision_validation.json"
SOURCE_ADMISSION_GATE_REF = "examples/read_only_worker_runtime_enablement_admission_gate.foundation.json"
DENIAL_REASONS = (
    "denied://foundation-mode/runtime-promotion-not-authorized",
    "denied://runtime-authority/live-promotion-decision-missing",
    "denied://operator/no-runtime-execution-requested-in-this-slice",
)
REENTRY_EVIDENCE_REQUIRED = (
    "evidence://foundation-mode/promoted-posture",
    "evidence://runtime-authority/non-foundation-promotion-approval",
    "evidence://runtime-execution/live-safety-preflight",
    "evidence://runtime-rollback/live-recovery-plan",
)
FALSE_FIELDS = (
    "runtime_promotion_allowed",
    "runtime_admission_allowed",
    "runtime_enablement_allowed",
    "runtime_enablement_executed",
    "runtime_dispatch_allowed",
    "worker_invocation_allowed",
    "runtime_receipt_emission_allowed",
    "receipt_append_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
    "secret_values_serialized",
    "connector_authority_allowed",
    "filesystem_write_allowed",
    "external_network_allowed",
)


@dataclass(frozen=True, slots=True)
class RuntimeEnablementPromotionDecisionValidation:
    """Validation result for one runtime enablement promotion decision."""

    valid: bool
    decision_path: str
    schema_path: str
    errors: tuple[str, ...]
    accepted_evidence_ref_count: int
    runtime_promotion_allowed: bool
    runtime_enablement_allowed: bool
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_runtime_enablement_promotion_decision() -> dict[str, Any]:
    """Build the runtime promotion decision from the admission gate."""

    admission_gate = build_runtime_enablement_admission_gate()
    accepted_refs = _string_list(admission_gate.get("accepted_evidence_refs"))
    blocked_actions = _string_list(admission_gate.get("blocked_actions"))
    return {
        "decision_id": "read-only-worker-runtime-enablement-promotion-decision-foundation-repo-inspection-20260620",
        "decision_version": "read_only_worker_runtime_enablement_promotion_decision.v1",
        "source_admission_gate_ref": SOURCE_ADMISSION_GATE_REF,
        "selected_worker_path": "read_only_repo_inspection",
        "solver_outcome": "GovernanceBlocked",
        "proof_state": "Pass",
        "decision_state": "runtime_promotion_denied_foundation_mode",
        "evidence_accepted": True,
        "runtime_promotion_decided": True,
        "runtime_promotion_denied": True,
        **{field_name: False for field_name in FALSE_FIELDS},
        "denial_reasons": list(DENIAL_REASONS),
        "reentry_evidence_required": list(REENTRY_EVIDENCE_REQUIRED),
        "accepted_evidence_refs": accepted_refs,
        "blocked_actions": blocked_actions,
        "summary": {
            "accepted_evidence_ref_count": len(accepted_refs),
            "denial_reason_count": len(DENIAL_REASONS),
            "reentry_evidence_required_count": len(REENTRY_EVIDENCE_REQUIRED),
            "runtime_promotion_allowed_count": 0,
            "runtime_enablement_count": 0,
            "blocked_action_count": len(blocked_actions),
        },
        "validators": [
            "scripts/validate_read_only_worker_runtime_enablement_promotion_decision.py",
            "scripts/validate_read_only_worker_runtime_enablement_admission_gate.py",
            "tests/test_validate_read_only_worker_runtime_enablement_promotion_decision.py",
        ],
        "next_action": "Runtime remains blocked until the operator intentionally leaves Foundation Mode and provides live promotion authority evidence.",
    }


def validate_runtime_enablement_promotion_decision(
    *,
    decision_path: Path = DEFAULT_EXAMPLE,
    schema_path: Path = DEFAULT_SCHEMA,
) -> RuntimeEnablementPromotionDecisionValidation:
    """Validate one runtime enablement promotion decision artifact."""

    errors: list[str] = []
    schema = _load_schema(schema_path)
    decision = _load_json_object(decision_path, "runtime enablement promotion decision", errors)
    expected_decision = build_runtime_enablement_promotion_decision()
    if decision:
        errors.extend(_validate_schema_instance(schema, decision))
        if decision != expected_decision:
            errors.append("runtime enablement promotion decision does not match generated admission projection")
        _validate_semantics(decision, errors)
    summary = expected_decision["summary"]
    return RuntimeEnablementPromotionDecisionValidation(
        valid=not errors,
        decision_path=_path_label(decision_path),
        schema_path=_path_label(schema_path),
        errors=tuple(errors),
        accepted_evidence_ref_count=int(summary["accepted_evidence_ref_count"]),
        runtime_promotion_allowed=False,
        runtime_enablement_allowed=False,
        next_action=str(expected_decision["next_action"]),
    )


def write_runtime_enablement_promotion_decision_validation(
    validation: RuntimeEnablementPromotionDecisionValidation,
    output_path: Path,
) -> Path:
    """Write one runtime promotion decision validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def write_runtime_enablement_promotion_decision_fixture(output_path: Path) -> Path:
    """Write the generated runtime promotion decision fixture."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_runtime_enablement_promotion_decision(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_semantics(decision: dict[str, Any], errors: list[str]) -> None:
    if decision.get("evidence_accepted") is not True:
        errors.append("evidence_accepted must be true")
    if decision.get("runtime_promotion_decided") is not True:
        errors.append("runtime_promotion_decided must be true")
    if decision.get("runtime_promotion_denied") is not True:
        errors.append("runtime_promotion_denied must be true")
    for field_name in FALSE_FIELDS:
        if decision.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    if set(_string_list(decision.get("denial_reasons"))) != set(DENIAL_REASONS):
        errors.append("denial_reasons must match Foundation Mode promotion denial reasons")
    if set(_string_list(decision.get("reentry_evidence_required"))) != set(REENTRY_EVIDENCE_REQUIRED):
        errors.append("reentry_evidence_required must match runtime promotion re-entry evidence")
    accepted_refs = _string_list(decision.get("accepted_evidence_refs"))
    if len(accepted_refs) != 12:
        errors.append("accepted_evidence_refs must contain twelve refs")
    summary = decision.get("summary")
    if not isinstance(summary, dict):
        errors.append("summary must be an object")
        return
    expected_counts = {
        "accepted_evidence_ref_count": len(accepted_refs),
        "denial_reason_count": len(_string_list(decision.get("denial_reasons"))),
        "reentry_evidence_required_count": len(_string_list(decision.get("reentry_evidence_required"))),
        "runtime_promotion_allowed_count": 0,
        "runtime_enablement_count": 0,
        "blocked_action_count": len(_string_list(decision.get("blocked_actions"))),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"summary.{field_name} must match promotion decision state")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing")
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
    raise ValueError(f"non-finite JSON constant is not permitted: {raw_constant}")


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _path_label(path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse promotion decision validation arguments."""

    parser = argparse.ArgumentParser(description="Validate read-only worker runtime enablement promotion decision.")
    parser.add_argument("--decision", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-fixture", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    args = parse_args(argv)
    if args.write_fixture:
        write_runtime_enablement_promotion_decision_fixture(Path(args.decision))
    validation = validate_runtime_enablement_promotion_decision(
        decision_path=Path(args.decision),
        schema_path=Path(args.schema),
    )
    if args.write:
        write_runtime_enablement_promotion_decision_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("runtime enablement promotion decision valid")
    else:
        print(f"runtime enablement promotion decision invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
