"""Purpose: Mfidel Substrate contract definitions for Ge'ez fidel encoding.
Governance scope: fidel position, audio formula, vector, and similarity types.
Dependencies: Python standard library only (dataclasses).
Invariants:
  - All contracts are frozen and immutable after creation.
  - __post_init__ validates every field; silent invalid state is rejected.
  - Fidel grid is 34 rows x 8 columns.
  - MfidelVector dimension is always 272 (34 * 8).
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Data contracts (frozen dataclasses)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Fidel:
    """A single Ge'ez fidel with its grid position and glyph."""

    row: int
    col: int
    glyph: str
    whisper_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.row, int):
            raise TypeError("row must be an int")
        if self.row < 1 or self.row > 34:
            raise ValueError("row must be between 1 and 34 inclusive")
        if not isinstance(self.col, int):
            raise TypeError("col must be an int")
        if self.col < 1 or self.col > 8:
            raise ValueError("col must be between 1 and 8 inclusive")
        if not isinstance(self.glyph, str) or not self.glyph:
            raise ValueError("glyph must be a non-empty string")
        if not isinstance(self.whisper_id, str) or not self.whisper_id:
            raise ValueError("whisper_id must be a non-empty string")


@dataclass(frozen=True, slots=True)
class FidelAudioFormula:
    """Audio formula for a fidel, describing its phonetic components."""

    fidel: Fidel
    whisper_component: str
    vibratory_component: str
    formula_text: str
    exception_type: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.fidel, Fidel):
            raise TypeError("fidel must be a Fidel instance")
        if not isinstance(self.whisper_component, str) or not self.whisper_component:
            raise ValueError("whisper_component must be a non-empty string")
        if not isinstance(self.vibratory_component, str) or not self.vibratory_component:
            raise ValueError("vibratory_component must be a non-empty string")
        if not isinstance(self.formula_text, str) or not self.formula_text:
            raise ValueError("formula_text must be a non-empty string")
        if self.exception_type is not None and not isinstance(self.exception_type, str):
            raise TypeError("exception_type must be a str or None")


@dataclass(frozen=True, slots=True)
class MfidelVector:
    """272-dimensional vector encoding of a fidel sequence."""

    vector_id: str
    fidel_weights: tuple[float, ...]
    dimension: int
    normalized: bool

    def __post_init__(self) -> None:
        if not isinstance(self.vector_id, str) or not self.vector_id:
            raise ValueError("vector_id must be a non-empty string")
        if not isinstance(self.fidel_weights, tuple):
            raise TypeError("fidel_weights must be a tuple of float")
        for w in self.fidel_weights:
            if not isinstance(w, (int, float)):
                raise TypeError("each weight must be numeric")
        if not isinstance(self.dimension, int):
            raise TypeError("dimension must be an int")
        if self.dimension != 272:
            raise ValueError("dimension must always be 272")
        if len(self.fidel_weights) != 272:
            raise ValueError("fidel_weights must have exactly 272 elements")
        if not isinstance(self.normalized, bool):
            raise TypeError("normalized must be a bool")


@dataclass(frozen=True, slots=True)
class MfidelSimilarity:
    """Cosine similarity result between two fidel vectors."""

    source_id: str
    target_id: str
    cosine_score: float
    matching_fidels: tuple[str, ...]
    computed_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id:
            raise ValueError("source_id must be a non-empty string")
        if not isinstance(self.target_id, str) or not self.target_id:
            raise ValueError("target_id must be a non-empty string")
        if not isinstance(self.cosine_score, (int, float)):
            raise TypeError("cosine_score must be numeric")
        if self.cosine_score < 0.0 or self.cosine_score > 1.0:
            raise ValueError("cosine_score must be between 0 and 1 inclusive")
        if not isinstance(self.matching_fidels, tuple):
            raise TypeError("matching_fidels must be a tuple")
        for f in self.matching_fidels:
            if not isinstance(f, str):
                raise TypeError("each matching fidel must be a str")
        if not isinstance(self.computed_at, str) or not self.computed_at:
            raise ValueError("computed_at must be a non-empty string")
