"""Peer-Review Verification — Second model checks primary output.

Purpose: After the primary LLM generates a response, a verification model
    checks for factual consistency, hallucination markers, and safety issues.
    Inspired by Grok's 4-agent peer-review that reduces hallucinations
    from 12% to 4.2%.

Invariants:
  - Verification is optional (configurable per tenant/request).
  - Verification model is always cheaper than primary model.
  - Flagged responses are audited with the reason.
  - Verification never blocks — it flags for human review.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable


class VerificationVerdict(StrEnum):
    """Verdict from peer review."""

    CONSISTENT = "consistent"  # Response appears factually sound
    FLAGGED = "flagged"  # Potential issues detected — needs review
    CONTRADICTED = "contradicted"  # Clear factual inconsistency found


@dataclass(frozen=True, slots=True)
class PeerReviewResult:
    """Result of peer-review verification."""

    verdict: VerificationVerdict
    confidence: float  # 0.0-1.0
    issues: tuple[str, ...] = ()
    verification_model: str = ""


# Simple heuristic checks (production would use a second LLM call)
_HALLUCINATION_MARKERS = (
    "I cannot verify",
    "I'm not sure if",
    "This may not be accurate",
    "I don't have access to real-time",
    "As of my last update",
    "I should note that I",
)

_CONTRADICTION_MARKERS = (
    "actually, that's not correct",
    "I need to correct",
    "contrary to what I said",
    "I was wrong about",
)


def verify_response(
    prompt: str,
    response: str,
    *,
    check_hallucination: bool = True,
    check_consistency: bool = True,
) -> PeerReviewResult:
    """Verify an LLM response for factual consistency.

    Uses heuristic markers for initial implementation.
    Production would call a second, cheaper model as verifier.
    """
    issues: list[str] = []

    if not response:
        return PeerReviewResult(
            verdict=VerificationVerdict.CONSISTENT,
            confidence=1.0,
        )

    response_lower = response.lower()

    # Check for self-admitted uncertainty (hallucination markers)
    if check_hallucination:
        for marker in _HALLUCINATION_MARKERS:
            if marker.lower() in response_lower:
                issues.append(f"uncertainty marker: '{marker}'")

    # Check for self-contradiction
    if check_consistency:
        for marker in _CONTRADICTION_MARKERS:
            if marker.lower() in response_lower:
                issues.append(f"contradiction marker: '{marker}'")

    # Check response length anomalies
    prompt_words = len(prompt.split())
    response_words = len(response.split())
    if prompt_words < 10 and response_words > 500:
        issues.append("disproportionately long response for short prompt")

    # Determine verdict
    if any("contradiction" in i for i in issues):
        verdict = VerificationVerdict.CONTRADICTED
        confidence = 0.8
    elif issues:
        verdict = VerificationVerdict.FLAGGED
        confidence = 0.7
    else:
        verdict = VerificationVerdict.CONSISTENT
        confidence = 0.85

    return PeerReviewResult(
        verdict=verdict,
        confidence=confidence,
        issues=tuple(issues),
        verification_model="heuristic-v1",
    )


class PeerReviewEngine:
    """Engine that runs peer-review verification on LLM responses.

    Configurable per tenant — some tenants may want strict verification,
    others may skip it for speed.
    """

    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = enabled
        self._review_count = 0
        self._flagged_count = 0

    @property
    def enabled(self) -> bool:
        return self._enabled

    def review(self, prompt: str, response: str) -> PeerReviewResult:
        """Review an LLM response. Returns verification result."""
        if not self._enabled:
            return PeerReviewResult(
                verdict=VerificationVerdict.CONSISTENT,
                confidence=1.0,
                verification_model="disabled",
            )

        self._review_count += 1
        result = verify_response(prompt, response)
        if result.verdict != VerificationVerdict.CONSISTENT:
            self._flagged_count += 1
        return result

    @property
    def review_count(self) -> int:
        return self._review_count

    @property
    def flagged_count(self) -> int:
        return self._flagged_count

    def summary(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "reviews": self._review_count,
            "flagged": self._flagged_count,
            "flag_rate": round(self._flagged_count / max(1, self._review_count), 3),
        }
