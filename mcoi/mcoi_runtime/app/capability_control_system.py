"""Build the master capability control-system read model.

Purpose: organize governed capabilities into registry rows, L0-L9 unlock
levels, friction modes, lab/real-world boundaries, and operator dashboard
tasks.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: capability packs, capability passports, capability dashboard,
and the reusable capability unlock ladder.
Invariants:
  - The control system is read-only visibility and never execution authority.
  - L0-L9 levels are derived from capability pack metadata, not operator text.
  - Friction modes may reduce local approval noise only inside lab boundaries.
  - Real-world, external, customer, billing, deployment, and connector writes
    remain approval-bound.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from mcoi_runtime.app.capability_passport_dashboard import build_capability_passport_dashboard
from mcoi_runtime.app.capability_passports import build_capability_passports
from mcoi_runtime.contracts.governed_capability_fabric import CapabilityRegistryEntry
from mcoi_runtime.core.capability_unlock_ladder import (
    UNLOCK_LADDER_ID,
    CapabilityUnlockAdmissionProfile,
    capability_unlock_admission_profile,
    default_capability_unlock_ladder,
)


SCHEMA_VERSION = 1
CONTROL_SYSTEM_ID = "capability_control_system.foundation.v1"
FRICTION_MODES = ("strict", "balanced", "fast")
OPERATING_BOUNDARIES = ("lab", "real_world")


class CapabilityControlSystemError(ValueError):
    """Raised when the capability control-system projection cannot close."""


def build_capability_control_system(
    *,
    capability_pack_paths: tuple[Path, ...] | None = None,
    passports: Mapping[str, Any] | None = None,
    dashboard: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the master read-only capability control system.

    Input contract: optional capability pack paths, passport set, and dashboard
    payload. When omitted, repository sources are loaded deterministically.
    Output contract: JSON-serializable operator read model that answers what is
    unlocked, blocked, why, and what evidence is needed next.
    Error contract: raises CapabilityControlSystemError for missing packs,
    duplicate capabilities, malformed unlock levels, or drift between source
    packs and passport projections.
    """

    repo_root = _repo_root()
    effective_pack_paths = capability_pack_paths or _default_capability_pack_paths(repo_root)
    entries_by_id = _load_entries_by_id(effective_pack_paths, repo_root)
    passport_set = dict(passports or build_capability_passports(capability_pack_paths=effective_pack_paths))
    dashboard_model = dict(dashboard or build_capability_passport_dashboard(passports=passport_set))
    passport_by_id = _passport_by_id(passport_set)
    _validate_source_alignment(entries_by_id, passport_by_id)

    levels = default_capability_unlock_ladder()
    level_rows = [_level_row(level) for level in levels]
    registry_rows = [
        _registry_row(entry, passport_by_id[capability_id])
        for capability_id, entry in sorted(entries_by_id.items())
    ]
    task_cards = _task_cards(registry_rows)

    return {
        "schema_version": SCHEMA_VERSION,
        "control_system_id": CONTROL_SYSTEM_ID,
        "mode": "foundation",
        "control_system_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "source_refs": {
            "capability_packs": [_path_label(path, repo_root) for path in effective_pack_paths],
            "passport_set_id": str(passport_set.get("passport_set_id", "")),
            "dashboard_id": str(dashboard_model.get("dashboard_id", "")),
            "unlock_ladder_id": UNLOCK_LADDER_ID,
        },
        "summary": {
            "capability_count": len(registry_rows),
            "unlocked_count": sum(1 for row in registry_rows if row["unlocked"] is True),
            "blocked_count": sum(1 for row in registry_rows if row["blocked"] is True),
            "approval_required_count": sum(
                1 for row in registry_rows if row["requires_operator_approval"] is True
            ),
            "rollback_required_count": sum(1 for row in registry_rows if row["requires_rollback"] is True),
            "live_witness_required_count": sum(
                1 for row in registry_rows if row["requires_live_witness"] is True
            ),
            "fast_mode_lab_ready_count": sum(
                1 for row in registry_rows if row["fast_mode_lab_ready"] is True
            ),
            "external_effects_allowed": False,
        },
        "unlock_levels": level_rows,
        "friction_modes": _friction_modes(),
        "operating_boundaries": _operating_boundaries(),
        "safe_automatic_zones": _safe_automatic_zones(),
        "dangerous_zones": _dangerous_zones(),
        "registry": registry_rows,
        "dashboard_tasks": task_cards,
        "validators": [
            {
                "validator_id": "capability_control_system_validator",
                "command": "python scripts/validate_capability_control_system.py",
                "required_for_closure": True,
            },
            {
                "validator_id": "capability_control_system_tests",
                "command": "python -m pytest tests/test_validate_capability_control_system.py -q",
                "required_for_closure": True,
            },
        ],
        "next_action": (
            "Use this read model as the master operator surface for reducing "
            "friction before wiring additional capability families into live "
            "execution paths."
        ),
    }


def _registry_row(entry: CapabilityRegistryEntry, passport: Mapping[str, Any]) -> dict[str, Any]:
    profile = capability_unlock_admission_profile(entry)
    if profile is None:
        profile = _fallback_unlock_profile(entry, passport)
    blocked_actions = [str(action) for action in passport.get("blocked_actions", [])]
    required_receipts = [str(receipt) for receipt in passport.get("required_receipts", [])]
    operator_status = str(passport.get("operator_status", ""))
    unlocked = operator_status in {"Ready", "Prepare-only", "Needs approval", "Live action disabled"}
    blocked = operator_status in {"Blocked", "Evidence missing"} or bool(passport.get("blockers", []))
    fast_mode_lab_ready = profile.level <= 4 and profile.requires_live_witness is False
    return {
        "capability_id": entry.capability_id,
        "family": entry.domain,
        "display_name": str(entry.metadata.get("display_name", entry.capability_id)),
        "status": _registry_status(operator_status, blocked),
        "operator_status": operator_status,
        "unlock_level": profile.level_id,
        "unlock_level_number": profile.level,
        "unlocked": unlocked,
        "blocked": blocked,
        "allowed": list(profile.allowed_effects),
        "blocked_actions": blocked_actions,
        "required_before_unlock": list(profile.gate_template_ids),
        "required_receipts": required_receipts,
        "next_evidence_needed": str(passport.get("next_unlock_step", "")),
        "requires_operator_approval": profile.requires_operator_approval,
        "requires_rollback": profile.requires_rollback,
        "requires_live_witness": profile.requires_live_witness,
        "safe_zone": _safe_zone_for(profile),
        "danger_zone": _danger_zone_for(profile),
        "fast_mode_lab_ready": fast_mode_lab_ready,
        "rollback_status": str(_rollback_status(passport)),
    }


def _level_row(level: Any) -> dict[str, Any]:
    return {
        "level_id": level.level_id,
        "level": level.level,
        "name": level.name,
        "summary": level.summary,
        "allowed_effects": list(level.allowed_effects),
        "forbidden_effects": list(level.forbidden_effects),
        "required_gates": list(level.required_gate_ids),
        "requires_operator_approval": level.requires_operator_approval,
        "requires_receipt": level.requires_receipt,
        "requires_rollback": level.requires_rollback,
        "requires_live_witness": level.requires_live_witness,
    }


def _friction_modes() -> list[dict[str, Any]]:
    return [
        {
            "mode_id": "strict",
            "label": "Strict Mode",
            "default_boundary": "real_world",
            "approval_policy": "approval_before_sensitive_or_external_effects",
            "automatic_zones": [],
            "blocked_zones": _dangerous_zones(),
        },
        {
            "mode_id": "balanced",
            "label": "Balanced Mode",
            "default_boundary": "lab",
            "approval_policy": "approval_before_risky_or_external_actions",
            "automatic_zones": ["docs", "tests", "examples", "schemas", "validators"],
            "blocked_zones": _dangerous_zones(),
        },
        {
            "mode_id": "fast",
            "label": "Fast Mode",
            "default_boundary": "lab",
            "approval_policy": "auto_admit_reversible_local_lab_actions_with_receipts",
            "automatic_zones": _safe_automatic_zones(),
            "blocked_zones": _dangerous_zones(),
        },
    ]


def _operating_boundaries() -> list[dict[str, Any]]:
    return [
        {
            "boundary_id": "lab",
            "label": "Lab mode",
            "allowed": ["write_local_files", "run_tests", "create_demos", "prepare_pr_packet"],
            "blocked": ["touch_real_users", "move_money", "send_email", "deploy", "write_production_data"],
        },
        {
            "boundary_id": "real_world",
            "label": "Real-world mode",
            "allowed": ["approved_live_read", "approved_live_write", "monitored_customer_workflow"],
            "blocked": ["unapproved_external_write", "receiptless_mutation", "unmonitored_production_action"],
        },
    ]


def _safe_automatic_zones() -> list[str]:
    return ["docs", "tests", "examples", "readme", "schemas", "validators", "local_demo_files"]


def _dangerous_zones() -> list[str]:
    return [
        "delete_files",
        "touch_secrets",
        "send_email",
        "move_money",
        "deploy",
        "merge_to_main",
        "write_production_data",
    ]


def _task_cards(registry_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    focus_ids = (
        "software_dev.change.run",
        "software_dev.pr_candidate.prepare",
        "financial.send_payment",
        "messaging.chat.send.with_approval",
        "document.create",
    )
    rows_by_id = {str(row["capability_id"]): row for row in registry_rows}
    cards = []
    for capability_id in focus_ids:
        row = rows_by_id.get(capability_id)
        if row is None:
            continue
        cards.append(
            {
                "task": str(row["display_name"]),
                "capability_id": capability_id,
                "status": str(row["status"]),
                "reason": _task_reason(row),
                "next_unlock": str(row["next_evidence_needed"]),
                "risk": _risk_for_row(row),
                "action_needed": _action_needed(row),
            }
        )
    return cards


def _load_entries_by_id(pack_paths: tuple[Path, ...], repo_root: Path) -> dict[str, CapabilityRegistryEntry]:
    entries: dict[str, CapabilityRegistryEntry] = {}
    for pack_path in pack_paths:
        payload = _load_json_object(pack_path, "capability pack")
        raw_capabilities = payload.get("capabilities")
        if not isinstance(raw_capabilities, list) or not raw_capabilities:
            raise CapabilityControlSystemError(f"{_path_label(pack_path, repo_root)} must contain capabilities")
        for raw_capability in raw_capabilities:
            if not isinstance(raw_capability, Mapping):
                raise CapabilityControlSystemError(f"{_path_label(pack_path, repo_root)} capability must be object")
            entry = CapabilityRegistryEntry.from_mapping(raw_capability)
            if entry.capability_id in entries:
                raise CapabilityControlSystemError(f"duplicate capability_id {entry.capability_id}")
            entries[entry.capability_id] = entry
    return entries


def _passport_by_id(passport_set: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw_passports = passport_set.get("passports")
    if not isinstance(raw_passports, list) or not raw_passports:
        raise CapabilityControlSystemError("passport set must contain passports")
    passports: dict[str, dict[str, Any]] = {}
    for raw_passport in raw_passports:
        if not isinstance(raw_passport, Mapping):
            raise CapabilityControlSystemError("passport entries must be objects")
        passport = dict(raw_passport)
        capability_id = str(passport.get("capability_id", ""))
        if not capability_id:
            raise CapabilityControlSystemError("passport capability_id missing")
        if capability_id in passports:
            raise CapabilityControlSystemError(f"duplicate passport {capability_id}")
        passports[capability_id] = passport
    return passports


def _validate_source_alignment(
    entries_by_id: Mapping[str, CapabilityRegistryEntry],
    passport_by_id: Mapping[str, Mapping[str, Any]],
) -> None:
    entry_ids = set(entries_by_id)
    passport_ids = set(passport_by_id)
    if entry_ids != passport_ids:
        missing = sorted(entry_ids - passport_ids)
        extra = sorted(passport_ids - entry_ids)
        raise CapabilityControlSystemError(f"capability passport drift missing={missing} extra={extra}")


def _fallback_unlock_profile(
    entry: CapabilityRegistryEntry,
    passport: Mapping[str, Any],
) -> CapabilityUnlockAdmissionProfile:
    level = 0 if passport.get("operator_status") == "Ready" else 1
    ladder_level = {item.level: item for item in default_capability_unlock_ladder()}[level]
    return CapabilityUnlockAdmissionProfile(
        capability_id=entry.capability_id,
        ladder_id=UNLOCK_LADDER_ID,
        level=ladder_level.level,
        level_id=ladder_level.level_id,
        gate_template_ids=ladder_level.required_gate_ids,
        requires_operator_approval=ladder_level.requires_operator_approval,
        requires_receipt=ladder_level.requires_receipt,
        requires_rollback=ladder_level.requires_rollback,
        requires_live_witness=ladder_level.requires_live_witness,
        allowed_effects=ladder_level.allowed_effects,
        forbidden_effects=ladder_level.forbidden_effects,
    )


def _registry_status(operator_status: str, blocked: bool) -> str:
    if blocked:
        return "blocked"
    if operator_status == "Needs approval":
        return "approval_ready"
    if operator_status in {"Prepare-only", "Live action disabled"}:
        return "preflight_ready"
    if operator_status == "Ready":
        return "ready"
    return "awaiting_evidence"


def _rollback_status(passport: Mapping[str, Any]) -> str:
    rollback = passport.get("rollback_status")
    if isinstance(rollback, Mapping):
        return str(rollback.get("status", ""))
    return ""


def _safe_zone_for(profile: CapabilityUnlockAdmissionProfile) -> str:
    if profile.level <= 2:
        return "prepare_only"
    if profile.level <= 4:
        return "local_lab"
    return "approval_bound"


def _danger_zone_for(profile: CapabilityUnlockAdmissionProfile) -> str:
    if profile.level >= 9:
        return "production_customer"
    if profile.level >= 8:
        return "live_connector_write"
    if profile.level >= 7:
        return "live_connector_read"
    if profile.level >= 5:
        return "source_control_publication"
    return "none"


def _task_reason(row: Mapping[str, Any]) -> str:
    if row["blocked"] is True:
        return "required evidence or hard governance condition is missing"
    if row["requires_operator_approval"] is True:
        return "operator approval is required before the next effect boundary"
    return "capability can operate inside its current read or preparation boundary"


def _risk_for_row(row: Mapping[str, Any]) -> str:
    if row["requires_live_witness"] is True:
        return "high"
    if row["requires_rollback"] is True or row["requires_operator_approval"] is True:
        return "medium"
    return "low"


def _action_needed(row: Mapping[str, Any]) -> str:
    if row["blocked"] is True:
        return str(row["next_evidence_needed"])
    if row["requires_operator_approval"] is True:
        return "approve bounded lab action or keep prepare-only"
    return "none"


def _default_capability_pack_paths(repo_root: Path) -> tuple[Path, ...]:
    capability_root = repo_root / "capabilities"
    if not capability_root.exists():
        raise CapabilityControlSystemError("capabilities directory is missing")
    return tuple(sorted(capability_root.glob("*/capability_pack.json")))


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise CapabilityControlSystemError(f"{label} file missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise CapabilityControlSystemError(f"{label} JSON parse failed: {path}") from exc
    if not isinstance(payload, dict):
        raise CapabilityControlSystemError(f"{label} root must be object: {path}")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _repo_root() -> Path:
    for candidate in (Path.cwd(), *Path(__file__).resolve().parents):
        if (candidate / "capabilities").exists() and (candidate / "schemas").exists():
            return candidate
    raise CapabilityControlSystemError("repository root with capabilities could not be found")


def _path_label(path: Path, repo_root: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.name
