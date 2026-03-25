"""Purpose: data governance / privacy / residency runtime contracts.
Governance scope: typed descriptors for data classification, handling policies,
    residency constraints, privacy rules, redaction rules, retention rules,
    handling decisions, violations, snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every data record has explicit classification and tenant scope.
  - Governance decisions are fail-closed — default is DENY.
  - Residency constraints are enforced before transfer.
  - Redaction is applied before outbound operations.
  - All outputs are frozen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DataClassification(Enum):
    """Classification level of data."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"
    PII = "pii"
    SECRET = "secret"


class ResidencyRegion(Enum):
    """Data residency region."""
    US = "us"
    EU = "eu"
    UK = "uk"
    APAC = "apac"
    GLOBAL = "global"
    RESTRICTED = "restricted"


class HandlingDisposition(Enum):
    """How data should be handled."""
    ALLOW = "allow"
    REDACT = "redact"
    DENY = "deny"
    ENCRYPT = "encrypt"
    AUDIT_ONLY = "audit_only"


class PrivacyBasis(Enum):
    """Legal basis for processing data."""
    CONSENT = "consent"
    CONTRACT = "contract"
    LEGAL_OBLIGATION = "legal_obligation"
    VITAL_INTEREST = "vital_interest"
    PUBLIC_INTEREST = "public_interest"
    LEGITIMATE_INTEREST = "legitimate_interest"


class RedactionLevel(Enum):
    """Level of redaction to apply."""
    NONE = "none"
    PARTIAL = "partial"
    FULL = "full"
    TOKENIZE = "tokenize"
    HASH = "hash"


class RetentionDisposition(Enum):
    """What to do when retention expires."""
    DELETE = "delete"
    ARCHIVE = "archive"
    ANONYMIZE = "anonymize"
    REVIEW = "review"


class GovernanceDecision(Enum):
    """Decision from data governance evaluation."""
    ALLOWED = "allowed"
    DENIED = "denied"
    REDACTED = "redacted"
    REQUIRES_REVIEW = "requires_review"
    VIOLATION = "violation"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DataRecord(ContractRecord):
    """A classified data record in the platform."""

    data_id: str = ""
    tenant_id: str = ""
    classification: DataClassification = DataClassification.INTERNAL
    residency: ResidencyRegion = ResidencyRegion.GLOBAL
    privacy_basis: PrivacyBasis = PrivacyBasis.LEGITIMATE_INTEREST
    domain: str = ""
    source_id: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_id", require_non_empty_text(self.data_id, "data_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.classification, DataClassification):
            raise ValueError("classification must be a DataClassification")
        if not isinstance(self.residency, ResidencyRegion):
            raise ValueError("residency must be a ResidencyRegion")
        if not isinstance(self.privacy_basis, PrivacyBasis):
            raise ValueError("privacy_basis must be a PrivacyBasis")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DataPolicy(ContractRecord):
    """A data handling policy bound to a scope."""

    policy_id: str = ""
    tenant_id: str = ""
    classification: DataClassification = DataClassification.INTERNAL
    disposition: HandlingDisposition = HandlingDisposition.DENY
    residency: ResidencyRegion = ResidencyRegion.GLOBAL
    scope_ref_id: str = ""
    description: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.classification, DataClassification):
            raise ValueError("classification must be a DataClassification")
        if not isinstance(self.disposition, HandlingDisposition):
            raise ValueError("disposition must be a HandlingDisposition")
        if not isinstance(self.residency, ResidencyRegion):
            raise ValueError("residency must be a ResidencyRegion")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ResidencyConstraint(ContractRecord):
    """A residency constraint for data handling."""

    constraint_id: str = ""
    tenant_id: str = ""
    allowed_regions: tuple[str, ...] = ()
    denied_regions: tuple[str, ...] = ()
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraint_id", require_non_empty_text(self.constraint_id, "constraint_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "allowed_regions", freeze_value(list(self.allowed_regions)))
        object.__setattr__(self, "denied_regions", freeze_value(list(self.denied_regions)))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PrivacyRule(ContractRecord):
    """A privacy rule governing data processing."""

    rule_id: str = ""
    tenant_id: str = ""
    classification: DataClassification = DataClassification.PII
    required_basis: PrivacyBasis = PrivacyBasis.CONSENT
    scope_ref_id: str = ""
    description: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", require_non_empty_text(self.rule_id, "rule_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.classification, DataClassification):
            raise ValueError("classification must be a DataClassification")
        if not isinstance(self.required_basis, PrivacyBasis):
            raise ValueError("required_basis must be a PrivacyBasis")
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class RedactionRule(ContractRecord):
    """A rule specifying redaction level for data."""

    rule_id: str = ""
    tenant_id: str = ""
    classification: DataClassification = DataClassification.SENSITIVE
    redaction_level: RedactionLevel = RedactionLevel.FULL
    scope_ref_id: str = ""
    field_patterns: tuple[str, ...] = ()
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", require_non_empty_text(self.rule_id, "rule_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.classification, DataClassification):
            raise ValueError("classification must be a DataClassification")
        if not isinstance(self.redaction_level, RedactionLevel):
            raise ValueError("redaction_level must be a RedactionLevel")
        object.__setattr__(self, "field_patterns", freeze_value(list(self.field_patterns)))
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class RetentionRule(ContractRecord):
    """A retention rule for data lifecycle."""

    rule_id: str = ""
    tenant_id: str = ""
    classification: DataClassification = DataClassification.INTERNAL
    retention_days: int = 0
    disposition: RetentionDisposition = RetentionDisposition.DELETE
    scope_ref_id: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", require_non_empty_text(self.rule_id, "rule_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.classification, DataClassification):
            raise ValueError("classification must be a DataClassification")
        object.__setattr__(self, "retention_days", require_non_negative_int(self.retention_days, "retention_days"))
        if not isinstance(self.disposition, RetentionDisposition):
            raise ValueError("disposition must be a RetentionDisposition")
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class HandlingDecision(ContractRecord):
    """A governance decision about data handling."""

    decision_id: str = ""
    data_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    decision: GovernanceDecision = GovernanceDecision.DENIED
    disposition: HandlingDisposition = HandlingDisposition.DENY
    redaction_level: RedactionLevel = RedactionLevel.NONE
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "data_id", require_non_empty_text(self.data_id, "data_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        if not isinstance(self.decision, GovernanceDecision):
            raise ValueError("decision must be a GovernanceDecision")
        if not isinstance(self.disposition, HandlingDisposition):
            raise ValueError("disposition must be a HandlingDisposition")
        if not isinstance(self.redaction_level, RedactionLevel):
            raise ValueError("redaction_level must be a RedactionLevel")
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DataViolation(ContractRecord):
    """A detected data governance violation."""

    violation_id: str = ""
    data_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    classification: DataClassification = DataClassification.INTERNAL
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "data_id", require_non_empty_text(self.data_id, "data_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        if not isinstance(self.classification, DataClassification):
            raise ValueError("classification must be a DataClassification")
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DataGovernanceSnapshot(ContractRecord):
    """Point-in-time data governance snapshot."""

    snapshot_id: str = ""
    scope_ref_id: str = ""
    total_records: int = 0
    total_policies: int = 0
    total_residency_constraints: int = 0
    total_privacy_rules: int = 0
    total_redaction_rules: int = 0
    total_retention_rules: int = 0
    total_decisions: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_records", require_non_negative_int(self.total_records, "total_records"))
        object.__setattr__(self, "total_policies", require_non_negative_int(self.total_policies, "total_policies"))
        object.__setattr__(self, "total_residency_constraints", require_non_negative_int(self.total_residency_constraints, "total_residency_constraints"))
        object.__setattr__(self, "total_privacy_rules", require_non_negative_int(self.total_privacy_rules, "total_privacy_rules"))
        object.__setattr__(self, "total_redaction_rules", require_non_negative_int(self.total_redaction_rules, "total_redaction_rules"))
        object.__setattr__(self, "total_retention_rules", require_non_negative_int(self.total_retention_rules, "total_retention_rules"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DataClosureReport(ContractRecord):
    """Summary report for data governance closure."""

    report_id: str = ""
    tenant_id: str = ""
    total_records: int = 0
    total_decisions: int = 0
    total_violations: int = 0
    total_redactions: int = 0
    total_denials: int = 0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_records", require_non_negative_int(self.total_records, "total_records"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        object.__setattr__(self, "total_redactions", require_non_negative_int(self.total_redactions, "total_redactions"))
        object.__setattr__(self, "total_denials", require_non_negative_int(self.total_denials, "total_denials"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
