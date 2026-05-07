"""Purpose: test sandboxed code-worker leases and receipts.
Governance scope: validates lease contracts, command admission, sandbox receipt
    propagation, denied command blocking, and allowed-path enforcement.
Dependencies: pytest plus MCOI code_worker contracts and worker runtime.
Invariants:
  - Commands are argv tuples and must exactly match a lease.
  - Blocked commands emit receipts without dispatching the sandbox runner.
  - Successful commands bind output hashes and sandbox evidence references.
  - Path and network authority stay bounded by the lease.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.code_worker import (
    CodeWorkerLease,
    CodeWorkerReceiptStatus,
)
from mcoi_runtime.workers.code_worker import SandboxedCodeWorker


def _lease(**overrides: object) -> CodeWorkerLease:
    values = {
        "lease_id": "lease-1",
        "tenant_id": "tenant-a",
        "repository": "repo-a",
        "commit_sha": "abc123",
        "allowed_paths": ("src",),
        "allowed_commands": (("python", "src/task.py"),),
        "network_enabled": False,
        "timeout_seconds": 30,
        "memory_mb": 256,
        "expires_at": "2026-05-08T12:00:00+00:00",
        "metadata": {"purpose": "test"},
    }
    values.update(overrides)
    return CodeWorkerLease(**values)


def test_code_worker_lease_contract_is_frozen_and_json_safe() -> None:
    lease = _lease(allowed_paths=("./src", "src"), allowed_commands=(("python", "src/task.py"),))
    payload = lease.to_json_dict()

    assert lease.allowed_paths == ("src",)
    assert payload["allowed_commands"] == [["python", "src/task.py"]]
    assert isinstance(lease.metadata, MappingProxyType)
    with pytest.raises(ValueError):
        _lease(allowed_commands=())
    with pytest.raises(ValueError):
        _lease(allowed_paths=("../outside",))
    with pytest.raises(Exception):
        lease.allowed_paths += ("tests",)  # type: ignore[misc]


def test_sandboxed_code_worker_executes_exact_lease_command_with_receipt(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "task.py").write_text("print('ok')\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_runner(argv, **kwargs):  # noqa: ANN001, ANN202
        calls.append(list(argv))
        (tmp_path / "src" / "result.txt").write_text("changed\n", encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, stdout="ok\n", stderr="")

    worker = SandboxedCodeWorker(
        workspace_root=str(tmp_path),
        clock=lambda: "2026-05-07T12:00:00+00:00",
        runner=fake_runner,
        platform_system=lambda: "Linux",
    )

    result = worker.execute_command(
        _lease(allowed_commands=(("python", "-m", "task"),)),
        command_id="cmd-1",
        argv=("python", "-m", "task"),
        cwd="src",
    )

    assert result.status is CodeWorkerReceiptStatus.SUCCEEDED
    assert result.stdout == "ok\n"
    assert result.receipt.returncode == 0
    assert result.receipt.sandbox_receipt_id is not None
    assert result.receipt.network_enabled is False
    assert result.receipt.metadata["sandbox_network_disabled"] is True
    assert result.receipt.metadata["production_credentials_available"] is False
    assert result.receipt.changed_file_refs
    assert result.receipt.evidence_refs[0].startswith("code_worker:")
    assert any(ref.startswith("sandbox:sandbox_execution:") for ref in result.receipt.evidence_refs)
    assert calls and "--network" in calls[0] and "none" in calls[0]


def test_sandboxed_code_worker_blocks_sandbox_mutation_outside_lease_path(
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "other").mkdir()

    def fake_runner(argv, **kwargs):  # noqa: ANN001, ANN202, ARG001
        (tmp_path / "other" / "result.txt").write_text("escaped\n", encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, stdout="ok\n", stderr="")

    worker = SandboxedCodeWorker(
        workspace_root=str(tmp_path),
        clock=lambda: "2026-05-07T12:00:00+00:00",
        runner=fake_runner,
        platform_system=lambda: "Linux",
    )

    result = worker.execute_command(
        _lease(allowed_commands=(("python", "-m", "task"),)),
        command_id="cmd-1b",
        argv=("python", "-m", "task"),
        cwd="src",
    )

    assert result.status is CodeWorkerReceiptStatus.BLOCKED
    assert result.stdout == "ok\n"
    assert result.receipt.sandbox_receipt_id is not None
    assert result.receipt.returncode == 0
    assert result.receipt.metadata["worker_changed_file_count"] == 1
    assert result.receipt.violation_reasons[0].startswith(
        "sandbox_changed_file_outside_lease_allowed_paths:"
    )
    assert "other/result.txt" not in result.stderr


def test_sandboxed_code_worker_blocks_denied_executable_without_dispatch(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    dispatched = False

    def fake_runner(argv, **kwargs):  # noqa: ANN001, ANN202
        nonlocal dispatched
        dispatched = True
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    worker = SandboxedCodeWorker(
        workspace_root=str(tmp_path),
        clock=lambda: "2026-05-07T12:00:00+00:00",
        runner=fake_runner,
    )

    result = worker.execute_command(
        _lease(allowed_commands=(("bash", "src/task.sh"),)),
        command_id="cmd-2",
        argv=("bash", "src/task.sh"),
        cwd="src",
    )

    assert result.status is CodeWorkerReceiptStatus.BLOCKED
    assert dispatched is False
    assert "denied_executable:bash" in result.stderr
    assert result.receipt.sandbox_receipt_id is None
    assert result.receipt.returncode is None
    assert result.receipt.violation_reasons == ("denied_executable:bash",)
    assert result.receipt.metadata["sandbox_dispatched"] is False


def test_sandboxed_code_worker_blocks_argv_path_outside_lease(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    worker = SandboxedCodeWorker(
        workspace_root=str(tmp_path),
        clock=lambda: "2026-05-07T12:00:00+00:00",
        runner=lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, stdout="", stderr=""),
    )

    result = worker.execute_command(
        _lease(allowed_commands=(("python", "tests/test_task.py"),)),
        command_id="cmd-3",
        argv=("python", "tests/test_task.py"),
        cwd="src",
    )

    assert result.status is CodeWorkerReceiptStatus.BLOCKED
    assert "argv_path_outside_lease_allowed_paths:" in result.stderr
    assert result.receipt.changed_file_refs == ()
    assert result.receipt.violation_reasons[0].startswith("argv_path_outside_lease_allowed_paths:")
    assert result.receipt.evidence_refs[0].startswith("code_worker:")


def test_sandboxed_code_worker_blocks_argv_path_outside_repository_boundary(
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    dispatched = False

    def fake_runner(argv, **kwargs):  # noqa: ANN001, ANN202
        nonlocal dispatched
        dispatched = True
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    worker = SandboxedCodeWorker(
        workspace_root=str(tmp_path),
        clock=lambda: "2026-05-07T12:00:00+00:00",
        runner=fake_runner,
    )

    result = worker.execute_command(
        _lease(allowed_commands=(("python", "../outside.py"),)),
        command_id="cmd-3b",
        argv=("python", "../outside.py"),
        cwd="src",
    )

    assert dispatched is False
    assert result.status is CodeWorkerReceiptStatus.BLOCKED
    assert "argv_path_outside_repository_boundary:" in result.stderr
    assert result.receipt.changed_file_refs == ()
    assert result.receipt.sandbox_receipt_id is None
    assert result.receipt.violation_reasons[0].startswith("argv_path_outside_repository_boundary:")
    assert "../outside.py" not in result.stderr


def test_sandboxed_code_worker_blocks_cwd_outside_repository_boundary(
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    dispatched = False

    def fake_runner(argv, **kwargs):  # noqa: ANN001, ANN202
        nonlocal dispatched
        dispatched = True
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    worker = SandboxedCodeWorker(
        workspace_root=str(tmp_path),
        clock=lambda: "2026-05-07T12:00:00+00:00",
        runner=fake_runner,
    )

    result = worker.execute_command(
        _lease(),
        command_id="cmd-3c",
        argv=("python", "src/task.py"),
        cwd="../outside",
    )

    assert dispatched is False
    assert result.status is CodeWorkerReceiptStatus.BLOCKED
    assert "cwd_outside_repository_boundary:" in result.stderr
    assert result.receipt.changed_file_refs == ()
    assert result.receipt.sandbox_receipt_id is None
    assert result.receipt.violation_reasons[0].startswith("cwd_outside_repository_boundary:")
    assert "../outside" not in result.stderr


def test_sandboxed_code_worker_blocks_flag_embedded_path_violations(
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    dispatched = False

    def fake_runner(argv, **kwargs):  # noqa: ANN001, ANN202
        nonlocal dispatched
        dispatched = True
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    worker = SandboxedCodeWorker(
        workspace_root=str(tmp_path),
        clock=lambda: "2026-05-07T12:00:00+00:00",
        runner=fake_runner,
    )

    boundary_result = worker.execute_command(
        _lease(allowed_commands=(("python", "--config=../outside.py"),)),
        command_id="cmd-3d",
        argv=("python", "--config=../outside.py"),
        cwd="src",
    )
    lease_result = worker.execute_command(
        _lease(allowed_commands=(("python", "--config=tests/test_task.py"),)),
        command_id="cmd-3e",
        argv=("python", "--config=tests/test_task.py"),
        cwd="src",
    )

    assert dispatched is False
    assert boundary_result.status is CodeWorkerReceiptStatus.BLOCKED
    assert lease_result.status is CodeWorkerReceiptStatus.BLOCKED
    assert boundary_result.receipt.violation_reasons[0].startswith("argv_path_outside_repository_boundary:")
    assert lease_result.receipt.violation_reasons[0].startswith("argv_path_outside_lease_allowed_paths:")
    assert "../outside.py" not in boundary_result.stderr
    assert "tests/test_task.py" not in lease_result.stderr


def test_sandboxed_code_worker_blocks_network_and_risky_git_without_dispatch(
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    dispatched = False

    def fake_runner(argv, **kwargs):  # noqa: ANN001, ANN202
        nonlocal dispatched
        dispatched = True
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    worker = SandboxedCodeWorker(
        workspace_root=str(tmp_path),
        clock=lambda: "2026-05-07T12:00:00+00:00",
        runner=fake_runner,
    )

    network_result = worker.execute_command(
        _lease(network_enabled=True),
        command_id="cmd-4",
        argv=("python", "src/task.py"),
        cwd="src",
    )
    git_result = worker.execute_command(
        _lease(allowed_commands=(("git", "push", "origin", "main"),)),
        command_id="cmd-5",
        argv=("git", "push", "origin", "main"),
        cwd="src",
    )

    assert dispatched is False
    assert network_result.status is CodeWorkerReceiptStatus.BLOCKED
    assert network_result.receipt.violation_reasons == ("network_enabled_not_allowed",)
    assert git_result.status is CodeWorkerReceiptStatus.BLOCKED
    assert git_result.receipt.violation_reasons == ("denied_git_subcommand:push",)
    assert git_result.receipt.sandbox_receipt_id is None


def test_sandboxed_code_worker_blocks_expired_lease_and_linux_only_sandbox(
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    expired_worker = SandboxedCodeWorker(
        workspace_root=str(tmp_path),
        clock=lambda: "2026-05-07T12:00:00+00:00",
        runner=lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, stdout="", stderr=""),
    )
    windows_worker = SandboxedCodeWorker(
        workspace_root=str(tmp_path),
        clock=lambda: "2026-05-07T12:00:00+00:00",
        runner=lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, stdout="", stderr=""),
        platform_system=lambda: "Windows",
    )

    expired = expired_worker.execute_command(
        _lease(expires_at="2026-05-07T11:00:00+00:00"),
        command_id="cmd-6",
        argv=("python", "src/task.py"),
        cwd="src",
    )
    linux_only = windows_worker.execute_command(
        _lease(),
        command_id="cmd-7",
        argv=("python", "src/task.py"),
        cwd="src",
    )

    assert expired.status is CodeWorkerReceiptStatus.BLOCKED
    assert expired.receipt.violation_reasons == ("lease_expired",)
    assert expired.receipt.sandbox_receipt_id is None
    assert linux_only.status is CodeWorkerReceiptStatus.BLOCKED
    assert linux_only.receipt.sandbox_receipt_id is not None
    assert linux_only.receipt.violation_reasons == ("sandbox runner is linux-only",)
