"""Build sandbox-to-live promotion paths for governed capabilities.

Purpose: project each capability onto a reusable promotion path from sandbox
to production without granting live authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: capability passports, gate template registry, and evidence
passports.
Invariants:
  - Promotion paths are read-only planning records and never execution authority.
  - Every capability has exactly one ordered sandbox-to-live path.
  - Foundation mode keeps live execution disabled for every stage.
  - No capability may jump from demo evidence directly to live action.
"""

from __future__ import annotations

from typing import Any, Mapping

from mcoi_runtime.app.capability_passports import build_capability_passports
from mcoi_runtime.app.evidence_passports import build_evidence_passports
from mcoi_runtime.app.gate_template_registry import build_gate_template_registry


SCHEMA_VERSION = 1
PROMOTION_PATH_SET_ID = "sandbox_to_live_promotion_paths.foundation.v1"
STAGE_ORDER = (
    "sandbox",
    "local_demo",
    "dry_run",
    "operator_review",
    "pilot",
    "limited_live",
    "approved_live",
    "production",
)
STAGE_LABELS = {
    "sandbox": "Sandbox",
    "local_demo": "Local demo",
    "dry_run": "Dry-run",
    "operator_review": "Operator review",
    "pilot": "Pilot",
    "limited_live": "Limited live",
    "approved_live": "Approved live",
    "production": "Production",
}
STAGE_DESCRIPTIONS = {
    "sandbox": "Capability is registered and bounded for isolated proof.",
    "local_demo": "Capability has local demo or mock-evaluation evidence.",
    "dry_run": "Capability has no-effect rehearsal, receipt, and replay obligations.",
    "operator_review": "Capability needs approval, evidence review, or recovery review.",
    "pilot": "Capability is eligible only for bounded pilot planning after live evidence.",
    "limited_live": "Capability requires bounded live receipts and active rollback coverage.",
    "approved_live": "Capability requires approved live action evidence and terminal receipts.",
    "production": "Capability requires production witness evidence and retained monitoring.",
}


class SandboxToLivePromotionError(ValueError):
    """Raised when promotion paths cannot be projected safely."""


def build_sandbox_to_live_promotion_paths(
    *,
    passports: Mapping[str, Any] | None = None,
    gate_registry: Mapping[str, Any] | None = None,
    evidence_passports: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic sandbox-to-live promotion paths.

    Input contract: optional passport, gate registry, and evidence passport
    payloads. When omitted, runtime projections are built from repository
    sources.
    Output contract: JSON-serializable read model containing one ordered
    promotion path per capability.
    Error contract: raises SandboxToLivePromotionError for malformed source
    payloads, duplicate capabilities, or mismatched evidence packets.
    """

    passport_set = dict(passports or build_capability_passports())
    registry = dict(gate_registry or build_gate_template_registry())
    evidence_set = dict(
        evidence_passports
        or build_evidence_passports(passports=passport_set, gate_registry=registry)
    )
    passport_entries = _passport_entries(passport_set)
    evidence_by_capability = _evidence_by_capability(evidence_set)
    paths = [
        _promotion_path(passport, evidence_by_capability[str(passport["capability_id"])])
        for passport in passport_entries
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "promotion_path_set_id": PROMOTION_PATH_SET_ID,
        "mode": "foundation",
        "promotion_path_set_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "source_refs": {
            "passport_set_id": str(passport_set.get("passport_set_id", "")),
            "gate_registry_id": str(registry.get("registry_id", "")),
            "evidence_passport_set_id": str(evidence_set.get("evidence_passport_set_id", "")),
        },
        "stage_order": list(STAGE_ORDER),
        "summary": _summary(paths),
        "promotion_paths": paths,
        "validators": [
            {
                "validator_id": "sandbox_to_live_promotion_validator",
                "command": "python scripts/validate_sandbox_to_live_promotion.py",
                "required_for_closure": True,
            },
            {
                "validator_id": "sandbox_to_live_promotion_tests",
                "command": "python -m pytest tests/test_validate_sandbox_to_live_promotion.py -q",
                "required_for_closure": True,
            },
        ],
        "next_action": (
            "Use sandbox-to-live promotion paths before adding the capability "
            "debt report and before enabling any live-action surface."
        ),
    }


def _promotion_path(passport: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    capability_id = str(passport["capability_id"])
    current_stage = _current_stage(passport, evidence)
    target_stage = _next_stage(current_stage)
    stages = [
        _stage_state(stage_id, current_stage, passport, evidence)
        for stage_id in STAGE_ORDER
    ]
    blocked_stage_ids = [
        stage["stage_id"]
        for stage in stages
        if stage["stage_status"] == "blocked"
    ]
    return {
        "promotion_path_id": f"sandbox_to_live_promotion.{capability_id}.foundation.v1",
        "capability_id": capability_id,
        "capability_name": str(passport["capability_name"]),
        "family": str(passport["family"]),
        "current_unlock_level": str(passport["current_unlock_level"]),
        "operator_status": str(passport["operator_status"]),
        "current_stage": current_stage,
        "next_stage": target_stage,
        "stage_count": len(STAGE_ORDER),
        "stages": stages,
        "blocked_stage_ids": blocked_stage_ids,
        "promotion_blocked": bool(blocked_stage_ids),
        "live_action_enabled": False,
        "next_promotion_step": _next_promotion_step(current_stage, passport, evidence),
        "promotion_path_is_not_execution_authority": True,
    }


def _passport_entries(passport_set: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    raw_passports = passport_set.get("passports")
    if not isinstance(raw_passports, list) or not raw_passports:
        raise SandboxToLivePromotionError("promotion path projection requires non-empty passports list")
    passports: list[dict[str, Any]] = []
    seen_capability_ids: set[str] = set()
    for raw_passport in raw_passports:
        if not isinstance(raw_passport, Mapping):
            raise SandboxToLivePromotionError("passport entries must be objects")
        passport = dict(raw_passport)
        capability_id = str(passport.get("capability_id", ""))
        if not capability_id:
            raise SandboxToLivePromotionError("passport capability_id is required")
        if capability_id in seen_capability_ids:
            raise SandboxToLivePromotionError(f"duplicate promotion capability {capability_id}")
        seen_capability_ids.add(capability_id)
        passports.append(passport)
    return tuple(sorted(passports, key=lambda passport: str(passport["capability_id"])))


def _evidence_by_capability(evidence_set: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw_evidence_passports = evidence_set.get("evidence_passports")
    if not isinstance(raw_evidence_passports, list) or not raw_evidence_passports:
        raise SandboxToLivePromotionError("promotion path projection requires non-empty evidence passports")
    by_capability: dict[str, dict[str, Any]] = {}
    for raw_evidence in raw_evidence_passports:
        if not isinstance(raw_evidence, Mapping):
            raise SandboxToLivePromotionError("evidence passport entries must be objects")
        evidence = dict(raw_evidence)
        capability_id = str(evidence.get("capability_id", ""))
        if not capability_id:
            raise SandboxToLivePromotionError("evidence passport capability_id is required")
        if capability_id in by_capability:
            raise SandboxToLivePromotionError(f"duplicate evidence passport capability {capability_id}")
        by_capability[capability_id] = evidence
    return by_capability


def _current_stage(passport: Mapping[str, Any], evidence: Mapping[str, Any]) -> str:
    if evidence.get("outcome") == "GovernanceBlocked" or passport.get("operator_status") == "Blocked":
        return "sandbox"
    level = str(passport.get("current_unlock_level", "C0"))
    if level in {"C0", "C1", "C2"}:
        return "sandbox"
    if level == "C3":
        return "local_demo"
    if level == "C4":
        return "dry_run"
    if level == "C5":
        return "operator_review"
    approval = evidence.get("approval")
    if isinstance(approval, Mapping) and approval.get("missing_approval") is True:
        return "operator_review"
    continuation = evidence.get("continuation")
    if isinstance(continuation, Mapping) and continuation.get("safe_for_live_action") is True:
        return "pilot"
    return "operator_review"


def _stage_state(
    stage_id: str,
    current_stage: str,
    passport: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    current_index = STAGE_ORDER.index(current_stage)
    stage_index = STAGE_ORDER.index(stage_id)
    if stage_index < current_index:
        status = "complete"
    elif stage_index == current_index:
        status = "current"
    else:
        status = _future_stage_status(stage_id, passport, evidence)
    return {
        "stage_id": stage_id,
        "label": STAGE_LABELS[stage_id],
        "sequence": stage_index + 1,
        "stage_status": status,
        "description": STAGE_DESCRIPTIONS[stage_id],
        "required_controls": _stage_controls(stage_id),
        "missing_controls": _missing_controls(stage_id, passport, evidence) if status in {"current", "blocked"} else [],
        "live_execution_allowed": False,
    }


def _future_stage_status(stage_id: str, passport: Mapping[str, Any], evidence: Mapping[str, Any]) -> str:
    if stage_id in {"pilot", "limited_live", "approved_live", "production"}:
        return "blocked"
    if _missing_controls(stage_id, passport, evidence):
        return "blocked"
    return "pending"


def _missing_controls(
    stage_id: str,
    passport: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> list[str]:
    missing: list[str] = []
    if stage_id == "sandbox" and passport.get("certification_status") in {"suspended", "retired"}:
        missing.append("active_capability_certification")
    if stage_id == "local_demo" and _level_index(passport) < 3:
        missing.append("mock_or_local_eval_evidence")
    if stage_id == "dry_run" and _level_index(passport) < 4:
        missing.append("sandbox_receipt_evidence")
    if stage_id == "operator_review":
        approval = evidence.get("approval")
        rollback = evidence.get("rollback")
        if isinstance(approval, Mapping) and approval.get("missing_approval") is True:
            missing.append("approval_evidence")
        if isinstance(rollback, Mapping) and rollback.get("rollback_evidence_missing") is True:
            missing.append("rollback_or_recovery_evidence")
        if evidence.get("missing_evidence"):
            missing.append("required_evidence")
    if stage_id == "pilot":
        if _level_index(passport) < 6:
            missing.append("production_readiness_evidence")
        if not _safe_for_live_action(evidence):
            missing.append("safe_live_action_evidence")
        missing.append("operator_pilot_authorization")
    if stage_id == "limited_live":
        missing.extend(["bounded_live_receipts", "active_monitoring_receipt"])
    if stage_id == "approved_live":
        missing.extend(["approved_live_action_receipt", "terminal_closure_certificate"])
    if stage_id == "production":
        missing.extend(["production_witness", "release_handoff_receipt"])
    return _dedupe(missing)


def _stage_controls(stage_id: str) -> list[str]:
    return {
        "sandbox": ["capability_registry_binding", "schema_policy_boundary"],
        "local_demo": ["mock_or_local_eval_receipt", "no_external_effects"],
        "dry_run": ["sandbox_receipt", "receipt_append", "deterministic_replay_plan"],
        "operator_review": ["approval_review", "evidence_review", "rollback_review"],
        "pilot": ["pilot_authorization", "live_evidence", "connector_lease"],
        "limited_live": ["bounded_live_scope", "monitoring", "rollback_or_compensation"],
        "approved_live": ["operator_approval", "external_effect_receipt", "terminal_certificate"],
        "production": ["production_witness", "public_claim_boundary", "release_handoff"],
    }[stage_id]


def _next_stage(current_stage: str) -> str:
    index = STAGE_ORDER.index(current_stage)
    if index >= len(STAGE_ORDER) - 1:
        return "production"
    return STAGE_ORDER[index + 1]


def _next_promotion_step(
    current_stage: str,
    passport: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> str:
    current_missing = _missing_controls(current_stage, passport, evidence)
    if current_missing:
        return f"close {current_stage} controls: {', '.join(current_missing)}"
    if current_stage in {"sandbox", "local_demo", "dry_run"}:
        return str(passport.get("next_unlock_step", "add required evidence"))
    if current_stage == "operator_review":
        return str(evidence.get("next_evidence_step", "collect approval and evidence review"))
    return "keep live execution disabled until pilot, live receipts, and production witnesses are collected"


def _summary(paths: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "capability_count": len(paths),
        "promotion_path_count": len(paths),
        "family_counts": _counts(paths, "family"),
        "current_stage_counts": {stage: _counts(paths, "current_stage").get(stage, 0) for stage in STAGE_ORDER},
        "blocked_path_count": sum(1 for path in paths if path["promotion_blocked"]),
        "live_action_enabled_count": sum(1 for path in paths if path["live_action_enabled"]),
        "production_stage_count": sum(1 for path in paths if path["current_stage"] == "production"),
    }


def _level_index(passport: Mapping[str, Any]) -> int:
    level = str(passport.get("current_unlock_level", "C0"))
    if not level.startswith("C"):
        return 0
    try:
        return int(level[1:])
    except ValueError:
        return 0


def _safe_for_live_action(evidence: Mapping[str, Any]) -> bool:
    continuation = evidence.get("continuation")
    return isinstance(continuation, Mapping) and continuation.get("safe_for_live_action") is True


def _counts(paths: list[dict[str, Any]], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in paths:
        key = str(path[field_name])
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
