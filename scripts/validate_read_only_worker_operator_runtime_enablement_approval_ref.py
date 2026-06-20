#!/usr/bin/env python3
"""Validate read-only worker operator runtime enablement approval refs.

Purpose: verify Foundation Mode operator approval references for future
read-only worker runtime enablement review without granting runtime authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schema validation helpers and the operator approval ref schema.
Invariants:
  - The approval ref is evidence only, not acceptance or authorization.
  - Runtime enablement, dispatch, worker invocation, receipt emission, receipt
    append, terminal closure, network, filesystem writes, connector authority,
    and secret serialization remain denied.
  - Evidence acceptance and runtime admission remain separate future gates.
  - Mfidel atomicity is preserved.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_read_only_worker_runtime_enablement_evidence_request_status_ledger import (  # noqa: E402
    BLOCKED_ACTIONS,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "read_only_worker_operator_runtime_enablement_approval_ref.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "read_only_worker_operator_runtime_enablement_approval_ref.foundation.json"
DENIED_FIELDS = (
    "runtime_enablement_allowed",
    "runtime_dispatch_allowed",
    "worker_invocation_allowed",
    "runtime_receipt_emission_allowed",
    "receipt_append_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
    "secret_values_serialized",
    "external_network_allowed",
    "filesystem_write_allowed",
    "connector_authority_allowed",
    "raw_secret_value_present",
)


def validate_operator_runtime_enablement_approval_ref(
    *,
    approval_ref_path: Path = DEFAULT_EXAMPLE,
    schema_path: Path = DEFAULT_SCHEMA,
) -> list[str]:
    """Return deterministic validation errors for one approval ref."""

    schema = _load_schema(schema_path)
    approval_ref = _load_json_object(approval_ref_path, "operator runtime enablement approval ref")
    return validate_operator_runtime_enablement_approval_ref_record(approval_ref, schema)


def validate_operator_runtime_enablement_approval_ref_record(
    approval_ref: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one approval ref record."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA)
    errors = _validate_schema_instance(schema_payload, approval_ref)
    if not isinstance(approval_ref, dict):
        errors.append("operator runtime enablement approval ref must be a JSON object")
        return errors
    if approval_ref.get("approval_ref_bound") is not True:
        errors.append("approval_ref_bound must be true")
    for field_name in (
        "approval_ref_is_not_acceptance",
        "approval_ref_is_not_authorization",
        "approval_ref_is_not_runtime_enablement",
    ):
        if approval_ref.get(field_name) is not True:
            errors.append(f"{field_name} must be true")
    for field_name in DENIED_FIELDS:
        if approval_ref.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    if set(_string_list(approval_ref.get("blocked_actions"))) != set(BLOCKED_ACTIONS):
        errors.append("blocked_actions must match runtime enablement blocked actions")
    approval_scope = approval_ref.get("approval_scope")
    if not isinstance(approval_scope, dict):
        errors.append("approval_scope must be an object")
    else:
        _validate_approval_scope(approval_scope, errors)
    return errors


def build_mutated_operator_runtime_enablement_approval_ref(**overrides: Any) -> dict[str, Any]:
    """Return a deep-copied approval ref fixture with simple overrides."""

    record = _load_json_object(DEFAULT_EXAMPLE, "operator runtime enablement approval ref")
    mutated = deepcopy(record)
    for key, value in overrides.items():
        mutated[key] = value
    return mutated


def _validate_approval_scope(approval_scope: dict[str, Any], errors: list[str]) -> None:
    if approval_scope.get("approval_ref_bound") is not True:
        errors.append("approval_scope.approval_ref_bound must be true")
    if approval_scope.get("evidence_acceptance_required") is not True:
        errors.append("approval_scope.evidence_acceptance_required must be true")
    if approval_scope.get("runtime_admission_required") is not True:
        errors.append("approval_scope.runtime_admission_required must be true")
    if approval_scope.get("required_name") != "MULLU_READ_ONLY_WORKER_RUNTIME_ENABLEMENT_APPROVAL_REF":
        errors.append("approval_scope.required_name must match operator approval input name")


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except OSError as exc:
        raise RuntimeError(f"{label} file missing: {path}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"{label} JSON parse failed") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} JSON root must be an object")
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


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description="Validate read-only worker operator runtime enablement approval ref.")
    parser.add_argument("--approval-ref", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    errors = validate_operator_runtime_enablement_approval_ref(
        approval_ref_path=Path(args.approval_ref),
        schema_path=Path(args.schema),
    )
    if args.json:
        print(
            json.dumps(
                {
                    "status": "passed" if not errors else "failed",
                    "approval_ref_path": _path_label(Path(args.approval_ref)),
                    "schema_path": _path_label(Path(args.schema)),
                    "errors": errors,
                    "runtime_enablement_allowed": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif errors:
        print(f"operator runtime enablement approval ref invalid errors={errors}")
    else:
        print("operator runtime enablement approval ref valid")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
