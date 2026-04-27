"""
Mfidel Convergence — Option 1b verification (v4.1.0).

Asserts that core/mfidel_matrix.py is now a derived view over
substrate/mfidel/grid.py:

  - Both modules see the same atomic glyphs at every position.
  - The three known-empty slots (f[20][8], f[21][8], f[24][8]) are empty
    in both implementations.
  - Vectorize masks the three empty positions to zero.
  - lookup() raises EmptyFidelSlotError on empty positions.
"""
from __future__ import annotations

import pytest

from mcoi_runtime.core.mfidel_matrix import (
    EmptyFidelSlotError,
    FIDEL_GEBETA,
    KNOWN_EMPTY_POSITIONS,
    MfidelMatrix,
)
from mcoi_runtime.substrate.mfidel.grid import (
    MFIDEL_GRID,
    GRID_COLS,
    GRID_ROWS,
)


def test_legacy_grid_is_substrate_grid():
    """The two grids must literally be the same object (same source)."""
    assert FIDEL_GEBETA is MFIDEL_GRID


def test_known_empty_positions_are_empty():
    for r, c in KNOWN_EMPTY_POSITIONS:
        assert FIDEL_GEBETA[r - 1][c - 1] == ""
        assert MFIDEL_GRID[r - 1][c - 1] == ""


def test_no_other_empty_positions():
    """Outside the three known empties, every slot must be non-empty."""
    empties: list[tuple[int, int]] = []
    for r in range(1, GRID_ROWS + 1):
        for c in range(1, GRID_COLS + 1):
            if not MFIDEL_GRID[r - 1][c - 1]:
                empties.append((r, c))
    assert set(empties) == KNOWN_EMPTY_POSITIONS


def test_lookup_empty_slot_raises():
    for r, c in KNOWN_EMPTY_POSITIONS:
        with pytest.raises(EmptyFidelSlotError):
            MfidelMatrix.lookup(r, c)


def test_lookup_non_empty_slot_succeeds():
    f = MfidelMatrix.lookup(1, 1)
    assert f.glyph == "ሀ"


def test_vectorize_masks_empty_positions_to_zero():
    """Vector positions corresponding to f[20][8], f[21][8], f[24][8] must
    always be zero, regardless of input. This is the convergence invariant.
    """
    # Vectorize text containing every non-empty fidel
    text = "".join(g for row in MFIDEL_GRID for g in row if g)
    vec = MfidelMatrix.vectorize(text)
    assert vec.dimension == 272
    for r, c in KNOWN_EMPTY_POSITIONS:
        idx = (r - 1) * GRID_COLS + (c - 1)
        assert vec.fidel_weights[idx] == 0.0, (
            f"position {idx} (f[{r}][{c}]) must be zero, got {vec.fidel_weights[idx]}"
        )


def test_glyph_to_position_does_not_resolve_empty_string():
    """Empty string is not a valid glyph and must not resolve to any position."""
    pos = MfidelMatrix.glyph_to_position("")
    assert pos is None


def test_audio_formula_empty_slot_raises():
    """Audio formula chains through lookup() — must propagate the error."""
    for r, c in KNOWN_EMPTY_POSITIONS:
        with pytest.raises(EmptyFidelSlotError):
            MfidelMatrix.audio_formula(r, c)


def test_known_empty_count_is_three():
    """The convergence specifically claims 3 empties — assert it stays 3."""
    assert len(KNOWN_EMPTY_POSITIONS) == 3
