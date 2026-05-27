"""Purpose: file persistence for the governed organization kernel.
Governance scope: OrganizationKernel state witnesses and restore boundaries.
Dependencies: organization kernel state, deterministic persistence serialization.
Invariants:
  - Kernel state is written as deterministic JSON.
  - Writes are atomic and never expose partial state.
  - Restore validates the state before mutating the target kernel.
  - Malformed persisted state fails closed.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from mcoi_runtime.core.organization_kernel import OrganizationKernel, OrganizationKernelState

from ._serialization import deserialize_record, serialize_record
from .errors import CorruptedDataError, PersistenceError, PersistenceWriteError


def _bounded_store_error(summary: str, exc: BaseException) -> str:
    return f"{summary} ({type(exc).__name__})"


def _atomic_write(path: Path, content: str) -> None:
    """Write content atomically via temp-file-then-rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            fd = -1
            os.replace(tmp_path, str(path))
        except BaseException:
            if fd >= 0:
                os.close(fd)
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    except OSError as exc:
        raise PersistenceWriteError(_bounded_store_error("organization kernel store write failed", exc)) from exc


class FileOrganizationKernelStore:
    """JSON-file backed persistence for OrganizationKernelState."""

    def __init__(self, path: Path) -> None:
        if not isinstance(path, Path):
            raise PersistenceError("path must be a Path instance")
        if path.exists() and not path.is_file():
            raise PersistenceError("organization kernel store path must be a file")
        self._path = path

    @property
    def path(self) -> Path:
        """Return the configured store path."""
        return self._path

    def exists(self) -> bool:
        """Return whether a persisted state witness exists."""
        return self._path.exists()

    def save_state(self, state: OrganizationKernelState) -> str:
        """Persist an exact organization kernel state witness."""
        if not isinstance(state, OrganizationKernelState):
            raise PersistenceError("state must be an OrganizationKernelState")
        content = serialize_record(state)
        _atomic_write(self._path, content)
        return content

    def load_state(self) -> OrganizationKernelState:
        """Load and validate a persisted organization kernel state witness."""
        if not self._path.exists():
            raise PersistenceError("organization kernel state file not found")
        try:
            content = self._path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CorruptedDataError(_bounded_store_error("organization kernel state file unreadable", exc)) from exc
        try:
            return deserialize_record(content, OrganizationKernelState)
        except CorruptedDataError:
            raise
        except (TypeError, ValueError) as exc:
            raise CorruptedDataError(_bounded_store_error("invalid organization kernel state", exc)) from exc

    def save_kernel(self, kernel: OrganizationKernel) -> str:
        """Persist the current snapshot from a live organization kernel."""
        if not isinstance(kernel, OrganizationKernel):
            raise PersistenceError("kernel must be an OrganizationKernel")
        return self.save_state(kernel.snapshot_state())

    def restore_kernel(self, kernel: OrganizationKernel) -> OrganizationKernelState:
        """Restore persisted state into an empty organization kernel if present."""
        if not isinstance(kernel, OrganizationKernel):
            raise PersistenceError("kernel must be an OrganizationKernel")
        if not self.exists():
            return OrganizationKernelState()
        state = self.load_state()
        kernel.restore_state(state)
        return state
