"""Audit Chain Anchoring — external tamper detection for governance proofs.

Purpose: compute periodic checkpoint roots from the audit hash chain and
    store them in an external anchor store. Any local chain rewrite after
    anchoring becomes detectable.
Governance scope: anchoring and verification only — never modifies audit entries.
Dependencies: audit trail (read), clock injection.
Invariants:
  - Anchors are append-only in the external store.
  - Local chain rewrite after anchor causes verification failure.
  - Anchor computation is deterministic.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Callable


@dataclass
class AuditAnchor:
    """A checkpoint anchor for a range of audit entries."""

    anchor_id: str
    from_sequence: int
    to_sequence: int
    entry_count: int
    merkle_root: str
    anchored_at: str
    verified: bool = True


class AuditAnchorStore:
    """Manages external audit chain anchors for tamper detection.

    Workflow:
    1. create_anchor() — compute Merkle root from audit trail range
    2. verify_anchor() — compare local chain against stored anchor
    3. list_anchors() — show anchoring history

    The anchor store itself should be backed by an append-only external
    system (DB, S3 object-lock, signed witness) for production use.
    This implementation provides the in-memory interface that any
    external backend can wrap.
    """

    _MAX_ANCHORS = 10_000

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._anchors: list[AuditAnchor] = []
        self._anchor_counter = 0
        self._lock = threading.Lock()

    def create_anchor(self, audit_entries: list[Any]) -> AuditAnchor:
        """Compute a Merkle root anchor from a list of audit entries."""
        if not audit_entries:
            raise ValueError("cannot anchor empty entry list")

        # Extract hashes
        hashes = []
        sequences = []
        for entry in audit_entries:
            h = getattr(entry, "entry_hash", "")
            seq = getattr(entry, "sequence", 0)
            if h:
                hashes.append(h)
                sequences.append(seq)

        if not hashes:
            raise ValueError("no hashable entries found")

        # Compute Merkle root
        merkle_root = self._compute_merkle_root(hashes)

        with self._lock:
            self._anchor_counter += 1
            anchor = AuditAnchor(
                anchor_id=f"anchor-{self._anchor_counter:06d}",
                from_sequence=min(sequences) if sequences else 0,
                to_sequence=max(sequences) if sequences else 0,
                entry_count=len(hashes),
                merkle_root=merkle_root,
                anchored_at=self._clock(),
            )
            self._anchors.append(anchor)
            if len(self._anchors) > self._MAX_ANCHORS:
                self._anchors = self._anchors[-self._MAX_ANCHORS:]

        return anchor

    def verify_anchor(self, anchor_id: str, audit_entries: list[Any]) -> dict[str, Any]:
        """Verify that current audit entries match a stored anchor."""
        with self._lock:
            anchor = next((a for a in self._anchors if a.anchor_id == anchor_id), None)
        if anchor is None:
            return {"valid": False, "reason": f"anchor not found: {anchor_id}"}

        hashes = [getattr(e, "entry_hash", "") for e in audit_entries if getattr(e, "entry_hash", "")]
        if len(hashes) != anchor.entry_count:
            return {
                "valid": False,
                "reason": f"entry count mismatch: expected {anchor.entry_count}, got {len(hashes)}",
                "anchor_id": anchor_id,
            }

        current_root = self._compute_merkle_root(hashes)
        if current_root != anchor.merkle_root:
            return {
                "valid": False,
                "reason": "merkle root mismatch — chain may have been tampered",
                "anchor_id": anchor_id,
                "expected": anchor.merkle_root[:16],
                "actual": current_root[:16],
            }

        return {
            "valid": True,
            "anchor_id": anchor_id,
            "entry_count": anchor.entry_count,
            "anchored_at": anchor.anchored_at,
        }

    def list_anchors(self, limit: int = 50) -> list[AuditAnchor]:
        with self._lock:
            return list(reversed(self._anchors[-limit:]))

    def _compute_merkle_root(self, hashes: list[str]) -> str:
        """Compute a binary Merkle tree root from a list of hashes."""
        if not hashes:
            return sha256(b"empty").hexdigest()
        if len(hashes) == 1:
            return hashes[0]

        # Build tree bottom-up
        level = [sha256(h.encode()).digest() for h in hashes]
        while len(level) > 1:
            next_level = []
            for i in range(0, len(level), 2):
                left = level[i]
                right = level[i + 1] if i + 1 < len(level) else left
                next_level.append(sha256(left + right).digest())
            level = next_level

        return level[0].hex()

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_anchors": len(self._anchors),
                "latest_anchor": self._anchors[-1].anchor_id if self._anchors else None,
            }
