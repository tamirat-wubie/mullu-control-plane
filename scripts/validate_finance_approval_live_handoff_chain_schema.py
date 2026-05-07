#!/usr/bin/env python3
"""Validate finance approval live handoff chain validation schema conformance.

Purpose: reject malformed or internally inconsistent aggregate finance live
handoff chain validation reports.
Governance scope: aggregate chain schema validation, five-check ordering,
blocker derivation, ok/blocker consistency, and readiness/blocker consistency.
Dependencies: schemas/finance_approval_live_handoff_chain_validation.schema.json
and .change_assurance/finance_approval_live_handoff_chain_validation.json.
Invariants:
  - Chain validation shape matches the public protocol schema.
  - The five aggregate checks appear in governed order.
  - Blockers are exactly the failed check names.
  - ok is derived from blockers.
  - ready is separated from ok and requires no readiness blockers.
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

from scripts.validate_finance_approval_live_handoff_chain import DEFAULT_OUTPUT as DEFAULT_CHAIN  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "finance_approval_live_handoff_chain_validation.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "finance_approval_live_handoff_chain_schema_validation.json"
EXPECTED_CHECK_NAMES = (
    "finance closure run schema validation",
    "finance email/calendar live receipt validation",
    "finance preflight schema validation",
    "finance handoff packet schema validation",
    "governance protocol manifest validation",
)


@dataclass(frozen=True, slots=True)
class FinanceLiveHandoffChainSchemaValidation:
    """Schema and semantic validation for one finance chain validation report."""

    ok: bool
    errors: tuple[str, ...]
    chain_path: str
    schema_path: str
    check_count: int
    blocker_count: int
    readiness_blocker_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_finance_approval_live_handoff_chain_schema(
    *,
    chain_path: Path = DEFAULT_CHAIN,
    schema_path: Path = DEFAULT_SCHEMA,
) -> FinanceLiveHandoffChainSchemaValidation:
    """Validate finance chain validation schema and semantic consistency."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "finance live handoff chain validation schema", errors)
    chain = _load_json_object(chain_path, "finance live handoff chain validation", errors)
    if not schema or not chain:
        return _validation_result(chain_path=chain_path, schema_path=schema_path, chain=chain, errors=errors)

    errors.extend(_validate_schema_instance(schema, chain))
    _validate_check_sequence(chain, errors)
    _validate_status_consistency(chain, errors)
    return _validation_result(chain_path=chain_path, schema_path=schema_path, chain=chain, errors=errors)


def write_finance_live_handoff_chain_schema_validation(
    validation: FinanceLiveHandoffChainSchemaValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic finance chain schema validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_check_sequence(chain: dict[str, Any], errors: list[str]) -> None:
    checks = chain.get("checks", [])
    if not isinstance(checks, list):
        errors.append("checks must be a list")
        return
    if chain.get("check_count") != len(checks):
        errors.append("check_count must match checks length")
    check_names = tuple(str(check.get("name", "")) for check in checks if isinstance(check, dict))
    if check_names != EXPECTED_CHECK_NAMES:
        errors.append(f"check names must match expected finance chain order: observed={list(check_names)}")


def _validate_status_consistency(chain: dict[str, Any], errors: list[str]) -> None:
    checks = chain.get("checks", [])
    if not isinstance(checks, list):
        return
    blockers = chain.get("blockers", [])
    readiness_blockers = chain.get("readiness_blockers", [])
    if not isinstance(blockers, list):
        errors.append("blockers must be a list")
        return
    if not isinstance(readiness_blockers, list):
        errors.append("readiness_blockers must be a list")
        return
    expected_blockers = [
        str(check.get("name", ""))
        for check in checks
        if isinstance(check, dict) and check.get("passed") is not True
    ]
    observed_blockers = [str(blocker) for blocker in blockers]
    if observed_blockers != expected_blockers:
        errors.append(
            "blockers must match failed finance chain check names: "
            f"observed={observed_blockers} expected={expected_blockers}"
        )
    ok = chain.get("ok") is True
    if ok and observed_blockers:
        errors.append("ok chain validation must not contain blockers")
    if not ok and not observed_blockers:
        errors.append("failed chain validation must contain blockers")
    ready = chain.get("ready") is True
    observed_readiness_blockers = [str(blocker) for blocker in readiness_blockers]
    if ready and not ok:
        errors.append("ready chain requires ok=true")
    if ready and observed_readiness_blockers:
        errors.append("ready chain must not contain readiness_blockers")
    if ready and _check_details_indicate_not_ready(checks):
        errors.append("ready chain contradicts not-ready child check detail")
    if not ready and not observed_readiness_blockers:
        errors.append("not-ready chain must contain readiness_blockers")
    if observed_blockers:
        missing_validation_blockers = [
            blocker
            for blocker in observed_blockers
            if not any(blocker in readiness_blocker for readiness_blocker in observed_readiness_blockers)
        ]
        if missing_validation_blockers:
            errors.append(
                "readiness_blockers must include failed validation blockers: "
                f"missing={missing_validation_blockers}"
            )


def _check_details_indicate_not_ready(checks: list[Any]) -> bool:
    for check in checks:
        if not isinstance(check, dict):
            continue
        detail = str(check.get("detail", ""))
        if "ready=False" in detail or "status=blocked" in detail:
            return True
        if any(f"blocker_count={count}" in detail for count in range(1, 100)):
            return True
    return False


def _validation_result(
    *,
    chain_path: Path,
    schema_path: Path,
    chain: dict[str, Any],
    errors: list[str],
) -> FinanceLiveHandoffChainSchemaValidation:
    checks = chain.get("checks", ())
    blockers = chain.get("blockers", ())
    readiness_blockers = chain.get("readiness_blockers", ())
    return FinanceLiveHandoffChainSchemaValidation(
        ok=not errors,
        errors=tuple(errors),
        chain_path=str(chain_path),
        schema_path=str(schema_path),
        check_count=len(checks) if isinstance(checks, list) else 0,
        blocker_count=len(blockers) if isinstance(blockers, list) else 0,
        readiness_blocker_count=len(readiness_blockers) if isinstance(readiness_blockers, list) else 0,
    )


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse finance chain schema validation arguments."""
    parser = argparse.ArgumentParser(description="Validate finance approval live handoff chain validation schema.")
    parser.add_argument("--chain", default=str(DEFAULT_CHAIN))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for finance chain schema validation."""
    args = parse_args(argv)
    validation = validate_finance_approval_live_handoff_chain_schema(
        chain_path=Path(args.chain),
        schema_path=Path(args.schema),
    )
    write_finance_live_handoff_chain_schema_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("FINANCE LIVE HANDOFF CHAIN SCHEMA VALID")
    else:
        print(f"FINANCE LIVE HANDOFF CHAIN SCHEMA INVALID errors={list(validation.errors)}")
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
