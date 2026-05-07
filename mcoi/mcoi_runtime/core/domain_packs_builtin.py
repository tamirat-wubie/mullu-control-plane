"""Purpose: built-in domain pack definitions.
Governance scope: pre-configured domain packs for software delivery,
    support/ticketing, and internal operations.
Dependencies: domain_pack contracts, DomainPackEngine.
Invariants:
  - Each pack is self-contained with all rules/profiles.
  - Packs are registered but NOT activated by default.
  - Deterministic IDs for all records.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..contracts.domain_pack import (
    DomainBenchmarkProfile,
    DomainEscalationProfile,
    DomainExtractionRule,
    DomainMemoryRule,
    DomainPackDescriptor,
    DomainPackStatus,
    DomainRoutingRule,
    DomainRuleKind,
    DomainSimulationProfile,
    DomainUtilityProfile,
    DomainVocabularyEntry,
    PackScope,
)
from .domain_pack import DomainPackEngine


NOW = "2026-03-20T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Software Delivery Pack
# ---------------------------------------------------------------------------


def register_software_delivery_pack(
    engine: DomainPackEngine,
    *,
    scope: PackScope = PackScope.GLOBAL,
    scope_ref_id: str = "",
    activate: bool = False,
) -> DomainPackDescriptor:
    """Register the software delivery domain pack."""
    pack = DomainPackDescriptor(
        pack_id="pack-software-delivery",
        domain_name="software-delivery",
        version="1.0.0",
        status=DomainPackStatus.DRAFT,
        scope=scope,
        scope_ref_id=scope_ref_id,
        description="Software delivery lifecycle: deploy, patch, rollback, build, test, incident",
        tags=("software", "delivery", "devops"),
        created_at=NOW,
    )
    engine.register_pack(pack)

    # Extraction rules
    for i, (pattern, ctype) in enumerate([
        (r"\b(deploy|deployment)\b", "delivery"),
        (r"\b(patch|hotfix)\b", "delivery"),
        (r"\b(rollback|revert)\b", "escalation"),
        (r"\b(build|compile)\b", "task"),
        (r"\b(test|testing)\b", "task"),
        (r"\b(incident|outage)\b", "escalation"),
    ]):
        engine.add_extraction_rule(DomainExtractionRule(
            rule_id=f"swd-extr-{i}",
            pack_id="pack-software-delivery",
            pattern=pattern,
            commitment_type=ctype,
            priority=10 + i,
            description="Software delivery extraction rule",
            created_at=NOW,
        ))

    # Routing rules
    for i, (source, target, channel) in enumerate([
        ("developer", "ops", "chat"),
        ("developer", "release", "email"),
        ("ops", "reviewer", "chat"),
        ("ops", "oncall", "pager"),
    ]):
        engine.add_routing_rule(DomainRoutingRule(
            rule_id=f"swd-route-{i}",
            pack_id="pack-software-delivery",
            source_role=source,
            target_role=target,
            channel_type=channel,
            priority=10 + i,
            description="Software delivery routing rule",
            created_at=NOW,
        ))

    # Simulation profile
    engine.add_simulation_profile(DomainSimulationProfile(
        profile_id="swd-sim-1",
        pack_id="pack-software-delivery",
        risk_weights={
            "deployment": 0.8,
            "rollback": 0.6,
            "build": 0.3,
            "test": 0.2,
        },
        default_risk_level="medium",
        scenario_templates=("deployment-risk", "rollback-impact"),
        description="Deployment risk weighting",
        created_at=NOW,
    ))

    # Utility profile
    engine.add_utility_profile(DomainUtilityProfile(
        profile_id="swd-util-1",
        pack_id="pack-software-delivery",
        bias_weights={
            "speed": 0.4,
            "safety": 0.6,
        },
        default_tradeoff_direction="safety",
        description="Speed vs safety bias for delivery",
        created_at=NOW,
    ))

    # Escalation profile
    engine.add_escalation_profile(DomainEscalationProfile(
        profile_id="swd-esc-1",
        pack_id="pack-software-delivery",
        escalation_roles=("oncall", "ops-lead", "engineering-manager"),
        escalation_mode="sequential",
        timeout_seconds=300,
        description="Pager/oncall escalation path",
        created_at=NOW,
    ))

    # Vocabulary
    for i, (term, canonical, aliases) in enumerate([
        ("deploy", "deployment", ("push", "ship", "release")),
        ("rollback", "rollback", ("revert", "undo deploy")),
        ("incident", "incident", ("outage", "P0", "sev1")),
    ]):
        engine.add_vocabulary_entry(DomainVocabularyEntry(
            entry_id=f"swd-vocab-{i}",
            pack_id="pack-software-delivery",
            term=term,
            canonical_form=canonical,
            aliases=aliases,
            rule_kind=DomainRuleKind.EXTRACTION,
            created_at=NOW,
        ))

    if activate:
        engine.activate_pack("pack-software-delivery")

    return engine.get_pack("pack-software-delivery")


# ---------------------------------------------------------------------------
# Support / Ticketing Pack
# ---------------------------------------------------------------------------


def register_support_pack(
    engine: DomainPackEngine,
    *,
    scope: PackScope = PackScope.GLOBAL,
    scope_ref_id: str = "",
    activate: bool = False,
) -> DomainPackDescriptor:
    """Register the support/ticketing domain pack."""
    pack = DomainPackDescriptor(
        pack_id="pack-support-ticketing",
        domain_name="support-ticketing",
        version="1.0.0",
        status=DomainPackStatus.DRAFT,
        scope=scope,
        scope_ref_id=scope_ref_id,
        description="Customer support: issue tracking, severity, SLA, follow-up",
        tags=("support", "ticketing", "customer"),
        created_at=NOW,
    )
    engine.register_pack(pack)

    # Extraction rules
    for i, (pattern, ctype) in enumerate([
        (r"\b(customer\s+issue|ticket|bug\s+report)\b", "task"),
        (r"\b(severity|sev\s*\d|priority\s*\d)\b", "deadline"),
        (r"\b(SLA|service\s+level)\b", "deadline"),
        (r"\b(follow[\s-]?up|check\s+back)\b", "follow_up"),
    ]):
        engine.add_extraction_rule(DomainExtractionRule(
            rule_id=f"sup-extr-{i}",
            pack_id="pack-support-ticketing",
            pattern=pattern,
            commitment_type=ctype,
            priority=10 + i,
            description="Support extraction rule",
            created_at=NOW,
        ))

    # Routing rules
    for i, (source, target, channel) in enumerate([
        ("customer", "support-queue", "email"),
        ("support", "escalation-queue", "chat"),
    ]):
        engine.add_routing_rule(DomainRoutingRule(
            rule_id=f"sup-route-{i}",
            pack_id="pack-support-ticketing",
            source_role=source,
            target_role=target,
            channel_type=channel,
            priority=10 + i,
            description="Support routing rule",
            created_at=NOW,
        ))

    # Memory rules
    for i, (mtype, trust, decay, ttl) in enumerate([
        ("observation", "verified", "ttl", 86400 * 30),
        ("outcome", "verified", "ttl", 86400 * 90),
    ]):
        engine.add_memory_rule(DomainMemoryRule(
            rule_id=f"sup-mem-{i}",
            pack_id="pack-support-ticketing",
            memory_type=mtype,
            trust_level=trust,
            decay_mode=decay,
            ttl_seconds=ttl,
            description="Support memory rule",
            created_at=NOW,
        ))

    # Benchmark profile
    engine.add_benchmark_profile(DomainBenchmarkProfile(
        profile_id="sup-bench-1",
        pack_id="pack-support-ticketing",
        suite_ids=("response-time", "resolution-quality"),
        adversarial_categories=("ambiguous-severity", "sla-edge-cases"),
        pass_thresholds={"response_time_p95": 0.95, "resolution_rate": 0.85},
        description="Support response time and resolution quality benchmarks",
        created_at=NOW,
    ))

    # Escalation profile
    engine.add_escalation_profile(DomainEscalationProfile(
        profile_id="sup-esc-1",
        pack_id="pack-support-ticketing",
        escalation_roles=("support-lead", "support-manager", "vp-support"),
        escalation_mode="sequential",
        timeout_seconds=600,
        description="Support escalation chain",
        created_at=NOW,
    ))

    if activate:
        engine.activate_pack("pack-support-ticketing")

    return engine.get_pack("pack-support-ticketing")


# ---------------------------------------------------------------------------
# Internal Operations Pack
# ---------------------------------------------------------------------------


def register_internal_ops_pack(
    engine: DomainPackEngine,
    *,
    scope: PackScope = PackScope.GLOBAL,
    scope_ref_id: str = "",
    activate: bool = False,
) -> DomainPackDescriptor:
    """Register the internal operations domain pack."""
    pack = DomainPackDescriptor(
        pack_id="pack-internal-ops",
        domain_name="internal-operations",
        version="1.0.0",
        status=DomainPackStatus.DRAFT,
        scope=scope,
        scope_ref_id=scope_ref_id,
        description="Internal ops: approvals, requests, owner assignment, due dates",
        tags=("internal", "operations", "governance"),
        created_at=NOW,
    )
    engine.register_pack(pack)

    # Extraction rules
    for i, (pattern, ctype) in enumerate([
        (r"\b(approv(?:al|ed?)|sign[\s-]?off)\b", "approval"),
        (r"\b(request|requisition)\b", "task"),
        (r"\b(assign(?:ed)?\s+to|owner)\b", "task"),
        (r"\b(due\s+(?:date|by)|deadline)\b", "deadline"),
    ]):
        engine.add_extraction_rule(DomainExtractionRule(
            rule_id=f"iop-extr-{i}",
            pack_id="pack-internal-ops",
            pattern=pattern,
            commitment_type=ctype,
            priority=10 + i,
            description="Internal ops extraction rule",
            created_at=NOW,
        ))

    # Routing rules — governance-heavy
    for i, (source, target, channel) in enumerate([
        ("employee", "manager", "email"),
        ("manager", "ops", "chat"),
        ("ops", "admin", "email"),
        ("admin", "legal", "email"),
    ]):
        engine.add_routing_rule(DomainRoutingRule(
            rule_id=f"iop-route-{i}",
            pack_id="pack-internal-ops",
            source_role=source,
            target_role=target,
            channel_type=channel,
            priority=10 + i,
            description="Internal ops routing rule",
            created_at=NOW,
        ))

    # Governance extraction rules (approval/review thresholds)
    engine.add_extraction_rule(DomainExtractionRule(
        rule_id="iop-extr-gov-0",
        pack_id="pack-internal-ops",
        pattern=r"\b(requires?\s+approval|needs?\s+sign[\s-]?off)\b",
        commitment_type="approval",
        priority=20,
        description="Governance: requires approval",
        created_at=NOW,
    ))
    engine.add_extraction_rule(DomainExtractionRule(
        rule_id="iop-extr-gov-1",
        pack_id="pack-internal-ops",
        pattern=r"\b(review\s+required|peer\s+review)\b",
        commitment_type="review",
        priority=20,
        description="Governance: review required",
        created_at=NOW,
    ))

    # Memory rules — policy-bound records
    engine.add_memory_rule(DomainMemoryRule(
        rule_id="iop-mem-0",
        pack_id="pack-internal-ops",
        memory_type="decision",
        trust_level="verified",
        decay_mode="none",
        ttl_seconds=86400 * 365,
        promotion_eligible=True,
        description="Policy-bound decision records (long retention)",
        created_at=NOW,
    ))

    if activate:
        engine.activate_pack("pack-internal-ops")

    return engine.get_pack("pack-internal-ops")


# ---------------------------------------------------------------------------
# Convenience: register all built-in packs
# ---------------------------------------------------------------------------


def register_all_builtin_packs(
    engine: DomainPackEngine,
    *,
    activate: bool = False,
) -> tuple[DomainPackDescriptor, ...]:
    """Register all three built-in domain packs."""
    packs = (
        register_software_delivery_pack(engine, activate=activate),
        register_support_pack(engine, activate=activate),
        register_internal_ops_pack(engine, activate=activate),
    )
    return packs
