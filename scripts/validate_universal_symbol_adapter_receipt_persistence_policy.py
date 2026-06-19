"""Validate the Universal Symbol adapter receipt persistence policy.

Purpose: prove adapter receipt persistence remains digest/ref-only and blocked
until receipt-store authority, approval, append audit, and recovery evidence
exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: persistence policy schema, foundation example, UniversalSymbol
schema, runtime admission policy, Symbol Skill Adapter, docs, and tests.
Invariants:
  - The policy is not receipt-store authority.
  - Candidate receipt evaluation may be inspected, but persistence is denied.
  - Raw payloads, raw secrets, dispatch, connector calls, writes, mutation, and
    terminal closure remain denied.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

try:
    import jsonschema
except ImportError:  # pragma: no cover - dependency is expected in CI/dev envs.
    jsonschema = None


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = REPO_ROOT / "schemas" / "universal_symbol_adapter_receipt_persistence_policy.schema.json"
DEFAULT_POLICY_PATH = REPO_ROOT / "examples" / "universal_symbol_adapter_receipt_persistence_policy.foundation.json"

AUTHORITY_DENIAL_FIELDS: tuple[str, ...] = (
    "receipt_store_append_performed",
    "raw_payload_stored",
    "raw_secret_stored",
    "runtime_dispatch_performed",
    "connector_call_performed",
    "filesystem_write_performed",
    "external_write_performed",
    "state_mutation_performed",
    "terminal_closure_allowed",
)

REQUIRED_EVIDENCE_REFS: tuple[str, ...] = (
    "schemas/universal_symbol_adapter_receipt_persistence_policy.schema.json",
    "examples/universal_symbol_adapter_receipt_persistence_policy.foundation.json",
    "schemas/universal_symbol_append_audit_witness.schema.json",
    "examples/universal_symbol_append_audit_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_path_custody_witness.schema.json",
    "examples/universal_symbol_receipt_store_path_custody_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_writer_identity_witness.schema.json",
    "examples/universal_symbol_receipt_store_writer_identity_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_writer_registration_witness.schema.json",
    "examples/universal_symbol_receipt_store_writer_registration_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
    "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_write_path_witness.schema.json",
    "examples/universal_symbol_receipt_store_write_path_witness.foundation.json",
    "schemas/universal_symbol.schema.json",
    "schemas/universal_symbol_runtime_admission_policy.schema.json",
    "mcoi/mcoi_runtime/core/symbol_skill_adapter.py",
    "docs/91_universal_symbol_kernel.md",
    "docs/92_universal_symbol_kernel_audit.md",
    "scripts/validate_universal_symbol_adapter_receipt_persistence_policy.py",
    "scripts/validate_universal_symbol_append_audit_witness.py",
    "scripts/validate_universal_symbol_receipt_store_path_custody_witness.py",
    "scripts/validate_universal_symbol_receipt_store_writer_identity_witness.py",
    "scripts/validate_universal_symbol_receipt_store_writer_registration_witness.py",
    "scripts/validate_universal_symbol_receipt_store_authority_witness.py",
    "scripts/validate_universal_symbol_receipt_store_write_path_witness.py",
    "tests/test_validate_universal_symbol_kernel.py",
    "scripts/proof_coverage_matrix.py",
    "tests/test_proof_coverage_matrix.py",
)


class UniversalSymbolAdapterReceiptPersistencePolicyError(ValueError):
    """Raised when the adapter receipt persistence policy violates Foundation Mode."""


def load_json_object(path: Path) -> dict[str, Any]:
    """Return a JSON object or raise a validation error with causal context."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UniversalSymbolAdapterReceiptPersistencePolicyError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UniversalSymbolAdapterReceiptPersistencePolicyError(f"invalid json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UniversalSymbolAdapterReceiptPersistencePolicyError(f"expected object: {path}")
    return value


def validate_universal_symbol_adapter_receipt_persistence_policy(
    policy_path: Path = DEFAULT_POLICY_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    """Validate schema shape, evidence custody, and denied persistence authority."""

    schema = load_json_object(schema_path)
    policy = load_json_object(policy_path)
    errors: list[str] = []

    _validate_schema_boundary(schema, errors)
    _validate_json_schema(policy, schema, errors)
    _validate_policy_boundary(policy, errors)
    _validate_candidate_policy(policy, errors)
    _validate_required_before_append(policy, errors)
    _validate_authority_denials(policy, errors)
    _validate_projection_sources(policy, errors)
    _validate_contract_summary(policy, errors)
    _validate_evidence_refs(policy, errors)
    _validate_evidence_ref_files(policy, errors)

    result = {
        "policy_path": _repo_relative(policy_path),
        "schema_path": _repo_relative(schema_path),
        "valid": not errors,
        "policy_id": policy.get("policy_id", ""),
        "solver_outcome": policy.get("solver_outcome", ""),
        "persistence_decision": policy.get("persistence_decision", ""),
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "projection_source_count": len(policy.get("admitted_projection_sources", []))
        if isinstance(policy.get("admitted_projection_sources"), list)
        else 0,
        "evidence_ref_count": len(policy.get("evidence_refs", []))
        if isinstance(policy.get("evidence_refs"), list)
        else 0,
        "errors": errors,
    }
    if errors:
        raise UniversalSymbolAdapterReceiptPersistencePolicyError("; ".join(errors))
    return result


def _validate_schema_boundary(schema: Mapping[str, Any], errors: list[str]) -> None:
    if schema.get("$id") != "urn:mullusi:schema:universal-symbol-adapter-receipt-persistence-policy:1":
        errors.append("schema id drift")
    if schema.get("additionalProperties") is not False:
        errors.append("schema must reject additional properties")
    required = schema.get("required")
    if not isinstance(required, list) or "authority_denials" not in required:
        errors.append("schema must require authority_denials")


def _validate_json_schema(policy: Mapping[str, Any], schema: Mapping[str, Any], errors: list[str]) -> None:
    if jsonschema is None:
        errors.append("jsonschema dependency missing")
        return
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    schema_errors = sorted(validator.iter_errors(policy), key=lambda error: tuple(error.path))
    for error in schema_errors:
        path = ".".join(str(part) for part in error.absolute_path) or "$"
        errors.append(f"schema validation failed at {path}: {error.message}")


def _validate_policy_boundary(policy: Mapping[str, Any], errors: list[str]) -> None:
    if policy.get("foundation_mode") is not True:
        errors.append("foundation_mode must remain true")
    if policy.get("policy_is_not_receipt_store_authority") is not True:
        errors.append("policy must not be receipt-store authority")
    if policy.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must remain AwaitingEvidence")
    if policy.get("persistence_decision") != "blocked_pending_receipt_store_authority":
        errors.append("persistence_decision must remain blocked")


def _validate_candidate_policy(policy: Mapping[str, Any], errors: list[str]) -> None:
    candidate = _mapping(policy.get("candidate_receipt_policy"))
    if candidate.get("candidate_receipt_evaluation_allowed") is not True:
        errors.append("candidate receipt evaluation must remain allowed")
    for field_name in (
        "candidate_receipt_persistence_allowed",
        "raw_payload_allowed",
        "raw_secret_allowed",
        "terminal_closure_ref_allowed",
    ):
        if candidate.get(field_name) is not False:
            errors.append(f"candidate_receipt_policy.{field_name} must remain false")
    for field_name in (
        "digest_and_ref_only",
        "source_ref_required",
        "schema_validation_required",
        "symbol_authority_denial_required",
    ):
        if candidate.get(field_name) is not True:
            errors.append(f"candidate_receipt_policy.{field_name} must remain true")


def _validate_required_before_append(policy: Mapping[str, Any], errors: list[str]) -> None:
    conditions = policy.get("required_before_append")
    if not isinstance(conditions, list) or not conditions:
        errors.append("required_before_append must be non-empty")
        return
    condition_ids: list[str] = []
    for condition in conditions:
        if not isinstance(condition, dict):
            errors.append("required_before_append entries must be objects")
            continue
        condition_ids.append(str(condition.get("condition_id")))
        if condition.get("decision") != "block_append":
            errors.append(f"{condition.get('condition_id')}: decision must be block_append")
        if condition.get("proof_state") not in {"Unknown", "BudgetUnknown", "Fail"}:
            errors.append(f"{condition.get('condition_id')}: proof_state must block append")
    if len(condition_ids) != len(set(condition_ids)):
        errors.append("required_before_append condition ids must be unique")


def _validate_authority_denials(policy: Mapping[str, Any], errors: list[str]) -> None:
    denials = _mapping(policy.get("authority_denials"))
    for field_name in AUTHORITY_DENIAL_FIELDS:
        if denials.get(field_name) is not False:
            errors.append(f"authority_denials.{field_name} must remain false")


def _validate_projection_sources(policy: Mapping[str, Any], errors: list[str]) -> None:
    sources = policy.get("admitted_projection_sources")
    if not isinstance(sources, list) or not sources:
        errors.append("admitted_projection_sources must be non-empty")
        return
    source_refs: list[str] = []
    for source in sources:
        if not isinstance(source, dict):
            errors.append("projection source entries must be objects")
            continue
        source_refs.append(str(source.get("source_ref")))
        if source.get("candidate_receipt_allowed") is not True:
            errors.append(f"{source.get('source_ref')}: candidate receipt evaluation must remain allowed")
        if source.get("persistence_allowed") is not False:
            errors.append(f"{source.get('source_ref')}: persistence_allowed must remain false")
        blocked_actions = set(_string_list(source.get("blocked_action_refs")))
        if not blocked_actions:
            errors.append(f"{source.get('source_ref')}: blocked action refs are required")
        if not any("terminal-closure" in action or "terminal_closure" in action for action in blocked_actions):
            errors.append(f"{source.get('source_ref')}: terminal closure must be blocked")
    if len(source_refs) != len(set(source_refs)):
        errors.append("projection source refs must be unique")


def _validate_contract_summary(policy: Mapping[str, Any], errors: list[str]) -> None:
    summary = _mapping(policy.get("contract_summary"))
    if summary.get("authority_denial_count") != len(AUTHORITY_DENIAL_FIELDS):
        errors.append("authority_denial_count drift")
    for field_name, source_name in (
        ("required_before_append_count", "required_before_append"),
        ("admitted_projection_source_count", "admitted_projection_sources"),
        ("blocked_reason_count", "blocked_reasons"),
        ("evidence_ref_count", "evidence_refs"),
    ):
        source = policy.get(source_name)
        if isinstance(source, list) and summary.get(field_name) != len(source):
            errors.append(f"{field_name} drift")


def _validate_evidence_refs(policy: Mapping[str, Any], errors: list[str]) -> None:
    refs = policy.get("evidence_refs")
    if not isinstance(refs, list):
        errors.append("evidence_refs must be a list")
        return
    missing = tuple(ref for ref in REQUIRED_EVIDENCE_REFS if ref not in refs)
    if missing:
        errors.append("missing required evidence refs: " + ", ".join(missing))


def _validate_evidence_ref_files(policy: Mapping[str, Any], errors: list[str]) -> None:
    refs = policy.get("evidence_refs")
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


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = validate_universal_symbol_adapter_receipt_persistence_policy(args.policy, args.schema)
    except UniversalSymbolAdapterReceiptPersistencePolicyError as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": str(exc).split("; ")}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_adapter_receipt_persistence_policy: {exc}")
            print("STATUS: failed")
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("[PASS] universal_symbol_adapter_receipt_persistence_policy")
        print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
