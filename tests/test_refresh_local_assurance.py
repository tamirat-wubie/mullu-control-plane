"""Purpose: contract tests for local assurance refresh orchestration.
Governance scope: deterministic local-only refresh order and explicit command
receipts.
Dependencies: scripts.refresh_local_assurance.
Invariants:
  - Dry-run does not execute commands.
  - Runner injection records command receipts without shell construction.
  - Default steps include document, durable Gmail, TeamOps approval binding,
    authority, input, observation routing, approval queue, approval decision,
    send preparation, send execution, adapter, protocol, and finance witnesses.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import refresh_local_assurance  # noqa: E402


def test_default_refresh_steps_cover_local_assurance_surfaces() -> None:
    names = tuple(step.name for step in refresh_local_assurance.LOCAL_ASSURANCE_STEPS)

    assert names[0] == "document_live_receipt"
    assert names[1] == "durable_gmail_oauth_operator_handoff"
    assert names[2] == "durable_gmail_oauth_operator_handoff_validation"
    assert names[3] == "durable_gmail_oauth_runtime_preflight"
    assert names[4] == "team_ops_shared_inbox_operator_handoff"
    assert names[5] == "team_ops_shared_inbox_operator_handoff_validation"
    assert names[6] == "team_ops_shared_inbox_live_probe_approval_binding"
    assert names[7] == "team_ops_shared_inbox_live_probe_approval_binding_validation"
    assert names[8] == "team_ops_shared_inbox_live_probe_authority"
    assert names[9] == "team_ops_shared_inbox_live_probe_authority_validation"
    assert names[10] == "team_ops_shared_inbox_live_probe_operator_input_request"
    assert names[11] == "team_ops_shared_inbox_live_probe_operator_input_request_validation"
    assert names[12] == "team_ops_shared_inbox_live_probe_receipt"
    assert names[13] == "team_ops_shared_inbox_live_probe_receipt_validation"
    assert names[14] == "team_ops_shared_inbox_observation_routing_receipt"
    assert names[15] == "team_ops_shared_inbox_observation_routing_receipt_validation"
    assert names[16] == "team_ops_shared_inbox_approval_queue_receipt"
    assert names[17] == "team_ops_shared_inbox_approval_queue_receipt_validation"
    assert names[18] == "team_ops_shared_inbox_approval_decision_receipt"
    assert names[19] == "team_ops_shared_inbox_approval_decision_receipt_validation"
    assert names[20] == "team_ops_shared_inbox_send_preparation_receipt"
    assert names[21] == "team_ops_shared_inbox_send_preparation_receipt_validation"
    assert names[22] == "team_ops_shared_inbox_send_execution_receipt"
    assert names[23] == "team_ops_shared_inbox_send_execution_receipt_validation"
    assert "capability_adapter_evidence" in names
    assert "proof_coverage_matrix" in names
    assert "protocol_manifest" in names
    assert names[-1] == "finance_pilot_witness"


def test_dry_run_returns_step_receipts_without_invoking_runner() -> None:
    def blocked_runner(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("dry-run must not invoke subprocess")

    results = refresh_local_assurance.run_refresh(dry_run=True, runner=blocked_runner)

    assert len(results) == len(refresh_local_assurance.LOCAL_ASSURANCE_STEPS)
    assert all(result.dry_run for result in results)
    assert all(result.returncode == 0 for result in results)
    assert results[0].command[1] == "scripts/produce_capability_adapter_live_receipts.py"


def test_runner_injection_stops_on_first_failure() -> None:
    calls: list[list[str]] = []

    def fake_runner(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 2, stdout="blocked", stderr="bounded")

    results = refresh_local_assurance.run_refresh(
        steps=refresh_local_assurance.LOCAL_ASSURANCE_STEPS[:2],
        runner=fake_runner,
    )

    assert len(results) == 1
    assert len(calls) == 1
    assert results[0].returncode == 2
    assert results[0].stdout_tail == "blocked"
    assert results[0].stderr_tail == "bounded"
