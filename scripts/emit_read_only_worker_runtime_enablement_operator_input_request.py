#!/usr/bin/env python3
"""Emit missing operator inputs for read-only worker runtime enablement.

Purpose: translate a blocked runtime enablement witness into an operator-safe
input request that names missing evidence without enabling runtime execution.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: read-only worker runtime enablement witness artifacts and
schemas/read_only_worker_runtime_enablement_operator_input_request.schema.json.
Invariants:
  - The request serializes evidence names only, never secret values.
  - Runtime enablement, dispatch, worker invocation, receipt emission, receipt
    append, and terminal closure remain unperformed.
  - Mfidel atomicity is preserved.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_read_only_worker_runtime_enablement_witness import (  # noqa: E402
    DEFAULT_RECEIPT_PATH as DEFAULT_WITNESS,
    validate_runtime_enablement_witness,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "read_only_worker_runtime_enablement_operator_input_request.schema.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "read_only_worker_runtime_enablement_operator_input_request.json"
)
BLOCKED_ACTIONS = (
    "read_only_worker_runtime_enablement",
    "read_only_worker_runtime_dispatch_admission",
    "read_only_worker_runtime_dispatch",
    "read_only_worker_invocation",
    "read_only_worker_runtime_receipt_emission",
    "read_only_worker_receipt_append",
    "read_only_worker_terminal_closure_claim",
)
EVIDENCE_INPUTS: dict[str, tuple[str, tuple[str, ...], str, str]] = {
    "evidence://terminal-closure/certificate": (
        "terminal_closure_certificate",
        ("read_only_worker_terminal_closure_certificate",),
        "blocked://terminal-closure/certificate-missing",
        "bind the terminal closure certificate, then rerun the runtime enablement witness validator",
    ),
    "evidence://runtime-runner/registered": (
        "runtime_runner_registration",
        ("read_only_worker_runtime_runner_registration_receipt",),
        "blocked://runtime-runner/not-registered",
        "register the read-only worker runtime runner and bind its receipt",
    ),
    "evidence://runtime-dispatch-endpoint/registered": (
        "runtime_dispatch_endpoint_registration",
        ("read_only_worker_runtime_dispatch_endpoint_registration_receipt",),
        "blocked://runtime-dispatch-endpoint/not-registered",
        "register the runtime dispatch endpoint and bind its receipt",
    ),
    "evidence://runtime-receipt-emitter/registered": (
        "runtime_receipt_emitter_registration",
        ("read_only_worker_runtime_receipt_emitter_registration_receipt",),
        "blocked://runtime-receipt-emitter/not-registered",
        "register the runtime receipt emitter and bind its receipt",
    ),
    "evidence://runtime-receipt-store/activated": (
        "runtime_receipt_store_activation",
        ("read_only_worker_runtime_receipt_store_activation_receipt",),
        "blocked://runtime-receipt-store/not-activated",
        "activate the runtime receipt store and bind its activation receipt",
    ),
    "evidence://operator-approval/runtime-enablement": (
        "operator_runtime_enablement_approval",
        ("MULLU_READ_ONLY_WORKER_RUNTIME_ENABLEMENT_APPROVAL_REF",),
        "blocked://operator-approval/runtime-enablement-missing",
        "record operator runtime enablement approval as a reference, not a secret value",
    ),
    "evidence://active-runtime-lease/observed": (
        "active_runtime_lease_observation",
        ("read_only_worker_active_runtime_lease_observation",),
        "blocked://active-runtime-lease/not-observed",
        "observe and bind the active runtime lease evidence",
    ),
    "evidence://uao-dispatch-authorization": (
        "uao_dispatch_authorization",
        ("read_only_worker_uao_dispatch_authorization_receipt",),
        "blocked://uao-dispatch-authorization/missing",
        "bind UAO dispatch authorization evidence",
    ),
    "evidence://phi-gov-dispatch-authorization": (
        "phi_gov_dispatch_authorization",
        ("read_only_worker_phi_gov_dispatch_authorization_receipt",),
        "blocked://phi-gov-dispatch-authorization/missing",
        "bind Phi_gov dispatch authorization evidence",
    ),
    "evidence://runtime-dispatch-admission": (
        "runtime_dispatch_admission",
        ("read_only_worker_runtime_dispatch_admission_receipt",),
        "blocked://runtime-dispatch-admission/missing",
        "bind runtime dispatch admission evidence",
    ),
    "evidence://runtime-disablement-rollback-plan": (
        "runtime_disablement_rollback_plan",
        ("read_only_worker_runtime_disablement_rollback_plan",),
        "blocked://runtime-disablement-rollback-plan/missing",
        "bind runtime disablement and rollback plan evidence",
    ),
    "evidence://runtime-clock/trusted-now": (
        "trusted_runtime_clock",
        ("read_only_worker_trusted_runtime_clock_receipt",),
        "blocked://runtime-clock/trusted-now-missing",
        "bind trusted runtime clock evidence",
    ),
}


@dataclass(frozen=True, slots=True)
class RuntimeEnablementOperatorInput:
    """One missing evidence item for runtime enablement."""

    input_id: str
    blocker: str
    input_kind: str
    required_names: tuple[str, ...]
    current_state: str
    evidence_source: str
    next_action: str


@dataclass(frozen=True, slots=True)
class RuntimeEnablementOperatorInputRequest:
    """Operator-safe request for read-only worker runtime enablement evidence."""

    request_id: str
    witness_receipt_id: str
    ready: bool
    runtime_enablement_allowed: bool
    witness_validation_ok: bool
    solver_outcome: str
    proof_state: str
    required_inputs: tuple[RuntimeEnablementOperatorInput, ...]
    blocked_actions: tuple[str, ...]
    source_artifacts: dict[str, str]
    runtime_enablement_summary: dict[str, Any]
    no_secret_values_serialized: bool
    runtime_enablement_executed: bool
    runtime_dispatch_performed: bool
    worker_invocation_performed: bool
    runtime_receipt_emitted: bool
    receipt_append_performed: bool
    terminal_closure_performed: bool
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready request payload."""

        payload = asdict(self)
        payload["required_inputs"] = [
            {
                **asdict(item),
                "required_names": list(item.required_names),
            }
            for item in self.required_inputs
        ]
        payload["blocked_actions"] = list(self.blocked_actions)
        return payload


def emit_runtime_enablement_operator_input_request(
    *,
    witness_path: Path = DEFAULT_WITNESS,
    schema_path: Path = DEFAULT_SCHEMA,
) -> RuntimeEnablementOperatorInputRequest:
    """Build one blocked operator input request from a runtime witness."""

    witness = _load_json_object(witness_path, "runtime enablement witness")
    validation_errors = validate_runtime_enablement_witness(receipt_path=witness_path)
    witness_validation_ok = not validation_errors
    required_inputs = _derive_required_inputs(witness, witness_validation_ok)
    request = RuntimeEnablementOperatorInputRequest(
        request_id=_request_id(witness, required_inputs, witness_validation_ok),
        witness_receipt_id=str(witness.get("receipt_id", "")),
        ready=False,
        runtime_enablement_allowed=False,
        witness_validation_ok=witness_validation_ok,
        solver_outcome="AwaitingEvidence" if witness_validation_ok else "GovernanceBlocked",
        proof_state="Unknown" if witness_validation_ok else "Fail",
        required_inputs=required_inputs,
        blocked_actions=BLOCKED_ACTIONS,
        source_artifacts={
            "read_only_worker_runtime_enablement_witness": _path_label(witness_path)
        },
        runtime_enablement_summary=_runtime_enablement_summary(witness),
        no_secret_values_serialized=True,
        runtime_enablement_executed=False,
        runtime_dispatch_performed=False,
        worker_invocation_performed=False,
        runtime_receipt_emitted=False,
        receipt_append_performed=False,
        terminal_closure_performed=False,
        next_action=_next_action(required_inputs, witness_validation_ok),
    )
    _validate_request_against_schema(request, schema_path)
    return request


def write_runtime_enablement_operator_input_request(
    request: RuntimeEnablementOperatorInputRequest,
    output_path: Path,
) -> Path:
    """Write one operator input request JSON report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(request.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _derive_required_inputs(
    witness: dict[str, Any],
    witness_validation_ok: bool,
) -> tuple[RuntimeEnablementOperatorInput, ...]:
    if not witness_validation_ok:
        return (
            _operator_input(
                blocker="blocked://runtime-enablement-witness/invalid",
                input_kind="valid_runtime_enablement_witness",
                required_names=("read_only_worker_runtime_enablement_witness",),
                current_state="present_invalid",
                next_action="repair the runtime enablement witness before collecting operator inputs",
            ),
        )

    decision = witness.get("admission_decision", {})
    denied_refs = decision.get("remaining_denied_until_refs", [])
    required_inputs: list[RuntimeEnablementOperatorInput] = []
    if isinstance(denied_refs, list):
        for denied_ref in denied_refs:
            input_spec = EVIDENCE_INPUTS.get(str(denied_ref))
            if input_spec is None:
                continue
            input_kind, required_names, blocker, next_action = input_spec
            required_inputs.append(
                _operator_input(
                    blocker=blocker,
                    input_kind=input_kind,
                    required_names=required_names,
                    current_state="awaiting_evidence",
                    next_action=next_action,
                )
            )
    return tuple(required_inputs)


def _operator_input(
    *,
    blocker: str,
    input_kind: str,
    required_names: tuple[str, ...],
    current_state: str,
    next_action: str,
) -> RuntimeEnablementOperatorInput:
    material = {
        "blocker": blocker,
        "input_kind": input_kind,
        "required_names": list(required_names),
        "current_state": current_state,
    }
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return RuntimeEnablementOperatorInput(
        input_id=f"read-only-worker-runtime-enablement-input-{digest[:12]}",
        blocker=blocker,
        input_kind=input_kind,
        required_names=required_names,
        current_state=current_state,
        evidence_source="read_only_worker_runtime_enablement_witness",
        next_action=next_action,
    )


def _runtime_enablement_summary(witness: dict[str, Any]) -> dict[str, Any]:
    contract = witness.get("runtime_enablement_contract", {})
    authority = witness.get("authority_scope", {})
    if not isinstance(contract, dict):
        contract = {}
    if not isinstance(authority, dict):
        authority = {}
    return {
        "worker_id": contract.get("worker_id", ""),
        "capability": contract.get("capability", ""),
        "operation_family": contract.get("operation_family", ""),
        "witness_mode": contract.get("witness_mode", ""),
        "read_only": authority.get("read_only") is True,
        "runtime_enablement_allowed": False,
        "dispatch_admission_allowed": False,
        "runtime_dispatch_allowed": False,
        "worker_invocation_allowed": False,
        "external_network_allowed": False,
        "secret_access_allowed": False,
        "filesystem_write_allowed": False,
        "connector_authority_allowed": False,
        "success_claim_allowed": False,
    }


def _request_id(
    witness: dict[str, Any],
    required_inputs: tuple[RuntimeEnablementOperatorInput, ...],
    witness_validation_ok: bool,
) -> str:
    material = {
        "receipt_id": witness.get("receipt_id", ""),
        "witness_validation_ok": witness_validation_ok,
        "required_input_ids": [item.input_id for item in required_inputs],
    }
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"read-only-worker-runtime-enablement-input-request-{digest[:16]}"


def _next_action(
    required_inputs: tuple[RuntimeEnablementOperatorInput, ...],
    witness_validation_ok: bool,
) -> str:
    if not witness_validation_ok:
        return "repair the runtime enablement witness before collecting operator inputs"
    if required_inputs:
        return required_inputs[0].next_action
    return "rerun runtime enablement witness validation before any enablement request"


def _validate_request_against_schema(
    request: RuntimeEnablementOperatorInputRequest,
    schema_path: Path,
) -> None:
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, request.as_dict())
    if errors:
        raise RuntimeError(f"runtime enablement operator input request schema validation failed: {errors}")


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


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse runtime enablement operator input request arguments."""

    parser = argparse.ArgumentParser(
        description="Emit read-only worker runtime enablement operator input request."
    )
    parser.add_argument("--witness", default=str(DEFAULT_WITNESS))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for operator input request emission."""

    args = parse_args(argv)
    try:
        request = emit_runtime_enablement_operator_input_request(
            witness_path=Path(args.witness),
            schema_path=Path(args.schema),
        )
        write_runtime_enablement_operator_input_request(request, Path(args.output))
    except RuntimeError as exc:
        if args.json:
            print(
                json.dumps(
                    {
                        "error": str(exc),
                        "request_written": False,
                        "runtime_enablement_allowed": False,
                        "solver_outcome": "GovernanceBlocked",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(f"runtime enablement operator input request failed: {exc}")
        return 1
    if args.json:
        print(json.dumps(request.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"runtime enablement operator input request written: {request.request_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
