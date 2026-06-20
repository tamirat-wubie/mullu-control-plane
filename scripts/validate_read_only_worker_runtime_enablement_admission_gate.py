#!/usr/bin/env python3
"""Validate read-only worker runtime enablement admission gates.

Purpose: evaluate runtime admission after evidence acceptance while keeping
Foundation Mode runtime authority denied.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: runtime enablement evidence acceptance gate and admission gate
schema.
Invariants:
  - Accepted evidence does not imply runtime admission.
  - Runtime enablement, dispatch, worker invocation, receipt emission, receipt
    append, terminal closure, network, filesystem writes, connector authority,
    and secret serialization remain denied.
  - Foundation Mode keeps admission blocked until a future authority witness.
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

from scripts.validate_read_only_worker_runtime_enablement_evidence_acceptance_gate import (  # noqa: E402
    build_runtime_enablement_evidence_acceptance_gate,
)
from scripts.validate_read_only_worker_runtime_enablement_evidence_request_status_ledger import (  # noqa: E402
    BLOCKED_ACTIONS,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "read_only_worker_runtime_enablement_admission_gate.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "read_only_worker_runtime_enablement_admission_gate.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "read_only_worker_runtime_enablement_admission_gate_validation.json"
GATE_ID = "read-only-worker-runtime-enablement-admission-gate-foundation-repo-inspection-20260620"
SOURCE_ACCEPTANCE_GATE_REF = "examples/read_only_worker_runtime_enablement_evidence_acceptance_gate.foundation.json"
ADMISSION_BLOCKERS = (
    "foundation_mode_runtime_authority_missing",
    "non_foundation_runtime_promotion_witness_missing",
    "runtime_admission_phi_gov_decision_missing",
)
FALSE_FIELDS = (
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
class RuntimeEnablementAdmissionGateValidation:
    """Validation result for one runtime admission gate."""

    valid: bool
    gate_path: str
    schema_path: str
    errors: tuple[str, ...]
    accepted_evidence_ref_count: int
    admission_blocker_count: int
    runtime_admission_allowed: bool
    runtime_enablement_allowed: bool
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_runtime_enablement_admission_gate() -> dict[str, Any]:
    """Build a Foundation Mode runtime admission gate."""

    acceptance_gate = build_runtime_enablement_evidence_acceptance_gate()
    accepted_refs = list(acceptance_gate["accepted_evidence_refs"])
    return {
        "gate_id": GATE_ID,
        "gate_version": "read_only_worker_runtime_enablement_admission_gate.v1",
        "source_acceptance_gate_ref": SOURCE_ACCEPTANCE_GATE_REF,
        "selected_worker_path": "read_only_repo_inspection",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "admission_state": "blocked_foundation_mode_runtime_authority_missing",
        "evidence_accepted": True,
        **{field_name: False for field_name in FALSE_FIELDS},
        "admission_blockers": list(ADMISSION_BLOCKERS),
        "accepted_evidence_refs": accepted_refs,
        "blocked_actions": list(BLOCKED_ACTIONS),
        "summary": {
            "accepted_evidence_ref_count": len(accepted_refs),
            "runtime_admission_count": 0,
            "runtime_enablement_count": 0,
            "admission_blocker_count": len(ADMISSION_BLOCKERS),
            "blocked_action_count": len(BLOCKED_ACTIONS),
        },
        "validators": [
            "scripts/validate_read_only_worker_runtime_enablement_admission_gate.py",
            "scripts/validate_read_only_worker_runtime_enablement_evidence_acceptance_gate.py",
            "tests/test_validate_read_only_worker_runtime_enablement_admission_gate.py",
        ],
        "next_action": "Produce a future non-Foundation runtime authority decision before runtime enablement.",
    }


def validate_runtime_enablement_admission_gate(
    *,
    gate_path: Path = DEFAULT_EXAMPLE,
    schema_path: Path = DEFAULT_SCHEMA,
) -> RuntimeEnablementAdmissionGateValidation:
    """Validate one runtime admission gate."""

    errors: list[str] = []
    schema = _load_schema(schema_path)
    gate = _load_json_object(gate_path, "runtime enablement admission gate", errors)
    expected_gate = build_runtime_enablement_admission_gate()
    if gate:
        errors.extend(_validate_schema_instance(schema, gate))
        if gate != expected_gate:
            errors.append("runtime enablement admission gate does not match generated acceptance gate")
        _validate_semantics(gate, expected_gate, errors)
    summary = expected_gate["summary"]
    return RuntimeEnablementAdmissionGateValidation(
        valid=not errors,
        gate_path=_path_label(gate_path),
        schema_path=_path_label(schema_path),
        errors=tuple(errors),
        accepted_evidence_ref_count=int(summary["accepted_evidence_ref_count"]),
        admission_blocker_count=int(summary["admission_blocker_count"]),
        runtime_admission_allowed=False,
        runtime_enablement_allowed=False,
        next_action=str(expected_gate["next_action"]),
    )


def write_runtime_enablement_admission_gate_validation(
    validation: RuntimeEnablementAdmissionGateValidation,
    output_path: Path,
) -> Path:
    """Write one runtime admission gate validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def write_runtime_enablement_admission_gate_fixture(output_path: Path) -> Path:
    """Write the generated runtime admission gate fixture."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(build_runtime_enablement_admission_gate(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_semantics(gate: dict[str, Any], expected_gate: dict[str, Any], errors: list[str]) -> None:
    if gate.get("gate_id") != GATE_ID:
        errors.append("gate_id is invalid")
    if gate.get("evidence_accepted") is not True:
        errors.append("evidence_accepted must be true")
    for field_name in FALSE_FIELDS:
        if gate.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    if gate.get("admission_blockers") != list(ADMISSION_BLOCKERS):
        errors.append("admission_blockers must match Foundation Mode blockers")
    if gate.get("accepted_evidence_refs") != expected_gate["accepted_evidence_refs"]:
        errors.append("accepted_evidence_refs must match evidence acceptance gate")
    if set(_string_list(gate.get("blocked_actions"))) != set(BLOCKED_ACTIONS):
        errors.append("blocked_actions must match runtime enablement blocked actions")
    _validate_summary(gate, errors)


def _validate_summary(gate: dict[str, Any], errors: list[str]) -> None:
    summary = gate.get("summary")
    if not isinstance(summary, dict):
        errors.append("summary must be an object")
        return
    expected_counts = {
        "accepted_evidence_ref_count": len(_string_list(gate.get("accepted_evidence_refs"))),
        "runtime_admission_count": 1 if gate.get("runtime_admission_allowed") is True else 0,
        "runtime_enablement_count": 1 if gate.get("runtime_enablement_allowed") is True else 0,
        "admission_blocker_count": len(_string_list(gate.get("admission_blockers"))),
        "blocked_action_count": len(_string_list(gate.get("blocked_actions"))),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"summary.{field_name} must match runtime admission gate state")


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
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse runtime admission gate validation arguments."""

    parser = argparse.ArgumentParser(description="Validate read-only worker runtime enablement admission gate.")
    parser.add_argument("--gate", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-fixture", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for runtime admission gate validation."""

    args = parse_args(argv)
    if args.write_fixture:
        write_runtime_enablement_admission_gate_fixture(Path(args.gate))
    validation = validate_runtime_enablement_admission_gate(gate_path=Path(args.gate), schema_path=Path(args.schema))
    if args.write:
        write_runtime_enablement_admission_gate_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("runtime enablement admission gate valid")
    else:
        print(f"runtime enablement admission gate invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
