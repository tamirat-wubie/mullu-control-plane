#!/usr/bin/env python3
"""Run the Foundation Mode local proof thread.

Purpose: execute one harmless local proof-thread rehearsal and emit local
result and receipt evidence.
Governance scope: Foundation Mode, local-only workflow execution, approval
gate, receipt evidence, verification, rollback note, and no external effects.
Dependencies: examples/foundation_local_proof_thread.workflow.json and
scripts/validate_foundation_local_proof_thread.py.
Invariants:
  - No network, deployment, DNS, payment, customer-access, or credential action.
  - The descriptor must validate before any output is written.
  - The local action is approval-gated by the operator request.
  - The receipt names a rollback/recovery path.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

try:
    from validate_foundation_local_proof_thread import (  # type: ignore
        DEFAULT_DESCRIPTOR_PATH,
        validate_foundation_local_proof_thread,
    )
except ModuleNotFoundError:  # pragma: no cover - exercised when imported as package.
    from scripts.validate_foundation_local_proof_thread import (  # type: ignore
        DEFAULT_DESCRIPTOR_PATH,
        validate_foundation_local_proof_thread,
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULT_OUTPUT = REPO_ROOT / ".change_assurance" / "foundation_local_proof_thread_result.json"
DEFAULT_RECEIPT_OUTPUT = REPO_ROOT / ".change_assurance" / "foundation_local_proof_thread_receipt.json"
DEFAULT_APPROVAL_REF = "user-request://current-thread/continue-foundation-local-proof-thread"
EXPECTED_STAGE_IDS = (
    "stage_intake",
    "stage_classify_intent",
    "stage_policy_authority_check",
    "stage_local_approval",
    "stage_create_local_result",
    "stage_verify_local_result",
    "stage_record_rollback_note",
    "stage_close_receipt",
)


@dataclass(frozen=True, slots=True)
class LocalProofRun:
    """One local proof-thread run payload."""

    result: dict[str, Any]
    receipt: dict[str, Any]


def run_foundation_local_proof_thread(
    *,
    descriptor_path: Path = DEFAULT_DESCRIPTOR_PATH,
    result_output: Path = DEFAULT_RESULT_OUTPUT,
    receipt_output: Path = DEFAULT_RECEIPT_OUTPUT,
    approval_ref: str = DEFAULT_APPROVAL_REF,
    now_utc: datetime | None = None,
    dry_run: bool = False,
) -> LocalProofRun:
    """Run the local proof thread and optionally write result and receipt files."""

    validation_findings = validate_foundation_local_proof_thread(descriptor_path=descriptor_path)
    if validation_findings:
        finding_messages = "; ".join(f"{finding.rule_id}: {finding.message}" for finding in validation_findings)
        raise RuntimeError(f"foundation local proof-thread descriptor is invalid: {finding_messages}")

    descriptor = _load_json_object(descriptor_path, "local proof-thread descriptor")
    checked_at = _format_utc(now_utc or datetime.now(UTC))
    relative_result_ref = _relative_workspace_path(result_output)
    relative_receipt_ref = _relative_workspace_path(receipt_output)
    result = _build_local_result(
        workflow_id=descriptor["workflow_id"],
        checked_at_utc=checked_at,
        result_ref=relative_result_ref,
    )
    receipt = _build_local_receipt(
        descriptor=descriptor,
        checked_at_utc=checked_at,
        approval_ref=approval_ref,
        result_ref=relative_result_ref,
        receipt_ref=relative_receipt_ref,
    )
    receipt_errors = validate_local_proof_run_receipt(receipt=receipt, result=result)
    if receipt_errors:
        raise RuntimeError(f"foundation local proof-thread receipt is invalid: {'; '.join(receipt_errors)}")
    if not dry_run:
        _write_json(result_output, result)
        _write_json(receipt_output, receipt)
    return LocalProofRun(result=result, receipt=receipt)


def validate_local_proof_run_receipt(*, receipt: dict[str, Any], result: dict[str, Any]) -> list[str]:
    """Return deterministic validation errors for one local proof-thread receipt."""

    errors: list[str] = []
    if receipt.get("receipt_type") != "foundation_local_proof_thread_receipt":
        errors.append("receipt_type must be foundation_local_proof_thread_receipt")
    if receipt.get("status") != "passed":
        errors.append("receipt status must be passed")
    if receipt.get("proof_state") != "Pass":
        errors.append("proof_state must be Pass")
    if receipt.get("solver_outcome") != "SolvedVerified":
        errors.append("solver_outcome must be SolvedVerified")
    if receipt.get("approval_ref") != DEFAULT_APPROVAL_REF and not str(receipt.get("approval_ref", "")).startswith(
        "approval://"
    ):
        errors.append("approval_ref must be default user request ref or approval:// ref")
    stage_results = receipt.get("stage_results")
    if not isinstance(stage_results, list):
        errors.append("stage_results must be a list")
    else:
        observed_stage_ids = tuple(stage.get("stage_id") for stage in stage_results if isinstance(stage, dict))
        if observed_stage_ids != EXPECTED_STAGE_IDS:
            errors.append("stage_results must preserve expected proof-thread stage order")
        if any(stage.get("status") != "completed" for stage in stage_results if isinstance(stage, dict)):
            errors.append("all stage_results must be completed")
    external_effects = receipt.get("external_effects")
    if not isinstance(external_effects, dict):
        errors.append("external_effects must be an object")
    else:
        for key, value in external_effects.items():
            if value is not False:
                errors.append(f"external_effects.{key} must be false")
    rollback = receipt.get("rollback")
    if not isinstance(rollback, dict):
        errors.append("rollback must be an object")
    elif not rollback.get("safe_to_delete"):
        errors.append("rollback.safe_to_delete must be true")
    result_external_effects = result.get("external_effects")
    if not isinstance(result_external_effects, dict):
        errors.append("result.external_effects must be an object")
    elif any(value is not False for value in result_external_effects.values()):
        errors.append("result external effects must all be false")
    return errors


def main(argv: list[str] | None = None) -> int:
    """Run the local proof thread and print deterministic status."""

    parser = argparse.ArgumentParser(description="Run the Foundation Mode local proof thread.")
    parser.add_argument("--descriptor", type=Path, default=DEFAULT_DESCRIPTOR_PATH)
    parser.add_argument("--result-output", type=Path, default=DEFAULT_RESULT_OUTPUT)
    parser.add_argument("--receipt-output", type=Path, default=DEFAULT_RECEIPT_OUTPUT)
    parser.add_argument("--approval-ref", default=DEFAULT_APPROVAL_REF)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", help="print receipt JSON")
    args = parser.parse_args(argv)

    try:
        run = run_foundation_local_proof_thread(
            descriptor_path=args.descriptor,
            result_output=args.result_output,
            receipt_output=args.receipt_output,
            approval_ref=args.approval_ref,
            dry_run=args.dry_run,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_local_proof_run: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(run.receipt, indent=2, sort_keys=True))
    if not args.dry_run:
        print(f"result: {_relative_workspace_path(args.result_output)}")
        print(f"receipt: {_relative_workspace_path(args.receipt_output)}")
    else:
        print("dry_run: true")
    print("STATUS: passed")
    return 0


def _build_local_result(*, workflow_id: str, checked_at_utc: str, result_ref: str) -> dict[str, Any]:
    material = {
        "workflow_id": workflow_id,
        "checked_at_utc": checked_at_utc,
        "result_ref": result_ref,
    }
    return {
        "result_id": _stable_identifier("foundation-local-proof-result", material),
        "result_type": "foundation_local_proof_thread_result",
        "workflow_id": workflow_id,
        "checked_at_utc": checked_at_utc,
        "summary": "Harmless local result proving the Foundation Mode proof-thread control shape.",
        "allowed_claims": [
            "local descriptor executed as a harmless proof-thread rehearsal",
            "operator approval was represented before local result creation",
            "rollback path was named before closure",
        ],
        "blocked_claims": [
            "customer access",
            "public deployment readiness",
            "public endpoint readiness",
            "real payment movement",
            "legal or company readiness",
        ],
        "external_effects": {
            "network_used": False,
            "credentials_used": False,
            "money_moved": False,
            "message_sent": False,
            "deployment_mutated": False,
            "dns_mutated": False,
            "customer_access_mutated": False,
        },
    }


def _build_local_receipt(
    *,
    descriptor: dict[str, Any],
    checked_at_utc: str,
    approval_ref: str,
    result_ref: str,
    receipt_ref: str,
) -> dict[str, Any]:
    stage_results = _build_stage_results(approval_ref=approval_ref, result_ref=result_ref)
    receipt_material = {
        "workflow_id": descriptor["workflow_id"],
        "checked_at_utc": checked_at_utc,
        "approval_ref": approval_ref,
        "result_ref": result_ref,
        "stage_ids": [stage["stage_id"] for stage in stage_results],
    }
    return {
        "receipt_id": _stable_identifier("foundation-local-proof-thread", receipt_material),
        "receipt_type": "foundation_local_proof_thread_receipt",
        "receipt_is_not_terminal_closure": True,
        "workflow_id": descriptor["workflow_id"],
        "workflow_descriptor_ref": "examples/foundation_local_proof_thread.workflow.json",
        "status": "passed",
        "proof_state": "Pass",
        "solver_outcome": "SolvedVerified",
        "checked_at_utc": checked_at_utc,
        "approval_ref": approval_ref,
        "result_ref": result_ref,
        "receipt_ref": receipt_ref,
        "external_effects": {
            "network_used": False,
            "credentials_used": False,
            "money_moved": False,
            "message_sent": False,
            "deployment_mutated": False,
            "dns_mutated": False,
            "customer_access_mutated": False,
        },
        "claim_boundary": {
            "can_claim": [
                "local proof-thread receipt emitted",
                "descriptor topology validated before local output",
                "approval gate represented before local result creation",
                "rollback path named before closure",
            ],
            "must_not_claim": [
                "customer access",
                "public deployment readiness",
                "public endpoint readiness",
                "real payment movement",
                "legal or company readiness",
            ],
        },
        "stage_results": stage_results,
        "verification": {
            "descriptor_validated": True,
            "stage_order_validated": True,
            "approval_before_local_result": True,
            "rollback_before_closure": True,
            "external_effects_absent": True,
        },
        "rollback": {
            "strategy": "delete or ignore local .change_assurance artifacts if this rehearsal should be discarded",
            "local_artifacts": [result_ref, receipt_ref],
            "safe_to_delete": True,
        },
        "next_action": "review the local receipt, then choose either commit boundary or another Foundation Mode prerequisite",
    }


def _build_stage_results(*, approval_ref: str, result_ref: str) -> list[dict[str, Any]]:
    return [
        {
            "stage_id": "stage_intake",
            "stage_type": "observation",
            "status": "completed",
            "evidence_refs": ["request://foundation/local-proof-thread/continue"],
            "output": {"local_request_ref": "request://foundation/local-proof-thread/continue"},
        },
        {
            "stage_id": "stage_classify_intent",
            "stage_type": "skill_execution",
            "status": "completed",
            "evidence_refs": ["classification://foundation/local-proof/local-only"],
            "output": {"intent_classification_ref": "classification://foundation/local-proof/local-only"},
        },
        {
            "stage_id": "stage_policy_authority_check",
            "stage_type": "skill_execution",
            "status": "completed",
            "evidence_refs": ["policy://foundation/local-proof/allowed-local-only"],
            "output": {"policy_decision_ref": "policy://foundation/local-proof/allowed-local-only"},
        },
        {
            "stage_id": "stage_local_approval",
            "stage_type": "approval_gate",
            "status": "completed",
            "evidence_refs": [approval_ref],
            "output": {"approval_ref": approval_ref},
        },
        {
            "stage_id": "stage_create_local_result",
            "stage_type": "skill_execution",
            "status": "completed",
            "evidence_refs": [result_ref],
            "output": {"local_result_ref": result_ref},
        },
        {
            "stage_id": "stage_verify_local_result",
            "stage_type": "observation",
            "status": "completed",
            "evidence_refs": ["verification://foundation/local-proof/no-external-effects"],
            "output": {"verification_ref": "verification://foundation/local-proof/no-external-effects"},
        },
        {
            "stage_id": "stage_record_rollback_note",
            "stage_type": "skill_execution",
            "status": "completed",
            "evidence_refs": ["rollback://foundation/local-proof/delete-local-artifacts"],
            "output": {"rollback_note_ref": "rollback://foundation/local-proof/delete-local-artifacts"},
        },
        {
            "stage_id": "stage_close_receipt",
            "stage_type": "observation",
            "status": "completed",
            "evidence_refs": ["closure://foundation/local-proof/passed"],
            "output": {"closure_receipt_ref": "closure://foundation/local-proof/passed"},
        },
    ]


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _write_json(output_path: Path, payload: dict[str, Any]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_identifier(prefix: str, material: dict[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:16]}"


def _relative_workspace_path(path: Path) -> str:
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved_path)


if __name__ == "__main__":
    raise SystemExit(main())
