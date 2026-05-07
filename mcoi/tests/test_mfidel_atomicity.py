"""Purpose: verify Mfidel runtime atomicity invariants.

Governance scope: OCE, RAG, CDCV, CQTE, UWMA, PRS.
Dependencies: mcoi_runtime.core.mfidel_matrix and substrate.mfidel.grid.
Invariants:
  - A fidel glyph is processed as one atomic codepoint.
  - Multi-codepoint overlays are rejected rather than normalized.
  - Multi-glyph strings are sequences, never one fused lookup key.
  - Runtime modules do not import Unicode normalization helpers.
"""

from __future__ import annotations

import inspect

import pytest

import mcoi_runtime.core.mfidel_matrix as mfidel_matrix
import mcoi_runtime.substrate.mfidel.grid as mfidel_grid
from mcoi_runtime.core.mfidel_matrix import MfidelMatrix


FIDEL_HA = "\u1200"
FIDEL_LA = "\u1208"
COMBINING_ACUTE = "\u0301"


def test_whole_fidel_glyph_is_atomic_lookup_unit() -> None:
    sequence = MfidelMatrix.text_to_fidel_sequence(FIDEL_HA)
    vector = MfidelMatrix.vectorize(FIDEL_HA)

    assert MfidelMatrix.glyph_to_position(FIDEL_HA) == (1, 1)
    assert len(sequence) == 1
    assert sequence[0].glyph == FIDEL_HA
    assert sequence[0].row == 1
    assert sequence[0].col == 1
    assert vector.fidel_weights[0] == 1.0


def test_combining_overlay_is_rejected_without_normalization() -> None:
    decomposed_like_text = FIDEL_HA + COMBINING_ACUTE

    with pytest.raises(ValueError, match="^text contains non-fidel characters$"):
        MfidelMatrix.text_to_fidel_sequence(decomposed_like_text)
    with pytest.raises(ValueError, match="^text contains non-fidel characters$"):
        MfidelMatrix.vectorize(decomposed_like_text)
    assert MfidelMatrix.glyph_to_position(decomposed_like_text) is None


def test_multi_fidel_text_is_sequence_not_single_symbol() -> None:
    sequence = MfidelMatrix.text_to_fidel_sequence(FIDEL_HA + FIDEL_LA)
    vector = MfidelMatrix.vectorize(FIDEL_HA + FIDEL_LA)

    assert MfidelMatrix.glyph_to_position(FIDEL_HA + FIDEL_LA) is None
    assert len(sequence) == 2
    assert tuple(fidel.glyph for fidel in sequence) == (FIDEL_HA, FIDEL_LA)
    assert vector.dimension == 272
    assert vector.fidel_weights[0] > 0.0
    assert vector.fidel_weights[8] > 0.0


def test_mfidel_runtime_does_not_import_unicode_normalization() -> None:
    matrix_source = inspect.getsource(mfidel_matrix)
    grid_source = inspect.getsource(mfidel_grid)

    assert "unicodedata" not in matrix_source
    assert "unicodedata" not in grid_source
    assert "normalize(" not in matrix_source
    assert "normalize(" not in grid_source
