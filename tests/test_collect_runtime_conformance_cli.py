"""Runtime conformance collector script-invocation tests.

Guards that ``python scripts/collect_runtime_conformance.py`` -- the exact
invocation used by ``.github/workflows/deployment-witness.yml`` -- can import
its sibling ``scripts.*`` dependencies. Running a file places that file's own
directory on ``sys.path`` rather than the repository root, so without a sys.path
bootstrap the ``from scripts.validate_schemas`` import regresses to
ModuleNotFoundError. The module-level pytest imports elsewhere do not catch this
because pytest already puts the repo root on ``sys.path``.
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
    )
    assert result.returncode == 0, result.stderr
    assert "ModuleNotFoundError" not in result.stderr
