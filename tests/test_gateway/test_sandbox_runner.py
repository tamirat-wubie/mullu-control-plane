"""Sandbox runner contract tests.

Tests: Linux-only rootless Docker command construction, allowlist denials, and
receipt-bound sandbox verification.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess

import pytest

from gateway.sandbox_runner import (
    DockerRootlessSandboxRunner,
    SandboxCommandRequest,
    SandboxRunnerProfile,
    _workspace_snapshot,
)


def test_sandbox_runner_builds_no_network_readonly_docker_command(tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["argv"] = args[0]
        captured["shell"] = kwargs["shell"]
        captured["timeout"] = kwargs["timeout"]
        return subprocess.CompletedProcess(args[0], 0, stdout="ok", stderr="")

    runner = DockerRootlessSandboxRunner(
        host_workspace_root=str(tmp_path),
        runner=fake_runner,
        platform_system=lambda: "Linux",
    )

    result = runner.execute(
        SandboxCommandRequest(
            request_id="sandbox-request-1",
            tenant_id="tenant-1",
            capability_id="computer.command.run",
            argv=("python", "-m", "pytest"),
            environment={"MULLU_TRACE_ID": "trace-1"},
        )
    )

    docker_argv = captured["argv"]
    assert result.status == "succeeded"
    assert result.stdout == "ok"
    assert captured["shell"] is False
    assert captured["timeout"] == 120
    assert docker_argv[:4] == ["docker", "run", "--rm", "--network"]
    assert "none" in docker_argv
    assert "--read-only" in docker_argv
    assert "--mount" in docker_argv
    assert f"type=bind,src={tmp_path.resolve()},dst=/workspace,rw" in docker_argv
    assert "--env" in docker_argv
    assert "MULLU_TRACE_ID=trace-1" in docker_argv
    assert docker_argv[-3:] == ["python", "-m", "pytest"]
    receipt = result.receipt
    assert receipt.network_disabled is True
    assert receipt.read_only_rootfs is True
    assert receipt.workspace_mount == "/workspace"
    assert receipt.forbidden_effects_observed is False
    assert receipt.verification_status == "passed"
    assert receipt.changed_file_count == 0
    assert receipt.changed_file_refs == ()
    assert receipt.evidence_refs[0].startswith("sandbox_execution:")


def test_sandbox_runner_receipt_witnesses_workspace_changes(tmp_path: Path) -> None:
    workspace_file = tmp_path / "result.txt"

    def fake_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        workspace_file.write_text("changed", encoding="utf-8")
        return subprocess.CompletedProcess(args[0], 0, stdout="ok", stderr="")

    runner = DockerRootlessSandboxRunner(
        host_workspace_root=str(tmp_path),
        runner=fake_runner,
        platform_system=lambda: "Linux",
    )

    result = runner.execute(
        SandboxCommandRequest(
            request_id="sandbox-request-diff",
            tenant_id="tenant-1",
            capability_id="computer.file.write.workspace",
            argv=("python", "-m", "pytest"),
        )
    )

    assert result.status == "succeeded"
    assert result.receipt.changed_file_count == 1
    assert len(result.receipt.changed_file_refs) == 1
    assert result.receipt.changed_file_refs[0].startswith("workspace_diff:")
    assert result.receipt.forbidden_effects_observed is False


def test_workspace_snapshot_records_symlink_without_reading_target(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (workspace / "regular.txt").write_text("inside\n", encoding="utf-8")
    (outside / "secret.txt").write_text("outside\n", encoding="utf-8")
    link_path = workspace / "linked-secret.txt"
    try:
        link_path.symlink_to(outside / "secret.txt")
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink creation unavailable: {type(exc).__name__}")

    snapshot = _workspace_snapshot(workspace)

    assert "regular.txt" in snapshot
    assert "linked-secret.txt" in snapshot
    assert snapshot["linked-secret.txt"].startswith("symlink:")
    assert snapshot["linked-secret.txt"] != hashlib.sha256(
        (outside / "secret.txt").read_bytes()
    ).hexdigest()


def test_sandbox_runner_blocks_on_non_linux_without_launch(tmp_path: Path) -> None:
    launched = False

    def fake_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal launched
        launched = True
        return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

    runner = DockerRootlessSandboxRunner(
        host_workspace_root=str(tmp_path),
        runner=fake_runner,
        platform_system=lambda: "Windows",
    )

    result = runner.execute(
        SandboxCommandRequest(
            request_id="sandbox-request-2",
            tenant_id="tenant-1",
            capability_id="computer.command.run",
            argv=("python", "--version"),
        )
    )

    assert result.status == "blocked"
    assert result.stderr == "sandbox runner is linux-only"
    assert result.receipt.forbidden_effects_observed is True
    assert result.receipt.verification_status == "blocked"
    assert result.receipt.changed_file_count == 0
    assert result.receipt.changed_file_refs == ()
    assert launched is False


def test_sandbox_runner_blocks_denied_executable(tmp_path: Path) -> None:
    runner = DockerRootlessSandboxRunner(
        host_workspace_root=str(tmp_path),
        platform_system=lambda: "Linux",
    )

    result = runner.execute(
        SandboxCommandRequest(
            request_id="sandbox-request-3",
            tenant_id="tenant-1",
            capability_id="computer.command.run",
            argv=("bash", "-lc", "echo unsafe"),
        )
    )

    assert result.status == "blocked"
    assert result.stderr == "denied executable: bash"
    assert result.receipt.returncode is None
    assert result.receipt.network_disabled is True
    assert result.receipt.changed_file_count == 0


def test_sandbox_runner_blocks_unallowlisted_executable(tmp_path: Path) -> None:
    runner = DockerRootlessSandboxRunner(
        host_workspace_root=str(tmp_path),
        platform_system=lambda: "Linux",
    )

    result = runner.execute(
        SandboxCommandRequest(
            request_id="sandbox-request-4",
            tenant_id="tenant-1",
            capability_id="computer.command.run",
            argv=("ruby", "--version"),
        )
    )

    assert result.status == "blocked"
    assert result.stderr == "executable not allowlisted: ruby"
    assert result.receipt.forbidden_effects_observed is True
    assert result.receipt.evidence_refs
    assert result.receipt.changed_file_refs == ()


def test_sandbox_runner_timeout_receipt_witnesses_workspace_changes(tmp_path: Path) -> None:
    workspace_file = tmp_path / "partial.txt"

    def fake_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        workspace_file.write_text("partial", encoding="utf-8")
        raise subprocess.TimeoutExpired(args[0], timeout=1, output="partial", stderr="")

    runner = DockerRootlessSandboxRunner(
        host_workspace_root=str(tmp_path),
        runner=fake_runner,
        platform_system=lambda: "Linux",
    )

    result = runner.execute(
        SandboxCommandRequest(
            request_id="sandbox-request-timeout",
            tenant_id="tenant-1",
            capability_id="computer.code.patch",
            argv=("python", "-m", "pytest"),
        )
    )

    assert result.status == "timeout"
    assert result.receipt.verification_status == "timeout"
    assert result.receipt.changed_file_count == 1
    assert result.receipt.changed_file_refs[0].startswith("workspace_diff:")


def test_sandbox_runner_rejects_networked_profile() -> None:
    with pytest.raises(ValueError, match="^sandbox network must be none$"):
        SandboxRunnerProfile(network="bridge")


def test_sandbox_runner_rejects_host_root_workspace() -> None:
    with pytest.raises(ValueError, match="^host workspace root cannot be a forbidden mount$"):
        DockerRootlessSandboxRunner(
            host_workspace_root="/",
            platform_system=lambda: "Linux",
        )


def test_sandbox_runner_rejects_missing_workspace(tmp_path: Path) -> None:
    missing_workspace = tmp_path / "missing-workspace"

    with pytest.raises(ValueError, match="^host_workspace_root must exist$"):
        DockerRootlessSandboxRunner(
            host_workspace_root=str(missing_workspace),
            platform_system=lambda: "Linux",
        )


def test_sandbox_runner_rejects_file_workspace(tmp_path: Path) -> None:
    file_workspace = tmp_path / "workspace.txt"
    file_workspace.write_text("not a directory\n", encoding="utf-8")

    with pytest.raises(ValueError, match="^host_workspace_root must be a directory$"):
        DockerRootlessSandboxRunner(
            host_workspace_root=str(file_workspace),
            platform_system=lambda: "Linux",
        )


def test_sandbox_request_rejects_cwd_outside_workspace() -> None:
    with pytest.raises(ValueError, match="^cwd must be inside /workspace$"):
        SandboxCommandRequest(
            request_id="sandbox-request-5",
            tenant_id="tenant-1",
            capability_id="computer.command.run",
            argv=("python", "--version"),
            cwd="/tmp",
        )


def test_sandbox_request_rejects_workspace_traversal_cwd() -> None:
    with pytest.raises(ValueError, match="^cwd must be inside /workspace$"):
        SandboxCommandRequest(
            request_id="sandbox-request-6",
            tenant_id="tenant-1",
            capability_id="computer.command.run",
            argv=("python", "--version"),
            cwd="/workspace/../host",
        )


def test_sandbox_request_rejects_control_character_cwd() -> None:
    with pytest.raises(ValueError, match="^cwd contains forbidden characters$"):
        SandboxCommandRequest(
            request_id="sandbox-request-6a",
            tenant_id="tenant-1",
            capability_id="computer.command.run",
            argv=("python", "--version"),
            cwd="/workspace/app\nother",
        )


def test_sandbox_request_rejects_scalar_argv_shape() -> None:
    with pytest.raises(ValueError, match="^argv must be an argv array$"):
        SandboxCommandRequest(
            request_id="sandbox-request-6b",
            tenant_id="tenant-1",
            capability_id="computer.command.run",
            argv="python --version",  # type: ignore[arg-type]
        )


def test_sandbox_request_rejects_control_character_argv_item() -> None:
    with pytest.raises(ValueError, match="^argv contains forbidden characters$"):
        SandboxCommandRequest(
            request_id="sandbox-request-6d",
            tenant_id="tenant-1",
            capability_id="computer.command.run",
            argv=("python", "line1\nline2"),
        )


def test_sandbox_request_accepts_list_argv_as_explicit_argv_array() -> None:
    request = SandboxCommandRequest(
        request_id="sandbox-request-6c",
        tenant_id="tenant-1",
        capability_id="computer.command.run",
        argv=["python", "--version"],  # type: ignore[arg-type]
    )

    assert request.argv == ("python", "--version")


def test_sandbox_request_rejects_invalid_environment_key() -> None:
    with pytest.raises(ValueError, match="^environment key contains forbidden characters$"):
        SandboxCommandRequest(
            request_id="sandbox-request-7",
            tenant_id="tenant-1",
            capability_id="computer.command.run",
            argv=("python", "--version"),
            environment={"BAD=KEY": "value"},
        )


def test_sandbox_request_rejects_non_string_environment_key() -> None:
    with pytest.raises(ValueError, match="^environment keys must be strings$"):
        SandboxCommandRequest(
            request_id="sandbox-request-7b",
            tenant_id="tenant-1",
            capability_id="computer.command.run",
            argv=("python", "--version"),
            environment={1: "value"},  # type: ignore[dict-item]
        )


def test_sandbox_request_rejects_control_character_environment_value() -> None:
    with pytest.raises(ValueError, match="^environment value contains forbidden characters$"):
        SandboxCommandRequest(
            request_id="sandbox-request-7c",
            tenant_id="tenant-1",
            capability_id="computer.command.run",
            argv=("python", "--version"),
            environment={"SAFE_KEY": "line1\nline2"},
        )


def test_sandbox_runner_rejects_workspace_mount_delimiter(tmp_path: Path) -> None:
    workspace_with_delimiter = tmp_path / "workspace,ro"
    workspace_with_delimiter.mkdir()

    with pytest.raises(ValueError, match="^host workspace root cannot contain Docker mount delimiters$"):
        DockerRootlessSandboxRunner(
            host_workspace_root=str(workspace_with_delimiter),
            platform_system=lambda: "Linux",
        )
