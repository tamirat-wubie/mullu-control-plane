"""Build capability passports from governed capability packs.

Purpose: project one operator-facing passport per registered capability.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: capability pack JSON, governed capability fabric contracts, and
    the C0-C7 capability maturity assessor.
Invariants:
  - Capability passports are read-only evidence and never execution authority.
  - Passport state is derived from governed capability pack entries.
  - Unlock level is derived from evidence, never declared by the passport.
  - Effect-bearing capabilities expose gates, receipts, and recovery status.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from gateway.capability_maturity import CapabilityRegistryMaturityProjector
from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityRegistryEntry,
    GovernedCapabilityRecord,
)


SCHEMA_VERSION = 1
PASSPORT_SET_ID = "capability_passports.foundation.v1"
MATURITY_LEVELS = ("C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7")
OPERATOR_STATUSES = (
    "Ready",
    "Prepare-only",
    "Needs approval",
    "Blocked",
    "Evidence missing",
    "Live action disabled",
)


class CapabilityPassportError(ValueError):
    """Raised when capability passports cannot be projected safely."""


def build_capability_passports(
    *,
    capability_pack_paths: tuple[Path, ...] | None = None,
) -> dict[str, Any]:
    """Return deterministic foundation capability passports.

    Input contract: optional capability pack paths. When omitted, every
    `capabilities/*/capability_pack.json` file is loaded.
    Output contract: JSON-serializable passport set suitable for operator read
    models and debt reports.
    Error contract: raises CapabilityPassportError when a capability pack is
    missing, malformed, duplicated, or unsafe to project.
    """

    repo_root = _repo_root()
    effective_pack_paths = capability_pack_paths or _default_capability_pack_paths(repo_root)
    entries_by_source = _load_capability_entries(effective_pack_paths, repo_root)
    entries = tuple(entry for _source, entry in entries_by_source)
    if not entries:
        raise CapabilityPassportError("capability passport projection requires at least one capability")

    passports = [
        _capability_passport(entry, source_path, repo_root)
        for source_path, entry in sorted(entries_by_source, key=lambda item: item[1].capability_id)
    ]
    passport_ids = [passport["passport_id"] for passport in passports]
    if len(set(passport_ids)) != len(passport_ids):
        raise CapabilityPassportError("duplicate capability passport id detected")

    return {
        "schema_version": SCHEMA_VERSION,
        "passport_set_id": PASSPORT_SET_ID,
        "mode": "foundation",
        "source_refs": {
            "capability_packs": [_path_label(path, repo_root) for path in effective_pack_paths],
        },
        "passport_set_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "summary": _summary(passports),
        "passports": passports,
        "validators": [
            {
                "validator_id": "capability_passports_validator",
                "command": "python scripts/validate_capability_passports.py",
                "required_for_closure": True,
            },
            {
                "validator_id": "capability_passports_tests",
                "command": "python -m pytest tests/test_validate_capability_passports.py -q",
                "required_for_closure": True,
            },
        ],
        "next_action": (
            "Use capability passports as the shared identity card before adding "
            "gate templates, dashboard projections, evidence passports, and "
            "sandbox-to-live promotion views."
        ),
    }


def _capability_passport(
    entry: CapabilityRegistryEntry,
    source_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    governed = GovernedCapabilityRecord.from_registry_entry(entry)
    assessment = CapabilityRegistryMaturityProjector().assess_entry(entry)
    assessment_payload = _assessment_payload(assessment)
    required_gates = _required_gates(entry, governed, assessment_payload)
    required_receipts = _required_receipts(entry)
    rollback_status = _rollback_status(entry, governed)
    blocked_actions = _blocked_actions(entry, governed, assessment_payload, rollback_status)
    operator_status = _operator_status(entry, governed, assessment_payload, rollback_status)

    return {
        "passport_id": f"capability_passport.{entry.capability_id}.foundation.v1",
        "capability_id": entry.capability_id,
        "capability_name": _display_name(entry),
        "family": entry.domain,
        "version": entry.version,
        "source_ref": _path_label(source_path, repo_root),
        "certification_status": entry.certification_status.value,
        "current_unlock_level": assessment.maturity_level,
        "unlock_label": assessment.maturity_label,
        "operator_status": operator_status,
        "allowed_actions": _allowed_actions(entry, governed),
        "allowed_tools": list(governed.allowed_tools),
        "blocked_actions": blocked_actions,
        "required_gates": required_gates,
        "required_receipts": required_receipts,
        "rollback_status": rollback_status,
        "next_unlock_step": _next_unlock_step(assessment_payload),
        "evidence_refs": list(assessment.evidence_refs),
        "production_ready": assessment.production_ready,
        "autonomy_ready": assessment.autonomy_ready,
        "blockers": list(assessment.blockers),
        "passport_is_not_execution_authority": True,
    }


def _load_capability_entries(
    pack_paths: tuple[Path, ...],
    repo_root: Path,
) -> tuple[tuple[Path, CapabilityRegistryEntry], ...]:
    entries: list[tuple[Path, CapabilityRegistryEntry]] = []
    capability_ids: set[str] = set()
    for pack_path in pack_paths:
        payload = _load_json_object(pack_path, "capability pack")
        raw_capabilities = payload.get("capabilities")
        if not isinstance(raw_capabilities, list) or not raw_capabilities:
            raise CapabilityPassportError(f"{_path_label(pack_path, repo_root)} must contain capabilities list")
        for raw_capability in raw_capabilities:
            if not isinstance(raw_capability, Mapping):
                raise CapabilityPassportError(f"{_path_label(pack_path, repo_root)} capability entries must be objects")
            entry = CapabilityRegistryEntry.from_mapping(raw_capability)
            if entry.capability_id in capability_ids:
                raise CapabilityPassportError(f"duplicate capability_id {entry.capability_id}")
            capability_ids.add(entry.capability_id)
            entries.append((pack_path, entry))
    return tuple(entries)


def _required_gates(
    entry: CapabilityRegistryEntry,
    governed: GovernedCapabilityRecord,
    assessment: Mapping[str, Any],
) -> list[str]:
    gates = [
        "gate.uao.admission",
        "gate.capability.registry",
        "gate.evidence.intake",
        "gate.evidence.verification",
        "gate.receipt.append",
    ]
    if governed.requires_approval or entry.authority_policy.approval_chain:
        gates.append("gate.approval.required")
    if governed.requires_sandbox:
        gates.append("gate.sandbox.required")
    if _requires_connector_lease(entry, governed):
        gates.append("gate.connector.lease")
    if governed.world_mutating:
        gates.append("gate.rollback.required")
    if _requires_external_send_gate(entry):
        gates.append("gate.external.send")
    if _requires_workspace_write_gate(entry, governed):
        gates.append("gate.workspace.write")
    if assessment.get("production_ready") is not True:
        gates.append("gate.production.evidence")
    return _dedupe(gates)


def _required_receipts(entry: CapabilityRegistryEntry) -> list[str]:
    receipts = list(entry.evidence_model.required_evidence)
    if entry.evidence_model.terminal_certificate_required:
        receipts.append("terminal_closure_certificate")
    if entry.effect_model.reconciliation_required:
        receipts.append("effect_reconciliation_receipt")
    return _dedupe(receipts)


def _rollback_status(
    entry: CapabilityRegistryEntry,
    governed: GovernedCapabilityRecord,
) -> dict[str, Any]:
    rollback_capability = entry.recovery_plan.rollback_capability
    compensation_capability = entry.recovery_plan.compensation_capability
    if rollback_capability:
        status = "ready"
    elif compensation_capability:
        status = "compensation_only"
    elif governed.world_mutating:
        status = "review_only" if entry.recovery_plan.review_required_on_failure else "missing"
    else:
        status = "not_required"
    return {
        "status": status,
        "rollback_capability": rollback_capability,
        "compensation_capability": compensation_capability,
        "review_required_on_failure": entry.recovery_plan.review_required_on_failure,
    }


def _blocked_actions(
    entry: CapabilityRegistryEntry,
    governed: GovernedCapabilityRecord,
    assessment: Mapping[str, Any],
    rollback_status: Mapping[str, Any],
) -> list[str]:
    blocked = list(entry.effect_model.forbidden_effects)
    if governed.requires_approval or entry.authority_policy.approval_chain:
        blocked.append("execute_without_approval")
    if _requires_connector_lease(entry, governed):
        blocked.append("connector_call_without_lease")
    if entry.evidence_model.terminal_certificate_required:
        blocked.append("claim_success_without_terminal_certificate")
    if governed.world_mutating and rollback_status.get("status") == "missing":
        blocked.append("execute_without_recovery")
    if assessment.get("production_ready") is not True:
        blocked.append("claim_production_ready")
        blocked.append("live_action_enablement")
    if assessment.get("autonomy_ready") is not True:
        blocked.append("claim_autonomous_live_action")
    return _dedupe(blocked)


def _allowed_actions(
    entry: CapabilityRegistryEntry,
    governed: GovernedCapabilityRecord,
) -> list[str]:
    actions: list[str] = []
    effects = tuple(effect.lower() for effect in entry.effect_model.expected_effects)
    if governed.read_only:
        actions.append("read")
    if any("draft" in effect for effect in effects) or "draft" in entry.capability_id:
        actions.append("prepare_draft")
    if governed.requires_approval and governed.world_mutating:
        actions.append("prepare_for_approval")
    elif governed.world_mutating:
        actions.append("execute_with_governance")
    if governed.verification_required:
        actions.append("verify_evidence")
    if governed.receipt_required:
        actions.append("emit_receipt")
    if not actions:
        actions.append("prepare")
    return _dedupe(actions)


def _operator_status(
    entry: CapabilityRegistryEntry,
    governed: GovernedCapabilityRecord,
    assessment: Mapping[str, Any],
    rollback_status: Mapping[str, Any],
) -> str:
    if entry.certification_status.value in {"suspended", "retired"}:
        return "Blocked"
    if assessment.get("production_ready") is not True:
        if not assessment.get("evidence_refs"):
            return "Evidence missing"
        return "Live action disabled"
    if governed.requires_approval:
        return "Needs approval"
    if governed.world_mutating and rollback_status.get("status") in {"missing", "review_only"}:
        return "Prepare-only"
    return "Ready"


def _next_unlock_step(assessment: Mapping[str, Any]) -> str:
    level = str(assessment.get("maturity_level", "C0"))
    blockers = tuple(str(blocker) for blocker in assessment.get("blockers", ()))
    if level == "C7":
        return "maintain autonomy controls, production evidence, and replay receipts"
    if "schema_evidence_missing" in blockers:
        return "bind valid input and output schema evidence"
    if "policy_evidence_missing" in blockers:
        return "bind authority, evidence, obligation, and policy evidence"
    if "eval_evidence_missing" in blockers:
        return "add certified mock or local evaluation evidence"
    if "sandbox_receipt_missing" in blockers:
        return "add sandbox receipt evidence"
    if "live_read_receipt_missing" in blockers:
        return "add live read receipt evidence"
    if "effect_bearing_production_requires_live_write" in blockers:
        return "add live write receipt evidence"
    if "worker_deployment_evidence_missing" in blockers:
        return "bind worker deployment evidence"
    if "recovery_evidence_missing" in blockers:
        return "bind rollback or recovery evidence"
    if "autonomy_controls_missing" in blockers:
        return "bind bounded autonomy controls"
    next_index = min(MATURITY_LEVELS.index(level) + 1, len(MATURITY_LEVELS) - 1)
    return f"advance evidence toward {MATURITY_LEVELS[next_index]}"


def _summary(passports: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "capability_count": len(passports),
        "passport_count": len(passports),
        "family_counts": _counts(passports, "family"),
        "unlock_level_counts": {level: _counts(passports, "current_unlock_level").get(level, 0) for level in MATURITY_LEVELS},
        "operator_status_counts": {
            status: _counts(passports, "operator_status").get(status, 0)
            for status in OPERATOR_STATUSES
        },
        "blocked_count": sum(1 for passport in passports if passport["operator_status"] == "Blocked"),
        "approval_required_count": sum(
            1 for passport in passports if "gate.approval.required" in passport["required_gates"]
        ),
        "receipt_required_count": sum(1 for passport in passports if passport["required_receipts"]),
        "rollback_ready_count": sum(
            1
            for passport in passports
            if passport["rollback_status"]["status"] in {"ready", "compensation_only", "not_required"}
        ),
    }


def _counts(passports: list[dict[str, Any]], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for passport in passports:
        key = str(passport[field_name])
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _requires_connector_lease(entry: CapabilityRegistryEntry, governed: GovernedCapabilityRecord) -> bool:
    execution_plane = entry.isolation_profile.execution_plane.lower()
    secret_scope = entry.isolation_profile.secret_scope.lower()
    return bool(
        governed.allowed_networks
        or "worker" in execution_plane
        or "connector" in execution_plane
        or "oauth" in secret_scope
        or "provider" in secret_scope
    )


def _requires_external_send_gate(entry: CapabilityRegistryEntry) -> bool:
    joined = " ".join((*entry.effect_model.expected_effects, *entry.effect_model.forbidden_effects)).lower()
    return any(marker in joined for marker in ("external", "send", "sent", "invite", "payment"))


def _requires_workspace_write_gate(entry: CapabilityRegistryEntry, governed: GovernedCapabilityRecord) -> bool:
    joined = " ".join((*entry.effect_model.expected_effects, *entry.effect_model.forbidden_effects)).lower()
    return entry.domain in {"computer", "software_dev", "document"} and (
        governed.world_mutating or any(marker in joined for marker in ("file", "workspace", "write", "diff"))
    )


def _display_name(entry: CapabilityRegistryEntry) -> str:
    value = entry.metadata.get("display_name")
    return str(value).strip() if isinstance(value, str) and value.strip() else entry.capability_id


def _assessment_payload(assessment: Any) -> dict[str, Any]:
    return {
        "maturity_level": assessment.maturity_level,
        "maturity_label": assessment.maturity_label,
        "production_ready": assessment.production_ready,
        "autonomy_ready": assessment.autonomy_ready,
        "blockers": list(assessment.blockers),
        "evidence_refs": list(assessment.evidence_refs),
    }


def _default_capability_pack_paths(repo_root: Path) -> tuple[Path, ...]:
    capability_root = repo_root / "capabilities"
    if not capability_root.exists():
        raise CapabilityPassportError("capabilities directory is missing")
    return tuple(sorted(capability_root.glob("*/capability_pack.json")))


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise CapabilityPassportError(f"{label} file missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise CapabilityPassportError(f"{label} JSON parse failed: {path}") from exc
    if not isinstance(payload, dict):
        raise CapabilityPassportError(f"{label} root must be an object: {path}")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _repo_root() -> Path:
    for candidate in (Path.cwd(), *Path(__file__).resolve().parents):
        if (candidate / "capabilities").exists() and (candidate / "schemas").exists():
            return candidate
    raise CapabilityPassportError("repository root with capabilities could not be found")


def _path_label(path: Path, repo_root: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.name
