#!/usr/bin/env python3
"""Validate capability closure runner artifacts.

Purpose: prove capability closure artifacts match schemas, runtime projection,
and no-authority semantic constraints.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/capability_closure_plan.schema.json,
schemas/missing_evidence_refs.schema.json, schemas/next_approval_action.schema.json,
schemas/closure_receipt.schema.json, and mcoi/capability_closure/runner.py.
Invariants:
  - The selected capability and debt item are consistent across all artifacts.
  - Missing refs match the selected debt item and category view.
  - Approval actions do not authorize execution after approval.
  - Closure receipts remain AwaitingEvidence and not execution authority.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from capability_closure.runner import (  # noqa: E402
    ARTIFACT_FILENAMES,
    EXAMPLE_ARTIFACT_FILENAMES,
    build_capability_closure_artifacts,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMAS = {
    "capability_closure_plan": REPO_ROOT / "schemas" / "capability_closure_plan.schema.json",
    "missing_evidence_refs": REPO_ROOT / "schemas" / "missing_evidence_refs.schema.json",
    "next_approval_action": REPO_ROOT / "schemas" / "next_approval_action.schema.json",
    "closure_receipt": REPO_ROOT / "schemas" / "closure_receipt.schema.json",
}
DEFAULT_ARTIFACTS = {
    key: REPO_ROOT / "examples" / filename
    for key, filename in EXAMPLE_ARTIFACT_FILENAMES.items()
}
DEFAULT_GENERATED_ARTIFACTS = {
    key: REPO_ROOT / ".change_assurance" / filename
    for key, filename in ARTIFACT_FILENAMES.items()
}
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "capability_closure_runner_validation.json"
REQUIRED_VALIDATOR_COMMANDS = {
    "capability_closure_runner_validator": "python scripts/validate_capability_closure_runner.py --strict",
    "capability_closure_runner_tests": (
        "python -m pytest tests/test_capability_closure_runner.py "
        "tests/test_validate_capability_closure_runner.py -q"
    ),
}


@dataclass(frozen=True, slots=True)
class CapabilityClosureRunnerValidation:
    """Validation report for capability closure runner artifacts."""

    ok: bool
    errors: tuple[str, ...]
    selected_capability_id: str
    selected_debt_id: str
    missing_ref_count: int
    status: str
    artifact_paths: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation report."""

        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_capability_closure_runner(
    *,
    artifact_paths: Mapping[str, Path] = DEFAULT_ARTIFACTS,
    schema_paths: Mapping[str, Path] = DEFAULT_SCHEMAS,
    artifact_filenames: Mapping[str, str] = EXAMPLE_ARTIFACT_FILENAMES,
    compare_runtime_projection: bool = True,
) -> CapabilityClosureRunnerValidation:
    """Validate the four capability closure artifacts."""

    errors: list[str] = []
    schemas = {
        key: _load_json_object(path, f"{key} schema", errors)
        for key, path in schema_paths.items()
    }
    artifacts = {
        key: _load_json_object(path, f"{key} artifact", errors)
        for key, path in artifact_paths.items()
    }
    for key, artifact in artifacts.items():
        schema = schemas.get(key, {})
        if schema and artifact:
            errors.extend(f"{key}: {error}" for error in _validate_schema_instance(schema, artifact))

    if compare_runtime_projection and not errors:
        runtime_artifacts = build_capability_closure_artifacts(artifact_filenames=artifact_filenames)
        for key, runtime_payload in runtime_artifacts.items():
            if artifacts.get(key) != runtime_payload:
                errors.append(f"{key}: artifact does not match runtime projection")

    if all(artifacts.values()):
        _validate_semantics(
            plan=artifacts["capability_closure_plan"],
            missing_refs=artifacts["missing_evidence_refs"],
            next_approval=artifacts["next_approval_action"],
            closure_receipt=artifacts["closure_receipt"],
            artifact_filenames=artifact_filenames,
            errors=errors,
        )

    plan = artifacts.get("capability_closure_plan", {})
    refs = artifacts.get("missing_evidence_refs", {})
    receipt = artifacts.get("closure_receipt", {})
    return CapabilityClosureRunnerValidation(
        ok=not errors,
        errors=tuple(errors),
        selected_capability_id=str(plan.get("selected_capability_id", "")) if isinstance(plan, dict) else "",
        selected_debt_id=str(plan.get("selected_debt_id", "")) if isinstance(plan, dict) else "",
        missing_ref_count=int(refs.get("selected_missing_ref_count", 0)) if isinstance(refs, dict) else 0,
        status=str(receipt.get("status", "")) if isinstance(receipt, dict) else "",
        artifact_paths={
            key: _path_label(path)
            for key, path in artifact_paths.items()
        },
    )


def write_capability_closure_runner_validation(
    validation: CapabilityClosureRunnerValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic capability closure validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_semantics(
    *,
    plan: Mapping[str, Any],
    missing_refs: Mapping[str, Any],
    next_approval: Mapping[str, Any],
    closure_receipt: Mapping[str, Any],
    artifact_filenames: Mapping[str, str],
    errors: list[str],
) -> None:
    capability_id = str(plan.get("selected_capability_id", ""))
    debt_id = str(plan.get("selected_debt_id", ""))
    for artifact_name, artifact in (
        ("missing_evidence_refs", missing_refs),
        ("next_approval_action", next_approval),
        ("closure_receipt", closure_receipt),
    ):
        if artifact.get("selected_capability_id") != capability_id:
            errors.append(f"{artifact_name}: selected_capability_id must match plan")
        if artifact.get("selected_debt_id") != debt_id:
            errors.append(f"{artifact_name}: selected_debt_id must match plan")

    _validate_no_authority(plan, "plan", "plan_is_not_execution_authority", errors)
    _validate_no_authority(missing_refs, "missing_refs", "refs_are_not_execution_authority", errors)
    _validate_no_authority(next_approval, "next_approval", "approval_action_is_not_execution_authority", errors)
    _validate_no_authority(closure_receipt, "closure_receipt", "closure_receipt_is_not_execution_authority", errors)
    _validate_selected_refs(plan, missing_refs, errors)
    _validate_next_approval(next_approval, missing_refs, errors)
    _validate_receipt(closure_receipt, artifact_filenames, errors)
    _validate_validators(plan, "plan", errors)
    _validate_validators(closure_receipt, "closure_receipt", errors)


def _validate_no_authority(
    artifact: Mapping[str, Any],
    label: str,
    authority_field: str,
    errors: list[str],
) -> None:
    if artifact.get(authority_field) is not True:
        errors.append(f"{label}: {authority_field} must be true")
    if artifact.get("live_execution_enabled") is not False:
        errors.append(f"{label}: live_execution_enabled must be false")


def _validate_selected_refs(
    plan: Mapping[str, Any],
    missing_refs: Mapping[str, Any],
    errors: list[str],
) -> None:
    selected_item = plan.get("selected_debt_item")
    if not isinstance(selected_item, Mapping):
        errors.append("plan: selected_debt_item must be an object")
        return
    selected_refs = _string_list(selected_item.get("missing_refs"))
    if missing_refs.get("selected_missing_refs") != selected_refs:
        errors.append("missing_refs: selected_missing_refs must match selected debt item")
    if missing_refs.get("selected_missing_ref_count") != len(selected_refs):
        errors.append("missing_refs: selected_missing_ref_count must match selected refs")
    category = str(plan.get("selected_category", ""))
    refs_by_category = missing_refs.get("missing_refs_by_category")
    if isinstance(refs_by_category, Mapping):
        if refs_by_category.get(category) != selected_refs:
            errors.append("missing_refs: selected category refs must match selected refs")
    lane = plan.get("closure_lane")
    if isinstance(lane, Mapping) and lane.get("missing_ref_count") != len(selected_refs):
        errors.append("plan: closure_lane missing_ref_count must match selected refs")


def _validate_next_approval(
    next_approval: Mapping[str, Any],
    missing_refs: Mapping[str, Any],
    errors: list[str],
) -> None:
    approval_refs = _string_list(missing_refs.get("approval_refs"))
    if next_approval.get("approval_required") != bool(approval_refs):
        errors.append("next_approval: approval_required must match approval refs")
    if next_approval.get("missing_approval_refs") != approval_refs:
        errors.append("next_approval: missing_approval_refs must match approval refs")
    if next_approval.get("blocked_until_refs_present") != approval_refs:
        errors.append("next_approval: blocked_until_refs_present must match approval refs")
    if next_approval.get("execution_after_approval_allowed") is not False:
        errors.append("next_approval: execution_after_approval_allowed must be false")
    if "gate.approval.required" in approval_refs and not next_approval.get("operator_review_required"):
        errors.append("next_approval: operator review required for approval gate")


def _validate_receipt(
    closure_receipt: Mapping[str, Any],
    artifact_filenames: Mapping[str, str],
    errors: list[str],
) -> None:
    if closure_receipt.get("status") != "AwaitingEvidence":
        errors.append("closure_receipt: status must be AwaitingEvidence")
    if closure_receipt.get("closure_claim") != "not_closed":
        errors.append("closure_receipt: closure_claim must be not_closed")
    if closure_receipt.get("proof_state") != "Unknown":
        errors.append("closure_receipt: proof_state must be Unknown")
    if closure_receipt.get("artifacts") != dict(artifact_filenames):
        errors.append("closure_receipt: artifacts must match expected filenames")
    effect_boundary = closure_receipt.get("effect_boundary")
    if not isinstance(effect_boundary, Mapping):
        errors.append("closure_receipt: effect_boundary must be an object")
        return
    enabled_effects = sorted(key for key, value in effect_boundary.items() if value is not False)
    if enabled_effects:
        errors.append(f"closure_receipt: effect boundary must remain false for {enabled_effects}")
    causal_trace = closure_receipt.get("causal_trace")
    if not isinstance(causal_trace, list) or len(causal_trace) < 4:
        errors.append("closure_receipt: causal_trace must include at least four steps")


def _validate_validators(
    artifact: Mapping[str, Any],
    label: str,
    errors: list[str],
) -> None:
    validators = artifact.get("validators")
    if not isinstance(validators, list):
        errors.append(f"{label}: validators must be a list")
        return
    validator_by_id = {
        str(validator.get("validator_id", "")): validator
        for validator in validators
        if isinstance(validator, Mapping)
    }
    for validator_id, expected_command in REQUIRED_VALIDATOR_COMMANDS.items():
        validator = validator_by_id.get(validator_id)
        if validator is None:
            errors.append(f"{label}: missing validator {validator_id}")
            continue
        if validator.get("command") != expected_command:
            errors.append(f"{label}: validator {validator_id} command drift")
        if validator.get("required_for_closure") is not True:
            errors.append(f"{label}: validator {validator_id} must be required_for_closure")


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


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse capability closure validation arguments."""

    parser = argparse.ArgumentParser(description="Validate capability closure runner artifacts.")
    parser.add_argument("--plan", default=str(DEFAULT_ARTIFACTS["capability_closure_plan"]))
    parser.add_argument("--missing-refs", default=str(DEFAULT_ARTIFACTS["missing_evidence_refs"]))
    parser.add_argument("--next-approval", default=str(DEFAULT_ARTIFACTS["next_approval_action"]))
    parser.add_argument("--receipt", default=str(DEFAULT_ARTIFACTS["closure_receipt"]))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--generated-names", action="store_true")
    parser.add_argument("--skip-runtime-compare", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def resolve_artifact_paths(args: argparse.Namespace) -> dict[str, Path]:
    """Resolve artifact paths, using generated defaults when requested."""

    raw_paths = {
        "capability_closure_plan": Path(args.plan),
        "missing_evidence_refs": Path(args.missing_refs),
        "next_approval_action": Path(args.next_approval),
        "closure_receipt": Path(args.receipt),
    }
    if not args.generated_names:
        return raw_paths
    default_path_args = {
        "capability_closure_plan": Path(str(DEFAULT_ARTIFACTS["capability_closure_plan"])),
        "missing_evidence_refs": Path(str(DEFAULT_ARTIFACTS["missing_evidence_refs"])),
        "next_approval_action": Path(str(DEFAULT_ARTIFACTS["next_approval_action"])),
        "closure_receipt": Path(str(DEFAULT_ARTIFACTS["closure_receipt"])),
    }
    return {
        key: DEFAULT_GENERATED_ARTIFACTS[key] if path == default_path_args[key] else path
        for key, path in raw_paths.items()
    }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for capability closure runner validation."""

    args = parse_args(argv)
    artifact_paths = resolve_artifact_paths(args)
    artifact_filenames = ARTIFACT_FILENAMES if args.generated_names else EXAMPLE_ARTIFACT_FILENAMES
    validation = validate_capability_closure_runner(
        artifact_paths=artifact_paths,
        artifact_filenames=artifact_filenames,
        compare_runtime_projection=not args.skip_runtime_compare,
    )
    write_capability_closure_runner_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("CAPABILITY CLOSURE RUNNER VALID")
    else:
        print(f"CAPABILITY CLOSURE RUNNER INVALID errors={list(validation.errors)}")
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
