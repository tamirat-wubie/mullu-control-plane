"""Purpose: Mfidel Matrix -- Ge'ez fidel lookup, audio formula, vectorization, similarity.
Governance scope: fidel grid operations, phonetic formula generation, vector encoding.
Dependencies: Python standard library only (math, hashlib, datetime).
Invariants:
  - FIDEL_GEBETA is a 34x8 immutable tuple of Ge'ez Unicode characters.
  - The matrix class is stateless; all methods are deterministic.
  - Vectors are always 272-dimensional (34 rows * 8 columns).
  - Cosine similarity is computed from normalized weight vectors.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone

from mcoi_runtime.contracts.mfidel import (
    Fidel,
    FidelAudioFormula,
    MfidelSimilarity,
    MfidelVector,
)

# ---------------------------------------------------------------------------
# Ge'ez Fidel Gebeta (34 rows x 8 columns)
# ---------------------------------------------------------------------------

FIDEL_GEBETA: tuple[tuple[str, ...], ...] = (
    # Row 1: Ha
    ("ሀ", "ሁ", "ሂ", "ሃ", "ሄ", "ህ", "ሆ", "ሇ"),
    # Row 2: Le
    ("ለ", "ሉ", "ሊ", "ላ", "ሌ", "ል", "ሎ", "ሏ"),
    # Row 3: Hha
    ("ሐ", "ሑ", "ሒ", "ሓ", "ሔ", "ሕ", "ሖ", "ሗ"),
    # Row 4: Me
    ("መ", "ሙ", "ሚ", "ማ", "ሜ", "ም", "ሞ", "ሟ"),
    # Row 5: Sze
    ("ሠ", "ሡ", "ሢ", "ሣ", "ሤ", "ሥ", "ሦ", "ሧ"),
    # Row 6: Re
    ("ረ", "ሩ", "ሪ", "ራ", "ሬ", "ር", "ሮ", "ሯ"),
    # Row 7: Se
    ("ሰ", "ሱ", "ሲ", "ሳ", "ሴ", "ስ", "ሶ", "ሷ"),
    # Row 8: She
    ("ሸ", "ሹ", "ሺ", "ሻ", "ሼ", "ሽ", "ሾ", "ሿ"),
    # Row 9: Qe
    ("ቀ", "ቁ", "ቂ", "ቃ", "ቄ", "ቅ", "ቆ", "ቋ"),
    # Row 10: Be
    ("በ", "ቡ", "ቢ", "ባ", "ቤ", "ብ", "ቦ", "ቧ"),
    # Row 11: Ve
    ("ቨ", "ቩ", "ቪ", "ቫ", "ቬ", "ቭ", "ቮ", "ቯ"),
    # Row 12: Te
    ("ተ", "ቱ", "ቲ", "ታ", "ቴ", "ት", "ቶ", "ቷ"),
    # Row 13: Che
    ("ቸ", "ቹ", "ቺ", "ቻ", "ቼ", "ች", "ቾ", "ቿ"),
    # Row 14: Xa
    ("ኀ", "ኁ", "ኂ", "ኃ", "ኄ", "ኅ", "ኆ", "ኈ"),
    # Row 15: Ne
    ("ነ", "ኑ", "ኒ", "ና", "ኔ", "ን", "ኖ", "ኗ"),
    # Row 16: Nye
    ("ኘ", "ኙ", "ኚ", "ኛ", "ኜ", "ኝ", "ኞ", "ኟ"),
    # Row 17: Vowels
    ("ኧ", "ኡ", "ኢ", "ኣ", "ኤ", "እ", "ኦ", "አ"),
    # Row 18: Ke
    ("ከ", "ኩ", "ኪ", "ካ", "ኬ", "ክ", "ኮ", "ኳ"),
    # Row 19: Khe
    ("ኸ", "ኹ", "ኺ", "ኻ", "ኼ", "ኽ", "ኾ", "ዃ"),
    # Row 20: We
    ("ወ", "ዉ", "ዊ", "ዋ", "ዌ", "ው", "ዎ", "ዏ"),
    # Row 21: Ayin
    ("ዐ", "ዑ", "ዒ", "ዓ", "ዔ", "ዕ", "ዖ", "዗"),
    # Row 22: Ze
    ("ዘ", "ዙ", "ዚ", "ዛ", "ዜ", "ዝ", "ዞ", "ዟ"),
    # Row 23: Zhe
    ("ዠ", "ዡ", "ዢ", "ዣ", "ዤ", "ዥ", "ዦ", "ዧ"),
    # Row 24: Ye
    ("የ", "ዩ", "ዪ", "ያ", "ዬ", "ይ", "ዮ", "ዯ"),
    # Row 25: De
    ("ደ", "ዱ", "ዲ", "ዳ", "ዴ", "ድ", "ዶ", "ዷ"),
    # Row 26: Je
    ("ጀ", "ጁ", "ጂ", "ጃ", "ጄ", "ጅ", "ጆ", "ጇ"),
    # Row 27: Ge
    ("ገ", "ጉ", "ጊ", "ጋ", "ጌ", "ግ", "ጎ", "ጓ"),
    # Row 28: Tse
    ("ጠ", "ጡ", "ጢ", "ጣ", "ጤ", "ጥ", "ጦ", "ጧ"),
    # Row 29: Che (ejective)
    ("ጨ", "ጩ", "ጪ", "ጫ", "ጬ", "ጭ", "ጮ", "ጯ"),
    # Row 30: Pe (ejective)
    ("ጰ", "ጱ", "ጲ", "ጳ", "ጴ", "ጵ", "ጶ", "ጷ"),
    # Row 31: Tse2
    ("ጸ", "ጹ", "ጺ", "ጻ", "ጼ", "ጽ", "ጾ", "ጿ"),
    # Row 32: Tse3
    ("ፀ", "ፁ", "ፂ", "ፃ", "ፄ", "ፅ", "ፆ", "ፇ"),
    # Row 33: Fe
    ("ፈ", "ፉ", "ፊ", "ፋ", "ፌ", "ፍ", "ፎ", "ፏ"),
    # Row 34: Pe
    ("ፐ", "ፑ", "ፒ", "ፓ", "ፔ", "ፕ", "ፖ", "ፗ"),
)

# Reverse lookup: glyph -> (row, col) -- 1-indexed
_GLYPH_INDEX: dict[str, tuple[int, int]] = {}
for _r_idx, _row in enumerate(FIDEL_GEBETA):
    for _c_idx, _glyph in enumerate(_row):
        _GLYPH_INDEX[_glyph] = (_r_idx + 1, _c_idx + 1)

# Vowel order names for audio formulas
_VOWEL_ORDERS = ("ge'ez", "ka'ib", "salis", "rabi'", "hamis", "sadis", "sabi'", "diqala")

# Total fidel count (dimension for vectors)
_DIMENSION = 34 * 8  # 272


def _validate_fidel_text(text: str) -> None:
    """Reject non-fidel, non-whitespace characters.

    Mfidel processing is fail-closed: operational callers must supply either
    fidel symbols from the gebeta or plain whitespace separators.
    """
    invalid_positions: list[str] = []
    for index, char in enumerate(text):
        if char.isspace():
            continue
        if char not in _GLYPH_INDEX:
            invalid_positions.append(str(index))
    if invalid_positions:
        raise ValueError(
            "text contains non-fidel characters at positions "
            + ", ".join(invalid_positions)
        )


class MfidelMatrix:
    """Stateless Ge'ez fidel matrix operations: lookup, audio, vectorize, similarity."""

    # -- Lookup --------------------------------------------------------------

    @staticmethod
    def lookup(row: int, col: int) -> Fidel:
        """Return the Fidel at the given 1-indexed (row, col) position."""
        if row < 1 or row > 34:
            raise ValueError("row must be between 1 and 34")
        if col < 1 or col > 8:
            raise ValueError("col must be between 1 and 8")
        glyph = FIDEL_GEBETA[row - 1][col - 1]
        whisper_id = f"fidel-{row:02d}-{col:02d}"
        return Fidel(row=row, col=col, glyph=glyph, whisper_id=whisper_id)

    @staticmethod
    def glyph_to_position(glyph: str) -> tuple[int, int] | None:
        """Return (row, col) for a glyph, or None if not found."""
        return _GLYPH_INDEX.get(glyph)

    # -- Audio formula -------------------------------------------------------

    @staticmethod
    def audio_formula(row: int, col: int) -> FidelAudioFormula:
        """Compute audio formula for the fidel at (row, col).

        Exceptions:
          - Row 1, Col 1 (ሀ): glottal onset exception
          - Row 3, Col 1 (ሐ): pharyngeal onset exception
          - Col 8 (any row): labialized extension exception
        """
        fidel = MfidelMatrix.lookup(row, col)
        vowel_order = _VOWEL_ORDERS[col - 1]
        whisper = f"w-{row:02d}-{col:02d}"
        vibratory = f"v-{row:02d}-{vowel_order}"

        exception_type: str | None = None
        if row == 1 and col == 1:
            exception_type = "glottal_onset"
        elif row == 3 and col == 1:
            exception_type = "pharyngeal_onset"
        elif col == 8:
            exception_type = "labialized_extension"

        formula_text = f"R{row:02d}C{col:02d}:{vowel_order}"
        if exception_type:
            formula_text += f" [{exception_type}]"

        return FidelAudioFormula(
            fidel=fidel,
            whisper_component=whisper,
            vibratory_component=vibratory,
            formula_text=formula_text,
            exception_type=exception_type,
        )

    # -- Text to fidel sequence ----------------------------------------------

    @staticmethod
    def text_to_fidel_sequence(text: str) -> tuple[Fidel, ...]:
        """Convert a string of Ge'ez characters to a tuple of Fidel objects.

        Whitespace separators are ignored. Any other non-fidel character is
        rejected to preserve explicit symbolic boundaries.
        """
        _validate_fidel_text(text)
        result: list[Fidel] = []
        for ch in text:
            pos = _GLYPH_INDEX.get(ch)
            if pos is not None:
                r, c = pos
                result.append(MfidelMatrix.lookup(r, c))
        return tuple(result)

    # -- Vectorization -------------------------------------------------------

    @staticmethod
    def vectorize(text: str) -> MfidelVector:
        """Produce a 272-dimensional normalized bag-of-fidels vector from text."""
        _validate_fidel_text(text)
        weights = [0.0] * _DIMENSION
        for ch in text:
            pos = _GLYPH_INDEX.get(ch)
            if pos is not None:
                r, c = pos
                idx = (r - 1) * 8 + (c - 1)
                weights[idx] += 1.0

        # Normalize
        magnitude = math.sqrt(sum(w * w for w in weights))
        if magnitude > 0:
            weights = [w / magnitude for w in weights]
            normalized = True
        else:
            normalized = False

        vector_id = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        return MfidelVector(
            vector_id=vector_id,
            fidel_weights=tuple(weights),
            dimension=_DIMENSION,
            normalized=normalized,
        )

    # -- Similarity ----------------------------------------------------------

    @staticmethod
    def similarity(vec_a: MfidelVector, vec_b: MfidelVector) -> float:
        """Compute cosine similarity between two MfidelVectors. Returns 0.0-1.0."""
        dot = sum(a * b for a, b in zip(vec_a.fidel_weights, vec_b.fidel_weights))
        mag_a = math.sqrt(sum(a * a for a in vec_a.fidel_weights))
        mag_b = math.sqrt(sum(b * b for b in vec_b.fidel_weights))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        score = dot / (mag_a * mag_b)
        # Clamp to [0, 1] to guard against float imprecision
        return max(0.0, min(1.0, score))
