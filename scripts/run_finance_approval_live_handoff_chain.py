#!/usr/bin/env python3
"""Run a deterministic finance approval live handoff chain dry run.

Purpose: produce a complete local finance live handoff artifact chain and
validate the aggregate chain without executing live email/calendar effects.
Governance scope: finance approval handoff chain production, live-readiness
blocker preservation, schema validation, and Foundation Mode evidence.
Dependencies: finance handoff planning, binding receipt emission, closure-run
dry run, preflight reporting, packet production, and chain validators.
Invariants:
  - Default execution is dry-run only.
  - No live connector command is executed.
  - Secret values are never serialized.
  - Blocked live readiness remains explicit and machine-readable.
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

from scripts.emit_finance_approval_email_calendar_binding_receipt import (  # noqa: E402
    emit_finance_approval_email_calendar_binding_receipt,
    write_finance_email_calendar_binding_receipt,
)
from scripts.emit_finance_approval_email_calendar_operator_input_request import (  # noqa: E402
    emit_finance_email_calendar_operator_input_request,
    write_finance_email_calendar_operator_input_request,
)
from scripts.plan_finance_approval_live_handoff import (  # noqa: E402
    plan_finance_approval_live_handoff,
    write_finance_live_handoff_plan,
)
from scripts.preflight_finance_approval_live_handoff import (  # noqa: E402
    preflight_finance_approval_live_handoff,
    write_finance_live_handoff_preflight_report,
)
from scripts.produce_finance_approval_handoff_packet import (  # noqa: E402
    produce_finance_approval_handoff_packet,
    write_finance_approval_handoff_packet,
)
from scripts.run_finance_approval_live_handoff_closure import (  # noqa: E402
    run_finance_approval_live_handoff_closure,
    write_finance_live_handoff_closure_run,
)
from scripts.validate_finance_approval_live_handoff_chain import (  # noqa: E402
    validate_finance_approval_live_handoff_chain,
    write_finance_live_handoff_chain_validation,
)
from scripts.validate_finance_approval_live_handoff_chain_schema import (  # noqa: E402
    validate_finance_approval_live_handoff_chain_schema,
    write_finance_live_handoff_chain_schema_validation,
)
from scripts.validate_finance_approval_email_calendar_operator_input_request import (  # noqa: E402
    validate_finance_email_calendar_operator_input_request,
    write_finance_email_calendar_operator_input_request_validation,
)


DEFAULT_OUTPUT_DIR = REPO_ROOT / ".tmp" / "finance-approval-live-handoff-chain"


@dataclass(frozen=True, slots=True)
class FinanceLiveHandoffChainDryRun:
    """Summary for one finance live handoff chain dry run."""

    mode: str
    status: str
    ready: bool
    chain_ok: bool
    schema_ok: bool
    artifact_count: int
    output_dir: str
    chain_validation_path: str
    schema_validation_path: str
    readiness_blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["readiness_blockers"] = list(self.readiness_blockers)
        return payload


def run_finance_approval_live_handoff_chain(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    live_ready: bool = False,
) -> FinanceLiveHandoffChainDryRun:
    """Produce and validate a local finance live handoff chain dry run."""
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = _write_chain_sources(output_dir, live_ready=live_ready)
    packet = produce_finance_approval_handoff_packet(
        witness_path=paths["witness"],
        handoff_plan_path=paths["handoff_plan"],
        binding_receipt_path=paths["binding_receipt"],
        live_receipt_path=paths["live_receipt"],
        closure_run_path=paths["closure_run"],
        preflight_path=paths["preflight"],
        adapter_evidence_path=paths["adapter_evidence"],
        artifact_base_path=output_dir,
    )
    packet_path = output_dir / "finance_approval_handoff_packet.json"
    write_finance_approval_handoff_packet(packet, packet_path)

    chain_validation = validate_finance_approval_live_handoff_chain(
        closure_run_path=paths["closure_run"],
        live_receipt_path=paths["live_receipt"],
        preflight_path=paths["preflight"],
        packet_path=packet_path,
    )
    chain_validation_path = output_dir / "finance_approval_live_handoff_chain_validation.json"
    write_finance_live_handoff_chain_validation(chain_validation, chain_validation_path)

    schema_validation = validate_finance_approval_live_handoff_chain_schema(chain_path=chain_validation_path)
    schema_validation_path = output_dir / "finance_approval_live_handoff_chain_schema_validation.json"
    write_finance_live_handoff_chain_schema_validation(schema_validation, schema_validation_path)

    status = _status_for(chain_ok=chain_validation.ok, schema_ok=schema_validation.ok, ready=chain_validation.ready)
    artifact_count = len(paths) + 3
    return FinanceLiveHandoffChainDryRun(
        mode="dry-run",
        status=status,
        ready=chain_validation.ready,
        chain_ok=chain_validation.ok,
        schema_ok=schema_validation.ok,
        artifact_count=artifact_count,
        output_dir=str(output_dir),
        chain_validation_path=str(chain_validation_path),
        schema_validation_path=str(schema_validation_path),
        readiness_blockers=tuple(chain_validation.readiness_blockers),
    )


def _write_chain_sources(output_dir: Path, *, live_ready: bool) -> dict[str, Path]:
    witness_path = output_dir / "finance_approval_pilot_witness.json"
    adapter_evidence_path = output_dir / "capability_adapter_evidence.json"
    binding_receipt_path = output_dir / "finance_approval_email_calendar_binding_receipt.json"
    operator_input_request_path = output_dir / "finance_approval_email_calendar_operator_input_request.json"
    operator_input_validation_path = output_dir / "finance_approval_email_calendar_operator_input_request_validation.json"
    live_receipt_path = output_dir / "email_calendar_live_receipt.json"
    handoff_plan_path = output_dir / "finance_approval_live_handoff_plan.json"
    closure_run_path = output_dir / "finance_approval_live_handoff_closure_run.json"
    preflight_path = output_dir / "finance_approval_live_handoff_preflight.json"

    witness_path.write_text(json.dumps(_pilot_witness(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    adapter_evidence_path.write_text(
        json.dumps(_adapter_evidence(live_ready=live_ready), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    live_receipt_path.write_text(
        json.dumps(_live_receipt(ready=live_ready), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    binding_receipt, binding_errors = emit_finance_approval_email_calendar_binding_receipt(env_reader=_dry_run_env)
    if binding_errors:
        raise RuntimeError(f"finance email/calendar dry-run binding receipt invalid: {list(binding_errors)}")
    write_finance_email_calendar_binding_receipt(binding_receipt, binding_receipt_path)

    operator_input_request = emit_finance_email_calendar_operator_input_request(
        receipt_path=binding_receipt_path,
    )
    write_finance_email_calendar_operator_input_request(operator_input_request, operator_input_request_path)
    operator_input_validation = validate_finance_email_calendar_operator_input_request(
        request_path=operator_input_request_path,
    )
    write_finance_email_calendar_operator_input_request_validation(
        operator_input_validation,
        operator_input_validation_path,
    )
    if not operator_input_validation.valid:
        raise RuntimeError(
            "finance email/calendar dry-run operator input request invalid: "
            f"{list(operator_input_validation.errors)}"
        )

    handoff_plan = plan_finance_approval_live_handoff(
        adapter_evidence_path=adapter_evidence_path,
        binding_receipt_path=binding_receipt_path,
    )
    write_finance_live_handoff_plan(handoff_plan, handoff_plan_path)

    closure_run = run_finance_approval_live_handoff_closure(
        binding_receipt_path=binding_receipt_path,
        adapter_evidence_path=adapter_evidence_path,
    )
    write_finance_live_handoff_closure_run(closure_run, closure_run_path)

    preflight = preflight_finance_approval_live_handoff(
        handoff_plan_path=handoff_plan_path,
        binding_receipt_path=binding_receipt_path,
        closure_run_path=closure_run_path,
        adapter_evidence_path=adapter_evidence_path,
    )
    write_finance_live_handoff_preflight_report(preflight, preflight_path)

    return {
        "witness": witness_path,
        "adapter_evidence": adapter_evidence_path,
        "binding_receipt": binding_receipt_path,
        "operator_input_request": operator_input_request_path,
        "operator_input_validation": operator_input_validation_path,
        "live_receipt": live_receipt_path,
        "handoff_plan": handoff_plan_path,
        "closure_run": closure_run_path,
        "preflight": preflight_path,
    }


def _pilot_witness() -> dict[str, Any]:
    return {
        "witness_id": "finance-approval-live-handoff-chain-dry-run",
        "status": "passed",
        "blocked_path": {"case": {"state": "requires_review"}},
        "successful_path": {
            "case": {
                "state": "closed_sent",
                "effect_refs": ["effect:finance-email-draft"],
            }
        },
        "claim_boundary": {
            "can_claim": ["proof-pilot finance approval packet flow"],
            "must_not_claim": [
                "autonomous payment execution",
                "bank settlement",
                "ERP reconciliation",
                "live email delivery",
                "production finance automation",
            ],
        },
    }


def _adapter_evidence(*, live_ready: bool) -> dict[str, Any]:
    email_calendar_status = "closed" if live_ready else "open"
    email_calendar_blockers: list[str] = [] if live_ready else ["email_calendar_live_evidence_missing"]
    email_calendar_refs: list[str] = ["email_calendar_live_receipt.json"] if live_ready else []
    return {
        "adapters": [
            {
                "adapter_id": "document.production_parsers",
                "status": "closed",
                "blockers": [],
                "evidence_refs": ["document_live_receipt.json"],
            },
            {
                "adapter_id": "communication.email_calendar_worker",
                "status": email_calendar_status,
                "blockers": email_calendar_blockers,
                "evidence_refs": email_calendar_refs,
            },
        ]
    }


def _live_receipt(*, ready: bool) -> dict[str, Any]:
    receipt = {
        "receipt_id": "email-calendar-live-receipt-dry-run",
        "adapter_id": "communication.email_calendar_worker",
        "status": "passed",
        "verification_status": "passed",
        "checked_at": "2026-05-01T12:00:00+00:00",
        "connector_id": "gmail",
        "provider_operation": "email.search",
        "resource_id": "email-search-live",
        "response_digest": "b" * 64,
        "external_write": False,
        "worker_receipt": {
            "receipt_id": "email-calendar-receipt-aaaaaaaaaaaaaaaa",
            "request_id": "email-calendar-live-receipt",
            "tenant_id": "tenant-adapter-evidence",
            "verification_status": "passed",
            "capability_id": "email.search",
            "action": "email.search",
            "worker_id": "email-calendar-worker",
            "connector_id": "gmail",
            "provider_operation": "email.search",
            "resource_id": "email-search-live",
            "response_digest": "b" * 64,
            "subject_hash": "0" * 64,
            "body_hash": "0" * 64,
            "query_hash": "1" * 64,
            "recipient_hashes": [],
            "attendee_hashes": [],
            "external_write": False,
            "effect_mode": "plan_only",
            "external_effect_claimed": False,
            "provider_receipt_hash": "",
            "provider_receipt_ref": "",
            "idempotency_key": "",
            "rollback_or_recovery_ref": "",
            "secret_values_disclosed": False,
            "forbidden_effects_observed": False,
            "evidence_refs": ["email_calendar_action:aaaaaaaaaaaaaaaa"],
            "approval_id": "",
        },
        "blockers": [],
    }
    if ready:
        return receipt
    return receipt | {
        "status": "failed",
        "verification_status": "failed",
        "provider_operation": "",
        "blockers": ["email_calendar_probe_exception"],
        "failure_class": "probe_exception",
        "recovery_actions": ["rerun_email_calendar_live_receipt_probe"],
    }


def _dry_run_env(name: str) -> str:
    values = {
        "MULLU_EMAIL_CALENDAR_WORKER_URL": "https://email-calendar.internal/execute",
        "MULLU_EMAIL_CALENDAR_WORKER_SECRET": "dry-run-worker-secret",
        "GMAIL_ACCESS_TOKEN": "dry-run-token",
        "GMAIL_SCOPE_ID": "gmail.readonly",
    }
    return values.get(name, "")


def _status_for(*, chain_ok: bool, schema_ok: bool, ready: bool) -> str:
    if not chain_ok or not schema_ok:
        return "failed"
    if ready:
        return "ready"
    return "passed_blocked"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse finance live handoff chain dry-run arguments."""
    parser = argparse.ArgumentParser(description="Run finance approval live handoff chain dry run.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--live-ready", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for finance live handoff chain dry run."""
    args = parse_args(argv)
    dry_run = run_finance_approval_live_handoff_chain(
        output_dir=Path(args.output_dir),
        live_ready=args.live_ready,
    )
    if args.json:
        print(json.dumps(dry_run.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"FINANCE LIVE HANDOFF CHAIN DRY RUN {dry_run.status}")
    if dry_run.status == "failed":
        return 2
    if args.require_ready and not dry_run.ready:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
