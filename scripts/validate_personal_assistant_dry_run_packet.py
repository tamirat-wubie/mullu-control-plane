#!/usr/bin/env python3
"""Validate Personal Assistant dry-run packets.

Purpose: gate no-effect Personal Assistant dry-run workflow packets on schema,
source binding, acyclic topology, approval placement, no-effect boundaries,
and secret serialization controls.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: dry-run packet schema, collector constants, and schema helpers.
Invariants:
  - Dry-run closure requires every source artifact to be bound and digest-only.
  - Source artifact schema refs must resolve and validate their source payloads.
  - P4/P5 or effect-bearing paths must have approval gates before execution.
  - The packet cannot grant execution, connector mutation, memory admission, or readiness authority.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.collect_personal_assistant_dry_run_packet import (  # noqa: E402
    BLOCKED_SECRET_VALUE_MARKERS,
    DEFAULT_OUTPUT,
    SOURCE_ARTIFACTS,
)
from scripts.personal_assistant_source_digest import canonical_source_sha256  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DRY_RUN_PACKET_SCHEMA_PATH = REPO_ROOT / "schemas" / "personal_assistant_dry_run_packet.schema.json"
DEFAULT_VALIDATION_OUTPUT = REPO_ROOT / ".change_assurance" / "personal_assistant_dry_run_packet_validation.json"
PACKET_ID_PATTERN = re.compile(r"^personal-assistant-dry-run-[0-9a-f]{16}$")


@dataclass(frozen=True, slots=True)
class PersonalAssistantDryRunPacketValidationStep:
    """One dry-run packet validation step."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class PersonalAssistantDryRunPacketValidation:
    """Structured validation report for one dry-run packet."""

    packet_path: str
    valid: bool
    packet_id: str
    solver_outcome: str
    dry_run_packet_closed: bool
    steps: tuple[PersonalAssistantDryRunPacketValidationStep, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable validation report."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def validate_personal_assistant_dry_run_packet(
    *,
    packet_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = DRY_RUN_PACKET_SCHEMA_PATH,
    require_closed: bool = False,
) -> PersonalAssistantDryRunPacketValidation:
    """Validate one Personal Assistant dry-run packet."""
    payload = _read_packet_payload(packet_path)
    steps = (
        _check_schema_contract(payload, schema_path),
        _check_packet_id(payload),
        _check_source_artifacts(payload),
        _check_source_artifact_digests(payload),
        _check_source_artifact_schemas(payload),
        _check_topology(payload),
        _check_bindings(payload),
        _check_approval_gate_order(payload),
        _check_no_effect_boundary(payload),
        _check_closure_gate(payload),
        _check_secret_value_boundary(payload),
        _check_require_closed(payload, require_closed=require_closed),
    )
    summary = _object(payload.get("closure_summary"))
    return PersonalAssistantDryRunPacketValidation(
        packet_path=_bounded_packet_path(packet_path),
        valid=all(step.passed for step in steps),
        packet_id=_bounded_packet_id(payload),
        solver_outcome=_bounded_text(payload.get("solver_outcome")),
        dry_run_packet_closed=summary.get("dry_run_packet_closed") is True,
        steps=steps,
    )


def write_personal_assistant_dry_run_packet_validation_report(
    validation: PersonalAssistantDryRunPacketValidation,
    output_path: Path,
) -> Path:
    """Write one local dry-run packet validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.to_json_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _read_packet_payload(packet_path: Path) -> dict[str, Any]:
    try:
        raw_text = packet_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError("failed to read Personal Assistant dry-run packet") from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Personal Assistant dry-run packet returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Personal Assistant dry-run packet was not a JSON object")
    return parsed


def _check_schema_contract(
    payload: dict[str, Any],
    schema_path: Path,
) -> PersonalAssistantDryRunPacketValidationStep:
    try:
        schema = _load_schema(schema_path)
    except OSError:
        return PersonalAssistantDryRunPacketValidationStep("schema contract", False, "schema-read-failed")
    errors = _validate_schema_instance(schema, payload)
    return PersonalAssistantDryRunPacketValidationStep(
        "schema contract",
        not errors,
        "valid" if not errors else f"schema-errors={len(errors)}",
    )


def _check_packet_id(payload: dict[str, Any]) -> PersonalAssistantDryRunPacketValidationStep:
    packet_id = payload.get("packet_id")
    passed = PACKET_ID_PATTERN.fullmatch(str(packet_id)) is not None
    return PersonalAssistantDryRunPacketValidationStep("packet id", passed, "valid" if passed else "invalid")


def _check_source_artifacts(payload: dict[str, Any]) -> PersonalAssistantDryRunPacketValidationStep:
    records = _list_of_objects(payload.get("source_artifacts"))
    required_kinds = {kind for kind, _path, _schema_ref in SOURCE_ARTIFACTS}
    observed_kinds = {str(record.get("source_kind")) for record in records}
    valid_records = [
        record
        for record in records
        if record.get("bound") is True
        and record.get("payload_digest_only") is True
        and record.get("solver_outcome") == "SolvedVerified"
        and record.get("effect_violation_count") == 0
        and _bounded_text(record.get("source_sha256"))
    ]
    passed = observed_kinds == required_kinds and len(valid_records) == len(required_kinds)
    return PersonalAssistantDryRunPacketValidationStep(
        "source artifacts",
        passed,
        f"kinds={len(observed_kinds)}/{len(required_kinds)} valid={len(valid_records)}",
    )


def _check_source_artifact_digests(payload: dict[str, Any]) -> PersonalAssistantDryRunPacketValidationStep:
    records = _list_of_objects(payload.get("source_artifacts"))
    mismatches: list[str] = []
    missing: list[str] = []
    for record in records:
        source_kind = _bounded_text(record.get("source_kind")) or "unknown"
        source_ref = _bounded_text(record.get("source_ref"))
        expected_digest = _bounded_text(record.get("source_sha256"))
        source_path = (REPO_ROOT / source_ref).resolve()
        if not source_ref or not _path_within_repo(source_path) or not source_path.exists():
            missing.append(source_kind)
            continue
        observed_digest = canonical_source_sha256(source_path)
        if observed_digest != expected_digest:
            mismatches.append(source_kind)
    passed = not mismatches and not missing and len(records) == len(SOURCE_ARTIFACTS)
    detail = (
        "digests-current"
        if passed
        else f"mismatches={len(mismatches)} missing={len(missing)}"
    )
    return PersonalAssistantDryRunPacketValidationStep("source artifact digests", passed, detail)


def _check_source_artifact_schemas(payload: dict[str, Any]) -> PersonalAssistantDryRunPacketValidationStep:
    records = _list_of_objects(payload.get("source_artifacts"))
    invalid: list[str] = []
    missing: list[str] = []
    for record in records:
        source_kind = _bounded_text(record.get("source_kind")) or "unknown"
        source_ref = _bounded_text(record.get("source_ref"))
        schema_ref = _bounded_text(record.get("schema_ref"))
        source_path = (REPO_ROOT / source_ref).resolve()
        schema_path = (REPO_ROOT / schema_ref).resolve()
        if (
            not source_ref
            or not schema_ref
            or not _path_within_repo(source_path)
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
    passed = not invalid and not missing and len(records) == len(SOURCE_ARTIFACTS)
    detail = (
        "schemas-current"
        if passed
        else f"invalid={len(invalid)} missing={len(missing)}"
    )
    return PersonalAssistantDryRunPacketValidationStep("source artifact schemas", passed, detail)


def _check_topology(payload: dict[str, Any]) -> PersonalAssistantDryRunPacketValidationStep:
    stages = _list_of_objects(payload.get("stages"))
    stage_ids = [str(stage.get("stage_id")) for stage in stages]
    unique_stage_ids = len(stage_ids) == len(set(stage_ids))
    predecessors_valid = all(
        str(predecessor_id) in stage_ids
        for stage in stages
        for predecessor_id in _strings(stage.get("predecessor_ids"))
    )
    acyclic = _acyclic(stages)
    summary = _object(payload.get("topology_summary"))
    passed = (
        len(stages) == 10
        and unique_stage_ids
        and predecessors_valid
        and acyclic
        and summary.get("stage_count") == len(stages)
        and summary.get("acyclic") is True
        and summary.get("terminal_stage_id") == "terminal_no_effect_closure"
    )
    return PersonalAssistantDryRunPacketValidationStep(
        "topology",
        passed,
        f"stages={len(stages)} unique={unique_stage_ids} acyclic={acyclic}",
    )


def _check_bindings(payload: dict[str, Any]) -> PersonalAssistantDryRunPacketValidationStep:
    stages = _list_of_objects(payload.get("stages"))
    source_kinds = {str(record.get("source_kind")) for record in _list_of_objects(payload.get("source_artifacts"))}
    passed = _bindings_resolved(stages, source_kinds)
    return PersonalAssistantDryRunPacketValidationStep(
        "bindings",
        passed,
        "resolved" if passed else "dangling",
    )


def _check_approval_gate_order(payload: dict[str, Any]) -> PersonalAssistantDryRunPacketValidationStep:
    stages = _list_of_objects(payload.get("stages"))
    passed = _approval_gates_before_effects(stages)
    p4p5_count = sum(1 for stage in stages if str(stage.get("risk_level")) in {"P4", "P5"})
    return PersonalAssistantDryRunPacketValidationStep(
        "approval gate order",
        passed,
        f"p4p5_stages={p4p5_count} gate_before_effect={passed}",
    )


def _check_no_effect_boundary(payload: dict[str, Any]) -> PersonalAssistantDryRunPacketValidationStep:
    no_effect_boundary = _object(payload.get("no_effect_boundary"))
    stages = _list_of_objects(payload.get("stages"))
    summary = _object(payload.get("closure_summary"))
    boundary_clear = no_effect_boundary and all(value is False for value in no_effect_boundary.values())
    stages_clear = all(stage.get("execution_allowed") is False for stage in stages)
    summary_clear = summary.get("no_effect_boundaries_clear") is True and summary.get("effect_violation_count") == 0
    passed = bool(boundary_clear and stages_clear and summary_clear)
    return PersonalAssistantDryRunPacketValidationStep(
        "no-effect boundary",
        passed,
        f"boundary_clear={boundary_clear} stages_clear={stages_clear}",
    )


def _check_closure_gate(payload: dict[str, Any]) -> PersonalAssistantDryRunPacketValidationStep:
    summary = _object(payload.get("closure_summary"))
    required_true = (
        "dry_run_packet_closed",
        "all_source_artifacts_bound",
        "all_source_artifacts_solved_verified",
        "all_stages_verified",
        "acyclic_topology",
        "all_bindings_resolved",
        "approval_gate_before_effect_bearing_actions",
        "no_effect_boundaries_clear",
        "no_secret_values_serialized",
    )
    passed = (
        payload.get("proof_state") == "Pass"
        and payload.get("solver_outcome") == "SolvedVerified"
        and all(summary.get(field) is True for field in required_true)
        and summary.get("live_connector_execution_ready") is False
        and summary.get("memory_write_ready") is False
        and summary.get("deployment_mutation_ready") is False
        and summary.get("customer_ready") is False
    )
    return PersonalAssistantDryRunPacketValidationStep(
        "closure gate",
        passed,
        "closed" if passed else "open",
    )


def _check_secret_value_boundary(payload: dict[str, Any]) -> PersonalAssistantDryRunPacketValidationStep:
    serialized = json.dumps(payload, sort_keys=True).lower()
    markers = sorted(marker for marker in BLOCKED_SECRET_VALUE_MARKERS if marker in serialized)
    declared_markers = payload.get("secret_value_markers")
    passed = not markers and declared_markers == []
    return PersonalAssistantDryRunPacketValidationStep(
        "secret value boundary",
        passed,
        "clean" if passed else f"markers={','.join(markers)}",
    )


def _check_require_closed(
    payload: dict[str, Any],
    *,
    require_closed: bool,
) -> PersonalAssistantDryRunPacketValidationStep:
    if not require_closed:
        return PersonalAssistantDryRunPacketValidationStep("require closed", True, "not-required")
    closed = _object(payload.get("closure_summary")).get("dry_run_packet_closed") is True
    return PersonalAssistantDryRunPacketValidationStep(
        "require closed",
        closed,
        "closed" if closed else "open",
    )


def _acyclic(stages: list[dict[str, Any]]) -> bool:
    predecessors = {
        str(stage.get("stage_id")): set(_strings(stage.get("predecessor_ids")))
        for stage in stages
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(stage_id: str) -> bool:
        if stage_id in visited:
            return True
        if stage_id in visiting:
            return False
        visiting.add(stage_id)
        for predecessor_id in predecessors.get(stage_id, set()):
            if predecessor_id in predecessors and not visit(predecessor_id):
                return False
        visiting.remove(stage_id)
        visited.add(stage_id)
        return True

    return all(visit(stage_id) for stage_id in predecessors)


def _bindings_resolved(stages: list[dict[str, Any]], source_kinds: set[str]) -> bool:
    outputs_by_stage = {
        str(stage.get("stage_id")): set(_strings(stage.get("output_keys")))
        for stage in stages
    }
    for stage in stages:
        predecessors = set(_strings(stage.get("predecessor_ids")))
        for binding in _strings(stage.get("input_bindings")):
            if binding.startswith("source:"):
                if binding.removeprefix("source:") not in source_kinds:
                    return False
                continue
            if "." not in binding:
                return False
            binding_stage, binding_output = binding.split(".", 1)
            if binding_stage not in outputs_by_stage or binding_output not in outputs_by_stage[binding_stage]:
                return False
            if binding_stage not in predecessors:
                return False
    return True


def _approval_gates_before_effects(stages: list[dict[str, Any]]) -> bool:
    stage_by_id = {str(stage.get("stage_id")): stage for stage in stages}
    for stage in stages:
        risk_level = str(stage.get("risk_level"))
        effect_boundary = str(stage.get("effect_boundary"))
        requires_gate = risk_level in {"P4", "P5"} or any(
            marker in effect_boundary
            for marker in ("external_email_send", "system_write", "calendar_write", "task_write", "memory_write")
        )
        if not requires_gate:
            continue
        if stage.get("stage_type") == "approval_gate" and stage.get("approval_required") is True:
            continue
        if not _has_approval_gate_ancestor(str(stage.get("stage_id")), stage_by_id, set()):
            return False
    return True


def _has_approval_gate_ancestor(stage_id: str, stage_by_id: dict[str, dict[str, Any]], seen: set[str]) -> bool:
    if stage_id in seen:
        return False
    seen.add(stage_id)
    stage = stage_by_id[stage_id]
    for predecessor_id in _strings(stage.get("predecessor_ids")):
        predecessor = stage_by_id.get(predecessor_id)
        if predecessor is None:
            continue
        if predecessor.get("stage_type") == "approval_gate" and predecessor.get("approval_required") is True:
            return True
        if _has_approval_gate_ancestor(predecessor_id, stage_by_id, seen):
            return True
    return False


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_objects(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _bounded_packet_id(payload: dict[str, Any]) -> str:
    packet_id = payload.get("packet_id")
    return str(packet_id) if packet_id is not None else ""


def _bounded_text(value: Any) -> str:
    return str(value) if value is not None else ""


def _bounded_packet_path(packet_path: Path) -> str:
    try:
        return packet_path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return packet_path.as_posix()


def _path_within_repo(path: Path) -> bool:
    try:
        path.relative_to(REPO_ROOT.resolve())
    except ValueError:
        return False
    return True


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("failed to read Personal Assistant dry-run source artifact") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Personal Assistant dry-run source artifact must be a JSON object")
    return parsed


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_VALIDATION_OUTPUT)
    parser.add_argument("--require-closed", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    validation = validate_personal_assistant_dry_run_packet(
        packet_path=args.packet,
        require_closed=args.require_closed,
    )
    write_personal_assistant_dry_run_packet_validation_report(validation, args.output)
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
