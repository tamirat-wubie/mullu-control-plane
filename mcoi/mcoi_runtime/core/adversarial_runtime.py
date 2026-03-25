"""Purpose: red-team / adversarial reasoning runtime engine.
Governance scope: governed attack scenario, vulnerability, exploit path,
    defense, stress test runtime with violation detection and replayable
    state hashing.
Dependencies: event_spine, invariants, contracts, engine_protocol.
Invariants:
  - Duplicate IDs are rejected fail-closed.
  - Attack status transitions are guarded (PLANNED->EXECUTING->COMPLETED|BLOCKED).
  - Vulnerability transitions are guarded (OPEN->MITIGATED|ACCEPTED|FALSE_POSITIVE).
  - Violation detection is idempotent.
  - All outputs are frozen.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.adversarial_runtime import (
    AdversarialAssessment,
    AdversarialClosureReport,
    AdversarialSnapshot,
    AdversarialViolation,
    AttackKind,
    AttackScenario,
    AttackStatus,
    DefenseDisposition,
    DefenseRecord,
    ExploitPath,
    ExploitSeverity,
    StressTestRecord,
    VulnerabilityRecord,
    VulnerabilityStatus,
)
from mcoi_runtime.core.engine_protocol import Clock, WallClock
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


# ---------------------------------------------------------------------------
# Terminal states
# ---------------------------------------------------------------------------

_ATTACK_TERMINAL = frozenset({AttackStatus.COMPLETED, AttackStatus.BLOCKED})
_VULNERABILITY_TERMINAL = frozenset({
    VulnerabilityStatus.MITIGATED,
    VulnerabilityStatus.ACCEPTED,
    VulnerabilityStatus.FALSE_POSITIVE,
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit(es: EventSpineEngine, action: str, payload: dict[str, Any], cid: str, clock: Clock) -> None:
    now = clock.now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-adv", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.EXTERNAL,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)


class AdversarialRuntimeEngine:
    """Governed red-team / adversarial reasoning engine."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._scenarios: dict[str, AttackScenario] = {}
        self._vulnerabilities: dict[str, VulnerabilityRecord] = {}
        self._exploits: dict[str, ExploitPath] = {}
        self._defenses: dict[str, DefenseRecord] = {}
        self._stress_tests: dict[str, StressTestRecord] = {}
        self._violations: dict[str, AdversarialViolation] = {}

    # -- Clock --

    def _now(self) -> str:
        return self._clock.now_iso()

    # -- Properties --

    @property
    def scenario_count(self) -> int:
        return len(self._scenarios)

    @property
    def vulnerability_count(self) -> int:
        return len(self._vulnerabilities)

    @property
    def exploit_count(self) -> int:
        return len(self._exploits)

    @property
    def defense_count(self) -> int:
        return len(self._defenses)

    @property
    def stress_test_count(self) -> int:
        return len(self._stress_tests)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # -------------------------------------------------------------------
    # Attack scenarios
    # -------------------------------------------------------------------

    def create_attack_scenario(
        self,
        scenario_id: str,
        tenant_id: str,
        display_name: str,
        kind: AttackKind = AttackKind.POLICY_BYPASS,
        target_runtime: str = "default",
    ) -> AttackScenario:
        if scenario_id in self._scenarios:
            raise RuntimeCoreInvariantError(f"duplicate scenario_id: {scenario_id}")
        now = self._now()
        scenario = AttackScenario(
            scenario_id=scenario_id, tenant_id=tenant_id,
            display_name=display_name, kind=kind,
            target_runtime=target_runtime,
            status=AttackStatus.PLANNED, created_at=now,
        )
        self._scenarios[scenario_id] = scenario
        _emit(self._events, "create_attack_scenario", {"scenario_id": scenario_id}, scenario_id, self._clock)
        return scenario

    def _get_scenario(self, scenario_id: str) -> AttackScenario:
        if scenario_id not in self._scenarios:
            raise RuntimeCoreInvariantError(f"unknown scenario_id: {scenario_id}")
        return self._scenarios[scenario_id]

    def _transition_scenario(self, scenario_id: str, target: AttackStatus) -> AttackScenario:
        scenario = self._get_scenario(scenario_id)
        if scenario.status in _ATTACK_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"scenario {scenario_id} is in terminal state {scenario.status.value}"
            )
        now = self._now()
        updated = AttackScenario(
            scenario_id=scenario.scenario_id, tenant_id=scenario.tenant_id,
            display_name=scenario.display_name, kind=scenario.kind,
            target_runtime=scenario.target_runtime,
            status=target, created_at=now,
        )
        self._scenarios[scenario_id] = updated
        _emit(self._events, f"scenario_{target.value}", {"scenario_id": scenario_id}, scenario_id, self._clock)
        return updated

    def execute_scenario(self, scenario_id: str) -> AttackScenario:
        return self._transition_scenario(scenario_id, AttackStatus.EXECUTING)

    def complete_scenario(self, scenario_id: str) -> AttackScenario:
        return self._transition_scenario(scenario_id, AttackStatus.COMPLETED)

    def block_scenario(self, scenario_id: str) -> AttackScenario:
        return self._transition_scenario(scenario_id, AttackStatus.BLOCKED)

    # -------------------------------------------------------------------
    # Vulnerabilities
    # -------------------------------------------------------------------

    def register_vulnerability(
        self,
        vulnerability_id: str,
        tenant_id: str,
        target_runtime: str,
        severity: ExploitSeverity = ExploitSeverity.MEDIUM,
        description: str = "Unspecified vulnerability",
    ) -> VulnerabilityRecord:
        if vulnerability_id in self._vulnerabilities:
            raise RuntimeCoreInvariantError(f"duplicate vulnerability_id: {vulnerability_id}")
        now = self._now()
        vuln = VulnerabilityRecord(
            vulnerability_id=vulnerability_id, tenant_id=tenant_id,
            target_runtime=target_runtime, status=VulnerabilityStatus.OPEN,
            severity=severity, description=description, detected_at=now,
        )
        self._vulnerabilities[vulnerability_id] = vuln
        _emit(self._events, "register_vulnerability", {"vulnerability_id": vulnerability_id}, vulnerability_id, self._clock)
        return vuln

    def _get_vulnerability(self, vulnerability_id: str) -> VulnerabilityRecord:
        if vulnerability_id not in self._vulnerabilities:
            raise RuntimeCoreInvariantError(f"unknown vulnerability_id: {vulnerability_id}")
        return self._vulnerabilities[vulnerability_id]

    def _transition_vulnerability(self, vulnerability_id: str, target: VulnerabilityStatus) -> VulnerabilityRecord:
        vuln = self._get_vulnerability(vulnerability_id)
        if vuln.status in _VULNERABILITY_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"vulnerability {vulnerability_id} is in terminal state {vuln.status.value}"
            )
        now = self._now()
        updated = VulnerabilityRecord(
            vulnerability_id=vuln.vulnerability_id, tenant_id=vuln.tenant_id,
            target_runtime=vuln.target_runtime, status=target,
            severity=vuln.severity, description=vuln.description, detected_at=now,
        )
        self._vulnerabilities[vulnerability_id] = updated
        _emit(self._events, f"vulnerability_{target.value}", {"vulnerability_id": vulnerability_id}, vulnerability_id, self._clock)
        return updated

    def mitigate_vulnerability(self, vulnerability_id: str) -> VulnerabilityRecord:
        return self._transition_vulnerability(vulnerability_id, VulnerabilityStatus.MITIGATED)

    def accept_vulnerability(self, vulnerability_id: str) -> VulnerabilityRecord:
        return self._transition_vulnerability(vulnerability_id, VulnerabilityStatus.ACCEPTED)

    def mark_false_positive(self, vulnerability_id: str) -> VulnerabilityRecord:
        return self._transition_vulnerability(vulnerability_id, VulnerabilityStatus.FALSE_POSITIVE)

    # -------------------------------------------------------------------
    # Exploit paths
    # -------------------------------------------------------------------

    def record_exploit_path(
        self,
        path_id: str,
        tenant_id: str,
        scenario_ref: str,
        step_count: int = 1,
        success: bool = False,
    ) -> ExploitPath:
        if path_id in self._exploits:
            raise RuntimeCoreInvariantError(f"duplicate path_id: {path_id}")
        now = self._now()
        ep = ExploitPath(
            path_id=path_id, tenant_id=tenant_id,
            scenario_ref=scenario_ref, step_count=step_count,
            success=success, created_at=now,
        )
        self._exploits[path_id] = ep
        _emit(self._events, "record_exploit_path", {"path_id": path_id}, path_id, self._clock)
        return ep

    # -------------------------------------------------------------------
    # Defenses
    # -------------------------------------------------------------------

    def record_defense(
        self,
        defense_id: str,
        tenant_id: str,
        vulnerability_ref: str,
        disposition: DefenseDisposition = DefenseDisposition.EFFECTIVE,
        mitigation: str = "Applied mitigation",
    ) -> DefenseRecord:
        if defense_id in self._defenses:
            raise RuntimeCoreInvariantError(f"duplicate defense_id: {defense_id}")
        now = self._now()
        defense = DefenseRecord(
            defense_id=defense_id, tenant_id=tenant_id,
            vulnerability_ref=vulnerability_ref, disposition=disposition,
            mitigation=mitigation, created_at=now,
        )
        self._defenses[defense_id] = defense
        _emit(self._events, "record_defense", {"defense_id": defense_id}, defense_id, self._clock)
        return defense

    # -------------------------------------------------------------------
    # Stress tests
    # -------------------------------------------------------------------

    def record_stress_test(
        self,
        test_id: str,
        tenant_id: str,
        target_runtime: str,
        load_factor: float = 1.0,
        outcome: str = "pass",
    ) -> StressTestRecord:
        if test_id in self._stress_tests:
            raise RuntimeCoreInvariantError(f"duplicate test_id: {test_id}")
        now = self._now()
        st = StressTestRecord(
            test_id=test_id, tenant_id=tenant_id,
            target_runtime=target_runtime, load_factor=load_factor,
            outcome=outcome, created_at=now,
        )
        self._stress_tests[test_id] = st
        _emit(self._events, "record_stress_test", {"test_id": test_id}, test_id, self._clock)
        return st

    # -------------------------------------------------------------------
    # Assessment
    # -------------------------------------------------------------------

    def adversarial_assessment(self, assessment_id: str, tenant_id: str) -> AdversarialAssessment:
        now = self._now()
        t_scenarios = len([s for s in self._scenarios.values() if s.tenant_id == tenant_id])
        t_vulns = len([v for v in self._vulnerabilities.values() if v.tenant_id == tenant_id])
        mitigated = len([v for v in self._vulnerabilities.values()
                         if v.tenant_id == tenant_id and v.status == VulnerabilityStatus.MITIGATED])
        open_count = len([v for v in self._vulnerabilities.values()
                          if v.tenant_id == tenant_id and v.status == VulnerabilityStatus.OPEN])
        denom = mitigated + open_count
        rate = mitigated / denom if denom > 0 else 0.0
        assessment = AdversarialAssessment(
            assessment_id=assessment_id, tenant_id=tenant_id,
            total_scenarios=t_scenarios, total_vulnerabilities=t_vulns,
            total_mitigated=mitigated, defense_rate=round(rate, 4),
            assessed_at=now,
        )
        _emit(self._events, "adversarial_assessment", {"assessment_id": assessment_id}, assessment_id, self._clock)
        return assessment

    # -------------------------------------------------------------------
    # Snapshot
    # -------------------------------------------------------------------

    def adversarial_snapshot(self, snapshot_id: str, tenant_id: str) -> AdversarialSnapshot:
        now = self._now()
        snap = AdversarialSnapshot(
            snapshot_id=snapshot_id, tenant_id=tenant_id,
            total_scenarios=len([s for s in self._scenarios.values() if s.tenant_id == tenant_id]),
            total_vulnerabilities=len([v for v in self._vulnerabilities.values() if v.tenant_id == tenant_id]),
            total_exploits=len([e for e in self._exploits.values() if e.tenant_id == tenant_id]),
            total_defenses=len([d for d in self._defenses.values() if d.tenant_id == tenant_id]),
            total_stress_tests=len([t for t in self._stress_tests.values() if t.tenant_id == tenant_id]),
            total_violations=len([v for v in self._violations.values() if v.tenant_id == tenant_id]),
            captured_at=now,
        )
        _emit(self._events, "adversarial_snapshot", {"snapshot_id": snapshot_id}, snapshot_id, self._clock)
        return snap

    # -------------------------------------------------------------------
    # Closure report
    # -------------------------------------------------------------------

    def adversarial_closure_report(self, report_id: str, tenant_id: str) -> AdversarialClosureReport:
        now = self._now()
        report = AdversarialClosureReport(
            report_id=report_id, tenant_id=tenant_id,
            total_scenarios=len([s for s in self._scenarios.values() if s.tenant_id == tenant_id]),
            total_vulnerabilities=len([v for v in self._vulnerabilities.values() if v.tenant_id == tenant_id]),
            total_defenses=len([d for d in self._defenses.values() if d.tenant_id == tenant_id]),
            total_violations=len([v for v in self._violations.values() if v.tenant_id == tenant_id]),
            created_at=now,
        )
        _emit(self._events, "adversarial_closure_report", {"report_id": report_id}, report_id, self._clock)
        return report

    # -------------------------------------------------------------------
    # Violations
    # -------------------------------------------------------------------

    def detect_adversarial_violations(self, tenant_id: str) -> tuple[AdversarialViolation, ...]:
        new_violations: list[AdversarialViolation] = []
        now = self._now()

        # 1. Open critical vulnerability
        for v in self._vulnerabilities.values():
            if v.tenant_id != tenant_id:
                continue
            if v.status == VulnerabilityStatus.OPEN and v.severity == ExploitSeverity.CRITICAL:
                vid = stable_identifier("viol-adv", {"vulnerability_id": v.vulnerability_id, "reason": "open_critical_vulnerability"})
                if vid not in self._violations:
                    viol = AdversarialViolation(
                        violation_id=vid, tenant_id=tenant_id,
                        operation="open_critical_vulnerability",
                        reason=f"critical vulnerability {v.vulnerability_id} is still open",
                        detected_at=now,
                    )
                    self._violations[vid] = viol
                    new_violations.append(viol)

        # 2. Unmitigated exploit: successful exploit with no defense
        for ep in self._exploits.values():
            if ep.tenant_id != tenant_id:
                continue
            if ep.success:
                has_defense = any(
                    d.vulnerability_ref == ep.scenario_ref
                    for d in self._defenses.values()
                    if d.tenant_id == tenant_id and d.disposition == DefenseDisposition.EFFECTIVE
                )
                if not has_defense:
                    vid = stable_identifier("viol-adv", {"path_id": ep.path_id, "reason": "unmitigated_exploit"})
                    if vid not in self._violations:
                        viol = AdversarialViolation(
                            violation_id=vid, tenant_id=tenant_id,
                            operation="unmitigated_exploit",
                            reason=f"exploit path {ep.path_id} succeeded without effective defense",
                            detected_at=now,
                        )
                        self._violations[vid] = viol
                        new_violations.append(viol)

        # 3. Untested defense
        for d in self._defenses.values():
            if d.tenant_id != tenant_id:
                continue
            if d.disposition == DefenseDisposition.UNTESTED:
                vid = stable_identifier("viol-adv", {"defense_id": d.defense_id, "reason": "untested_defense"})
                if vid not in self._violations:
                    viol = AdversarialViolation(
                        violation_id=vid, tenant_id=tenant_id,
                        operation="untested_defense",
                        reason=f"defense {d.defense_id} is untested",
                        detected_at=now,
                    )
                    self._violations[vid] = viol
                    new_violations.append(viol)

        if new_violations:
            _emit(self._events, "detect_adversarial_violations", {
                "tenant_id": tenant_id, "count": len(new_violations),
            }, tenant_id, self._clock)
        return tuple(new_violations)

    # -------------------------------------------------------------------
    # Collections / snapshot / state_hash
    # -------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        return {
            "scenarios": self._scenarios,
            "vulnerabilities": self._vulnerabilities,
            "exploits": self._exploits,
            "defenses": self._defenses,
            "stress_tests": self._stress_tests,
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
        for k in sorted(self._scenarios):
            parts.append(f"scenario:{k}:{self._scenarios[k].status.value}")
        for k in sorted(self._vulnerabilities):
            parts.append(f"vulnerability:{k}:{self._vulnerabilities[k].status.value}")
        for k in sorted(self._exploits):
            parts.append(f"exploit:{k}:{self._exploits[k].success}")
        for k in sorted(self._defenses):
            parts.append(f"defense:{k}:{self._defenses[k].disposition.value}")
        for k in sorted(self._stress_tests):
            parts.append(f"stress_test:{k}:{self._stress_tests[k].outcome}")
        for k in sorted(self._violations):
            parts.append(f"violation:{k}")
        return sha256("|".join(parts).encode()).hexdigest()
