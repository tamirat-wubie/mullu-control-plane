#!/usr/bin/env python3
"""Validate TeamOps shared inbox live-probe approval bindings.

Purpose: prove a TeamOps live-probe approval binding is schema-valid,
redacted, and truthful about whether authority may consume it.
Governance scope: handoff readiness binding, probe approval evidence,
external effect separation, and secret redaction.
Dependencies: schemas/team_ops_shared_inbox_live_probe_approval_binding.schema.json.
Invariants:
  - Ready bindings require valid handoff readiness and a redacted approval ref.
  - Validation never executes a live probe.
  - Provider calls, mailbox writes, draft creation, and message sends remain
    false in this binding receipt.
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

from scripts.bind_team_ops_shared_inbox_live_probe_approval import DEFAULT_OUTPUT as DEFAULT_BINDING  # noqa: E402
from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_live_probe_approval_binding.schema.json"
DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_live_probe_approval_binding_validation.json"
)
REQUIRED_ALLOWED_CAPABILITIES = frozenset({"email.read", "messaging.thread.read"})


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxLiveProbeApprovalBindingValidation:
    """Validation result for one TeamOps live-probe approval binding."""

    ok: bool
    binding_path: str
    schema_path: str
    status: str
    ready_for_authority_receipt: bool
    blocker_count: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation receipt."""

        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_team_ops_shared_inbox_live_probe_approval_binding(
    *,
    binding_path: Path = DEFAULT_BINDING,
    schema_path: Path = DEFAULT_SCHEMA,
    require_blocked: bool = False,
    require_ready: bool = False,
) -> TeamOpsSharedInboxLiveProbeApprovalBindingValidation:
    """Validate one TeamOps shared inbox live-probe approval binding."""

    errors: list[str] = []
    try:
        schema = _load_schema(schema_path)
    except OSError:
        schema = {}
        errors.append("TeamOps shared inbox live-probe approval binding schema file missing")
    binding = _load_json_object(binding_path, "TeamOps live-probe approval binding", errors)
    if schema and binding:
        errors.extend(_validate_schema_instance(schema, binding))
        _validate_semantics(binding, errors)
        if require_blocked and binding.get("ready_for_authority_receipt") is True:
            errors.append("require blocked: TeamOps live-probe approval binding is ready")
        if require_ready and binding.get("ready_for_authority_receipt") is not True:
            errors.append("require ready: TeamOps live-probe approval binding is not ready")
    return TeamOpsSharedInboxLiveProbeApprovalBindingValidation(
        ok=not errors,
        binding_path=_path_label(binding_path),
        schema_path=_path_label(schema_path),
        status=str(binding.get("status", "")) if binding else "",
        ready_for_authority_receipt=binding.get("ready_for_authority_receipt") is True if binding else False,
        blocker_count=_blocker_count(binding),
        errors=tuple(errors),
    )


def write_team_ops_shared_inbox_live_probe_approval_binding_validation(
    validation: TeamOpsSharedInboxLiveProbeApprovalBindingValidation,
    output_path: Path,
) -> Path:
    """Write one TeamOps live-probe approval binding validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_semantics(binding: dict[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(binding, sort_keys=True)
    for marker in SECRET_VALUE_MARKERS:
        if marker.lower() in serialized.lower():
            errors.append(f"binding must not serialize secret marker: {marker}")

    for field_name in (
        "live_probe_executed",
        "external_provider_call_performed",
        "external_mailbox_write_performed",
        "external_message_sent",
        "provider_mutation_performed",
        "credential_values_disclosed",
        "approval_ref_value_serialized",
    ):
        if binding.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    if binding.get("no_secret_values_serialized") is not True:
        errors.append("no_secret_values_serialized must be true")

    blocked_until = binding.get("blocked_until")
    blocker_entries = blocked_until if isinstance(blocked_until, list) else []
    handoff_validation_ok = binding.get("handoff_validation_ok") is True
    handoff_ready = binding.get("handoff_ready_for_live_probe") is True
    approval_present = binding.get("probe_approval_ref_present") is True
    declared_ready = binding.get("ready_for_authority_receipt") is True
    expected_ready = handoff_validation_ok and handoff_ready and approval_present and not blocker_entries
    if declared_ready is not expected_ready:
        errors.append("ready_for_authority_receipt must equal handoff readiness plus approval without blockers")

    expected_status = "ready_for_authority_receipt" if expected_ready else (
        "awaiting_probe_approval" if handoff_ready else "awaiting_handoff_readiness"
    )
    if binding.get("status") != expected_status:
        errors.append(f"status must be {expected_status}")

    expected_outcome = "SolvedVerified" if expected_ready else (
        "GovernanceBlocked"
        if not handoff_validation_ok and binding.get("source_handoff_id") != "missing"
        else "AwaitingEvidence"
    )
    if binding.get("solver_outcome") != expected_outcome:
        errors.append("solver_outcome must align with approval binding state")

    approval_ref = str(binding.get("probe_approval_ref", ""))
    if declared_ready and not approval_present:
        errors.append("ready binding requires probe_approval_ref_present")
    if declared_ready and not approval_ref.startswith("ref:"):
        errors.append("ready binding requires redacted probe_approval_ref")
    if not approval_present and approval_ref:
        errors.append("missing approval state must not carry probe_approval_ref")
    if approval_present and not approval_ref.startswith("ref:"):
        errors.append("probe_approval_ref must be redacted when present")
    if declared_ready and binding.get("blocked_until"):
        errors.append("ready binding must not list blockers")
    if not declared_ready and not binding.get("blocked_until"):
        errors.append("blocked approval binding must list blocked_until entries")
    if binding.get("effect_classification") != "approval_binding_only":
        errors.append("effect_classification must remain approval_binding_only")

    _validate_allowed_probe_summary(binding.get("allowed_probe_summary", {}), errors)
    _validate_handoff_summary(binding.get("handoff_summary", {}), handoff_ready, errors)
    _validate_source_artifacts(binding.get("source_artifacts", {}), errors)


def _validate_allowed_probe_summary(allowed_probe: Any, errors: list[str]) -> None:
    if not isinstance(allowed_probe, dict):
        errors.append("allowed_probe_summary must be an object")
        return
    if allowed_probe.get("probe_id") != "team_ops.shared_inbox.read_only_probe":
        errors.append("allowed_probe_summary.probe_id must be team_ops.shared_inbox.read_only_probe")
    capabilities = set(allowed_probe.get("capabilities_used", []))
    if capabilities != REQUIRED_ALLOWED_CAPABILITIES:
        errors.append(f"allowed_probe_summary.capabilities_used must be {sorted(REQUIRED_ALLOWED_CAPABILITIES)}")
    for field_name in ("read_only", "requires_approval_ref"):
        if allowed_probe.get(field_name) is not True:
            errors.append(f"allowed_probe_summary.{field_name} must be true")
    for field_name in ("draft_allowed", "external_send_allowed"):
        if allowed_probe.get(field_name) is not False:
            errors.append(f"allowed_probe_summary.{field_name} must be false")
    if not isinstance(allowed_probe.get("max_message_count"), int) or allowed_probe["max_message_count"] > 50:
        errors.append("allowed_probe_summary.max_message_count must be an integer <= 50")


def _validate_handoff_summary(handoff_summary: Any, handoff_ready: bool, errors: list[str]) -> None:
    if not isinstance(handoff_summary, dict):
        errors.append("handoff_summary must be an object")
        return
    if handoff_summary.get("ready_for_live_probe") is not handoff_ready:
        errors.append("handoff_summary.ready_for_live_probe must match binding handoff readiness")
    if handoff_ready and handoff_summary.get("blocker_count") != 0:
        errors.append("ready handoff summary must have blocker_count=0")


def _validate_source_artifacts(source_artifacts: Any, errors: list[str]) -> None:
    if not isinstance(source_artifacts, dict):
        errors.append("source_artifacts must be an object")
        return
    if not source_artifacts.get("team_ops_shared_inbox_operator_handoff"):
        errors.append("source_artifacts.team_ops_shared_inbox_operator_handoff is required")


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


def _blocker_count(binding: dict[str, Any]) -> int:
    blocked_until = binding.get("blocked_until", ())
    return len(blocked_until) if isinstance(blocked_until, list) else 0


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps live-probe approval binding validation arguments."""

    parser = argparse.ArgumentParser(description="Validate TeamOps shared inbox live-probe approval binding.")
    parser.add_argument("--binding", default=str(DEFAULT_BINDING))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-blocked", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps live-probe approval binding validation."""

    args = parse_args(argv)
    validation = validate_team_ops_shared_inbox_live_probe_approval_binding(
        binding_path=Path(args.binding),
        schema_path=Path(args.schema),
        require_blocked=args.require_blocked,
        require_ready=args.require_ready,
    )
    write_team_ops_shared_inbox_live_probe_approval_binding_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("TeamOps shared inbox live-probe approval binding valid")
    else:
        print(f"TeamOps shared inbox live-probe approval binding invalid errors={list(validation.errors)}")
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
