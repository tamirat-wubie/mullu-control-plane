"""
Mfidel Atomic Substrate — 34x8 Universal Causal Encoding Grid.

Foundational layer for MUSIA. Each fidel is atomic:
- atomic shape (no Unicode decomposition)
- atomic whisper sound
- vibratory overlay via vowel column (row 17)

Hard rules:
- No root letters
- No phonetic decomposition
- Layering/fusion = sound only
- Each f[r][c] is irreducible
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

GRID_ROWS = 34
GRID_COLS = 8


class FidelKind(Enum):
    CONSONANT = "consonant"
    VOWEL = "vowel"  # row 17 only


@dataclass(frozen=True)
class FidelCoord:
    """Immutable coordinate identifying one atomic fidel."""

    row: int  # 1..34 (1-indexed to match Mfidel spec)
    col: int  # 1..8

    def __post_init__(self) -> None:
        if not (1 <= self.row <= GRID_ROWS):
            raise ValueError(f"row {self.row} out of range [1,{GRID_ROWS}]")
        if not (1 <= self.col <= GRID_COLS):
            raise ValueError(f"col {self.col} out of range [1,{GRID_COLS}]")


# Canonical Mfidel grid — atomic shapes only, no decomposition.
# Row 17 is the vowel/vibratory overlay row.
# Empty strings denote slots that have no atomic glyph in the MUSIA spec.
MFIDEL_GRID: tuple[tuple[str, ...], ...] = (
    # row 1: ሀ family (uses አ overlay exception)
    ("ሀ", "ሁ", "ሂ", "ሃ", "ሄ", "ህ", "ሆ", "ሇ"),
    ("ለ", "ሉ", "ሊ", "ላ", "ሌ", "ል", "ሎ", "ሏ"),
    ("ሐ", "ሑ", "ሒ", "ሓ", "ሔ", "ሕ", "ሖ", "ሗ"),  # row 3: ሐ exception
    ("መ", "ሙ", "ሚ", "ማ", "ሜ", "ም", "ሞ", "ሟ"),
    ("ሠ", "ሡ", "ሢ", "ሣ", "ሤ", "ሥ", "ሦ", "ሧ"),
    ("ረ", "ሩ", "ሪ", "ራ", "ሬ", "ር", "ሮ", "ሯ"),
    ("ሰ", "ሱ", "ሲ", "ሳ", "ሴ", "ስ", "ሶ", "ሷ"),
    ("ሸ", "ሹ", "ሺ", "ሻ", "ሼ", "ሽ", "ሾ", "ሿ"),
    ("ቀ", "ቁ", "ቂ", "ቃ", "ቄ", "ቅ", "ቆ", "ቋ"),
    ("በ", "ቡ", "ቢ", "ባ", "ቤ", "ብ", "ቦ", "ቧ"),
    ("ቨ", "ቩ", "ቪ", "ቫ", "ቬ", "ቭ", "ቮ", "ቯ"),
    ("ተ", "ቱ", "ቲ", "ታ", "ቴ", "ት", "ቶ", "ቷ"),
    ("ቸ", "ቹ", "ቺ", "ቻ", "ቼ", "ች", "ቾ", "ቿ"),
    ("ኀ", "ኁ", "ኂ", "ኃ", "ኄ", "ኅ", "ኆ", "ኈ"),
    ("ነ", "ኑ", "ኒ", "ና", "ኔ", "ን", "ኖ", "ኗ"),
    ("ኘ", "ኙ", "ኚ", "ኛ", "ኜ", "ኝ", "ኞ", "ኟ"),
    ("ኧ", "ኡ", "ኢ", "ኣ", "ኤ", "እ", "ኦ", "አ"),  # row 17: VOWELS
    ("ከ", "ኩ", "ኪ", "ካ", "ኬ", "ክ", "ኮ", "ኳ"),
    ("ኸ", "ኹ", "ኺ", "ኻ", "ኼ", "ኽ", "ኾ", "ዃ"),
    ("ወ", "ዉ", "ዊ", "ዋ", "ዌ", "ው", "ዎ", ""),
    ("ዐ", "ዑ", "ዒ", "ዓ", "ዔ", "ዕ", "ዖ", ""),
    ("ዘ", "ዙ", "ዚ", "ዛ", "ዜ", "ዝ", "ዞ", "ዟ"),
    ("ዠ", "ዡ", "ዢ", "ዣ", "ዤ", "ዥ", "ዦ", "ዧ"),
    ("የ", "ዩ", "ዪ", "ያ", "ዬ", "ይ", "ዮ", ""),
    ("ደ", "ዱ", "ዲ", "ዳ", "ዴ", "ድ", "ዶ", "ዷ"),
    ("ጀ", "ጁ", "ጂ", "ጃ", "ጄ", "ጅ", "ጆ", "ጇ"),
    ("ገ", "ጉ", "ጊ", "ጋ", "ጌ", "ግ", "ጎ", "ጓ"),
    ("ጠ", "ጡ", "ጢ", "ጣ", "ጤ", "ጥ", "ጦ", "ጧ"),
    ("ጨ", "ጩ", "ጪ", "ጫ", "ጬ", "ጭ", "ጮ", "ጯ"),
    ("ጰ", "ጱ", "ጲ", "ጳ", "ጴ", "ጵ", "ጶ", "ጷ"),
    ("ጸ", "ጹ", "ጺ", "ጻ", "ጼ", "ጽ", "ጾ", "ጿ"),
    ("ፀ", "ፁ", "ፂ", "ፃ", "ፄ", "ፅ", "ፆ", "ፇ"),
    ("ፈ", "ፉ", "ፊ", "ፋ", "ፌ", "ፍ", "ፎ", "ፏ"),
    ("ፐ", "ፑ", "ፒ", "ፓ", "ፔ", "ፕ", "ፖ", "ፗ"),
)

VOWEL_ROW = 17  # 1-indexed
VOWEL_NAMES: dict[int, str] = {
    1: "e",   # ኧ
    2: "u",   # ኡ
    3: "i",   # ኢ
    4: "a",   # ኣ
    5: "ie",  # ኤ
    6: "à",   # እ
    7: "o",   # ኦ
    8: "aa",  # አ
}

# Audio overlay exceptions — only ሀ and ሐ use አ (col 8) instead of ኧ (col 1)
AUDIO_OVERLAY_EXCEPTIONS: dict[FidelCoord, FidelCoord] = {
    FidelCoord(1, 1): FidelCoord(VOWEL_ROW, 8),   # ሀ uses አ
    FidelCoord(3, 1): FidelCoord(VOWEL_ROW, 8),   # ሐ uses አ
}


@dataclass(frozen=True)
class Fidel:
    """One atomic fidel. Irreducible. Identity-stable."""

    coord: FidelCoord
    glyph: str
    kind: FidelKind

    @property
    def is_vowel(self) -> bool:
        return self.coord.row == VOWEL_ROW

    @property
    def is_empty(self) -> bool:
        return self.glyph == ""


def fidel_at(row: int, col: int) -> Fidel:
    """Get atomic fidel at f[row][col]. 1-indexed."""
    coord = FidelCoord(row, col)
    glyph = MFIDEL_GRID[row - 1][col - 1]
    kind = FidelKind.VOWEL if row == VOWEL_ROW else FidelKind.CONSONANT
    # Soak telemetry — records the canonical-grid path lookup. Lazy import
    # avoids a circular load-time dependency since metrics.py lives one level up.
    from mcoi_runtime.substrate.metrics import REGISTRY, CANONICAL_GRID_PATH
    REGISTRY.record_lookup(CANONICAL_GRID_PATH)
    return Fidel(coord=coord, glyph=glyph, kind=kind)


def get_overlay_for(fidel: Fidel) -> Optional[Fidel]:
    """
    Return the vowel overlay fidel for audio formula:
    f[r][c].s(w,v) = f[r][c].s(w) + f[17][c].s(w,v)

    With exceptions for ሀ and ሐ which use አ overlay.
    Vowels themselves overlay onto themselves (identity).
    Empty slots have no overlay.
    """
    if fidel.is_empty:
        return None

    if fidel.coord in AUDIO_OVERLAY_EXCEPTIONS:
        oc = AUDIO_OVERLAY_EXCEPTIONS[fidel.coord]
        return fidel_at(oc.row, oc.col)

    # Column 8 family: f[r][8] uses f[17][4] overlay
    if fidel.coord.col == 8:
        return fidel_at(VOWEL_ROW, 4)

    return fidel_at(VOWEL_ROW, fidel.coord.col)


def all_fidels() -> list[Fidel]:
    """Enumerate all 272 atomic fidels (including empties for completeness)."""
    return [
        fidel_at(r, c)
        for r in range(1, GRID_ROWS + 1)
        for c in range(1, GRID_COLS + 1)
    ]


def non_empty_fidels() -> list[Fidel]:
    """Enumerate only fidels with actual glyphs."""
    return [f for f in all_fidels() if not f.is_empty]


def fidel_count() -> int:
    """Total non-empty atomic fidels available."""
    return len(non_empty_fidels())


# ---- INVARIANTS (verified at module load) ----


def _verify_grid_invariants() -> None:
    """Hard rules. Module fails to load if violated."""
    assert len(MFIDEL_GRID) == GRID_ROWS, f"expected {GRID_ROWS} rows"
    for row in MFIDEL_GRID:
        assert len(row) == GRID_COLS, f"expected {GRID_COLS} cols, got {len(row)}"

    vowels = MFIDEL_GRID[VOWEL_ROW - 1]
    assert vowels[0] == "ኧ", "row 17 col 1 must be ኧ"
    assert vowels[7] == "አ", "row 17 col 8 must be አ"

    assert MFIDEL_GRID[0][0] == "ሀ", "f[1][1] must be ሀ"
    assert MFIDEL_GRID[2][0] == "ሐ", "f[3][1] must be ሐ"

    for r, row in enumerate(MFIDEL_GRID, start=1):
        for c, glyph in enumerate(row, start=1):
            if glyph and len(glyph) > 1:
                raise ValueError(
                    f"non-atomic glyph at f[{r}][{c}]: {glyph!r}"
                )


_verify_grid_invariants()
