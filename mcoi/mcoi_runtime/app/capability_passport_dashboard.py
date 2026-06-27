"""Build the capability passport operator dashboard read model.

Purpose: project capability passports into simple operator-facing status lanes.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: capability passport projection and gate template registry.
Invariants:
  - The dashboard is read-only visibility and never execution authority.
  - Every passport appears in exactly one operator status lane.
  - Operator cards hide raw gates, schema refs, and admission internals.
  - Gate coverage is tracked in governance health, not used for execution.
"""

from __future__ import annotations

from typing import Any, Mapping

from mcoi_runtime.app.capability_passports import build_capability_passports
from mcoi_runtime.app.gate_template_registry import build_gate_template_registry


SCHEMA_VERSION = 1
DASHBOARD_ID = "capability_passport_dashboard.foundation.v1"
STATUS_ORDER = (
    "Ready",
    "Prepare-only",
    "Needs approval",
    "Blocked",
    "Evidence missing",
    "Live action disabled",
)
STATUS_MEANINGS = {
    "Ready": "Capability has enough governed evidence for its current allowed action surface.",
    "Prepare-only": "Capability can prepare work but must not execute live effects.",
    "Needs approval": "Capability requires operator or policy approval before execution.",
    "Blocked": "Capability is suspended, retired, or missing a hard governance requirement.",
    "Evidence missing": "Capability needs evidence intake or verification before promotion.",
    "Live action disabled": "Capability can be inspected or prepared, but live action remains disabled.",
}


class CapabilityPassportDashboardError(ValueError):
    """Raised when the dashboard read model cannot be projected safely."""


def build_capability_passport_dashboard(
    *,
    passports: Mapping[str, Any] | None = None,
    gate_registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic capability passport dashboard read model.

    Input contract: optional passport and gate registry payloads. When omitted,
    runtime projections are built from repository sources.
    Output contract: JSON-serializable operator read model with simple status
    lanes, family rows, and governance coverage health.
    Error contract: raises CapabilityPassportDashboardError when source
    payloads are malformed, incomplete, or expose unsupported status values.
    """

    passport_set = dict(passports or build_capability_passports())
    registry = dict(gate_registry or build_gate_template_registry())
    passport_entries = _passport_entries(passport_set)
    templates_by_gate = _templates_by_gate(registry)
    status_lanes = _status_lanes(passport_entries)
    family_rows = _family_rows(passport_entries)
    required_gate_ids = _required_gate_ids(passport_entries)
    unresolved_gate_ids = sorted(gate_id for gate_id in required_gate_ids if gate_id not in templates_by_gate)

    return {
        "schema_version": SCHEMA_VERSION,
        "dashboard_id": DASHBOARD_ID,
        "mode": "foundation",
        "dashboard_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "source_refs": {
            "passport_set_id": str(passport_set.get("passport_set_id", "")),
            "gate_registry_id": str(registry.get("registry_id", "")),
        },
        "summary": {
            "capability_count": len(passport_entries),
            "family_count": len(family_rows),
            "status_counts": _status_counts(passport_entries),
            "ready_count": _status_counts(passport_entries)["Ready"],
            "attention_required_count": sum(
                _status_counts(passport_entries)[status]
                for status in ("Prepare-only", "Needs approval", "Blocked", "Evidence missing", "Live action disabled")
            ),
            "live_action_disabled": True,
        },
        "operator_view": {
            "status_tiles": _status_tiles(passport_entries),
            "status_lanes": status_lanes,
            "family_rows": family_rows,
        },
        "governance_health": {
            "required_gate_template_count": len(required_gate_ids),
            "resolved_gate_template_count": len(required_gate_ids) - len(unresolved_gate_ids),
            "unresolved_gate_count": len(unresolved_gate_ids),
            "unresolved_gate_ids": unresolved_gate_ids,
            "passport_count": len(passport_entries),
            "gate_registry_template_count": len(templates_by_gate),
            "operator_view_hides_internal_gate_ids": True,
            "operator_view_hides_schema_refs": True,
        },
        "validators": [
            {
                "validator_id": "capability_passport_dashboard_validator",
                "command": "python scripts/validate_capability_passport_dashboard.py",
                "required_for_closure": True,
            },
            {
                "validator_id": "capability_passport_dashboard_tests",
                "command": "python -m pytest tests/test_validate_capability_passport_dashboard.py -q",
                "required_for_closure": True,
            },
        ],
        "next_action": (
            "Use this read model as the operator-facing surface before adding "
            "evidence passports, sandbox-to-live promotion views, and debt reports."
        ),
    }


def _passport_entries(passport_set: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    raw_passports = passport_set.get("passports")
    if not isinstance(raw_passports, list) or not raw_passports:
        raise CapabilityPassportDashboardError("dashboard projection requires non-empty passports list")
    passports: list[dict[str, Any]] = []
    seen_capability_ids: set[str] = set()
    for raw_passport in raw_passports:
        if not isinstance(raw_passport, Mapping):
            raise CapabilityPassportDashboardError("passport entries must be objects")
        passport = dict(raw_passport)
        capability_id = str(passport.get("capability_id", ""))
        if not capability_id:
            raise CapabilityPassportDashboardError("passport capability_id is required")
        if capability_id in seen_capability_ids:
            raise CapabilityPassportDashboardError(f"duplicate dashboard capability {capability_id}")
        seen_capability_ids.add(capability_id)
        status = str(passport.get("operator_status", ""))
        if status not in STATUS_ORDER:
            raise CapabilityPassportDashboardError(f"{capability_id}: unsupported operator_status {status!r}")
        passports.append(passport)
    return tuple(sorted(passports, key=lambda passport: str(passport["capability_id"])))


def _templates_by_gate(gate_registry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw_templates = gate_registry.get("templates")
    if not isinstance(raw_templates, list) or not raw_templates:
        raise CapabilityPassportDashboardError("dashboard projection requires non-empty gate templates")
    templates_by_gate: dict[str, dict[str, Any]] = {}
    for raw_template in raw_templates:
        if not isinstance(raw_template, Mapping):
            raise CapabilityPassportDashboardError("gate templates must be objects")
        template = dict(raw_template)
        gate_id = str(template.get("gate_id", ""))
        if not gate_id:
            raise CapabilityPassportDashboardError("gate template gate_id is required")
        if gate_id in templates_by_gate:
            raise CapabilityPassportDashboardError(f"duplicate gate template {gate_id}")
        templates_by_gate[gate_id] = template
    return templates_by_gate


def _status_tiles(passports: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    counts = _status_counts(passports)
    return [
        {
            "label": status,
            "count": counts[status],
            "meaning": STATUS_MEANINGS[status],
            "severity_rank": index,
        }
        for index, status in enumerate(STATUS_ORDER)
    ]


def _status_lanes(passports: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    return [
        {
            "label": status,
            "count": len(_passports_with_status(passports, status)),
            "capabilities": [_operator_card(passport) for passport in _passports_with_status(passports, status)],
        }
        for status in STATUS_ORDER
    ]


def _family_rows(passports: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family in sorted({str(passport["family"]) for passport in passports}):
        family_passports = tuple(passport for passport in passports if passport["family"] == family)
        counts = _status_counts(family_passports)
        rows.append(
            {
                "family": family,
                "capability_count": len(family_passports),
                "status_counts": counts,
                "dominant_status": _dominant_status(counts),
                "highest_unlock_level": _highest_unlock_level(family_passports),
                "next_action": _family_next_action(family_passports),
            }
        )
    return rows


def _operator_card(passport: Mapping[str, Any]) -> dict[str, Any]:
    rollback_status = passport.get("rollback_status")
    rollback_label = ""
    if isinstance(rollback_status, Mapping):
        rollback_label = str(rollback_status.get("status", ""))
    return {
        "capability_id": str(passport["capability_id"]),
        "capability_name": str(passport["capability_name"]),
        "family": str(passport["family"]),
        "status": str(passport["operator_status"]),
        "current_unlock_level": str(passport["current_unlock_level"]),
        "allowed_actions": [str(action) for action in passport.get("allowed_actions", [])],
        "blocked_action_count": len(passport.get("blocked_actions", [])),
        "required_receipt_count": len(passport.get("required_receipts", [])),
        "rollback_status": rollback_label,
        "next_unlock_step": str(passport["next_unlock_step"]),
    }


def _passports_with_status(passports: tuple[dict[str, Any], ...], status: str) -> tuple[dict[str, Any], ...]:
    return tuple(passport for passport in passports if passport["operator_status"] == status)


def _status_counts(passports: tuple[dict[str, Any], ...]) -> dict[str, int]:
    return {
        status: sum(1 for passport in passports if passport["operator_status"] == status)
        for status in STATUS_ORDER
    }


def _dominant_status(counts: Mapping[str, int]) -> str:
    return sorted(STATUS_ORDER, key=lambda status: (-int(counts.get(status, 0)), STATUS_ORDER.index(status)))[0]


def _highest_unlock_level(passports: tuple[dict[str, Any], ...]) -> str:
    levels = [str(passport["current_unlock_level"]) for passport in passports]
    return sorted(levels, key=lambda level: int(level.removeprefix("C")), reverse=True)[0]


def _family_next_action(passports: tuple[dict[str, Any], ...]) -> str:
    for status in STATUS_ORDER:
        matching = _passports_with_status(passports, status)
        if matching:
            return str(matching[0]["next_unlock_step"])
    raise CapabilityPassportDashboardError("family row requires at least one passport")


def _required_gate_ids(passports: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    gate_ids: set[str] = set()
    for passport in passports:
        raw_gates = passport.get("required_gates", [])
        if not isinstance(raw_gates, list):
            raise CapabilityPassportDashboardError(f"{passport['capability_id']}: required_gates must be a list")
        gate_ids.update(str(gate_id) for gate_id in raw_gates)
    return tuple(sorted(gate_ids))
