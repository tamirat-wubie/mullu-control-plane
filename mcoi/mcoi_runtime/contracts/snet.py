"""Purpose: typed SNet records for bounded recursive symbolic inquiry.
Governance scope: WH inquiry ticks, metadata promotion, relations,
    contradictions, unknown records, inquiry budgets, and proof receipts.
Dependencies: shared contract utilities, dataclasses, enum, and typing.
Invariants:
  - Records are immutable and deterministic.
  - No answer is trusted only because it exists.
  - Metadata promotion requires an explicit score.
  - Unknowns and contradictions remain first-class records.
  - Text handling never applies Unicode decomposition or recomposition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import math
import unicodedata
from types import MappingProxyType
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_non_empty_text,
)


SNET_VERSION = "0.1.5"
SNET_SEMANTICS_HASH = "sha256:snet-v0.1.5-answer-and-text-boundary-refined"
SNET_READ_ONLY_SURFACE = "read_only_snet_recursive_mesh"
_FORBIDDEN_TEXT_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})


class SNetWHType(StrEnum):
    """Bounded WH inquiry roles used by the first SNet prototype."""

    WHAT = "what"
    WHY = "why"
    HOW = "how"
    WHEN = "when"
    WHERE = "where"
    WHICH = "which"
    WHO = "who"
    WHOSE = "whose"
    WHAT_IF = "what_if"
    WHAT_NOT = "what_not"
    WHY_NOT = "why_not"
    HOW_NOT = "how_not"
    DEPENDS_ON = "depends_on"
    DEPENDS_ON_ME = "depends_on_me"


class SNetValidationState(StrEnum):
    """Evidence state for answers and metadata before trusted use."""

    UNVERIFIED = "unverified"
    WEAKLY_SUPPORTED = "weakly_supported"
    SUPPORTED = "supported"
    STRONGLY_SUPPORTED = "strongly_supported"
    CONTRADICTED = "contradicted"
    NOT_APPLICABLE = "not_applicable"


class SNetSettlementState(StrEnum):
    """Current inquiry status for one symbol."""

    ACTIVE = "active"
    EXPANDING = "expanding"
    SETTLED = "settled"
    DORMANT = "dormant"
    CONTRADICTORY = "contradictory"
    UNKNOWN_HEAVY = "unknown_heavy"
    DEPRECATED = "deprecated"


class SNetOntologyStatus(StrEnum):
    """Reality-status boundary for a symbol."""

    PHYSICAL_REAL = "physical_real"
    FICTIONAL = "fictional"
    MYTHOLOGICAL = "mythological"
    HYPOTHETICAL = "hypothetical"
    MATHEMATICAL = "mathematical"
    SIMULATED = "simulated"
    UNKNOWN_STATUS = "unknown_status"


class SNetContradictionState(StrEnum):
    """Resolution state for contradictory or context-divergent claims."""

    OPEN = "open"
    CONTEXTUAL_DUALITY = "contextual_duality"
    TEMPORAL_STATE_CHANGE = "temporal_state_change"
    PERSPECTIVE_DIFFERENCE = "perspective_difference"
    WEAK_CONTRADICTION = "weak_contradiction"
    TRUE_CONFLICT = "true_conflict"
    RESOLVED = "resolved"


class SNetTickStatus(StrEnum):
    """Terminal condition for one WH tick."""

    RAN = "ran"
    DUPLICATE_SKIPPED = "duplicate_skipped"
    DEPTH_LIMIT_REACHED = "depth_limit_reached"


WH_TYPES: tuple[SNetWHType, ...] = (
    SNetWHType.WHAT,
    SNetWHType.WHY,
    SNetWHType.HOW,
    SNetWHType.WHEN,
    SNetWHType.WHERE,
    SNetWHType.WHICH,
    SNetWHType.WHO,
    SNetWHType.WHOSE,
    SNetWHType.WHAT_IF,
    SNetWHType.WHAT_NOT,
    SNetWHType.WHY_NOT,
    SNetWHType.HOW_NOT,
    SNetWHType.DEPENDS_ON,
    SNetWHType.DEPENDS_ON_ME,
)


def _freeze_text_tuple(values: object, field_name: str) -> tuple[str, ...]:
    if type(values) not in (list, tuple):
        raise ValueError(f"{field_name} must be an array")
    frozen = freeze_value(list(values))
    if not isinstance(frozen, tuple):
        raise ValueError(f"{field_name} must be an array")
    for index, value in enumerate(frozen):
        _require_exact_text(value, f"{field_name}[{index}]")
    return frozen


def _freeze_metadata(metadata: Mapping[str, Any], field_name: str = "metadata") -> Mapping[str, Any]:
    if type(metadata) not in (dict, MappingProxyType):
        raise ValueError(f"{field_name} must be a mapping")
    sorted_metadata: dict[str, Any] = {}
    try:
        metadata_items = tuple(metadata.items())
    except Exception as exc:
        raise ValueError(f"{field_name} must be a mapping") from exc
    for key, value in metadata_items:
        metadata_key = _require_text_key(key, f"{field_name}.key")
        sorted_metadata[metadata_key] = _freeze_metadata_value(value, f"{field_name}.{metadata_key}")
    return freeze_value(dict(sorted(sorted_metadata.items(), key=lambda item: item[0])))


def _freeze_metadata_value(value: object, field_name: str) -> object:
    if type(value) in (dict, MappingProxyType):
        sorted_metadata: dict[str, object] = {}
        try:
            metadata_items = tuple(value.items())
        except Exception as exc:
            raise ValueError(f"{field_name} must be a mapping") from exc
        for key, item in metadata_items:
            metadata_key = _require_text_key(key, f"{field_name}.key")
            sorted_metadata[metadata_key] = _freeze_metadata_value(item, f"{field_name}.{metadata_key}")
        return freeze_value(dict(sorted(sorted_metadata.items(), key=lambda item: item[0])))
    if isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    if type(value) in (list, tuple):
        return freeze_value(
            [
                _freeze_metadata_value(item, f"{field_name}[{index}]")
                for index, item in enumerate(value)
            ]
        )
    return _require_metadata_scalar(value, field_name)


def _require_metadata_scalar(value: object, field_name: str) -> object:
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{field_name} must be finite")
        return value
    raise ValueError(f"{field_name} must be a JSON metadata value")


def _require_text_key(key: object, field_name: str) -> str:
    return _require_exact_text(key, field_name)


def _require_text(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{field_name} must be a non-empty string")
    exact_value = require_non_empty_text(value, field_name)
    _require_visible_text_characters(exact_value, field_name)
    return exact_value


def _require_exact_text(value: object, field_name: str) -> str:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be an exact non-empty string")
    _require_visible_text_characters(value, field_name)
    return value


def _require_optional_exact_text(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{field_name} must be an exact non-empty string or empty")
    if value == "":
        return ""
    return _require_exact_text(value, field_name)


def _require_scope_text(value: object, field_name: str) -> str:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be an exact non-empty scope string")
    _require_visible_text_characters(value, field_name)
    return value


def _require_semantic_text(value: object, field_name: str) -> str:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be an exact non-empty semantic string")
    _require_visible_text_characters(value, field_name)
    return value


def _require_visible_text_characters(value: str, field_name: str) -> None:
    for index, character in enumerate(value):
        if unicodedata.category(character) in _FORBIDDEN_TEXT_CATEGORIES:
            raise ValueError(
                f"{field_name} contains forbidden control or invisible character at index {index}"
            )


def _require_optional_scope_text(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{field_name} must be an exact non-empty scope string or empty")
    if value == "":
        return ""
    return _require_scope_text(value, field_name)


def _require_optional_text(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{field_name} must be a non-empty string")
    if value == "":
        return ""
    exact_value = require_non_empty_text(value, field_name)
    _require_visible_text_characters(exact_value, field_name)
    return exact_value


def _require_literal_bool(value: object, expected: bool, field_name: str) -> bool:
    if type(value) is not bool or value is not expected:
        expected_text = "true" if expected else "false"
        raise ValueError(f"{field_name} must be {expected_text}")
    return expected


def _require_non_negative_int(value: object, field_name: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return value


def _require_unit_float(value: object, field_name: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{field_name} must be a number")
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        raise ValueError(f"{field_name} must be finite")
    if not 0.0 <= numeric_value <= 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")
    return numeric_value


@dataclass(frozen=True, slots=True)
class SNetInquiryBudget(ContractRecord):
    """Hard budget for one local recursive inquiry pass."""

    max_depth: int = 3
    max_questions_per_symbol: int = len(WH_TYPES)
    promotion_threshold: float = 0.65
    unknown_gravity_threshold: int = 3

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_depth", _require_non_negative_int(self.max_depth, "max_depth"))
        max_questions_per_symbol = _require_non_negative_int(
            self.max_questions_per_symbol,
            "max_questions_per_symbol",
        )
        if max_questions_per_symbol < 1:
            raise ValueError("max_questions_per_symbol must be >= 1")
        if max_questions_per_symbol > len(WH_TYPES):
            raise ValueError("max_questions_per_symbol must not exceed the finite SNet WH spine")
        object.__setattr__(self, "max_questions_per_symbol", max_questions_per_symbol)
        object.__setattr__(
            self,
            "promotion_threshold",
            _require_unit_float(self.promotion_threshold, "promotion_threshold"),
        )
        unknown_gravity_threshold = _require_non_negative_int(
            self.unknown_gravity_threshold,
            "unknown_gravity_threshold",
        )
        if unknown_gravity_threshold < 1:
            raise ValueError("unknown_gravity_threshold must be >= 1")
        object.__setattr__(self, "unknown_gravity_threshold", unknown_gravity_threshold)


@dataclass(frozen=True, slots=True)
class SNetSymbol(ContractRecord):
    """A symbol admitted to the local recursive inquiry mesh."""

    symbol_id: str
    label: str
    symbol_type: str = "unknown"
    sense_id: str = ""
    definition: str = ""
    ontology_status: SNetOntologyStatus = SNetOntologyStatus.UNKNOWN_STATUS
    settlement_state: SNetSettlementState = SNetSettlementState.ACTIVE
    depth: int = 0
    parent_context: str = ""
    created_from_metadata_id: str = ""
    metadata_refs: tuple[str, ...] = ()
    relation_refs: tuple[str, ...] = ()
    inquiry_history: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol_id", _require_exact_text(self.symbol_id, "symbol_id"))
        object.__setattr__(self, "label", _require_text(self.label, "label"))
        object.__setattr__(self, "symbol_type", _require_text(self.symbol_type, "symbol_type"))
        object.__setattr__(self, "sense_id", _require_optional_exact_text(self.sense_id, "sense_id"))
        object.__setattr__(self, "definition", _require_optional_text(self.definition, "definition"))
        if not isinstance(self.ontology_status, SNetOntologyStatus):
            raise ValueError("ontology_status must be a SNetOntologyStatus")
        if not isinstance(self.settlement_state, SNetSettlementState):
            raise ValueError("settlement_state must be a SNetSettlementState")
        object.__setattr__(self, "depth", _require_non_negative_int(self.depth, "depth"))
        object.__setattr__(
            self,
            "parent_context",
            _require_optional_scope_text(self.parent_context, "parent_context"),
        )
        object.__setattr__(
            self,
            "created_from_metadata_id",
            _require_optional_exact_text(self.created_from_metadata_id, "created_from_metadata_id"),
        )
        object.__setattr__(self, "metadata_refs", _freeze_text_tuple(self.metadata_refs, "metadata_refs"))
        object.__setattr__(self, "relation_refs", _freeze_text_tuple(self.relation_refs, "relation_refs"))
        object.__setattr__(self, "inquiry_history", _freeze_text_tuple(self.inquiry_history, "inquiry_history"))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class SNetQuestion(ContractRecord):
    """One generated WH question scoped to a symbol, context, and perspective."""

    question_id: str
    target_symbol_id: str
    wh_type: SNetWHType
    text: str
    facet: str
    perspective: str = "general"
    context: str = "general"
    depth: int = 0
    parent_question_id: str = ""
    branch_signature: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "question_id", _require_exact_text(self.question_id, "question_id"))
        object.__setattr__(self, "target_symbol_id", _require_exact_text(self.target_symbol_id, "target_symbol_id"))
        if not isinstance(self.wh_type, SNetWHType):
            raise ValueError("wh_type must be a SNetWHType")
        object.__setattr__(self, "text", _require_text(self.text, "text"))
        object.__setattr__(self, "facet", _require_semantic_text(self.facet, "facet"))
        object.__setattr__(self, "perspective", _require_scope_text(self.perspective, "perspective"))
        object.__setattr__(self, "context", _require_scope_text(self.context, "context"))
        object.__setattr__(self, "depth", _require_non_negative_int(self.depth, "depth"))
        object.__setattr__(
            self,
            "parent_question_id",
            _require_optional_exact_text(self.parent_question_id, "parent_question_id"),
        )
        object.__setattr__(
            self,
            "branch_signature",
            _require_optional_exact_text(self.branch_signature, "branch_signature"),
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class SNetAnswer(ContractRecord):
    """A candidate answer that is not trusted until evidence admits it."""

    answer_id: str
    question_id: str
    raw_answer: str
    ascii_folded_answer: str
    confidence: float
    validation_state: SNetValidationState = SNetValidationState.UNVERIFIED
    evidence_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "answer_id", _require_exact_text(self.answer_id, "answer_id"))
        object.__setattr__(self, "question_id", _require_exact_text(self.question_id, "question_id"))
        object.__setattr__(self, "raw_answer", _require_exact_text(self.raw_answer, "raw_answer"))
        object.__setattr__(
            self,
            "ascii_folded_answer",
            _require_exact_text(self.ascii_folded_answer, "ascii_folded_answer"),
        )
        object.__setattr__(self, "confidence", _require_unit_float(self.confidence, "confidence"))
        if not isinstance(self.validation_state, SNetValidationState):
            raise ValueError("validation_state must be a SNetValidationState")
        object.__setattr__(self, "evidence_refs", _freeze_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class SNetMetadata(ContractRecord):
    """Contextual metadata extracted from one answer."""

    metadata_id: str
    parent_symbol_id: str
    question_id: str
    answer_id: str
    facet: str
    value: str
    context: str
    perspective: str
    confidence: float
    validation_state: SNetValidationState
    promotion_score: float = 0.0
    promoted_symbol_id: str = ""
    evidence_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata_id", _require_exact_text(self.metadata_id, "metadata_id"))
        object.__setattr__(self, "parent_symbol_id", _require_exact_text(self.parent_symbol_id, "parent_symbol_id"))
        object.__setattr__(self, "question_id", _require_exact_text(self.question_id, "question_id"))
        object.__setattr__(self, "answer_id", _require_exact_text(self.answer_id, "answer_id"))
        object.__setattr__(self, "facet", _require_semantic_text(self.facet, "facet"))
        object.__setattr__(self, "value", _require_semantic_text(self.value, "value"))
        object.__setattr__(self, "context", _require_scope_text(self.context, "context"))
        object.__setattr__(self, "perspective", _require_scope_text(self.perspective, "perspective"))
        object.__setattr__(self, "confidence", _require_unit_float(self.confidence, "confidence"))
        if not isinstance(self.validation_state, SNetValidationState):
            raise ValueError("validation_state must be a SNetValidationState")
        object.__setattr__(self, "promotion_score", _require_unit_float(self.promotion_score, "promotion_score"))
        object.__setattr__(
            self,
            "promoted_symbol_id",
            _require_optional_exact_text(self.promoted_symbol_id, "promoted_symbol_id"),
        )
        object.__setattr__(self, "evidence_refs", _freeze_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class SNetRelation(ContractRecord):
    """Typed relation created through metadata promotion."""

    relation_id: str
    source_symbol_id: str
    relation_type: str
    target_symbol_id: str
    confidence: float
    context: str
    perspective: str
    evidence_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "relation_id", _require_exact_text(self.relation_id, "relation_id"))
        object.__setattr__(self, "source_symbol_id", _require_exact_text(self.source_symbol_id, "source_symbol_id"))
        object.__setattr__(self, "relation_type", _require_semantic_text(self.relation_type, "relation_type"))
        object.__setattr__(self, "target_symbol_id", _require_exact_text(self.target_symbol_id, "target_symbol_id"))
        object.__setattr__(self, "confidence", _require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "context", _require_scope_text(self.context, "context"))
        object.__setattr__(self, "perspective", _require_scope_text(self.perspective, "perspective"))
        object.__setattr__(self, "evidence_refs", _freeze_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class SNetContradiction(ContractRecord):
    """Stored contradiction or context-divergent metadata pair."""

    contradiction_id: str
    symbol_id: str
    metadata_a_id: str
    metadata_b_id: str
    context_a: str
    context_b: str
    reason: str
    resolution_state: SNetContradictionState = SNetContradictionState.OPEN
    evidence_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "contradiction_id", _require_exact_text(self.contradiction_id, "contradiction_id"))
        object.__setattr__(self, "symbol_id", _require_exact_text(self.symbol_id, "symbol_id"))
        object.__setattr__(self, "metadata_a_id", _require_exact_text(self.metadata_a_id, "metadata_a_id"))
        object.__setattr__(self, "metadata_b_id", _require_exact_text(self.metadata_b_id, "metadata_b_id"))
        object.__setattr__(self, "context_a", _require_scope_text(self.context_a, "context_a"))
        object.__setattr__(self, "context_b", _require_scope_text(self.context_b, "context_b"))
        object.__setattr__(self, "reason", _require_text(self.reason, "reason"))
        if not isinstance(self.resolution_state, SNetContradictionState):
            raise ValueError("resolution_state must be a SNetContradictionState")
        object.__setattr__(self, "evidence_refs", _freeze_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class SNetUnknown(ContractRecord):
    """First-class missing knowledge record generated by an inquiry tick."""

    unknown_id: str
    symbol_id: str
    missing_facet: str
    question_id: str
    importance_score: float
    blocking_reason: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "unknown_id", _require_exact_text(self.unknown_id, "unknown_id"))
        object.__setattr__(self, "symbol_id", _require_exact_text(self.symbol_id, "symbol_id"))
        object.__setattr__(self, "missing_facet", _require_semantic_text(self.missing_facet, "missing_facet"))
        object.__setattr__(self, "question_id", _require_exact_text(self.question_id, "question_id"))
        object.__setattr__(self, "importance_score", _require_unit_float(self.importance_score, "importance_score"))
        object.__setattr__(
            self,
            "blocking_reason",
            _require_semantic_text(self.blocking_reason, "blocking_reason"),
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class SNetTickResult(ContractRecord):
    """Receipt-style result for one local WH tick."""

    tick_id: str
    symbol_id: str
    status: SNetTickStatus
    generated_question_ids: tuple[str, ...] = ()
    answer_ids: tuple[str, ...] = ()
    metadata_ids: tuple[str, ...] = ()
    promoted_symbol_ids: tuple[str, ...] = ()
    unknown_ids: tuple[str, ...] = ()
    contradiction_ids: tuple[str, ...] = ()
    blocked_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "tick_id", _require_exact_text(self.tick_id, "tick_id"))
        object.__setattr__(self, "symbol_id", _require_exact_text(self.symbol_id, "symbol_id"))
        if not isinstance(self.status, SNetTickStatus):
            raise ValueError("status must be a SNetTickStatus")
        object.__setattr__(
            self,
            "generated_question_ids",
            _freeze_text_tuple(self.generated_question_ids, "generated_question_ids"),
        )
        object.__setattr__(self, "answer_ids", _freeze_text_tuple(self.answer_ids, "answer_ids"))
        object.__setattr__(self, "metadata_ids", _freeze_text_tuple(self.metadata_ids, "metadata_ids"))
        object.__setattr__(
            self,
            "promoted_symbol_ids",
            _freeze_text_tuple(self.promoted_symbol_ids, "promoted_symbol_ids"),
        )
        object.__setattr__(self, "unknown_ids", _freeze_text_tuple(self.unknown_ids, "unknown_ids"))
        object.__setattr__(
            self,
            "contradiction_ids",
            _freeze_text_tuple(self.contradiction_ids, "contradiction_ids"),
        )
        object.__setattr__(self, "blocked_reasons", _freeze_text_tuple(self.blocked_reasons, "blocked_reasons"))


@dataclass(frozen=True, slots=True)
class SNetMeshReceipt(ContractRecord):
    """Read-only receipt for one projected SNet mesh state."""

    receipt_id: str
    snet_version: str
    semantics_hash: str
    mesh_digest: str
    surface: str
    symbol_count: int
    question_count: int
    answer_count: int
    metadata_count: int
    relation_count: int
    unknown_count: int
    contradiction_count: int
    max_depth: int
    promotion_threshold: float
    settlement_counts: Mapping[str, int]
    terminal_closure_required: bool = True
    receipt_is_not_terminal_closure: bool = True
    raw_answers_exposed: bool = False
    raw_metadata_values_exposed: bool = False
    execution_authority_granted: bool = False
    connector_authority_granted: bool = False
    route_authority_granted: bool = False
    filesystem_authority_granted: bool = False
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", _require_exact_text(self.receipt_id, "receipt_id"))
        if not _is_snet_mesh_receipt_id(self.receipt_id):
            raise ValueError("receipt_id must match snet-mesh-[0-9a-f]{16}")
        object.__setattr__(self, "snet_version", _require_exact_text(self.snet_version, "snet_version"))
        if self.snet_version != SNET_VERSION:
            raise ValueError("snet_version must match runtime SNet version")
        object.__setattr__(self, "semantics_hash", _require_exact_text(self.semantics_hash, "semantics_hash"))
        if self.semantics_hash != SNET_SEMANTICS_HASH:
            raise ValueError("semantics_hash must match runtime SNet semantics")
        object.__setattr__(self, "mesh_digest", _require_exact_text(self.mesh_digest, "mesh_digest"))
        if not _is_sha256_digest(self.mesh_digest):
            raise ValueError("mesh_digest must be a sha256 digest")
        object.__setattr__(self, "surface", _require_exact_text(self.surface, "surface"))
        if self.surface != SNET_READ_ONLY_SURFACE:
            raise ValueError("surface must be the read-only SNet operator surface")
        object.__setattr__(self, "symbol_count", _require_non_negative_int(self.symbol_count, "symbol_count"))
        object.__setattr__(self, "question_count", _require_non_negative_int(self.question_count, "question_count"))
        object.__setattr__(self, "answer_count", _require_non_negative_int(self.answer_count, "answer_count"))
        object.__setattr__(self, "metadata_count", _require_non_negative_int(self.metadata_count, "metadata_count"))
        object.__setattr__(self, "relation_count", _require_non_negative_int(self.relation_count, "relation_count"))
        object.__setattr__(self, "unknown_count", _require_non_negative_int(self.unknown_count, "unknown_count"))
        object.__setattr__(
            self,
            "contradiction_count",
            _require_non_negative_int(self.contradiction_count, "contradiction_count"),
        )
        object.__setattr__(self, "max_depth", _require_non_negative_int(self.max_depth, "max_depth"))
        object.__setattr__(
            self,
            "promotion_threshold",
            _require_unit_float(self.promotion_threshold, "promotion_threshold"),
        )
        if type(self.settlement_counts) is not dict:
            raise ValueError("settlement_counts must be a mapping")
        settlement_count_map: dict[str, int] = {}
        for key, value in self.settlement_counts.items():
            settlement_key = _require_text_key(key, "settlement_counts.key")
            if settlement_key in settlement_count_map:
                raise ValueError("settlement_counts must not contain duplicate keys")
            settlement_count_map[settlement_key] = _require_non_negative_int(
                value,
                "settlement_counts.value",
            )
        required_settlement_keys = {state.value for state in SNetSettlementState}
        if set(settlement_count_map) != required_settlement_keys:
            raise ValueError("settlement_counts must contain every SNet settlement state exactly")
        if sum(settlement_count_map.values()) != self.symbol_count:
            raise ValueError("settlement_counts total must match symbol_count")
        object.__setattr__(self, "settlement_counts", freeze_value(settlement_count_map))
        object.__setattr__(
            self,
            "terminal_closure_required",
            _require_literal_bool(self.terminal_closure_required, True, "terminal closure required flag"),
        )
        object.__setattr__(
            self,
            "receipt_is_not_terminal_closure",
            _require_literal_bool(self.receipt_is_not_terminal_closure, True, "receipt is not terminal closure flag"),
        )
        object.__setattr__(
            self,
            "raw_answers_exposed",
            _require_literal_bool(self.raw_answers_exposed, False, "raw answers exposed flag"),
        )
        object.__setattr__(
            self,
            "raw_metadata_values_exposed",
            _require_literal_bool(self.raw_metadata_values_exposed, False, "raw metadata values exposed flag"),
        )
        object.__setattr__(
            self,
            "execution_authority_granted",
            _require_literal_bool(self.execution_authority_granted, False, "execution authority flag"),
        )
        object.__setattr__(
            self,
            "connector_authority_granted",
            _require_literal_bool(self.connector_authority_granted, False, "connector authority flag"),
        )
        object.__setattr__(
            self,
            "route_authority_granted",
            _require_literal_bool(self.route_authority_granted, False, "route authority flag"),
        )
        object.__setattr__(
            self,
            "filesystem_authority_granted",
            _require_literal_bool(self.filesystem_authority_granted, False, "filesystem authority flag"),
        )
        object.__setattr__(self, "evidence_refs", _freeze_text_tuple(self.evidence_refs, "evidence_refs"))
        if not self.evidence_refs:
            raise ValueError("evidence_refs must contain at least one evidence reference")


def _is_snet_mesh_receipt_id(receipt_id: str) -> bool:
    prefix = "snet-mesh-"
    suffix = receipt_id[len(prefix) :]
    return receipt_id.startswith(prefix) and len(suffix) == 16 and all(char in "0123456789abcdef" for char in suffix)


def _is_sha256_digest(digest: str) -> bool:
    prefix = "sha256:"
    suffix = digest[len(prefix) :]
    return digest.startswith(prefix) and len(suffix) == 64 and all(char in "0123456789abcdef" for char in suffix)
