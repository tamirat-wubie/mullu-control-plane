"""Purpose: repair template registry for governed rollback and compensation.
Governance scope: domain/action repair admission, evidence requirements, and
    deterministic operator read models.
Dependencies: Python standard library, causal repair contracts, invariant helpers.
Invariants:
  - Every template has one explicit domain/action boundary.
  - External, user-visible, financial, public, and physical actions require an
    idempotency key before admission.
  - Rollback and version-restore claims require sufficient snapshot evidence.
  - Required evidence, approval, and external confirmation gaps block admission.
  - Registry reads are deterministic and side-effect free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Iterable, Mapping

from .causal_repair import (
    EffectClass,
    RepairStrategy,
    ReversibilityClass,
    SnapshotQuality,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


class RepairTemplateRegistryError(RuntimeCoreInvariantError):
    """Raised when a repair template registry invariant is violated."""


class RepairTemplateKind(StrEnum):
    """Primary repair playbook encoded by a template."""

    READ_ONLY = "read_only"
    ROLLBACK = "rollback"
    VERSION_RESTORE = "version_restore"
    SEMANTIC_COMPENSATION = "semantic_compensation"
    RECONCILIATION = "reconciliation"
    QUARANTINE = "quarantine"
    ESCALATION = "escalation"
    FORBIDDEN = "forbidden"


class RepairTemplateRisk(StrEnum):
    """Operator-facing risk level for default repair policy."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class RepairTemplateAdmissionStatus(StrEnum):
    """Admission result for a domain/action template request."""

    ADMITTED = "admitted"
    BLOCKED = "blocked"
    APPROVAL_REQUIRED = "approval_required"
    TEMPLATE_MISSING = "template_missing"


_EXTERNAL_EFFECTS = frozenset(
    {
        EffectClass.EXTERNAL_MUTATION,
        EffectClass.USER_VISIBLE,
        EffectClass.FINANCIAL_OR_LEGAL,
        EffectClass.PUBLIC_IRREVERSIBLE,
        EffectClass.PHYSICAL_WORLD,
    }
)


@dataclass(frozen=True, slots=True)
class RepairTemplate:
    """Static repair obligation for one domain/action pair."""

    template_id: str
    domain: str
    action_type: str
    effect_class: EffectClass
    reversibility_class: ReversibilityClass
    template_kind: RepairTemplateKind
    risk: RepairTemplateRisk
    required_strategy: RepairStrategy
    snapshot_quality_minimum: SnapshotQuality = SnapshotQuality.S0_NONE
    idempotency_required: bool = False
    approval_required: bool = False
    reconciliation_required: bool = False
    external_confirmation_required: bool = False
    verification_required: bool = True
    rollback_capability_ref: str | None = None
    compensation_capability_ref: str | None = None
    residual_damage_policy: str = "no_residual_damage_claim_without_verification"
    required_evidence: tuple[str, ...] = ()
    forbidden_if_missing: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("template_id", "domain", "action_type"):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, getattr(self, field_name)),
            )
        object.__setattr__(self, "effect_class", EffectClass(self.effect_class))
        object.__setattr__(
            self,
            "reversibility_class",
            ReversibilityClass(self.reversibility_class),
        )
        object.__setattr__(
            self,
            "template_kind",
            RepairTemplateKind(self.template_kind),
        )
        object.__setattr__(self, "risk", RepairTemplateRisk(self.risk))
        object.__setattr__(
            self,
            "required_strategy",
            RepairStrategy(self.required_strategy),
        )
        object.__setattr__(
            self,
            "snapshot_quality_minimum",
            _coerce_snapshot_quality(self.snapshot_quality_minimum),
        )
        object.__setattr__(
            self,
            "required_evidence",
            _text_tuple(self.required_evidence, "required_evidence", allow_empty=True),
        )
        object.__setattr__(
            self,
            "forbidden_if_missing",
            _text_tuple(self.forbidden_if_missing, "forbidden_if_missing", allow_empty=True),
        )
        if self.rollback_capability_ref is not None:
            object.__setattr__(
                self,
                "rollback_capability_ref",
                ensure_non_empty_text("rollback_capability_ref", self.rollback_capability_ref),
            )
        if self.compensation_capability_ref is not None:
            object.__setattr__(
                self,
                "compensation_capability_ref",
                ensure_non_empty_text(
                    "compensation_capability_ref",
                    self.compensation_capability_ref,
                ),
            )
        object.__setattr__(
            self,
            "residual_damage_policy",
            ensure_non_empty_text("residual_damage_policy", self.residual_damage_policy),
        )
        if not isinstance(self.metadata, Mapping):
            raise RepairTemplateRegistryError("metadata must be a mapping")
        if self.effect_class in _EXTERNAL_EFFECTS and not self.idempotency_required:
            raise RepairTemplateRegistryError(
                "external repair templates must require idempotency"
            )
        if self.reversibility_class is ReversibilityClass.EXACT_ROLLBACK:
            if self.snapshot_quality_minimum < SnapshotQuality.S2_LOCAL:
                raise RepairTemplateRegistryError(
                    "exact rollback templates require S2 or stronger snapshots"
                )
            if self.rollback_capability_ref is None:
                raise RepairTemplateRegistryError("exact rollback template missing capability")
        if self.reversibility_class is ReversibilityClass.VERSION_RESTORE:
            if self.snapshot_quality_minimum < SnapshotQuality.S3_VERSIONED:
                raise RepairTemplateRegistryError(
                    "version restore templates require S3 or stronger snapshots"
                )
            if self.rollback_capability_ref is None:
                raise RepairTemplateRegistryError("version restore template missing capability")
        if self.reversibility_class is ReversibilityClass.SEMANTIC_COMPENSATION:
            if self.compensation_capability_ref is None:
                raise RepairTemplateRegistryError(
                    "semantic compensation template missing capability"
                )

    @property
    def template_key(self) -> tuple[str, str]:
        return (self.domain, self.action_type)

    def to_json_dict(self) -> dict[str, Any]:
        """Return a deterministic read-model projection for this template."""
        return {
            "template_id": self.template_id,
            "domain": self.domain,
            "action_type": self.action_type,
            "effect_class": self.effect_class.value,
            "reversibility_class": self.reversibility_class.value,
            "template_kind": self.template_kind.value,
            "risk": self.risk.value,
            "required_strategy": self.required_strategy.value,
            "snapshot_quality_minimum": int(self.snapshot_quality_minimum),
            "idempotency_required": self.idempotency_required,
            "approval_required": self.approval_required,
            "reconciliation_required": self.reconciliation_required,
            "external_confirmation_required": self.external_confirmation_required,
            "verification_required": self.verification_required,
            "rollback_capability_ref": self.rollback_capability_ref,
            "compensation_capability_ref": self.compensation_capability_ref,
            "residual_damage_policy": self.residual_damage_policy,
            "required_evidence": self.required_evidence,
            "forbidden_if_missing": self.forbidden_if_missing,
            "metadata": dict(sorted(self.metadata.items())),
        }


@dataclass(frozen=True, slots=True)
class TemplateSelectionRequest:
    """Observed repair context checked against a registered template."""

    domain: str
    action_type: str
    effect_class: EffectClass
    reversibility_class: ReversibilityClass
    available_evidence: tuple[str, ...] = ()
    has_idempotency_key: bool = False
    snapshot_quality: SnapshotQuality = SnapshotQuality.S0_NONE
    approval_present: bool = False
    external_confirmation_present: bool = False

    def __post_init__(self) -> None:
        for field_name in ("domain", "action_type"):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, getattr(self, field_name)),
            )
        object.__setattr__(self, "effect_class", EffectClass(self.effect_class))
        object.__setattr__(
            self,
            "reversibility_class",
            ReversibilityClass(self.reversibility_class),
        )
        object.__setattr__(
            self,
            "available_evidence",
            _text_tuple(self.available_evidence, "available_evidence", allow_empty=True),
        )
        object.__setattr__(
            self,
            "snapshot_quality",
            _coerce_snapshot_quality(self.snapshot_quality),
        )


@dataclass(frozen=True, slots=True)
class RepairTemplateSelection:
    """Decision receipt emitted by template admission."""

    request_id: str
    status: RepairTemplateAdmissionStatus
    admitted: bool
    template_id: str | None
    reason: str
    missing_evidence: tuple[str, ...]
    required_strategy: RepairStrategy
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", ensure_non_empty_text("request_id", self.request_id))
        object.__setattr__(
            self,
            "status",
            RepairTemplateAdmissionStatus(self.status),
        )
        object.__setattr__(self, "reason", ensure_non_empty_text("reason", self.reason))
        object.__setattr__(
            self,
            "missing_evidence",
            _text_tuple(self.missing_evidence, "missing_evidence", allow_empty=True),
        )
        object.__setattr__(
            self,
            "required_strategy",
            RepairStrategy(self.required_strategy),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True),
        )
        if self.template_id is not None:
            object.__setattr__(
                self,
                "template_id",
                ensure_non_empty_text("template_id", self.template_id),
            )

    def to_json_dict(self) -> dict[str, Any]:
        """Return deterministic admission receipt fields."""
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "admitted": self.admitted,
            "template_id": self.template_id,
            "reason": self.reason,
            "missing_evidence": self.missing_evidence,
            "required_strategy": self.required_strategy.value,
            "evidence_refs": self.evidence_refs,
        }


class RepairTemplateRegistry:
    """Immutable domain/action index for repair admission templates."""

    def __init__(self, templates: Iterable[RepairTemplate]) -> None:
        template_tuple = tuple(templates)
        if not template_tuple:
            raise RepairTemplateRegistryError("repair template registry requires templates")
        by_key: dict[tuple[str, str], RepairTemplate] = {}
        by_id: dict[str, RepairTemplate] = {}
        for template in template_tuple:
            if template.template_key in by_key:
                raise RepairTemplateRegistryError(
                    f"duplicate repair template key: {template.template_key}"
                )
            if template.template_id in by_id:
                raise RepairTemplateRegistryError(
                    f"duplicate repair template id: {template.template_id}"
                )
            by_key[template.template_key] = template
            by_id[template.template_id] = template
        self._by_key = by_key
        self._by_id = by_id

    @property
    def template_count(self) -> int:
        return len(self._by_key)

    @classmethod
    def default_registry(cls) -> "RepairTemplateRegistry":
        """Build the canonical foundation-stage repair template registry."""
        return cls(
            (
                RepairTemplate(
                    template_id="repair-template.file.edit.v1",
                    domain="file",
                    action_type="edit",
                    effect_class=EffectClass.INTERNAL_VERSIONED,
                    reversibility_class=ReversibilityClass.VERSION_RESTORE,
                    template_kind=RepairTemplateKind.VERSION_RESTORE,
                    risk=RepairTemplateRisk.LOW,
                    required_strategy=RepairStrategy.VERSION_RESTORE,
                    snapshot_quality_minimum=SnapshotQuality.S3_VERSIONED,
                    rollback_capability_ref="capability://file.version_restore",
                    required_evidence=("before_hash", "version_id", "restore_pointer"),
                    forbidden_if_missing=("version_id", "restore_pointer"),
                ),
                RepairTemplate(
                    template_id="repair-template.email.draft_update.v1",
                    domain="email",
                    action_type="draft_update",
                    effect_class=EffectClass.INTERNAL_VERSIONED,
                    reversibility_class=ReversibilityClass.VERSION_RESTORE,
                    template_kind=RepairTemplateKind.VERSION_RESTORE,
                    risk=RepairTemplateRisk.MODERATE,
                    required_strategy=RepairStrategy.VERSION_RESTORE,
                    snapshot_quality_minimum=SnapshotQuality.S3_VERSIONED,
                    rollback_capability_ref="capability://email.restore_draft_version",
                    required_evidence=("draft_id", "before_hash", "version_id"),
                    forbidden_if_missing=("draft_id", "version_id"),
                ),
                RepairTemplate(
                    template_id="repair-template.email.send.v1",
                    domain="email",
                    action_type="send",
                    effect_class=EffectClass.USER_VISIBLE,
                    reversibility_class=ReversibilityClass.SEMANTIC_COMPENSATION,
                    template_kind=RepairTemplateKind.SEMANTIC_COMPENSATION,
                    risk=RepairTemplateRisk.HIGH,
                    required_strategy=RepairStrategy.SEMANTIC_COMPENSATION,
                    snapshot_quality_minimum=SnapshotQuality.S4_CAUSAL_WITH_EXTERNAL_IDS,
                    idempotency_required=True,
                    reconciliation_required=True,
                    external_confirmation_required=True,
                    compensation_capability_ref="capability://email.send_correction",
                    required_evidence=("message_id", "recipient_set", "idempotency_key"),
                    forbidden_if_missing=("recipient_set", "message_id"),
                ),
                RepairTemplate(
                    template_id="repair-template.github.pr_create.v1",
                    domain="github",
                    action_type="pr_create",
                    effect_class=EffectClass.EXTERNAL_MUTATION,
                    reversibility_class=ReversibilityClass.SEMANTIC_COMPENSATION,
                    template_kind=RepairTemplateKind.SEMANTIC_COMPENSATION,
                    risk=RepairTemplateRisk.MODERATE,
                    required_strategy=RepairStrategy.SEMANTIC_COMPENSATION,
                    snapshot_quality_minimum=SnapshotQuality.S4_CAUSAL_WITH_EXTERNAL_IDS,
                    idempotency_required=True,
                    reconciliation_required=True,
                    external_confirmation_required=True,
                    compensation_capability_ref="capability://github.close_or_update_pr",
                    required_evidence=("repo_ref", "branch_ref", "idempotency_key"),
                    forbidden_if_missing=("repo_ref", "branch_ref"),
                ),
                RepairTemplate(
                    template_id="repair-template.deployment.release.v1",
                    domain="deployment",
                    action_type="release",
                    effect_class=EffectClass.EXTERNAL_MUTATION,
                    reversibility_class=ReversibilityClass.VERSION_RESTORE,
                    template_kind=RepairTemplateKind.VERSION_RESTORE,
                    risk=RepairTemplateRisk.CRITICAL,
                    required_strategy=RepairStrategy.VERSION_RESTORE,
                    snapshot_quality_minimum=SnapshotQuality.S4_CAUSAL_WITH_EXTERNAL_IDS,
                    idempotency_required=True,
                    approval_required=True,
                    reconciliation_required=True,
                    external_confirmation_required=True,
                    rollback_capability_ref="capability://deployment.rollback_release",
                    required_evidence=(
                        "release_id",
                        "previous_version_id",
                        "health_baseline",
                        "idempotency_key",
                    ),
                    forbidden_if_missing=("previous_version_id", "health_baseline"),
                ),
                RepairTemplate(
                    template_id="repair-template.payment.charge.v1",
                    domain="payment",
                    action_type="charge",
                    effect_class=EffectClass.FINANCIAL_OR_LEGAL,
                    reversibility_class=ReversibilityClass.RECONCILE_REQUIRED,
                    template_kind=RepairTemplateKind.RECONCILIATION,
                    risk=RepairTemplateRisk.CRITICAL,
                    required_strategy=RepairStrategy.RECONCILE_THEN_DECIDE,
                    snapshot_quality_minimum=SnapshotQuality.S4_CAUSAL_WITH_EXTERNAL_IDS,
                    idempotency_required=True,
                    approval_required=True,
                    reconciliation_required=True,
                    external_confirmation_required=True,
                    required_evidence=(
                        "provider_charge_lookup",
                        "customer_authorization",
                        "idempotency_key",
                    ),
                    forbidden_if_missing=("provider_charge_lookup", "customer_authorization"),
                    residual_damage_policy="no_financial_success_claim_until_provider_reconciliation",
                ),
                RepairTemplate(
                    template_id="repair-template.secret.exposed.v1",
                    domain="secret",
                    action_type="exposed",
                    effect_class=EffectClass.PUBLIC_IRREVERSIBLE,
                    reversibility_class=ReversibilityClass.HUMAN_ESCALATION,
                    template_kind=RepairTemplateKind.QUARANTINE,
                    risk=RepairTemplateRisk.CRITICAL,
                    required_strategy=RepairStrategy.QUARANTINE,
                    snapshot_quality_minimum=SnapshotQuality.S1_PARTIAL,
                    idempotency_required=True,
                    approval_required=True,
                    reconciliation_required=True,
                    external_confirmation_required=True,
                    required_evidence=("exposure_ref", "rotation_plan", "containment_receipt"),
                    forbidden_if_missing=("rotation_plan", "containment_receipt"),
                    residual_damage_policy="irreversible_exposure_requires_rotation_and_escalation",
                ),
            )
        )

    def get_template(self, domain: str, action_type: str) -> RepairTemplate:
        key = (
            ensure_non_empty_text("domain", domain),
            ensure_non_empty_text("action_type", action_type),
        )
        template = self._by_key.get(key)
        if template is None:
            raise RepairTemplateRegistryError(f"unknown repair template: {key}")
        return template

    def evaluate(self, request: TemplateSelectionRequest) -> RepairTemplateSelection:
        """Evaluate request evidence against the matching repair template."""
        request_id = stable_identifier(
            "repair-template-request",
            {
                "domain": request.domain,
                "action_type": request.action_type,
                "effect_class": request.effect_class.value,
                "reversibility_class": request.reversibility_class.value,
                "evidence": request.available_evidence,
                "has_idempotency": request.has_idempotency_key,
                "snapshot_quality": int(request.snapshot_quality),
                "approval_present": request.approval_present,
                "external_confirmation_present": request.external_confirmation_present,
            },
        )
        template = self._by_key.get((request.domain, request.action_type))
        if template is None:
            return RepairTemplateSelection(
                request_id=request_id,
                status=RepairTemplateAdmissionStatus.TEMPLATE_MISSING,
                admitted=False,
                template_id=None,
                reason="repair_template_missing",
                missing_evidence=(),
                required_strategy=RepairStrategy.FORBID,
                evidence_refs=(),
            )

        if request.effect_class is not template.effect_class:
            return self._blocked(
                request_id=request_id,
                template=template,
                reason="effect_class_mismatch",
                missing=(),
                evidence=request.available_evidence,
            )
        if request.reversibility_class is not template.reversibility_class:
            return self._blocked(
                request_id=request_id,
                template=template,
                reason="reversibility_class_mismatch",
                missing=(),
                evidence=request.available_evidence,
            )
        if template.idempotency_required and not request.has_idempotency_key:
            return self._blocked(
                request_id=request_id,
                template=template,
                reason="idempotency_key_missing",
                missing=("idempotency_key",),
                evidence=request.available_evidence,
            )
        if request.snapshot_quality < template.snapshot_quality_minimum:
            return self._blocked(
                request_id=request_id,
                template=template,
                reason="snapshot_quality_insufficient",
                missing=(f"S{int(template.snapshot_quality_minimum)}_snapshot",),
                evidence=request.available_evidence,
            )

        available = set(request.available_evidence)
        missing = tuple(
            evidence
            for evidence in template.required_evidence
            if evidence not in available
        )
        if missing:
            return self._blocked(
                request_id=request_id,
                template=template,
                reason="required_evidence_missing",
                missing=missing,
                evidence=request.available_evidence,
            )
        forbidden_gaps = tuple(
            evidence
            for evidence in template.forbidden_if_missing
            if evidence not in available
        )
        if forbidden_gaps:
            return self._blocked(
                request_id=request_id,
                template=template,
                reason="forbidden_evidence_gap",
                missing=forbidden_gaps,
                evidence=request.available_evidence,
            )
        if template.approval_required and not request.approval_present:
            return RepairTemplateSelection(
                request_id=request_id,
                status=RepairTemplateAdmissionStatus.APPROVAL_REQUIRED,
                admitted=False,
                template_id=template.template_id,
                reason="approval_required",
                missing_evidence=("approval_ref",),
                required_strategy=template.required_strategy,
                evidence_refs=request.available_evidence,
            )
        if (
            template.external_confirmation_required
            and not request.external_confirmation_present
        ):
            return self._blocked(
                request_id=request_id,
                template=template,
                reason="external_confirmation_required",
                missing=("external_confirmation_ref",),
                evidence=request.available_evidence,
            )

        return RepairTemplateSelection(
            request_id=request_id,
            status=RepairTemplateAdmissionStatus.ADMITTED,
            admitted=True,
            template_id=template.template_id,
            reason="repair_template_admitted",
            missing_evidence=(),
            required_strategy=template.required_strategy,
            evidence_refs=request.available_evidence,
        )

    def read_model(self) -> dict[str, Any]:
        """Return deterministic operator projection for all templates."""
        templates = tuple(
            self._by_id[template_id].to_json_dict()
            for template_id in sorted(self._by_id)
        )
        risk_counts: dict[str, int] = {}
        effect_counts: dict[str, int] = {}
        for template in self._by_id.values():
            risk_counts[template.risk.value] = risk_counts.get(template.risk.value, 0) + 1
            effect_counts[template.effect_class.value] = (
                effect_counts.get(template.effect_class.value, 0) + 1
            )
        return {
            "template_count": self.template_count,
            "template_ids": tuple(sorted(self._by_id)),
            "template_keys": tuple(sorted(f"{domain}.{action}" for domain, action in self._by_key)),
            "risk_counts": dict(sorted(risk_counts.items())),
            "effect_counts": dict(sorted(effect_counts.items())),
            "templates": templates,
        }

    def _blocked(
        self,
        *,
        request_id: str,
        template: RepairTemplate,
        reason: str,
        missing: tuple[str, ...],
        evidence: tuple[str, ...],
    ) -> RepairTemplateSelection:
        return RepairTemplateSelection(
            request_id=request_id,
            status=RepairTemplateAdmissionStatus.BLOCKED,
            admitted=False,
            template_id=template.template_id,
            reason=reason,
            missing_evidence=missing,
            required_strategy=template.required_strategy,
            evidence_refs=evidence,
        )


def _coerce_snapshot_quality(value: SnapshotQuality | int) -> SnapshotQuality:
    if isinstance(value, SnapshotQuality):
        return value
    try:
        return SnapshotQuality(value)
    except ValueError as exc:
        raise RepairTemplateRegistryError("snapshot_quality must be S0 through S5") from exc


def _text_tuple(
    values: Iterable[str],
    field_name: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise RepairTemplateRegistryError(f"{field_name} must be an array")
    result = tuple(ensure_non_empty_text(field_name, value) for value in values)
    if not result and not allow_empty:
        raise RepairTemplateRegistryError(f"{field_name} must contain at least one item")
    return result
