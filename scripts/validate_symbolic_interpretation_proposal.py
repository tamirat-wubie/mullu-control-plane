#!/usr/bin/env python3
"""Validate symbolic interpretation proposal artifacts.

Purpose: prove lower-authority interpretation proposals remain proposal-only
and cannot override deterministic gateway interpretation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: symbolic interpretation proposal schema and Foundation example.
Invariants:
  - Proposal authority never grants action or execution.
  - Deterministic override is denied.
  - Private payloads and secret values are never serialized.
  - Rejected proposals must carry at least one rejected reason.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "symbolic_interpretation_proposal.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "symbolic_interpretation_proposal.foundation.json"


@dataclass(frozen=True, slots=True)
class SymbolicInterpretationProposalValidation:
    """Validation result for one symbolic interpretation proposal."""

    valid: bool
    errors: tuple[str, ...]
    validation_status: str


def validate_symbolic_interpretation_proposal(
    *,
    path: Path = DEFAULT_EXAMPLE,
    schema_path: Path = DEFAULT_SCHEMA,
) -> SymbolicInterpretationProposalValidation:
    """Validate one symbolic interpretation proposal artifact."""
    errors: list[str] = []
    payload = _load_json_object(path, "symbolic interpretation proposal", errors)
    schema = _load_schema(schema_path)
    if payload:
        errors.extend(_validate_schema_instance(schema, payload))
        errors.extend(_semantic_errors(payload))
    return SymbolicInterpretationProposalValidation(
        valid=not errors,
        errors=tuple(errors),
        validation_status=str(payload.get("validation_status", "")) if payload else "",
    )


def _semantic_errors(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("authority_level") != "proposal_only":
        errors.append("authority_level must be proposal_only")
    if payload.get("deterministic_override_allowed") is not False:
        errors.append("deterministic_override_allowed must be false")
    if payload.get("action_authority_granted") is not False:
        errors.append("action_authority_granted must be false")
    if payload.get("execution_allowed") is not False:
        errors.append("execution_allowed must be false")
    if payload.get("private_payload_included") is not False:
        errors.append("private_payload_included must be false")
    if payload.get("secret_values_serialized") is not False:
        errors.append("secret_values_serialized must be false")
    if payload.get("validation_status") == "rejected" and not _text_list(payload.get("rejected_reasons")):
        errors.append("rejected proposal must include rejected_reasons")
    if payload.get("validation_status") == "accepted_as_proposal" and _text_list(payload.get("rejected_reasons")):
        errors.append("accepted proposal must not include rejected_reasons")
    if payload.get("comparison_result") == "rejected_before_comparison" and payload.get("validation_status") != "rejected":
        errors.append("rejected_before_comparison requires rejected validation_status")
    return errors


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label} failed to load: {exc}")
        return {}
    if not isinstance(parsed, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return parsed


def _text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def main(argv: list[str] | None = None) -> int:
    """Run symbolic interpretation proposal validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT_EXAMPLE)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args(argv)
    result = validate_symbolic_interpretation_proposal(path=args.path, schema_path=args.schema)
    if result.valid:
        print(f"[PASS] symbolic_interpretation_proposal status={result.validation_status}")
        print("STATUS: passed")
        return 0
    for error in result.errors:
        print(f"[FAIL] {error}")
    print("STATUS: failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
