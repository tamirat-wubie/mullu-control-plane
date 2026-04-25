"""Phase 3B — Content Safety Filter Chain.

Purpose: Detect and block unsafe content in LLM inputs and outputs.
    Covers prompt injection detection, harmful content filtering,
    and output validation. Integrates with the governance guard chain.
Governance scope: content safety enforcement only.
Dependencies: stdlib (re).
Invariants:
  - Filters run in registration order (fail-fast on first block).
  - Prompt injection patterns are conservative (minimize false positives).
  - All filter decisions are auditable with reason + matched pattern.
  - Disabled filters are skipped (hot-toggleable).
  - Filter chain is stateless — no content is stored.
"""

from __future__ import annotations

import base64
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcoi_runtime.core.governance_guard import GovernanceGuard


LAMBDA_INPUT_SAFETY = "Lambda_input_safety"
LAMBDA_OUTPUT_SAFETY = "Lambda_output_safety"


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
    """Normalize only non-Ethiopic segments."""
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


class SafetyVerdict(str, Enum):
    """Verdict from content safety evaluation."""

    SAFE = "safe"
    FLAGGED = "flagged"  # Suspicious but allowed (logged)
    BLOCKED = "blocked"  # Rejected — will not be processed


class ThreatCategory(str, Enum):
    """Categories of content safety threats."""

    PROMPT_INJECTION = "prompt_injection"
    JAILBREAK = "jailbreak"
    PII_EXPOSURE = "pii_exposure"
    HARMFUL_CONTENT = "harmful_content"
    CODE_INJECTION = "code_injection"
    DATA_EXFILTRATION = "data_exfiltration"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class SafetyFilterResult:
    """Result of a single safety filter check."""

    filter_name: str
    verdict: SafetyVerdict
    category: ThreatCategory
    reason: str = ""
    matched_pattern: str = ""
    confidence: float = 1.0  # 0.0-1.0


@dataclass(frozen=True, slots=True)
class ContentSafetyResult:
    """Result of running the full content safety chain."""

    verdict: SafetyVerdict
    filter_results: tuple[SafetyFilterResult, ...]
    blocking_filter: str = ""
    reason: str = ""

    @property
    def is_safe(self) -> bool:
        return self.verdict == SafetyVerdict.SAFE

    @property
    def flagged_count(self) -> int:
        return sum(1 for r in self.filter_results if r.verdict == SafetyVerdict.FLAGGED)


@dataclass(frozen=True, slots=True)
class OutputSafetyResult:
    """Result of output safety validation and deterministic scrubbing."""

    allowed: bool
    content: str
    stage_name: str = LAMBDA_OUTPUT_SAFETY
    reason: str = ""
    pii_redacted: bool = False
    content_verdict: SafetyVerdict = SafetyVerdict.SAFE
    flags: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class SafetyPattern:
    """A named pattern for content safety detection."""

    name: str
    pattern: str  # Regex
    category: ThreatCategory
    verdict: SafetyVerdict = SafetyVerdict.BLOCKED
    description: str = ""


# ═══ Built-in Safety Patterns ═══

PROMPT_INJECTION_PATTERNS: tuple[SafetyPattern, ...] = (
    SafetyPattern(
        name="system_override",
        pattern=r"(?i)(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|above|prior)\s+(?:instructions|prompts|rules)",
        category=ThreatCategory.PROMPT_INJECTION,
        verdict=SafetyVerdict.BLOCKED,
        description="Attempts to override system instructions",
    ),
    SafetyPattern(
        name="role_hijack",
        pattern=r"(?i)you\s+are\s+now\s+(?:a|an|the)\s+(?:different|new|evil|unrestricted)",
        category=ThreatCategory.JAILBREAK,
        verdict=SafetyVerdict.BLOCKED,
        description="Attempts to redefine the symbolic intelligence role",
    ),
    SafetyPattern(
        name="system_prompt_leak",
        pattern=r"(?i)(?:reveal|show|print|output|display|repeat)\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions|rules|guidelines)",
        category=ThreatCategory.PROMPT_INJECTION,
        verdict=SafetyVerdict.FLAGGED,
        description="Attempts to extract system prompt",
    ),
    SafetyPattern(
        name="encoded_injection",
        pattern=r"(?i)(?:base64|hex|rot13|unicode)\s*(?:decode|encode)\s*[:\(]",
        category=ThreatCategory.PROMPT_INJECTION,
        verdict=SafetyVerdict.FLAGGED,
        description="Encoded content that may hide injection",
    ),
    SafetyPattern(
        name="data_exfil_url",
        pattern=r"(?i)(?:send|post|transmit|exfiltrate|upload)\s+(?:to|data\s+to)\s+(?:https?://|ftp://)",
        category=ThreatCategory.DATA_EXFILTRATION,
        verdict=SafetyVerdict.BLOCKED,
        description="Attempts to exfiltrate data to external URLs",
    ),
    SafetyPattern(
        name="code_exec_attempt",
        pattern=r"(?i)(?:exec|eval|import\s+os|subprocess|system)\s*\(",
        category=ThreatCategory.CODE_INJECTION,
        verdict=SafetyVerdict.FLAGGED,
        description="Code execution patterns in prompts",
    ),
)


class ContentSafetyFilter:
    """A single content safety filter with pattern matching."""

    def __init__(
        self,
        name: str,
        patterns: tuple[SafetyPattern, ...],
        *,
        enabled: bool = True,
    ) -> None:
        self.name = name
        self._patterns = patterns
        self._compiled: list[tuple[SafetyPattern, re.Pattern[str]]] = [
            (p, re.compile(p.pattern)) for p in patterns
        ]
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def check(self, content: str) -> SafetyFilterResult | None:
        """Check content against filter patterns.

        Returns SafetyFilterResult if a pattern matches, None if content is clean.
        """
        if not self._enabled or not content:
            return None

        for pattern_def, compiled in self._compiled:
            match = compiled.search(content)
            if match:
                return SafetyFilterResult(
                    filter_name=self.name,
                    verdict=pattern_def.verdict,
                    category=pattern_def.category,
                    reason=pattern_def.description,
                    matched_pattern=pattern_def.name,
                )
        return None


def normalize_content(text: str) -> str:
    """Normalize text to defeat common bypass techniques.

    Applies:
    1. Unicode NFKC normalization (collapses homoglyphs: Cyrillic а → Latin a)
    2. Strip zero-width characters (ZWJ, ZWNJ, ZWSP, soft hyphens)
    3. Collapse whitespace variants (non-breaking space, em/en space → regular space)
    4. Decode obvious base64 segments and append decoded text
    """
    if not text:
        return text

    # 1. NFKC normalization — maps homoglyphs to canonical forms
    normalized = _normalize_non_ethiopic_runs(text)

    # 2. Strip zero-width and invisible characters
    _INVISIBLE = frozenset({
        "\u200b",  # Zero-width space
        "\u200c",  # Zero-width non-joiner
        "\u200d",  # Zero-width joiner
        "\u00ad",  # Soft hyphen
        "\u2060",  # Word joiner
        "\ufeff",  # Zero-width no-break space (BOM)
    })
    normalized = "".join(c for c in normalized if c not in _INVISIBLE)

    # 3. Collapse whitespace variants to regular space
    normalized = re.sub(r"[\u00a0\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f]+", " ", normalized)

    # 4. Detect and decode base64 segments (≥20 chars of base64 alphabet)
    b64_pattern = re.compile(r"[A-Za-z0-9+/=]{20,}")
    decoded_parts: list[str] = []
    for match in b64_pattern.finditer(normalized):
        try:
            decoded = base64.b64decode(match.group(), validate=True).decode("utf-8", errors="ignore")
            if decoded and any(c.isalpha() for c in decoded):
                decoded_parts.append(decoded)
        except Exception:
            pass

    if decoded_parts:
        normalized = normalized + " " + " ".join(decoded_parts)

    # 5. Decode HTML entities (&#82;&#101;... → Re...)
    import html
    html_decoded = html.unescape(normalized)
    if html_decoded != normalized:
        normalized = normalized + " " + html_decoded

    # 6. Decode percent-encoded sequences (%52%65... → Re...)
    try:
        from urllib.parse import unquote
        url_decoded = unquote(normalized)
        if url_decoded != normalized:
            normalized = normalized + " " + url_decoded
    except Exception:
        pass

    return normalized


class ContentSafetyChain:
    """Ordered chain of content safety filters.

    Filters run in registration order. Accumulates flagged results.
    Stops on first BLOCKED verdict. Content is normalized before evaluation
    to defeat Unicode homoglyph, zero-width character, and encoding bypasses.
    """

    def __init__(self, *, normalize: bool = True) -> None:
        self._filters: list[ContentSafetyFilter] = []
        self._normalize = normalize

    def add(self, filter_: ContentSafetyFilter) -> None:
        self._filters.append(filter_)

    def evaluate(self, content: str) -> ContentSafetyResult:
        """Run all filters. Returns aggregate safety verdict.

        Content is normalized before pattern matching to prevent bypass
        via Unicode homoglyphs, zero-width characters, and base64 encoding.
        """
        # Pre-scan normalization
        if self._normalize and content:
            content = normalize_content(content)

        results: list[SafetyFilterResult] = []

        for f in self._filters:
            if not f.enabled:
                continue
            result = f.check(content)
            if result is not None:
                results.append(result)
                if result.verdict == SafetyVerdict.BLOCKED:
                    return ContentSafetyResult(
                        verdict=SafetyVerdict.BLOCKED,
                        filter_results=tuple(results),
                        blocking_filter=f.name,
                        reason=result.reason,
                    )

        # If any flags but no blocks
        if any(r.verdict == SafetyVerdict.FLAGGED for r in results):
            return ContentSafetyResult(
                verdict=SafetyVerdict.FLAGGED,
                filter_results=tuple(results),
            )

        return ContentSafetyResult(
            verdict=SafetyVerdict.SAFE,
            filter_results=tuple(results),
        )

    @property
    def filter_count(self) -> int:
        return len(self._filters)

    def filter_names(self) -> list[str]:
        return [f.name for f in self._filters]


_DEFAULT_CHAIN: ContentSafetyChain | None = None


def build_default_safety_chain() -> ContentSafetyChain:
    """Build the default content safety chain with built-in filters.

    Returns a cached singleton — patterns are compiled once.
    """
    global _DEFAULT_CHAIN
    if _DEFAULT_CHAIN is None:
        chain = ContentSafetyChain()
        chain.add(ContentSafetyFilter(
            name="prompt_injection",
            patterns=PROMPT_INJECTION_PATTERNS,
        ))
        _DEFAULT_CHAIN = chain
    return _DEFAULT_CHAIN


def create_content_safety_guard(
    chain: ContentSafetyChain,
) -> GovernanceGuard:
    """Create a content safety guard for the governance guard chain.

    Scans the request body/prompt for unsafe content before processing.
    Only activates when 'prompt' or 'content' is present in guard context.
    """
    from mcoi_runtime.core.governance_guard import GovernanceGuard, GuardResult

    def check(ctx: dict[str, Any]) -> GuardResult:
        content = ctx.get("prompt", "") or ctx.get("content", "")
        if not content:
            return GuardResult(allowed=True, guard_name="content_safety")

        result = chain.evaluate(content)
        if result.verdict == SafetyVerdict.BLOCKED:
            return GuardResult(
                allowed=False, guard_name="content_safety",
                reason="content blocked",
            )

        # Flagged content is allowed but noted in context for audit
        if result.verdict == SafetyVerdict.FLAGGED:
            ctx["content_safety_flags"] = [
                {"filter": r.filter_name, "category": r.category.value, "reason": r.reason}
                for r in result.filter_results
                if r.verdict == SafetyVerdict.FLAGGED
            ]

        return GuardResult(allowed=True, guard_name="content_safety")

    return GovernanceGuard("content_safety", check)


def create_input_safety_guard(
    chain: ContentSafetyChain,
) -> GovernanceGuard:
    """Create Lambda_input_safety for the governance guard chain."""
    from mcoi_runtime.core.governance_guard import GovernanceGuard, GuardResult

    def check(ctx: dict[str, Any]) -> GuardResult:
        content = ctx.get("prompt", "") or ctx.get("content", "")
        if not content:
            return GuardResult(allowed=True, guard_name=LAMBDA_INPUT_SAFETY)

        result = chain.evaluate(content)
        if result.verdict == SafetyVerdict.BLOCKED:
            return GuardResult(
                allowed=False,
                guard_name=LAMBDA_INPUT_SAFETY,
                reason="input safety blocked",
                detail={
                    "category": result.filter_results[-1].category.value if result.filter_results else "",
                    "blocking_filter": result.blocking_filter,
                },
            )

        if result.verdict == SafetyVerdict.FLAGGED:
            ctx["content_safety_flags"] = [
                {"filter": r.filter_name, "category": r.category.value, "reason": r.reason}
                for r in result.filter_results
                if r.verdict == SafetyVerdict.FLAGGED
            ]
            ctx["input_safety_stage"] = LAMBDA_INPUT_SAFETY

        return GuardResult(allowed=True, guard_name=LAMBDA_INPUT_SAFETY)

    return GovernanceGuard(LAMBDA_INPUT_SAFETY, check)


def evaluate_output_safety(
    content: str,
    *,
    chain: ContentSafetyChain | None = None,
    pii_scanner: Any | None = None,
) -> OutputSafetyResult:
    """Run Lambda_output_safety over model output and return scrubbed content."""
    safe_content = content or ""
    pii_redacted = False
    flags: list[dict[str, str]] = []

    if pii_scanner is not None and safe_content:
        scan_result = pii_scanner.scan(safe_content)
        safe_content = scan_result.redacted_text
        pii_redacted = bool(scan_result.pii_detected)
        if scan_result.pii_detected:
            flags.append({
                "filter": "pii_scanner",
                "category": ThreatCategory.PII_EXPOSURE.value,
                "reason": "output PII redacted",
            })

    if chain is not None and safe_content:
        safety_result = chain.evaluate(safe_content)
        if safety_result.verdict == SafetyVerdict.BLOCKED:
            return OutputSafetyResult(
                allowed=False,
                content="",
                reason="output safety blocked",
                pii_redacted=pii_redacted,
                content_verdict=safety_result.verdict,
                flags=tuple(flags),
            )
        for result in safety_result.filter_results:
            if result.verdict == SafetyVerdict.FLAGGED:
                flags.append({
                    "filter": result.filter_name,
                    "category": result.category.value,
                    "reason": result.reason,
                })
        return OutputSafetyResult(
            allowed=True,
            content=safe_content,
            pii_redacted=pii_redacted,
            content_verdict=safety_result.verdict,
            flags=tuple(flags),
        )

    return OutputSafetyResult(
        allowed=True,
        content=safe_content,
        pii_redacted=pii_redacted,
        flags=tuple(flags),
    )


def create_output_safety_guard(
    *,
    chain: ContentSafetyChain | None = None,
    pii_scanner: Any | None = None,
) -> GovernanceGuard:
    """Create Lambda_output_safety for contexts that carry model output."""
    from mcoi_runtime.core.governance_guard import GovernanceGuard, GuardResult

    def check(ctx: dict[str, Any]) -> GuardResult:
        content = ctx.get("output", "")
        if not isinstance(content, str) or not content:
            return GuardResult(allowed=True, guard_name=LAMBDA_OUTPUT_SAFETY)

        result = evaluate_output_safety(content, chain=chain, pii_scanner=pii_scanner)
        ctx["output_safety_stage"] = LAMBDA_OUTPUT_SAFETY
        ctx["output_safety_flags"] = list(result.flags)
        ctx["output"] = result.content
        if not result.allowed:
            return GuardResult(
                allowed=False,
                guard_name=LAMBDA_OUTPUT_SAFETY,
                reason=result.reason,
            )
        return GuardResult(allowed=True, guard_name=LAMBDA_OUTPUT_SAFETY)

    return GovernanceGuard(LAMBDA_OUTPUT_SAFETY, check)
