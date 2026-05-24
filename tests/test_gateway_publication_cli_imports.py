"""Validate gateway publication operator CLIs can run from repository root.

Purpose: protect direct script execution for documented gateway publication
operator commands.
Governance scope: CLI import path, operator handoff, and fail-closed readiness
tooling.
Dependencies: Python subprocess and gateway publication scripts.
Invariants: help commands do not require network, secrets, or repository
mutation.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_gateway_publication_operator_scripts_print_help_from_repo_root() -> None:
    scripts = [
        "scripts/collect_gateway_dns_resolution_receipt.py",
        "scripts/dispatch_gateway_publication.py",
        "scripts/publish_gateway_publication.py",
        "scripts/report_gateway_publication_readiness.py",
    ]

    for script in scripts:
        result = subprocess.run(
            [sys.executable, script, "--help"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "usage:" in result.stdout
        assert result.stderr == ""
