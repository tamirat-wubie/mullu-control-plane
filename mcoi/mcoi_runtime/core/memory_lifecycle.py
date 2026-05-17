"""Purpose: governed memory lifecycle decisions for decay, compaction, erasure, and retention.
Governance scope: memory lifecycle planning only; no physical deletion is performed.
Dependencies: runtime invariant helpers.
Invariants:
  - Consent withdrawal always produces an erasure decision.
  - Legal hold blocks erasure and hard deletion decisions.
  - Decisions are deterministic for identical memory facts and policies.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text


class MemoryLifecycleAction(StrEnum):
    RETAIN = "retain"
    DECAY = "decay"
    SUMMARIZE = "summarize"
    COMPACT = "compact"
    ERASE = "erase"


@dataclass(frozen=True, slots=True)
class MemoryLifecyclePolicy:
    policy_id: str
    decay_after_days: int
    summarize_after_days: int
    compact_after_days: int
    erase_after_days: int
    right_to_erasure_enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", ensure_non_empty_text("policy_id", self.policy_id))
        for field_name in ("decay_after_days", "summarize_after_days", "compact_after_days", "erase_after_days"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 0:
                raise RuntimeCoreInvariantError(f"{field_name} must be a non-negative integer")
        if not isinstance(self.right_to_erasure_enabled, bool):
            raise RuntimeCoreInvariantError("right_to_erasure_enabled must be a bool")


@dataclass(frozen=True, slots=True)
class MemoryLifecycleFact:
    memory_id: str
    age_days: int
    consent_active: bool
    legal_hold: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "memory_id", ensure_non_empty_text("memory_id", self.memory_id))
        if not isinstance(self.age_days, int) or self.age_days < 0:
            raise RuntimeCoreInvariantError("age_days must be a non-negative integer")
        if not isinstance(self.consent_active, bool):
            raise RuntimeCoreInvariantError("consent_active must be a bool")
        if not isinstance(self.legal_hold, bool):
            raise RuntimeCoreInvariantError("legal_hold must be a bool")


@dataclass(frozen=True, slots=True)
class MemoryLifecycleDecision:
    memory_id: str
    action: MemoryLifecycleAction
    reasons: tuple[str, ...]


def evaluate_memory_lifecycle(
    fact: MemoryLifecycleFact,
    policy: MemoryLifecyclePolicy,
) -> MemoryLifecycleDecision:
    """Return the next governed memory lifecycle action."""
    if fact.legal_hold:
        return MemoryLifecycleDecision(fact.memory_id, MemoryLifecycleAction.RETAIN, ("legal_hold",))
    if not fact.consent_active and policy.right_to_erasure_enabled:
        return MemoryLifecycleDecision(fact.memory_id, MemoryLifecycleAction.ERASE, ("consent_withdrawn",))
    if policy.erase_after_days and fact.age_days >= policy.erase_after_days:
        return MemoryLifecycleDecision(fact.memory_id, MemoryLifecycleAction.ERASE, ("retention_window_elapsed",))
    if policy.compact_after_days and fact.age_days >= policy.compact_after_days:
        return MemoryLifecycleDecision(fact.memory_id, MemoryLifecycleAction.COMPACT, ("compaction_window_reached",))
    if policy.summarize_after_days and fact.age_days >= policy.summarize_after_days:
        return MemoryLifecycleDecision(fact.memory_id, MemoryLifecycleAction.SUMMARIZE, ("summarization_window_reached",))
    if policy.decay_after_days and fact.age_days >= policy.decay_after_days:
        return MemoryLifecycleDecision(fact.memory_id, MemoryLifecycleAction.DECAY, ("decay_window_reached",))
    return MemoryLifecycleDecision(fact.memory_id, MemoryLifecycleAction.RETAIN, ("within_retention_policy",))
