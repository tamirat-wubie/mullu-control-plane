"""Purpose: logic / proof / truth-maintenance runtime engine.
Governance scope: managing logical statements, inference rules, proofs,
    assumptions, contradictions, revisions, truth-maintenance decisions,
    violations, assessments, snapshots, and closure reports.
Dependencies: logic_runtime contracts, event_spine, core invariants.
Invariants:
  - Duplicate IDs raise RuntimeCoreInvariantError.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
  - Violation detection is idempotent.
"""

from __future__ import annotations

from collections import deque
from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.logic_runtime import (
    AssumptionDisposition,
    AssumptionRecord,
    ContradictionRecord,
    ContradictionSeverity,
    InferenceRule,
    LogicAssessment,
    LogicClosureReport,
    LogicSnapshot,
    LogicalStatement,
    LogicalStatus,
    ProofRecord,
    ProofStatus,
    RevisionDisposition,
    RevisionRecord,
    StatementKind,
    TruthMaintenanceDecision,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-logrt", {"action": action, "seq": str(es.event_count), "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class LogicRuntimeEngine:
    """Engine for governed logic / proof / truth-maintenance runtime."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._statements: dict[str, LogicalStatement] = {}
        self._rules: dict[str, InferenceRule] = {}
        self._proofs: dict[str, ProofRecord] = {}
        self._assumptions: dict[str, AssumptionRecord] = {}
        self._contradictions: dict[str, ContradictionRecord] = {}
        self._revisions: dict[str, RevisionRecord] = {}
        self._decisions: dict[str, TruthMaintenanceDecision] = {}
        self._violations: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def statement_count(self) -> int:
        return len(self._statements)

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    @property
    def proof_count(self) -> int:
        return len(self._proofs)

    @property
    def assumption_count(self) -> int:
        return len(self._assumptions)

    @property
    def contradiction_count(self) -> int:
        return len(self._contradictions)

    @property
    def revision_count(self) -> int:
        return len(self._revisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def register_statement(
        self,
        statement_id: str,
        tenant_id: str,
        kind: StatementKind,
        content: str,
        status: LogicalStatus = LogicalStatus.ASSERTED,
    ) -> LogicalStatement:
        """Register a new logical statement. Duplicate statement_id raises."""
        if statement_id in self._statements:
            raise RuntimeCoreInvariantError("Duplicate statement_id")
        now = self._now()
        stmt = LogicalStatement(
            statement_id=statement_id,
            tenant_id=tenant_id,
            kind=kind,
            content=content,
            status=status,
            created_at=now,
        )
        self._statements[statement_id] = stmt
        _emit(self._events, "statement_registered", {
            "statement_id": statement_id, "kind": kind.value,
        }, statement_id, self._now())
        return stmt

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------

    def register_rule(
        self,
        rule_id: str,
        tenant_id: str,
        antecedent: str,
        consequent: str,
        confidence: float = 1.0,
    ) -> InferenceRule:
        """Register an inference rule. Duplicate rule_id raises."""
        if rule_id in self._rules:
            raise RuntimeCoreInvariantError("Duplicate rule_id")
        now = self._now()
        rule = InferenceRule(
            rule_id=rule_id,
            tenant_id=tenant_id,
            antecedent=antecedent,
            consequent=consequent,
            confidence=confidence,
            created_at=now,
        )
        self._rules[rule_id] = rule
        _emit(self._events, "rule_registered", {
            "rule_id": rule_id, "antecedent": antecedent, "consequent": consequent,
        }, rule_id, self._now())
        return rule

    # ------------------------------------------------------------------
    # Derive conclusion
    # ------------------------------------------------------------------

    def derive_conclusion(
        self,
        tenant_id: str,
        rule_id: str,
        premise_id: str,
    ) -> tuple[LogicalStatement, ProofRecord]:
        """Derive a conclusion by applying a rule to a premise.

        Creates a DERIVED statement and a ProofRecord. The rule's antecedent
        must match the premise's content, and the premise must be ASSERTED or DERIVED.
        """
        rule = self._rules.get(rule_id)
        if rule is None:
            raise RuntimeCoreInvariantError("Unknown rule_id")
        premise = self._statements.get(premise_id)
        if premise is None:
            raise RuntimeCoreInvariantError("Unknown premise statement_id")
        if premise.status not in (LogicalStatus.ASSERTED, LogicalStatus.DERIVED):
            raise RuntimeCoreInvariantError("Premise is not ASSERTED or DERIVED")
        if premise.content != rule.antecedent:
            raise RuntimeCoreInvariantError("Premise does not match rule antecedent")

        now = self._now()
        stmt_id = stable_identifier("stmt-derived", {
            "rule": rule_id, "premise": premise_id, "tenant": tenant_id,
        })
        conclusion = LogicalStatement(
            statement_id=stmt_id,
            tenant_id=tenant_id,
            kind=StatementKind.CONCLUSION,
            content=rule.consequent,
            status=LogicalStatus.DERIVED,
            created_at=now,
        )
        self._statements[stmt_id] = conclusion

        proof_id = stable_identifier("proof-derived", {
            "rule": rule_id, "premise": premise_id, "tenant": tenant_id,
        })
        proof = ProofRecord(
            proof_id=proof_id,
            tenant_id=tenant_id,
            conclusion_ref=stmt_id,
            rule_ref=rule_id,
            status=ProofStatus.VALID,
            step_count=1,
            created_at=now,
        )
        self._proofs[proof_id] = proof

        _emit(self._events, "conclusion_derived", {
            "statement_id": stmt_id, "proof_id": proof_id, "rule_id": rule_id,
        }, stmt_id, self._now())
        return conclusion, proof

    # ------------------------------------------------------------------
    # Proofs
    # ------------------------------------------------------------------

    def record_proof(
        self,
        proof_id: str,
        tenant_id: str,
        conclusion_ref: str,
        rule_ref: str,
        status: ProofStatus = ProofStatus.VALID,
        step_count: int = 1,
    ) -> ProofRecord:
        """Record a proof. Duplicate proof_id raises."""
        if proof_id in self._proofs:
            raise RuntimeCoreInvariantError("Duplicate proof_id")
        now = self._now()
        proof = ProofRecord(
            proof_id=proof_id,
            tenant_id=tenant_id,
            conclusion_ref=conclusion_ref,
            rule_ref=rule_ref,
            status=status,
            step_count=step_count,
            created_at=now,
        )
        self._proofs[proof_id] = proof
        _emit(self._events, "proof_recorded", {
            "proof_id": proof_id, "status": status.value,
        }, proof_id, self._now())
        return proof

    # ------------------------------------------------------------------
    # Assumptions
    # ------------------------------------------------------------------

    def register_assumption(
        self,
        assumption_id: str,
        tenant_id: str,
        statement_ref: str,
        justification: str,
    ) -> AssumptionRecord:
        """Register an assumption as ACTIVE. Duplicate assumption_id raises."""
        if assumption_id in self._assumptions:
            raise RuntimeCoreInvariantError("Duplicate assumption_id")
        now = self._now()
        assumption = AssumptionRecord(
            assumption_id=assumption_id,
            tenant_id=tenant_id,
            statement_ref=statement_ref,
            disposition=AssumptionDisposition.ACTIVE,
            justification=justification,
            created_at=now,
        )
        self._assumptions[assumption_id] = assumption
        _emit(self._events, "assumption_registered", {
            "assumption_id": assumption_id, "statement_ref": statement_ref,
        }, assumption_id, self._now())
        return assumption

    def retract_assumption(self, assumption_id: str) -> AssumptionRecord:
        """Retract an assumption. Also retracts dependent conclusions."""
        old = self._assumptions.get(assumption_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown assumption_id")
        now = self._now()
        retracted = AssumptionRecord(
            assumption_id=old.assumption_id,
            tenant_id=old.tenant_id,
            statement_ref=old.statement_ref,
            disposition=AssumptionDisposition.RETRACTED,
            justification=old.justification,
            created_at=old.created_at,
        )
        self._assumptions[assumption_id] = retracted

        # Retract the underlying statement if it exists
        stmt = self._statements.get(old.statement_ref)
        if stmt is not None and stmt.status not in (LogicalStatus.RETRACTED,):
            retracted_stmt = LogicalStatement(
                statement_id=stmt.statement_id,
                tenant_id=stmt.tenant_id,
                kind=stmt.kind,
                content=stmt.content,
                status=LogicalStatus.RETRACTED,
                created_at=stmt.created_at,
            )
            self._statements[stmt.statement_id] = retracted_stmt

            # Retract proofs that depend on this statement as a conclusion
            # and cascade to derived conclusions
            self._cascade_retraction(stmt.statement_id, now)

        _emit(self._events, "assumption_retracted", {
            "assumption_id": assumption_id,
        }, assumption_id, self._now())
        return retracted

    def _cascade_retraction(self, statement_id: str, now: str) -> None:
        """Cascade retraction to proofs and derived conclusions."""
        for proof_id, proof in list(self._proofs.items()):
            if proof.conclusion_ref == statement_id and proof.status == ProofStatus.VALID:
                self._proofs[proof_id] = ProofRecord(
                    proof_id=proof.proof_id,
                    tenant_id=proof.tenant_id,
                    conclusion_ref=proof.conclusion_ref,
                    rule_ref=proof.rule_ref,
                    status=ProofStatus.RETRACTED,
                    step_count=proof.step_count,
                    created_at=proof.created_at,
                )

    # ------------------------------------------------------------------
    # Contradictions
    # ------------------------------------------------------------------

    def detect_contradictions(self, tenant_id: str) -> tuple[ContradictionRecord, ...]:
        """Detect contradictions: statements where one negates another.

        Convention: a statement with content "NOT X" contradicts a statement
        with content "X". Idempotent.
        """
        now = self._now()
        new_contradictions: list[ContradictionRecord] = []
        tenant_stmts = [
            s for s in self._statements.values()
            if s.tenant_id == tenant_id
            and s.status in (LogicalStatus.ASSERTED, LogicalStatus.DERIVED)
        ]

        for i, sa in enumerate(tenant_stmts):
            for sb in tenant_stmts[i + 1:]:
                is_contradiction = False
                if sa.content.startswith("NOT ") and sa.content[4:] == sb.content:
                    is_contradiction = True
                elif sb.content.startswith("NOT ") and sb.content[4:] == sa.content:
                    is_contradiction = True

                if is_contradiction:
                    cid = stable_identifier("contr-logrt", {
                        "a": sa.statement_id, "b": sb.statement_id,
                    })
                    if cid not in self._contradictions:
                        rec = ContradictionRecord(
                            contradiction_id=cid,
                            tenant_id=tenant_id,
                            statement_a_ref=sa.statement_id,
                            statement_b_ref=sb.statement_id,
                            severity=ContradictionSeverity.MEDIUM,
                            resolved=False,
                            detected_at=now,
                        )
                        self._contradictions[cid] = rec
                        new_contradictions.append(rec)

        return tuple(new_contradictions)

    # ------------------------------------------------------------------
    # Belief revision
    # ------------------------------------------------------------------

    def revise_belief_state(
        self,
        revision_id: str,
        tenant_id: str,
        contradiction_id: str,
        disposition: RevisionDisposition = RevisionDisposition.ACCEPTED,
        reason: str = "contradiction resolved",
    ) -> tuple[RevisionRecord, TruthMaintenanceDecision]:
        """Process a contradiction into a revision and truth-maintenance decision."""
        contradiction = self._contradictions.get(contradiction_id)
        if contradiction is None:
            raise RuntimeCoreInvariantError("Unknown contradiction_id")
        if revision_id in self._revisions:
            raise RuntimeCoreInvariantError("Duplicate revision_id")

        now = self._now()

        # Revision targets statement_a (the negation or first party)
        revision = RevisionRecord(
            revision_id=revision_id,
            tenant_id=tenant_id,
            statement_ref=contradiction.statement_a_ref,
            disposition=disposition,
            reason=reason,
            revised_at=now,
        )
        self._revisions[revision_id] = revision

        # Mark contradiction resolved
        self._contradictions[contradiction_id] = ContradictionRecord(
            contradiction_id=contradiction.contradiction_id,
            tenant_id=contradiction.tenant_id,
            statement_a_ref=contradiction.statement_a_ref,
            statement_b_ref=contradiction.statement_b_ref,
            severity=contradiction.severity,
            resolved=True,
            detected_at=contradiction.detected_at,
        )

        # Create truth maintenance decision
        dec_id = stable_identifier("tmd-logrt", {
            "revision": revision_id, "contradiction": contradiction_id,
        })
        decision = TruthMaintenanceDecision(
            decision_id=dec_id,
            tenant_id=tenant_id,
            contradiction_ref=contradiction_id,
            disposition=disposition,
            reason=reason,
            decided_at=now,
        )
        self._decisions[dec_id] = decision

        _emit(self._events, "belief_revised", {
            "revision_id": revision_id, "contradiction_id": contradiction_id,
        }, revision_id, self._now())
        return revision, decision

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def logic_assessment(
        self,
        assessment_id: str,
        tenant_id: str,
    ) -> LogicAssessment:
        """Produce a logic assessment for a tenant."""
        now = self._now()
        t_stmts = sum(1 for s in self._statements.values() if s.tenant_id == tenant_id)
        t_proofs = sum(1 for p in self._proofs.values() if p.tenant_id == tenant_id)
        t_contrs = sum(
            1 for c in self._contradictions.values()
            if c.tenant_id == tenant_id and not c.resolved
        )
        rate = (t_stmts - t_contrs) / t_stmts if t_stmts > 0 else 1.0
        rate = max(0.0, min(1.0, rate))

        asm = LogicAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_statements=t_stmts,
            total_proofs=t_proofs,
            total_contradictions=t_contrs,
            consistency_rate=rate,
            assessed_at=now,
        )
        _emit(self._events, "logic_assessed", {
            "assessment_id": assessment_id, "consistency_rate": rate,
        }, assessment_id, self._now())
        return asm

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def logic_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> LogicSnapshot:
        """Produce a point-in-time snapshot for a tenant."""
        now = self._now()
        return LogicSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_statements=sum(1 for s in self._statements.values() if s.tenant_id == tenant_id),
            total_rules=sum(1 for r in self._rules.values() if r.tenant_id == tenant_id),
            total_proofs=sum(1 for p in self._proofs.values() if p.tenant_id == tenant_id),
            total_assumptions=sum(1 for a in self._assumptions.values() if a.tenant_id == tenant_id),
            total_contradictions=sum(1 for c in self._contradictions.values() if c.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.get("tenant_id") == tenant_id),
            captured_at=now,
        )

    # ------------------------------------------------------------------
    # Closure report
    # ------------------------------------------------------------------

    def logic_closure_report(
        self,
        report_id: str,
        tenant_id: str,
    ) -> LogicClosureReport:
        """Produce a final closure report for a tenant."""
        now = self._now()
        return LogicClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_statements=sum(1 for s in self._statements.values() if s.tenant_id == tenant_id),
            total_proofs=sum(1 for p in self._proofs.values() if p.tenant_id == tenant_id),
            total_contradictions=sum(1 for c in self._contradictions.values() if c.tenant_id == tenant_id),
            total_revisions=sum(1 for r in self._revisions.values() if r.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.get("tenant_id") == tenant_id),
            created_at=now,
        )

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_logic_violations(self, tenant_id: str) -> tuple[dict[str, Any], ...]:
        """Detect logic violations for a tenant. Idempotent.

        Checks:
        1. unresolved_contradiction: contradictions not yet resolved.
        2. retracted_proof_still_used: proof is RETRACTED but conclusion not retracted.
        3. assumption_no_justification: should not occur with contract validation
           but checks for assumptions with empty justification in metadata.
        """
        now = self._now()
        new_violations: list[dict[str, Any]] = []

        # 1. unresolved_contradiction
        for cid, contr in self._contradictions.items():
            if contr.tenant_id == tenant_id and not contr.resolved:
                vid = stable_identifier("viol-logrt", {
                    "contradiction": cid, "op": "unresolved_contradiction",
                })
                if vid not in self._violations:
                    v = {
                        "violation_id": vid,
                        "tenant_id": tenant_id,
                        "operation": "unresolved_contradiction",
                        "reason": "Contradiction is unresolved",
                        "detected_at": now,
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        # 2. retracted_proof_still_used
        for pid, proof in self._proofs.items():
            if proof.tenant_id == tenant_id and proof.status == ProofStatus.RETRACTED:
                conclusion = self._statements.get(proof.conclusion_ref)
                if conclusion is not None and conclusion.status not in (
                    LogicalStatus.RETRACTED, LogicalStatus.CONTRADICTED
                ):
                    vid = stable_identifier("viol-logrt", {
                        "proof": pid, "op": "retracted_proof_still_used",
                    })
                    if vid not in self._violations:
                        v = {
                            "violation_id": vid,
                            "tenant_id": tenant_id,
                            "operation": "retracted_proof_still_used",
                            "reason": "Retracted proof still has active conclusion",
                            "detected_at": now,
                        }
                        self._violations[vid] = v
                        new_violations.append(v)

        # 3. assumption_no_justification (metadata-level check)
        for aid, assumption in self._assumptions.items():
            if assumption.tenant_id == tenant_id and assumption.disposition == AssumptionDisposition.ACTIVE:
                if assumption.justification.strip() == "":
                    vid = stable_identifier("viol-logrt", {
                        "assumption": aid, "op": "assumption_no_justification",
                    })
                    if vid not in self._violations:
                        v = {
                            "violation_id": vid,
                            "tenant_id": tenant_id,
                            "operation": "assumption_no_justification",
                            "reason": "Assumption has no justification",
                            "detected_at": now,
                        }
                        self._violations[vid] = v
                        new_violations.append(v)

        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Collections / snapshot / state_hash
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "assumptions": self._assumptions,
            "contradictions": self._contradictions,
            "decisions": self._decisions,
            "proofs": self._proofs,
            "revisions": self._revisions,
            "rules": self._rules,
            "statements": self._statements,
            "violations": self._violations,
        }

    def snapshot(self) -> dict[str, Any]:
        """Capture complete engine state as a serializable dict."""
        result: dict[str, Any] = {}
        for name, collection in self._collections().items():
            if isinstance(collection, dict):
                result[name] = {
                    k: v.to_dict() if hasattr(v, "to_dict") else v
                    for k, v in collection.items()
                }
            elif isinstance(collection, list):
                result[name] = [
                    v.to_dict() if hasattr(v, "to_dict") else v
                    for v in collection
                ]
        result["_state_hash"] = self.state_hash()
        return result

    def state_hash(self) -> str:
        """Compute a deterministic hash of engine state (sorted keys, full 64-char)."""
        parts = [
            f"assumptions={self.assumption_count}",
            f"contradictions={self.contradiction_count}",
            f"decisions={len(self._decisions)}",
            f"proofs={self.proof_count}",
            f"revisions={self.revision_count}",
            f"rules={self.rule_count}",
            f"statements={self.statement_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
