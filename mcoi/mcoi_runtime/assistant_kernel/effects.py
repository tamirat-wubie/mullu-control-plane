"""Purpose: assistant effect expectation and receipt verification.
Governance scope: observed effect receipts, forbidden-effect detection, and
    evidence references used by closure.
Dependencies: dataclasses and runtime invariant helpers.
Test contract: tests/test_assistant_kernel.py.
Invariants:
  - Planned effects and observed receipts are separate records.
  - A receipt without evidence cannot satisfy an expectation.
  - Failed or forbidden effects remain visible to closure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


EFFECT_STATUSES = ("passed", "failed", "blocked")


@dataclass(frozen=True, slots=True)
class EffectExpectation:
    """Expected observable effect for one assistant plan step."""

    expectation_id: str
    capability_id: str
    predicate_id: str
    evidence_required: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "expectation_id", ensure_non_empty_text("expectation_id", self.expectation_id))
        object.__setattr__(self, "capability_id", ensure_non_empty_text("capability_id", self.capability_id))
        object.__setattr__(self, "predicate_id", ensure_non_empty_text("predicate_id", self.predicate_id))
        object.__setattr__(
            self,
            "evidence_required",
            _normalize_text_tuple(self.evidence_required, "evidence_required"),
        )


@dataclass(frozen=True, slots=True)
class EffectReceipt:
    """Observed effect receipt from a worker, connector, or ledger."""

    receipt_id: str
    capability_id: str
    predicate_id: str
    status: str
    observed_at: str
    evidence_refs: tuple[str, ...]
    forbidden_effects_observed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", ensure_non_empty_text("receipt_id", self.receipt_id))
        object.__setattr__(self, "capability_id", ensure_non_empty_text("capability_id", self.capability_id))
        object.__setattr__(self, "predicate_id", ensure_non_empty_text("predicate_id", self.predicate_id))
        if self.status not in EFFECT_STATUSES:
            raise RuntimeCoreInvariantError("effect status is not admitted")
        object.__setattr__(self, "observed_at", ensure_non_empty_text("observed_at", self.observed_at))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))
        if not isinstance(self.forbidden_effects_observed, bool):
            raise RuntimeCoreInvariantError("forbidden_effects_observed must be boolean")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class EffectVerification:
    """Verification result over expected and observed assistant effects."""

    passed: bool
    reason: str
    missing_predicates: tuple[str, ...]
    failed_predicates: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "missing_predicates", tuple(self.missing_predicates))
        object.__setattr__(self, "failed_predicates", tuple(self.failed_predicates))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


def expectation_for_predicate(*, capability_id: str, predicate_id: str) -> EffectExpectation:
    """Create an effect expectation for one capability/predicate pair."""
    return EffectExpectation(
        expectation_id=stable_identifier(
            "assistant-effect",
            {"capability_id": capability_id, "predicate_id": predicate_id},
        ),
        capability_id=capability_id,
        predicate_id=predicate_id,
        evidence_required=(f"evidence:{predicate_id}",),
    )


def verify_effect_receipts(
    expectations: tuple[EffectExpectation, ...],
    receipts: tuple[EffectReceipt, ...],
) -> EffectVerification:
    """Verify observed effect receipts against required expectations."""
    expected = {item.predicate_id: item for item in expectations}
    observed = {item.predicate_id: item for item in receipts if item.status == "passed"}
    missing = tuple(predicate for predicate in expected if predicate not in observed)
    failed = tuple(
        receipt.predicate_id
        for receipt in receipts
        if receipt.predicate_id in expected and (receipt.status != "passed" or receipt.forbidden_effects_observed)
    )
    evidence_refs = tuple(dict.fromkeys(ref for receipt in receipts for ref in receipt.evidence_refs))
    if missing:
        return EffectVerification(False, "effect_receipt_missing", missing, failed, evidence_refs)
    if failed:
        return EffectVerification(False, "effect_receipt_failed", (), failed, evidence_refs)
    return EffectVerification(True, "effect_receipts_passed", (), (), evidence_refs)


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized:
        raise RuntimeCoreInvariantError(f"{field_name} must contain at least one item")
    return normalized
