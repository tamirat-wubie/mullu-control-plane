#!/usr/bin/env python3
"""Collect a Personal Assistant policy matrix receipt.

Purpose: project checked-in Personal Assistant approval matrix, skill policy,
capsule policy refs, authority coverage, and capsule alignment evidence into a
replayable no-effect policy consistency receipt.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Personal Assistant skill policy, approval matrix, capsule,
authority coverage receipt, and capsule alignment receipt.
Invariants:
  - Collection never calls connectors, providers, deployment routes, or workers.
  - The receipt is not execution authority and is not terminal closure.
  - P4/P5 actions remain approval-gated or blocked in Foundation Mode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SKILL_POLICY = REPO_ROOT / "governance" / "personal_assistant_skill_policy.yaml"
DEFAULT_APPROVAL_MATRIX = REPO_ROOT / "governance" / "personal_assistant_approval_matrix.yaml"
DEFAULT_CAPSULE = REPO_ROOT / "capsules" / "personal_assistant.json"
DEFAULT_AUTHORITY_COVERAGE = REPO_ROOT / "examples" / "personal_assistant_authority_coverage_receipt.json"
DEFAULT_CAPSULE_ALIGNMENT = REPO_ROOT / "examples" / "personal_assistant_capsule_alignment_receipt.json"
DEFAULT_OUTPUT = REPO_ROOT / "examples" / "personal_assistant_policy_matrix_receipt.json"

REQUIRED_RISK_LEVELS = ("P0", "P1", "P2", "P3", "P4", "P5")
NO_EFFECT_FLAGS = (
    "execution_authority_granted",
    "live_connector_execution_allowed",
    "connector_mutation_allowed",
    "external_effect_allowed",
    "system_of_record_write_allowed",
    "memory_write_allowed",
    "deployment_mutation_allowed",
    "money_legal_public_allowed",
    "production_ready_claim_allowed",
    "customer_ready_claim_allowed",
    "live_nested_mind_activation_allowed",
)
REQUIRED_OVERCLAIM_BLOCKS = (
    "customer_readiness_claim_allowed",
    "enterprise_sla_claim_allowed",
    "production_readiness_claim_allowed",
    "live_nested_mind_activation_allowed",
)
REQUIRED_HARD_INVARIANTS = (
    "receipt_required_for_every_skill",
    "uao_required_for_effect_bearing_action",
    "read_only_skills_may_mutate",
    "draft_only_skills_may_send",
    "p4_p5_may_run_without_approval",
    "secret_values_may_be_serialized",
    "raw_private_connector_payloads_may_be_serialized",
    "public_readiness_claim_allowed",
    "live_nested_mind_activation_allowed",
    "customer_readiness_claim_allowed",
)
REQUIRED_BLOCKED_CONNECTOR_FIELDS = (
    "access_token",
    "refresh_token",
    "private_key",
    "credential_value",
    "raw_mailbox_payload",
    "raw_message_body",
    "raw_calendar_payload",
)
ALLOWED_REDACTED_CONNECTOR_FIELDS = (
    "connector_id",
    "query_hash",
    "response_digest",
    "redacted_summary",
    "evidence_ref",
    "provider_receipt_ref",
)


def collect_personal_assistant_policy_matrix(
    *,
    skill_policy_path: Path = DEFAULT_SKILL_POLICY,
    approval_matrix_path: Path = DEFAULT_APPROVAL_MATRIX,
    capsule_path: Path = DEFAULT_CAPSULE,
    authority_coverage_path: Path = DEFAULT_AUTHORITY_COVERAGE,
    capsule_alignment_path: Path = DEFAULT_CAPSULE_ALIGNMENT,
    now_utc: datetime | None = None,
) -> dict[str, object]:
    """Collect one no-effect Personal Assistant policy matrix receipt."""
    skill_policy = _read_json_object(skill_policy_path, "skill policy")
    approval_matrix = _read_json_object(approval_matrix_path, "approval matrix")
    capsule = _read_json_object(capsule_path, "capsule")
    authority_coverage = _read_json_object(authority_coverage_path, "authority coverage receipt")
    capsule_alignment = _read_json_object(capsule_alignment_path, "capsule alignment receipt")
    generated_at = _format_utc(now_utc or datetime.now(UTC))

    risk_records = _risk_level_records(approval_matrix)
    blocked_action_records = _blocked_action_records(approval_matrix, skill_policy)
    hard_invariant_records = _hard_invariant_records(skill_policy)
    connector_policy = _connector_payload_policy(skill_policy)
    effect_boundary = {flag: False for flag in NO_EFFECT_FLAGS}

    authority_summary = _object(authority_coverage.get("authority_summary"))
    alignment_summary = _object(capsule_alignment.get("alignment_summary"))
    capsule_policy_refs_bound = _capsule_policy_refs_bound(capsule)
    foundation_mode_required = (
        skill_policy.get("foundation_mode_required") is True
        and approval_matrix.get("foundation_mode_required") is True
        and _object(capsule.get("extensions")).get("foundation_mode_required") is True
    )
    p4_p5_require_explicit_approval = all(
        record["approval_rule_consistent"] is True for record in risk_records if record["level"] in {"P4", "P5"}
    )
    p5_execute_blocked = any(record["level"] == "P5" and record["p5_blocked"] is True for record in risk_records)
    blocked_actions_match_policy = bool(blocked_action_records) and all(
        record["in_approval_matrix"] is True and record["in_skill_policy"] is True for record in blocked_action_records
    )
    overclaim_blocks_closed = _overclaim_blocks_closed(approval_matrix)
    hard_invariants_closed = all(record["closed"] is True for record in hard_invariant_records)
    connector_payload_policy_closed = connector_policy["policy_closed"] is True
    no_effect_boundary_verified = not any(effect_boundary.values())
    authority_coverage_closed = authority_summary.get("authority_coverage_closed") is True
    capsule_alignment_closed = alignment_summary.get("capsule_alignment_closed") is True

    policy_matrix_closed = (
        authority_coverage_closed
        and capsule_alignment_closed
        and len(risk_records) == len(REQUIRED_RISK_LEVELS)
        and capsule_policy_refs_bound
        and foundation_mode_required
        and p4_p5_require_explicit_approval
        and p5_execute_blocked
        and blocked_actions_match_policy
        and overclaim_blocks_closed
        and hard_invariants_closed
        and connector_payload_policy_closed
        and no_effect_boundary_verified
    )
    proof_state = "Pass" if policy_matrix_closed else "Fail"
    solver_outcome = "SolvedVerified" if policy_matrix_closed else "AwaitingEvidence"

    receipt_without_id = {
        "schema_version": "personal_assistant.policy_matrix_receipt.v1",
        "generated_at": generated_at,
        "proof_state": proof_state,
        "solver_outcome": solver_outcome,
        "governed": True,
        "receipt_is_not_execution_authority": True,
        "receipt_is_not_terminal_closure": True,
        "source_refs": _source_refs(
            skill_policy_path,
            approval_matrix_path,
            capsule_path,
            authority_coverage_path,
            capsule_alignment_path,
        ),
        "policy_matrix_summary": {
            "policy_matrix_closed": policy_matrix_closed,
            "authority_coverage_closed": authority_coverage_closed,
            "capsule_alignment_closed": capsule_alignment_closed,
            "risk_level_count": len(risk_records),
            "action_classification_count": len(_object(approval_matrix.get("action_classification"))),
            "blocked_action_count": len(blocked_action_records),
            "capsule_policy_refs_bound": capsule_policy_refs_bound,
            "foundation_mode_required": foundation_mode_required,
            "p4_p5_require_explicit_approval": p4_p5_require_explicit_approval,
            "p5_execute_blocked": p5_execute_blocked,
            "blocked_actions_match_policy": blocked_actions_match_policy,
            "overclaim_blocks_closed": overclaim_blocks_closed,
            "hard_invariants_closed": hard_invariants_closed,
            "connector_payload_policy_closed": connector_payload_policy_closed,
            "no_effect_boundary_verified": no_effect_boundary_verified,
            "production_ready": False,
            "customer_ready": False,
            "next_allowed_action": "continue_foundation_hardening_only",
        },
        "risk_level_records": risk_records,
        "blocked_action_records": blocked_action_records,
        "hard_invariant_records": hard_invariant_records,
        "connector_payload_policy": connector_policy,
        "effect_boundary": effect_boundary,
        "lineage": {
            "accepted_deltas": [
                {
                    "delta_id": f"delta-personal-assistant-policy-matrix-{generated_at[:10]}",
                    "reason": _lineage_reason(policy_matrix_closed),
                    "logged_in_lineage": True,
                }
            ],
            "rejected_deltas": [],
        },
    }
    return {"receipt_id": _receipt_id(receipt_without_id), **receipt_without_id}


def write_personal_assistant_policy_matrix(receipt: Mapping[str, object], output_path: Path) -> Path:
    """Write one local Personal Assistant policy matrix receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return output_path


def _source_refs(*paths: Path) -> list[dict[str, object]]:
    kinds = (
        "skill_policy",
        "approval_matrix",
        "capsule",
        "authority_coverage_receipt",
        "capsule_alignment_receipt",
    )
    return [
        {
            "source_id": f"personal_assistant_{kind}",
            "source_ref": _path_label(path),
            "source_kind": kind,
            "bound": path.exists(),
        }
        for kind, path in zip(kinds, paths, strict=True)
    ]


def _risk_level_records(approval_matrix: Mapping[str, Any]) -> list[dict[str, object]]:
    records_by_level = {
        _bounded_text(record.get("level")): record
        for record in _list_of_objects(approval_matrix.get("risk_levels"))
    }
    records: list[dict[str, object]] = []
    for level in REQUIRED_RISK_LEVELS:
        record = records_by_level.get(level, {})
        allowed_modes = _string_list(record.get("allowed_modes"))
        explicit_approval_required = record.get("explicit_approval_required") is True
        effect_bearing = record.get("effect_bearing") is True
        approval_rule_consistent = (
            (level in {"P0", "P1", "P2"} and not explicit_approval_required and not effect_bearing)
            or (level in {"P3", "P4", "P5"} and explicit_approval_required and effect_bearing)
        )
        execute_without_approval_blocked = (
            "execute_with_approval" not in allowed_modes or explicit_approval_required
        )
        p5_blocked = level != "P5" or allowed_modes == ["blocked"]
        records.append(
            {
                "level": level,
                "description": _bounded_text(record.get("description")),
                "private_connector_allowed": record.get("private_connector_allowed") is True,
                "effect_bearing": effect_bearing,
                "explicit_approval_required": explicit_approval_required,
                "allowed_modes": allowed_modes,
                "approval_rule_consistent": approval_rule_consistent,
                "execute_without_approval_blocked": execute_without_approval_blocked,
                "p5_blocked": p5_blocked,
            }
        )
    return records


def _blocked_action_records(
    approval_matrix: Mapping[str, Any],
    skill_policy: Mapping[str, Any],
) -> list[dict[str, object]]:
    matrix_actions = set(_string_list(approval_matrix.get("blocked_without_approval")))
    policy_actions = set(_string_list(skill_policy.get("default_blocked_actions")))
    all_actions = sorted(matrix_actions | policy_actions)
    return [
        {
            "action": action,
            "in_approval_matrix": action in matrix_actions,
            "in_skill_policy": action in policy_actions,
            "blocked_without_approval": action in matrix_actions and action in policy_actions,
        }
        for action in all_actions
    ]


def _hard_invariant_records(skill_policy: Mapping[str, Any]) -> list[dict[str, object]]:
    hard_invariants = _object(skill_policy.get("hard_invariants"))
    records: list[dict[str, object]] = []
    for invariant_id in REQUIRED_HARD_INVARIANTS:
        expected = invariant_id in {
            "receipt_required_for_every_skill",
            "uao_required_for_effect_bearing_action",
        }
        actual = hard_invariants.get(invariant_id) is True
        records.append(
            {
                "invariant_id": invariant_id,
                "expected": expected,
                "actual": actual,
                "closed": actual is expected,
            }
        )
    return records


def _connector_payload_policy(skill_policy: Mapping[str, Any]) -> dict[str, object]:
    payload_policy = _object(skill_policy.get("connector_payload_policy"))
    allowed_fields = _string_list(payload_policy.get("allowed"))
    blocked_fields = _string_list(payload_policy.get("blocked"))
    allowed_fields_are_redacted_evidence_only = set(allowed_fields) == set(ALLOWED_REDACTED_CONNECTOR_FIELDS)
    secret_values_blocked = set(REQUIRED_BLOCKED_CONNECTOR_FIELDS) <= set(blocked_fields)
    raw_private_payloads_blocked = {
        "raw_mailbox_payload",
        "raw_message_body",
        "raw_calendar_payload",
    } <= set(blocked_fields)
    policy_closed = allowed_fields_are_redacted_evidence_only and secret_values_blocked and raw_private_payloads_blocked
    return {
        "allowed_fields": allowed_fields,
        "blocked_fields": blocked_fields,
        "allowed_fields_are_redacted_evidence_only": allowed_fields_are_redacted_evidence_only,
        "secret_values_blocked": secret_values_blocked,
        "raw_private_payloads_blocked": raw_private_payloads_blocked,
        "policy_closed": policy_closed,
    }


def _capsule_policy_refs_bound(capsule: Mapping[str, Any]) -> bool:
    policy_refs = _string_list(capsule.get("policy_refs"))
    required = {
        "governance/personal_assistant_skill_policy.yaml",
        "governance/personal_assistant_approval_matrix.yaml",
    }
    return required <= set(policy_refs) and all(_repo_path(ref).exists() for ref in policy_refs)


def _overclaim_blocks_closed(approval_matrix: Mapping[str, Any]) -> bool:
    overclaim_blocks = _object(approval_matrix.get("overclaim_blocks"))
    return all(overclaim_blocks.get(block) is False for block in REQUIRED_OVERCLAIM_BLOCKS)


def _lineage_reason(policy_matrix_closed: bool) -> str:
    if policy_matrix_closed:
        return "Policy matrix consistency closed for no-effect Foundation Mode hardening without granting execution authority."
    return "Policy matrix consistency remains AwaitingEvidence because at least one policy, matrix, or authority binding is open."


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"failed to read Personal Assistant {label}") from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Personal Assistant {label} was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Personal Assistant {label} must be a JSON object")
    return parsed


def _receipt_id(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"personal-assistant-policy-matrix-{hashlib.sha256(encoded).hexdigest()[:16]}"


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_path(ref: str) -> Path:
    return REPO_ROOT / ref


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _object(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_objects(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _bounded_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def main(argv: list[str] | None = None, *, now_utc: datetime | None = None) -> int:
    """Run the Personal Assistant policy matrix collector."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-policy", type=Path, default=DEFAULT_SKILL_POLICY)
    parser.add_argument("--approval-matrix", type=Path, default=DEFAULT_APPROVAL_MATRIX)
    parser.add_argument("--capsule", type=Path, default=DEFAULT_CAPSULE)
    parser.add_argument("--authority-coverage", type=Path, default=DEFAULT_AUTHORITY_COVERAGE)
    parser.add_argument("--capsule-alignment", type=Path, default=DEFAULT_CAPSULE_ALIGNMENT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print the generated receipt as JSON.")
    args = parser.parse_args(argv)

    receipt = collect_personal_assistant_policy_matrix(
        skill_policy_path=args.skill_policy,
        approval_matrix_path=args.approval_matrix,
        capsule_path=args.capsule,
        authority_coverage_path=args.authority_coverage,
        capsule_alignment_path=args.capsule_alignment,
        now_utc=now_utc,
    )
    write_personal_assistant_policy_matrix(receipt, args.output)
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=False))
    else:
        print(f"policy_matrix_receipt: {_path_label(args.output)}")
        print(f"receipt_id: {receipt['receipt_id']}")
        print(f"solver_outcome: {receipt['solver_outcome']}")
        print(f"policy_matrix_closed: {receipt['policy_matrix_summary']['policy_matrix_closed']}")  # type: ignore[index]
    return 0 if receipt["proof_state"] == "Pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
