"""Causal repair service.

Purpose: classify governed workflow failures, propose the next repair proof,
and emit a reusable repair receipt before any live repair execution.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: mcoi_runtime.core.causal_repair enums and schema validation.
Invariants:
  - The service is proof-only.
  - Rollback and compensation are described as proof obligations, not executed.
  - Missing approval, stale evidence, unsafe evidence, and irreversible effects
    fail closed as AwaitingEvidence or GovernanceBlocked.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MCOI_ROOT = REPO_ROOT / "mcoi"
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from mcoi_runtime.core.causal_repair import (  # noqa: E402
    EffectClass,
    RepairStrategy,
    ReversibilityClass,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


CAPABILITY_ID = "govern.causal_repair.service"
SERVICE_ID = "mcoi.causal_repair.service"
SCHEMA_REF = "urn:mullusi:schema:causal-repair-service-receipt:1"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "causal_repair_service_receipt.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "causal_repair_service_receipt.json"
DEFAULT_FAILURE_IDS = (
    "failed_patch_plan",
    "failed_test",
    "stale_evidence",
    "missing_approval",
    "rollback_impossible",
    "ci_failure",
    "unsafe_browser_evidence",
)
FORBIDDEN_EFFECTS = (
    "repair_execute",
    "file_write",
    "branch_push",
    "pull_request_create",
    "merge",
    "deploy",
    "connector_call",
    "external_write",
    "live_execution",
)


@dataclass(frozen=True, slots=True)
class FailureRepairTemplate:
    """Deterministic repair template for one known failure class."""

    failure_id: str
    cause_class: str
    severity: str
    effect_class: EffectClass
    reversibility_class: ReversibilityClass
    repair_strategy: RepairStrategy
    proof_status: str
    rollback_claim_allowed: bool
    compensation_claim_allowed: bool
    approval_required: bool
    proof_state: str
    operator_outcome: str
    next_action: str
    required_evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CausalRepairServiceValidation:
    """Validation report for a causal repair service receipt."""

    ok: bool
    errors: tuple[str, ...]
    receipt_path: str
    service_status: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


TEMPLATES: dict[str, FailureRepairTemplate] = {
    "failed_patch_plan": FailureRepairTemplate(
        "failed_patch_plan",
        "planning_contract_failure",
        "medium",
        EffectClass.INTERNAL_REVERSIBLE,
        ReversibilityClass.EXACT_ROLLBACK,
        RepairStrategy.EXACT_ROLLBACK,
        "proof_required",
        True,
        False,
        False,
        "AwaitingEvidence",
        "AwaitingEvidence",
        "collect patch plan receipt, before hash, and safe diff preview before repair admission",
        ("patch_plan_receipt", "before_hash", "diff_preview"),
    ),
    "failed_test": FailureRepairTemplate(
        "failed_test",
        "verification_failure",
        "high",
        EffectClass.INTERNAL_REVERSIBLE,
        ReversibilityClass.EXACT_ROLLBACK,
        RepairStrategy.EXACT_ROLLBACK,
        "proof_required",
        True,
        False,
        False,
        "AwaitingEvidence",
        "AwaitingEvidence",
        "bind failing assertion, test receipt, and rollback plan before repair execution",
        ("test_failure_receipt", "failing_assertion", "rollback_plan"),
    ),
    "stale_evidence": FailureRepairTemplate(
        "stale_evidence",
        "evidence_freshness_failure",
        "medium",
        EffectClass.READ_ONLY,
        ReversibilityClass.READ_ONLY,
        RepairStrategy.NONE_REQUIRED,
        "blocked_until_evidence",
        False,
        False,
        False,
        "AwaitingEvidence",
        "AwaitingEvidence",
        "refresh evidence and bind temporal freshness receipt before closure",
        ("fresh_evidence_ref", "temporal_evidence_freshness_receipt", "source_timestamp"),
    ),
    "missing_approval": FailureRepairTemplate(
        "missing_approval",
        "approval_gap",
        "high",
        EffectClass.USER_VISIBLE,
        ReversibilityClass.HUMAN_ESCALATION,
        RepairStrategy.ESCALATE,
        "blocked_until_evidence",
        False,
        False,
        True,
        "AwaitingEvidence",
        "AwaitingEvidence",
        "request approval gate decision and bind approval receipt before any user-visible effect",
        ("approval_gate_id", "approval_decision_receipt", "approval_input_refs"),
    ),
    "rollback_impossible": FailureRepairTemplate(
        "rollback_impossible",
        "repair_authority_gap",
        "critical",
        EffectClass.PUBLIC_IRREVERSIBLE,
        ReversibilityClass.FORBIDDEN,
        RepairStrategy.FORBID,
        "blocked_until_evidence",
        False,
        False,
        True,
        "Fail(repair_forbidden_without_compensation_authority)",
        "GovernanceBlocked",
        "halt repair execution and escalate accepted-risk plus compensation authority to governance",
        ("accepted_risk_record", "compensation_plan", "operator_escalation_ref"),
    ),
    "ci_failure": FailureRepairTemplate(
        "ci_failure",
        "ci_verification_failure",
        "high",
        EffectClass.INTERNAL_VERSIONED,
        ReversibilityClass.VERSION_RESTORE,
        RepairStrategy.VERSION_RESTORE,
        "proof_required",
        True,
        False,
        False,
        "AwaitingEvidence",
        "AwaitingEvidence",
        "bind CI run, failing check log, version id, and restore pointer before repair admission",
        ("ci_run_ref", "failing_check_log", "version_id", "restore_pointer"),
    ),
    "unsafe_browser_evidence": FailureRepairTemplate(
        "unsafe_browser_evidence",
        "unsafe_evidence_origin",
        "critical",
        EffectClass.READ_ONLY,
        ReversibilityClass.READ_ONLY,
        RepairStrategy.NONE_REQUIRED,
        "blocked_until_evidence",
        False,
        False,
        False,
        "AwaitingEvidence",
        "AwaitingEvidence",
        "isolate browser sandbox evidence origin before trusting the evidence in any closure lane",
        ("browser_sandbox_workspace_ref", "evidence_origin_receipt", "sandbox_isolation_receipt"),
    ),
}


def run_causal_repair_service(
    *,
    failure_ids: Sequence[str] = DEFAULT_FAILURE_IDS,
    output_path: Path = DEFAULT_OUTPUT,
) -> tuple[dict[str, Any], CausalRepairServiceValidation]:
    """Build, write, and validate a proof-only causal repair service receipt."""

    receipt = build_causal_repair_service_receipt(failure_ids=failure_ids)
    written_path = write_causal_repair_service_receipt(receipt, output_path)
    validation = validate_causal_repair_service_receipt(
        receipt=receipt,
        receipt_path=written_path,
    )
    return receipt, validation


def build_causal_repair_service_receipt(
    *,
    failure_ids: Sequence[str] = DEFAULT_FAILURE_IDS,
) -> dict[str, Any]:
    """Return a proof-only repair classification receipt for selected failures."""

    cases = [classify_failure(failure_id) for failure_id in failure_ids]
    receipt = {
        "schema_ref": SCHEMA_REF,
        "receipt_id": "causal_repair_service.foundation.v1",
        "service_id": SERVICE_ID,
        "capability_id": CAPABILITY_ID,
        "service_status": "planned_no_effect",
        "solver_outcome": "AwaitingEvidence",
        "live_execution_enabled": False,
        "repair_execution_performed": False,
        "case_count": len(cases),
        "cases": cases,
        "blocked_effects": list(FORBIDDEN_EFFECTS),
        "source_refs": {
            "builder": "mcoi/causal_repair/service.py",
            "repair_engine": "mcoi/mcoi_runtime/core/causal_repair.py",
        },
        "receipt_hash": "",
    }
    receipt["receipt_hash"] = _canonical_hash(receipt)
    return receipt


def classify_failure(failure_id: str) -> dict[str, Any]:
    """Classify one failure and return its proof-only repair proposal."""

    template = TEMPLATES.get(failure_id)
    if template is None:
        raise ValueError(f"unknown_failure_id:{failure_id}")
    return {
        "failure_id": template.failure_id,
        "detected": True,
        "cause_class": template.cause_class,
        "severity": template.severity,
        "effect_class": template.effect_class.value,
        "reversibility_class": template.reversibility_class.value,
        "repair_strategy": template.repair_strategy.value,
        "rollback_or_compensation_proof": {
            "status": template.proof_status,
            "rollback_claim_allowed": template.rollback_claim_allowed,
            "compensation_claim_allowed": template.compensation_claim_allowed,
            "required_evidence": list(template.required_evidence),
            "execution_performed": False,
        },
        "proposal": {
            "next_action": template.next_action,
            "approval_required": template.approval_required,
            "proof_state": template.proof_state,
            "operator_outcome": template.operator_outcome,
        },
    }


def validate_causal_repair_service_receipt(
    *,
    receipt: Mapping[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_path: Path = Path("<generated>"),
) -> CausalRepairServiceValidation:
    """Validate schema and proof-only semantics for a repair service receipt."""

    errors = [str(error) for error in _validate_schema_instance(_load_json_object(schema_path), dict(receipt))]
    if receipt.get("capability_id") != CAPABILITY_ID:
        errors.append("capability_id_invalid")
    if receipt.get("service_id") != SERVICE_ID:
        errors.append("service_id_invalid")
    if receipt.get("live_execution_enabled") is not False:
        errors.append("live_execution_enabled_must_be_false")
    if receipt.get("repair_execution_performed") is not False:
        errors.append("repair_execution_performed_must_be_false")
    blocked_effects = receipt.get("blocked_effects", ())
    if not isinstance(blocked_effects, list):
        errors.append("blocked_effects_must_be_list")
        blocked_effects = []
    for forbidden_effect in FORBIDDEN_EFFECTS:
        if forbidden_effect not in blocked_effects:
            errors.append(f"blocked_effect_missing:{forbidden_effect}")
    cases = receipt.get("cases", ())
    if not isinstance(cases, list) or not cases:
        errors.append("cases_must_be_non_empty_list")
        cases = []
    case_ids = {
        str(case.get("failure_id"))
        for case in cases
        if isinstance(case, Mapping)
    }
    for required_case_id in DEFAULT_FAILURE_IDS:
        if required_case_id not in case_ids:
            errors.append(f"required_case_missing:{required_case_id}")
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            errors.append(f"cases[{index}]_must_be_object")
            continue
        proof = _mapping(case.get("rollback_or_compensation_proof"))
        proposal = _mapping(case.get("proposal"))
        if proof.get("execution_performed") is not False:
            errors.append(f"cases[{index}].execution_performed_must_be_false")
        required_evidence = proof.get("required_evidence", ())
        if not isinstance(required_evidence, list) or not required_evidence:
            errors.append(f"cases[{index}].required_evidence_missing")
        if case.get("failure_id") == "rollback_impossible":
            if case.get("repair_strategy") != RepairStrategy.FORBID.value:
                errors.append("rollback_impossible_must_forbid_repair")
            if proposal.get("operator_outcome") != "GovernanceBlocked":
                errors.append("rollback_impossible_must_be_governance_blocked")
        if case.get("failure_id") == "missing_approval" and proposal.get("approval_required") is not True:
            errors.append("missing_approval_must_require_approval")
        if case.get("failure_id") == "stale_evidence" and proposal.get("proof_state") != "AwaitingEvidence":
            errors.append("stale_evidence_must_await_evidence")
    expected = dict(receipt)
    expected["receipt_hash"] = ""
    if receipt.get("receipt_hash") != _canonical_hash(expected):
        errors.append("receipt_hash_mismatch")
    return CausalRepairServiceValidation(
        ok=not errors,
        errors=tuple(errors),
        receipt_path=_path_label(receipt_path),
        service_status=str(receipt.get("service_status") or ""),
    )


def write_causal_repair_service_receipt(receipt: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic causal repair service receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"json_parse_failed:{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("json_root_must_be_object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)
