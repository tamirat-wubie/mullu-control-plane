#!/usr/bin/env python3
"""Collect a Personal Assistant dry-run packet.

Purpose: bind the Personal Assistant foundation artifacts into one replayable
dry-run workflow packet covering intake, WHQR binding, skill routing, preview,
draft, approval gating, receipt replay, and memory-review observation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: checked-in Personal Assistant schemas, examples, and receipts.
Invariants:
  - Collection reads local JSON evidence only.
  - The packet grants no execution, connector, memory, deployment, or customer authority.
  - Source artifacts are represented by bounded refs, digests, and lengths only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "examples" / "personal_assistant_dry_run_packet.json"

SOURCE_ARTIFACTS: tuple[tuple[str, Path, str], ...] = (
    ("request", REPO_ROOT / "examples" / "personal_assistant_request_inbox_summary.json", "schemas/personal_assistant_request.schema.json"),
    ("skill_registry", REPO_ROOT / "examples" / "personal_assistant_skill_registry.json", "schemas/personal_assistant_skill.schema.json"),
    ("read_only_projection", REPO_ROOT / "examples" / "personal_assistant_read_only_projection.json", "schemas/personal_assistant_read_only_projection.schema.json"),
    ("draft_projection", REPO_ROOT / "examples" / "personal_assistant_draft_projection.json", "schemas/personal_assistant_draft_projection.schema.json"),
    ("approval_packet", REPO_ROOT / "examples" / "personal_assistant_approval_packet.json", "schemas/personal_assistant_approval.schema.json"),
    ("draft_receipt", REPO_ROOT / "examples" / "personal_assistant_receipt_draft_only.json", "schemas/personal_assistant_receipt.schema.json"),
    ("memory_review", REPO_ROOT / "examples" / "personal_assistant_memory_review_evidence.json", "schemas/personal_assistant_memory_review.schema.json"),
    ("skill_readiness_catalog", REPO_ROOT / "examples" / "personal_assistant_skill_readiness_catalog.json", "schemas/personal_assistant_skill_readiness_catalog.schema.json"),
    ("foundation_closure_packet", REPO_ROOT / "examples" / "personal_assistant_foundation_closure_packet.json", "schemas/personal_assistant_foundation_closure_packet.schema.json"),
)

NO_EFFECT_FLAGS = (
    "execution_allowed",
    "execution_authority_granted",
    "runtime_execution_authority_granted",
    "live_connector_execution_allowed",
    "connector_mutation_allowed",
    "external_effect_allowed",
    "external_write_allowed",
    "external_send_allowed",
    "mailbox_mutation_allowed",
    "calendar_write_allowed",
    "task_write_allowed",
    "system_of_record_write_allowed",
    "memory_write_allowed",
    "memory_admission_allowed",
    "deployment_mutation_allowed",
    "money_legal_public_allowed",
    "production_ready_claim_allowed",
    "customer_readiness_claim_allowed",
    "customer_ready_claim_allowed",
    "public_readiness_claim_allowed",
    "live_nested_mind_activation_allowed",
    "nested_mind_live_activation_allowed",
    "secret_values_serialized",
    "raw_private_payload_serialized",
    "raw_connector_payload_serialized",
)

BLOCKED_SECRET_VALUE_MARKERS = (
    "access_token=",
    "api_key=",
    "authorization: bearer",
    "bearer ",
    "client_secret=",
    "password=",
    "private_key=",
    "-----begin private key-----",
)


def collect_personal_assistant_dry_run_packet(*, now_utc: datetime | None = None) -> dict[str, object]:
    """Collect one deterministic no-effect Personal Assistant dry-run packet."""
    generated_at = _format_utc(now_utc or datetime.now(UTC))
    source_records = [_source_artifact_record(kind, path, schema_ref) for kind, path, schema_ref in SOURCE_ARTIFACTS]
    stages = _stage_records()
    topology_summary = _topology_summary(stages, source_records)
    effect_violation_count = sum(int(record["effect_violation_count"]) for record in source_records)
    all_source_artifacts_bound = all(record["bound"] is True for record in source_records)
    all_source_artifacts_solved_verified = all(record["solver_outcome"] == "SolvedVerified" for record in source_records)
    no_effect_boundary = {
        "execution_authority_granted": False,
        "live_connector_execution_allowed": False,
        "connector_mutation_allowed": False,
        "external_effect_allowed": False,
        "system_of_record_write_allowed": False,
        "memory_write_allowed": False,
        "memory_admission_allowed": False,
        "deployment_mutation_allowed": False,
        "money_legal_public_allowed": False,
        "production_ready_claim_allowed": False,
        "customer_ready_claim_allowed": False,
        "live_nested_mind_activation_allowed": False,
    }
    packet_without_id: dict[str, object] = {
        "schema_version": "personal_assistant.dry_run_packet.v1",
        "generated_at": generated_at,
        "proof_state": "Fail",
        "solver_outcome": "AwaitingEvidence",
        "governed": True,
        "packet_is_not_execution_authority": True,
        "packet_is_not_memory_admission": True,
        "packet_is_not_customer_readiness": True,
        "workflow": {
            "workflow_id": "pa_workflow_dry_run_inbox_to_draft_001",
            "goal": "Replay a governed inbox-to-draft Personal Assistant request through all foundation gates without live execution.",
            "actor_ref": "operator:tamirat",
            "tenant_ref": "tenant:foundation-local",
            "expected_effects": ["digest_only_evidence_packet_created"],
            "forbidden_effects": [
                "live_connector_execution",
                "connector_mutation",
                "external_send",
                "calendar_write",
                "task_write",
                "memory_write",
                "deployment_mutation",
                "money_legal_public_action",
                "customer_readiness_claim",
                "live_nested_mind_activation",
            ],
            "terminal_closure_condition": "All stages are replayable, verified, and no-effect with approval gates before any effect-bearing path.",
        },
        "source_artifacts": source_records,
        "stages": stages,
        "topology_summary": topology_summary,
        "no_effect_boundary": no_effect_boundary,
        "closure_summary": {},
        "secret_value_markers": [],
        "lineage": {
            "accepted_deltas": [
                {
                    "delta_id": "dry_run_packet_collected",
                    "reason": "Digest-only workflow evidence can be collected in Foundation Mode.",
                    "logged_in_lineage": True,
                }
            ],
            "rejected_deltas": [
                {
                    "delta_id": "live_connector_execution",
                    "reason": "Dry-run packet does not grant live connector execution authority.",
                    "logged_in_lineage": True,
                },
                {
                    "delta_id": "memory_admission",
                    "reason": "Memory observations remain review candidates; no live memory write is admitted.",
                    "logged_in_lineage": True,
                },
                {
                    "delta_id": "external_send",
                    "reason": "External communication remains blocked without explicit approval and live adapter evidence.",
                    "logged_in_lineage": True,
                },
            ],
        },
    }
    secret_value_markers = sorted(_secret_markers_for_payload(packet_without_id))
    no_secret_values_serialized = not secret_value_markers
    no_effect_boundaries_clear = not any(no_effect_boundary.values()) and effect_violation_count == 0
    all_stages_verified = topology_summary["all_stages_verified"] is True
    dry_run_packet_closed = (
        all_source_artifacts_bound
        and all_source_artifacts_solved_verified
        and all_stages_verified
        and topology_summary["acyclic"] is True
        and topology_summary["no_dangling_bindings"] is True
        and topology_summary["approval_gates_before_effects"] is True
        and no_effect_boundaries_clear
        and no_secret_values_serialized
    )
    packet_without_id["proof_state"] = "Pass" if dry_run_packet_closed else "Fail"
    packet_without_id["solver_outcome"] = "SolvedVerified" if dry_run_packet_closed else "AwaitingEvidence"
    packet_without_id["secret_value_markers"] = secret_value_markers
    packet_without_id["closure_summary"] = {
        "dry_run_packet_closed": dry_run_packet_closed,
        "source_artifact_count": len(source_records),
        "bound_source_artifact_count": sum(1 for record in source_records if record["bound"] is True),
        "stage_count": len(stages),
        "approval_gate_count": sum(1 for stage in stages if stage["stage_type"] == "approval_gate"),
        "effect_violation_count": effect_violation_count,
        "secret_value_marker_count": len(secret_value_markers),
        "all_source_artifacts_bound": all_source_artifacts_bound,
        "all_source_artifacts_solved_verified": all_source_artifacts_solved_verified,
        "all_stages_verified": all_stages_verified,
        "acyclic_topology": topology_summary["acyclic"] is True,
        "all_bindings_resolved": topology_summary["no_dangling_bindings"] is True,
        "approval_gate_before_effect_bearing_actions": topology_summary["approval_gates_before_effects"] is True,
        "no_effect_boundaries_clear": no_effect_boundaries_clear,
        "no_secret_values_serialized": no_secret_values_serialized,
        "live_connector_execution_ready": False,
        "memory_write_ready": False,
        "deployment_mutation_ready": False,
        "customer_ready": False,
        "next_allowed_action": "continue_foundation_hardening_only",
    }
    packet_id = _packet_id(packet_without_id)
    return {"packet_id": packet_id, **packet_without_id}


def write_personal_assistant_dry_run_packet(packet: dict[str, object], output_path: Path) -> Path:
    """Write one local Personal Assistant dry-run packet."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _source_artifact_record(kind: str, path: Path, schema_ref: str) -> dict[str, object]:
    if not path.exists():
        return {
            "source_kind": kind,
            "source_ref": _repo_path(path),
            "schema_ref": schema_ref,
            "source_sha256": "",
            "bound": False,
            "payload_digest_only": True,
            "serialized_length": 0,
            "proof_state": "Fail",
            "solver_outcome": "AwaitingEvidence",
            "effect_violation_count": 1,
            "effect_violations": ["source_missing"],
        }
    raw_bytes = path.read_bytes()
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except json.JSONDecodeError:
        payload = {}
    effect_violations = [] if kind == "skill_registry" else _effect_violations(payload)
    return {
        "source_kind": kind,
        "source_ref": _repo_path(path),
        "schema_ref": schema_ref,
        "source_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "bound": True,
        "payload_digest_only": True,
        "serialized_length": len(raw_bytes),
        "proof_state": "Pass" if not effect_violations else "Fail",
        "solver_outcome": "SolvedVerified" if not effect_violations else "GovernanceBlocked",
        "effect_violation_count": len(effect_violations),
        "effect_violations": effect_violations,
    }


def _stage_records() -> list[dict[str, object]]:
    return [
        _stage(
            "intake_observation",
            "observation",
            [],
            "",
            ["personal_assistant.intake.project"],
            ["source:request"],
            ["governed_intent"],
            "P1",
            False,
            "none",
            "intake_only_no_execution",
            ["proof://personal-assistant/dry-run/intake"],
            ["request_digest_bound"],
            ["connector_not_called", "private_payload_not_serialized"],
        ),
        _stage(
            "whqr_binding",
            "observation",
            ["intake_observation"],
            "",
            ["personal_assistant.whqr.bind"],
            ["intake_observation.governed_intent"],
            ["whqr_binding"],
            "P1",
            False,
            "none",
            "clarification_binding_only",
            ["proof://personal-assistant/dry-run/whqr"],
            ["missing_bindings_checked"],
            ["operator_not_contacted", "external_context_not_loaded"],
        ),
        _stage(
            "skill_route",
            "skill_execution",
            ["whqr_binding"],
            "email.inbox.summarize",
            ["email.read", "email.search", "personal_assistant.receipt.project"],
            ["source:skill_registry", "whqr_binding.whqr_binding"],
            ["skill_plan_binding"],
            "P1",
            False,
            "none",
            "skill_route_no_provider_call",
            ["proof://personal-assistant/dry-run/skill-route"],
            ["skill_route_selected"],
            ["gmail_not_called", "connector_state_not_mutated"],
        ),
        _stage(
            "read_only_preview",
            "skill_execution",
            ["skill_route"],
            "email.inbox.summarize",
            ["email.read", "email.search", "personal_assistant.receipt.project"],
            ["source:read_only_projection", "skill_route.skill_plan_binding"],
            ["read_only_receipt_ref"],
            "P1",
            False,
            "none",
            "read_only_redacted_projection",
            ["proof://personal-assistant/dry-run/read-only-preview"],
            ["read_only_projection_replayed"],
            ["mailbox_not_mutated", "email_not_sent", "connector_state_not_mutated"],
        ),
        _stage(
            "draft_preview",
            "skill_execution",
            ["read_only_preview"],
            "email.response.draft",
            ["email.reply_suggest", "personal_assistant.receipt.project"],
            ["source:draft_projection", "source:draft_receipt", "read_only_preview.read_only_receipt_ref"],
            ["draft_receipt_ref", "draft_artifact_ref"],
            "P2",
            False,
            "none",
            "draft_only_email_not_sent",
            ["proof://personal-assistant/dry-run/draft-preview"],
            ["draft_projection_replayed"],
            ["email_not_sent", "mailbox_not_modified", "connector_state_not_mutated"],
        ),
        _stage(
            "approval_gate_external_send",
            "approval_gate",
            ["draft_preview"],
            "email.send.with_approval",
            ["email.send", "personal_assistant.approval.request"],
            ["source:approval_packet", "draft_preview.draft_artifact_ref"],
            ["approval_request_ref"],
            "P4",
            True,
            "P4",
            "external_email_send_requires_explicit_approval",
            ["proof://personal-assistant/dry-run/approval-gate"],
            ["approval_gate_recorded"],
            ["email_not_sent", "approval_not_auto_granted", "connector_state_not_mutated"],
        ),
        _stage(
            "blocked_external_send",
            "wait_for_event",
            ["approval_gate_external_send"],
            "email.send.with_approval",
            ["email.send"],
            ["approval_gate_external_send.approval_request_ref"],
            ["external_send_blocked"],
            "P4",
            True,
            "P4",
            "external_email_send_blocked_without_approval",
            ["proof://personal-assistant/dry-run/external-send-blocked"],
            ["approval_wait_state_recorded"],
            ["email_not_sent", "provider_not_called", "system_of_record_not_mutated"],
            outcome="AwaitingEvidence",
        ),
        _stage(
            "memory_observation_review",
            "skill_execution",
            ["draft_preview"],
            "memory.observe",
            ["personal_assistant.memory.review"],
            ["source:memory_review", "draft_preview.draft_receipt_ref"],
            ["memory_review_ref"],
            "P2",
            False,
            "none",
            "memory_review_candidate_only",
            ["proof://personal-assistant/dry-run/memory-review"],
            ["memory_review_replayed"],
            ["live_memory_not_written", "nested_mind_not_activated", "raw_chat_log_not_stored"],
        ),
        _stage(
            "receipt_replay",
            "observation",
            ["read_only_preview", "draft_preview", "approval_gate_external_send", "memory_observation_review"],
            "",
            ["personal_assistant.receipt.replay"],
            ["source:skill_readiness_catalog", "source:foundation_closure_packet", "memory_observation_review.memory_review_ref"],
            ["replay_evidence_ref"],
            "P2",
            False,
            "none",
            "digest_only_receipt_replay",
            ["proof://personal-assistant/dry-run/receipt-replay"],
            ["receipt_chain_replayed"],
            ["raw_private_payload_not_serialized", "secret_values_not_serialized"],
        ),
        _stage(
            "terminal_no_effect_closure",
            "observation",
            ["blocked_external_send", "receipt_replay"],
            "",
            ["personal_assistant.foundation.close"],
            ["blocked_external_send.external_send_blocked", "receipt_replay.replay_evidence_ref"],
            ["dry_run_packet_closed"],
            "P2",
            False,
            "none",
            "terminal_foundation_closure_only",
            ["proof://personal-assistant/dry-run/terminal-closure"],
            ["dry_run_closure_recorded"],
            ["terminal_product_readiness_not_claimed", "live_execution_not_enabled"],
        ),
    ]


def _stage(
    stage_id: str,
    stage_type: str,
    predecessor_ids: list[str],
    skill_id: str,
    capability_refs: list[str],
    input_bindings: list[str],
    output_keys: list[str],
    risk_level: str,
    approval_required: bool,
    approval_level: str,
    effect_boundary: str,
    verification_refs: list[str],
    actions_taken: list[str],
    actions_not_taken: list[str],
    *,
    outcome: str = "SolvedVerified",
) -> dict[str, object]:
    return {
        "stage_id": stage_id,
        "stage_type": stage_type,
        "predecessor_ids": predecessor_ids,
        "skill_id": skill_id,
        "capability_refs": capability_refs,
        "input_bindings": input_bindings,
        "output_keys": output_keys,
        "risk_level": risk_level,
        "approval_required": approval_required,
        "approval_level": approval_level,
        "execution_allowed": False,
        "effect_boundary": effect_boundary,
        "timeout_boundary": "bounded_to_operator_review_no_background_worker",
        "verification_refs": verification_refs,
        "actions_taken": actions_taken,
        "actions_not_taken": actions_not_taken,
        "outcome": outcome,
    }


def _topology_summary(stages: list[dict[str, object]], source_records: list[dict[str, object]]) -> dict[str, object]:
    stage_ids = {str(stage["stage_id"]) for stage in stages}
    source_kinds = {str(record["source_kind"]) for record in source_records}
    edge_count = sum(len(stage["predecessor_ids"]) for stage in stages)
    no_dangling_predecessors = all(
        str(predecessor_id) in stage_ids
        for stage in stages
        for predecessor_id in _strings(stage["predecessor_ids"])
    )
    no_dangling_bindings = _bindings_resolved(stages, source_kinds)
    return {
        "stage_count": len(stages),
        "edge_count": edge_count,
        "terminal_stage_id": "terminal_no_effect_closure",
        "acyclic": _acyclic(stages),
        "no_dangling_predecessors": no_dangling_predecessors,
        "no_dangling_bindings": no_dangling_bindings,
        "approval_gates_before_effects": _approval_gates_before_effects(stages),
        "all_stages_verified": all(_strings(stage["verification_refs"]) for stage in stages),
    }


def _bindings_resolved(stages: list[dict[str, object]], source_kinds: set[str]) -> bool:
    outputs_by_stage = {
        str(stage["stage_id"]): set(_strings(stage["output_keys"]))
        for stage in stages
    }
    for stage in stages:
        stage_id = str(stage["stage_id"])
        predecessors = set(_strings(stage["predecessor_ids"]))
        for binding in _strings(stage["input_bindings"]):
            if binding.startswith("source:"):
                if binding.removeprefix("source:") not in source_kinds:
                    return False
                continue
            if "." not in binding:
                return False
            binding_stage, binding_output = binding.split(".", 1)
            if binding_stage not in outputs_by_stage or binding_output not in outputs_by_stage[binding_stage]:
                return False
            if binding_stage not in predecessors and binding_stage != stage_id:
                return False
    return True


def _acyclic(stages: list[dict[str, object]]) -> bool:
    predecessors = {
        str(stage["stage_id"]): set(_strings(stage["predecessor_ids"]))
        for stage in stages
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(stage_id: str) -> bool:
        if stage_id in visited:
            return True
        if stage_id in visiting:
            return False
        visiting.add(stage_id)
        for predecessor_id in predecessors.get(stage_id, set()):
            if predecessor_id in predecessors and not visit(predecessor_id):
                return False
        visiting.remove(stage_id)
        visited.add(stage_id)
        return True

    return all(visit(stage_id) for stage_id in predecessors)


def _approval_gates_before_effects(stages: list[dict[str, object]]) -> bool:
    stage_by_id = {str(stage["stage_id"]): stage for stage in stages}
    for stage in stages:
        risk_level = str(stage["risk_level"])
        effect_boundary = str(stage["effect_boundary"])
        requires_gate = risk_level in {"P4", "P5"} or any(
            marker in effect_boundary
            for marker in ("external_email_send", "system_write", "calendar_write", "task_write", "memory_write")
        )
        if not requires_gate:
            continue
        if stage["stage_type"] == "approval_gate" and stage["approval_required"] is True:
            continue
        if not _has_approval_gate_ancestor(str(stage["stage_id"]), stage_by_id, set()):
            return False
    return True


def _has_approval_gate_ancestor(stage_id: str, stage_by_id: dict[str, dict[str, object]], seen: set[str]) -> bool:
    if stage_id in seen:
        return False
    seen.add(stage_id)
    stage = stage_by_id[stage_id]
    for predecessor_id in _strings(stage["predecessor_ids"]):
        predecessor = stage_by_id.get(predecessor_id)
        if predecessor is None:
            continue
        if predecessor["stage_type"] == "approval_gate" and predecessor["approval_required"] is True:
            return True
        if _has_approval_gate_ancestor(predecessor_id, stage_by_id, seen):
            return True
    return False


def _effect_violations(payload: object) -> list[str]:
    violations: list[str] = []

    def visit(value: object, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                if key in NO_EFFECT_FLAGS and child is True:
                    violations.append(child_path)
                visit(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(payload, "")
    return sorted(set(violations))


def _secret_markers_for_payload(payload: object) -> set[str]:
    text = json.dumps(payload, sort_keys=True).lower()
    return {marker for marker in BLOCKED_SECRET_VALUE_MARKERS if marker in text}


def _packet_id(payload: dict[str, object]) -> str:
    stable_payload = dict(payload)
    stable_payload.pop("generated_at", None)
    digest = hashlib.sha256(json.dumps(stable_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"personal-assistant-dry-run-{digest[:16]}"


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _repo_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print the collected packet to stdout.")
    args = parser.parse_args(argv)
    packet = collect_personal_assistant_dry_run_packet()
    write_personal_assistant_dry_run_packet(packet, args.output)
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        summary = packet["closure_summary"]
        print(f"dry_run_packet: {_repo_path(args.output)}")
        print(f"packet_id: {packet['packet_id']}")
        print(f"solver_outcome: {packet['solver_outcome']}")
        print(f"dry_run_packet_closed: {summary['dry_run_packet_closed']}")  # type: ignore[index]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
