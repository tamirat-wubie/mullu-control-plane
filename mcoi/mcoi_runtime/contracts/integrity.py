"""Purpose: hash-chain integrity contracts for tamper-detection of persisted records.
Governance scope: integrity verification contracts only.
Dependencies: contracts _base (ContractRecord, validation helpers).
Invariants: all entries are immutable; chain_hash is deterministic SHA-256.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._base import (
    ContractRecord,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
)


@dataclass(frozen=True, slots=True)
class HashChainEntry(ContractRecord):
    """A single entry in a SHA-256 hash chain.

    Each entry links to its predecessor via previous_hash, forming an
    append-only tamper-evident log. The chain_hash is computed as
    SHA-256("{sequence_number}:{content_hash}:{previous_hash}").
    """

    entry_id: str
    sequence_number: int
    content_hash: str
    previous_hash: str
    chain_hash: str
    recorded_at: str

    def __post_init__(self) -> None:
        for name in ("entry_id", "content_hash", "previous_hash", "chain_hash"):
            object.__setattr__(
                self, name, require_non_empty_text(getattr(self, name), name)
            )
        object.__setattr__(
            self,
            "sequence_number",
            require_non_negative_int(self.sequence_number, "sequence_number"),
        )
        object.__setattr__(
            self,
            "recorded_at",
            require_datetime_text(self.recorded_at, "recorded_at"),
        )


@dataclass(frozen=True, slots=True)
class HashChainValidationResult(ContractRecord):
    """Result of validating a hash chain for integrity.

    When valid is False, first_broken_sequence indicates the sequence number
    where the chain diverged from expected hashes.
    """

    chain_id: str
    entries_checked: int
    valid: bool
    first_broken_sequence: int | None
    detail: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "chain_id", require_non_empty_text(self.chain_id, "chain_id")
        )
        object.__setattr__(
            self,
            "entries_checked",
            require_non_negative_int(self.entries_checked, "entries_checked"),
        )
        if not isinstance(self.valid, bool):
            raise ValueError("valid must be a boolean")
        if self.first_broken_sequence is not None:
            object.__setattr__(
                self,
                "first_broken_sequence",
                require_non_negative_int(
                    self.first_broken_sequence, "first_broken_sequence"
                ),
            )
        if not isinstance(self.detail, str):
            raise ValueError("detail must be a string")
