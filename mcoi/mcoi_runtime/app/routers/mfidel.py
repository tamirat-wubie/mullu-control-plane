"""
/mfidel/* — substrate atom access endpoints.

Stateless: every endpoint is a pure function over the static grid. No
authentication required beyond whatever middleware the server applies; no
side effects.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.substrate.mfidel.grid import (
    GRID_COLS,
    GRID_ROWS,
    fidel_at,
    fidel_count,
    get_overlay_for,
)

router = APIRouter(prefix="/mfidel", tags=["mfidel"])


class FidelResponse(BaseModel):
    row: int = Field(..., ge=1, le=GRID_ROWS)
    col: int = Field(..., ge=1, le=GRID_COLS)
    glyph: str
    kind: str
    is_empty: bool


class OverlayResponse(BaseModel):
    base: FidelResponse
    overlay: FidelResponse | None


class GridSummary(BaseModel):
    rows: int
    cols: int
    total_slots: int
    non_empty_count: int
    empty_positions: list[tuple[int, int]]


def _to_response(f) -> FidelResponse:
    return FidelResponse(
        row=f.coord.row,
        col=f.coord.col,
        glyph=f.glyph,
        kind=f.kind.value,
        is_empty=f.is_empty,
    )


@router.get("/grid", response_model=GridSummary)
def grid_summary() -> GridSummary:
    """Top-level grid metadata."""
    from mcoi_runtime.substrate.mfidel.grid import MFIDEL_GRID
    empties: list[tuple[int, int]] = []
    for r in range(1, GRID_ROWS + 1):
        for c in range(1, GRID_COLS + 1):
            if not MFIDEL_GRID[r - 1][c - 1]:
                empties.append((r, c))
    return GridSummary(
        rows=GRID_ROWS,
        cols=GRID_COLS,
        total_slots=GRID_ROWS * GRID_COLS,
        non_empty_count=fidel_count(),
        empty_positions=empties,
    )


@router.get("/atom/{row}/{col}", response_model=FidelResponse)
def get_atom(row: int, col: int) -> FidelResponse:
    """Look up the atomic fidel at f[row][col] (1-indexed)."""
    if not (1 <= row <= GRID_ROWS):
        raise HTTPException(
            status_code=400,
            detail={"error": "row_out_of_range", "row": row, "max": GRID_ROWS},
        )
    if not (1 <= col <= GRID_COLS):
        raise HTTPException(
            status_code=400,
            detail={"error": "col_out_of_range", "col": col, "max": GRID_COLS},
        )
    return _to_response(fidel_at(row, col))


@router.get("/overlay/{row}/{col}", response_model=OverlayResponse)
def get_overlay(row: int, col: int) -> OverlayResponse:
    """Return the audio overlay fidel for f[row][col]. None if empty slot."""
    if not (1 <= row <= GRID_ROWS):
        raise HTTPException(
            status_code=400,
            detail={"error": "row_out_of_range", "row": row, "max": GRID_ROWS},
        )
    if not (1 <= col <= GRID_COLS):
        raise HTTPException(
            status_code=400,
            detail={"error": "col_out_of_range", "col": col, "max": GRID_COLS},
        )
    base = fidel_at(row, col)
    overlay = get_overlay_for(base)
    return OverlayResponse(
        base=_to_response(base),
        overlay=_to_response(overlay) if overlay is not None else None,
    )
