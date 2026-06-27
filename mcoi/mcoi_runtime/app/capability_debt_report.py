"""Build the capability debt report.

Purpose: turn capability passport, evidence, and promotion gaps into a clear
operator next-action list.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: capability passports, gate template registry, evidence passports,
and sandbox-to-live promotion paths.
Invariants:
  - Debt reports are read-only planning records and never execution authority.
  - Every capability has exactly one debt row.
  - Missing approval, evidence, replay, rollback, and promotion controls are explicit.
  - Live execution remains disabled in foundation mode.
"""

from __future__ import annotations

from typing import Any, Mapping

from mcoi_runtime.app.capability_passports import build_capability_passports
from mcoi_runtime.app.evidence_passports import build_evidence_passports
from mcoi_runtime.app.gate_template_registry import build_gate_template_registry
from mcoi_runtime.app.sandbox_to_live_promotion import build_sandbox_to_live_promotion_paths


SCHEMA_VERSION = 1
DEBT_REPORT_ID = "capability_debt_report.foundation.v1"
DEBT_CATEGORIES = (
    "evidence",
    "approval",
    "rollback",
    "replay",
    "promotion",
    "live_action",
)
SEVERITY_ORDER = ("critical", "high", "medium", "low")


class CapabilityDebtReportError(ValueError):
    """Raised when the capability debt report cannot be projected safely."""


def build_capability_debt_report(
    *,
    passports: Mapping[str, Any] | None = None,
    gate_registry: Mapping[str, Any] | None = None,
    evidence_passports: Mapping[str, Any] | None = None,
    promotion_paths: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic capability debt report.

    Input contract: optional source read models. When omitted, runtime
    projections are built from repository sources.
    Output contract: JSON-serializable read model with one debt row per
    capability and summary counters for operator planning.
    Error contract: raises CapabilityDebtReportError for malformed source
    payloads, duplicate capabilities, or mismatched source coverage.
    """

    passport_set = dict(passports or build_capability_passports())
    passport_entries = _passport_entries(passport_set)
    registry = dict(gate_registry or build_gate_template_registry())
    evidence_set = dict(
        evidence_passports
        or build_evidence_passports(passports=passport_set, gate_registry=registry)
    )
    promotion_set = dict(
        promotion_paths
        or build_sandbox_to_live_promotion_paths(
            passports=passport_set,
            gate_registry=registry,
            evidence_passports=evidence_set,
        )
    )
    evidence_by_capability = _source_by_capability(evidence_set, "evidence_passports")
    promotion_by_capability = _source_by_capability(promotion_set, "promotion_paths")
    debt_rows = [
        _debt_row(
            passport,
            evidence_by_capability[str(passport["capability_id"])],
            promotion_by_capability[str(passport["capability_id"])],
        )
        for passport in passport_entries
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "debt_report_id": DEBT_REPORT_ID,
        "mode": "foundation",
        "debt_report_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "source_refs": {
            "passport_set_id": str(passport_set.get("passport_set_id", "")),
            "gate_registry_id": str(registry.get("registry_id", "")),
            "evidence_passport_set_id": str(evidence_set.get("evidence_passport_set_id", "")),
            "promotion_path_set_id": str(promotion_set.get("promotion_path_set_id", "")),
        },
        "summary": _summary(debt_rows),
        "debt_rows": debt_rows,
        "top_debt_items": _top_debt_items(debt_rows, limit=25),
        "validators": [
            {
                "validator_id": "capability_debt_report_validator",
                "command": "python scripts/validate_capability_debt_report.py",
                "required_for_closure": True,
            },
            {
                "validator_id": "capability_debt_report_tests",
                "command": "python -m pytest tests/test_validate_capability_debt_report.py -q",
                "required_for_closure": True,
            },
        ],
        "next_action": "Use this report to select the next highest-impact evidence or promotion closure task.",
    }


def _debt_row(
    passport: Mapping[str, Any],
    evidence: Mapping[str, Any],
    promotion: Mapping[str, Any],
) -> dict[str, Any]:
    capability_id = str(passport["capability_id"])
    debt_items = _debt_items(passport, evidence, promotion)
    severity = _row_severity(debt_items)
    return {
        "debt_row_id": f"capability_debt.{capability_id}.foundation.v1",
        "capability_id": capability_id,
        "capability_name": str(passport["capability_name"]),
        "family": str(passport["family"]),
        "operator_status": str(passport["operator_status"]),
        "current_unlock_level": str(passport["current_unlock_level"]),
        "current_stage": str(promotion["current_stage"]),
        "debt_severity": severity,
        "debt_item_count": len(debt_items),
        "debt_items": debt_items,
        "next_action": _next_action(debt_items, passport, evidence, promotion),
        "live_action_enabled": False,
        "debt_row_is_not_execution_authority": True,
    }


def _debt_items(
    passport: Mapping[str, Any],
    evidence: Mapping[str, Any],
    promotion: Mapping[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    capability_id = str(passport["capability_id"])
    missing_evidence = _string_list(evidence.get("missing_evidence"))
    if missing_evidence:
        items.append(_item(capability_id, "evidence", "high", "missing required evidence", missing_evidence))

    approval = _mapping(evidence.get("approval"))
    if approval.get("missing_approval") is True:
        items.append(_item(capability_id, "approval", "high", "missing governed approval", ["approval_evidence"]))

    rollback = _mapping(evidence.get("rollback"))
    if rollback.get("rollback_evidence_missing") is True:
        items.append(
            _item(
                capability_id,
                "rollback",
                "high",
                "missing rollback or recovery proof",
                ["rollback_or_recovery_evidence"],
            )
        )

    replay = _mapping(evidence.get("replay"))
    if replay.get("missing_replay_evidence") is True:
        items.append(_item(capability_id, "replay", "medium", "missing deterministic replay proof", ["replay_evidence"]))

    blocked_stage_ids = _string_list(promotion.get("blocked_stage_ids"))
    if blocked_stage_ids:
        missing_controls = _blocked_stage_missing_controls(promotion)
        items.append(_item(capability_id, "promotion", "medium", "blocked promotion stages", missing_controls))

    if promotion.get("live_action_enabled") is not True:
        items.append(_item(capability_id, "live_action", "low", "live action disabled", ["live_action_authority"]))

    if passport.get("operator_status") == "Blocked":
        items.append(_item(capability_id, "promotion", "critical", "capability blocked", ["active_capability_certification"]))

    return _sort_items(items)


def _item(
    capability_id: str,
    category: str,
    severity: str,
    description: str,
    missing_refs: list[str],
) -> dict[str, Any]:
    if category not in DEBT_CATEGORIES:
        raise CapabilityDebtReportError(f"{capability_id}: unsupported debt category {category}")
    if severity not in SEVERITY_ORDER:
        raise CapabilityDebtReportError(f"{capability_id}: unsupported debt severity {severity}")
    normalized_refs = _dedupe(missing_refs)
    return {
        "debt_id": f"{capability_id}.{category}.{description.replace(' ', '_')}",
        "category": category,
        "severity": severity,
        "description": description,
        "missing_refs": normalized_refs,
        "fix": _fix(category, normalized_refs),
    }


def _passport_entries(passport_set: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    raw_passports = passport_set.get("passports")
    if not isinstance(raw_passports, list) or not raw_passports:
        raise CapabilityDebtReportError("debt report projection requires non-empty passports list")
    passports: list[dict[str, Any]] = []
    seen_capability_ids: set[str] = set()
    for raw_passport in raw_passports:
        if not isinstance(raw_passport, Mapping):
            raise CapabilityDebtReportError("passport entries must be objects")
        passport = dict(raw_passport)
        capability_id = str(passport.get("capability_id", ""))
        if not capability_id:
            raise CapabilityDebtReportError("passport capability_id is required")
        if capability_id in seen_capability_ids:
            raise CapabilityDebtReportError(f"duplicate debt report capability {capability_id}")
        seen_capability_ids.add(capability_id)
        passports.append(passport)
    return tuple(sorted(passports, key=lambda passport: str(passport["capability_id"])))


def _source_by_capability(source: Mapping[str, Any], field_name: str) -> dict[str, dict[str, Any]]:
    raw_entries = source.get(field_name)
    if not isinstance(raw_entries, list) or not raw_entries:
        raise CapabilityDebtReportError(f"debt report projection requires non-empty {field_name}")
    by_capability: dict[str, dict[str, Any]] = {}
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, Mapping):
            raise CapabilityDebtReportError(f"{field_name} entries must be objects")
        entry = dict(raw_entry)
        capability_id = str(entry.get("capability_id", ""))
        if not capability_id:
            raise CapabilityDebtReportError(f"{field_name} capability_id is required")
        if capability_id in by_capability:
            raise CapabilityDebtReportError(f"duplicate {field_name} capability {capability_id}")
        by_capability[capability_id] = entry
    return by_capability


def _blocked_stage_missing_controls(promotion: Mapping[str, Any]) -> list[str]:
    controls: list[str] = []
    stages = promotion.get("stages")
    if not isinstance(stages, list):
        return controls
    for stage in stages:
        if isinstance(stage, Mapping) and stage.get("stage_status") == "blocked":
            controls.extend(_string_list(stage.get("missing_controls")))
    return _dedupe(controls)


def _next_action(
    debt_items: list[dict[str, Any]],
    passport: Mapping[str, Any],
    evidence: Mapping[str, Any],
    promotion: Mapping[str, Any],
) -> str:
    if debt_items:
        first = debt_items[0]
        return str(first["fix"])
    if evidence.get("outcome") == "SolvedVerified":
        return "maintain evidence receipts and monitor promotion readiness"
    return str(promotion.get("next_promotion_step") or passport.get("next_unlock_step") or "review capability")


def _fix(category: str, missing_refs: list[str]) -> str:
    if category == "approval":
        return "collect governed approval receipt"
    if category == "rollback":
        return "bind rollback, compensation, or recovery evidence"
    if category == "replay":
        return "collect deterministic replay receipt"
    if category == "promotion":
        return f"close promotion controls: {', '.join(missing_refs)}"
    if category == "live_action":
        return "keep live action disabled until promotion evidence is complete"
    return f"collect evidence: {', '.join(missing_refs)}"


def _row_severity(debt_items: list[dict[str, Any]]) -> str:
    if not debt_items:
        return "low"
    return sorted((str(item["severity"]) for item in debt_items), key=SEVERITY_ORDER.index)[0]


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "capability_count": len(rows),
        "debt_row_count": len(rows),
        "family_counts": _counts(rows, "family"),
        "severity_counts": {severity: _counts(rows, "debt_severity").get(severity, 0) for severity in SEVERITY_ORDER},
        "category_counts": _category_counts(rows),
        "total_debt_item_count": sum(int(row["debt_item_count"]) for row in rows),
        "capabilities_with_debt_count": sum(1 for row in rows if int(row["debt_item_count"]) > 0),
        "live_action_enabled_count": sum(1 for row in rows if row["live_action_enabled"]),
    }


def _category_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {category: 0 for category in DEBT_CATEGORIES}
    for row in rows:
        for item in row["debt_items"]:
            counts[str(item["category"])] += 1
    return counts


def _top_debt_items(rows: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in rows:
        for item in row["debt_items"]:
            items.append({
                "capability_id": row["capability_id"],
                "family": row["family"],
                **item,
            })
    return _sort_items(items)[:limit]


def _sort_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            SEVERITY_ORDER.index(str(item["severity"])),
            str(item["category"]),
            str(item.get("capability_id", "")),
            str(item["debt_id"]),
        ),
    )


def _counts(rows: list[dict[str, Any]], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row[field_name])
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
