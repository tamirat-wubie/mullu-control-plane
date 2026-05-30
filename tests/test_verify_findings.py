"""Tests for scripts/verify_findings.py (governed self-enhancement finding gate)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "verify_findings.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "finding_verifier"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(FIXTURES),
    )


def test_calibration_reproduces_all_known_verdicts() -> None:
    # The verifier must reproduce every known verdict (3 fabrications rejected,
    # 3 genuine admitted). A failure here means the verifier itself is untrusted.
    proc = _run(["corpus.json", "--calibrate"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CALIBRATION PASS" in proc.stdout


def test_strict_mode_fails_on_confabulated_finding() -> None:
    # The mixed batch has one genuine + one fabricated finding. Strict mode must
    # drop the fabricated one and fail the run.
    proc = _run(["demo_mixed.json", "--strict"])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "1 admitted, 1 dropped" in proc.stdout
    assert "FAIL" in proc.stdout


def test_nonstrict_mode_reports_but_does_not_fail() -> None:
    proc = _run(["demo_mixed.json"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "1 admitted, 1 dropped" in proc.stdout


def test_genuine_finding_is_admitted() -> None:
    proc = _run(["demo_mixed.json"])
    assert "[ADMITTED] real-001" in proc.stdout


def test_missing_file_is_bounded() -> None:
    proc = _run(["does_not_exist.json"])
    assert proc.returncode == 3
    assert "no such file" in proc.stdout
