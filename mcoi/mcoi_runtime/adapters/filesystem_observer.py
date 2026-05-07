"""Purpose: provide read-only filesystem observation for the MCOI runtime.
Governance scope: execution-slice filesystem observation only.
Dependencies: pathlib, canonical evidence contracts, and observer-base typing.
Invariants: observation is read-only, non-recursive, and explicitly bounded when reading file contents.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from mcoi_runtime.contracts.evidence import EvidenceRecord
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

from .observer_base import ObservationFailure, ObservationResult, ObservationStatus


class FilesystemObservationMode(StrEnum):
    EXISTS = "exists"
    METADATA = "metadata"
    LIST_DIRECTORY = "list_directory"
    READ_TEXT = "read_text"


@dataclass(frozen=True, slots=True)
class FilesystemObservationRequest:
    path: str
    mode: FilesystemObservationMode
    max_entries: int | None = None
    max_bytes: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or not self.path.strip():
            raise RuntimeCoreInvariantError("path must be a non-empty string")
        if not isinstance(self.mode, FilesystemObservationMode):
            raise RuntimeCoreInvariantError("mode must be a FilesystemObservationMode value")
        if self.max_entries is not None and self.max_entries <= 0:
            raise RuntimeCoreInvariantError("max_entries must be greater than zero when provided")
        if self.mode is FilesystemObservationMode.READ_TEXT and (
            self.max_bytes is None or self.max_bytes <= 0
        ):
            raise RuntimeCoreInvariantError("READ_TEXT mode requires max_bytes greater than zero")
        if self.max_bytes is not None and self.max_bytes <= 0:
            raise RuntimeCoreInvariantError("max_bytes must be greater than zero when provided")


class FilesystemObserver:
    def __init__(self, *, allowed_root: Path | None = None) -> None:
        self._allowed_root = allowed_root.resolve() if allowed_root else None

    def observe(self, request: FilesystemObservationRequest) -> ObservationResult:
        target = Path(request.path)
        resolved = target.resolve()

        # Path traversal guard: reject paths outside allowed root
        if self._allowed_root is not None and not resolved.is_relative_to(self._allowed_root):
            return ObservationResult(
                status=ObservationStatus.FAILED,
                failures=(
                    ObservationFailure(
                        code="path_traversal",
                        message="target path is outside allowed root",
                        details={"path": request.path},
                    ),
                ),
            )

        if not target.exists():
            return ObservationResult(
                status=ObservationStatus.FAILED,
                failures=(
                    ObservationFailure(
                        code="path_not_found",
                        message="target path does not exist",
                        details={"path": request.path},
                    ),
                ),
            )

        resolved_uri = target.resolve().as_uri()

        if request.mode is FilesystemObservationMode.EXISTS:
            return ObservationResult(
                status=ObservationStatus.SUCCEEDED,
                evidence=(
                    EvidenceRecord(
                        description="filesystem.exists",
                        uri=resolved_uri,
                        details={
                            "exists": True,
                            "is_file": target.is_file(),
                            "is_dir": target.is_dir(),
                        },
                    ),
                ),
            )

        if request.mode is FilesystemObservationMode.METADATA:
            stat_result = target.stat()
            return ObservationResult(
                status=ObservationStatus.SUCCEEDED,
                evidence=(
                    EvidenceRecord(
                        description="filesystem.metadata",
                        uri=resolved_uri,
                        details={
                            "is_file": target.is_file(),
                            "is_dir": target.is_dir(),
                            "size_bytes": stat_result.st_size,
                            "modified_time_ns": stat_result.st_mtime_ns,
                        },
                    ),
                ),
            )

        if request.mode is FilesystemObservationMode.LIST_DIRECTORY:
            if not target.is_dir():
                return ObservationResult(
                    status=ObservationStatus.FAILED,
                    failures=(
                        ObservationFailure(
                            code="not_directory",
                            message="target path is not a directory",
                            details={"path": request.path},
                        ),
                    ),
                )
            entries = sorted(child.name for child in target.iterdir())
            if request.max_entries is not None:
                entries = entries[: request.max_entries]
            return ObservationResult(
                status=ObservationStatus.SUCCEEDED,
                evidence=(
                    EvidenceRecord(
                        description="filesystem.directory_listing",
                        uri=resolved_uri,
                        details={"entries": entries, "entry_count": len(entries)},
                    ),
                ),
            )

        if not target.is_file():
            return ObservationResult(
                status=ObservationStatus.FAILED,
                failures=(
                    ObservationFailure(
                        code="not_file",
                        message="target path is not a regular file",
                        details={"path": request.path},
                    ),
                ),
            )

        payload = target.read_bytes()[: request.max_bytes]
        return ObservationResult(
            status=ObservationStatus.SUCCEEDED,
            evidence=(
                EvidenceRecord(
                    description="filesystem.read_text",
                    uri=resolved_uri,
                    details={
                        "text": payload.decode("utf-8", errors="replace"),
                        "bytes_read": len(payload),
                    },
                ),
            ),
        )
