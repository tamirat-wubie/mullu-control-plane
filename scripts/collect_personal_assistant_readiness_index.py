#!/usr/bin/env python3
"""Collect a personal-assistant readiness index receipt.

Purpose: summarize checked-in personal-assistant foundation evidence into one
no-effect readiness index for future lane selection.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: foundation evidence receipt, console read model, skill registry,
and personal-assistant capability pack fixtures.
Invariants:
  - Collection never calls connectors, providers, deployment routes, or workers.
  - The readiness index is not execution authority and is not terminal closure.
  - Production, customer-readiness, and live Nested Mind claims remain blocked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FOUNDATION_EVIDENCE = REPO_ROOT / "examples" / "personal_assistant_foundation_evidence_receipt.json"
DEFAULT_CONSOLE_READ_MODEL = REPO_ROOT / "examples" / "personal_assistant_console_read_model.json"
DEFAULT_SKILL_REGISTRY = REPO_ROOT / "examples" / "personal_assistant_skill_registry.json"
DEFAULT_CAPABILITY_PACK = REPO_ROOT / "capabilities" / "personal_assistant" / "capability_pack.json"
DEFAULT_OUTPUT = REPO_ROOT / "examples" / "personal_assistant_readiness_index_receipt.json"

NO_EFFECT_FLAGS = (
    "execution_allowed",
    "live_connector_execution_allowed",
    "connector_mutation_allowed",
    "external_effect_allowed",
    "customer_readiness_claim_allowed",
    "nested_mind_live_activation_allowed",
)


def collect_personal_assistant_readiness_index(
    *,
    foundation_evidence_path: Path = DEFAULT_FOUNDATION_EVIDENCE,
    console_read_model_path: Path = DEFAULT_CONSOLE_READ_MODEL,
    skill_registry_path: Path = DEFAULT_SKILL_REGISTRY,
    capability_pack_path: Path = DEFAULT_CAPABILITY_PACK,
    now_utc: datetime | None = None,
) -> dict[str, object]:
    """Collect one no-effect personal-assistant readiness index receipt."""
    foundation_evidence = _read_json_object(foundation_evidence_path, "foundation evidence receipt")
    console = _read_json_object(console_read_model_path, "console read model")
    skill_registry = _read_json_object(skill_registry_path, "skill registry")
    capability_pack = _read_json_object(capability_pack_path, "capability pack")
    generated_at = _format_utc(now_utc or datetime.now(UTC))

    lane_records = _lane_records(console)
    readiness_index = _readiness_index(console, skill_registry, capability_pack, lane_records)
    effect_boundary = _effect_boundary(foundation_evidence, console, capability_pack)
    authority_blocks = {
        "live_execution_blocked": effect_boundary["execution_allowed"] is False
        and effect_boundary["live_connector_execution_allowed"] is False,
        "connector_mutation_blocked": effect_boundary["connector_mutation_allowed"] is False,
        "external_communication_blocked": effect_boundary["external_effect_allowed"] is False,
        "deployment_mutation_blocked": _object(console.get("effect_boundary")).get("deployment_mutation_allowed")
        is False,
        "customer_readiness_claim_blocked": effect_boundary["customer_readiness_claim_allowed"] is False,
        "nested_mind_live_activation_blocked": effect_boundary["nested_mind_live_activation_allowed"] is False,
        "secret_serialization_blocked": effect_boundary["secret_values_serialized"] is False,
        "raw_private_payload_serialization_blocked": effect_boundary["raw_private_payloads_serialized"] is False,
    }
    foundation_closed = _foundation_evidence_closed(foundation_evidence)
    all_lanes_solved = readiness_index["lane_count"] == readiness_index["solved_verified_lane_count"]
    all_lane_boundaries_closed = all(record["no_effect_boundary_verified"] is True for record in lane_records)
    no_effect_closed = not any(effect_boundary.values()) and all(authority_blocks.values()) and all_lane_boundaries_closed
    readiness_index_closed = foundation_closed and all_lanes_solved and no_effect_closed
    proof_state = "Pass" if readiness_index_closed else "Fail"
    solver_outcome = "SolvedVerified" if readiness_index_closed else "AwaitingEvidence"

    receipt_without_id = {
        "schema_version": "personal_assistant.readiness_index_receipt.v1",
        "generated_at": generated_at,
        "proof_state": proof_state,
        "solver_outcome": solver_outcome,
        "governed": True,
        "receipt_is_not_execution_authority": True,
        "receipt_is_not_terminal_closure": True,
        "source_evidence": [
            {
                "source_id": "personal_assistant_foundation_evidence",
                "source_ref": _path_label(foundation_evidence_path),
                "receipt_id": _bounded_identifier(foundation_evidence.get("receipt_id")),
                "proof_state": _bounded_outcome(foundation_evidence.get("proof_state"), allowed={"Pass", "Fail"}),
                "solver_outcome": _bounded_outcome(
                    foundation_evidence.get("solver_outcome"),
                    allowed={"SolvedVerified", "AwaitingEvidence"},
                ),
                "closed": foundation_closed,
                "no_effect_boundary_verified": _object(foundation_evidence.get("summary")).get(
                    "no_effect_boundary_verified"
                )
                is True,
            }
        ],
        "readiness_index": readiness_index,
        "lane_records": lane_records,
        "effect_boundary": effect_boundary,
        "authority_blocks": authority_blocks,
        "summary": {
            "readiness_index_closed": readiness_index_closed,
            "foundation_evidence_closed": foundation_closed,
            "all_lanes_solved_verified": all_lanes_solved,
            "no_effect_boundary_verified": no_effect_closed,
            "production_ready": False,
            "customer_ready": False,
            "next_allowed_action": "continue_foundation_hardening_only",
        },
        "lineage": {
            "accepted_deltas": [
                {
                    "delta_id": f"delta-personal-assistant-readiness-index-{generated_at[:10]}",
                    "reason": _lineage_reason(readiness_index_closed),
                    "logged_in_lineage": True,
                }
            ],
            "rejected_deltas": [],
        },
    }
    return {
        "receipt_id": _receipt_id(receipt_without_id),
        **receipt_without_id,
    }


def write_personal_assistant_readiness_index(
    receipt: Mapping[str, object],
    output_path: Path,
) -> Path:
    """Write one personal-assistant readiness index receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return output_path


def _lane_records(console: Mapping[str, Any]) -> list[dict[str, object]]:
    lanes = _list_of_objects(_object(console.get("lane_status")).get("lanes"))
    records: list[dict[str, object]] = []
    for lane in lanes:
        records.append(
            {
                "lane_id": _bounded_identifier(lane.get("lane_id")),
                "stage": _bounded_identifier(lane.get("stage")),
                "state": _bounded_outcome(lane.get("state"), allowed={"SolvedVerified", "AwaitingEvidence"}),
                "route_count": len(_list(lane.get("route_refs"))),
                "schema_count": len(_list(lane.get("schema_refs"))),
                "validator_count": len(_list(lane.get("validator_refs"))),
                "receipt_required": lane.get("receipt_required") is True,
                "foundation_only": lane.get("foundation_only") is True,
                "no_effect_boundary_verified": _lane_no_effect_boundary_verified(lane),
            }
        )
    return records


def _readiness_index(
    console: Mapping[str, Any],
    skill_registry: Mapping[str, Any],
    capability_pack: Mapping[str, Any],
    lane_records: list[dict[str, object]],
) -> dict[str, int]:
    skills = _list_of_objects(skill_registry.get("skills"))
    capabilities = _list_of_objects(capability_pack.get("capabilities"))
    return {
        "lane_count": _int(_object(console.get("lane_status")).get("lane_count")),
        "solved_verified_lane_count": sum(1 for lane in lane_records if lane["state"] == "SolvedVerified"),
        "awaiting_evidence_lane_count": sum(1 for lane in lane_records if lane["state"] == "AwaitingEvidence"),
        "blocked_action_count": len(_list(console.get("blocked_actions"))),
        "registered_skill_count": len(skills),
        "foundation_only_skill_count": sum(1 for skill in skills if _object(skill.get("metadata")).get("foundation_only") is True),
        "capability_count": len(capabilities),
        "candidate_capability_count": sum(
            1 for capability in capabilities if capability.get("certification_status") == "candidate"
        ),
        "production_ready_capability_count": sum(
            1 for capability in capabilities if _object(capability.get("metadata")).get("production_ready") is True
        ),
    }


def _effect_boundary(
    foundation_evidence: Mapping[str, Any],
    console: Mapping[str, Any],
    capability_pack: Mapping[str, Any],
) -> dict[str, bool]:
    foundation_boundary = _object(foundation_evidence.get("effect_boundary"))
    console_boundary = _object(console.get("effect_boundary"))
    console_lane = _object(console.get("lane_status"))
    private_payload_policy = _object(console.get("private_payload_policy"))
    capabilities = _list_of_objects(capability_pack.get("capabilities"))
    return {
        "execution_allowed": _any_true(foundation_boundary.get("execution_allowed"), console_lane.get("execution_allowed")),
        "live_connector_execution_allowed": _any_true(
            foundation_boundary.get("live_connector_execution_allowed"),
            console_boundary.get("live_connector_execution_allowed"),
            console_lane.get("live_connector_execution_allowed"),
        ),
        "connector_mutation_allowed": _any_true(
            foundation_boundary.get("connector_mutation_allowed"),
            console_lane.get("connector_mutation_allowed"),
        ),
        "external_effect_allowed": _any_true(
            foundation_boundary.get("external_effect_allowed"),
            console_lane.get("external_effect_allowed"),
            console_boundary.get("external_send_allowed"),
        ),
        "customer_readiness_claim_allowed": _any_true(
            foundation_boundary.get("customer_readiness_claim_allowed"),
            console_lane.get("customer_readiness_claim_allowed"),
            console_boundary.get("public_readiness_claim_allowed"),
        ),
        "nested_mind_live_activation_allowed": _any_true(
            foundation_boundary.get("nested_mind_live_activation_allowed"),
            console_lane.get("nested_mind_live_activation_allowed"),
            console_boundary.get("nested_mind_live_activation_allowed"),
        ),
        "production_ready_claim_allowed": any(
            _object(capability.get("metadata")).get("production_ready") is True for capability in capabilities
        ),
        "secret_values_serialized": _any_true(
            foundation_boundary.get("secret_values_serialized"),
            private_payload_policy.get("secret_values_serialized"),
        ),
        "raw_private_payloads_serialized": _any_true(
            foundation_boundary.get("raw_private_payloads_serialized"),
            private_payload_policy.get("raw_private_payload_serialized"),
        ),
    }


def _foundation_evidence_closed(foundation_evidence: Mapping[str, Any]) -> bool:
    summary = _object(foundation_evidence.get("summary"))
    return (
        foundation_evidence.get("proof_state") == "Pass"
        and foundation_evidence.get("solver_outcome") == "SolvedVerified"
        and summary.get("foundation_evidence_closed") is True
        and summary.get("no_effect_boundary_verified") is True
    )


def _lane_no_effect_boundary_verified(lane: Mapping[str, Any]) -> bool:
    return (
        lane.get("foundation_only") is True
        and lane.get("receipt_required") is True
        and all(lane.get(flag) is False for flag in NO_EFFECT_FLAGS)
    )


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"failed to read {label}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{label} must be a JSON object")
    return parsed


def _object(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _list_of_objects(value: Any) -> tuple[dict[str, Any], ...]:
    return tuple(item for item in _list(value) if isinstance(item, dict))


def _any_true(*values: object) -> bool:
    return any(value is True for value in values)


def _int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _bounded_identifier(value: object) -> str:
    return value if isinstance(value, str) and value else "missing"


def _bounded_outcome(value: object, *, allowed: set[str]) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    if "Fail" in allowed:
        return "Fail"
    return "AwaitingEvidence"


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _receipt_id(receipt_without_id: Mapping[str, object]) -> str:
    material = json.dumps(receipt_without_id, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"personal-assistant-readiness-index-{hashlib.sha256(material).hexdigest()[:16]}"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _lineage_reason(readiness_index_closed: bool) -> str:
    if readiness_index_closed:
        return "Recorded Personal Assistant readiness index while preserving no-effect authority."
    return "Recorded Personal Assistant readiness index and preserved AwaitingEvidence."


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse personal-assistant readiness index collection arguments."""
    parser = argparse.ArgumentParser(description="Collect personal-assistant readiness index evidence.")
    parser.add_argument("--foundation-evidence", default=str(DEFAULT_FOUNDATION_EVIDENCE))
    parser.add_argument("--console-read-model", default=str(DEFAULT_CONSOLE_READ_MODEL))
    parser.add_argument("--skill-registry", default=str(DEFAULT_SKILL_REGISTRY))
    parser.add_argument("--capability-pack", default=str(DEFAULT_CAPABILITY_PACK))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, now_utc: datetime | None = None) -> int:
    """CLI entry point for personal-assistant readiness index collection."""
    args = parse_args(argv)
    receipt = collect_personal_assistant_readiness_index(
        foundation_evidence_path=Path(args.foundation_evidence),
        console_read_model_path=Path(args.console_read_model),
        skill_registry_path=Path(args.skill_registry),
        capability_pack_path=Path(args.capability_pack),
        now_utc=now_utc,
    )
    write_personal_assistant_readiness_index(receipt, Path(args.output))
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=False))
    else:
        print(f"personal-assistant readiness index outcome: {receipt['solver_outcome']}")
    return 0 if receipt["solver_outcome"] == "SolvedVerified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
