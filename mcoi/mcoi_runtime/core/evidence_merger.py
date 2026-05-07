"""Purpose: merge evidence into typed state with explicit provenance.
Governance scope: runtime-core state preparation only.
Dependencies: runtime-core invariant helpers.
Invariants: observed, inferred, predicted, and committed state remain distinct and committed state is never silently overwritten.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from .invariants import RuntimeCoreInvariantError, copied, ensure_non_empty_text, freeze_mapping


class EvidenceStateCategory(StrEnum):
    OBSERVED = "observed"
    INFERRED = "inferred"
    PREDICTED = "predicted"
    COMMITTED = "committed"


@dataclass(frozen=True, slots=True)
class StateAtom:
    state_key: str
    value: Any
    provenance_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_key", ensure_non_empty_text("state_key", self.state_key))
        if not self.provenance_ids:
            raise RuntimeCoreInvariantError("provenance_ids must contain at least one evidence id")
        for evidence_id in self.provenance_ids:
            ensure_non_empty_text("evidence_id", evidence_id)
        object.__setattr__(self, "value", copied(self.value))


@dataclass(frozen=True, slots=True)
class EvidenceState:
    observed: Mapping[str, StateAtom] = field(default_factory=dict)
    inferred: Mapping[str, StateAtom] = field(default_factory=dict)
    predicted: Mapping[str, StateAtom] = field(default_factory=dict)
    committed: Mapping[str, StateAtom] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed", freeze_mapping(dict(self.observed)))
        object.__setattr__(self, "inferred", freeze_mapping(dict(self.inferred)))
        object.__setattr__(self, "predicted", freeze_mapping(dict(self.predicted)))
        object.__setattr__(self, "committed", freeze_mapping(dict(self.committed)))


@dataclass(frozen=True, slots=True)
class EvidenceInput:
    evidence_id: str
    state_key: str
    value: Any
    category: EvidenceStateCategory

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", ensure_non_empty_text("evidence_id", self.evidence_id))
        object.__setattr__(self, "state_key", ensure_non_empty_text("state_key", self.state_key))
        if not isinstance(self.category, EvidenceStateCategory):
            raise RuntimeCoreInvariantError("category must be an EvidenceStateCategory value")
        object.__setattr__(self, "value", copied(self.value))


class EvidenceMerger:
    """Explicit state merger with provenance preservation and fail-closed committed writes."""

    def merge(
        self,
        state: EvidenceState,
        evidence_entries: tuple[EvidenceInput, ...],
    ) -> EvidenceState:
        observed = dict(state.observed)
        inferred = dict(state.inferred)
        predicted = dict(state.predicted)
        committed = dict(state.committed)

        for entry in evidence_entries:
            target = self._target_map(
                entry.category,
                observed=observed,
                inferred=inferred,
                predicted=predicted,
                committed=committed,
            )
            existing = target.get(entry.state_key)

            if existing is not None and existing.value != entry.value:
                raise RuntimeCoreInvariantError("state conflict requires explicit reconciliation")

            if existing is None:
                target[entry.state_key] = StateAtom(
                    state_key=entry.state_key,
                    value=entry.value,
                    provenance_ids=(entry.evidence_id,),
                )
                continue

            provenance_ids = tuple(dict.fromkeys(existing.provenance_ids + (entry.evidence_id,)))
            target[entry.state_key] = StateAtom(
                state_key=entry.state_key,
                value=existing.value,
                provenance_ids=provenance_ids,
            )

        return EvidenceState(
            observed=observed,
            inferred=inferred,
            predicted=predicted,
            committed=committed,
        )

    @staticmethod
    def _target_map(
        category: EvidenceStateCategory,
        *,
        observed: dict[str, StateAtom],
        inferred: dict[str, StateAtom],
        predicted: dict[str, StateAtom],
        committed: dict[str, StateAtom],
    ) -> dict[str, StateAtom]:
        if category is EvidenceStateCategory.OBSERVED:
            return observed
        if category is EvidenceStateCategory.INFERRED:
            return inferred
        if category is EvidenceStateCategory.PREDICTED:
            return predicted
        return committed
