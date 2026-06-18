#!/usr/bin/env python3
"""Refresh local, non-secret assurance artifacts.

Purpose: regenerate local proof and adapter-evidence witnesses that can drift
during development without requiring live provider credentials.
Governance scope: document adapter receipt, durable Gmail OAuth blocked
handoff receipts, runtime preflight, account-binding operator input request,
revocation recovery rehearsal, write authority rehearsal, live-write operator
input request, TeamOps shared inbox
blocked handoff, approval binding, probe-authority, operator-input request,
live-probe receipt, observation routing receipt, approval queue receipt,
approval decision receipt, and send-preparation receipt, send-execution receipt,
sent-message observation receipt, terminal closure review packet, aggregate
adapter evidence, proof coverage witness, protocol manifest validation, and
finance proof-pilot readiness.
Dependencies: repository-local assurance scripts and Python subprocess.
Invariants:
  - The default step set performs no external writes and requires no secrets.
  - Live email/calendar, voice, browser, PostgreSQL, and SMTP evidence remains
    blocked unless separately supplied by operator-controlled live lanes.
  - Durable Gmail OAuth steps emit blocked, preflight-only, account-binding
    operator-input, recovery rehearsal, write rehearsal, or live-write
    operator-input receipts; they do not mint tokens, contact Google, create
    drafts, send messages, write mailbox state, probe profiles, or claim live
    readiness.
  - TeamOps shared inbox steps emit blocked handoff, redacted probe approval
    binding, read-only probe authority, operator-input request, live-probe receipt,
    observation routing receipt, approval queue receipt, approval decision
    receipt, send-preparation receipt, and blocked send-execution receipt
    plus blocked sent-message observation receipt and blocked terminal closure
    review packet without provider calls, mailbox writes, drafts, producer-made
    approval decisions, local send execution, observation, replay, terminal
    certificate minting, or sends.
  - Each step returns an explicit command receipt; failures are not hidden.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True, slots=True)
class AssuranceStep:
    """One local assurance refresh step."""

    name: str
    command: tuple[str, ...]
    purpose: str


@dataclass(frozen=True, slots=True)
class AssuranceStepResult:
    """Execution receipt for one local assurance step."""

    name: str
    command: tuple[str, ...]
    returncode: int
    elapsed_seconds: float
    stdout_tail: str
    stderr_tail: str
    dry_run: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "command": list(self.command),
            "returncode": self.returncode,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
            "dry_run": self.dry_run,
        }


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


LOCAL_ASSURANCE_STEPS: tuple[AssuranceStep, ...] = (
    AssuranceStep(
        name="document_live_receipt",
        command=(
            sys.executable,
            "scripts/produce_capability_adapter_live_receipts.py",
            "--target",
            "document",
            "--document-output",
            ".change_assurance/document_live_receipt.json",
            "--json",
        ),
        purpose="regenerate deterministic document parser live receipt",
    ),
    AssuranceStep(
        name="durable_gmail_oauth_operator_handoff",
        command=(
            sys.executable,
            "scripts/produce_durable_gmail_oauth_operator_handoff.py",
            "--output",
            ".change_assurance/durable_gmail_oauth_operator_handoff.json",
            "--json",
        ),
        purpose="regenerate blocked durable Gmail OAuth operator handoff receipt",
    ),
    AssuranceStep(
        name="durable_gmail_oauth_operator_handoff_validation",
        command=(
            sys.executable,
            "scripts/validate_durable_gmail_oauth_operator_handoff.py",
            "--handoff",
            ".change_assurance/durable_gmail_oauth_operator_handoff.json",
            "--output",
            ".change_assurance/durable_gmail_oauth_operator_handoff_validation.json",
            "--require-blocked",
            "--json",
        ),
        purpose="validate blocked durable Gmail OAuth handoff without live claim",
    ),
    AssuranceStep(
        name="durable_gmail_oauth_runtime_preflight",
        command=(
            sys.executable,
            "scripts/validate_durable_gmail_oauth_runtime_preflight.py",
            "--output",
            ".change_assurance/durable_gmail_oauth_runtime_preflight.json",
            "--json",
        ),
        purpose="persist redacted durable Gmail OAuth runtime preflight receipt",
    ),
    AssuranceStep(
        name="durable_gmail_account_binding_operator_input_request",
        command=(
            sys.executable,
            "scripts/emit_durable_gmail_account_binding_operator_input_request.py",
            "--output",
            ".change_assurance/durable_gmail_account_binding_operator_input_request.json",
            "--json",
        ),
        purpose="emit blocked Gmail account-binding operator inputs without profile probe or provider call",
    ),
    AssuranceStep(
        name="durable_gmail_account_binding_operator_input_request_validation",
        command=(
            sys.executable,
            "scripts/validate_durable_gmail_account_binding_operator_input_request.py",
            "--request",
            ".change_assurance/durable_gmail_account_binding_operator_input_request.json",
            "--output",
            ".change_assurance/durable_gmail_account_binding_operator_input_request_validation.json",
            "--require-blocked",
            "--json",
        ),
        purpose="validate blocked Gmail account-binding operator inputs without account-binding claim",
    ),
    AssuranceStep(
        name="durable_gmail_revocation_recovery_rehearsal_receipt",
        command=(
            sys.executable,
            "scripts/produce_durable_gmail_revocation_recovery_rehearsal_receipt.py",
            "--output",
            ".change_assurance/durable_gmail_revocation_recovery_rehearsal_receipt.json",
            "--strict",
            "--json",
        ),
        purpose="regenerate Gmail invalid-grant recovery rehearsal without provider revocation",
    ),
    AssuranceStep(
        name="durable_gmail_revocation_recovery_rehearsal_receipt_validation",
        command=(
            sys.executable,
            "scripts/validate_durable_gmail_revocation_recovery_rehearsal_receipt.py",
            "--receipt",
            ".change_assurance/durable_gmail_revocation_recovery_rehearsal_receipt.json",
            "--max-age-days",
            "14",
            "--require-ready",
            "--json",
        ),
        purpose="validate Gmail revocation recovery rehearsal without destructive provider action",
    ),
    AssuranceStep(
        name="durable_gmail_write_authority_rehearsal_receipt",
        command=(
            sys.executable,
            "scripts/produce_durable_gmail_write_authority_rehearsal_receipt.py",
            "--output",
            ".change_assurance/durable_gmail_write_authority_rehearsal_receipt.json",
            "--strict",
            "--json",
        ),
        purpose="regenerate Gmail write-authority rehearsal without draft, send, or provider call",
    ),
    AssuranceStep(
        name="durable_gmail_write_authority_rehearsal_receipt_validation",
        command=(
            sys.executable,
            "scripts/validate_durable_gmail_write_authority_rehearsal_receipt.py",
            "--receipt",
            ".change_assurance/durable_gmail_write_authority_rehearsal_receipt.json",
            "--max-age-days",
            "14",
            "--require-ready",
            "--json",
        ),
        purpose="validate Gmail write-authority rehearsal without live write authority claim",
    ),
    AssuranceStep(
        name="durable_gmail_live_write_operator_input_request",
        command=(
            sys.executable,
            "scripts/emit_durable_gmail_live_write_operator_input_request.py",
            "--output",
            ".change_assurance/durable_gmail_live_write_operator_input_request.json",
            "--json",
        ),
        purpose="emit blocked Gmail live-write operator inputs without draft, send, or provider call",
    ),
    AssuranceStep(
        name="durable_gmail_live_write_operator_input_request_validation",
        command=(
            sys.executable,
            "scripts/validate_durable_gmail_live_write_operator_input_request.py",
            "--request",
            ".change_assurance/durable_gmail_live_write_operator_input_request.json",
            "--output",
            ".change_assurance/durable_gmail_live_write_operator_input_request_validation.json",
            "--require-blocked",
            "--json",
        ),
        purpose="validate blocked Gmail live-write operator inputs without live write authority claim",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_operator_handoff",
        command=(
            sys.executable,
            "scripts/produce_team_ops_shared_inbox_operator_handoff.py",
            "--output",
            ".change_assurance/team_ops_shared_inbox_operator_handoff.json",
            "--json",
        ),
        purpose="regenerate blocked TeamOps shared inbox operator handoff receipt",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_operator_handoff_validation",
        command=(
            sys.executable,
            "scripts/validate_team_ops_shared_inbox_operator_handoff.py",
            "--handoff",
            ".change_assurance/team_ops_shared_inbox_operator_handoff.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_operator_handoff_validation.json",
            "--require-blocked",
            "--json",
        ),
        purpose="validate blocked TeamOps shared inbox handoff without live claim",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_live_probe_approval_binding",
        command=(
            sys.executable,
            "scripts/bind_team_ops_shared_inbox_live_probe_approval.py",
            "--handoff",
            ".change_assurance/team_ops_shared_inbox_operator_handoff.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_live_probe_approval_binding.json",
            "--json",
        ),
        purpose="regenerate blocked TeamOps live-probe approval binding receipt",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_live_probe_approval_binding_validation",
        command=(
            sys.executable,
            "scripts/validate_team_ops_shared_inbox_live_probe_approval_binding.py",
            "--binding",
            ".change_assurance/team_ops_shared_inbox_live_probe_approval_binding.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_live_probe_approval_binding_validation.json",
            "--require-blocked",
            "--json",
        ),
        purpose="validate blocked TeamOps live-probe approval binding without executing the probe",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_live_probe_authority",
        command=(
            sys.executable,
            "scripts/produce_team_ops_shared_inbox_live_probe_authority.py",
            "--handoff",
            ".change_assurance/team_ops_shared_inbox_operator_handoff.json",
            "--approval-binding",
            ".change_assurance/team_ops_shared_inbox_live_probe_approval_binding.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_live_probe_authority.json",
            "--json",
        ),
        purpose="regenerate blocked TeamOps read-only live-probe authority receipt",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_live_probe_authority_validation",
        command=(
            sys.executable,
            "scripts/validate_team_ops_shared_inbox_live_probe_authority.py",
            "--authority",
            ".change_assurance/team_ops_shared_inbox_live_probe_authority.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_live_probe_authority_validation.json",
            "--require-blocked",
            "--json",
        ),
        purpose="validate blocked TeamOps live-probe authority without executing the probe",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_live_probe_operator_input_request",
        command=(
            sys.executable,
            "scripts/emit_team_ops_shared_inbox_live_probe_operator_input_request.py",
            "--authority",
            ".change_assurance/team_ops_shared_inbox_live_probe_authority.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_live_probe_operator_input_request.json",
            "--json",
        ),
        purpose="emit blocked TeamOps live-probe operator inputs without executing the probe",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_live_probe_operator_input_request_validation",
        command=(
            sys.executable,
            "scripts/validate_team_ops_shared_inbox_live_probe_operator_input_request.py",
            "--request",
            ".change_assurance/team_ops_shared_inbox_live_probe_operator_input_request.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_live_probe_operator_input_request_validation.json",
            "--require-blocked",
            "--json",
        ),
        purpose="validate blocked TeamOps live-probe operator inputs without executing the probe",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_live_probe_receipt",
        command=(
            sys.executable,
            "scripts/produce_team_ops_shared_inbox_live_probe_receipt.py",
            "--operator-input",
            ".change_assurance/team_ops_shared_inbox_live_probe_operator_input_request.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_live_probe_receipt.json",
            "--json",
        ),
        purpose="emit blocked TeamOps live-probe receipt without executing a provider call",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_live_probe_receipt_validation",
        command=(
            sys.executable,
            "scripts/validate_team_ops_shared_inbox_live_probe_receipt.py",
            "--receipt",
            ".change_assurance/team_ops_shared_inbox_live_probe_receipt.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_live_probe_receipt_validation.json",
            "--json",
        ),
        purpose="validate blocked TeamOps live-probe receipt without live readiness claim",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_observation_routing_receipt",
        command=(
            sys.executable,
            "scripts/produce_team_ops_shared_inbox_observation_routing_receipt.py",
            "--live-probe-receipt",
            ".change_assurance/team_ops_shared_inbox_live_probe_receipt.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_observation_routing_receipt.json",
            "--json",
        ),
        purpose="emit blocked TeamOps observation routing receipt without drafts or sends",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_observation_routing_receipt_validation",
        command=(
            sys.executable,
            "scripts/validate_team_ops_shared_inbox_observation_routing_receipt.py",
            "--receipt",
            ".change_assurance/team_ops_shared_inbox_observation_routing_receipt.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_observation_routing_receipt_validation.json",
            "--json",
        ),
        purpose="validate blocked TeamOps observation routing receipt without workflow promotion claim",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_approval_queue_receipt",
        command=(
            sys.executable,
            "scripts/produce_team_ops_shared_inbox_approval_queue_receipt.py",
            "--routing-receipt",
            ".change_assurance/team_ops_shared_inbox_observation_routing_receipt.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_approval_queue_receipt.json",
            "--json",
        ),
        purpose="emit blocked TeamOps approval queue receipt without approval decisions, drafts, or sends",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_approval_queue_receipt_validation",
        command=(
            sys.executable,
            "scripts/validate_team_ops_shared_inbox_approval_queue_receipt.py",
            "--receipt",
            ".change_assurance/team_ops_shared_inbox_approval_queue_receipt.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_approval_queue_receipt_validation.json",
            "--json",
        ),
        purpose="validate blocked TeamOps approval queue receipt without approval or send claim",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_approval_decision_receipt",
        command=(
            sys.executable,
            "scripts/produce_team_ops_shared_inbox_approval_decision_receipt.py",
            "--approval-queue-receipt",
            ".change_assurance/team_ops_shared_inbox_approval_queue_receipt.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_approval_decision_receipt.json",
            "--json",
        ),
        purpose="emit blocked TeamOps approval decision receipt without producer-made decisions, drafts, or sends",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_approval_decision_receipt_validation",
        command=(
            sys.executable,
            "scripts/validate_team_ops_shared_inbox_approval_decision_receipt.py",
            "--receipt",
            ".change_assurance/team_ops_shared_inbox_approval_decision_receipt.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_approval_decision_receipt_validation.json",
            "--json",
        ),
        purpose="validate blocked TeamOps approval decision receipt without send claim",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_send_preparation_receipt",
        command=(
            sys.executable,
            "scripts/produce_team_ops_shared_inbox_send_preparation_receipt.py",
            "--approval-decision-receipt",
            ".change_assurance/team_ops_shared_inbox_approval_decision_receipt.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_send_preparation_receipt.json",
            "--json",
        ),
        purpose="emit blocked TeamOps send-preparation receipt without draft, send, or provider mutation",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_send_preparation_receipt_validation",
        command=(
            sys.executable,
            "scripts/validate_team_ops_shared_inbox_send_preparation_receipt.py",
            "--receipt",
            ".change_assurance/team_ops_shared_inbox_send_preparation_receipt.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_send_preparation_receipt_validation.json",
            "--json",
        ),
        purpose="validate blocked TeamOps send-preparation receipt without send-execution claim",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_send_execution_receipt",
        command=(
            sys.executable,
            "scripts/produce_team_ops_shared_inbox_send_execution_receipt.py",
            "--send-preparation-receipt",
            ".change_assurance/team_ops_shared_inbox_send_preparation_receipt.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_send_execution_receipt.json",
            "--json",
        ),
        purpose="emit blocked TeamOps send-execution receipt without provider call or send claim",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_send_execution_receipt_validation",
        command=(
            sys.executable,
            "scripts/validate_team_ops_shared_inbox_send_execution_receipt.py",
            "--receipt",
            ".change_assurance/team_ops_shared_inbox_send_execution_receipt.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_send_execution_receipt_validation.json",
            "--json",
        ),
        purpose="validate blocked TeamOps send-execution receipt without provider mutation claim",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_sent_message_observation_receipt",
        command=(
            sys.executable,
            "scripts/produce_team_ops_shared_inbox_sent_message_observation_receipt.py",
            "--send-execution-receipt",
            ".change_assurance/team_ops_shared_inbox_send_execution_receipt.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_sent_message_observation_receipt.json",
            "--json",
        ),
        purpose="emit blocked TeamOps sent-message observation receipt without provider observation or replay claim",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_sent_message_observation_receipt_validation",
        command=(
            sys.executable,
            "scripts/validate_team_ops_shared_inbox_sent_message_observation_receipt.py",
            "--receipt",
            ".change_assurance/team_ops_shared_inbox_sent_message_observation_receipt.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_sent_message_observation_receipt_validation.json",
            "--json",
        ),
        purpose="validate blocked TeamOps sent-message observation receipt without terminal closure claim",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_terminal_closure_review_packet",
        command=(
            sys.executable,
            "scripts/produce_team_ops_shared_inbox_terminal_closure_review_packet.py",
            "--sent-message-observation-receipt",
            ".change_assurance/team_ops_shared_inbox_sent_message_observation_receipt.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_terminal_closure_review_packet.json",
            "--json",
        ),
        purpose="emit blocked TeamOps terminal closure review packet without certificate minting or production claim",
    ),
    AssuranceStep(
        name="team_ops_shared_inbox_terminal_closure_review_packet_validation",
        command=(
            sys.executable,
            "scripts/validate_team_ops_shared_inbox_terminal_closure_review_packet.py",
            "--packet",
            ".change_assurance/team_ops_shared_inbox_terminal_closure_review_packet.json",
            "--output",
            ".change_assurance/team_ops_shared_inbox_terminal_closure_review_packet_validation.json",
            "--json",
        ),
        purpose="validate blocked TeamOps terminal closure review packet without terminal certificate claim",
    ),
    AssuranceStep(
        name="capability_adapter_evidence",
        command=(
            sys.executable,
            "scripts/collect_capability_adapter_evidence.py",
            "--output",
            ".change_assurance/capability_adapter_evidence.json",
            "--json",
        ),
        purpose="recollect aggregate adapter evidence from local receipts",
    ),
    AssuranceStep(
        name="proof_coverage_matrix",
        command=(sys.executable, "-m", "scripts.proof_coverage_matrix"),
        purpose="refresh canonical and assurance proof coverage witnesses",
    ),
    AssuranceStep(
        name="protocol_manifest",
        command=(sys.executable, "scripts/validate_protocol_manifest.py"),
        purpose="validate protocol manifest schema index",
    ),
    AssuranceStep(
        name="finance_pilot_readiness",
        command=(sys.executable, "scripts/validate_finance_approval_pilot.py", "--json"),
        purpose="validate proof-pilot finance readiness without live handoff claim",
    ),
    AssuranceStep(
        name="finance_pilot_witness",
        command=(
            sys.executable,
            "scripts/produce_finance_approval_pilot_witness.py",
            "--output",
            ".change_assurance/finance_approval_pilot_witness.json",
            "--json",
        ),
        purpose="regenerate deterministic finance approval pilot witness",
    ),
)


def run_refresh(
    *,
    steps: Sequence[AssuranceStep] = LOCAL_ASSURANCE_STEPS,
    dry_run: bool = False,
    runner: CommandRunner = subprocess.run,
    validation_timestamp: str | None = None,
) -> tuple[AssuranceStepResult, ...]:
    """Run local assurance refresh steps in governed order."""
    results: list[AssuranceStepResult] = []
    timestamp = _resolve_validation_timestamp(validation_timestamp)
    for step in steps:
        result = _run_step(step, dry_run=dry_run, runner=runner, validation_timestamp=timestamp)
        results.append(result)
        if result.returncode != 0:
            break
    return tuple(results)


def _run_step(
    step: AssuranceStep,
    *,
    dry_run: bool,
    runner: CommandRunner,
    validation_timestamp: str,
) -> AssuranceStepResult:
    started = time.perf_counter()
    if dry_run:
        return AssuranceStepResult(
            name=step.name,
            command=step.command,
            returncode=0,
            elapsed_seconds=0.0,
            stdout_tail="",
            stderr_tail="",
            dry_run=True,
        )
    env = os.environ.copy()
    env["MULLU_VALIDATION_TIMESTAMP"] = validation_timestamp
    completed = runner(
        list(step.command),
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = time.perf_counter() - started
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    return AssuranceStepResult(
        name=step.name,
        command=step.command,
        returncode=int(completed.returncode),
        elapsed_seconds=elapsed,
        stdout_tail=_tail(completed.stdout),
        stderr_tail=_tail(completed.stderr),
    )


def _resolve_validation_timestamp(explicit_timestamp: str | None) -> str:
    if explicit_timestamp:
        return explicit_timestamp
    env_timestamp = os.environ.get("MULLU_VALIDATION_TIMESTAMP", "").strip()
    if env_timestamp:
        return env_timestamp
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _tail(value: str, *, max_chars: int = 4000) -> str:
    if len(value) <= max_chars:
        return value
    return value[-max_chars:]


def _print_text_summary(results: Sequence[AssuranceStepResult]) -> None:
    for result in results:
        status = "PASS" if result.returncode == 0 else "FAIL"
        dry = " dry-run" if result.dry_run else ""
        print(f"[{status}] {result.name}{dry}: elapsed={result.elapsed_seconds:.2f}s")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="Print planned steps without executing.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable step receipts.")
    args = parser.parse_args(argv)

    results = run_refresh(dry_run=bool(args.dry_run))
    if args.json:
        print(json.dumps([result.as_dict() for result in results], indent=2, sort_keys=True))
    else:
        _print_text_summary(results)
    return 0 if all(result.returncode == 0 for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
