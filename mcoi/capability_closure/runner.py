"""Build capability debt closure artifacts.

Purpose: choose one governed capability-debt closure lane and emit the next
proof step without enabling live execution.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: capability debt report projection and repository-local JSON
artifact writers.
Invariants:
  - Closure artifacts are read-only planning records and never execution authority.
  - Exactly one selected debt lane is emitted per run.
  - Missing approval and evidence refs remain explicit.
  - Live execution, connector mutation, repository mutation, PR creation, and
    merge remain disabled.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from mcoi_runtime.app.capability_debt_report import build_capability_debt_report


SCHEMA_VERSION = 1
ARTIFACT_VERSION = "foundation.v1"
MODE = "foundation"
PREFERRED_CATEGORY = "approval"
DEFAULT_PREFERRED_CAPABILITY_IDS = (
    "email.send.with_approval",
    "browser.submit",
    "software_dev.pr_candidate.prepare",
    "software_dev.change.run",
    "software_dev.github_patch_plan.draft",
)
ARTIFACT_FILENAMES = {
    "capability_closure_plan": "capability_closure_plan.json",
    "missing_evidence_refs": "missing_evidence_refs.json",
    "next_approval_action": "next_approval_action.json",
    "closure_receipt": "closure_receipt.json",
}
EXAMPLE_ARTIFACT_FILENAMES = {
    key: value.replace(".json", ".foundation.json")
    for key, value in ARTIFACT_FILENAMES.items()
}
SEVERITY_ORDER = ("critical", "high", "medium", "low")
CATEGORY_ORDER = ("approval", "evidence", "rollback", "replay", "promotion", "live_action")
LIVE_EFFECT_BOUNDARY = {
    "capability_live_execution_performed": False,
    "connector_mutation_performed": False,
    "external_write_performed": False,
    "target_repository_mutation_authorized": False,
    "target_repository_file_write_performed": False,
    "branch_push_performed": False,
    "pull_request_created": False,
    "merge_performed": False,
    "production_claim_made": False,
}


class CapabilityClosureRunnerError(ValueError):
    """Raised when capability closure artifacts cannot be projected safely."""


def build_capability_closure_artifacts(
    *,
    debt_report: Mapping[str, Any] | None = None,
    preferred_capability_ids: tuple[str, ...] = DEFAULT_PREFERRED_CAPABILITY_IDS,
    preferred_category: str = PREFERRED_CATEGORY,
    artifact_filenames: Mapping[str, str] = ARTIFACT_FILENAMES,
) -> dict[str, dict[str, Any]]:
    """Return the four deterministic capability closure artifacts.

    Input contract: optional capability debt report projection and deterministic
    selection hints. The report must contain capability debt rows.
    Output contract: JSON-serializable artifacts keyed by artifact name.
    Error contract: raises CapabilityClosureRunnerError for malformed debt
    rows, unsupported categories, or empty closure candidates.
    """

    report = dict(debt_report or build_capability_debt_report())
    selected = _select_closure_lane(
        report,
        preferred_capability_ids=preferred_capability_ids,
        preferred_category=preferred_category,
    )
    source_refs = _source_refs(report, selected)
    selected_missing_refs = _string_list(selected["debt_item"].get("missing_refs"))
    refs_by_category = _missing_refs_by_category(selected["debt_row"])
    approval_refs = refs_by_category.get("approval", [])
    next_approval = _next_approval_action(
        selected=selected,
        source_refs=source_refs,
        approval_refs=approval_refs,
    )
    missing_refs = _missing_evidence_refs(
        selected=selected,
        source_refs=source_refs,
        refs_by_category=refs_by_category,
    )
    plan = _closure_plan(
        selected=selected,
        source_refs=source_refs,
        selected_missing_refs=selected_missing_refs,
        preferred_capability_ids=preferred_capability_ids,
        preferred_category=preferred_category,
    )
    receipt = _closure_receipt(
        selected=selected,
        source_refs=source_refs,
        plan=plan,
        missing_refs=missing_refs,
        next_approval=next_approval,
        artifact_filenames=artifact_filenames,
    )
    return {
        "capability_closure_plan": plan,
        "missing_evidence_refs": missing_refs,
        "next_approval_action": next_approval,
        "closure_receipt": receipt,
    }


def write_capability_closure_artifacts(
    artifacts: Mapping[str, Mapping[str, Any]],
    output_dir: Path,
    *,
    artifact_filenames: Mapping[str, str] = ARTIFACT_FILENAMES,
) -> dict[str, Path]:
    """Write the four capability closure artifacts to one directory."""

    output_dir.mkdir(parents=True, exist_ok=True)
    written_paths: dict[str, Path] = {}
    for artifact_name, filename in artifact_filenames.items():
        payload = artifacts.get(artifact_name)
        if not isinstance(payload, Mapping):
            raise CapabilityClosureRunnerError(f"missing artifact payload {artifact_name}")
        output_path = output_dir / filename
        output_path.write_text(
            json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written_paths[artifact_name] = output_path
    return written_paths


def _select_closure_lane(
    debt_report: Mapping[str, Any],
    *,
    preferred_capability_ids: tuple[str, ...],
    preferred_category: str,
) -> dict[str, Any]:
    rows = _debt_rows(debt_report)
    if preferred_category not in CATEGORY_ORDER:
        raise CapabilityClosureRunnerError(f"unsupported preferred category {preferred_category}")
    for capability_id in preferred_capability_ids:
        row = rows.get(capability_id)
        if row is None:
            continue
        item = _item_by_category(row, preferred_category)
        if item is not None:
            return _selected_lane(row, item, "preferred_approval_lane")
    ranked_items = _ranked_items(rows.values())
    if not ranked_items:
        raise CapabilityClosureRunnerError("capability closure requires at least one debt item")
    row, item = ranked_items[0]
    return _selected_lane(row, item, "highest_ranked_debt_item")


def _closure_plan(
    *,
    selected: Mapping[str, Any],
    source_refs: Mapping[str, Any],
    selected_missing_refs: list[str],
    preferred_capability_ids: tuple[str, ...],
    preferred_category: str,
) -> dict[str, Any]:
    debt_item = dict(selected["debt_item"])
    capability_id = str(selected["capability_id"])
    category = str(debt_item["category"])
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": f"capability_closure_plan.{capability_id}.{category}.{ARTIFACT_VERSION}",
        "mode": MODE,
        "plan_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "selected_capability_id": capability_id,
        "selected_capability_name": str(selected["capability_name"]),
        "selected_family": str(selected["family"]),
        "selected_debt_id": str(debt_item["debt_id"]),
        "selected_category": category,
        "selection_policy": {
            "policy_id": "capability_closure.selection.foundation.v1",
            "preferred_category": preferred_category,
            "preferred_capability_ids": list(preferred_capability_ids),
            "fallback_order": [
                "severity",
                "category",
                "capability_id",
                "debt_id",
            ],
            "selection_reason": str(selected["selection_reason"]),
        },
        "source_refs": dict(source_refs),
        "selected_debt_item": debt_item,
        "closure_lane": {
            "lane_id": f"capability_closure.{capability_id}.{category}",
            "lane_type": category,
            "current_gate": _current_gate(selected_missing_refs, category),
            "proof_state": "Unknown",
            "outcome": "AwaitingEvidence",
            "missing_ref_count": len(selected_missing_refs),
            "next_required_proof_step": _next_required_proof_step(category, selected_missing_refs),
        },
        "blocked_effects": [
            "live_execution",
            "connector_mutation",
            "external_write",
            "target_repository_mutation",
            "branch_push",
            "pull_request_create",
            "merge",
            "production_claim",
        ],
        "validators": _validators(),
        "next_action": _next_required_proof_step(category, selected_missing_refs),
    }


def _missing_evidence_refs(
    *,
    selected: Mapping[str, Any],
    source_refs: Mapping[str, Any],
    refs_by_category: Mapping[str, list[str]],
) -> dict[str, Any]:
    debt_item = dict(selected["debt_item"])
    selected_refs = _string_list(debt_item.get("missing_refs"))
    return {
        "schema_version": SCHEMA_VERSION,
        "refs_id": f"missing_evidence_refs.{selected['capability_id']}.{ARTIFACT_VERSION}",
        "mode": MODE,
        "refs_are_not_execution_authority": True,
        "live_execution_enabled": False,
        "selected_capability_id": str(selected["capability_id"]),
        "selected_debt_id": str(debt_item["debt_id"]),
        "selected_category": str(debt_item["category"]),
        "source_refs": dict(source_refs),
        "selected_missing_refs": selected_refs,
        "selected_missing_ref_count": len(selected_refs),
        "missing_refs_by_category": {
            category: list(refs_by_category.get(category, []))
            for category in CATEGORY_ORDER
        },
        "approval_refs": list(refs_by_category.get("approval", [])),
        "evidence_refs": list(refs_by_category.get("evidence", [])),
        "rollback_refs": list(refs_by_category.get("rollback", [])),
        "replay_refs": list(refs_by_category.get("replay", [])),
        "promotion_refs": list(refs_by_category.get("promotion", [])),
        "live_action_refs": list(refs_by_category.get("live_action", [])),
        "next_action": str(debt_item["fix"]),
    }


def _next_approval_action(
    *,
    selected: Mapping[str, Any],
    source_refs: Mapping[str, Any],
    approval_refs: list[str],
) -> dict[str, Any]:
    debt_item = dict(selected["debt_item"])
    approval_required = bool(approval_refs)
    required_receipts = [ref for ref in approval_refs if ref.endswith("_receipt")]
    required_inputs = [
        ref for ref in approval_refs
        if not ref.startswith("gate.") and not ref.endswith("_receipt")
    ]
    next_step = (
        "collect approval_decision_receipt with approval_chain, approval_refs, actor_id, and separation_of_duty"
        if approval_required
        else "no approval evidence required for selected closure lane"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "approval_action_id": f"next_approval_action.{selected['capability_id']}.{ARTIFACT_VERSION}",
        "mode": MODE,
        "approval_action_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "selected_capability_id": str(selected["capability_id"]),
        "selected_debt_id": str(debt_item["debt_id"]),
        "source_refs": dict(source_refs),
        "approval_required": approval_required,
        "approval_gate_ids": [ref for ref in approval_refs if ref.startswith("gate.")],
        "required_approval_receipts": required_receipts,
        "required_approval_inputs": required_inputs,
        "missing_approval_refs": list(approval_refs),
        "next_required_proof_step": next_step,
        "operator_review_required": approval_required,
        "execution_after_approval_allowed": False,
        "blocked_until_refs_present": list(approval_refs),
        "proof_validator_command": "python scripts/validate_capability_closure_runner.py --strict",
    }


def _closure_receipt(
    *,
    selected: Mapping[str, Any],
    source_refs: Mapping[str, Any],
    plan: Mapping[str, Any],
    missing_refs: Mapping[str, Any],
    next_approval: Mapping[str, Any],
    artifact_filenames: Mapping[str, str],
) -> dict[str, Any]:
    material = {
        "selected_capability_id": selected["capability_id"],
        "selected_debt_id": selected["debt_item"]["debt_id"],
        "plan_id": plan["plan_id"],
        "refs_id": missing_refs["refs_id"],
        "approval_action_id": next_approval["approval_action_id"],
    }
    digest = _digest(material)
    return {
        "schema_version": SCHEMA_VERSION,
        "closure_receipt_id": f"closure_receipt.{selected['capability_id']}.{digest[:16]}.{ARTIFACT_VERSION}",
        "mode": MODE,
        "closure_receipt_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "selected_capability_id": str(selected["capability_id"]),
        "selected_debt_id": str(selected["debt_item"]["debt_id"]),
        "source_refs": dict(source_refs),
        "status": "AwaitingEvidence",
        "closure_claim": "not_closed",
        "proof_state": "Unknown",
        "artifacts": {
            "capability_closure_plan": str(artifact_filenames["capability_closure_plan"]),
            "missing_evidence_refs": str(artifact_filenames["missing_evidence_refs"]),
            "next_approval_action": str(artifact_filenames["next_approval_action"]),
            "closure_receipt": str(artifact_filenames["closure_receipt"]),
        },
        "causal_trace": [
            "Read capability debt report runtime projection.",
            "Selected one deterministic closure lane.",
            "Emitted missing approval and evidence refs.",
            "Emitted next approval proof step.",
            "Stopped before live execution or mutation authority.",
        ],
        "effect_boundary": dict(LIVE_EFFECT_BOUNDARY),
        "validators": _validators(),
        "next_action": str(plan["next_action"]),
    }


def _debt_rows(debt_report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw_rows = debt_report.get("debt_rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise CapabilityClosureRunnerError("capability closure requires non-empty debt_rows")
    rows: dict[str, dict[str, Any]] = {}
    for raw_row in raw_rows:
        if not isinstance(raw_row, Mapping):
            raise CapabilityClosureRunnerError("debt row entries must be objects")
        row = dict(raw_row)
        capability_id = str(row.get("capability_id", ""))
        if not capability_id:
            raise CapabilityClosureRunnerError("debt row capability_id is required")
        if capability_id in rows:
            raise CapabilityClosureRunnerError(f"duplicate debt row {capability_id}")
        rows[capability_id] = row
    return rows


def _ranked_items(rows: Any) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    ranked: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for row in rows:
        for item in _debt_items(row):
            ranked.append((row, item))
    return sorted(
        ranked,
        key=lambda pair: (
            SEVERITY_ORDER.index(str(pair[1]["severity"])),
            CATEGORY_ORDER.index(str(pair[1]["category"])),
            str(pair[0]["capability_id"]),
            str(pair[1]["debt_id"]),
        ),
    )


def _selected_lane(row: Mapping[str, Any], item: Mapping[str, Any], reason: str) -> dict[str, Any]:
    return {
        "capability_id": str(row["capability_id"]),
        "capability_name": str(row["capability_name"]),
        "family": str(row["family"]),
        "debt_row": dict(row),
        "debt_item": dict(item),
        "selection_reason": reason,
    }


def _item_by_category(row: Mapping[str, Any], category: str) -> dict[str, Any] | None:
    for item in _debt_items(row):
        if item.get("category") == category:
            return item
    return None


def _debt_items(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_items = row.get("debt_items")
    if not isinstance(raw_items, list):
        raise CapabilityClosureRunnerError(f"{row.get('capability_id', '<missing>')}: debt_items must be a list")
    items: list[dict[str, Any]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, Mapping):
            raise CapabilityClosureRunnerError("debt item entries must be objects")
        item = dict(raw_item)
        category = str(item.get("category", ""))
        severity = str(item.get("severity", ""))
        if category not in CATEGORY_ORDER:
            raise CapabilityClosureRunnerError(f"unsupported debt category {category}")
        if severity not in SEVERITY_ORDER:
            raise CapabilityClosureRunnerError(f"unsupported debt severity {severity}")
        items.append(item)
    return items


def _source_refs(debt_report: Mapping[str, Any], selected: Mapping[str, Any]) -> dict[str, str]:
    raw_source_refs = debt_report.get("source_refs")
    source_refs = {
        key: str(value)
        for key, value in raw_source_refs.items()
    } if isinstance(raw_source_refs, Mapping) else {}
    capability_id = str(selected["capability_id"])
    source_refs.update({
        "debt_report_id": str(debt_report.get("debt_report_id", "")),
        "debt_row_id": str(selected["debt_row"].get("debt_row_id", "")),
        "selected_debt_id": str(selected["debt_item"].get("debt_id", "")),
        "evidence_passport_id": f"evidence_passport.{capability_id}.foundation.v1",
    })
    return source_refs


def _missing_refs_by_category(row: Mapping[str, Any]) -> dict[str, list[str]]:
    refs_by_category = {category: [] for category in CATEGORY_ORDER}
    for item in _debt_items(row):
        category = str(item["category"])
        refs_by_category[category] = _string_list(item.get("missing_refs"))
    return refs_by_category


def _current_gate(missing_refs: list[str], category: str) -> str:
    for ref in missing_refs:
        if ref.startswith("gate."):
            return ref
    return f"gate.capability_debt.{category}"


def _next_required_proof_step(category: str, missing_refs: list[str]) -> str:
    joined_refs = ", ".join(missing_refs)
    if category == "approval":
        return f"collect governed approval evidence: {joined_refs}"
    if category == "rollback":
        return f"bind rollback or recovery evidence: {joined_refs}"
    if category == "replay":
        return f"collect deterministic replay evidence: {joined_refs}"
    if category == "promotion":
        return f"close promotion controls: {joined_refs}"
    if category == "live_action":
        return "keep live action disabled until evidence and approval closure complete"
    return f"collect required evidence: {joined_refs}"


def _validators() -> list[dict[str, Any]]:
    return [
        {
            "validator_id": "capability_closure_runner_validator",
            "command": "python scripts/validate_capability_closure_runner.py --strict",
            "required_for_closure": True,
        },
        {
            "validator_id": "capability_closure_runner_tests",
            "command": "python -m pytest tests/test_capability_closure_runner.py tests/test_validate_capability_closure_runner.py -q",
            "required_for_closure": True,
        },
    ]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item]


def _digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
