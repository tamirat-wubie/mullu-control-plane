"""Phase 3A — PII Scanner & Redaction Engine.

Purpose: Detect and redact personally identifiable information (PII) in
    text payloads, LLM prompts/responses, and data fields. Supports
    configurable patterns and redaction levels per tenant.
Governance scope: PII detection and redaction only — never modifies business logic.
Dependencies: stdlib (re, hashlib).
Invariants:
  - PII patterns are regex-based with named categories.
  - Redaction is deterministic — same input produces same output.
  - Full redaction replaces with placeholder; partial masks middle chars.
  - Hash redaction produces consistent tokens for linking without exposure.
  - Scanner is stateless — no PII is ever stored.
  - All detected PII is counted for audit reporting.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


_ETHIOPIC_RANGES: tuple[tuple[int, int], ...] = (
    (0x1200, 0x137F),
    (0x1380, 0x139F),
    (0x2D80, 0x2DDF),
    (0xAB00, 0xAB2F),
)


def _is_ethiopic_char(char: str) -> bool:
    codepoint = ord(char)
    return any(start <= codepoint <= end for start, end in _ETHIOPIC_RANGES)


def _normalize_non_ethiopic_runs(text: str) -> str:
    if not text:
        return text

    pieces: list[str] = []
    current_run: list[str] = []
    current_is_ethiopic: bool | None = None

    for char in text:
        char_is_ethiopic = _is_ethiopic_char(char)
        if current_is_ethiopic is None:
            current_is_ethiopic = char_is_ethiopic
        elif char_is_ethiopic != current_is_ethiopic:
            segment = "".join(current_run)
            pieces.append(
                segment if current_is_ethiopic else unicodedata.normalize("NFKC", segment)
            )
            current_run = []
            current_is_ethiopic = char_is_ethiopic
        current_run.append(char)

    if current_run:
        segment = "".join(current_run)
        pieces.append(
            segment if current_is_ethiopic else unicodedata.normalize("NFKC", segment)
        )

    return "".join(pieces)


class PIICategory(str, Enum):
    """Categories of personally identifiable information."""

    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    DATE_OF_BIRTH = "date_of_birth"
    NAME = "name"
    ADDRESS = "address"
    API_KEY = "api_key"
    PASSWORD = "password"
    CUSTOM = "custom"


class RedactionMode(str, Enum):
    """How to redact detected PII."""

    FULL = "full"  # Replace with [REDACTED:category]
    PARTIAL = "partial"  # Mask middle characters
    HASH = "hash"  # Replace with deterministic hash token
    NONE = "none"  # Detect but don't redact


@dataclass(frozen=True, slots=True)
class PIIPattern:
    """A named pattern for PII detection."""

    category: PIICategory
    pattern: str  # Regex pattern
    redaction_mode: RedactionMode = RedactionMode.FULL
    description: str = ""


@dataclass(frozen=True, slots=True)
class PIIMatch:
    """A single PII detection result."""

    category: PIICategory
    start: int
    end: int
    original_length: int
    redacted_value: str


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Result of scanning text for PII."""

    original_length: int
    redacted_text: str
    matches: tuple[PIIMatch, ...]
    pii_detected: bool
    category_counts: dict[str, int] = field(default_factory=dict)


# ═══ Built-in PII Patterns ═══

BUILTIN_PATTERNS: tuple[PIIPattern, ...] = (
    PIIPattern(
        category=PIICategory.EMAIL,
        pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        redaction_mode=RedactionMode.FULL,
        description="Email addresses",
    ),
    PIIPattern(
        category=PIICategory.PHONE,
        pattern=r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b",
        redaction_mode=RedactionMode.PARTIAL,
        description="US phone numbers",
    ),
    PIIPattern(
        category=PIICategory.SSN,
        pattern=r"\b\d{3}-\d{2}-\d{4}\b",
        redaction_mode=RedactionMode.FULL,
        description="US Social Security Numbers",
    ),
    PIIPattern(
        category=PIICategory.CREDIT_CARD,
        pattern=r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
        redaction_mode=RedactionMode.PARTIAL,
        description="Credit card numbers (16 digits)",
    ),
    PIIPattern(
        category=PIICategory.IP_ADDRESS,
        pattern=r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        redaction_mode=RedactionMode.FULL,
        description="IPv4 addresses",
    ),
    PIIPattern(
        category=PIICategory.API_KEY,
        pattern=r"\b(?:sk-|pk-|ak-|key-)[A-Za-z0-9]{20,}\b",
        redaction_mode=RedactionMode.FULL,
        description="API keys with common prefixes",
    ),
    PIIPattern(
        category=PIICategory.PASSWORD,
        pattern=r'(?i)(?:password|passwd|pwd)\s*[=:]\s*\S+',
        redaction_mode=RedactionMode.FULL,
        description="Password assignments",
    ),
)


def _luhn_check(digits: str) -> bool:
    """Validate a digit string using the Luhn algorithm (ISO/IEC 7812-1).

    Returns True if the digit string passes the Luhn checksum.
    Used to reduce false positives on credit card detection.
    """
    if not digits or len(digits) < 13:
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _apply_redaction(match_text: str, category: PIICategory, mode: RedactionMode, salt: str = "") -> str:
    """Apply redaction to a matched PII value."""
    if mode == RedactionMode.NONE:
        return match_text
    if mode == RedactionMode.FULL:
        return f"[REDACTED:{category.value}]"
    if mode == RedactionMode.PARTIAL:
        if len(match_text) <= 4:
            return f"[REDACTED:{category.value}]"
        visible = max(2, len(match_text) // 4)
        return match_text[:visible] + "*" * (len(match_text) - visible * 2) + match_text[-visible:]
    if mode == RedactionMode.HASH:
        token = hashlib.sha256(f"{salt}{match_text}".encode()).hexdigest()[:12]
        return f"[HASH:{category.value}:{token}]"
    return f"[REDACTED:{category.value}]"


class PIIScanner:
    """Scans text for PII and applies redaction.

    Thread-safe (stateless). Patterns are compiled once at init.
    Custom patterns can be added per-tenant.
    """

    MAX_SCAN_LENGTH = 1_000_000  # 1MB max to prevent regex DoS

    def __init__(
        self,
        *,
        patterns: tuple[PIIPattern, ...] | None = None,
        hash_salt: str = "",
        enabled: bool = True,
    ) -> None:
        self._patterns = patterns or BUILTIN_PATTERNS
        self._compiled: list[tuple[PIIPattern, re.Pattern[str]]] = []
        self._hash_salt = hash_salt
        self._enabled = enabled

        for p in self._patterns:
            try:
                self._compiled.append((p, re.compile(p.pattern)))
            except re.error:
                pass  # Skip invalid patterns — logged at startup

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def pattern_count(self) -> int:
        return len(self._compiled)

    def scan(self, text: str) -> ScanResult:
        """Scan text for PII and return redacted version with match details."""
        if text is None:
            text = ""
        if not self._enabled or not text:
            return ScanResult(
                original_length=len(text),
                redacted_text=text,
                matches=(),
                pii_detected=False,
            )

        # Truncate to prevent regex DoS on very large texts
        if len(text) > self.MAX_SCAN_LENGTH:
            text = text[:self.MAX_SCAN_LENGTH]

        # Normalize only non-Ethiopic runs to preserve Mfidel atomicity.
        text = _normalize_non_ethiopic_runs(text)
        # Strip zero-width and invisible characters
        text = re.sub(r"[\u200b\u200c\u200d\u00ad\u2060\ufeff]", "", text)

        all_matches: list[tuple[int, int, PIIPattern, str]] = []
        for pattern_def, compiled in self._compiled:
            for m in compiled.finditer(text):
                matched = m.group()
                # Luhn validation for credit card matches (reduce false positives)
                if pattern_def.category == PIICategory.CREDIT_CARD:
                    digits = "".join(c for c in matched if c.isdigit())
                    if not _luhn_check(digits):
                        continue
                all_matches.append((m.start(), m.end(), pattern_def, matched))

        if not all_matches:
            return ScanResult(
                original_length=len(text),
                redacted_text=text,
                matches=(),
                pii_detected=False,
            )

        # Sort by start position, longest match first for overlaps
        all_matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))

        # Remove overlapping matches (keep first/longest)
        filtered: list[tuple[int, int, PIIPattern, str]] = []
        last_end = -1
        for start, end, pdef, matched in all_matches:
            if start >= last_end:
                filtered.append((start, end, pdef, matched))
                last_end = end

        # Apply redactions (reverse order to preserve positions)
        redacted = text
        pii_matches: list[PIIMatch] = []
        category_counts: dict[str, int] = {}

        for start, end, pdef, matched in reversed(filtered):
            replacement = _apply_redaction(matched, pdef.category, pdef.redaction_mode, self._hash_salt)
            redacted = redacted[:start] + replacement + redacted[end:]
            pii_matches.append(PIIMatch(
                category=pdef.category,
                start=start,
                end=end,
                original_length=len(matched),
                redacted_value=replacement,
            ))
            cat_key = pdef.category.value
            category_counts[cat_key] = category_counts.get(cat_key, 0) + 1

        pii_matches.reverse()  # Back to forward order

        return ScanResult(
            original_length=len(text),
            redacted_text=redacted,
            matches=tuple(pii_matches),
            pii_detected=True,
            category_counts=category_counts,
        )

    def scan_dict(self, data: dict[str, Any], *, max_depth: int = 5) -> tuple[dict[str, Any], list[PIIMatch]]:
        """Scan all string values in a dict for PII, returning redacted copy.

        Recursively scans nested dicts and lists up to max_depth.
        Returns (redacted_dict, all_matches).
        """
        if not isinstance(data, dict):
            return data, []  # type: ignore[return-value]
        all_matches: list[PIIMatch] = []
        redacted = self._scan_value(data, all_matches, depth=0, max_depth=max_depth)
        return redacted, all_matches

    def _scan_value(self, value: Any, matches: list[PIIMatch], depth: int, max_depth: int) -> Any:
        if depth > max_depth:
            return value
        if isinstance(value, str):
            result = self.scan(value)
            matches.extend(result.matches)
            return result.redacted_text
        if isinstance(value, dict):
            return {k: self._scan_value(v, matches, depth + 1, max_depth) for k, v in value.items()}
        if isinstance(value, list):
            return [self._scan_value(v, matches, depth + 1, max_depth) for v in value]
        return value

    def has_pii(self, text: str) -> bool:
        """Quick check: does the text contain any PII?"""
        if not self._enabled:
            return False
        for _, compiled in self._compiled:
            if compiled.search(text):
                return True
        return False
