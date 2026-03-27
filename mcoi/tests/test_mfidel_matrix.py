"""Tests for the Mfidel Matrix -- gebeta structure, lookup, audio, vectorize, similarity."""

from __future__ import annotations

import math

import pytest

from mcoi_runtime.contracts.mfidel import (
    Fidel,
    FidelAudioFormula,
    MfidelSimilarity,
    MfidelVector,
)
from mcoi_runtime.core.mfidel_matrix import FIDEL_GEBETA, MfidelMatrix


# ---------------------------------------------------------------------------
# Gebeta structure
# ---------------------------------------------------------------------------

class TestGebetaStructure:
    def test_gebeta_has_34_rows(self) -> None:
        assert len(FIDEL_GEBETA) == 34

    def test_each_row_has_8_columns(self) -> None:
        for i, row in enumerate(FIDEL_GEBETA):
            assert len(row) == 8, f"Row {i + 1} has {len(row)} columns, expected 8"

    def test_total_fidel_count_is_272(self) -> None:
        total = sum(len(row) for row in FIDEL_GEBETA)
        assert total == 272

    def test_all_glyphs_are_unique(self) -> None:
        all_glyphs = [g for row in FIDEL_GEBETA for g in row]
        assert len(all_glyphs) == len(set(all_glyphs))

    def test_row_11_is_ve_family(self) -> None:
        assert FIDEL_GEBETA[10][0] == "ቨ"

    def test_row_18_is_ke_family(self) -> None:
        assert FIDEL_GEBETA[17][0] == "ከ"

    def test_row_19_is_khe_family(self) -> None:
        assert FIDEL_GEBETA[18][0] == "ኸ"

    def test_row_9_col8_is_qwa(self) -> None:
        assert FIDEL_GEBETA[8][7] == "ቋ"

    def test_row_18_col8_is_kwa(self) -> None:
        assert FIDEL_GEBETA[17][7] == "ኳ"

    def test_row_27_col8_is_gwa(self) -> None:
        assert FIDEL_GEBETA[26][7] == "ጓ"

    def test_row_14_col8_is_xa_labialized(self) -> None:
        assert FIDEL_GEBETA[13][7] == "ኈ"

    def test_canonical_order_first_glyph_per_row(self) -> None:
        expected_firsts = [
            "ሀ", "ለ", "ሐ", "መ", "ሠ", "ረ", "ሰ", "ሸ",
            "ቀ", "በ", "ቨ", "ተ", "ቸ", "ኀ", "ነ", "ኘ",
            "ኧ", "ከ", "ኸ", "ወ", "ዐ", "ዘ", "ዠ", "የ",
            "ደ", "ጀ", "ገ", "ጠ", "ጨ", "ጰ", "ጸ", "ፀ",
            "ፈ", "ፐ",
        ]
        actual_firsts = [row[0] for row in FIDEL_GEBETA]
        assert actual_firsts == expected_firsts

    def test_vowel_row_is_row_17(self) -> None:
        assert FIDEL_GEBETA[16] == ("ኧ", "ኡ", "ኢ", "ኣ", "ኤ", "እ", "ኦ", "አ")


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

class TestLookup:
    def test_lookup_row1_col1(self) -> None:
        fidel = MfidelMatrix.lookup(1, 1)
        assert fidel.glyph == "ሀ"
        assert fidel.row == 1
        assert fidel.col == 1

    def test_lookup_row34_col8(self) -> None:
        fidel = MfidelMatrix.lookup(34, 8)
        assert fidel.glyph == "ፗ"  # Row 34 is Pe family

    def test_lookup_out_of_range_row(self) -> None:
        with pytest.raises(ValueError):
            MfidelMatrix.lookup(0, 1)
        with pytest.raises(ValueError):
            MfidelMatrix.lookup(35, 1)

    def test_lookup_out_of_range_col(self) -> None:
        with pytest.raises(ValueError):
            MfidelMatrix.lookup(1, 0)
        with pytest.raises(ValueError):
            MfidelMatrix.lookup(1, 9)

    def test_glyph_to_position_known(self) -> None:
        pos = MfidelMatrix.glyph_to_position("ለ")
        assert pos == (2, 1)

    def test_glyph_to_position_unknown(self) -> None:
        assert MfidelMatrix.glyph_to_position("X") is None


# ---------------------------------------------------------------------------
# Audio formulas with exceptions
# ---------------------------------------------------------------------------

class TestAudioFormula:
    def test_normal_formula_no_exception(self) -> None:
        af = MfidelMatrix.audio_formula(2, 3)
        assert af.exception_type is None
        assert isinstance(af.fidel, Fidel)
        assert af.fidel.glyph == "ሊ"

    def test_glottal_onset_exception(self) -> None:
        af = MfidelMatrix.audio_formula(1, 1)
        assert af.exception_type == "glottal_onset"

    def test_pharyngeal_onset_exception(self) -> None:
        af = MfidelMatrix.audio_formula(3, 1)
        assert af.exception_type == "pharyngeal_onset"

    def test_labialized_extension_exception_col8(self) -> None:
        af = MfidelMatrix.audio_formula(5, 8)
        assert af.exception_type == "labialized_extension"

    def test_col8_exception_any_row(self) -> None:
        for row in (1, 10, 20, 34):
            af = MfidelMatrix.audio_formula(row, 8)
            # Row 1 col 8 is labialized, not glottal
            assert af.exception_type == "labialized_extension"


# ---------------------------------------------------------------------------
# Vectorize and similarity
# ---------------------------------------------------------------------------

class TestVectorize:
    def test_vector_dimension_is_272(self) -> None:
        vec = MfidelMatrix.vectorize("ሀ")
        assert vec.dimension == 272
        assert len(vec.fidel_weights) == 272

    def test_normalized_vector_has_unit_magnitude(self) -> None:
        vec = MfidelMatrix.vectorize("ሀለመ")
        mag = math.sqrt(sum(w * w for w in vec.fidel_weights))
        assert abs(mag - 1.0) < 1e-9

    def test_empty_text_not_normalized(self) -> None:
        vec = MfidelMatrix.vectorize("")
        assert vec.normalized is False
        assert all(w == 0.0 for w in vec.fidel_weights)

    def test_non_fidel_chars_ignored(self) -> None:
        vec = MfidelMatrix.vectorize("abc")
        assert vec.normalized is False

    def test_text_to_fidel_sequence(self) -> None:
        seq = MfidelMatrix.text_to_fidel_sequence("ሀለ")
        assert len(seq) == 2
        assert seq[0].glyph == "ሀ"
        assert seq[1].glyph == "ለ"


class TestSimilarity:
    def test_identical_texts_have_similarity_one(self) -> None:
        va = MfidelMatrix.vectorize("ሀለመ")
        vb = MfidelMatrix.vectorize("ሀለመ")
        assert abs(MfidelMatrix.similarity(va, vb) - 1.0) < 1e-9

    def test_disjoint_texts_have_similarity_zero(self) -> None:
        va = MfidelMatrix.vectorize("ሀ")
        vb = MfidelMatrix.vectorize("ፗ")
        assert abs(MfidelMatrix.similarity(va, vb)) < 1e-9

    def test_similarity_is_between_zero_and_one(self) -> None:
        va = MfidelMatrix.vectorize("ሀለመ")
        vb = MfidelMatrix.vectorize("ሀረሰ")
        score = MfidelMatrix.similarity(va, vb)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Atomicity -- contract validation
# ---------------------------------------------------------------------------

class TestContractAtomicity:
    def test_fidel_rejects_bad_row(self) -> None:
        with pytest.raises(ValueError):
            Fidel(row=0, col=1, glyph="ሀ", whisper_id="w")

    def test_mfidel_vector_rejects_wrong_dimension(self) -> None:
        with pytest.raises(ValueError):
            MfidelVector(vector_id="x", fidel_weights=(0.0,) * 100, dimension=272, normalized=False)

    def test_mfidel_similarity_rejects_score_out_of_range(self) -> None:
        with pytest.raises(ValueError):
            MfidelSimilarity(
                source_id="a", target_id="b", cosine_score=1.5,
                matching_fidels=(), computed_at="now",
            )
