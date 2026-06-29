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
keeps validation receipts canonical and under the workspace root.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import sys
from pathlib import Path
from typing import Any

try:
    from detect_uao_runtime_bypass import build_detection_report
except ModuleNotFoundError:  # pragma: no cover - exercised when imported as package.
    from scripts.detect_uao_runtime_bypass import build_detection_report


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = (
    WORKSPACE_ROOT / "schemas" / "universal_action_orchestration.schema.json"
)
DEFAULT_DOCUMENT_PATH = WORKSPACE_ROOT / "docs" / "UNIVERSAL_ACTION_ORCHESTRATION.md"
DEFAULT_EXAMPLE_PATHS = (
    WORKSPACE_ROOT
    / "examples"
    / "universal_action_orchestration.allowed_status_publish.json",
    WORKSPACE_ROOT
    / "examples"
    / "universal_action_orchestration.blocked_invoice_payment.json",
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
    "recovery_plan",
    "claim_ledger",
    "fracture_report",
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
CANONICAL_ROOT_FIELDS = (
    *REQUIRED_ROOT_FIELDS,
    "life_meaning_judgment",
    "life_continuity_judgment",
)
PIPELINE_STAGE_KINDS = (
    "action",
    "evidence",
    "trace",
    "admission",
    "capability",
    "fracture",
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
LIFE_CONTINUITY_IMPACTS = {"none", "indirect", "direct", "unknown"}
LIFE_CONTINUITY_DELTAS = {"positive", "neutral", "negative", "unknown"}
LIFE_CONTINUITY_RISKS = {"none", "low", "medium", "high", "unknown"}
LIFE_CONTINUITY_DECISIONS = {"pass", "pause", "block", "escalate"}
LIFE_CONTINUITY_BOUNDARY_STATES = {"pass", "fail", "unknown"}
LIFE_MEANING_IMPACTS = {"none", "indirect", "direct", "unknown"}
LIFE_MEANING_DELTAS = {"positive", "neutral", "negative", "unknown"}
LIFE_MEANING_DECISIONS = {"pass", "pause", "block", "escalate"}
LIFE_MEANING_BOUNDARY_STATES = {"pass", "fail", "unknown"}
LIFE_MEANING_LIFE_STATUSES = {"not_life", "life", "unknown"}
LIFE_MEANING_FEELING_STATUSES = {"not_feeling", "feeling", "unknown"}
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
    "exposure_boundary": (
        "redaction_level",
        "allowed_audiences",
        "blocked_payload_classes",
    ),
    "recovery_plan": (
        "available",
        "recovery_plan_ref",
        "recovery_kind",
        "rollback_plan_ref",
        "compensation_plan_ref",
        "review_required_on_failure",
        "certificate_ref",
        "effect_plan_ref",
    ),
    "claim_ledger": ("ledger_ref", "claims", "unverified_claim_ids"),
    "claim": (
        "claim_id",
        "claim_type",
        "statement",
        "evidence_refs",
        "confidence",
        "verified",
    ),
    "memory_constitution": (
        "constitution_ref",
        "source_refs",
        "owner_ref",
        "scope_ref",
        "confidence",
        "sensitivity",
        "expires_at",
        "allowed_uses",
        "forbidden_uses",
        "evidence_refs",
        "last_verified_at",
        "mutation_history_refs",
    ),
    "fracture_report": (
        "report_ref",
        "status",
        "checks",
        "blocking_check_ids",
        "risk_notes",
    ),
    "fracture_check": (
        "check_id",
        "check_type",
        "status",
        "proof_state",
        "reason_code",
        "evidence_refs",
        "blocking",
    ),
    "life_meaning_judgment": (
        "judgment_id",
        "action_id",
        "decision",
        "affected_symbols",
        "life_impact",
        "feeling_impact",
        "meaning_impact",
        "truth_preserved",
        "dignity_boundary",
        "consent_required",
        "consent_present",
        "love_delta",
        "resonance_delta",
        "domination_risk",
        "justice_repair_required",
        "continuity_delta",
        "irreversible",
        "reasons",
        "evidence_refs",
        "approval_required",
        "rollback_required",
    ),
    "life_meaning_affected_symbol": (
        "symbol_id",
        "symbol_kind",
        "life_status",
        "feeling_status",
        "meaning_bearing",
        "fragility_level",
        "agency_level",
    ),
    "life_continuity_judgment": (
        "judgment_ref",
        "conflict_law_ref",
        "life_impact",
        "feeling_impact",
        "feeling_observer_impact",
        "meaning_impact",
        "meaning_continuity_delta",
        "value_bearing_symbol",
        "lived_meaning_risk",
        "love_delta",
        "resonance_delta",
        "dignity_boundary",
        "truth_preserved",
        "domination_risk",
        "decision",
        "evidence_refs",
        "review_required",
    ),
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
    "admission_guard": (
        "guard",
        "verdict",
        "proof_state",
        "reason_code",
        "evidence_refs",
    ),
    "decision": (
        "status",
        "reason_code",
        "proof_state",
        "solver_outcome",
        "next_action",
        "execution_allowed",
    ),
    "receipt": (
        "receipt_id",
        "tier",
        "kind",
        "stage_id",
        "confirms",
        "external_state_confirmed",
    ),
    "reconciliation": (
        "status",
        "observed_outcome_ref",
        "required_for_closure",
        "mismatch_reason",
    ),
    "memory_update": ("status", "memory_ref", "learning_allowed", "constitution"),
    "closure": (
        "status",
        "terminal",
        "closure_receipt_ref",
        "reconciliation_ref",
        "memory_ref",
        "next_action",
    ),
    "whqr_replay_binding": (
        "replay_ref",
        "canonical_hash",
        "semantics_hash",
        "version",
    ),
    "lineage": ("delta_ref", "logged_in_lineage", "accepted_deltas", "rejected_deltas"),
}
REQUIRED_DOCUMENT_TERMS = (
    "passive doc -> schema contract -> example fixtures -> validator -> workspace preflight required gate",
    "effect_bearing(action) -> trace_ref and admission_receipt_ref and closure_state",
    "not UAO_valid(action) -> preflight_fail",
    "does not execute actions",
    "raw private reasoning",
    "Canonical validation receipts require the default schema, doctrine, and fixture set.",
    "Every command replay record must fail closed when the persisted candidate is malformed or exposes private reasoning fields.",
    "Every command replay record must bind to the command id, tenant, actor, and persisted event identity before exposure.",
    "Every command replay record must bind emitted receipts to the matching pipeline stage, receipt kind, tier, and root receipt reference before exposure.",
    "Every command replay record must bind to the same event-local universal action proof detail, including action id, trace, receipts, closure state, orchestration id, and lineage delta before exposure.",
    "Every command replay record must come from a command event whose event hash recomputes from the persisted event payload before exposure.",
    "Every command replay record must come from a command event whose source channel, idempotency key, policy version, and trace id match the command envelope before exposure.",
    "Every command replay record must carry the canonical ordered UAO pipeline stage sequence before exposure.",
    "Runtime bypass detection scans effect-bearing dispatch and execute call sites for UAO or governed binding before closure.",
    "Every command replay record must bind proof hash to an independent recomputation of the persisted event-local universal action proof detail before exposure.",
    "Every closure receipt must bind closure state to reconciliation, memory, and available WHQR replay references before exposure.",
    "Every effect-bearing `allow` or post-dispatch review action must carry an available `recovery_plan` with rollback or compensation references before closure.",
    "Every UAO record must expose a `claim_ledger`; verified claims require evidence refs and evidence-free claims must be marked unverified.",
    "Every memory update must expose a `constitution`; recorded memory requires evidence refs, owner, scope, source refs, allowed uses, and mutation history.",
    "Every UAO record must expose a `fracture_report`; execution-allowed records require fracture status `passed`, no blocking checks, and a canonical fracture pipeline stage before execution.",
    "Every canonical UAO record must expose a `life_meaning_judgment`.",
    "life_meaning_judgment.decision = pass -> truth preserved, dignity boundary pass, no domination risk, consent satisfied when required, and no unknown effect-bearing meaning impact",
    "docs/LIFE_MEANING_GOVERNANCE_KERNEL.md",
    "Every canonical UAO record must expose a `life_continuity_judgment`.",
    "life_continuity_judgment.decision = pass -> truth preserved, dignity boundary pass, no domination risk, and no high or unknown lived-meaning risk",
    "docs/LIFE_CONTINUITY_CONFLICT_DOCTRINE.md",
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
        raise FileNotFoundError(
            f"missing Universal Action Orchestration document: {document_path}"
        )
    if not document_path.is_file():
        raise IsADirectoryError(
            f"Universal Action Orchestration document path is not a file: {document_path}"
        )
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
    errors.extend(
        _validate_required_properties("schema", schema, "root", REQUIRED_ROOT_FIELDS)
    )
    properties = schema.get("properties")
    if isinstance(properties, dict):
        for property_name in ("life_meaning_judgment", "life_continuity_judgment"):
            if property_name not in properties:
                errors.append(f"schema: root missing property: {property_name}")
    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        errors.append("schema $defs must be an object")
        return errors
    for definition_name in (
        "life_meaning_affected_symbol",
        "life_meaning_impact",
        "life_meaning_delta",
        "life_meaning_boundary_state",
        "life_continuity_impact",
        "life_continuity_delta",
    ):
        if definition_name not in defs:
            errors.append(f"schema missing definition: {definition_name}")
    for definition_name, required_fields in REQUIRED_SCHEMA_DEFS.items():
        errors.extend(
            _validate_required_properties(
                "schema", defs.get(definition_name), definition_name, required_fields
            )
        )
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

    errors = _validate_required_fields("orchestration", record, CANONICAL_ROOT_FIELDS)
    if errors:
        return errors
    errors.extend(_validate_no_private_reasoning_fields(record))

    for field_name in (
        "orchestration_id",
        "action_id",
        "tenant_id",
        "actor_id",
        "created_at",
    ):
        if not isinstance(record[field_name], str) or not record[field_name]:
            errors.append(f"orchestration.{field_name} must be a non-empty string")
    if record["uao_schema_version"] != EXPECTED_SCHEMA_VERSION:
        errors.append("orchestration.uao_schema_version must be uao.v1")
    if record["raw_reasoning_included"] is not False:
        errors.append("orchestration.raw_reasoning_included must be false")
    if not isinstance(record["effect_bearing"], bool):
        errors.append("orchestration.effect_bearing must be boolean")
    errors.extend(_validate_action_envelope(record["action_envelope"], record))

    errors.extend(
        _validate_string_array("orchestration.effect_classes", record["effect_classes"])
    )
    errors.extend(
        _validate_string_array(
            "orchestration.input_refs", record["input_refs"], min_count=1
        )
    )
    errors.extend(
        _validate_string_array(
            "orchestration.policy_refs", record["policy_refs"], min_count=1
        )
    )
    errors.extend(
        _validate_string_array(
            "orchestration.capability_refs", record["capability_refs"], min_count=1
        )
    )
    errors.extend(
        _validate_string_array(
            "orchestration.temporal_refs", record["temporal_refs"], min_count=1
        )
    )
    errors.extend(_validate_recovery_plan(record["recovery_plan"], record["decision"]))
    errors.extend(_validate_claim_ledger(record["claim_ledger"], record))
    errors.extend(_validate_fracture_report(record["fracture_report"], record))
    errors.extend(
        _validate_life_meaning_judgment(
            record["life_meaning_judgment"], record
        )
    )
    errors.extend(
        _validate_life_continuity_judgment(
            record["life_continuity_judgment"], record
        )
    )
    errors.extend(_validate_life_judgment_projection(record))
    errors.extend(_validate_exposure_boundary(record["exposure_boundary"]))

    stages_by_kind: dict[str, dict[str, Any]] = {}
    stages_by_id: dict[str, dict[str, Any]] = {}
    errors.extend(
        _validate_pipeline_stages(
            record["pipeline_stages"], stages_by_kind, stages_by_id
        )
    )

    guards_by_name: dict[str, dict[str, Any]] = {}
    errors.extend(
        _validate_admission_guards(record["admission_guards"], guards_by_name)
    )
    errors.extend(
        _validate_decision(record["decision"], guards_by_name, stages_by_kind)
    )
    errors.extend(
        _validate_fracture_stage_binding(
            record["fracture_report"], record["decision"], stages_by_kind
        )
    )
    errors.extend(_validate_trace_binding(record, stages_by_kind))

    receipt_ids: set[str] = set()
    receipt_kinds: set[str] = set()
    errors.extend(
        _validate_receipts(record["receipts"], stages_by_id, receipt_ids, receipt_kinds)
    )
    errors.extend(
        _validate_reconciliation(record["reconciliation"], record["decision"])
    )
    errors.extend(_validate_memory_update(record["memory_update"]))
    errors.extend(
        _validate_closure(
            record["closure"],
            record["decision"],
            receipt_ids,
            stages_by_kind,
            record["reconciliation"],
            record["memory_update"],
            record["receipts"],
        )
    )
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
        record = load_json_object(
            example_path, f"Universal Action Orchestration example {example_path.name}"
        )
        errors.extend(
            f"{example_path.name}: {error}" for error in validate_orchestration(record)
        )
    errors.extend(validate_runtime_bypass_detector())
    return errors


def validate_runtime_bypass_detector() -> list[str]:
    """Return deterministic errors for direct runtime bypass findings."""

    report = build_detection_report()
    errors: list[str] = []
    for parse_error in report["parse_errors"]:
        errors.append(f"runtime bypass detector parse error: {parse_error}")
    for finding in report["findings"]:
        if finding["classification"] == "violation":
            errors.append(
                "runtime bypass detector violation: "
                f"{finding['path']}:{finding['line']} "
                f"{finding['symbol']} {finding['call']} - {finding['reason']}"
            )
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
        "universal_action_orchestration_runtime_bypass_detector",
    )
    try:
        errors = validate_contract(schema_path, example_paths, document_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [
            f"load-universal-action-orchestration: {_sanitize_receipt_error(exc, schema_path, example_paths, document_path)}"
        ]
    valid = not errors
    return {
        "receipt_id": "universal_action_orchestration_validation_receipt",
        "terminal_closure_required": True,
        "receipt_is_not_terminal_closure": True,
        "valid": valid,
        "status": "passed" if valid else "failed",
        "schema_path": _receipt_path_label(schema_path),
        "document_path": _receipt_path_label(document_path),
        "example_paths": [
            _receipt_path_label(example_path) for example_path in example_paths
        ],
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


def validate_validation_receipt_scope(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    example_paths: tuple[Path, ...] = DEFAULT_EXAMPLE_PATHS,
    document_path: Path = DEFAULT_DOCUMENT_PATH,
) -> list[str]:
    """Return deterministic errors for non-canonical validation receipt scope."""

    errors: list[str] = []
    if _resolve_scope_path(schema_path) != DEFAULT_SCHEMA_PATH.resolve():
        errors.append("receipt scope schema_path must be the canonical UAO schema")
    if _resolve_scope_path(document_path) != DEFAULT_DOCUMENT_PATH.resolve():
        errors.append("receipt scope document_path must be the canonical UAO doctrine")
    observed_examples = tuple(
        _resolve_scope_path(example_path) for example_path in example_paths
    )
    expected_examples = tuple(
        example_path.resolve() for example_path in DEFAULT_EXAMPLE_PATHS
    )
    if observed_examples != expected_examples:
        errors.append(
            "receipt scope example_paths must preserve the canonical UAO fixture set and order"
        )
    return errors


def validate_validation_receipt_report_scope(report: dict[str, Any]) -> list[str]:
    """Return deterministic errors when a report cannot be persisted as a receipt."""

    errors: list[str] = []
    if report.get("schema_path") != _receipt_path_label(DEFAULT_SCHEMA_PATH):
        errors.append("receipt report schema_path must bind the canonical UAO schema")
    if report.get("document_path") != _receipt_path_label(DEFAULT_DOCUMENT_PATH):
        errors.append(
            "receipt report document_path must bind the canonical UAO doctrine"
        )
    expected_example_labels = tuple(
        _receipt_path_label(example_path) for example_path in DEFAULT_EXAMPLE_PATHS
    )
    if tuple(report.get("example_paths", ())) != expected_example_labels:
        errors.append(
            "receipt report example_paths must bind the canonical UAO fixture set and order"
        )
    if report.get("example_count") != len(DEFAULT_EXAMPLE_PATHS):
        errors.append(
            "receipt report example_count must match the canonical UAO fixture count"
        )
    return errors


def resolve_validation_receipt_path(
    receipt_path: Path, workspace_root: Path = WORKSPACE_ROOT
) -> Path:
    """Resolve a workspace-local JSON receipt path and reject path escapes."""

    if receipt_path.suffix.lower() != ".json":
        raise ValueError("UAO validation receipt path must use .json suffix")
    resolved_root = workspace_root.resolve()
    resolved_path = (
        (workspace_root / receipt_path).resolve()
        if not receipt_path.is_absolute()
        else receipt_path.resolve()
    )
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError(
            f"UAO validation receipt path must stay under workspace root: {receipt_path}"
        )
    return resolved_path


def write_validation_report(
    report: dict[str, Any],
    receipt_path: Path,
    workspace_root: Path = WORKSPACE_ROOT,
) -> Path:
    """Persist a UAO validation receipt without executing actions."""

    receipt_scope_errors = validate_validation_receipt_report_scope(report)
    if receipt_scope_errors:
        raise ValueError("; ".join(receipt_scope_errors))
    resolved_path = resolve_validation_receipt_path(receipt_path, workspace_root)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return resolved_path


def _resolve_scope_path(path: Path) -> Path:
    """Resolve a path for receipt-scope comparison without requiring existence."""

    return path.resolve(strict=False)


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
            errors.append(
                f"{contract_name}: {fragment_name} missing required field: {field_name}"
            )
        if field_name not in properties:
            errors.append(
                f"{contract_name}: {fragment_name} missing property: {field_name}"
            )
    return errors


def _validate_required_fields(
    label: str, record: Any, fields: tuple[str, ...]
) -> list[str]:
    if not isinstance(record, dict):
        return [f"{label} must be an object"]
    return [
        f"{label} missing field: {field_name}"
        for field_name in fields
        if field_name not in record
    ]


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
    if exposure_boundary["redaction_level"] not in {
        "internal",
        "operator",
        "user_safe",
        "audit",
        "external",
    }:
        errors.append("exposure_boundary.redaction_level is invalid")
    errors.extend(
        _validate_string_array(
            "exposure_boundary.allowed_audiences",
            exposure_boundary["allowed_audiences"],
            1,
        )
    )
    errors.extend(
        _validate_string_array(
            "exposure_boundary.blocked_payload_classes",
            exposure_boundary["blocked_payload_classes"],
            1,
        )
    )
    if "raw_private_reasoning" not in exposure_boundary["blocked_payload_classes"]:
        errors.append(
            "exposure_boundary.blocked_payload_classes must include raw_private_reasoning"
        )
    return errors


def _validate_recovery_plan(
    recovery_plan: Any,
    decision: dict[str, Any],
) -> list[str]:
    errors = _validate_required_fields(
        "recovery_plan",
        recovery_plan,
        (
            "available",
            "recovery_plan_ref",
            "recovery_kind",
            "rollback_plan_ref",
            "compensation_plan_ref",
            "review_required_on_failure",
            "certificate_ref",
            "effect_plan_ref",
        ),
    )
    if errors:
        return errors
    if not isinstance(recovery_plan["available"], bool):
        errors.append("recovery_plan.available must be boolean")
    if recovery_plan["recovery_kind"] not in {
        "none",
        "rollback",
        "compensation",
        "rollback_and_compensation",
    }:
        errors.append("recovery_plan.recovery_kind is invalid")
    for field_name in (
        "recovery_plan_ref",
        "rollback_plan_ref",
        "compensation_plan_ref",
        "certificate_ref",
        "effect_plan_ref",
    ):
        value = recovery_plan[field_name]
        if value is not None and (not isinstance(value, str) or not value):
            errors.append(f"recovery_plan.{field_name} must be null or non-empty string")
    if not isinstance(recovery_plan["review_required_on_failure"], bool):
        errors.append("recovery_plan.review_required_on_failure must be boolean")
    if recovery_plan["available"]:
        if recovery_plan["recovery_kind"] == "none":
            errors.append("recovery_plan.available requires a recovery kind")
        if not recovery_plan["recovery_plan_ref"]:
            errors.append("recovery_plan.available requires recovery_plan_ref")
        if not recovery_plan["certificate_ref"]:
            errors.append("recovery_plan.available requires certificate_ref")
        if not recovery_plan["effect_plan_ref"]:
            errors.append("recovery_plan.available requires effect_plan_ref")
        if (
            not recovery_plan["rollback_plan_ref"]
            and not recovery_plan["compensation_plan_ref"]
        ):
            errors.append(
                "recovery_plan.available requires rollback or compensation plan ref"
            )
    else:
        if recovery_plan["recovery_kind"] != "none":
            errors.append("recovery_plan unavailable must use recovery_kind none")
        if decision.get("status") == "allow":
            errors.append("allow decision requires available recovery_plan")
    if decision.get("reason_code") == "recovery_plan_missing" and recovery_plan[
        "available"
    ]:
        errors.append("recovery_plan_missing decision cannot carry available recovery_plan")
    errors.extend(_validate_causal_repair_recovery_fields(recovery_plan, decision))
    return errors


def _validate_causal_repair_recovery_fields(
    recovery_plan: dict[str, Any],
    decision: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    status = recovery_plan.get("causal_repair_admission_status")
    if status is None:
        return errors
    if status not in {"not_required", "admitted", "blocked", "approval_required"}:
        errors.append("recovery_plan.causal_repair_admission_status is invalid")
    for field_name in (
        "causal_repair_admission_ref",
        "causal_repair_admission_reason",
        "causal_repair_effect_class",
        "causal_repair_reversibility_class",
        "causal_repair_template_id",
        "causal_repair_template_reason",
        "causal_repair_template_required_strategy",
    ):
        value = recovery_plan.get(field_name)
        if value is not None and (not isinstance(value, str) or not value):
            errors.append(f"recovery_plan.{field_name} must be null or non-empty string")
    template_status = recovery_plan.get("causal_repair_template_status")
    if template_status is not None and template_status not in {
        "admitted",
        "blocked",
        "approval_required",
        "template_missing",
    }:
        errors.append("recovery_plan.causal_repair_template_status is invalid")
    snapshot_quality = recovery_plan.get("causal_repair_snapshot_quality")
    if snapshot_quality is not None:
        if (
            not isinstance(snapshot_quality, int)
            or isinstance(snapshot_quality, bool)
            or snapshot_quality < 0
            or snapshot_quality > 5
        ):
            errors.append("recovery_plan.causal_repair_snapshot_quality must be 0 through 5 or null")
    for field_name in (
        "causal_repair_idempotency_required",
        "causal_repair_idempotency_present",
    ):
        value = recovery_plan.get(field_name)
        if value is not None and not isinstance(value, bool):
            errors.append(f"recovery_plan.{field_name} must be boolean")
    if status in {"admitted", "blocked", "approval_required"}:
        if not recovery_plan.get("causal_repair_admission_ref"):
            errors.append("causal repair admission status requires admission ref")
        if not recovery_plan.get("causal_repair_admission_reason"):
            errors.append("causal repair admission status requires admission reason")
    if (
        recovery_plan.get("causal_repair_idempotency_required") is True
        and recovery_plan.get("causal_repair_idempotency_present") is not True
        and decision.get("status") == "allow"
    ):
        errors.append("allow decision cannot omit required causal repair idempotency")
    if (
        isinstance(decision.get("reason_code"), str)
        and decision["reason_code"].startswith("causal_repair_admission_")
        and status == "admitted"
    ):
        errors.append("causal repair admission block cannot carry admitted status")
    if (
        decision.get("status") == "allow"
        and template_status in {"blocked", "approval_required", "template_missing"}
    ):
        errors.append("allow decision cannot carry blocked causal repair template")
    return errors


def _validate_claim_ledger(claim_ledger: Any, record: dict[str, Any]) -> list[str]:
    errors = _validate_required_fields(
        "claim_ledger",
        claim_ledger,
        ("ledger_ref", "claims", "unverified_claim_ids"),
    )
    if errors:
        return errors
    if not isinstance(claim_ledger["ledger_ref"], str) or not claim_ledger["ledger_ref"]:
        errors.append("claim_ledger.ledger_ref must be a non-empty string")
    errors.extend(
        _validate_string_array(
            "claim_ledger.unverified_claim_ids",
            claim_ledger["unverified_claim_ids"],
        )
    )
    claims = claim_ledger["claims"]
    if not isinstance(claims, list):
        return [*errors, "claim_ledger.claims must be a list"]
    if not claims:
        errors.append("claim_ledger.claims must contain at least one claim")
    claim_ids: set[str] = set()
    known_refs = _known_claim_evidence_refs(record)
    unverified_claim_ids = set(claim_ledger["unverified_claim_ids"])
    for index, claim in enumerate(claims):
        label = f"claim_ledger.claims[{index}]"
        errors.extend(_validate_claim_record(label, claim))
        if not isinstance(claim, dict) or any(
            field not in claim for field in REQUIRED_SCHEMA_DEFS["claim"]
        ):
            continue
        claim_id = claim["claim_id"]
        if claim_id in claim_ids:
            errors.append(f"duplicate claim_id: {claim_id}")
        else:
            claim_ids.add(claim_id)
        evidence_refs = claim["evidence_refs"]
        verified = claim["verified"]
        if verified and not evidence_refs:
            errors.append(f"{label}: verified claim requires evidence_refs")
        if not evidence_refs and verified is False and claim_id not in unverified_claim_ids:
            errors.append(
                f"{label}: evidence-free claim must appear in unverified_claim_ids"
            )
        if evidence_refs and verified is False and claim_id not in unverified_claim_ids:
            errors.append(f"{label}: unverified claim must appear in unverified_claim_ids")
        for evidence_ref in evidence_refs:
            if evidence_ref not in known_refs:
                errors.append(f"{label}.evidence_refs references unknown evidence: {evidence_ref}")
    if unknown_unverified := sorted(unverified_claim_ids - claim_ids):
        errors.append(
            "claim_ledger.unverified_claim_ids references unknown claim(s): "
            + ", ".join(unknown_unverified)
        )
    for claim in claims:
        if (
            isinstance(claim, dict)
            and claim.get("claim_id") in unverified_claim_ids
            and claim.get("verified") is True
        ):
            errors.append(
                f"claim_ledger.unverified_claim_ids includes verified claim: {claim['claim_id']}"
            )
    return errors


def _validate_claim_record(label: str, claim: Any) -> list[str]:
    errors = _validate_required_fields(label, claim, REQUIRED_SCHEMA_DEFS["claim"])
    if errors:
        return errors
    for field_name in ("claim_id", "claim_type", "statement"):
        if not isinstance(claim[field_name], str) or not claim[field_name]:
            errors.append(f"{label}.{field_name} must be a non-empty string")
    if claim["claim_type"] not in {
        "decision",
        "execution",
        "reconciliation",
        "memory",
        "closure",
        "recovery",
    }:
        errors.append(f"{label}.claim_type is invalid")
    errors.extend(_validate_string_array(f"{label}.evidence_refs", claim["evidence_refs"]))
    confidence = claim["confidence"]
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0 <= confidence <= 1
    ):
        errors.append(f"{label}.confidence must be a number in [0, 1]")
    if not isinstance(claim["verified"], bool):
        errors.append(f"{label}.verified must be boolean")
    return errors


def _validate_fracture_report(
    fracture_report: Any, record: dict[str, Any]
) -> list[str]:
    errors = _validate_required_fields(
        "fracture_report",
        fracture_report,
        ("report_ref", "status", "checks", "blocking_check_ids", "risk_notes"),
    )
    if errors:
        return errors
    if not isinstance(fracture_report["report_ref"], str) or not fracture_report[
        "report_ref"
    ]:
        errors.append("fracture_report.report_ref must be a non-empty string")
    if fracture_report["status"] not in {"passed", "failed", "skipped"}:
        errors.append("fracture_report.status is invalid")
    errors.extend(
        _validate_string_array(
            "fracture_report.blocking_check_ids",
            fracture_report["blocking_check_ids"],
        )
    )
    errors.extend(
        _validate_string_array("fracture_report.risk_notes", fracture_report["risk_notes"])
    )

    checks = fracture_report["checks"]
    if not isinstance(checks, list):
        return [*errors, "fracture_report.checks must be a list"]
    if not checks:
        errors.append("fracture_report.checks must contain at least one check")

    check_ids: set[str] = set()
    blocking_check_ids = set(fracture_report["blocking_check_ids"])
    observed_blocking_ids: set[str] = set()
    for index, check in enumerate(checks):
        label = f"fracture_report.checks[{index}]"
        errors.extend(_validate_fracture_check(label, check))
        if not isinstance(check, dict) or "check_id" not in check:
            continue
        check_id = check["check_id"]
        if isinstance(check_id, str) and check_id:
            if check_id in check_ids:
                errors.append(f"duplicate fracture check_id: {check_id}")
            check_ids.add(check_id)
            if check.get("blocking") is True:
                observed_blocking_ids.add(check_id)

    unknown_blocking_ids = blocking_check_ids.difference(check_ids)
    if unknown_blocking_ids:
        errors.append(
            "fracture_report.blocking_check_ids references unknown check(s): "
            + ", ".join(sorted(unknown_blocking_ids))
        )
    if blocking_check_ids != observed_blocking_ids:
        errors.append(
            "fracture_report.blocking_check_ids must match blocking failed checks"
        )
    if fracture_report["status"] == "passed" and blocking_check_ids:
        errors.append("fracture_report: passed status cannot include blocking checks")
    if fracture_report["status"] == "failed" and not blocking_check_ids:
        errors.append("fracture_report: failed status requires blocking checks")
    execution_observed = record["decision"]["execution_allowed"] or record.get(
        "execution_receipt_ref"
    )
    if execution_observed:
        if fracture_report["status"] != "passed":
            errors.append("execution requires fracture_report.status passed")
        if blocking_check_ids:
            errors.append("execution requires no fracture blocking_check_ids")
    return errors


def _validate_fracture_check(label: str, check: Any) -> list[str]:
    errors = _validate_required_fields(
        label,
        check,
        (
            "check_id",
            "check_type",
            "status",
            "proof_state",
            "reason_code",
            "evidence_refs",
            "blocking",
        ),
    )
    if errors:
        return errors
    for field_name in ("check_id", "reason_code"):
        if not isinstance(check[field_name], str) or not check[field_name]:
            errors.append(f"{label}.{field_name} must be a non-empty string")
    if check["check_type"] not in {
        "policy_conflict",
        "identity_conflict",
        "budget_conflict",
        "schema_conflict",
        "capability_mismatch",
        "memory_contradiction",
        "unverified_claim",
        "missing_recovery",
        "authority_mismatch",
        "duplicate_command",
        "prompt_injection",
    }:
        errors.append(f"{label}.check_type is invalid")
    if check["status"] not in {"passed", "failed", "waived", "not_applicable"}:
        errors.append(f"{label}.status is invalid")
    if check["proof_state"] not in PROOF_STATES:
        errors.append(f"{label}.proof_state is invalid")
    if not isinstance(check["blocking"], bool):
        errors.append(f"{label}.blocking must be boolean")
    if check["blocking"] and check["status"] != "failed":
        errors.append(f"{label}: blocking check must have failed status")
    if check["status"] == "failed" and not check["blocking"]:
        errors.append(f"{label}: failed check must be blocking")
    errors.extend(_validate_string_array(f"{label}.evidence_refs", check["evidence_refs"]))
    return errors


def _validate_life_meaning_judgment(
    judgment: Any,
    record: dict[str, Any],
) -> list[str]:
    errors = _validate_required_fields(
        "life_meaning_judgment",
        judgment,
        REQUIRED_SCHEMA_DEFS["life_meaning_judgment"],
    )
    if errors:
        return errors
    for field_name in ("judgment_id", "action_id"):
        if not isinstance(judgment[field_name], str) or not judgment[field_name]:
            errors.append(
                f"life_meaning_judgment.{field_name} must be a non-empty string"
            )
    if judgment["action_id"] != record["action_id"]:
        errors.append("life_meaning_judgment.action_id must match orchestration.action_id")
    if judgment["decision"] not in LIFE_MEANING_DECISIONS:
        errors.append("life_meaning_judgment.decision is invalid")
    for field_name in ("life_impact", "feeling_impact", "meaning_impact"):
        if judgment[field_name] not in LIFE_MEANING_IMPACTS:
            errors.append(f"life_meaning_judgment.{field_name} is invalid")
    for field_name in ("love_delta", "resonance_delta", "continuity_delta"):
        if judgment[field_name] not in LIFE_MEANING_DELTAS:
            errors.append(f"life_meaning_judgment.{field_name} is invalid")
    if judgment["dignity_boundary"] not in LIFE_MEANING_BOUNDARY_STATES:
        errors.append("life_meaning_judgment.dignity_boundary is invalid")
    for field_name in (
        "truth_preserved",
        "consent_required",
        "consent_present",
        "domination_risk",
        "justice_repair_required",
        "irreversible",
        "approval_required",
        "rollback_required",
    ):
        if not isinstance(judgment[field_name], bool):
            errors.append(f"life_meaning_judgment.{field_name} must be boolean")

    errors.extend(_validate_life_meaning_affected_symbols(judgment["affected_symbols"]))
    errors.extend(
        _validate_string_array(
            "life_meaning_judgment.reasons",
            judgment["reasons"],
            min_count=1,
        )
    )
    errors.extend(
        _validate_string_array(
            "life_meaning_judgment.evidence_refs",
            judgment["evidence_refs"],
        )
    )

    known_refs = _known_claim_evidence_refs(record)
    for evidence_ref in judgment["evidence_refs"]:
        if evidence_ref not in known_refs:
            errors.append(
                "life_meaning_judgment.evidence_refs references unknown evidence: "
                f"{evidence_ref}"
            )

    life_decision = judgment["decision"]
    action_decision = record["decision"]["status"]
    if action_decision == "allow" and life_decision != "pass":
        errors.append("allow decision requires life_meaning_judgment.decision pass")
    if action_decision == "escalate" and life_decision != "escalate":
        errors.append(
            "escalate decision requires life_meaning_judgment.decision escalate"
        )
    if action_decision == "defer" and life_decision not in {"pause", "escalate"}:
        errors.append(
            "defer decision requires life_meaning_judgment.decision pause or escalate"
        )

    if life_decision == "pass":
        if judgment["truth_preserved"] is not True:
            errors.append(
                "life_meaning_judgment.decision pass requires truth_preserved true"
            )
        if judgment["dignity_boundary"] != "pass":
            errors.append(
                "life_meaning_judgment.decision pass requires dignity_boundary pass"
            )
        if judgment["domination_risk"] is not False:
            errors.append(
                "life_meaning_judgment.decision pass requires domination_risk false"
            )
        if judgment["consent_required"] and not judgment["consent_present"]:
            errors.append(
                "life_meaning_judgment.decision pass requires consent_present when consent_required"
            )
        for field_name in ("love_delta", "resonance_delta", "continuity_delta"):
            if judgment[field_name] == "negative":
                errors.append(
                    f"life_meaning_judgment.decision pass rejects negative {field_name}"
                )
        if record["effect_bearing"] and judgment["meaning_impact"] == "unknown":
            errors.append(
                "effect-bearing pass requires known life_meaning_judgment.meaning_impact"
            )

    unknown_life_meaning = (
        judgment["life_impact"] == "unknown"
        or judgment["feeling_impact"] == "unknown"
        or judgment["meaning_impact"] == "unknown"
        or _life_meaning_symbols_include_unknown(judgment["affected_symbols"])
    )
    if judgment["irreversible"] and unknown_life_meaning and life_decision != "escalate":
        errors.append(
            "irreversible unknown life, feeling, or meaning impact requires escalation"
        )
    if judgment["truth_preserved"] is False and life_decision not in {"block", "escalate"}:
        errors.append(
            "life_meaning_judgment.truth_preserved false requires block or escalate"
        )
    if judgment["dignity_boundary"] == "fail" and life_decision not in {
        "block",
        "escalate",
    }:
        errors.append(
            "life_meaning_judgment.dignity_boundary fail requires block or escalate"
        )
    if judgment["domination_risk"] and life_decision not in {"block", "escalate"}:
        errors.append(
            "life_meaning_judgment.domination_risk true requires block or escalate"
        )
    if (
        judgment["consent_required"]
        and not judgment["consent_present"]
        and judgment["irreversible"]
        and life_decision != "escalate"
    ):
        errors.append(
            "irreversible consent-missing life-meaning action requires escalation"
        )
    if life_decision in {"pause", "escalate"} and judgment["approval_required"] is not True:
        errors.append(
            "life_meaning_judgment pause or escalate requires approval_required true"
        )
    if judgment["irreversible"] and judgment["rollback_required"] is not True:
        errors.append(
            "life_meaning_judgment irreversible action requires rollback_required true"
        )
    if (
        life_decision == "pass"
        and judgment["life_impact"] in {"direct", "indirect", "unknown"}
        and not judgment["evidence_refs"]
    ):
        errors.append(
            "life_meaning_judgment pass with life impact requires evidence_refs"
        )
    if (
        life_decision == "pass"
        and judgment["meaning_impact"] in {"direct", "indirect", "unknown"}
        and not judgment["evidence_refs"]
    ):
        errors.append(
            "life_meaning_judgment pass with meaning impact requires evidence_refs"
        )
    return errors


def _validate_life_meaning_affected_symbols(symbols: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(symbols, list) or not symbols:
        return ["life_meaning_judgment.affected_symbols must be a non-empty list"]
    for index, symbol in enumerate(symbols):
        label = f"life_meaning_judgment.affected_symbols[{index}]"
        errors.extend(
            _validate_required_fields(
                label,
                symbol,
                REQUIRED_SCHEMA_DEFS["life_meaning_affected_symbol"],
            )
        )
        if not isinstance(symbol, dict):
            errors.append(f"{label} must be an object")
            continue
        if any(
            field_name not in symbol
            for field_name in REQUIRED_SCHEMA_DEFS["life_meaning_affected_symbol"]
        ):
            continue
        for field_name in ("symbol_id", "symbol_kind"):
            if not isinstance(symbol[field_name], str) or not symbol[field_name]:
                errors.append(f"{label}.{field_name} must be a non-empty string")
        if symbol["life_status"] not in LIFE_MEANING_LIFE_STATUSES:
            errors.append(f"{label}.life_status is invalid")
        if symbol["feeling_status"] not in LIFE_MEANING_FEELING_STATUSES:
            errors.append(f"{label}.feeling_status is invalid")
        if symbol["meaning_bearing"] not in LIFE_MEANING_IMPACTS:
            errors.append(f"{label}.meaning_bearing is invalid")
        for field_name in ("fragility_level", "agency_level"):
            if (
                not isinstance(symbol[field_name], int)
                or symbol[field_name] < 0
                or symbol[field_name] > 10
            ):
                errors.append(f"{label}.{field_name} must be an integer in [0,10]")
    return errors


def _life_meaning_symbols_include_unknown(symbols: Any) -> bool:
    if not isinstance(symbols, list):
        return False
    return any(
        isinstance(symbol, dict)
        and (
            symbol.get("life_status") == "unknown"
            or symbol.get("feeling_status") == "unknown"
            or symbol.get("meaning_bearing") == "unknown"
        )
        for symbol in symbols
    )


def _validate_life_judgment_projection(record: dict[str, Any]) -> list[str]:
    meaning = record["life_meaning_judgment"]
    continuity = record["life_continuity_judgment"]
    errors: list[str] = []
    field_pairs = (
        ("life_impact", "life_impact"),
        ("feeling_impact", "feeling_impact"),
        ("meaning_impact", "meaning_impact"),
        ("continuity_delta", "meaning_continuity_delta"),
        ("love_delta", "love_delta"),
        ("resonance_delta", "resonance_delta"),
        ("dignity_boundary", "dignity_boundary"),
        ("truth_preserved", "truth_preserved"),
        ("domination_risk", "domination_risk"),
        ("decision", "decision"),
    )
    for meaning_field, continuity_field in field_pairs:
        if meaning.get(meaning_field) != continuity.get(continuity_field):
            errors.append(
                "life_continuity_judgment must project life_meaning_judgment "
                f"{meaning_field}->{continuity_field}"
            )
    value_bearing_expected = (
        meaning.get("life_impact") in {"direct", "indirect", "unknown"}
        or meaning.get("feeling_impact") in {"direct", "indirect", "unknown"}
        or meaning.get("meaning_impact") in {"direct", "indirect", "unknown"}
    )
    if continuity.get("value_bearing_symbol") is not value_bearing_expected:
        errors.append(
            "life_continuity_judgment.value_bearing_symbol must project life_meaning_judgment impact"
        )
    return errors


def _validate_life_continuity_judgment(
    judgment: Any,
    record: dict[str, Any],
) -> list[str]:
    errors = _validate_required_fields(
        "life_continuity_judgment",
        judgment,
        REQUIRED_SCHEMA_DEFS["life_continuity_judgment"],
    )
    if errors:
        return errors
    for field_name in ("judgment_ref", "conflict_law_ref"):
        if not isinstance(judgment[field_name], str) or not judgment[field_name]:
            errors.append(
                f"life_continuity_judgment.{field_name} must be a non-empty string"
            )
    for field_name in (
        "life_impact",
        "feeling_impact",
        "feeling_observer_impact",
        "meaning_impact",
    ):
        if judgment[field_name] not in LIFE_CONTINUITY_IMPACTS:
            errors.append(f"life_continuity_judgment.{field_name} is invalid")
    for field_name in (
        "meaning_continuity_delta",
        "love_delta",
        "resonance_delta",
    ):
        if judgment[field_name] not in LIFE_CONTINUITY_DELTAS:
            errors.append(f"life_continuity_judgment.{field_name} is invalid")
    if judgment["lived_meaning_risk"] not in LIFE_CONTINUITY_RISKS:
        errors.append("life_continuity_judgment.lived_meaning_risk is invalid")
    if judgment["dignity_boundary"] not in LIFE_CONTINUITY_BOUNDARY_STATES:
        errors.append("life_continuity_judgment.dignity_boundary is invalid")
    if judgment["decision"] not in LIFE_CONTINUITY_DECISIONS:
        errors.append("life_continuity_judgment.decision is invalid")
    for field_name in ("value_bearing_symbol", "truth_preserved", "domination_risk", "review_required"):
        if not isinstance(judgment[field_name], bool):
            errors.append(f"life_continuity_judgment.{field_name} must be boolean")
    errors.extend(
        _validate_string_array(
            "life_continuity_judgment.evidence_refs",
            judgment["evidence_refs"],
            min_count=1,
        )
    )
    if judgment["feeling_impact"] != judgment["feeling_observer_impact"]:
        errors.append(
            "life_continuity_judgment.feeling_impact must match feeling_observer_impact"
        )

    known_refs = _known_claim_evidence_refs(record)
    for evidence_ref in judgment["evidence_refs"]:
        if evidence_ref not in known_refs:
            errors.append(
                "life_continuity_judgment.evidence_refs references unknown evidence: "
                f"{evidence_ref}"
            )

    life_decision = judgment["decision"]
    action_decision = record["decision"]["status"]
    if action_decision == "allow" and life_decision != "pass":
        errors.append("allow decision requires life_continuity_judgment.decision pass")
    if action_decision == "escalate" and life_decision != "escalate":
        errors.append(
            "escalate decision requires life_continuity_judgment.decision escalate"
        )
    if action_decision == "defer" and life_decision not in {"pause", "escalate"}:
        errors.append(
            "defer decision requires life_continuity_judgment.decision pause or escalate"
        )

    if life_decision == "pass":
        if judgment["truth_preserved"] is not True:
            errors.append(
                "life_continuity_judgment.decision pass requires truth_preserved true"
            )
        if judgment["dignity_boundary"] != "pass":
            errors.append(
                "life_continuity_judgment.decision pass requires dignity_boundary pass"
            )
        if judgment["domination_risk"] is not False:
            errors.append(
                "life_continuity_judgment.decision pass requires domination_risk false"
            )
        if judgment["meaning_continuity_delta"] == "negative":
            errors.append(
                "life_continuity_judgment.decision pass rejects negative meaning_continuity_delta"
            )
        if judgment["lived_meaning_risk"] in {"high", "unknown"}:
            errors.append(
                "life_continuity_judgment.decision pass rejects high or unknown lived_meaning_risk"
            )
        if record["effect_bearing"] and judgment["meaning_impact"] == "unknown":
            errors.append(
                "effect-bearing pass requires known life_continuity_judgment.meaning_impact"
            )
    if judgment["dignity_boundary"] == "fail" and life_decision not in {
        "block",
        "escalate",
    }:
        errors.append(
            "life_continuity_judgment.dignity_boundary fail requires block or escalate"
        )
    if judgment["domination_risk"] and life_decision not in {"block", "escalate"}:
        errors.append(
            "life_continuity_judgment.domination_risk true requires block or escalate"
        )
    if judgment["lived_meaning_risk"] == "high" and life_decision not in {
        "block",
        "escalate",
    }:
        errors.append(
            "life_continuity_judgment.lived_meaning_risk high requires block or escalate"
        )
    if (
        record["effect_bearing"]
        and judgment["meaning_impact"] == "unknown"
        and life_decision == "pass"
    ):
        errors.append(
            "unknown meaning-impact on effect-bearing action cannot pass life-continuity judgment"
        )
    if life_decision in {"pause", "escalate"} and judgment["review_required"] is not True:
        errors.append(
            "life_continuity_judgment pause or escalate requires review_required true"
        )
    if (
        judgment["value_bearing_symbol"] is False
        and (
            judgment["life_impact"] in {"direct", "indirect"}
            or judgment["feeling_impact"] in {"direct", "indirect"}
            or judgment["meaning_impact"] in {"direct", "indirect"}
            or judgment["meaning_continuity_delta"] in {"positive", "negative"}
        )
    ):
        errors.append(
            "life_continuity_judgment.value_bearing_symbol false conflicts with declared life or meaning impact"
        )
    return errors


def _validate_fracture_stage_binding(
    fracture_report: Any,
    decision: dict[str, Any],
    stages_by_kind: dict[str, dict[str, Any]],
) -> list[str]:
    if not isinstance(fracture_report, dict):
        return []
    fracture_stage = stages_by_kind.get("fracture")
    execution_stage = stages_by_kind.get("execution")
    if not isinstance(fracture_stage, dict) or not isinstance(execution_stage, dict):
        return []
    errors: list[str] = []
    if fracture_stage["stage_order"] >= execution_stage["stage_order"]:
        errors.append("fracture stage must precede execution stage")
    report_ref = fracture_report.get("report_ref")
    if report_ref not in fracture_stage.get("output_refs", []):
        errors.append("fracture stage output_refs must include fracture_report.report_ref")
    if decision["execution_allowed"] and fracture_stage["status"] != "completed":
        errors.append("execution_allowed requires completed fracture stage")
    if (
        fracture_report.get("status") == "failed"
        and fracture_stage["status"] != "blocked"
    ):
        errors.append("failed fracture_report requires blocked fracture stage")
    return errors


def _known_claim_evidence_refs(record: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for field_name in (
        "input_refs",
        "policy_refs",
        "capability_refs",
        "temporal_refs",
    ):
        refs.update(_text_items(record.get(field_name)))
    refs.update(_text_items(record.get("action_envelope", {}).get("evidence_refs")))
    refs.update(_text_items(record.get("action_envelope", {}).get("capability_refs")))
    for field_name in (
        "trace_ref",
        "causal_decision_trace_ref",
        "admission_receipt_ref",
        "execution_receipt_ref",
        "closure_state",
    ):
        value = record.get(field_name)
        if isinstance(value, str) and value:
            refs.add(value)
    for receipt in record.get("receipts", ()):
        if isinstance(receipt, dict):
            refs.update(_text_items((receipt.get("receipt_id"), receipt.get("confirms"))))
    for stage in record.get("pipeline_stages", ()):
        if isinstance(stage, dict):
            refs.update(_text_items(stage.get("input_refs")))
            refs.update(_text_items(stage.get("output_refs")))
            refs.update(_text_items((stage.get("receipt_ref"),)))
    for guard in record.get("admission_guards", ()):
        if isinstance(guard, dict):
            refs.update(_text_items(guard.get("evidence_refs")))
    for field_name in ("recovery_plan", "reconciliation", "memory_update", "closure"):
        value = record.get(field_name)
        if isinstance(value, dict):
            refs.update(_iter_nested_text(value))
    return refs


def _text_items(value: Any) -> set[str]:
    if isinstance(value, str) and value:
        return {value}
    if isinstance(value, (list, tuple)):
        return {item for item in value if isinstance(item, str) and item}
    return set()


def _iter_nested_text(value: Any):
    if isinstance(value, str) and value:
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _iter_nested_text(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_nested_text(child)


def _validate_action_envelope(
    action_envelope: Any, record: dict[str, Any]
) -> list[str]:
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
        if (
            not isinstance(action_envelope[field_name], str)
            or not action_envelope[field_name]
        ):
            errors.append(f"action_envelope.{field_name} must be a non-empty string")
    if action_envelope["risk"] not in {"low", "H1", "H2", "H3", "H4"}:
        errors.append("action_envelope.risk is invalid")
    if action_envelope["approval_ref"] is not None and (
        not isinstance(action_envelope["approval_ref"], str)
        or not action_envelope["approval_ref"]
    ):
        errors.append("action_envelope.approval_ref must be null or a non-empty string")
    errors.extend(
        _validate_string_array(
            "action_envelope.evidence_refs", action_envelope["evidence_refs"]
        )
    )
    errors.extend(
        _validate_string_array(
            "action_envelope.capability_refs", action_envelope["capability_refs"]
        )
    )
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
                (
                    "stage_id",
                    "stage_order",
                    "stage_kind",
                    "status",
                    "input_refs",
                    "output_refs",
                    "receipt_ref",
                    "failure_reason",
                ),
            )
        )
        if not isinstance(stage, dict) or any(
            field not in stage
            for field in (
                "stage_id",
                "stage_order",
                "stage_kind",
                "status",
                "input_refs",
                "output_refs",
                "receipt_ref",
                "failure_reason",
            )
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
        if not isinstance(stage["stage_order"], int) or isinstance(
            stage["stage_order"], bool
        ):
            errors.append(f"{label}.stage_order must be an integer")
        else:
            observed_orders.append(stage["stage_order"])
        if stage["status"] not in {
            "completed",
            "blocked",
            "skipped",
            "deferred",
            "escalated",
            "simulated",
        }:
            errors.append(f"{label}.status is invalid")
        if (
            stage["status"] in {"blocked", "skipped", "deferred", "escalated"}
            and not stage["failure_reason"]
        ):
            errors.append(f"{label}: non-completed stage requires failure_reason")
        if stage["receipt_ref"] is not None and (
            not isinstance(stage["receipt_ref"], str) or not stage["receipt_ref"]
        ):
            errors.append(f"{label}.receipt_ref must be null or a non-empty string")
        if stage["failure_reason"] is not None and (
            not isinstance(stage["failure_reason"], str) or not stage["failure_reason"]
        ):
            errors.append(f"{label}.failure_reason must be null or a non-empty string")
        errors.extend(
            _validate_string_array(f"{label}.input_refs", stage["input_refs"])
        )
        errors.extend(
            _validate_string_array(f"{label}.output_refs", stage["output_refs"])
        )
    if tuple(observed_kinds) != PIPELINE_STAGE_KINDS:
        errors.append("pipeline_stages must contain canonical UAO stage kinds in order")
    if observed_orders != list(range(1, len(observed_orders) + 1)):
        errors.append(
            "pipeline_stages must use contiguous stage_order values starting at 1"
        )
    return errors


def _validate_admission_guards(
    guards: Any, guards_by_name: dict[str, dict[str, Any]]
) -> list[str]:
    if not isinstance(guards, list):
        return ["admission_guards must be a list"]
    errors: list[str] = []
    for index, guard in enumerate(guards):
        label = f"admission_guards[{index}]"
        errors.extend(
            _validate_required_fields(
                label,
                guard,
                ("guard", "verdict", "proof_state", "reason_code", "evidence_refs"),
            )
        )
        if not isinstance(guard, dict) or any(
            field not in guard
            for field in (
                "guard",
                "verdict",
                "proof_state",
                "reason_code",
                "evidence_refs",
            )
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
        errors.extend(
            _validate_string_array(f"{label}.evidence_refs", guard["evidence_refs"])
        )
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
        (
            "status",
            "reason_code",
            "proof_state",
            "solver_outcome",
            "next_action",
            "execution_allowed",
        ),
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
    post_dispatch_escalation = (
        decision["status"] == "escalate"
        and execution_stage.get("status") == "completed"
        and decision["reason_code"] == "effect_reconciliation_mismatch"
    )
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
        if execution_stage.get("status") == "completed" and not post_dispatch_escalation:
            errors.append("decision: non-allow status cannot complete execution stage")
        if decision["solver_outcome"] in PASSING_OUTCOMES:
            errors.append(
                "decision: non-allow status cannot use a passing solver outcome"
            )
    if decision["status"] == "block" and "blocked" not in guard_verdicts:
        errors.append("decision: block requires at least one blocked admission guard")
    if decision["status"] == "defer" and "deferred" not in guard_verdicts:
        errors.append("decision: defer requires at least one deferred admission guard")
    if decision["status"] == "escalate" and "escalated" not in guard_verdicts:
        errors.append(
            "decision: escalate requires at least one escalated admission guard"
        )
    if decision["status"] == "simulate" and "simulated" not in guard_verdicts:
        errors.append(
            "decision: simulate requires at least one simulated admission guard"
        )
    return errors


def _validate_trace_binding(
    record: dict[str, Any], stages_by_kind: dict[str, dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    trace_ref = record["trace_ref"]
    causal_trace_ref = record["causal_decision_trace_ref"]
    if not isinstance(trace_ref, str) or not trace_ref:
        errors.append("orchestration.trace_ref must be a non-empty string")
    if not isinstance(causal_trace_ref, str) or not causal_trace_ref:
        errors.append(
            "orchestration.causal_decision_trace_ref must be a non-empty string"
        )
    if trace_ref != causal_trace_ref:
        errors.append("trace_ref must match causal_decision_trace_ref")
    if record["effect_bearing"]:
        if not record["effect_classes"]:
            errors.append("effect-bearing action requires effect_classes")
        if not trace_ref or not causal_trace_ref:
            errors.append(
                "effect-bearing action requires trace_ref and causal_decision_trace_ref"
            )
    trace_stage = stages_by_kind.get("trace", {})
    output_refs = trace_stage.get("output_refs", [])
    if (
        causal_trace_ref
        and isinstance(output_refs, list)
        and causal_trace_ref not in output_refs
    ):
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
                (
                    "receipt_id",
                    "tier",
                    "kind",
                    "stage_id",
                    "confirms",
                    "external_state_confirmed",
                ),
            )
        )
        if not isinstance(receipt, dict) or any(
            field not in receipt
            for field in (
                "receipt_id",
                "tier",
                "kind",
                "stage_id",
                "confirms",
                "external_state_confirmed",
            )
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
        if receipt["kind"] not in {
            "admission",
            "trace",
            "execution",
            "provider",
            "reconciliation",
            "closure",
            "simulation",
        }:
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


def _validate_reconciliation(
    reconciliation: Any, decision: dict[str, Any]
) -> list[str]:
    errors = _validate_required_fields(
        "reconciliation",
        reconciliation,
        ("status", "observed_outcome_ref", "required_for_closure", "mismatch_reason"),
    )
    if errors:
        return errors
    if reconciliation["status"] not in {
        "not_required",
        "pending",
        "matched",
        "mismatched",
        "blocked",
    }:
        errors.append("reconciliation.status is invalid")
    if not isinstance(reconciliation["required_for_closure"], bool):
        errors.append("reconciliation.required_for_closure must be boolean")
    if reconciliation["observed_outcome_ref"] is not None and (
        not isinstance(reconciliation["observed_outcome_ref"], str)
        or not reconciliation["observed_outcome_ref"]
    ):
        errors.append(
            "reconciliation.observed_outcome_ref must be null or a non-empty string"
        )
    if reconciliation["mismatch_reason"] is not None and (
        not isinstance(reconciliation["mismatch_reason"], str)
        or not reconciliation["mismatch_reason"]
    ):
        errors.append(
            "reconciliation.mismatch_reason must be null or a non-empty string"
        )
    if decision["status"] == "allow":
        if reconciliation["status"] != "matched":
            errors.append("reconciliation: allow requires matched reconciliation")
        if reconciliation["required_for_closure"] is not True:
            errors.append(
                "reconciliation: allow requires reconciliation before closure"
            )
    if (
        decision["status"] == "escalate"
        and decision["reason_code"] == "effect_reconciliation_mismatch"
    ):
        if reconciliation["status"] != "mismatched":
            errors.append(
                "reconciliation: effect mismatch escalation requires mismatched reconciliation"
            )
        if reconciliation["required_for_closure"] is not True:
            errors.append(
                "reconciliation: effect mismatch escalation requires reconciliation before closure"
            )
    return errors


def _validate_memory_update(memory_update: Any) -> list[str]:
    errors = _validate_required_fields(
        "memory_update",
        memory_update,
        ("status", "memory_ref", "learning_allowed", "constitution"),
    )
    if errors:
        return errors
    if memory_update["status"] not in {
        "not_allowed",
        "not_required",
        "recorded",
        "blocked",
        "deferred",
    }:
        errors.append("memory_update.status is invalid")
    if memory_update["memory_ref"] is not None and (
        not isinstance(memory_update["memory_ref"], str)
        or not memory_update["memory_ref"]
    ):
        errors.append("memory_update.memory_ref must be null or a non-empty string")
    if not isinstance(memory_update["learning_allowed"], bool):
        errors.append("memory_update.learning_allowed must be boolean")
    if memory_update["learning_allowed"] and memory_update["status"] != "recorded":
        errors.append("memory_update: learning_allowed requires recorded status")
    if memory_update["status"] == "recorded" and memory_update["memory_ref"] is None:
        errors.append("memory_update: recorded status requires memory_ref")
    errors.extend(
        _validate_memory_constitution(
            memory_update["constitution"],
            memory_update_status=memory_update["status"],
            memory_ref=memory_update["memory_ref"],
            learning_allowed=memory_update["learning_allowed"],
        )
    )
    return errors


def _validate_memory_constitution(
    constitution: Any,
    *,
    memory_update_status: str,
    memory_ref: str | None,
    learning_allowed: bool,
) -> list[str]:
    errors = _validate_required_fields(
        "memory_update.constitution",
        constitution,
        (
            "constitution_ref",
            "source_refs",
            "owner_ref",
            "scope_ref",
            "confidence",
            "sensitivity",
            "expires_at",
            "allowed_uses",
            "forbidden_uses",
            "evidence_refs",
            "last_verified_at",
            "mutation_history_refs",
        ),
    )
    if errors:
        return errors

    for field_name in ("constitution_ref", "owner_ref", "scope_ref"):
        if not isinstance(constitution[field_name], str) or not constitution[field_name]:
            errors.append(f"memory_update.constitution.{field_name} must be a non-empty string")
    confidence = constitution["confidence"]
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0 <= confidence <= 1
    ):
        errors.append("memory_update.constitution.confidence must be a number in [0, 1]")
    if constitution["sensitivity"] not in {
        "public",
        "operational",
        "tenant_confidential",
        "financial",
        "security",
        "personal",
        "regulated",
    }:
        errors.append("memory_update.constitution.sensitivity is invalid")
    for nullable_field in ("expires_at", "last_verified_at"):
        if constitution[nullable_field] is not None and (
            not isinstance(constitution[nullable_field], str)
            or not constitution[nullable_field]
        ):
            errors.append(
                f"memory_update.constitution.{nullable_field} must be null or a non-empty string"
            )

    errors.extend(
        _validate_string_array(
            "memory_update.constitution.source_refs",
            constitution["source_refs"],
            min_count=1 if memory_update_status == "recorded" else 0,
        )
    )
    errors.extend(
        _validate_string_array(
            "memory_update.constitution.allowed_uses",
            constitution["allowed_uses"],
            min_count=1 if memory_update_status == "recorded" else 0,
        )
    )
    errors.extend(
        _validate_string_array(
            "memory_update.constitution.forbidden_uses",
            constitution["forbidden_uses"],
        )
    )
    errors.extend(
        _validate_string_array(
            "memory_update.constitution.evidence_refs",
            constitution["evidence_refs"],
            min_count=1 if memory_update_status == "recorded" else 0,
        )
    )
    errors.extend(
        _validate_string_array(
            "memory_update.constitution.mutation_history_refs",
            constitution["mutation_history_refs"],
            min_count=1 if memory_update_status == "recorded" else 0,
        )
    )

    allowed_uses = set(constitution["allowed_uses"])
    forbidden_uses = set(constitution["forbidden_uses"])
    overlap = sorted(allowed_uses.intersection(forbidden_uses))
    if overlap:
        errors.append(
            "memory_update.constitution allowed_uses and forbidden_uses overlap: "
            + ", ".join(overlap)
        )
    if learning_allowed and "learning" not in allowed_uses:
        errors.append(
            "memory_update.constitution: learning_allowed requires learning allowed_use"
        )
    if not learning_allowed and "learning" not in forbidden_uses:
        errors.append(
            "memory_update.constitution: learning must be forbidden when learning_allowed is false"
        )
    if memory_update_status == "recorded" and memory_ref not in constitution["source_refs"]:
        errors.append(
            "memory_update.constitution.source_refs must include memory_ref for recorded memory"
        )
    if memory_update_status != "recorded" and learning_allowed:
        errors.append(
            "memory_update.constitution: non-recorded memory cannot allow learning"
        )
    return errors


def _validate_closure(
    closure: Any,
    decision: dict[str, Any],
    receipt_ids: set[str],
    stages_by_kind: dict[str, dict[str, Any]],
    reconciliation: Any,
    memory_update: Any,
    receipts: Any,
) -> list[str]:
    errors = _validate_required_fields(
        "closure",
        closure,
        (
            "status",
            "terminal",
            "closure_receipt_ref",
            "reconciliation_ref",
            "memory_ref",
            "next_action",
        ),
    )
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
        errors.append(
            f"closure.status must be {expected_status} for decision {decision['status']}"
        )
    if closure["terminal"] is not True:
        errors.append("closure.terminal must be true")
    if closure["closure_receipt_ref"] not in receipt_ids:
        errors.append("closure.closure_receipt_ref must reference an emitted receipt")
    for ref_field in ("reconciliation_ref", "memory_ref"):
        if closure[ref_field] is not None and (
            not isinstance(closure[ref_field], str) or not closure[ref_field]
        ):
            errors.append(f"closure.{ref_field} must be null or a non-empty string")
    expected_reconciliation_ref = _single_stage_output_ref(
        stages_by_kind.get("reconciliation")
    )
    if closure["reconciliation_ref"] != expected_reconciliation_ref:
        errors.append(
            "closure.reconciliation_ref must bind the reconciliation stage output"
        )
    if isinstance(memory_update, dict):
        if closure["memory_ref"] != memory_update.get("memory_ref"):
            errors.append("closure.memory_ref must match memory_update.memory_ref")
        if closure["memory_ref"] is not None:
            if closure["memory_ref"] != _single_stage_output_ref(
                stages_by_kind.get("memory")
            ):
                errors.append("closure.memory_ref must bind the memory stage output")
            closure_stage = stages_by_kind.get("closure", {})
            if closure["memory_ref"] not in closure_stage.get("input_refs", []):
                errors.append("closure.memory_ref must feed the closure stage input")
    if isinstance(reconciliation, dict):
        if decision["status"] == "allow":
            if closure["reconciliation_ref"] is None:
                errors.append("allow closure requires reconciliation_ref")
            if reconciliation.get("observed_outcome_ref") not in stages_by_kind.get(
                "execution", {}
            ).get("output_refs", []):
                errors.append(
                    "reconciliation.observed_outcome_ref must bind the execution stage output"
                )
        elif (
            not (
                decision["status"] == "escalate"
                and decision["reason_code"] == "effect_reconciliation_mismatch"
            )
            and reconciliation.get("required_for_closure") is not False
        ):
            errors.append("non-allow closure must not require reconciliation")
    closure_receipt = _receipt_by_id(receipts, closure["closure_receipt_ref"])
    whqr_replay_binding = closure.get("whqr_replay_binding")
    errors.extend(_validate_whqr_replay_binding(whqr_replay_binding))
    if closure_receipt is not None:
        expected_confirms = _closure_confirmation(
            closure_state=closure["status"],
            reconciliation_ref=closure["reconciliation_ref"],
            memory_ref=closure["memory_ref"],
            whqr_replay_binding=whqr_replay_binding,
        )
        if closure_receipt.get("confirms") != expected_confirms:
            errors.append(
                "closure receipt confirms must bind closure state, reconciliation_ref, memory_ref, and whqr_replay_binding"
            )
    if not isinstance(closure["next_action"], str) or not closure["next_action"]:
        errors.append("closure.next_action must be a non-empty string")
    return errors


def _single_stage_output_ref(stage: dict[str, Any] | None) -> str | None:
    if not isinstance(stage, dict):
        return None
    output_refs = stage.get("output_refs")
    if not isinstance(output_refs, list) or not output_refs:
        return None
    if len(output_refs) != 1:
        return None
    output_ref = output_refs[0]
    return output_ref if isinstance(output_ref, str) and output_ref else None


def _receipt_by_id(receipts: Any, receipt_id: str) -> dict[str, Any] | None:
    if not isinstance(receipts, list):
        return None
    for receipt in receipts:
        if isinstance(receipt, dict) and receipt.get("receipt_id") == receipt_id:
            return receipt
    return None


def _closure_confirmation(
    *,
    closure_state: str,
    reconciliation_ref: str | None,
    memory_ref: str | None,
    whqr_replay_binding: Any = None,
) -> str:
    payload = {
        "closure_state": closure_state,
        "reconciliation_ref": reconciliation_ref or "",
        "memory_ref": memory_ref or "",
    }
    payload.update(_whqr_replay_confirmation_payload(whqr_replay_binding))
    return _stable_identifier("universal-action-closure-confirmation", payload)


def _validate_whqr_replay_binding(binding: Any) -> list[str]:
    if binding is None:
        return []
    errors: list[str] = []
    if not isinstance(binding, dict):
        return ["closure.whqr_replay_binding must be null or an object"]
    expected = ("replay_ref", "canonical_hash", "semantics_hash", "version")
    for field_name in expected:
        value = binding.get(field_name)
        if not isinstance(value, str) or not value:
            errors.append(
                f"closure.whqr_replay_binding.{field_name} must be a non-empty string"
            )
    replay_ref = binding.get("replay_ref")
    canonical_hash = binding.get("canonical_hash")
    semantics_hash = binding.get("semantics_hash")
    version = binding.get("version")
    if isinstance(replay_ref, str) and replay_ref:
        if not replay_ref.startswith("whqr://replay/sha256:"):
            errors.append(
                "closure.whqr_replay_binding.replay_ref must start with whqr://replay/sha256:"
            )
        elif not _has_whqr_sha256_digest_ref(replay_ref):
            errors.append(
                "closure.whqr_replay_binding.replay_ref must include a 64-character lowercase hex sha256 digest"
            )
    if isinstance(replay_ref, str) and isinstance(canonical_hash, str):
        if replay_ref != f"whqr://replay/{canonical_hash}":
            errors.append(
                "closure.whqr_replay_binding.replay_ref must bind canonical_hash"
            )
    if isinstance(canonical_hash, str) and canonical_hash:
        if not canonical_hash.startswith("sha256:"):
            errors.append(
                "closure.whqr_replay_binding.canonical_hash must start with sha256:"
            )
        elif not _has_sha256_digest_ref(canonical_hash):
            errors.append(
                "closure.whqr_replay_binding.canonical_hash must include a 64-character lowercase hex sha256 digest"
            )
    if isinstance(semantics_hash, str) and semantics_hash:
        if not semantics_hash.startswith("sha256:"):
            errors.append(
                "closure.whqr_replay_binding.semantics_hash must start with sha256:"
            )
        elif not _has_sha256_digest_ref(semantics_hash):
            errors.append(
                "closure.whqr_replay_binding.semantics_hash must include a 64-character lowercase hex sha256 digest"
            )
    if isinstance(version, str) and version:
        if not _is_semver_core(version):
            errors.append(
                "closure.whqr_replay_binding.version must use major.minor.patch"
            )
    extra_keys = set(binding) - set(expected)
    if extra_keys:
        errors.append(
            "closure.whqr_replay_binding contains unsupported field(s): "
            + ", ".join(sorted(extra_keys))
        )
    return errors


def _has_sha256_digest_ref(value: str) -> bool:
    prefix = "sha256:"
    return value.startswith(prefix) and _has_sha256_hex_suffix(value, prefix)


def _has_whqr_sha256_digest_ref(value: str) -> bool:
    prefix = "whqr://replay/sha256:"
    return value.startswith(prefix) and _has_sha256_hex_suffix(value, prefix)


def _has_sha256_hex_suffix(value: str, prefix: str) -> bool:
    suffix = value[len(prefix):]
    return len(suffix) == 64 and all(char in "0123456789abcdef" for char in suffix)


def _is_semver_core(value: str) -> bool:
    parts = value.split(".")
    return len(parts) == 3 and all(_is_semver_core_identifier(part) for part in parts)


def _is_semver_core_identifier(value: str) -> bool:
    if not value.isascii() or not value.isdecimal():
        return False
    return value == "0" or not value.startswith("0")


def _whqr_replay_confirmation_payload(binding: Any) -> dict[str, str]:
    if not isinstance(binding, dict):
        return {}
    return {
        "whqr_replay_ref": str(binding.get("replay_ref") or ""),
        "whqr_canonical_hash": str(binding.get("canonical_hash") or ""),
        "whqr_semantics_hash": str(binding.get("semantics_hash") or ""),
        "whqr_version": str(binding.get("version") or ""),
    }


def _stable_identifier(prefix: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return f"{prefix}-{sha256(encoded.encode('utf-8')).hexdigest()[:12]}"


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
    errors.extend(
        _validate_delta_records("lineage.accepted_deltas", lineage["accepted_deltas"])
    )
    errors.extend(
        _validate_delta_records("lineage.rejected_deltas", lineage["rejected_deltas"])
    )
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
        errors.extend(
            _validate_required_fields(
                record_label, record, ("delta_id", "reason", "logged_in_lineage")
            )
        )
        if not isinstance(record, dict) or any(
            field not in record for field in ("delta_id", "reason", "logged_in_lineage")
        ):
            continue
        if not isinstance(record["delta_id"], str) or not record["delta_id"]:
            errors.append(f"{record_label}.delta_id must be a non-empty string")
        if not isinstance(record["reason"], str) or not record["reason"]:
            errors.append(f"{record_label}.reason must be a non-empty string")
        if record["logged_in_lineage"] is not True:
            errors.append(f"{record_label}.logged_in_lineage must be true")
    return errors


def _validate_receipt_requirements(
    decision: dict[str, Any], receipt_kinds: set[str]
) -> list[str]:
    errors: list[str] = []
    required_kinds = {"admission", "trace", "closure"}
    if decision["status"] == "allow" or (
        decision["status"] == "escalate"
        and decision["reason_code"] == "effect_reconciliation_mismatch"
    ):
        required_kinds |= {"execution", "reconciliation"}
    missing = sorted(required_kinds - receipt_kinds)
    if missing:
        errors.append(f"receipts missing required kind(s): {', '.join(missing)}")
    return errors


def _validate_root_receipt_refs(
    record: dict[str, Any], receipt_ids: set[str], receipt_kinds: set[str]
) -> list[str]:
    errors: list[str] = []
    admission_receipt_ref = record["admission_receipt_ref"]
    execution_receipt_ref = record["execution_receipt_ref"]
    closure_state = record["closure_state"]
    if not isinstance(admission_receipt_ref, str) or not admission_receipt_ref:
        errors.append("admission_receipt_ref must be a non-empty string")
    elif admission_receipt_ref not in receipt_ids:
        errors.append("admission_receipt_ref must reference an emitted receipt")
    if execution_receipt_ref is not None and (
        not isinstance(execution_receipt_ref, str) or not execution_receipt_ref
    ):
        errors.append("execution_receipt_ref must be null or a non-empty string")
    execution_receipt_required = record["decision"]["status"] == "allow" or (
        record["decision"]["status"] == "escalate"
        and record["decision"]["reason_code"] == "effect_reconciliation_mismatch"
    )
    if execution_receipt_required:
        if execution_receipt_ref not in receipt_ids:
            errors.append(
                "execution decision requires execution_receipt_ref to reference an emitted receipt"
            )
        if "execution" not in receipt_kinds:
            errors.append("execution decision requires an execution receipt")
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
    recovery_plan = record.get("recovery_plan")
    decision = record.get("decision")
    if isinstance(recovery_plan, dict) and isinstance(decision, dict):
        post_dispatch_review = (
            decision.get("status") == "escalate"
            and decision.get("reason_code") == "effect_reconciliation_mismatch"
        )
        if decision.get("status") == "allow" or post_dispatch_review:
            if recovery_plan.get("available") is not True:
                errors.append(
                    "effect_bearing(action) requires recovery_plan before execution closure"
                )
        if decision.get("reason_code") == "recovery_plan_missing":
            recovery_guard = next(
                (
                    guard
                    for guard in record.get("admission_guards", ())
                    if isinstance(guard, dict)
                    and guard.get("guard") == "recovery_available"
                ),
                {},
            )
            if recovery_guard.get("verdict") != "blocked":
                errors.append(
                    "recovery_plan_missing requires blocked recovery_available guard"
                )
    return errors


def _validate_high_risk_allow_controls(record: dict[str, Any]) -> list[str]:
    action_envelope = record["action_envelope"]
    if not isinstance(action_envelope, dict):
        return []
    if (
        record["decision"]["status"] != "allow"
        or action_envelope.get("risk") not in HIGH_RISK_CLASSES
    ):
        return []
    errors: list[str] = []
    if not action_envelope.get("approval_ref"):
        errors.append("high-risk allow requires action_envelope.approval_ref")
    if not action_envelope.get("evidence_refs"):
        errors.append("high-risk allow requires action_envelope.evidence_refs")
    if not action_envelope.get("capability_refs"):
        errors.append("high-risk allow requires action_envelope.capability_refs")
    return errors


def _validate_no_private_reasoning_fields(
    value: Any, path: str = "orchestration"
) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in PROHIBITED_PRIVATE_REASONING_FIELDS:
                errors.append(f"{path}.{key} is prohibited")
            errors.extend(_validate_no_private_reasoning_fields(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(
                _validate_no_private_reasoning_fields(child, f"{path}[{index}]")
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    """Validate the Universal Action Orchestration contract."""

    parser = argparse.ArgumentParser(
        description="Validate Universal Action Orchestration contract."
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA_PATH,
        help="path to UAO schema JSON",
    )
    parser.add_argument(
        "--document",
        type=Path,
        default=DEFAULT_DOCUMENT_PATH,
        help="path to UAO doctrine Markdown",
    )
    parser.add_argument(
        "--example",
        action="append",
        type=Path,
        default=[],
        help="UAO example JSON path; may be provided more than once",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit a machine-readable UAO validation receipt",
    )
    parser.add_argument(
        "--receipt-path",
        type=Path,
        help="optional path to persist the UAO validation receipt",
    )
    args = parser.parse_args(argv)

    example_paths = tuple(args.example) if args.example else DEFAULT_EXAMPLE_PATHS
    if args.json or args.receipt_path is not None:
        receipt_scope_errors = validate_validation_receipt_scope(
            args.schema, example_paths, args.document
        )
        if receipt_scope_errors:
            for error in receipt_scope_errors:
                sys.stderr.write(f"[FAIL] receipt-scope: {error}\n")
            sys.stderr.write("STATUS: failed\n")
            return 1
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
    sys.stdout.write("[PASS] universal_action_orchestration_runtime_bypass_detector\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
