"""Gateway domain operating pack compiler.

Purpose: package governed domain solutions from schemas, policies, workflows,
    connectors, evals, risk rules, approval roles, evidence exports, and views.
Governance scope: solution-pack completeness, certification evidence, activation
    blocking, and domain-specific operating model validation.
Dependencies: standard-library dataclasses, hashlib, and JSON serialization.
Invariants:
  - Operating packs are solution packages, not bypasses around capability governance.
  - Every pack declares schemas, policies, workflows, evals, evidence, and views.
  - Activation remains blocked until certification evidence is present.
  - High-risk packs must declare approval roles and recovery evidence exports.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Iterable


DOMAIN_PACKS = (
    "finance_ops",
    "customer_support",
    "compliance",
    "research",
    "healthcare_admin",
    "education",
    "manufacturing_ops",
)
CERTIFICATION_STATUSES = ("draft", "candidate", "certified", "suspended", "retired")
HIGH_RISK_DOMAINS = frozenset({"finance_ops", "compliance", "healthcare_admin", "manufacturing_ops"})


@dataclass(frozen=True, slots=True)
class DomainOperatingPackSpec:
    """Source specification for one domain operating pack."""

    pack_id: str
    domain: str
    version: str
    owner_team: str
    schemas: tuple[str, ...]
    policies: tuple[str, ...]
    workflows: tuple[str, ...]
    connectors: tuple[str, ...]
    evals: tuple[str, ...]
    risk_rules: tuple[str, ...]
    approval_roles: tuple[str, ...]
    evidence_exports: tuple[str, ...]
    dashboard_views: tuple[str, ...]
    certification_status: str = "candidate"
    certification_evidence_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.pack_id:
            raise ValueError("pack_id_required")
        if self.domain not in DOMAIN_PACKS:
            raise ValueError("domain_invalid")
        if not self.version:
            raise ValueError("version_required")
        if not self.owner_team:
            raise ValueError("owner_team_required")
        if self.certification_status not in CERTIFICATION_STATUSES:
            raise ValueError("certification_status_invalid")
        for field_name in (
            "schemas",
            "policies",
            "workflows",
            "evals",
            "risk_rules",
            "evidence_exports",
            "dashboard_views",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name}_required")
        for field_name in (
            "schemas",
            "policies",
            "workflows",
            "connectors",
            "evals",
            "risk_rules",
            "approval_roles",
            "evidence_exports",
            "dashboard_views",
            "certification_evidence_refs",
        ):
            object.__setattr__(self, field_name, tuple(str(item) for item in getattr(self, field_name)))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class DomainOperatingPack:
    """Compiled domain operating pack proposal."""

    pack_id: str
    domain: str
    version: str
    owner_team: str
    schemas: tuple[str, ...]
    policies: tuple[str, ...]
    workflows: tuple[str, ...]
    connectors: tuple[str, ...]
    evals: tuple[str, ...]
    risk_rules: tuple[str, ...]
    approval_roles: tuple[str, ...]
    evidence_exports: tuple[str, ...]
    dashboard_views: tuple[str, ...]
    certification_status: str
    certification_evidence_refs: tuple[str, ...]
    activation_blocked: bool
    blocked_reasons: tuple[str, ...]
    pack_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "schemas",
            "policies",
            "workflows",
            "connectors",
            "evals",
            "risk_rules",
            "approval_roles",
            "evidence_exports",
            "dashboard_views",
            "certification_evidence_refs",
            "blocked_reasons",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if self.certification_status not in CERTIFICATION_STATUSES:
            raise ValueError("certification_status_invalid")
        if not self.activation_blocked and self.certification_status != "certified":
            raise ValueError("activation_requires_certified_pack")


@dataclass(frozen=True, slots=True)
class DomainOperatingPackValidation:
    """Validation result for one operating pack."""

    accepted: bool
    reason: str
    errors: tuple[str, ...]
    pack_id: str = ""
    pack_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "errors", tuple(self.errors))


@dataclass(frozen=True, slots=True)
class DomainOperatingPackCatalog:
    """Catalog of compiled operating packs."""

    catalog_id: str
    packs: tuple[DomainOperatingPack, ...]
    catalog_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "packs", tuple(self.packs))
        if not self.catalog_id:
            raise ValueError("catalog_id_required")


class DomainOperatingPackCompiler:
    """Compile and validate domain operating packs."""

    def compile(self, spec: DomainOperatingPackSpec) -> DomainOperatingPack:
        """Compile a source spec into an activation-blocked operating pack."""
        errors = _validation_errors(spec)
        blocked_reasons = _activation_blockers(spec, errors)
        pack = DomainOperatingPack(
            pack_id=spec.pack_id,
            domain=spec.domain,
            version=spec.version,
            owner_team=spec.owner_team,
            schemas=spec.schemas,
            policies=spec.policies,
            workflows=spec.workflows,
            connectors=spec.connectors,
            evals=spec.evals,
            risk_rules=spec.risk_rules,
            approval_roles=spec.approval_roles,
            evidence_exports=spec.evidence_exports,
            dashboard_views=spec.dashboard_views,
            certification_status=spec.certification_status,
            certification_evidence_refs=spec.certification_evidence_refs,
            activation_blocked=bool(blocked_reasons),
            blocked_reasons=tuple(blocked_reasons),
            metadata={"compiled_from": "domain_operating_pack_spec", **spec.metadata},
        )
        return _stamp_pack(pack)

    def validate(self, pack: DomainOperatingPack) -> DomainOperatingPackValidation:
        """Validate a compiled pack before catalog publication."""
        errors = _pack_errors(pack)
        if errors:
            return DomainOperatingPackValidation(False, "domain_operating_pack_invalid", tuple(errors), pack.pack_id, pack.pack_hash)
        return DomainOperatingPackValidation(True, "domain_operating_pack_ready", (), pack.pack_id, pack.pack_hash)

    def catalog(self, specs: Iterable[DomainOperatingPackSpec]) -> DomainOperatingPackCatalog:
        """Compile specs into a deterministic catalog."""
        packs = tuple(sorted((self.compile(spec) for spec in specs), key=lambda pack: pack.pack_id))
        catalog = DomainOperatingPackCatalog(
            catalog_id=f"domain-operating-pack-catalog-{_hash_payload({'pack_ids': [pack.pack_id for pack in packs]})[:16]}",
            packs=packs,
        )
        return _stamp_catalog(catalog)


def builtin_domain_operating_pack_specs() -> tuple[DomainOperatingPackSpec, ...]:
    """Return default solution-pack specifications."""
    return (
        _spec("finance-ops-pack", "finance_ops", ("invoice.approval", "payment.guard", "budget.enforcement", "duplicate.detect"), ("bank_change_hold", "fresh_approval", "duplicate_invoice_block"), ("finance_admin", "manager")),
        _spec("customer-support-pack", "customer_support", ("ticket.triage", "sla.track", "refund.review", "escalation.route"), ("refund_threshold", "sla_breach"), ("support_lead",)),
        _spec("compliance-pack", "compliance", ("evidence.bundle", "audit.export", "policy.exception", "control.review"), ("exception_expiry", "dual_control"), ("compliance_officer", "legal_reviewer")),
        _spec("research-pack", "research", ("source.track", "claim.graph", "literature.review", "experiment.log"), ("source_freshness", "claim_contradiction"), ("research_lead",)),
        _spec("healthcare-admin-pack", "healthcare_admin", ("intake.summary", "appointment.support", "privacy.gate", "escalation.route"), ("privacy_gate", "human_review"), ("care_admin", "privacy_officer")),
        _spec("education-pack", "education", ("lesson.plan", "assessment.feedback", "learning.memory", "tutoring.support"), ("minor_safety", "assessment_review"), ("educator",)),
        _spec("manufacturing-ops-pack", "manufacturing_ops", ("sop.assist", "incident.report", "maintenance.workflow", "quality.check"), ("safety_envelope", "operator_override"), ("plant_supervisor", "safety_officer")),
    )


def _spec(
    pack_id: str,
    domain: str,
    workflows: tuple[str, ...],
    risk_rules: tuple[str, ...],
    approval_roles: tuple[str, ...],
) -> DomainOperatingPackSpec:
    return DomainOperatingPackSpec(
        pack_id=pack_id,
        domain=domain,
        version="1.0.0",
        owner_team=f"{domain}_ops",
        schemas=tuple(f"schemas/{domain}/{workflow}.schema.json" for workflow in workflows),
        policies=("tenant_boundary", "policy_gate", "budget_gate", "terminal_closure"),
        workflows=workflows,
        connectors=(f"{domain}.primary_connector",),
        evals=("tenant_boundary", "approval_required", "prompt_injection", "evidence_integrity"),
        risk_rules=risk_rules,
        approval_roles=approval_roles,
        evidence_exports=("audit_bundle", "receipt_export", "terminal_certificate_export"),
        dashboard_views=("operator_queue", "risk_register", "evidence_export"),
        certification_status="candidate",
    )


def _validation_errors(spec: DomainOperatingPackSpec) -> list[str]:
    errors: list[str] = []
    if spec.domain in HIGH_RISK_DOMAINS and not spec.approval_roles:
        errors.append("high_risk_domain_requires_approval_roles")
    if spec.domain in HIGH_RISK_DOMAINS and "terminal_certificate_export" not in spec.evidence_exports:
        errors.append("high_risk_domain_requires_terminal_certificate_export")
    if "tenant_boundary" not in spec.policies:
        errors.append("tenant_boundary_policy_required")
    if "approval_required" not in spec.evals:
        errors.append("approval_required_eval_required")
    if spec.certification_status == "certified" and not spec.certification_evidence_refs:
        errors.append("certified_pack_requires_certification_evidence")
    return errors


def _activation_blockers(spec: DomainOperatingPackSpec, errors: list[str]) -> list[str]:
    blockers = list(errors)
    if spec.certification_status != "certified":
        blockers.append("pack_not_certified")
    if not spec.certification_evidence_refs:
        blockers.append("certification_evidence_missing")
    return tuple(dict.fromkeys(blockers))


def _pack_errors(pack: DomainOperatingPack) -> list[str]:
    errors: list[str] = []
    if not pack.pack_hash:
        errors.append("pack_hash_required")
    if not pack.schemas or not pack.policies or not pack.workflows:
        errors.append("core_artifacts_required")
    if not pack.evidence_exports or not pack.dashboard_views:
        errors.append("evidence_and_views_required")
    if pack.domain in HIGH_RISK_DOMAINS and not pack.approval_roles:
        errors.append("high_risk_domain_requires_approval_roles")
    if not pack.activation_blocked and pack.certification_status != "certified":
        errors.append("uncertified_pack_must_remain_blocked")
    return errors


def _stamp_pack(pack: DomainOperatingPack) -> DomainOperatingPack:
    payload = asdict(replace(pack, pack_hash=""))
    return replace(pack, pack_hash=_hash_payload(payload))


def _stamp_catalog(catalog: DomainOperatingPackCatalog) -> DomainOperatingPackCatalog:
    payload = asdict(replace(catalog, catalog_hash=""))
    return replace(catalog, catalog_hash=_hash_payload(payload))


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
