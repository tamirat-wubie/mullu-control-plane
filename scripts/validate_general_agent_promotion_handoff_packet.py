#!/usr/bin/env python3
"""Validate the general-agent promotion handoff packet artifact.

Purpose: keep the operator handoff packet machine-readable, schema-valid, and
aligned with closure-plan, checklist, blocker, and terminal proof gates.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: examples/general_agent_promotion_handoff_packet.json,
schemas/general_agent_promotion_handoff_packet.schema.json,
scripts/validate_general_agent_promotion.py, redacted adapter evidence, and
promotion closure artifacts.
Invariants:
  - The packet never claims production readiness while blockers remain.
  - Required blockers and approval-required blockers remain visible.
  - Entry points name the runbook, checklist, validators, preflight, and closure reports.
  - The terminal proof command is strict and writes the readiness artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_general_agent_promotion import validate_general_agent_promotion  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_PACKET = REPO_ROOT / "examples" / "general_agent_promotion_handoff_packet.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "general_agent_promotion_handoff_packet.schema.json"
DEFAULT_CHECKLIST = REPO_ROOT / "examples" / "general_agent_promotion_operator_checklist.json"
DEFAULT_CLOSURE_PLAN = REPO_ROOT / ".change_assurance" / "general_agent_promotion_closure_plan.json"
DEFAULT_ADAPTER_EVIDENCE = REPO_ROOT / ".change_assurance" / "capability_adapter_evidence.json"
DEFAULT_CLOSED_ADAPTER_EVIDENCE = REPO_ROOT / "examples" / "capability_adapter_evidence_live_closed_20260611.json"
PRODUCTION_PROMOTION_BLOCKER_ORDER = (
    "deployment_witness_not_published",
    "production_health_not_declared",
)
PRODUCTION_PROMOTION_BLOCKERS = frozenset(PRODUCTION_PROMOTION_BLOCKER_ORDER)
PRODUCTION_BLOCKED_READINESS_LEVEL = "pilot-governed-core"
ADAPTER_PROMOTION_BLOCKER_ORDER = (
    "adapter_evidence_not_closed",
    "voice_adapter_not_closed",
    "email_calendar_adapter_not_closed",
)
ADAPTER_PROMOTION_BLOCKERS = frozenset(ADAPTER_PROMOTION_BLOCKER_ORDER)
PACKET_BLOCKED_ADAPTER_EVIDENCE_BLOCKERS = (
    "voice_dependency_missing:OPENAI_API_KEY",
    "voice_live_evidence_missing",
    "email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN",
    "email_calendar_live_evidence_missing",
)

REQUIRED_ENTRY_POINTS = {
    "human_runbook": "docs/58_general_agent_promotion_operator_runbook.md",
    "machine_checklist": "examples/general_agent_promotion_operator_checklist.json",
    "machine_handoff_packet": "examples/general_agent_promotion_handoff_packet.json",
    "environment_binding_contract": "examples/general_agent_promotion_environment_bindings.json",
    "checklist_validator": "scripts/validate_general_agent_promotion_operator_checklist.py",
    "handoff_packet_validator": "scripts/validate_general_agent_promotion_handoff_packet.py",
    "environment_binding_validator": "scripts/validate_general_agent_promotion_environment_bindings.py",
    "environment_binding_receipt_emitter": "scripts/emit_general_agent_promotion_environment_binding_receipt.py",
    "environment_binding_receipt_validator": "scripts/validate_general_agent_promotion_environment_binding_receipt.py",
    "handoff_preflight": "scripts/preflight_general_agent_promotion_handoff.py",
    "handoff_preflight_validator": "scripts/validate_general_agent_promotion_handoff_preflight.py",
    "adapter_closure_plan": ".change_assurance/capability_adapter_closure_plan.json",
    "adapter_schema_validation_report": ".change_assurance/capability_adapter_closure_plan_schema_validation.json",
    "adapter_schema_validator": "scripts/validate_capability_adapter_closure_plan_schema.py",
    "aggregate_closure_plan": ".change_assurance/general_agent_promotion_closure_plan.json",
    "capability_improvement_portfolio": ".change_assurance/capability_improvement_portfolio.json",
    "closure_chain_runner": "scripts/run_general_agent_promotion_closure_chain.py",
    "live_evidence_queue": ".change_assurance/general_agent_promotion_live_evidence_queue.json",
    "live_evidence_queue_planner": "scripts/plan_general_agent_promotion_live_evidence_queue.py",
    "terminal_approval_receipt": ".change_assurance/general_agent_promotion_terminal_approvals.json",
    "terminal_approval_receipt_schema": "schemas/general_agent_promotion_terminal_approvals.schema.json",
    "terminal_approval_receipt_validator": "scripts/validate_general_agent_promotion_terminal_approvals.py",
    "terminal_certificate_gate": ".change_assurance/general_agent_promotion_terminal_certificate_gate.json",
    "terminal_certificate_gate_planner": "scripts/plan_general_agent_promotion_terminal_certificate_gate.py",
    "terminal_certificate_candidates": ".change_assurance/general_agent_promotion_terminal_certificate_candidates.json",
    "terminal_certificate_candidates_schema": "schemas/general_agent_promotion_terminal_certificate_candidates.schema.json",
    "terminal_certificate_candidates_planner": "scripts/plan_general_agent_promotion_terminal_certificate_candidates.py",
    "terminal_evidence_reconciliation": ".change_assurance/general_agent_promotion_terminal_evidence_reconciliation.json",
    "terminal_evidence_reconciliation_schema": "schemas/general_agent_promotion_terminal_evidence_reconciliation.schema.json",
    "terminal_evidence_reconciliation_planner": "scripts/reconcile_general_agent_promotion_terminal_evidence.py",
    "terminal_minting_gate": ".change_assurance/general_agent_promotion_terminal_minting_gate.json",
    "terminal_minting_gate_schema": "schemas/general_agent_promotion_terminal_minting_gate.schema.json",
    "terminal_minting_gate_planner": "scripts/gate_general_agent_promotion_terminal_minting.py",
    "terminal_certificate_minting_run": ".change_assurance/general_agent_promotion_terminal_certificate_minting_run.json",
    "terminal_certificate_minting_run_schema": (
        "schemas/general_agent_promotion_terminal_certificate_minting_run.schema.json"
    ),
    "terminal_certificate_minting_executor": "scripts/mint_general_agent_promotion_terminal_certificates.py",
    "schema_validation_report": ".change_assurance/general_agent_promotion_closure_plan_schema_validation.json",
    "drift_validation_report": ".change_assurance/general_agent_promotion_closure_plan_validation.json",
    "readiness_report": ".change_assurance/general_agent_promotion_readiness.json",
    "preflight_report": ".change_assurance/general_agent_promotion_handoff_preflight.json",
    "environment_binding_receipt": ".change_assurance/general_agent_promotion_environment_binding_receipt.json",
}
REQUIRED_VALIDATION_REPORTS = frozenset(
    {
        "general_agent_promotion_operator_checklist valid=true",
        "capability_improvement_portfolio schema-valid",
        "promotion closure chain artifact_valid=true",
        "general_agent_promotion_live_evidence_queue schema-valid",
        "general_agent_promotion_terminal_approvals absent-or-schema-valid",
        "general_agent_promotion_terminal_certificate_gate schema-valid",
        "general_agent_promotion_terminal_certificate_candidates schema-valid",
        "general_agent_promotion_terminal_evidence_reconciliation schema-valid",
        "general_agent_promotion_terminal_minting_gate schema-valid",
        "capability_adapter_closure_plan_schema_validation ok=true",
        "general_agent_promotion_closure_plan_schema_validation ok=true",
        "general_agent_promotion_closure_plan_validation ok=true",
    }
)
REQUIRED_SEQUENCE_ITEMS = frozenset(
    {
        "validate_operator_checklist",
        "regenerate_adapter_evidence",
        "write_promotion_readiness",
        "write_source_closure_plans",
        "run_closure_artifact_chain",
        "review_capability_improvement_portfolio",
        "inspect_live_evidence_queue",
        "inspect_terminal_certificate_gate",
        "inspect_terminal_certificate_candidates",
        "inspect_terminal_evidence_reconciliation",
        "inspect_terminal_minting_gate",
        "validate_adapter_closure_plan_schema",
        "write_aggregate_closure_plan",
        "validate_aggregate_closure_plan_schema",
        "validate_aggregate_closure_plan_drift",
        "validate_environment_binding_receipt",
        "complete_dependency_and_credential_actions",
        "produce_live_adapter_receipts",
        "run_terminal_promotion_validation",
    }
)


@dataclass(frozen=True, slots=True)
class PromotionHandoffPacketValidation:
    """Validation result for one promotion handoff packet."""

    valid: bool
    packet_id: str
    packet_path: str
    schema_path: str
    open_blocker_count: int
    approval_required_count: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready validation output."""
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_general_agent_promotion_handoff_packet(
    *,
    packet_path: Path = DEFAULT_PACKET,
    schema_path: Path = DEFAULT_SCHEMA,
    checklist_path: Path = DEFAULT_CHECKLIST,
    closure_plan_path: Path | None = None,
    adapter_evidence_path: Path | None = None,
) -> PromotionHandoffPacketValidation:
    """Validate one general-agent promotion handoff packet."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "handoff packet schema", errors)
    packet = _load_json_object(packet_path, "handoff packet", errors)
    checklist = _load_json_object(checklist_path, "operator checklist", errors)
    effective_adapter_evidence_path = _adapter_evidence_path_for_packet(
        packet,
        explicit_path=adapter_evidence_path,
    )
    adapter_blockers = _adapter_promotion_blockers_from_packet(packet)
    production_blockers = _production_promotion_blockers_from_packet(packet)
    effective_closure_plan_path = closure_plan_path
    closure_plan = _load_or_derive_closure_plan(
        effective_closure_plan_path,
        errors,
        adapter_evidence_path=effective_adapter_evidence_path,
        adapter_blockers=adapter_blockers,
        production_blockers=production_blockers,
    )
    if not schema or not packet:
        return _validation_result(packet_path, schema_path, packet, errors)

    errors.extend(_validate_schema_instance(schema, packet))
    readiness = _evaluate_promotion_readiness(
        errors,
        adapter_evidence_path=effective_adapter_evidence_path,
        adapter_blockers=adapter_blockers,
        production_blockers=production_blockers,
    )
    _validate_scalar_fields(packet, checklist, closure_plan, readiness, errors)
    _validate_required_sets(packet, closure_plan, readiness, errors)
    _validate_entry_points(packet, errors)
    _validate_terminal_proof(packet, errors)
    return _validation_result(packet_path, schema_path, packet, errors)


def _validate_scalar_fields(
    packet: dict[str, Any],
    checklist: dict[str, Any],
    closure_plan: dict[str, Any],
    readiness: dict[str, Any],
    errors: list[str],
) -> None:
    expected_closure_actions = _expected_closure_actions_from_checklist(checklist, errors)
    closure_action_count = _closure_plan_int(closure_plan, "total_action_count", errors)
    approval_action_count = _closure_plan_int(closure_plan, "approval_required_action_count", errors)
    if (
        expected_closure_actions is not None
        and closure_action_count is not None
        and expected_closure_actions != closure_action_count
    ):
        errors.append("operator checklist aggregate total_action_count does not match closure plan")
    expected_status = (
        "ready_for_final_validation" if readiness.get("ready") is True else "blocked_until_live_evidence"
    )
    expected_promotion = "ready" if readiness.get("ready") is True else "blocked"
    expected_scalars: dict[str, Any] = {
        "schema_version": 1,
        "packet_id": "general-agent-promotion-handoff-v1",
        "status": expected_status,
        "readiness_level": readiness.get("readiness_level"),
        "capability_capsules": readiness.get("capsule_count"),
        "governed_capabilities": readiness.get("capability_count"),
        "production_promotion": expected_promotion,
    }
    if closure_action_count is not None:
        expected_scalars["aggregate_closure_actions"] = closure_action_count
    if approval_action_count is not None:
        expected_scalars["approval_required_actions"] = approval_action_count
    for field_name, expected_value in expected_scalars.items():
        if packet.get(field_name) != expected_value:
            errors.append(f"{field_name} must be {expected_value!r}")


def _expected_closure_actions_from_checklist(
    checklist: dict[str, Any],
    errors: list[str],
) -> int | None:
    steps = checklist.get("required_commands", checklist.get("steps"))
    if not isinstance(steps, list):
        errors.append("operator checklist required_commands must be a list")
        return None
    for step in steps:
        if not isinstance(step, dict) or step.get("step_id") != "validate_aggregate_closure_plan":
            continue
        evidence_items = step.get("required_evidence")
        if not isinstance(evidence_items, list):
            errors.append("validate_aggregate_closure_plan required_evidence must be a list")
            return None
        for item in evidence_items:
            text = str(item)
            prefix = "general_agent_promotion_closure_plan.json total_action_count="
            if text.startswith(prefix):
                raw_count = text.removeprefix(prefix)
                try:
                    return int(raw_count)
                except ValueError:
                    errors.append("operator checklist total_action_count must be an integer")
                    return None
        errors.append("operator checklist missing aggregate total_action_count evidence")
        return None
    errors.append("operator checklist missing validate_aggregate_closure_plan step")
    return None


def _validate_required_sets(
    packet: dict[str, Any],
    closure_plan: dict[str, Any],
    readiness: dict[str, Any],
    errors: list[str],
) -> None:
    _require_exact_set(
        packet,
        "open_blockers",
        frozenset(str(blocker) for blocker in readiness.get("blockers", ())),
        errors,
    )
    _require_exact_set(
        packet,
        "approval_required_blockers",
        _approval_blockers_from_closure_plan(closure_plan, errors),
        errors,
    )
    _require_superset(packet, "required_validation_reports", REQUIRED_VALIDATION_REPORTS, errors)
    _require_superset(packet, "operator_sequence", REQUIRED_SEQUENCE_ITEMS, errors)
    open_blockers = packet.get("open_blockers", [])
    approval_blockers = packet.get("approval_required_blockers", [])
    if isinstance(open_blockers, list) and packet.get("production_promotion") == "ready" and open_blockers:
        errors.append("production_promotion cannot be ready while open_blockers are present")
    if isinstance(approval_blockers, list) and len(approval_blockers) != packet.get("approval_required_actions"):
        errors.append("approval_required_actions does not match approval_required_blockers length")


def _validate_entry_points(packet: dict[str, Any], errors: list[str]) -> None:
    entry_points = packet.get("entry_points", {})
    if not isinstance(entry_points, dict):
        errors.append("entry_points must be an object")
        return
    for key, expected_value in REQUIRED_ENTRY_POINTS.items():
        if entry_points.get(key) != expected_value:
            errors.append(f"entry_points.{key} must be {expected_value}")


def _validate_terminal_proof(packet: dict[str, Any], errors: list[str]) -> None:
    terminal_command = str(packet.get("terminal_proof_command", ""))
    for token in (
        "validate_general_agent_promotion.py",
        "--strict",
        "--output",
        ".change_assurance/general_agent_promotion_readiness.json",
    ):
        if token not in terminal_command:
            errors.append(f"terminal_proof_command missing token {token}")


def _load_or_derive_closure_plan(
    path: Path | None,
    errors: list[str],
    *,
    adapter_evidence_path: Path | None,
    adapter_blockers: tuple[str, ...],
    production_blockers: tuple[str, ...],
) -> dict[str, Any]:
    if path is not None and path.exists():
        return _load_json_object(path, "aggregate closure plan", errors)
    return _derive_closure_plan_or_error(
        errors,
        adapter_evidence_path=adapter_evidence_path,
        adapter_blockers=adapter_blockers,
        production_blockers=production_blockers,
    )


def _derive_closure_plan_or_error(
    errors: list[str],
    *,
    adapter_evidence_path: Path | None,
    adapter_blockers: tuple[str, ...],
    production_blockers: tuple[str, ...],
) -> dict[str, Any]:
    try:
        return _derive_current_closure_plan(
            adapter_evidence_path=adapter_evidence_path,
            adapter_blockers=adapter_blockers,
            production_blockers=production_blockers,
        )
    except (ImportError, OSError, TypeError, ValueError) as exc:
        errors.append(f"aggregate closure plan could not be derived: {exc.__class__.__name__}")
        return {}


def _derive_current_closure_plan(
    *,
    adapter_evidence_path: Path | None,
    adapter_blockers: tuple[str, ...],
    production_blockers: tuple[str, ...],
) -> dict[str, Any]:
    from scripts.collect_capability_adapter_evidence import collect_capability_adapter_evidence
    from scripts.plan_capability_adapter_closure import plan_capability_adapter_closure
    from scripts.plan_deployment_publication_closure import plan_deployment_publication_closure
    from scripts.plan_general_agent_promotion_closure import plan_general_agent_promotion_closure
    from scripts.produce_capability_improvement_portfolio import produce_capability_improvement_portfolio
    from scripts.validate_deployment_publication_closure import (
        validate_deployment_publication_closure_report,
        write_deployment_publication_closure_validation_report,
    )

    with tempfile.TemporaryDirectory(prefix="mullu-handoff-closure-") as raw_tmp_dir:
        tmp_dir = Path(raw_tmp_dir)
        readiness_path = tmp_dir / "general_agent_promotion_readiness.json"
        derived_adapter_evidence_path = tmp_dir / "capability_adapter_evidence.json"
        adapter_plan_path = tmp_dir / "capability_adapter_closure_plan.json"
        deployment_closure_validation_path = tmp_dir / "deployment_publication_closure_validation.json"
        deployment_plan_path = tmp_dir / "deployment_publication_closure_plan.json"
        dns_target_receipt_path = tmp_dir / "gateway_dns_target_binding_receipt.json"
        dns_resolution_receipt_path = tmp_dir / "gateway_dns_resolution_receipt.json"
        upstream_blocker_receipt_path = tmp_dir / "deployment_upstream_blocker_receipt.json"
        portfolio_path = tmp_dir / "capability_improvement_portfolio.json"

        if adapter_evidence_path is None and adapter_blockers:
            _write_json_payload(
                derived_adapter_evidence_path,
                _packet_blocked_adapter_evidence_payload(),
            )
        elif adapter_evidence_path is None:
            _write_json_payload(
                derived_adapter_evidence_path,
                collect_capability_adapter_evidence(
                    browser_receipt_path=tmp_dir / "browser_live_receipt.absent.json",
                    document_receipt_path=tmp_dir / "document_live_receipt.absent.json",
                    voice_receipt_path=tmp_dir / "voice_live_receipt.absent.json",
                    email_calendar_receipt_path=tmp_dir / "email_calendar_live_receipt.absent.json",
                    clock=lambda: "2026-05-01T12:00:00+00:00",
                    env_reader=lambda _name: None,
                ).as_dict(),
            )
        else:
            derived_adapter_evidence_path = adapter_evidence_path
        readiness_payload = _readiness_payload_with_packet_blockers(
            validate_general_agent_promotion(
                repo_root=REPO_ROOT,
                adapter_evidence_path=derived_adapter_evidence_path,
            ).as_dict(),
            adapter_blockers=adapter_blockers,
            production_blockers=production_blockers,
        )
        _write_json_payload(readiness_path, readiness_payload)
        _write_json_payload(
            adapter_plan_path,
            plan_capability_adapter_closure(evidence_path=derived_adapter_evidence_path).as_dict(),
        )
        write_deployment_publication_closure_validation_report(
            validate_deployment_publication_closure_report(),
            deployment_closure_validation_path,
        )
        _write_json_payload(
            upstream_blocker_receipt_path,
            {
                "api_provisioning_allowed": False,
                "dns_publication_allowed": False,
                "ready": False,
                "upstream_state": "AwaitingEvidence",
            },
        )
        _write_json_payload(
            dns_target_receipt_path,
            {
                "binding_state": "bound",
                "gateway_host": "api.mullusi.com",
                "provider": "derived-handoff-fixture",
                "ready": True,
                "record_type": "CNAME",
                "target": "gateway-origin.example.net",
                "target_kind": "hostname",
            },
        )
        _write_json_payload(
            dns_resolution_receipt_path,
            {
                "addresses": ["203.0.113.10"],
                "host": "api.mullusi.com",
                "resolved": True,
            },
        )
        _write_json_payload(
            deployment_plan_path,
            plan_deployment_publication_closure(
                readiness_path=readiness_path,
                upstream_blocker_receipt_path=upstream_blocker_receipt_path,
                dns_target_binding_receipt_path=dns_target_receipt_path,
                dns_resolution_receipt_path=dns_resolution_receipt_path,
                deployment_publication_closure_validation_path=deployment_closure_validation_path,
            ).as_dict(),
        )
        portfolio_run = produce_capability_improvement_portfolio(output_path=portfolio_path)
        if not portfolio_run.passed:
            raise ValueError("capability improvement portfolio derivation failed")
        return plan_general_agent_promotion_closure(
            readiness_path=readiness_path,
            adapter_plan_path=adapter_plan_path,
            deployment_plan_path=deployment_plan_path,
            portfolio_plan_path=portfolio_path,
        ).as_dict()


def _write_json_payload(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left == right


def _require_superset(
    packet: dict[str, Any],
    field_name: str,
    required_values: frozenset[str],
    errors: list[str],
) -> None:
    observed = packet.get(field_name, [])
    if not isinstance(observed, list):
        errors.append(f"{field_name} must be a list")
        return
    missing = sorted(required_values - {str(item) for item in observed})
    if missing:
        errors.append(f"{field_name} missing {missing}")


def _require_exact_set(
    packet: dict[str, Any],
    field_name: str,
    required_values: frozenset[str],
    errors: list[str],
) -> None:
    observed = packet.get(field_name, [])
    if not isinstance(observed, list):
        errors.append(f"{field_name} must be a list")
        return
    observed_values = {str(item) for item in observed}
    missing = sorted(required_values - observed_values)
    unexpected = sorted(observed_values - required_values)
    if missing:
        errors.append(f"{field_name} missing {missing}")
    if unexpected:
        errors.append(f"{field_name} has unexpected {unexpected}")


def _approval_blockers_from_closure_plan(
    closure_plan: dict[str, Any],
    errors: list[str],
) -> frozenset[str]:
    actions = closure_plan.get("actions", [])
    if not isinstance(actions, list):
        errors.append("aggregate closure plan actions must be a list")
        return frozenset()
    blockers: set[str] = set()
    for action in actions:
        if not isinstance(action, dict):
            errors.append("aggregate closure plan actions entries must be objects")
            continue
        if action.get("approval_required") is not True:
            continue
        blocker = str(action.get("blocker", "")).strip()
        if not blocker:
            errors.append("approval-required closure action must name blocker")
            continue
        blockers.add(blocker)
    return frozenset(blockers)


def _closure_plan_int(
    closure_plan: dict[str, Any],
    field_name: str,
    errors: list[str],
) -> int | None:
    value = closure_plan.get(field_name)
    if isinstance(value, int) and value >= 0:
        return value
    errors.append(f"aggregate closure plan {field_name} must be a non-negative integer")
    return None


def _evaluate_promotion_readiness(
    errors: list[str],
    *,
    adapter_evidence_path: Path | None,
    adapter_blockers: tuple[str, ...],
    production_blockers: tuple[str, ...],
) -> dict[str, Any]:
    try:
        readiness = validate_general_agent_promotion(
            repo_root=REPO_ROOT,
            adapter_evidence_path=adapter_evidence_path,
        ).as_dict()
        return _readiness_payload_with_packet_blockers(
            readiness,
            adapter_blockers=adapter_blockers,
            production_blockers=production_blockers,
        )
    except Exception:  # noqa: BLE001
        errors.append("promotion readiness could not be evaluated")
        return {
            "ready": False,
            "readiness_level": "unknown",
            "capability_count": None,
            "capsule_count": None,
            "blockers": (),
        }


def _readiness_payload_with_packet_blockers(
    readiness: dict[str, Any],
    *,
    adapter_blockers: tuple[str, ...],
    production_blockers: tuple[str, ...],
) -> dict[str, Any]:
    """Return a readiness payload that preserves explicit handoff blockers."""
    packet_blockers = (*adapter_blockers, *production_blockers)
    if not packet_blockers:
        return readiness
    effective = dict(readiness)
    observed_readiness_blockers = [str(item) for item in readiness.get("blockers", ())]
    blockers = list(dict.fromkeys([*packet_blockers, *observed_readiness_blockers]))
    effective["ready"] = False
    effective["readiness_level"] = PRODUCTION_BLOCKED_READINESS_LEVEL
    effective["blockers"] = blockers
    return effective


def _adapter_promotion_blockers_from_packet(packet: dict[str, Any]) -> tuple[str, ...]:
    """Return adapter blockers the packet intentionally keeps open."""
    if (
        packet.get("status") != "blocked_until_live_evidence"
        and packet.get("production_promotion") != "blocked"
    ):
        return ()
    observed_blockers = packet.get("open_blockers", [])
    if not isinstance(observed_blockers, list):
        return ()
    observed = {str(blocker) for blocker in observed_blockers} & ADAPTER_PROMOTION_BLOCKERS
    return tuple(blocker for blocker in ADAPTER_PROMOTION_BLOCKER_ORDER if blocker in observed)


def _production_promotion_blockers_from_packet(packet: dict[str, Any]) -> tuple[str, ...]:
    """Return deployment/public-health blockers the packet intentionally keeps open."""
    if (
        packet.get("status") != "blocked_until_live_evidence"
        and packet.get("production_promotion") != "blocked"
    ):
        return ()
    observed_blockers = packet.get("open_blockers", [])
    if not isinstance(observed_blockers, list):
        return ()
    observed = {str(blocker) for blocker in observed_blockers} & PRODUCTION_PROMOTION_BLOCKERS
    return tuple(blocker for blocker in PRODUCTION_PROMOTION_BLOCKER_ORDER if blocker in observed)


def _adapter_evidence_path_for_packet(
    packet: dict[str, Any],
    *,
    explicit_path: Path | None,
) -> Path | None:
    if explicit_path is not None:
        return explicit_path
    if (
        packet.get("status") == "ready_for_final_validation"
        or packet.get("production_promotion") == "ready"
    ) and DEFAULT_CLOSED_ADAPTER_EVIDENCE.exists():
        return DEFAULT_CLOSED_ADAPTER_EVIDENCE
    open_blockers = packet.get("open_blockers", [])
    observed_open_blockers = (
        {str(blocker) for blocker in open_blockers}
        if isinstance(open_blockers, list)
        else set()
    )
    if (
        ADAPTER_PROMOTION_BLOCKERS.intersection(observed_open_blockers)
        and _adapter_evidence_is_open(DEFAULT_ADAPTER_EVIDENCE)
    ):
        return DEFAULT_ADAPTER_EVIDENCE
    if (
        packet.get("readiness_level") == "pilot-governed-core"
        and isinstance(open_blockers, list)
        and ADAPTER_PROMOTION_BLOCKERS.isdisjoint(observed_open_blockers)
        and DEFAULT_CLOSED_ADAPTER_EVIDENCE.exists()
    ):
        return DEFAULT_CLOSED_ADAPTER_EVIDENCE
    return None


def _adapter_evidence_is_open(path: Path) -> bool:
    """Return true when adapter evidence exists and still reports blockers."""
    if not path.exists():
        return False
    try:
        payload = _loads_strict_json(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    if not isinstance(payload, dict):
        return False
    return payload.get("ready") is not True and bool(payload.get("blockers"))


def _packet_blocked_adapter_evidence_payload() -> dict[str, Any]:
    """Return deterministic adapter evidence for the static blocked handoff packet."""
    return {
        "adapters": [
            {
                "adapter_id": "browser.playwright",
                "blockers": [],
                "status": "closed",
            },
            {
                "adapter_id": "document.production_parsers",
                "blockers": [],
                "status": "closed",
            },
            {
                "adapter_id": "voice.openai",
                "blockers": [
                    "voice_dependency_missing:OPENAI_API_KEY",
                    "voice_live_evidence_missing",
                ],
                "status": "not_closed",
            },
            {
                "adapter_id": "communication.email_calendar_worker",
                "blockers": [
                    "email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN",
                    "email_calendar_live_evidence_missing",
                ],
                "status": "not_closed",
            },
        ],
        "blockers": list(PACKET_BLOCKED_ADAPTER_EVIDENCE_BLOCKERS),
        "checked_at": "2026-05-01T12:00:00+00:00",
        "ready": False,
        "report_id": "capability-adapter-evidence-packet-handoff-blocked",
    }


def _validation_result(
    packet_path: Path,
    schema_path: Path,
    packet: dict[str, Any],
    errors: list[str],
) -> PromotionHandoffPacketValidation:
    open_blockers = packet.get("open_blockers", ())
    approval_blockers = packet.get("approval_required_blockers", ())
    return PromotionHandoffPacketValidation(
        valid=not errors,
        packet_id=str(packet.get("packet_id", "")),
        packet_path=str(packet_path),
        schema_path=str(schema_path),
        open_blocker_count=len(open_blockers) if isinstance(open_blockers, list) else 0,
        approval_required_count=len(approval_blockers) if isinstance(approval_blockers, list) else 0,
        errors=tuple(errors),
    )


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = _loads_strict_json(path.read_text(encoding="utf-8"))
    except OSError:
        errors.append(f"{label} could not be read")
        return {}
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} must be JSON")
        return {}
    if not isinstance(parsed, dict):
        errors.append(f"{label} root must be an object")
        return {}
    return parsed


def _loads_strict_json(raw: str) -> Any:
    return json.loads(raw, parse_constant=_reject_json_constant)


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse promotion handoff packet validation arguments."""
    parser = argparse.ArgumentParser(description="Validate general-agent promotion handoff packet.")
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--checklist", default=str(DEFAULT_CHECKLIST))
    parser.add_argument(
        "--closure-plan",
        default="",
        help=(
            "Optional aggregate closure plan artifact to validate against. "
            "When omitted, the expected closure plan is derived from current governed sources."
        ),
    )
    parser.add_argument(
        "--adapter-evidence",
        default="",
        help=(
            "Optional adapter evidence report used for readiness and derived closure-plan validation. "
            "Ready packets default to the tracked redacted live-closed evidence fixture."
        ),
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for promotion handoff packet validation."""
    args = parse_args(argv)
    result = validate_general_agent_promotion_handoff_packet(
        packet_path=Path(args.packet),
        schema_path=Path(args.schema),
        checklist_path=Path(args.checklist),
        closure_plan_path=Path(args.closure_plan) if str(args.closure_plan).strip() else None,
        adapter_evidence_path=Path(args.adapter_evidence) if str(args.adapter_evidence).strip() else None,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"general-agent promotion handoff packet ok blockers={result.open_blocker_count}")
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
