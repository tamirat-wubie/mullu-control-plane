"""Governed swarm staging runner preflight tests.

Purpose: prove staging witness runner readiness is emitted as an auditable receipt.
Governance scope: runner-local runtime bridge checks, audit-store checks, and dispatch input checks.
Dependencies: scripts.preflight_governed_swarm_staging_runner.
Invariants: ready receipts require all checks to pass; missing runner surfaces fail closed with causal detail.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.preflight_governed_swarm_staging_runner import preflight_runner, write_receipt


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "preflight_governed_swarm_staging_runner.py"


def test_preflight_runner_emits_ready_receipt(tmp_path: Path) -> None:
    runtime_path = tmp_path / "runtime"
    bridge_path = runtime_path / "mcoi_runtime" / "swarm"
    bridge_path.mkdir(parents=True)
    audit_store_path = tmp_path / "swarm-runs.jsonl"
    audit_store_path.write_text('{"closure": true}\n', encoding="utf-8")

    receipt = preflight_runner(
        staging_url="https://staging-api.example.com",
        control_plane_commit="7eac1d0",
        runtime_path=runtime_path,
        audit_store_path=audit_store_path,
        clock=lambda: "2026-05-17T00:00:00Z",
    )

    assert receipt.ready is True
    assert receipt.outcome == "SolvedVerified"
    assert len(receipt.checks) == 5
    assert all(check.passed for check in receipt.checks)
    assert receipt.runtime_path == str(runtime_path)


def test_preflight_runner_fails_closed_for_missing_surfaces(tmp_path: Path) -> None:
    receipt = preflight_runner(
        staging_url="not-a-url",
        control_plane_commit="",
        runtime_path=tmp_path / "missing-runtime",
        audit_store_path=tmp_path / "missing-audit.jsonl",
        clock=lambda: "2026-05-17T00:00:00Z",
    )

    failed_checks = {check.name: check.detail for check in receipt.checks if not check.passed}
    assert receipt.ready is False
    assert receipt.outcome == "AwaitingEvidence"
    assert "staging_url" in failed_checks
    assert "control_plane_commit" in failed_checks
    assert "runtime_bridge" in failed_checks
    assert "audit_store_exists" in failed_checks


def test_preflight_runner_cli_writes_receipt(tmp_path: Path) -> None:
    runtime_path = tmp_path / "runtime"
    (runtime_path / "mcoi_runtime" / "swarm").mkdir(parents=True)
    audit_store_path = tmp_path / "swarm-runs.jsonl"
    audit_store_path.write_text('{"closure": true}\n', encoding="utf-8")
    output_path = tmp_path / "receipt.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--staging-url",
            "https://staging-api.example.com",
            "--control-plane-commit",
            "7eac1d0",
            "--runtime-path",
            str(runtime_path),
            "--audit-store-path",
            str(audit_store_path),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.returncode == 0
    assert payload["ready"] is True
    assert payload["outcome"] == "SolvedVerified"
    assert len(payload["checks"]) == 5
    assert "STATUS: passed" in result.stdout
