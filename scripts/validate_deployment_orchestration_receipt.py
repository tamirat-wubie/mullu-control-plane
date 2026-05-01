#!/usr/bin/env python3
"""Validate deployment witness orchestration receipts.

Purpose: turn deployment orchestration receipts into reusable handoff evidence
for operator shells, CI jobs, and release promotion.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.orchestrate_deployment_witness receipt contract.
Invariants:
  - Receipt JSON must be structurally complete before policy checks pass.
  - Required MCP checklist, preflight, and dispatch gates fail closed.
  - Evidence references must name ingress, target, preflight, dispatch, and
    checklist state.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.orchestrate_deployment_witness import DEFAULT_ORCHESTRATION_OUTPUT  # noqa: E402
from scripts.provision_deployment_target import (  # noqa: E402
    DEFAULT_REPOSITORY,
    VALID_ENVIRONMENTS,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_VALIDATION_OUTPUT = (
    Path(".change_assurance") / "deployment_witness_orchestration_validation.json"
)
ORCHESTRATION_RECEIPT_SCHEMA_PATH = (
    REPO_ROOT / "schemas" / "deployment_orchestration_receipt.schema.json"
)
RECEIPT_ID_PATTERN = re.compile(r"^deployment-witness-orchestration-[0-9a-f]{16}$")


@dataclass(frozen=True, slots=True)
class OrchestrationReceiptValidationStep:
    """One deployment orchestration receipt validation step."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class DeploymentOrchestrationReceiptValidation:
    """Structured validation report for one orchestration receipt."""

    receipt_path: str
    valid: bool
    receipt_id: str
    steps: tuple[OrchestrationReceiptValidationStep, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable validation payload."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def validate_deployment_orchestration_receipt(
    *,
    receipt_path: Path = DEFAULT_ORCHESTRATION_OUTPUT,
    require_preflight: bool = False,
    require_mcp_operator_checklist: bool = False,
    require_dispatch: bool = False,
    require_success: bool = False,
    expected_repository: str = "",
    expected_gateway_host: str = "",
    expected_gateway_url: str = "",
    expected_environment: str = "",
) -> DeploymentOrchestrationReceiptValidation:
    """Validate one deployment orchestration receipt and optional policy gates."""
    payload = _read_receipt_payload(receipt_path)
    steps = [
        _check_schema_contract(payload),
        _check_required_fields(payload),
        _check_receipt_id(payload),
        _check_evidence_refs(payload),
        _check_preflight_policy(payload, require_preflight=require_preflight),
        _check_mcp_checklist_policy(
            payload,
            require_mcp_operator_checklist=require_mcp_operator_checklist,
        ),
        _check_dispatch_policy(payload, require_dispatch=require_dispatch),
        _check_success_policy(payload, require_success=require_success),
        _check_expected_value(
            payload=payload,
            field_name="repository",
            expected_value=expected_repository,
        ),
        _check_expected_value(
            payload=payload,
            field_name="gateway_host",
            expected_value=expected_gateway_host,
        ),
        _check_expected_value(
            payload=payload,
            field_name="gateway_url",
            expected_value=expected_gateway_url.rstrip("/") if expected_gateway_url else "",
        ),
        _check_expected_value(
            payload=payload,
            field_name="expected_environment",
            expected_value=expected_environment,
        ),
    ]
    return DeploymentOrchestrationReceiptValidation(
        receipt_path=str(receipt_path),
        valid=all(step.passed for step in steps),
        receipt_id=str(payload.get("receipt_id", "")),
        steps=tuple(steps),
    )


def write_orchestration_receipt_validation_report(
    validation: DeploymentOrchestrationReceiptValidation,
    output_path: Path,
) -> Path:
    """Write one local deployment orchestration receipt validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.to_json_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _read_receipt_payload(receipt_path: Path) -> dict[str, Any]:
    try:
        raw_text = receipt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"failed to read deployment orchestration receipt {receipt_path}"
        ) from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("deployment orchestration receipt returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("deployment orchestration receipt was not a JSON object")
    return parsed


def _check_schema_contract(payload: dict[str, Any]) -> OrchestrationReceiptValidationStep:
    try:
        schema = _load_schema(ORCHESTRATION_RECEIPT_SCHEMA_PATH)
    except OSError as exc:
        return OrchestrationReceiptValidationStep(
            "schema contract",
            False,
            f"schema-read-failed:{exc}",
        )
    errors = _validate_schema_instance(schema, payload)
    return OrchestrationReceiptValidationStep(
        "schema contract",
        not errors,
        "valid" if not errors else f"errors={errors}",
    )


def _check_required_fields(payload: dict[str, Any]) -> OrchestrationReceiptValidationStep:
    required_fields = {
        "receipt_id": str,
        "gateway_host": str,
        "gateway_url": str,
        "expected_environment": str,
        "repository": str,
        "rendered_ingress_output": str,
        "ingress_applied": bool,
        "preflight_required": bool,
        "dispatch_requested": bool,
        "dispatch_conclusion": str,
        "mcp_operator_checklist_required": bool,
        "mcp_operator_checklist_path": str,
        "evidence_refs": list,
    }
    required_nullable_fields = {
        "preflight_ready": (bool, type(None)),
        "dispatch_run_id": (int, type(None)),
        "mcp_operator_checklist_valid": (bool, type(None)),
    }
    missing = [
        field
        for field in (*required_fields, *required_nullable_fields)
        if field not in payload
    ]
    malformed = [
        field
        for field, field_type in required_fields.items()
        if field in payload and not isinstance(payload[field], field_type)
    ]
    malformed.extend(
        field
        for field, field_type in required_nullable_fields.items()
        if field in payload and not isinstance(payload[field], field_type)
    )
    if missing or malformed:
        return OrchestrationReceiptValidationStep(
            "required fields",
            False,
            f"missing={missing} malformed={malformed}",
        )
    empty_strings = [
        field
        for field in (
            "gateway_host",
            "gateway_url",
            "expected_environment",
            "repository",
            "rendered_ingress_output",
            "mcp_operator_checklist_path",
        )
        if not str(payload.get(field, "")).strip()
    ]
    return OrchestrationReceiptValidationStep(
        "required fields",
        not empty_strings,
        "present" if not empty_strings else f"empty={empty_strings}",
    )


def _check_receipt_id(payload: dict[str, Any]) -> OrchestrationReceiptValidationStep:
    receipt_id = str(payload.get("receipt_id", ""))
    passed = RECEIPT_ID_PATTERN.fullmatch(receipt_id) is not None
    return OrchestrationReceiptValidationStep(
        "receipt id",
        passed,
        f"receipt_id={receipt_id}",
    )


def _check_evidence_refs(payload: dict[str, Any]) -> OrchestrationReceiptValidationStep:
    refs = payload.get("evidence_refs", [])
    if not isinstance(refs, list):
        return OrchestrationReceiptValidationStep("evidence refs", False, "not-list")
    required_prefixes = (
        "ingress_render:",
        "deployment_target:",
        "preflight:",
        "dispatch:",
        "mcp_operator_checklist:",
    )
    missing = [
        prefix
        for prefix in required_prefixes
        if not any(str(ref).startswith(prefix) for ref in refs)
    ]
    return OrchestrationReceiptValidationStep(
        "evidence refs",
        not missing,
        f"missing={missing}",
    )


def _check_preflight_policy(
    payload: dict[str, Any],
    *,
    require_preflight: bool,
) -> OrchestrationReceiptValidationStep:
    if not require_preflight:
        return OrchestrationReceiptValidationStep(
            "require preflight",
            True,
            "not-required",
        )
    passed = (
        payload.get("preflight_required") is True
        and payload.get("preflight_ready") is True
    )
    return OrchestrationReceiptValidationStep(
        "require preflight",
        passed,
        (
            f"preflight_required={payload.get('preflight_required')} "
            f"preflight_ready={payload.get('preflight_ready')}"
        ),
    )


def _check_mcp_checklist_policy(
    payload: dict[str, Any],
    *,
    require_mcp_operator_checklist: bool,
) -> OrchestrationReceiptValidationStep:
    if not require_mcp_operator_checklist:
        return OrchestrationReceiptValidationStep(
            "require mcp operator checklist",
            True,
            "not-required",
        )
    passed = (
        payload.get("mcp_operator_checklist_required") is True
        and payload.get("mcp_operator_checklist_valid") is True
    )
    return OrchestrationReceiptValidationStep(
        "require mcp operator checklist",
        passed,
        (
            f"required={payload.get('mcp_operator_checklist_required')} "
            f"valid={payload.get('mcp_operator_checklist_valid')}"
        ),
    )


def _check_dispatch_policy(
    payload: dict[str, Any],
    *,
    require_dispatch: bool,
) -> OrchestrationReceiptValidationStep:
    if not require_dispatch:
        return OrchestrationReceiptValidationStep(
            "require dispatch",
            True,
            "not-required",
        )
    passed = (
        payload.get("dispatch_requested") is True
        and isinstance(payload.get("dispatch_run_id"), int)
    )
    return OrchestrationReceiptValidationStep(
        "require dispatch",
        passed,
        (
            f"dispatch_requested={payload.get('dispatch_requested')} "
            f"dispatch_run_id={payload.get('dispatch_run_id')}"
        ),
    )


def _check_success_policy(
    payload: dict[str, Any],
    *,
    require_success: bool,
) -> OrchestrationReceiptValidationStep:
    if not require_success:
        return OrchestrationReceiptValidationStep(
            "require success",
            True,
            "not-required",
        )
    passed = (
        payload.get("dispatch_requested") is True
        and payload.get("dispatch_conclusion") == "success"
    )
    return OrchestrationReceiptValidationStep(
        "require success",
        passed,
        (
            f"dispatch_requested={payload.get('dispatch_requested')} "
            f"conclusion={payload.get('dispatch_conclusion')}"
        ),
    )


def _check_expected_value(
    *,
    payload: dict[str, Any],
    field_name: str,
    expected_value: str,
) -> OrchestrationReceiptValidationStep:
    if not expected_value:
        return OrchestrationReceiptValidationStep(
            f"expected {field_name}",
            True,
            "not-required",
        )
    actual_value = str(payload.get(field_name, ""))
    return OrchestrationReceiptValidationStep(
        f"expected {field_name}",
        actual_value == expected_value,
        f"expected={expected_value} actual={actual_value}",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse deployment orchestration receipt validation CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Validate a deployment orchestration receipt."
    )
    parser.add_argument("--receipt", default=str(DEFAULT_ORCHESTRATION_OUTPUT))
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-preflight", action="store_true")
    parser.add_argument("--require-mcp-operator-checklist", action="store_true")
    parser.add_argument("--require-dispatch", action="store_true")
    parser.add_argument("--require-success", action="store_true")
    parser.add_argument("--expected-repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--expected-gateway-host", default="")
    parser.add_argument("--expected-gateway-url", default="")
    parser.add_argument(
        "--expected-environment",
        choices=("", *VALID_ENVIRONMENTS),
        default="",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for deployment orchestration receipt validation."""
    args = parse_args(argv)
    try:
        validation = validate_deployment_orchestration_receipt(
            receipt_path=Path(args.receipt),
            require_preflight=args.require_preflight,
            require_mcp_operator_checklist=args.require_mcp_operator_checklist,
            require_dispatch=args.require_dispatch,
            require_success=args.require_success,
            expected_repository=args.expected_repository,
            expected_gateway_host=args.expected_gateway_host,
            expected_gateway_url=args.expected_gateway_url,
            expected_environment=args.expected_environment,
        )
    except RuntimeError as exc:
        print(f"deployment orchestration receipt validation failed: {exc}")
        return 1

    output_path = write_orchestration_receipt_validation_report(
        validation,
        Path(args.output),
    )
    print(f"validation_report: {output_path}")
    print(f"receipt: {validation.receipt_path}")
    print(f"receipt_id: {validation.receipt_id}")
    print(f"valid: {str(validation.valid).lower()}")
    for step in validation.steps:
        print(
            f"step: {step.name} "
            f"passed={str(step.passed).lower()} "
            f"detail={step.detail}"
        )
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
