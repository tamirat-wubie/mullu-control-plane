"""Purpose: risk / compliance integration bridge.
Governance scope: composing risk/compliance engine with campaign, program,
    portfolio, connector, domain-pack scopes; evidence binding; failure
    escalation; memory mesh and operational graph attachment.
Dependencies: risk_compliance engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every risk/compliance operation emits events.
  - Risk state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.risk_compliance import (
    ComplianceDisposition,
    ControlStatus,
    ControlTestStatus,
    EvidenceSourceKind,
    ExceptionStatus,
    RiskCategory,
    RiskSeverity,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .risk_compliance import RiskComplianceEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-rcint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class RiskComplianceIntegration:
    """Integration bridge for risk/compliance with platform layers."""

    def __init__(
        self,
        risk_engine: RiskComplianceEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(risk_engine, RiskComplianceEngine):
            raise RuntimeCoreInvariantError("risk_engine must be a RiskComplianceEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._risk = risk_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Scope assessments
    # ------------------------------------------------------------------

    def assess_campaign(
        self,
        assessment_id: str,
        campaign_ref_id: str,
    ) -> dict[str, Any]:
        """Assess risk for a campaign scope."""
        assessment = self._risk.assess_scope(assessment_id, campaign_ref_id)
        snapshot_id = f"{assessment_id}-snap"
        try:
            snapshot = self._risk.capture_compliance_snapshot(snapshot_id, campaign_ref_id)
        except RuntimeCoreInvariantError:
            snapshot = None
        _emit(self._events, "campaign_assessed", {
            "assessment_id": assessment_id,
            "campaign_ref_id": campaign_ref_id,
            "overall_severity": assessment.overall_severity.value,
        }, assessment_id)
        result: dict[str, Any] = {
            "assessment_id": assessment_id,
            "scope_ref_id": campaign_ref_id,
            "scope_type": "campaign",
            "overall_severity": assessment.overall_severity.value,
            "risk_score": assessment.risk_score,
            "risk_count": assessment.risk_count,
        }
        if snapshot is not None:
            result["disposition"] = snapshot.disposition.value
            result["compliance_pct"] = snapshot.compliance_pct
        return result

    def assess_program(
        self,
        assessment_id: str,
        program_ref_id: str,
    ) -> dict[str, Any]:
        """Assess risk for a program scope."""
        assessment = self._risk.assess_scope(assessment_id, program_ref_id)
        snapshot_id = f"{assessment_id}-snap"
        try:
            snapshot = self._risk.capture_compliance_snapshot(snapshot_id, program_ref_id)
        except RuntimeCoreInvariantError:
            snapshot = None
        _emit(self._events, "program_assessed", {
            "assessment_id": assessment_id,
            "program_ref_id": program_ref_id,
            "overall_severity": assessment.overall_severity.value,
        }, assessment_id)
        result: dict[str, Any] = {
            "assessment_id": assessment_id,
            "scope_ref_id": program_ref_id,
            "scope_type": "program",
            "overall_severity": assessment.overall_severity.value,
            "risk_score": assessment.risk_score,
            "risk_count": assessment.risk_count,
        }
        if snapshot is not None:
            result["disposition"] = snapshot.disposition.value
            result["compliance_pct"] = snapshot.compliance_pct
        return result

    def assess_portfolio(
        self,
        assessment_id: str,
        portfolio_ref_id: str,
    ) -> dict[str, Any]:
        """Assess risk for a portfolio scope."""
        assessment = self._risk.assess_scope(assessment_id, portfolio_ref_id)
        snapshot_id = f"{assessment_id}-snap"
        try:
            snapshot = self._risk.capture_compliance_snapshot(snapshot_id, portfolio_ref_id)
        except RuntimeCoreInvariantError:
            snapshot = None
        _emit(self._events, "portfolio_assessed", {
            "assessment_id": assessment_id,
            "portfolio_ref_id": portfolio_ref_id,
            "overall_severity": assessment.overall_severity.value,
        }, assessment_id)
        result: dict[str, Any] = {
            "assessment_id": assessment_id,
            "scope_ref_id": portfolio_ref_id,
            "scope_type": "portfolio",
            "overall_severity": assessment.overall_severity.value,
            "risk_score": assessment.risk_score,
            "risk_count": assessment.risk_count,
        }
        if snapshot is not None:
            result["disposition"] = snapshot.disposition.value
            result["compliance_pct"] = snapshot.compliance_pct
        return result

    def assess_connector(
        self,
        assessment_id: str,
        connector_ref_id: str,
    ) -> dict[str, Any]:
        """Assess risk for a connector scope."""
        assessment = self._risk.assess_scope(assessment_id, connector_ref_id)
        snapshot_id = f"{assessment_id}-snap"
        try:
            snapshot = self._risk.capture_compliance_snapshot(snapshot_id, connector_ref_id)
        except RuntimeCoreInvariantError:
            snapshot = None
        _emit(self._events, "connector_assessed", {
            "assessment_id": assessment_id,
            "connector_ref_id": connector_ref_id,
            "overall_severity": assessment.overall_severity.value,
        }, assessment_id)
        result: dict[str, Any] = {
            "assessment_id": assessment_id,
            "scope_ref_id": connector_ref_id,
            "scope_type": "connector",
            "overall_severity": assessment.overall_severity.value,
            "risk_score": assessment.risk_score,
            "risk_count": assessment.risk_count,
        }
        if snapshot is not None:
            result["disposition"] = snapshot.disposition.value
            result["compliance_pct"] = snapshot.compliance_pct
        return result

    def assess_domain_pack(
        self,
        assessment_id: str,
        domain_pack_ref_id: str,
    ) -> dict[str, Any]:
        """Assess risk for a domain pack scope."""
        assessment = self._risk.assess_scope(assessment_id, domain_pack_ref_id)
        snapshot_id = f"{assessment_id}-snap"
        try:
            snapshot = self._risk.capture_compliance_snapshot(snapshot_id, domain_pack_ref_id)
        except RuntimeCoreInvariantError:
            snapshot = None
        _emit(self._events, "domain_pack_assessed", {
            "assessment_id": assessment_id,
            "domain_pack_ref_id": domain_pack_ref_id,
            "overall_severity": assessment.overall_severity.value,
        }, assessment_id)
        result: dict[str, Any] = {
            "assessment_id": assessment_id,
            "scope_ref_id": domain_pack_ref_id,
            "scope_type": "domain_pack",
            "overall_severity": assessment.overall_severity.value,
            "risk_score": assessment.risk_score,
            "risk_count": assessment.risk_count,
        }
        if snapshot is not None:
            result["disposition"] = snapshot.disposition.value
            result["compliance_pct"] = snapshot.compliance_pct
        return result

    # ------------------------------------------------------------------
    # Evidence binding
    # ------------------------------------------------------------------

    def bind_artifact_evidence(
        self,
        test_id: str,
        control_id: str,
        artifact_refs: list[str],
        *,
        tester: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        """Bind artifact evidence to a control via a test record."""
        test = self._risk.record_control_test(
            test_id, control_id, ControlTestStatus.PASSED,
            evidence_refs=artifact_refs,
            tester=tester,
            notes=notes or "artifact evidence",
        )
        _emit(self._events, "artifact_evidence_bound", {
            "test_id": test_id, "control_id": control_id,
            "artifact_count": len(artifact_refs),
        }, test_id)
        return {
            "test_id": test_id,
            "control_id": control_id,
            "evidence_kind": EvidenceSourceKind.ARTIFACT.value,
            "evidence_count": len(artifact_refs),
            "status": test.status.value,
        }

    def bind_memory_evidence(
        self,
        test_id: str,
        control_id: str,
        memory_refs: list[str],
        *,
        tester: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        """Bind memory evidence to a control via a test record."""
        test = self._risk.record_control_test(
            test_id, control_id, ControlTestStatus.PASSED,
            evidence_refs=memory_refs,
            tester=tester,
            notes=notes or "memory evidence",
        )
        _emit(self._events, "memory_evidence_bound", {
            "test_id": test_id, "control_id": control_id,
            "memory_count": len(memory_refs),
        }, test_id)
        return {
            "test_id": test_id,
            "control_id": control_id,
            "evidence_kind": EvidenceSourceKind.MEMORY.value,
            "evidence_count": len(memory_refs),
            "status": test.status.value,
        }

    def bind_event_evidence(
        self,
        test_id: str,
        control_id: str,
        event_refs: list[str],
        *,
        tester: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        """Bind event evidence to a control via a test record."""
        test = self._risk.record_control_test(
            test_id, control_id, ControlTestStatus.PASSED,
            evidence_refs=event_refs,
            tester=tester,
            notes=notes or "event evidence",
        )
        _emit(self._events, "event_evidence_bound", {
            "test_id": test_id, "control_id": control_id,
            "event_count": len(event_refs),
        }, test_id)
        return {
            "test_id": test_id,
            "control_id": control_id,
            "evidence_kind": EvidenceSourceKind.EVENT.value,
            "evidence_count": len(event_refs),
            "status": test.status.value,
        }

    # ------------------------------------------------------------------
    # Failure escalation
    # ------------------------------------------------------------------

    def block_or_escalate_from_failure(
        self,
        failure_id: str,
        control_id: str,
        *,
        test_id: str = "",
        scope_ref_id: str = "",
        severity: RiskSeverity = RiskSeverity.MEDIUM,
    ) -> dict[str, Any]:
        """Record a control failure and escalate/block based on severity."""
        escalated = severity in (RiskSeverity.CRITICAL, RiskSeverity.HIGH)
        blocked = severity == RiskSeverity.CRITICAL
        failure = self._risk.record_control_failure(
            failure_id, control_id,
            test_id=test_id,
            scope_ref_id=scope_ref_id,
            severity=severity,
            action_taken="blocked" if blocked else ("escalated" if escalated else "logged"),
            escalated=escalated,
            blocked=blocked,
        )

        # Auto-register a risk for critical/high failures
        risk_id = ""
        if escalated:
            risk_id = f"{failure_id}-risk"
            try:
                self._risk.register_risk(
                    risk_id,
                    f"Control failure: {control_id}",
                    severity=severity,
                    category=RiskCategory.COMPLIANCE,
                    likelihood=0.8 if severity == RiskSeverity.CRITICAL else 0.5,
                    impact=0.9 if severity == RiskSeverity.CRITICAL else 0.6,
                    scope_ref_id=scope_ref_id,
                )
            except RuntimeCoreInvariantError:
                risk_id = ""

        _emit(self._events, "failure_escalated", {
            "failure_id": failure_id, "control_id": control_id,
            "severity": severity.value, "escalated": escalated, "blocked": blocked,
        }, failure_id)
        return {
            "failure_id": failure_id,
            "control_id": control_id,
            "severity": severity.value,
            "escalated": escalated,
            "blocked": blocked,
            "risk_id": risk_id,
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_risk_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist risk/compliance state to memory mesh."""
        now = _now_iso()
        failed = self._risk.failed_controls()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_risks": self._risk.risk_count,
            "total_requirements": self._risk.requirement_count,
            "total_controls": self._risk.control_count,
            "total_bindings": self._risk.binding_count,
            "total_tests": self._risk.test_count,
            "total_exceptions": self._risk.exception_count,
            "total_failures": self._risk.failure_count,
            "failed_control_ids": [c.control_id for c in failed],
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-risk", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Risk/compliance state: {scope_ref_id}",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("risk", "compliance", "controls"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "risk_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_risk_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return risk/compliance state suitable for operational graph."""
        failed = self._risk.failed_controls()
        scope_failures = self._risk.failures_for_scope(scope_ref_id)
        scope_exceptions = self._risk.active_exceptions_for_scope(scope_ref_id)
        return {
            "scope_ref_id": scope_ref_id,
            "total_risks": self._risk.risk_count,
            "total_controls": self._risk.control_count,
            "total_bindings": self._risk.binding_count,
            "failed_control_ids": [c.control_id for c in failed],
            "scope_failure_count": len(scope_failures),
            "scope_active_exceptions": len(scope_exceptions),
        }
