#!/usr/bin/env python3
"""Validate finance approval operator summary schema conformance.

Purpose: reject malformed or promotion-unsafe finance operator summaries.
Governance scope: operator summary schema validation, ok/ready consistency,
strict promotion command preservation, artifact status coverage, and
must-not-claim preservation.
Dependencies: .change_assurance/finance_approval_operator_summary.json and
schemas/finance_approval_operator_summary.schema.json.
Invariants:
  - Summary shape matches the public protocol schema.
  - Packet readiness and chain readiness agree.
  - Blocked summaries carry readiness blockers.
  - Strict promotion command includes --strict and --require-ready.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.produce_finance_approval_operator_summary import DEFAULT_OUTPUT as DEFAULT_SUMMARY  # noqa: E402
from scripts.produce_finance_approval_operator_summary import DEFAULT_SCHEMA  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "finance_approval_operator_summary_schema_validation.json"
REQUIRED_ARTIFACT_STATUSES = (
    "pilot_witness",
    "live_handoff_plan",
    "email_calendar_binding_receipt",
    "live_handoff_closure_run",
    "live_handoff_preflight",
)
REQUIRED_MUST_NOT_CLAIM = (
    "live email delivery",
    "production finance automation",
)


@dataclass(frozen=True, slots=True)
class FinanceOperatorSummarySchemaValidation:
    """Schema and semantic validation for one finance operator summary."""

    ok: bool
    errors: tuple[str, ...]
    summary_path: str
    schema_path: str
    packet_ready: bool
    chain_ready: bool
    readiness_blocker_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_finance_approval_operator_summary_schema(
    *,
    summary_path: Path = DEFAULT_SUMMARY,
    schema_path: Path = DEFAULT_SCHEMA,
) -> FinanceOperatorSummarySchemaValidation:
    """Validate one finance approval operator summary."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "finance operator summary schema", errors)
    summary = _load_json_object(summary_path, "finance operator summary", errors)
    if not schema or not summary:
        return _validation_result(summary_path=summary_path, schema_path=schema_path, summary=summary, errors=errors)

    errors.extend(_validate_schema_instance(schema, summary))
    _validate_summary_semantics(summary, errors)
    return _validation_result(summary_path=summary_path, schema_path=schema_path, summary=summary, errors=errors)


def write_finance_operator_summary_schema_validation(
    validation: FinanceOperatorSummarySchemaValidation,
    output_path: Path,
) -> Path:
    """Write one finance operator summary schema validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_summary_semantics(summary: dict[str, Any], errors: list[str]) -> None:
    packet_ready = summary.get("packet_ready") is True
    chain_ready = summary.get("chain_ready") is True
    if packet_ready != chain_ready:
        errors.append("packet_ready and chain_ready must match")
    readiness_blockers = summary.get("readiness_blockers", [])
    if not isinstance(readiness_blockers, list):
        errors.append("readiness_blockers must be a list")
        return
    if packet_ready and readiness_blockers:
        errors.append("ready operator summary must not contain readiness_blockers")
    if not packet_ready and not readiness_blockers:
        errors.append("blocked operator summary must contain readiness_blockers")
    expected_mode = "live-email-handoff" if packet_ready else "proof-pilot-blocked"
    if summary.get("promotion_mode") != expected_mode:
        errors.append(f"promotion_mode must be {expected_mode}")
    strict_command = str(summary.get("strict_promotion_command", ""))
    for token in ("validate_finance_approval_live_handoff_chain.py", "--strict", "--require-ready"):
        if token not in strict_command:
            errors.append(f"strict_promotion_command missing token {token}")
    artifact_statuses = summary.get("artifact_statuses", {})
    if not isinstance(artifact_statuses, dict):
        errors.append("artifact_statuses must be an object")
    else:
        missing_artifacts = sorted(set(REQUIRED_ARTIFACT_STATUSES) - set(artifact_statuses))
        if missing_artifacts:
            errors.append(f"artifact_statuses missing {missing_artifacts}")
    must_not_claim = {str(item) for item in summary.get("must_not_claim", []) if isinstance(item, str)}
    missing_claims = sorted(set(REQUIRED_MUST_NOT_CLAIM) - must_not_claim)
    if missing_claims:
        errors.append(f"must_not_claim missing {missing_claims}")


def _validation_result(
    *,
    summary_path: Path,
    schema_path: Path,
    summary: dict[str, Any],
    errors: list[str],
) -> FinanceOperatorSummarySchemaValidation:
    readiness_blockers = summary.get("readiness_blockers", [])
    return FinanceOperatorSummarySchemaValidation(
        ok=not errors,
        errors=tuple(errors),
        summary_path=str(summary_path),
        schema_path=str(schema_path),
        packet_ready=summary.get("packet_ready") is True,
        chain_ready=summary.get("chain_ready") is True,
        readiness_blocker_count=len(readiness_blockers) if isinstance(readiness_blockers, list) else 0,
    )


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        errors.append(f"{label} could not be read")
        return {}
    except json.JSONDecodeError:
        errors.append(f"{label} must be JSON")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} root must be an object")
        return {}
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse finance operator summary schema validation arguments."""
    parser = argparse.ArgumentParser(description="Validate finance approval operator summary schema.")
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for finance operator summary schema validation."""
    args = parse_args(argv)
    validation = validate_finance_approval_operator_summary_schema(
        summary_path=Path(args.summary),
        schema_path=Path(args.schema),
    )
    write_finance_operator_summary_schema_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("FINANCE OPERATOR SUMMARY SCHEMA VALID")
    else:
        print(f"FINANCE OPERATOR SUMMARY SCHEMA INVALID errors={list(validation.errors)}")
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
