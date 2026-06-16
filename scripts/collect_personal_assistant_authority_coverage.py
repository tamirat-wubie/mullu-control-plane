#!/usr/bin/env python3
"""Collect a Personal Assistant authority coverage receipt.

Purpose: project checked-in Personal Assistant skill, policy, approval, and
capability artifacts into a replayable no-effect authority coverage receipt.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: skill registry, approval matrix, skill policy, capability pack,
and coherence ledger fixtures.
Invariants:
  - Collection never calls connectors, providers, deployment routes, or workers.
  - The receipt is not execution authority and is not terminal closure.
  - Foundation Mode keeps production, customer, and live Nested Mind claims blocked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SKILL_REGISTRY = REPO_ROOT / "examples" / "personal_assistant_skill_registry.json"
DEFAULT_APPROVAL_MATRIX = REPO_ROOT / "governance" / "personal_assistant_approval_matrix.yaml"
DEFAULT_SKILL_POLICY = REPO_ROOT / "governance" / "personal_assistant_skill_policy.yaml"
DEFAULT_CAPABILITY_PACK = REPO_ROOT / "capabilities" / "personal_assistant" / "capability_pack.json"
DEFAULT_COHERENCE_LEDGER = REPO_ROOT / "examples" / "personal_assistant_coherence_ledger_receipt.json"
DEFAULT_OUTPUT = REPO_ROOT / "examples" / "personal_assistant_authority_coverage_receipt.json"

REQUIRED_RISK_LEVELS = ("P0", "P1", "P2", "P3", "P4", "P5")
EFFECT_BEARING_SKILL_FLAGS = (
    "internal_write_allowed",
    "external_write_allowed",
    "system_of_record_write_allowed",
    "connector_mutation_allowed",
    "money_legal_public_allowed",
)
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


def collect_personal_assistant_authority_coverage(
    *,
    skill_registry_path: Path = DEFAULT_SKILL_REGISTRY,
    approval_matrix_path: Path = DEFAULT_APPROVAL_MATRIX,
    skill_policy_path: Path = DEFAULT_SKILL_POLICY,
    capability_pack_path: Path = DEFAULT_CAPABILITY_PACK,
    coherence_ledger_path: Path = DEFAULT_COHERENCE_LEDGER,
    now_utc: datetime | None = None,
) -> dict[str, object]:
    """Collect one no-effect Personal Assistant authority coverage receipt."""
    skill_registry = _read_json_object(skill_registry_path, "skill registry")
    approval_matrix = _read_json_object(approval_matrix_path, "approval matrix")
    skill_policy = _read_json_object(skill_policy_path, "skill policy")
    capability_pack = _read_json_object(capability_pack_path, "capability pack")
    coherence_ledger = _read_json_object(coherence_ledger_path, "coherence ledger")
    generated_at = _format_utc(now_utc or datetime.now(UTC))

    matrix_records = _matrix_records(approval_matrix)
    policy_levels = set(_string_list(skill_policy.get("risk_levels")))
    skills = _list_of_objects(skill_registry.get("skills"))
    capabilities = _list_of_objects(capability_pack.get("capabilities"))
    risk_level_records = _risk_level_records(matrix_records, policy_levels, skills)
    skill_records = _skill_authority_records(skills, matrix_records, skill_policy)
    capability_records = _capability_authority_records(capabilities)
    effect_boundary = {flag: False for flag in NO_EFFECT_FLAGS}

    approval_matrix_levels_bound = set(matrix_records) == set(REQUIRED_RISK_LEVELS)
    skill_policy_levels_bound = policy_levels == set(REQUIRED_RISK_LEVELS)
    all_skills_have_policy_ref = all(record["approval_policy_ref"].endswith(record["risk_level"]) for record in skill_records)
    all_skills_have_known_risk_level = all(record["risk_level"] in REQUIRED_RISK_LEVELS for record in skill_records)
    all_effect_bearing_skills_require_approval = all(
        (not _skill_effect_bearing(record)) or record["requires_approval"] is True for record in skill_records
    )
    p4_p5_actions_require_explicit_approval = all(
        record["requires_approval"] is True for record in skill_records if record["risk_level"] in {"P4", "P5"}
    )
    foundation_execution_disabled = all(record["execution_enabled"] is False for record in skill_records)
    all_capabilities_fixture_only = all(record["fixture_only"] is True for record in capability_records)
    all_capabilities_candidate_only = all(record["certification_status"] == "candidate" for record in capability_records)
    all_capabilities_secretless = all(record["secret_scope"] == "none" for record in capability_records)
    coherence_ledger_closed = _object(coherence_ledger.get("coherence_summary")).get("coherence_ledger_closed") is True
    no_effect_boundary_verified = not any(effect_boundary.values())

    authority_coverage_closed = (
        coherence_ledger_closed
        and approval_matrix_levels_bound
        and skill_policy_levels_bound
        and all_skills_have_policy_ref
        and all_skills_have_known_risk_level
        and all_effect_bearing_skills_require_approval
        and p4_p5_actions_require_explicit_approval
        and foundation_execution_disabled
        and all(record["authority_covered"] is True for record in skill_records)
        and all(record["authority_covered"] is True for record in capability_records)
        and all_capabilities_fixture_only
        and all_capabilities_candidate_only
        and all_capabilities_secretless
        and no_effect_boundary_verified
    )
    proof_state = "Pass" if authority_coverage_closed else "Fail"
    solver_outcome = "SolvedVerified" if authority_coverage_closed else "AwaitingEvidence"

    receipt_without_id = {
        "schema_version": "personal_assistant.authority_coverage_receipt.v1",
        "generated_at": generated_at,
        "proof_state": proof_state,
        "solver_outcome": solver_outcome,
        "governed": True,
        "receipt_is_not_execution_authority": True,
        "receipt_is_not_terminal_closure": True,
        "source_refs": _source_refs(
            skill_registry_path,
            approval_matrix_path,
            skill_policy_path,
            capability_pack_path,
            coherence_ledger_path,
        ),
        "authority_summary": {
            "authority_coverage_closed": authority_coverage_closed,
            "coherence_ledger_closed": coherence_ledger_closed,
            "skill_count": len(skill_records),
            "capability_count": len(capability_records),
            "risk_level_count": len(REQUIRED_RISK_LEVELS),
            "approval_matrix_levels_bound": approval_matrix_levels_bound,
            "skill_policy_levels_bound": skill_policy_levels_bound,
            "all_skills_have_policy_ref": all_skills_have_policy_ref,
            "all_skills_have_known_risk_level": all_skills_have_known_risk_level,
            "all_effect_bearing_skills_require_approval": all_effect_bearing_skills_require_approval,
            "p4_p5_actions_require_explicit_approval": p4_p5_actions_require_explicit_approval,
            "foundation_execution_disabled": foundation_execution_disabled,
            "all_capabilities_fixture_only": all_capabilities_fixture_only,
            "all_capabilities_candidate_only": all_capabilities_candidate_only,
            "all_capabilities_secretless": all_capabilities_secretless,
            "no_effect_boundary_verified": no_effect_boundary_verified,
            "production_ready": False,
            "customer_ready": False,
            "next_allowed_action": "continue_foundation_hardening_only",
        },
        "risk_level_records": risk_level_records,
        "skill_authority_records": skill_records,
        "capability_authority_records": capability_records,
        "effect_boundary": effect_boundary,
        "lineage": {
            "accepted_deltas": [
                {
                    "delta_id": f"delta-personal-assistant-authority-coverage-{generated_at[:10]}",
                    "reason": _lineage_reason(authority_coverage_closed),
                    "logged_in_lineage": True,
                }
            ],
            "rejected_deltas": [],
        },
    }
    return {"receipt_id": _receipt_id(receipt_without_id), **receipt_without_id}


def write_personal_assistant_authority_coverage(receipt: Mapping[str, object], output_path: Path) -> Path:
    """Write one local Personal Assistant authority coverage receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return output_path


def _source_refs(*paths: Path) -> list[dict[str, object]]:
    kinds = ("skill_registry", "approval_matrix", "skill_policy", "capability_pack", "coherence_ledger")
    return [
        {
            "source_id": f"personal_assistant_{kind}",
            "source_ref": _path_label(path),
            "source_kind": kind,
            "bound": path.exists(),
        }
        for kind, path in zip(kinds, paths, strict=True)
    ]


def _matrix_records(approval_matrix: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _bounded_identifier(record.get("level")): record
        for record in _list_of_objects(approval_matrix.get("risk_levels"))
    }


def _risk_level_records(
    matrix_records: Mapping[str, Mapping[str, Any]],
    policy_levels: set[str],
    skills: list[Mapping[str, Any]],
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for level in REQUIRED_RISK_LEVELS:
        matrix = _object(matrix_records.get(level))
        records.append(
            {
                "level": level,
                "approval_policy_ref": f"governance/personal_assistant_approval_matrix.yaml#{level}",
                "effect_bearing": matrix.get("effect_bearing") is True,
                "explicit_approval_required": matrix.get("explicit_approval_required") is True,
                "allowed_modes": _string_list(matrix.get("allowed_modes")),
                "skill_count": sum(1 for skill in skills if skill.get("risk_level") == level),
                "matrix_bound": level in matrix_records,
                "policy_bound": level in policy_levels,
            }
        )
    return records


def _skill_authority_records(
    skills: list[Mapping[str, Any]],
    matrix_records: Mapping[str, Mapping[str, Any]],
    skill_policy: Mapping[str, Any],
) -> list[dict[str, object]]:
    skill_modes = _object(skill_policy.get("skill_modes"))
    records: list[dict[str, object]] = []
    for skill in skills:
        risk_level = _bounded_identifier(skill.get("risk_level"))
        mode = _bounded_identifier(skill.get("mode"))
        metadata = _object(skill.get("metadata"))
        effect_boundary = _skill_effect_boundary(skill.get("effect_boundary"))
        execution_enabled = metadata.get("execution_enabled") is True
        requires_approval = skill.get("requires_approval") is True
        matrix = _object(matrix_records.get(risk_level))
        effect_bearing = any(effect_boundary.get(flag) is True for flag in EFFECT_BEARING_SKILL_FLAGS)
        authority_covered = (
            risk_level in REQUIRED_RISK_LEVELS
            and mode in skill_modes
            and str(skill.get("approval_policy_ref")) == f"governance/personal_assistant_approval_matrix.yaml#{risk_level}"
            and skill.get("receipt_required") is True
            and skill.get("uao_required") is True
            and skill.get("memory_write_allowed") is False
            and skill.get("nested_mind_live_activation_allowed") is False
            and skill.get("public_readiness_claim_allowed") is False
            and metadata.get("foundation_only") is True
            and execution_enabled is False
            and (not effect_bearing or requires_approval)
            and (risk_level not in {"P4", "P5"} or requires_approval)
            and (risk_level not in matrix_records or matrix.get("explicit_approval_required") is requires_approval or not effect_bearing)
        )
        records.append(
            {
                "skill_id": _bounded_identifier(skill.get("skill_id")),
                "mode": mode,
                "risk_level": risk_level,
                "approval_policy_ref": _bounded_text(skill.get("approval_policy_ref")),
                "requires_approval": requires_approval,
                "private_connector_required": skill.get("private_connector_required") is True,
                "uao_required": skill.get("uao_required") is True,
                "receipt_required": skill.get("receipt_required") is True,
                "memory_write_allowed": skill.get("memory_write_allowed") is True,
                "allowed_actions": _string_list(skill.get("allowed_actions")),
                "blocked_actions": _string_list(skill.get("blocked_actions")),
                "effect_boundary": effect_boundary,
                "foundation_only": metadata.get("foundation_only") is True,
                "execution_enabled": execution_enabled,
                "authority_covered": authority_covered,
                "no_effect_boundary_verified": execution_enabled is False,
            }
        )
    return records


def _capability_authority_records(capabilities: list[Mapping[str, Any]]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for capability in capabilities:
        metadata = _object(capability.get("metadata"))
        isolation_profile = _object(capability.get("isolation_profile"))
        governed_record = _object(_object(capability.get("extensions")).get("governed_record"))
        forbidden_effects = _string_list(governed_record.get("forbidden_effects"))
        network_allowlist = _string_list(isolation_profile.get("network_allowlist"))
        certification_status = _bounded_identifier(capability.get("certification_status"))
        fixture_only = metadata.get("fixture_only") is True
        production_ready = metadata.get("production_ready") is True
        secret_scope = _bounded_identifier(isolation_profile.get("secret_scope"))
        world_mutating = governed_record.get("world_mutating") is True
        receipt_required = governed_record.get("receipt_required") is True
        requires_approval = governed_record.get("requires_approval") is True
        authority_covered = (
            certification_status == "candidate"
            and fixture_only
            and not production_ready
            and secret_scope == "none"
            and not network_allowlist
            and not world_mutating
            and receipt_required
            and bool(forbidden_effects)
        )
        records.append(
            {
                "capability_id": _bounded_identifier(capability.get("capability_id")),
                "risk_tier": _bounded_identifier(metadata.get("risk_tier")),
                "certification_status": certification_status,
                "fixture_only": fixture_only,
                "production_ready": production_ready,
                "secret_scope": secret_scope,
                "network_allowlist_empty": not network_allowlist,
                "world_mutating": world_mutating,
                "requires_approval": requires_approval,
                "receipt_required": receipt_required,
                "forbidden_effect_count": len(forbidden_effects),
                "authority_covered": authority_covered,
            }
        )
    return records


def _skill_effect_bearing(record: Mapping[str, Any]) -> bool:
    boundary = _object(record.get("effect_boundary"))
    return any(boundary.get(flag) is True for flag in EFFECT_BEARING_SKILL_FLAGS)


def _skill_effect_boundary(value: object) -> dict[str, bool]:
    boundary = _object(value)
    return {
        "read_only": boundary.get("read_only") is True,
        "draft_only": boundary.get("draft_only") is True,
        "internal_write_allowed": boundary.get("internal_write_allowed") is True,
        "external_write_allowed": boundary.get("external_write_allowed") is True,
        "system_of_record_write_allowed": boundary.get("system_of_record_write_allowed") is True,
        "connector_mutation_allowed": boundary.get("connector_mutation_allowed") is True,
        "money_legal_public_allowed": boundary.get("money_legal_public_allowed") is True,
    }


def _lineage_reason(coverage_closed: bool) -> str:
    if coverage_closed:
        return "Authority coverage closed for no-effect Foundation Mode hardening without granting execution authority."
    return "Authority coverage remains AwaitingEvidence because at least one policy, skill, or capability binding is open."


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
    return f"personal-assistant-authority-coverage-{hashlib.sha256(encoded).hexdigest()[:16]}"


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    return [str(item) for item in value if isinstance(item, str)]


def _bounded_identifier(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _bounded_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def main(argv: list[str] | None = None, *, now_utc: datetime | None = None) -> int:
    """Run the Personal Assistant authority coverage collector."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-registry", type=Path, default=DEFAULT_SKILL_REGISTRY)
    parser.add_argument("--approval-matrix", type=Path, default=DEFAULT_APPROVAL_MATRIX)
    parser.add_argument("--skill-policy", type=Path, default=DEFAULT_SKILL_POLICY)
    parser.add_argument("--capability-pack", type=Path, default=DEFAULT_CAPABILITY_PACK)
    parser.add_argument("--coherence-ledger", type=Path, default=DEFAULT_COHERENCE_LEDGER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print the generated receipt as JSON.")
    args = parser.parse_args(argv)

    receipt = collect_personal_assistant_authority_coverage(
        skill_registry_path=args.skill_registry,
        approval_matrix_path=args.approval_matrix,
        skill_policy_path=args.skill_policy,
        capability_pack_path=args.capability_pack,
        coherence_ledger_path=args.coherence_ledger,
        now_utc=now_utc,
    )
    write_personal_assistant_authority_coverage(receipt, args.output)
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=False))
    else:
        print(f"authority_coverage_receipt: {_path_label(args.output)}")
        print(f"receipt_id: {receipt['receipt_id']}")
        print(f"solver_outcome: {receipt['solver_outcome']}")
        print(f"authority_coverage_closed: {receipt['authority_summary']['authority_coverage_closed']}")  # type: ignore[index]
    return 0 if receipt["proof_state"] == "Pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
