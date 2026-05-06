"""Gateway connector certification registry.

Purpose: certify external connectors before production use.
Governance scope: connector manifests, side-effect classification, OAuth scope
    bounds, idempotency, approval requirements, receipt requirements, maturity
    evidence, eval coverage, revocation, and production promotion decisions.
Dependencies: dataclasses, enum, typing, and command-spine canonical hashing.
Invariants:
  - Write-capable connectors require approval, idempotency, and receipts.
  - Production certification requires live evidence and eval coverage.
  - Requested OAuth scopes must be a subset of the connector manifest.
  - Revoked connectors fail closed regardless of evidence level.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from typing import Any, Iterable

from gateway.command_spine import canonical_hash


class ConnectorCertificationLevel(StrEnum):
    """Connector certification maturity ladder."""

    L0_CONTRACT_DEFINED = "L0_contract_defined"
    L1_MOCK_TESTED = "L1_mock_tested"
    L2_SANDBOX_TESTED = "L2_sandbox_tested"
    L3_LIVE_READ_ONLY_TESTED = "L3_live_read_only_tested"
    L4_LIVE_WRITE_TESTED = "L4_live_write_tested"
    L5_PRODUCTION_CERTIFIED = "L5_production_certified"


class ConnectorRisk(StrEnum):
    """Connector risk tier."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConnectorCertificationVerdict(StrEnum):
    """Certification admission verdict."""

    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"


_LEVEL_ORDER = {
    ConnectorCertificationLevel.L0_CONTRACT_DEFINED: 0,
    ConnectorCertificationLevel.L1_MOCK_TESTED: 1,
    ConnectorCertificationLevel.L2_SANDBOX_TESTED: 2,
    ConnectorCertificationLevel.L3_LIVE_READ_ONLY_TESTED: 3,
    ConnectorCertificationLevel.L4_LIVE_WRITE_TESTED: 4,
    ConnectorCertificationLevel.L5_PRODUCTION_CERTIFIED: 5,
}
_WRITE_SIDE_EFFECTS = frozenset({
    "external_message_send",
    "financial_record_create",
    "financial_record_update",
    "payment_dispatch",
    "external_write",
    "ticket_update",
})
_PRODUCTION_REQUIRED_EVIDENCE = frozenset({
    "mock_test",
    "sandbox_receipt",
    "live_receipt",
    "deployment_witness",
})
_PRODUCTION_REQUIRED_EVALS = frozenset({
    "tenant_isolation",
    "approval_required",
})


@dataclass(frozen=True, slots=True)
class ConnectorManifest:
    """Governed manifest for one external connector action."""

    connector_id: str
    provider: str
    action: str
    version: str
    risk: ConnectorRisk
    side_effects: tuple[str, ...]
    oauth_scopes: tuple[str, ...]
    requires_approval: bool
    requires_receipt: bool
    requires_idempotency: bool
    requires_tenant_binding: bool
    eval_suites: tuple[str, ...]
    evidence_required: tuple[str, ...]
    owner_team: str
    manifest_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("connector_id", "provider", "action", "version", "owner_team"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.risk, ConnectorRisk):
            raise ValueError("connector_risk_invalid")
        object.__setattr__(self, "side_effects", _normalize_text_tuple(self.side_effects, "side_effects", allow_empty=True))
        object.__setattr__(self, "oauth_scopes", _normalize_text_tuple(self.oauth_scopes, "oauth_scopes"))
        object.__setattr__(self, "eval_suites", _normalize_text_tuple(self.eval_suites, "eval_suites"))
        object.__setattr__(self, "evidence_required", _normalize_text_tuple(self.evidence_required, "evidence_required"))
        if _has_write_side_effect(self) and not self.requires_approval:
            raise ValueError("write_connector_requires_approval")
        if _has_write_side_effect(self) and not self.requires_receipt:
            raise ValueError("write_connector_requires_receipt")
        if _has_write_side_effect(self) and not self.requires_idempotency:
            raise ValueError("write_connector_requires_idempotency")
        if self.requires_tenant_binding is not True:
            raise ValueError("connector_requires_tenant_binding")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class ConnectorEvidence:
    """Evidence attached to one connector certification decision."""

    evidence_id: str
    connector_id: str
    evidence_type: str
    evidence_ref: str
    observed_at: str
    passed: bool
    evidence_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("evidence_id", "connector_id", "evidence_type", "evidence_ref", "observed_at"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.passed, bool):
            raise ValueError("evidence_passed_boolean_required")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class ConnectorCertification:
    """Current certification state for one connector."""

    certification_id: str
    connector_id: str
    level: ConnectorCertificationLevel
    certified_by: str
    certified_at: str
    evidence_ids: tuple[str, ...]
    revoked_at: str = ""
    revocation_reason: str = ""
    certification_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("certification_id", "connector_id", "certified_by", "certified_at"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.level, ConnectorCertificationLevel):
            raise ValueError("connector_certification_level_invalid")
        object.__setattr__(self, "evidence_ids", _normalize_text_tuple(self.evidence_ids, "evidence_ids"))
        if self.revoked_at and not self.revocation_reason:
            raise ValueError("revocation_reason_required")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class ConnectorCertificationDecision:
    """Deterministic production-admission decision for a connector."""

    decision_id: str
    connector_id: str
    requested_level: ConnectorCertificationLevel
    verdict: ConnectorCertificationVerdict
    reason: str
    missing_evidence: tuple[str, ...]
    missing_evals: tuple[str, ...]
    required_controls: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    decision_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.decision_id, "decision_id")
        _require_text(self.connector_id, "connector_id")
        if not isinstance(self.requested_level, ConnectorCertificationLevel):
            raise ValueError("requested_level_invalid")
        if not isinstance(self.verdict, ConnectorCertificationVerdict):
            raise ValueError("connector_certification_verdict_invalid")
        _require_text(self.reason, "reason")
        object.__setattr__(self, "missing_evidence", _normalize_text_tuple(self.missing_evidence, "missing_evidence", allow_empty=True))
        object.__setattr__(self, "missing_evals", _normalize_text_tuple(self.missing_evals, "missing_evals", allow_empty=True))
        object.__setattr__(self, "required_controls", _normalize_text_tuple(self.required_controls, "required_controls", allow_empty=True))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class ConnectorCertificationRegistrySnapshot:
    """Operator read model for connector certification state."""

    registry_id: str
    manifests: tuple[ConnectorManifest, ...]
    evidence: tuple[ConnectorEvidence, ...]
    certifications: tuple[ConnectorCertification, ...]
    decisions: tuple[ConnectorCertificationDecision, ...]
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        _require_text(self.registry_id, "registry_id")
        object.__setattr__(self, "manifests", tuple(self.manifests))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "certifications", tuple(self.certifications))
        object.__setattr__(self, "decisions", tuple(self.decisions))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


class ConnectorCertificationRegistry:
    """In-memory governed connector certification registry."""

    def __init__(self, *, registry_id: str = "connector-certification-registry") -> None:
        self._registry_id = registry_id
        self._manifests: dict[str, ConnectorManifest] = {}
        self._evidence: dict[str, ConnectorEvidence] = {}
        self._certifications: dict[str, ConnectorCertification] = {}
        self._decisions: list[ConnectorCertificationDecision] = []

    def register_manifest(self, manifest: ConnectorManifest) -> ConnectorManifest:
        """Register one stamped connector manifest."""
        stamped = _stamp_manifest(manifest)
        self._manifests[stamped.connector_id] = stamped
        return stamped

    def add_evidence(self, evidence: ConnectorEvidence) -> ConnectorEvidence:
        """Attach one stamped evidence record."""
        if evidence.connector_id not in self._manifests:
            raise ValueError("connector_manifest_missing")
        stamped = _stamp_evidence(evidence)
        self._evidence[stamped.evidence_id] = stamped
        return stamped

    def certify(
        self,
        *,
        connector_id: str,
        requested_level: ConnectorCertificationLevel,
        certified_by: str,
        certified_at: str,
        requested_oauth_scopes: Iterable[str],
    ) -> tuple[ConnectorCertification | None, ConnectorCertificationDecision]:
        """Issue certification only if required evidence and scopes are present."""
        manifest = self._manifests.get(connector_id)
        if manifest is None:
            decision = self._decision(connector_id, requested_level, ConnectorCertificationVerdict.DENY, "connector_manifest_missing", (), (), (), ())
            return None, decision
        requested_scopes = _normalize_text_tuple(tuple(requested_oauth_scopes), "requested_oauth_scopes")
        if not set(requested_scopes).issubset(manifest.oauth_scopes):
            decision = self._decision(connector_id, requested_level, ConnectorCertificationVerdict.DENY, "oauth_scope_exceeds_manifest", (), (), (), ())
            return None, decision

        connector_evidence = tuple(evidence for evidence in self._evidence.values() if evidence.connector_id == connector_id and evidence.passed)
        evidence_types = {evidence.evidence_type for evidence in connector_evidence}
        required_evidence = _required_evidence_for_level(manifest, requested_level)
        missing_evidence = tuple(sorted(required_evidence.difference(evidence_types)))
        missing_evals = tuple(sorted(_required_evals_for_level(requested_level).difference(manifest.eval_suites)))
        if missing_evidence or missing_evals:
            decision = self._decision(
                connector_id,
                requested_level,
                ConnectorCertificationVerdict.DENY,
                "connector_certification_requirements_missing",
                missing_evidence,
                missing_evals,
                _controls_for_manifest(manifest),
                tuple(evidence.evidence_ref for evidence in connector_evidence),
            )
            return None, decision

        certification = _stamp_certification(ConnectorCertification(
            certification_id=f"connector-cert-{canonical_hash({'connector_id': connector_id, 'level': requested_level.value, 'certified_at': certified_at})[:16]}",
            connector_id=connector_id,
            level=requested_level,
            certified_by=certified_by,
            certified_at=certified_at,
            evidence_ids=tuple(evidence.evidence_id for evidence in connector_evidence),
            metadata={"requested_oauth_scopes": requested_scopes},
        ))
        self._certifications[connector_id] = certification
        decision = self._decision(
            connector_id,
            requested_level,
            ConnectorCertificationVerdict.ALLOW,
            "connector_certification_satisfied",
            (),
            (),
            _controls_for_manifest(manifest),
            tuple(evidence.evidence_ref for evidence in connector_evidence),
        )
        return certification, decision

    def evaluate_invocation(
        self,
        *,
        connector_id: str,
        requested_oauth_scopes: Iterable[str],
        requires_write: bool,
        tenant_bound: bool,
        idempotency_key: str = "",
        receipt_ref: str = "",
    ) -> ConnectorCertificationDecision:
        """Evaluate whether a connector invocation is production-admissible."""
        manifest = self._manifests.get(connector_id)
        certification = self._certifications.get(connector_id)
        requested_scopes = tuple(requested_oauth_scopes)
        if manifest is None:
            return self._decision(connector_id, ConnectorCertificationLevel.L5_PRODUCTION_CERTIFIED, ConnectorCertificationVerdict.DENY, "connector_manifest_missing", (), (), (), ())
        if certification is None:
            return self._decision(connector_id, ConnectorCertificationLevel.L5_PRODUCTION_CERTIFIED, ConnectorCertificationVerdict.DENY, "connector_not_certified", (), (), _controls_for_manifest(manifest), ())
        if certification.revoked_at:
            return self._decision(connector_id, certification.level, ConnectorCertificationVerdict.DENY, "connector_certification_revoked", (), (), _controls_for_manifest(manifest), ())
        if _LEVEL_ORDER[certification.level] < _LEVEL_ORDER[ConnectorCertificationLevel.L5_PRODUCTION_CERTIFIED]:
            return self._decision(connector_id, certification.level, ConnectorCertificationVerdict.DENY, "connector_not_production_certified", (), (), _controls_for_manifest(manifest), ())
        if not set(requested_scopes).issubset(manifest.oauth_scopes):
            return self._decision(connector_id, certification.level, ConnectorCertificationVerdict.DENY, "oauth_scope_exceeds_manifest", (), (), _controls_for_manifest(manifest), ())
        if manifest.requires_tenant_binding and not tenant_bound:
            return self._decision(connector_id, certification.level, ConnectorCertificationVerdict.DENY, "tenant_binding_required", (), (), _controls_for_manifest(manifest), ())
        if requires_write and manifest.requires_idempotency and not idempotency_key:
            return self._decision(connector_id, certification.level, ConnectorCertificationVerdict.DENY, "idempotency_key_required", (), (), _controls_for_manifest(manifest), ())
        if requires_write and manifest.requires_receipt and not receipt_ref:
            return self._decision(connector_id, certification.level, ConnectorCertificationVerdict.DENY, "connector_receipt_required", (), (), _controls_for_manifest(manifest), ())
        return self._decision(connector_id, certification.level, ConnectorCertificationVerdict.ALLOW, "connector_invocation_certified", (), (), _controls_for_manifest(manifest), (receipt_ref,) if receipt_ref else ())

    def revoke(self, *, connector_id: str, revoked_at: str, reason: str) -> ConnectorCertification:
        """Revoke one connector certification."""
        certification = self._certifications.get(connector_id)
        if certification is None:
            raise ValueError("connector_certification_missing")
        revoked = _stamp_certification(replace(certification, revoked_at=revoked_at, revocation_reason=reason))
        self._certifications[connector_id] = revoked
        return revoked

    def snapshot(self) -> ConnectorCertificationRegistrySnapshot:
        """Return a stamped operator read model."""
        snapshot = ConnectorCertificationRegistrySnapshot(
            registry_id=self._registry_id,
            manifests=tuple(sorted(self._manifests.values(), key=lambda item: item.connector_id)),
            evidence=tuple(sorted(self._evidence.values(), key=lambda item: item.evidence_id)),
            certifications=tuple(sorted(self._certifications.values(), key=lambda item: item.connector_id)),
            decisions=tuple(self._decisions),
        )
        payload = snapshot.to_json_dict()
        payload["snapshot_hash"] = ""
        return replace(snapshot, snapshot_hash=canonical_hash(payload))

    def _decision(
        self,
        connector_id: str,
        requested_level: ConnectorCertificationLevel,
        verdict: ConnectorCertificationVerdict,
        reason: str,
        missing_evidence: tuple[str, ...],
        missing_evals: tuple[str, ...],
        required_controls: tuple[str, ...],
        evidence_refs: tuple[str, ...],
    ) -> ConnectorCertificationDecision:
        decision = ConnectorCertificationDecision(
            decision_id="pending",
            connector_id=connector_id or "unknown",
            requested_level=requested_level,
            verdict=verdict,
            reason=reason,
            missing_evidence=missing_evidence,
            missing_evals=missing_evals,
            required_controls=required_controls,
            evidence_refs=evidence_refs,
        )
        payload = decision.to_json_dict()
        payload["decision_hash"] = ""
        decision_hash = canonical_hash(payload)
        stamped = replace(decision, decision_id=f"connector-decision-{decision_hash[:16]}", decision_hash=decision_hash)
        self._decisions.append(stamped)
        return stamped


def connector_certification_snapshot_to_json_dict(snapshot: ConnectorCertificationRegistrySnapshot) -> dict[str, Any]:
    """Return the public JSON-contract representation of a registry snapshot."""
    return snapshot.to_json_dict()


def _required_evidence_for_level(
    manifest: ConnectorManifest,
    requested_level: ConnectorCertificationLevel,
) -> set[str]:
    required = {item for item in manifest.evidence_required}
    if _LEVEL_ORDER[requested_level] >= _LEVEL_ORDER[ConnectorCertificationLevel.L1_MOCK_TESTED]:
        required.add("mock_test")
    if _LEVEL_ORDER[requested_level] >= _LEVEL_ORDER[ConnectorCertificationLevel.L2_SANDBOX_TESTED]:
        required.add("sandbox_receipt")
    if _LEVEL_ORDER[requested_level] >= _LEVEL_ORDER[ConnectorCertificationLevel.L3_LIVE_READ_ONLY_TESTED]:
        required.add("live_read_receipt")
    if _LEVEL_ORDER[requested_level] >= _LEVEL_ORDER[ConnectorCertificationLevel.L4_LIVE_WRITE_TESTED]:
        required.add("live_write_receipt")
    if _LEVEL_ORDER[requested_level] >= _LEVEL_ORDER[ConnectorCertificationLevel.L5_PRODUCTION_CERTIFIED]:
        required.update(_PRODUCTION_REQUIRED_EVIDENCE)
    return required


def _required_evals_for_level(requested_level: ConnectorCertificationLevel) -> set[str]:
    if _LEVEL_ORDER[requested_level] >= _LEVEL_ORDER[ConnectorCertificationLevel.L5_PRODUCTION_CERTIFIED]:
        return set(_PRODUCTION_REQUIRED_EVALS)
    return set()


def _controls_for_manifest(manifest: ConnectorManifest) -> tuple[str, ...]:
    controls = ["tenant_binding", "credential_scope"]
    if manifest.requires_approval:
        controls.append("approval_required")
    if manifest.requires_receipt:
        controls.append("connector_receipt")
    if manifest.requires_idempotency:
        controls.append("idempotency_key")
    return tuple(controls)


def _has_write_side_effect(manifest: ConnectorManifest) -> bool:
    return bool(set(manifest.side_effects).intersection(_WRITE_SIDE_EFFECTS))


def _stamp_manifest(manifest: ConnectorManifest) -> ConnectorManifest:
    payload = manifest.to_json_dict()
    payload["manifest_hash"] = ""
    return replace(manifest, manifest_hash=canonical_hash(payload))


def _stamp_evidence(evidence: ConnectorEvidence) -> ConnectorEvidence:
    payload = evidence.to_json_dict()
    payload["evidence_hash"] = ""
    return replace(evidence, evidence_hash=canonical_hash(payload))


def _stamp_certification(certification: ConnectorCertification) -> ConnectorCertification:
    payload = certification.to_json_dict()
    payload["certification_hash"] = ""
    return replace(certification, certification_hash=canonical_hash(payload))


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized and not allow_empty:
        raise ValueError(f"{field_name}_required")
    return normalized


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name}_required")


def _json_ready(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
