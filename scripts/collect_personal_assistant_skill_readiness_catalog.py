#!/usr/bin/env python3
"""Collect a Personal Assistant skill readiness catalog.

Purpose: bind every registered Personal Assistant skill to a foundation
readiness lane, authority coverage record, approval boundary, and source
evidence without granting execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: skill registry, readiness index receipt, authority coverage
receipt, and Personal Assistant capability pack fixtures.
Invariants:
  - Collection never calls connectors, providers, deployment routes, or workers.
  - The catalog is not execution authority and not customer readiness.
  - Every skill remains foundation-only and non-executable in this layer.
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
DEFAULT_READINESS_INDEX = REPO_ROOT / "examples" / "personal_assistant_readiness_index_receipt.json"
DEFAULT_AUTHORITY_COVERAGE = REPO_ROOT / "examples" / "personal_assistant_authority_coverage_receipt.json"
DEFAULT_CAPABILITY_PACK = REPO_ROOT / "capabilities" / "personal_assistant" / "capability_pack.json"
DEFAULT_OUTPUT = REPO_ROOT / "examples" / "personal_assistant_skill_readiness_catalog.json"

NO_EFFECT_FLAGS = (
    "execution_authority_granted",
    "live_connector_execution_allowed",
    "connector_mutation_allowed",
    "external_effect_allowed",
    "system_of_record_write_allowed",
    "memory_write_allowed",
    "deployment_mutation_allowed",
    "money_legal_public_allowed",
    "customer_readiness_claim_allowed",
    "production_readiness_claim_allowed",
    "nested_mind_live_activation_allowed",
    "secret_values_serialized",
    "raw_private_payloads_serialized",
)


def collect_personal_assistant_skill_readiness_catalog(
    *,
    skill_registry_path: Path = DEFAULT_SKILL_REGISTRY,
    readiness_index_path: Path = DEFAULT_READINESS_INDEX,
    authority_coverage_path: Path = DEFAULT_AUTHORITY_COVERAGE,
    capability_pack_path: Path = DEFAULT_CAPABILITY_PACK,
    now_utc: datetime | None = None,
) -> dict[str, object]:
    """Collect one no-effect skill readiness catalog."""
    skill_registry = _read_json_object(skill_registry_path, "skill registry")
    readiness_index = _read_json_object(readiness_index_path, "readiness index receipt")
    authority_coverage = _read_json_object(authority_coverage_path, "authority coverage receipt")
    capability_pack = _read_json_object(capability_pack_path, "capability pack")
    generated_at = _format_utc(now_utc or datetime.now(UTC))

    lane_states = _lane_states(readiness_index)
    authority_records = _authority_records(authority_coverage)
    capability_ids = {
        _bounded_identifier(capability.get("capability_id"))
        for capability in _list_of_objects(capability_pack.get("capabilities"))
    }
    skill_records = _skill_records(skill_registry, lane_states, authority_records, capability_ids)
    effect_boundary = {flag: False for flag in NO_EFFECT_FLAGS}

    readiness_summary = _object(readiness_index.get("summary"))
    authority_summary = _object(authority_coverage.get("authority_summary"))
    catalog_summary = {
        "catalog_closed": False,
        "skill_count": len(skill_records),
        "lane_count": len(lane_states),
        "registered_skill_count": _int(_object(readiness_index.get("readiness_index")).get("registered_skill_count")),
        "readiness_index_closed": readiness_summary.get("readiness_index_closed") is True,
        "authority_coverage_closed": authority_summary.get("authority_coverage_closed") is True,
        "all_skills_lane_bound": all(record["readiness_bound"] is True for record in skill_records),
        "all_skills_lane_solved_verified": all(
            record["readiness_lane_state"] == "SolvedVerified" for record in skill_records
        ),
        "all_skills_authority_covered": all(record["authority_covered"] is True for record in skill_records),
        "all_skills_foundation_only": all(record["foundation_only"] is True for record in skill_records),
        "all_skills_non_executable": all(record["execution_enabled"] is False for record in skill_records),
        "p4_p5_skills_require_approval": all(
            record["requires_approval"] is True for record in skill_records if record["risk_level"] in {"P4", "P5"}
        ),
        "customer_ready": False,
        "production_ready": False,
        "next_allowed_action": "continue_foundation_hardening_only",
    }
    catalog_summary["catalog_closed"] = (
        catalog_summary["skill_count"] == catalog_summary["registered_skill_count"]
        and catalog_summary["readiness_index_closed"] is True
        and catalog_summary["authority_coverage_closed"] is True
        and catalog_summary["all_skills_lane_bound"] is True
        and catalog_summary["all_skills_lane_solved_verified"] is True
        and catalog_summary["all_skills_authority_covered"] is True
        and catalog_summary["all_skills_foundation_only"] is True
        and catalog_summary["all_skills_non_executable"] is True
        and catalog_summary["p4_p5_skills_require_approval"] is True
        and not any(effect_boundary.values())
    )
    proof_state = "Pass" if catalog_summary["catalog_closed"] else "Fail"
    solver_outcome = "SolvedVerified" if catalog_summary["catalog_closed"] else "AwaitingEvidence"

    catalog_without_id = {
        "schema_version": "personal_assistant.skill_readiness_catalog.v1",
        "generated_at": generated_at,
        "proof_state": proof_state,
        "solver_outcome": solver_outcome,
        "governed": True,
        "catalog_is_not_execution_authority": True,
        "catalog_is_not_customer_readiness": True,
        "source_refs": _source_refs(skill_registry_path, readiness_index_path, authority_coverage_path, capability_pack_path),
        "catalog_summary": catalog_summary,
        "skill_records": skill_records,
        "effect_boundary": effect_boundary,
        "lineage": {
            "accepted_deltas": [
                {
                    "delta_id": f"delta-personal-assistant-skill-readiness-catalog-{generated_at[:10]}",
                    "reason": _lineage_reason(catalog_summary["catalog_closed"]),
                    "logged_in_lineage": True,
                }
            ],
            "rejected_deltas": [],
        },
    }
    return {"catalog_id": _catalog_id(catalog_without_id), **catalog_without_id}


def write_personal_assistant_skill_readiness_catalog(catalog: Mapping[str, object], output_path: Path) -> Path:
    """Write one local Personal Assistant skill readiness catalog."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(catalog, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return output_path


def _source_refs(*paths: Path) -> list[dict[str, object]]:
    kinds = ("skill_registry", "readiness_index", "authority_coverage", "capability_pack")
    return [
        {
            "source_id": f"personal_assistant_{kind}",
            "source_ref": _path_label(path),
            "source_kind": kind,
            "bound": path.exists(),
        }
        for kind, path in zip(kinds, paths, strict=True)
    ]


def _lane_states(readiness_index: Mapping[str, Any]) -> dict[str, str]:
    return {
        _bounded_identifier(record.get("lane_id")): _bounded_outcome(record.get("state"))
        for record in _list_of_objects(readiness_index.get("lane_records"))
    }


def _authority_records(authority_coverage: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        _bounded_identifier(record.get("skill_id")): record
        for record in _list_of_objects(authority_coverage.get("skill_authority_records"))
    }


def _skill_records(
    skill_registry: Mapping[str, Any],
    lane_states: Mapping[str, str],
    authority_records: Mapping[str, Mapping[str, Any]],
    capability_ids: set[str],
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for skill in _list_of_objects(skill_registry.get("skills")):
        skill_id = _bounded_identifier(skill.get("skill_id"))
        group = _bounded_identifier(skill.get("group"))
        mode = _bounded_identifier(skill.get("mode"))
        risk_level = _bounded_identifier(skill.get("risk_level"))
        lane_id = _readiness_lane_id(group, mode, skill_id)
        authority = _object(authority_records.get(skill_id))
        capability_refs = _string_list(skill.get("capability_refs"))
        capability_refs_bound = all(
            ref in capability_ids or ref.startswith(("email.", "calendar.", "document.", "software_dev.", "task."))
            for ref in capability_refs
        )
        requires_approval = skill.get("requires_approval") is True
        execution_enabled = _object(skill.get("metadata")).get("execution_enabled") is True
        p4_p5_approval_guarded = risk_level not in {"P4", "P5"} or requires_approval
        records.append(
            {
                "skill_id": skill_id,
                "group": group,
                "mode": mode,
                "risk_level": risk_level,
                "readiness_lane_id": lane_id,
                "readiness_lane_state": lane_states.get(lane_id, "AwaitingEvidence"),
                "approval_policy_ref": _bounded_identifier(skill.get("approval_policy_ref")),
                "requires_approval": requires_approval,
                "p4_p5_approval_guarded": p4_p5_approval_guarded,
                "foundation_only": _object(skill.get("metadata")).get("foundation_only") is True,
                "execution_enabled": execution_enabled,
                "authority_covered": authority.get("authority_covered") is True,
                "receipt_required": skill.get("receipt_required") is True,
                "uao_required": skill.get("uao_required") is True,
                "capability_refs": capability_refs,
                "connector_count": len(_string_list(skill.get("connectors"))),
                "blocked_action_count": len(_string_list(skill.get("blocked_actions"))),
                "readiness_bound": lane_id in lane_states and bool(capability_refs) and capability_refs_bound,
            }
        )
    return records


def _readiness_lane_id(group: str, mode: str, skill_id: str) -> str:
    if skill_id == "personal_assistant.clarification.request":
        return "request_intake_whqr"
    if group == "memory":
        return "memory_observation"
    if group == "teamops":
        return "teamops_shared_inbox"
    if group == "github_codex":
        return "github_codex_review"
    if group == "research":
        return "research_source_compare"
    if group == "math":
        return "math_reasoning"
    if group == "planning":
        return "schedule_planning"
    if mode in {"approval_required", "blocked"}:
        return "approval_queue"
    if mode == "draft_only":
        return "draft_projection"
    if mode == "read_only":
        return "read_only_projection"
    return "skill_registry"


def _lineage_reason(catalog_closed: bool) -> str:
    if catalog_closed:
        return "Bound every Personal Assistant skill to a no-effect readiness lane without granting execution authority."
    return "Skill readiness catalog remains AwaitingEvidence because at least one skill lacks lane or authority binding."


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"failed to read Personal Assistant {label}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Personal Assistant {label} must be a JSON object")
    return parsed


def _catalog_id(catalog_without_id: Mapping[str, object]) -> str:
    encoded = json.dumps(catalog_without_id, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"personal-assistant-skill-readiness-catalog-{hashlib.sha256(encoded).hexdigest()[:16]}"


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
    return [item for item in value if isinstance(item, str)]


def _bounded_identifier(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _bounded_outcome(value: object) -> str:
    if value == "SolvedVerified":
        return "SolvedVerified"
    return "AwaitingEvidence"


def _int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def main(argv: list[str] | None = None, *, now_utc: datetime | None = None) -> int:
    """Run the Personal Assistant skill readiness catalog collector."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-registry", type=Path, default=DEFAULT_SKILL_REGISTRY)
    parser.add_argument("--readiness-index", type=Path, default=DEFAULT_READINESS_INDEX)
    parser.add_argument("--authority-coverage", type=Path, default=DEFAULT_AUTHORITY_COVERAGE)
    parser.add_argument("--capability-pack", type=Path, default=DEFAULT_CAPABILITY_PACK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print the generated catalog as JSON.")
    args = parser.parse_args(argv)

    catalog = collect_personal_assistant_skill_readiness_catalog(
        skill_registry_path=args.skill_registry,
        readiness_index_path=args.readiness_index,
        authority_coverage_path=args.authority_coverage,
        capability_pack_path=args.capability_pack,
        now_utc=now_utc,
    )
    write_personal_assistant_skill_readiness_catalog(catalog, args.output)
    if args.json:
        print(json.dumps(catalog, indent=2, sort_keys=False))
    else:
        print(f"skill_readiness_catalog: {_path_label(args.output)}")
        print(f"catalog_id: {catalog['catalog_id']}")
        print(f"solver_outcome: {catalog['solver_outcome']}")
        print(f"catalog_closed: {catalog['catalog_summary']['catalog_closed']}")  # type: ignore[index]
    return 0 if catalog["proof_state"] == "Pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
