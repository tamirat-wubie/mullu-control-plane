"""Purpose: local code workspace adapter — bounded file ops, patch apply, build/test.
Governance scope: local filesystem code operations only.
Dependencies: code contracts, invariant helpers.
Invariants:
  - All paths resolved against workspace root. Out-of-root = blocked.
  - No shell expansion. No glob. No variable substitution.
  - Malformed patches fail closed.
  - Build/test commands run with explicit timeout.
  - Subprocess environment is scrubbed: parent credentials and runtime
    modifiers do not leak. Only platform infrastructure (PATH, locale, OS
    keys) and caller-opted-in extra_env values are passed through.
  - Network egress is NOT enforced at this layer — callers requiring a
    no-network guarantee must run via a sandbox (e.g. Docker --network=none).
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Callable, Iterator
from uuid import uuid4

from mcoi_runtime.contracts.code import (
    PatchApplicationResult,
    PatchStatus,
    RepositoryDescriptor,
    SourceFile,
    WorkspaceState,
)
from mcoi_runtime.core.invariants import ensure_non_empty_text


def _is_within_root(root: Path, target: Path) -> bool:
    """Check if target path is strictly within root (no traversal).

    Uses Path.is_relative_to() to avoid string-prefix collisions
    (e.g., /tmp/workspace vs /tmp/workspace_evil).
    """
    try:
        resolved_root = root.resolve()
        resolved_target = target.resolve()
        return resolved_target.is_relative_to(resolved_root)
    except (OSError, ValueError):
        return False


_DEFAULT_MAX_OUTPUT_BYTES: int = 1_048_576  # 1 MB
_TRUNCATION_MARKER: str = "\n[TRUNCATED at {limit} bytes]"


_LOCALE_BASELINE: dict[str, str] = {
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1",
}

_PLATFORM_PASSTHROUGH_KEYS: tuple[str, ...] = (
    ("PATH", "SYSTEMROOT", "COMSPEC", "PATHEXT", "TEMP", "TMP", "WINDIR")
    if os.name == "nt"
    else ("PATH", "HOME", "TMPDIR")
)


def _scrubbed_env(extra_env: dict[str, str] | None = None) -> dict[str, str]:
    """Build a minimal environment for child processes.

    The parent process may carry credentials (AWS_*, GITHUB_TOKEN,
    ANTHROPIC_API_KEY, SSH_AUTH_SOCK) and runtime modifiers (LD_PRELOAD,
    PYTHONPATH) that must not leak into untrusted code-automation commands.
    This returns a fresh environment containing only platform infrastructure
    plus caller-opted-in keys.
    """
    env: dict[str, str] = dict(_LOCALE_BASELINE)
    parent = os.environ
    for key in _PLATFORM_PASSTHROUGH_KEYS:
        value = parent.get(key)
        if value is not None:
            env[key] = value
    if extra_env:
        for key, value in extra_env.items():
            if not isinstance(key, str) or not key:
                continue
            if "=" in key or "\x00" in key:
                continue
            if not isinstance(value, str) or "\x00" in value:
                continue
            env[key] = value
    return env


def _truncate_output(text: str | None, max_bytes: int) -> str:
    """Truncate output to max_bytes, appending a marker if truncated."""
    if text is None:
        return ""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text
    truncated = encoded[:max_bytes].decode("utf-8", errors="replace")
    return truncated + _TRUNCATION_MARKER.format(limit=max_bytes)


def _content_hash(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


def _bounded_code_error(summary: str, exc: Exception) -> str:
    """Return a stable code-adapter failure without raw backend detail."""
    return f"{summary} ({type(exc).__name__})"


_DEFAULT_MAX_FILE_BYTES: int = 10 * 1024 * 1024  # 10 MB
_STREAM_CHUNK_BYTES: int = 64 * 1024  # 64 KB


def _file_metrics(
    path: Path, *, max_file_bytes: int = _DEFAULT_MAX_FILE_BYTES,
) -> tuple[str, int, int] | None:
    """Stream-hash a file and return (hex_digest, size_bytes, line_count).

    Returns None if the file is unreadable, decodes as non-utf-8, or exceeds
    max_file_bytes. Streaming avoids loading large files into memory.
    """
    digest = sha256()
    size = 0
    lines = 0
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(_STREAM_CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_file_bytes:
                    return None
                digest.update(chunk)
                lines += chunk.count(b"\n")
    except OSError:
        return None
    return digest.hexdigest(), size, lines


@dataclass(frozen=True, slots=True)
class CommandPolicy:
    """Allowlist + denylist policy for run_command.

    Defaults are strict: only common build/test/runtime executables, no shells,
    no network tools, no git push/clone/etc, no inline-eval flags. Tests that
    monkeypatch subprocess.run can construct CommandPolicy.permissive_for_testing()
    to skip these gates.
    """

    allowed_executables: tuple[str, ...] = (
        "python", "python3", "py", "pip", "pip3", "pipx", "pytest",
        "ruff", "mypy", "black", "flake8", "isort",
        "node", "nodejs", "npm", "pnpm", "yarn", "npx",
        "cargo", "rustc", "go", "gofmt", "make", "git",
    )
    denied_executables: tuple[str, ...] = (
        "sh", "bash", "zsh", "fish", "dash", "ksh",
        "cmd", "powershell", "pwsh",
        "curl", "wget", "ssh", "scp", "rsync",
        "nc", "ncat", "telnet", "socat",
    )
    denied_git_subcommands: tuple[str, ...] = (
        "push", "pull", "fetch", "clone", "remote", "submodule", "credential",
    )
    max_timeout_seconds: int = 300
    max_output_bytes: int = 1_048_576

    @classmethod
    def permissive_for_testing(cls) -> "CommandPolicy":
        """Construct a no-allowlist, no-denylist policy. For tests only."""
        return cls(
            allowed_executables=(),
            denied_executables=(),
            denied_git_subcommands=(),
        )


_PYTHON_FAMILY: frozenset[str] = frozenset({"python", "python3", "py"})
_NODE_FAMILY: frozenset[str] = frozenset({"node", "nodejs"})
_GIT_GLOBAL_FLAGS_WITH_VALUE: frozenset[str] = frozenset(
    {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}
)


def _executable_basename(arg: str) -> str:
    """Return the executable basename normalized for comparison."""
    name = Path(arg).name.lower()
    if name.endswith(".exe"):
        name = name[:-4]
    return name


def _scan_git_subcommand(args: list[str]) -> str | None:
    """Return the first non-flag positional after 'git'. Skips global flags."""
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in _GIT_GLOBAL_FLAGS_WITH_VALUE:
            i += 2
            continue
        if (
            arg.startswith("--git-dir=")
            or arg.startswith("--work-tree=")
            or arg.startswith("--namespace=")
            or arg.startswith("--config-env=")
        ):
            i += 1
            continue
        if arg.startswith("-"):
            i += 1
            continue
        return arg
    return None


def _validate_command_policy(
    command: list[str], policy: CommandPolicy,
) -> str | None:
    """Return None if command is allowed, else a stable rejection reason."""
    if not command or not isinstance(command, list):
        return "command must be a non-empty list of non-empty strings"
    if not all(isinstance(p, str) and p for p in command):
        return "command must be a non-empty list of non-empty strings"
    if any("\x00" in p for p in command):
        return "command contains NUL byte"

    exe = _executable_basename(command[0])

    if exe in policy.denied_executables:
        return f"denied executable: {exe}"
    if policy.allowed_executables and exe not in policy.allowed_executables:
        return f"executable not allowlisted: {exe}"

    if exe == "git":
        sub = _scan_git_subcommand(command[1:])
        if sub is not None and sub.lower() in policy.denied_git_subcommands:
            return f"denied git subcommand: {sub.lower()}"

    if exe in _PYTHON_FAMILY:
        for arg in command[1:]:
            if arg in {"-c", "--command", "-e", "--eval"}:
                return f"python {arg} flag denied"
            if arg == "-m":
                return "python -m flag denied"

    if exe in _NODE_FAMILY:
        for arg in command[1:]:
            if arg in {"-r", "--require", "-p", "--print", "-e", "--eval"}:
                return f"node {arg} flag denied"

    return None


_DIFF_HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)


def _parse_diff_path(line: str) -> str:
    """Extract the file path from a '--- ' or '+++ ' diff header line."""
    rest = line[4:].rstrip("\r\n")
    rest = rest.split("\t", 1)[0].strip()
    if rest == "/dev/null":
        return "/dev/null"
    if rest.startswith("a/") or rest.startswith("b/"):
        return rest[2:]
    return rest


def _strip_eol(line: str) -> str:
    """Strip a single trailing CRLF or LF from a line."""
    if line.endswith("\r\n"):
        return line[:-2]
    if line.endswith("\n"):
        return line[:-1]
    return line


def _detect_line_ending(text: str) -> str:
    """Return the dominant line ending in text. Defaults to LF."""
    if not text:
        return "\n"
    crlf = text.count("\r\n")
    lf_only = text.count("\n") - crlf
    return "\r\n" if crlf > lf_only else "\n"


def _split_logical_lines(text: str) -> tuple[list[str], bool]:
    """Split text into logical lines (no terminators) + ends_without_newline flag."""
    if not text:
        return [], False
    raw = text.splitlines(keepends=True)
    logical = [_strip_eol(line) for line in raw]
    ends_without_newline = not (raw[-1].endswith("\n") or raw[-1].endswith("\r"))
    return logical, ends_without_newline


def _peek_diff_kind(unified_diff: str, target_file: str) -> str:
    """Determine the operation kind from diff headers without applying hunks.

    Returns one of 'create', 'delete', 'modify'.
    Raises ValueError(stable_message) if the headers are malformed or do not
    name target_file.
    """
    raw_lines = unified_diff.splitlines(keepends=True)
    minus_indexes = [i for i, l in enumerate(raw_lines) if l.startswith("--- ")]
    plus_indexes = [i for i, l in enumerate(raw_lines) if l.startswith("+++ ")]
    if len(minus_indexes) != 1:
        raise ValueError("diff must contain exactly one '---' header")
    if len(plus_indexes) != 1:
        raise ValueError("diff must contain exactly one '+++' header")
    if plus_indexes[0] != minus_indexes[0] + 1:
        raise ValueError("'+++' header must immediately follow '---' header")
    old_path = _parse_diff_path(raw_lines[minus_indexes[0]])
    new_path = _parse_diff_path(raw_lines[plus_indexes[0]])
    if old_path == "/dev/null" and new_path == target_file:
        return "create"
    if old_path == target_file and new_path == "/dev/null":
        return "delete"
    if old_path == target_file and new_path == target_file:
        return "modify"
    raise ValueError("diff path does not match requested target file")


def _apply_unified_diff_strict(
    *, original: str, unified_diff: str, target_file: str,
) -> tuple[str, str]:
    """Apply a single-file unified diff. Returns (new_content, kind).

    kind is one of 'create', 'delete', 'modify'.
    Raises ValueError(stable_message) on any malformed input.
    """
    raw_lines = unified_diff.splitlines(keepends=True)
    minus_indexes = [i for i, l in enumerate(raw_lines) if l.startswith("--- ")]
    plus_indexes = [i for i, l in enumerate(raw_lines) if l.startswith("+++ ")]

    if len(minus_indexes) != 1:
        raise ValueError("diff must contain exactly one '---' header")
    if len(plus_indexes) != 1:
        raise ValueError("diff must contain exactly one '+++' header")

    minus_idx = minus_indexes[0]
    plus_idx = plus_indexes[0]
    if plus_idx != minus_idx + 1:
        raise ValueError("'+++' header must immediately follow '---' header")

    old_path = _parse_diff_path(raw_lines[minus_idx])
    new_path = _parse_diff_path(raw_lines[plus_idx])

    if old_path == "/dev/null" and new_path == target_file:
        kind = "create"
    elif old_path == target_file and new_path == "/dev/null":
        kind = "delete"
    elif old_path == target_file and new_path == target_file:
        kind = "modify"
    else:
        raise ValueError("diff path does not match requested target file")

    hunk_indexes = [
        i for i, l in enumerate(raw_lines)
        if l.startswith("@@") and i > plus_idx
    ]
    if not hunk_indexes:
        raise ValueError("missing diff hunk")

    if kind == "create":
        original_logical: list[str] = []
        original_no_newline = False
        target_ending = "\n"
    else:
        original_logical, original_no_newline = _split_logical_lines(original)
        target_ending = _detect_line_ending(original)

    result_logical: list[str] = []
    cursor = 0
    new_no_newline = False

    for hunk_pos, hunk_idx in enumerate(hunk_indexes):
        next_hunk = (
            hunk_indexes[hunk_pos + 1]
            if hunk_pos + 1 < len(hunk_indexes)
            else len(raw_lines)
        )

        header = _strip_eol(raw_lines[hunk_idx])
        match = _DIFF_HUNK_HEADER_RE.match(header)
        if match is None:
            raise ValueError("malformed hunk header")

        old_start = int(match.group("old_start"))
        old_count = 1 if match.group("old_count") is None else int(match.group("old_count"))
        new_count = 1 if match.group("new_count") is None else int(match.group("new_count"))

        if old_count == 0 and old_start == 0:
            expected_cursor = 0
        else:
            expected_cursor = max(old_start - 1, 0)

        if expected_cursor < cursor:
            raise ValueError("overlapping or out-of-order hunk")
        if expected_cursor > len(original_logical):
            raise ValueError("hunk starts beyond end of file")

        result_logical.extend(original_logical[cursor:expected_cursor])
        cursor = expected_cursor

        old_seen = 0
        new_seen = 0
        last_emit = "none"  # one of {'none', 'context', 'minus', 'plus'}

        for raw_line in raw_lines[hunk_idx + 1:next_hunk]:
            stripped = _strip_eol(raw_line)

            if stripped == "":
                # An empty diff line is sometimes produced by tools to mean a
                # blank context line. Treat strictly as ' ' context line of "".
                if cursor >= len(original_logical) or original_logical[cursor] != "":
                    raise ValueError("context line mismatch")
                result_logical.append("")
                cursor += 1
                old_seen += 1
                new_seen += 1
                last_emit = "context"
                continue

            prefix = stripped[0]
            body = stripped[1:]

            if prefix == "\\":
                if not stripped.startswith("\\ No newline at end of file"):
                    raise ValueError("invalid backslash diff line")
                if last_emit in ("plus", "context"):
                    new_no_newline = True
                # If last_emit == 'minus', the marker refers to the original
                # side which is fine (we just don't add a trailing newline if
                # this was the file's last logical state).
                continue

            if prefix == " ":
                if cursor >= len(original_logical) or original_logical[cursor] != body:
                    raise ValueError("context line mismatch")
                result_logical.append(body)
                cursor += 1
                old_seen += 1
                new_seen += 1
                last_emit = "context"
            elif prefix == "-":
                if cursor >= len(original_logical) or original_logical[cursor] != body:
                    raise ValueError("removed line mismatch")
                cursor += 1
                old_seen += 1
                last_emit = "minus"
            elif prefix == "+":
                result_logical.append(body)
                new_seen += 1
                last_emit = "plus"
            else:
                raise ValueError("invalid diff line prefix")

        if old_seen != old_count:
            raise ValueError("old hunk length mismatch")
        if new_seen != new_count:
            raise ValueError("new hunk length mismatch")

    result_logical.extend(original_logical[cursor:])

    if kind == "delete":
        if result_logical:
            raise ValueError("delete patch produced non-empty content")
        return "", kind

    if not result_logical:
        new_content = ""
    else:
        new_content = target_ending.join(result_logical)
        # Carry forward the original "no newline at end" state unless the diff
        # explicitly added a trailing newline. For modify, the new_no_newline
        # flag governs the new side; for create, default to terminating newline
        # unless explicitly suppressed.
        suppress_final = (
            new_no_newline
            if kind == "modify"
            else new_no_newline or (kind == "modify" and original_no_newline)
        )
        if not suppress_final:
            new_content += target_ending

    if kind == "modify" and new_content == original:
        raise ValueError("patch had no effect")

    return new_content, kind


def _atomic_write_text(path: Path, content: str) -> None:
    """Write text atomically; preserve mode, sync data, sync parent dir on POSIX."""
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)

    try:
        existing_mode: int | None = path.stat().st_mode & 0o7777
    except OSError:
        existing_mode = None

    fd, tmp = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=f".{uuid4().hex}.tmp",
        dir=str(parent),
    )
    tmp_path = Path(tmp)
    written = False
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        os.replace(tmp_path, path)
        written = True
        if existing_mode is not None:
            try:
                os.chmod(path, existing_mode)
            except OSError:
                pass
        if hasattr(os, "O_DIRECTORY"):
            try:
                dir_fd = os.open(str(parent), os.O_DIRECTORY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass
    finally:
        if not written:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _iter_workspace_files(root: Path):
    """Yield each regular file under root that resolves inside root.

    Defends against symlinks pointing outside the workspace: an entry is
    skipped unless its resolved real path is strictly within the resolved
    workspace root. Broken symlinks (resolve(strict=True) raises) are also
    skipped. Yielded paths are the original tree positions, so callers can
    still call .relative_to(root) on them.
    """
    try:
        resolved_root = root.resolve(strict=True)
    except (OSError, ValueError):
        return
    for path in sorted(root.rglob("*")):
        try:
            resolved = path.resolve(strict=True)
        except (OSError, ValueError):
            continue
        try:
            if not resolved.is_relative_to(resolved_root):
                continue
        except (OSError, ValueError):
            continue
        if not resolved.is_file():
            continue
        yield path


class LocalCodeAdapter:
    """Bounded local code workspace adapter.

    All file operations are restricted to paths inside the workspace root.
    Build/test commands run via subprocess with timeout (no shell expansion).
    """

    def __init__(
        self,
        *,
        root_path: str,
        clock: Callable[[], str],
        command_policy: CommandPolicy | None = None,
        max_file_bytes: int = _DEFAULT_MAX_FILE_BYTES,
    ) -> None:
        ensure_non_empty_text("root_path", root_path)
        self._root = Path(root_path).resolve()
        self._clock = clock
        self._command_policy = command_policy or CommandPolicy()
        if not isinstance(max_file_bytes, int) or max_file_bytes <= 0:
            raise ValueError("max_file_bytes must be a positive integer")
        self._max_file_bytes = max_file_bytes
        if not self._root.is_dir():
            raise ValueError("workspace root is not a directory")

    @property
    def command_policy(self) -> CommandPolicy:
        return self._command_policy

    @property
    def max_file_bytes(self) -> int:
        return self._max_file_bytes

    @property
    def root(self) -> Path:
        return self._root

    def inspect_repository(self, repo_id: str, name: str) -> RepositoryDescriptor:
        """Create a repository descriptor from the workspace."""
        ensure_non_empty_text("repo_id", repo_id)
        # Detect language hints from file extensions
        extensions: set[str] = set()
        for f in _iter_workspace_files(self._root):
            if f.suffix:
                extensions.add(f.suffix.lstrip("."))
        hints = sorted(extensions)[:10]  # Cap at 10

        return RepositoryDescriptor(
            repo_id=repo_id,
            name=name,
            root_path=str(self._root),
            language_hints=tuple(hints),
        )

    def list_files(self, repo_id: str, extensions: tuple[str, ...] = ()) -> WorkspaceState:
        """List files in the workspace, optionally filtered by extension."""
        files: list[SourceFile] = []
        total_bytes = 0

        for path in _iter_workspace_files(self._root):
            if extensions and path.suffix.lstrip(".") not in extensions:
                continue

            metrics = _file_metrics(path, max_file_bytes=self._max_file_bytes)
            if metrics is None:
                continue  # unreadable, oversize, or stream error

            content_hash, size, line_breaks = metrics
            line_count = line_breaks + (1 if size > 0 else 0)

            rel = str(path.relative_to(self._root))
            total_bytes += size
            files.append(SourceFile(
                file_path=str(path),
                relative_path=rel,
                content_hash=content_hash,
                size_bytes=size,
                line_count=line_count,
            ))

        return WorkspaceState(
            repo_id=repo_id,
            root_path=str(self._root),
            files=tuple(files),
            total_files=len(files),
            total_bytes=total_bytes,
            captured_at=self._clock(),
        )

    def read_file(self, relative_path: str) -> str | None:
        """Read a file from the workspace. Returns None if not found or outside root."""
        target = self._root / relative_path
        if not _is_within_root(self._root, target):
            return None
        if not target.is_file():
            return None
        try:
            return target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    def write_file(self, relative_path: str, content: str) -> bool:
        """Write a file to the workspace. Returns False if path is outside root."""
        target = self._root / relative_path
        if not _is_within_root(self._root, target):
            return False
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return True
        except OSError:
            return False

    def apply_patch(
        self, patch_id: str, target_file: str, unified_diff: str,
    ) -> PatchApplicationResult:
        """Apply a strict unified-diff patch. Fail closed on any inconsistency.

        Supports modify (in-place), create (--- /dev/null), and delete
        (+++ /dev/null). Multi-file diffs are rejected. Context and removed
        lines must match the original byte-for-byte (modulo line-ending
        normalization). The output preserves the file's line ending convention
        and respects '\\ No newline at end of file' markers. Atomic write with
        mode preservation and parent-dir fsync (POSIX).
        """
        ensure_non_empty_text("patch_id", patch_id)
        target = self._root / target_file

        if not _is_within_root(self._root, target):
            return PatchApplicationResult(
                patch_id=patch_id, status=PatchStatus.BLOCKED,
                target_file=target_file, error_message="path outside workspace root",
            )

        target_exists = False
        try:
            target_exists = target.is_file()
        except OSError:
            target_exists = False

        try:
            peek_kind = _peek_diff_kind(unified_diff, target_file)
        except ValueError as exc:
            return PatchApplicationResult(
                patch_id=patch_id, status=PatchStatus.MALFORMED,
                target_file=target_file,
                error_message=_bounded_code_error("patch error", exc),
            )

        if peek_kind == "modify" and not target_exists:
            return PatchApplicationResult(
                patch_id=patch_id, status=PatchStatus.FAILED,
                target_file=target_file, error_message="target file not found",
            )
        if peek_kind == "delete" and not target_exists:
            return PatchApplicationResult(
                patch_id=patch_id, status=PatchStatus.FAILED,
                target_file=target_file, error_message="target file not found",
            )
        if peek_kind == "create" and target_exists:
            return PatchApplicationResult(
                patch_id=patch_id, status=PatchStatus.MALFORMED,
                target_file=target_file,
                error_message="create patch but target exists",
            )

        try:
            original = (
                target.read_bytes().decode("utf-8") if target_exists else ""
            )
        except (OSError, UnicodeDecodeError) as exc:
            return PatchApplicationResult(
                patch_id=patch_id, status=PatchStatus.FAILED,
                target_file=target_file,
                error_message=_bounded_code_error("patch error", exc),
            )

        try:
            new_content, kind = _apply_unified_diff_strict(
                original=original,
                unified_diff=unified_diff,
                target_file=target_file,
            )
        except ValueError as exc:
            return PatchApplicationResult(
                patch_id=patch_id, status=PatchStatus.MALFORMED,
                target_file=target_file,
                error_message=_bounded_code_error("patch error", exc),
            )

        try:
            if kind == "delete":
                target.unlink()
            else:
                _atomic_write_text(target, new_content)
        except (OSError, IndexError) as exc:
            return PatchApplicationResult(
                patch_id=patch_id, status=PatchStatus.MALFORMED,
                target_file=target_file,
                error_message=_bounded_code_error("patch error", exc),
            )

        return PatchApplicationResult(
            patch_id=patch_id, status=PatchStatus.APPLIED, target_file=target_file,
        )

    def run_command(
        self,
        command_id: str,
        command: list[str],
        *,
        timeout_seconds: int = 60,
        max_output_bytes: int = _DEFAULT_MAX_OUTPUT_BYTES,
        extra_env: dict[str, str] | None = None,
    ) -> tuple[int, str, str, int]:
        """Run a command in the workspace root. Returns (exit_code, stdout, stderr, duration_ms).

        The command is validated against the adapter's CommandPolicy before
        execution. Subprocess environment is scrubbed (no parent credentials).
        Timeout and output budget are clamped to the policy maxima.
        """
        ensure_non_empty_text("command_id", command_id)

        policy_error = _validate_command_policy(command, self._command_policy)
        if policy_error is not None:
            return -1, "", f"blocked command: {policy_error}", 0

        timeout_seconds = max(1, min(timeout_seconds, self._command_policy.max_timeout_seconds))
        max_output_bytes = max(1, min(max_output_bytes, self._command_policy.max_output_bytes))

        start = time.monotonic()
        try:
            result = subprocess.run(
                command,
                cwd=str(self._root),
                env=_scrubbed_env(extra_env),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=False,  # Explicit: no shell expansion
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            stdout = _truncate_output(result.stdout, max_output_bytes)
            stderr = _truncate_output(result.stderr, max_output_bytes)
            return result.returncode, stdout, stderr, duration_ms
        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - start) * 1000)
            return -1, "", "timeout", duration_ms
        except OSError as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            return -1, "", _bounded_code_error("command error", exc), duration_ms
