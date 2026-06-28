#!/usr/bin/env python3
"""Validate an external PR execution approval witness.

Purpose: prove external PR execution authority is explicit, hash checked, and
derived from local PR-tool admission.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: external PR execution approval witness schema and semantic validator.
Invariants: pending witnesses keep external effects disabled.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_external_pr_execution_approval_witness import (  # noqa: E402
    DEFAULT_SCHEMA,
    ExternalPrExecutionApprovalWitnessValidation,
    validate_external_pr_execution_approval_witness as validate_witness_object,
)


DEFAULT_WITNESS = REPO_ROOT / "examples" / "external_pr_execution_approval_witness.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "external_pr_execution_approval_witness_validation.json"


def validate_external_pr_execution_approval_witness(
    *,
    witness_path: Path = DEFAULT_WITNESS,
    schema_path: Path = DEFAULT_SCHEMA,
) -> ExternalPrExecutionApprovalWitnessValidation:
    """Validate an external PR execution approval witness file."""

    witness = _load_json_object(witness_path)
    return validate_witness_object(
        witness=witness,
        schema_path=schema_path,
        witness_path=witness_path,
    )


def write_external_pr_execution_approval_witness_validation(
    validation: ExternalPrExecutionApprovalWitnessValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _load_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"json_parse_failed:{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("json_root_must_be_object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse external PR execution approval witness validation arguments."""

    parser = argparse.ArgumentParser(description="Validate external PR execution approval witness.")
    parser.add_argument("--witness", default=str(DEFAULT_WITNESS))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for external PR execution approval witness validation."""

    args = parse_args(argv)
    validation = validate_external_pr_execution_approval_witness(
        witness_path=Path(args.witness),
        schema_path=Path(args.schema),
    )
    write_external_pr_execution_approval_witness_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("EXTERNAL PR EXECUTION APPROVAL WITNESS VALID")
    else:
        print(f"EXTERNAL PR EXECUTION APPROVAL WITNESS INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
