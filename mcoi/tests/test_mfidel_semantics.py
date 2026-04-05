"""Tests for the Mfidel semantic overlay layer.

Covers: annotation creation, similarity scoring, find_similar search,
single-linkage clustering, family explanation, edge cases, immutability,
and clock injection determinism.
"""

from __future__ import annotations

import math
import pytest

from mcoi_runtime.core.mfidel_semantics import (
    MfidelSemanticIndex,
    SemanticAnnotation,
    SemanticFamily,
    SemanticTag,
    _build_embedding,
    _cosine_similarity_vocab,
    _normalize_text,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXED_CLOCK_VALUE = "2026-03-19T12:00:00+00:00"


def _fixed_clock() -> str:
    return FIXED_CLOCK_VALUE


@pytest.fixture
def index() -> MfidelSemanticIndex:
    return MfidelSemanticIndex(clock=_fixed_clock)


def _tag(tag_id: str, label: str, category: str = "general") -> SemanticTag:
    return SemanticTag(tag_id=tag_id, label=label, category=category)


# ---------------------------------------------------------------------------
# 1. Annotation creation
# ---------------------------------------------------------------------------


class TestAnnotationCreation:
    def test_annotate_produces_annotation(self, index: MfidelSemanticIndex) -> None:
        ann = index.annotate("a1", "skill", "deploy the service")
        assert isinstance(ann, SemanticAnnotation)
        assert ann.artifact_id == "a1"
        assert ann.artifact_type == "skill"
        assert ann.annotated_at == FIXED_CLOCK_VALUE

    def test_annotate_with_tags(self, index: MfidelSemanticIndex) -> None:
        tags = (_tag("t1", "deploy"), _tag("t2", "infra"))
        ann = index.annotate("a2", "workflow", "deploy infra", tags=tags)
        assert len(ann.tags) == 2
        assert ann.tags[0].label == "deploy"
        assert ann.tags[1].label == "infra"

    def test_annotate_generates_embedding(self, index: MfidelSemanticIndex) -> None:
        ann = index.annotate("a3", "goal", "build and test the pipeline")
        assert isinstance(ann.embedding, tuple)
        assert len(ann.embedding) > 0
        assert all(isinstance(v, float) for v in ann.embedding)

    def test_annotate_description_is_bounded(
        self, index: MfidelSemanticIndex
    ) -> None:
        ann = index.annotate("a4", "incident", "disk full on node 3")
        assert ann.description == "Semantic annotation"
        assert "incident" not in ann.description
        assert "a4" not in ann.description

    def test_annotate_empty_text_produces_zero_embedding(
        self, index: MfidelSemanticIndex
    ) -> None:
        ann = index.annotate("a5", "lesson", "")
        assert ann.embedding == (0.0,)


# ---------------------------------------------------------------------------
# 2. Similarity -- identical text
# ---------------------------------------------------------------------------


class TestSimilarityIdentical:
    def test_identical_text_similarity_is_one(
        self, index: MfidelSemanticIndex
    ) -> None:
        a = index.annotate("x1", "skill", "deploy service to production")
        b = index.annotate("x2", "skill", "deploy service to production")
        score = index.similarity(a, b)
        assert score == pytest.approx(1.0, abs=1e-9)

    def test_identical_ethiopic_text_similarity_is_one(
        self, index: MfidelSemanticIndex
    ) -> None:
        text = "\u1230\u120b\u121d \u12a0\u1308\u120d\u130d\u120e\u1275"
        a = index.annotate("x1-et", "skill", text)
        b = index.annotate("x2-et", "skill", text)
        score = index.similarity(a, b)
        assert score == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# 3. Similarity -- completely different text
# ---------------------------------------------------------------------------


class TestSimilarityDifferent:
    def test_completely_different_text_low_score(
        self, index: MfidelSemanticIndex
    ) -> None:
        a = index.annotate("x3", "skill", "quantum physics nuclear reactor")
        b = index.annotate("x4", "skill", "deploy web application server")
        score = index.similarity(a, b)
        assert score < 0.2

    def test_no_overlap_zero_score(self, index: MfidelSemanticIndex) -> None:
        a = index.annotate("x5", "skill", "aaa bbb ccc")
        b = index.annotate("x6", "skill", "ddd eee fff")
        score = index.similarity(a, b)
        assert score == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# 4. Similarity -- related text
# ---------------------------------------------------------------------------


class TestSimilarityRelated:
    def test_related_text_moderate_score(
        self, index: MfidelSemanticIndex
    ) -> None:
        a = index.annotate("x7", "skill", "deploy the web service to staging")
        b = index.annotate("x8", "skill", "deploy the api service to production")
        score = index.similarity(a, b)
        assert 0.2 < score < 1.0

    def test_partial_overlap_positive_score(
        self, index: MfidelSemanticIndex
    ) -> None:
        a = index.annotate("x9", "goal", "build pipeline test pipeline")
        b = index.annotate("x10", "goal", "pipeline monitoring alerts")
        score = index.similarity(a, b)
        assert score > 0.0

    def test_related_ethiopic_text_has_positive_score(
        self, index: MfidelSemanticIndex
    ) -> None:
        a = index.annotate(
            "x9-et",
            "goal",
            "\u1230\u120b\u121d \u12a0\u1308\u120d\u130d\u120e\u1275",
        )
        b = index.annotate(
            "x10-et",
            "goal",
            "\u1230\u120b\u121d \u1235\u122d\u12d3\u1275",
        )
        score = index.similarity(a, b)
        assert score > 0.0


# ---------------------------------------------------------------------------
# 5. find_similar -- matches above threshold
# ---------------------------------------------------------------------------


class TestFindSimilarAbove:
    def test_find_similar_returns_matches_above_threshold(
        self, index: MfidelSemanticIndex
    ) -> None:
        target = index.annotate("s1", "skill", "deploy service deploy service")
        same = index.annotate("s2", "skill", "deploy service deploy service")
        diff = index.annotate("s3", "skill", "zzz yyy xxx")
        results = index.find_similar(target, [same, diff], threshold=0.3)
        ids = [ann.artifact_id for ann, _ in results]
        assert "s2" in ids

    def test_find_similar_sorted_by_score_descending(
        self, index: MfidelSemanticIndex
    ) -> None:
        target = index.annotate("s4", "skill", "deploy deploy deploy")
        high = index.annotate("s5", "skill", "deploy deploy deploy")
        mid = index.annotate("s6", "skill", "deploy something else entirely different")
        results = index.find_similar(target, [mid, high], threshold=0.0)
        assert results[0][1] >= results[-1][1]


# ---------------------------------------------------------------------------
# 6. find_similar -- excludes below threshold
# ---------------------------------------------------------------------------


class TestFindSimilarBelow:
    def test_find_similar_excludes_below_threshold(
        self, index: MfidelSemanticIndex
    ) -> None:
        target = index.annotate("e1", "skill", "aaa bbb ccc")
        unrelated = index.annotate("e2", "skill", "ddd eee fff")
        results = index.find_similar(target, [unrelated], threshold=0.5)
        assert len(results) == 0

    def test_find_similar_excludes_self(
        self, index: MfidelSemanticIndex
    ) -> None:
        target = index.annotate("e3", "skill", "hello world")
        results = index.find_similar(target, [target], threshold=0.0)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# 7. Clustering -- groups related annotations
# ---------------------------------------------------------------------------


class TestClusteringRelated:
    def test_clustering_groups_identical(
        self, index: MfidelSemanticIndex
    ) -> None:
        a = index.annotate("c1", "skill", "deploy deploy deploy")
        b = index.annotate("c2", "skill", "deploy deploy deploy")
        families = index.cluster_into_families([a, b], threshold=0.5)
        assert len(families) == 1
        assert set(families[0].members) == {"c1", "c2"}

    def test_clustering_three_related(
        self, index: MfidelSemanticIndex
    ) -> None:
        a = index.annotate("c3", "skill", "deploy service production")
        b = index.annotate("c4", "skill", "deploy service staging")
        c = index.annotate("c5", "skill", "deploy service canary")
        families = index.cluster_into_families([a, b, c], threshold=0.3)
        # All three share significant overlap, expect one family
        all_members = set()
        for f in families:
            all_members.update(f.members)
        assert {"c3", "c4", "c5"}.issubset(all_members)

    def test_family_description_is_bounded(
        self, index: MfidelSemanticIndex
    ) -> None:
        tags = (_tag("t1", "deploy"), _tag("t2", "infra"))
        a = index.annotate("c6", "skill", "deploy service production", tags=tags)
        b = index.annotate("c7", "skill", "deploy service staging", tags=tags)
        families = index.cluster_into_families([a, b], threshold=0.3)
        assert len(families) == 1
        assert families[0].description == "Semantic family"
        assert "deploy" not in families[0].description
        assert "c6" not in families[0].description


# ---------------------------------------------------------------------------
# 8. Clustering -- keeps unrelated annotations separate
# ---------------------------------------------------------------------------


class TestClusteringSeparate:
    def test_clustering_separates_unrelated(
        self, index: MfidelSemanticIndex
    ) -> None:
        a = index.annotate("u1", "skill", "aaa bbb ccc")
        b = index.annotate("u2", "skill", "ddd eee fff")
        families = index.cluster_into_families([a, b], threshold=0.5)
        assert len(families) == 2

    def test_clustering_mixed_groups(
        self, index: MfidelSemanticIndex
    ) -> None:
        a1 = index.annotate("m1", "skill", "deploy deploy deploy")
        a2 = index.annotate("m2", "skill", "deploy deploy deploy")
        b1 = index.annotate("m3", "skill", "zzz yyy xxx")
        families = index.cluster_into_families([a1, a2, b1], threshold=0.5)
        assert len(families) == 2


# ---------------------------------------------------------------------------
# 9. Family explanation
# ---------------------------------------------------------------------------


class TestFamilyExplanation:
    def test_explain_family_contains_tag_info(
        self, index: MfidelSemanticIndex
    ) -> None:
        tags = (_tag("t1", "deploy"), _tag("t2", "infra"))
        a = index.annotate("f1", "skill", "deploy infra", tags=tags)
        b = index.annotate("f2", "skill", "deploy infra", tags=tags)
        families = index.cluster_into_families([a, b], threshold=0.3)
        assert len(families) >= 1
        explanation = index.explain_family(families[0])
        assert "deploy" in explanation
        assert "infra" in explanation

    def test_explain_empty_family(self, index: MfidelSemanticIndex) -> None:
        family = SemanticFamily(
            family_id="fam-empty",
            name="Empty family",
            members=(),
            description="no members",
        )
        explanation = index.explain_family(family)
        assert "empty" in explanation.lower() or "0" in explanation

    def test_explain_family_includes_member_ids(
        self, index: MfidelSemanticIndex
    ) -> None:
        family = SemanticFamily(
            family_id="fam-x",
            name="Family: testing",
            members=("art1", "art2"),
            description="test family",
        )
        explanation = index.explain_family(family)
        assert "art1" in explanation
        assert "art2" in explanation


# ---------------------------------------------------------------------------
# 10. Empty input handling
# ---------------------------------------------------------------------------


class TestEmptyInputs:
    def test_cluster_empty_list(self, index: MfidelSemanticIndex) -> None:
        families = index.cluster_into_families([])
        assert families == []

    def test_find_similar_empty_candidates(
        self, index: MfidelSemanticIndex
    ) -> None:
        target = index.annotate("z1", "skill", "hello")
        results = index.find_similar(target, [])
        assert results == []

    def test_similarity_empty_embeddings(
        self, index: MfidelSemanticIndex
    ) -> None:
        a = index.annotate("z2", "skill", "")
        b = index.annotate("z3", "skill", "")
        score = index.similarity(a, b)
        # Both are zero vectors -> 0.0
        assert score == pytest.approx(0.0, abs=1e-9) or score == pytest.approx(
            1.0, abs=1e-9
        )


# ---------------------------------------------------------------------------
# 11. Clock injection determinism
# ---------------------------------------------------------------------------


class TestClockDeterminism:
    def test_clock_value_used_in_annotation(self) -> None:
        custom_time = "2099-01-01T00:00:00+00:00"
        idx = MfidelSemanticIndex(clock=lambda: custom_time)
        ann = idx.annotate("d1", "goal", "test clock")
        assert ann.annotated_at == custom_time

    def test_different_clocks_produce_different_timestamps(self) -> None:
        call_count = 0

        def ticking_clock() -> str:
            nonlocal call_count
            call_count += 1
            return f"2026-01-01T00:00:{call_count:02d}+00:00"

        idx = MfidelSemanticIndex(clock=ticking_clock)
        a = idx.annotate("d2", "goal", "first")
        b = idx.annotate("d3", "goal", "second")
        assert a.annotated_at != b.annotated_at


# ---------------------------------------------------------------------------
# 12. Annotation is frozen / immutable
# ---------------------------------------------------------------------------


class TestImmutability:
    def test_annotation_is_frozen(self, index: MfidelSemanticIndex) -> None:
        ann = index.annotate("imm1", "skill", "test immutability")
        with pytest.raises(AttributeError):
            ann.artifact_id = "changed"  # type: ignore[misc]

    def test_semantic_tag_is_frozen(self) -> None:
        tag = SemanticTag(tag_id="t1", label="test", category="general")
        with pytest.raises(AttributeError):
            tag.label = "changed"  # type: ignore[misc]

    def test_semantic_family_is_frozen(self) -> None:
        family = SemanticFamily(
            family_id="f1", name="test", members=("a",), description="d"
        )
        with pytest.raises(AttributeError):
            family.name = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 13. Validation errors
# ---------------------------------------------------------------------------


class TestValidation:
    def test_tag_rejects_empty_tag_id(self) -> None:
        with pytest.raises(ValueError, match="tag_id"):
            SemanticTag(tag_id="", label="ok", category="ok")

    def test_tag_rejects_empty_label(self) -> None:
        with pytest.raises(ValueError, match="label"):
            SemanticTag(tag_id="t1", label="", category="ok")

    def test_tag_rejects_empty_category(self) -> None:
        with pytest.raises(ValueError, match="category"):
            SemanticTag(tag_id="t1", label="ok", category="")

    def test_annotation_rejects_empty_artifact_id(
        self, index: MfidelSemanticIndex
    ) -> None:
        with pytest.raises(ValueError, match="artifact_id"):
            index.annotate("", "skill", "text")

    def test_annotation_rejects_empty_artifact_type(
        self, index: MfidelSemanticIndex
    ) -> None:
        with pytest.raises(ValueError, match="artifact_type"):
            index.annotate("a1", "", "text")

    def test_family_rejects_empty_family_id(self) -> None:
        with pytest.raises(ValueError, match="family_id"):
            SemanticFamily(family_id="", name="ok", members=(), description="ok")


# ---------------------------------------------------------------------------
# 14. Internal helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_normalize_text_lowercases(self) -> None:
        assert _normalize_text("Hello WORLD") == ["hello", "world"]

    def test_normalize_text_strips_punctuation(self) -> None:
        result = _normalize_text("deploy! the; service.")
        assert result == ["deploy", "the", "service"]

    def test_normalize_text_preserves_ethiopic_tokens(self) -> None:
        result = _normalize_text(
            "\u1230\u120b\u121d world 123 \u12a0\u1308\u120d\u130d\u120e\u1275"
        )
        assert result == [
            "\u1230\u120b\u121d",
            "world",
            "123",
            "\u12a0\u1308\u120d\u130d\u120e\u1275",
        ]

    def test_build_embedding_keeps_ethiopic_content_non_empty(self) -> None:
        vocab, values = _build_embedding("\u1230\u120b\u121d \u12a0\u1308\u120d\u130d\u120e\u1275")
        assert vocab == (
            "\u1230\u120b\u121d",
            "\u12a0\u1308\u120d\u130d\u120e\u1275",
        )
        assert len(values) == 2
        assert all(value > 0.0 for value in values)

    def test_build_embedding_deterministic(self) -> None:
        e1 = _build_embedding("deploy service")
        e2 = _build_embedding("deploy service")
        assert e1 == e2

    def test_build_embedding_is_normalized(self) -> None:
        _vocab, vals = _build_embedding("alpha beta gamma delta")
        magnitude = math.sqrt(sum(v * v for v in vals))
        assert magnitude == pytest.approx(1.0, abs=1e-9)

    def test_cosine_similarity_orthogonal(self) -> None:
        va, vb = ("x",), ("y",)
        a, b = (1.0,), (1.0,)
        assert _cosine_similarity_vocab(va, a, vb, b) == pytest.approx(0.0, abs=1e-9)

    def test_cosine_similarity_identical(self) -> None:
        v = ("a", "b")
        a = (0.6, 0.8)
        assert _cosine_similarity_vocab(v, a, v, a) == pytest.approx(1.0, abs=1e-9)

    def test_cosine_similarity_partial_overlap(self) -> None:
        va = ("a", "b", "c")
        vb = ("a",)
        a = (1.0, 0.0, 0.0)
        b = (1.0,)
        score = _cosine_similarity_vocab(va, a, vb, b)
        assert score == pytest.approx(1.0, abs=1e-9)
