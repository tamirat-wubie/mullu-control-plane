#!/usr/bin/env python3
"""Validate Personal Assistant foundation closure packets.

Purpose: gate aggregate Personal Assistant Foundation Mode closure packets on
schema, source receipt closure, authority denials, and no-effect boundaries.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: foundation closure packet schema, collector constants, and schema helpers.
Invariants:
  - Closure requires every source receipt to be bound, SolvedVerified, and closed.
  - Source receipt kinds must match canonical source refs, schema refs, and closure fields.
  - Source receipt digests must match current checked-in source refs.
  - Source receipt schema refs must resolve and validate their source payloads.
  - Source receipt closure fields must be true in the source payloads themselves.
  - Packet IDs must bind to the current packet body.
  - The packet grants no live, connector, memory, deployment, customer, or terminal authority.
  - Secret-shaped values are rejected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.collect_personal_assistant_foundation_closure_packet import (  # noqa: E402
    AUTHORITY_DENIALS,
    DEFAULT_OUTPUT,
    NO_EFFECT_FLAGS,
    SOURCE_RECEIPTS,
)
from scripts.personal_assistant_source_digest import canonical_source_sha256  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

FOUNDATION_CLOSURE_SCHEMA_PATH = (
    REPO_ROOT / "schemas" / "personal_assistant_foundation_closure_packet.schema.json"
)
DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "personal_assistant_foundation_closure_packet_validation.json"
)
PACKET_ID_PATTERN = re.compile(r"^personal-assistant-foundation-closure-[0-9a-f]{16}$")
BLOCKED_SECRET_VALUE_MARKERS = (
    "access_token=",
    "api_key=",
    "authorization: bearer",
    "bearer ",
    "client_secret=",
    "password=",
    "private_key=",
    "-----begin private key-----",
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantFoundationClosureValidationStep:
    """One foundation closure packet validation step."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class PersonalAssistantFoundationClosureValidation:
    """Structured validation report for one foundation closure packet."""

    packet_path: str
    valid: bool
    packet_id: str
    solver_outcome: str
    foundation_closure_packet_closed: bool
    steps: tuple[PersonalAssistantFoundationClosureValidationStep, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable validation report."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def validate_personal_assistant_foundation_closure_packet(
    *,
    packet_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = FOUNDATION_CLOSURE_SCHEMA_PATH,
    require_closed: bool = False,
) -> PersonalAssistantFoundationClosureValidation:
    """Validate one Personal Assistant foundation closure packet."""
    payload = _read_packet_payload(packet_path)
    steps = (
        _check_schema_contract(payload, schema_path),
        _check_packet_id(payload),
        _check_packet_id_binding(payload),
        _check_source_receipts(payload),
        _check_source_receipt_bindings(payload),
        _check_source_receipt_digests(payload),
        _check_source_receipt_schemas(payload),
        _check_source_receipt_source_closure_fields(payload),
        _check_authority_denials(payload),
        _check_no_effect_boundary(payload),
        _check_closure_gate(payload),
        _check_secret_value_boundary(payload),
        _check_require_closed(payload, require_closed=require_closed),
    )
    summary = _object(payload.get("closure_summary"))
    return PersonalAssistantFoundationClosureValidation(
        packet_path=_bounded_packet_path(packet_path),
        valid=all(step.passed for step in steps),
        packet_id=_bounded_packet_id(payload),
        solver_outcome=_bounded_text(payload.get("solver_outcome")),
        foundation_closure_packet_closed=summary.get("foundation_closure_packet_closed") is True,
        steps=steps,
    )


def write_personal_assistant_foundation_closure_validation_report(
    validation: PersonalAssistantFoundationClosureValidation,
    output_path: Path,
) -> Path:
    """Write one local foundation closure packet validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.to_json_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _read_packet_payload(packet_path: Path) -> dict[str, Any]:
    try:
        raw_text = packet_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError("failed to read Personal Assistant foundation closure packet") from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Personal Assistant foundation closure packet returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Personal Assistant foundation closure packet was not a JSON object")
    return parsed


def _check_schema_contract(
    payload: dict[str, Any],
    schema_path: Path,
) -> PersonalAssistantFoundationClosureValidationStep:
    try:
        schema = _load_schema(schema_path)
    except OSError:
        return PersonalAssistantFoundationClosureValidationStep("schema contract", False, "schema-read-failed")
    errors = _validate_schema_instance(schema, payload)
    return PersonalAssistantFoundationClosureValidationStep(
        "schema contract",
        not errors,
        "valid" if not errors else f"schema-errors={len(errors)}",
    )


def _check_packet_id(payload: dict[str, Any]) -> PersonalAssistantFoundationClosureValidationStep:
    packet_id = payload.get("packet_id")
    passed = PACKET_ID_PATTERN.fullmatch(str(packet_id)) is not None
    return PersonalAssistantFoundationClosureValidationStep("packet id", passed, "valid" if passed else "invalid")


def _check_packet_id_binding(payload: dict[str, Any]) -> PersonalAssistantFoundationClosureValidationStep:
    packet_id = _bounded_text(payload.get("packet_id"))
    expected_packet_id = _expected_packet_id(payload)
    passed = bool(packet_id) and packet_id == expected_packet_id
    return PersonalAssistantFoundationClosureValidationStep(
        "packet id binding",
        passed,
        "body-bound" if passed else "body-mismatch",
    )


def _check_source_receipts(payload: dict[str, Any]) -> PersonalAssistantFoundationClosureValidationStep:
    records = _list_of_objects(payload.get("source_receipts"))
    required_kinds = {kind for kind, _path, _schema_ref, _closure_field in SOURCE_RECEIPTS}
    observed_kinds = {str(record.get("source_kind")) for record in records}
    closed_records = [
        record
        for record in records
        if record.get("bound") is True
        and record.get("schema_versioned") is True
        and record.get("proof_state") == "Pass"
        and record.get("solver_outcome") == "SolvedVerified"
        and record.get("closed") is True
        and record.get("no_effect_boundary_verified") is True
        and record.get("receipt_non_authoritative") is True
        and record.get("effect_violation_count") == 0
    ]
    passed = observed_kinds == required_kinds and len(closed_records) == len(SOURCE_RECEIPTS)
    return PersonalAssistantFoundationClosureValidationStep(
        "source receipts",
        passed,
        f"kinds={len(observed_kinds)}/{len(required_kinds)} closed={len(closed_records)}",
    )


def _check_source_receipt_bindings(payload: dict[str, Any]) -> PersonalAssistantFoundationClosureValidationStep:
    records = _list_of_objects(payload.get("source_receipts"))
    expected_by_kind = {
        kind: (
            _repo_relative_ref(source_path),
            schema_ref,
            closure_field,
        )
        for kind, source_path, schema_ref, closure_field in SOURCE_RECEIPTS
    }
    mismatches: list[str] = []
    missing: list[str] = []
    for record in records:
        source_kind = _bounded_text(record.get("source_kind")) or "unknown"
        expected = expected_by_kind.get(source_kind)
        if expected is None:
            missing.append(source_kind)
            continue
        expected_source_ref, expected_schema_ref, expected_closure_field = expected
        if (
            record.get("source_ref") != expected_source_ref
            or record.get("schema_ref") != expected_schema_ref
            or record.get("closure_field") != expected_closure_field
        ):
            mismatches.append(source_kind)
    passed = not mismatches and not missing and len(records) == len(SOURCE_RECEIPTS)
    detail = (
        "bindings-canonical"
        if passed
        else f"mismatches={len(mismatches)} missing={len(missing)}"
    )
    return PersonalAssistantFoundationClosureValidationStep("source receipt bindings", passed, detail)


def _check_source_receipt_digests(payload: dict[str, Any]) -> PersonalAssistantFoundationClosureValidationStep:
    records = _list_of_objects(payload.get("source_receipts"))
    mismatches: list[str] = []
    missing: list[str] = []
    for record in records:
        source_kind = _bounded_text(record.get("source_kind")) or "unknown"
        source_ref = _bounded_text(record.get("source_ref"))
        expected_digest = _bounded_text(record.get("source_sha256"))
        source_path = (REPO_ROOT / source_ref).resolve()
        if not _path_within_repo(source_path) or not source_path.exists():
            missing.append(source_kind)
            continue
        observed_digest = _file_sha256(source_path)
        if observed_digest != expected_digest:
            mismatches.append(source_kind)
    passed = not mismatches and not missing and len(records) == len(SOURCE_RECEIPTS)
    detail = (
        "digests-current"
        if passed
        else f"mismatches={len(mismatches)} missing={len(missing)}"
    )
    return PersonalAssistantFoundationClosureValidationStep("source receipt digests", passed, detail)


def _check_source_receipt_schemas(payload: dict[str, Any]) -> PersonalAssistantFoundationClosureValidationStep:
    records = _list_of_objects(payload.get("source_receipts"))
    invalid: list[str] = []
    missing: list[str] = []
    for record in records:
        source_kind = _bounded_text(record.get("source_kind")) or "unknown"
        source_ref = _bounded_text(record.get("source_ref"))
        schema_ref = _bounded_text(record.get("schema_ref"))
        if not source_ref or not schema_ref:
            missing.append(source_kind)
            continue
        source_path = (REPO_ROOT / source_ref).resolve()
        schema_path = (REPO_ROOT / schema_ref).resolve()
        if (
            not _path_within_repo(source_path)
            or not _path_within_repo(schema_path)
            or not source_path.exists()
            or not schema_path.exists()
        ):
            missing.append(source_kind)
            continue
        try:
            source_payload = _read_json_object(source_path)
            schema_payload = _load_schema(schema_path)
        except (OSError, RuntimeError, json.JSONDecodeError):
            invalid.append(source_kind)
            continue
        if _validate_schema_instance(schema_payload, source_payload):
            invalid.append(source_kind)
    passed = not invalid and not missing and len(records) == len(SOURCE_RECEIPTS)
    detail = (
        "schemas-current"
        if passed
        else f"invalid={len(invalid)} missing={len(missing)}"
    )
    return PersonalAssistantFoundationClosureValidationStep("source receipt schemas", passed, detail)


def _check_source_receipt_source_closure_fields(
    payload: dict[str, Any],
) -> PersonalAssistantFoundationClosureValidationStep:
    records = _list_of_objects(payload.get("source_receipts"))
    invalid: list[str] = []
    missing: list[str] = []
    for record in records:
        source_kind = _bounded_text(record.get("source_kind")) or "unknown"
        source_ref = _bounded_text(record.get("source_ref"))
        closure_field = _bounded_text(record.get("closure_field"))
        if not source_ref or not closure_field:
            missing.append(source_kind)
            continue
        source_path = (REPO_ROOT / source_ref).resolve()
        if not _path_within_repo(source_path) or not source_path.exists():
            missing.append(source_kind)
            continue
        try:
            source_payload = _read_json_object(source_path)
        except (OSError, RuntimeError, json.JSONDecodeError):
            invalid.append(source_kind)
            continue
        source_summary = _source_summary_object(source_payload)
        if source_summary.get(closure_field) is not True:
            invalid.append(source_kind)
    passed = not invalid and not missing and len(records) == len(SOURCE_RECEIPTS)
    detail = (
        "source-closure-fields-current"
        if passed
        else f"invalid={len(invalid)} missing={len(missing)}"
    )
    return PersonalAssistantFoundationClosureValidationStep("source receipt source closure fields", passed, detail)


def _check_authority_denials(payload: dict[str, Any]) -> PersonalAssistantFoundationClosureValidationStep:
    records = _list_of_objects(payload.get("authority_denials"))
    required = set(AUTHORITY_DENIALS)
    observed = {str(record.get("authority")) for record in records if record.get("denied") is True}
    passed = required <= observed and len(records) == len(required)
    return PersonalAssistantFoundationClosureValidationStep(
        "authority denials",
        passed,
        f"denied={len(observed)} required={len(required)}",
    )


def _check_no_effect_boundary(payload: dict[str, Any]) -> PersonalAssistantFoundationClosureValidationStep:
    boundary = _object(payload.get("no_effect_boundary"))
    flags_clear = all(value is False for value in boundary.values()) and bool(boundary)
    packet_non_authoritative = (
        payload.get("packet_is_not_execution_authority") is True
        and payload.get("packet_is_not_terminal_closure") is True
        and payload.get("packet_is_not_customer_readiness") is True
    )
    serialized = json.dumps(payload, sort_keys=True)
    flagged_terms = [flag for flag in NO_EFFECT_FLAGS if f'"{flag}": true' in serialized.casefold()]
    passed = flags_clear and packet_non_authoritative and not flagged_terms
    return PersonalAssistantFoundationClosureValidationStep(
        "no-effect boundary",
        passed,
        f"flags_clear={flags_clear} packet_non_authoritative={packet_non_authoritative}",
    )


def _check_closure_gate(payload: dict[str, Any]) -> PersonalAssistantFoundationClosureValidationStep:
    summary = _object(payload.get("closure_summary"))
    required_true = (
        "foundation_closure_packet_closed",
        "all_sources_bound",
        "all_sources_schema_versioned",
        "all_sources_solved_verified",
        "all_source_closure_flags_pass",
        "all_no_effect_boundaries_clear",
        "all_source_receipts_non_authoritative",
        "no_secret_values_serialized",
    )
    required_false = (
        "live_connector_execution_ready",
        "memory_write_ready",
        "deployment_mutation_ready",
        "customer_ready",
        "live_nested_mind_ready",
    )
    passed = (
        all(summary.get(key) is True for key in required_true)
        and all(summary.get(key) is False for key in required_false)
        and summary.get("source_receipt_count") == len(SOURCE_RECEIPTS)
        and summary.get("effect_violation_count") == 0
        and summary.get("secret_value_marker_count") == 0
        and payload.get("proof_state") == "Pass"
        and payload.get("solver_outcome") == "SolvedVerified"
    )
    return PersonalAssistantFoundationClosureValidationStep(
        "closure gate",
        passed,
        "closed" if passed else "open",
    )


def _check_secret_value_boundary(payload: dict[str, Any]) -> PersonalAssistantFoundationClosureValidationStep:
    serialized = json.dumps(payload, sort_keys=True).casefold()
    leaked_markers = [marker for marker in BLOCKED_SECRET_VALUE_MARKERS if marker in serialized]
    declared_markers = _list(payload.get("secret_value_markers"))
    passed = not leaked_markers and not declared_markers
    return PersonalAssistantFoundationClosureValidationStep(
        "secret value boundary",
        passed,
        "clean" if passed else f"blocked_markers={len(leaked_markers) + len(declared_markers)}",
    )


def _check_require_closed(
    payload: dict[str, Any],
    *,
    require_closed: bool,
) -> PersonalAssistantFoundationClosureValidationStep:
    summary = _object(payload.get("closure_summary"))
    closed = summary.get("foundation_closure_packet_closed") is True
    passed = closed or not require_closed
    return PersonalAssistantFoundationClosureValidationStep(
        "require closed",
        passed,
        "closed" if closed else "not-required" if not require_closed else "open",
    )


def _bounded_packet_id(payload: dict[str, Any]) -> str:
    packet_id = payload.get("packet_id")
    return str(packet_id) if isinstance(packet_id, str) else ""


def _expected_packet_id(payload: dict[str, Any]) -> str:
    packet_without_id = dict(payload)
    packet_without_id.pop("packet_id", None)
    material = json.dumps(
        packet_without_id,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return f"personal-assistant-foundation-closure-{hashlib.sha256(material).hexdigest()[:16]}"


def _bounded_packet_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return "provided_packet"


def _bounded_text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _path_within_repo(path: Path) -> bool:
    try:
        path.relative_to(REPO_ROOT.resolve())
    except ValueError:
        return False
    return True


def _file_sha256(path: Path) -> str:
    return canonical_source_sha256(path)


def _repo_relative_ref(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("failed to read Personal Assistant foundation closure source receipt") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Personal Assistant foundation closure source receipt must be a JSON object")
    return parsed


def _source_summary_object(payload: dict[str, Any]) -> dict[str, Any]:
    for key in (
        "summary",
        "coherence_summary",
        "authority_summary",
        "alignment_summary",
        "policy_matrix_summary",
        "runtime_boundary_summary",
        "catalog_summary",
        "closure_summary",
    ):
        summary = payload.get(key)
        if isinstance(summary, dict):
            return summary
    return {}


def _object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _list_of_objects(value: object) -> list[dict[str, Any]]:
    return [item for item in _list(value) if isinstance(item, dict)]


def main(argv: list[str] | None = None) -> int:
    """Run the Personal Assistant foundation closure packet validator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--schema", type=Path, default=FOUNDATION_CLOSURE_SCHEMA_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_VALIDATION_OUTPUT)
    parser.add_argument("--require-closed", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print validation report JSON.")
    args = parser.parse_args(argv)

    validation = validate_personal_assistant_foundation_closure_packet(
        packet_path=args.packet,
        schema_path=args.schema,
        require_closed=args.require_closed,
    )
    write_personal_assistant_foundation_closure_validation_report(validation, args.output)
    if args.json:
        print(json.dumps(validation.to_json_dict(), indent=2, sort_keys=True))
    else:
        print(f"validation_report: {_bounded_packet_path(args.output)}")
        print(f"packet: {_bounded_packet_path(args.packet)}")
        print(f"packet_id: {validation.packet_id}")
        print(f"valid: {validation.valid}")
        for step in validation.steps:
            print(f"step: {step.name} passed={step.passed} detail={step.detail}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
