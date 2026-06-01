"""Runtime conformance collector script-invocation tests.

Purpose: guard that ``python scripts/collect_runtime_conformance.py`` can import
its sibling ``scripts.*`` dependencies from workflow-style invocation paths.
Governance scope: deployment witness collection, runtime conformance evidence,
and script entrypoint import boundaries.
Dependencies: subprocess, Python executable, and collect_runtime_conformance.py.
Invariants: script help exits deterministically, emits no import failure, and is
independent of the caller's current working directory.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "collect_runtime_conformance.py"


def test_script_help_invocation_imports_cleanly() -> None:
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--help"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "ModuleNotFoundError" not in result.stderr
    assert "usage" in result.stdout.lower()


def test_script_invocation_from_unrelated_cwd_imports_cleanly(tmp_path: Path) -> None:
    # Running from an unrelated working directory must still resolve scripts.*,
    # since the bootstrap is anchored to the script path, not the cwd.
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--help"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "ModuleNotFoundError" not in result.stderr
