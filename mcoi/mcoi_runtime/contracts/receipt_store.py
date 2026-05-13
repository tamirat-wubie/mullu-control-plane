"""ReceiptStore — pluggable backend for ProofBridge causal-lineage state.

Closes the architectural-shape half of the "Receipts not persisted" gap
documented in `docs/MAF_RECEIPT_COVERAGE.md`. Defines the seam at which a
durable backend (PostgreSQL, ledger-hashed, append table, etc.) can plug
in without touching ProofBridge's core logic.

Mirrors the `AuditStore` optional-backend pattern in
`mcoi/mcoi_runtime/governance/audit/trail.py`:

    base class with no-op / minimal defaults
    InMemory*Store provides the default working implementation
    durable subclasses override only the methods they care about

The base class is NOT abstract on purpose — a downstream caller that
wants to disable lineage entirely can pass a bare `ReceiptStore()` and
get safe no-op semantics. This matches AuditStore's design rationale
("degraded gracefully — the in-process anchor still works for single-
process integrity").

What this module does NOT decide:
  * Schema for durable storage. A future PostgresReceiptStore picks
    its own table layout; this module only specifies the operations
    every backend must support.
  * Whether the store also persists individual receipts (currently
    only the lineage chain is durable here; receipts are content-
    addressed by their hash and re-derivable from the chain plus the
    in-flight context that produced them).
  * Hash-chain integrity. That belongs to LEDGER_SPEC.md and the
    audit ledger; receipt-chain integrity is a separate spec.

Migration note (read carefully if writing a durable subclass):
  ProofBridge previously held lineages in `_lineage: dict[str, CausalLineage]`
  with simple FIFO-by-insertion-order eviction. Subclasses targeting durable
  storage should preserve that eviction discipline OR document explicitly
  that they don't (because then the bridge's MAX_LINEAGE_ENTRIES bound is
  no longer load-bearing for that backend).
"""

from __future__ import annotations

from mcoi_runtime.contracts.proof import CausalLineage


def _require_entity_id(entity_id: object) -> str:
    if not isinstance(entity_id, str) or not entity_id.strip():
        raise ValueError("entity_id must be a non-empty string")
    return entity_id


def _require_lineage(lineage: object) -> CausalLineage:
    if not isinstance(lineage, CausalLineage):
        raise ValueError("lineage must be a CausalLineage instance")
    return lineage


def _require_positive_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if value < 1:
        raise ValueError(f"{field_name} must be >= 1")
    return value


class ReceiptStore:
    """Base class for causal-lineage storage backends. Defaults are
    no-ops; subclasses override only the operations they support.

    A bare `ReceiptStore()` instance produces a bridge that emits
    receipts but persists no lineage — useful for tests or surfaces
    where lineage tracking is intentionally disabled.

    For the default in-memory behavior matching pre-Protocol
    ProofBridge, use `InMemoryReceiptStore`.
    """

    def get_lineage(self, entity_id: str) -> CausalLineage | None:
        """Return the lineage for an entity, or None if absent."""
        _require_entity_id(entity_id)
        return None

    def record_lineage(self, entity_id: str, lineage: CausalLineage) -> None:
        """Persist (or replace) the lineage for an entity."""
        _require_entity_id(entity_id)
        _require_lineage(lineage)
        return None

    def evict_oldest(self) -> None:
        """Remove the oldest entity's lineage to free capacity.

        Called by ProofBridge before recording a new lineage when
        `len(self) >= max_entries`. The default no-op is safe — backends
        that don't bound capacity simply ignore the request.
        """
        return None

    def has_lineage(self, entity_id: str) -> bool:
        """Whether a lineage currently exists for an entity."""
        _require_entity_id(entity_id)
        return False

    def __len__(self) -> int:
        """Number of lineages tracked."""
        return 0

    @property
    def max_entries(self) -> int:
        """Capacity bound. ProofBridge calls evict_oldest() when len(self)
        reaches this. A backend that doesn't bound capacity should return
        a number large enough that the bridge never triggers eviction."""
        return 10_000


class InMemoryReceiptStore(ReceiptStore):
    """Default in-memory implementation. Bounded by max_entries with
    FIFO eviction matching pre-Protocol ProofBridge behavior.

    Insertion order is preserved by Python dict semantics (3.7+
    guarantee), so `next(iter(self._lineage))` returns the oldest
    inserted entity_id — same eviction discipline as the dict ProofBridge
    held directly before this refactor.
    """

    DEFAULT_MAX_ENTRIES = 10_000

    def __init__(self, *, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        self._max_entries = _require_positive_int(max_entries, "max_entries")
        self._lineage: dict[str, CausalLineage] = {}

    def get_lineage(self, entity_id: str) -> CausalLineage | None:
        entity_id = _require_entity_id(entity_id)
        return self._lineage.get(entity_id)

    def record_lineage(self, entity_id: str, lineage: CausalLineage) -> None:
        entity_id = _require_entity_id(entity_id)
        lineage = _require_lineage(lineage)
        if lineage.entity_id != entity_id:
            raise ValueError("lineage entity_id must match entity_id")
        self._lineage[entity_id] = lineage

    def evict_oldest(self) -> None:
        if not self._lineage:
            return
        oldest_key = next(iter(self._lineage))
        del self._lineage[oldest_key]

    def has_lineage(self, entity_id: str) -> bool:
        entity_id = _require_entity_id(entity_id)
        return entity_id in self._lineage

    def __len__(self) -> int:
        return len(self._lineage)

    @property
    def max_entries(self) -> int:
        return self._max_entries
