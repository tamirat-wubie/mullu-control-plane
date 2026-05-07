"""v4.45.0 — stress test harness smoke test.

Ensures ``mcoi/scripts/stress_test_governance.py`` runs end-to-end
without errors and reports all 4 scenarios passing on the in-memory
backend. This is a CI gate: if any audit-grade atomicity invariant
breaks (F2 budget, F11 rate limit, F4 audit append, F12 pool
throughput), this test catches it on every PR.

The harness itself is the documented operator-facing tool for
empirically validating atomicity claims under load. This test just
ensures the tool stays runnable as the underlying APIs evolve.

A separate CI workflow (or operator manual run) exercises the
``--postgres`` mode against a real PostgreSQL to validate the
atomic SQL path. That run is out of scope for this unit test
because it requires Docker + PostgreSQL.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS = REPO_ROOT / "mcoi" / "scripts" / "stress_test_governance.py"


def test_harness_script_exists():
    assert HARNESS.is_file(), f"stress test harness missing at {HARNESS}"


def test_harness_help_runs_cleanly():
    """``--help`` should print and exit 0 — verifies argparse wiring."""
    result = subprocess.run(
        [sys.executable, str(HARNESS), "--help"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"--help exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "stress test" in result.stdout.lower()


def test_harness_in_memory_run_passes_all_scenarios():
    """Default in-memory run must exit 0 and report all scenarios passing.

    A non-zero exit means some atomicity invariant broke — that's a
    release blocker. Test reduces thread / iter counts so CI runs
    quickly without losing contention coverage (50 threads is enough
    to surface a race; 200 ops on the budget scenario covers the
    overshoot case).
    """
    result = subprocess.run(
        [
            sys.executable, str(HARNESS),
            "--threads", "50",
            "--iters", "10",
        ],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"harness exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    # All 4 scenarios should be marked PASS in the report
    assert "[PASS] atomic_budget" in result.stdout
    assert "[PASS] atomic_rate_limit" in result.stdout
    assert "[PASS] atomic_audit_append" in result.stdout
    assert "[PASS] pool_throughput" in result.stdout
    assert "4 / 4 scenarios passed" in result.stdout


def test_harness_subset_scenarios_runs():
    """``--scenarios budget,rate_limit`` runs only the requested
    scenarios. Catches regression in the dispatch logic."""
    result = subprocess.run(
        [
            sys.executable, str(HARNESS),
            "--scenarios", "budget,rate_limit",
            "--threads", "20",
            "--iters", "5",
        ],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0
    assert "[PASS] atomic_budget" in result.stdout
    assert "[PASS] atomic_rate_limit" in result.stdout
    # The other two should NOT appear
    assert "atomic_audit_append" not in result.stdout
    assert "pool_throughput" not in result.stdout
    assert "2 / 2 scenarios passed" in result.stdout


def test_harness_unknown_scenario_rejected():
    """Unknown scenario names exit non-zero. Catches typo-in-CI bugs."""
    result = subprocess.run(
        [
            sys.executable, str(HARNESS),
            "--scenarios", "bogus_scenario",
        ],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode != 0
    assert "unknown" in result.stderr.lower() or "unknown" in result.stdout.lower()
