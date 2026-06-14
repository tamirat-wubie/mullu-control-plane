#!/usr/bin/env python3
"""Emit missing operator inputs for durable Gmail account binding evidence.

Purpose: translate Gmail account-binding blockers into a public-safe operator
input request before any profile probe or tenant/mailbox binding claim.
Governance scope: Gmail account binding, source live receipt freshness refs,
access-token runtime binding, tenant refs, hash inputs, external-effect
separation, and secret redaction.
Dependencies: schemas/durable_gmail_account_binding_operator_input_request.schema.json.
Invariants:
  - This emitter never calls Gmail, probes the profile endpoint, mutates
    provider state, writes mailbox state, or reads credential values.
  - Account binding remains blocked even when the operator input packet is
    complete; a separate live profile-probe evidence workflow is required.
  - Operator-visible output contains input names and public refs only.
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


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "durable_gmail_account_binding_operator_input_request.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "durable_gmail_account_binding_operator_input_request.json"
REQUIRED_BLOCKED_ACTIONS = (
    "account_binding_claim",
    "calendar_authority_claim",
    "external_provider_call",
    "gmail_profile_probe",
    "mailbox_write",
    "production_readiness_claim",
    "write_authority_claim",
)
EMAIL_ADDRESS_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
SHA256_HEX_RE = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True, slots=True)
class DurableGmailAccountBindingOperatorInput:
    """One missing or invalid input for a durable Gmail account-binding request."""

    input_id: str
    blocker: str
    input_kind: str
    required_names: tuple[str, ...]
    current_state: str
    evidence_source: str
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["required_names"] = list(self.required_names)
        return payload


@dataclass(frozen=True, slots=True)
class DurableGmailAccountBindingOperatorInputRequest:
    """Public-safe durable Gmail account-binding operator input request."""

    request_id: str
    adapter_id: str
    connector_id: str
    mode: str
    ready_for_operator_review: bool
    profile_probe_allowed: bool
    account_binding_claim_allowed: bool
    solver_outcome: str
    proof_state: str
    required_inputs: tuple[DurableGmailAccountBindingOperatorInput, ...]
    blocked_actions: tuple[str, ...]
    source_artifacts: dict[str, str]
    account_binding_summary: dict[str, bool]
    no_secret_values_serialized: bool
    raw_mailbox_address_disclosed: bool
    raw_hash_material_disclosed: bool
    external_provider_call_performed: bool
    external_mailbox_write_performed: bool
    provider_mutation_performed: bool
    production_ready_claimed: bool
    write_authority_claimed: bool
    calendar_authority_claimed: bool
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "adapter_id": self.adapter_id,
            "connector_id": self.connector_id,
            "mode": self.mode,
            "ready_for_operator_review": self.ready_for_operator_review,
            "profile_probe_allowed": self.profile_probe_allowed,
            "account_binding_claim_allowed": self.account_binding_claim_allowed,
            "solver_outcome": self.solver_outcome,
            "proof_state": self.proof_state,
            "required_inputs": [item.as_dict() for item in self.required_inputs],
            "blocked_actions": list(self.blocked_actions),
            "source_artifacts": dict(self.source_artifacts),
            "account_binding_summary": dict(self.account_binding_summary),
            "no_secret_values_serialized": self.no_secret_values_serialized,
            "raw_mailbox_address_disclosed": self.raw_mailbox_address_disclosed,
            "raw_hash_material_disclosed": self.raw_hash_material_disclosed,
            "external_provider_call_performed": self.external_provider_call_performed,
            "external_mailbox_write_performed": self.external_mailbox_write_performed,
            "provider_mutation_performed": self.provider_mutation_performed,
            "production_ready_claimed": self.production_ready_claimed,
            "write_authority_claimed": self.write_authority_claimed,
            "calendar_authority_claimed": self.calendar_authority_claimed,
            "next_action": self.next_action,
        }


def emit_durable_gmail_account_binding_operator_input_request(
    *,
    environment: Mapping[str, str] | None = None,
    schema_path: Path = DEFAULT_SCHEMA,
) -> DurableGmailAccountBindingOperatorInputRequest:
    """Build a durable Gmail account-binding operator input request."""

    env = dict(os.environ if environment is None else environment)
    required_inputs = _derive_required_inputs(env)
    ready_for_operator_review = not required_inputs
    request = DurableGmailAccountBindingOperatorInputRequest(
        request_id=_request_id(required_inputs, ready_for_operator_review),
        adapter_id="communication.gmail_oauth",
        connector_id="gmail",
        mode="foundation-local",
        ready_for_operator_review=ready_for_operator_review,
        profile_probe_allowed=False,
        account_binding_claim_allowed=False,
        solver_outcome="SolvedVerified" if ready_for_operator_review else "AwaitingEvidence",
        proof_state="Pass" if ready_for_operator_review else "Unknown",
        required_inputs=required_inputs,
        blocked_actions=REQUIRED_BLOCKED_ACTIONS,
        source_artifacts=_source_artifacts(env),
        account_binding_summary={
            "profile_probe_required": True,
            "source_live_receipt_required": True,
            "tenant_binding_required": True,
            "expected_hash_required": True,
        },
        no_secret_values_serialized=True,
        raw_mailbox_address_disclosed=False,
        raw_hash_material_disclosed=False,
        external_provider_call_performed=False,
        external_mailbox_write_performed=False,
        provider_mutation_performed=False,
        production_ready_claimed=False,
        write_authority_claimed=False,
        calendar_authority_claimed=False,
        next_action=_next_action(required_inputs, ready_for_operator_review),
    )
    _assert_redacted(request.as_dict())
    _validate_request_against_schema(request, schema_path)
    return request


def write_durable_gmail_account_binding_operator_input_request(
    request: DurableGmailAccountBindingOperatorInputRequest,
    output_path: Path,
) -> Path:
    """Write one durable Gmail account-binding operator input request."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(request.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _derive_required_inputs(env: Mapping[str, str]) -> tuple[DurableGmailAccountBindingOperatorInput, ...]:
    inputs: list[DurableGmailAccountBindingOperatorInput] = []
    if not _runtime_token_present(env):
        inputs.append(
            _operator_input(
                blocker="gmail_account_binding_access_token_missing",
                input_kind="access_token_runtime_binding",
                required_names=("GMAIL_ACCESS_TOKEN", "EMAIL_CALENDAR_CONNECTOR_TOKEN"),
                current_state="missing",
                next_action="provide a runtime-only Gmail access token binding before account-binding review",
            )
        )
    expected_hash = env.get("MULLU_GMAIL_EXPECTED_ACCOUNT_HASH", "").strip()
    if not expected_hash:
        inputs.append(
            _operator_input(
                blocker="gmail_account_binding_expected_hash_missing",
                input_kind="expected_account_hash_binding",
                required_names=("MULLU_GMAIL_EXPECTED_ACCOUNT_HASH",),
                current_state="missing",
                next_action="provide the expected mailbox account hash before account-binding review",
            )
        )
    elif not SHA256_HEX_RE.fullmatch(expected_hash):
        inputs.append(
            _operator_input(
                blocker="gmail_account_binding_expected_hash_invalid",
                input_kind="valid_expected_account_hash_binding",
                required_names=("MULLU_GMAIL_EXPECTED_ACCOUNT_HASH",),
                current_state="present_invalid",
                next_action="replace MULLU_GMAIL_EXPECTED_ACCOUNT_HASH with lowercase sha256 hex",
            )
        )
    if not env.get("GMAIL_ACCOUNT_BINDING_HASH_SALT", "").strip():
        inputs.append(
            _operator_input(
                blocker="gmail_account_binding_hash_salt_missing",
                input_kind="hash_salt_runtime_binding",
                required_names=("GMAIL_ACCOUNT_BINDING_HASH_SALT",),
                current_state="missing",
                next_action="provide the hash salt as runtime-only secret material before account-binding review",
            )
        )
    tenant_ref = env.get("MULLU_GMAIL_ACCOUNT_BINDING_TENANT_REF", "").strip()
    if not tenant_ref:
        inputs.append(
            _operator_input(
                blocker="gmail_account_binding_tenant_ref_missing",
                input_kind="tenant_ref_binding",
                required_names=("MULLU_GMAIL_ACCOUNT_BINDING_TENANT_REF",),
                current_state="missing",
                next_action="provide a public tenant reference before account-binding review",
            )
        )
    elif not _is_public_ref(tenant_ref):
        inputs.append(
            _operator_input(
                blocker="gmail_account_binding_tenant_ref_invalid",
                input_kind="valid_tenant_ref_binding",
                required_names=("MULLU_GMAIL_ACCOUNT_BINDING_TENANT_REF",),
                current_state="present_invalid",
                next_action="replace the tenant reference with a public-safe ref",
            )
        )
    source_ref = env.get("MULLU_GMAIL_ACCOUNT_BINDING_SOURCE_RECEIPT_REF", "").strip()
    if not source_ref:
        inputs.append(
            _operator_input(
                blocker="gmail_account_binding_source_live_receipt_ref_missing",
                input_kind="source_live_receipt_ref",
                required_names=("MULLU_GMAIL_ACCOUNT_BINDING_SOURCE_RECEIPT_REF",),
                current_state="missing",
                next_action="provide the fresh source live receipt ref before account-binding review",
            )
        )
    elif not _is_public_ref(source_ref):
        inputs.append(
            _operator_input(
                blocker="gmail_account_binding_source_live_receipt_ref_invalid",
                input_kind="valid_source_live_receipt_ref",
                required_names=("MULLU_GMAIL_ACCOUNT_BINDING_SOURCE_RECEIPT_REF",),
                current_state="present_invalid",
                next_action="replace the source live receipt ref with a public-safe workspace or receipt ref",
            )
        )
    return tuple(_dedupe_inputs(inputs))


def _runtime_token_present(env: Mapping[str, str]) -> bool:
    return bool(env.get("GMAIL_ACCESS_TOKEN", "").strip() or env.get("EMAIL_CALENDAR_CONNECTOR_TOKEN", "").strip())


def _operator_input(
    *,
    blocker: str,
    input_kind: str,
    required_names: tuple[str, ...],
    current_state: str,
    next_action: str,
) -> DurableGmailAccountBindingOperatorInput:
    material = {
        "blocker": blocker,
        "input_kind": input_kind,
        "required_names": list(required_names),
        "current_state": current_state,
        "evidence_source": "durable_gmail_account_binding_operator_input_request",
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return DurableGmailAccountBindingOperatorInput(
        input_id=f"durable-gmail-account-binding-input-{digest[:12]}",
        blocker=blocker,
        input_kind=input_kind,
        required_names=required_names,
        current_state=current_state,
        evidence_source="durable_gmail_account_binding_operator_input_request",
        next_action=next_action,
    )


def _dedupe_inputs(
    inputs: list[DurableGmailAccountBindingOperatorInput],
) -> tuple[DurableGmailAccountBindingOperatorInput, ...]:
    observed: set[str] = set()
    deduped: list[DurableGmailAccountBindingOperatorInput] = []
    for item in inputs:
        if item.input_id not in observed:
            observed.add(item.input_id)
            deduped.append(item)
    return tuple(deduped)


def _source_artifacts(env: Mapping[str, str]) -> dict[str, str]:
    return {
        "source_live_receipt_ref": _safe_public_ref(env.get("MULLU_GMAIL_ACCOUNT_BINDING_SOURCE_RECEIPT_REF", "")),
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
    if text.startswith(("receipt:", "witness:", "github-actions:", "tenant://")):
        return True
    candidate = Path(text)
    return not candidate.is_absolute() and ".." not in candidate.parts


def _next_action(
    required_inputs: tuple[DurableGmailAccountBindingOperatorInput, ...],
    ready_for_operator_review: bool,
) -> str:
    if ready_for_operator_review:
        return (
            "review the input packet, then run a separate read-only Gmail profile-probe evidence workflow; "
            "this request does not authorize account binding"
        )
    if required_inputs:
        return required_inputs[0].next_action
    return "inspect durable Gmail account-binding operator input blockers"


def _request_id(
    required_inputs: tuple[DurableGmailAccountBindingOperatorInput, ...],
    ready_for_operator_review: bool,
) -> str:
    material = {
        "required_input_ids": [item.input_id for item in required_inputs],
        "ready_for_operator_review": ready_for_operator_review,
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return f"durable-gmail-account-binding-input-request-{digest[:16]}"


def _assert_redacted(payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, sort_keys=True)
    if matched_secret_marker(serialized) or EMAIL_ADDRESS_RE.search(serialized):
        raise ValueError("durable Gmail account-binding operator input request contains prohibited material")


def _validate_request_against_schema(
    request: DurableGmailAccountBindingOperatorInputRequest,
    schema_path: Path,
) -> None:
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, request.as_dict())
    if errors:
        raise RuntimeError(f"durable Gmail account-binding operator input request schema validation failed: {errors}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse durable Gmail account-binding operator input request arguments."""

    parser = argparse.ArgumentParser(description="Emit durable Gmail account-binding operator input request.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for durable Gmail account-binding operator input request emission."""

    args = parse_args(argv)
    try:
        request = emit_durable_gmail_account_binding_operator_input_request(schema_path=Path(args.schema))
        write_durable_gmail_account_binding_operator_input_request(request, Path(args.output))
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
            print(f"durable Gmail account-binding operator input request failed: {exc}")
        return 1
    if args.json:
        print(json.dumps(request.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"durable Gmail account-binding operator input request written: {request.request_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
