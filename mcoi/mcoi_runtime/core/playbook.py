"""Purpose: incident playbook engine — match, select, execute, record.
Governance scope: incident playbook management and execution only.
Dependencies: playbook contracts, incident contracts, invariant helpers.
Invariants:
  - Pattern matching is deterministic.
  - Only reviewed/active playbooks may execute.
  - Review and approval gating are respected.
  - Execution outcomes are persisted and feed back into telemetry.
"""

from __future__ import annotations

from typing import Callable

from mcoi_runtime.contracts.incident import IncidentRecord
from mcoi_runtime.contracts.playbook import (
    IncidentMatchRecord,
    IncidentPattern,
    IncidentPlaybookDescriptor,
    PatternMatchResult,
    PlaybookExecutionRecord,
    PlaybookOutcome,
    PlaybookStatus,
)
from .invariants import ensure_non_empty_text, stable_identifier


class PlaybookEngine:
    """Matches incidents to playbooks, validates governance, and executes procedures."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._playbooks: dict[str, IncidentPlaybookDescriptor] = {}
        self._executions: list[PlaybookExecutionRecord] = []

    def register(self, playbook: IncidentPlaybookDescriptor) -> IncidentPlaybookDescriptor:
        if playbook.playbook_id in self._playbooks:
            raise ValueError(f"playbook already registered: {playbook.playbook_id}")
        self._playbooks[playbook.playbook_id] = playbook
        return playbook

    def get(self, playbook_id: str) -> IncidentPlaybookDescriptor | None:
        return self._playbooks.get(playbook_id)

    def list_playbooks(self, *, active_only: bool = False) -> tuple[IncidentPlaybookDescriptor, ...]:
        result = sorted(self._playbooks.values(), key=lambda p: p.playbook_id)
        if active_only:
            result = [p for p in result if p.is_executable]
        return tuple(result)

    def match_incident(self, incident: IncidentRecord) -> IncidentMatchRecord:
        """Match an incident against all registered playbook patterns."""
        best_match: IncidentPlaybookDescriptor | None = None
        best_score = 0.0
        reasons: list[str] = []

        for playbook in sorted(self._playbooks.values(), key=lambda p: p.playbook_id):
            if not playbook.is_executable:
                continue
            score, match_reasons = self._score_match(playbook.pattern, incident)
            if score > best_score:
                best_score = score
                best_match = playbook
                reasons = match_reasons

        if best_match is None or best_score == 0.0:
            return IncidentMatchRecord(
                incident_id=incident.incident_id,
                result=PatternMatchResult.NO_MATCH,
            )

        result = PatternMatchResult.MATCHED if best_score >= 1.0 else PatternMatchResult.PARTIAL
        return IncidentMatchRecord(
            incident_id=incident.incident_id,
            result=result,
            matched_playbook_id=best_match.playbook_id,
            match_score=best_score,
            match_reasons=tuple(reasons),
        )

    def execute(
        self,
        playbook_id: str,
        incident_id: str,
        *,
        review_satisfied: bool = False,
        approval_satisfied: bool = False,
        step_executor: Callable[[str], bool] | None = None,
    ) -> PlaybookExecutionRecord:
        """Execute a playbook for an incident, respecting governance gates."""
        ensure_non_empty_text("playbook_id", playbook_id)
        ensure_non_empty_text("incident_id", incident_id)
        started_at = self._clock()

        playbook = self._playbooks.get(playbook_id)
        if playbook is None:
            return self._make_record(playbook_id, incident_id, started_at,
                                      PlaybookOutcome.BLOCKED, 0, 0, False, False,
                                      "playbook not found")

        if not playbook.is_executable:
            return self._make_record(playbook_id, incident_id, started_at,
                                      PlaybookOutcome.BLOCKED, 0, len(playbook.steps), False, False,
                                      f"playbook status is {playbook.status.value}")

        # Review gate
        if playbook.requires_review and not review_satisfied:
            return self._make_record(playbook_id, incident_id, started_at,
                                      PlaybookOutcome.BLOCKED, 0, len(playbook.steps), False, approval_satisfied,
                                      "review required but not satisfied")

        # Approval gate
        if playbook.requires_approval and not approval_satisfied:
            return self._make_record(playbook_id, incident_id, started_at,
                                      PlaybookOutcome.BLOCKED, 0, len(playbook.steps), review_satisfied, False,
                                      "approval required but not satisfied")

        # Execute steps
        executor = step_executor or (lambda s: True)
        completed = 0
        for step in playbook.steps:
            if not executor(step):
                record = self._make_record(playbook_id, incident_id, started_at,
                                            PlaybookOutcome.FAILED, completed, len(playbook.steps),
                                            review_satisfied, approval_satisfied,
                                            f"step failed: {step}")
                self._executions.append(record)
                return record
            completed += 1

        record = self._make_record(playbook_id, incident_id, started_at,
                                    PlaybookOutcome.RESOLVED, completed, len(playbook.steps),
                                    review_satisfied, approval_satisfied)
        self._executions.append(record)
        return record

    def list_executions(self) -> tuple[PlaybookExecutionRecord, ...]:
        return tuple(self._executions)

    def _score_match(self, pattern: IncidentPattern, incident: IncidentRecord) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []

        if pattern.failure_family == incident.failure_family:
            score += 0.5
            reasons.append(f"failure_family={pattern.failure_family}")

        if pattern.source_type and pattern.source_type == incident.source_type:
            score += 0.3
            reasons.append(f"source_type={pattern.source_type}")

        if pattern.keyword_match:
            msg_lower = incident.message.lower()
            matched = sum(1 for kw in pattern.keyword_match if kw.lower() in msg_lower)
            if matched > 0:
                keyword_score = 0.2 * (matched / len(pattern.keyword_match))
                score += keyword_score
                reasons.append(f"keywords={matched}/{len(pattern.keyword_match)}")

        return round(score, 4), reasons

    def _make_record(
        self, playbook_id, incident_id, started_at,
        outcome, completed, total, review_ok, approval_ok,
        error=None,
    ) -> PlaybookExecutionRecord:
        return PlaybookExecutionRecord(
            record_id=stable_identifier("pb-exec", {
                "playbook_id": playbook_id,
                "incident_id": incident_id,
                "started_at": started_at,
            }),
            playbook_id=playbook_id,
            incident_id=incident_id,
            outcome=outcome,
            steps_completed=completed,
            steps_total=total,
            review_satisfied=review_ok,
            approval_satisfied=approval_ok,
            started_at=started_at,
            finished_at=self._clock(),
            error_message=error,
        )
