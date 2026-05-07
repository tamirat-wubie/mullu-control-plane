"""Gateway Sandbox Runner - isolated computer/code execution contract.

Purpose: Build and execute Linux rootless Docker sandbox commands for governed
    computer/code capabilities.
Governance scope: sandbox profile validation, command allowlisting,
    no-network/no-host-root/no-docker-socket guarantees, and receipt emission.
Dependencies: Python subprocess and gateway canonical hashing.
Invariants:
  - Sandbox execution is Linux-only.
  - The container network mode is always none.
  - The workspace is the only writable mount.
  - Workdirs are canonical container paths under /workspace.
  - Docker --mount source paths cannot contain option delimiters.
  - Host root and Docker socket mounts are rejected before subprocess launch.
  - Commands are argv-only and executable allowlisted.
  - Workspace mutations are witnessed as hash-only changed-file refs.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
import platform
import subprocess
from typing import Any, Callable, Mapping

from gateway.command_spine import canonical_hash


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True, slots=True)
class SandboxRunnerProfile:
    """Rootless Docker profile for one governed sandbox runner."""

    sandbox_id: str = "docker-rootless"
    image: str = "mullu-agent-runner:latest"
    user: str = "nonroot"
    network: str = "none"
    read_only_rootfs: bool = True
    workspace_mount: str = "/workspace"
    max_cpu: str = "1"
    max_memory: str = "1g"
    timeout_seconds: int = 120
    kill_process_tree: bool = True
    allowed_executables: tuple[str, ...] = (
        "python",
        "pytest",
        "npm",
        "pnpm",
        "node",
        "cargo",
        "go",
        "make",
        "git",
    )
    denied_executables: tuple[str, ...] = (
        "bash",
        "sh",
        "zsh",
        "curl",
        "wget",
        "ssh",
        "scp",
        "nc",
        "powershell",
        "pwsh",
        "docker",
    )
    forbidden_mounts: tuple[str, ...] = ("/", "/var/run/docker.sock")

    def __post_init__(self) -> None:
        _require_text(self.sandbox_id, "sandbox_id")
        _require_text(self.image, "image")
        _require_text(self.user, "user")
        if self.network != "none":
            raise ValueError("sandbox network must be none")
        if self.read_only_rootfs is not True:
            raise ValueError("sandbox root filesystem must be read-only")
        if self.workspace_mount != "/workspace":
            raise ValueError("workspace mount must be /workspace")
        _require_text(self.max_cpu, "max_cpu")
        _require_text(self.max_memory, "max_memory")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        if not isinstance(self.kill_process_tree, bool):
            raise ValueError("kill_process_tree must be a boolean")
        _validate_text_tuple(self.allowed_executables, "allowed_executables")
        _validate_text_tuple(self.denied_executables, "denied_executables")
        _validate_text_tuple(self.forbidden_mounts, "forbidden_mounts")


@dataclass(frozen=True, slots=True)
class SandboxCommandRequest:
    """One argv-only command requested for sandbox execution."""

    request_id: str
    tenant_id: str
    capability_id: str
    argv: tuple[str, ...]
    cwd: str = "/workspace"
    environment: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.capability_id, "capability_id")
        object.__setattr__(self, "argv", tuple(self.argv))
        _validate_text_tuple(self.argv, "argv")
        if not _is_workspace_container_path(self.cwd):
            raise ValueError("cwd must be inside /workspace")
        object.__setattr__(self, "environment", dict(self.environment))
        for key, value in self.environment.items():
            _validate_environment_key(str(key))
            if not isinstance(value, str):
                raise ValueError("environment values must be strings")


@dataclass(frozen=True, slots=True)
class SandboxExecutionReceipt:
    """Proof that sandbox execution used the declared isolation boundary."""

    receipt_id: str
    request_id: str
    tenant_id: str
    capability_id: str
    sandbox_id: str
    image: str
    command_hash: str
    docker_args_hash: str
    stdout_hash: str
    stderr_hash: str
    returncode: int | None
    network_disabled: bool
    read_only_rootfs: bool
    workspace_mount: str
    forbidden_effects_observed: bool
    verification_status: str
    changed_file_count: int
    changed_file_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SandboxCommandResult:
    """Sandbox command result with receipt-bound observations."""

    status: str
    stdout: str
    stderr: str
    receipt: SandboxExecutionReceipt

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "receipt": asdict(self.receipt),
        }


class DockerRootlessSandboxRunner:
    """Run governed commands through a rootless Docker no-network sandbox."""

    def __init__(
        self,
        *,
        host_workspace_root: str,
        profile: SandboxRunnerProfile | None = None,
        runner: Runner = subprocess.run,
        clock: Callable[[], str] | None = None,
        platform_system: Callable[[], str] = platform.system,
    ) -> None:
        self._host_workspace_root = Path(host_workspace_root).resolve(strict=False)
        self._profile = profile or SandboxRunnerProfile()
        self._runner = runner
        self._clock = clock or (lambda: "")
        self._platform_system = platform_system
        if not str(self._host_workspace_root):
            raise ValueError("host_workspace_root is required")
        _reject_forbidden_host_mount(str(self._host_workspace_root), self._profile)

    @property
    def profile(self) -> SandboxRunnerProfile:
        return self._profile

    def execute(self, request: SandboxCommandRequest) -> SandboxCommandResult:
        """Execute a request or return a blocked receipt before launch."""
        denial = self._admission_denial(request)
        docker_args = self._docker_args(request) if denial is None else ()
        if denial is not None:
            receipt = self._receipt(
                request=request,
                docker_args=docker_args,
                stdout="",
                stderr=denial,
                returncode=None,
                verification_status="blocked",
                forbidden_effects_observed=True,
                changed_file_refs=(),
            )
            return SandboxCommandResult(status="blocked", stdout="", stderr=denial, receipt=receipt)

        before_snapshot = _workspace_snapshot(self._host_workspace_root)
        try:
            completed = self._runner(
                list(docker_args),
                capture_output=True,
                check=False,
                shell=False,
                text=True,
                timeout=self._profile.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.output if isinstance(exc.output, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else "sandbox command timed out"
            changed_file_refs = _changed_file_refs(
                before_snapshot,
                _workspace_snapshot(self._host_workspace_root),
            )
            receipt = self._receipt(
                request=request,
                docker_args=docker_args,
                stdout=stdout,
                stderr=stderr,
                returncode=None,
                verification_status="timeout",
                forbidden_effects_observed=False,
                changed_file_refs=changed_file_refs,
            )
            return SandboxCommandResult(status="timeout", stdout=stdout, stderr=stderr, receipt=receipt)
        except OSError as exc:
            stderr = f"sandbox runner failed ({type(exc).__name__})"
            receipt = self._receipt(
                request=request,
                docker_args=docker_args,
                stdout="",
                stderr=stderr,
                returncode=None,
                verification_status="failed",
                forbidden_effects_observed=False,
                changed_file_refs=(),
            )
            return SandboxCommandResult(status="failed", stdout="", stderr=stderr, receipt=receipt)

        status = "succeeded" if completed.returncode == 0 else "failed"
        changed_file_refs = _changed_file_refs(
            before_snapshot,
            _workspace_snapshot(self._host_workspace_root),
        )
        receipt = self._receipt(
            request=request,
            docker_args=docker_args,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            returncode=completed.returncode,
            verification_status="passed" if status == "succeeded" else "failed",
            forbidden_effects_observed=False,
            changed_file_refs=changed_file_refs,
        )
        return SandboxCommandResult(
            status=status,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            receipt=receipt,
        )

    def _admission_denial(self, request: SandboxCommandRequest) -> str | None:
        if self._platform_system().lower() != "linux":
            return "sandbox runner is linux-only"
        exe = _executable_name(request.argv[0])
        if exe in self._profile.denied_executables:
            return f"denied executable: {exe}"
        if self._profile.allowed_executables and exe not in self._profile.allowed_executables:
            return f"executable not allowlisted: {exe}"
        if _contains_forbidden_mount_argument(request.argv, self._profile):
            return "forbidden mount requested"
        return None

    def _docker_args(self, request: SandboxCommandRequest) -> tuple[str, ...]:
        mount_arg = f"type=bind,src={self._host_workspace_root},dst=/workspace,rw"
        args = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--user",
            self._profile.user,
            "--read-only",
            "--cpus",
            self._profile.max_cpu,
            "--memory",
            self._profile.max_memory,
            "--mount",
            mount_arg,
            "--workdir",
            request.cwd,
        ]
        for key in sorted(request.environment):
            args.extend(["--env", f"{key}={request.environment[key]}"])
        args.append(self._profile.image)
        args.extend(request.argv)
        return tuple(args)

    def _receipt(
        self,
        *,
        request: SandboxCommandRequest,
        docker_args: tuple[str, ...],
        stdout: str,
        stderr: str,
        returncode: int | None,
        verification_status: str,
        forbidden_effects_observed: bool,
        changed_file_refs: tuple[str, ...],
    ) -> SandboxExecutionReceipt:
        command_hash = canonical_hash({
            "argv": request.argv,
            "cwd": request.cwd,
            "environment_keys": tuple(sorted(request.environment)),
        })
        docker_args_hash = canonical_hash(docker_args)
        stdout_hash = _sha256(stdout)
        stderr_hash = _sha256(stderr)
        receipt_hash = canonical_hash({
            "request_id": request.request_id,
            "command_hash": command_hash,
            "docker_args_hash": docker_args_hash,
            "stdout_hash": stdout_hash,
            "stderr_hash": stderr_hash,
            "returncode": returncode,
            "verification_status": verification_status,
            "changed_file_refs": changed_file_refs,
        })
        return SandboxExecutionReceipt(
            receipt_id=f"sandbox-receipt-{receipt_hash[:16]}",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            capability_id=request.capability_id,
            sandbox_id=self._profile.sandbox_id,
            image=self._profile.image,
            command_hash=command_hash,
            docker_args_hash=docker_args_hash,
            stdout_hash=stdout_hash,
            stderr_hash=stderr_hash,
            returncode=returncode,
            network_disabled=self._profile.network == "none",
            read_only_rootfs=self._profile.read_only_rootfs,
            workspace_mount=self._profile.workspace_mount,
            forbidden_effects_observed=forbidden_effects_observed,
            verification_status=verification_status,
            changed_file_count=len(changed_file_refs),
            changed_file_refs=changed_file_refs,
            evidence_refs=(f"sandbox_execution:{receipt_hash[:16]}",),
        )


def _contains_forbidden_mount_argument(argv: tuple[str, ...], profile: SandboxRunnerProfile) -> bool:
    lowered = tuple(item.lower() for item in argv)
    return any(forbidden.lower() in item for forbidden in profile.forbidden_mounts for item in lowered)


def _reject_forbidden_host_mount(host_workspace_root: str, profile: SandboxRunnerProfile) -> None:
    resolved_path = Path(host_workspace_root).resolve(strict=False)
    if resolved_path.parent == resolved_path:
        raise ValueError("host workspace root cannot be a forbidden mount")
    normalized = host_workspace_root.replace("\\", "/").rstrip("/") or "/"
    if _contains_mount_delimiter_or_control(normalized):
        raise ValueError("host workspace root cannot contain Docker mount delimiters")
    for forbidden in profile.forbidden_mounts:
        if normalized == forbidden.rstrip("/"):
            raise ValueError("host workspace root cannot be a forbidden mount")
        if normalized.endswith("/var/run/docker.sock"):
            raise ValueError("host workspace root cannot be the Docker socket")


def _executable_name(value: str) -> str:
    name = Path(value).name.lower()
    if name.endswith(".exe"):
        name = name[:-4]
    return name


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _is_workspace_container_path(value: str) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = PurePosixPath(value)
    if not path.is_absolute():
        return False
    if any(part in {"", ".", ".."} for part in path.parts):
        return False
    workspace = PurePosixPath("/workspace")
    return path == workspace or workspace in path.parents


def _validate_environment_key(value: str) -> None:
    _require_text(value, "environment key")
    if "=" in value or any(ord(character) < 32 for character in value):
        raise ValueError("environment key contains forbidden characters")


def _contains_mount_delimiter_or_control(value: str) -> bool:
    return "," in value or any(ord(character) < 32 for character in value)


def _validate_text_tuple(values: tuple[str, ...], field_name: str) -> None:
    if not isinstance(values, tuple) or not values:
        raise ValueError(f"{field_name} must contain at least one item")
    for value in values:
        _require_text(value, field_name)


def _workspace_snapshot(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    if not root.exists() or not root.is_dir():
        return snapshot
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.relative_to(root).parts:
            continue
        relative_path = path.relative_to(root).as_posix()
        try:
            snapshot[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            snapshot[relative_path] = "unreadable"
    return snapshot


def _changed_file_refs(before: Mapping[str, str], after: Mapping[str, str]) -> tuple[str, ...]:
    changed_paths = sorted(
        path
        for path in set(before) | set(after)
        if before.get(path) != after.get(path)
    )
    return tuple(f"workspace_diff:{_sha256(path)[:16]}" for path in changed_paths)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()
