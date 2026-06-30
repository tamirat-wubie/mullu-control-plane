"""Finance approval handoff test fixture builders.

Purpose: create deterministic FinanceOps handoff artifacts for packet and
chain validation tests without relying on workspace-local change assurance
files.
Governance scope: test-only witness, binding receipt, live receipt, handoff
plan, closure run, preflight, and adapter evidence construction.
Dependencies: finance handoff planning, binding receipt, closure, preflight,
and packet producer modules.
Invariants:
  - Fixture artifacts are explicit files under the pytest temp directory.
  - Blocked fixtures carry valid but not-ready live receipt evidence.
  - Ready fixtures require both closed adapter evidence and a read-only live receipt.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.emit_finance_approval_email_calendar_binding_receipt import (
    emit_finance_approval_email_calendar_binding_receipt,
    write_finance_email_calendar_binding_receipt,
)
from scripts.plan_finance_approval_live_handoff import (
    plan_finance_approval_live_handoff,
    write_finance_live_handoff_plan,
)
from scripts.preflight_finance_approval_live_handoff import (
    preflight_finance_approval_live_handoff,
    write_finance_live_handoff_preflight_report,
)
from scripts.produce_finance_approval_handoff_packet import produce_finance_approval_handoff_packet
from scripts.run_finance_approval_live_handoff_closure import (
    run_finance_approval_live_handoff_closure,
    write_finance_live_handoff_closure_run,
)


def write_finance_handoff_sources(tmp_path: Path, *, live_ready: bool = False) -> dict[str, Path]:
    """Write a complete finance handoff source chain and return artifact paths."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    witness_path = _write_witness(tmp_path)
    adapter_evidence_path = _write_adapter_evidence(tmp_path, email_calendar_closed=live_ready)
    binding_receipt_path = _write_binding_receipt(tmp_path)
    live_receipt_path = _write_live_receipt(tmp_path, ready=live_ready)
    handoff_plan_path = tmp_path / "finance_approval_live_handoff_plan.json"
    closure_run_path = tmp_path / "finance_approval_live_handoff_closure_run.json"
    preflight_path = tmp_path / "finance_approval_live_handoff_preflight.json"

    plan = plan_finance_approval_live_handoff(
        adapter_evidence_path=adapter_evidence_path,
        binding_receipt_path=binding_receipt_path,
    )
    write_finance_live_handoff_plan(plan, handoff_plan_path)

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
        "handoff_plan": handoff_plan_path,
        "binding_receipt": binding_receipt_path,
        "live_receipt": live_receipt_path,
        "closure_run": closure_run_path,
        "preflight": preflight_path,
        "adapter_evidence": adapter_evidence_path,
    }


def produce_finance_handoff_packet_from_sources(paths: dict[str, Path]) -> dict[str, object]:
    """Produce a packet from explicit finance handoff source paths."""
    return produce_finance_approval_handoff_packet(
        witness_path=paths["witness"],
        handoff_plan_path=paths["handoff_plan"],
        binding_receipt_path=paths["binding_receipt"],
        live_receipt_path=paths["live_receipt"],
        closure_run_path=paths["closure_run"],
        preflight_path=paths["preflight"],
        adapter_evidence_path=paths["adapter_evidence"],
    )


def _write_witness(tmp_path: Path) -> Path:
    witness_path = tmp_path / "finance_approval_pilot_witness.json"
    witness_path.write_text(
        json.dumps(
            {
                "witness_id": "finance-approval-pilot-witness-test",
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
        ),
        encoding="utf-8",
    )
    return witness_path


def _write_adapter_evidence(tmp_path: Path, *, email_calendar_closed: bool) -> Path:
    evidence_path = tmp_path / "capability_adapter_evidence.json"
    email_calendar_status = "closed" if email_calendar_closed else "open"
    email_calendar_blockers: list[str] = [] if email_calendar_closed else ["email_calendar_live_evidence_missing"]
    email_calendar_refs: list[str] = ["email_calendar_live_receipt.json"] if email_calendar_closed else []
    evidence_path.write_text(
        json.dumps(
            {
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
        ),
        encoding="utf-8",
    )
    return evidence_path


def _write_binding_receipt(tmp_path: Path) -> Path:
    receipt_path = tmp_path / "finance_approval_email_calendar_binding_receipt.json"
    receipt, errors = emit_finance_approval_email_calendar_binding_receipt(env_reader=_ready_env)
    assert errors == ()
    write_finance_email_calendar_binding_receipt(receipt, receipt_path)
    return receipt_path


def _write_live_receipt(tmp_path: Path, *, ready: bool) -> Path:
    receipt_path = tmp_path / "email_calendar_live_receipt.json"
    payload = _ready_live_receipt()
    if not ready:
        payload = payload | {
            "status": "failed",
            "verification_status": "failed",
            "provider_operation": "",
            "blockers": ["email_calendar_probe_exception"],
            "failure_class": "probe_exception",
            "recovery_actions": ["rerun_email_calendar_live_receipt_probe"],
        }
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")
    return receipt_path


def _ready_live_receipt() -> dict[str, object]:
    return {
        "receipt_id": "email-calendar-live-receipt-test",
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


def _ready_env(name: str) -> str:
    values = {
        "MULLU_EMAIL_CALENDAR_WORKER_URL": "https://email-calendar.internal/execute",
        "MULLU_EMAIL_CALENDAR_WORKER_SECRET": "secret-worker-value",
        "GMAIL_ACCESS_TOKEN": "secret-token-value",
        "GMAIL_SCOPE_ID": "gmail.readonly",
    }
    return values.get(name, "")
