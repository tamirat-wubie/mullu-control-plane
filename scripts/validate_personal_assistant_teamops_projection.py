#!/usr/bin/env python3
"""Validate personal-assistant TeamOps shared-inbox projection evidence.

Purpose: prove TeamOps shared-inbox plans are schema-backed, no-effect
Personal Assistant projections.
Governance scope: operator handoff projection, live-probe gate summary,
receipt conformance, private payload redaction, and Foundation Mode no-effect
boundaries.
Dependencies: personal-assistant TeamOps runtime helpers, TeamOps handoff
schema, personal-assistant receipt schema, and schema validators.
Invariants:
  - TeamOps projection records are not Gmail calls.
  - Live-probe readiness is evidence state, not provider execution.
  - Mailboxes are not read, drafted, sent, archived, deleted, or mutated.
  - Raw connector payloads and secret-like values are rejected.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for candidate_path in (REPO_ROOT, MCOI_ROOT):
    if str(candidate_path) not in sys.path:
        sys.path.insert(0, str(candidate_path))

from mcoi_runtime.personal_assistant import (  # noqa: E402
    ConnectorProofRef,
    interpret_user_request,
    plan_teamops_shared_inbox,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_PROJECTION = REPO_ROOT / "examples" / "personal_assistant_teamops_projection.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_teamops_projection.schema.json"
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
DEFAULT_HANDOFF_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_operator_handoff.schema.json"
RUNTIME_SUBMITTED_AT = "2026-06-15T00:10:00+00:00"
RUNTIME_GENERATED_AT = "2026-06-15T00:15:00+00:00"

FALSE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "execution_allowed",
        "live_connector_execution_allowed",
        "live_probe_execution_allowed",
        "mailbox_read_allowed",
        "mailbox_mutation_allowed",
        "draft_creation_allowed",
        "external_send_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "deployment_mutation_allowed",
        "public_readiness_claim_allowed",
        "customer_readiness_claim_allowed",
        "nested_mind_live_activation_allowed",
    }
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)
RAW_PRIVATE_FIELD_NAMES = frozenset(
    {
        "raw_private_connector_payload",
        "raw_connector_payload",
        "private_connector_payload",
        "connector_response",
        "message_body",
        "email_body",
        "mailbox_payload",
        "raw_message",
        "raw_thread",
        "credential",
        "credentials",
        "token",
        "secret",
        "private_key",
        "authorization",
        "cookie",
    }
)
ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "connector_payload_projection",
        "body_projection",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantTeamOpsProjectionValidation:
    """Validation result for a TeamOps projection evidence envelope."""

    valid: bool
    projection_path: str
    runtime_validated: bool
    projection_count: int
    receipt_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_teamops_projection(
    *,
    projection_path: Path = DEFAULT_PROJECTION,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
    handoff_schema_path: Path = DEFAULT_HANDOFF_SCHEMA,
    validate_runtime: bool = True,
) -> PersonalAssistantTeamOpsProjectionValidation:
    """Validate a TeamOps projection fixture and optional runtime envelope."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "TeamOps projection schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    handoff_schema = _load_json_object(handoff_schema_path, "TeamOps handoff schema", errors)
    projection = _load_json_object(projection_path, "TeamOps projection evidence", errors)
    assurance_outcome = ""
    if schema and projection:
        errors.extend(_validate_schema_instance(schema, projection))
    if projection:
        assurance = _mapping(projection.get("assurance"))
        assurance_outcome = str(assurance.get("outcome", ""))
        errors.extend(_validate_projection_semantics(projection, receipt_schema, handoff_schema))
        _scan_private_or_secret_payload(projection, errors, path="$")

    runtime_validated = False
    if validate_runtime and schema:
        runtime_projection = build_runtime_teamops_projection_evidence()
        runtime_errors = list(_validate_schema_instance(schema, runtime_projection))
        runtime_errors.extend(_validate_projection_semantics(runtime_projection, receipt_schema, handoff_schema))
        _scan_private_or_secret_payload(runtime_projection, runtime_errors, path="$runtime")
        if runtime_errors:
            errors.extend(f"runtime {message}" for message in runtime_errors)
        runtime_validated = not runtime_errors

    return PersonalAssistantTeamOpsProjectionValidation(
        valid=not errors,
        projection_path=_path_label(projection_path),
        runtime_validated=runtime_validated,
        projection_count=int(projection.get("projection_count", 0)) if isinstance(projection, dict) else 0,
        receipt_count=len(projection.get("receipt_ids", ())) if isinstance(projection, dict) else 0,
        assurance_outcome=assurance_outcome,
        errors=tuple(errors),
    )


def build_runtime_teamops_projection_evidence() -> dict[str, Any]:
    """Build deterministic blocked and ready-evidence TeamOps projections."""
    blocked = plan_teamops_shared_inbox(
        _teamops_intent("pa_request_teamops_projection_blocked_001"),
        generated_at=RUNTIME_GENERATED_AT,
        environment={},
        github_secret_names=set(),
    )
    ready = plan_teamops_shared_inbox(
        _teamops_intent("pa_request_teamops_projection_ready_001"),
        generated_at=RUNTIME_GENERATED_AT,
        environment=_ready_environment(),
        github_secret_names=_ready_secret_names(),
        operator_approval_ref="approval:teamops-shared-inbox-provider-setup-20260615",
    )
    return build_teamops_projection_evidence_envelope(
        generated_at=RUNTIME_GENERATED_AT,
        projections=(
            ("pa_teamops_projection_item_blocked_001", blocked.as_dict()),
            ("pa_teamops_projection_item_ready_001", ready.as_dict()),
        ),
    )


def build_teamops_projection_evidence_envelope(
    *,
    generated_at: str,
    projections: tuple[tuple[str, Mapping[str, Any]], ...],
) -> dict[str, Any]:
    """Build a schema-shaped no-effect envelope around TeamOps plans."""
    items: list[dict[str, Any]] = []
    projection_ids: list[str] = []
    receipt_ids: list[str] = []
    connectors: list[str] = []
    has_awaiting_evidence = False
    for projection_id, projection in projections:
        plan = _mapping(projection.get("plan"))
        receipt = _mapping(projection.get("receipt"))
        projection_ids.append(projection_id)
        receipt_id = str(receipt.get("receipt_id", ""))
        if receipt_id and receipt_id not in receipt_ids:
            receipt_ids.append(receipt_id)
        for connector in receipt.get("connectors_used", ()):
            if isinstance(connector, str) and connector not in connectors:
                connectors.append(connector)
        handoff = _mapping(plan.get("handoff"))
        if handoff.get("solver_outcome") == "AwaitingEvidence":
            has_awaiting_evidence = True
        items.append(
            {
                "projection_id": projection_id,
                "request_id": str(projection.get("request_id", "")),
                "skill_id": str(projection.get("skill_id", "")),
                "plan_type": str(plan.get("plan_type", "")),
                "plan": dict(plan),
                "receipt": dict(receipt),
            }
        )
    return {
        "projection_set_id": "pa_teamops_projection_foundation_001",
        "generated_at": generated_at,
        "governed": True,
        "source_projection": "operator_supplied_teamops_shared_inbox_evidence",
        "projection_count": len(items),
        "projection_ids": projection_ids,
        "receipt_ids": receipt_ids,
        "connectors_used": connectors,
        "projections": items,
        "effect_boundary": {
            "teamops_plan_records_allowed": True,
            "execution_allowed": False,
            "live_connector_execution_allowed": False,
            "live_probe_execution_allowed": False,
            "mailbox_read_allowed": False,
            "mailbox_mutation_allowed": False,
            "draft_creation_allowed": False,
            "external_send_allowed": False,
            "connector_mutation_allowed": False,
            "system_of_record_write_allowed": False,
            "deployment_mutation_allowed": False,
            "public_readiness_claim_allowed": False,
            "customer_readiness_claim_allowed": False,
            "nested_mind_live_activation_allowed": False,
        },
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "ref_only",
            "body_projection": "none",
            "handoff_payload_projection": "bounded_operator_handoff",
        },
        "assurance": {
            "assurance_id": "personal_assistant_teamops_projection_no_effect_assurance",
            "outcome": "AwaitingEvidence" if has_awaiting_evidence else "SolvedVerified",
            "foundation_only": True,
            "ready_for_live_connector_execution": False,
            "ready_for_live_probe_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "teamops_plan_is_not_provider_call",
                "live_probe_gate_is_evidence_only",
                "no_mailbox_read",
                "no_mailbox_mutation",
                "no_draft_creation",
                "no_external_send",
                "no_connector_mutation",
                "no_secret_value_serialization",
                "no_raw_private_payload_storage",
            ],
            "blocking_reasons": [
                "live_probe_requires_separate_approval_binding"
            ] if has_awaiting_evidence else [],
            "next_action": "bind live-probe evidence separately before any provider probe",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "teamops_shared_inbox_plan_evidence_only",
            "runtime_boundary": "teamops_plan_does_not_call_provider",
            "live_connector_execution_allowed": False,
            "live_probe_execution_allowed": False,
            "mailbox_read_allowed": False,
            "mailbox_mutation_allowed": False,
            "external_send_allowed": False,
            "connector_mutation_allowed": False,
            "system_of_record_write_allowed": False,
        },
    }


def _validate_projection_semantics(
    projection: dict[str, Any],
    receipt_schema: dict[str, Any],
    handoff_schema: dict[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    effect_boundary = _mapping(projection.get("effect_boundary"))
    if effect_boundary.get("teamops_plan_records_allowed") is not True:
        errors.append("effect_boundary.teamops_plan_records_allowed must be true")
    _require_false_fields(effect_boundary, FALSE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    private_policy = _mapping(projection.get("private_payload_policy"))
    if private_policy.get("raw_private_payload_serialized") is not False:
        errors.append("private_payload_policy.raw_private_payload_serialized must be false")
    if private_policy.get("secret_values_serialized") is not False:
        errors.append("private_payload_policy.secret_values_serialized must be false")
    assurance = _mapping(projection.get("assurance"))
    if assurance.get("foundation_only") is not True:
        errors.append("assurance.foundation_only must be true")
    if assurance.get("ready_for_live_connector_execution") is not False:
        errors.append("assurance.ready_for_live_connector_execution must be false")
    if assurance.get("ready_for_live_probe_execution") is not False:
        errors.append("assurance.ready_for_live_probe_execution must be false")
    if assurance.get("ready_for_customer_readiness_claim") is not False:
        errors.append("assurance.ready_for_customer_readiness_claim must be false")

    items = projection.get("projections")
    if not isinstance(items, list):
        errors.append("projections must be a list")
        return tuple(errors)
    if projection.get("projection_count") != len(items):
        errors.append("projection_count must equal projections length")
    projection_ids: list[str] = []
    receipt_ids: list[str] = []
    seen_ready = False
    seen_blocked = False
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"projections[{index}] must be an object")
            continue
        projection_ids.append(str(item.get("projection_id", "")))
        plan = _mapping(item.get("plan"))
        handoff = _mapping(plan.get("handoff"))
        gate = _mapping(plan.get("live_probe_gate"))
        receipt = _mapping(item.get("receipt"))
        if handoff_schema:
            errors.extend(
                f"projections[{index}].plan.handoff {message}"
                for message in _validate_schema_instance(handoff_schema, handoff)
            )
        if receipt_schema:
            errors.extend(
                f"projections[{index}].receipt {message}"
                for message in _validate_schema_instance(receipt_schema, receipt)
            )
        errors.extend(
            f"projections[{index}].receipt {message}"
            for message in validate_personal_assistant_receipt_payload(receipt)
        )
        if item.get("skill_id") != "teamops.shared_inbox.plan":
            errors.append(f"projections[{index}].skill_id must be teamops.shared_inbox.plan")
        if plan.get("execution_allowed") is not False:
            errors.append(f"projections[{index}].plan.execution_allowed must be false")
        if plan.get("live_probe_executed") is not False:
            errors.append(f"projections[{index}].plan.live_probe_executed must be false")
        if gate.get("external_provider_call_performed") is not False:
            errors.append(f"projections[{index}].plan.live_probe_gate.external_provider_call_performed must be false")
        if gate.get("mailbox_write_performed") is not False:
            errors.append(f"projections[{index}].plan.live_probe_gate.mailbox_write_performed must be false")
        if gate.get("external_message_sent") is not False:
            errors.append(f"projections[{index}].plan.live_probe_gate.external_message_sent must be false")
        if "gmail_not_called" not in receipt.get("actions_not_taken", ()):
            errors.append(f"projections[{index}].receipt.actions_not_taken must include gmail_not_called")
        if "shared_inbox_not_read" not in receipt.get("actions_not_taken", ()):
            errors.append(f"projections[{index}].receipt.actions_not_taken must include shared_inbox_not_read")
        if "email_not_sent" not in receipt.get("actions_not_taken", ()):
            errors.append(f"projections[{index}].receipt.actions_not_taken must include email_not_sent")
        metadata = _mapping(receipt.get("metadata"))
        if metadata.get("live_connector_execution_allowed") is not False:
            errors.append(f"projections[{index}].receipt.metadata.live_connector_execution_allowed must be false")
        if metadata.get("live_probe_executed") is not False:
            errors.append(f"projections[{index}].receipt.metadata.live_probe_executed must be false")
        if handoff.get("ready_for_live_probe") is True:
            seen_ready = True
        else:
            seen_blocked = True
        receipt_id = receipt.get("receipt_id")
        if isinstance(receipt_id, str):
            receipt_ids.append(receipt_id)
    if not seen_ready:
        errors.append("projections must include a ready-evidence handoff")
    if not seen_blocked:
        errors.append("projections must include a blocked handoff")
    if projection.get("projection_ids") != projection_ids:
        errors.append("projection_ids must match projections order")
    if sorted(projection.get("receipt_ids", ())) != sorted(receipt_ids):
        errors.append("receipt_ids must match embedded receipts")
    return tuple(errors)


def _teamops_intent(request_id: str):
    return interpret_user_request(
        "Prepare a TeamOps shared inbox handoff.",
        request_id=request_id,
        submitted_at=RUNTIME_SUBMITTED_AT,
        connector_refs=(
            ConnectorProofRef(
                connector_id="connector:gmail:operator",
                connector_name="gmail",
                proof_state="Pass",
                private_data_allowed=True,
                scopes=("gmail.readonly",),
            ),
        ),
    )


def _ready_environment() -> dict[str, str]:
    return {
        "MULLU_TEAM_OPS_ASSISTANT_PROFILE": "team_ops.default",
        "MULLU_TEAM_OPS_SHARED_INBOX_PROVIDER": "gmail",
        "MULLU_TEAM_OPS_CONNECTOR_OPERATION_MODE": "shared_inbox_triage",
        "MULLU_TEAM_OPS_EXTERNAL_SEND_POLICY": "approval_required",
        "MULLU_TEAM_OPS_TENANT_SCOPE_WITNESS_REF": "witness:teamops-tenant-scope",
        "MULLU_TEAM_OPS_SHARED_INBOX_WITNESS_REF": "witness:teamops-shared-inbox",
        "MULLU_TEAM_OPS_DIRECTORY_WITNESS_REF": "witness:teamops-directory",
        "MULLU_TEAM_OPS_OWNER_QUEUE_WITNESS_REF": "witness:teamops-owner-queue",
        "MULLU_TEAM_OPS_EXTERNAL_SEND_APPROVAL_POLICY_REF": "policy:teamops-external-send-approval",
        "MULLU_TEAM_OPS_IDEMPOTENCY_POLICY_REF": "policy:teamops-idempotency",
        "MULLU_TEAM_OPS_REVOCATION_RECOVERY_RECEIPT_REF": "receipt:teamops-revocation-recovery",
        "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER": "google",
        "EMAIL_CALENDAR_CONNECTOR_ID": "gmail",
        "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY": "read_and_send_with_approval",
        "GMAIL_SCOPE_ID": (
            "https://www.googleapis.com/auth/gmail.readonly "
            "https://www.googleapis.com/auth/gmail.send"
        ),
        "EMAIL_CALENDAR_CONNECTOR_SCOPE_ID": (
            "https://www.googleapis.com/auth/gmail.readonly "
            "https://www.googleapis.com/auth/gmail.send"
        ),
        "GMAIL_OAUTH_CLIENT_ID": "present",
        "GMAIL_OAUTH_CLIENT_SECRET": "present",
        "GMAIL_REFRESH_TOKEN": "present",
        "MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF": "witness:gmail-consent",
        "MULLU_GMAIL_OAUTH_CLIENT_WITNESS_REF": "witness:gmail-client",
        "MULLU_GMAIL_LEAST_PRIVILEGE_SCOPE_RECEIPT_REF": "receipt:gmail-scope",
        "MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF": "receipt:gmail-token-storage",
        "MULLU_GMAIL_REVOCATION_RECOVERY_RECEIPT_REF": "receipt:gmail-revocation",
        "MULLU_GMAIL_CONNECTOR_TENANT_WITNESS_REF": "witness:gmail-tenant",
    }


def _ready_secret_names() -> set[str]:
    return {
        "GMAIL_OAUTH_CLIENT_ID",
        "GMAIL_OAUTH_CLIENT_SECRET",
        "GMAIL_REFRESH_TOKEN",
        "MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF",
        "MULLU_GMAIL_OAUTH_CLIENT_WITNESS_REF",
        "MULLU_GMAIL_LEAST_PRIVILEGE_SCOPE_RECEIPT_REF",
        "MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF",
        "MULLU_GMAIL_REVOCATION_RECOVERY_RECEIPT_REF",
        "MULLU_GMAIL_CONNECTOR_TENANT_WITNESS_REF",
        "MULLU_TEAM_OPS_TENANT_SCOPE_WITNESS_REF",
        "MULLU_TEAM_OPS_SHARED_INBOX_WITNESS_REF",
        "MULLU_TEAM_OPS_DIRECTORY_WITNESS_REF",
        "MULLU_TEAM_OPS_OWNER_QUEUE_WITNESS_REF",
        "MULLU_TEAM_OPS_EXTERNAL_SEND_APPROVAL_POLICY_REF",
        "MULLU_TEAM_OPS_IDEMPOTENCY_POLICY_REF",
        "MULLU_TEAM_OPS_REVOCATION_RECOVERY_RECEIPT_REF",
    }


def _require_false_fields(payload: Mapping[str, Any], fields: frozenset[str], label: str, errors: list[str]) -> None:
    model = _mapping(payload)
    if not model:
        errors.append(f"{label} must be an object")
        return
    for field_name in sorted(fields):
        if model.get(field_name) is not False:
            errors.append(f"{label}.{field_name} must be false")


def _scan_private_or_secret_payload(payload: Any, errors: list[str], *, path: str) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized_key = str(key).lower()
            if normalized_key not in ALLOWED_POLICY_FIELD_NAMES and normalized_key in RAW_PRIVATE_FIELD_NAMES:
                errors.append(f"{path}.{key}: raw private or secret field is forbidden")
            _scan_private_or_secret_payload(value, errors, path=f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _scan_private_or_secret_payload(value, errors, path=f"{path}[{index}]")
    elif isinstance(payload, str):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(payload):
                errors.append(f"{path}: secret-like value must not be serialized")
                break


def _mapping(payload: Any) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) else {}


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        errors.append(f"{label} could not be read")
        return {}
    except json.JSONDecodeError:
        errors.append(f"{label} must be JSON")
        return {}
    if not isinstance(parsed, dict):
        errors.append(f"{label} root must be an object")
        return {}
    return parsed


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps projection validation arguments."""
    parser = argparse.ArgumentParser(description="Validate personal-assistant TeamOps projection evidence.")
    parser.add_argument("--projection", default=str(DEFAULT_PROJECTION))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--receipt-schema", default=str(DEFAULT_RECEIPT_SCHEMA))
    parser.add_argument("--handoff-schema", default=str(DEFAULT_HANDOFF_SCHEMA))
    parser.add_argument("--skip-runtime", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps projection validation."""
    args = parse_args(argv)
    result = validate_personal_assistant_teamops_projection(
        projection_path=Path(args.projection),
        schema_path=Path(args.schema),
        receipt_schema_path=Path(args.receipt_schema),
        handoff_schema_path=Path(args.handoff_schema),
        validate_runtime=not args.skip_runtime,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(
            "personal-assistant TeamOps projection ok "
            f"projections={result.projection_count} receipts={result.receipt_count} "
            f"runtime_validated={result.runtime_validated}"
        )
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
