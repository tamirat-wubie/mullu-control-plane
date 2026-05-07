"""Gateway risk and compliance mapping foundation.

Purpose: map governed Mullu evidence into buyer-facing risk controls, control
    gaps, evidence coverage, and publication-safe compliance reports.
Governance scope: symbolic system inventory, control mappings, risk register,
    evidence references, report decisions, and certification-claim boundaries.
Dependencies: dataclasses, enum, typing, and command-spine canonical hashing.
Invariants:
  - Compliance reports are alignment evidence, not certification claims.
  - Every control mapping declares required evidence kinds.
  - Missing required evidence creates a review gap.
  - External publication requires explicit review even when controls are mapped.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from typing import Any

from gateway.command_spine import canonical_hash


class ComplianceFramework(StrEnum):
    """Supported compliance and risk frameworks."""

    SOC2 = "SOC2"
    HIPAA = "HIPAA"
    EU_ACT = "EU_ACT"
    ISO_IEC_42001 = "ISO_IEC_42001"
    NIST_RMF = "NIST_RMF"


class EvidenceKind(StrEnum):
    """Governed evidence kinds that can satisfy control mappings."""

    POLICY_DECISION = "policy_decision"
    APPROVAL_RECORD = "approval_record"
    EVAL_RUN = "eval_run"
    TERMINAL_CERTIFICATE = "terminal_certificate"
    INCIDENT_CASE = "incident_case"
    CAPABILITY_EVIDENCE = "capability_evidence"
    DEPLOYMENT_WITNESS = "deployment_witness"
    LEARNING_ADMISSION_DECISION = "learning_admission_decision"
    DATA_GOVERNANCE = "data_governance"
    COMMERCIAL_METERING = "commercial_metering"


class RiskSeverity(StrEnum):
    """Risk register severity."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MappingDisposition(StrEnum):
    """Control mapping status."""

    MAPPED = "mapped"
    GAP = "gap"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class SymbolicSystemInventoryItem:
    """Inventory entry for a governed Mullu system, agent, model, or capability."""

    item_id: str
    item_type: str
    tenant_id: str
    owner: str
    risk_tier: RiskSeverity
    evidence_refs: tuple[str, ...]
    item_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("item_id", "item_type", "tenant_id", "owner"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.risk_tier, RiskSeverity):
            raise ValueError("risk_tier_invalid")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class ControlMapping:
    """Map a Mullu evidence surface to a framework control area."""

    mapping_id: str
    framework: ComplianceFramework
    control_id: str
    control_area: str
    mullu_evidence_surface: str
    required_evidence_kinds: tuple[EvidenceKind, ...]
    owner: str
    mapping_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("mapping_id", "control_id", "control_area", "mullu_evidence_surface", "owner"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.framework, ComplianceFramework):
            raise ValueError("compliance_framework_invalid")
        kinds = tuple(self.required_evidence_kinds)
        if not kinds:
            raise ValueError("required_evidence_kinds_required")
        if any(not isinstance(kind, EvidenceKind) for kind in kinds):
            raise ValueError("evidence_kind_invalid")
        object.__setattr__(self, "required_evidence_kinds", tuple(dict.fromkeys(kinds)))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class ComplianceEvidenceRecord:
    """Evidence reference that can satisfy one or more control mappings."""

    evidence_id: str
    tenant_id: str
    kind: EvidenceKind
    source_ref: str
    observed_at: str
    passed: bool
    evidence_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("evidence_id", "tenant_id", "source_ref", "observed_at"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.kind, EvidenceKind):
            raise ValueError("evidence_kind_invalid")
        if not isinstance(self.passed, bool):
            raise ValueError("evidence_passed_boolean_required")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class RiskRegisterEntry:
    """Risk register entry tied to a system, control, or evidence surface."""

    risk_id: str
    tenant_id: str
    title: str
    severity: RiskSeverity
    control_ids: tuple[str, ...]
    mitigation_refs: tuple[str, ...]
    owner: str
    status: str
    risk_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("risk_id", "tenant_id", "title", "owner", "status"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.severity, RiskSeverity):
            raise ValueError("risk_severity_invalid")
        object.__setattr__(self, "control_ids", _normalize_text_tuple(self.control_ids, "control_ids", allow_empty=True))
        object.__setattr__(self, "mitigation_refs", _normalize_text_tuple(self.mitigation_refs, "mitigation_refs", allow_empty=True))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class ControlMappingResult:
    """Control-level mapping result for one tenant report."""

    mapping_id: str
    framework: ComplianceFramework
    control_id: str
    disposition: MappingDisposition
    present_evidence_kinds: tuple[EvidenceKind, ...]
    missing_evidence_kinds: tuple[EvidenceKind, ...]
    evidence_refs: tuple[str, ...]
    result_hash: str = ""

    def __post_init__(self) -> None:
        for field_name in ("mapping_id", "control_id"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.framework, ComplianceFramework):
            raise ValueError("compliance_framework_invalid")
        if not isinstance(self.disposition, MappingDisposition):
            raise ValueError("mapping_disposition_invalid")
        object.__setattr__(self, "present_evidence_kinds", tuple(self.present_evidence_kinds))
        object.__setattr__(self, "missing_evidence_kinds", tuple(self.missing_evidence_kinds))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class ComplianceReport:
    """Tenant/framework compliance alignment report."""

    report_id: str
    tenant_id: str
    framework: ComplianceFramework
    generated_at: str
    certification_claimed: bool
    external_publication_review_required: bool
    mapped_control_count: int
    gap_control_count: int
    review_control_count: int
    evidence_coverage_percent: float
    high_or_critical_risk_count: int
    publication_allowed: bool
    results: tuple[ControlMappingResult, ...]
    report_hash: str = ""

    def __post_init__(self) -> None:
        for field_name in ("report_id", "tenant_id", "generated_at"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.framework, ComplianceFramework):
            raise ValueError("compliance_framework_invalid")
        if self.certification_claimed is not False:
            raise ValueError("certification_claim_must_be_false")
        if self.external_publication_review_required is not True:
            raise ValueError("external_publication_review_required")
        for field_name in ("mapped_control_count", "gap_control_count", "review_control_count", "high_or_critical_risk_count"):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name}_non_negative")
        if not 0.0 <= self.evidence_coverage_percent <= 100.0:
            raise ValueError("evidence_coverage_percent_out_of_range")
        object.__setattr__(self, "results", tuple(self.results))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class RiskComplianceMappingSnapshot:
    """Operator read model for risk and compliance mappings."""

    snapshot_id: str
    inventory: tuple[SymbolicSystemInventoryItem, ...]
    mappings: tuple[ControlMapping, ...]
    evidence: tuple[ComplianceEvidenceRecord, ...]
    risks: tuple[RiskRegisterEntry, ...]
    reports: tuple[ComplianceReport, ...]
    open_gap_count: int
    high_or_critical_risk_count: int
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        _require_text(self.snapshot_id, "snapshot_id")
        for field_name in ("inventory", "mappings", "evidence", "risks", "reports"):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if self.open_gap_count < 0:
            raise ValueError("open_gap_count_non_negative")
        if self.high_or_critical_risk_count < 0:
            raise ValueError("high_or_critical_risk_count_non_negative")

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


class RiskComplianceMapper:
    """In-memory control mapping registry and report builder."""

    def __init__(self, *, snapshot_id: str = "risk-compliance-mapping-snapshot") -> None:
        self._snapshot_id = snapshot_id
        self._inventory: dict[str, SymbolicSystemInventoryItem] = {}
        self._mappings: dict[str, ControlMapping] = {}
        self._evidence: dict[str, ComplianceEvidenceRecord] = {}
        self._risks: dict[str, RiskRegisterEntry] = {}
        self._reports: list[ComplianceReport] = []

    def register_inventory_item(self, item: SymbolicSystemInventoryItem) -> SymbolicSystemInventoryItem:
        """Register one stamped system inventory item."""
        stamped = _stamp_inventory(item)
        self._inventory[stamped.item_id] = stamped
        return stamped

    def register_mapping(self, mapping: ControlMapping) -> ControlMapping:
        """Register one stamped framework control mapping."""
        stamped = _stamp_mapping(mapping)
        self._mappings[stamped.mapping_id] = stamped
        return stamped

    def add_evidence(self, evidence: ComplianceEvidenceRecord) -> ComplianceEvidenceRecord:
        """Add one stamped evidence record."""
        stamped = _stamp_evidence(evidence)
        self._evidence[stamped.evidence_id] = stamped
        return stamped

    def register_risk(self, risk: RiskRegisterEntry) -> RiskRegisterEntry:
        """Register one stamped risk register entry."""
        stamped = _stamp_risk(risk)
        self._risks[stamped.risk_id] = stamped
        return stamped

    def generate_report(self, *, tenant_id: str, framework: ComplianceFramework, generated_at: str) -> ComplianceReport:
        """Generate a report for one tenant and framework."""
        _require_text(tenant_id, "tenant_id")
        _require_text(generated_at, "generated_at")
        if not isinstance(framework, ComplianceFramework):
            raise ValueError("compliance_framework_invalid")
        mappings = tuple(mapping for mapping in self._mappings.values() if mapping.framework == framework)
        results = tuple(_stamp_result(self._result_for_mapping(tenant_id, mapping)) for mapping in mappings)
        mapped_count = sum(1 for result in results if result.disposition == MappingDisposition.MAPPED)
        gap_count = sum(1 for result in results if result.disposition == MappingDisposition.GAP)
        review_count = sum(1 for result in results if result.disposition == MappingDisposition.REVIEW)
        coverage = round((mapped_count / len(results)) * 100.0, 2) if results else 0.0
        high_risk_count = self._high_or_critical_risk_count(tenant_id)
        report = ComplianceReport(
            report_id="pending",
            tenant_id=tenant_id,
            framework=framework,
            generated_at=generated_at,
            certification_claimed=False,
            external_publication_review_required=True,
            mapped_control_count=mapped_count,
            gap_control_count=gap_count,
            review_control_count=review_count,
            evidence_coverage_percent=coverage,
            high_or_critical_risk_count=high_risk_count,
            publication_allowed=False,
            results=results,
        )
        stamped = _stamp_report(report)
        self._reports.append(stamped)
        return stamped

    def snapshot(self) -> RiskComplianceMappingSnapshot:
        """Return a stamped risk/compliance read model."""
        snapshot = RiskComplianceMappingSnapshot(
            snapshot_id=self._snapshot_id,
            inventory=tuple(sorted(self._inventory.values(), key=lambda item: item.item_id)),
            mappings=tuple(sorted(self._mappings.values(), key=lambda item: item.mapping_id)),
            evidence=tuple(sorted(self._evidence.values(), key=lambda item: item.evidence_id)),
            risks=tuple(sorted(self._risks.values(), key=lambda item: item.risk_id)),
            reports=tuple(self._reports),
            open_gap_count=sum(report.gap_control_count + report.review_control_count for report in self._reports),
            high_or_critical_risk_count=sum(1 for risk in self._risks.values() if risk.severity in {RiskSeverity.HIGH, RiskSeverity.CRITICAL}),
        )
        payload = snapshot.to_json_dict()
        payload["snapshot_hash"] = ""
        return replace(snapshot, snapshot_hash=canonical_hash(payload))

    def _result_for_mapping(self, tenant_id: str, mapping: ControlMapping) -> ControlMappingResult:
        tenant_evidence = tuple(
            evidence for evidence in self._evidence.values() if evidence.tenant_id == tenant_id and evidence.passed
        )
        present_kinds = tuple(
            kind for kind in mapping.required_evidence_kinds if any(evidence.kind == kind for evidence in tenant_evidence)
        )
        missing_kinds = tuple(kind for kind in mapping.required_evidence_kinds if kind not in present_kinds)
        evidence_refs = tuple(
            evidence.source_ref for evidence in tenant_evidence if evidence.kind in mapping.required_evidence_kinds
        )
        disposition = MappingDisposition.MAPPED
        if missing_kinds:
            disposition = MappingDisposition.GAP
        elif self._control_has_open_high_risk(tenant_id, mapping.control_id):
            disposition = MappingDisposition.REVIEW
        return ControlMappingResult(
            mapping_id=mapping.mapping_id,
            framework=mapping.framework,
            control_id=mapping.control_id,
            disposition=disposition,
            present_evidence_kinds=present_kinds,
            missing_evidence_kinds=missing_kinds,
            evidence_refs=evidence_refs,
        )

    def _control_has_open_high_risk(self, tenant_id: str, control_id: str) -> bool:
        return any(
            risk.tenant_id == tenant_id
            and risk.status != "closed"
            and control_id in risk.control_ids
            and risk.severity in {RiskSeverity.HIGH, RiskSeverity.CRITICAL}
            for risk in self._risks.values()
        )

    def _high_or_critical_risk_count(self, tenant_id: str) -> int:
        return sum(
            1
            for risk in self._risks.values()
            if risk.tenant_id == tenant_id and risk.severity in {RiskSeverity.HIGH, RiskSeverity.CRITICAL}
        )


def risk_compliance_mapping_snapshot_to_json_dict(snapshot: RiskComplianceMappingSnapshot) -> dict[str, Any]:
    """Return the public JSON-contract representation of risk/compliance state."""
    return snapshot.to_json_dict()


def _stamp_inventory(item: SymbolicSystemInventoryItem) -> SymbolicSystemInventoryItem:
    payload = item.to_json_dict()
    payload["item_hash"] = ""
    return replace(item, item_hash=canonical_hash(payload))


def _stamp_mapping(mapping: ControlMapping) -> ControlMapping:
    payload = mapping.to_json_dict()
    payload["mapping_hash"] = ""
    return replace(mapping, mapping_hash=canonical_hash(payload))


def _stamp_evidence(evidence: ComplianceEvidenceRecord) -> ComplianceEvidenceRecord:
    payload = evidence.to_json_dict()
    payload["evidence_hash"] = ""
    return replace(evidence, evidence_hash=canonical_hash(payload))


def _stamp_risk(risk: RiskRegisterEntry) -> RiskRegisterEntry:
    payload = risk.to_json_dict()
    payload["risk_hash"] = ""
    return replace(risk, risk_hash=canonical_hash(payload))


def _stamp_result(result: ControlMappingResult) -> ControlMappingResult:
    payload = result.to_json_dict()
    payload["result_hash"] = ""
    return replace(result, result_hash=canonical_hash(payload))


def _stamp_report(report: ComplianceReport) -> ComplianceReport:
    payload = report.to_json_dict()
    payload["report_hash"] = ""
    report_hash = canonical_hash(payload)
    return replace(report, report_id=f"compliance-report-{report_hash[:16]}", report_hash=report_hash)


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
