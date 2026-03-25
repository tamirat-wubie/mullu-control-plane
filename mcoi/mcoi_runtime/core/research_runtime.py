"""Purpose: research workflow runtime engine.
Governance scope: managing research questions, hypotheses, study protocols,
    experiments, literature packets, evidence synthesis, peer reviews;
    detecting research violations; producing snapshots and state hashes.
Dependencies: research_runtime contracts, event_spine, core invariants.
Invariants:
  - Evidence-free synthesis is never marked verified.
  - Terminal study/experiment states are immutable.
  - Every mutation emits an event.
  - All returns are frozen dataclasses.
  - Violation detection is idempotent.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.research_runtime import (
    EvidenceStrength,
    EvidenceSynthesis,
    ExperimentRun,
    ExperimentStatus,
    HypothesisRecord,
    HypothesisStatus,
    LiteraturePacket,
    PeerReviewRecord,
    PublicationDisposition,
    ResearchAssessment,
    ResearchClosureReport,
    ResearchQuestion,
    ResearchSnapshot,
    ResearchStatus,
    StudyProtocol,
    StudyStatus,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-res", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ResearchRuntimeEngine:
    """Research workflow runtime engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._questions: dict[str, ResearchQuestion] = {}
        self._hypotheses: dict[str, HypothesisRecord] = {}
        self._studies: dict[str, StudyProtocol] = {}
        self._experiments: dict[str, ExperimentRun] = {}
        self._literature: dict[str, LiteraturePacket] = {}
        self._syntheses: dict[str, EvidenceSynthesis] = {}
        self._reviews: dict[str, PeerReviewRecord] = {}
        self._violations: dict[str, dict[str, Any]] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def question_count(self) -> int:
        return len(self._questions)

    @property
    def hypothesis_count(self) -> int:
        return len(self._hypotheses)

    @property
    def study_count(self) -> int:
        return len(self._studies)

    @property
    def experiment_count(self) -> int:
        return len(self._experiments)

    @property
    def literature_count(self) -> int:
        return len(self._literature)

    @property
    def synthesis_count(self) -> int:
        return len(self._syntheses)

    @property
    def review_count(self) -> int:
        return len(self._reviews)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Questions
    # ------------------------------------------------------------------

    def register_question(
        self,
        question_id: str,
        tenant_id: str,
        title: str,
        description: str,
    ) -> ResearchQuestion:
        """Register a new research question."""
        if question_id in self._questions:
            raise RuntimeCoreInvariantError(f"Duplicate question_id: {question_id}")
        now = _now_iso()
        q = ResearchQuestion(
            question_id=question_id,
            tenant_id=tenant_id,
            title=title,
            description=description,
            status=ResearchStatus.ACTIVE,
            hypothesis_count=0,
            created_at=now,
        )
        self._questions[question_id] = q
        _emit(self._events, "question_registered", {
            "question_id": question_id, "tenant_id": tenant_id,
        }, question_id)
        return q

    def get_question(self, question_id: str) -> ResearchQuestion:
        """Get a question by ID."""
        q = self._questions.get(question_id)
        if q is None:
            raise RuntimeCoreInvariantError(f"Unknown question_id: {question_id}")
        return q

    def questions_for_tenant(self, tenant_id: str) -> tuple[ResearchQuestion, ...]:
        """Return all questions for a tenant."""
        return tuple(q for q in self._questions.values() if q.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Hypotheses
    # ------------------------------------------------------------------

    def register_hypothesis(
        self,
        hypothesis_id: str,
        tenant_id: str,
        question_id: str,
        statement: str,
    ) -> HypothesisRecord:
        """Register a hypothesis linked to a question."""
        if hypothesis_id in self._hypotheses:
            raise RuntimeCoreInvariantError(f"Duplicate hypothesis_id: {hypothesis_id}")
        q = self._questions.get(question_id)
        if q is None:
            raise RuntimeCoreInvariantError(f"Unknown question_id: {question_id}")
        now = _now_iso()
        h = HypothesisRecord(
            hypothesis_id=hypothesis_id,
            tenant_id=tenant_id,
            question_ref=question_id,
            statement=statement,
            status=HypothesisStatus.PROPOSED,
            confidence=0.0,
            evidence_count=0,
            created_at=now,
        )
        self._hypotheses[hypothesis_id] = h
        # Increment hypothesis_count on the question
        updated_q = ResearchQuestion(
            question_id=q.question_id,
            tenant_id=q.tenant_id,
            title=q.title,
            description=q.description,
            status=q.status,
            hypothesis_count=q.hypothesis_count + 1,
            created_at=q.created_at,
            metadata=q.metadata,
        )
        self._questions[question_id] = updated_q
        _emit(self._events, "hypothesis_registered", {
            "hypothesis_id": hypothesis_id, "question_id": question_id,
        }, hypothesis_id)
        return h

    def get_hypothesis(self, hypothesis_id: str) -> HypothesisRecord:
        """Get a hypothesis by ID."""
        h = self._hypotheses.get(hypothesis_id)
        if h is None:
            raise RuntimeCoreInvariantError(f"Unknown hypothesis_id: {hypothesis_id}")
        return h

    # ------------------------------------------------------------------
    # Study protocols
    # ------------------------------------------------------------------

    def register_study_protocol(
        self,
        study_id: str,
        tenant_id: str,
        hypothesis_id: str,
        title: str,
    ) -> StudyProtocol:
        """Register a study protocol linked to a hypothesis."""
        if study_id in self._studies:
            raise RuntimeCoreInvariantError(f"Duplicate study_id: {study_id}")
        if hypothesis_id not in self._hypotheses:
            raise RuntimeCoreInvariantError(f"Unknown hypothesis_id: {hypothesis_id}")
        now = _now_iso()
        s = StudyProtocol(
            study_id=study_id,
            tenant_id=tenant_id,
            title=title,
            hypothesis_ref=hypothesis_id,
            status=StudyStatus.DRAFT,
            experiment_count=0,
            created_at=now,
        )
        self._studies[study_id] = s
        _emit(self._events, "study_registered", {
            "study_id": study_id, "hypothesis_id": hypothesis_id,
        }, study_id)
        return s

    def get_study(self, study_id: str) -> StudyProtocol:
        """Get a study protocol by ID."""
        s = self._studies.get(study_id)
        if s is None:
            raise RuntimeCoreInvariantError(f"Unknown study_id: {study_id}")
        return s

    def _update_study_status(self, study_id: str, new_status: StudyStatus) -> StudyProtocol:
        """Update a study's status with terminal-state guard."""
        old = self._studies.get(study_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown study_id: {study_id}")
        if old.status in (StudyStatus.COMPLETED, StudyStatus.CANCELLED):
            raise RuntimeCoreInvariantError(
                f"Cannot transition study from terminal state {old.status.value}"
            )
        updated = StudyProtocol(
            study_id=old.study_id,
            tenant_id=old.tenant_id,
            title=old.title,
            hypothesis_ref=old.hypothesis_ref,
            status=new_status,
            experiment_count=old.experiment_count,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._studies[study_id] = updated
        _emit(self._events, "study_status_updated", {
            "study_id": study_id, "status": new_status.value,
        }, study_id)
        return updated

    def approve_study(self, study_id: str) -> StudyProtocol:
        """Approve a study protocol (DRAFT -> APPROVED)."""
        return self._update_study_status(study_id, StudyStatus.APPROVED)

    def start_study(self, study_id: str) -> StudyProtocol:
        """Start a study (APPROVED -> IN_PROGRESS)."""
        return self._update_study_status(study_id, StudyStatus.IN_PROGRESS)

    def complete_study(self, study_id: str) -> StudyProtocol:
        """Complete a study."""
        return self._update_study_status(study_id, StudyStatus.COMPLETED)

    def cancel_study(self, study_id: str) -> StudyProtocol:
        """Cancel a study."""
        return self._update_study_status(study_id, StudyStatus.CANCELLED)

    # ------------------------------------------------------------------
    # Experiments
    # ------------------------------------------------------------------

    def start_experiment(
        self,
        experiment_id: str,
        tenant_id: str,
        study_id: str,
        result_summary: str = "pending",
    ) -> ExperimentRun:
        """Start an experiment linked to a study."""
        if experiment_id in self._experiments:
            raise RuntimeCoreInvariantError(f"Duplicate experiment_id: {experiment_id}")
        s = self._studies.get(study_id)
        if s is None:
            raise RuntimeCoreInvariantError(f"Unknown study_id: {study_id}")
        now = _now_iso()
        exp = ExperimentRun(
            experiment_id=experiment_id,
            tenant_id=tenant_id,
            study_ref=study_id,
            status=ExperimentStatus.RUNNING,
            result_summary=result_summary,
            confidence=0.0,
            created_at=now,
        )
        self._experiments[experiment_id] = exp
        # Increment experiment_count on the study
        updated_s = StudyProtocol(
            study_id=s.study_id,
            tenant_id=s.tenant_id,
            title=s.title,
            hypothesis_ref=s.hypothesis_ref,
            status=s.status,
            experiment_count=s.experiment_count + 1,
            created_at=s.created_at,
            metadata=s.metadata,
        )
        self._studies[study_id] = updated_s
        _emit(self._events, "experiment_started", {
            "experiment_id": experiment_id, "study_id": study_id,
        }, experiment_id)
        return exp

    def record_experiment_result(
        self,
        experiment_id: str,
        status: ExperimentStatus,
        result_summary: str,
        confidence: float,
    ) -> ExperimentRun:
        """Record an experiment result (COMPLETED or FAILED)."""
        old = self._experiments.get(experiment_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown experiment_id: {experiment_id}")
        if old.status in (ExperimentStatus.COMPLETED, ExperimentStatus.FAILED, ExperimentStatus.CANCELLED):
            raise RuntimeCoreInvariantError(
                f"Cannot transition experiment from terminal state {old.status.value}"
            )
        if status not in (ExperimentStatus.COMPLETED, ExperimentStatus.FAILED):
            raise RuntimeCoreInvariantError("Result status must be COMPLETED or FAILED")
        updated = ExperimentRun(
            experiment_id=old.experiment_id,
            tenant_id=old.tenant_id,
            study_ref=old.study_ref,
            status=status,
            result_summary=result_summary,
            confidence=confidence,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._experiments[experiment_id] = updated
        _emit(self._events, "experiment_result_recorded", {
            "experiment_id": experiment_id, "status": status.value,
            "confidence": confidence,
        }, experiment_id)
        return updated

    def get_experiment(self, experiment_id: str) -> ExperimentRun:
        """Get an experiment by ID."""
        e = self._experiments.get(experiment_id)
        if e is None:
            raise RuntimeCoreInvariantError(f"Unknown experiment_id: {experiment_id}")
        return e

    # ------------------------------------------------------------------
    # Literature
    # ------------------------------------------------------------------

    def attach_literature_packet(
        self,
        packet_id: str,
        tenant_id: str,
        hypothesis_id: str,
        title: str,
        source_count: int = 1,
        relevance_score: float = 0.5,
    ) -> LiteraturePacket:
        """Attach a literature review packet to a hypothesis."""
        if packet_id in self._literature:
            raise RuntimeCoreInvariantError(f"Duplicate packet_id: {packet_id}")
        if hypothesis_id not in self._hypotheses:
            raise RuntimeCoreInvariantError(f"Unknown hypothesis_id: {hypothesis_id}")
        now = _now_iso()
        pkt = LiteraturePacket(
            packet_id=packet_id,
            tenant_id=tenant_id,
            hypothesis_ref=hypothesis_id,
            title=title,
            source_count=source_count,
            relevance_score=relevance_score,
            created_at=now,
        )
        self._literature[packet_id] = pkt
        _emit(self._events, "literature_attached", {
            "packet_id": packet_id, "hypothesis_id": hypothesis_id,
        }, packet_id)
        return pkt

    # ------------------------------------------------------------------
    # Evidence synthesis
    # ------------------------------------------------------------------

    def build_evidence_synthesis(
        self,
        synthesis_id: str,
        tenant_id: str,
        hypothesis_id: str,
    ) -> EvidenceSynthesis:
        """Build an evidence synthesis for a hypothesis.

        Auto-counts experiments (via study) and literature for the hypothesis.
        Derives strength from confidence and contradiction count.
        """
        if synthesis_id in self._syntheses:
            raise RuntimeCoreInvariantError(f"Duplicate synthesis_id: {synthesis_id}")
        if hypothesis_id not in self._hypotheses:
            raise RuntimeCoreInvariantError(f"Unknown hypothesis_id: {hypothesis_id}")

        # Count experiments linked to hypothesis via studies
        hyp_studies = [s for s in self._studies.values() if s.hypothesis_ref == hypothesis_id]
        study_ids = {s.study_id for s in hyp_studies}
        hyp_experiments = [e for e in self._experiments.values() if e.study_ref in study_ids]
        exp_count = len(hyp_experiments)

        # Count literature for hypothesis
        lit_count = sum(1 for p in self._literature.values() if p.hypothesis_ref == hypothesis_id)

        # Compute average confidence from completed experiments
        completed_exps = [e for e in hyp_experiments if e.status == ExperimentStatus.COMPLETED]
        avg_conf = (
            sum(e.confidence for e in completed_exps) / len(completed_exps)
            if completed_exps
            else 0.0
        )

        # Count contradictions (failed experiments)
        contradiction_count = sum(
            1 for e in hyp_experiments if e.status == ExperimentStatus.FAILED
        )

        # Auto-derive strength
        if contradiction_count > 0:
            strength = EvidenceStrength.CONTRADICTORY
        elif avg_conf >= 0.8:
            strength = EvidenceStrength.STRONG
        elif avg_conf >= 0.5:
            strength = EvidenceStrength.MODERATE
        elif avg_conf >= 0.3:
            strength = EvidenceStrength.WEAK
        else:
            strength = EvidenceStrength.WEAK

        now = _now_iso()
        syn = EvidenceSynthesis(
            synthesis_id=synthesis_id,
            tenant_id=tenant_id,
            hypothesis_ref=hypothesis_id,
            strength=strength,
            experiment_count=exp_count,
            literature_count=lit_count,
            contradiction_count=contradiction_count,
            confidence=avg_conf,
            created_at=now,
        )
        self._syntheses[synthesis_id] = syn
        _emit(self._events, "evidence_synthesis_built", {
            "synthesis_id": synthesis_id, "hypothesis_id": hypothesis_id,
            "strength": strength.value,
        }, synthesis_id)
        return syn

    # ------------------------------------------------------------------
    # Peer review
    # ------------------------------------------------------------------

    def request_peer_review(
        self,
        review_id: str,
        tenant_id: str,
        target_ref: str,
        reviewer_ref: str,
        comments: str = "Review requested",
    ) -> PeerReviewRecord:
        """Request a peer review."""
        if review_id in self._reviews:
            raise RuntimeCoreInvariantError(f"Duplicate review_id: {review_id}")
        now = _now_iso()
        rev = PeerReviewRecord(
            review_id=review_id,
            tenant_id=tenant_id,
            target_ref=target_ref,
            reviewer_ref=reviewer_ref,
            disposition=PublicationDisposition.IN_REVIEW,
            comments=comments,
            confidence=0.0,
            reviewed_at=now,
        )
        self._reviews[review_id] = rev
        _emit(self._events, "peer_review_requested", {
            "review_id": review_id, "target_ref": target_ref,
        }, review_id)
        return rev

    def complete_peer_review(
        self,
        review_id: str,
        disposition: PublicationDisposition,
        comments: str,
        confidence: float,
    ) -> PeerReviewRecord:
        """Complete a peer review with disposition and comments."""
        old = self._reviews.get(review_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown review_id: {review_id}")
        if old.disposition not in (PublicationDisposition.IN_REVIEW, PublicationDisposition.DRAFT):
            raise RuntimeCoreInvariantError(
                f"Cannot complete review in state {old.disposition.value}"
            )
        now = _now_iso()
        updated = PeerReviewRecord(
            review_id=old.review_id,
            tenant_id=old.tenant_id,
            target_ref=old.target_ref,
            reviewer_ref=old.reviewer_ref,
            disposition=disposition,
            comments=comments,
            confidence=confidence,
            reviewed_at=now,
            metadata=old.metadata,
        )
        self._reviews[review_id] = updated
        _emit(self._events, "peer_review_completed", {
            "review_id": review_id, "disposition": disposition.value,
        }, review_id)
        return updated

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def research_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> ResearchSnapshot:
        """Capture a point-in-time research state snapshot (tenant-scoped counts)."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError(f"Duplicate snapshot_id: {snapshot_id}")
        now = _now_iso()

        t_questions = sum(1 for q in self._questions.values() if q.tenant_id == tenant_id)
        t_hypotheses = sum(1 for h in self._hypotheses.values() if h.tenant_id == tenant_id)
        t_studies = sum(1 for s in self._studies.values() if s.tenant_id == tenant_id)
        t_experiments = sum(1 for e in self._experiments.values() if e.tenant_id == tenant_id)
        t_literature = sum(1 for p in self._literature.values() if p.tenant_id == tenant_id)
        t_syntheses = sum(1 for s in self._syntheses.values() if s.tenant_id == tenant_id)
        t_reviews = sum(1 for r in self._reviews.values() if r.tenant_id == tenant_id)
        t_violations = sum(
            1 for v in self._violations.values() if v.get("tenant_id") == tenant_id
        )

        snap = ResearchSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_questions=t_questions,
            total_hypotheses=t_hypotheses,
            total_studies=t_studies,
            total_experiments=t_experiments,
            total_literature=t_literature,
            total_syntheses=t_syntheses,
            total_reviews=t_reviews,
            total_violations=t_violations,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "research_snapshot_captured", {
            "snapshot_id": snapshot_id, "tenant_id": tenant_id,
        }, snapshot_id)
        return snap

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_research_violations(self) -> tuple[dict[str, Any], ...]:
        """Detect research governance violations (idempotent).

        Checks:
        - evidence_free_synthesis: synthesis with 0 experiments + 0 literature
        - incomplete_study: study IN_PROGRESS with no experiments
        - unreviewed_closure: completed study with no reviews
        """
        now = _now_iso()
        new_violations: list[dict[str, Any]] = []

        # evidence_free_synthesis
        for syn in self._syntheses.values():
            if syn.experiment_count == 0 and syn.literature_count == 0:
                vid = stable_identifier(
                    "viol-res", {"syn": syn.synthesis_id, "op": "evidence_free_synthesis"}
                )
                if vid not in self._violations:
                    v = {
                        "violation_id": vid,
                        "tenant_id": syn.tenant_id,
                        "operation": "evidence_free_synthesis",
                        "reason": f"Synthesis {syn.synthesis_id} has 0 experiments and 0 literature",
                        "detected_at": now,
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        # incomplete_study
        for study in self._studies.values():
            if study.status == StudyStatus.IN_PROGRESS:
                study_exps = [
                    e for e in self._experiments.values() if e.study_ref == study.study_id
                ]
                if not study_exps:
                    vid = stable_identifier(
                        "viol-res", {"study": study.study_id, "op": "incomplete_study"}
                    )
                    if vid not in self._violations:
                        v = {
                            "violation_id": vid,
                            "tenant_id": study.tenant_id,
                            "operation": "incomplete_study",
                            "reason": f"Study {study.study_id} is IN_PROGRESS with no experiments",
                            "detected_at": now,
                        }
                        self._violations[vid] = v
                        new_violations.append(v)

        # unreviewed_closure
        for study in self._studies.values():
            if study.status == StudyStatus.COMPLETED:
                study_reviews = [
                    r for r in self._reviews.values() if r.target_ref == study.study_id
                ]
                if not study_reviews:
                    vid = stable_identifier(
                        "viol-res", {"study": study.study_id, "op": "unreviewed_closure"}
                    )
                    if vid not in self._violations:
                        v = {
                            "violation_id": vid,
                            "tenant_id": study.tenant_id,
                            "operation": "unreviewed_closure",
                            "reason": f"Study {study.study_id} completed with no peer reviews",
                            "detected_at": now,
                        }
                        self._violations[vid] = v
                        new_violations.append(v)

        if new_violations:
            _emit(self._events, "research_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def research_assessment(self, assessment_id: str, tenant_id: str) -> ResearchAssessment:
        now = _now_iso()
        t_questions = sum(1 for q in self._questions.values() if q.tenant_id == tenant_id)
        t_hypotheses = sum(1 for h in self._hypotheses.values() if h.tenant_id == tenant_id)
        t_experiments = sum(1 for e in self._experiments.values() if e.tenant_id == tenant_id)
        t_syntheses = sum(1 for s in self._syntheses.values() if s.tenant_id == tenant_id)
        t_reviews = sum(1 for r in self._reviews.values() if r.tenant_id == tenant_id)
        completed_studies = sum(
            1 for s in self._studies.values()
            if s.tenant_id == tenant_id and s.status == StudyStatus.COMPLETED
        )
        total_studies = sum(1 for s in self._studies.values() if s.tenant_id == tenant_id)
        rate = completed_studies / total_studies if total_studies else 0.0
        assessment = ResearchAssessment(
            assessment_id=assessment_id, tenant_id=tenant_id,
            total_questions=t_questions, total_hypotheses=t_hypotheses,
            total_experiments=t_experiments, total_syntheses=t_syntheses,
            total_reviews=t_reviews,
            completion_rate=round(rate, 4),
            assessed_at=now,
        )
        _emit(self._events, "research_assessment", {"assessment_id": assessment_id}, assessment_id)
        return assessment

    # ------------------------------------------------------------------
    # Closure report
    # ------------------------------------------------------------------

    def research_closure_report(self, report_id: str, tenant_id: str) -> ResearchClosureReport:
        now = _now_iso()
        report = ResearchClosureReport(
            report_id=report_id, tenant_id=tenant_id,
            total_questions=sum(1 for q in self._questions.values() if q.tenant_id == tenant_id),
            total_hypotheses=sum(1 for h in self._hypotheses.values() if h.tenant_id == tenant_id),
            total_studies=sum(1 for s in self._studies.values() if s.tenant_id == tenant_id),
            total_experiments=sum(1 for e in self._experiments.values() if e.tenant_id == tenant_id),
            total_syntheses=sum(1 for s in self._syntheses.values() if s.tenant_id == tenant_id),
            total_reviews=sum(1 for r in self._reviews.values() if r.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.get("tenant_id") == tenant_id),
            created_at=now,
        )
        _emit(self._events, "research_closure_report", {"report_id": report_id}, report_id)
        return report

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute SHA256 hash over sorted keys of all collections.

        NO timestamps in hash keys — only counts.
        """
        parts = sorted([
            f"experiments={self.experiment_count}",
            f"hypotheses={self.hypothesis_count}",
            f"literature={self.literature_count}",
            f"questions={self.question_count}",
            f"reviews={self.review_count}",
            f"studies={self.study_count}",
            f"syntheses={self.synthesis_count}",
            f"violations={self.violation_count}",
        ])
        return sha256("|".join(parts).encode()).hexdigest()
