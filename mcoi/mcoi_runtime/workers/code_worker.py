"""Purpose: lease-bound sandboxed code worker.
Governance scope: command admission, lease expiry, allowed command/path checks,
    no-network enforcement, rootless Docker sandbox dispatch, and worker receipts.
Dependencies: code_worker contracts and gateway.sandbox_runner.
Invariants:
  - Commands are argv tuples, never shell strings.
  - A command must exactly match a lease allowed_commands entry.
  - Network-enabled leases are blocked by default.
  - Shells, network tools, and risky git subcommands are denied even if listed.
  - Every denied or executed command returns a CodeWorkerReceipt.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
from typing import Callable, Sequence

from gateway.sandbox_runner import (
    DockerRootlessSandboxRunner,
    SandboxCommandRequest,
    SandboxRunnerProfile,
)

from mcoi_runtime.contracts.code_worker import (
    CodeWorkerCommandResult,
    CodeWorkerLease,
    CodeWorkerReceipt,
    CodeWorkerReceiptStatus,
)


Runner = Callable[..., subprocess.CompletedProcess[str]]

_CAPABILITY_ID = "code.worker.command.run"
_DENIED_EXECUTABLES: frozenset[str] = frozenset(
    {
        "bash",
        "sh",
        "zsh",
        "fish",
        "dash",
        "ksh",
        "cmd",
        "powershell",
        "pwsh",
        "curl",
        "wget",
        "ssh",
        "scp",
        "rsync",
        "nc",
        "ncat",
        "telnet",
        "socat",
        "docker",
    }
)
_DENIED_GIT_SUBCOMMANDS: frozenset[str] = frozenset(
    {"push", "pull", "fetch", "clone", "remote", "submodule", "credential"}
)
_PATH_SUFFIXES: tuple[str, ...] = (
    ".py",
    ".pyi",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".md",
    ".txt",
    ".rs",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
)


class SandboxedCodeWorker:
    """Execute exact lease-admitted commands in a no-network sandbox."""

    def __init__(
        self,
        *,
        workspace_root: str,
        clock: Callable[[], str],
        runner: Runner = subprocess.run,
        platform_system: Callable[[], str] | None = None,
        sandbox_image: str = "mullu-agent-runner:latest",
        allow_network_leases: bool = False,
    ) -> None:
        root = Path(workspace_root).resolve(strict=False)
        if not root.exists() or not root.is_dir():
            raise ValueError("workspace_root must be an existing directory")
        self._workspace_root = root
        self._clock = clock
        self._runner = runner
        self._platform_system = platform_system
        self._sandbox_image = sandbox_image
        self._allow_network_leases = allow_network_leases

    @property
    def workspace_root(self) -> Path:
        return self._workspace_root

    def execute_command(
        self,
        lease: CodeWorkerLease,
        *,
        command_id: str,
        argv: Sequence[str],
        cwd: str = ".",
    ) -> CodeWorkerCommandResult:
        """Execute one command or return a blocked receipt.

        Error contract:
          - Raises ValueError only for malformed typed inputs.
          - Policy, lease, sandbox, and timeout failures return receipts.
        """
        if not isinstance(lease, CodeWorkerLease):
            raise ValueError("lease must be a CodeWorkerLease")
        normalized_command_id = _require_text(command_id, "command_id")
        command = _normalize_argv(argv)
        normalized_cwd = _normalize_relative_path(cwd)
        started_at = self._clock()

        violations = _admission_violations(
            lease=lease,
            argv=command,
            cwd=normalized_cwd,
            now=started_at,
            allow_network_leases=self._allow_network_leases,
        )
        if violations:
            finished_at = self._clock()
            return self._blocked_result(
                lease=lease,
                command_id=normalized_command_id,
                argv=command,
                started_at=started_at,
                finished_at=finished_at,
                violations=violations,
            )

        profile = SandboxRunnerProfile(
            image=self._sandbox_image,
            network="none",
            read_only_rootfs=True,
            timeout_seconds=lease.timeout_seconds,
            max_memory=f"{lease.memory_mb}m",
            allowed_executables=tuple(sorted({_executable_name(command[0])})),
            denied_executables=tuple(sorted(_DENIED_EXECUTABLES)),
        )
        sandbox_runner = DockerRootlessSandboxRunner(
            host_workspace_root=str(self._workspace_root),
            profile=profile,
            runner=self._runner,
            clock=self._clock,
            platform_system=self._platform_system or _platform_system_default,
        )
        sandbox_result = sandbox_runner.execute(
            SandboxCommandRequest(
                request_id=normalized_command_id,
                tenant_id=lease.tenant_id,
                capability_id=_CAPABILITY_ID,
                argv=_sandbox_argv(command, normalized_cwd),
                cwd=_container_cwd(normalized_cwd),
                environment={},
            )
        )
        finished_at = self._clock()
        status = _status_from_sandbox_status(sandbox_result.status)
        violation_reasons = (
            (_bounded_violation(sandbox_result.stderr),)
            if status is CodeWorkerReceiptStatus.BLOCKED and sandbox_result.stderr
            else ()
        )
        receipt = _build_receipt(
            lease=lease,
            command_id=normalized_command_id,
            argv=command,
            status=status,
            stdout=sandbox_result.stdout,
            stderr=sandbox_result.stderr,
            started_at=started_at,
            finished_at=finished_at,
            returncode=sandbox_result.receipt.returncode,
            sandbox_receipt_id=sandbox_result.receipt.receipt_id,
            changed_file_refs=sandbox_result.receipt.changed_file_refs,
            violation_reasons=violation_reasons,
            sandbox_evidence_refs=sandbox_result.receipt.evidence_refs,
            metadata={
                "sandbox_id": sandbox_result.receipt.sandbox_id,
                "sandbox_verification_status": sandbox_result.receipt.verification_status,
                "sandbox_network_disabled": sandbox_result.receipt.network_disabled,
                "sandbox_read_only_rootfs": sandbox_result.receipt.read_only_rootfs,
                "workspace_mount": sandbox_result.receipt.workspace_mount,
                "production_credentials_available": False,
            },
        )
        return CodeWorkerCommandResult(
            status=status,
            stdout=sandbox_result.stdout,
            stderr=sandbox_result.stderr,
            receipt=receipt,
        )

    def _blocked_result(
        self,
        *,
        lease: CodeWorkerLease,
        command_id: str,
        argv: tuple[str, ...],
        started_at: str,
        finished_at: str,
        violations: tuple[str, ...],
    ) -> CodeWorkerCommandResult:
        stderr = "; ".join(violations)
        receipt = _build_receipt(
            lease=lease,
            command_id=command_id,
            argv=argv,
            status=CodeWorkerReceiptStatus.BLOCKED,
            stdout="",
            stderr=stderr,
            started_at=started_at,
            finished_at=finished_at,
            returncode=None,
            sandbox_receipt_id=None,
            changed_file_refs=(),
            violation_reasons=violations,
            sandbox_evidence_refs=(),
            metadata={
                "sandbox_dispatched": False,
                "production_credentials_available": False,
            },
        )
        return CodeWorkerCommandResult(
            status=CodeWorkerReceiptStatus.BLOCKED,
            stdout="",
            stderr=stderr,
            receipt=receipt,
        )


def _admission_violations(
    *,
    lease: CodeWorkerLease,
    argv: tuple[str, ...],
    cwd: str,
    now: str,
    allow_network_leases: bool,
) -> tuple[str, ...]:
    violations: list[str] = []
    if _is_expired(lease.expires_at, now):
        violations.append("lease_expired")
    if lease.network_enabled and not allow_network_leases:
        violations.append("network_enabled_not_allowed")
    if argv not in lease.allowed_commands:
        violations.append("command_not_in_lease_allowed_commands")
    executable = _executable_name(argv[0])
    if executable in _DENIED_EXECUTABLES:
        violations.append(f"denied_executable:{executable}")
    if executable == "git":
        git_subcommand = _git_subcommand(argv[1:])
        if git_subcommand in _DENIED_GIT_SUBCOMMANDS:
            violations.append(f"denied_git_subcommand:{git_subcommand}")
    if not _path_within_allowed(cwd, lease.allowed_paths):
        violations.append("cwd_outside_lease_allowed_paths")
    path_violation = _argv_path_violation(argv, lease.allowed_paths)
    if path_violation is not None:
        violations.append(path_violation)
    return tuple(violations)


def _build_receipt(
    *,
    lease: CodeWorkerLease,
    command_id: str,
    argv: tuple[str, ...],
    status: CodeWorkerReceiptStatus,
    stdout: str,
    stderr: str,
    started_at: str,
    finished_at: str,
    returncode: int | None,
    sandbox_receipt_id: str | None,
    changed_file_refs: tuple[str, ...],
    violation_reasons: tuple[str, ...],
    sandbox_evidence_refs: tuple[str, ...],
    metadata: dict[str, object],
) -> CodeWorkerReceipt:
    command_hash = _canonical_hash(
        {
            "lease_id": lease.lease_id,
            "command_id": command_id,
            "argv": argv,
            "allowed_paths": lease.allowed_paths,
        }
    )
    stdout_hash = _sha256_text(stdout)
    stderr_hash = _sha256_text(stderr)
    receipt_hash = _canonical_hash(
        {
            "lease_id": lease.lease_id,
            "command_id": command_id,
            "status": status.value,
            "command_hash": command_hash,
            "stdout_hash": stdout_hash,
            "stderr_hash": stderr_hash,
            "sandbox_receipt_id": sandbox_receipt_id,
            "returncode": returncode,
            "changed_file_refs": changed_file_refs,
            "violation_reasons": violation_reasons,
        }
    )
    evidence_refs = (
        f"code_worker:{receipt_hash[:16]}",
        *(f"sandbox:{ref}" for ref in sandbox_evidence_refs),
    )
    return CodeWorkerReceipt(
        receipt_id=f"code-worker-receipt-{receipt_hash[:16]}",
        lease_id=lease.lease_id,
        command_id=command_id,
        tenant_id=lease.tenant_id,
        repository=lease.repository,
        commit_sha=lease.commit_sha,
        status=status,
        command_hash=command_hash,
        stdout_hash=stdout_hash,
        stderr_hash=stderr_hash,
        network_enabled=lease.network_enabled,
        started_at=started_at,
        finished_at=finished_at,
        returncode=returncode,
        sandbox_receipt_id=sandbox_receipt_id,
        changed_file_refs=changed_file_refs,
        violation_reasons=violation_reasons,
        evidence_refs=evidence_refs,
        metadata=metadata,
    )


def _status_from_sandbox_status(status: str) -> CodeWorkerReceiptStatus:
    if status == "succeeded":
        return CodeWorkerReceiptStatus.SUCCEEDED
    if status == "timeout":
        return CodeWorkerReceiptStatus.TIMEOUT
    if status == "blocked":
        return CodeWorkerReceiptStatus.BLOCKED
    return CodeWorkerReceiptStatus.FAILED


def _is_expired(expires_at: str, now: str) -> bool:
    expires_at_dt = _parse_datetime(expires_at)
    now_dt = _parse_datetime(now)
    return now_dt >= expires_at_dt


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _normalize_argv(argv: Sequence[str]) -> tuple[str, ...]:
    if isinstance(argv, str):
        raise ValueError("argv must be a sequence of strings, not a shell string")
    command = tuple(argv)
    if not command:
        raise ValueError("argv must contain at least one item")
    for item in command:
        _require_text(item, "argv item")
        if "\x00" in item:
            raise ValueError("argv item contains NUL byte")
    return command


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _normalize_relative_path(path_text: str) -> str:
    normalized = _require_text(path_text, "path").replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized == ".":
        return "."
    if normalized.startswith("/") or ".." in PurePosixPath(normalized).parts:
        raise ValueError("path must stay inside repository root")
    return normalized


def _container_cwd(relative_cwd: str) -> str:
    if relative_cwd == ".":
        return "/workspace"
    return f"/workspace/{relative_cwd}"


def _sandbox_argv(argv: tuple[str, ...], relative_cwd: str) -> tuple[str, ...]:
    """Project lease-validated argv into the sandbox workdir.

    gateway.sandbox_runner treats slash-bearing argv entries as possible mount
    requests. The lease still validates the original repository-relative path;
    when the caller has selected that path's parent as cwd, the sandbox can
    receive the shorter in-workdir path without losing authority traceability.
    """
    if relative_cwd == ".":
        return argv
    projected: list[str] = [argv[0]]
    prefix = f"{relative_cwd}/"
    for item in argv[1:]:
        if _looks_like_path(item):
            normalized = _normalize_relative_path(item)
            if normalized.startswith(prefix):
                projected.append(normalized[len(prefix):] or ".")
                continue
        projected.append(item)
    return tuple(projected)


def _path_within_allowed(path_text: str, allowed_paths: tuple[str, ...]) -> bool:
    normalized_path = _normalize_relative_path(path_text)
    if "." in allowed_paths:
        return True
    return any(normalized_path == allowed_path or normalized_path.startswith(f"{allowed_path}/") for allowed_path in allowed_paths)


def _argv_path_violation(argv: tuple[str, ...], allowed_paths: tuple[str, ...]) -> str | None:
    for item in argv[1:]:
        if item.startswith("-"):
            continue
        if not _looks_like_path(item):
            continue
        normalized_path = _normalize_relative_path(item)
        if not _path_within_allowed(normalized_path, allowed_paths):
            return f"argv_path_outside_lease_allowed_paths:{_sha256_text(normalized_path)[:16]}"
    return None


def _looks_like_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    if normalized == "." or "/" in normalized:
        return True
    return normalized.endswith(_PATH_SUFFIXES)


def _executable_name(value: str) -> str:
    name = Path(value).name.lower()
    if name.endswith(".exe"):
        name = name[:-4]
    return name


def _git_subcommand(args: Sequence[str]) -> str | None:
    for arg in args:
        if arg.startswith("-"):
            continue
        return arg.lower()
    return None


def _bounded_violation(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return "sandbox_blocked"
    return stripped[:160]


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return _sha256_text(payload)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _platform_system_default() -> str:
    import platform

    return platform.system()
