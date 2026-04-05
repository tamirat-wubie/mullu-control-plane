"""Purpose: commitment extraction engine.
Governance scope: extracting commitments, approvals, deadlines, owners,
    and escalation instructions from text sources.
Dependencies: commitment_extraction contracts, core invariants.
Invariants:
  - Extraction rules are deterministic and narrow.
  - Ambiguous signals fail-closed (AMBIGUOUS disposition).
  - No direct state mutation outside owned stores.
  - Typed rejection, not vague rejection.
  - Deterministic ordering of extracted candidates.
  - Duplicate commitment IDs rejected.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping

from ..contracts.commitment_extraction import (
    ApprovalSignal,
    CommitmentCandidate,
    CommitmentDisposition,
    CommitmentExtractionResult,
    CommitmentPromotionRecord,
    CommitmentRoutingDecision,
    CommitmentSourceType,
    CommitmentType,
    DeadlineSignal,
    EscalationSignal,
    ExtractionConfidenceLevel,
    OwnerSignal,
)
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Canonical extraction patterns (deterministic, narrow)
# ---------------------------------------------------------------------------

_APPROVAL_PATTERNS = [
    (re.compile(r"\b(approved|approve|go ahead)\b", re.IGNORECASE), True),
    (re.compile(r"(?<!not )(?<!don't )\b(proceed)\b", re.IGNORECASE), True),
    (re.compile(r"\b(rejected?|denied|do not proceed|don't proceed)\b", re.IGNORECASE), False),
]

_DEADLINE_PATTERNS = [
    re.compile(r"\b(by\s+\w+day)\b", re.IGNORECASE),
    re.compile(r"\b(before\s+\d{1,2}\s*(?:am|pm))\b", re.IGNORECASE),
    re.compile(r"\b(due\s+(?:today|tomorrow|next\s+\w+))\b", re.IGNORECASE),
    re.compile(r"\b(within\s+\d+\s+(?:hour|minute|day|week)s?)\b", re.IGNORECASE),
    re.compile(r"\b(by\s+(?:end\s+of\s+(?:day|week|month)|EOD|EOW|EOM))\b", re.IGNORECASE),
    re.compile(r"\b(by\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", re.IGNORECASE),
]

_OWNER_PATTERNS = [
    re.compile(r"\b(\w+)\s+will\s+(?:handle|take care of|follow up|do|complete)\b", re.IGNORECASE),
    re.compile(r"\bassign(?:ed)?\s+to\s+(\w+)\b", re.IGNORECASE),
    re.compile(r"\bsend\s+(?:it\s+)?to\s+(\w+)\b", re.IGNORECASE),
    re.compile(r"\b(\w+)\s+is\s+responsible\b", re.IGNORECASE),
]

_ESCALATION_PATTERNS = [
    re.compile(r"\b(escalate\s+to\s+\w+(?:\s+\w+)?)\b", re.IGNORECASE),
    re.compile(r"\b(notify\s+\w+(?:\s+\w+)?)\b", re.IGNORECASE),
    re.compile(r"\b(urgent\s+escalation)\b", re.IGNORECASE),
    re.compile(r"\b(page\s+\w+)\b", re.IGNORECASE),
]

_FOLLOW_UP_PATTERNS = [
    re.compile(r"\b(follow\s+up)\b", re.IGNORECASE),
    re.compile(r"\b(circle\s+back)\b", re.IGNORECASE),
    re.compile(r"\b(check\s+(?:in|back))\b", re.IGNORECASE),
]

_AMBIGUITY_PATTERNS = [
    re.compile(r"\b(maybe\s+later)\b", re.IGNORECASE),
    re.compile(r"\b(not\s+sure)\b", re.IGNORECASE),
    re.compile(r"\b(we(?:'ll)?\s+see)\b", re.IGNORECASE),
    re.compile(r"\b(possibly|perhaps|might)\b", re.IGNORECASE),
    re.compile(r"\b(let\s+me\s+think)\b", re.IGNORECASE),
    re.compile(r"\b(TBD|to\s+be\s+determined)\b", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class CommitmentExtractionEngine:
    """Extracts commitments, approvals, deadlines, owners, and escalation
    instructions from text sources using deterministic pattern matching.
    """

    def __init__(self) -> None:
        self._candidates: dict[str, CommitmentCandidate] = {}
        self._results: dict[str, CommitmentExtractionResult] = {}
        self._promotions: dict[str, CommitmentPromotionRecord] = {}
        self._routing: dict[str, CommitmentRoutingDecision] = {}

    # ------------------------------------------------------------------
    # Core text extraction
    # ------------------------------------------------------------------

    def extract_from_text(
        self,
        text: str,
        source_type: CommitmentSourceType,
        source_ref_id: str,
    ) -> CommitmentExtractionResult:
        """Extract all signals from raw text. Returns immutable result."""
        now = _now_iso()
        result_id = stable_identifier("extr", {"src": source_ref_id, "seq": str(len(self._results))})

        approvals = self._extract_approvals(text, source_ref_id, now)
        deadlines = self._extract_deadlines(text, source_ref_id, now)
        owners = self._extract_owners(text, source_ref_id, now)
        escalations = self._extract_escalations(text, source_ref_id, now)
        candidates = self._build_candidates(
            text, source_type, source_ref_id, now,
            approvals, deadlines, owners, escalations,
        )

        # Store candidates
        for c in candidates:
            if c.commitment_id not in self._candidates:
                self._candidates[c.commitment_id] = c

        result = CommitmentExtractionResult(
            result_id=result_id,
            source_type=source_type,
            source_ref_id=source_ref_id,
            candidates=tuple(candidates),
            approvals=tuple(approvals),
            deadlines=tuple(deadlines),
            owners=tuple(owners),
            escalations=tuple(escalations),
            created_at=now,
        )
        self._results[result_id] = result
        return result

    def extract_from_message(
        self,
        message_id: str,
        text: str,
    ) -> CommitmentExtractionResult:
        """Extract commitments from a message."""
        return self.extract_from_text(text, CommitmentSourceType.MESSAGE, message_id)

    def extract_from_transcript(
        self,
        transcript_id: str,
        text: str,
    ) -> CommitmentExtractionResult:
        """Extract commitments from a call transcript."""
        return self.extract_from_text(text, CommitmentSourceType.CALL_TRANSCRIPT, transcript_id)

    def extract_from_artifact(
        self,
        artifact_id: str,
        text: str,
    ) -> CommitmentExtractionResult:
        """Extract commitments from an ingested artifact."""
        return self.extract_from_text(text, CommitmentSourceType.ARTIFACT, artifact_id)

    # ------------------------------------------------------------------
    # Signal extraction helpers
    # ------------------------------------------------------------------

    def _extract_approvals(self, text: str, ref_id: str, now: str) -> list[ApprovalSignal]:
        signals = []
        for pattern, approved in _APPROVAL_PATTERNS:
            for match in pattern.finditer(text):
                signals.append(ApprovalSignal(
                    signal_id=stable_identifier("appr", {"ref": ref_id, "span": match.group(), "pos": match.start()}),
                    source_ref_id=ref_id,
                    approved=approved,
                    text_span=match.group(),
                    confidence=0.85,
                    created_at=now,
                ))
        return signals

    def _extract_deadlines(self, text: str, ref_id: str, now: str) -> list[DeadlineSignal]:
        signals = []
        for pattern in _DEADLINE_PATTERNS:
            for match in pattern.finditer(text):
                signals.append(DeadlineSignal(
                    signal_id=stable_identifier("dl", {"ref": ref_id, "span": match.group(), "pos": match.start()}),
                    source_ref_id=ref_id,
                    text_span=match.group(),
                    normalized_deadline=match.group().strip().lower(),
                    confidence=0.75,
                    created_at=now,
                ))
        return signals

    def _extract_owners(self, text: str, ref_id: str, now: str) -> list[OwnerSignal]:
        signals = []
        for pattern in _OWNER_PATTERNS:
            for match in pattern.finditer(text):
                owner_name = match.group(1).strip()
                # Skip common false positives
                if owner_name.lower() in ("i", "we", "they", "it", "this", "that", "someone"):
                    continue
                signals.append(OwnerSignal(
                    signal_id=stable_identifier("own", {"ref": ref_id, "owner": owner_name, "pos": match.start()}),
                    source_ref_id=ref_id,
                    text_span=match.group(),
                    normalized_owner=owner_name.lower(),
                    confidence=0.7,
                    created_at=now,
                ))
        return signals

    def _extract_escalations(self, text: str, ref_id: str, now: str) -> list[EscalationSignal]:
        signals = []
        for pattern in _ESCALATION_PATTERNS:
            for match in pattern.finditer(text):
                span = match.group()
                # Determine urgency
                urgency = "urgent" if "urgent" in span.lower() or "page" in span.lower() else "normal"
                # Extract target from span
                target = span
                for prefix in ("escalate to ", "notify ", "page "):
                    if span.lower().startswith(prefix):
                        target = span[len(prefix):]
                        break
                signals.append(EscalationSignal(
                    signal_id=stable_identifier("esc", {"ref": ref_id, "span": span, "pos": match.start()}),
                    source_ref_id=ref_id,
                    text_span=span,
                    target_description=target,
                    urgency=urgency,
                    confidence=0.8,
                    created_at=now,
                ))
        return signals

    # ------------------------------------------------------------------
    # Candidate building
    # ------------------------------------------------------------------

    def _build_candidates(
        self,
        text: str,
        source_type: CommitmentSourceType,
        ref_id: str,
        now: str,
        approvals: list[ApprovalSignal],
        deadlines: list[DeadlineSignal],
        owners: list[OwnerSignal],
        escalations: list[EscalationSignal],
    ) -> list[CommitmentCandidate]:
        candidates: list[CommitmentCandidate] = []
        idx = 0

        # Check for ambiguity first
        is_ambiguous = any(p.search(text) for p in _AMBIGUITY_PATTERNS)

        # Approval candidates
        for appr in approvals:
            ctype = CommitmentType.APPROVAL
            disposition = CommitmentDisposition.PROPOSED
            if is_ambiguous:
                disposition = CommitmentDisposition.AMBIGUOUS
            elif not appr.approved:
                disposition = CommitmentDisposition.REJECTED
            else:
                disposition = CommitmentDisposition.ACCEPTED

            confidence = appr.confidence
            conf_level = self._confidence_band(confidence)

            candidates.append(CommitmentCandidate(
                commitment_id=stable_identifier("commit", {"ref": ref_id, "idx": idx}),
                source_type=source_type,
                source_ref_id=ref_id,
                commitment_type=ctype,
                text_span=appr.text_span,
                normalized_text=f"{'Approval' if appr.approved else 'Rejection'}: {appr.text_span}",
                confidence=confidence,
                confidence_level=conf_level,
                disposition=disposition,
                reason="approval signal detected" if appr.approved else "rejection signal detected",
                created_at=now,
            ))
            idx += 1

        # Follow-up candidates
        for pattern in _FOLLOW_UP_PATTERNS:
            for match in pattern.finditer(text):
                disposition = CommitmentDisposition.AMBIGUOUS if is_ambiguous else CommitmentDisposition.PROPOSED
                owner_id = owners[0].normalized_owner if owners else ""
                due_at = deadlines[0].normalized_deadline if deadlines else ""

                candidates.append(CommitmentCandidate(
                    commitment_id=stable_identifier("commit", {"ref": ref_id, "idx": idx}),
                    source_type=source_type,
                    source_ref_id=ref_id,
                    commitment_type=CommitmentType.FOLLOW_UP,
                    text_span=match.group(),
                    normalized_text=f"Follow-up: {match.group()}",
                    proposed_owner_id=owner_id,
                    proposed_due_at=due_at,
                    confidence=0.7,
                    confidence_level=ExtractionConfidenceLevel.MEDIUM,
                    disposition=disposition,
                    reason="Detected follow-up pattern",
                    created_at=now,
                ))
                idx += 1

        # Escalation candidates
        for esc in escalations:
            disposition = CommitmentDisposition.AMBIGUOUS if is_ambiguous else CommitmentDisposition.PROPOSED
            candidates.append(CommitmentCandidate(
                commitment_id=stable_identifier("commit", {"ref": ref_id, "idx": idx}),
                source_type=source_type,
                source_ref_id=ref_id,
                commitment_type=CommitmentType.ESCALATION,
                text_span=esc.text_span,
                normalized_text=f"Escalation: {esc.text_span}",
                confidence=esc.confidence,
                confidence_level=self._confidence_band(esc.confidence),
                disposition=disposition,
                reason="Detected escalation instruction",
                created_at=now,
            ))
            idx += 1

        # Deadline-only candidates (deadline without explicit follow-up/approval)
        if deadlines and not approvals and not any(
            c.commitment_type in (CommitmentType.FOLLOW_UP, CommitmentType.APPROVAL) for c in candidates
        ):
            for dl in deadlines:
                disposition = CommitmentDisposition.AMBIGUOUS if is_ambiguous else CommitmentDisposition.PROPOSED
                owner_id = owners[0].normalized_owner if owners else ""
                candidates.append(CommitmentCandidate(
                    commitment_id=stable_identifier("commit", {"ref": ref_id, "idx": idx}),
                    source_type=source_type,
                    source_ref_id=ref_id,
                    commitment_type=CommitmentType.DEADLINE,
                    text_span=dl.text_span,
                    normalized_text=f"Deadline: {dl.normalized_deadline}",
                    proposed_owner_id=owner_id,
                    proposed_due_at=dl.normalized_deadline,
                    confidence=dl.confidence,
                    confidence_level=self._confidence_band(dl.confidence),
                    disposition=disposition,
                    reason="Detected deadline pattern",
                    created_at=now,
                ))
                idx += 1

        # Task candidates from owner assignment without other signals
        if owners and not candidates:
            for own in owners:
                disposition = CommitmentDisposition.AMBIGUOUS if is_ambiguous else CommitmentDisposition.PROPOSED
                due_at = deadlines[0].normalized_deadline if deadlines else ""
                candidates.append(CommitmentCandidate(
                    commitment_id=stable_identifier("commit", {"ref": ref_id, "idx": idx}),
                    source_type=source_type,
                    source_ref_id=ref_id,
                    commitment_type=CommitmentType.TASK,
                    text_span=own.text_span,
                    normalized_text=f"Task assigned to {own.normalized_owner}",
                    proposed_owner_id=own.normalized_owner,
                    proposed_due_at=due_at,
                    confidence=own.confidence,
                    confidence_level=self._confidence_band(own.confidence),
                    disposition=disposition,
                    reason="Detected owner assignment pattern",
                    created_at=now,
                ))
                idx += 1

        # Attach deadline/owner info to approval candidates that don't have it
        if deadlines and approvals:
            updated = []
            for c in candidates:
                if c.commitment_type == CommitmentType.APPROVAL and not c.proposed_due_at:
                    # Rebuild with deadline
                    updated.append(CommitmentCandidate(
                        commitment_id=c.commitment_id,
                        source_type=c.source_type,
                        source_ref_id=c.source_ref_id,
                        commitment_type=c.commitment_type,
                        text_span=c.text_span,
                        normalized_text=c.normalized_text,
                        proposed_owner_id=c.proposed_owner_id,
                        proposed_due_at=deadlines[0].normalized_deadline,
                        confidence=c.confidence,
                        confidence_level=c.confidence_level,
                        disposition=c.disposition,
                        reason=c.reason,
                        created_at=c.created_at,
                    ))
                else:
                    updated.append(c)
            candidates = updated

        return candidates

    @staticmethod
    def _confidence_band(confidence: float) -> ExtractionConfidenceLevel:
        if confidence >= 0.95:
            return ExtractionConfidenceLevel.VERIFIED
        if confidence >= 0.75:
            return ExtractionConfidenceLevel.HIGH
        if confidence >= 0.5:
            return ExtractionConfidenceLevel.MEDIUM
        return ExtractionConfidenceLevel.LOW

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def route_commitments(
        self,
        result: CommitmentExtractionResult,
        default_identity_id: str,
    ) -> tuple[CommitmentRoutingDecision, ...]:
        """Route extracted commitment candidates to identities."""
        now = _now_iso()
        decisions = []
        for c in result.candidates:
            if c.disposition in (CommitmentDisposition.REJECTED, CommitmentDisposition.AMBIGUOUS):
                continue
            target = c.proposed_owner_id if c.proposed_owner_id else default_identity_id
            decision = CommitmentRoutingDecision(
                decision_id=stable_identifier("rt-commit", {"cid": c.commitment_id}),
                commitment_id=c.commitment_id,
                routed_to_identity_id=target,
                reason="commitment routed",
                created_at=now,
            )
            decisions.append(decision)
            self._routing[decision.decision_id] = decision
        return tuple(decisions)

    # ------------------------------------------------------------------
    # Promotion
    # ------------------------------------------------------------------

    def promote_commitment(
        self,
        commitment_id: str,
        obligation_id: str,
    ) -> CommitmentPromotionRecord:
        """Record promotion of a commitment candidate to an obligation."""
        if commitment_id not in self._candidates:
            raise RuntimeCoreInvariantError("commitment not found")
        candidate = self._candidates[commitment_id]
        if candidate.disposition in (CommitmentDisposition.REJECTED, CommitmentDisposition.AMBIGUOUS):
            raise RuntimeCoreInvariantError(
                "cannot promote commitment"
            )
        if commitment_id in self._promotions:
            raise RuntimeCoreInvariantError("commitment already promoted")

        now = _now_iso()
        promotion = CommitmentPromotionRecord(
            promotion_id=stable_identifier("promo", {"cid": commitment_id, "oid": obligation_id}),
            commitment_id=commitment_id,
            obligation_id=obligation_id,
            promoted_at=now,
        )
        self._promotions[commitment_id] = promotion
        return promotion

    # ------------------------------------------------------------------
    # Retrieval / properties
    # ------------------------------------------------------------------

    def get_candidate(self, commitment_id: str) -> CommitmentCandidate | None:
        return self._candidates.get(commitment_id)

    def get_result(self, result_id: str) -> CommitmentExtractionResult | None:
        return self._results.get(result_id)

    def is_promoted(self, commitment_id: str) -> bool:
        return commitment_id in self._promotions

    @property
    def candidate_count(self) -> int:
        return len(self._candidates)

    @property
    def result_count(self) -> int:
        return len(self._results)

    @property
    def promotion_count(self) -> int:
        return len(self._promotions)

    def state_hash(self) -> str:
        parts = []
        parts.extend(f"cand:{k}" for k in sorted(self._candidates))
        parts.extend(f"res:{k}" for k in sorted(self._results))
        parts.extend(f"promo:{k}" for k in sorted(self._promotions))
        parts.extend(f"route:{k}" for k in sorted(self._routing))
        return sha256("|".join(parts).encode()).hexdigest()
