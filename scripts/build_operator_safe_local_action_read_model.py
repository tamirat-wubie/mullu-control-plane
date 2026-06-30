#!/usr/bin/env python3
"""Build the compact safe-local action read model.

Purpose: expose the next safe local-lab action from the operator control tower
status receipt without requiring the gateway server or granting execution
authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_operator_control_tower_status_receipt.
Invariants:
  - This script is projection-only and never executes the selected action.
  - External effects, PR creation, branch push, merge, deployment, and
    connector calls remain disabled.
  - The source status receipt is validated before projection.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_operator_control_tower_status_receipt import (  # noqa: E402
    build_default_operator_control_tower_status_receipt,
    validate_operator_control_tower_status_receipt,
)


DEFAULT_RECEIPT = REPO_ROOT / ".change_assurance" / "operator_control_tower_status_receipt.generated.json"
DEFAULT_FRICTION_CONTROL = REPO_ROOT / "examples" / "capability_friction_control.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "operator_safe_local_action_read_model.generated.json"


@dataclass(frozen=True, slots=True)
class OperatorSafeLocalActionValidation:
    """Validation report for the safe-local action read model."""

    ok: bool
    errors: tuple[str, ...]
    read_model_path: str
    queue_status: str
    candidate_id: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_operator_safe_local_action_read_model(
    *,
    status_receipt: Mapping[str, Any],
    source_ref: str,
) -> dict[str, Any]:
    """Return the next safe local-lab action projection."""

    queue = _mapping(status_receipt.get("safe_local_action_queue_summary"))
    candidates = status_receipt.get("safe_automatic_action_candidates", ())
    if not isinstance(candidates, list):
        candidates = []
    if not candidates:
        candidates = _safe_candidates_from_friction_control(DEFAULT_FRICTION_CONTROL)
    if not queue or (int(queue.get("candidate_count", 0) or 0) == 0 and candidates):
        queue = _safe_queue_summary_from_candidates(candidates)
    first_candidate = _first_candidate(candidates, str(queue.get("first_candidate_id") or ""))
    candidate_id = str(first_candidate.get("candidate_id") or queue.get("first_candidate_id") or "")
    zone = str(first_candidate.get("zone") or queue.get("first_zone") or "")
    action = str(first_candidate.get("primary_action") or queue.get("first_action") or "prepare safe local sandbox work")
    href = str(first_candidate.get("primary_href") or "/operator/control-tower?domain=software_dev")
    queue_status = str(queue.get("queue_status") or ("ready" if candidate_id else "empty"))
    candidate_count = int(queue.get("candidate_count", len(candidates)) or 0)
    recommended_mode = str(queue.get("recommended_mode") or "fast")
    operator_message = str(
        queue.get("operator_message")
        or f"{candidate_count} safe local actions queued for {recommended_mode} mode; approval not required for local preparation"
    )
    return {
        "read_model_id": "operator_safe_local_action.read_model",
        "projection_only": True,
        "execution_performed": False,
        "external_effects_allowed": False,
        "task": "Safe Local Action Queue",
        "queue_status": queue_status,
        "candidate_count": candidate_count,
        "candidate": {
            "candidate_id": candidate_id,
            "zone": zone,
            "title": str(first_candidate.get("title") or _title_from_zone(zone)),
            "status": str(first_candidate.get("status") or ("candidate" if candidate_id else "missing")),
            "primary_action": action,
            "primary_href": href,
            "risk": "low, local lab only",
            "execution_boundary": "local_lab_only",
            "approval_required": False,
            "external_effects_allowed": False,
        },
        "action_contract": {
            "recommended_mode": recommended_mode,
            "approval_required": False,
            "rollback_required": False,
            "allowed_effect": "prepare_local_lab_artifact",
            "forbidden_effects": [
                "create_pr",
                "push_branch",
                "merge",
                "deploy",
                "connector_call",
                "send_email",
                "move_money",
                "write_production_data",
            ],
            "execution_performed": False,
            "external_effects_allowed": False,
        },
        "operator_message": operator_message,
        "source_ref": source_ref,
    }


def validate_operator_safe_local_action_read_model(
    *,
    read_model: Mapping[str, Any],
    read_model_path: Path = Path("<generated>"),
) -> OperatorSafeLocalActionValidation:
    """Validate no-effect semantics for a safe-local action read model."""

    errors: list[str] = []
    if read_model.get("read_model_id") != "operator_safe_local_action.read_model":
        errors.append("read_model_id_invalid")
    if read_model.get("projection_only") is not True:
        errors.append("projection_only_must_be_true")
    if read_model.get("execution_performed") is not False:
        errors.append("execution_performed_must_be_false")
    if read_model.get("external_effects_allowed") is not False:
        errors.append("external_effects_must_be_false")
    candidate = _mapping(read_model.get("candidate"))
    action_contract = _mapping(read_model.get("action_contract"))
    if candidate.get("approval_required") is not False:
        errors.append("candidate_approval_required_must_be_false")
    if candidate.get("external_effects_allowed") is not False:
        errors.append("candidate_external_effects_must_be_false")
    if candidate.get("execution_boundary") != "local_lab_only":
        errors.append("candidate_boundary_must_be_local_lab_only")
    if action_contract.get("approval_required") is not False:
        errors.append("contract_approval_required_must_be_false")
    if action_contract.get("execution_performed") is not False:
        errors.append("contract_execution_performed_must_be_false")
    if action_contract.get("external_effects_allowed") is not False:
        errors.append("contract_external_effects_must_be_false")
    forbidden_effects = action_contract.get("forbidden_effects", ())
    if not isinstance(forbidden_effects, list):
        errors.append("forbidden_effects_must_be_list")
        forbidden_effects = []
    for forbidden_effect in ("create_pr", "push_branch", "merge", "deploy", "connector_call"):
        if forbidden_effect not in forbidden_effects:
            errors.append(f"forbidden_effect_missing:{forbidden_effect}")
    queue_status = str(read_model.get("queue_status") or "")
    candidate_id = str(candidate.get("candidate_id") or "")
    if queue_status == "ready" and not candidate_id:
        errors.append("ready_queue_requires_candidate_id")
    return OperatorSafeLocalActionValidation(
        ok=not errors,
        errors=tuple(errors),
        read_model_path=_path_label(read_model_path),
        queue_status=queue_status,
        candidate_id=candidate_id,
    )


def write_operator_safe_local_action_read_model(read_model: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic safe-local action read model."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(read_model, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _load_status_receipt(receipt_path: Path | None) -> tuple[dict[str, Any], str]:
    if receipt_path is None:
        return build_default_operator_control_tower_status_receipt(), "<generated-control-tower-status-receipt>"
    validation = validate_operator_control_tower_status_receipt(receipt_path=receipt_path)
    if not validation.ok:
        raise ValueError(f"status_receipt_invalid:{list(validation.errors)}")
    payload = _load_json_object(receipt_path)
    return payload, _path_label(receipt_path)


def _safe_candidates_from_friction_control(friction_control_path: Path) -> list[dict[str, Any]]:
    payload = _load_json_object(friction_control_path)
    safe_zones = payload.get("safe_automatic_zones", ())
    if not isinstance(safe_zones, list):
        return []
    labels = {
        "write_docs": "Prepare documentation update",
        "write_tests": "Prepare test update",
        "write_examples": "Prepare example update",
        "write_local_demo_files": "Prepare local demo file",
        "update_README": "Prepare README update",
        "generate_schemas": "Prepare schema generation",
        "generate_validators": "Prepare validator generation",
    }
    candidates: list[dict[str, Any]] = []
    for zone in safe_zones:
        zone_id = str(zone).strip()
        if not zone_id:
            continue
        title = labels.get(zone_id, f"Prepare {zone_id.replace('_', ' ')}")
        candidates.append({
            "candidate_id": f"safe_zone.{zone_id}",
            "zone": zone_id,
            "title": title,
            "status": "candidate",
            "primary_action": f"{title} in local sandbox",
            "primary_href": "/operator/control-tower?domain=software_dev",
            "risk": "low, local lab only",
            "execution_boundary": "local_lab_only",
            "approval_required": False,
            "external_effects_allowed": False,
        })
    return candidates[:8]


def _safe_queue_summary_from_candidates(candidates: Sequence[Any]) -> Mapping[str, Any]:
    normalized_candidates = [candidate for candidate in candidates if isinstance(candidate, Mapping)]
    first_candidate = normalized_candidates[0] if normalized_candidates else {}
    candidate_count = len(normalized_candidates)
    return {
        "queue_status": "ready" if candidate_count else "empty",
        "candidate_count": candidate_count,
        "first_candidate_id": str(first_candidate.get("candidate_id") or ""),
        "first_zone": str(first_candidate.get("zone") or ""),
        "first_action": str(first_candidate.get("primary_action") or "prepare safe local sandbox work"),
        "recommended_mode": "fast",
        "approval_required": False,
        "local_execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "operator_message": (
            f"{candidate_count} safe local actions queued for fast mode; "
            "approval not required for local preparation"
        ),
    }


def _first_candidate(candidates: Sequence[Any], preferred_candidate_id: str) -> Mapping[str, Any]:
    for candidate in candidates:
        if isinstance(candidate, Mapping) and str(candidate.get("candidate_id") or "") == preferred_candidate_id:
            return candidate
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            return candidate
    return {}


def _title_from_zone(zone: str) -> str:
    if not zone:
        return "Safe local action unavailable"
    return f"Prepare {zone.replace('_', ' ')}"


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


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse safe-local action read-model builder arguments."""

    parser = argparse.ArgumentParser(description="Build safe local action read model.")
    parser.add_argument("--receipt", default="", help="Optional operator control tower status receipt path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for safe-local action read-model building."""

    args = parse_args(argv)
    output_path = Path(args.output)
    try:
        status_receipt, source_ref = _load_status_receipt(Path(args.receipt) if args.receipt else None)
        read_model = build_operator_safe_local_action_read_model(
            status_receipt=status_receipt,
            source_ref=source_ref,
        )
        written_path = write_operator_safe_local_action_read_model(read_model, output_path)
        validation = validate_operator_safe_local_action_read_model(
            read_model=read_model,
            read_model_path=written_path,
        )
    except ValueError as exc:
        print(f"OPERATOR SAFE LOCAL ACTION INVALID error={exc}")
        return 2
    if not validation.ok:
        print(f"OPERATOR SAFE LOCAL ACTION INVALID errors={list(validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(read_model, indent=2, sort_keys=True))
    else:
        print(f"OPERATOR SAFE LOCAL ACTION BUILT path={written_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
