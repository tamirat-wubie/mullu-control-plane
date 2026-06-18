"""Purpose: deterministic SNet recursive WH mesh prototype.
Governance scope: local WH ticks, answer metadata extraction, promotion gates,
    contextual contradiction records, unknown records, and depth-bounded recursion.
Dependencies: SNet contracts plus Python dataclasses, hashlib, and typing.
Invariants:
  - No external calls or filesystem writes occur.
  - No raw answer becomes a trusted fact by default.
  - No metadata becomes a symbol without a promotion score.
  - Recursive expansion terminates at the configured depth budget.
  - Mfidel text is never Unicode-normalized, decomposed, recomposed, or root-modeled.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from hashlib import sha256
from math import isfinite
from types import MappingProxyType

from mcoi_runtime.contracts.snet import (
    SNetAnswer,
    SNetContradiction,
    SNetContradictionState,
    SNetInquiryBudget,
    SNetMetadata,
    SNetOntologyStatus,
    SNetQuestion,
    SNetRelation,
    SNetSettlementState,
    SNetSymbol,
    SNetTickResult,
    SNetTickStatus,
    SNetUnknown,
    SNetValidationState,
    SNetWHType,
    WH_TYPES,
)


_HIGH_VALUE_FACETS = frozenset(
    {
        "cause_purpose",
        "mechanism",
        "upstream_dependency",
        "downstream_dependency",
        "failure",
        "counterfactual",
        "lineage",
        "boundary",
    }
)
_UNKNOWN_VALUES = frozenset({"unknown", "not applicable", "none", "n/a"})


AnswerProvider = Callable[[SNetSymbol], Mapping[str | SNetWHType, str]]


class SNetRecursiveMesh:
    """In-memory local proof engine for recursive WH-driven symbolization."""

    def __init__(self, budget: SNetInquiryBudget | None = None) -> None:
        self.budget = _require_budget(budget)
        self.symbols: dict[str, SNetSymbol] = {}
        self.questions: dict[str, SNetQuestion] = {}
        self.answers: dict[str, SNetAnswer] = {}
        self.metadata: dict[str, SNetMetadata] = {}
        self.relations: dict[str, SNetRelation] = {}
        self.contradictions: dict[str, SNetContradiction] = {}
        self.unknowns: dict[str, SNetUnknown] = {}
        self._symbol_identity_index: dict[tuple[str, str, str, str], str] = {}

    def add_symbol(
        self,
        label: str,
        *,
        symbol_type: str = "unknown",
        sense_id: str = "",
        definition: str = "",
        ontology_status: SNetOntologyStatus = SNetOntologyStatus.UNKNOWN_STATUS,
        parent_context: str = "",
        created_from_metadata_id: str = "",
        depth: int = 0,
    ) -> SNetSymbol:
        """Add or return a symbol using label, sense, type, and parent context."""
        label_text = _require_text(label, "label")
        symbol_type_text = _require_text(symbol_type, "symbol_type")
        sense_id_text = _optional_text(sense_id, "sense_id")
        definition_text = _optional_text(definition, "definition")
        ontology_status_value = _require_ontology_status(ontology_status)
        parent_context_text = _optional_text(parent_context, "parent_context")
        created_from_metadata_id_text = _optional_text(created_from_metadata_id, "created_from_metadata_id")
        depth_value = _require_depth(depth)
        if created_from_metadata_id_text:
            self._require_metadata_symbol_provenance(
                created_from_metadata_id_text,
                label_text,
                symbol_type_text,
                parent_context_text,
                depth_value,
            )
        identity_key = (
            _ascii_lower_stripped(label_text),
            _ascii_lower_stripped(sense_id_text or label_text),
            _ascii_lower_stripped(symbol_type_text),
            _ascii_lower_stripped(parent_context_text),
        )
        existing_symbol_id = self._symbol_identity_index.get(identity_key)
        if existing_symbol_id is not None:
            return self.symbols[existing_symbol_id]

        symbol_id = _stable_id("snet-symbol", *identity_key)
        symbol = SNetSymbol(
            symbol_id=symbol_id,
            label=label_text,
            symbol_type=symbol_type_text,
            sense_id=sense_id_text,
            definition=definition_text,
            ontology_status=ontology_status_value,
            parent_context=parent_context_text,
            created_from_metadata_id=created_from_metadata_id_text,
            depth=depth_value,
        )
        self.symbols[symbol.symbol_id] = symbol
        self._symbol_identity_index[identity_key] = symbol.symbol_id
        return symbol

    def generate_wh_tick(
        self,
        symbol_id: str,
        *,
        perspective: str = "general",
        context: str = "general",
        parent_question_id: str = "",
    ) -> SNetTickResult:
        """Generate the fixed WH burst for one symbol unless budget blocks it."""
        symbol = self._require_symbol(symbol_id)
        perspective = _require_text(perspective, "perspective")
        context = _require_text(context, "context")
        parent_question_id = _optional_text(parent_question_id, "parent_question_id")
        if parent_question_id:
            self._require_parent_question_scope(symbol, self._require_question(parent_question_id))
        tick_id = _stable_id("snet-tick", symbol_id, perspective, context, str(symbol.depth))
        if symbol.depth >= self.budget.max_depth:
            return SNetTickResult(
                tick_id=tick_id,
                symbol_id=symbol_id,
                status=SNetTickStatus.DEPTH_LIMIT_REACHED,
                blocked_reasons=("max_depth_reached",),
            )

        generated_question_ids: list[str] = []
        for wh_type in WH_TYPES[: self.budget.max_questions_per_symbol]:
            branch_signature = _branch_signature(symbol_id, wh_type, perspective, context)
            question_id = _stable_id("snet-question", branch_signature)
            if question_id in self.questions:
                continue
            question = SNetQuestion(
                question_id=question_id,
                target_symbol_id=symbol_id,
                wh_type=wh_type,
                text=render_question(wh_type, symbol.label),
                facet=map_wh_to_facet(wh_type),
                perspective=perspective,
                context=context,
                depth=symbol.depth,
                parent_question_id=parent_question_id,
                branch_signature=branch_signature,
            )
            self.questions[question.question_id] = question
            generated_question_ids.append(question.question_id)

        if not generated_question_ids:
            return SNetTickResult(
                tick_id=tick_id,
                symbol_id=symbol_id,
                status=SNetTickStatus.DUPLICATE_SKIPPED,
                blocked_reasons=("duplicate_tick",),
            )

        self._update_symbol(
            replace(
                symbol,
                inquiry_history=_append_unique(symbol.inquiry_history, tuple(generated_question_ids)),
                settlement_state=SNetSettlementState.EXPANDING,
            )
        )
        return SNetTickResult(
            tick_id=tick_id,
            symbol_id=symbol_id,
            status=SNetTickStatus.RAN,
            generated_question_ids=tuple(generated_question_ids),
        )

    def ingest_answer(
        self,
        question_id: str,
        raw_answer: str,
        *,
        confidence: float = 0.5,
        validation_state: SNetValidationState = SNetValidationState.UNVERIFIED,
        evidence_refs: tuple[str, ...] = (),
    ) -> SNetAnswer:
        """Store one answer as untrusted candidate material."""
        self._require_question(question_id)
        confidence_value = _require_confidence(confidence)
        validation_state = _require_validation_state(validation_state)
        raw_answer_text = _require_text(raw_answer, "raw_answer")
        ascii_folded_answer = _ascii_lower_stripped(raw_answer_text)
        evidence_ref_values = _require_text_tuple(evidence_refs, "evidence_refs")
        answer_id = _stable_id(
            "snet-answer",
            question_id,
            raw_answer_text,
            ascii_folded_answer,
            f"{confidence_value:.6f}",
            validation_state.value,
        )
        answer = SNetAnswer(
            answer_id=answer_id,
            question_id=question_id,
            raw_answer=raw_answer_text,
            ascii_folded_answer=ascii_folded_answer,
            confidence=confidence_value,
            validation_state=validation_state,
            evidence_refs=evidence_ref_values,
        )
        self.answers[answer.answer_id] = answer
        return answer

    def extract_metadata(self, question_id: str, answer_id: str) -> SNetMetadata:
        """Convert one answer into contextual metadata and record contradictions."""
        question = self._require_question(question_id)
        answer = self._require_answer(answer_id)
        if answer.question_id != question.question_id:
            raise ValueError("SNet answer_id must belong to the supplied question_id")
        metadata_id = _stable_id("snet-metadata", question_id, answer_id, question.facet)
        promotion_score = self.score_metadata(
            facet=question.facet,
            ascii_folded_value=answer.ascii_folded_answer,
            confidence=answer.confidence,
            validation_state=answer.validation_state,
        )
        record = SNetMetadata(
            metadata_id=metadata_id,
            parent_symbol_id=question.target_symbol_id,
            question_id=question_id,
            answer_id=answer_id,
            facet=question.facet,
            value=answer.ascii_folded_answer,
            context=question.context,
            perspective=question.perspective,
            confidence=answer.confidence,
            validation_state=answer.validation_state,
            promotion_score=promotion_score,
            evidence_refs=answer.evidence_refs,
        )
        self.metadata[record.metadata_id] = record
        symbol = self._require_symbol(record.parent_symbol_id)
        self._update_symbol(replace(symbol, metadata_refs=_append_unique(symbol.metadata_refs, (record.metadata_id,))))
        self._record_metadata_contradictions(record)
        return record

    def score_metadata(
        self,
        *,
        facet: str,
        ascii_folded_value: str,
        confidence: float,
        validation_state: SNetValidationState,
    ) -> float:
        """Score metadata for promotion using bounded deterministic features."""
        _require_text(facet, "facet")
        ascii_folded_value = _require_text(ascii_folded_value, "ascii_folded_value")
        confidence_value = _require_confidence(confidence)
        validation_state = _require_validation_state(validation_state)
        if ascii_folded_value in _UNKNOWN_VALUES or validation_state in {
            SNetValidationState.CONTRADICTED,
            SNetValidationState.NOT_APPLICABLE,
        }:
            return 0.0

        score = 0.0
        if confidence_value >= 0.70:
            score += 0.20
        if validation_state in {SNetValidationState.SUPPORTED, SNetValidationState.STRONGLY_SUPPORTED}:
            score += 0.15
        if facet in _HIGH_VALUE_FACETS:
            score += 0.25
        if 1 <= len(ascii_folded_value.split()) <= 5:
            score += 0.10
        if not self.find_symbols_by_label(ascii_folded_value):
            score += 0.20
        return max(0.0, min(1.0, score))

    def promote_metadata(self, metadata_id: str) -> SNetSymbol | None:
        """Promote metadata into a child symbol when the score allows it."""
        record = self._require_metadata(metadata_id)
        if record.promotion_score < self.budget.promotion_threshold:
            return None
        if record.value in _UNKNOWN_VALUES:
            return None

        parent = self._require_symbol(record.parent_symbol_id)
        parent_context = f"{parent.label}:{record.facet}:{record.value}"
        child = self.add_symbol(
            record.value,
            symbol_type="promoted_metadata",
            parent_context=parent_context,
            created_from_metadata_id=record.metadata_id,
            depth=parent.depth + 1,
        )
        relation_id = _stable_id("snet-relation", parent.symbol_id, record.facet, child.symbol_id, record.context)
        relation = SNetRelation(
            relation_id=relation_id,
            source_symbol_id=parent.symbol_id,
            relation_type=record.facet,
            target_symbol_id=child.symbol_id,
            confidence=record.confidence,
            context=record.context,
            perspective=record.perspective,
            evidence_refs=record.evidence_refs,
        )
        self.relations[relation.relation_id] = relation
        self._update_symbol(
            replace(
                parent,
                relation_refs=_append_unique(parent.relation_refs, (relation.relation_id,)),
            )
        )
        self.metadata[record.metadata_id] = replace(record, promoted_symbol_id=child.symbol_id)
        return child

    def run_tick_with_answers(
        self,
        symbol_id: str,
        answer_map: Mapping[str | SNetWHType, str],
        *,
        perspective: str = "general",
        context: str = "general",
        confidence: float = 0.75,
        validation_state: SNetValidationState = SNetValidationState.SUPPORTED,
    ) -> SNetTickResult:
        """Generate a WH tick, ingest supplied answers, and promote allowed metadata."""
        symbol = self._require_symbol(symbol_id)
        answer_lookup = _coerce_answer_map(answer_map)
        confidence_value = _require_confidence(confidence)
        validation_state = _require_validation_state(validation_state)
        allowed_wh_types = frozenset(WH_TYPES[: self.budget.max_questions_per_symbol])
        unexpected_wh_types = tuple(sorted(set(answer_lookup) - allowed_wh_types, key=lambda item: item.value))
        if unexpected_wh_types:
            unexpected_labels = ", ".join(wh_type.value for wh_type in unexpected_wh_types)
            raise ValueError(f"SNet answer key outside current question budget: {unexpected_labels}")
        if symbol.depth >= self.budget.max_depth and answer_lookup:
            raise ValueError("SNet answers supplied for depth-limited symbol")

        initial_tick = self.generate_wh_tick(symbol_id, perspective=perspective, context=context)
        if initial_tick.status is SNetTickStatus.DUPLICATE_SKIPPED and answer_lookup:
            raise ValueError("SNet answers supplied for duplicate tick")
        if initial_tick.status is not SNetTickStatus.RAN:
            return initial_tick

        answer_ids: list[str] = []
        metadata_ids: list[str] = []
        promoted_symbol_ids: list[str] = []
        unknown_ids: list[str] = []
        contradiction_ids_before = set(self.contradictions)

        for question_id in initial_tick.generated_question_ids:
            question = self.questions[question_id]
            answer_text = answer_lookup.get(question.wh_type)
            if answer_text is None:
                unknown = self._create_unknown(question, "answer_missing")
                unknown_ids.append(unknown.unknown_id)
                continue

            if _ascii_lower_stripped(answer_text) in _UNKNOWN_VALUES:
                unknown = self._create_unknown(question, "answer_unknown")
                unknown_ids.append(unknown.unknown_id)
                continue

            answer = self.ingest_answer(
                question.question_id,
                answer_text,
                confidence=confidence_value,
                validation_state=validation_state,
            )
            metadata_record = self.extract_metadata(question.question_id, answer.answer_id)
            child = self.promote_metadata(metadata_record.metadata_id)
            answer_ids.append(answer.answer_id)
            metadata_ids.append(metadata_record.metadata_id)
            if child is not None:
                promoted_symbol_ids.append(child.symbol_id)

        new_contradiction_ids = tuple(
            contradiction_id
            for contradiction_id in sorted(self.contradictions)
            if contradiction_id not in contradiction_ids_before
        )
        self.settle_symbol(symbol_id)
        return SNetTickResult(
            tick_id=initial_tick.tick_id,
            symbol_id=symbol_id,
            status=SNetTickStatus.RAN,
            generated_question_ids=initial_tick.generated_question_ids,
            answer_ids=tuple(answer_ids),
            metadata_ids=tuple(metadata_ids),
            promoted_symbol_ids=tuple(dict.fromkeys(promoted_symbol_ids)),
            unknown_ids=tuple(unknown_ids),
            contradiction_ids=new_contradiction_ids,
        )

    def run_recursive(
        self,
        root_symbol_id: str,
        answer_provider: AnswerProvider,
        *,
        perspective: str = "general",
        context: str = "general",
    ) -> tuple[SNetTickResult, ...]:
        """Run breadth-first recursive inquiry until the depth budget stops it."""
        self._require_symbol(root_symbol_id)
        results: list[SNetTickResult] = []
        queue: list[str] = [root_symbol_id]
        expanded_symbol_ids: set[str] = set()
        while queue:
            symbol_id = queue.pop(0)
            if symbol_id in expanded_symbol_ids:
                continue
            expanded_symbol_ids.add(symbol_id)
            symbol = self._require_symbol(symbol_id)
            if symbol.depth >= self.budget.max_depth:
                results.append(self.generate_wh_tick(symbol_id, perspective=perspective, context=context))
                continue
            result = self.run_tick_with_answers(
                symbol_id,
                answer_provider(symbol),
                perspective=perspective,
                context=context,
            )
            results.append(result)
            for child_symbol_id in result.promoted_symbol_ids:
                child_symbol = self._require_symbol(child_symbol_id)
                if child_symbol.depth < self.budget.max_depth:
                    queue.append(child_symbol_id)
        return tuple(results)

    def find_symbols_by_label(self, label: str) -> tuple[SNetSymbol, ...]:
        """Return all symbols whose label matches without collapsing senses."""
        ascii_folded_label = _ascii_lower_stripped(label)
        return tuple(
            symbol
            for symbol in self.symbols.values()
            if _ascii_lower_stripped(symbol.label) == ascii_folded_label
        )

    def settle_symbol(self, symbol_id: str) -> SNetSymbol:
        """Update a symbol settlement state from local records."""
        symbol = self._require_symbol(symbol_id)
        open_contradictions = tuple(
            contradiction
            for contradiction in self.contradictions.values()
            if contradiction.symbol_id == symbol_id and contradiction.resolution_state is SNetContradictionState.OPEN
        )
        symbol_unknowns = tuple(unknown for unknown in self.unknowns.values() if unknown.symbol_id == symbol_id)
        if open_contradictions:
            next_state = SNetSettlementState.CONTRADICTORY
        elif len(symbol_unknowns) >= self.budget.unknown_gravity_threshold:
            next_state = SNetSettlementState.UNKNOWN_HEAVY
        elif symbol.metadata_refs and not symbol_unknowns:
            next_state = SNetSettlementState.SETTLED
        else:
            next_state = SNetSettlementState.ACTIVE
        updated = replace(symbol, settlement_state=next_state)
        self._update_symbol(updated)
        return updated

    def _create_unknown(self, question: SNetQuestion, blocking_reason: str) -> SNetUnknown:
        unknown_id = _stable_id("snet-unknown", question.question_id, blocking_reason)
        unknown = SNetUnknown(
            unknown_id=unknown_id,
            symbol_id=question.target_symbol_id,
            missing_facet=question.facet,
            question_id=question.question_id,
            importance_score=_facet_importance(question.facet),
            blocking_reason=blocking_reason,
        )
        self.unknowns[unknown.unknown_id] = unknown
        return unknown

    def _record_metadata_contradictions(self, new_record: SNetMetadata) -> None:
        for existing_record in tuple(self.metadata.values()):
            if existing_record.metadata_id == new_record.metadata_id:
                continue
            if existing_record.parent_symbol_id != new_record.parent_symbol_id:
                continue
            if existing_record.facet != new_record.facet:
                continue
            if existing_record.value == new_record.value:
                continue
            contradiction_id = _stable_id(
                "snet-contradiction",
                new_record.parent_symbol_id,
                existing_record.metadata_id,
                new_record.metadata_id,
            )
            if contradiction_id in self.contradictions:
                continue
            state, reason = _classify_metadata_difference(existing_record, new_record)
            self.contradictions[contradiction_id] = SNetContradiction(
                contradiction_id=contradiction_id,
                symbol_id=new_record.parent_symbol_id,
                metadata_a_id=existing_record.metadata_id,
                metadata_b_id=new_record.metadata_id,
                context_a=existing_record.context,
                context_b=new_record.context,
                reason=reason,
                resolution_state=state,
                evidence_refs=tuple(dict.fromkeys(existing_record.evidence_refs + new_record.evidence_refs)),
            )

    def _require_parent_question_scope(self, symbol: SNetSymbol, parent_question: SNetQuestion) -> None:
        if parent_question.target_symbol_id == symbol.symbol_id:
            return
        if not symbol.created_from_metadata_id:
            raise ValueError("SNet parent_question_id must belong to the symbol causal scope")
        try:
            source_metadata = self.metadata[symbol.created_from_metadata_id]
        except KeyError as exc:
            raise ValueError("SNet parent_question_id must belong to the symbol causal scope") from exc
        if source_metadata.question_id != parent_question.question_id:
            raise ValueError("SNet parent_question_id must belong to the symbol causal scope")

    def _require_metadata_symbol_provenance(
        self,
        metadata_id: str,
        label: str,
        symbol_type: str,
        parent_context: str,
        depth: int,
    ) -> None:
        source_metadata = self._require_metadata(metadata_id)
        parent = self._require_symbol(source_metadata.parent_symbol_id)
        expected_parent_context = f"{parent.label}:{source_metadata.facet}:{source_metadata.value}"
        if (
            label != source_metadata.value
            or symbol_type != "promoted_metadata"
            or parent_context != expected_parent_context
            or type(depth) is not int
            or depth != parent.depth + 1
        ):
            raise ValueError("SNet created_from_metadata_id must match promoted metadata provenance")

    def _update_symbol(self, symbol: SNetSymbol) -> None:
        self.symbols[symbol.symbol_id] = symbol

    def _require_symbol(self, symbol_id: str) -> SNetSymbol:
        symbol_id = _require_id_text(symbol_id, "symbol_id")
        try:
            return self.symbols[symbol_id]
        except KeyError as exc:
            raise KeyError(f"unknown SNet symbol_id: {symbol_id}") from exc

    def _require_question(self, question_id: str) -> SNetQuestion:
        question_id = _require_id_text(question_id, "question_id")
        try:
            return self.questions[question_id]
        except KeyError as exc:
            raise KeyError(f"unknown SNet question_id: {question_id}") from exc

    def _require_answer(self, answer_id: str) -> SNetAnswer:
        answer_id = _require_id_text(answer_id, "answer_id")
        try:
            return self.answers[answer_id]
        except KeyError as exc:
            raise KeyError(f"unknown SNet answer_id: {answer_id}") from exc

    def _require_metadata(self, metadata_id: str) -> SNetMetadata:
        metadata_id = _require_id_text(metadata_id, "metadata_id")
        try:
            return self.metadata[metadata_id]
        except KeyError as exc:
            raise KeyError(f"unknown SNet metadata_id: {metadata_id}") from exc


def render_question(wh_type: SNetWHType, label: str) -> str:
    """Render a deterministic question template for one WH role."""
    templates = {
        SNetWHType.WHAT: f"What is {label}?",
        SNetWHType.WHY: f"Why does {label} exist or matter?",
        SNetWHType.HOW: f"How does {label} work or behave?",
        SNetWHType.WHEN: f"When does {label} appear, change, activate, or end?",
        SNetWHType.WHERE: f"Where does {label} exist, operate, or belong?",
        SNetWHType.WHICH: f"Which types, variants, or cases of {label} exist?",
        SNetWHType.WHO: f"Who or what agents interact with {label}?",
        SNetWHType.WHOSE: f"Whose origin, lineage, ownership, or belonging relation defines {label}?",
        SNetWHType.WHAT_IF: f"What if {label} changes, fails, is absent, or is placed in another context?",
        SNetWHType.WHAT_NOT: f"What is not {label}?",
        SNetWHType.WHY_NOT: f"Why would {label} not happen, not work, or not apply?",
        SNetWHType.HOW_NOT: f"How can {label} fail or be blocked?",
        SNetWHType.DEPENDS_ON: f"What does {label} depend on?",
        SNetWHType.DEPENDS_ON_ME: f"What depends on {label}?",
    }
    return templates[wh_type]


def map_wh_to_facet(wh_type: SNetWHType) -> str:
    """Map a WH role to the metadata facet it interrogates."""
    mapping = {
        SNetWHType.WHAT: "identity",
        SNetWHType.WHY: "cause_purpose",
        SNetWHType.HOW: "mechanism",
        SNetWHType.WHEN: "time_state",
        SNetWHType.WHERE: "environment",
        SNetWHType.WHICH: "classification",
        SNetWHType.WHO: "agency",
        SNetWHType.WHOSE: "lineage",
        SNetWHType.WHAT_IF: "counterfactual",
        SNetWHType.WHAT_NOT: "boundary",
        SNetWHType.WHY_NOT: "inhibition",
        SNetWHType.HOW_NOT: "failure",
        SNetWHType.DEPENDS_ON: "upstream_dependency",
        SNetWHType.DEPENDS_ON_ME: "downstream_dependency",
    }
    return mapping[wh_type]


def _coerce_answer_map(answer_map: Mapping[str | SNetWHType, str]) -> dict[SNetWHType, str]:
    if type(answer_map) not in (dict, MappingProxyType):
        raise ValueError("SNet answer_map must be a mapping")
    answer_lookup: dict[SNetWHType, str] = {}
    try:
        answer_items = tuple(answer_map.items())
    except Exception as exc:
        raise ValueError("SNet answer_map must be a mapping") from exc
    for raw_key, answer_text in answer_items:
        if isinstance(raw_key, SNetWHType):
            wh_type = raw_key
        elif type(raw_key) is str:
            try:
                wh_type = SNetWHType(raw_key)
            except ValueError as exc:
                raise ValueError(f"unknown SNet WH answer key: {raw_key!r}") from exc
        else:
            raise ValueError("SNet WH answer key must be a string or SNetWHType")
        if wh_type in answer_lookup:
            raise ValueError(f"duplicate SNet WH answer key: {wh_type.value}")
        if type(answer_text) is not str or not answer_text.strip():
            raise ValueError(f"SNet answer for {wh_type.value} must be a non-empty string")
        answer_lookup[wh_type] = answer_text
    return answer_lookup


def _require_text(value: str, field_name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_text(value: str, field_name: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{field_name} must be a non-empty string")
    if value == "":
        return ""
    return _require_text(value, field_name)


def _require_ontology_status(ontology_status: SNetOntologyStatus) -> SNetOntologyStatus:
    if not isinstance(ontology_status, SNetOntologyStatus):
        raise ValueError("ontology_status must be a SNetOntologyStatus")
    return ontology_status


def _require_depth(depth: int) -> int:
    if type(depth) is not int:
        raise ValueError("depth must be an integer")
    if depth < 0:
        raise ValueError("depth must be non-negative")
    return depth


def _require_id_text(value: str, field_name: str) -> str:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be an exact non-empty string")
    return value


def _require_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if type(values) is not tuple:
        raise ValueError(f"{field_name} must be a tuple of non-empty strings")
    for index, value in enumerate(values):
        _require_text(value, f"{field_name}[{index}]")
    return values


def _require_confidence(confidence: float) -> float:
    if type(confidence) not in (int, float):
        raise ValueError("SNet confidence must be a finite number in [0.0, 1.0]")
    confidence_value = float(confidence)
    if not isfinite(confidence_value) or not 0.0 <= confidence_value <= 1.0:
        raise ValueError("SNet confidence must be a finite number in [0.0, 1.0]")
    return confidence_value


def _require_validation_state(validation_state: SNetValidationState) -> SNetValidationState:
    if not isinstance(validation_state, SNetValidationState):
        raise ValueError("validation_state must be a SNetValidationState")
    return validation_state


def _require_budget(budget: SNetInquiryBudget | None) -> SNetInquiryBudget:
    if budget is None:
        return SNetInquiryBudget()
    if type(budget) is not SNetInquiryBudget:
        raise ValueError("SNet budget must be a SNetInquiryBudget")
    return budget


def _classify_metadata_difference(
    existing_record: SNetMetadata,
    new_record: SNetMetadata,
) -> tuple[SNetContradictionState, str]:
    if existing_record.context != new_record.context:
        return SNetContradictionState.CONTEXTUAL_DUALITY, "metadata values differ by context"
    if existing_record.perspective != new_record.perspective:
        return SNetContradictionState.PERSPECTIVE_DIFFERENCE, "metadata values differ by perspective"
    if (
        existing_record.validation_state is SNetValidationState.UNVERIFIED
        or new_record.validation_state is SNetValidationState.UNVERIFIED
    ):
        return SNetContradictionState.WEAK_CONTRADICTION, "one metadata value lacks support"
    return SNetContradictionState.OPEN, "metadata values conflict in the same context and perspective"


def _facet_importance(facet: str) -> float:
    if facet in _HIGH_VALUE_FACETS:
        return 0.90
    if facet in {"identity", "classification", "environment"}:
        return 0.70
    return 0.50


def _branch_signature(symbol_id: str, wh_type: SNetWHType, perspective: str, context: str) -> str:
    return "|".join((symbol_id, wh_type.value, _ascii_lower_stripped(perspective), _ascii_lower_stripped(context)))


def _append_unique(existing_values: tuple[str, ...], new_values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(existing_values + new_values))


def _stable_id(prefix: str, *parts: str) -> str:
    joined = "\x1f".join(parts)
    digest = sha256(joined.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}:{digest}"


def _ascii_lower_stripped(value: str) -> str:
    """Lowercase ASCII only so non-Latin symbols remain atomic codepoints."""
    if type(value) is not str:
        raise ValueError("SNet text value must be a string")
    stripped = value.strip()
    return "".join(chr(ord(char) + 32) if "A" <= char <= "Z" else char for char in stripped)
