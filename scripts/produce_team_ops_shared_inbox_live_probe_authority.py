#!/usr/bin/env python3
"""Produce a TeamOps shared inbox live-probe authority receipt.

Purpose: decide whether the TeamOps shared inbox handoff may proceed to a
future read-only live probe without executing that probe.
Governance scope: TeamOps assistant authority, Gmail shared inbox evidence,
external-send separation, approval reference handling, and live-probe admission.
Dependencies: scripts.produce_team_ops_shared_inbox_operator_handoff and
scripts.validate_team_ops_shared_inbox_operator_handoff.
Invariants:
  - This producer never calls Gmail, mutates provider state, writes a mailbox,
    drafts or sends a message, or reads credential values.
  - Probe authority requires a schema-valid handoff already ready for live
    probe plus an explicit probe approval reference.
  - Approval references are redacted before serialization.
  - Missing evidence remains AwaitingEvidence; invalid handoff evidence is
    GovernanceBlocked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.produce_team_ops_shared_inbox_operator_handoff import (  # noqa: E402
    DEFAULT_REPOSITORY,
    SECRET_VALUE_MARKERS,
)
from scripts.validate_team_ops_shared_inbox_operator_handoff import (  # noqa: E402
    DEFAULT_HANDOFF,
    validate_team_ops_shared_inbox_operator_handoff,
)


DEFAULT_OUTPUT = WORKSPACE_ROOT / ".change_assurance" / "team_ops_shared_inbox_live_probe_authority.json"
DEFAULT_QUERY = "newer_than:1d"
DEFAULT_MAX_MESSAGE_COUNT = 10
FORBIDDEN_EFFECTS = (
    "external_message_send",
    "draft_creation",
    "mailbox_write",
    "provider_configuration_mutation",
    "secret_value_serialization",
    "cross_tenant_shared_inbox_access",
)
ALLOWED_CAPABILITIES = (
    "email.read",
    "messaging.thread.read",
)


def produce_team_ops_shared_inbox_live_probe_authority(
    *,
    handoff_path: Path = DEFAULT_HANDOFF,
    probe_approval_ref: str = "",
    repository: str = DEFAULT_REPOSITORY,
    query: str = DEFAULT_QUERY,
    max_message_count: int = DEFAULT_MAX_MESSAGE_COUNT,
) -> dict[str, Any]:
    """Return a redacted authority receipt for a future read-only TeamOps probe."""

    handoff = _load_handoff_object(handoff_path)
    validation = validate_team_ops_shared_inbox_operator_handoff(handoff_path=handoff_path)
    handoff_validation_ok = validation.ok
    handoff_ready = handoff_validation_ok and handoff.get("ready_for_live_probe") is True
    probe_authorized = bool(probe_approval_ref.strip())
    redacted_approval_ref = _redacted_ref(probe_approval_ref)
    blocked_until = _blocked_until(
        handoff_exists=handoff_path.exists(),
        handoff_validation_ok=handoff_validation_ok,
        handoff_ready=handoff_ready,
        probe_authorized=probe_authorized,
        validation_errors=validation.errors,
    )
    read_only_probe_allowed = handoff_ready and probe_authorized and not blocked_until
    status = _authority_status(
        handoff_ready=handoff_ready,
        read_only_probe_allowed=read_only_probe_allowed,
    )
    solver_outcome = _solver_outcome(
        handoff_exists=handoff_path.exists(),
        handoff_validation_ok=handoff_validation_ok,
        read_only_probe_allowed=read_only_probe_allowed,
    )
    payload = {
        "authority_id": _stable_authority_id(
            handoff_path=handoff_path,
            source_handoff_id=str(handoff.get("handoff_id", "missing")),
            status=status,
            probe_approval_ref=redacted_approval_ref,
        ),
        "schema_version": 1,
        "status": status,
        "solver_outcome": solver_outcome,
        "repository": repository,
        "workflow_id": "team_ops.shared_inbox_triage",
        "connector_id": "gmail",
        "source_handoff_ref": _workspace_ref(handoff_path),
        "source_handoff_id": str(handoff.get("handoff_id", "missing")),
        "handoff_validation_ok": handoff_validation_ok,
        "handoff_ready_for_live_probe": handoff_ready,
        "probe_authorized": probe_authorized,
        "probe_approval_ref": redacted_approval_ref,
        "read_only_probe_allowed": read_only_probe_allowed,
        "live_probe_executed": False,
        "external_provider_call_performed": False,
        "external_mailbox_write_performed": False,
        "external_message_sent": False,
        "provider_mutation_performed": False,
        "credential_values_disclosed": False,
        "effect_classification": "epistemic_external_observation",
        "allowed_probe": _allowed_probe(query=query, max_message_count=max_message_count),
        "forbidden_effects": list(FORBIDDEN_EFFECTS),
        "handoff_summary": _handoff_summary(handoff, validation.errors),
        "blocked_until": blocked_until,
        "verification_commands": (
            "python scripts\\validate_team_ops_shared_inbox_live_probe_authority.py --require-blocked --json",
            "python scripts\\validate_team_ops_shared_inbox_live_probe_authority.py --require-admitted --json",
            "python -m pytest tests\\test_produce_team_ops_shared_inbox_live_probe_authority.py "
            "tests\\test_validate_team_ops_shared_inbox_live_probe_authority.py -q",
        ),
    }
    _assert_redacted(payload)
    return payload


def write_team_ops_shared_inbox_live_probe_authority(payload: Mapping[str, Any], output_path: Path) -> Path:
    """Write one redacted TeamOps live-probe authority receipt."""

    _assert_redacted(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _load_handoff_object(handoff_path: Path) -> dict[str, Any]:
    if not handoff_path.exists():
        return {}
    try:
        payload = json.loads(handoff_path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _allowed_probe(*, query: str, max_message_count: int) -> dict[str, Any]:
    bounded_count = min(max(1, int(max_message_count)), 50)
    bounded_query = query.strip() or DEFAULT_QUERY
    return {
        "probe_id": "team_ops.shared_inbox.read_only_probe",
        "capabilities_used": list(ALLOWED_CAPABILITIES),
        "query": bounded_query,
        "max_message_count": bounded_count,
        "read_only": True,
        "draft_allowed": False,
        "external_send_allowed": False,
        "requires_approval_ref": True,
    }


def _blocked_until(
    *,
    handoff_exists: bool,
    handoff_validation_ok: bool,
    handoff_ready: bool,
    probe_authorized: bool,
    validation_errors: tuple[str, ...],
) -> list[str]:
    blockers: list[str] = []
    if not handoff_exists:
        blockers.append("team_ops_handoff_missing")
    if handoff_exists and not handoff_validation_ok:
        blockers.extend(f"team_ops_handoff_invalid:{error}" for error in validation_errors)
    if handoff_validation_ok and not handoff_ready:
        blockers.append("team_ops_handoff_not_ready_for_live_probe")
    if not probe_authorized:
        blockers.append("probe_approval_ref")
    return blockers


def _authority_status(*, handoff_ready: bool, read_only_probe_allowed: bool) -> str:
    if read_only_probe_allowed:
        return "admitted_for_read_only_probe"
    if handoff_ready:
        return "awaiting_probe_authority"
    return "awaiting_handoff_readiness"


def _solver_outcome(
    *,
    handoff_exists: bool,
    handoff_validation_ok: bool,
    read_only_probe_allowed: bool,
) -> str:
    if read_only_probe_allowed:
        return "SolvedVerified"
    if handoff_exists and not handoff_validation_ok:
        return "GovernanceBlocked"
    return "AwaitingEvidence"


def _handoff_summary(handoff: Mapping[str, Any], validation_errors: tuple[str, ...]) -> dict[str, Any]:
    blocked_until = handoff.get("blocked_until", ())
    blocker_count = len(blocked_until) if isinstance(blocked_until, list) else 0
    return {
        "status": str(handoff.get("status", "missing")),
        "solver_outcome": str(handoff.get("solver_outcome", "AwaitingEvidence")),
        "ready_for_live_probe": handoff.get("ready_for_live_probe") is True,
        "blocker_count": blocker_count,
        "validation_error_count": len(validation_errors),
    }


def _stable_authority_id(
    *,
    handoff_path: Path,
    source_handoff_id: str,
    status: str,
    probe_approval_ref: str,
) -> str:
    material = {
        "handoff_path": _workspace_ref(handoff_path),
        "source_handoff_id": source_handoff_id,
        "status": status,
        "probe_approval_ref": probe_approval_ref,
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"teamops-shared-inbox-live-probe-authority-{digest}"


def _redacted_ref(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    for marker in SECRET_VALUE_MARKERS:
        if marker.lower() in stripped.lower():
            raise ValueError(f"TeamOps live-probe approval reference contains prohibited secret marker: {marker}")
    return f"ref:{hashlib.sha256(stripped.encode('utf-8')).hexdigest()[:12]}"


def _assert_redacted(payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, sort_keys=True)
    for marker in SECRET_VALUE_MARKERS:
        if marker.lower() in serialized.lower():
            raise ValueError(f"TeamOps live-probe authority contains prohibited secret marker: {marker}")


def _workspace_ref(path: Path) -> str:
    resolved = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return resolved.resolve(strict=False).relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return path.name


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps live-probe authority arguments."""

    parser = argparse.ArgumentParser(description="Produce TeamOps shared inbox live-probe authority receipt.")
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--repo", default=DEFAULT_REPOSITORY)
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--max-message-count", type=int, default=DEFAULT_MAX_MESSAGE_COUNT)
    parser.add_argument(
        "--probe-approval-ref",
        default=os.environ.get("MULLU_TEAM_OPS_LIVE_PROBE_APPROVAL_REF", ""),
    )
    parser.add_argument("--require-admitted", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps shared inbox live-probe authority."""

    args = parse_args(argv)
    payload = produce_team_ops_shared_inbox_live_probe_authority(
        handoff_path=args.handoff,
        probe_approval_ref=args.probe_approval_ref,
        repository=args.repo,
        query=args.query,
        max_message_count=args.max_message_count,
    )
    write_team_ops_shared_inbox_live_probe_authority(payload, args.output)
    if args.json:
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if args.require_admitted and not payload["read_only_probe_allowed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
