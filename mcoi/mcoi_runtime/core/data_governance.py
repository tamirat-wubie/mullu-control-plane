"""Purpose: data governance / privacy / residency runtime engine.
Governance scope: classifying data; binding handling policies by scope;
    enforcing residency and privacy rules; producing redaction decisions;
    gating storage, connector transfer, and memory attachment; detecting
    violations; exposing immutable snapshots and state hash.
Dependencies: data_governance contracts, event_spine, core invariants.
Invariants:
  - Governance is fail-closed: default decision is DENY.
  - RESTRICTED/SECRET data cannot leave tenant without explicit ALLOW policy.
  - Residency constraints are checked before any transfer.
  - Privacy rules enforce basis requirements.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.data_governance import (
    DataClassification,
    DataClosureReport,
    DataGovernanceSnapshot,
    DataPolicy,
    DataRecord,
    DataViolation,
    GovernanceDecision,
    HandlingDecision,
    HandlingDisposition,
    PrivacyBasis,
    PrivacyRule,
    RedactionLevel,
    RedactionRule,
    ResidencyConstraint,
    ResidencyRegion,
    RetentionDisposition,
    RetentionRule,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-dgov", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


# Classification severity for comparison
_CLASSIFICATION_ORDER = [
    DataClassification.PUBLIC,
    DataClassification.INTERNAL,
    DataClassification.CONFIDENTIAL,
    DataClassification.SENSITIVE,
    DataClassification.PII,
    DataClassification.RESTRICTED,
    DataClassification.SECRET,
]


def _classification_level(c: DataClassification) -> int:
    return _CLASSIFICATION_ORDER.index(c)


class DataGovernanceEngine:
    """Data governance, privacy, and residency engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._records: dict[str, DataRecord] = {}
        self._policies: dict[str, DataPolicy] = {}
        self._residency_constraints: dict[str, ResidencyConstraint] = {}
        self._privacy_rules: dict[str, PrivacyRule] = {}
        self._redaction_rules: dict[str, RedactionRule] = {}
        self._retention_rules: dict[str, RetentionRule] = {}
        self._decisions: dict[str, HandlingDecision] = {}
        self._violations: dict[str, DataViolation] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def record_count(self) -> int:
        return len(self._records)

    @property
    def policy_count(self) -> int:
        return len(self._policies)

    @property
    def residency_constraint_count(self) -> int:
        return len(self._residency_constraints)

    @property
    def privacy_rule_count(self) -> int:
        return len(self._privacy_rules)

    @property
    def redaction_rule_count(self) -> int:
        return len(self._redaction_rules)

    @property
    def retention_rule_count(self) -> int:
        return len(self._retention_rules)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Data classification
    # ------------------------------------------------------------------

    def classify_data(
        self,
        data_id: str,
        tenant_id: str,
        *,
        classification: DataClassification = DataClassification.INTERNAL,
        residency: ResidencyRegion = ResidencyRegion.GLOBAL,
        privacy_basis: PrivacyBasis = PrivacyBasis.LEGITIMATE_INTEREST,
        domain: str = "",
        source_id: str = "",
    ) -> DataRecord:
        """Classify and register a data record."""
        if data_id in self._records:
            raise RuntimeCoreInvariantError(f"Duplicate data_id: {data_id}")
        now = _now_iso()
        record = DataRecord(
            data_id=data_id,
            tenant_id=tenant_id,
            classification=classification,
            residency=residency,
            privacy_basis=privacy_basis,
            domain=domain,
            source_id=source_id,
            created_at=now,
        )
        self._records[data_id] = record
        _emit(self._events, "data_classified", {
            "data_id": data_id, "classification": classification.value,
        }, data_id)
        return record

    def get_record(self, data_id: str) -> DataRecord:
        """Get a data record by ID."""
        r = self._records.get(data_id)
        if r is None:
            raise RuntimeCoreInvariantError(f"Unknown data_id: {data_id}")
        return r

    def records_for_tenant(self, tenant_id: str) -> tuple[DataRecord, ...]:
        """Return all data records for a tenant."""
        return tuple(r for r in self._records.values() if r.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Policy management
    # ------------------------------------------------------------------

    def register_policy(
        self,
        policy_id: str,
        tenant_id: str,
        *,
        classification: DataClassification = DataClassification.INTERNAL,
        disposition: HandlingDisposition = HandlingDisposition.DENY,
        residency: ResidencyRegion = ResidencyRegion.GLOBAL,
        scope_ref_id: str = "",
        description: str = "",
    ) -> DataPolicy:
        """Register a data handling policy."""
        if policy_id in self._policies:
            raise RuntimeCoreInvariantError(f"Duplicate policy_id: {policy_id}")
        now = _now_iso()
        policy = DataPolicy(
            policy_id=policy_id,
            tenant_id=tenant_id,
            classification=classification,
            disposition=disposition,
            residency=residency,
            scope_ref_id=scope_ref_id,
            description=description,
            created_at=now,
        )
        self._policies[policy_id] = policy
        _emit(self._events, "policy_registered", {
            "policy_id": policy_id, "disposition": disposition.value,
        }, policy_id)
        return policy

    def register_residency_constraint(
        self,
        constraint_id: str,
        tenant_id: str,
        *,
        allowed_regions: list[str] | None = None,
        denied_regions: list[str] | None = None,
    ) -> ResidencyConstraint:
        """Register a residency constraint."""
        if constraint_id in self._residency_constraints:
            raise RuntimeCoreInvariantError(f"Duplicate constraint_id: {constraint_id}")
        now = _now_iso()
        constraint = ResidencyConstraint(
            constraint_id=constraint_id,
            tenant_id=tenant_id,
            allowed_regions=tuple(allowed_regions or []),
            denied_regions=tuple(denied_regions or []),
            created_at=now,
        )
        self._residency_constraints[constraint_id] = constraint
        _emit(self._events, "residency_constraint_registered", {
            "constraint_id": constraint_id,
        }, constraint_id)
        return constraint

    def register_privacy_rule(
        self,
        rule_id: str,
        tenant_id: str,
        *,
        classification: DataClassification = DataClassification.PII,
        required_basis: PrivacyBasis = PrivacyBasis.CONSENT,
        scope_ref_id: str = "",
        description: str = "",
    ) -> PrivacyRule:
        """Register a privacy rule."""
        if rule_id in self._privacy_rules:
            raise RuntimeCoreInvariantError(f"Duplicate privacy rule_id: {rule_id}")
        now = _now_iso()
        rule = PrivacyRule(
            rule_id=rule_id,
            tenant_id=tenant_id,
            classification=classification,
            required_basis=required_basis,
            scope_ref_id=scope_ref_id,
            description=description,
            created_at=now,
        )
        self._privacy_rules[rule_id] = rule
        _emit(self._events, "privacy_rule_registered", {
            "rule_id": rule_id,
        }, rule_id)
        return rule

    def register_redaction_rule(
        self,
        rule_id: str,
        tenant_id: str,
        *,
        classification: DataClassification = DataClassification.SENSITIVE,
        redaction_level: RedactionLevel = RedactionLevel.FULL,
        scope_ref_id: str = "",
        field_patterns: list[str] | None = None,
    ) -> RedactionRule:
        """Register a redaction rule."""
        if rule_id in self._redaction_rules:
            raise RuntimeCoreInvariantError(f"Duplicate redaction rule_id: {rule_id}")
        now = _now_iso()
        rule = RedactionRule(
            rule_id=rule_id,
            tenant_id=tenant_id,
            classification=classification,
            redaction_level=redaction_level,
            scope_ref_id=scope_ref_id,
            field_patterns=tuple(field_patterns or []),
            created_at=now,
        )
        self._redaction_rules[rule_id] = rule
        _emit(self._events, "redaction_rule_registered", {
            "rule_id": rule_id,
        }, rule_id)
        return rule

    def register_retention_rule(
        self,
        rule_id: str,
        tenant_id: str,
        *,
        classification: DataClassification = DataClassification.INTERNAL,
        retention_days: int = 365,
        disposition: RetentionDisposition = RetentionDisposition.DELETE,
        scope_ref_id: str = "",
    ) -> RetentionRule:
        """Register a retention rule."""
        if rule_id in self._retention_rules:
            raise RuntimeCoreInvariantError(f"Duplicate retention rule_id: {rule_id}")
        now = _now_iso()
        rule = RetentionRule(
            rule_id=rule_id,
            tenant_id=tenant_id,
            classification=classification,
            retention_days=retention_days,
            disposition=disposition,
            scope_ref_id=scope_ref_id,
            created_at=now,
        )
        self._retention_rules[rule_id] = rule
        _emit(self._events, "retention_rule_registered", {
            "rule_id": rule_id,
        }, rule_id)
        return rule

    # ------------------------------------------------------------------
    # Handling evaluation
    # ------------------------------------------------------------------

    def _find_matching_policy(
        self, tenant_id: str, classification: DataClassification,
    ) -> DataPolicy | None:
        """Find the most specific matching policy.

        For RESTRICTED/SECRET data, require the policy classification to be
        at least RESTRICTED level — lower policies do not cover high-sensitivity
        data (fail-closed).
        """
        restricted_level = _classification_level(DataClassification.RESTRICTED)
        data_level = _classification_level(classification)
        matches = [
            p for p in self._policies.values()
            if p.tenant_id == tenant_id
            and _classification_level(p.classification) <= data_level
        ]
        if data_level >= restricted_level:
            # For high-sensitivity data, only policies at RESTRICTED+ level apply
            matches = [
                p for p in matches
                if _classification_level(p.classification) >= restricted_level
            ]
        if not matches:
            return None
        # Return the policy matching the highest classification level
        return max(matches, key=lambda p: _classification_level(p.classification))

    def _check_residency(
        self, tenant_id: str, target_region: ResidencyRegion,
    ) -> bool:
        """Check if a target region is allowed by residency constraints."""
        constraints = [
            c for c in self._residency_constraints.values()
            if c.tenant_id == tenant_id
        ]
        if not constraints:
            return True  # No constraints = allowed
        for c in constraints:
            if c.denied_regions and target_region.value in c.denied_regions:
                return False
            if c.allowed_regions and target_region.value not in c.allowed_regions:
                return False
        return True

    def _check_privacy(
        self, tenant_id: str, classification: DataClassification,
        privacy_basis: PrivacyBasis,
    ) -> PrivacyRule | None:
        """Check if privacy rules are satisfied. Returns violating rule or None."""
        for rule in self._privacy_rules.values():
            if rule.tenant_id != tenant_id:
                continue
            if _classification_level(rule.classification) > _classification_level(classification):
                continue
            if rule.required_basis != privacy_basis:
                return rule  # Privacy basis mismatch
        return None

    def _find_redaction_level(
        self, tenant_id: str, classification: DataClassification,
    ) -> RedactionLevel:
        """Find the redaction level for a classification."""
        matches = [
            r for r in self._redaction_rules.values()
            if r.tenant_id == tenant_id
            and _classification_level(r.classification) <= _classification_level(classification)
        ]
        if not matches:
            return RedactionLevel.NONE
        # Use the highest redaction level
        level_order = [
            RedactionLevel.NONE, RedactionLevel.PARTIAL,
            RedactionLevel.HASH, RedactionLevel.TOKENIZE, RedactionLevel.FULL,
        ]
        return max(
            (r.redaction_level for r in matches),
            key=lambda rl: level_order.index(rl),
        )

    def _make_decision(
        self,
        data_id: str,
        tenant_id: str,
        operation: str,
        decision: GovernanceDecision,
        disposition: HandlingDisposition,
        redaction_level: RedactionLevel,
        reason: str,
    ) -> HandlingDecision:
        now = _now_iso()
        did = stable_identifier("gdec", {
            "data": data_id, "op": operation, "ts": now,
        })
        dec = HandlingDecision(
            decision_id=did,
            data_id=data_id,
            tenant_id=tenant_id,
            operation=operation,
            decision=decision,
            disposition=disposition,
            redaction_level=redaction_level,
            reason=reason,
            decided_at=now,
        )
        self._decisions[did] = dec
        return dec

    def evaluate_handling(
        self,
        data_id: str,
        operation: str,
        *,
        target_region: ResidencyRegion | None = None,
    ) -> HandlingDecision:
        """Evaluate data handling. Fail-closed: default is DENY."""
        record = self._records.get(data_id)
        if record is None:
            raise RuntimeCoreInvariantError(f"Unknown data_id: {data_id}")

        tenant_id = record.tenant_id
        classification = record.classification

        # Check privacy rules
        violating_rule = self._check_privacy(
            tenant_id, classification, record.privacy_basis,
        )
        if violating_rule is not None:
            dec = self._make_decision(
                data_id, tenant_id, operation,
                GovernanceDecision.DENIED, HandlingDisposition.DENY,
                RedactionLevel.NONE,
                f"privacy basis mismatch: requires {violating_rule.required_basis.value}",
            )
            _emit(self._events, "handling_denied_privacy", {
                "data_id": data_id, "operation": operation,
            }, data_id)
            return dec

        # Check residency
        effective_region = target_region or record.residency
        if not self._check_residency(tenant_id, effective_region):
            dec = self._make_decision(
                data_id, tenant_id, operation,
                GovernanceDecision.DENIED, HandlingDisposition.DENY,
                RedactionLevel.NONE,
                f"residency constraint: {effective_region.value} not allowed",
            )
            _emit(self._events, "handling_denied_residency", {
                "data_id": data_id, "region": effective_region.value,
            }, data_id)
            return dec

        # Find matching policy
        policy = self._find_matching_policy(tenant_id, classification)

        # No policy for high-sensitivity data → DENY (fail-closed)
        if policy is None and _classification_level(classification) >= _classification_level(
            DataClassification.RESTRICTED
        ):
            dec = self._make_decision(
                data_id, tenant_id, operation,
                GovernanceDecision.DENIED, HandlingDisposition.DENY,
                RedactionLevel.NONE,
                "no policy for restricted/secret data",
            )
            _emit(self._events, "handling_denied_no_policy", {
                "data_id": data_id, "classification": classification.value,
            }, data_id)
            return dec

        # Determine redaction level
        redaction = self._find_redaction_level(tenant_id, classification)

        # Apply policy disposition
        if policy is not None:
            if policy.disposition == HandlingDisposition.DENY:
                dec = self._make_decision(
                    data_id, tenant_id, operation,
                    GovernanceDecision.DENIED, HandlingDisposition.DENY,
                    RedactionLevel.NONE, "policy denies operation",
                )
                _emit(self._events, "handling_denied_policy", {
                    "data_id": data_id,
                }, data_id)
                return dec
            elif policy.disposition == HandlingDisposition.REDACT:
                effective_redaction = redaction if redaction != RedactionLevel.NONE else RedactionLevel.FULL
                dec = self._make_decision(
                    data_id, tenant_id, operation,
                    GovernanceDecision.REDACTED, HandlingDisposition.REDACT,
                    effective_redaction, "policy requires redaction",
                )
                _emit(self._events, "handling_redacted", {
                    "data_id": data_id, "level": effective_redaction.value,
                }, data_id)
                return dec
            elif policy.disposition == HandlingDisposition.AUDIT_ONLY:
                dec = self._make_decision(
                    data_id, tenant_id, operation,
                    GovernanceDecision.ALLOWED, HandlingDisposition.AUDIT_ONLY,
                    redaction, "allowed with audit",
                )
                _emit(self._events, "handling_audit_only", {
                    "data_id": data_id,
                }, data_id)
                return dec
            elif policy.disposition == HandlingDisposition.ENCRYPT:
                dec = self._make_decision(
                    data_id, tenant_id, operation,
                    GovernanceDecision.ALLOWED, HandlingDisposition.ENCRYPT,
                    redaction, "allowed with encryption",
                )
                _emit(self._events, "handling_encrypted", {
                    "data_id": data_id,
                }, data_id)
                return dec
            else:  # ALLOW
                dec = self._make_decision(
                    data_id, tenant_id, operation,
                    GovernanceDecision.ALLOWED, HandlingDisposition.ALLOW,
                    redaction, "allowed by policy",
                )
                _emit(self._events, "handling_allowed", {
                    "data_id": data_id,
                }, data_id)
                return dec

        # No policy, low classification → ALLOW with redaction if applicable
        if redaction != RedactionLevel.NONE:
            dec = self._make_decision(
                data_id, tenant_id, operation,
                GovernanceDecision.REDACTED, HandlingDisposition.REDACT,
                redaction, "redaction rule applied",
            )
            _emit(self._events, "handling_redacted_default", {
                "data_id": data_id,
            }, data_id)
            return dec

        dec = self._make_decision(
            data_id, tenant_id, operation,
            GovernanceDecision.ALLOWED, HandlingDisposition.ALLOW,
            RedactionLevel.NONE, "allowed by default",
        )
        _emit(self._events, "handling_allowed_default", {
            "data_id": data_id,
        }, data_id)
        return dec

    def evaluate_connector_transfer(
        self,
        data_id: str,
        connector_region: ResidencyRegion,
    ) -> HandlingDecision:
        """Evaluate whether data may be transferred to a connector region."""
        return self.evaluate_handling(
            data_id, "connector_transfer", target_region=connector_region,
        )

    def evaluate_memory_storage(
        self,
        data_id: str,
    ) -> HandlingDecision:
        """Evaluate whether data may be stored in memory mesh."""
        return self.evaluate_handling(data_id, "memory_storage")

    def evaluate_artifact_storage(
        self,
        data_id: str,
    ) -> HandlingDecision:
        """Evaluate whether data may be stored as an artifact."""
        return self.evaluate_handling(data_id, "artifact_storage")

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_violations(self) -> tuple[DataViolation, ...]:
        """Detect governance violations from decision history."""
        now = _now_iso()
        new_violations: list[DataViolation] = []

        for dec in self._decisions.values():
            if dec.decision != GovernanceDecision.DENIED:
                continue
            vid = stable_identifier("viol-dgov", {"dec": dec.decision_id})
            if vid in self._violations:
                continue
            record = self._records.get(dec.data_id)
            classification = record.classification if record else DataClassification.INTERNAL
            violation = DataViolation(
                violation_id=vid,
                data_id=dec.data_id,
                tenant_id=dec.tenant_id,
                operation=dec.operation,
                reason=dec.reason,
                classification=classification,
                detected_at=now,
            )
            self._violations[vid] = violation
            new_violations.append(violation)

        if new_violations:
            _emit(self._events, "data_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    def violations_for_tenant(self, tenant_id: str) -> tuple[DataViolation, ...]:
        """Return all violations for a tenant."""
        return tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def governance_snapshot(
        self,
        snapshot_id: str,
        scope_ref_id: str = "",
    ) -> DataGovernanceSnapshot:
        """Capture a point-in-time governance snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError(f"Duplicate snapshot_id: {snapshot_id}")
        now = _now_iso()
        snapshot = DataGovernanceSnapshot(
            snapshot_id=snapshot_id,
            scope_ref_id=scope_ref_id,
            total_records=self.record_count,
            total_policies=self.policy_count,
            total_residency_constraints=self.residency_constraint_count,
            total_privacy_rules=self.privacy_rule_count,
            total_redaction_rules=self.redaction_rule_count,
            total_retention_rules=self.retention_rule_count,
            total_decisions=self.decision_count,
            total_violations=self.violation_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "governance_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id)
        return snapshot

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"records={self.record_count}",
            f"policies={self.policy_count}",
            f"residency={self.residency_constraint_count}",
            f"privacy={self.privacy_rule_count}",
            f"redaction={self.redaction_rule_count}",
            f"retention={self.retention_rule_count}",
            f"decisions={self.decision_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
