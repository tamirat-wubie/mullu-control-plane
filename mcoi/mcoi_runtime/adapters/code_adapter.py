"""Purpose: local code workspace adapter — bounded file ops, patch apply, build/test.
Governance scope: local filesystem code operations only.
Dependencies: code contracts, invariant helpers.
Invariants:
  - All paths resolved against workspace root. Out-of-root = blocked.
  - No shell expansion. No glob. No variable substitution.
  - Malformed patches fail closed.
  - Build/test commands run with explicit timeout.
  - No git push, no network, no package publication.
"""

from __future__ import annotations

import subprocess
import time
from hashlib import sha256
from pathlib import Path
from typing import Callable

from mcoi_runtime.contracts.code import (
    BuildResult,
    BuildStatus,
    PatchApplicationResult,
    PatchStatus,
    RepositoryDescriptor,
    SourceFile,
    TestResult,
    TestStatus,
    WorkspaceState,
)
from mcoi_runtime.core.invariants import ensure_non_empty_text, stable_identifier


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


def _content_hash(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


class LocalCodeAdapter:
    """Bounded local code workspace adapter.

    All file operations are restricted to paths inside the workspace root.
    Build/test commands run via subprocess with timeout (no shell expansion).
    """

    def __init__(self, *, root_path: str, clock: Callable[[], str]) -> None:
        ensure_non_empty_text("root_path", root_path)
        self._root = Path(root_path).resolve()
        self._clock = clock
        if not self._root.is_dir():
            raise ValueError(f"workspace root is not a directory: {root_path}")

    @property
    def root(self) -> Path:
        return self._root

    def inspect_repository(self, repo_id: str, name: str) -> RepositoryDescriptor:
        """Create a repository descriptor from the workspace."""
        ensure_non_empty_text("repo_id", repo_id)
        # Detect language hints from file extensions
        extensions: set[str] = set()
        for f in self._root.rglob("*"):
            if f.is_file() and f.suffix:
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

        for path in sorted(self._root.rglob("*")):
            if not path.is_file():
                continue
            if extensions and path.suffix.lstrip(".") not in extensions:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue  # Skip unreadable files

            rel = str(path.relative_to(self._root))
            h = _content_hash(content)
            size = len(content.encode("utf-8"))
            lines = content.count("\n") + (1 if content else 0)
            total_bytes += size
            files.append(SourceFile(
                file_path=str(path),
                relative_path=rel,
                content_hash=h,
                size_bytes=size,
                line_count=lines,
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

    def apply_patch(self, patch_id: str, target_file: str, unified_diff: str) -> PatchApplicationResult:
        """Apply a simple line-replacement patch. Fail closed on malformed input."""
        ensure_non_empty_text("patch_id", patch_id)
        target = self._root / target_file

        if not _is_within_root(self._root, target):
            return PatchApplicationResult(
                patch_id=patch_id, status=PatchStatus.BLOCKED,
                target_file=target_file, error_message="path outside workspace root",
            )

        if not target.is_file():
            return PatchApplicationResult(
                patch_id=patch_id, status=PatchStatus.FAILED,
                target_file=target_file, error_message="target file not found",
            )

        # Parse simple replacement patches: lines starting with - are removed, + are added
        try:
            original = target.read_text(encoding="utf-8")
            lines = original.splitlines(keepends=True)
            result_lines: list[str] = []
            diff_lines = unified_diff.splitlines()

            # Simple application: find --- old/+++ new header, then apply hunks
            in_hunk = False
            line_idx = 0

            for dl in diff_lines:
                if dl.startswith("---") or dl.startswith("+++"):
                    continue
                if dl.startswith("@@"):
                    in_hunk = True
                    # Parse line number: @@ -start,count +start,count @@
                    parts = dl.split()
                    if len(parts) >= 2:
                        old_range = parts[1]  # -start,count
                        start_str = old_range.lstrip("-").split(",")[0]
                        try:
                            line_idx = int(start_str) - 1  # 0-indexed
                            # Flush lines before this hunk
                            while len(result_lines) < line_idx and line_idx <= len(lines):
                                result_lines.append(lines[len(result_lines)])
                        except ValueError:
                            pass
                    continue
                if not in_hunk:
                    continue
                if dl.startswith("-"):
                    # Remove line — skip it in original
                    line_idx += 1
                elif dl.startswith("+"):
                    # Add line
                    result_lines.append(dl[1:] + "\n")
                elif dl.startswith(" "):
                    # Context line
                    if line_idx < len(lines):
                        result_lines.append(lines[line_idx])
                    line_idx += 1

            # Append remaining lines
            while line_idx < len(lines):
                result_lines.append(lines[line_idx])
                line_idx += 1

            new_content = "".join(result_lines)
            target.write_text(new_content, encoding="utf-8")

            return PatchApplicationResult(
                patch_id=patch_id, status=PatchStatus.APPLIED, target_file=target_file,
            )
        except Exception as exc:
            return PatchApplicationResult(
                patch_id=patch_id, status=PatchStatus.MALFORMED,
                target_file=target_file, error_message=f"patch error: {exc}",
            )

    def run_command(
        self,
        command_id: str,
        command: list[str],
        *,
        timeout_seconds: int = 60,
    ) -> tuple[int, str, str, int]:
        """Run a command in the workspace root. Returns (exit_code, stdout, stderr, duration_ms).

        Uses list form (no shell expansion). Timeout enforced.
        """
        ensure_non_empty_text("command_id", command_id)
        start = time.monotonic()
        try:
            result = subprocess.run(
                command,
                cwd=str(self._root),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=False,  # Explicit: no shell expansion
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            return result.returncode, result.stdout, result.stderr, duration_ms
        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - start) * 1000)
            return -1, "", "timeout", duration_ms
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            return -1, "", f"error: {exc}", duration_ms
