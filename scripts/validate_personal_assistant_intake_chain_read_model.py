#!/usr/bin/env python3
"""Validate the personal-assistant intake-chain read model.

Purpose: prove the intake-chain projection binds request, symbolic
interpretation, WHQR clarification, plan preview, approval, receipts, and
lineage without granting execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS].
Dependencies: intake-chain schema, personal-assistant request/plan/approval/
receipt schemas, symbolic interpretation proposal schema, and foundation
example fixtures.
Invariants:
  - The read model remains foundation-only and no-effect.
  - Interpretation proposals cannot override deterministic interpretation.
  - Approval records do not execute actions.
  - Raw private connector payloads and secret-like values are rejected.
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
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_READ_MODEL = REPO_ROOT / "examples" / "personal_assistant_intake_chain_read_model.foundation.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_intake_chain_read_model.schema.json"
REQUEST_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_request.schema.json"
INTERPRETATION_SCHEMA = REPO_ROOT / "schemas" / "symbolic_interpretation_proposal.schema.json"
PLAN_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_plan.schema.json"
APPROVAL_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_approval.schema.json"
RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"

NO_EFFECT_FIELDS = (
    "execution_allowed",
    "live_connector_execution_allowed",
    "connector_mutation_allowed",
    "mailbox_read_allowed",
    "mailbox_mutation_allowed",
    "external_send_allowed",
    "calendar_write_allowed",
    "task_write_allowed",
    "memory_write_allowed",
    "deployment_mutation_allowed",
    "customer_readiness_claim_allowed",
    "money_legal_public_action_allowed",
)
RAW_PRIVATE_FIELD_NAMES = frozenset(
    {
        "raw_private_connector_payload",
        "raw_connector_payload",
        "private_connector_payload",
        "connector_response",
        "message_body",
        "email_body",
        "calendar_payload",
        "mailbox_payload",
        "raw_message",
        "raw_thread",
    }
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantIntakeChainValidation:
    """Validation result for one intake-chain read model."""

    valid: bool
    read_model_path: str
    source_artifact_count: int
    receipt_ref_count: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_intake_chain_read_model(
    *,
    read_model_path: Path = DEFAULT_READ_MODEL,
    schema_path: Path = DEFAULT_SCHEMA,
) -> PersonalAssistantIntakeChainValidation:
    """Validate one personal-assistant intake-chain read model."""
    errors: list[str] = []
    payload = _load_json_object(read_model_path, "intake-chain read model", errors)
    if payload:
        schema = _load_schema(schema_path)
        errors.extend(_validate_schema_instance(schema, payload))
        errors.extend(_validate_semantics(payload))
        _scan_private_or_secret_payload(payload, errors, path="$")
    return PersonalAssistantIntakeChainValidation(
        valid=not errors,
        read_model_path=_path_label(read_model_path),
        source_artifact_count=len(payload.get("source_artifacts", ())) if isinstance(payload, dict) else 0,
        receipt_ref_count=len(payload.get("receipt_refs", ())) if isinstance(payload, dict) else 0,
        errors=tuple(errors),
    )


def _validate_semantics(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    request = _mapping(payload.get("request"))
    interpretation = _mapping(payload.get("interpretation"))
    clarification = _mapping(payload.get("clarification"))
    plan_preview = _mapping(payload.get("plan_preview"))
    approval_boundary = _mapping(payload.get("approval_boundary"))
    receipt_boundary = _mapping(payload.get("receipt_boundary"))
    memory_boundary = _mapping(payload.get("memory_boundary"))
    effect_boundary = _mapping(payload.get("effect_boundary"))
    private_payload_policy = _mapping(payload.get("private_payload_policy"))
    contract_summary = _mapping(payload.get("contract_summary"))

    _require_false_fields(effect_boundary, NO_EFFECT_FIELDS, errors, prefix="effect_boundary")
    _require_false_fields(
        approval_boundary,
        ("approval_is_execution", "execution_allowed", "external_send_allowed"),
        errors,
        prefix="approval_boundary",
    )
    _require_false_fields(
        memory_boundary,
        ("memory_write_allowed", "nested_mind_live_activation_allowed", "raw_chat_log_storage_allowed"),
        errors,
        prefix="memory_boundary",
    )
    _require_false_fields(
        private_payload_policy,
        ("raw_private_payload_serialized", "secret_values_serialized"),
        errors,
        prefix="private_payload_policy",
    )
    if payload.get("foundation_only") is not True:
        errors.append("foundation_only must be true")
    if receipt_boundary.get("receipt_required") is not True:
        errors.append("receipt_boundary.receipt_required must be true")
    if receipt_boundary.get("success_claim_allowed") is not False:
        errors.append("receipt_boundary.success_claim_allowed must be false")
    if approval_boundary.get("approval_required_for_p4_p5") is not True:
        errors.append("approval_boundary.approval_required_for_p4_p5 must be true")

    request_id = request.get("request_id")
    if interpretation.get("personal_assistant_request_id") != request_id:
        errors.append("interpretation.personal_assistant_request_id must match request.request_id")
    plan = _mapping(plan_preview.get("plan"))
    if plan.get("request_id") != request_id:
        errors.append("plan_preview.plan.request_id must match request.request_id")
    if plan.get("execution_allowed") is not False:
        errors.append("plan_preview.plan.execution_allowed must be false")
    if plan_preview.get("step_count") != len(plan.get("steps", ())) if isinstance(plan.get("steps"), list) else True:
        errors.append("plan_preview.step_count must match plan.steps length")
    if sorted(plan_preview.get("actions_not_authorized", ())) != sorted(plan.get("actions_not_authorized", ())):
        errors.append("plan_preview.actions_not_authorized must match plan.actions_not_authorized")

    clarification_required = clarification.get("required")
    missing_count = clarification.get("missing_binding_count")
    questions = clarification.get("questions")
    if clarification_required is True and (not isinstance(questions, list) or len(questions) < int(missing_count or 0)):
        errors.append("clarification.questions must cover every missing binding when clarification is required")
    if clarification_required is False and missing_count != 0:
        errors.append("clarification.missing_binding_count must be 0 when clarification is not required")
    if request.get("missing_binding_count") != missing_count:
        errors.append("request.missing_binding_count must match clarification.missing_binding_count")

    _validate_source_payloads(payload, errors)
    _validate_counts(payload, contract_summary, errors)
    return errors


def _validate_source_payloads(payload: Mapping[str, Any], errors: list[str]) -> None:
    request = _mapping(payload.get("request"))
    interpretation = _mapping(payload.get("interpretation"))
    plan = _mapping(_mapping(payload.get("plan_preview")).get("plan"))
    approval_boundary = _mapping(payload.get("approval_boundary"))
    receipt_boundary = _mapping(payload.get("receipt_boundary"))

    request_payload = _load_and_validate_ref(request.get("source_ref"), REQUEST_SCHEMA, "request.source_ref", errors)
    if request_payload and request_payload.get("request_id") != request.get("request_id"):
        errors.append("request.source_ref request_id must match request.request_id")

    proposal_payload = _load_and_validate_ref(
        interpretation.get("source_ref"),
        INTERPRETATION_SCHEMA,
        "interpretation.source_ref",
        errors,
    )
    if proposal_payload:
        if proposal_payload.get("proposal_id") != interpretation.get("proposal_id"):
            errors.append("interpretation.source_ref proposal_id must match interpretation.proposal_id")
        if proposal_payload.get("request_id") != interpretation.get("gateway_request_id"):
            errors.append("interpretation.source_ref request_id must match interpretation.gateway_request_id")
        for field_name in (
            "deterministic_override_allowed",
            "action_authority_granted",
            "execution_allowed",
            "private_payload_included",
            "secret_values_serialized",
        ):
            if proposal_payload.get(field_name) is not False:
                errors.append(f"interpretation.source_ref {field_name} must be false")

    _validate_schema_payload(plan, PLAN_SCHEMA, "plan_preview.plan", errors)
    approval_payload = _load_and_validate_ref(
        approval_boundary.get("source_ref"),
        APPROVAL_SCHEMA,
        "approval_boundary.source_ref",
        errors,
    )
    if approval_payload:
        if approval_payload.get("approval_id") != approval_boundary.get("approval_id"):
            errors.append("approval_boundary.source_ref approval_id must match approval_boundary.approval_id")
        if approval_payload.get("request_id") != request.get("request_id"):
            errors.append("approval_boundary.source_ref request_id must match request.request_id")
        if approval_payload.get("metadata", {}).get("execution_allowed") is not False:
            errors.append("approval_boundary.source_ref metadata.execution_allowed must be false")

    receipt_payload = _load_and_validate_ref(
        receipt_boundary.get("source_ref"),
        RECEIPT_SCHEMA,
        "receipt_boundary.source_ref",
        errors,
    )
    if receipt_payload:
        errors.extend(
            f"receipt_boundary.source_ref {message}"
            for message in validate_personal_assistant_receipt_payload(receipt_payload)
        )
        if receipt_payload.get("request_id") != request.get("request_id"):
            errors.append("receipt_boundary.source_ref request_id must match request.request_id")
        receipt_refs = payload.get("receipt_refs", ())
        if receipt_payload.get("receipt_id") not in receipt_refs:
            errors.append("receipt_boundary.source_ref receipt_id must be listed in receipt_refs")

    for index, source_artifact in enumerate(_list(payload.get("source_artifacts"))):
        source_ref = source_artifact.get("source_ref") if isinstance(source_artifact, dict) else None
        schema_ref = source_artifact.get("schema_ref") if isinstance(source_artifact, dict) else None
        _resolve_repo_path(str(source_ref or ""), errors, f"source_artifacts[{index}].source_ref", must_exist=True)
        _resolve_repo_path(str(schema_ref or ""), errors, f"source_artifacts[{index}].schema_ref", must_exist=True)
        if isinstance(source_artifact, dict) and source_artifact.get("payload_digest_only") is not True:
            errors.append(f"source_artifacts[{index}].payload_digest_only must be true")


def _validate_counts(payload: Mapping[str, Any], contract_summary: Mapping[str, Any], errors: list[str]) -> None:
    source_artifacts = _list(payload.get("source_artifacts"))
    evidence_refs = _list(payload.get("evidence_refs"))
    receipt_refs = _list(payload.get("receipt_refs"))
    plan_steps = _list(_mapping(_mapping(payload.get("plan_preview")).get("plan")).get("steps"))
    missing_count = _mapping(payload.get("clarification")).get("missing_binding_count")
    if contract_summary.get("source_artifact_count") != len(source_artifacts):
        errors.append("contract_summary.source_artifact_count must match source_artifacts length")
    if contract_summary.get("evidence_ref_count") != len(evidence_refs):
        errors.append("contract_summary.evidence_ref_count must match evidence_refs length")
    if contract_summary.get("receipt_ref_count") != len(receipt_refs):
        errors.append("contract_summary.receipt_ref_count must match receipt_refs length")
    if contract_summary.get("plan_step_count") != len(plan_steps):
        errors.append("contract_summary.plan_step_count must match plan steps length")
    if contract_summary.get("missing_binding_count") != missing_count:
        errors.append("contract_summary.missing_binding_count must match clarification missing binding count")
    if contract_summary.get("customer_readiness_claim_allowed") is not False:
        errors.append("contract_summary.customer_readiness_claim_allowed must be false")
    if contract_summary.get("deployment_mutation_allowed") is not False:
        errors.append("contract_summary.deployment_mutation_allowed must be false")


def _load_and_validate_ref(
    source_ref: object,
    schema_path: Path,
    label: str,
    errors: list[str],
) -> dict[str, Any]:
    path = _resolve_repo_path(str(source_ref or ""), errors, label, must_exist=True)
    if path is None:
        return {}
    payload = _load_json_object(path, label, errors)
    if payload:
        _validate_schema_payload(payload, schema_path, label, errors)
    return payload


def _validate_schema_payload(payload: Mapping[str, Any], schema_path: Path, label: str, errors: list[str]) -> None:
    schema = _load_schema(schema_path)
    errors.extend(f"{label} {message}" for message in _validate_schema_instance(schema, dict(payload)))


def _require_false_fields(
    payload: Mapping[str, Any],
    field_names: tuple[str, ...],
    errors: list[str],
    *,
    prefix: str,
) -> None:
    for field_name in field_names:
        if payload.get(field_name) is not False:
            errors.append(f"{prefix}.{field_name} must be false")


def _scan_private_or_secret_payload(payload: Any, errors: list[str], *, path: str) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized_key = str(key).lower()
            if normalized_key in RAW_PRIVATE_FIELD_NAMES:
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


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"{label} could not be read: {exc}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{label} must be JSON: {exc}")
        return {}
    if not isinstance(parsed, dict):
        errors.append(f"{label} root must be an object")
        return {}
    return parsed


def _resolve_repo_path(path_text: str, errors: list[str], label: str, *, must_exist: bool) -> Path | None:
    if not path_text:
        errors.append(f"{label} must be present")
        return None
    candidate = (REPO_ROOT / path_text).resolve()
    root = REPO_ROOT.resolve()
    if candidate != root and root not in candidate.parents:
        errors.append(f"{label} must stay under repository root")
        return None
    if must_exist and not candidate.exists():
        errors.append(f"{label} does not exist")
        return None
    return candidate


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse intake-chain validation arguments."""
    parser = argparse.ArgumentParser(description="Validate personal-assistant intake-chain read model.")
    parser.add_argument("--read-model", default=str(DEFAULT_READ_MODEL))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = parse_args(argv)
    result = validate_personal_assistant_intake_chain_read_model(
        read_model_path=Path(args.read_model),
        schema_path=Path(args.schema),
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(
            "personal-assistant intake-chain read model ok "
            f"sources={result.source_artifact_count} receipts={result.receipt_ref_count}"
        )
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
