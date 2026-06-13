#!/usr/bin/env python3
"""Emit missing operator inputs for finance email/calendar handoff.

Purpose: translate a blocked redacted finance email/calendar binding receipt
into a public-safe operator input request.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/finance_approval_email_calendar_operator_input_request.schema.json
and finance approval email/calendar binding receipt artifacts.
Invariants:
  - Report contains binding names, blocker names, and next actions only.
  - Worker URLs, signing secrets, connector tokens, scope values, provider
    account details, and mailbox contents are never serialized.
  - Finance live handoff remains blocked unless the source receipt is ready.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.emit_finance_approval_email_calendar_binding_receipt import (  # noqa: E402
    CONNECTOR_TOKEN_BINDING_NAMES,
    SCOPE_WITNESS_BINDING_NAMES,
    WORKER_ENDPOINT_BINDING_NAMES,
    WORKER_SECRET_BINDING_NAMES,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_RECEIPT = (
    REPO_ROOT / ".change_assurance" / "finance_approval_email_calendar_binding_receipt.json"
)
DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "finance_approval_email_calendar_operator_input_request.schema.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "finance_approval_email_calendar_operator_input_request.json"
)


@dataclass(frozen=True, slots=True)
class FinanceEmailCalendarOperatorInput:
    """One missing finance email/calendar operator input group."""

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
class FinanceEmailCalendarOperatorInputRequest:
    """Public-safe operator input request for finance email/calendar handoff."""

    request_id: str
    receipt_id: str
    ready: bool
    handoff_allowed: bool
    solver_outcome: str
    proof_state: str
    required_inputs: tuple[FinanceEmailCalendarOperatorInput, ...]
    blocked_actions: tuple[str, ...]
    source_artifacts: dict[str, str]
    no_secret_values_serialized: bool
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready request payload."""
        return {
            "request_id": self.request_id,
            "receipt_id": self.receipt_id,
            "ready": self.ready,
            "handoff_allowed": self.handoff_allowed,
            "solver_outcome": self.solver_outcome,
            "proof_state": self.proof_state,
            "required_inputs": [item.as_dict() for item in self.required_inputs],
            "blocked_actions": list(self.blocked_actions),
            "source_artifacts": dict(self.source_artifacts),
            "no_secret_values_serialized": self.no_secret_values_serialized,
            "next_action": self.next_action,
        }


def emit_finance_email_calendar_operator_input_request(
    *,
    receipt_path: Path = DEFAULT_RECEIPT,
    schema_path: Path = DEFAULT_SCHEMA,
) -> FinanceEmailCalendarOperatorInputRequest:
    """Build one operator input request from a finance binding receipt."""
    receipt = _load_json_object(receipt_path, "finance email/calendar binding receipt")
    required_inputs = _derive_required_inputs(receipt)
    ready = receipt.get("ready") is True
    request = FinanceEmailCalendarOperatorInputRequest(
        request_id=_request_id(receipt, required_inputs),
        receipt_id=str(receipt.get("receipt_id", "")),
        ready=ready,
        handoff_allowed=ready and not required_inputs,
        solver_outcome="SolvedVerified" if ready else "AwaitingEvidence",
        proof_state="Pass" if ready else "Unknown",
        required_inputs=required_inputs,
        blocked_actions=_blocked_actions(ready),
        source_artifacts={
            "finance_approval_email_calendar_binding_receipt": _artifact_ref(receipt_path)
        },
        no_secret_values_serialized=True,
        next_action=_next_action(required_inputs, ready),
    )
    _validate_request_against_schema(request, schema_path)
    return request


def write_finance_email_calendar_operator_input_request(
    request: FinanceEmailCalendarOperatorInputRequest,
    output_path: Path,
) -> Path:
    """Write one finance email/calendar operator input request JSON report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(request.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _derive_required_inputs(
    receipt: dict[str, Any],
) -> tuple[FinanceEmailCalendarOperatorInput, ...]:
    required_inputs: list[FinanceEmailCalendarOperatorInput] = []
    blockers = tuple(str(blocker) for blocker in receipt.get("readiness_blockers", []))
    for blocker in blockers:
        if blocker == "missing_worker_endpoint":
            required_inputs.append(
                _operator_input(
                    blocker=blocker,
                    input_kind="worker_endpoint",
                    required_names=WORKER_ENDPOINT_BINDING_NAMES,
                    current_state="missing",
                    next_action=(
                        "bind MULLU_EMAIL_CALENDAR_WORKER_URL outside this report, "
                        "then rerun the finance email/calendar binding receipt"
                    ),
                )
            )
        elif blocker == "missing_worker_secret":
            required_inputs.append(
                _operator_input(
                    blocker=blocker,
                    input_kind="worker_secret",
                    required_names=WORKER_SECRET_BINDING_NAMES,
                    current_state="missing",
                    next_action=(
                        "bind MULLU_EMAIL_CALENDAR_WORKER_SECRET outside this report, "
                        "then rerun the finance email/calendar binding receipt"
                    ),
                )
            )
        elif blocker == "missing_connector_token":
            required_inputs.append(
                _operator_input(
                    blocker=blocker,
                    input_kind="connector_token",
                    required_names=CONNECTOR_TOKEN_BINDING_NAMES,
                    current_state="missing_one_of",
                    next_action=(
                        "bind one accepted read-only email/calendar connector token outside this "
                        "report, then rerun the finance email/calendar binding receipt"
                    ),
                )
            )
        elif blocker == "missing_read_only_scope_witness":
            required_inputs.append(
                _operator_input(
                    blocker=blocker,
                    input_kind="read_only_scope_witness",
                    required_names=SCOPE_WITNESS_BINDING_NAMES,
                    current_state="missing_one_of",
                    next_action=(
                        "bind one accepted read-only scope witness outside this report, "
                        "then rerun the finance email/calendar binding receipt"
                    ),
                )
            )
        elif blocker.startswith("invalid_scope_witness:"):
            required_inputs.append(
                _operator_input(
                    blocker=blocker,
                    input_kind="valid_scope_witness",
                    required_names=_invalid_scope_required_names(blocker),
                    current_state="present_invalid",
                    next_action=(
                        "replace the invalid scope witness with a read-only scope witness, "
                        "then rerun the finance email/calendar binding receipt"
                    ),
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
) -> FinanceEmailCalendarOperatorInput:
    material = {
        "blocker": blocker,
        "input_kind": input_kind,
        "required_names": required_names,
        "current_state": current_state,
        "evidence_source": "finance_approval_email_calendar_binding_receipt",
    }
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return FinanceEmailCalendarOperatorInput(
        input_id=f"finance-email-calendar-input-{digest[:12]}",
        blocker=blocker,
        input_kind=input_kind,
        required_names=required_names,
        current_state=current_state,
        evidence_source="finance_approval_email_calendar_binding_receipt",
        next_action=next_action,
    )


def _invalid_scope_required_names(blocker: str) -> tuple[str, ...]:
    name = blocker.split(":", 1)[1].strip()
    if name in SCOPE_WITNESS_BINDING_NAMES:
        return (name,)
    return SCOPE_WITNESS_BINDING_NAMES


def _blocked_actions(ready: bool) -> tuple[str, ...]:
    if ready:
        return ()
    return (
        "email_calendar_live_probe",
        "finance_approval_live_handoff",
        "customer_or_external_email_dispatch",
        "finance_approval_production_readiness_claim",
    )


def _next_action(
    required_inputs: tuple[FinanceEmailCalendarOperatorInput, ...],
    ready: bool,
) -> str:
    if ready:
        return "run finance email/calendar live receipt probe with require-ready validation"
    if required_inputs:
        return required_inputs[0].next_action
    return "inspect finance email/calendar binding receipt blockers"


def _request_id(
    receipt: dict[str, Any],
    required_inputs: tuple[FinanceEmailCalendarOperatorInput, ...],
) -> str:
    material = {
        "receipt_id": receipt.get("receipt_id", ""),
        "ready": receipt.get("ready", False),
        "required_input_ids": [item.input_id for item in required_inputs],
    }
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"finance-email-calendar-operator-input-request-{digest[:16]}"


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
    """Return a public-safe artifact reference without host-local ancestry."""
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


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _validate_request_against_schema(
    request: FinanceEmailCalendarOperatorInputRequest,
    schema_path: Path,
) -> None:
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, request.as_dict())
    if errors:
        raise RuntimeError(f"finance email/calendar operator input request schema validation failed: {errors}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse finance email/calendar operator input request arguments."""
    parser = argparse.ArgumentParser(
        description="Emit finance email/calendar operator input request."
    )
    parser.add_argument("--receipt", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for operator input request emission."""
    args = parse_args(argv)
    try:
        request = emit_finance_email_calendar_operator_input_request(
            receipt_path=Path(args.receipt),
            schema_path=Path(args.schema),
        )
        write_finance_email_calendar_operator_input_request(request, Path(args.output))
    except RuntimeError as exc:
        if args.json:
            print(
                json.dumps(
                    {
                        "error": str(exc),
                        "handoff_allowed": False,
                        "request_written": False,
                        "solver_outcome": "AwaitingEvidence",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(f"finance email/calendar operator input request failed: {exc}")
        return 1
    if args.json:
        print(json.dumps(request.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"finance email/calendar operator input request written: {request.request_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
