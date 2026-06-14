#!/usr/bin/env python3
"""Emit missing operator inputs for durable Gmail live write evidence.

Purpose: translate Gmail live write blockers into a public-safe operator input
request before any draft, send, or provider mutation can be considered.
Governance scope: Gmail write authority, account binding, source live receipt
freshness refs, approval refs, draft/send split, external-effect separation,
and secret redaction.
Dependencies: schemas/durable_gmail_live_write_operator_input_request.schema.json.
Invariants:
  - This emitter never calls Gmail, creates a draft, sends a message, mutates
    provider state, writes mailbox state, or reads credential values.
  - Live write authority remains blocked even when the operator input packet is
    complete; a separate approval-gated live evidence workflow is required.
  - Operator-visible output contains input names and artifact refs only.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_durable_gmail_oauth_runtime_preflight import matched_secret_marker  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "durable_gmail_live_write_operator_input_request.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "durable_gmail_live_write_operator_input_request.json"
SUPPORTED_OPERATION_FAMILIES = frozenset({"draft_create", "send_with_approval"})
REQUIRED_BLOCKED_ACTIONS = (
    "calendar_authority_claim",
    "external_provider_call",
    "gmail_live_draft_create",
    "gmail_live_send",
    "gmail_write_authority_claim",
    "mailbox_write",
    "production_readiness_claim",
)
EMAIL_ADDRESS_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class DurableGmailLiveWriteOperatorInput:
    """One missing or invalid input for a durable Gmail live write request."""

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
class DurableGmailLiveWriteOperatorInputRequest:
    """Public-safe durable Gmail live write operator input request."""

    request_id: str
    adapter_id: str
    connector_id: str
    mode: str
    operation_family: str
    ready_for_operator_review: bool
    write_action_allowed: bool
    solver_outcome: str
    proof_state: str
    required_inputs: tuple[DurableGmailLiveWriteOperatorInput, ...]
    blocked_actions: tuple[str, ...]
    source_artifacts: dict[str, str]
    operation_summary: dict[str, Any]
    no_secret_values_serialized: bool
    raw_mailbox_address_disclosed: bool
    raw_message_content_disclosed: bool
    live_write_executed: bool
    external_provider_call_performed: bool
    external_mailbox_write_performed: bool
    external_draft_created: bool
    external_send_performed: bool
    provider_mutation_performed: bool
    production_ready_claimed: bool
    write_authority_claimed: bool
    calendar_authority_claimed: bool
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready request payload."""

        return {
            "request_id": self.request_id,
            "adapter_id": self.adapter_id,
            "connector_id": self.connector_id,
            "mode": self.mode,
            "operation_family": self.operation_family,
            "ready_for_operator_review": self.ready_for_operator_review,
            "write_action_allowed": self.write_action_allowed,
            "solver_outcome": self.solver_outcome,
            "proof_state": self.proof_state,
            "required_inputs": [item.as_dict() for item in self.required_inputs],
            "blocked_actions": list(self.blocked_actions),
            "source_artifacts": dict(self.source_artifacts),
            "operation_summary": dict(self.operation_summary),
            "no_secret_values_serialized": self.no_secret_values_serialized,
            "raw_mailbox_address_disclosed": self.raw_mailbox_address_disclosed,
            "raw_message_content_disclosed": self.raw_message_content_disclosed,
            "live_write_executed": self.live_write_executed,
            "external_provider_call_performed": self.external_provider_call_performed,
            "external_mailbox_write_performed": self.external_mailbox_write_performed,
            "external_draft_created": self.external_draft_created,
            "external_send_performed": self.external_send_performed,
            "provider_mutation_performed": self.provider_mutation_performed,
            "production_ready_claimed": self.production_ready_claimed,
            "write_authority_claimed": self.write_authority_claimed,
            "calendar_authority_claimed": self.calendar_authority_claimed,
            "next_action": self.next_action,
        }


def emit_durable_gmail_live_write_operator_input_request(
    *,
    environment: Mapping[str, str] | None = None,
    schema_path: Path = DEFAULT_SCHEMA,
) -> DurableGmailLiveWriteOperatorInputRequest:
    """Build a durable Gmail live write operator input request from bindings."""

    env = dict(os.environ if environment is None else environment)
    operation_family = env.get("MULLU_GMAIL_WRITE_OPERATION_FAMILY", "send_with_approval").strip()
    supported_operation = operation_family in SUPPORTED_OPERATION_FAMILIES
    required_scope_ref = "oauth:gmail.compose" if operation_family == "draft_create" else "oauth:gmail.send"
    required_inputs = _derive_required_inputs(env, operation_family, required_scope_ref)
    ready_for_operator_review = supported_operation and not required_inputs
    request = DurableGmailLiveWriteOperatorInputRequest(
        request_id=_request_id(operation_family, required_inputs, ready_for_operator_review),
        adapter_id="communication.gmail_oauth",
        connector_id="gmail",
        mode="foundation-local",
        operation_family=operation_family or "send_with_approval",
        ready_for_operator_review=ready_for_operator_review,
        write_action_allowed=False,
        solver_outcome=_solver_outcome(supported_operation, ready_for_operator_review),
        proof_state=_proof_state(supported_operation, ready_for_operator_review),
        required_inputs=required_inputs,
        blocked_actions=REQUIRED_BLOCKED_ACTIONS,
        source_artifacts=_source_artifacts(env),
        operation_summary={
            "approval_required": True,
            "draft_send_split_required": True,
            "operator_review_required": True,
            "required_scope_ref": required_scope_ref if supported_operation else "oauth:gmail.send",
        },
        no_secret_values_serialized=True,
        raw_mailbox_address_disclosed=False,
        raw_message_content_disclosed=False,
        live_write_executed=False,
        external_provider_call_performed=False,
        external_mailbox_write_performed=False,
        external_draft_created=False,
        external_send_performed=False,
        provider_mutation_performed=False,
        production_ready_claimed=False,
        write_authority_claimed=False,
        calendar_authority_claimed=False,
        next_action=_next_action(required_inputs, ready_for_operator_review),
    )
    _assert_redacted(request.as_dict())
    _validate_request_against_schema(request, schema_path)
    return request


def write_durable_gmail_live_write_operator_input_request(
    request: DurableGmailLiveWriteOperatorInputRequest,
    output_path: Path,
) -> Path:
    """Write one durable Gmail live write operator input request."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(request.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _derive_required_inputs(
    env: Mapping[str, str],
    operation_family: str,
    required_scope_ref: str,
) -> tuple[DurableGmailLiveWriteOperatorInput, ...]:
    inputs: list[DurableGmailLiveWriteOperatorInput] = []
    if operation_family not in SUPPORTED_OPERATION_FAMILIES:
        inputs.append(
            _operator_input(
                blocker="gmail_write_operation_family_unsupported",
                input_kind="valid_operation_family",
                required_names=("MULLU_GMAIL_WRITE_OPERATION_FAMILY",),
                current_state="present_invalid",
                next_action="set MULLU_GMAIL_WRITE_OPERATION_FAMILY to draft_create or send_with_approval",
            )
        )
    inputs.extend(
        _receipt_ref_input(
            env,
            env_name="MULLU_GMAIL_ACCOUNT_BINDING_RECEIPT_REF",
            input_kind="account_binding_receipt_ref",
            valid_input_kind="valid_account_binding_receipt_ref",
            blocker_prefix="gmail_account_binding_receipt_ref",
            next_action="provide a redacted Gmail account-binding receipt ref before live write review",
        )
    )
    inputs.extend(
        _receipt_ref_input(
            env,
            env_name="MULLU_GMAIL_WRITE_SOURCE_LIVE_RECEIPT_REF",
            input_kind="source_live_receipt_ref",
            valid_input_kind="valid_source_live_receipt_ref",
            blocker_prefix="gmail_write_source_live_receipt_ref",
            next_action="provide the fresh source live receipt ref before live write review",
        )
    )
    inputs.extend(
        _receipt_ref_input(
            env,
            env_name="MULLU_GMAIL_WRITE_REHEARSAL_RECEIPT_REF",
            input_kind="write_rehearsal_receipt_ref",
            valid_input_kind="valid_write_rehearsal_receipt_ref",
            blocker_prefix="gmail_write_rehearsal_receipt_ref",
            next_action="provide the Gmail write-authority rehearsal receipt ref before live write review",
        )
    )
    inputs.extend(
        _receipt_ref_input(
            env,
            env_name="MULLU_GMAIL_WRITE_APPROVAL_RECEIPT_REF",
            input_kind="write_approval_receipt_ref",
            valid_input_kind="valid_write_approval_receipt_ref",
            blocker_prefix="gmail_write_approval_receipt_ref",
            next_action="provide a separate approval receipt ref before live write review",
        )
    )
    if not _scope_binding_satisfies(env.get("GMAIL_SCOPE_ID", ""), required_scope_ref):
        current_state = "present_invalid" if env.get("GMAIL_SCOPE_ID", "").strip() else "missing"
        inputs.append(
            _operator_input(
                blocker=f"gmail_scope_binding_{current_state}",
                input_kind="gmail_scope_binding",
                required_names=("GMAIL_SCOPE_ID",),
                current_state=current_state,
                next_action=f"bind GMAIL_SCOPE_ID to a scope containing {required_scope_ref}",
            )
        )
    return tuple(_dedupe_inputs(inputs))


def _receipt_ref_input(
    env: Mapping[str, str],
    *,
    env_name: str,
    input_kind: str,
    valid_input_kind: str,
    blocker_prefix: str,
    next_action: str,
) -> tuple[DurableGmailLiveWriteOperatorInput, ...]:
    value = env.get(env_name, "").strip()
    if not value:
        return (
            _operator_input(
                blocker=f"{blocker_prefix}_missing",
                input_kind=input_kind,
                required_names=(env_name,),
                current_state="missing",
                next_action=next_action,
            ),
        )
    if not _is_public_ref(value):
        return (
            _operator_input(
                blocker=f"{blocker_prefix}_invalid",
                input_kind=valid_input_kind,
                required_names=(env_name,),
                current_state="present_invalid",
                next_action=next_action,
            ),
        )
    return ()


def _operator_input(
    *,
    blocker: str,
    input_kind: str,
    required_names: tuple[str, ...],
    current_state: str,
    next_action: str,
) -> DurableGmailLiveWriteOperatorInput:
    material = {
        "blocker": blocker,
        "input_kind": input_kind,
        "required_names": list(required_names),
        "current_state": current_state,
        "evidence_source": "durable_gmail_live_write_operator_input_request",
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return DurableGmailLiveWriteOperatorInput(
        input_id=f"durable-gmail-live-write-input-{digest[:12]}",
        blocker=blocker,
        input_kind=input_kind,
        required_names=required_names,
        current_state=current_state,
        evidence_source="durable_gmail_live_write_operator_input_request",
        next_action=next_action,
    )


def _dedupe_inputs(
    inputs: list[DurableGmailLiveWriteOperatorInput],
) -> tuple[DurableGmailLiveWriteOperatorInput, ...]:
    observed: set[str] = set()
    deduped: list[DurableGmailLiveWriteOperatorInput] = []
    for item in inputs:
        if item.input_id not in observed:
            observed.add(item.input_id)
            deduped.append(item)
    return tuple(deduped)


def _source_artifacts(env: Mapping[str, str]) -> dict[str, str]:
    return {
        "account_binding_receipt_ref": _safe_public_ref(env.get("MULLU_GMAIL_ACCOUNT_BINDING_RECEIPT_REF", "")),
        "source_live_receipt_ref": _safe_public_ref(env.get("MULLU_GMAIL_WRITE_SOURCE_LIVE_RECEIPT_REF", "")),
        "write_rehearsal_receipt_ref": _safe_public_ref(env.get("MULLU_GMAIL_WRITE_REHEARSAL_RECEIPT_REF", "")),
        "write_approval_receipt_ref": _safe_public_ref(env.get("MULLU_GMAIL_WRITE_APPROVAL_RECEIPT_REF", "")),
    }


def _safe_public_ref(value: str) -> str:
    text = value.strip()
    return text if _is_public_ref(text) else ""


def _is_public_ref(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or matched_secret_marker(text) or EMAIL_ADDRESS_RE.search(text):
        return False
    if text.startswith(("receipt:", "witness:", "github-actions:", "approval:")):
        return True
    candidate = Path(text)
    return not candidate.is_absolute() and ".." not in candidate.parts


def _scope_binding_satisfies(value: str, required_scope_ref: str) -> bool:
    text = value.strip()
    if not text or matched_secret_marker(text) or EMAIL_ADDRESS_RE.search(text):
        return False
    if required_scope_ref == "oauth:gmail.compose":
        return "gmail.compose" in text
    return "gmail.send" in text


def _solver_outcome(supported_operation: bool, ready_for_operator_review: bool) -> str:
    if ready_for_operator_review:
        return "SolvedVerified"
    if not supported_operation:
        return "GovernanceBlocked"
    return "AwaitingEvidence"


def _proof_state(supported_operation: bool, ready_for_operator_review: bool) -> str:
    if ready_for_operator_review:
        return "Pass"
    if not supported_operation:
        return "Fail"
    return "Unknown"


def _next_action(
    required_inputs: tuple[DurableGmailLiveWriteOperatorInput, ...],
    ready_for_operator_review: bool,
) -> str:
    if ready_for_operator_review:
        return (
            "review the input packet, then run a separate approval-gated live write evidence workflow; "
            "this request does not authorize a Gmail draft or send"
        )
    if required_inputs:
        return required_inputs[0].next_action
    return "inspect durable Gmail live write operator input blockers"


def _request_id(
    operation_family: str,
    required_inputs: tuple[DurableGmailLiveWriteOperatorInput, ...],
    ready_for_operator_review: bool,
) -> str:
    material = {
        "operation_family": operation_family,
        "required_input_ids": [item.input_id for item in required_inputs],
        "ready_for_operator_review": ready_for_operator_review,
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return f"durable-gmail-live-write-input-request-{digest[:16]}"


def _assert_redacted(payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, sort_keys=True)
    if matched_secret_marker(serialized) or EMAIL_ADDRESS_RE.search(serialized):
        raise ValueError("durable Gmail live write operator input request contains prohibited material")


def _validate_request_against_schema(
    request: DurableGmailLiveWriteOperatorInputRequest,
    schema_path: Path,
) -> None:
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, request.as_dict())
    if errors:
        raise RuntimeError(f"durable Gmail live write operator input request schema validation failed: {errors}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse durable Gmail live write operator input request arguments."""

    parser = argparse.ArgumentParser(description="Emit durable Gmail live write operator input request.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for durable Gmail live write operator input request emission."""

    args = parse_args(argv)
    try:
        request = emit_durable_gmail_live_write_operator_input_request(schema_path=Path(args.schema))
        write_durable_gmail_live_write_operator_input_request(request, Path(args.output))
    except (RuntimeError, ValueError) as exc:
        if args.json:
            print(
                json.dumps(
                    {
                        "error": str(exc),
                        "ready_for_operator_review": False,
                        "request_written": False,
                        "solver_outcome": "AwaitingEvidence",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(f"durable Gmail live write operator input request failed: {exc}")
        return 1
    if args.json:
        print(json.dumps(request.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"durable Gmail live write operator input request written: {request.request_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
