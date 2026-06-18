#!/usr/bin/env python3
"""Collect a personal-assistant coherence ledger receipt.

Purpose: project checked-in Personal Assistant foundation evidence into a
replayable no-effect ledger of lane dependencies, authority blocks, and next
allowed work.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: readiness index receipt, console read model, skill registry, and
capability pack fixtures.
Invariants:
  - Collection never calls connectors, providers, deployment routes, or workers.
  - The coherence ledger is not execution authority and is not terminal closure.
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
DEFAULT_READINESS_INDEX = REPO_ROOT / "examples" / "personal_assistant_readiness_index_receipt.json"
DEFAULT_CONSOLE_READ_MODEL = REPO_ROOT / "examples" / "personal_assistant_console_read_model.json"
DEFAULT_SKILL_REGISTRY = REPO_ROOT / "examples" / "personal_assistant_skill_registry.json"
DEFAULT_CAPABILITY_PACK = REPO_ROOT / "capabilities" / "personal_assistant" / "capability_pack.json"
DEFAULT_OUTPUT = REPO_ROOT / "examples" / "personal_assistant_coherence_ledger_receipt.json"

NO_EFFECT_FLAGS = (
    "execution_allowed",
    "live_connector_execution_allowed",
    "connector_mutation_allowed",
    "external_effect_allowed",
    "customer_readiness_claim_allowed",
    "nested_mind_live_activation_allowed",
    "production_ready_claim_allowed",
)

AUTHORITY_BLOCK_REASONS = {
    "live_execution_blocked": "Live execution remains blocked until operator-approved runtime evidence exists.",
    "connector_mutation_blocked": "Connector mutation remains blocked without approval, receipt, and recovery evidence.",
    "external_communication_blocked": "External communication remains blocked without explicit approval.",
    "deployment_mutation_blocked": "Deployment mutation remains blocked in Foundation Mode.",
    "customer_readiness_claim_blocked": "Customer-readiness claims remain blocked without named readiness witnesses.",
    "nested_mind_live_activation_blocked": "Live Nested Mind activation remains blocked until staging evidence and topology decision exist.",
    "secret_serialization_blocked": "Secret values must not be serialized into assistant receipts.",
    "raw_private_payload_serialization_blocked": "Raw private connector payloads must not be serialized into assistant receipts.",
}


def collect_personal_assistant_coherence_ledger(
    *,
    readiness_index_path: Path = DEFAULT_READINESS_INDEX,
    console_read_model_path: Path = DEFAULT_CONSOLE_READ_MODEL,
    skill_registry_path: Path = DEFAULT_SKILL_REGISTRY,
    capability_pack_path: Path = DEFAULT_CAPABILITY_PACK,
    now_utc: datetime | None = None,
) -> dict[str, object]:
    """Collect one no-effect Personal Assistant coherence ledger receipt."""
    readiness_index = _read_json_object(readiness_index_path, "readiness index receipt")
    console = _read_json_object(console_read_model_path, "console read model")
    skill_registry = _read_json_object(skill_registry_path, "skill registry")
    capability_pack = _read_json_object(capability_pack_path, "capability pack")
    generated_at = _format_utc(now_utc or datetime.now(UTC))

    source_receipts = _source_receipts(readiness_index, readiness_index_path)
    authority_block_records = _authority_block_records(readiness_index)
    lane_ledger_records = _lane_ledger_records(
        readiness_index=readiness_index,
        console=console,
        source_receipt_ids=[record["receipt_id"] for record in source_receipts],
        authority_block_ids=[record["authority_id"] for record in authority_block_records],
    )
    effect_boundary = _effect_boundary(readiness_index, console, capability_pack)
    all_lanes_bound = all(_lane_has_evidence(record) for record in lane_ledger_records)
    all_edges_no_effect = (
        all(record["no_effect_boundary_verified"] is True for record in lane_ledger_records)
        and not any(effect_boundary.values())
        and all(record["blocked"] is True for record in authority_block_records)
    )
    readiness_closed = _readiness_index_closed(readiness_index)
    coherence_closed = readiness_closed and all_lanes_bound and all_edges_no_effect
    proof_state = "Pass" if coherence_closed else "Fail"
    solver_outcome = "SolvedVerified" if coherence_closed else "AwaitingEvidence"

    receipt_without_id = {
        "schema_version": "personal_assistant.coherence_ledger_receipt.v1",
        "generated_at": generated_at,
        "proof_state": proof_state,
        "solver_outcome": solver_outcome,
        "governed": True,
        "receipt_is_not_execution_authority": True,
        "receipt_is_not_terminal_closure": True,
        "source_receipts": source_receipts,
        "coherence_summary": {
            "coherence_ledger_closed": coherence_closed,
            "readiness_index_closed": readiness_closed,
            "lane_count": len(lane_ledger_records),
            "dependency_edge_count": sum(_int(record["dependency_edge_count"]) for record in lane_ledger_records),
            "blocked_authority_count": sum(1 for record in authority_block_records if record["blocked"] is True),
            "next_action_count": sum(
                1
                for record in lane_ledger_records
                if record["next_allowed_action"] == "continue_foundation_hardening_only"
            ),
            "all_lanes_bound_to_sources": all_lanes_bound,
            "all_edges_no_effect": all_edges_no_effect,
            "no_effect_boundary_verified": all_edges_no_effect,
            "production_ready": False,
            "customer_ready": False,
            "next_allowed_action": "continue_foundation_hardening_only",
        },
        "lane_ledger_records": lane_ledger_records,
        "authority_block_records": authority_block_records,
        "effect_boundary": effect_boundary,
        "lineage": {
            "accepted_deltas": [
                {
                    "delta_id": f"delta-personal-assistant-coherence-ledger-{generated_at[:10]}",
                    "reason": _lineage_reason(coherence_closed),
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


def write_personal_assistant_coherence_ledger(
    receipt: Mapping[str, object],
    output_path: Path,
) -> Path:
    """Write one local Personal Assistant coherence ledger receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return output_path


def _source_receipts(readiness_index: Mapping[str, Any], readiness_index_path: Path) -> list[dict[str, object]]:
    summary = _object(readiness_index.get("summary"))
    return [
        {
            "source_id": "personal_assistant_readiness_index",
            "source_ref": _path_label(readiness_index_path),
            "receipt_id": _bounded_identifier(readiness_index.get("receipt_id")),
            "proof_state": _bounded_outcome(readiness_index.get("proof_state"), allowed={"Pass", "Fail"}),
            "solver_outcome": _bounded_outcome(
                readiness_index.get("solver_outcome"),
                allowed={"SolvedVerified", "AwaitingEvidence"},
            ),
            "closed": summary.get("readiness_index_closed") is True,
            "no_effect_boundary_verified": summary.get("no_effect_boundary_verified") is True,
        }
    ]


def _authority_block_records(readiness_index: Mapping[str, Any]) -> list[dict[str, object]]:
    blocks = _object(readiness_index.get("authority_blocks"))
    records: list[dict[str, object]] = []
    for authority_id, reason in AUTHORITY_BLOCK_REASONS.items():
        records.append(
            {
                "authority_id": authority_id,
                "blocked": blocks.get(authority_id) is True,
                "source": "personal_assistant_readiness_index",
                "reason": reason,
            }
        )
    return records


def _lane_ledger_records(
    *,
    readiness_index: Mapping[str, Any],
    console: Mapping[str, Any],
    source_receipt_ids: list[object],
    authority_block_ids: list[object],
) -> list[dict[str, object]]:
    readiness_lanes = {
        str(lane.get("lane_id")): lane for lane in _list_of_objects(readiness_index.get("lane_records"))
    }
    console_lanes = _list_of_objects(_object(console.get("lane_status")).get("lanes"))
    records: list[dict[str, object]] = []
    for console_lane in console_lanes:
        lane_id = _bounded_identifier(console_lane.get("lane_id"))
        readiness_lane = readiness_lanes.get(lane_id, {})
        route_refs = _string_list(console_lane.get("route_refs"))
        schema_refs = _string_list(console_lane.get("schema_refs"))
        validator_refs = _string_list(console_lane.get("validator_refs"))
        dependency_edge_count = len(route_refs) + len(schema_refs) + len(validator_refs)
        records.append(
            {
                "ledger_record_id": f"pa-coherence-lane-{lane_id}",
                "lane_id": lane_id,
                "stage": _bounded_identifier(readiness_lane.get("stage") or console_lane.get("stage")),
                "state": _bounded_outcome(readiness_lane.get("state"), allowed={"SolvedVerified", "AwaitingEvidence"}),
                "source_receipt_ids": [_bounded_identifier(receipt_id) for receipt_id in source_receipt_ids],
                "route_refs": route_refs,
                "schema_refs": schema_refs,
                "validator_refs": validator_refs,
                "dependency_edge_count": dependency_edge_count,
                "blocked_authority_refs": [_bounded_identifier(authority_id) for authority_id in authority_block_ids],
                "foundation_only": readiness_lane.get("foundation_only") is True and console_lane.get("foundation_only") is True,
                "receipt_required": readiness_lane.get("receipt_required") is True and console_lane.get("receipt_required") is True,
                "no_effect_boundary_verified": readiness_lane.get("no_effect_boundary_verified") is True
                and _lane_no_effect_boundary_verified(console_lane),
                "next_allowed_action": "continue_foundation_hardening_only",
            }
        )
    return records


def _effect_boundary(
    readiness_index: Mapping[str, Any],
    console: Mapping[str, Any],
    capability_pack: Mapping[str, Any],
) -> dict[str, bool]:
    readiness_boundary = _object(readiness_index.get("effect_boundary"))
    console_boundary = _object(console.get("effect_boundary"))
    console_lane = _object(console.get("lane_status"))
    private_payload_policy = _object(console.get("private_payload_policy"))
    capabilities = _list_of_objects(capability_pack.get("capabilities"))
    return {
        "execution_allowed": _any_true(readiness_boundary.get("execution_allowed"), console_lane.get("execution_allowed")),
        "live_connector_execution_allowed": _any_true(
            readiness_boundary.get("live_connector_execution_allowed"),
            console_boundary.get("live_connector_execution_allowed"),
            console_lane.get("live_connector_execution_allowed"),
        ),
        "connector_mutation_allowed": _any_true(
            readiness_boundary.get("connector_mutation_allowed"),
            console_lane.get("connector_mutation_allowed"),
        ),
        "external_effect_allowed": _any_true(
            readiness_boundary.get("external_effect_allowed"),
            console_boundary.get("external_send_allowed"),
            console_lane.get("external_effect_allowed"),
        ),
        "customer_readiness_claim_allowed": _any_true(
            readiness_boundary.get("customer_readiness_claim_allowed"),
            console_boundary.get("public_readiness_claim_allowed"),
            console_lane.get("customer_readiness_claim_allowed"),
        ),
        "nested_mind_live_activation_allowed": _any_true(
            readiness_boundary.get("nested_mind_live_activation_allowed"),
            console_boundary.get("nested_mind_live_activation_allowed"),
            console_lane.get("nested_mind_live_activation_allowed"),
        ),
        "production_ready_claim_allowed": _any_true(
            readiness_boundary.get("production_ready_claim_allowed"),
            any(_object(capability.get("metadata")).get("production_ready") is True for capability in capabilities),
        ),
        "secret_values_serialized": _any_true(
            readiness_boundary.get("secret_values_serialized"),
            private_payload_policy.get("secret_values_serialized"),
        ),
        "raw_private_payloads_serialized": _any_true(
            readiness_boundary.get("raw_private_payloads_serialized"),
            private_payload_policy.get("raw_private_payload_serialized"),
        ),
    }


def _readiness_index_closed(readiness_index: Mapping[str, Any]) -> bool:
    summary = _object(readiness_index.get("summary"))
    return (
        readiness_index.get("proof_state") == "Pass"
        and readiness_index.get("solver_outcome") == "SolvedVerified"
        and summary.get("readiness_index_closed") is True
        and summary.get("no_effect_boundary_verified") is True
        and summary.get("production_ready") is False
        and summary.get("customer_ready") is False
    )


def _lane_has_evidence(record: Mapping[str, object]) -> bool:
    return (
        bool(_list(record.get("source_receipt_ids")))
        and bool(_list(record.get("schema_refs")))
        and bool(_list(record.get("validator_refs")))
        and _int(record.get("dependency_edge_count")) >= 1
    )


def _lane_no_effect_boundary_verified(lane: Mapping[str, Any]) -> bool:
    return (
        lane.get("foundation_only") is True
        and lane.get("receipt_required") is True
        and all(lane.get(flag) is False for flag in NO_EFFECT_FLAGS if flag != "production_ready_claim_allowed")
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


def _string_list(value: Any) -> list[str]:
    return [item for item in _list(value) if isinstance(item, str) and item]


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
    return f"personal-assistant-coherence-ledger-{hashlib.sha256(material).hexdigest()[:16]}"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _lineage_reason(coherence_closed: bool) -> str:
    if coherence_closed:
        return "Recorded Personal Assistant coherence ledger while preserving no-effect authority."
    return "Recorded Personal Assistant coherence ledger and preserved AwaitingEvidence."


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse Personal Assistant coherence ledger collection arguments."""
    parser = argparse.ArgumentParser(description="Collect Personal Assistant coherence ledger evidence.")
    parser.add_argument("--readiness-index", default=str(DEFAULT_READINESS_INDEX))
    parser.add_argument("--console-read-model", default=str(DEFAULT_CONSOLE_READ_MODEL))
    parser.add_argument("--skill-registry", default=str(DEFAULT_SKILL_REGISTRY))
    parser.add_argument("--capability-pack", default=str(DEFAULT_CAPABILITY_PACK))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, now_utc: datetime | None = None) -> int:
    """CLI entry point for Personal Assistant coherence ledger collection."""
    args = parse_args(argv)
    receipt = collect_personal_assistant_coherence_ledger(
        readiness_index_path=Path(args.readiness_index),
        console_read_model_path=Path(args.console_read_model),
        skill_registry_path=Path(args.skill_registry),
        capability_pack_path=Path(args.capability_pack),
        now_utc=now_utc,
    )
    write_personal_assistant_coherence_ledger(receipt, Path(args.output))
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=False))
    else:
        print(f"personal-assistant coherence ledger outcome: {receipt['solver_outcome']}")
    return 0 if receipt["solver_outcome"] == "SolvedVerified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
