#!/usr/bin/env python3
"""Validate Universal Symbol receipt-store lifecycle evidence bundles.

Purpose: prove lifecycle evidence bundle packets carry verifier output without
granting lifecycle recording, runtime authority, receipt append, mutation, or
terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: lifecycle evidence bundle schema/example and lifecycle evidence
ref verifier.
Invariants:
  - A bundle is a carrier, not lifecycle authority.
  - Every evidence kind appears exactly once.
  - Content-verified entries never grant authority.
  - Authority denial fields remain false.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

try:
    import jsonschema
except ImportError:  # pragma: no cover - dependency is expected in CI/dev envs.
    jsonschema = None


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.produce_universal_symbol_receipt_store_lifecycle_evidence_receipt import EVIDENCE_KINDS  # noqa: E402
from scripts.validate_universal_symbol_receipt_store_lifecycle_evidence_receipt import (  # noqa: E402
    AUTHORITY_DENIAL_FIELDS,
)


DEFAULT_SCHEMA_PATH = REPO_ROOT / "schemas" / "universal_symbol_receipt_store_lifecycle_evidence_bundle.schema.json"
DEFAULT_BUNDLE_PATH = (
    REPO_ROOT / "examples" / "universal_symbol_receipt_store_lifecycle_evidence_bundle.foundation.json"
)

CONSISTENCY_CONSTRAINT_TRUE_FIELDS: tuple[str, ...] = (
    "all_evidence_kinds_present",
    "source_receipt_validated",
    "verifier_status_bound",
    "placeholder_entries_do_not_authorize",
    "content_verified_entries_do_not_authorize",
    "authority_denials_remain_false",
    "terminal_closure_denied",
)

REQUIRED_BLOCKED_REASONS: tuple[str, ...] = (
    "lifecycle_evidence_bundle_is_not_authority",
    "receipt_store_lifecycle_recording_forbidden",
    "terminal_closure_not_allowed",
)

REQUIRED_EVIDENCE_REFS: tuple[str, ...] = (
    "schemas/universal_symbol_receipt_store_lifecycle_evidence_bundle.schema.json",
    "examples/universal_symbol_receipt_store_lifecycle_evidence_bundle.foundation.json",
    "schemas/universal_symbol_receipt_store_lifecycle_evidence_receipt.schema.json",
    "examples/universal_symbol_receipt_store_lifecycle_evidence_receipt.foundation.json",
    "scripts/validate_universal_symbol_receipt_store_lifecycle_evidence_bundle.py",
    "scripts/verify_universal_symbol_receipt_store_lifecycle_evidence_refs.py",
    "tests/test_validate_universal_symbol_receipt_store_lifecycle_evidence_bundle.py",
    "tests/test_verify_universal_symbol_receipt_store_lifecycle_evidence_refs.py",
    "scripts/proof_coverage_matrix.py",
    "tests/test_proof_coverage_matrix.py",
)


class UniversalSymbolReceiptStoreLifecycleEvidenceBundleError(ValueError):
    """Raised when a lifecycle evidence bundle violates Foundation Mode."""


def build_lifecycle_evidence_bundle_payload(
    verifier_report: Mapping[str, Any],
    *,
    source_receipt_ref: str,
    generated_at: str = "1970-01-01T00:00:00Z",
) -> dict[str, Any]:
    """Build a non-authorizing lifecycle evidence bundle from a verifier report."""

    evidence_entries = [
        {
            "evidence_kind": str(item.get("evidence_kind", "")),
            "evidence_ref": str(item.get("evidence_ref", "")),
            "placeholder_ref": item.get("placeholder_ref") is True,
            "local_file_ref": item.get("local_file_ref") is True,
            "content_verified": item.get("content_verified") is True,
            "structurally_verified": item.get("structurally_verified") is True,
            "authority_granted": False,
        }
        for item in _list_of_mappings(verifier_report.get("evidence_ref_reports"))
    ]
    placeholder_count = sum(1 for item in evidence_entries if item["placeholder_ref"])
    content_verified_count = sum(1 for item in evidence_entries if item["content_verified"])
    blocked_reasons = [
        "lifecycle_evidence_bundle_is_not_authority",
        "receipt_store_lifecycle_recording_forbidden",
        "terminal_closure_not_allowed",
        "source_receipt_still_awaiting_evidence",
    ]
    if placeholder_count:
        blocked_reasons.append("placeholder_lifecycle_evidence_remaining")
    return {
        "bundle_id": "universal-symbol-receipt-store-lifecycle-evidence-bundle-foundation",
        "schema_version": 1,
        "generated_at": generated_at,
        "bundle_scope": "foundation-mode-universal-symbol-receipt-store-lifecycle-evidence-bundle",
        "solver_outcome": "AwaitingEvidence",
        "foundation_mode": True,
        "bundle_decision": "blocked_non_authorizing_lifecycle_evidence_bundle",
        "bundle_is_not_lifecycle_authority": True,
        "source_receipt_ref": source_receipt_ref,
        "verifier_status": str(verifier_report.get("status", "")),
        "evidence_entries": evidence_entries,
        "bundle_consistency_constraints": {
            "all_evidence_kinds_present": True,
            "source_receipt_validated": bool(_mapping(verifier_report.get("schema_validation")).get("valid")),
            "verifier_status_bound": True,
            "placeholder_entries_do_not_authorize": True,
            "content_verified_entries_do_not_authorize": True,
            "authority_denials_remain_false": True,
            "terminal_closure_denied": True,
        },
        "authority_denials": {field_name: False for field_name in AUTHORITY_DENIAL_FIELDS},
        "blocked_reasons": blocked_reasons,
        "next_actions": [
            "bind_bundle_to_non_authorizing_operator_read_model",
            "collect_live_lifecycle_evidence_content_witnesses",
        ],
        "evidence_refs": list(REQUIRED_EVIDENCE_REFS),
        "contract_summary": {
            "evidence_entry_count": len(evidence_entries),
            "content_verified_entry_count": content_verified_count,
            "placeholder_entry_count": placeholder_count,
            "consistency_constraint_count": len(CONSISTENCY_CONSTRAINT_TRUE_FIELDS),
            "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
            "blocked_reason_count": len(blocked_reasons),
            "evidence_ref_count": len(REQUIRED_EVIDENCE_REFS),
        },
    }


def validate_universal_symbol_receipt_store_lifecycle_evidence_bundle(
    bundle_path: Path = DEFAULT_BUNDLE_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    """Validate schema shape, evidence coverage, and denied authority."""

    schema = load_json_object(schema_path)
    bundle = load_json_object(bundle_path)
    errors: list[str] = []

    _validate_schema_boundary(schema, errors)
    _validate_json_schema(bundle, schema, errors)
    _validate_bundle_boundary(bundle, errors)
    _validate_evidence_entries(bundle, errors)
    _validate_consistency_constraints(bundle, errors)
    _validate_authority_denials(bundle, errors)
    _validate_blocked_reasons(bundle, errors)
    _validate_contract_summary(bundle, errors)
    _validate_evidence_refs(bundle, errors)
    _validate_evidence_ref_files(bundle, errors)

    report = {
        "bundle_path": _repo_relative(bundle_path),
        "schema_path": _repo_relative(schema_path),
        "valid": not errors,
        "bundle_id": bundle.get("bundle_id", ""),
        "solver_outcome": bundle.get("solver_outcome", ""),
        "verifier_status": bundle.get("verifier_status", ""),
        "evidence_entry_count": _list_len(bundle.get("evidence_entries")) or 0,
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "evidence_ref_count": _list_len(bundle.get("evidence_refs")) or 0,
        "errors": errors,
    }
    if errors:
        raise UniversalSymbolReceiptStoreLifecycleEvidenceBundleError("; ".join(errors))
    return report


def load_json_object(path: Path) -> dict[str, Any]:
    """Return a JSON object or raise a validation error with causal context."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UniversalSymbolReceiptStoreLifecycleEvidenceBundleError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UniversalSymbolReceiptStoreLifecycleEvidenceBundleError(f"invalid json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UniversalSymbolReceiptStoreLifecycleEvidenceBundleError(f"expected object: {path}")
    return value


def _validate_schema_boundary(schema: Mapping[str, Any], errors: list[str]) -> None:
    if schema.get("$id") != "urn:mullusi:schema:universal-symbol-receipt-store-lifecycle-evidence-bundle:1":
        errors.append("schema id drift")
    if schema.get("additionalProperties") is not False:
        errors.append("schema must reject additional properties")


def _validate_json_schema(bundle: Mapping[str, Any], schema: Mapping[str, Any], errors: list[str]) -> None:
    if jsonschema is None:
        errors.append("jsonschema dependency missing")
        return
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    schema_errors = sorted(validator.iter_errors(bundle), key=lambda error: tuple(error.path))
    for error in schema_errors:
        path = ".".join(str(part) for part in error.absolute_path) or "$"
        errors.append(f"schema validation failed at {path}: {error.message}")


def _validate_bundle_boundary(bundle: Mapping[str, Any], errors: list[str]) -> None:
    if bundle.get("foundation_mode") is not True:
        errors.append("foundation_mode must remain true")
    if bundle.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must remain AwaitingEvidence")
    if bundle.get("bundle_decision") != "blocked_non_authorizing_lifecycle_evidence_bundle":
        errors.append("bundle_decision must remain blocked")
    if bundle.get("bundle_is_not_lifecycle_authority") is not True:
        errors.append("bundle must not be lifecycle authority")


def _validate_evidence_entries(bundle: Mapping[str, Any], errors: list[str]) -> None:
    entries = bundle.get("evidence_entries")
    if not isinstance(entries, list) or not entries:
        errors.append("evidence_entries must be non-empty")
        return
    evidence_kinds: list[str] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            errors.append("evidence_entries must contain objects")
            continue
        evidence_kinds.append(str(entry.get("evidence_kind", "")))
        if entry.get("authority_granted") is not False:
            errors.append(f"{entry.get('evidence_kind')}: authority_granted must remain false")
        if entry.get("placeholder_ref") is True and entry.get("content_verified") is True:
            errors.append(f"{entry.get('evidence_kind')}: placeholder ref cannot be content verified")
        if entry.get("content_verified") is True and entry.get("local_file_ref") is not True:
            errors.append(f"{entry.get('evidence_kind')}: content verified requires local file ref")
        if entry.get("content_verified") is True and entry.get("structurally_verified") is not True:
            errors.append(f"{entry.get('evidence_kind')}: content verified requires structural verification")
    _require_members("evidence_entries", evidence_kinds, EVIDENCE_KINDS, errors)


def _validate_consistency_constraints(bundle: Mapping[str, Any], errors: list[str]) -> None:
    constraints = _mapping(bundle.get("bundle_consistency_constraints"))
    for field_name in CONSISTENCY_CONSTRAINT_TRUE_FIELDS:
        if constraints.get(field_name) is not True:
            errors.append(f"bundle_consistency_constraints.{field_name} must remain true")


def _validate_authority_denials(bundle: Mapping[str, Any], errors: list[str]) -> None:
    denials = _mapping(bundle.get("authority_denials"))
    for field_name in AUTHORITY_DENIAL_FIELDS:
        if denials.get(field_name) is not False:
            errors.append(f"authority_denials.{field_name} must remain false")


def _validate_blocked_reasons(bundle: Mapping[str, Any], errors: list[str]) -> None:
    blocked_reasons = bundle.get("blocked_reasons")
    if not isinstance(blocked_reasons, list):
        errors.append("blocked_reasons must be a list")
        return
    _require_members("blocked_reasons", [item for item in blocked_reasons if isinstance(item, str)], REQUIRED_BLOCKED_REASONS, errors)


def _validate_contract_summary(bundle: Mapping[str, Any], errors: list[str]) -> None:
    summary = _mapping(bundle.get("contract_summary"))
    entries = [entry for entry in _list_of_mappings(bundle.get("evidence_entries"))]
    observed_counts = {
        "evidence_entry_count": len(entries),
        "content_verified_entry_count": sum(1 for entry in entries if entry.get("content_verified") is True),
        "placeholder_entry_count": sum(1 for entry in entries if entry.get("placeholder_ref") is True),
        "consistency_constraint_count": len(CONSISTENCY_CONSTRAINT_TRUE_FIELDS),
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "blocked_reason_count": _list_len(bundle.get("blocked_reasons")),
        "evidence_ref_count": _list_len(bundle.get("evidence_refs")),
    }
    for field_name, observed_count in observed_counts.items():
        if observed_count is not None and summary.get(field_name) != observed_count:
            errors.append(f"{field_name} drift")


def _validate_evidence_refs(bundle: Mapping[str, Any], errors: list[str]) -> None:
    refs = bundle.get("evidence_refs")
    if not isinstance(refs, list):
        errors.append("evidence_refs must be a list")
        return
    missing = tuple(ref for ref in REQUIRED_EVIDENCE_REFS if ref not in refs)
    if missing:
        errors.append("missing required evidence refs: " + ", ".join(missing))


def _validate_evidence_ref_files(bundle: Mapping[str, Any], errors: list[str]) -> None:
    refs = bundle.get("evidence_refs")
    if not isinstance(refs, list):
        return
    for ref in refs:
        if not isinstance(ref, str) or "://" in ref:
            continue
        ref_path = Path(ref)
        if ref_path.is_absolute():
            errors.append(f"evidence ref must be repository-relative: {ref}")
            continue
        resolved = (REPO_ROOT / ref_path).resolve()
        if REPO_ROOT.resolve() not in resolved.parents and resolved != REPO_ROOT.resolve():
            errors.append(f"evidence ref escapes repository: {ref}")
            continue
        if not resolved.exists():
            errors.append(f"evidence ref file missing: {ref}")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list_of_mappings(value: Any) -> list[Mapping[str, Any]]:
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _list_len(value: Any) -> int | None:
    return len(value) if isinstance(value, list) else None


def _require_members(
    field_name: str,
    observed_values: list[str],
    required_values: tuple[str, ...],
    errors: list[str],
) -> None:
    for missing_value in sorted(set(required_values) - set(observed_values)):
        errors.append(f"{field_name} missing required value: {missing_value}")
    if len(observed_values) != len(set(observed_values)):
        errors.append(f"{field_name} values must be unique")


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = validate_universal_symbol_receipt_store_lifecycle_evidence_bundle(
            args.bundle,
            args.schema,
        )
    except UniversalSymbolReceiptStoreLifecycleEvidenceBundleError as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": str(exc).split("; ")}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_receipt_store_lifecycle_evidence_bundle: {exc}")
            print("STATUS: failed")
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("[PASS] universal_symbol_receipt_store_lifecycle_evidence_bundle")
        print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
