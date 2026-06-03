"""Purpose: adapt the existing (toothless) peer-review engine into the cognitive
    loop's consequential InnerCritic seam, so a mechanically-passing outcome that
    carries model-generated text with hallucination/contradiction markers is
    DOWNGRADED (not trusted, not learned) instead of merely flagged into the void.
Governance scope: VERIFY-phase inner-critic adaptation only. This module adds no
    new verification heuristics of its own; it delegates verdicts to the existing
    ``core.peer_review`` engine and maps them onto the monotone-skeptic critic
    contract. It never mutates engine or loop state.
Dependencies:
  - mcoi_runtime.core.peer_review.verify_response / VerificationVerdict (the
    existing heuristic engine - reused verbatim, never re-implemented here)
  - mcoi_runtime.core.cognitive_loop.CriticVerdict / InnerCritic (the seam)
  - mcoi_runtime.contracts.execution.ExecutionResult (the object under review)
Invariants:
  - Monotone-skeptic: review() returns ``accepted=False`` ONLY to downgrade; it
    never grants trust the mechanical proof did not already grant (the loop only
    consults a critic when the mechanical proof already passed).
  - Deterministic + side-effect free: verify_response is a pure heuristic, and
    text extraction is a pure function of the ExecutionResult. Identical inputs
    yield an identical CriticVerdict.
  - Honest scope (no green-but-unwired overclaim): peer_review's markers target
    LLM self-talk. When the ExecutionResult carries NO model-generated text this
    critic ABSTAINS (accepts) rather than blocking blindly - downgrading on
    no-evidence would be wrong. It bites exactly where reviewable text flows.
  - Abstain-safe: a missing/empty text surface => accept (defer to the mechanical
    proof). Only a positive CONTRADICTED/FLAGGED verdict downgrades.
"""

from __future__ import annotations

from typing import Mapping

from mcoi_runtime.contracts.execution import ExecutionResult
from mcoi_runtime.core.cognitive_loop import CriticVerdict
from mcoi_runtime.core.peer_review import VerificationVerdict, verify_response


# Metadata / extension / effect-detail keys under which model-generated text is
# conventionally carried. Ordered: the first non-empty string wins as the
# reviewable "response". Extend deliberately - each key is a real surface the
# runtime is known to populate with model output.
_TEXT_KEYS: tuple[str, ...] = (
    "response",
    "output",
    "text",
    "content",
    "message",
    "completion",
    "answer",
    "summary",
)
# Keys that may carry the originating instruction, used only to give
# verify_response a prompt context (improves its length-anomaly heuristic).
_PROMPT_KEYS: tuple[str, ...] = ("prompt", "goal", "instruction", "query")


def _first_text(source: Mapping[str, object] | None, keys: tuple[str, ...]) -> str:
    """Return the first non-empty string value among ``keys`` (pure)."""
    if not isinstance(source, Mapping):
        return ""
    for key in keys:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def extract_reviewable_text(execution_result: ExecutionResult) -> tuple[str, str]:
    """Extract ``(prompt, response)`` reviewable text from an ExecutionResult.

    Pure function. Looks in metadata, then extensions, then string-valued effect
    details. Returns ``("", "")`` when nothing reviewable is present (the critic
    then abstains). This is the ONLY place text is sourced, so the critic's bite
    is exactly as wide as the runtime's known text surfaces - no hidden guesses.
    """
    prompt = _first_text(execution_result.metadata, _PROMPT_KEYS) or _first_text(
        execution_result.extensions, _PROMPT_KEYS
    )

    response = _first_text(execution_result.metadata, _TEXT_KEYS) or _first_text(
        execution_result.extensions, _TEXT_KEYS
    )
    if not response:
        for effect in execution_result.actual_effects:
            details = effect.details
            if isinstance(details, str) and details.strip():
                response = details
                break
            if isinstance(details, Mapping):
                candidate = _first_text(details, _TEXT_KEYS)
                if candidate:
                    response = candidate
                    break
    return prompt, response


class PeerReviewCritic:
    """An InnerCritic backed by the existing heuristic peer-review engine.

    Maps peer-review verdicts onto the monotone-skeptic critic contract:
      - CONTRADICTED -> always reject (clear factual inconsistency).
      - FLAGGED      -> reject when ``strict`` (default), else accept (advisory).
      - CONSISTENT   -> accept.
      - no reviewable text -> abstain (accept), deferring to the mechanical proof.

    ``strict`` defaults to True so a flagged outcome is treated as untrusted - the
    whole point of the seam is that peer-review findings finally have teeth. Set
    ``strict=False`` to keep flags advisory (accept but record the reason).
    """

    def __init__(self, *, strict: bool = True) -> None:
        self._strict = bool(strict)

    @property
    def strict(self) -> bool:
        return self._strict

    def review(
        self,
        *,
        capability_id: str,
        execution_result: ExecutionResult,
        mechanical_verification_passed: bool,
    ) -> CriticVerdict:
        prompt, response = extract_reviewable_text(execution_result)
        if not response:
            # Abstain: no model-generated text to review => defer to the proof.
            return CriticVerdict(
                accepted=True,
                confidence=0.5,
                reason="peer-review critic abstained: no reviewable model text in result",
            )

        # capability_id is a minimal prompt context when none is carried.
        result = verify_response(prompt or capability_id, response)

        # Canonical-reason discipline: ``reason`` is a fixed string per verdict;
        # the variable marker detail rides in ``issues`` (non-contract field), so
        # this passes the reflective-contract guard without losing diagnostics.
        if result.verdict is VerificationVerdict.CONTRADICTED:
            return CriticVerdict(
                accepted=False,
                confidence=result.confidence,
                reason="peer-review contradicted the outcome",
                issues=result.issues,
            )
        if result.verdict is VerificationVerdict.FLAGGED:
            if self._strict:
                return CriticVerdict(
                    accepted=False,
                    confidence=result.confidence,
                    reason="peer-review flagged the outcome (strict)",
                    issues=result.issues,
                )
            return CriticVerdict(
                accepted=True,
                confidence=result.confidence,
                reason="peer-review flagged the outcome (advisory)",
                issues=result.issues,
            )
        return CriticVerdict(
            accepted=True,
            confidence=result.confidence,
            reason="peer-review consistent",
        )


__all__ = [
    "PeerReviewCritic",
    "extract_reviewable_text",
]
