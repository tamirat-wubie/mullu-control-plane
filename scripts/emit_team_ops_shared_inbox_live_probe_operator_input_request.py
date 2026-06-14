#!/usr/bin/env python3
"""Emit missing operator inputs for a TeamOps shared inbox live probe.

Purpose: translate a TeamOps live-probe authority receipt into a public-safe
operator input request before any Gmail connector call is attempted.
Governance scope: TeamOps probe authority, handoff readiness, approval refs,
source receipt validation, external-effect separation, and secret redaction.
Dependencies: schemas/team_ops_shared_inbox_live_probe_operator_input_request.schema.json
and scripts.validate_team_ops_shared_inbox_live_probe_authority.
Invariants:
  - This emitter never calls Gmail, reads a mailbox, drafts or sends a message,
    mutates provider state, or reads credential values.
  - Missing authority, handoff, or approval evidence remains AwaitingEvidence.
  - Invalid authority evidence is GovernanceBlocked.
  - Operator-visible output contains binding names and artifact refs only.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402
from scripts.validate_team_ops_shared_inbox_live_probe_authority import (  # noqa: E402
    DEFAULT_AUTHORITY,
    validate_team_ops_shared_inbox_live_probe_authority,
)


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_live_probe_operator_input_request.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_live_probe_operator_input_request.json"
BLOCKED_ACTIONS = (
    "team_ops_shared_inbox_live_probe",
    "external_provider_call",
    "shared_inbox_message_read",
    "external_message_send",
    "team_ops_production_readiness_claim",
)


@dataclass(frozen=True, slots=True)
class TeamOpsLiveProbeOperatorInput:
    """One missing input required before the TeamOps read-only probe may run."""

    input_id: str
    blocker: str
    input_kind: str
    required_names: tuple[str, ...]
    current_state: str
    evidence_source: str
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready operator input."""

        payload = asdict(self)
        payload["required_names"] = list(self.required_names)
        return payload


@dataclass(frozen=True, slots=True)
class TeamOpsLiveProbeOperatorInputRequest:
    """Public-safe TeamOps live-probe operator input request."""

    request_id: str
    authority_id: str
    ready: bool
    probe_allowed: bool
    authority_validation_ok: bool
    solver_outcome: str
    proof_state: str
    required_inputs: tuple[TeamOpsLiveProbeOperatorInput, ...]
    blocked_actions: tuple[str, ...]
    source_artifacts: dict[str, str]
    allowed_probe_summary: dict[str, Any]
    no_secret_values_serialized: bool
    live_probe_executed: bool
    external_provider_call_performed: bool
    external_mailbox_write_performed: bool
    external_message_sent: bool
    provider_mutation_performed: bool
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready request payload."""

        return {
            "request_id": self.request_id,
            "authority_id": self.authority_id,
            "ready": self.ready,
            "probe_allowed": self.probe_allowed,
            "authority_validation_ok": self.authority_validation_ok,
            "solver_outcome": self.solver_outcome,
            "proof_state": self.proof_state,
            "required_inputs": [item.as_dict() for item in self.required_inputs],
            "blocked_actions": list(self.blocked_actions),
            "source_artifacts": dict(self.source_artifacts),
            "allowed_probe_summary": dict(self.allowed_probe_summary),
            "no_secret_values_serialized": self.no_secret_values_serialized,
            "live_probe_executed": self.live_probe_executed,
            "external_provider_call_performed": self.external_provider_call_performed,
            "external_mailbox_write_performed": self.external_mailbox_write_performed,
            "external_message_sent": self.external_message_sent,
            "provider_mutation_performed": self.provider_mutation_performed,
            "next_action": self.next_action,
        }


def emit_team_ops_live_probe_operator_input_request(
    *,
    authority_path: Path = DEFAULT_AUTHORITY,
    schema_path: Path = DEFAULT_SCHEMA,
) -> TeamOpsLiveProbeOperatorInputRequest:
    """Build one TeamOps live-probe operator input request from authority."""

    authority = _load_json_object(authority_path, "TeamOps shared inbox live-probe authority")
    authority_validation = validate_team_ops_shared_inbox_live_probe_authority(
        authority_path=authority_path,
    )
    required_inputs = _derive_required_inputs(authority, authority_validation.errors)
    authority_validation_ok = authority_validation.ok
    ready = authority_validation_ok and authority.get("read_only_probe_allowed") is True
    probe_allowed = ready and not required_inputs
    request = TeamOpsLiveProbeOperatorInputRequest(
        request_id=_request_id(authority, required_inputs, authority_validation_ok),
        authority_id=str(authority.get("authority_id", "")),
        ready=ready,
        probe_allowed=probe_allowed,
        authority_validation_ok=authority_validation_ok,
        solver_outcome=_solver_outcome(ready=ready, authority_validation_ok=authority_validation_ok),
        proof_state=_proof_state(ready=ready, authority_validation_ok=authority_validation_ok),
        required_inputs=required_inputs,
        blocked_actions=() if probe_allowed else BLOCKED_ACTIONS,
        source_artifacts={
            "team_ops_shared_inbox_live_probe_authority": _artifact_ref(authority_path),
        },
        allowed_probe_summary=_allowed_probe_summary(authority.get("allowed_probe", {})),
        no_secret_values_serialized=True,
        live_probe_executed=False,
        external_provider_call_performed=False,
        external_mailbox_write_performed=False,
        external_message_sent=False,
        provider_mutation_performed=False,
        next_action=_next_action(required_inputs, probe_allowed),
    )
    _assert_redacted(request.as_dict())
    _validate_request_against_schema(request, schema_path)
    return request


def write_team_ops_live_probe_operator_input_request(
    request: TeamOpsLiveProbeOperatorInputRequest,
    output_path: Path,
) -> Path:
    """Write one TeamOps live-probe operator input request."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(request.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _derive_required_inputs(
    authority: Mapping[str, Any],
    authority_validation_errors: tuple[str, ...],
) -> tuple[TeamOpsLiveProbeOperatorInput, ...]:
    inputs: list[TeamOpsLiveProbeOperatorInput] = []
    if authority_validation_errors:
        inputs.append(
            _operator_input(
                blocker="authority_validation_failed",
                input_kind="valid_authority_receipt",
                required_names=("team_ops_shared_inbox_live_probe_authority",),
                current_state="present_invalid",
                next_action=(
                    "regenerate and validate the TeamOps live-probe authority receipt before running the probe"
                ),
            )
        )
    blocked_until = authority.get("blocked_until", [])
    blockers = blocked_until if isinstance(blocked_until, list) else []
    for blocker_value in blockers:
        blocker = str(blocker_value)
        if blocker == "team_ops_handoff_missing":
            inputs.append(
                _operator_input(
                    blocker=blocker,
                    input_kind="source_handoff_receipt",
                    required_names=("team_ops_shared_inbox_operator_handoff",),
                    current_state="missing",
                    next_action=(
                        "emit the TeamOps shared inbox operator handoff receipt, then rerun live-probe authority"
                    ),
                )
            )
        elif blocker.startswith("team_ops_handoff_invalid:"):
            inputs.append(
                _operator_input(
                    blocker=blocker,
                    input_kind="valid_handoff_receipt",
                    required_names=("team_ops_shared_inbox_operator_handoff",),
                    current_state="present_invalid",
                    next_action=(
                        "fix the TeamOps handoff receipt validation errors, then rerun live-probe authority"
                    ),
                )
            )
        elif blocker == "team_ops_handoff_not_ready_for_live_probe":
            inputs.append(
                _operator_input(
                    blocker=blocker,
                    input_kind="handoff_readiness_evidence",
                    required_names=("team_ops_handoff_readiness_evidence",),
                    current_state="awaiting_evidence",
                    next_action=(
                        "close TeamOps handoff readiness witnesses and rerun the authority receipt"
                    ),
                )
            )
        elif blocker == "probe_approval_ref":
            inputs.append(
                _operator_input(
                    blocker=blocker,
                    input_kind="probe_approval_ref",
                    required_names=("MULLU_TEAM_OPS_LIVE_PROBE_APPROVAL_REF",),
                    current_state="missing",
                    next_action=(
                        "bind MULLU_TEAM_OPS_LIVE_PROBE_APPROVAL_REF outside this report, then rerun authority"
                    ),
                )
            )
        elif blocker == "approval_binding_missing":
            inputs.append(
                _operator_input(
                    blocker=blocker,
                    input_kind="approval_binding_receipt",
                    required_names=("team_ops_shared_inbox_live_probe_approval_binding",),
                    current_state="missing",
                    next_action=(
                        "emit the TeamOps live-probe approval binding receipt, then rerun authority"
                    ),
                )
            )
        elif blocker.startswith("approval_binding_invalid:"):
            inputs.append(
                _operator_input(
                    blocker=blocker,
                    input_kind="valid_approval_binding_receipt",
                    required_names=("team_ops_shared_inbox_live_probe_approval_binding",),
                    current_state="present_invalid",
                    next_action=(
                        "fix the TeamOps approval binding receipt validation errors, then rerun authority"
                    ),
                )
            )
        elif blocker == "approval_binding_not_ready":
            inputs.append(
                _operator_input(
                    blocker=blocker,
                    input_kind="approval_binding_readiness_evidence",
                    required_names=("team_ops_shared_inbox_live_probe_approval_binding",),
                    current_state="awaiting_evidence",
                    next_action=(
                        "close TeamOps approval binding evidence, then rerun live-probe authority"
                    ),
                )
            )
    return tuple(_dedupe_inputs(inputs))


def _operator_input(
    *,
    blocker: str,
    input_kind: str,
    required_names: tuple[str, ...],
    current_state: str,
    next_action: str,
) -> TeamOpsLiveProbeOperatorInput:
    material = {
        "blocker": blocker,
        "input_kind": input_kind,
        "required_names": list(required_names),
        "current_state": current_state,
        "evidence_source": "team_ops_shared_inbox_live_probe_authority",
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return TeamOpsLiveProbeOperatorInput(
        input_id=f"teamops-live-probe-input-{digest[:12]}",
        blocker=blocker,
        input_kind=input_kind,
        required_names=required_names,
        current_state=current_state,
        evidence_source="team_ops_shared_inbox_live_probe_authority",
        next_action=next_action,
    )


def _dedupe_inputs(
    inputs: list[TeamOpsLiveProbeOperatorInput],
) -> tuple[TeamOpsLiveProbeOperatorInput, ...]:
    observed: set[str] = set()
    deduped: list[TeamOpsLiveProbeOperatorInput] = []
    for item in inputs:
        if item.input_id not in observed:
            observed.add(item.input_id)
            deduped.append(item)
    return tuple(deduped)


def _allowed_probe_summary(value: Any) -> dict[str, Any]:
    allowed_probe = value if isinstance(value, Mapping) else {}
    return {
        "probe_id": str(allowed_probe.get("probe_id", "team_ops.shared_inbox.read_only_probe")),
        "capabilities_used": [
            str(capability) for capability in allowed_probe.get("capabilities_used", ["email.read"])
        ],
        "query": str(allowed_probe.get("query", "newer_than:1d")),
        "max_message_count": int(allowed_probe.get("max_message_count", 1)),
        "read_only": allowed_probe.get("read_only") is True,
        "draft_allowed": allowed_probe.get("draft_allowed") is True,
        "external_send_allowed": allowed_probe.get("external_send_allowed") is True,
    }


def _solver_outcome(*, ready: bool, authority_validation_ok: bool) -> str:
    if ready:
        return "SolvedVerified"
    if not authority_validation_ok:
        return "GovernanceBlocked"
    return "AwaitingEvidence"


def _proof_state(*, ready: bool, authority_validation_ok: bool) -> str:
    if ready:
        return "Pass"
    if not authority_validation_ok:
        return "Fail"
    return "Unknown"


def _next_action(
    required_inputs: tuple[TeamOpsLiveProbeOperatorInput, ...],
    probe_allowed: bool,
) -> str:
    if probe_allowed:
        return "run the TeamOps shared inbox read-only live probe and validate its receipt"
    if required_inputs:
        return required_inputs[0].next_action
    return "inspect TeamOps live-probe authority blockers"


def _request_id(
    authority: Mapping[str, Any],
    required_inputs: tuple[TeamOpsLiveProbeOperatorInput, ...],
    authority_validation_ok: bool,
) -> str:
    material = {
        "authority_id": authority.get("authority_id", ""),
        "read_only_probe_allowed": authority.get("read_only_probe_allowed", False),
        "authority_validation_ok": authority_validation_ok,
        "required_input_ids": [item.input_id for item in required_inputs],
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return f"teamops-shared-inbox-live-probe-input-request-{digest[:16]}"


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except OSError as exc:
        raise RuntimeError(f"{label} file missing: {path}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"{label} JSON parse failed") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} JSON root must be an object")
    return payload


def _artifact_ref(path: Path) -> str:
    label = path.as_posix().replace("\\", "/")
    if not path.is_absolute():
        return label
    resolved_path = path.resolve(strict=False)
    try:
        relative_label = os.path.relpath(str(resolved_path), str(REPO_ROOT)).replace(os.sep, "/")
    except ValueError:
        return path.name
    if relative_label == "." or relative_label.startswith("../") or relative_label.startswith("..\\"):
        return path.name
    return relative_label


def _assert_redacted(payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, sort_keys=True)
    for marker in SECRET_VALUE_MARKERS:
        if marker.lower() in serialized.lower():
            raise ValueError(f"TeamOps live-probe operator input request contains secret marker: {marker}")


def _validate_request_against_schema(
    request: TeamOpsLiveProbeOperatorInputRequest,
    schema_path: Path,
) -> None:
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, request.as_dict())
    if errors:
        raise RuntimeError(f"TeamOps live-probe operator input request schema validation failed: {errors}")


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps live-probe operator input request arguments."""

    parser = argparse.ArgumentParser(description="Emit TeamOps live-probe operator input request.")
    parser.add_argument("--authority", default=str(DEFAULT_AUTHORITY))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps live-probe operator input request emission."""

    args = parse_args(argv)
    try:
        request = emit_team_ops_live_probe_operator_input_request(
            authority_path=Path(args.authority),
            schema_path=Path(args.schema),
        )
        write_team_ops_live_probe_operator_input_request(request, Path(args.output))
    except (RuntimeError, ValueError) as exc:
        if args.json:
            print(
                json.dumps(
                    {
                        "error": str(exc),
                        "probe_allowed": False,
                        "request_written": False,
                        "solver_outcome": "AwaitingEvidence",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(f"TeamOps live-probe operator input request failed: {exc}")
        return 1
    if args.json:
        print(json.dumps(request.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"TeamOps live-probe operator input request written: {request.request_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
