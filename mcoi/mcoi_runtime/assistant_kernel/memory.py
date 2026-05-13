"""Purpose: assistant memory admission contracts.
Governance scope: verified fact admission, owner/tenant scope, source evidence,
    and memory-class policy checks.
Dependencies: dataclasses and runtime invariant helpers.
Test contract: tests/test_assistant_kernel.py.
Invariants:
  - Memory admission does not infer facts from unstable state.
  - Every admitted fact has tenant, owner, source evidence, and verification.
  - Forbidden memory classes fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


ADMITTED_MEMORY_CLASSES = (
    "preference_memory",
    "project_memory",
    "commitment_memory",
    "episodic_closure_memory",
    "team_memory",
    "finance_case_memory",
)
VERIFICATION_STATUSES = ("verified", "accepted_risk")


@dataclass(frozen=True, slots=True)
class AssistantMemoryCandidate:
    """Fact proposed for assistant memory admission."""

    tenant_id: str
    owner_id: str
    memory_class: str
    fact: str
    source: str
    verification_status: str
    evidence_refs: tuple[str, ...]
    sensitivity: str = "low"
    expires_at: str = "never"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", ensure_non_empty_text("tenant_id", self.tenant_id))
        object.__setattr__(self, "owner_id", ensure_non_empty_text("owner_id", self.owner_id))
        if self.memory_class not in ADMITTED_MEMORY_CLASSES:
            raise RuntimeCoreInvariantError("memory_class is not admitted")
        object.__setattr__(self, "fact", ensure_non_empty_text("fact", self.fact))
        object.__setattr__(self, "source", ensure_non_empty_text("source", self.source))
        if self.verification_status not in VERIFICATION_STATUSES:
            raise RuntimeCoreInvariantError("verification_status is not admissible")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "sensitivity", ensure_non_empty_text("sensitivity", self.sensitivity))
        object.__setattr__(self, "expires_at", ensure_non_empty_text("expires_at", self.expires_at))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class AssistantMemoryAdmission:
    """Decision for a proposed assistant memory fact."""

    accepted: bool
    reason: str
    memory_id: str = ""
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


def admit_memory_candidate(candidate: AssistantMemoryCandidate) -> AssistantMemoryAdmission:
    """Admit a verified assistant memory candidate."""
    memory_id = stable_identifier(
        "assistant-memory",
        {
            "tenant_id": candidate.tenant_id,
            "owner_id": candidate.owner_id,
            "memory_class": candidate.memory_class,
            "fact": candidate.fact,
            "source": candidate.source,
        },
    )
    return AssistantMemoryAdmission(
        accepted=True,
        reason="memory_candidate_admitted",
        memory_id=memory_id,
        evidence_refs=candidate.evidence_refs,
    )


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized:
        raise RuntimeCoreInvariantError(f"{field_name} must contain at least one item")
    return normalized
