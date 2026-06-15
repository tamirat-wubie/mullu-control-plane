#!/usr/bin/env python3
"""Validate the Component Harness read-model projection.

Purpose: prove the read-model route payload is schema-valid, deterministic from
the governed component harness artifacts, and non-executing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/component_read_model.schema.json,
examples/component_read_model.foundation.json, mcoi_runtime.app.component_read_model,
and scripts.validate_schemas.
Invariants:
  - The example payload equals the runtime projection from foundation sources.
  - Live execution, connector send, and terminal closure stay blocked.
  - Every component with a receipt claim is proof-bound and witness-backed.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from mcoi_runtime.app.component_read_model import (  # noqa: E402
    LIVE_AUTHORITY_FLAGS,
    READ_MODEL_ROUTE,
    build_component_read_model,
)
from scripts.validate_component_proof_binding import validate_component_proof_binding  # noqa: E402
from scripts.validate_component_lifecycle_transition_receipts import (  # noqa: E402
    validate_component_lifecycle_transition_receipts,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_read_model.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "component_read_model.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_read_model_validation.json"


@dataclass(frozen=True, slots=True)
class ComponentReadModelValidation:
    """Schema and semantic validation report for the read model."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    component_count: int
    bound_route_count: int
    proof_bound_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_read_model(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentReadModelValidation:
    """Validate the read model example against schema and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component read model schema", errors)
    example = _load_json_object(example_path, "component read model example", errors)

    proof_binding_validation = validate_component_proof_binding()
    if not proof_binding_validation.ok:
        errors.extend(
            f"component proof binding validation failed: {error}"
            for error in proof_binding_validation.errors
        )
    lifecycle_validation = validate_component_lifecycle_transition_receipts()
    if not lifecycle_validation.ok:
        errors.extend(
            f"component lifecycle transition receipt validation failed: {error}"
            for error in lifecycle_validation.errors
        )

    expected_read_model = build_component_read_model()
    if schema and example:
        errors.extend(
            f"{_path_label(example_path)}: {error}"
            for error in _validate_schema_instance(schema, example)
        )
        if example != expected_read_model:
            errors.append(f"{_path_label(example_path)}: example does not match runtime projection")
        _validate_read_model_semantics(example, errors, _path_label(example_path))

    summary = example.get("summary", {}) if isinstance(example, dict) else {}
    return ComponentReadModelValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        component_count=int(summary.get("component_count", 0)) if isinstance(summary, dict) else 0,
        bound_route_count=int(summary.get("bound_route_count", 0)) if isinstance(summary, dict) else 0,
        proof_bound_count=int(summary.get("proof_bound_count", 0)) if isinstance(summary, dict) else 0,
    )


def write_component_read_model_validation(
    validation: ComponentReadModelValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic read model validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_read_model_semantics(
    read_model: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if read_model.get("route") != READ_MODEL_ROUTE:
        errors.append(f"{label}: route must be {READ_MODEL_ROUTE}")
    if read_model.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    if read_model.get("read_model_is_not_execution_authority") is not True:
        errors.append(f"{label}: read model must not be execution authority")
    if read_model.get("live_execution_enabled") is not False:
        errors.append(f"{label}: live_execution_enabled must be false")
    if read_model.get("live_connector_send_enabled") is not False:
        errors.append(f"{label}: live_connector_send_enabled must be false")
    if read_model.get("terminal_closure_required") is not True:
        errors.append(f"{label}: terminal_closure_required must be true")

    components = read_model.get("components")
    if not isinstance(components, list):
        errors.append(f"{label}: components must be a list")
        return
    for component in components:
        if not isinstance(component, dict):
            errors.append(f"{label}: component entries must be objects")
            continue
        component_id = str(component.get("component_id", "<missing>"))
        authority = component.get("authority")
        if not isinstance(authority, dict):
            errors.append(f"{label}: component {component_id} authority must be an object")
            continue
        for flag_name in LIVE_AUTHORITY_FLAGS:
            if authority.get(flag_name) is not False:
                errors.append(f"{label}: component {component_id} authority.{flag_name} must remain false")
        blocked_actions = component.get("blocked_actions")
        if not isinstance(blocked_actions, list) or "terminal_closure" not in blocked_actions:
            errors.append(f"{label}: component {component_id} must block terminal_closure")
        if component.get("receipt_required") is True:
            proof_binding = component.get("proof_binding")
            if not isinstance(proof_binding, dict):
                errors.append(f"{label}: component {component_id} proof_binding must be an object")
            elif proof_binding.get("state") != "proof_bound":
                errors.append(f"{label}: component {component_id} receipt requires proof_bound state")
            elif int(proof_binding.get("runtime_witness_count", 0)) <= 0:
                errors.append(f"{label}: component {component_id} receipt requires runtime witnesses")
        lifecycle_receipt = component.get("lifecycle_receipt")
        if not isinstance(lifecycle_receipt, dict):
            errors.append(f"{label}: component {component_id} lifecycle_receipt must be an object")
            continue
        if lifecycle_receipt.get("to_state") != component.get("state"):
            errors.append(f"{label}: component {component_id} lifecycle receipt must target current state")
        if lifecycle_receipt.get("proof_state") != "Pass":
            errors.append(f"{label}: component {component_id} lifecycle receipt proof_state must be Pass")
        if lifecycle_receipt.get("external_effect") is not False:
            errors.append(f"{label}: component {component_id} lifecycle receipt external_effect must be false")
        if lifecycle_receipt.get("transition_is_not_execution_authority") is not True:
            errors.append(f"{label}: component {component_id} lifecycle receipt must not grant execution authority")
        if lifecycle_receipt.get("can_claim_terminal_closure") is not False:
            errors.append(f"{label}: component {component_id} lifecycle receipt cannot claim terminal closure")
        if not isinstance(lifecycle_receipt.get("evidence_refs"), list) or not lifecycle_receipt["evidence_refs"]:
            errors.append(f"{label}: component {component_id} lifecycle receipt must list evidence refs")


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
    """Parse component read model validation arguments."""

    parser = argparse.ArgumentParser(description="Validate the Component Harness read model.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for component read model validation."""

    args = parse_args(argv)
    validation = validate_component_read_model(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_read_model_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT READ MODEL VALID")
    else:
        print(f"COMPONENT READ MODEL INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
