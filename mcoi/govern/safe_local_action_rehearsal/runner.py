"""Safe local action rehearsal runner.

Purpose: rehearse local developer actions as proof-only scenarios before any
    real workspace mutation or external effect is allowed.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: JSON schema validation helper and operator workflow dashboard
    projection.
Invariants:
  - Rehearsal is not execution proof.
  - No file write, branch push, PR creation, merge, rollback, deployment,
    connector call, email send, money movement, or production write occurs.
  - Post-execution evidence remains required before live closure.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MCOI_ROOT = REPO_ROOT / "mcoi"
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from gateway.operator_workflow_dashboard import (  # noqa: E402
    build_operator_workflow_dashboard_read_model,
    validate_operator_workflow_dashboard_read_model,
)
from scripts.build_operator_local_developer_workflow_receipt_read_model import (  # noqa: E402
    _load_control_tower_status_receipt,
    _load_operator_receipt,
    build_operator_local_developer_workflow_receipt_read_model,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


CAPABILITY_ID = "govern.safe_local_action.rehearsal"
SCHEMA_REF = "urn:mullusi:schema:safe-local-action-rehearsal-receipt:1"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "safe_local_action_rehearsal_receipt.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "safe_local_action_rehearsal_receipt.json"
FORBIDDEN_EFFECTS = (
    "file_write",
    "branch_push",
    "pull_request_create",
    "merge",
    "rollback_execute",
    "deploy",
    "connector_call",
    "external_write",
    "live_execution",
)
SCENARIOS = (
    ("simulate_file_write", "workspace file write preview"),
    ("simulate_pr_creation", "pull request creation preview"),
    ("simulate_merge_request", "merge request preview"),
    ("simulate_rollback", "rollback command preview"),
    ("simulate_connector_action", "connector action preview"),
)


@dataclass(frozen=True, slots=True)
class SafeLocalActionRehearsalValidation:
    """Validation report for a safe local action rehearsal receipt."""

    ok: bool
    errors: tuple[str, ...]
    receipt_path: str
    rehearsal_status: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def run_safe_local_action_rehearsal(
    *,
    dashboard_path: Path | None = None,
    output_path: Path = DEFAULT_OUTPUT,
) -> tuple[dict[str, Any], SafeLocalActionRehearsalValidation]:
    """Build, write, and validate a safe local action rehearsal receipt."""

    dashboard, dashboard_ref = _load_or_build_dashboard(dashboard_path)
    receipt = build_safe_local_action_rehearsal_receipt(
        operator_workflow_dashboard=dashboard,
        dashboard_source_ref=dashboard_ref,
    )
    written_path = write_safe_local_action_rehearsal_receipt(receipt, output_path)
    validation = validate_safe_local_action_rehearsal_receipt(
        receipt=receipt,
        receipt_path=written_path,
    )
    return receipt, validation


def build_safe_local_action_rehearsal_receipt(
    *,
    operator_workflow_dashboard: Mapping[str, Any],
    dashboard_source_ref: str,
) -> dict[str, Any]:
    """Return a proof-only safe local action rehearsal receipt."""

    dashboard_validation = validate_operator_workflow_dashboard_read_model(
        dashboard=operator_workflow_dashboard
    )
    if not dashboard_validation.ok:
        raise ValueError(f"operator_workflow_dashboard_invalid:{list(dashboard_validation.errors)}")
    row = _first_dashboard_row(operator_workflow_dashboard)
    current_gate = _mapping(row.get("current_gate"))
    selected_action = {
        "task": str(row.get("task") or "Mullu Developer Workflow v1"),
        "next_action": str(row.get("next_action") or "prepare safe local action rehearsal"),
        "current_gate": str(current_gate.get("stage_id") or "unknown"),
        "risk": str(row.get("risk") or "low, local lab only"),
        "source_ref": dashboard_source_ref,
    }
    scenarios = [
        _scenario(index=index, scenario_id=scenario_id, label=label, selected_action=selected_action)
        for index, (scenario_id, label) in enumerate(SCENARIOS, start=1)
    ]
    receipt = {
        "schema_ref": SCHEMA_REF,
        "receipt_id": "safe_local_action_rehearsal.foundation.v1",
        "capability_id": CAPABILITY_ID,
        "rehearsal_status": "rehearsed_no_effect",
        "solver_outcome": "SolvedUnverified",
        "rehearsal_is_not_execution_proof": True,
        "post_execution_evidence_required": True,
        "live_execution_enabled": False,
        "selected_action": selected_action,
        "scenarios": scenarios,
        "effect_boundary": {
            "file_write_allowed": False,
            "branch_push_allowed": False,
            "pull_request_create_allowed": False,
            "merge_allowed": False,
            "rollback_execute_allowed": False,
            "deploy_allowed": False,
            "connector_call_allowed": False,
            "external_write_allowed": False,
            "live_execution_allowed": False,
        },
        "approval": {
            "required_for_live_execution": True,
            "approval_status": "not_requested",
            "approval_performed": False,
            "approval_ref": "absent",
        },
        "blocked_effects": list(FORBIDDEN_EFFECTS),
        "source_refs": {
            "operator_workflow_dashboard": dashboard_source_ref,
            "builder": "mcoi/govern/safe_local_action_rehearsal/runner.py",
        },
        "receipt_hash": "",
    }
    receipt["receipt_hash"] = _canonical_hash(receipt)
    return receipt


def validate_safe_local_action_rehearsal_receipt(
    *,
    receipt: Mapping[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_path: Path = Path("<generated>"),
) -> SafeLocalActionRehearsalValidation:
    """Validate safe-local rehearsal schema and no-effect semantics."""

    errors = [str(error) for error in _validate_schema_instance(_load_json_object(schema_path), dict(receipt))]
    if receipt.get("capability_id") != CAPABILITY_ID:
        errors.append("capability_id_invalid")
    if receipt.get("rehearsal_is_not_execution_proof") is not True:
        errors.append("rehearsal_must_not_claim_execution_proof")
    if receipt.get("post_execution_evidence_required") is not True:
        errors.append("post_execution_evidence_must_remain_required")
    if receipt.get("live_execution_enabled") is not False:
        errors.append("live_execution_enabled_must_be_false")
    effect_boundary = _mapping(receipt.get("effect_boundary"))
    for key, value in effect_boundary.items():
        if key.endswith("_allowed") and value is not False:
            errors.append(f"effect_boundary_must_be_false:{key}")
    approval = _mapping(receipt.get("approval"))
    if approval.get("approval_performed") is not False:
        errors.append("approval_performed_must_be_false")
    blocked_effects = receipt.get("blocked_effects", ())
    if not isinstance(blocked_effects, list):
        errors.append("blocked_effects_must_be_list")
        blocked_effects = []
    for forbidden_effect in FORBIDDEN_EFFECTS:
        if forbidden_effect not in blocked_effects:
            errors.append(f"blocked_effect_missing:{forbidden_effect}")
    scenarios = receipt.get("scenarios", ())
    if not isinstance(scenarios, list) or not scenarios:
        errors.append("scenarios_must_be_non_empty_list")
        scenarios = []
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, Mapping):
            errors.append(f"scenarios[{index}]_must_be_object")
            continue
        if scenario.get("proof_only") is not True:
            errors.append(f"scenarios[{index}].proof_only_must_be_true")
        if scenario.get("mutation_performed") is not False:
            errors.append(f"scenarios[{index}].mutation_performed_must_be_false")
        if scenario.get("external_effects_allowed") is not False:
            errors.append(f"scenarios[{index}].external_effects_must_be_false")
    expected = dict(receipt)
    expected["receipt_hash"] = ""
    if receipt.get("receipt_hash") != _canonical_hash(expected):
        errors.append("receipt_hash_mismatch")
    return SafeLocalActionRehearsalValidation(
        ok=not errors,
        errors=tuple(errors),
        receipt_path=_path_label(receipt_path),
        rehearsal_status=str(receipt.get("rehearsal_status") or ""),
    )


def write_safe_local_action_rehearsal_receipt(receipt: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic safe local action rehearsal receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _scenario(
    *,
    index: int,
    scenario_id: str,
    label: str,
    selected_action: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "scenario_id": scenario_id,
        "sequence": index,
        "label": label,
        "status": "rehearsed",
        "target": str(selected_action.get("task") or "Mullu Developer Workflow v1"),
        "current_gate": str(selected_action.get("current_gate") or "unknown"),
        "expected_live_evidence": [
            "approved_live_execution_ref",
            "post_execution_observation_receipt",
            "rollback_or_compensation_receipt",
        ],
        "proof_limit": "simulation_is_not_execution_proof",
        "proof_only": True,
        "mutation_performed": False,
        "external_effects_allowed": False,
    }


def _load_or_build_dashboard(dashboard_path: Path | None) -> tuple[dict[str, Any], str]:
    if dashboard_path is not None:
        dashboard = _load_json_object(dashboard_path)
        validation = validate_operator_workflow_dashboard_read_model(
            dashboard=dashboard,
            dashboard_path=dashboard_path,
        )
        if not validation.ok:
            raise ValueError(f"operator_workflow_dashboard_invalid:{list(validation.errors)}")
        return dashboard, _path_label(dashboard_path)
    operator_receipt, operator_source_ref = _load_operator_receipt(None)
    control_receipt, control_source_ref = _load_control_tower_status_receipt(None)
    local_receipt = build_operator_local_developer_workflow_receipt_read_model(
        operator_receipt=operator_receipt,
        operator_receipt_source_ref=operator_source_ref,
        control_tower_status_receipt=control_receipt,
        control_tower_source_ref=control_source_ref,
    )
    return build_operator_workflow_dashboard_read_model(
        local_workflow_receipt=local_receipt,
        local_workflow_source_ref="<generated-local-workflow-receipt-read-model>",
    ), "<generated-operator-workflow-dashboard>"


def _first_dashboard_row(dashboard: Mapping[str, Any]) -> Mapping[str, Any]:
    rows = dashboard.get("rows", ())
    if isinstance(rows, list) and rows and isinstance(rows[0], Mapping):
        return rows[0]
    raise ValueError("operator_workflow_dashboard_rows_missing")


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
