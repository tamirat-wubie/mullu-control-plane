"""Build evidence passports for governed capabilities.

Purpose: standardize proof packets for capability actions across families.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: capability passports and gate template registry.
Invariants:
  - Evidence passports are read-only proof packets and never execution authority.
  - Every capability passport has exactly one evidence passport.
  - Missing evidence, approval, replay, rollback, and blocked actions are explicit.
  - Live action remains disabled in foundation mode.
"""

from __future__ import annotations

from typing import Any, Mapping

from mcoi_runtime.app.capability_passports import build_capability_passports
from mcoi_runtime.app.gate_template_registry import build_gate_template_registry


SCHEMA_VERSION = 1
EVIDENCE_PASSPORT_SET_ID = "evidence_passports.foundation.v1"
PROOF_STATES = ("Pass", "Fail", "Unknown", "BudgetUnknown")
OUTCOMES = (
    "SolvedVerified",
    "AwaitingEvidence",
    "SafeHalt",
    "GovernanceBlocked",
    "BudgetExhausted",
    "ImpossibleProved",
    "ModelInvalidated",
)


class EvidencePassportError(ValueError):
    """Raised when evidence passports cannot be projected safely."""


def build_evidence_passports(
    *,
    passports: Mapping[str, Any] | None = None,
    gate_registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic evidence passports for governed capabilities.

    Input contract: optional capability passport set and gate registry. When
    omitted, runtime projections are built from repository sources.
    Output contract: JSON-serializable proof packet set suitable for evidence
    dashboards, debt reports, and promotion planning.
    Error contract: raises EvidencePassportError for malformed source payloads,
    duplicate capabilities, or unresolved gate templates.
    """

    passport_set = dict(passports or build_capability_passports())
    registry = dict(gate_registry or build_gate_template_registry())
    passport_entries = _passport_entries(passport_set)
    templates_by_gate = _templates_by_gate(registry)
    evidence_passports = [
        _evidence_passport(passport, templates_by_gate)
        for passport in passport_entries
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_passport_set_id": EVIDENCE_PASSPORT_SET_ID,
        "mode": "foundation",
        "evidence_passport_set_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "source_refs": {
            "passport_set_id": str(passport_set.get("passport_set_id", "")),
            "gate_registry_id": str(registry.get("registry_id", "")),
        },
        "summary": _summary(evidence_passports),
        "evidence_passports": evidence_passports,
        "validators": [
            {
                "validator_id": "evidence_passports_validator",
                "command": "python scripts/validate_evidence_passports.py",
                "required_for_closure": True,
            },
            {
                "validator_id": "evidence_passports_tests",
                "command": "python -m pytest tests/test_validate_evidence_passports.py -q",
                "required_for_closure": True,
            },
        ],
        "next_action": (
            "Use evidence passports as the shared proof packet before adding "
            "sandbox-to-live promotion paths and capability debt reports."
        ),
    }


def _evidence_passport(
    passport: Mapping[str, Any],
    templates_by_gate: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    capability_id = str(passport["capability_id"])
    required_gates = _string_list(passport.get("required_gates"))
    missing_gate_templates = sorted(gate_id for gate_id in required_gates if gate_id not in templates_by_gate)
    if missing_gate_templates:
        raise EvidencePassportError(f"{capability_id}: unresolved gate templates {missing_gate_templates}")

    required_evidence = _required_evidence(passport, templates_by_gate)
    present_evidence_refs = _string_list(passport.get("evidence_refs"))
    production_ready = passport.get("production_ready") is True
    approval_packet = _approval_packet(passport, templates_by_gate)
    rollback_packet = _rollback_packet(passport)
    replay_packet = _replay_packet(passport, present_evidence_refs, production_ready)
    missing_evidence = [] if production_ready else required_evidence
    outcome = _outcome(passport, missing_evidence, approval_packet, rollback_packet)
    proof_state = _proof_state(outcome)

    return {
        "evidence_passport_id": f"evidence_passport.{capability_id}.foundation.v1",
        "capability_id": capability_id,
        "capability_name": str(passport["capability_name"]),
        "family": str(passport["family"]),
        "operator_status": str(passport["operator_status"]),
        "current_unlock_level": str(passport["current_unlock_level"]),
        "proof_state": proof_state,
        "outcome": outcome,
        "evidence_exists": {
            "present_evidence_refs": present_evidence_refs,
            "present_evidence_count": len(present_evidence_refs),
        },
        "required_evidence": required_evidence,
        "missing_evidence": missing_evidence,
        "approval": approval_packet,
        "blocked": {
            "blocked_actions": _string_list(passport.get("blocked_actions")),
            "blocked_action_count": len(_string_list(passport.get("blocked_actions"))),
            "blocked_by_gate_ids": _blocked_by_gate_ids(passport, templates_by_gate),
        },
        "replay": replay_packet,
        "rollback": rollback_packet,
        "continuation": _continuation_packet(passport, outcome, approval_packet, rollback_packet),
        "next_evidence_step": _next_evidence_step(passport, missing_evidence, approval_packet, rollback_packet),
        "evidence_passport_is_not_execution_authority": True,
    }


def _passport_entries(passport_set: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    raw_passports = passport_set.get("passports")
    if not isinstance(raw_passports, list) or not raw_passports:
        raise EvidencePassportError("evidence passport projection requires non-empty passports list")
    passports: list[dict[str, Any]] = []
    seen_capability_ids: set[str] = set()
    for raw_passport in raw_passports:
        if not isinstance(raw_passport, Mapping):
            raise EvidencePassportError("passport entries must be objects")
        passport = dict(raw_passport)
        capability_id = str(passport.get("capability_id", ""))
        if not capability_id:
            raise EvidencePassportError("passport capability_id is required")
        if capability_id in seen_capability_ids:
            raise EvidencePassportError(f"duplicate evidence passport capability {capability_id}")
        seen_capability_ids.add(capability_id)
        passports.append(passport)
    return tuple(sorted(passports, key=lambda passport: str(passport["capability_id"])))


def _templates_by_gate(gate_registry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw_templates = gate_registry.get("templates")
    if not isinstance(raw_templates, list) or not raw_templates:
        raise EvidencePassportError("evidence passport projection requires non-empty gate templates")
    templates_by_gate: dict[str, dict[str, Any]] = {}
    for raw_template in raw_templates:
        if not isinstance(raw_template, Mapping):
            raise EvidencePassportError("gate templates must be objects")
        template = dict(raw_template)
        gate_id = str(template.get("gate_id", ""))
        if not gate_id:
            raise EvidencePassportError("gate template gate_id is required")
        if gate_id in templates_by_gate:
            raise EvidencePassportError(f"duplicate gate template {gate_id}")
        templates_by_gate[gate_id] = template
    return templates_by_gate


def _required_evidence(
    passport: Mapping[str, Any],
    templates_by_gate: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    required = _string_list(passport.get("required_receipts"))
    for gate_id in _string_list(passport.get("required_gates")):
        template = templates_by_gate[gate_id]
        required.extend(_string_list(template.get("required_receipts")))
    return _dedupe(required)


def _approval_packet(
    passport: Mapping[str, Any],
    templates_by_gate: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    required_gates = set(_string_list(passport.get("required_gates")))
    approval_required = "gate.approval.required" in required_gates
    approval_template = templates_by_gate.get("gate.approval.required", {})
    required_inputs = _string_list(approval_template.get("required_inputs")) if approval_required else []
    required_receipts = _string_list(approval_template.get("required_receipts")) if approval_required else []
    blocked_actions = _string_list(passport.get("blocked_actions"))
    approval_blocked_actions = [
        action
        for action in blocked_actions
        if action in set(_string_list(approval_template.get("blocks_when_missing")))
    ]
    missing_refs = _dedupe([
        "gate.approval.required",
        *required_receipts,
        *required_inputs,
    ]) if approval_required else []
    return {
        "approval_required": approval_required,
        "approved": False,
        "approval_refs": [],
        "missing_approval": approval_required,
        "approval_state": "required_missing" if approval_required else "not_required",
        "required_approval_gate_ids": ["gate.approval.required"] if approval_required else [],
        "required_approval_inputs": required_inputs,
        "required_approval_receipts": required_receipts,
        "approval_blocked_actions": approval_blocked_actions,
        "missing_approval_refs": missing_refs,
        "next_approval_action": (
            "collect approval_decision_receipt with approval_chain, approval_refs, actor_id, and separation_of_duty"
            if approval_required
            else "no approval evidence required"
        ),
    }


def _rollback_packet(passport: Mapping[str, Any]) -> dict[str, Any]:
    rollback_status = passport.get("rollback_status")
    if not isinstance(rollback_status, Mapping):
        raise EvidencePassportError(f"{passport['capability_id']}: rollback_status must be an object")
    status = str(rollback_status.get("status", ""))
    if status not in {"not_required", "ready", "compensation_only", "review_only", "missing"}:
        raise EvidencePassportError(f"{passport['capability_id']}: unsupported rollback status {status!r}")
    rollback_ready = status in {"not_required", "ready", "compensation_only"}
    missing_refs = _rollback_missing_refs(status, rollback_status)
    return {
        "rollback_status": status,
        "rollback_capability": str(rollback_status.get("rollback_capability", "")),
        "compensation_capability": str(rollback_status.get("compensation_capability", "")),
        "rollback_or_compensation_available": rollback_ready,
        "rollback_evidence_missing": status in {"review_only", "missing"},
        "can_rollback": status in {"ready", "not_required"},
        "can_compensate": status == "compensation_only",
        "missing_rollback_refs": missing_refs,
        "next_rollback_action": (
            f"bind rollback, compensation, or recovery evidence: {', '.join(missing_refs)}"
            if missing_refs
            else "no rollback evidence required"
        ),
    }


def _rollback_missing_refs(
    status: str,
    rollback_status: Mapping[str, Any],
) -> list[str]:
    if status not in {"review_only", "missing"}:
        return []
    refs = ["recovery_evidence_missing"]
    if not str(rollback_status.get("rollback_capability", "")):
        refs.append("rollback_capability")
    if not str(rollback_status.get("compensation_capability", "")):
        refs.append("compensation_capability")
    if rollback_status.get("review_required_on_failure") is True:
        refs.append("failure_review_receipt")
    refs.append("rollback_or_recovery_evidence")
    return _dedupe(refs)


def _replay_packet(
    passport: Mapping[str, Any],
    present_evidence_refs: list[str],
    production_ready: bool,
) -> dict[str, Any]:
    required_receipts = _string_list(passport.get("required_receipts"))
    replay_required = bool(required_receipts)
    replay_refs = [ref for ref in present_evidence_refs if "replay" in ref.lower()]
    replayable = production_ready and (not replay_required or bool(replay_refs))
    missing_refs = _replay_missing_refs(replay_required, replay_refs, required_receipts)
    return {
        "replay_required": replay_required,
        "replayable": replayable,
        "replay_refs": replay_refs,
        "missing_replay_evidence": replay_required and not replay_refs,
        "missing_replay_refs": missing_refs,
        "next_replay_action": (
            f"collect deterministic replay evidence: {', '.join(missing_refs)}"
            if missing_refs
            else "no replay evidence required"
        ),
    }


def _replay_missing_refs(
    replay_required: bool,
    replay_refs: list[str],
    required_receipts: list[str],
) -> list[str]:
    if not replay_required or replay_refs:
        return []
    return _dedupe([
        "replay_record",
        "replay_input_digest",
        "replay_output_digest",
        *required_receipts,
    ])


def _blocked_by_gate_ids(
    passport: Mapping[str, Any],
    templates_by_gate: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    blocked_actions = set(_string_list(passport.get("blocked_actions")))
    blocked_gate_ids: list[str] = []
    for gate_id in _string_list(passport.get("required_gates")):
        template_blocks = set(_string_list(templates_by_gate[gate_id].get("blocks_when_missing")))
        if blocked_actions & template_blocks:
            blocked_gate_ids.append(gate_id)
    return blocked_gate_ids


def _outcome(
    passport: Mapping[str, Any],
    missing_evidence: list[str],
    approval_packet: Mapping[str, Any],
    rollback_packet: Mapping[str, Any],
) -> str:
    if passport.get("operator_status") == "Blocked":
        return "GovernanceBlocked"
    if approval_packet.get("missing_approval") is True:
        return "AwaitingEvidence"
    if rollback_packet.get("rollback_evidence_missing") is True:
        return "AwaitingEvidence"
    if missing_evidence:
        return "AwaitingEvidence"
    return "SolvedVerified"


def _proof_state(outcome: str) -> str:
    if outcome == "SolvedVerified":
        return "Pass"
    if outcome == "GovernanceBlocked":
        return "Fail"
    return "Unknown"


def _continuation_packet(
    passport: Mapping[str, Any],
    outcome: str,
    approval_packet: Mapping[str, Any],
    rollback_packet: Mapping[str, Any],
) -> dict[str, Any]:
    operator_status = str(passport["operator_status"])
    safe_to_continue = outcome != "GovernanceBlocked"
    safe_for_live_action = (
        passport.get("production_ready") is True
        and approval_packet.get("missing_approval") is not True
        and rollback_packet.get("rollback_evidence_missing") is not True
        and outcome == "SolvedVerified"
    )
    return {
        "safe_to_continue": safe_to_continue,
        "safe_for_live_action": safe_for_live_action,
        "continuation_mode": _continuation_mode(operator_status, safe_for_live_action),
        "live_action_disabled": not safe_for_live_action,
    }


def _continuation_mode(operator_status: str, safe_for_live_action: bool) -> str:
    if safe_for_live_action:
        return "live_ready"
    if operator_status == "Blocked":
        return "blocked"
    if operator_status == "Needs approval":
        return "approval_required"
    if operator_status == "Evidence missing":
        return "evidence_collection"
    if operator_status == "Prepare-only":
        return "prepare_only"
    return "live_action_disabled"


def _next_evidence_step(
    passport: Mapping[str, Any],
    missing_evidence: list[str],
    approval_packet: Mapping[str, Any],
    rollback_packet: Mapping[str, Any],
) -> str:
    if approval_packet.get("missing_approval") is True:
        return "collect governed approval evidence"
    if rollback_packet.get("rollback_evidence_missing") is True:
        return "bind rollback, compensation, or recovery evidence"
    if missing_evidence:
        return str(passport["next_unlock_step"])
    return "maintain evidence, replay, approval, and rollback receipts"


def _summary(evidence_passports: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "capability_count": len(evidence_passports),
        "evidence_passport_count": len(evidence_passports),
        "family_counts": _counts(evidence_passports, "family"),
        "proof_state_counts": {state: _counts(evidence_passports, "proof_state").get(state, 0) for state in PROOF_STATES},
        "outcome_counts": {outcome: _counts(evidence_passports, "outcome").get(outcome, 0) for outcome in OUTCOMES},
        "approval_required_count": sum(
            1 for passport in evidence_passports if passport["approval"]["approval_required"]
        ),
        "missing_evidence_count": sum(1 for passport in evidence_passports if passport["missing_evidence"]),
        "blocked_action_count": sum(passport["blocked"]["blocked_action_count"] for passport in evidence_passports),
        "replayable_count": sum(1 for passport in evidence_passports if passport["replay"]["replayable"]),
        "rollback_ready_count": sum(
            1 for passport in evidence_passports if passport["rollback"]["rollback_or_compensation_available"]
        ),
        "safe_to_continue_count": sum(
            1 for passport in evidence_passports if passport["continuation"]["safe_to_continue"]
        ),
        "safe_for_live_action_count": sum(
            1 for passport in evidence_passports if passport["continuation"]["safe_for_live_action"]
        ),
    }


def _counts(passports: list[dict[str, Any]], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for passport in passports:
        key = str(passport[field_name])
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
