"""Purpose: industry pack runtime engine.
Governance scope: registering, validating, deploying, suspending, retiring
    industry packs; managing capabilities, configurations, bindings;
    assessing readiness; recording decisions; detecting violations;
    producing immutable snapshots and closure reports.
Dependencies: industry_pack contracts, event_spine, core invariants.
Invariants:
  - No duplicate pack IDs.
  - Only VALIDATED packs may be deployed.
  - RETIRED is terminal — no transitions out.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.industry_pack import (
    DeploymentDisposition,
    IndustryPack,
    IndustryPackStatus,
    PackAssessment,
    PackBinding,
    PackCapability,
    PackCapabilityKind,
    PackClosureReport,
    PackConfiguration,
    PackDecision,
    PackDeploymentRecord,
    PackDomain,
    PackReadiness,
    PackRiskLevel,
    PackSnapshot,
    PackViolation,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str = "") -> EventRecord:
    if not now:
        now = datetime.now(timezone.utc).isoformat()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-ipk", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_TERMINAL = frozenset({IndustryPackStatus.RETIRED})

# Required capability kinds per domain for validation
_REQUIRED_CAPABILITIES: dict[PackDomain, frozenset[PackCapabilityKind]] = {
    PackDomain.REGULATED_OPS: frozenset({
        PackCapabilityKind.INTAKE, PackCapabilityKind.CASE_MANAGEMENT,
        PackCapabilityKind.APPROVAL, PackCapabilityKind.EVIDENCE,
        PackCapabilityKind.REPORTING, PackCapabilityKind.DASHBOARD,
        PackCapabilityKind.COPILOT, PackCapabilityKind.GOVERNANCE,
        PackCapabilityKind.OBSERVABILITY, PackCapabilityKind.CONTINUITY,
    }),
    PackDomain.RESEARCH_LAB: frozenset({
        PackCapabilityKind.INTAKE, PackCapabilityKind.EVIDENCE,
        PackCapabilityKind.REPORTING, PackCapabilityKind.DASHBOARD,
        PackCapabilityKind.OBSERVABILITY,
    }),
    PackDomain.FACTORY_QUALITY: frozenset({
        PackCapabilityKind.INTAKE, PackCapabilityKind.CASE_MANAGEMENT,
        PackCapabilityKind.EVIDENCE, PackCapabilityKind.REPORTING,
        PackCapabilityKind.DASHBOARD, PackCapabilityKind.OBSERVABILITY,
    }),
    PackDomain.ENTERPRISE_SERVICE: frozenset({
        PackCapabilityKind.INTAKE, PackCapabilityKind.CASE_MANAGEMENT,
        PackCapabilityKind.APPROVAL, PackCapabilityKind.REPORTING,
        PackCapabilityKind.DASHBOARD, PackCapabilityKind.COPILOT,
    }),
    PackDomain.FINANCIAL_CONTROL: frozenset({
        PackCapabilityKind.INTAKE, PackCapabilityKind.APPROVAL,
        PackCapabilityKind.EVIDENCE, PackCapabilityKind.REPORTING,
        PackCapabilityKind.GOVERNANCE, PackCapabilityKind.OBSERVABILITY,
    }),
}


class IndustryPackEngine:
    """Manages industry pack lifecycle, capabilities, and deployment."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._packs: dict[str, IndustryPack] = {}
        self._capabilities: dict[str, PackCapability] = {}
        self._configurations: dict[str, PackConfiguration] = {}
        self._bindings: dict[str, PackBinding] = {}
        self._assessments: dict[str, PackAssessment] = {}
        self._decisions: dict[str, PackDecision] = {}
        self._deployments: dict[str, PackDeploymentRecord] = {}
        self._violations: dict[str, PackViolation] = {}
        self._snapshot_ids: set[str] = set()

    def _now(self) -> str:
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def pack_count(self) -> int:
        return len(self._packs)

    @property
    def capability_count(self) -> int:
        return len(self._capabilities)

    @property
    def config_count(self) -> int:
        return len(self._configurations)

    @property
    def binding_count(self) -> int:
        return len(self._bindings)

    @property
    def deployment_count(self) -> int:
        return len(self._deployments)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Pack lifecycle
    # ------------------------------------------------------------------

    def register_pack(
        self,
        pack_id: str,
        tenant_id: str,
        display_name: str,
        domain: PackDomain,
    ) -> IndustryPack:
        """Register a new industry pack in DRAFT status."""
        if pack_id in self._packs:
            raise RuntimeCoreInvariantError("Duplicate pack_id")
        now = self._now()
        pack = IndustryPack(
            pack_id=pack_id,
            tenant_id=tenant_id,
            display_name=display_name,
            domain=domain,
            status=IndustryPackStatus.DRAFT,
            capability_count=0,
            created_at=now,
        )
        self._packs[pack_id] = pack
        _emit(self._events, "register_pack", {"pack_id": pack_id, "tenant_id": tenant_id}, pack_id, now)
        return pack

    def get_pack(self, pack_id: str) -> IndustryPack:
        """Retrieve a pack by ID."""
        if pack_id not in self._packs:
            raise RuntimeCoreInvariantError("Unknown pack_id")
        return self._packs[pack_id]

    def packs_for_tenant(self, tenant_id: str) -> list[IndustryPack]:
        """Return all packs for a tenant."""
        return [p for p in self._packs.values() if p.tenant_id == tenant_id]

    def _replace_pack(self, pack_id: str, **overrides: Any) -> IndustryPack:
        """Replace a pack with updated fields."""
        old = self.get_pack(pack_id)
        d = old.to_dict()
        d.update(overrides)
        # Restore enum types from dict values
        if "domain" in d and not isinstance(d["domain"], PackDomain):
            d["domain"] = PackDomain(d["domain"])
        if "status" in d and not isinstance(d["status"], IndustryPackStatus):
            d["status"] = IndustryPackStatus(d["status"])
        new_pack = IndustryPack(**d)
        self._packs[pack_id] = new_pack
        return new_pack

    def validate_pack(self, pack_id: str) -> IndustryPack:
        """Validate a DRAFT pack. Transitions to VALIDATED if all required capabilities are present and enabled."""
        pack = self.get_pack(pack_id)
        if pack.status != IndustryPackStatus.DRAFT:
            raise RuntimeCoreInvariantError("Only DRAFT packs can be validated")
        now = self._now()
        # Check required capabilities for this domain
        required = _REQUIRED_CAPABILITIES.get(pack.domain, frozenset())
        caps = [c for c in self._capabilities.values() if c.pack_ref == pack_id]
        enabled_kinds = frozenset(c.kind for c in caps if c.enabled)
        if required and required.issubset(enabled_kinds):
            new_pack = self._replace_pack(pack_id, status=IndustryPackStatus.VALIDATED)
        else:
            new_pack = pack  # stays DRAFT
        _emit(self._events, "validate_pack", {
            "pack_id": pack_id, "result": new_pack.status.value,
        }, pack_id, now)
        return new_pack

    def deploy_pack(self, pack_id: str) -> IndustryPack:
        """Deploy a VALIDATED pack."""
        pack = self.get_pack(pack_id)
        if pack.status != IndustryPackStatus.VALIDATED:
            raise RuntimeCoreInvariantError("Only VALIDATED packs can be deployed")
        now = self._now()
        new_pack = self._replace_pack(pack_id, status=IndustryPackStatus.DEPLOYED)
        dep_id = stable_identifier("dep-ipk", {"pack_id": pack_id, "ts": now})
        deployment = PackDeploymentRecord(
            deployment_id=dep_id,
            tenant_id=pack.tenant_id,
            pack_ref=pack_id,
            disposition=DeploymentDisposition.APPROVED,
            deployed_at=now,
        )
        self._deployments[dep_id] = deployment
        _emit(self._events, "deploy_pack", {"pack_id": pack_id}, pack_id, now)
        return new_pack

    def suspend_pack(self, pack_id: str) -> IndustryPack:
        """Suspend a pack."""
        pack = self.get_pack(pack_id)
        if pack.status in _TERMINAL:
            raise RuntimeCoreInvariantError("Cannot suspend pack in current status")
        now = self._now()
        new_pack = self._replace_pack(pack_id, status=IndustryPackStatus.SUSPENDED)
        _emit(self._events, "suspend_pack", {"pack_id": pack_id}, pack_id, now)
        return new_pack

    def retire_pack(self, pack_id: str) -> IndustryPack:
        """Retire a pack (terminal state)."""
        pack = self.get_pack(pack_id)
        if pack.status in _TERMINAL:
            raise RuntimeCoreInvariantError("Cannot retire pack in current status")
        now = self._now()
        new_pack = self._replace_pack(pack_id, status=IndustryPackStatus.RETIRED)
        _emit(self._events, "retire_pack", {"pack_id": pack_id}, pack_id, now)
        return new_pack

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    def add_capability(
        self,
        capability_id: str,
        tenant_id: str,
        pack_ref: str,
        kind: PackCapabilityKind,
        target_runtime: str,
        enabled: bool = True,
    ) -> PackCapability:
        """Add a capability to a pack."""
        if capability_id in self._capabilities:
            raise RuntimeCoreInvariantError("Duplicate capability_id")
        if pack_ref not in self._packs:
            raise RuntimeCoreInvariantError("Unknown pack_ref")
        now = self._now()
        cap = PackCapability(
            capability_id=capability_id,
            tenant_id=tenant_id,
            pack_ref=pack_ref,
            kind=kind,
            target_runtime=target_runtime,
            enabled=enabled,
            created_at=now,
        )
        self._capabilities[capability_id] = cap
        # Increment capability_count on the pack
        pack = self._packs[pack_ref]
        self._replace_pack(pack_ref, capability_count=pack.capability_count + 1)
        _emit(self._events, "add_capability", {
            "capability_id": capability_id, "pack_ref": pack_ref,
        }, capability_id, now)
        return cap

    # ------------------------------------------------------------------
    # Configurations
    # ------------------------------------------------------------------

    def add_configuration(
        self,
        config_id: str,
        tenant_id: str,
        pack_ref: str,
        key: str,
        value: str,
    ) -> PackConfiguration:
        """Add a configuration entry to a pack."""
        if config_id in self._configurations:
            raise RuntimeCoreInvariantError("Duplicate config_id")
        if pack_ref not in self._packs:
            raise RuntimeCoreInvariantError("Unknown pack_ref")
        now = self._now()
        cfg = PackConfiguration(
            config_id=config_id,
            tenant_id=tenant_id,
            pack_ref=pack_ref,
            key=key,
            value=value,
            created_at=now,
        )
        self._configurations[config_id] = cfg
        _emit(self._events, "add_configuration", {
            "config_id": config_id, "pack_ref": pack_ref,
        }, config_id, now)
        return cfg

    # ------------------------------------------------------------------
    # Bindings
    # ------------------------------------------------------------------

    def add_binding(
        self,
        binding_id: str,
        tenant_id: str,
        pack_ref: str,
        runtime_ref: str,
        binding_type: str,
    ) -> PackBinding:
        """Bind a pack to a runtime component."""
        if binding_id in self._bindings:
            raise RuntimeCoreInvariantError("Duplicate binding_id")
        if pack_ref not in self._packs:
            raise RuntimeCoreInvariantError("Unknown pack_ref")
        now = self._now()
        binding = PackBinding(
            binding_id=binding_id,
            tenant_id=tenant_id,
            pack_ref=pack_ref,
            runtime_ref=runtime_ref,
            binding_type=binding_type,
            created_at=now,
        )
        self._bindings[binding_id] = binding
        _emit(self._events, "add_binding", {
            "binding_id": binding_id, "pack_ref": pack_ref,
        }, binding_id, now)
        return binding

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def assess_pack(
        self,
        assessment_id: str,
        tenant_id: str,
        pack_ref: str,
    ) -> PackAssessment:
        """Assess the readiness of a pack."""
        if assessment_id in self._assessments:
            raise RuntimeCoreInvariantError("Duplicate assessment_id")
        if pack_ref not in self._packs:
            raise RuntimeCoreInvariantError("Unknown pack_ref")
        now = self._now()
        caps = [c for c in self._capabilities.values() if c.pack_ref == pack_ref]
        total = len(caps)
        enabled = sum(1 for c in caps if c.enabled)
        score = enabled / total if total > 0 else 1.0
        if score >= 1.0:
            readiness = PackReadiness.READY
        elif score >= 0.5:
            readiness = PackReadiness.PARTIAL
        else:
            readiness = PackReadiness.NOT_READY
        assessment = PackAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            pack_ref=pack_ref,
            readiness=readiness,
            total_capabilities=total,
            enabled_capabilities=enabled,
            readiness_score=score,
            assessed_at=now,
        )
        self._assessments[assessment_id] = assessment
        _emit(self._events, "assess_pack", {
            "assessment_id": assessment_id, "pack_ref": pack_ref,
        }, assessment_id, now)
        return assessment

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    def record_decision(
        self,
        decision_id: str,
        tenant_id: str,
        pack_ref: str,
        disposition: DeploymentDisposition,
        reason: str,
    ) -> PackDecision:
        """Record a deployment decision."""
        if decision_id in self._decisions:
            raise RuntimeCoreInvariantError("Duplicate decision_id")
        now = self._now()
        decision = PackDecision(
            decision_id=decision_id,
            tenant_id=tenant_id,
            pack_ref=pack_ref,
            disposition=disposition,
            reason=reason,
            decided_at=now,
        )
        self._decisions[decision_id] = decision
        _emit(self._events, "record_decision", {
            "decision_id": decision_id, "pack_ref": pack_ref,
        }, decision_id, now)
        return decision

    # ------------------------------------------------------------------
    # Bootstrap: Regulated Operations Control Tower
    # ------------------------------------------------------------------

    def bootstrap_regulated_ops_pack(
        self,
        pack_id: str,
        tenant_id: str,
    ) -> dict[str, Any]:
        """Create a complete Regulated Operations Control Tower pack with 10 capabilities."""
        pack = self.register_pack(pack_id, tenant_id, "Regulated Operations Control Tower", PackDomain.REGULATED_OPS)
        kinds = list(PackCapabilityKind)  # All 10 kinds
        for i, kind in enumerate(kinds):
            self.add_capability(
                capability_id=f"{pack_id}-cap-{kind.value}",
                tenant_id=tenant_id,
                pack_ref=pack_id,
                kind=kind,
                target_runtime=f"rt-{kind.value}",
                enabled=True,
            )
        updated_pack = self.get_pack(pack_id)
        return {
            "pack_id": updated_pack.pack_id,
            "domain": updated_pack.domain.value,
            "capability_count": updated_pack.capability_count,
            "status": updated_pack.status.value,
        }

    # ------------------------------------------------------------------
    # Snapshot & Closure
    # ------------------------------------------------------------------

    def pack_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> PackSnapshot:
        """Produce a point-in-time snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError("Duplicate snapshot_id")
        now = self._now()
        snap = PackSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_packs=self.pack_count,
            total_capabilities=self.capability_count,
            total_bindings=self.binding_count,
            total_configs=self.config_count,
            total_violations=self.violation_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "pack_snapshot", {"snapshot_id": snapshot_id}, snapshot_id, now)
        return snap

    def pack_closure_report(
        self,
        report_id: str,
        tenant_id: str,
    ) -> PackClosureReport:
        """Produce a closure report."""
        now = self._now()
        report = PackClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_packs=self.pack_count,
            total_deployments=self.deployment_count,
            total_violations=self.violation_count,
            created_at=now,
        )
        _emit(self._events, "pack_closure_report", {"report_id": report_id}, report_id, now)
        return report

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_pack_violations(self, tenant_id: str) -> list[PackViolation]:
        """Detect and record violations. Idempotent — skips already-detected violations."""
        now = self._now()
        new_violations: list[PackViolation] = []
        existing_violation_ids = set(self._violations)

        # 1. pack_not_validated: DEPLOYED but never VALIDATED path
        #    We check packs that are DEPLOYED but have no deployment record referencing them
        #    Actually: packs that are DEPLOYED but were never assessed as READY
        for pack in self._packs.values():
            if pack.tenant_id != tenant_id:
                continue
            if pack.status == IndustryPackStatus.DEPLOYED:
                # Check if there's an assessment showing READY
                assessed = any(
                    a.pack_ref == pack.pack_id and a.readiness == PackReadiness.READY
                    for a in self._assessments.values()
                )
                if not assessed:
                    vid = stable_identifier(
                        "viol-ipk",
                        {"t": tenant_id, "op": "pack_not_validated", "p": pack.pack_id},
                    )
                    if vid not in existing_violation_ids:
                        v = PackViolation(
                            violation_id=vid,
                            tenant_id=tenant_id,
                            operation="pack_not_validated",
                            reason="deployed pack has no ready assessment",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)
                        existing_violation_ids.add(vid)

        # 2. missing_required_capability: pack domain requires certain capabilities
        for pack in self._packs.values():
            if pack.tenant_id != tenant_id:
                continue
            required = _REQUIRED_CAPABILITIES.get(pack.domain, frozenset())
            if not required:
                continue
            caps = [c for c in self._capabilities.values() if c.pack_ref == pack.pack_id]
            present_kinds = frozenset(c.kind for c in caps)
            missing = required - present_kinds
            for kind in sorted(missing, key=lambda k: k.value):
                vid = stable_identifier(
                    "viol-ipk",
                    {"t": tenant_id, "op": "missing_cap", "p": pack.pack_id, "k": kind.value},
                )
                if vid not in existing_violation_ids:
                    v = PackViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="missing_required_capability",
                        reason="pack is missing required capability",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)
                    existing_violation_ids.add(vid)

        # 3. binding_orphan: binding references non-existent runtime
        #    We treat any binding whose runtime_ref doesn't match a pack_id as orphan
        known_runtimes = set(self._packs.keys())
        for binding in self._bindings.values():
            if binding.tenant_id != tenant_id:
                continue
            if binding.runtime_ref not in known_runtimes:
                vid = stable_identifier(
                    "viol-ipk",
                    {"t": tenant_id, "op": "binding_orphan", "b": binding.binding_id},
                )
                if vid not in existing_violation_ids:
                    v = PackViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="binding_orphan",
                        reason="binding references unknown runtime",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)
                    existing_violation_ids.add(vid)

        if new_violations:
            _emit(self._events, "detect_pack_violations", {
                "tenant_id": tenant_id, "count": len(new_violations),
            }, tenant_id, now)
        return new_violations

    # ------------------------------------------------------------------
    # State hash / Snapshot / Collections
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute SHA-256 hash of engine state with sorted keys."""
        parts = sorted([
            f"bindings={self.binding_count}",
            f"capabilities={self.capability_count}",
            f"configs={self.config_count}",
            f"decisions={self.decision_count}",
            f"deployments={self.deployment_count}",
            f"packs={self.pack_count}",
            f"violations={self.violation_count}",
        ])
        return sha256("|".join(parts).encode()).hexdigest()

    def _collections(self) -> dict[str, Any]:
        return {
            "packs": self._packs,
            "capabilities": self._capabilities,
            "configurations": self._configurations,
            "bindings": self._bindings,
            "assessments": self._assessments,
            "decisions": self._decisions,
            "deployments": self._deployments,
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
