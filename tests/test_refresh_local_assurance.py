"""Purpose: contract tests for local assurance refresh orchestration.
Governance scope: deterministic local-only refresh order and explicit command
receipts.
Dependencies: scripts.refresh_local_assurance.
Invariants:
  - Dry-run does not execute commands.
  - Runner injection records command receipts without shell construction.
  - Default steps include document, durable Gmail, adapter, protocol, and finance witnesses.
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
    assert results[1].command[1] == "scripts/produce_durable_gmail_oauth_operator_handoff.py"
    assert results[2].command[1] == "scripts/validate_durable_gmail_oauth_operator_handoff.py"


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
