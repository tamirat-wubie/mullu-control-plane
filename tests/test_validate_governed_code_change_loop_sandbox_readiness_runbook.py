"""Purpose: test governed code-change loop sandbox readiness runbook validation.
Governance scope: Linux strict-readiness handoff, blocker taxonomy, and
    non-terminal evidence boundaries.
Dependencies: pytest, pathlib, and runbook validator.
Invariants:
  - The canonical runbook contains the strict probe command.
  - Missing strict-readiness fragments are reported explicitly.
  - Missing files fail without raising.
"""

from __future__ import annotations

from pathlib import Path

from scripts.validate_governed_code_change_loop_sandbox_readiness_runbook import (
    DEFAULT_RUNNER_DOCKERFILE_PATH,
    DEFAULT_RUNBOOK_PATH,
    DEFAULT_WINDOWS_ASSESSOR_PATH,
    DEFAULT_WSL_LAUNCHER_PATH,
    REQUIRED_DOCKERFILE_FRAGMENTS,
    REQUIRED_FRAGMENTS,
    REQUIRED_WINDOWS_ASSESSOR_FRAGMENTS,
    REQUIRED_WSL_LAUNCHER_FRAGMENTS,
    validate_runbook,
)


def test_canonical_runbook_validates() -> None:
    validation = validate_runbook(DEFAULT_RUNBOOK_PATH)

    assert validation.valid is True
    assert validation.runbook_path == "docs/GOVERNED_CODE_CHANGE_LOOP_SANDBOX_READINESS.md"
    assert validation.missing_fragments == ()
    assert "verified" in validation.detail
    assert DEFAULT_RUNNER_DOCKERFILE_PATH.exists()
    assert DEFAULT_RUNNER_DOCKERFILE_PATH.name == "governed-code-change-loop-runner.Dockerfile"
    assert DEFAULT_WSL_LAUNCHER_PATH.exists()
    assert DEFAULT_WSL_LAUNCHER_PATH.name == "run_wsl_governed_code_change_loop_sandbox_probe.py"
    assert DEFAULT_WINDOWS_ASSESSOR_PATH.exists()
    assert DEFAULT_WINDOWS_ASSESSOR_PATH.name == "assess_windows_governed_code_change_loop_readiness.py"


def test_runner_dockerfile_carries_required_contract() -> None:
    dockerfile_text = DEFAULT_RUNNER_DOCKERFILE_PATH.read_text(encoding="utf-8")

    assert "Purpose: minimal no-network sandbox image" in dockerfile_text
    assert all(fragment in dockerfile_text for fragment in REQUIRED_DOCKERFILE_FRAGMENTS)
    assert "USER nonroot" in dockerfile_text
    assert "WORKDIR /workspace" in dockerfile_text


def test_wsl_launcher_carries_required_contract() -> None:
    launcher_text = DEFAULT_WSL_LAUNCHER_PATH.read_text(encoding="utf-8")

    assert "Run the governed code-change loop strict sandbox probe through WSL" in launcher_text
    assert all(fragment in launcher_text for fragment in REQUIRED_WSL_LAUNCHER_FRAGMENTS)
    assert "build_wsl_argv" in launcher_text
    assert "--print-command" in launcher_text
    assert "wsl_workspace_path_invalid" in launcher_text


def test_windows_assessor_carries_required_contract() -> None:
    assessor_text = DEFAULT_WINDOWS_ASSESSOR_PATH.read_text(encoding="utf-8")

    assert "Assess Windows readiness for governed code-change loop sandbox evidence" in assessor_text
    assert all(fragment in assessor_text for fragment in REQUIRED_WINDOWS_ASSESSOR_FRAGMENTS)
    assert "windows_docker_cli_missing" in assessor_text
    assert "windows_wsl_cli_missing" in assessor_text
    assert "strict_probe_argv" in assessor_text


def test_missing_required_fragment_is_reported(tmp_path: Path) -> None:
    runbook_path = tmp_path / "runbook.md"
    runbook_path.write_text(
        "\n".join(fragment for fragment in REQUIRED_FRAGMENTS if fragment != "windows_wsl_cli_missing"),
        encoding="utf-8",
    )

    validation = validate_runbook(runbook_path)

    assert validation.valid is False
    assert validation.missing_fragments == ("windows_wsl_cli_missing",)
    assert validation.detail == "runbook missing required strict-readiness fragments"
    assert validation.runbook_path == "runbook.md"


def test_missing_runbook_file_fails_without_exception(tmp_path: Path) -> None:
    validation = validate_runbook(tmp_path / "missing.md")

    assert validation.valid is False
    assert validation.missing_fragments == ()
    assert validation.detail == "runbook file not found"
