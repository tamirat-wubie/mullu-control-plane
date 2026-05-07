"""Purpose: knowledge extraction engine — document parsing, pattern extraction, registry.
Governance scope: knowledge extraction, registration, lifecycle management only.
Dependencies: knowledge ingestion contracts, invariant helpers.
Invariants:
  - Extraction never fabricates content; missing parts are marked explicitly.
  - Confidence derives from completeness and corroboration, never assumed.
  - Lifecycle transitions follow a strict promotion ladder.
  - Blocked knowledge MUST NOT be promoted.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.knowledge_ingestion import (
    BestPracticeRecord,
    ConfidenceLevel,
    FailurePattern,
    KnowledgeLifecycle,
    KnowledgePromotionDecision,
    KnowledgeScope,
    KnowledgeSource,
    KnowledgeSourceType,
    KnowledgeVerificationResult,
    LessonRecord,
    MethodPattern,
    ProcedureCandidate,
    ProcedureStep,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


# --- Lifecycle transition rules ---

_VALID_KNOWLEDGE_TRANSITIONS: dict[KnowledgeLifecycle, frozenset[KnowledgeLifecycle]] = {
    KnowledgeLifecycle.CANDIDATE: frozenset({
        KnowledgeLifecycle.PROVISIONAL,
        KnowledgeLifecycle.DEPRECATED,
        KnowledgeLifecycle.BLOCKED,
    }),
    KnowledgeLifecycle.PROVISIONAL: frozenset({
        KnowledgeLifecycle.VERIFIED,
        KnowledgeLifecycle.DEPRECATED,
        KnowledgeLifecycle.BLOCKED,
    }),
    KnowledgeLifecycle.VERIFIED: frozenset({
        KnowledgeLifecycle.TRUSTED,
        KnowledgeLifecycle.DEPRECATED,
        KnowledgeLifecycle.BLOCKED,
    }),
    KnowledgeLifecycle.TRUSTED: frozenset({
        KnowledgeLifecycle.DEPRECATED,
        KnowledgeLifecycle.BLOCKED,
    }),
    KnowledgeLifecycle.DEPRECATED: frozenset({
        KnowledgeLifecycle.BLOCKED,
    }),
    KnowledgeLifecycle.BLOCKED: frozenset(),
}


class KnowledgeExtractor:
    """Extracts structured knowledge artifacts from documents and operational data.

    This extractor:
    - Parses documents into ordered procedure candidates
    - Identifies failure patterns from incident data
    - Extracts method patterns from successful execution runs
    - Marks missing parts explicitly rather than fabricating content
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock

    def extract_from_document(
        self,
        source: KnowledgeSource,
        document_content: str,
    ) -> ProcedureCandidate:
        """Parse structured text into an ordered procedure candidate.

        Sections are identified by numbered lines (e.g., "1. Do something")
        or lines starting with "- ".  Missing preconditions, postconditions,
        or warnings are flagged in *missing_parts*.
        """
        ensure_non_empty_text("document_content", document_content)

        # Sanitize control characters (keep newlines \n, tabs \t, carriage returns \r)
        document_content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', document_content)

        lines = [line.strip() for line in document_content.strip().splitlines() if line.strip()]

        steps: list[ProcedureStep] = []
        step_order = 0
        for line in lines:
            # Detect numbered lines ("1. ...", "2) ...", "10. ...") or bullet lines ("- ...")
            text = None
            numbered_match = re.match(r'^\d+[.)]\s', line)
            if numbered_match:
                text = line[numbered_match.end():].strip()
            elif line.startswith("- "):
                text = line[2:].strip()
            if text:
                steps.append(ProcedureStep(
                    step_order=step_order,
                    description=text,
                ))
                step_order += 1

        # If no steps were found, create a single step from the full content
        if not steps:
            steps.append(ProcedureStep(
                step_order=0,
                description=document_content.strip()[:200],
            ))

        # Determine missing parts
        missing_parts: list[str] = []
        content_lower = document_content.lower()
        if "precondition" not in content_lower:
            missing_parts.append("no preconditions found")
        if "postcondition" not in content_lower:
            missing_parts.append("no postconditions found")
        if "warning" not in content_lower and "caution" not in content_lower:
            missing_parts.append("no warnings found")

        # Confidence based on completeness: more steps and fewer missing parts = higher
        completeness = len(steps) / max(len(steps) + len(missing_parts), 1)
        confidence_value = round(min(max(completeness, 0.1), 1.0), 4)

        now = self._clock()

        candidate_id = stable_identifier("proc", {
            "source_id": source.source_id,
            "extracted_at": now,
        })

        confidence = ConfidenceLevel(
            value=confidence_value,
            reason="completeness-based extraction assessment",
            assessed_at=now,
        )

        return ProcedureCandidate(
            candidate_id=candidate_id,
            source_id=source.source_id,
            name="procedure candidate",
            steps=tuple(steps),
            missing_parts=tuple(missing_parts),
            confidence=confidence,
            created_at=now,
        )

    def extract_failure_pattern(
        self,
        source: KnowledgeSource,
        incidents: list[Mapping[str, Any]],
    ) -> FailurePattern:
        """Find recurring trigger conditions across incidents.

        Each incident mapping is expected to have keys: trigger, failure_mode, response.
        Common values are extracted by frequency.
        """
        if not incidents:
            raise RuntimeCoreInvariantError("incidents must contain at least one item")

        # Count trigger occurrences
        trigger_counts: dict[str, int] = {}
        mode_counts: dict[str, int] = {}
        response_counts: dict[str, int] = {}
        for inc in incidents:
            trigger = str(inc.get("trigger", "unknown"))
            mode = str(inc.get("failure_mode", "unknown"))
            response = str(inc.get("response", "unknown"))
            trigger_counts[trigger] = trigger_counts.get(trigger, 0) + 1
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
            response_counts[response] = response_counts.get(response, 0) + 1

        common_trigger = max(trigger_counts, key=trigger_counts.get)  # type: ignore[arg-type]
        common_mode = max(mode_counts, key=mode_counts.get)  # type: ignore[arg-type]
        common_response = max(response_counts, key=response_counts.get)  # type: ignore[arg-type]

        # Confidence: proportion of incidents matching the most common trigger
        confidence_value = round(trigger_counts[common_trigger] / len(incidents), 4)
        now = self._clock()

        pattern_id = stable_identifier("fail-pat", {
            "source_id": source.source_id,
            "extracted_at": now,
        })

        confidence = ConfidenceLevel(
            value=confidence_value,
            reason="trigger frequency assessment",
            assessed_at=now,
        )

        return FailurePattern(
            pattern_id=pattern_id,
            source_ids=(source.source_id,),
            name="failure pattern",
            trigger_conditions=(common_trigger,),
            failure_mode=common_mode,
            recommended_response=common_response,
            confidence=confidence,
            created_at=now,
        )

    def extract_method_pattern(
        self,
        source: KnowledgeSource,
        successful_runs: list[Mapping[str, Any]],
    ) -> MethodPattern:
        """Find common steps across multiple successful skill/workflow runs.

        Each run mapping is expected to have a "steps" key containing a list of step descriptions.
        Confidence is based on how many runs share the same step sequence.
        """
        if not successful_runs:
            raise RuntimeCoreInvariantError("successful_runs must contain at least one item")

        # Collect step sequences and find the most common
        step_sequences: dict[tuple[str, ...], int] = {}
        for run in successful_runs:
            raw_steps = run.get("steps", [])
            seq = tuple(str(s) for s in raw_steps)
            step_sequences[seq] = step_sequences.get(seq, 0) + 1

        common_seq = max(step_sequences, key=step_sequences.get)  # type: ignore[arg-type]
        match_count = step_sequences[common_seq]
        confidence_value = round(match_count / len(successful_runs), 4)

        now = self._clock()

        pattern_id = stable_identifier("method-pat", {
            "source_id": source.source_id,
            "extracted_at": now,
        })

        confidence = ConfidenceLevel(
            value=confidence_value,
            reason="step match assessment",
            assessed_at=now,
        )

        return MethodPattern(
            pattern_id=pattern_id,
            source_ids=(source.source_id,),
            name="method pattern",
            description="common steps across successful runs",
            applicability="general",
            steps=common_seq if common_seq else ("unknown",),
            confidence=confidence,
            created_at=now,
        )


class KnowledgeRegistry:
    """Central registry for knowledge artifacts with lifecycle management.

    Registration, lookup, lifecycle transitions, and verification tracking.
    Only allows valid lifecycle transitions following the promotion ladder.
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._artifacts: dict[str, Any] = {}
        self._lifecycles: dict[str, KnowledgeLifecycle] = {}
        self._source_index: dict[str, list[str]] = {}
        self._verifications: dict[str, list[KnowledgeVerificationResult]] = {}

    def register(self, artifact: Any) -> Any:
        """Register a knowledge artifact. The artifact must have a unique identifying id attribute."""
        knowledge_id = self._extract_id(artifact)
        if knowledge_id in self._artifacts:
            raise RuntimeCoreInvariantError("knowledge already registered")
        self._artifacts[knowledge_id] = artifact
        # Use artifact's lifecycle if present, otherwise default to CANDIDATE
        lifecycle = getattr(artifact, "lifecycle", KnowledgeLifecycle.CANDIDATE)
        if isinstance(lifecycle, KnowledgeLifecycle):
            self._lifecycles[knowledge_id] = lifecycle
        else:
            self._lifecycles[knowledge_id] = KnowledgeLifecycle.CANDIDATE

        # Index by all source IDs (multi-source artifacts like FailurePattern)
        source_ids = self._extract_all_source_ids(artifact)
        for sid in source_ids:
            self._source_index.setdefault(sid, []).append(knowledge_id)

        return artifact

    def lookup(self, knowledge_id: str) -> Any | None:
        ensure_non_empty_text("knowledge_id", knowledge_id)
        return self._artifacts.get(knowledge_id)

    def get_lifecycle(self, knowledge_id: str) -> KnowledgeLifecycle | None:
        ensure_non_empty_text("knowledge_id", knowledge_id)
        return self._lifecycles.get(knowledge_id)

    def list_by_lifecycle(self, lifecycle: KnowledgeLifecycle) -> tuple[Any, ...]:
        return tuple(
            self._artifacts[kid]
            for kid, lc in sorted(self._lifecycles.items())
            if lc == lifecycle
        )

    def list_by_source(self, source_id: str) -> tuple[Any, ...]:
        ensure_non_empty_text("source_id", source_id)
        ids = self._source_index.get(source_id, [])
        return tuple(self._artifacts[kid] for kid in sorted(ids) if kid in self._artifacts)

    def promote(
        self,
        knowledge_id: str,
        to_lifecycle: KnowledgeLifecycle,
        reason: str,
        decided_by: str,
    ) -> KnowledgePromotionDecision:
        """Promote a knowledge artifact through the lifecycle ladder."""
        ensure_non_empty_text("knowledge_id", knowledge_id)
        ensure_non_empty_text("reason", reason)
        ensure_non_empty_text("decided_by", decided_by)

        current = self._lifecycles.get(knowledge_id)
        if current is None:
            raise RuntimeCoreInvariantError("knowledge not found")

        allowed = _VALID_KNOWLEDGE_TRANSITIONS.get(current, frozenset())
        if to_lifecycle not in allowed:
            raise RuntimeCoreInvariantError("invalid lifecycle transition")

        self._lifecycles[knowledge_id] = to_lifecycle

        return KnowledgePromotionDecision(
            knowledge_id=knowledge_id,
            from_lifecycle=current,
            to_lifecycle=to_lifecycle,
            reason=reason,
            decided_by=decided_by,
            decided_at=self._clock(),
        )

    def verify(
        self,
        knowledge_id: str,
        verifier_id: str,
        method: str,
        notes: str,
    ) -> KnowledgeVerificationResult:
        """Record a verification against a knowledge artifact."""
        ensure_non_empty_text("knowledge_id", knowledge_id)
        ensure_non_empty_text("verifier_id", verifier_id)
        ensure_non_empty_text("method", method)

        if knowledge_id not in self._artifacts:
            raise RuntimeCoreInvariantError("knowledge not found")

        result = KnowledgeVerificationResult(
            knowledge_id=knowledge_id,
            verified=True,
            verifier_id=verifier_id,
            verification_method=method,
            notes=notes,
            verified_at=self._clock(),
        )

        self._verifications.setdefault(knowledge_id, []).append(result)
        return result

    @property
    def size(self) -> int:
        return len(self._artifacts)

    @staticmethod
    def _extract_id(artifact: Any) -> str:
        """Extract the primary identifier from a knowledge artifact."""
        for attr in ("candidate_id", "pattern_id", "practice_id", "lesson_id", "knowledge_id", "record_id"):
            val = getattr(artifact, attr, None)
            if val is not None:
                return str(val)
        raise RuntimeCoreInvariantError("artifact has no recognizable id attribute")

    @staticmethod
    def _extract_all_source_ids(artifact: Any) -> list[str]:
        """Extract all source IDs from an artifact."""
        # Direct source_id field
        source_id = getattr(artifact, "source_id", None)
        if source_id is not None:
            return [str(source_id)]
        # source_ids tuple (all entries for multi-source artifacts)
        source_ids = getattr(artifact, "source_ids", None)
        if source_ids:
            return [str(sid) for sid in source_ids]
        return []
