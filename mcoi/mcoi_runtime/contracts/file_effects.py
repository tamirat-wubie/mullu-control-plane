"""Purpose: typed receipts for local file mutation evidence.
Governance scope: filesystem write/delete observation contracts only.
Dependencies: contract base helpers and Python dataclasses.
Invariants: file effect receipts expose hashes and bounded metadata, never raw file contents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
)


class FileEffectOperation(StrEnum):
    WRITE = "write"
    DELETE = "delete"


@dataclass(frozen=True, slots=True)
class FileWriteReceipt(ContractRecord):
    """Observed local file write evidence for effect reconciliation."""

    receipt_id: str
    operation: FileEffectOperation
    target_path_hash: str
    content_hash: str
    bytes_written: int
    atomic_replace: bool
    evidence_ref: str
    written_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("receipt_id", "target_path_hash", "content_hash", "evidence_ref"):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        if not isinstance(self.operation, FileEffectOperation):
            raise ValueError("operation must be a FileEffectOperation value")
        if not isinstance(self.bytes_written, int) or isinstance(self.bytes_written, bool):
            raise ValueError("bytes_written must be a non-negative integer")
        if self.bytes_written < 0:
            raise ValueError("bytes_written must be a non-negative integer")
        if not isinstance(self.atomic_replace, bool):
            raise ValueError("atomic_replace must be a boolean")
        object.__setattr__(self, "written_at", require_datetime_text(self.written_at, "written_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
