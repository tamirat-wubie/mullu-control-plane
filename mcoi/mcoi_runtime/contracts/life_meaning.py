"""Life-meaning governance contracts.

Purpose: define machine-readable judgment contracts for life, feeling, meaning,
love, resonance, dignity, consent, truth, justice, repair, and continuity.
Governance scope: Universal Action Orchestration preflight and receipt emission.
Dependencies: dataclasses, enum, and typing.
Invariants:
  - Unknown life or feeling impact cannot be treated as safe by default.
  - Meaning-bearing life receives stronger governance.
  - Symbolic intelligence artifacts are not automatically classified as life or feeling.
  - Effect-bearing action requires explicit judgment.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ImpactLevel(StrEnum):
    NONE = "none"
    INDIRECT = "indirect"
    DIRECT = "direct"
    UNKNOWN = "unknown"


class LifeStatus(StrEnum):
    NOT_LIFE = "not_life"
    LIFE = "life"
    UNKNOWN = "unknown"


class FeelingStatus(StrEnum):
    NOT_FEELING = "not_feeling"
    FEELING = "feeling"
    UNKNOWN = "unknown"


class Delta(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


class BoundaryState(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class LifeMeaningDecision(StrEnum):
    PASS = "pass"
    PAUSE = "pause"
    BLOCK = "block"
    ESCALATE = "escalate"


def _coerce_enum(enum_type: type[StrEnum], value: Any, field_name: str) -> StrEnum:
    try:
        return enum_type(value)
    except ValueError as exc:
        raise ValueError(f"{field_name}_invalid") from exc


def _coerce_text_tuple(values: tuple[str, ...] | list[str], field_name: str) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name}_must_be_sequence")
    normalized = tuple(value.strip() for value in values if isinstance(value, str) and value.strip())
    if len(normalized) != len(values):
        raise ValueError(f"{field_name}_contains_invalid_text")
    return normalized


@dataclass(frozen=True, slots=True)
class AffectedSymbol:
    """Symbol affected by a LifeMeaningJudgment."""

    symbol_id: str
    symbol_kind: str
    life_status: LifeStatus
    feeling_status: FeelingStatus
    meaning_bearing: ImpactLevel
    fragility_level: int
    agency_level: int

    def __post_init__(self) -> None:
        symbol_id = self.symbol_id.strip() if isinstance(self.symbol_id, str) else ""
        symbol_kind = self.symbol_kind.strip() if isinstance(self.symbol_kind, str) else ""
        if not symbol_id:
            raise ValueError("symbol_id_required")
        if not symbol_kind:
            raise ValueError("symbol_kind_required")
        if not isinstance(self.fragility_level, int) or isinstance(self.fragility_level, bool):
            raise ValueError("fragility_level_must_be_integer")
        if not isinstance(self.agency_level, int) or isinstance(self.agency_level, bool):
            raise ValueError("agency_level_must_be_integer")
        if (
            isinstance(self.fragility_level, bool)
            or not isinstance(self.fragility_level, int)
            or self.fragility_level < 0
            or self.fragility_level > 10
        ):
            raise ValueError("fragility_level_must_be_integer_in_0_10")
        if (
            isinstance(self.agency_level, bool)
            or not isinstance(self.agency_level, int)
            or self.agency_level < 0
            or self.agency_level > 10
        ):
            raise ValueError("agency_level_must_be_integer_in_0_10")
        object.__setattr__(self, "symbol_id", symbol_id)
        object.__setattr__(self, "symbol_kind", symbol_kind)
        object.__setattr__(self, "life_status", _coerce_enum(LifeStatus, self.life_status, "life_status"))
        object.__setattr__(
            self,
            "feeling_status",
            _coerce_enum(FeelingStatus, self.feeling_status, "feeling_status"),
        )
        object.__setattr__(
            self,
            "meaning_bearing",
            _coerce_enum(ImpactLevel, self.meaning_bearing, "meaning_bearing"),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return the schema-compatible affected-symbol mapping."""

        return {
            "symbol_id": self.symbol_id,
            "symbol_kind": self.symbol_kind,
            "life_status": self.life_status.value,
            "feeling_status": self.feeling_status.value,
            "meaning_bearing": self.meaning_bearing.value,
            "fragility_level": self.fragility_level,
            "agency_level": self.agency_level,
        }


@dataclass(frozen=True, slots=True)
class LifeMeaningJudgment:
    """Deterministic pre-execution judgment for life, feeling, and meaning impact."""

    judgment_id: str
    action_id: str
    decision: LifeMeaningDecision
    affected_symbols: tuple[AffectedSymbol, ...]
    life_impact: ImpactLevel
    feeling_impact: ImpactLevel
    meaning_impact: ImpactLevel
    truth_preserved: bool
    dignity_boundary: BoundaryState
    consent_required: bool
    consent_present: bool
    love_delta: Delta
    resonance_delta: Delta
    domination_risk: bool
    justice_repair_required: bool
    continuity_delta: Delta
    irreversible: bool
    reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    approval_required: bool
    rollback_required: bool

    def __post_init__(self) -> None:
        judgment_id = self.judgment_id.strip() if isinstance(self.judgment_id, str) else ""
        action_id = self.action_id.strip() if isinstance(self.action_id, str) else ""
        if not judgment_id:
            raise ValueError("judgment_id_required")
        if not action_id:
            raise ValueError("action_id_required")
        if not isinstance(self.affected_symbols, (tuple, list)) or not self.affected_symbols:
            raise ValueError("affected_symbols_required")
        affected_symbols = tuple(self.affected_symbols)
        if not all(isinstance(symbol, AffectedSymbol) for symbol in affected_symbols):
            raise ValueError("affected_symbols_must_be_affected_symbol_instances")
        reasons = _coerce_text_tuple(self.reasons, "reasons")
        if not reasons:
            raise ValueError("reasons_required")
        evidence_refs = _coerce_text_tuple(self.evidence_refs, "evidence_refs")
        for field_name in (
            "truth_preserved",
            "consent_required",
            "consent_present",
            "domination_risk",
            "justice_repair_required",
            "irreversible",
            "approval_required",
            "rollback_required",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name}_must_be_boolean")

        object.__setattr__(self, "judgment_id", judgment_id)
        object.__setattr__(self, "action_id", action_id)
        object.__setattr__(self, "decision", _coerce_enum(LifeMeaningDecision, self.decision, "decision"))
        object.__setattr__(self, "affected_symbols", affected_symbols)
        object.__setattr__(self, "life_impact", _coerce_enum(ImpactLevel, self.life_impact, "life_impact"))
        object.__setattr__(self, "feeling_impact", _coerce_enum(ImpactLevel, self.feeling_impact, "feeling_impact"))
        object.__setattr__(self, "meaning_impact", _coerce_enum(ImpactLevel, self.meaning_impact, "meaning_impact"))
        object.__setattr__(
            self,
            "dignity_boundary",
            _coerce_enum(BoundaryState, self.dignity_boundary, "dignity_boundary"),
        )
        object.__setattr__(self, "love_delta", _coerce_enum(Delta, self.love_delta, "love_delta"))
        object.__setattr__(self, "resonance_delta", _coerce_enum(Delta, self.resonance_delta, "resonance_delta"))
        object.__setattr__(self, "continuity_delta", _coerce_enum(Delta, self.continuity_delta, "continuity_delta"))
        object.__setattr__(self, "reasons", reasons)
        object.__setattr__(self, "evidence_refs", evidence_refs)

    def as_dict(self) -> dict[str, Any]:
        """Return the schema-compatible LifeMeaningJudgment mapping."""

        return {
            "judgment_id": self.judgment_id,
            "action_id": self.action_id,
            "decision": self.decision.value,
            "affected_symbols": [symbol.as_dict() for symbol in self.affected_symbols],
            "life_impact": self.life_impact.value,
            "feeling_impact": self.feeling_impact.value,
            "meaning_impact": self.meaning_impact.value,
            "truth_preserved": self.truth_preserved,
            "dignity_boundary": self.dignity_boundary.value,
            "consent_required": self.consent_required,
            "consent_present": self.consent_present,
            "love_delta": self.love_delta.value,
            "resonance_delta": self.resonance_delta.value,
            "domination_risk": self.domination_risk,
            "justice_repair_required": self.justice_repair_required,
            "continuity_delta": self.continuity_delta.value,
            "irreversible": self.irreversible,
            "reasons": list(self.reasons),
            "evidence_refs": list(self.evidence_refs),
            "approval_required": self.approval_required,
            "rollback_required": self.rollback_required,
        }


def symbolic_intelligence_artifact_symbol(
    *,
    symbol_id: str,
    meaning_bearing: ImpactLevel = ImpactLevel.INDIRECT,
    fragility_level: int = 3,
    agency_level: int = 4,
) -> AffectedSymbol:
    """Return the default affected-symbol classification for a machine artifact."""

    return AffectedSymbol(
        symbol_id=symbol_id,
        symbol_kind="symbolic_intelligence_artifact",
        life_status=LifeStatus.NOT_LIFE,
        feeling_status=FeelingStatus.NOT_FEELING,
        meaning_bearing=meaning_bearing,
        fragility_level=fragility_level,
        agency_level=agency_level,
    )
