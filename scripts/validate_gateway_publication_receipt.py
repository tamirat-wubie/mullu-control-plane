#!/usr/bin/env python3
"""Validate gateway publication receipt state.

Purpose: turn the local gateway publication receipt into a reusable validation
gate for operator shells, CI jobs, and deployment witness closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.publish_gateway_publication receipt schema.
Invariants:
  - Receipt JSON must be structurally complete before policy checks pass.
  - Embedded readiness state must agree with top-level receipt fields.
  - Dispatch success is only accepted from an explicit dispatched state.
  - Validation writes its own local report before returning a status code.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.dispatch_deployment_witness import DEFAULT_REPOSITORY, VALID_ENVIRONMENTS  # noqa: E402
from scripts.publish_gateway_publication import DEFAULT_RECEIPT_OUTPUT  # noqa: E402

DEFAULT_VALIDATION_OUTPUT = (
    Path(".change_assurance") / "gateway_publication_receipt_validation.json"
)
VALID_RESOLUTION_STATES = frozenset(
    {"ready-only", "blocked-not-ready", "dispatched", "not-ready"}
)


@dataclass(frozen=True, slots=True)
class ReceiptValidationStep:
    """One gateway publication receipt validation step."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class GatewayPublicationReceiptValidation:
    """Structured validation report for one gateway publication receipt."""

    receipt_path: str
    valid: bool
    resolution_state: str
    steps: tuple[ReceiptValidationStep, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable validation payload."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def validate_gateway_publication_receipt(
    *,
    receipt_path: Path = DEFAULT_RECEIPT_OUTPUT,
    require_ready: bool = False,
    require_dispatched: bool = False,
    require_success: bool = False,
    expected_repository: str = "",
    expected_gateway_host: str = "",
    expected_gateway_url: str = "",
    expected_environment: str = "",
) -> GatewayPublicationReceiptValidation:
    """Validate one gateway publication receipt and optional policy gates."""
    payload = _read_receipt_payload(receipt_path)
    steps = [
        _check_required_fields(payload),
        _check_resolution_state(payload),
        _check_readiness_consistency(payload),
        _check_readiness_proof_steps(payload),
        _check_dispatch_consistency(payload),
        _check_dispatch_proof_quality(payload),
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
        _check_require_ready(payload=payload, require_ready=require_ready),
        _check_require_dispatched(
            payload=payload,
            require_dispatched=require_dispatched,
        ),
        _check_require_success(payload=payload, require_success=require_success),
    ]
    resolution_state = str(payload.get("resolution_state", ""))
    return GatewayPublicationReceiptValidation(
        receipt_path=str(receipt_path),
        valid=all(step.passed for step in steps),
        resolution_state=resolution_state,
        steps=tuple(steps),
    )


def write_receipt_validation_report(
    validation: GatewayPublicationReceiptValidation,
    output_path: Path,
) -> Path:
    """Write one local gateway publication receipt validation report."""
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
        raise RuntimeError("failed to read gateway publication receipt") from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("gateway publication receipt returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("gateway publication receipt was not a JSON object")
    return parsed


def _check_required_fields(payload: dict[str, Any]) -> ReceiptValidationStep:
    required_fields = {
        "artifact_dir": str,
        "dispatch_conclusion": str,
        "dispatch_performed": bool,
        "dispatch_requested": bool,
        "dispatch_run_id": int,
        "dispatch_run_url": str,
        "dispatch_status": str,
        "expected_environment": str,
        "gateway_host": str,
        "gateway_url": str,
        "readiness": dict,
        "readiness_ready": bool,
        "readiness_report": str,
        "receipt": str,
        "repository": str,
        "resolution_state": str,
    }
    missing = [field for field in required_fields if field not in payload]
    malformed = [
        field
        for field, field_type in required_fields.items()
        if field in payload and not isinstance(payload[field], field_type)
    ]
    if missing or malformed:
        return ReceiptValidationStep(
            "required fields",
            False,
            f"missing={missing} malformed={malformed}",
        )

    empty_strings = [
        field
        for field in (
            "expected_environment",
            "gateway_host",
            "gateway_url",
            "readiness_report",
            "receipt",
            "repository",
            "resolution_state",
        )
        if not str(payload.get(field, "")).strip()
    ]
    if empty_strings:
        return ReceiptValidationStep(
            "required fields",
            False,
            f"empty={empty_strings}",
        )
    return ReceiptValidationStep("required fields", True, "present")


def _check_resolution_state(payload: dict[str, Any]) -> ReceiptValidationStep:
    resolution_state = str(payload.get("resolution_state", ""))
    if resolution_state not in VALID_RESOLUTION_STATES:
        return ReceiptValidationStep(
            "resolution state",
            False,
            f"invalid={resolution_state}",
        )
    expected_state = _expected_resolution_state(payload)
    if expected_state != resolution_state:
        return ReceiptValidationStep(
            "resolution state",
            False,
            "state-mismatch",
        )
    return ReceiptValidationStep("resolution state", True, f"state={resolution_state}")


def _expected_resolution_state(payload: dict[str, Any]) -> str:
    dispatch_performed = payload.get("dispatch_performed")
    dispatch_requested = payload.get("dispatch_requested")
    readiness_ready = payload.get("readiness_ready")
    if dispatch_performed is True:
        return "dispatched"
    if dispatch_requested is True:
        return "blocked-not-ready" if readiness_ready is False else "invalid"
    if readiness_ready is True:
        return "ready-only"
    if readiness_ready is False:
        return "not-ready"
    return "invalid"


def _check_readiness_consistency(payload: dict[str, Any]) -> ReceiptValidationStep:
    readiness = payload.get("readiness")
    if not isinstance(readiness, dict):
        return ReceiptValidationStep("readiness consistency", False, "missing-readiness")
    mismatches: list[str] = []
    _append_mismatch(
        mismatches,
        "repository",
        payload.get("repository"),
        readiness.get("repository"),
    )
    _append_mismatch(
        mismatches,
        "gateway_host",
        payload.get("gateway_host"),
        readiness.get("gateway_host"),
    )
    _append_mismatch(
        mismatches,
        "gateway_url",
        payload.get("gateway_url"),
        readiness.get("gateway_url"),
    )
    _append_mismatch(
        mismatches,
        "expected_environment",
        payload.get("expected_environment"),
        readiness.get("expected_environment"),
    )
    _append_mismatch(
        mismatches,
        "readiness_ready",
        payload.get("readiness_ready"),
        readiness.get("ready"),
    )
    if mismatches:
        return ReceiptValidationStep(
            "readiness consistency",
            False,
            f"mismatched={mismatches}",
        )
    return ReceiptValidationStep("readiness consistency", True, "matched")


def _check_readiness_proof_steps(payload: dict[str, Any]) -> ReceiptValidationStep:
    readiness = payload.get("readiness")
    if not isinstance(readiness, dict):
        return ReceiptValidationStep("readiness proof steps", False, "missing-readiness")
    raw_steps = readiness.get("steps", ())
    if not isinstance(raw_steps, list):
        return ReceiptValidationStep("readiness proof steps", False, "steps-not-list")
    required_step_names = {
        "repository variables",
        "runtime witness secret",
        "kubeconfig secret",
        "gateway publication workflow",
        "dns resolution",
    }
    step_by_name = {
        str(step.get("name", "")): step
        for step in raw_steps
        if isinstance(step, dict)
    }
    missing = sorted(required_step_names - set(step_by_name))
    failed = sorted(
        name
        for name in required_step_names & set(step_by_name)
        if step_by_name[name].get("passed") is not True
    )
    if missing or failed:
        return ReceiptValidationStep(
            "readiness proof steps",
            False,
            f"missing={missing} failed={failed}",
        )
    return ReceiptValidationStep("readiness proof steps", True, "all-required-passed")


def _append_mismatch(
    mismatches: list[str],
    field_name: str,
    left_value: object,
    right_value: object,
) -> None:
    if left_value != right_value:
        mismatches.append(field_name)


def _check_dispatch_consistency(payload: dict[str, Any]) -> ReceiptValidationStep:
    dispatch_performed = payload.get("dispatch_performed")
    dispatch_requested = payload.get("dispatch_requested")
    dispatch_run_id = payload.get("dispatch_run_id")
    dispatch_run_url = str(payload.get("dispatch_run_url", ""))
    dispatch_status = str(payload.get("dispatch_status", ""))
    dispatch_conclusion = str(payload.get("dispatch_conclusion", ""))
    artifact_dir = str(payload.get("artifact_dir", ""))

    if dispatch_performed is True:
        missing = []
        if dispatch_requested is not True:
            missing.append("dispatch_requested")
        if not isinstance(dispatch_run_id, int) or dispatch_run_id <= 0:
            missing.append("dispatch_run_id")
        if not dispatch_run_url:
            missing.append("dispatch_run_url")
        if not dispatch_status:
            missing.append("dispatch_status")
        if not dispatch_conclusion:
            missing.append("dispatch_conclusion")
        if not artifact_dir:
            missing.append("artifact_dir")
        if missing:
            return ReceiptValidationStep(
                "dispatch consistency",
                False,
                f"missing={missing}",
            )
        return ReceiptValidationStep("dispatch consistency", True, "dispatched")

    forbidden = []
    if isinstance(dispatch_run_id, int) and dispatch_run_id != 0:
        forbidden.append("dispatch_run_id")
    for field_name, value in (
        ("dispatch_run_url", dispatch_run_url),
        ("dispatch_status", dispatch_status),
        ("dispatch_conclusion", dispatch_conclusion),
        ("artifact_dir", artifact_dir),
    ):
        if value:
            forbidden.append(field_name)
    if forbidden:
        return ReceiptValidationStep(
            "dispatch consistency",
            False,
            f"unexpected={forbidden}",
        )
    return ReceiptValidationStep("dispatch consistency", True, "not-dispatched")


def _check_dispatch_proof_quality(payload: dict[str, Any]) -> ReceiptValidationStep:
    if payload.get("dispatch_performed") is not True:
        return ReceiptValidationStep("dispatch proof quality", True, "not-dispatched")
    dispatch_run_url = str(payload.get("dispatch_run_url", ""))
    dispatch_status = str(payload.get("dispatch_status", ""))
    artifact_dir = str(payload.get("artifact_dir", ""))
    malformed = []
    if not dispatch_run_url.startswith("https://github.com/"):
        malformed.append("dispatch_run_url")
    if dispatch_status != "completed":
        malformed.append("dispatch_status")
    if not artifact_dir.strip():
        malformed.append("artifact_dir")
    if malformed:
        return ReceiptValidationStep(
            "dispatch proof quality",
            False,
            f"malformed={malformed}",
        )
    return ReceiptValidationStep("dispatch proof quality", True, "github-run-completed")


def _check_expected_value(
    *,
    payload: dict[str, Any],
    field_name: str,
    expected_value: str,
) -> ReceiptValidationStep:
    if not expected_value:
        return ReceiptValidationStep(f"expected {field_name}", True, "not-required")
    actual_value = str(payload.get(field_name, ""))
    return ReceiptValidationStep(
        f"expected {field_name}",
        actual_value == expected_value,
        "matched" if actual_value == expected_value else "mismatched",
    )


def _check_require_ready(
    *,
    payload: dict[str, Any],
    require_ready: bool,
) -> ReceiptValidationStep:
    if not require_ready:
        return ReceiptValidationStep("require ready", True, "not-required")
    readiness_ready = payload.get("readiness_ready")
    return ReceiptValidationStep(
        "require ready",
        readiness_ready is True,
        f"readiness_ready={readiness_ready}",
    )


def _check_require_dispatched(
    *,
    payload: dict[str, Any],
    require_dispatched: bool,
) -> ReceiptValidationStep:
    if not require_dispatched:
        return ReceiptValidationStep("require dispatched", True, "not-required")
    dispatch_performed = payload.get("dispatch_performed")
    return ReceiptValidationStep(
        "require dispatched",
        dispatch_performed is True,
        f"dispatch_performed={dispatch_performed}",
    )


def _check_require_success(
    *,
    payload: dict[str, Any],
    require_success: bool,
) -> ReceiptValidationStep:
    if not require_success:
        return ReceiptValidationStep("require success", True, "not-required")
    dispatch_performed = payload.get("dispatch_performed")
    dispatch_conclusion = str(payload.get("dispatch_conclusion", ""))
    passed = dispatch_performed is True and dispatch_conclusion == "success"
    return ReceiptValidationStep(
        "require success",
        passed,
        f"dispatch_performed={dispatch_performed} conclusion={dispatch_conclusion}",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse gateway publication receipt validation CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Validate a local gateway publication receipt."
    )
    parser.add_argument("--receipt", default=str(DEFAULT_RECEIPT_OUTPUT))
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--require-dispatched", action="store_true")
    parser.add_argument("--require-success", action="store_true")
    parser.add_argument("--expected-repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--expected-gateway-host", default="")
    parser.add_argument("--expected-gateway-url", default="")
    parser.add_argument("--expected-environment", choices=("", *VALID_ENVIRONMENTS), default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for gateway publication receipt validation."""
    args = parse_args(argv)
    try:
        validation = validate_gateway_publication_receipt(
            receipt_path=Path(args.receipt),
            require_ready=args.require_ready,
            require_dispatched=args.require_dispatched,
            require_success=args.require_success,
            expected_repository=args.expected_repository,
            expected_gateway_host=args.expected_gateway_host,
            expected_gateway_url=args.expected_gateway_url,
            expected_environment=args.expected_environment,
        )
    except RuntimeError:
        print("gateway publication receipt validation failed")
        return 1

    output_path = write_receipt_validation_report(validation, Path(args.output))
    print(f"validation_report: {output_path}")
    print(f"receipt: {validation.receipt_path}")
    print(f"resolution_state: {validation.resolution_state}")
    print(f"valid: {str(validation.valid).lower()}")
    for step in validation.steps:
        print(f"step: {step.name} passed={str(step.passed).lower()} detail={step.detail}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
