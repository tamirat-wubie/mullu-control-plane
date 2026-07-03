#!/usr/bin/env python3
"""Validate the read-only worker runtime status read model.

Purpose: provide a deterministic operator projection that distinguishes
Foundation Mode runtime closure from live runtime authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: runtime Foundation closure summary validator and schema
validation helpers.
Invariants:
  - The read model is fixture-derived and read-only.
  - Evidence acceptance is visible without admitting runtime authority.
  - Runtime admission, promotion, enablement, dispatch, worker invocation,
    receipt emission, receipt append, live terminal closure, connector
    authority, filesystem writes, network access, and secret serialization
    remain denied.
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

from scripts.validate_read_only_worker_runtime_foundation_closure_summary import (  # noqa: E402
    build_runtime_foundation_closure_summary,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "read_only_worker_runtime_status_read_model.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "read_only_worker_runtime_status_read_model.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "read_only_worker_runtime_status_read_model_validation.json"
SOURCE_CLOSURE_SUMMARY_REF = "examples/read_only_worker_runtime_foundation_closure_summary.foundation.json"
EXPECTED_READ_MODEL_VERSION = "read_only_worker_runtime_status_read_model.v1"
EXPECTED_PROJECTION_MODE = "FOUNDATION_STATUS_PROJECTION"
REQUIRED_EVIDENCE_REFS = (
    "schemas/read_only_worker_runtime_status_read_model.schema.json",
    "examples/read_only_worker_runtime_status_read_model.foundation.json",
    "scripts/validate_read_only_worker_runtime_status_read_model.py",
    "tests/test_validate_read_only_worker_runtime_status_read_model.py",
    "examples/read_only_worker_runtime_foundation_closure_summary.foundation.json",
    "scripts/validate_read_only_worker_runtime_foundation_closure_summary.py",
    "schemas/read_only_worker_runtime_foundation_closure_summary.schema.json",
    "docs/80_read_only_worker_binding_contract.md",
)
DENIED_AUTHORITY_FIELDS = (
    "runtime_admission_allowed",
    "runtime_promotion_allowed",
    "runtime_enablement_allowed",
    "runtime_dispatch_allowed",
    "worker_invocation_allowed",
    "runtime_receipt_emission_allowed",
    "receipt_append_allowed",
    "terminal_live_closure_allowed",
    "connector_authority_allowed",
    "filesystem_write_allowed",
    "external_network_allowed",
    "secret_values_serialized",
    "success_claim_allowed",
)


@dataclass(frozen=True, slots=True)
class RuntimeStatusReadModelValidation:
    """Validation result for one runtime status read model."""

    valid: bool
    read_model_path: str
    schema_path: str
    errors: tuple[str, ...]
    foundation_closure_complete: bool
    live_runtime_blocked: bool
    runtime_admission_allowed: bool
    runtime_promotion_allowed: bool
    runtime_enablement_allowed: bool
    runtime_dispatch_allowed: bool
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_runtime_status_read_model() -> dict[str, Any]:
    """Build the Foundation Mode runtime status projection."""

    closure_summary = build_runtime_foundation_closure_summary()
    chain_refs = _string_list(closure_summary.get("chain_refs"))
    if "docs/80_read_only_worker_binding_contract.md" in chain_refs:
        docs_index = chain_refs.index("docs/80_read_only_worker_binding_contract.md")
        chain_refs.insert(docs_index, SOURCE_CLOSURE_SUMMARY_REF)
    else:
        chain_refs.append(SOURCE_CLOSURE_SUMMARY_REF)
    accepted_evidence_refs = _string_list(closure_summary.get("accepted_evidence_refs"))
    authority_denials = {field_name: False for field_name in DENIED_AUTHORITY_FIELDS}
    authority_denials["mfidel_atomicity_preserved"] = True
    return {
        "read_model_id": "read-only-worker-runtime-status-read-model-foundation",
        "read_model_version": EXPECTED_READ_MODEL_VERSION,
        "source_closure_summary_ref": SOURCE_CLOSURE_SUMMARY_REF,
        "projection_scope": {
            "projection_mode": EXPECTED_PROJECTION_MODE,
            "fixture_projection": True,
            "live_runtime_observed": False,
            "source_fixture_read_performed": True,
            "source_runtime_invocation_performed": False,
            "raw_secret_values_included": False,
        },
        "operator_status": {
            "headline": "Foundation Mode worker runtime is closed with live runtime blocked.",
            "solver_outcome": "SolvedVerified",
            "proof_state": "Pass",
            "foundation_closure_complete": True,
            "live_runtime_blocked": True,
            "status_reason": (
                "Evidence is accepted for the Foundation proof thread, but admission, promotion, "
                "enablement, dispatch, invocation, and receipt writes remain denied."
            ),
        },
        "runtime_status": {
            "evidence_acceptance_state": "accepted_for_foundation_review",
            "runtime_admission_state": "denied",
            "runtime_promotion_state": "denied_foundation_mode",
            "runtime_enablement_state": "not_executed",
            "runtime_dispatch_state": "denied",
            "receipt_append_state": "denied",
            "terminal_closure_state": "foundation_closed_not_live_terminal_closure",
        },
        "authority_denials": authority_denials,
        "chain_refs": chain_refs,
        "evidence_refs": list(REQUIRED_EVIDENCE_REFS),
        "summary": {
            "chain_ref_count": len(chain_refs),
            "accepted_evidence_ref_count": len(accepted_evidence_refs),
            "blocked_authority_count": len(DENIED_AUTHORITY_FIELDS),
            "runtime_enablement_count": 0,
            "runtime_dispatch_count": 0,
            "receipt_append_count": 0,
            "terminal_live_closure_count": 0,
        },
        "next_action": (
            "No runtime action in Foundation Mode; open a separate non-Foundation authority thread "
            "only if live runtime is explicitly requested."
        ),
    }


def validate_runtime_status_read_model(
    *,
    read_model_path: Path = DEFAULT_EXAMPLE,
    schema_path: Path = DEFAULT_SCHEMA,
) -> RuntimeStatusReadModelValidation:
    """Validate the default or supplied runtime status read model."""

    errors: list[str] = []
    schema = _load_schema(schema_path)
    read_model = _load_json_object(read_model_path, "runtime status read model", errors)
    expected_read_model = build_runtime_status_read_model()
    if read_model:
        errors.extend(_validate_schema_instance(schema, read_model))
        if read_model != expected_read_model:
            errors.append("runtime status read model does not match generated Foundation closure projection")
        _validate_semantics(read_model, errors)
    return RuntimeStatusReadModelValidation(
        valid=not errors,
        read_model_path=_path_label(read_model_path),
        schema_path=_path_label(schema_path),
        errors=tuple(errors),
        foundation_closure_complete=True,
        live_runtime_blocked=True,
        runtime_admission_allowed=False,
        runtime_promotion_allowed=False,
        runtime_enablement_allowed=False,
        runtime_dispatch_allowed=False,
        next_action=str(expected_read_model["next_action"]),
    )


def write_runtime_status_read_model_validation(
    validation: RuntimeStatusReadModelValidation,
    output_path: Path,
) -> Path:
    """Write a status read-model validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def write_runtime_status_read_model_fixture(output_path: Path) -> Path:
    """Write the generated status read-model fixture."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(build_runtime_status_read_model(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_semantics(read_model: dict[str, Any], errors: list[str]) -> None:
    projection_scope = read_model.get("projection_scope")
    if not isinstance(projection_scope, dict):
        errors.append("projection_scope must be an object")
    else:
        if projection_scope.get("projection_mode") != EXPECTED_PROJECTION_MODE:
            errors.append("projection_scope.projection_mode must be FOUNDATION_STATUS_PROJECTION")
        if projection_scope.get("source_runtime_invocation_performed") is not False:
            errors.append("projection_scope.source_runtime_invocation_performed must be false")
        if projection_scope.get("raw_secret_values_included") is not False:
            errors.append("projection_scope.raw_secret_values_included must be false")

    operator_status = read_model.get("operator_status")
    if not isinstance(operator_status, dict):
        errors.append("operator_status must be an object")
    else:
        if operator_status.get("foundation_closure_complete") is not True:
            errors.append("operator_status.foundation_closure_complete must be true")
        if operator_status.get("live_runtime_blocked") is not True:
            errors.append("operator_status.live_runtime_blocked must be true")

    authority_denials = read_model.get("authority_denials")
    if not isinstance(authority_denials, dict):
        errors.append("authority_denials must be an object")
    else:
        for field_name in DENIED_AUTHORITY_FIELDS:
            if authority_denials.get(field_name) is not False:
                errors.append(f"authority_denials.{field_name} must be false")
        if authority_denials.get("mfidel_atomicity_preserved") is not True:
            errors.append("authority_denials.mfidel_atomicity_preserved must be true")

    chain_refs = _string_list(read_model.get("chain_refs"))
    evidence_refs = _string_list(read_model.get("evidence_refs"))
    for missing_ref in sorted(set(REQUIRED_EVIDENCE_REFS) - set(evidence_refs)):
        errors.append(f"evidence_refs missing required ref: {missing_ref}")
    for chain_ref in chain_refs:
        if not (REPO_ROOT / chain_ref).exists():
            errors.append(f"chain ref missing: {chain_ref}")

    summary = read_model.get("summary")
    if not isinstance(summary, dict):
        errors.append("summary must be an object")
        return
    expected_counts = {
        "chain_ref_count": len(chain_refs),
        "accepted_evidence_ref_count": len(_string_list(build_runtime_foundation_closure_summary().get("accepted_evidence_refs"))),
        "blocked_authority_count": len(DENIED_AUTHORITY_FIELDS),
        "runtime_enablement_count": 0,
        "runtime_dispatch_count": 0,
        "receipt_append_count": 0,
        "terminal_live_closure_count": 0,
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"summary.{field_name} must match runtime status projection")


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
    """Parse status read-model validation arguments."""

    parser = argparse.ArgumentParser(description="Validate read-only worker runtime status read model.")
    parser.add_argument("--read-model", default=str(DEFAULT_EXAMPLE))
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
        write_runtime_status_read_model_fixture(Path(args.read_model))
    validation = validate_runtime_status_read_model(
        read_model_path=Path(args.read_model),
        schema_path=Path(args.schema),
    )
    if args.write:
        write_runtime_status_read_model_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("runtime status read model valid")
    else:
        print(f"runtime status read model invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
