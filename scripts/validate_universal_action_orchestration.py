"""Validate the Universal Action Orchestration contract.

Purpose: verify the schema, examples, no-bypass invariant, admission guards,
receipt linkage, reconciliation, memory update, closure, and lineage records
for governed effect-bearing actions.
Governance scope: OCE field completeness, RAG stage-to-receipt relationships,
CDCV execution causality, CQTE guard proof states, UWMA lineage anchoring, and
PRS closure receipts.
Dependencies: Python standard library only.
Invariants: validation is read-only, rejects raw private reasoning exposure,
blocks execution for non-allow decisions, requires receipt-bound closure, and
keeps persisted validation receipts under the workspace root.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "universal_action_orchestration.schema.json"
DEFAULT_DOCUMENT_PATH = WORKSPACE_ROOT / "docs" / "UNIVERSAL_ACTION_ORCHESTRATION.md"
DEFAULT_EXAMPLE_PATHS = (
    WORKSPACE_ROOT / "examples" / "universal_action_orchestration.allowed_status_publish.json",
    WORKSPACE_ROOT / "examples" / "universal_action_orchestration.blocked_invoice_payment.json",
    WORKSPACE_ROOT / "examples" / "uao" / "blocked_missing_approval.json",
    WORKSPACE_ROOT / "examples" / "uao" / "deferred_stale_evidence.json",
    WORKSPACE_ROOT / "examples" / "uao" / "simulated_low_risk_readonly.json",
)

EXPECTED_SCHEMA_ID = "urn:mullusi:schema:universal-action-orchestration:1"
EXPECTED_SCHEMA_TITLE = "Universal Action Orchestration"
EXPECTED_SCHEMA_VERSION = "uao.v1"
REQUIRED_ROOT_FIELDS = (
    "orchestration_id",
    "uao_schema_version",
    "action_id",
    "tenant_id",
    "actor_id",
    "created_at",
    "action_envelope",
    "effect_bearing",
    "effect_classes",
    "input_refs",
    "policy_refs",
    "capability_refs",
    "temporal_refs",
    "exposure_boundary",
    "pipeline_stages",
    "admission_guards",
    "decision",
    "trace_ref",
    "causal_decision_trace_ref",
    "admission_receipt_ref",
    "execution_receipt_ref",
    "receipts",
    "reconciliation",
    "memory_update",
    "closure_state",
    "closure",
    "raw_reasoning_included",
    "lineage",
)
PIPELINE_STAGE_KINDS = (
    "action",
    "evidence",
    "trace",
    "admission",
    "capability",
    "execution",
    "receipt",
    "reconciliation",
    "memory",
    "closure",
)
REQUIRED_GUARDS = (
    "identity_valid",
    "tenant_valid",
    "authority_valid",
    "policy_allows",
    "risk_acceptable",
    "budget_available",
    "evidence_sufficient",
    "temporal_window_valid",
    "capability_certified",
    "recovery_available",
    "receipt_emittable",
)
PROOF_STATES = {"Pass", "Fail", "Unknown", "BudgetUnknown"}
GUARD_VERDICTS = {"passed", "blocked", "deferred", "escalated", "simulated"}
DECISION_STATUSES = {"allow", "block", "defer", "escalate", "simulate"}
PASSING_OUTCOMES = {"SolvedVerified", "SolvedUnverified"}
HIGH_RISK_CLASSES = {"H3", "H4"}
PROHIBITED_PRIVATE_REASONING_FIELDS = {
    "chain_of_thought",
    "raw_chain_of_thought",
    "private_reasoning",
    "hidden_reasoning",
    "scratchpad",
}
NON_PASS_OUTCOMES = {
    "AwaitingEvidence",
    "SafeHalt",
    "GovernanceBlocked",
    "BudgetExhausted",
    "ImpossibleProved",
    "ModelInvalidated",
}
REQUIRED_SCHEMA_DEFS = {
    "action_envelope": (
        "source",
        "actor",
        "tenant",
        "intent",
        "target",
        "risk",
        "requested_at",
        "approval_ref",
        "evidence_refs",
        "capability_refs",
    ),
    "exposure_boundary": ("redaction_level", "allowed_audiences", "blocked_payload_classes"),
    "pipeline_stage": (
        "stage_id",
        "stage_order",
        "stage_kind",
        "status",
        "input_refs",
        "output_refs",
        "receipt_ref",
        "failure_reason",
    ),
    "admission_guard": ("guard", "verdict", "proof_state", "reason_code", "evidence_refs"),
    "decision": ("status", "reason_code", "proof_state", "solver_outcome", "next_action", "execution_allowed"),
    "receipt": ("receipt_id", "tier", "kind", "stage_id", "confirms", "external_state_confirmed"),
    "reconciliation": ("status", "observed_outcome_ref", "required_for_closure", "mismatch_reason"),
    "memory_update": ("status", "memory_ref", "learning_allowed"),
    "closure": ("status", "terminal", "closure_receipt_ref", "next_action"),
    "lineage": ("delta_ref", "logged_in_lineage", "accepted_deltas", "rejected_deltas"),
}
REQUIRED_DOCUMENT_TERMS = (
    "passive doc -> schema contract -> example fixtures -> validator -> workspace preflight required gate",
    "effect_bearing(action) -> trace_ref and admission_receipt_ref and closure_state",
    "not UAO_valid(action) -> preflight_fail",
    "does not execute actions",
    "raw private reasoning",
)


class UniversalActionOrchestrationError(ValueError):
    """Raised when Universal Action Orchestration contract input is invalid."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object with explicit artifact identity."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise UniversalActionOrchestrationError(f"{label} must be a JSON object")
    return payload


def load_document_text(document_path: Path) -> str:
    """Load the human-readable Universal Action Orchestration doctrine."""

    if not document_path.exists():
        raise FileNotFoundError(f"missing Universal Action Orchestration document: {document_path}")
    if not document_path.is_file():
        raise IsADirectoryError(f"Universal Action Orchestration document path is not a file: {document_path}")
    return document_path.read_text(encoding="utf-8")


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema artifact validation errors."""

    errors: list[str] = []
    if schema.get("title") != EXPECTED_SCHEMA_TITLE:
        errors.append("schema title does not identify Universal Action Orchestration")
    if schema.get("$id") != EXPECTED_SCHEMA_ID:
        errors.append("schema $id is invalid")
    if schema.get("type") != "object":
        errors.append("schema root type must be object")
    if schema.get("additionalProperties") is not False:
        errors.append("schema root must close additional properties")
    errors.extend(_validate_required_properties("schema", schema, "root", REQUIRED_ROOT_FIELDS))
    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        errors.append("schema $defs must be an object")
        return errors
    for definition_name, required_fields in REQUIRED_SCHEMA_DEFS.items():
        errors.extend(_validate_required_properties("schema", defs.get(definition_name), definition_name, required_fields))
    return errors


def validate_document_contract(document_text: str) -> list[str]:
    """Return deterministic findings for the Universal Action Orchestration doctrine."""

    errors: list[str] = []
    for required_term in REQUIRED_DOCUMENT_TERMS:
        if required_term not in document_text:
            errors.append(f"document missing required UAO v1 term: {required_term}")
    return errors


def validate_orchestration(record: dict[str, Any]) -> list[str]:
    """Return deterministic contract violations for one UAO record."""

    errors = _validate_required_fields("orchestration", record, REQUIRED_ROOT_FIELDS)
    if errors:
        return errors
    errors.extend(_validate_no_private_reasoning_fields(record))

    for field_name in ("orchestration_id", "action_id", "tenant_id", "actor_id", "created_at"):
        if not isinstance(record[field_name], str) or not record[field_name]:
            errors.append(f"orchestration.{field_name} must be a non-empty string")
    if record["uao_schema_version"] != EXPECTED_SCHEMA_VERSION:
        errors.append("orchestration.uao_schema_version must be uao.v1")
    if record["raw_reasoning_included"] is not False:
        errors.append("orchestration.raw_reasoning_included must be false")
    if not isinstance(record["effect_bearing"], bool):
        errors.append("orchestration.effect_bearing must be boolean")
    errors.extend(_validate_action_envelope(record["action_envelope"], record))

    errors.extend(_validate_string_array("orchestration.effect_classes", record["effect_classes"]))
    errors.extend(_validate_string_array("orchestration.input_refs", record["input_refs"], min_count=1))
    errors.extend(_validate_string_array("orchestration.policy_refs", record["policy_refs"], min_count=1))
    errors.extend(_validate_string_array("orchestration.capability_refs", record["capability_refs"], min_count=1))
    errors.extend(_validate_string_array("orchestration.temporal_refs", record["temporal_refs"], min_count=1))
    errors.extend(_validate_exposure_boundary(record["exposure_boundary"]))

    stages_by_kind: dict[str, dict[str, Any]] = {}
    stages_by_id: dict[str, dict[str, Any]] = {}
    errors.extend(_validate_pipeline_stages(record["pipeline_stages"], stages_by_kind, stages_by_id))

    guards_by_name: dict[str, dict[str, Any]] = {}
    errors.extend(_validate_admission_guards(record["admission_guards"], guards_by_name))
    errors.extend(_validate_decision(record["decision"], guards_by_name, stages_by_kind))
    errors.extend(_validate_trace_binding(record, stages_by_kind))

    receipt_ids: set[str] = set()
    receipt_kinds: set[str] = set()
    errors.extend(_validate_receipts(record["receipts"], stages_by_id, receipt_ids, receipt_kinds))
    errors.extend(_validate_reconciliation(record["reconciliation"], record["decision"]))
    errors.extend(_validate_memory_update(record["memory_update"]))
    errors.extend(_validate_closure(record["closure"], record["decision"], receipt_ids))
    errors.extend(_validate_lineage(record["lineage"], record["decision"]))
    errors.extend(_validate_receipt_requirements(record["decision"], receipt_kinds))
    errors.extend(_validate_root_receipt_refs(record, receipt_ids, receipt_kinds))
    errors.extend(_validate_effect_bearing_invariant(record))
    errors.extend(_validate_high_risk_allow_controls(record))
    return errors


def validate_contract(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    example_paths: tuple[Path, ...] = DEFAULT_EXAMPLE_PATHS,
    document_path: Path = DEFAULT_DOCUMENT_PATH,
) -> list[str]:
    """Validate the schema artifact and all UAO examples."""

    schema = load_json_object(schema_path, "Universal Action Orchestration schema")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_document_contract(load_document_text(document_path)))
    for example_path in example_paths:
        record = load_json_object(example_path, f"Universal Action Orchestration example {example_path.name}")
        errors.extend(f"{example_path.name}: {error}" for error in validate_orchestration(record))
    return errors


def build_validation_report(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    example_paths: tuple[Path, ...] = DEFAULT_EXAMPLE_PATHS,
    document_path: Path = DEFAULT_DOCUMENT_PATH,
) -> dict[str, Any]:
    """Build a machine-readable UAO validation receipt."""

    checks = (
        "universal_action_orchestration_schema",
        "universal_action_orchestration_examples",
        "universal_action_orchestration_document",
        "universal_action_orchestration_no_bypass",
        "universal_action_orchestration_receipts",
    )
    try:
        errors = validate_contract(schema_path, example_paths, document_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [f"load-universal-action-orchestration: {_sanitize_receipt_error(exc, schema_path, example_paths, document_path)}"]
    valid = not errors
    return {
        "receipt_id": "universal_action_orchestration_validation_receipt",
        "terminal_closure_required": True,
        "receipt_is_not_terminal_closure": True,
        "valid": valid,
        "status": "passed" if valid else "failed",
        "schema_path": _receipt_path_label(schema_path),
        "document_path": _receipt_path_label(document_path),
        "example_paths": [_receipt_path_label(example_path) for example_path in example_paths],
        "example_count": len(example_paths),
        "checks": [
            {
                "name": check_name,
                "passed": valid,
            }
            for check_name in checks
        ],
        "check_count": len(checks),
        "error_count": len(errors),
        "errors": errors,
    }


def resolve_validation_receipt_path(receipt_path: Path, workspace_root: Path = WORKSPACE_ROOT) -> Path:
    """Resolve a workspace-local JSON receipt path and reject path escapes."""

    if receipt_path.suffix.lower() != ".json":
        raise ValueError("UAO validation receipt path must use .json suffix")
    resolved_root = workspace_root.resolve()
    resolved_path = (workspace_root / receipt_path).resolve() if not receipt_path.is_absolute() else receipt_path.resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError(f"UAO validation receipt path must stay under workspace root: {receipt_path}")
    return resolved_path


def write_validation_report(
    report: dict[str, Any],
    receipt_path: Path,
    workspace_root: Path = WORKSPACE_ROOT,
) -> Path:
    """Persist a UAO validation receipt without executing actions."""

    resolved_path = resolve_validation_receipt_path(receipt_path, workspace_root)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return resolved_path


def _receipt_path_label(path: Path) -> str:
    """Return a receipt-safe path label without host-local absolute ancestry."""

    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return path.name


def _sanitize_receipt_error(
    exc: BaseException,
    schema_path: Path,
    example_paths: tuple[Path, ...],
    document_path: Path,
) -> str:
    """Bound load errors so receipts do not leak machine-local directories."""

    message = str(exc)
    for path in (schema_path, document_path, *example_paths):
        safe_label = _receipt_path_label(path)
        for path_text in {str(path), str(path.resolve(strict=False))}:
            if path_text:
                message = message.replace(path_text, safe_label)
    return message


def _validate_required_properties(
    contract_name: str,
    schema_fragment: Any,
    fragment_name: str,
    required_fields: tuple[str, ...],
) -> list[str]:
    if not isinstance(schema_fragment, dict):
        return [f"{contract_name}: schema missing object definition: {fragment_name}"]
    if schema_fragment.get("type") != "object":
        return [f"{contract_name}: {fragment_name} must be an object schema"]
    if schema_fragment.get("additionalProperties") is not False:
        return [f"{contract_name}: {fragment_name} must close additional properties"]
    required = schema_fragment.get("required")
    properties = schema_fragment.get("properties")
    errors: list[str] = []
    if not isinstance(required, list):
        errors.append(f"{contract_name}: {fragment_name}.required must be a list")
    if not isinstance(properties, dict):
        errors.append(f"{contract_name}: {fragment_name}.properties must be an object")
    if errors:
        return errors
    for field_name in required_fields:
        if field_name not in required:
            errors.append(f"{contract_name}: {fragment_name} missing required field: {field_name}")
        if field_name not in properties:
            errors.append(f"{contract_name}: {fragment_name} missing property: {field_name}")
    return errors


def _validate_required_fields(label: str, record: Any, fields: tuple[str, ...]) -> list[str]:
    if not isinstance(record, dict):
        return [f"{label} must be an object"]
    return [f"{label} missing field: {field_name}" for field_name in fields if field_name not in record]


def _validate_string_array(label: str, value: Any, min_count: int = 0) -> list[str]:
    if not isinstance(value, list):
        return [f"{label} must be a list"]
    errors: list[str] = []
    if len(value) < min_count:
        errors.append(f"{label} must contain at least {min_count} item(s)")
    if len(set(value)) != len(value):
        errors.append(f"{label} must not contain duplicates")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            errors.append(f"{label}[{index}] must be a non-empty string")
    return errors


def _validate_exposure_boundary(exposure_boundary: Any) -> list[str]:
    errors = _validate_required_fields(
        "exposure_boundary",
        exposure_boundary,
        ("redaction_level", "allowed_audiences", "blocked_payload_classes"),
    )
    if errors:
        return errors
    if exposure_boundary["redaction_level"] not in {"internal", "operator", "user_safe", "audit", "external"}:
        errors.append("exposure_boundary.redaction_level is invalid")
    errors.extend(_validate_string_array("exposure_boundary.allowed_audiences", exposure_boundary["allowed_audiences"], 1))
    errors.extend(
        _validate_string_array(
            "exposure_boundary.blocked_payload_classes",
            exposure_boundary["blocked_payload_classes"],
            1,
        )
    )
    if "raw_private_reasoning" not in exposure_boundary["blocked_payload_classes"]:
        errors.append("exposure_boundary.blocked_payload_classes must include raw_private_reasoning")
    return errors


def _validate_action_envelope(action_envelope: Any, record: dict[str, Any]) -> list[str]:
    errors = _validate_required_fields(
        "action_envelope",
        action_envelope,
        (
            "source",
            "actor",
            "tenant",
            "intent",
            "target",
            "risk",
            "requested_at",
            "approval_ref",
            "evidence_refs",
            "capability_refs",
        ),
    )
    if errors:
        return errors
    for field_name in ("source", "actor", "tenant", "intent", "target", "requested_at"):
        if not isinstance(action_envelope[field_name], str) or not action_envelope[field_name]:
            errors.append(f"action_envelope.{field_name} must be a non-empty string")
    if action_envelope["risk"] not in {"low", "H1", "H2", "H3", "H4"}:
        errors.append("action_envelope.risk is invalid")
    if action_envelope["approval_ref"] is not None and (
        not isinstance(action_envelope["approval_ref"], str) or not action_envelope["approval_ref"]
    ):
        errors.append("action_envelope.approval_ref must be null or a non-empty string")
    errors.extend(_validate_string_array("action_envelope.evidence_refs", action_envelope["evidence_refs"]))
    errors.extend(_validate_string_array("action_envelope.capability_refs", action_envelope["capability_refs"]))
    if action_envelope["actor"] != record["actor_id"]:
        errors.append("action_envelope.actor must match actor_id")
    if action_envelope["tenant"] != record["tenant_id"]:
        errors.append("action_envelope.tenant must match tenant_id")
    if action_envelope["requested_at"] != record["created_at"]:
        errors.append("action_envelope.requested_at must match created_at")
    if action_envelope["risk"] not in {"low", "H1"} and not record["effect_bearing"]:
        errors.append("action_envelope.risk H2/H3/H4 requires effect_bearing true")
    return errors


def _validate_pipeline_stages(
    stages: Any,
    stages_by_kind: dict[str, dict[str, Any]],
    stages_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    if not isinstance(stages, list):
        return ["pipeline_stages must be a list"]
    errors: list[str] = []
    observed_kinds: list[str] = []
    observed_orders: list[int] = []
    for index, stage in enumerate(stages):
        label = f"pipeline_stages[{index}]"
        errors.extend(
            _validate_required_fields(
                label,
                stage,
                ("stage_id", "stage_order", "stage_kind", "status", "input_refs", "output_refs", "receipt_ref", "failure_reason"),
            )
        )
        if not isinstance(stage, dict) or any(
            field not in stage
            for field in ("stage_id", "stage_order", "stage_kind", "status", "input_refs", "output_refs", "receipt_ref", "failure_reason")
        ):
            continue
        stage_id = stage["stage_id"]
        stage_kind = stage["stage_kind"]
        if not isinstance(stage_id, str) or not stage_id:
            errors.append(f"{label}.stage_id must be a non-empty string")
        elif stage_id in stages_by_id:
            errors.append(f"duplicate stage_id: {stage_id}")
        else:
            stages_by_id[stage_id] = stage
        if stage_kind not in PIPELINE_STAGE_KINDS:
            errors.append(f"{label}.stage_kind is invalid")
        elif stage_kind in stages_by_kind:
            errors.append(f"duplicate pipeline stage kind: {stage_kind}")
        else:
            stages_by_kind[stage_kind] = stage
            observed_kinds.append(stage_kind)
        if not isinstance(stage["stage_order"], int) or isinstance(stage["stage_order"], bool):
            errors.append(f"{label}.stage_order must be an integer")
        else:
            observed_orders.append(stage["stage_order"])
        if stage["status"] not in {"completed", "blocked", "skipped", "deferred", "escalated", "simulated"}:
            errors.append(f"{label}.status is invalid")
        if stage["status"] in {"blocked", "skipped", "deferred", "escalated"} and not stage["failure_reason"]:
            errors.append(f"{label}: non-completed stage requires failure_reason")
        if stage["receipt_ref"] is not None and (not isinstance(stage["receipt_ref"], str) or not stage["receipt_ref"]):
            errors.append(f"{label}.receipt_ref must be null or a non-empty string")
        if stage["failure_reason"] is not None and (not isinstance(stage["failure_reason"], str) or not stage["failure_reason"]):
            errors.append(f"{label}.failure_reason must be null or a non-empty string")
        errors.extend(_validate_string_array(f"{label}.input_refs", stage["input_refs"]))
        errors.extend(_validate_string_array(f"{label}.output_refs", stage["output_refs"]))
    if tuple(observed_kinds) != PIPELINE_STAGE_KINDS:
        errors.append("pipeline_stages must contain canonical UAO stage kinds in order")
    if observed_orders != list(range(1, len(observed_orders) + 1)):
        errors.append("pipeline_stages must use contiguous stage_order values starting at 1")
    return errors


def _validate_admission_guards(guards: Any, guards_by_name: dict[str, dict[str, Any]]) -> list[str]:
    if not isinstance(guards, list):
        return ["admission_guards must be a list"]
    errors: list[str] = []
    for index, guard in enumerate(guards):
        label = f"admission_guards[{index}]"
        errors.extend(_validate_required_fields(label, guard, ("guard", "verdict", "proof_state", "reason_code", "evidence_refs")))
        if not isinstance(guard, dict) or any(
            field not in guard for field in ("guard", "verdict", "proof_state", "reason_code", "evidence_refs")
        ):
            continue
        guard_name = guard["guard"]
        if not isinstance(guard_name, str) or not guard_name:
            errors.append(f"{label}.guard must be a non-empty string")
        elif guard_name in guards_by_name:
            errors.append(f"duplicate admission guard: {guard_name}")
        else:
            guards_by_name[guard_name] = guard
        if guard["verdict"] not in GUARD_VERDICTS:
            errors.append(f"{label}.verdict is invalid")
        if guard["proof_state"] not in PROOF_STATES:
            errors.append(f"{label}.proof_state is invalid")
        if guard["verdict"] == "passed" and guard["proof_state"] != "Pass":
            errors.append(f"{label}: passed guard requires Pass proof_state")
        if guard["verdict"] == "blocked" and guard["proof_state"] == "Pass":
            errors.append(f"{label}: blocked guard cannot carry Pass proof_state")
        if not isinstance(guard["reason_code"], str) or not guard["reason_code"]:
            errors.append(f"{label}.reason_code must be a non-empty string")
        errors.extend(_validate_string_array(f"{label}.evidence_refs", guard["evidence_refs"]))
    for guard_name in REQUIRED_GUARDS:
        if guard_name not in guards_by_name:
            errors.append(f"missing required admission guard: {guard_name}")
    return errors


def _validate_decision(
    decision: Any,
    guards_by_name: dict[str, dict[str, Any]],
    stages_by_kind: dict[str, dict[str, Any]],
) -> list[str]:
    errors = _validate_required_fields(
        "decision",
        decision,
        ("status", "reason_code", "proof_state", "solver_outcome", "next_action", "execution_allowed"),
    )
    if errors:
        return errors
    if decision["status"] not in DECISION_STATUSES:
        errors.append("decision.status is invalid")
    if decision["proof_state"] not in PROOF_STATES:
        errors.append("decision.proof_state is invalid")
    if decision["solver_outcome"] not in PASSING_OUTCOMES | NON_PASS_OUTCOMES:
        errors.append("decision.solver_outcome is invalid")
    if not isinstance(decision["execution_allowed"], bool):
        errors.append("decision.execution_allowed must be boolean")
    for field_name in ("reason_code", "next_action"):
        if not isinstance(decision[field_name], str) or not decision[field_name]:
            errors.append(f"decision.{field_name} must be a non-empty string")

    guard_verdicts = {guard.get("verdict") for guard in guards_by_name.values()}
    execution_stage = stages_by_kind.get("execution", {})
    if decision["status"] == "allow":
        if decision["execution_allowed"] is not True:
            errors.append("decision: allow requires execution_allowed true")
        if any(guard.get("verdict") != "passed" for guard in guards_by_name.values()):
            errors.append("decision: allow requires every admission guard to pass")
        if decision["proof_state"] != "Pass":
            errors.append("decision: allow requires Pass proof_state")
        if decision["solver_outcome"] not in PASSING_OUTCOMES:
            errors.append("decision: allow requires a passing solver outcome")
        if execution_stage.get("status") != "completed":
            errors.append("decision: allow requires completed execution stage")
    else:
        if decision["execution_allowed"] is not False:
            errors.append("decision: non-allow status requires execution_allowed false")
        if execution_stage.get("status") == "completed":
            errors.append("decision: non-allow status cannot complete execution stage")
        if decision["solver_outcome"] in PASSING_OUTCOMES:
            errors.append("decision: non-allow status cannot use a passing solver outcome")
    if decision["status"] == "block" and "blocked" not in guard_verdicts:
        errors.append("decision: block requires at least one blocked admission guard")
    if decision["status"] == "defer" and "deferred" not in guard_verdicts:
        errors.append("decision: defer requires at least one deferred admission guard")
    if decision["status"] == "escalate" and "escalated" not in guard_verdicts:
        errors.append("decision: escalate requires at least one escalated admission guard")
    if decision["status"] == "simulate" and "simulated" not in guard_verdicts:
        errors.append("decision: simulate requires at least one simulated admission guard")
    return errors


def _validate_trace_binding(record: dict[str, Any], stages_by_kind: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    trace_ref = record["trace_ref"]
    causal_trace_ref = record["causal_decision_trace_ref"]
    if not isinstance(trace_ref, str) or not trace_ref:
        errors.append("orchestration.trace_ref must be a non-empty string")
    if not isinstance(causal_trace_ref, str) or not causal_trace_ref:
        errors.append("orchestration.causal_decision_trace_ref must be a non-empty string")
    if trace_ref != causal_trace_ref:
        errors.append("trace_ref must match causal_decision_trace_ref")
    if record["effect_bearing"]:
        if not record["effect_classes"]:
            errors.append("effect-bearing action requires effect_classes")
        if not trace_ref or not causal_trace_ref:
            errors.append("effect-bearing action requires trace_ref and causal_decision_trace_ref")
    trace_stage = stages_by_kind.get("trace", {})
    output_refs = trace_stage.get("output_refs", [])
    if causal_trace_ref and isinstance(output_refs, list) and causal_trace_ref not in output_refs:
        errors.append("causal_decision_trace_ref must be emitted by trace stage")
    return errors


def _validate_receipts(
    receipts: Any,
    stages_by_id: dict[str, dict[str, Any]],
    receipt_ids: set[str],
    receipt_kinds: set[str],
) -> list[str]:
    if not isinstance(receipts, list):
        return ["receipts must be a list"]
    errors: list[str] = []
    for index, receipt in enumerate(receipts):
        label = f"receipts[{index}]"
        errors.extend(
            _validate_required_fields(
                label,
                receipt,
                ("receipt_id", "tier", "kind", "stage_id", "confirms", "external_state_confirmed"),
            )
        )
        if not isinstance(receipt, dict) or any(
            field not in receipt for field in ("receipt_id", "tier", "kind", "stage_id", "confirms", "external_state_confirmed")
        ):
            continue
        receipt_id = receipt["receipt_id"]
        if not isinstance(receipt_id, str) or not receipt_id:
            errors.append(f"{label}.receipt_id must be a non-empty string")
        elif receipt_id in receipt_ids:
            errors.append(f"duplicate receipt_id: {receipt_id}")
        else:
            receipt_ids.add(receipt_id)
        if receipt["tier"] not in {"R0", "R1", "R2", "R3", "R4"}:
            errors.append(f"{label}.tier is invalid")
        if receipt["kind"] not in {"admission", "trace", "execution", "provider", "reconciliation", "closure", "simulation"}:
            errors.append(f"{label}.kind is invalid")
        else:
            receipt_kinds.add(receipt["kind"])
        if receipt["stage_id"] not in stages_by_id:
            errors.append(f"{label}.stage_id does not reference a pipeline stage")
        if not isinstance(receipt["confirms"], str) or not receipt["confirms"]:
            errors.append(f"{label}.confirms must be a non-empty string")
        if not isinstance(receipt["external_state_confirmed"], bool):
            errors.append(f"{label}.external_state_confirmed must be boolean")
    return errors


def _validate_reconciliation(reconciliation: Any, decision: dict[str, Any]) -> list[str]:
    errors = _validate_required_fields(
        "reconciliation",
        reconciliation,
        ("status", "observed_outcome_ref", "required_for_closure", "mismatch_reason"),
    )
    if errors:
        return errors
    if reconciliation["status"] not in {"not_required", "pending", "matched", "mismatched", "blocked"}:
        errors.append("reconciliation.status is invalid")
    if not isinstance(reconciliation["required_for_closure"], bool):
        errors.append("reconciliation.required_for_closure must be boolean")
    if reconciliation["observed_outcome_ref"] is not None and (
        not isinstance(reconciliation["observed_outcome_ref"], str) or not reconciliation["observed_outcome_ref"]
    ):
        errors.append("reconciliation.observed_outcome_ref must be null or a non-empty string")
    if reconciliation["mismatch_reason"] is not None and (
        not isinstance(reconciliation["mismatch_reason"], str) or not reconciliation["mismatch_reason"]
    ):
        errors.append("reconciliation.mismatch_reason must be null or a non-empty string")
    if decision["status"] == "allow":
        if reconciliation["status"] != "matched":
            errors.append("reconciliation: allow requires matched reconciliation")
        if reconciliation["required_for_closure"] is not True:
            errors.append("reconciliation: allow requires reconciliation before closure")
    return errors


def _validate_memory_update(memory_update: Any) -> list[str]:
    errors = _validate_required_fields("memory_update", memory_update, ("status", "memory_ref", "learning_allowed"))
    if errors:
        return errors
    if memory_update["status"] not in {"not_allowed", "not_required", "recorded", "blocked", "deferred"}:
        errors.append("memory_update.status is invalid")
    if memory_update["memory_ref"] is not None and (
        not isinstance(memory_update["memory_ref"], str) or not memory_update["memory_ref"]
    ):
        errors.append("memory_update.memory_ref must be null or a non-empty string")
    if not isinstance(memory_update["learning_allowed"], bool):
        errors.append("memory_update.learning_allowed must be boolean")
    if memory_update["learning_allowed"] and memory_update["status"] != "recorded":
        errors.append("memory_update: learning_allowed requires recorded status")
    return errors


def _validate_closure(closure: Any, decision: dict[str, Any], receipt_ids: set[str]) -> list[str]:
    errors = _validate_required_fields("closure", closure, ("status", "terminal", "closure_receipt_ref", "next_action"))
    if errors:
        return errors
    expected_status = {
        "allow": "closed_allowed",
        "block": "closed_blocked",
        "defer": "closed_deferred",
        "escalate": "closed_escalated",
        "simulate": "closed_simulated",
    }.get(decision["status"])
    if closure["status"] != expected_status:
        errors.append(f"closure.status must be {expected_status} for decision {decision['status']}")
    if closure["terminal"] is not True:
        errors.append("closure.terminal must be true")
    if closure["closure_receipt_ref"] not in receipt_ids:
        errors.append("closure.closure_receipt_ref must reference an emitted receipt")
    if not isinstance(closure["next_action"], str) or not closure["next_action"]:
        errors.append("closure.next_action must be a non-empty string")
    return errors


def _validate_lineage(lineage: Any, decision: dict[str, Any]) -> list[str]:
    errors = _validate_required_fields(
        "lineage",
        lineage,
        ("delta_ref", "logged_in_lineage", "accepted_deltas", "rejected_deltas"),
    )
    if errors:
        return errors
    if not isinstance(lineage["delta_ref"], str) or not lineage["delta_ref"]:
        errors.append("lineage.delta_ref must be a non-empty string")
    if lineage["logged_in_lineage"] is not True:
        errors.append("lineage.logged_in_lineage must be true")
    errors.extend(_validate_delta_records("lineage.accepted_deltas", lineage["accepted_deltas"]))
    errors.extend(_validate_delta_records("lineage.rejected_deltas", lineage["rejected_deltas"]))
    if decision["status"] == "allow" and not lineage["accepted_deltas"]:
        errors.append("lineage: allow requires accepted_deltas")
    if decision["status"] != "allow" and not lineage["rejected_deltas"]:
        errors.append("lineage: non-allow status requires rejected_deltas")
    return errors


def _validate_delta_records(label: str, records: Any) -> list[str]:
    if not isinstance(records, list):
        return [f"{label} must be a list"]
    errors: list[str] = []
    for index, record in enumerate(records):
        record_label = f"{label}[{index}]"
        errors.extend(_validate_required_fields(record_label, record, ("delta_id", "reason", "logged_in_lineage")))
        if not isinstance(record, dict) or any(field not in record for field in ("delta_id", "reason", "logged_in_lineage")):
            continue
        if not isinstance(record["delta_id"], str) or not record["delta_id"]:
            errors.append(f"{record_label}.delta_id must be a non-empty string")
        if not isinstance(record["reason"], str) or not record["reason"]:
            errors.append(f"{record_label}.reason must be a non-empty string")
        if record["logged_in_lineage"] is not True:
            errors.append(f"{record_label}.logged_in_lineage must be true")
    return errors


def _validate_receipt_requirements(decision: dict[str, Any], receipt_kinds: set[str]) -> list[str]:
    errors: list[str] = []
    required_kinds = {"admission", "trace", "closure"}
    if decision["status"] == "allow":
        required_kinds |= {"execution", "reconciliation"}
    missing = sorted(required_kinds - receipt_kinds)
    if missing:
        errors.append(f"receipts missing required kind(s): {', '.join(missing)}")
    return errors


def _validate_root_receipt_refs(record: dict[str, Any], receipt_ids: set[str], receipt_kinds: set[str]) -> list[str]:
    errors: list[str] = []
    admission_receipt_ref = record["admission_receipt_ref"]
    execution_receipt_ref = record["execution_receipt_ref"]
    closure_state = record["closure_state"]
    if not isinstance(admission_receipt_ref, str) or not admission_receipt_ref:
        errors.append("admission_receipt_ref must be a non-empty string")
    elif admission_receipt_ref not in receipt_ids:
        errors.append("admission_receipt_ref must reference an emitted receipt")
    if execution_receipt_ref is not None and (not isinstance(execution_receipt_ref, str) or not execution_receipt_ref):
        errors.append("execution_receipt_ref must be null or a non-empty string")
    if record["decision"]["status"] == "allow":
        if execution_receipt_ref not in receipt_ids:
            errors.append("allow decision requires execution_receipt_ref to reference an emitted receipt")
        if "execution" not in receipt_kinds:
            errors.append("allow decision requires an execution receipt")
    else:
        if execution_receipt_ref is not None:
            errors.append("non-allow decision must not carry execution_receipt_ref")
    closure = record.get("closure")
    if isinstance(closure, dict) and closure_state != closure.get("status"):
        errors.append("closure_state must match closure.status")
    return errors


def _validate_effect_bearing_invariant(record: dict[str, Any]) -> list[str]:
    if not record["effect_bearing"]:
        return []
    errors: list[str] = []
    if not record["trace_ref"]:
        errors.append("effect_bearing(action) requires trace_ref")
    if not record["admission_receipt_ref"]:
        errors.append("effect_bearing(action) requires admission_receipt_ref")
    if not record["closure_state"]:
        errors.append("effect_bearing(action) requires closure_state")
    return errors


def _validate_high_risk_allow_controls(record: dict[str, Any]) -> list[str]:
    action_envelope = record["action_envelope"]
    if not isinstance(action_envelope, dict):
        return []
    if record["decision"]["status"] != "allow" or action_envelope.get("risk") not in HIGH_RISK_CLASSES:
        return []
    errors: list[str] = []
    if not action_envelope.get("approval_ref"):
        errors.append("high-risk allow requires action_envelope.approval_ref")
    if not action_envelope.get("evidence_refs"):
        errors.append("high-risk allow requires action_envelope.evidence_refs")
    if not action_envelope.get("capability_refs"):
        errors.append("high-risk allow requires action_envelope.capability_refs")
    return errors


def _validate_no_private_reasoning_fields(value: Any, path: str = "orchestration") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in PROHIBITED_PRIVATE_REASONING_FIELDS:
                errors.append(f"{path}.{key} is prohibited")
            errors.extend(_validate_no_private_reasoning_fields(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_validate_no_private_reasoning_fields(child, f"{path}[{index}]"))
    return errors


def main(argv: list[str] | None = None) -> int:
    """Validate the Universal Action Orchestration contract."""

    parser = argparse.ArgumentParser(description="Validate Universal Action Orchestration contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH, help="path to UAO schema JSON")
    parser.add_argument("--document", type=Path, default=DEFAULT_DOCUMENT_PATH, help="path to UAO doctrine Markdown")
    parser.add_argument(
        "--example",
        action="append",
        type=Path,
        default=[],
        help="UAO example JSON path; may be provided more than once",
    )
    parser.add_argument("--json", action="store_true", help="emit a machine-readable UAO validation receipt")
    parser.add_argument("--receipt-path", type=Path, help="optional path to persist the UAO validation receipt")
    args = parser.parse_args(argv)

    example_paths = tuple(args.example) if args.example else DEFAULT_EXAMPLE_PATHS
    report = build_validation_report(args.schema, example_paths, args.document)
    if args.receipt_path is not None:
        try:
            write_validation_report(report, args.receipt_path)
        except ValueError as exc:
            sys.stderr.write(f"[FAIL] receipt-path: {exc}\nSTATUS: failed\n")
            return 1
    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return 0 if report["valid"] else 1

    if not report["valid"]:
        for error in report["errors"]:
            sys.stderr.write(f"[FAIL] universal-action-orchestration: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    sys.stdout.write("[PASS] universal_action_orchestration_schema\n")
    sys.stdout.write("[PASS] universal_action_orchestration_examples\n")
    sys.stdout.write("[PASS] universal_action_orchestration_document\n")
    sys.stdout.write("[PASS] universal_action_orchestration_no_bypass\n")
    sys.stdout.write("[PASS] universal_action_orchestration_receipts\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
