"""Purpose: IntentSet contracts for source-bound intent resolution.
Governance scope: confused-deputy prevention and intent ambiguity handling.
Dependencies: capability contract source-trust enum and shared base helpers.
Invariants:
  - Intent is represented as a set, not a single guessed meaning.
  - Each candidate binds probability, risk class, and source trust.
  - Effectful authorization is never promoted from monitored content alone.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.contracts._base import ContractRecord, require_non_empty_text, require_unit_float
from mcoi_runtime.contracts.capability_contract import EffectClass, IntentSource


@dataclass(frozen=True, slots=True)
class IntentCandidate(ContractRecord):
    intent: str
    probability: float
    risk_class: str
    source_trust: IntentSource

    def __post_init__(self) -> None:
        object.__setattr__(self, "intent", require_non_empty_text(self.intent, "intent"))
        object.__setattr__(self, "probability", require_unit_float(self.probability, "probability"))
        object.__setattr__(self, "risk_class", require_non_empty_text(self.risk_class, "risk_class"))
        if not isinstance(self.source_trust, IntentSource):
            object.__setattr__(self, "source_trust", IntentSource(str(self.source_trust)))


@dataclass(frozen=True, slots=True)
class IntentSet(ContractRecord):
    candidates: tuple[IntentCandidate, ...]

    def __post_init__(self) -> None:
        if isinstance(self.candidates, (str, bytes)) or not isinstance(self.candidates, (tuple, list)):
            raise ValueError("candidates must be an array")
        candidates = tuple(self.candidates)
        if not candidates:
            raise ValueError("candidates must contain at least one item")
        for candidate in candidates:
            if not isinstance(candidate, IntentCandidate):
                raise ValueError("candidates must contain IntentCandidate instances")
        object.__setattr__(self, "candidates", candidates)

    def highest_probability(self) -> IntentCandidate:
        return sorted(self.candidates, key=lambda item: (-item.probability, item.intent))[0]

    def authorizes_effect(self, effect_class: EffectClass) -> bool:
        if effect_class is EffectClass.VALUE_PRODUCING:
            return True
        return any(candidate.source_trust is IntentSource.USER_DIRECT for candidate in self.candidates)
