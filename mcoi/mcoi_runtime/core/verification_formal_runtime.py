"""Purpose: formal verification runtime engine.
Governance scope: governed specification, property, verification run,
    proof certificate, counter-example, invariant runtime with violation
    detection and replayable state hashing.
Dependencies: event_spine, invariants, contracts, engine_protocol.
Invariants:
  - Duplicate IDs are rejected fail-closed.
  - Verification run transitions: PENDING->PROVING->PROVEN|DISPROVEN|TIMEOUT.
  - Violation detection is idempotent.
  - All outputs are frozen.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.verification_formal_runtime import (
    AssertionStatus,
    CounterExample,
    FormalProperty,
    FormalSpecification,
    FormalVerificationClosureReport,
    FormalVerificationSnapshot,
    FormalVerificationViolation,
    FormalVerificationStatus,
    InvariantRecord,
    ProofCertificate,
    ProofMethod,
    PropertyKind,
    SpecificationStatus,
    VerificationAssessment,
    VerificationRun,
)
from mcoi_runtime.core.engine_protocol import Clock, WallClock
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


# ---------------------------------------------------------------------------
# Terminal states
# ---------------------------------------------------------------------------

_RUN_TERMINAL = frozenset({
    FormalVerificationStatus.PROVEN,
    FormalVerificationStatus.DISPROVEN,
    FormalVerificationStatus.TIMEOUT,
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit(es: EventSpineEngine, action: str, payload: dict[str, Any], cid: str, clock: Clock) -> None:
    now = clock.now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-fvr", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.EXTERNAL,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)


class FormalVerificationEngine:
    """Governed formal verification runtime engine."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._specs: dict[str, FormalSpecification] = {}
        self._properties: dict[str, FormalProperty] = {}
        self._runs: dict[str, VerificationRun] = {}
        self._certificates: dict[str, ProofCertificate] = {}
        self._counterexamples: dict[str, CounterExample] = {}
        self._invariants: dict[str, InvariantRecord] = {}
        self._violations: dict[str, FormalVerificationViolation] = {}

    # -- Clock --

    def _now(self) -> str:
        return self._clock.now_iso()

    # -- Properties --

    @property
    def spec_count(self) -> int:
        return len(self._specs)

    @property
    def property_count(self) -> int:
        return len(self._properties)

    @property
    def run_count(self) -> int:
        return len(self._runs)

    @property
    def certificate_count(self) -> int:
        return len(self._certificates)

    @property
    def counterexample_count(self) -> int:
        return len(self._counterexamples)

    @property
    def invariant_count(self) -> int:
        return len(self._invariants)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # -------------------------------------------------------------------
    # Specifications
    # -------------------------------------------------------------------

    def register_specification(
        self,
        spec_id: str,
        tenant_id: str,
        display_name: str,
        target_runtime: str = "default",
    ) -> FormalSpecification:
        if spec_id in self._specs:
            raise RuntimeCoreInvariantError("duplicate spec_id")
        now = self._now()
        spec = FormalSpecification(
            spec_id=spec_id, tenant_id=tenant_id,
            display_name=display_name, target_runtime=target_runtime,
            status=SpecificationStatus.ACTIVE, property_count=0,
            created_at=now,
        )
        self._specs[spec_id] = spec
        _emit(self._events, "register_specification", {"spec_id": spec_id}, spec_id, self._clock)
        return spec

    # -------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------

    def add_property(
        self,
        property_id: str,
        tenant_id: str,
        spec_ref: str,
        kind: PropertyKind = PropertyKind.SAFETY,
        expression: str = "true",
    ) -> FormalProperty:
        if property_id in self._properties:
            raise RuntimeCoreInvariantError("duplicate property_id")
        if spec_ref not in self._specs:
            raise RuntimeCoreInvariantError("unknown spec_ref")
        now = self._now()
        prop = FormalProperty(
            property_id=property_id, tenant_id=tenant_id,
            spec_ref=spec_ref, kind=kind,
            expression=expression, status=AssertionStatus.UNKNOWN,
            created_at=now,
        )
        self._properties[property_id] = prop
        # Update spec property_count
        spec = self._specs[spec_ref]
        updated_spec = FormalSpecification(
            spec_id=spec.spec_id, tenant_id=spec.tenant_id,
            display_name=spec.display_name, target_runtime=spec.target_runtime,
            status=spec.status, property_count=spec.property_count + 1,
            created_at=spec.created_at,
        )
        self._specs[spec_ref] = updated_spec
        _emit(self._events, "add_property", {"property_id": property_id, "spec_ref": spec_ref}, property_id, self._clock)
        return prop

    # -------------------------------------------------------------------
    # Verification runs
    # -------------------------------------------------------------------

    def start_verification_run(
        self,
        run_id: str,
        tenant_id: str,
        spec_ref: str,
        method: ProofMethod = ProofMethod.MODEL_CHECK,
    ) -> VerificationRun:
        if run_id in self._runs:
            raise RuntimeCoreInvariantError("duplicate run_id")
        now = self._now()
        run = VerificationRun(
            run_id=run_id, tenant_id=tenant_id,
            spec_ref=spec_ref, method=method,
            status=FormalVerificationStatus.PROVING,
            duration_ms=0.0, created_at=now,
        )
        self._runs[run_id] = run
        _emit(self._events, "start_verification_run", {"run_id": run_id}, run_id, self._clock)
        return run

    def _get_run(self, run_id: str) -> VerificationRun:
        if run_id not in self._runs:
            raise RuntimeCoreInvariantError("unknown run_id")
        return self._runs[run_id]

    def complete_run(self, run_id: str, duration_ms: float = 0.0) -> VerificationRun:
        run = self._get_run(run_id)
        if run.status in _RUN_TERMINAL:
            raise RuntimeCoreInvariantError("run is in terminal state")
        # Determine if PROVEN or DISPROVEN based on properties
        spec_props = [p for p in self._properties.values() if p.spec_ref == run.spec_ref]
        all_holds = all(p.status == AssertionStatus.HOLDS for p in spec_props) if spec_props else True
        any_violated = any(p.status == AssertionStatus.VIOLATED for p in spec_props)
        if any_violated:
            target = FormalVerificationStatus.DISPROVEN
        elif all_holds:
            target = FormalVerificationStatus.PROVEN
        else:
            target = FormalVerificationStatus.PROVEN
        now = self._now()
        updated = VerificationRun(
            run_id=run.run_id, tenant_id=run.tenant_id,
            spec_ref=run.spec_ref, method=run.method,
            status=target, duration_ms=duration_ms,
            created_at=now,
        )
        self._runs[run_id] = updated
        _emit(self._events, f"run_{target.value}", {"run_id": run_id}, run_id, self._clock)
        return updated

    def timeout_run(self, run_id: str, duration_ms: float = 0.0) -> VerificationRun:
        run = self._get_run(run_id)
        if run.status in _RUN_TERMINAL:
            raise RuntimeCoreInvariantError("run is in terminal state")
        now = self._now()
        updated = VerificationRun(
            run_id=run.run_id, tenant_id=run.tenant_id,
            spec_ref=run.spec_ref, method=run.method,
            status=FormalVerificationStatus.TIMEOUT,
            duration_ms=duration_ms, created_at=now,
        )
        self._runs[run_id] = updated
        _emit(self._events, "run_timeout", {"run_id": run_id}, run_id, self._clock)
        return updated

    # -------------------------------------------------------------------
    # Proof certificates
    # -------------------------------------------------------------------

    def record_proof_certificate(
        self,
        cert_id: str,
        tenant_id: str,
        run_ref: str,
        property_ref: str,
        proven: bool = True,
        witness: str = "auto-generated",
    ) -> ProofCertificate:
        if cert_id in self._certificates:
            raise RuntimeCoreInvariantError("duplicate cert_id")
        now = self._now()
        cert = ProofCertificate(
            cert_id=cert_id, tenant_id=tenant_id,
            run_ref=run_ref, property_ref=property_ref,
            proven=proven, witness=witness, created_at=now,
        )
        self._certificates[cert_id] = cert
        # Update property status based on proof
        if property_ref in self._properties:
            prop = self._properties[property_ref]
            new_status = AssertionStatus.HOLDS if proven else AssertionStatus.VIOLATED
            updated_prop = FormalProperty(
                property_id=prop.property_id, tenant_id=prop.tenant_id,
                spec_ref=prop.spec_ref, kind=prop.kind,
                expression=prop.expression, status=new_status,
                created_at=prop.created_at,
            )
            self._properties[property_ref] = updated_prop
        _emit(self._events, "record_proof_certificate", {"cert_id": cert_id}, cert_id, self._clock)
        return cert

    # -------------------------------------------------------------------
    # Counter-examples
    # -------------------------------------------------------------------

    def record_counter_example(
        self,
        example_id: str,
        tenant_id: str,
        run_ref: str,
        property_ref: str,
        trace: str = "counter-example trace",
    ) -> CounterExample:
        if example_id in self._counterexamples:
            raise RuntimeCoreInvariantError("duplicate example_id")
        now = self._now()
        ce = CounterExample(
            example_id=example_id, tenant_id=tenant_id,
            run_ref=run_ref, property_ref=property_ref,
            trace=trace, created_at=now,
        )
        self._counterexamples[example_id] = ce
        # Mark property as VIOLATED
        if property_ref in self._properties:
            prop = self._properties[property_ref]
            updated_prop = FormalProperty(
                property_id=prop.property_id, tenant_id=prop.tenant_id,
                spec_ref=prop.spec_ref, kind=prop.kind,
                expression=prop.expression, status=AssertionStatus.VIOLATED,
                created_at=prop.created_at,
            )
            self._properties[property_ref] = updated_prop
        _emit(self._events, "record_counter_example", {"example_id": example_id}, example_id, self._clock)
        return ce

    # -------------------------------------------------------------------
    # Invariants
    # -------------------------------------------------------------------

    def register_invariant(
        self,
        invariant_id: str,
        tenant_id: str,
        target_runtime: str,
        expression: str = "true",
    ) -> InvariantRecord:
        if invariant_id in self._invariants:
            raise RuntimeCoreInvariantError("duplicate invariant_id")
        now = self._now()
        inv = InvariantRecord(
            invariant_id=invariant_id, tenant_id=tenant_id,
            target_runtime=target_runtime, expression=expression,
            status=AssertionStatus.UNKNOWN, created_at=now,
        )
        self._invariants[invariant_id] = inv
        _emit(self._events, "register_invariant", {"invariant_id": invariant_id}, invariant_id, self._clock)
        return inv

    def check_invariant(self, invariant_id: str) -> InvariantRecord:
        if invariant_id not in self._invariants:
            raise RuntimeCoreInvariantError("unknown invariant_id")
        inv = self._invariants[invariant_id]
        # Evaluate: expression is "true"-like if it looks truthy
        expr_lower = inv.expression.strip().lower()
        holds = expr_lower in ("true", "1", "yes", "holds", "valid", "ok")
        new_status = AssertionStatus.HOLDS if holds else AssertionStatus.VIOLATED
        now = self._now()
        updated = InvariantRecord(
            invariant_id=inv.invariant_id, tenant_id=inv.tenant_id,
            target_runtime=inv.target_runtime, expression=inv.expression,
            status=new_status, created_at=now,
        )
        self._invariants[invariant_id] = updated
        _emit(self._events, "check_invariant", {
            "invariant_id": invariant_id, "status": new_status.value,
        }, invariant_id, self._clock)
        return updated

    # -------------------------------------------------------------------
    # Assessment
    # -------------------------------------------------------------------

    def verification_assessment(self, assessment_id: str, tenant_id: str) -> VerificationAssessment:
        now = self._now()
        t_specs = len([s for s in self._specs.values() if s.tenant_id == tenant_id])
        t_props = len([p for p in self._properties.values() if p.tenant_id == tenant_id])
        proven = len([p for p in self._properties.values()
                      if p.tenant_id == tenant_id and p.status == AssertionStatus.HOLDS])
        coverage = proven / t_props if t_props > 0 else 0.0
        assessment = VerificationAssessment(
            assessment_id=assessment_id, tenant_id=tenant_id,
            total_specs=t_specs, total_properties=t_props,
            total_proven=proven, proof_coverage=round(coverage, 4),
            assessed_at=now,
        )
        _emit(self._events, "verification_assessment", {"assessment_id": assessment_id}, assessment_id, self._clock)
        return assessment

    # -------------------------------------------------------------------
    # Snapshot
    # -------------------------------------------------------------------

    def verification_snapshot(self, snapshot_id: str, tenant_id: str) -> FormalVerificationSnapshot:
        now = self._now()
        snap = FormalVerificationSnapshot(
            snapshot_id=snapshot_id, tenant_id=tenant_id,
            total_specs=len([s for s in self._specs.values() if s.tenant_id == tenant_id]),
            total_properties=len([p for p in self._properties.values() if p.tenant_id == tenant_id]),
            total_runs=len([r for r in self._runs.values() if r.tenant_id == tenant_id]),
            total_certificates=len([c for c in self._certificates.values() if c.tenant_id == tenant_id]),
            total_counterexamples=len([ce for ce in self._counterexamples.values() if ce.tenant_id == tenant_id]),
            total_violations=len([v for v in self._violations.values() if v.tenant_id == tenant_id]),
            captured_at=now,
        )
        _emit(self._events, "verification_snapshot", {"snapshot_id": snapshot_id}, snapshot_id, self._clock)
        return snap

    # -------------------------------------------------------------------
    # Closure report
    # -------------------------------------------------------------------

    def verification_closure_report(self, report_id: str, tenant_id: str) -> FormalVerificationClosureReport:
        now = self._now()
        proven = len([p for p in self._properties.values()
                      if p.tenant_id == tenant_id and p.status == AssertionStatus.HOLDS])
        report = FormalVerificationClosureReport(
            report_id=report_id, tenant_id=tenant_id,
            total_specs=len([s for s in self._specs.values() if s.tenant_id == tenant_id]),
            total_properties=len([p for p in self._properties.values() if p.tenant_id == tenant_id]),
            total_proven=proven,
            total_violations=len([v for v in self._violations.values() if v.tenant_id == tenant_id]),
            created_at=now,
        )
        _emit(self._events, "verification_closure_report", {"report_id": report_id}, report_id, self._clock)
        return report

    # -------------------------------------------------------------------
    # Violations
    # -------------------------------------------------------------------

    def detect_verification_violations(self, tenant_id: str) -> tuple[FormalVerificationViolation, ...]:
        new_violations: list[FormalVerificationViolation] = []
        now = self._now()

        # 1. Violated invariant
        for inv in self._invariants.values():
            if inv.tenant_id != tenant_id:
                continue
            if inv.status == AssertionStatus.VIOLATED:
                vid = stable_identifier("viol-fvr", {"invariant_id": inv.invariant_id, "reason": "violated_invariant"})
                if vid not in self._violations:
                    v = FormalVerificationViolation(
                        violation_id=vid, tenant_id=tenant_id,
                        operation="violated_invariant",
                        reason="formal invariant is violated",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 2. Unproven safety property
        for p in self._properties.values():
            if p.tenant_id != tenant_id:
                continue
            if p.kind == PropertyKind.SAFETY and p.status != AssertionStatus.HOLDS:
                vid = stable_identifier("viol-fvr", {"property_id": p.property_id, "reason": "unproven_safety_property"})
                if vid not in self._violations:
                    v = FormalVerificationViolation(
                        violation_id=vid, tenant_id=tenant_id,
                        operation="unproven_safety_property",
                        reason="safety property is not proven",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 3. Timeout on critical spec
        for r in self._runs.values():
            if r.tenant_id != tenant_id:
                continue
            if r.status == FormalVerificationStatus.TIMEOUT:
                vid = stable_identifier("viol-fvr", {"run_id": r.run_id, "reason": "timeout_critical_spec"})
                if vid not in self._violations:
                    v = FormalVerificationViolation(
                        violation_id=vid, tenant_id=tenant_id,
                        operation="timeout_critical_spec",
                        reason="verification run timed out",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        if new_violations:
            _emit(self._events, "detect_verification_violations", {
                "tenant_id": tenant_id, "count": len(new_violations),
            }, tenant_id, self._clock)
        return tuple(new_violations)

    # -------------------------------------------------------------------
    # Collections / snapshot / state_hash
    # -------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        return {
            "specs": self._specs,
            "properties": self._properties,
            "runs": self._runs,
            "certificates": self._certificates,
            "counterexamples": self._counterexamples,
            "invariants": self._invariants,
            "violations": self._violations,
        }

    def snapshot(self) -> dict[str, Any]:
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
        parts: list[str] = []
        for k in sorted(self._specs):
            parts.append(f"spec:{k}:{self._specs[k].status.value}")
        for k in sorted(self._properties):
            parts.append(f"property:{k}:{self._properties[k].status.value}")
        for k in sorted(self._runs):
            parts.append(f"run:{k}:{self._runs[k].status.value}")
        for k in sorted(self._certificates):
            parts.append(f"cert:{k}:{self._certificates[k].proven}")
        for k in sorted(self._counterexamples):
            parts.append(f"counterexample:{k}")
        for k in sorted(self._invariants):
            parts.append(f"invariant:{k}:{self._invariants[k].status.value}")
        for k in sorted(self._violations):
            parts.append(f"violation:{k}")
        return sha256("|".join(parts).encode()).hexdigest()
