#!/usr/bin/env python3
"""Validate read-only worker runtime Foundation closure summaries.

Purpose: prove the read-only worker runtime enablement chain is closed for
Foundation Mode while live runtime remains blocked.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: runtime promotion decision and schema validation helpers.
Invariants:
  - Foundation closure summary is not terminal live-runtime closure.
  - Runtime promotion, admission, enablement, dispatch, worker invocation,
    receipt emission, receipt append, connector authority, filesystem writes,
    network access, and secret serialization remain denied.
  - The summary references the complete Foundation Mode runtime chain.
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

from scripts.validate_read_only_worker_runtime_enablement_promotion_decision import (  # noqa: E402
    build_runtime_enablement_promotion_decision,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "read_only_worker_runtime_foundation_closure_summary.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "read_only_worker_runtime_foundation_closure_summary.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "read_only_worker_runtime_foundation_closure_summary_validation.json"
SOURCE_PROMOTION_DECISION_REF = "examples/read_only_worker_runtime_enablement_promotion_decision.foundation.json"
CHAIN_REFS = (
    "examples/read_only_worker_runtime_enablement_witness.foundation.json",
    "examples/read_only_worker_runtime_enablement_evidence_request_status_ledger.foundation.json",
    "examples/read_only_worker_runtime_enablement_submitted_evidence_refs.foundation.json",
    "examples/read_only_worker_runtime_enablement_review_packet.foundation.json",
    "examples/read_only_worker_runtime_disablement_rollback_plan.foundation.json",
    "examples/read_only_worker_trusted_runtime_clock_receipt.foundation.json",
    "examples/read_only_worker_operator_runtime_enablement_approval_ref.foundation.json",
    "examples/read_only_worker_runtime_enablement_evidence_acceptance_gate.foundation.json",
    "examples/read_only_worker_runtime_enablement_admission_gate.foundation.json",
    "examples/read_only_worker_runtime_enablement_promotion_decision.foundation.json",
    "docs/80_read_only_worker_binding_contract.md",
)
LIVE_RUNTIME_BLOCKERS = (
    "blocked://foundation-mode/runtime-execution-not-authorized",
    "blocked://runtime-promotion/promotion-denied",
    "blocked://operator/no-non-foundation-authority-thread",
)
FALSE_FIELDS = (
    "terminal_closure_claimed",
    "runtime_promotion_allowed",
    "runtime_admission_allowed",
    "runtime_enablement_allowed",
    "runtime_enablement_executed",
    "runtime_dispatch_allowed",
    "worker_invocation_allowed",
    "runtime_receipt_emission_allowed",
    "receipt_append_allowed",
    "success_claim_allowed",
    "secret_values_serialized",
    "connector_authority_allowed",
    "filesystem_write_allowed",
    "external_network_allowed",
)


@dataclass(frozen=True, slots=True)
class RuntimeFoundationClosureSummaryValidation:
    """Validation result for one runtime Foundation closure summary."""

    valid: bool
    summary_path: str
    schema_path: str
    errors: tuple[str, ...]
    chain_ref_count: int
    accepted_evidence_ref_count: int
    live_runtime_blocked: bool
    runtime_enablement_allowed: bool
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_runtime_foundation_closure_summary() -> dict[str, Any]:
    """Build the Foundation closure summary from the promotion decision."""

    promotion_decision = build_runtime_enablement_promotion_decision()
    accepted_refs = _string_list(promotion_decision.get("accepted_evidence_refs"))
    blocked_actions = _string_list(promotion_decision.get("blocked_actions"))
    return {
        "closure_id": "read-only-worker-runtime-foundation-closure-summary-repo-inspection-20260620",
        "closure_version": "read_only_worker_runtime_foundation_closure_summary.v1",
        "source_promotion_decision_ref": SOURCE_PROMOTION_DECISION_REF,
        "selected_worker_path": "read_only_repo_inspection",
        "solver_outcome": "SolvedVerified",
        "proof_state": "Pass",
        "closure_state": "foundation_closed_live_runtime_blocked",
        "foundation_closure_complete": True,
        "live_runtime_blocked": True,
        **{field_name: False for field_name in FALSE_FIELDS},
        "chain_refs": list(CHAIN_REFS),
        "accepted_evidence_refs": accepted_refs,
        "live_runtime_blockers": list(LIVE_RUNTIME_BLOCKERS),
        "blocked_actions": blocked_actions,
        "summary": {
            "chain_ref_count": len(CHAIN_REFS),
            "accepted_evidence_ref_count": len(accepted_refs),
            "live_runtime_blocker_count": len(LIVE_RUNTIME_BLOCKERS),
            "runtime_promotion_allowed_count": 0,
            "runtime_enablement_count": 0,
            "blocked_action_count": len(blocked_actions),
        },
        "validators": [
            "scripts/validate_read_only_worker_runtime_foundation_closure_summary.py",
            "scripts/validate_read_only_worker_runtime_enablement_promotion_decision.py",
            "tests/test_validate_read_only_worker_runtime_foundation_closure_summary.py",
        ],
        "next_action": "Stop the worker-runtime line in Foundation Mode; open a separate non-Foundation authority thread only if live runtime is explicitly requested.",
    }


def validate_runtime_foundation_closure_summary(
    *,
    summary_path: Path = DEFAULT_EXAMPLE,
    schema_path: Path = DEFAULT_SCHEMA,
) -> RuntimeFoundationClosureSummaryValidation:
    """Validate one runtime Foundation closure summary artifact."""

    errors: list[str] = []
    schema = _load_schema(schema_path)
    closure_summary = _load_json_object(summary_path, "runtime Foundation closure summary", errors)
    expected_summary = build_runtime_foundation_closure_summary()
    if closure_summary:
        errors.extend(_validate_schema_instance(schema, closure_summary))
        if closure_summary != expected_summary:
            errors.append("runtime Foundation closure summary does not match generated promotion-decision projection")
        _validate_semantics(closure_summary, errors)
    summary = expected_summary["summary"]
    return RuntimeFoundationClosureSummaryValidation(
        valid=not errors,
        summary_path=_path_label(summary_path),
        schema_path=_path_label(schema_path),
        errors=tuple(errors),
        chain_ref_count=int(summary["chain_ref_count"]),
        accepted_evidence_ref_count=int(summary["accepted_evidence_ref_count"]),
        live_runtime_blocked=True,
        runtime_enablement_allowed=False,
        next_action=str(expected_summary["next_action"]),
    )


def write_runtime_foundation_closure_summary_validation(
    validation: RuntimeFoundationClosureSummaryValidation,
    output_path: Path,
) -> Path:
    """Write one closure summary validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def write_runtime_foundation_closure_summary_fixture(output_path: Path) -> Path:
    """Write the generated closure summary fixture."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_runtime_foundation_closure_summary(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_semantics(closure_summary: dict[str, Any], errors: list[str]) -> None:
    if closure_summary.get("foundation_closure_complete") is not True:
        errors.append("foundation_closure_complete must be true")
    if closure_summary.get("live_runtime_blocked") is not True:
        errors.append("live_runtime_blocked must be true")
    for field_name in FALSE_FIELDS:
        if closure_summary.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    chain_refs = _string_list(closure_summary.get("chain_refs"))
    if set(chain_refs) != set(CHAIN_REFS):
        errors.append("chain_refs must match the complete Foundation runtime chain")
    accepted_refs = _string_list(closure_summary.get("accepted_evidence_refs"))
    if len(accepted_refs) != 12:
        errors.append("accepted_evidence_refs must contain twelve refs")
    blockers = _string_list(closure_summary.get("live_runtime_blockers"))
    if set(blockers) != set(LIVE_RUNTIME_BLOCKERS):
        errors.append("live_runtime_blockers must match Foundation runtime blockers")
    for chain_ref in chain_refs:
        if not (REPO_ROOT / chain_ref).exists():
            errors.append(f"chain ref missing: {chain_ref}")
    summary = closure_summary.get("summary")
    if not isinstance(summary, dict):
        errors.append("summary must be an object")
        return
    expected_counts = {
        "chain_ref_count": len(chain_refs),
        "accepted_evidence_ref_count": len(accepted_refs),
        "live_runtime_blocker_count": len(blockers),
        "runtime_promotion_allowed_count": 0,
        "runtime_enablement_count": 0,
        "blocked_action_count": len(_string_list(closure_summary.get("blocked_actions"))),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"summary.{field_name} must match closure summary state")


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
    """Parse closure summary validation arguments."""

    parser = argparse.ArgumentParser(description="Validate read-only worker runtime Foundation closure summary.")
    parser.add_argument("--summary", default=str(DEFAULT_EXAMPLE))
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
        write_runtime_foundation_closure_summary_fixture(Path(args.summary))
    validation = validate_runtime_foundation_closure_summary(
        summary_path=Path(args.summary),
        schema_path=Path(args.schema),
    )
    if args.write:
        write_runtime_foundation_closure_summary_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("runtime Foundation closure summary valid")
    else:
        print(f"runtime Foundation closure summary invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
