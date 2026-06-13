#!/usr/bin/env python3
"""Validate TeamOps shared inbox live-probe authority receipts.

Purpose: prove a TeamOps live-probe authority packet is schema-valid, redacted,
and truthful about whether a read-only live probe may be attempted.
Governance scope: probe authority, external effect separation, handoff
readiness binding, approval evidence, and secret redaction.
Dependencies: schemas/team_ops_shared_inbox_live_probe_authority.schema.json.
Invariants:
  - A packet admitted for probe must include handoff readiness and probe
    approval.
  - Probe-authority validation never executes the probe.
  - Provider calls, mailbox writes, draft creation, and message sends remain
    false in this authority receipt.
  - Secret-shaped values are rejected.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_AUTHORITY = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_live_probe_authority.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_live_probe_authority.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_live_probe_authority_validation.json"
REQUIRED_FORBIDDEN_EFFECTS = frozenset(
    {
        "external_message_send",
        "draft_creation",
        "mailbox_write",
        "provider_configuration_mutation",
        "secret_value_serialization",
        "cross_tenant_shared_inbox_access",
    }
)
REQUIRED_ALLOWED_CAPABILITIES = frozenset({"email.read", "messaging.thread.read"})


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxLiveProbeAuthorityValidation:
    """Validation result for one TeamOps live-probe authority packet."""

    ok: bool
    authority_path: str
    schema_path: str
    status: str
    read_only_probe_allowed: bool
    blocker_count: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation receipt."""

        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_team_ops_shared_inbox_live_probe_authority(
    *,
    authority_path: Path = DEFAULT_AUTHORITY,
    schema_path: Path = DEFAULT_SCHEMA,
    require_blocked: bool = False,
    require_admitted: bool = False,
) -> TeamOpsSharedInboxLiveProbeAuthorityValidation:
    """Validate one TeamOps shared inbox live-probe authority packet."""

    errors: list[str] = []
    try:
        schema = _load_schema(schema_path)
    except OSError:
        schema = {}
        errors.append("TeamOps shared inbox live-probe authority schema file missing")
    authority = _load_json_object(authority_path, "TeamOps live-probe authority", errors)
    if schema and authority:
        errors.extend(_validate_schema_instance(schema, authority))
        _validate_semantics(authority, errors)
        if require_blocked and authority.get("read_only_probe_allowed") is True:
            errors.append("require blocked: TeamOps live-probe authority is admitted")
        if require_admitted and authority.get("read_only_probe_allowed") is not True:
            errors.append("require admitted: TeamOps live-probe authority is not admitted")
    return TeamOpsSharedInboxLiveProbeAuthorityValidation(
        ok=not errors,
        authority_path=_path_label(authority_path),
        schema_path=_path_label(schema_path),
        status=str(authority.get("status", "")) if authority else "",
        read_only_probe_allowed=authority.get("read_only_probe_allowed") is True if authority else False,
        blocker_count=_blocker_count(authority),
        errors=tuple(errors),
    )


def write_team_ops_shared_inbox_live_probe_authority_validation(
    validation: TeamOpsSharedInboxLiveProbeAuthorityValidation,
    output_path: Path,
) -> Path:
    """Write one TeamOps live-probe authority validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_semantics(authority: dict[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(authority, sort_keys=True)
    for marker in SECRET_VALUE_MARKERS:
        if marker.lower() in serialized.lower():
            errors.append(f"authority must not serialize secret marker: {marker}")

    for field_name in (
        "live_probe_executed",
        "external_provider_call_performed",
        "external_mailbox_write_performed",
        "external_message_sent",
        "provider_mutation_performed",
        "credential_values_disclosed",
    ):
        if authority.get(field_name) is not False:
            errors.append(f"{field_name} must be false")

    declared_admitted = authority.get("read_only_probe_allowed") is True
    handoff_ready = authority.get("handoff_ready_for_live_probe") is True
    handoff_validation_ok = authority.get("handoff_validation_ok") is True
    probe_authorized = authority.get("probe_authorized") is True
    blocked_until = authority.get("blocked_until")
    blocker_entries = blocked_until if isinstance(blocked_until, list) else []
    expected_admitted = handoff_validation_ok and handoff_ready and probe_authorized and not blocker_entries
    if declared_admitted is not expected_admitted:
        errors.append("read_only_probe_allowed must equal valid handoff readiness plus probe approval without blockers")
    expected_status = "admitted_for_read_only_probe" if expected_admitted else (
        "awaiting_probe_authority" if handoff_ready else "awaiting_handoff_readiness"
    )
    if authority.get("status") != expected_status:
        errors.append(f"status must be {expected_status}")
    expected_outcome = "SolvedVerified" if expected_admitted else (
        "GovernanceBlocked" if not handoff_validation_ok and authority.get("source_handoff_id") != "missing" else "AwaitingEvidence"
    )
    if authority.get("solver_outcome") != expected_outcome:
        errors.append("solver_outcome must align with probe authority state")
    if declared_admitted and not handoff_validation_ok:
        errors.append("admitted probe requires valid handoff")
    if declared_admitted and not handoff_ready:
        errors.append("admitted probe requires handoff_ready_for_live_probe")
    if declared_admitted and not probe_authorized:
        errors.append("admitted probe requires probe_authorized")
    if declared_admitted and not str(authority.get("probe_approval_ref", "")).startswith("ref:"):
        errors.append("admitted probe requires redacted probe_approval_ref")
    if declared_admitted and authority.get("blocked_until"):
        errors.append("admitted probe must not list blockers")
    if not declared_admitted and not authority.get("blocked_until"):
        errors.append("blocked probe authority must list blocked_until entries")
    if authority.get("effect_classification") != "epistemic_external_observation":
        errors.append("effect_classification must remain epistemic_external_observation")

    _validate_allowed_probe(authority.get("allowed_probe", {}), errors)
    forbidden_effects = set(authority.get("forbidden_effects", []))
    if forbidden_effects != REQUIRED_FORBIDDEN_EFFECTS:
        errors.append(f"forbidden_effects must match TeamOps probe boundaries: observed={sorted(forbidden_effects)}")
    _validate_handoff_summary(authority.get("handoff_summary", {}), handoff_ready, errors)


def _validate_allowed_probe(allowed_probe: Any, errors: list[str]) -> None:
    if not isinstance(allowed_probe, dict):
        errors.append("allowed_probe must be an object")
        return
    if allowed_probe.get("probe_id") != "team_ops.shared_inbox.read_only_probe":
        errors.append("allowed_probe.probe_id must be team_ops.shared_inbox.read_only_probe")
    capabilities = set(allowed_probe.get("capabilities_used", []))
    if capabilities != REQUIRED_ALLOWED_CAPABILITIES:
        errors.append(f"allowed_probe.capabilities_used must be {sorted(REQUIRED_ALLOWED_CAPABILITIES)}")
    for field_name in ("read_only", "requires_approval_ref"):
        if allowed_probe.get(field_name) is not True:
            errors.append(f"allowed_probe.{field_name} must be true")
    for field_name in ("draft_allowed", "external_send_allowed"):
        if allowed_probe.get(field_name) is not False:
            errors.append(f"allowed_probe.{field_name} must be false")
    if not isinstance(allowed_probe.get("max_message_count"), int) or allowed_probe["max_message_count"] > 50:
        errors.append("allowed_probe.max_message_count must be an integer <= 50")


def _validate_handoff_summary(handoff_summary: Any, handoff_ready: bool, errors: list[str]) -> None:
    if not isinstance(handoff_summary, dict):
        errors.append("handoff_summary must be an object")
        return
    if handoff_summary.get("ready_for_live_probe") is not handoff_ready:
        errors.append("handoff_summary.ready_for_live_probe must match authority handoff readiness")
    if handoff_ready and handoff_summary.get("blocker_count") != 0:
        errors.append("ready handoff summary must have blocker_count=0")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _blocker_count(authority: dict[str, Any]) -> int:
    blocked_until = authority.get("blocked_until", ())
    return len(blocked_until) if isinstance(blocked_until, list) else 0


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps live-probe authority validation arguments."""

    parser = argparse.ArgumentParser(description="Validate TeamOps shared inbox live-probe authority.")
    parser.add_argument("--authority", default=str(DEFAULT_AUTHORITY))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--require-blocked", action="store_true")
    parser.add_argument("--require-admitted", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps live-probe authority validation."""

    args = parse_args(argv)
    validation = validate_team_ops_shared_inbox_live_probe_authority(
        authority_path=Path(args.authority),
        schema_path=Path(args.schema),
        require_blocked=args.require_blocked,
        require_admitted=args.require_admitted,
    )
    write_team_ops_shared_inbox_live_probe_authority_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("TeamOps shared inbox live-probe authority valid")
    else:
        print(f"TeamOps shared inbox live-probe authority invalid errors={list(validation.errors)}")
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
