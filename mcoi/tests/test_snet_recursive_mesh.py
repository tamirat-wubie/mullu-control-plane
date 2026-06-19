"""Purpose: verify SNet recursive WH mesh prototype behavior.
Governance scope: WH coverage, promotion gates, context retention,
    contradiction recording, perspective isolation, and recursion termination.
Dependencies: mcoi_runtime.contracts.snet and mcoi_runtime.snet.engine.
Invariants:
  - Inquiry remains local and deterministic.
  - Unknowns are not promoted.
  - Context and perspective are never silently merged.
  - Recursion stops at the configured budget.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.snet import (
    SNetAnswer,
    SNetContradictionState,
    SNetInquiryBudget,
    SNetMeshReceipt,
    SNetMetadata,
    SNetOntologyStatus,
    SNetQuestion,
    SNetRelation,
    SNetSettlementState,
    SNetSymbol,
    SNetTickStatus,
    SNetTickResult,
    SNetUnknown,
    SNetValidationState,
    SNetWHType,
    WH_TYPES,
)
from mcoi_runtime.snet.engine import SNetRecursiveMesh, map_wh_to_facet
from mcoi_runtime.snet.read_model import build_snet_operator_read_model, create_snet_mesh_receipt


def test_wh_tick_generates_required_questions() -> None:
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")

    tick = mesh.generate_wh_tick(seed.symbol_id)

    assert tick.status is SNetTickStatus.RAN
    assert len(tick.generated_question_ids) == len(WH_TYPES) == 14
    assert {mesh.questions[question_id].wh_type for question_id in tick.generated_question_ids} == set(WH_TYPES)
    assert mesh.questions[tick.generated_question_ids[0]].text == "What is Seed?"
    assert map_wh_to_facet(SNetWHType.DEPENDS_ON) == "upstream_dependency"
    assert len(mesh.symbols[seed.symbol_id].inquiry_history) == 14


def test_promotion_gate_preserves_context_and_blocks_unknowns() -> None:
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")

    tick = mesh.run_tick_with_answers(
        seed.symbol_id,
        {
            SNetWHType.WHAT: "unknown",
            SNetWHType.WHICH: "brown",
            SNetWHType.DEPENDS_ON: "Water",
            SNetWHType.DEPENDS_ON_ME: "Future plant",
        },
    )
    promoted_labels = {mesh.symbols[symbol_id].label for symbol_id in tick.promoted_symbol_ids}
    promoted_contexts = {mesh.symbols[symbol_id].parent_context for symbol_id in tick.promoted_symbol_ids}
    relation_types = {
        mesh.relations[relation_id].relation_type
        for relation_id in mesh.symbols[seed.symbol_id].relation_refs
    }

    assert "water" in promoted_labels
    assert "future plant" in promoted_labels
    assert "unknown" not in promoted_labels
    assert "brown" not in promoted_labels
    assert any(context.startswith("Seed:upstream_dependency:water") for context in promoted_contexts)
    assert {"upstream_dependency", "downstream_dependency"}.issubset(relation_types)
    assert len(tick.unknown_ids) >= 1


def test_contextual_contradiction_is_recorded_instead_of_deleting_claims() -> None:
    mesh = SNetRecursiveMesh()
    fire = mesh.add_symbol("Fire", symbol_type="physical_process")

    controlled_tick = mesh.run_tick_with_answers(
        fire.symbol_id,
        {SNetWHType.WHY: "Controlled warmth helps seed germination"},
        context="controlled cooking heat",
    )
    uncontrolled_tick = mesh.run_tick_with_answers(
        fire.symbol_id,
        {SNetWHType.WHY: "Uncontrolled fire destroys seed structure"},
        context="uncontrolled burning heat",
    )
    contradiction = mesh.contradictions[uncontrolled_tick.contradiction_ids[0]]

    assert len(controlled_tick.metadata_ids) == 1
    assert len(uncontrolled_tick.metadata_ids) == 1
    assert contradiction.resolution_state is SNetContradictionState.CONTEXTUAL_DUALITY
    assert contradiction.context_a == "controlled cooking heat"
    assert contradiction.context_b == "uncontrolled burning heat"
    assert len(mesh.metadata) == 2


def test_perspective_isolation_keeps_same_label_senses_separate() -> None:
    mesh = SNetRecursiveMesh()
    biological_seed = mesh.add_symbol(
        "Seed",
        symbol_type="physical_biological_object",
        sense_id="seed#biological",
    )
    economic_seed = mesh.add_symbol(
        "Seed",
        symbol_type="economic_input",
        sense_id="seed#economic",
    )
    repeated_biological_seed = mesh.add_symbol(
        "Seed",
        symbol_type="physical_biological_object",
        sense_id="seed#biological",
    )
    matching_label_symbols = mesh.find_symbols_by_label("seed")

    assert biological_seed.symbol_id != economic_seed.symbol_id
    assert repeated_biological_seed.symbol_id == biological_seed.symbol_id
    assert {symbol.sense_id for symbol in matching_label_symbols} == {"seed#biological", "seed#economic"}
    assert len(matching_label_symbols) == 2


def test_recursive_expansion_stops_at_depth_budget() -> None:
    mesh = SNetRecursiveMesh(SNetInquiryBudget(max_depth=2))
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")

    def answers_for(symbol):
        if symbol.label == "Seed":
            return {SNetWHType.DEPENDS_ON: "Water"}
        if symbol.label == "water":
            return {SNetWHType.DEPENDS_ON: "Molecule"}
        if symbol.label == "molecule":
            return {SNetWHType.DEPENDS_ON: "Hydrogen"}
        return {}

    results = mesh.run_recursive(seed.symbol_id, answers_for)
    symbol_labels = {symbol.label for symbol in mesh.symbols.values()}
    depth_limit_results = [result for result in results if result.status is SNetTickStatus.DEPTH_LIMIT_REACHED]

    assert "water" in symbol_labels
    assert "molecule" in symbol_labels
    assert "hydrogen" not in symbol_labels
    assert max(symbol.depth for symbol in mesh.symbols.values()) == 2
    assert len(depth_limit_results) == 0
    assert mesh.symbols[seed.symbol_id].settlement_state is SNetSettlementState.UNKNOWN_HEAVY


def test_operator_read_model_is_bounded_and_hides_raw_answers() -> None:
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    mesh.run_tick_with_answers(
        seed.symbol_id,
        {
            SNetWHType.DEPENDS_ON: "Water",
            SNetWHType.DEPENDS_ON_ME: "Future plant",
        },
    )

    projection = build_snet_operator_read_model(mesh, max_symbol_count=1)
    receipt = projection["receipt"]
    selected_symbol = projection["selected_symbols"][0]

    assert projection["surface"] == "read_only_snet_recursive_mesh"
    assert projection["raw_answers_exposed"] is False
    assert projection["raw_metadata_values_exposed"] is False
    assert projection["execution_authority_granted"] is False
    assert projection["connector_authority_granted"] is False
    assert projection["route_authority_granted"] is False
    assert projection["filesystem_authority_granted"] is False
    assert "answers" not in projection
    assert "metadata_values" not in projection
    assert projection["symbol_count"] == 3
    assert projection["truncated_symbol_count"] == 2
    assert selected_symbol["label"] == "Seed"
    assert receipt["receipt_id"].startswith("snet-mesh-")
    assert receipt["evidence_refs"]


def test_operator_read_model_rejects_non_integer_symbol_bound() -> None:
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    mesh.run_tick_with_answers(seed.symbol_id, {SNetWHType.DEPENDS_ON: "Water"})

    with pytest.raises(ValueError, match="max_symbol_count"):
        build_snet_operator_read_model(mesh, max_symbol_count=1.5)
    with pytest.raises(ValueError, match="max_symbol_count"):
        build_snet_operator_read_model(mesh, max_symbol_count=True)
    assert build_snet_operator_read_model(mesh, max_symbol_count=0)["selected_symbols"] == []


def test_mesh_receipt_is_deterministic_for_same_state() -> None:
    first_mesh = SNetRecursiveMesh()
    second_mesh = SNetRecursiveMesh()
    for mesh in (first_mesh, second_mesh):
        seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
        mesh.run_tick_with_answers(seed.symbol_id, {SNetWHType.DEPENDS_ON: "Water"})

    first_receipt = create_snet_mesh_receipt(first_mesh)
    second_receipt = create_snet_mesh_receipt(second_mesh)

    assert first_receipt.receipt_id == second_receipt.receipt_id
    assert first_receipt.mesh_digest == second_receipt.mesh_digest
    assert first_receipt.to_json() == second_receipt.to_json()
    assert first_receipt.raw_answers_exposed is False
    assert first_receipt.raw_metadata_values_exposed is False
    assert first_receipt.execution_authority_granted is False
    assert first_receipt.connector_authority_granted is False
    assert first_receipt.route_authority_granted is False
    assert first_receipt.filesystem_authority_granted is False


def test_mesh_receipt_changes_for_different_same_count_mesh_state() -> None:
    first_mesh = SNetRecursiveMesh()
    second_mesh = SNetRecursiveMesh()
    first_seed = first_mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    second_seed = second_mesh.add_symbol("Root", symbol_type="physical_biological_object")
    first_mesh.run_tick_with_answers(first_seed.symbol_id, {SNetWHType.DEPENDS_ON: "Water"})
    second_mesh.run_tick_with_answers(second_seed.symbol_id, {SNetWHType.DEPENDS_ON: "Light"})

    first_receipt = create_snet_mesh_receipt(first_mesh)
    second_receipt = create_snet_mesh_receipt(second_mesh)

    assert first_receipt.symbol_count == second_receipt.symbol_count
    assert first_receipt.question_count == second_receipt.question_count
    assert first_receipt.metadata_count == second_receipt.metadata_count
    assert first_receipt.mesh_digest != second_receipt.mesh_digest
    assert first_receipt.receipt_id != second_receipt.receipt_id
    assert any(ref == f"snet:mesh_digest:{first_receipt.mesh_digest}" for ref in first_receipt.evidence_refs)


def test_budget_rejects_zero_question_and_zero_unknown_threshold() -> None:
    class IntSubclass(int):
        pass

    class FloatSubclass(float):
        pass

    with pytest.raises(ValueError, match="max_questions_per_symbol"):
        SNetInquiryBudget(max_questions_per_symbol=0)
    with pytest.raises(ValueError, match="finite SNet WH spine"):
        SNetInquiryBudget(max_questions_per_symbol=len(WH_TYPES) + 1)
    with pytest.raises(ValueError, match="unknown_gravity_threshold"):
        SNetInquiryBudget(unknown_gravity_threshold=0)
    with pytest.raises(ValueError, match="max_depth"):
        SNetInquiryBudget(max_depth=IntSubclass(1))
    with pytest.raises(ValueError, match="promotion_threshold"):
        SNetInquiryBudget(promotion_threshold=FloatSubclass(0.5))
    assert SNetInquiryBudget(max_questions_per_symbol=1, unknown_gravity_threshold=1).max_questions_per_symbol == 1
    assert SNetInquiryBudget(max_depth=1, promotion_threshold=0.5).promotion_threshold == 0.5


def test_mesh_constructor_rejects_budget_shape_drift() -> None:
    class BudgetSubclass(SNetInquiryBudget):
        pass

    exact_budget = SNetInquiryBudget(max_depth=1)
    default_mesh = SNetRecursiveMesh(None)
    exact_mesh = SNetRecursiveMesh(exact_budget)

    assert default_mesh.budget == SNetInquiryBudget()
    assert exact_mesh.budget is exact_budget
    assert exact_mesh.budget.max_depth == 1

    for invalid_budget in (0, False, object(), {"max_depth": 1}, BudgetSubclass(max_depth=1)):
        with pytest.raises(ValueError, match="SNet budget"):
            SNetRecursiveMesh(invalid_budget)  # type: ignore[arg-type]


def test_answer_map_rejects_shape_drift_and_empty_wh_answers() -> None:
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")

    class DictSubclass(dict):
        pass

    class CustomAnswerMap(Mapping):
        def __getitem__(self, key):
            if key is SNetWHType.DEPENDS_ON:
                return "Water"
            raise KeyError(key)

        def __iter__(self):
            return iter((SNetWHType.DEPENDS_ON,))

        def __len__(self):
            return 1

        def items(self):
            return ((SNetWHType.DEPENDS_ON, "Water"),)

    class RaisingItems(dict):
        def items(self):
            raise RuntimeError("items leak")

    class TextSubclass(str):
        pass

    for invalid_answer_map in (
        DictSubclass({SNetWHType.DEPENDS_ON: "Water"}),
        CustomAnswerMap(),
        RaisingItems({SNetWHType.DEPENDS_ON: "Water"}),
        MappingProxyType(RaisingItems({SNetWHType.DEPENDS_ON: "Water"})),
    ):
        with pytest.raises(ValueError, match="answer_map must be a mapping"):
            mesh.run_tick_with_answers(seed.symbol_id, invalid_answer_map)

    second_mesh = SNetRecursiveMesh()
    second_seed = second_mesh.add_symbol("Second seed", symbol_type="physical_biological_object")
    with pytest.raises(ValueError, match="must be a non-empty string"):
        second_mesh.run_tick_with_answers(second_seed.symbol_id, {SNetWHType.WHAT: "   "})
    with pytest.raises(ValueError, match="no leading or trailing whitespace"):
        second_mesh.run_tick_with_answers(second_seed.symbol_id, {SNetWHType.WHAT: " Seed"})
    with pytest.raises(ValueError, match="no leading or trailing whitespace"):
        second_mesh.run_tick_with_answers(second_seed.symbol_id, {SNetWHType.WHAT: "Seed "})
    with pytest.raises(ValueError, match="WH answer key"):
        second_mesh.run_tick_with_answers(second_seed.symbol_id, {TextSubclass("what"): "Seed"})
    with pytest.raises(ValueError, match="must be a non-empty string"):
        second_mesh.run_tick_with_answers(second_seed.symbol_id, {SNetWHType.WHAT: TextSubclass("Seed")})

    valid_mesh = SNetRecursiveMesh()
    valid_seed = valid_mesh.add_symbol("Valid seed", symbol_type="physical_biological_object")
    valid_tick = valid_mesh.run_tick_with_answers(
        valid_seed.symbol_id,
        MappingProxyType({SNetWHType.DEPENDS_ON: "Water"}),
    )

    assert mesh.answers == {}
    assert mesh.questions == {}
    assert mesh.metadata == {}
    assert second_mesh.answers == {}
    assert second_mesh.questions == {}
    assert second_mesh.metadata == {}
    assert len(valid_tick.answer_ids) == 1
    assert len(valid_mesh.answers) == 1
    assert len(valid_mesh.metadata) == 1


def test_run_tick_rejects_invalid_confidence_and_state_before_mutation() -> None:
    confidence_mesh = SNetRecursiveMesh()
    confidence_seed = confidence_mesh.add_symbol("Confidence seed", symbol_type="physical_biological_object")
    with pytest.raises(ValueError, match="SNet confidence"):
        confidence_mesh.run_tick_with_answers(confidence_seed.symbol_id, {SNetWHType.WHAT: "Seed"}, confidence=1.2)

    state_mesh = SNetRecursiveMesh()
    state_seed = state_mesh.add_symbol("State seed", symbol_type="physical_biological_object")
    with pytest.raises(ValueError, match="validation_state"):
        state_mesh.run_tick_with_answers(state_seed.symbol_id, {SNetWHType.WHAT: "Seed"}, validation_state="supported")

    map_mesh = SNetRecursiveMesh()
    map_seed = map_mesh.add_symbol("Map seed", symbol_type="physical_biological_object")
    with pytest.raises(ValueError, match="answer_map must be a mapping"):
        map_mesh.run_tick_with_answers(map_seed.symbol_id, [(SNetWHType.WHAT, "Seed")])

    assert confidence_mesh.questions == {}
    assert state_mesh.questions == {}
    assert map_mesh.questions == {}


def test_direct_answer_and_score_validation_fail_closed() -> None:
    class TextSubclass(str):
        pass

    class IntSubclass(int):
        pass

    class FloatSubclass(float):
        pass

    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    tick = mesh.generate_wh_tick(seed.symbol_id)
    question_id = tick.generated_question_ids[0]

    with pytest.raises(ValueError, match="raw_answer"):
        mesh.ingest_answer(question_id, "   ")
    with pytest.raises(ValueError, match="raw_answer"):
        mesh.ingest_answer(question_id, " Seed")
    with pytest.raises(ValueError, match="raw_answer"):
        mesh.ingest_answer(question_id, TextSubclass("Seed"))
    with pytest.raises(ValueError, match="validation_state"):
        mesh.ingest_answer(question_id, "Seed", validation_state="supported")
    with pytest.raises(ValueError, match="SNet confidence"):
        mesh.score_metadata(
            facet="identity",
            ascii_folded_value="seed",
            confidence=float("nan"),
            validation_state=SNetValidationState.SUPPORTED,
        )
    with pytest.raises(ValueError, match="SNet confidence"):
        mesh.ingest_answer(question_id, "Seed", confidence=IntSubclass(1))
    with pytest.raises(ValueError, match="SNet confidence"):
        mesh.ingest_answer(question_id, "Seed", confidence=FloatSubclass(0.5))
    with pytest.raises(ValueError, match="SNet confidence"):
        mesh.score_metadata(
            facet="identity",
            ascii_folded_value="seed",
            confidence=IntSubclass(1),
            validation_state=SNetValidationState.SUPPORTED,
        )
    with pytest.raises(ValueError, match="facet"):
        mesh.score_metadata(
            facet=TextSubclass("identity"),
            ascii_folded_value="seed",
            confidence=0.5,
            validation_state=SNetValidationState.SUPPORTED,
        )
    with pytest.raises(ValueError, match="ascii_folded_value"):
        mesh.score_metadata(
            facet="identity",
            ascii_folded_value=TextSubclass("seed"),
            confidence=0.5,
            validation_state=SNetValidationState.SUPPORTED,
        )

    assert mesh.answers == {}
    assert mesh.metadata == {}
    assert mesh.questions[question_id].question_id == question_id


def test_runtime_id_lookups_reject_shape_drift_before_mutation() -> None:
    class TextSubclass(str):
        pass

    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    tick = mesh.generate_wh_tick(seed.symbol_id)
    question_id = tick.generated_question_ids[0]
    answer = mesh.ingest_answer(
        question_id,
        "Seed",
        confidence=0.8,
        validation_state=SNetValidationState.SUPPORTED,
    )
    metadata = mesh.extract_metadata(question_id, answer.answer_id)
    before_state = (
        len(mesh.questions),
        len(mesh.answers),
        len(mesh.metadata),
        len(mesh.relations),
        mesh.symbols[seed.symbol_id].settlement_state,
    )

    with pytest.raises(ValueError, match="symbol_id"):
        mesh.generate_wh_tick(TextSubclass(seed.symbol_id))
    with pytest.raises(ValueError, match="symbol_id"):
        mesh.generate_wh_tick(1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="symbol_id"):
        mesh.generate_wh_tick(f" {seed.symbol_id}")
    with pytest.raises(ValueError, match="question_id"):
        mesh.ingest_answer(TextSubclass(question_id), "Seed")
    with pytest.raises(ValueError, match="question_id"):
        mesh.ingest_answer(1, "Seed")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="question_id"):
        mesh.extract_metadata(TextSubclass(question_id), answer.answer_id)
    with pytest.raises(ValueError, match="answer_id"):
        mesh.extract_metadata(question_id, TextSubclass(answer.answer_id))
    with pytest.raises(ValueError, match="metadata_id"):
        mesh.promote_metadata(TextSubclass(metadata.metadata_id))
    with pytest.raises(ValueError, match="symbol_id"):
        mesh.settle_symbol(TextSubclass(seed.symbol_id))

    after_state = (
        len(mesh.questions),
        len(mesh.answers),
        len(mesh.metadata),
        len(mesh.relations),
        mesh.symbols[seed.symbol_id].settlement_state,
    )

    assert after_state == before_state
    assert mesh.answers == {answer.answer_id: answer}
    assert mesh.metadata == {metadata.metadata_id: metadata}


def test_duplicate_symbol_revalidates_non_identity_fields_before_index_return() -> None:
    class IntSubclass(int):
        pass

    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol(
        "Seed",
        symbol_type="physical_biological_object",
        ontology_status=SNetOntologyStatus.PHYSICAL_REAL,
        depth=0,
    )
    before_symbol_ids = set(mesh.symbols)
    before_identity_index = dict(mesh._symbol_identity_index)

    invalid_symbol_specs = (
        {"ontology_status": SNetOntologyStatus.PHYSICAL_REAL, "depth": -1, "match": "depth"},
        {"ontology_status": SNetOntologyStatus.PHYSICAL_REAL, "depth": False, "match": "depth"},
        {"ontology_status": SNetOntologyStatus.PHYSICAL_REAL, "depth": IntSubclass(0), "match": "depth"},
        {"ontology_status": "physical_real", "depth": 0, "match": "ontology_status"},
    )

    for invalid_spec in invalid_symbol_specs:
        with pytest.raises(ValueError, match=invalid_spec["match"]):
            mesh.add_symbol(
                "Seed",
                symbol_type="physical_biological_object",
                ontology_status=invalid_spec["ontology_status"],
                depth=invalid_spec["depth"],
            )

    duplicate = mesh.add_symbol(
        "Seed",
        symbol_type="physical_biological_object",
        ontology_status=SNetOntologyStatus.PHYSICAL_REAL,
        depth=0,
    )

    assert duplicate.symbol_id == seed.symbol_id
    assert set(mesh.symbols) == before_symbol_ids
    assert mesh._symbol_identity_index == before_identity_index


def test_extract_metadata_rejects_answer_question_mismatch_before_mutation() -> None:
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    tick = mesh.generate_wh_tick(seed.symbol_id)
    answer_question_id, mismatched_question_id = tick.generated_question_ids[:2]
    answer = mesh.ingest_answer(
        answer_question_id,
        "Seed answer",
        confidence=0.8,
        validation_state=SNetValidationState.SUPPORTED,
    )
    before_symbol = mesh.symbols[seed.symbol_id]
    before_metadata = dict(mesh.metadata)

    with pytest.raises(ValueError, match="answer_id must belong"):
        mesh.extract_metadata(mismatched_question_id, answer.answer_id)

    assert mesh.metadata == before_metadata
    assert mesh.symbols[seed.symbol_id] == before_symbol
    assert mesh.answers == {answer.answer_id: answer}


def test_parent_question_id_must_exist_before_wh_tick_mutation() -> None:
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    before_symbol = mesh.symbols[seed.symbol_id]

    with pytest.raises(KeyError, match="unknown SNet question_id"):
        mesh.generate_wh_tick(seed.symbol_id, parent_question_id="snet-question:missing")

    assert mesh.questions == {}
    assert mesh.symbols[seed.symbol_id] == before_symbol
    assert mesh.symbols[seed.symbol_id].inquiry_history == ()

    parent_tick = mesh.generate_wh_tick(seed.symbol_id, perspective="root")
    parent_question_id = parent_tick.generated_question_ids[0]
    child_tick = mesh.generate_wh_tick(
        seed.symbol_id,
        perspective="child",
        parent_question_id=parent_question_id,
    )

    assert child_tick.status is SNetTickStatus.RAN
    assert mesh.questions[child_tick.generated_question_ids[0]].parent_question_id == parent_question_id
    assert parent_question_id in mesh.questions


def test_parent_question_id_must_match_symbol_causal_scope() -> None:
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    unrelated_root = mesh.add_symbol("Unrelated root", symbol_type="physical_biological_object")
    seed_tick = mesh.generate_wh_tick(seed.symbol_id, perspective="seed")
    parent_question_id = seed_tick.generated_question_ids[0]
    before_question_count = len(mesh.questions)
    before_unrelated_root = mesh.symbols[unrelated_root.symbol_id]

    with pytest.raises(ValueError, match="parent_question_id must belong"):
        mesh.generate_wh_tick(
            unrelated_root.symbol_id,
            perspective="unrelated",
            parent_question_id=parent_question_id,
        )

    assert len(mesh.questions) == before_question_count
    assert mesh.symbols[unrelated_root.symbol_id] == before_unrelated_root
    assert mesh.symbols[unrelated_root.symbol_id].inquiry_history == ()

    depends_on_question_id = next(
        question_id
        for question_id in seed_tick.generated_question_ids
        if mesh.questions[question_id].wh_type is SNetWHType.DEPENDS_ON
    )
    answer = mesh.ingest_answer(
        depends_on_question_id,
        "Water",
        confidence=0.8,
        validation_state=SNetValidationState.SUPPORTED,
    )
    metadata = mesh.extract_metadata(depends_on_question_id, answer.answer_id)
    promoted_child = mesh.promote_metadata(metadata.metadata_id)

    assert promoted_child is not None
    assert promoted_child.created_from_metadata_id == metadata.metadata_id

    child_tick = mesh.generate_wh_tick(
        promoted_child.symbol_id,
        perspective="promoted-child",
        parent_question_id=depends_on_question_id,
    )

    assert child_tick.status is SNetTickStatus.RAN
    assert mesh.questions[child_tick.generated_question_ids[0]].parent_question_id == depends_on_question_id
    assert mesh.metadata[promoted_child.created_from_metadata_id].question_id == depends_on_question_id


def test_created_from_metadata_id_must_exist_before_symbol_mutation() -> None:
    mesh = SNetRecursiveMesh()

    with pytest.raises(KeyError, match="unknown SNet metadata_id"):
        mesh.add_symbol("Forged child", created_from_metadata_id="snet-metadata:missing")

    assert mesh.symbols == {}
    assert mesh._symbol_identity_index == {}

    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    tick = mesh.generate_wh_tick(seed.symbol_id)
    question_id = next(
        question_id
        for question_id in tick.generated_question_ids
        if mesh.questions[question_id].wh_type is SNetWHType.DEPENDS_ON
    )
    answer = mesh.ingest_answer(
        question_id,
        "Water",
        confidence=0.8,
        validation_state=SNetValidationState.SUPPORTED,
    )
    metadata = mesh.extract_metadata(question_id, answer.answer_id)
    promoted_child = mesh.promote_metadata(metadata.metadata_id)

    assert promoted_child is not None
    assert promoted_child.created_from_metadata_id == metadata.metadata_id
    assert mesh.metadata[metadata.metadata_id].promoted_symbol_id == promoted_child.symbol_id


def test_created_from_metadata_id_must_match_promoted_symbol_semantics() -> None:
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    tick = mesh.generate_wh_tick(seed.symbol_id)
    question_id = next(
        question_id
        for question_id in tick.generated_question_ids
        if mesh.questions[question_id].wh_type is SNetWHType.DEPENDS_ON
    )
    answer = mesh.ingest_answer(
        question_id,
        "Water",
        confidence=0.8,
        validation_state=SNetValidationState.SUPPORTED,
    )
    metadata = mesh.extract_metadata(question_id, answer.answer_id)
    expected_parent_context = f"{seed.label}:{metadata.facet}:{metadata.value}"
    before_symbol_ids = set(mesh.symbols)
    before_identity_index = dict(mesh._symbol_identity_index)

    invalid_symbol_specs = (
        {"label": "Fire", "symbol_type": "promoted_metadata", "parent_context": expected_parent_context, "depth": 1},
        {"label": metadata.value, "symbol_type": "unknown", "parent_context": expected_parent_context, "depth": 1},
        {"label": metadata.value, "symbol_type": "promoted_metadata", "parent_context": "Seed:wrong:water", "depth": 1},
        {"label": metadata.value, "symbol_type": "promoted_metadata", "parent_context": expected_parent_context, "depth": 0},
    )

    for invalid_spec in invalid_symbol_specs:
        with pytest.raises(ValueError, match="created_from_metadata_id must match"):
            mesh.add_symbol(
                invalid_spec["label"],
                symbol_type=invalid_spec["symbol_type"],
                parent_context=invalid_spec["parent_context"],
                created_from_metadata_id=metadata.metadata_id,
                depth=invalid_spec["depth"],
            )

    assert set(mesh.symbols) == before_symbol_ids
    assert mesh._symbol_identity_index == before_identity_index
    assert mesh.metadata[metadata.metadata_id].promoted_symbol_id == ""

    promoted_child = mesh.promote_metadata(metadata.metadata_id)

    assert promoted_child is not None
    assert promoted_child.label == metadata.value
    assert promoted_child.symbol_type == "promoted_metadata"
    assert promoted_child.parent_context == expected_parent_context
    assert promoted_child.depth == seed.depth + 1


def test_case_distinct_raw_answers_do_not_silently_overwrite() -> None:
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    tick = mesh.generate_wh_tick(seed.symbol_id)
    question_id = tick.generated_question_ids[0]

    upper_answer = mesh.ingest_answer(
        question_id,
        "Seed",
        confidence=0.8,
        validation_state=SNetValidationState.SUPPORTED,
    )
    lower_answer = mesh.ingest_answer(
        question_id,
        "seed",
        confidence=0.8,
        validation_state=SNetValidationState.SUPPORTED,
    )
    upper_metadata = mesh.extract_metadata(question_id, upper_answer.answer_id)
    lower_metadata = mesh.extract_metadata(question_id, lower_answer.answer_id)

    assert upper_answer.answer_id != lower_answer.answer_id
    assert upper_answer.raw_answer == "Seed"
    assert lower_answer.raw_answer == "seed"
    assert upper_answer.ascii_folded_answer == lower_answer.ascii_folded_answer == "seed"
    assert upper_metadata.metadata_id != lower_metadata.metadata_id
    assert len(mesh.answers) == 2
    assert len(mesh.metadata) == 2


def test_direct_text_inputs_fail_with_explicit_errors() -> None:
    class TextSubclass(str):
        pass

    class AlwaysEqualToEmpty:
        def __eq__(self, other: object) -> bool:
            raise AssertionError("optional text validation must not compare before type validation")

    class RaisingEquality:
        def __eq__(self, other: object) -> bool:
            raise RuntimeError("comparison leak")

    mesh = SNetRecursiveMesh()
    with pytest.raises(ValueError, match="label"):
        mesh.add_symbol(123)
    with pytest.raises(ValueError, match="label"):
        mesh.add_symbol(TextSubclass("Seed"))
    with pytest.raises(ValueError, match="label"):
        mesh.add_symbol(SNetWHType.WHAT)
    with pytest.raises(ValueError, match="sense_id"):
        mesh.add_symbol("Seed", sense_id=0)
    with pytest.raises(ValueError, match="sense_id"):
        mesh.add_symbol("Seed", sense_id=AlwaysEqualToEmpty())
    with pytest.raises(ValueError, match="sense_id"):
        mesh.add_symbol("Seed", sense_id=RaisingEquality())
    with pytest.raises(ValueError, match="created_from_metadata_id"):
        mesh.add_symbol("Seed", created_from_metadata_id=None)
    assert mesh.symbols == {}

    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    with pytest.raises(ValueError, match="SNet text value"):
        mesh.find_symbols_by_label(123)
    with pytest.raises(ValueError, match="perspective"):
        mesh.generate_wh_tick(seed.symbol_id, perspective="")
    with pytest.raises(ValueError, match="context"):
        mesh.generate_wh_tick(seed.symbol_id, context=123)
    with pytest.raises(ValueError, match="context"):
        mesh.generate_wh_tick(seed.symbol_id, context=TextSubclass("general"))
    with pytest.raises(ValueError, match="parent_question_id"):
        mesh.generate_wh_tick(seed.symbol_id, parent_question_id=0)
    with pytest.raises(ValueError, match="parent_question_id"):
        mesh.generate_wh_tick(seed.symbol_id, parent_question_id=RaisingEquality())
    with pytest.raises(ValueError, match="facet"):
        mesh.score_metadata(
            facet="",
            ascii_folded_value="seed",
            confidence=0.5,
            validation_state=SNetValidationState.SUPPORTED,
        )
    with pytest.raises(ValueError, match="ascii_folded_value"):
        mesh.score_metadata(
            facet="identity",
            ascii_folded_value="",
            confidence=0.5,
            validation_state=SNetValidationState.SUPPORTED,
        )

    assert seed.symbol_id in mesh.symbols
    assert mesh.questions == {}
    assert mesh.answers == {}


def test_direct_snet_contracts_reject_numeric_shape_drift() -> None:
    class IntSubclass(int):
        pass

    class FloatSubclass(float):
        pass

    with pytest.raises(ValueError, match="depth"):
        SNetSymbol(symbol_id="symbol:1", label="Seed", depth=IntSubclass(1))
    with pytest.raises(ValueError, match="confidence"):
        SNetAnswer(
            answer_id="answer:1",
            question_id="question:1",
            raw_answer="Seed",
            ascii_folded_answer="seed",
            confidence=FloatSubclass(0.5),
        )
    with pytest.raises(ValueError, match="promotion_score"):
        SNetMetadata(
            metadata_id="metadata:1",
            parent_symbol_id="symbol:1",
            question_id="question:1",
            answer_id="answer:1",
            facet="identity",
            value="Seed",
            context="general",
            perspective="general",
            confidence=0.5,
            validation_state=SNetValidationState.SUPPORTED,
            promotion_score=FloatSubclass(0.5),
        )
    with pytest.raises(ValueError, match="importance_score"):
        SNetUnknown(
            unknown_id="unknown:1",
            symbol_id="symbol:1",
            missing_facet="identity",
            question_id="question:1",
            importance_score=FloatSubclass(0.5),
            blocking_reason="answer_missing",
        )

    valid_symbol = SNetSymbol(symbol_id="symbol:2", label="Seed", depth=1)
    valid_answer = SNetAnswer(
        answer_id="answer:2",
        question_id="question:2",
        raw_answer="Seed",
        ascii_folded_answer="seed",
        confidence=0.5,
    )

    assert valid_symbol.depth == 1
    assert valid_answer.confidence == 0.5


def test_evidence_refs_require_tuple_without_partial_answer_mutation() -> None:
    class TextSubclass(str):
        pass

    class TupleSubclass(tuple):
        pass

    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    tick = mesh.generate_wh_tick(seed.symbol_id)
    question_id = tick.generated_question_ids[0]

    with pytest.raises(ValueError, match="evidence_refs"):
        mesh.ingest_answer(question_id, "Seed", evidence_refs="evidence:1")
    with pytest.raises(ValueError, match="evidence_refs"):
        mesh.ingest_answer(question_id, "Seed", evidence_refs=("",))
    with pytest.raises(ValueError, match="evidence_refs"):
        mesh.ingest_answer(question_id, "Seed", evidence_refs=TupleSubclass(("evidence:1",)))
    with pytest.raises(ValueError, match="evidence_refs"):
        mesh.ingest_answer(question_id, "Seed", evidence_refs=(TextSubclass("evidence:1"),))
    with pytest.raises(ValueError, match="evidence_refs"):
        mesh.ingest_answer(question_id, "Seed", evidence_refs=(" evidence:1",))
    answer = mesh.ingest_answer(question_id, "Seed", evidence_refs=("evidence:1",))

    assert mesh.answers == {answer.answer_id: answer}
    assert answer.evidence_refs == ("evidence:1",)
    assert mesh.metadata == {}


def test_duplicate_answer_id_rejects_evidence_ref_drift_without_overwrite() -> None:
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    tick = mesh.generate_wh_tick(seed.symbol_id)
    question_id = tick.generated_question_ids[0]
    original_answer = mesh.ingest_answer(question_id, "Seed", evidence_refs=("evidence:1",))
    before_answers = dict(mesh.answers)

    duplicate_answer = mesh.ingest_answer(question_id, "Seed", evidence_refs=("evidence:1",))

    assert duplicate_answer is original_answer
    assert mesh.answers == before_answers

    with pytest.raises(ValueError, match="duplicate answer_id cannot change answer evidence"):
        mesh.ingest_answer(question_id, "Seed", evidence_refs=("evidence:2",))

    assert mesh.answers == before_answers
    assert mesh.answers[original_answer.answer_id].evidence_refs == ("evidence:1",)
    assert mesh.metadata == {}


def test_direct_snet_contracts_reject_string_sequence_drift() -> None:
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    mesh.run_tick_with_answers(seed.symbol_id, {SNetWHType.DEPENDS_ON: "Water"})
    receipt_payload = create_snet_mesh_receipt(mesh).to_json_dict()

    with pytest.raises(ValueError, match="metadata_refs"):
        SNetSymbol(symbol_id="symbol:1", label="Seed", metadata_refs="metadata:1")
    with pytest.raises(ValueError, match="metadata_refs"):
        SNetSymbol(symbol_id="symbol:1", label="Seed", metadata_refs=(" metadata:1",))
    with pytest.raises(ValueError, match="evidence_refs"):
        SNetAnswer(
            answer_id="answer:1",
            question_id="question:1",
            raw_answer="Seed",
            ascii_folded_answer="seed",
            confidence=0.5,
            evidence_refs="evidence:1",
        )
    with pytest.raises(ValueError, match="evidence_refs"):
        SNetAnswer(
            answer_id="answer:1",
            question_id="question:1",
            raw_answer="Seed",
            ascii_folded_answer="seed",
            confidence=0.5,
            evidence_refs=(" evidence:1",),
        )
    with pytest.raises(ValueError, match="evidence_refs"):
        SNetMetadata(
            metadata_id="metadata:1",
            parent_symbol_id="symbol:1",
            question_id="question:1",
            answer_id="answer:1",
            facet="identity",
            value="Seed",
            context="general",
            perspective="general",
            confidence=0.5,
            validation_state=SNetValidationState.SUPPORTED,
            evidence_refs="evidence:1",
        )
    with pytest.raises(ValueError, match="evidence_refs"):
        SNetRelation(
            relation_id="relation:1",
            source_symbol_id="symbol:1",
            relation_type="upstream_dependency",
            target_symbol_id="symbol:2",
            confidence=0.5,
            context="general",
            perspective="general",
            evidence_refs="evidence:1",
        )
    with pytest.raises(ValueError, match="generated_question_ids"):
        SNetTickResult(
            tick_id="tick:1",
            symbol_id="symbol:1",
            status=SNetTickStatus.RAN,
            generated_question_ids="question:1",
        )
    with pytest.raises(ValueError, match="evidence_refs"):
        SNetMeshReceipt(**{**receipt_payload, "evidence_refs": "snet:mesh_digest:sha256:" + "a" * 64})

    assert receipt_payload["evidence_refs"]
    assert SNetSymbol(symbol_id="symbol:2", label="Seed", metadata_refs=["metadata:1"]).metadata_refs == (
        "metadata:1",
    )
    assert (
        SNetTickResult(
            tick_id="tick:2",
            symbol_id="symbol:2",
            status=SNetTickStatus.RAN,
            generated_question_ids=["question:1"],
        ).generated_question_ids
        == ("question:1",)
    )


def test_direct_snet_contracts_reject_sequence_subclass_drift() -> None:
    class ListSubclass(list):
        pass

    class TupleSubclass(tuple):
        pass

    class RaisingList(list):
        def __iter__(self):
            raise RuntimeError("iteration leak")

    for invalid_refs in (
        ListSubclass(["metadata:1"]),
        TupleSubclass(("metadata:1",)),
        RaisingList(["metadata:1"]),
    ):
        with pytest.raises(ValueError, match="metadata_refs"):
            SNetSymbol(symbol_id="symbol:1", label="Seed", metadata_refs=invalid_refs)

    for invalid_refs in (
        ListSubclass(["evidence:1"]),
        TupleSubclass(("evidence:1",)),
        RaisingList(["evidence:1"]),
    ):
        with pytest.raises(ValueError, match="evidence_refs"):
            SNetAnswer(
                answer_id="answer:1",
                question_id="question:1",
                raw_answer="Seed",
                ascii_folded_answer="seed",
                confidence=0.5,
                evidence_refs=invalid_refs,
            )

    valid_symbol = SNetSymbol(symbol_id="symbol:2", label="Seed", metadata_refs=["metadata:1"])
    valid_answer = SNetAnswer(
        answer_id="answer:2",
        question_id="question:2",
        raw_answer="Seed",
        ascii_folded_answer="seed",
        confidence=0.5,
        evidence_refs=["evidence:1"],
    )

    assert valid_symbol.metadata_refs == ("metadata:1",)
    assert valid_answer.evidence_refs == ("evidence:1",)
    assert valid_answer.raw_answer == "Seed"


def test_direct_snet_contracts_reject_map_key_shape_drift() -> None:
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    mesh.run_tick_with_answers(seed.symbol_id, {SNetWHType.DEPENDS_ON: "Water"})
    receipt_payload = create_snet_mesh_receipt(mesh).to_json_dict()
    enum_keyed_settlement_counts = dict(receipt_payload["settlement_counts"])
    active_count = enum_keyed_settlement_counts.pop("active")
    enum_keyed_settlement_counts[SNetSettlementState.ACTIVE] = active_count

    with pytest.raises(ValueError, match="metadata.key"):
        SNetSymbol(symbol_id="symbol:1", label="Seed", metadata={1: "numeric key"})
    with pytest.raises(ValueError, match="metadata.key"):
        SNetAnswer(
            answer_id="answer:1",
            question_id="question:1",
            raw_answer="Seed",
            ascii_folded_answer="seed",
            confidence=0.5,
            metadata={SNetWHType.WHAT: "enum key"},
        )
    with pytest.raises(ValueError, match="settlement_counts.key"):
        SNetMeshReceipt(**{**receipt_payload, "settlement_counts": enum_keyed_settlement_counts})

    valid_symbol = SNetSymbol(symbol_id="symbol:2", label="Seed", metadata={"source": "test"})
    valid_receipt = SNetMeshReceipt(**receipt_payload)

    assert valid_symbol.metadata["source"] == "test"
    assert set(valid_receipt.settlement_counts) == {state.value for state in SNetSettlementState}
    assert valid_receipt.symbol_count == receipt_payload["symbol_count"]


def test_direct_snet_contracts_reject_metadata_map_subclass_drift() -> None:
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    mesh.run_tick_with_answers(seed.symbol_id, {SNetWHType.DEPENDS_ON: "Water"})
    receipt_payload = create_snet_mesh_receipt(mesh).to_json_dict()

    class DictSubclass(dict):
        pass

    class MappingSubclass(Mapping):
        def __getitem__(self, key):
            if key == "source":
                return "test"
            raise KeyError(key)

        def __iter__(self):
            return iter(("source",))

        def __len__(self):
            return 1

        def items(self):
            return (("source", "test"),)

    class RaisingItems(dict):
        def items(self):
            raise RuntimeError("items leak")

    class ListSubclass(list):
        pass

    for invalid_metadata in (
        DictSubclass({"source": "test"}),
        MappingSubclass(),
        RaisingItems({"source": "test"}),
        MappingProxyType(RaisingItems({"source": "test"})),
    ):
        with pytest.raises(ValueError, match="metadata"):
            SNetSymbol(symbol_id="symbol:1", label="Seed", metadata=invalid_metadata)
        with pytest.raises(ValueError, match="metadata"):
            SNetAnswer(
                answer_id="answer:1",
                question_id="question:1",
                raw_answer="Seed",
                ascii_folded_answer="seed",
                confidence=0.5,
                metadata=invalid_metadata,
            )

    with pytest.raises(ValueError, match="metadata.outer"):
        SNetSymbol(symbol_id="symbol:2", label="Seed", metadata={"outer": DictSubclass({"inner": "ok"})})
    with pytest.raises(ValueError, match="metadata.items"):
        SNetSymbol(symbol_id="symbol:3", label="Seed", metadata={"items": ListSubclass(["ok"])})
    with pytest.raises(ValueError, match="settlement_counts must be a mapping"):
        SNetMeshReceipt(**{**receipt_payload, "settlement_counts": DictSubclass(receipt_payload["settlement_counts"])})

    valid_symbol = SNetSymbol(
        symbol_id="symbol:4",
        label="Seed",
        metadata={"outer": {"inner": "ok"}, "items": ["ok"]},
    )
    valid_receipt = SNetMeshReceipt(**receipt_payload)

    assert valid_symbol.metadata["outer"]["inner"] == "ok"
    assert valid_symbol.metadata["items"] == ("ok",)
    assert valid_receipt.settlement_counts["active"] == receipt_payload["settlement_counts"]["active"]


def test_mesh_receipt_rejects_settlement_counts_map_boundary_drift() -> None:
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    mesh.run_tick_with_answers(seed.symbol_id, {SNetWHType.DEPENDS_ON: "Water"})
    receipt_payload = create_snet_mesh_receipt(mesh).to_json_dict()

    class DuplicateSettlementCounts(Mapping):
        def __getitem__(self, key):
            return receipt_payload["settlement_counts"][key]

        def __iter__(self):
            keys = tuple(receipt_payload["settlement_counts"]) + ("active",)
            return iter(keys)

        def __len__(self):
            return len(receipt_payload["settlement_counts"]) + 1

    with pytest.raises(ValueError, match="settlement_counts must be a mapping"):
        SNetMeshReceipt(**{**receipt_payload, "settlement_counts": None})
    with pytest.raises(ValueError, match="settlement_counts must be a mapping"):
        SNetMeshReceipt(**{**receipt_payload, "settlement_counts": []})
    with pytest.raises(ValueError, match="settlement_counts must be a mapping"):
        SNetMeshReceipt(**{**receipt_payload, "settlement_counts": "active"})
    with pytest.raises(ValueError, match="settlement_counts must be a mapping"):
        SNetMeshReceipt(**{**receipt_payload, "settlement_counts": DuplicateSettlementCounts()})

    valid_receipt = SNetMeshReceipt(**receipt_payload)

    assert valid_receipt.settlement_counts["active"] == receipt_payload["settlement_counts"]["active"]
    assert sum(valid_receipt.settlement_counts.values()) == valid_receipt.symbol_count
    assert set(valid_receipt.settlement_counts) == {state.value for state in SNetSettlementState}


def test_direct_snet_contracts_reject_nested_metadata_key_shape_drift() -> None:
    with pytest.raises(ValueError, match="metadata.key"):
        SNetSymbol(symbol_id="symbol:1", label="Seed", metadata={" outer": "whitespace key"})
    with pytest.raises(ValueError, match="metadata.key"):
        SNetAnswer(
            answer_id="answer:1",
            question_id="question:1",
            raw_answer="Seed",
            ascii_folded_answer="seed",
            confidence=0.5,
            metadata={"outer ": "whitespace key"},
        )
    with pytest.raises(ValueError, match="metadata.outer.key"):
        SNetSymbol(symbol_id="symbol:1", label="Seed", metadata={"outer": {1: "numeric nested key"}})
    with pytest.raises(ValueError, match="metadata.outer.key"):
        SNetSymbol(symbol_id="symbol:1", label="Seed", metadata={"outer": {" inner": "whitespace nested key"}})
    with pytest.raises(ValueError, match="metadata.outer.key"):
        SNetAnswer(
            answer_id="answer:1",
            question_id="question:1",
            raw_answer="Seed",
            ascii_folded_answer="seed",
            confidence=0.5,
            metadata={"outer": {SNetWHType.WHAT: "enum nested key"}},
        )
    with pytest.raises(ValueError, match=r"metadata.items\[0\].key"):
        SNetSymbol(symbol_id="symbol:2", label="Seed", metadata={"items": [{1: "numeric list key"}]})

    valid_symbol = SNetSymbol(
        symbol_id="symbol:3",
        label="Seed",
        metadata={"outer": {"inner": "ok"}, "items": [{"key": "value"}]},
    )

    assert valid_symbol.metadata["outer"]["inner"] == "ok"
    assert valid_symbol.metadata["items"][0]["key"] == "value"
    assert tuple(valid_symbol.metadata) == ("items", "outer")


def test_direct_snet_contracts_reject_non_json_metadata_value_drift() -> None:
    with pytest.raises(ValueError, match="metadata.tags"):
        SNetSymbol(symbol_id="symbol:1", label="Seed", metadata={"tags": {"b", "a"}})
    with pytest.raises(ValueError, match="metadata.tags"):
        SNetSymbol(symbol_id="symbol:2", label="Seed", metadata={"tags": frozenset(("b", "a"))})
    with pytest.raises(ValueError, match="metadata.wh"):
        SNetAnswer(
            answer_id="answer:1",
            question_id="question:1",
            raw_answer="Seed",
            ascii_folded_answer="seed",
            confidence=0.5,
            metadata={"wh": SNetWHType.WHAT},
        )
    with pytest.raises(ValueError, match="metadata.opaque"):
        SNetSymbol(symbol_id="symbol:3", label="Seed", metadata={"opaque": object()})
    with pytest.raises(ValueError, match="metadata.score"):
        SNetSymbol(symbol_id="symbol:4", label="Seed", metadata={"score": float("nan")})
    with pytest.raises(ValueError, match=r"metadata.items\[0\]"):
        SNetSymbol(symbol_id="symbol:5", label="Seed", metadata={"items": [b"bytes"]})

    valid_symbol = SNetSymbol(
        symbol_id="symbol:6",
        label="Seed",
        metadata={"flags": [True, None, 3, 0.5, "ok"], "nested": {"score": 1}},
    )
    valid_metadata = valid_symbol.to_json_dict()["metadata"]

    assert valid_symbol.metadata["flags"] == (True, None, 3, 0.5, "ok")
    assert valid_metadata["flags"] == [True, None, 3, 0.5, "ok"]
    assert valid_metadata["nested"]["score"] == 1
    assert "\"metadata\":{\"flags\":[true,null,3,0.5,\"ok\"],\"nested\":{\"score\":1}}" in valid_symbol.to_json()


def test_direct_snet_contracts_reject_text_shape_drift() -> None:
    with pytest.raises(ValueError, match="label"):
        SNetSymbol(symbol_id="symbol:1", label=SNetWHType.WHAT)
    with pytest.raises(ValueError, match="sense_id"):
        SNetSymbol(symbol_id="symbol:1", label="Seed", sense_id=None)
    with pytest.raises(ValueError, match="parent_question_id"):
        SNetQuestion(
            question_id="question:1",
            target_symbol_id="symbol:1",
            wh_type=SNetWHType.WHAT,
            text="What is Seed?",
            facet="identity",
            parent_question_id=None,
        )
    with pytest.raises(ValueError, match="raw_answer"):
        SNetAnswer(
            answer_id="answer:1",
            question_id="question:1",
            raw_answer=SNetWHType.WHAT,
            ascii_folded_answer="what",
            confidence=0.5,
        )
    with pytest.raises(ValueError, match="raw_answer"):
        SNetAnswer(
            answer_id="answer:1",
            question_id="question:1",
            raw_answer=" Seed",
            ascii_folded_answer="seed",
            confidence=0.5,
        )
    with pytest.raises(ValueError, match="ascii_folded_answer"):
        SNetAnswer(
            answer_id="answer:1",
            question_id="question:1",
            raw_answer="Seed",
            ascii_folded_answer=" seed",
            confidence=0.5,
        )
    with pytest.raises(ValueError, match="promoted_symbol_id"):
        SNetMetadata(
            metadata_id="metadata:1",
            parent_symbol_id="symbol:1",
            question_id="question:1",
            answer_id="answer:1",
            facet="identity",
            value="Seed",
            context="general",
            perspective="general",
            confidence=0.5,
            validation_state=SNetValidationState.SUPPORTED,
            promoted_symbol_id=None,
        )

    valid_symbol = SNetSymbol(symbol_id="symbol:2", label="Seed", sense_id="", parent_context="")
    valid_question = SNetQuestion(
        question_id="question:2",
        target_symbol_id="symbol:2",
        wh_type=SNetWHType.WHAT,
        text="What is Seed?",
        facet="identity",
        parent_question_id="",
    )
    valid_metadata = SNetMetadata(
        metadata_id="metadata:2",
        parent_symbol_id="symbol:2",
        question_id="question:2",
        answer_id="answer:2",
        facet="identity",
        value="Seed",
        context="general",
        perspective="general",
        confidence=0.5,
        validation_state=SNetValidationState.SUPPORTED,
        promoted_symbol_id="",
    )

    assert valid_symbol.sense_id == ""
    assert valid_question.parent_question_id == ""
    assert valid_metadata.promoted_symbol_id == ""


def test_direct_snet_contracts_reject_identifier_whitespace_drift() -> None:
    with pytest.raises(ValueError, match="symbol_id"):
        SNetSymbol(symbol_id=" symbol:1", label="Seed")
    with pytest.raises(ValueError, match="created_from_metadata_id"):
        SNetSymbol(symbol_id="symbol:1", label="Seed", created_from_metadata_id=" metadata:1")
    with pytest.raises(ValueError, match="target_symbol_id"):
        SNetQuestion(
            question_id="question:1",
            target_symbol_id="symbol:1 ",
            wh_type=SNetWHType.WHAT,
            text="What is Seed?",
            facet="identity",
        )
    with pytest.raises(ValueError, match="question_id"):
        SNetAnswer(
            answer_id="answer:1",
            question_id=" question:1",
            raw_answer="Seed",
            ascii_folded_answer="seed",
            confidence=0.5,
        )
    with pytest.raises(ValueError, match="answer_id"):
        SNetMetadata(
            metadata_id="metadata:1",
            parent_symbol_id="symbol:1",
            question_id="question:1",
            answer_id="answer:1 ",
            facet="identity",
            value="Seed",
            context="general",
            perspective="general",
            confidence=0.5,
            validation_state=SNetValidationState.SUPPORTED,
        )
    with pytest.raises(ValueError, match="target_symbol_id"):
        SNetRelation(
            relation_id="relation:1",
            source_symbol_id="symbol:1",
            relation_type="identity",
            target_symbol_id=" symbol:2",
            confidence=0.5,
            context="general",
            perspective="general",
        )
    with pytest.raises(ValueError, match="question_id"):
        SNetUnknown(
            unknown_id="unknown:1",
            symbol_id="symbol:1",
            missing_facet="identity",
            question_id="question:1 ",
            importance_score=0.5,
            blocking_reason="missing answer",
        )
    with pytest.raises(ValueError, match="tick_id"):
        SNetTickResult(tick_id=" tick:1", symbol_id="symbol:1", status=SNetTickStatus.RAN)

    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    mesh.run_tick_with_answers(seed.symbol_id, {SNetWHType.DEPENDS_ON: "Water"})
    receipt_payload = create_snet_mesh_receipt(mesh).to_json_dict()

    with pytest.raises(ValueError, match="receipt_id"):
        SNetMeshReceipt(**{**receipt_payload, "receipt_id": f"{receipt_payload['receipt_id']} "})
    with pytest.raises(ValueError, match="mesh_digest"):
        SNetMeshReceipt(**{**receipt_payload, "mesh_digest": f" {receipt_payload['mesh_digest']}"})

    valid_symbol = SNetSymbol(symbol_id="symbol:2", label="Seed", created_from_metadata_id="metadata:2")
    valid_question = SNetQuestion(
        question_id="question:2",
        target_symbol_id="symbol:2",
        wh_type=SNetWHType.WHAT,
        text="What is Seed?",
        facet="identity",
        parent_question_id="question:1",
    )
    valid_tick = SNetTickResult(tick_id="tick:1", symbol_id="symbol:2", status=SNetTickStatus.RAN)

    assert valid_symbol.created_from_metadata_id == "metadata:2"
    assert valid_question.parent_question_id == "question:1"
    assert valid_tick.tick_id == "tick:1"


def test_direct_snet_contracts_reject_optional_text_comparison_drift() -> None:
    class AlwaysEqualToEmpty:
        def __eq__(self, other: object) -> bool:
            return True

    class RaisingEquality:
        def __eq__(self, other: object) -> bool:
            raise RuntimeError("comparison leak")

    for invalid_value in (AlwaysEqualToEmpty(), RaisingEquality()):
        with pytest.raises(ValueError, match="sense_id"):
            SNetSymbol(symbol_id="symbol:1", label="Seed", sense_id=invalid_value)
        with pytest.raises(ValueError, match="parent_question_id"):
            SNetQuestion(
                question_id="question:1",
                target_symbol_id="symbol:1",
                wh_type=SNetWHType.WHAT,
                text="What is Seed?",
                facet="identity",
                parent_question_id=invalid_value,
            )
        with pytest.raises(ValueError, match="promoted_symbol_id"):
            SNetMetadata(
                metadata_id="metadata:1",
                parent_symbol_id="symbol:1",
                question_id="question:1",
                answer_id="answer:1",
                facet="identity",
                value="Seed",
                context="general",
                perspective="general",
                confidence=0.5,
                validation_state=SNetValidationState.SUPPORTED,
                promoted_symbol_id=invalid_value,
            )

    valid_symbol = SNetSymbol(symbol_id="symbol:2", label="Seed", sense_id="")
    valid_question = SNetQuestion(
        question_id="question:2",
        target_symbol_id="symbol:2",
        wh_type=SNetWHType.WHAT,
        text="What is Seed?",
        facet="identity",
        parent_question_id="",
    )
    valid_metadata = SNetMetadata(
        metadata_id="metadata:2",
        parent_symbol_id="symbol:2",
        question_id="question:2",
        answer_id="answer:2",
        facet="identity",
        value="Seed",
        context="general",
        perspective="general",
        confidence=0.5,
        validation_state=SNetValidationState.SUPPORTED,
        promoted_symbol_id="",
    )

    assert valid_symbol.sense_id == ""
    assert valid_question.parent_question_id == ""
    assert valid_metadata.promoted_symbol_id == ""


def test_answer_map_rejects_unusable_answers_without_partial_mutation() -> None:
    budgeted_mesh = SNetRecursiveMesh(SNetInquiryBudget(max_questions_per_symbol=1))
    budgeted_seed = budgeted_mesh.add_symbol("Budgeted seed", symbol_type="physical_biological_object")
    with pytest.raises(ValueError, match="outside current question budget"):
        budgeted_mesh.run_tick_with_answers(budgeted_seed.symbol_id, {SNetWHType.DEPENDS_ON: "Water"})

    depth_mesh = SNetRecursiveMesh(SNetInquiryBudget(max_depth=0))
    depth_seed = depth_mesh.add_symbol("Depth seed", symbol_type="physical_biological_object")
    with pytest.raises(ValueError, match="depth-limited symbol"):
        depth_mesh.run_tick_with_answers(depth_seed.symbol_id, {SNetWHType.WHAT: "Seed"})

    duplicate_mesh = SNetRecursiveMesh()
    duplicate_seed = duplicate_mesh.add_symbol("Duplicate seed", symbol_type="physical_biological_object")
    duplicate_mesh.generate_wh_tick(duplicate_seed.symbol_id)
    with pytest.raises(ValueError, match="duplicate tick"):
        duplicate_mesh.run_tick_with_answers(duplicate_seed.symbol_id, {SNetWHType.WHAT: "Seed"})

    assert budgeted_mesh.questions == {}
    assert depth_mesh.questions == {}
    assert duplicate_mesh.answers == {}
    assert duplicate_mesh.metadata == {}


def test_mojibake_sequence_is_preserved_without_text_rewrite() -> None:
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("ሀ", symbol_type="mfidel_atomic_symbol")
    fidel_sequence = "ሀሁአ"

    tick = mesh.run_tick_with_answers(seed.symbol_id, {SNetWHType.DEPENDS_ON: fidel_sequence})
    answer = mesh.answers[tick.answer_ids[0]]
    metadata = mesh.metadata[tick.metadata_ids[0]]
    promoted_symbol = mesh.symbols[tick.promoted_symbol_ids[0]]

    assert answer.raw_answer == fidel_sequence
    assert answer.ascii_folded_answer == fidel_sequence
    assert metadata.value == fidel_sequence
    assert promoted_symbol.label == fidel_sequence


def test_mfidel_sequence_is_preserved_as_atomic_symbol_text() -> None:
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("ሀ", symbol_type="mfidel_atomic_symbol")
    fidel_sequence = "ሀሁአ"

    tick = mesh.run_tick_with_answers(seed.symbol_id, {SNetWHType.DEPENDS_ON: fidel_sequence})
    answer = mesh.answers[tick.answer_ids[0]]
    metadata = mesh.metadata[tick.metadata_ids[0]]
    promoted_symbol = mesh.symbols[tick.promoted_symbol_ids[0]]

    assert answer.raw_answer == fidel_sequence
    assert answer.ascii_folded_answer == fidel_sequence
    assert metadata.value == fidel_sequence
    assert promoted_symbol.label == fidel_sequence
    assert [ord(fidel) for fidel in promoted_symbol.label] == [0x1200, 0x1201, 0x12A0]


def test_mesh_receipt_rejects_authority_and_settlement_drift() -> None:
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    mesh.run_tick_with_answers(seed.symbol_id, {SNetWHType.DEPENDS_ON: "Water"})
    receipt = create_snet_mesh_receipt(mesh)
    receipt_payload = receipt.to_json_dict()

    with pytest.raises(ValueError, match="connector authority"):
        SNetMeshReceipt(**{**receipt_payload, "connector_authority_granted": True})
    with pytest.raises(ValueError, match="settlement_counts total"):
        SNetMeshReceipt(**{**receipt_payload, "settlement_counts": {**receipt_payload["settlement_counts"], "active": 99}})
    assert sum(receipt_payload["settlement_counts"].values()) == receipt_payload["symbol_count"]


def test_mesh_receipt_rejects_boolean_flag_shape_drift() -> None:
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    mesh.run_tick_with_answers(seed.symbol_id, {SNetWHType.DEPENDS_ON: "Water"})
    receipt_payload = create_snet_mesh_receipt(mesh).to_json_dict()

    with pytest.raises(ValueError, match="terminal closure required flag"):
        SNetMeshReceipt(**{**receipt_payload, "terminal_closure_required": 1})
    with pytest.raises(ValueError, match="raw answers exposed flag"):
        SNetMeshReceipt(**{**receipt_payload, "raw_answers_exposed": 0})
    with pytest.raises(ValueError, match="connector authority flag"):
        SNetMeshReceipt(**{**receipt_payload, "connector_authority_granted": ""})

    valid_receipt = SNetMeshReceipt(**receipt_payload)

    assert valid_receipt.terminal_closure_required is True
    assert valid_receipt.raw_answers_exposed is False
    assert valid_receipt.connector_authority_granted is False


def test_mesh_receipt_rejects_direct_contract_drift() -> None:
    class IntSubclass(int):
        pass

    class FloatSubclass(float):
        pass

    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    mesh.run_tick_with_answers(seed.symbol_id, {SNetWHType.DEPENDS_ON: "Water"})
    receipt_payload = create_snet_mesh_receipt(mesh).to_json_dict()

    with pytest.raises(ValueError, match="read-only SNet operator surface"):
        SNetMeshReceipt(**{**receipt_payload, "surface": "unsafe_surface"})
    with pytest.raises(ValueError, match="runtime SNet version"):
        SNetMeshReceipt(**{**receipt_payload, "snet_version": "0.0.0"})
    with pytest.raises(ValueError, match="runtime SNet semantics"):
        SNetMeshReceipt(**{**receipt_payload, "semantics_hash": "sha256:wrong"})
    with pytest.raises(ValueError, match="sha256 digest"):
        SNetMeshReceipt(**{**receipt_payload, "mesh_digest": "sha256:nothex"})
    with pytest.raises(ValueError, match="evidence_refs"):
        SNetMeshReceipt(**{**receipt_payload, "evidence_refs": []})
    with pytest.raises(ValueError, match="symbol_count"):
        SNetMeshReceipt(**{**receipt_payload, "symbol_count": IntSubclass(receipt_payload["symbol_count"])})
    with pytest.raises(ValueError, match="promotion_threshold"):
        SNetMeshReceipt(**{**receipt_payload, "promotion_threshold": FloatSubclass(receipt_payload["promotion_threshold"])})
    with pytest.raises(ValueError, match="settlement_counts.value"):
        SNetMeshReceipt(
            **{
                **receipt_payload,
                "settlement_counts": {
                    **receipt_payload["settlement_counts"],
                    "active": IntSubclass(receipt_payload["settlement_counts"]["active"]),
                },
            }
        )
    assert receipt_payload["mesh_digest"].startswith("sha256:")
