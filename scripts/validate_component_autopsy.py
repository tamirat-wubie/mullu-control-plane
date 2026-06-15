#!/usr/bin/env python3
"""Validate Component Harness autopsy artifacts.

Purpose: prove component autopsy views are schema-valid, deterministic from the
read model and lifecycle receipts, and denied execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/component_autopsy.schema.json,
examples/component_autopsy.nested_mind_bridge.json,
mcoi_runtime.app.component_autopsy, and component harness validators.
Invariants:
  - The example payload equals the runtime autopsy for its component.
  - Every foundation component autopsy keeps live authority false.
  - Missing proof, witness, approval, or lifecycle evidence is explicit.
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

from mcoi_runtime.app.component_autopsy import (  # noqa: E402
    build_component_autopsy,
    build_foundation_component_autopsies,
)
from scripts.validate_component_lifecycle_transition_receipts import (  # noqa: E402
    validate_component_lifecycle_transition_receipts,
)
from scripts.validate_component_read_model import validate_component_read_model  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_autopsy.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "component_autopsy.nested_mind_bridge.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_autopsy_validation.json"
LIVE_FALSE_FIELDS = (
    "live_execution_enabled",
    "live_connector_send_enabled",
    "can_execute",
    "can_mutate",
    "can_call_connector",
    "can_write_files",
    "can_send_external_message",
    "can_claim_terminal_closure",
)


@dataclass(frozen=True, slots=True)
class ComponentAutopsyValidation:
    """Schema and semantic validation report for component autopsy views."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    autopsy_count: int
    awaiting_evidence_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_autopsy(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentAutopsyValidation:
    """Validate the autopsy schema, example, and foundation projections."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component autopsy schema", errors)
    example = _load_json_object(example_path, "component autopsy example", errors)

    read_model_validation = validate_component_read_model()
    if not read_model_validation.ok:
        errors.extend(f"component read model validation failed: {error}" for error in read_model_validation.errors)
    lifecycle_validation = validate_component_lifecycle_transition_receipts()
    if not lifecycle_validation.ok:
        errors.extend(
            f"component lifecycle transition receipt validation failed: {error}"
            for error in lifecycle_validation.errors
        )

    autopsies = build_foundation_component_autopsies()
    if schema and example:
        errors.extend(
            f"{_path_label(example_path)}: {error}"
            for error in _validate_schema_instance(schema, example)
        )
        expected_example = build_component_autopsy(str(example.get("component_id", "")))
        if example != expected_example:
            errors.append(f"{_path_label(example_path)}: example does not match runtime autopsy")
        _validate_autopsy_semantics(example, errors, _path_label(example_path))

    for index, autopsy in enumerate(autopsies):
        errors.extend(f"foundation autopsy {index}: {error}" for error in _validate_schema_instance(schema, autopsy))
        _validate_autopsy_semantics(autopsy, errors, f"foundation autopsy {index}")

    return ComponentAutopsyValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        autopsy_count=len(autopsies),
        awaiting_evidence_count=sum(1 for autopsy in autopsies if autopsy.get("outcome") == "AwaitingEvidence"),
    )


def write_component_autopsy_validation(
    validation: ComponentAutopsyValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic autopsy validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_autopsy_semantics(
    autopsy: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if autopsy.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    if autopsy.get("autopsy_is_not_execution_authority") is not True:
        errors.append(f"{label}: autopsy must not be execution authority")
    for field_name in LIVE_FALSE_FIELDS:
        if autopsy.get(field_name) is not False:
            errors.append(f"{label}: {field_name} must be false")
    if autopsy.get("terminal_closure_required") is not True:
        errors.append(f"{label}: terminal_closure_required must be true")
    forbidden_actions = _string_list(autopsy.get("forbidden_actions"))
    if "terminal_closure" not in forbidden_actions:
        errors.append(f"{label}: forbidden_actions must include terminal_closure")
    blockers = autopsy.get("blockers")
    if not isinstance(blockers, list) or not blockers:
        errors.append(f"{label}: blockers must be non-empty")
    expected_receipts = _string_list(autopsy.get("expected_receipts"))
    if "authority_denial_receipt" not in expected_receipts:
        errors.append(f"{label}: expected_receipts must include authority_denial_receipt")
    for candidate in autopsy.get("next_transition_candidates", []):
        if not isinstance(candidate, dict):
            errors.append(f"{label}: transition candidates must be objects")
            continue
        if candidate.get("external_effect") is not False:
            errors.append(f"{label}: transition candidate external_effect must be false")
        if candidate.get("transition_is_not_authority") is not True:
            errors.append(f"{label}: transition candidate must not be authority")
        if candidate.get("to_state") == "approved_live_action":
            errors.append(f"{label}: transition candidate cannot target approved_live_action")
    if autopsy.get("component_id") == "nested_mind_bridge":
        missing_evidence = set(_string_list(autopsy.get("missing_evidence")))
        for required_gap in ("proof_matrix_surface", "memory_topology_activation_witness"):
            if required_gap not in missing_evidence:
                errors.append(f"{label}: nested_mind_bridge missing_evidence must include {required_gap}")


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


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse component autopsy validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness autopsy views.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for component autopsy validation."""

    args = parse_args(argv)
    validation = validate_component_autopsy(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_autopsy_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT AUTOPSY VALID")
    else:
        print(f"COMPONENT AUTOPSY INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
