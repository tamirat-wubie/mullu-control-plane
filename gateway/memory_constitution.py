"""Gateway Memory Constitution - governed memory cells.

Purpose: Stores explicit memory facts with source, owner, scope, sensitivity,
    expiry, allowed use, forbidden use, confidence, and mutation history.
Governance scope: gateway-local memory admission, automatic closure memory
    admission, and scoped lookup only.
Dependencies: standard-library dataclasses, hashing, datetime parsing.
Invariants:
  - No source means weak memory.
  - No owner means unusable memory.
  - No expiry and sensitivity means unsafe memory.
  - Automatic memory writes require verified closure evidence.
  - Automatic memory writes target episodic memory only.
  - Memory lookup is scoped by tenant, owner, and allowed use.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class GovernedMemoryCell:
    """One governed memory fact."""

    memory_id: str
    tenant_id: str
    owner_id: str
    scope: str
    fact: str
    source: str
    confidence: float
    sensitivity: str
    expires_at: str
    allowed_use: tuple[str, ...]
    forbidden_use: tuple[str, ...]
    last_verified_at: str
    mutation_history: tuple[str, ...] = ()
    created_at: str = ""
    cell_hash: str = ""


@dataclass(frozen=True, slots=True)
class MemoryAdmission:
    """Admission decision for one memory cell."""

    accepted: bool
    reason: str
    memory_id: str = ""
    cell_hash: str = ""


@dataclass(frozen=True, slots=True)
class ClosureMemoryCandidate:
    """Closure-derived fact proposed for automatic episodic memory admission."""

    tenant_id: str
    owner_id: str
    fact: str
    closure_id: str
    terminal_certificate_id: str
    verification_status: str
    evidence_refs: tuple[str, ...]
    accepted_risk_id: str = ""
    sensitivity: str = "low"
    expires_at: str = "never"
    confidence: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", tuple(str(ref) for ref in self.evidence_refs))


class GovernedMemoryStore:
    """Persistence contract for governed memory cells."""

    def admit(self, cell: GovernedMemoryCell) -> MemoryAdmission:
        """Validate and persist one memory cell."""
        raise NotImplementedError

    def query(
        self,
        *,
        tenant_id: str,
        owner_id: str,
        allowed_use: str,
        scope: str = "",
    ) -> list[GovernedMemoryCell]:
        """Return usable memory cells for a scoped use."""
        raise NotImplementedError

    def count(self) -> int:
        """Return active memory cell count."""
        return 0

    def status(self) -> dict[str, Any]:
        """Return memory store health."""
        return {"backend": "unknown"}

    def admit_closure(self, candidate: ClosureMemoryCandidate) -> MemoryAdmission:
        """Validate and persist one closure-derived episodic memory cell."""
        raise NotImplementedError


class InMemoryGovernedMemoryStore(GovernedMemoryStore):
    """In-memory governed memory store for local development and tests."""

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._cells: dict[str, GovernedMemoryCell] = {}

    def admit(self, cell: GovernedMemoryCell) -> MemoryAdmission:
        decision = validate_memory_cell(cell, now=self._clock())
        if not decision.accepted:
            return decision
        created_at = cell.created_at or self._clock()
        payload = {
            "tenant_id": cell.tenant_id,
            "owner_id": cell.owner_id,
            "scope": cell.scope,
            "fact": cell.fact,
            "source": cell.source,
            "confidence": cell.confidence,
            "sensitivity": cell.sensitivity,
            "expires_at": cell.expires_at,
            "allowed_use": tuple(cell.allowed_use),
            "forbidden_use": tuple(cell.forbidden_use),
            "last_verified_at": cell.last_verified_at,
            "mutation_history": tuple(cell.mutation_history),
            "created_at": created_at,
        }
        cell_hash = _canonical_hash(payload)
        memory_id = cell.memory_id or f"mem-{cell_hash[:16]}"
        stored = GovernedMemoryCell(
            memory_id=memory_id,
            tenant_id=cell.tenant_id,
            owner_id=cell.owner_id,
            scope=cell.scope,
            fact=cell.fact,
            source=cell.source,
            confidence=cell.confidence,
            sensitivity=cell.sensitivity,
            expires_at=cell.expires_at,
            allowed_use=tuple(cell.allowed_use),
            forbidden_use=tuple(cell.forbidden_use),
            last_verified_at=cell.last_verified_at,
            mutation_history=tuple(cell.mutation_history),
            created_at=created_at,
            cell_hash=cell_hash,
        )
        self._cells[memory_id] = stored
        return MemoryAdmission(True, "admitted", memory_id=memory_id, cell_hash=cell_hash)

    def query(
        self,
        *,
        tenant_id: str,
        owner_id: str,
        allowed_use: str,
        scope: str = "",
    ) -> list[GovernedMemoryCell]:
        now = self._clock()
        cells: list[GovernedMemoryCell] = []
        for cell in self._cells.values():
            if cell.tenant_id != tenant_id or cell.owner_id != owner_id:
                continue
            if scope and cell.scope != scope:
                continue
            if allowed_use in cell.forbidden_use:
                continue
            if allowed_use not in cell.allowed_use:
                continue
            if _is_expired(cell.expires_at, now):
                continue
            cells.append(cell)
        return sorted(cells, key=lambda item: (item.scope, item.memory_id))

    def count(self) -> int:
        now = self._clock()
        return sum(1 for cell in self._cells.values() if not _is_expired(cell.expires_at, now))

    def status(self) -> dict[str, Any]:
        return {
            "backend": "memory",
            "active_cells": self.count(),
            "available": True,
        }

    def admit_closure(self, candidate: ClosureMemoryCandidate) -> MemoryAdmission:
        """Validate and persist one closure-derived episodic memory cell."""
        cell_or_denial = closure_candidate_to_memory_cell(candidate, now=self._clock())
        if isinstance(cell_or_denial, MemoryAdmission):
            return cell_or_denial
        return self.admit(cell_or_denial)


def validate_memory_cell(cell: GovernedMemoryCell, *, now: str) -> MemoryAdmission:
    """Validate constitutional memory requirements."""
    if not cell.tenant_id:
        return MemoryAdmission(False, "tenant_required")
    if not cell.owner_id:
        return MemoryAdmission(False, "owner_required")
    if not cell.source:
        return MemoryAdmission(False, "source_required")
    if not cell.scope:
        return MemoryAdmission(False, "scope_required")
    if not cell.fact:
        return MemoryAdmission(False, "fact_required")
    if cell.confidence < 0.0 or cell.confidence > 1.0:
        return MemoryAdmission(False, "confidence_out_of_range")
    if not cell.sensitivity:
        return MemoryAdmission(False, "sensitivity_required")
    if not cell.expires_at:
        return MemoryAdmission(False, "expiry_required")
    if _is_expired(cell.expires_at, now):
        return MemoryAdmission(False, "memory_expired")
    if not cell.allowed_use:
        return MemoryAdmission(False, "allowed_use_required")
    if any(use in cell.forbidden_use for use in cell.allowed_use):
        return MemoryAdmission(False, "use_conflict")
    if not cell.last_verified_at:
        return MemoryAdmission(False, "last_verified_required")
    return MemoryAdmission(True, "admissible")


def closure_candidate_to_memory_cell(
    candidate: ClosureMemoryCandidate,
    *,
    now: str,
) -> GovernedMemoryCell | MemoryAdmission:
    """Convert a verified closure candidate into an episodic memory cell."""
    if not candidate.tenant_id:
        return MemoryAdmission(False, "tenant_required")
    if not candidate.owner_id:
        return MemoryAdmission(False, "owner_required")
    if not candidate.fact:
        return MemoryAdmission(False, "fact_required")
    if not candidate.closure_id:
        return MemoryAdmission(False, "closure_id_required")
    if not candidate.terminal_certificate_id:
        return MemoryAdmission(False, "terminal_certificate_required")
    if not candidate.evidence_refs:
        return MemoryAdmission(False, "evidence_required")
    if candidate.verification_status == "passed":
        trust_marker = "verified_closure"
    elif candidate.verification_status == "accepted_risk":
        if not candidate.accepted_risk_id:
            return MemoryAdmission(False, "accepted_risk_required")
        trust_marker = "accepted_risk_closure"
    else:
        return MemoryAdmission(False, "verification_not_admissible")
    source = f"closure:{candidate.closure_id}"
    return GovernedMemoryCell(
        memory_id="",
        tenant_id=candidate.tenant_id,
        owner_id=candidate.owner_id,
        scope="episodic_closure",
        fact=candidate.fact,
        source=source,
        confidence=candidate.confidence,
        sensitivity=candidate.sensitivity,
        expires_at=candidate.expires_at,
        allowed_use=("continuity", "audit", "closure_recall"),
        forbidden_use=("semantic_generalization", "procedural_promotion", "external_sharing"),
        last_verified_at=now,
        mutation_history=(
            "created:auto_closure_memory",
            f"terminal_certificate:{candidate.terminal_certificate_id}",
            f"verification:{candidate.verification_status}",
            trust_marker,
            *tuple(f"evidence:{ref}" for ref in candidate.evidence_refs),
        ),
    )


def governed_memory_cell_from_mapping(
    raw: dict[str, Any],
    *,
    tenant_id: str,
    owner_id: str,
) -> GovernedMemoryCell:
    """Build a governed memory cell from tenant mapping metadata."""
    return GovernedMemoryCell(
        memory_id=str(raw.get("memory_id", "")),
        tenant_id=tenant_id,
        owner_id=owner_id,
        scope=str(raw.get("scope", "")),
        fact=str(raw.get("fact", "")),
        source=str(raw.get("source", "")),
        confidence=float(raw.get("confidence", 0.0)),
        sensitivity=str(raw.get("sensitivity", "")),
        expires_at=str(raw.get("expires_at", "")),
        allowed_use=tuple(str(item) for item in raw.get("allowed_use", ())),
        forbidden_use=tuple(str(item) for item in raw.get("forbidden_use", ())),
        last_verified_at=str(raw.get("last_verified_at", "")),
        mutation_history=tuple(str(item) for item in raw.get("mutation_history", ())),
        created_at=str(raw.get("created_at", "")),
    )


def _is_expired(expires_at: str, now: str) -> bool:
    if expires_at == "never":
        return False
    try:
        expires = datetime.fromisoformat(expires_at)
        current = datetime.fromisoformat(now)
    except ValueError:
        return True
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return expires <= current
