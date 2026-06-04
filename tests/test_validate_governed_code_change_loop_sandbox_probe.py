"""Purpose: test governed code-change loop sandbox probe validation.
Governance scope: probe evidence shape, blocker consistency, strict readiness,
    host path redaction, and tamper rejection.
Dependencies: sandbox probe producer and validator.
Invariants:
  - Blocked probes validate as evidence without readiness claims.
  - Strict-ready mode rejects any unresolved blocker.
  - Passed probes require strict sandbox validation and closure permission.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.probe_governed_code_change_loop_sandbox import (
    probe_governed_code_change_loop_sandbox,
)
from scripts.validate_governed_code_change_loop_sandbox_probe import (
    validate_governed_code_change_loop_sandbox_probe,
)


def test_blocked_probe_validates_without_readiness_claim(tmp_path: Path) -> None:
    probe_path = _blocked_probe(tmp_path)

    validation = validate_governed_code_change_loop_sandbox_probe(probe_path)

    assert validation.valid is True
    assert validation.blockers == ()
    assert validation.strict_sandbox_valid is False
    assert validation.probe_id.startswith("governed-code-change-loop-sandbox-probe-")


def test_strict_ready_rejects_blocked_probe(tmp_path: Path) -> None:
    probe_path = _blocked_probe(tmp_path)

    validation = validate_governed_code_change_loop_sandbox_probe(
        probe_path,
        require_strict_sandbox_ready=True,
    )

    assert validation.valid is False
    assert validation.blockers == ("governed_code_change_loop_sandbox_probe_invalid",)
    assert "strict_sandbox_ready_requires_passed_status" in validation.detail
    assert "strict_sandbox_ready_requires_linux" in validation.detail


def test_strict_ready_accepts_simulated_linux_probe(tmp_path: Path) -> None:
    probe_path = _ready_probe(tmp_path)

    validation = validate_governed_code_change_loop_sandbox_probe(
        probe_path,
        require_strict_sandbox_ready=True,
    )

    assert validation.valid is True
    assert validation.blockers == ()
    assert validation.strict_sandbox_valid is True
    assert validation.detail == "governed code-change loop sandbox probe verified"


def test_probe_validator_rejects_host_path_leak(tmp_path: Path) -> None:
    probe_path = _blocked_probe(tmp_path)
    payload = json.loads(probe_path.read_text(encoding="utf-8"))
    payload["receipt_path"] = "C:/Users/example/receipt.json"
    probe_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    validation = validate_governed_code_change_loop_sandbox_probe(probe_path)

    assert validation.valid is False
    assert "receipt_path_must_be_repository_relative" in validation.detail


def test_probe_validator_rejects_non_string_worker_receipt_ref(tmp_path: Path) -> None:
    probe_path = _blocked_probe(tmp_path)
    payload = json.loads(probe_path.read_text(encoding="utf-8"))
    payload["code_worker_receipt_ref"] = 7
    probe_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    validation = validate_governed_code_change_loop_sandbox_probe(probe_path)

    assert validation.valid is False
    assert "code_worker_receipt_ref_invalid" in validation.detail


def test_probe_validator_rejects_non_string_blocker(tmp_path: Path) -> None:
    probe_path = _blocked_probe(tmp_path)
    payload = json.loads(probe_path.read_text(encoding="utf-8"))
    payload["blockers"] = ["sandbox_runner_linux_only", 7]
    probe_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    validation = validate_governed_code_change_loop_sandbox_probe(probe_path)

    assert validation.valid is False
    assert "blockers_not_string_list" in validation.detail


def _blocked_probe(tmp_path: Path) -> Path:
    probe_path = tmp_path / "probe.json"
    probe_governed_code_change_loop_sandbox(
        output_path=probe_path,
        receipt_output_path=tmp_path / "receipt.json",
        probe_workspace=tmp_path / "workspace",
        runner=lambda argv, **kwargs: subprocess.CompletedProcess(
            argv,
            0,
            stdout="Python 3.13\n",
            stderr="",
        ),
        platform_system=lambda: "Windows",
        docker_runner=_blocked_docker_runner,
    )
    return probe_path


def _ready_probe(tmp_path: Path) -> Path:
    probe_path = tmp_path / "probe.json"
    probe_governed_code_change_loop_sandbox(
        output_path=probe_path,
        receipt_output_path=tmp_path / "receipt.json",
        probe_workspace=tmp_path / "workspace",
        runner=lambda argv, **kwargs: subprocess.CompletedProcess(
            argv,
            0,
            stdout="Python 3.13\n",
            stderr="",
        ),
        platform_system=lambda: "Linux",
        docker_runner=_reachable_docker_runner,
    )
    return probe_path


def _blocked_docker_runner(argv, **kwargs):  # noqa: ANN001, ANN202, ARG001
    if argv[:2] == ["docker", "--version"]:
        return subprocess.CompletedProcess(argv, 0, stdout="Docker version test\n", stderr="")
    return subprocess.CompletedProcess(argv, 1, stdout="", stderr="daemon unavailable")


def _reachable_docker_runner(argv, **kwargs):  # noqa: ANN001, ANN202, ARG001
    if argv[:2] == ["docker", "--version"]:
        return subprocess.CompletedProcess(argv, 0, stdout="Docker version test\n", stderr="")
    return subprocess.CompletedProcess(argv, 0, stdout='["name=rootless"]\n', stderr="")
