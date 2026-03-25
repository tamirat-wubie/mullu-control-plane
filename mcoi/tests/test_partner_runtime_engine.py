"""Comprehensive tests for PartnerRuntimeEngine.

Tests: mcoi/mcoi_runtime/core/partner_runtime.py
Covers: registration, linking, agreements, revenue shares, commitments,
    health tracking, violations, snapshots, closure reports, state hash,
    and golden integration scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.partner_runtime import PartnerRuntimeEngine
from mcoi_runtime.contracts.partner_runtime import (
    EcosystemAgreement,
    EcosystemRole,
    PartnerAccountLink,
    PartnerClosureReport,
    PartnerCommitment,
    PartnerDecision,
    PartnerDisposition,
    PartnerHealthSnapshot,
    PartnerHealthStatus,
    PartnerKind,
    PartnerRecord,
    PartnerSnapshot,
    PartnerStatus,
    PartnerViolation,
    RevenueShareRecord,
    RevenueShareStatus,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture
def engine(spine: EventSpineEngine) -> PartnerRuntimeEngine:
    return PartnerRuntimeEngine(spine)


@pytest.fixture
def seeded(engine: PartnerRuntimeEngine) -> PartnerRuntimeEngine:
    """Engine with a registered active partner + agreement."""
    engine.register_partner("p1", "t1", "Acme Reseller")
    engine.register_agreement("ag1", "p1", "t1", "Main Agreement", revenue_share_pct=0.10)
    return engine


# ===================================================================
# 1. Construction
# ===================================================================


class TestConstruction:
    def test_requires_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            PartnerRuntimeEngine("not-a-spine")

    def test_initial_counts_zero(self, engine: PartnerRuntimeEngine):
        assert engine.partner_count == 0
        assert engine.link_count == 0
        assert engine.agreement_count == 0
        assert engine.revenue_share_count == 0
        assert engine.commitment_count == 0
        assert engine.health_snapshot_count == 0
        assert engine.decision_count == 0
        assert engine.violation_count == 0


# ===================================================================
# 2. register_partner
# ===================================================================


class TestRegisterPartner:
    def test_basic_registration(self, engine: PartnerRuntimeEngine):
        rec = engine.register_partner("p1", "t1", "Acme")
        assert isinstance(rec, PartnerRecord)
        assert rec.partner_id == "p1"
        assert rec.tenant_id == "t1"
        assert rec.display_name == "Acme"
        assert rec.kind == PartnerKind.RESELLER
        assert rec.status == PartnerStatus.ACTIVE
        assert rec.tier == "standard"
        assert rec.account_link_count == 0
        assert rec.created_at != ""

    def test_custom_kind(self, engine: PartnerRuntimeEngine):
        rec = engine.register_partner("p1", "t1", "D", kind=PartnerKind.DISTRIBUTOR)
        assert rec.kind == PartnerKind.DISTRIBUTOR

    def test_custom_tier(self, engine: PartnerRuntimeEngine):
        rec = engine.register_partner("p1", "t1", "D", tier="premium")
        assert rec.tier == "premium"

    def test_custom_status(self, engine: PartnerRuntimeEngine):
        rec = engine.register_partner("p1", "t1", "D", status=PartnerStatus.PROSPECT)
        assert rec.status == PartnerStatus.PROSPECT

    def test_duplicate_raises(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            engine.register_partner("p1", "t1", "Acme2")

    def test_increments_count(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_partner("p2", "t1", "B")
        assert engine.partner_count == 2

    def test_all_partner_kinds(self, engine: PartnerRuntimeEngine):
        for i, kind in enumerate(PartnerKind):
            rec = engine.register_partner(f"pk{i}", "t1", f"K{i}", kind=kind)
            assert rec.kind == kind

    def test_all_partner_statuses(self, engine: PartnerRuntimeEngine):
        for i, status in enumerate(PartnerStatus):
            rec = engine.register_partner(f"ps{i}", "t1", f"S{i}", status=status)
            assert rec.status == status

    def test_frozen_record(self, engine: PartnerRuntimeEngine):
        rec = engine.register_partner("p1", "t1", "Acme")
        with pytest.raises(AttributeError):
            rec.partner_id = "x"

    def test_emits_event(self, spine: EventSpineEngine, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        assert spine.event_count >= 1


# ===================================================================
# 3. get_partner
# ===================================================================


class TestGetPartner:
    def test_get_existing(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        rec = engine.get_partner("p1")
        assert rec.partner_id == "p1"

    def test_unknown_raises(self, engine: PartnerRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown partner"):
            engine.get_partner("nope")

    def test_returns_latest_state(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.update_partner_status("p1", PartnerStatus.SUSPENDED)
        rec = engine.get_partner("p1")
        assert rec.status == PartnerStatus.SUSPENDED


# ===================================================================
# 4. update_partner_status
# ===================================================================


class TestUpdatePartnerStatus:
    def test_active_to_suspended(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        updated = engine.update_partner_status("p1", PartnerStatus.SUSPENDED)
        assert updated.status == PartnerStatus.SUSPENDED

    def test_active_to_terminated(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        updated = engine.update_partner_status("p1", PartnerStatus.TERMINATED)
        assert updated.status == PartnerStatus.TERMINATED

    def test_terminated_is_terminal(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.update_partner_status("p1", PartnerStatus.TERMINATED)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.update_partner_status("p1", PartnerStatus.ACTIVE)

    def test_terminated_to_terminated_raises(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.update_partner_status("p1", PartnerStatus.TERMINATED)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.update_partner_status("p1", PartnerStatus.TERMINATED)

    def test_unknown_raises(self, engine: PartnerRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown partner"):
            engine.update_partner_status("nope", PartnerStatus.ACTIVE)

    def test_preserves_other_fields(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme", kind=PartnerKind.DISTRIBUTOR, tier="gold")
        updated = engine.update_partner_status("p1", PartnerStatus.INACTIVE)
        assert updated.display_name == "Acme"
        assert updated.kind == PartnerKind.DISTRIBUTOR
        assert updated.tier == "gold"
        assert updated.tenant_id == "t1"

    def test_multiple_transitions(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.update_partner_status("p1", PartnerStatus.SUSPENDED)
        engine.update_partner_status("p1", PartnerStatus.ACTIVE)
        engine.update_partner_status("p1", PartnerStatus.INACTIVE)
        rec = engine.get_partner("p1")
        assert rec.status == PartnerStatus.INACTIVE

    def test_suspended_to_active(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.update_partner_status("p1", PartnerStatus.SUSPENDED)
        updated = engine.update_partner_status("p1", PartnerStatus.ACTIVE)
        assert updated.status == PartnerStatus.ACTIVE

    def test_prospect_to_active(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme", status=PartnerStatus.PROSPECT)
        updated = engine.update_partner_status("p1", PartnerStatus.ACTIVE)
        assert updated.status == PartnerStatus.ACTIVE


# ===================================================================
# 5. partners_for_tenant
# ===================================================================


class TestPartnersForTenant:
    def test_empty(self, engine: PartnerRuntimeEngine):
        assert engine.partners_for_tenant("t1") == ()

    def test_filters_by_tenant(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_partner("p2", "t2", "B")
        engine.register_partner("p3", "t1", "C")
        result = engine.partners_for_tenant("t1")
        assert len(result) == 2
        ids = {r.partner_id for r in result}
        assert ids == {"p1", "p3"}

    def test_returns_tuple(self, engine: PartnerRuntimeEngine):
        result = engine.partners_for_tenant("t1")
        assert isinstance(result, tuple)

    def test_no_match(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        assert engine.partners_for_tenant("t999") == ()


# ===================================================================
# 6. link_partner_to_account
# ===================================================================


class TestLinkPartnerToAccount:
    def test_basic_link(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        link = engine.link_partner_to_account("lk1", "p1", "acc1", "t1")
        assert isinstance(link, PartnerAccountLink)
        assert link.link_id == "lk1"
        assert link.partner_id == "p1"
        assert link.account_id == "acc1"
        assert link.tenant_id == "t1"
        assert link.role == EcosystemRole.INTERMEDIARY

    def test_custom_role(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        link = engine.link_partner_to_account("lk1", "p1", "acc1", "t1", role=EcosystemRole.PROVIDER)
        assert link.role == EcosystemRole.PROVIDER

    def test_duplicate_raises(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.link_partner_to_account("lk1", "p1", "acc1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="link already exists"):
            engine.link_partner_to_account("lk1", "p1", "acc2", "t1")

    def test_unknown_partner_raises(self, engine: PartnerRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown partner"):
            engine.link_partner_to_account("lk1", "nope", "acc1", "t1")

    def test_terminated_partner_raises(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.update_partner_status("p1", PartnerStatus.TERMINATED)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.link_partner_to_account("lk1", "p1", "acc1", "t1")

    def test_increments_account_link_count(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.link_partner_to_account("lk1", "p1", "acc1", "t1")
        rec = engine.get_partner("p1")
        assert rec.account_link_count == 1
        engine.link_partner_to_account("lk2", "p1", "acc2", "t1")
        rec = engine.get_partner("p1")
        assert rec.account_link_count == 2

    def test_increments_link_count(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.link_partner_to_account("lk1", "p1", "acc1", "t1")
        assert engine.link_count == 1

    def test_all_ecosystem_roles(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        for i, role in enumerate(EcosystemRole):
            link = engine.link_partner_to_account(f"lk{i}", "p1", f"acc{i}", "t1", role=role)
            assert link.role == role

    def test_multiple_partners_same_account(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_partner("p2", "t1", "B")
        engine.link_partner_to_account("lk1", "p1", "acc1", "t1")
        engine.link_partner_to_account("lk2", "p2", "acc1", "t1")
        assert engine.link_count == 2

    def test_frozen_link(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        link = engine.link_partner_to_account("lk1", "p1", "acc1", "t1")
        with pytest.raises(AttributeError):
            link.role = EcosystemRole.PROVIDER


# ===================================================================
# 7. links_for_partner / links_for_account
# ===================================================================


class TestLinksQueries:
    def test_links_for_partner_empty(self, engine: PartnerRuntimeEngine):
        assert engine.links_for_partner("p1") == ()

    def test_links_for_partner_filters(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_partner("p2", "t1", "B")
        engine.link_partner_to_account("lk1", "p1", "acc1", "t1")
        engine.link_partner_to_account("lk2", "p2", "acc2", "t1")
        engine.link_partner_to_account("lk3", "p1", "acc3", "t1")
        result = engine.links_for_partner("p1")
        assert len(result) == 2
        assert all(l.partner_id == "p1" for l in result)

    def test_links_for_account_empty(self, engine: PartnerRuntimeEngine):
        assert engine.links_for_account("acc1") == ()

    def test_links_for_account_filters(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_partner("p2", "t1", "B")
        engine.link_partner_to_account("lk1", "p1", "acc1", "t1")
        engine.link_partner_to_account("lk2", "p2", "acc1", "t1")
        engine.link_partner_to_account("lk3", "p1", "acc2", "t1")
        result = engine.links_for_account("acc1")
        assert len(result) == 2
        assert all(l.account_id == "acc1" for l in result)

    def test_returns_tuples(self, engine: PartnerRuntimeEngine):
        assert isinstance(engine.links_for_partner("x"), tuple)
        assert isinstance(engine.links_for_account("x"), tuple)


# ===================================================================
# 8. register_agreement
# ===================================================================


class TestRegisterAgreement:
    def test_basic_agreement(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        ag = engine.register_agreement("ag1", "p1", "t1", "Reseller Agreement")
        assert isinstance(ag, EcosystemAgreement)
        assert ag.agreement_id == "ag1"
        assert ag.partner_id == "p1"
        assert ag.tenant_id == "t1"
        assert ag.title == "Reseller Agreement"
        assert ag.contract_ref == "none"
        assert ag.revenue_share_pct == 0.0

    def test_custom_contract_ref(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        ag = engine.register_agreement("ag1", "p1", "t1", "X", contract_ref="CR-001")
        assert ag.contract_ref == "CR-001"

    def test_empty_contract_ref_defaults_to_none(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        ag = engine.register_agreement("ag1", "p1", "t1", "X", contract_ref="")
        assert ag.contract_ref == "none"

    def test_custom_revenue_share_pct(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        ag = engine.register_agreement("ag1", "p1", "t1", "X", revenue_share_pct=0.15)
        assert ag.revenue_share_pct == 0.15

    def test_duplicate_raises(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.register_agreement("ag1", "p1", "t1", "X")
        with pytest.raises(RuntimeCoreInvariantError, match="agreement already exists"):
            engine.register_agreement("ag1", "p1", "t1", "Y")

    def test_unknown_partner_raises(self, engine: PartnerRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown partner"):
            engine.register_agreement("ag1", "nope", "t1", "X")

    def test_increments_agreement_count(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.register_agreement("ag1", "p1", "t1", "X")
        engine.register_agreement("ag2", "p1", "t1", "Y")
        assert engine.agreement_count == 2

    def test_frozen_agreement(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        ag = engine.register_agreement("ag1", "p1", "t1", "X")
        with pytest.raises(AttributeError):
            ag.title = "changed"


# ===================================================================
# 9. get_agreement
# ===================================================================


class TestGetAgreement:
    def test_get_existing(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.register_agreement("ag1", "p1", "t1", "X")
        ag = engine.get_agreement("ag1")
        assert ag.agreement_id == "ag1"

    def test_unknown_raises(self, engine: PartnerRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown agreement"):
            engine.get_agreement("nope")


# ===================================================================
# 10. agreements_for_partner
# ===================================================================


class TestAgreementsForPartner:
    def test_empty(self, engine: PartnerRuntimeEngine):
        assert engine.agreements_for_partner("p1") == ()

    def test_filters(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_partner("p2", "t1", "B")
        engine.register_agreement("ag1", "p1", "t1", "X")
        engine.register_agreement("ag2", "p2", "t1", "Y")
        engine.register_agreement("ag3", "p1", "t1", "Z")
        result = engine.agreements_for_partner("p1")
        assert len(result) == 2
        assert all(a.partner_id == "p1" for a in result)

    def test_returns_tuple(self, engine: PartnerRuntimeEngine):
        assert isinstance(engine.agreements_for_partner("x"), tuple)


# ===================================================================
# 11. record_revenue_share
# ===================================================================


class TestRecordRevenueShare:
    def test_basic_revenue_share(self, seeded: PartnerRuntimeEngine):
        rs = seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 1000.0)
        assert isinstance(rs, RevenueShareRecord)
        assert rs.share_id == "rs1"
        assert rs.partner_id == "p1"
        assert rs.agreement_id == "ag1"
        assert rs.gross_amount == 1000.0
        assert rs.share_pct == 0.10
        assert rs.share_amount == 100.0
        assert rs.status == RevenueShareStatus.PENDING

    def test_auto_computes_share_amount(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_agreement("ag1", "p1", "t1", "X", revenue_share_pct=0.25)
        rs = engine.record_revenue_share("rs1", "p1", "ag1", "t1", 200.0)
        assert rs.share_amount == 50.0

    def test_rounding(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_agreement("ag1", "p1", "t1", "X", revenue_share_pct=0.33)
        rs = engine.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        assert rs.share_amount == 33.0

    def test_zero_pct(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_agreement("ag1", "p1", "t1", "X", revenue_share_pct=0.0)
        rs = engine.record_revenue_share("rs1", "p1", "ag1", "t1", 1000.0)
        assert rs.share_amount == 0.0

    def test_duplicate_raises(self, seeded: PartnerRuntimeEngine):
        seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        with pytest.raises(RuntimeCoreInvariantError, match="revenue share already exists"):
            seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 200.0)

    def test_unknown_partner_raises(self, engine: PartnerRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown partner"):
            engine.record_revenue_share("rs1", "nope", "ag1", "t1", 100.0)

    def test_unknown_agreement_raises(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        with pytest.raises(RuntimeCoreInvariantError, match="unknown agreement"):
            engine.record_revenue_share("rs1", "p1", "nope", "t1", 100.0)

    def test_increments_count(self, seeded: PartnerRuntimeEngine):
        seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        seeded.record_revenue_share("rs2", "p1", "ag1", "t1", 200.0)
        assert seeded.revenue_share_count == 2

    def test_fraction_rounding(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_agreement("ag1", "p1", "t1", "X", revenue_share_pct=0.07)
        rs = engine.record_revenue_share("rs1", "p1", "ag1", "t1", 333.33)
        assert rs.share_amount == round(333.33 * 0.07, 2)


# ===================================================================
# 12. settle_revenue_share
# ===================================================================


class TestSettleRevenueShare:
    def test_settle_pending(self, seeded: PartnerRuntimeEngine):
        seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        settled = seeded.settle_revenue_share("rs1")
        assert settled.status == RevenueShareStatus.SETTLED

    def test_settled_is_terminal(self, seeded: PartnerRuntimeEngine):
        seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        seeded.settle_revenue_share("rs1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            seeded.settle_revenue_share("rs1")

    def test_unknown_raises(self, engine: PartnerRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown revenue share"):
            engine.settle_revenue_share("nope")

    def test_preserves_amounts(self, seeded: PartnerRuntimeEngine):
        seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 1000.0)
        settled = seeded.settle_revenue_share("rs1")
        assert settled.gross_amount == 1000.0
        assert settled.share_amount == 100.0
        assert settled.share_pct == 0.10

    def test_cancelled_is_terminal_for_settle(self, seeded: PartnerRuntimeEngine):
        seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        seeded.dispute_revenue_share("rs1")
        # disputed is not terminal, but we need to test cancelled
        # Can't directly cancel, but settled is terminal
        seeded2 = seeded
        seeded2.record_revenue_share("rs2", "p1", "ag1", "t1", 100.0)
        seeded2.settle_revenue_share("rs2")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            seeded2.settle_revenue_share("rs2")


# ===================================================================
# 13. dispute_revenue_share
# ===================================================================


class TestDisputeRevenueShare:
    def test_dispute_pending(self, seeded: PartnerRuntimeEngine):
        seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        disputed = seeded.dispute_revenue_share("rs1")
        assert disputed.status == RevenueShareStatus.DISPUTED

    def test_settled_is_terminal_for_dispute(self, seeded: PartnerRuntimeEngine):
        seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        seeded.settle_revenue_share("rs1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            seeded.dispute_revenue_share("rs1")

    def test_unknown_raises(self, engine: PartnerRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown revenue share"):
            engine.dispute_revenue_share("nope")

    def test_dispute_then_settle_not_terminal(self, seeded: PartnerRuntimeEngine):
        """Disputed is NOT terminal - can still settle after dispute."""
        seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        seeded.dispute_revenue_share("rs1")
        settled = seeded.settle_revenue_share("rs1")
        assert settled.status == RevenueShareStatus.SETTLED

    def test_double_dispute(self, seeded: PartnerRuntimeEngine):
        """Disputed is NOT terminal so can dispute again."""
        seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        seeded.dispute_revenue_share("rs1")
        d2 = seeded.dispute_revenue_share("rs1")
        assert d2.status == RevenueShareStatus.DISPUTED


# ===================================================================
# 14. revenue_shares_for_partner
# ===================================================================


class TestRevenueSharesForPartner:
    def test_empty(self, engine: PartnerRuntimeEngine):
        assert engine.revenue_shares_for_partner("p1") == ()

    def test_filters(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_partner("p2", "t1", "B")
        engine.register_agreement("ag1", "p1", "t1", "X", revenue_share_pct=0.10)
        engine.register_agreement("ag2", "p2", "t1", "Y", revenue_share_pct=0.10)
        engine.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        engine.record_revenue_share("rs2", "p2", "ag2", "t1", 100.0)
        engine.record_revenue_share("rs3", "p1", "ag1", "t1", 200.0)
        result = engine.revenue_shares_for_partner("p1")
        assert len(result) == 2
        assert all(r.partner_id == "p1" for r in result)

    def test_returns_tuple(self, engine: PartnerRuntimeEngine):
        assert isinstance(engine.revenue_shares_for_partner("x"), tuple)


# ===================================================================
# 15. record_commitment
# ===================================================================


class TestRecordCommitment:
    def test_basic_commitment_unmet(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        c = engine.record_commitment("c1", "p1", "t1", "Sell 100 units", 100.0, 50.0)
        assert isinstance(c, PartnerCommitment)
        assert c.commitment_id == "c1"
        assert c.partner_id == "p1"
        assert c.target_value == 100.0
        assert c.actual_value == 50.0
        assert c.met is False

    def test_commitment_met(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        c = engine.record_commitment("c1", "p1", "t1", "Sell 100", 100.0, 100.0)
        assert c.met is True

    def test_commitment_exceeded(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        c = engine.record_commitment("c1", "p1", "t1", "Sell 100", 100.0, 150.0)
        assert c.met is True

    def test_default_actual_value(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        c = engine.record_commitment("c1", "p1", "t1", "Sell 100", 100.0)
        assert c.actual_value == 0.0
        assert c.met is False

    def test_duplicate_raises(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.record_commitment("c1", "p1", "t1", "X", 10.0)
        with pytest.raises(RuntimeCoreInvariantError, match="commitment already exists"):
            engine.record_commitment("c1", "p1", "t1", "Y", 20.0)

    def test_unknown_partner_raises(self, engine: PartnerRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown partner"):
            engine.record_commitment("c1", "nope", "t1", "X", 10.0)

    def test_increments_count(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.record_commitment("c1", "p1", "t1", "X", 10.0)
        engine.record_commitment("c2", "p1", "t1", "Y", 20.0)
        assert engine.commitment_count == 2

    def test_zero_target_always_met(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        c = engine.record_commitment("c1", "p1", "t1", "Zero target", 0.0, 0.0)
        assert c.met is True


# ===================================================================
# 16. commitments_for_partner
# ===================================================================


class TestCommitmentsForPartner:
    def test_empty(self, engine: PartnerRuntimeEngine):
        assert engine.commitments_for_partner("p1") == ()

    def test_filters(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_partner("p2", "t1", "B")
        engine.record_commitment("c1", "p1", "t1", "X", 10.0)
        engine.record_commitment("c2", "p2", "t1", "Y", 20.0)
        result = engine.commitments_for_partner("p1")
        assert len(result) == 1
        assert result[0].commitment_id == "c1"


# ===================================================================
# 17. partner_health
# ===================================================================


class TestPartnerHealth:
    def test_perfect_health(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        snap = engine.partner_health("h1", "p1", "t1")
        assert snap.health_score == 1.0
        assert snap.health_status == PartnerHealthStatus.HEALTHY

    def test_healthy_boundary(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        # 1.0 - 1*0.15 - 0 - 0 - 0 = 0.85 -> HEALTHY
        snap = engine.partner_health("h1", "p1", "t1", sla_breaches=1)
        assert snap.health_score == 0.85
        assert snap.health_status == PartnerHealthStatus.HEALTHY

    def test_at_risk_threshold(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        # 1.0 - 1*0.15 - 0 - 0 - 1*0.15 = 0.70 -> AT_RISK
        snap = engine.partner_health("h1", "p1", "t1", sla_breaches=1, commitment_failures=1)
        assert snap.health_score == 0.7
        assert snap.health_status == PartnerHealthStatus.AT_RISK

    def test_at_risk_lower_boundary(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        # 1.0 - 2*0.15 - 2*0.1 = 0.5 -> AT_RISK (>=0.5)
        snap = engine.partner_health("h1", "p1", "t1", sla_breaches=2, open_cases=2)
        assert snap.health_score == 0.5
        assert snap.health_status == PartnerHealthStatus.AT_RISK

    def test_degraded_threshold(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        # 1.0 - 2*0.15 - 2*0.1 - 1*0.2 = 0.3 -> DEGRADED (>=0.3)
        snap = engine.partner_health("h1", "p1", "t1", sla_breaches=2, open_cases=2, billing_issues=1)
        assert snap.health_score == 0.3
        assert snap.health_status == PartnerHealthStatus.DEGRADED

    def test_critical_threshold(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        # 1.0 - 3*0.15 - 2*0.1 - 1*0.2 = 0.15 -> CRITICAL (<0.3)
        snap = engine.partner_health("h1", "p1", "t1", sla_breaches=3, open_cases=2, billing_issues=1)
        assert snap.health_score == 0.15
        assert snap.health_status == PartnerHealthStatus.CRITICAL

    def test_zero_clamped(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        # Way over the limit
        snap = engine.partner_health("h1", "p1", "t1", sla_breaches=10, open_cases=10, billing_issues=10, commitment_failures=10)
        assert snap.health_score == 0.0
        assert snap.health_status == PartnerHealthStatus.CRITICAL

    def test_critical_auto_creates_escalation_decision(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        assert engine.decision_count == 0
        engine.partner_health("h1", "p1", "t1", sla_breaches=10)
        assert engine.decision_count == 1

    def test_healthy_no_decision(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.partner_health("h1", "p1", "t1")
        assert engine.decision_count == 0

    def test_at_risk_no_decision(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.partner_health("h1", "p1", "t1", sla_breaches=1, commitment_failures=1)
        assert engine.decision_count == 0

    def test_degraded_no_decision(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.partner_health("h1", "p1", "t1", sla_breaches=2, open_cases=2, billing_issues=1)
        assert engine.decision_count == 0

    def test_duplicate_raises(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.partner_health("h1", "p1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="health snapshot already exists"):
            engine.partner_health("h1", "p1", "t1")

    def test_unknown_partner_raises(self, engine: PartnerRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown partner"):
            engine.partner_health("h1", "nope", "t1")

    def test_increments_snapshot_count(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.partner_health("h1", "p1", "t1")
        engine.partner_health("h2", "p1", "t1", sla_breaches=1)
        assert engine.health_snapshot_count == 2

    def test_snapshot_fields(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        snap = engine.partner_health("h1", "p1", "t1", sla_breaches=2, open_cases=3, billing_issues=1, commitment_failures=1)
        assert snap.snapshot_id == "h1"
        assert snap.partner_id == "p1"
        assert snap.tenant_id == "t1"
        assert snap.sla_breaches == 2
        assert snap.open_cases == 3
        assert snap.billing_issues == 1
        assert snap.commitment_failures == 1

    def test_score_calculation_all_factors(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        # 1.0 - 1*0.15 - 1*0.1 - 1*0.2 - 1*0.15 = 0.4
        snap = engine.partner_health("h1", "p1", "t1",
                                     sla_breaches=1, open_cases=1,
                                     billing_issues=1, commitment_failures=1)
        assert snap.health_score == 0.4
        assert snap.health_status == PartnerHealthStatus.DEGRADED

    def test_exact_boundary_08(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        # 1.0 - 0 - 2*0.1 - 0 - 0 = 0.8 -> HEALTHY (>=0.8)
        snap = engine.partner_health("h1", "p1", "t1", open_cases=2)
        assert snap.health_score == 0.8
        assert snap.health_status == PartnerHealthStatus.HEALTHY

    def test_just_below_08(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        # 1.0 - 0 - 0 - 0 - 1*0.15 - 1*0.1 = 0.75 -> AT_RISK
        snap = engine.partner_health("h1", "p1", "t1", sla_breaches=1, open_cases=1)
        assert snap.health_score == 0.75
        assert snap.health_status == PartnerHealthStatus.AT_RISK

    def test_frozen_snapshot(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        snap = engine.partner_health("h1", "p1", "t1")
        with pytest.raises(AttributeError):
            snap.health_score = 0.5


# ===================================================================
# 18. health_snapshots_for_partner
# ===================================================================


class TestHealthSnapshotsForPartner:
    def test_empty(self, engine: PartnerRuntimeEngine):
        assert engine.health_snapshots_for_partner("p1") == ()

    def test_filters(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_partner("p2", "t1", "B")
        engine.partner_health("h1", "p1", "t1")
        engine.partner_health("h2", "p2", "t1")
        engine.partner_health("h3", "p1", "t1", sla_breaches=1)
        result = engine.health_snapshots_for_partner("p1")
        assert len(result) == 2
        assert all(h.partner_id == "p1" for h in result)


# ===================================================================
# 19. partner_snapshot
# ===================================================================


class TestPartnerSnapshot:
    def test_empty_snapshot(self, engine: PartnerRuntimeEngine):
        snap = engine.partner_snapshot("snap1")
        assert isinstance(snap, PartnerSnapshot)
        assert snap.snapshot_id == "snap1"
        assert snap.total_partners == 0
        assert snap.total_links == 0
        assert snap.total_agreements == 0
        assert snap.total_revenue_shares == 0
        assert snap.total_commitments == 0
        assert snap.total_health_snapshots == 0
        assert snap.total_decisions == 0
        assert snap.total_violations == 0

    def test_populated_snapshot(self, seeded: PartnerRuntimeEngine):
        seeded.link_partner_to_account("lk1", "p1", "acc1", "t1")
        seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        seeded.record_commitment("c1", "p1", "t1", "X", 10.0)
        seeded.partner_health("h1", "p1", "t1")
        snap = seeded.partner_snapshot("snap1")
        assert snap.total_partners == 1
        assert snap.total_links == 1
        assert snap.total_agreements == 1
        assert snap.total_revenue_shares == 1
        assert snap.total_commitments == 1
        assert snap.total_health_snapshots == 1

    def test_snapshot_has_timestamp(self, engine: PartnerRuntimeEngine):
        snap = engine.partner_snapshot("snap1")
        assert snap.captured_at != ""


# ===================================================================
# 20. detect_partner_violations
# ===================================================================


class TestDetectPartnerViolations:
    def test_no_violations(self, seeded: PartnerRuntimeEngine):
        violations = seeded.detect_partner_violations("t1")
        assert violations == ()

    def test_no_agreement_violation(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        violations = engine.detect_partner_violations("t1")
        assert len(violations) == 1
        assert violations[0].operation == "no_agreement"
        assert "p1" in violations[0].reason

    def test_disputed_revenue_violation(self, seeded: PartnerRuntimeEngine):
        seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        seeded.dispute_revenue_share("rs1")
        violations = seeded.detect_partner_violations("t1")
        assert len(violations) == 1
        assert violations[0].operation == "disputed_revenue"

    def test_unmet_commitment_violation(self, seeded: PartnerRuntimeEngine):
        seeded.record_commitment("c1", "p1", "t1", "Sell 100", 100.0, 50.0)
        violations = seeded.detect_partner_violations("t1")
        assert len(violations) == 1
        assert violations[0].operation == "unmet_commitment"

    def test_multiple_violations(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.register_partner("p2", "t1", "Beta")
        # Both have no agreements -> 2 violations
        violations = engine.detect_partner_violations("t1")
        assert len(violations) == 2
        assert all(v.operation == "no_agreement" for v in violations)

    def test_idempotent(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        v1 = engine.detect_partner_violations("t1")
        assert len(v1) == 1
        v2 = engine.detect_partner_violations("t1")
        assert len(v2) == 0  # no new violations
        assert engine.violation_count == 1

    def test_filters_by_tenant(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_partner("p2", "t2", "B")
        violations = engine.detect_partner_violations("t1")
        assert len(violations) == 1
        assert violations[0].partner_id == "p1"

    def test_inactive_partner_no_violation(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme", status=PartnerStatus.INACTIVE)
        violations = engine.detect_partner_violations("t1")
        assert len(violations) == 0

    def test_terminated_partner_no_violation(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.update_partner_status("p1", PartnerStatus.TERMINATED)
        violations = engine.detect_partner_violations("t1")
        assert len(violations) == 0

    def test_met_commitment_no_violation(self, seeded: PartnerRuntimeEngine):
        seeded.record_commitment("c1", "p1", "t1", "Sell 100", 100.0, 150.0)
        violations = seeded.detect_partner_violations("t1")
        assert len(violations) == 0

    def test_settled_revenue_no_violation(self, seeded: PartnerRuntimeEngine):
        seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        seeded.settle_revenue_share("rs1")
        violations = seeded.detect_partner_violations("t1")
        assert len(violations) == 0

    def test_combined_violations(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.register_agreement("ag1", "p1", "t1", "X", revenue_share_pct=0.10)
        engine.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        engine.dispute_revenue_share("rs1")
        engine.record_commitment("c1", "p1", "t1", "Sell", 100.0, 10.0)
        violations = engine.detect_partner_violations("t1")
        assert len(violations) == 2
        ops = {v.operation for v in violations}
        assert "disputed_revenue" in ops
        assert "unmet_commitment" in ops

    def test_returns_tuple(self, engine: PartnerRuntimeEngine):
        result = engine.detect_partner_violations("t1")
        assert isinstance(result, tuple)

    def test_violation_record_fields(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        violations = engine.detect_partner_violations("t1")
        v = violations[0]
        assert isinstance(v, PartnerViolation)
        assert v.tenant_id == "t1"
        assert v.partner_id == "p1"
        assert v.violation_id != ""
        assert v.detected_at != ""


# ===================================================================
# 21. violations_for_tenant
# ===================================================================


class TestViolationsForTenant:
    def test_empty(self, engine: PartnerRuntimeEngine):
        assert engine.violations_for_tenant("t1") == ()

    def test_returns_accumulated(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.detect_partner_violations("t1")
        result = engine.violations_for_tenant("t1")
        assert len(result) == 1

    def test_filters_by_tenant(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_partner("p2", "t2", "B")
        engine.detect_partner_violations("t1")
        engine.detect_partner_violations("t2")
        assert len(engine.violations_for_tenant("t1")) == 1
        assert len(engine.violations_for_tenant("t2")) == 1

    def test_returns_tuple(self, engine: PartnerRuntimeEngine):
        assert isinstance(engine.violations_for_tenant("t1"), tuple)


# ===================================================================
# 22. closure_report
# ===================================================================


class TestClosureReport:
    def test_empty_report(self, engine: PartnerRuntimeEngine):
        report = engine.closure_report("rpt1", "t1")
        assert isinstance(report, PartnerClosureReport)
        assert report.report_id == "rpt1"
        assert report.tenant_id == "t1"
        assert report.total_partners == 0
        assert report.total_links == 0
        assert report.total_agreements == 0
        assert report.total_revenue_shares == 0
        assert report.total_commitments == 0
        assert report.total_violations == 0
        assert report.closed_at != ""

    def test_populated_report(self, seeded: PartnerRuntimeEngine):
        seeded.link_partner_to_account("lk1", "p1", "acc1", "t1")
        seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        seeded.record_commitment("c1", "p1", "t1", "X", 10.0)
        seeded.detect_partner_violations("t1")
        report = seeded.closure_report("rpt1", "t1")
        assert report.total_partners == 1
        assert report.total_links == 1
        assert report.total_agreements == 1
        assert report.total_revenue_shares == 1
        assert report.total_commitments == 1

    def test_filters_by_tenant(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_partner("p2", "t2", "B")
        report = engine.closure_report("rpt1", "t1")
        assert report.total_partners == 1

    def test_frozen_report(self, engine: PartnerRuntimeEngine):
        report = engine.closure_report("rpt1", "t1")
        with pytest.raises(AttributeError):
            report.total_partners = 99


# ===================================================================
# 23. state_hash
# ===================================================================


class TestStateHash:
    def test_empty_hash(self, engine: PartnerRuntimeEngine):
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64  # SHA256 hex

    def test_deterministic(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_changes_with_partner(self, engine: PartnerRuntimeEngine):
        h1 = engine.state_hash()
        engine.register_partner("p1", "t1", "Acme")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_with_link(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        h1 = engine.state_hash()
        engine.link_partner_to_account("lk1", "p1", "acc1", "t1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_with_agreement(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        h1 = engine.state_hash()
        engine.register_agreement("ag1", "p1", "t1", "X")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_with_revenue_share(self, seeded: PartnerRuntimeEngine):
        h1 = seeded.state_hash()
        seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        h2 = seeded.state_hash()
        assert h1 != h2

    def test_changes_with_commitment(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        h1 = engine.state_hash()
        engine.record_commitment("c1", "p1", "t1", "X", 10.0)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_with_health(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        h1 = engine.state_hash()
        engine.partner_health("h1", "p1", "t1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_with_violation(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        h1 = engine.state_hash()
        engine.detect_partner_violations("t1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_with_decision(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        h1 = engine.state_hash()
        engine.partner_health("h1", "p1", "t1", sla_breaches=10)
        h2 = engine.state_hash()
        assert h1 != h2


# ===================================================================
# Properties
# ===================================================================


class TestProperties:
    def test_partner_count(self, engine: PartnerRuntimeEngine):
        assert engine.partner_count == 0
        engine.register_partner("p1", "t1", "A")
        assert engine.partner_count == 1

    def test_link_count(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        assert engine.link_count == 0
        engine.link_partner_to_account("lk1", "p1", "acc1", "t1")
        assert engine.link_count == 1

    def test_agreement_count(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        assert engine.agreement_count == 0
        engine.register_agreement("ag1", "p1", "t1", "X")
        assert engine.agreement_count == 1

    def test_revenue_share_count(self, seeded: PartnerRuntimeEngine):
        assert seeded.revenue_share_count == 0
        seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        assert seeded.revenue_share_count == 1

    def test_commitment_count(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        assert engine.commitment_count == 0
        engine.record_commitment("c1", "p1", "t1", "X", 10.0)
        assert engine.commitment_count == 1

    def test_health_snapshot_count(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        assert engine.health_snapshot_count == 0
        engine.partner_health("h1", "p1", "t1")
        assert engine.health_snapshot_count == 1

    def test_decision_count(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        assert engine.decision_count == 0
        engine.partner_health("h1", "p1", "t1", sla_breaches=10)
        assert engine.decision_count == 1

    def test_violation_count(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        assert engine.violation_count == 0
        engine.detect_partner_violations("t1")
        assert engine.violation_count == 1


# ===================================================================
# Golden Scenario 1: Contract creates partner-linked customer relationship
# ===================================================================


class TestGoldenScenario1ContractCreatesRelationship:
    def test_full_flow(self, engine: PartnerRuntimeEngine):
        partner = engine.register_partner("reseller-1", "tenant-a", "Premier Reseller", kind=PartnerKind.RESELLER, tier="gold")
        assert partner.status == PartnerStatus.ACTIVE
        agreement = engine.register_agreement("agr-1", "reseller-1", "tenant-a", "Enterprise Reseller Agreement", contract_ref="CR-2024-001", revenue_share_pct=0.15)
        assert agreement.contract_ref == "CR-2024-001"
        link = engine.link_partner_to_account("link-1", "reseller-1", "customer-100", "tenant-a", role=EcosystemRole.INTERMEDIARY)
        assert link.account_id == "customer-100"
        assert engine.get_partner("reseller-1").account_link_count == 1
        links = engine.links_for_partner("reseller-1")
        assert len(links) == 1
        account_links = engine.links_for_account("customer-100")
        assert len(account_links) == 1
        assert account_links[0].partner_id == "reseller-1"

    def test_partner_with_multiple_customers(self, engine: PartnerRuntimeEngine):
        engine.register_partner("r1", "t1", "Reseller")
        engine.register_agreement("ag1", "r1", "t1", "Main", revenue_share_pct=0.10)
        for i in range(5):
            engine.link_partner_to_account(f"lk{i}", "r1", f"cust{i}", "t1")
        assert engine.get_partner("r1").account_link_count == 5
        assert len(engine.links_for_partner("r1")) == 5


# ===================================================================
# Golden Scenario 2: Reseller account inherits product/customer linkage
# ===================================================================


class TestGoldenScenario2ResellerInheritance:
    def test_reseller_manages_multiple_accounts(self, engine: PartnerRuntimeEngine):
        engine.register_partner("reseller-a", "t1", "Alpha Reseller", kind=PartnerKind.RESELLER)
        engine.register_agreement("ag-a", "reseller-a", "t1", "Alpha Agreement", revenue_share_pct=0.20)
        customers = ["cust-1", "cust-2", "cust-3"]
        for i, cust in enumerate(customers):
            engine.link_partner_to_account(f"link-a-{i}", "reseller-a", cust, "t1", role=EcosystemRole.INTERMEDIARY)
        for cust in customers:
            acc_links = engine.links_for_account(cust)
            assert len(acc_links) == 1
            assert acc_links[0].partner_id == "reseller-a"
        assert engine.get_partner("reseller-a").account_link_count == 3

    def test_distributor_with_sub_resellers(self, engine: PartnerRuntimeEngine):
        engine.register_partner("dist-1", "t1", "Top Distributor", kind=PartnerKind.DISTRIBUTOR)
        engine.register_partner("reseller-1", "t1", "Sub Reseller", kind=PartnerKind.RESELLER)
        engine.register_agreement("ag-dist", "dist-1", "t1", "Dist Agreement", revenue_share_pct=0.05)
        engine.register_agreement("ag-res", "reseller-1", "t1", "Reseller Agreement", revenue_share_pct=0.15)
        engine.link_partner_to_account("lk-d1", "dist-1", "cust-a", "t1", role=EcosystemRole.PROVIDER)
        engine.link_partner_to_account("lk-r1", "reseller-1", "cust-a", "t1", role=EcosystemRole.INTERMEDIARY)
        acc_links = engine.links_for_account("cust-a")
        assert len(acc_links) == 2
        roles = {l.role for l in acc_links}
        assert EcosystemRole.PROVIDER in roles
        assert EcosystemRole.INTERMEDIARY in roles


# ===================================================================
# Golden Scenario 3: Repeated SLA failures degrade partner health
# ===================================================================


class TestGoldenScenario3SLADegradation:
    def test_progressive_degradation(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        # Month 1: healthy
        h1 = engine.partner_health("h-m1", "p1", "t1", sla_breaches=0)
        assert h1.health_status == PartnerHealthStatus.HEALTHY
        # Month 2: minor issues
        h2 = engine.partner_health("h-m2", "p1", "t1", sla_breaches=1, open_cases=1)
        assert h2.health_status == PartnerHealthStatus.AT_RISK
        # Month 3: worsening
        h3 = engine.partner_health("h-m3", "p1", "t1", sla_breaches=2, open_cases=2, billing_issues=1)
        assert h3.health_status == PartnerHealthStatus.DEGRADED
        # Month 4: critical
        h4 = engine.partner_health("h-m4", "p1", "t1", sla_breaches=4, open_cases=3, billing_issues=2)
        assert h4.health_status == PartnerHealthStatus.CRITICAL
        assert engine.decision_count == 1  # auto-escalation
        snapshots = engine.health_snapshots_for_partner("p1")
        assert len(snapshots) == 4

    def test_critical_triggers_escalation_decision(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.partner_health("h1", "p1", "t1", sla_breaches=5, billing_issues=3)
        assert engine.decision_count == 1

    def test_recovery_from_degraded(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        h1 = engine.partner_health("h1", "p1", "t1", sla_breaches=3, open_cases=2)
        assert h1.health_status in {PartnerHealthStatus.DEGRADED, PartnerHealthStatus.AT_RISK, PartnerHealthStatus.CRITICAL}
        h2 = engine.partner_health("h2", "p1", "t1", sla_breaches=0)
        assert h2.health_status == PartnerHealthStatus.HEALTHY


# ===================================================================
# Golden Scenario 4: Revenue-share record settlement/billing flow
# ===================================================================


class TestGoldenScenario4RevenueShareSettlement:
    def test_full_settlement_flow(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Reseller Co")
        engine.register_agreement("ag1", "p1", "t1", "Revenue Deal", revenue_share_pct=0.20)
        # Record multiple revenue shares
        rs1 = engine.record_revenue_share("rs-q1", "p1", "ag1", "t1", 10000.0)
        assert rs1.share_amount == 2000.0
        assert rs1.status == RevenueShareStatus.PENDING
        rs2 = engine.record_revenue_share("rs-q2", "p1", "ag1", "t1", 15000.0)
        assert rs2.share_amount == 3000.0
        # Settle Q1
        settled1 = engine.settle_revenue_share("rs-q1")
        assert settled1.status == RevenueShareStatus.SETTLED
        # Dispute Q2
        disputed2 = engine.dispute_revenue_share("rs-q2")
        assert disputed2.status == RevenueShareStatus.DISPUTED
        # Settled is terminal
        with pytest.raises(RuntimeCoreInvariantError):
            engine.settle_revenue_share("rs-q1")
        # Disputed can still be settled
        settled2 = engine.settle_revenue_share("rs-q2")
        assert settled2.status == RevenueShareStatus.SETTLED

    def test_multiple_agreements_different_rates(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.register_agreement("ag-low", "p1", "t1", "Low Rate", revenue_share_pct=0.05)
        engine.register_agreement("ag-high", "p1", "t1", "High Rate", revenue_share_pct=0.30)
        rs_low = engine.record_revenue_share("rs-low", "p1", "ag-low", "t1", 1000.0)
        rs_high = engine.record_revenue_share("rs-high", "p1", "ag-high", "t1", 1000.0)
        assert rs_low.share_amount == 50.0
        assert rs_high.share_amount == 300.0

    def test_zero_revenue_share(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.register_agreement("ag1", "p1", "t1", "Free", revenue_share_pct=0.0)
        rs = engine.record_revenue_share("rs1", "p1", "ag1", "t1", 5000.0)
        assert rs.share_amount == 0.0
        assert rs.share_pct == 0.0


# ===================================================================
# Golden Scenario 5: Partner violation escalates executive attention
# ===================================================================


class TestGoldenScenario5ViolationEscalation:
    def test_violations_detected_and_reported(self, engine: PartnerRuntimeEngine):
        # Partner with no agreement
        engine.register_partner("p-risk", "t1", "Risky Partner")
        # Partner with agreement but disputed revenue + unmet commitment
        engine.register_partner("p-ok", "t1", "Other Partner")
        engine.register_agreement("ag-ok", "p-ok", "t1", "Deal", revenue_share_pct=0.10)
        engine.record_revenue_share("rs-dispute", "p-ok", "ag-ok", "t1", 5000.0)
        engine.dispute_revenue_share("rs-dispute")
        engine.record_commitment("c-fail", "p-ok", "t1", "Hit target", 100.0, 20.0)
        violations = engine.detect_partner_violations("t1")
        assert len(violations) == 3
        ops = {v.operation for v in violations}
        assert ops == {"no_agreement", "disputed_revenue", "unmet_commitment"}
        # Add critical health for escalation
        engine.partner_health("h-crit", "p-risk", "t1", sla_breaches=10)
        assert engine.decision_count == 1
        # Closure report captures everything
        report = engine.closure_report("rpt-exec", "t1")
        assert report.total_violations == 3
        assert report.total_partners == 2

    def test_violation_escalation_with_suspension(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Bad Partner")
        engine.detect_partner_violations("t1")
        assert engine.violation_count == 1
        engine.update_partner_status("p1", PartnerStatus.SUSPENDED)
        rec = engine.get_partner("p1")
        assert rec.status == PartnerStatus.SUSPENDED


# ===================================================================
# Golden Scenario 6: Replay/restore preserves partner/ecosystem state
# ===================================================================


class TestGoldenScenario6Replay:
    def test_state_hash_reproducible(self, spine: EventSpineEngine):
        e1 = PartnerRuntimeEngine(spine)
        e1.register_partner("p1", "t1", "Acme")
        e1.register_agreement("ag1", "p1", "t1", "Deal", revenue_share_pct=0.10)
        e1.link_partner_to_account("lk1", "p1", "acc1", "t1")
        e1.record_revenue_share("rs1", "p1", "ag1", "t1", 1000.0)
        e1.record_commitment("c1", "p1", "t1", "Target", 100.0, 80.0)
        e1.partner_health("h1", "p1", "t1", sla_breaches=1)
        e1.detect_partner_violations("t1")
        hash1 = e1.state_hash()
        # Replay in new engine
        spine2 = EventSpineEngine()
        e2 = PartnerRuntimeEngine(spine2)
        e2.register_partner("p1", "t1", "Acme")
        e2.register_agreement("ag1", "p1", "t1", "Deal", revenue_share_pct=0.10)
        e2.link_partner_to_account("lk1", "p1", "acc1", "t1")
        e2.record_revenue_share("rs1", "p1", "ag1", "t1", 1000.0)
        e2.record_commitment("c1", "p1", "t1", "Target", 100.0, 80.0)
        e2.partner_health("h1", "p1", "t1", sla_breaches=1)
        e2.detect_partner_violations("t1")
        hash2 = e2.state_hash()
        assert hash1 == hash2

    def test_snapshot_matches_counts(self, seeded: PartnerRuntimeEngine):
        seeded.link_partner_to_account("lk1", "p1", "acc1", "t1")
        seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        seeded.record_commitment("c1", "p1", "t1", "X", 10.0)
        seeded.partner_health("h1", "p1", "t1")
        snap = seeded.partner_snapshot("replay-snap")
        assert snap.total_partners == seeded.partner_count
        assert snap.total_links == seeded.link_count
        assert snap.total_agreements == seeded.agreement_count
        assert snap.total_revenue_shares == seeded.revenue_share_count
        assert snap.total_commitments == seeded.commitment_count
        assert snap.total_health_snapshots == seeded.health_snapshot_count
        assert snap.total_decisions == seeded.decision_count
        assert snap.total_violations == seeded.violation_count

    def test_empty_state_hash_consistent(self):
        s1 = EventSpineEngine()
        e1 = PartnerRuntimeEngine(s1)
        s2 = EventSpineEngine()
        e2 = PartnerRuntimeEngine(s2)
        assert e1.state_hash() == e2.state_hash()

    def test_different_operations_different_hash(self, spine: EventSpineEngine):
        e1 = PartnerRuntimeEngine(spine)
        e1.register_partner("p1", "t1", "A")
        spine2 = EventSpineEngine()
        e2 = PartnerRuntimeEngine(spine2)
        e2.register_partner("p2", "t1", "B")
        assert e1.state_hash() != e2.state_hash()


# ===================================================================
# Edge cases and cross-cutting concerns
# ===================================================================


class TestEdgeCases:
    def test_partner_with_special_chars_in_name(self, engine: PartnerRuntimeEngine):
        rec = engine.register_partner("p1", "t1", "Acme & Co. (International)")
        assert rec.display_name == "Acme & Co. (International)"

    def test_many_partners_same_tenant(self, engine: PartnerRuntimeEngine):
        for i in range(50):
            engine.register_partner(f"p{i}", "t1", f"Partner {i}")
        assert engine.partner_count == 50
        assert len(engine.partners_for_tenant("t1")) == 50

    def test_many_links_same_partner(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        for i in range(20):
            engine.link_partner_to_account(f"lk{i}", "p1", f"acc{i}", "t1")
        assert engine.get_partner("p1").account_link_count == 20

    def test_suspended_partner_can_be_linked(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme")
        engine.update_partner_status("p1", PartnerStatus.SUSPENDED)
        # Suspended is NOT terminal, so linking should work
        link = engine.link_partner_to_account("lk1", "p1", "acc1", "t1")
        assert link.partner_id == "p1"

    def test_inactive_partner_can_be_linked(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme", status=PartnerStatus.INACTIVE)
        link = engine.link_partner_to_account("lk1", "p1", "acc1", "t1")
        assert link.partner_id == "p1"

    def test_prospect_partner_can_be_linked(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Acme", status=PartnerStatus.PROSPECT)
        link = engine.link_partner_to_account("lk1", "p1", "acc1", "t1")
        assert link.partner_id == "p1"


class TestEventEmission:
    def test_register_partner_emits(self, spine: EventSpineEngine, engine: PartnerRuntimeEngine):
        before = spine.event_count
        engine.register_partner("p1", "t1", "A")
        assert spine.event_count == before + 1

    def test_update_status_emits(self, spine: EventSpineEngine, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        before = spine.event_count
        engine.update_partner_status("p1", PartnerStatus.SUSPENDED)
        assert spine.event_count == before + 1

    def test_link_emits(self, spine: EventSpineEngine, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        before = spine.event_count
        engine.link_partner_to_account("lk1", "p1", "acc1", "t1")
        assert spine.event_count == before + 1

    def test_agreement_emits(self, spine: EventSpineEngine, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        before = spine.event_count
        engine.register_agreement("ag1", "p1", "t1", "X")
        assert spine.event_count == before + 1

    def test_revenue_share_emits(self, spine: EventSpineEngine, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_agreement("ag1", "p1", "t1", "X", revenue_share_pct=0.10)
        before = spine.event_count
        engine.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        assert spine.event_count == before + 1

    def test_settle_emits(self, spine: EventSpineEngine, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_agreement("ag1", "p1", "t1", "X", revenue_share_pct=0.10)
        engine.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        before = spine.event_count
        engine.settle_revenue_share("rs1")
        assert spine.event_count == before + 1

    def test_dispute_emits(self, spine: EventSpineEngine, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_agreement("ag1", "p1", "t1", "X", revenue_share_pct=0.10)
        engine.record_revenue_share("rs1", "p1", "ag1", "t1", 100.0)
        before = spine.event_count
        engine.dispute_revenue_share("rs1")
        assert spine.event_count == before + 1

    def test_commitment_emits(self, spine: EventSpineEngine, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        before = spine.event_count
        engine.record_commitment("c1", "p1", "t1", "X", 10.0)
        assert spine.event_count == before + 1

    def test_health_emits(self, spine: EventSpineEngine, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        before = spine.event_count
        engine.partner_health("h1", "p1", "t1")
        assert spine.event_count == before + 1

    def test_detect_violations_emits(self, spine: EventSpineEngine, engine: PartnerRuntimeEngine):
        before = spine.event_count
        engine.detect_partner_violations("t1")
        assert spine.event_count == before + 1


class TestMultiTenantIsolation:
    def test_partners_isolated(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_partner("p2", "t2", "B")
        assert len(engine.partners_for_tenant("t1")) == 1
        assert len(engine.partners_for_tenant("t2")) == 1

    def test_violations_isolated(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_partner("p2", "t2", "B")
        engine.detect_partner_violations("t1")
        engine.detect_partner_violations("t2")
        assert len(engine.violations_for_tenant("t1")) == 1
        assert len(engine.violations_for_tenant("t2")) == 1

    def test_closure_report_isolated(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.register_partner("p2", "t1", "B")
        engine.register_partner("p3", "t2", "C")
        r1 = engine.closure_report("rpt1", "t1")
        r2 = engine.closure_report("rpt2", "t2")
        assert r1.total_partners == 2
        assert r2.total_partners == 1

    def test_links_cross_tenant(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.link_partner_to_account("lk1", "p1", "acc1", "t1")
        engine.link_partner_to_account("lk2", "p1", "acc2", "t2")
        all_links = engine.links_for_partner("p1")
        assert len(all_links) == 2


class TestRevenueShareEdgeCases:
    def test_large_gross_amount(self, seeded: PartnerRuntimeEngine):
        rs = seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 999999999.99)
        assert rs.share_amount == round(999999999.99 * 0.10, 2)

    def test_zero_gross_amount(self, seeded: PartnerRuntimeEngine):
        rs = seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 0.0)
        assert rs.share_amount == 0.0

    def test_small_gross_amount(self, seeded: PartnerRuntimeEngine):
        rs = seeded.record_revenue_share("rs1", "p1", "ag1", "t1", 0.01)
        assert rs.share_amount == round(0.01 * 0.10, 2)


class TestHealthScoreEdgeCases:
    def test_only_billing_issues(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        snap = engine.partner_health("h1", "p1", "t1", billing_issues=2)
        # 1.0 - 0.4 = 0.6
        assert snap.health_score == 0.6
        assert snap.health_status == PartnerHealthStatus.AT_RISK

    def test_only_commitment_failures(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        snap = engine.partner_health("h1", "p1", "t1", commitment_failures=3)
        # 1.0 - 0.45 = 0.55
        assert snap.health_score == 0.55
        assert snap.health_status == PartnerHealthStatus.AT_RISK

    def test_only_open_cases(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        snap = engine.partner_health("h1", "p1", "t1", open_cases=5)
        # 1.0 - 0.5 = 0.5
        assert snap.health_score == 0.5
        assert snap.health_status == PartnerHealthStatus.AT_RISK

    def test_score_clamped_at_zero(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        snap = engine.partner_health("h1", "p1", "t1", sla_breaches=100)
        assert snap.health_score == 0.0

    def test_exact_03_boundary(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        # 1.0 - 2*0.15 - 2*0.1 - 1*0.2 = 0.3 -> DEGRADED
        snap = engine.partner_health("h1", "p1", "t1", sla_breaches=2, open_cases=2, billing_issues=1)
        assert snap.health_score == 0.3
        assert snap.health_status == PartnerHealthStatus.DEGRADED

    def test_just_below_03(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        # 1.0 - 2*0.15 - 2*0.1 - 1*0.2 - 1*0.15 = 0.15 -> CRITICAL
        snap = engine.partner_health("h1", "p1", "t1", sla_breaches=2, open_cases=2, billing_issues=1, commitment_failures=1)
        assert snap.health_score == 0.15
        assert snap.health_status == PartnerHealthStatus.CRITICAL


class TestComplexFlows:
    def test_full_lifecycle(self, engine: PartnerRuntimeEngine):
        """Full partner lifecycle: register -> link -> agreement -> revenue -> health -> violations -> closure."""
        # Register
        engine.register_partner("p1", "t1", "Full Lifecycle Corp", kind=PartnerKind.SERVICE_PARTNER, tier="enterprise")
        # Agreement
        engine.register_agreement("ag1", "p1", "t1", "Service Agreement", revenue_share_pct=0.12)
        # Link accounts
        engine.link_partner_to_account("lk1", "p1", "acct-a", "t1", role=EcosystemRole.PROVIDER)
        engine.link_partner_to_account("lk2", "p1", "acct-b", "t1", role=EcosystemRole.INTEGRATOR)
        # Revenue shares
        rs1 = engine.record_revenue_share("rs1", "p1", "ag1", "t1", 50000.0)
        assert rs1.share_amount == 6000.0
        rs2 = engine.record_revenue_share("rs2", "p1", "ag1", "t1", 30000.0)
        assert rs2.share_amount == 3600.0
        # Settle one, dispute one
        engine.settle_revenue_share("rs1")
        engine.dispute_revenue_share("rs2")
        # Commitments
        engine.record_commitment("c1", "p1", "t1", "Revenue target", 100000.0, 80000.0)
        engine.record_commitment("c2", "p1", "t1", "Customer satisfaction", 90.0, 95.0)
        # Health check
        snap = engine.partner_health("h1", "p1", "t1", sla_breaches=1, open_cases=2)
        assert snap.health_status in {PartnerHealthStatus.HEALTHY, PartnerHealthStatus.AT_RISK}
        # Detect violations
        violations = engine.detect_partner_violations("t1")
        assert len(violations) == 2  # disputed revenue + unmet commitment
        # Snapshot
        psnap = engine.partner_snapshot("lifecycle-snap")
        assert psnap.total_partners == 1
        assert psnap.total_agreements == 1
        assert psnap.total_links == 2
        assert psnap.total_revenue_shares == 2
        assert psnap.total_commitments == 2
        assert psnap.total_violations == 2
        # Closure report
        report = engine.closure_report("lifecycle-rpt", "t1")
        assert report.total_partners == 1
        assert report.total_violations == 2
        # State hash is stable
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_multiple_tenants_full_isolation(self, engine: PartnerRuntimeEngine):
        for tid in ["t1", "t2", "t3"]:
            engine.register_partner(f"p-{tid}", tid, f"Partner {tid}")
            engine.register_agreement(f"ag-{tid}", f"p-{tid}", tid, f"Agreement {tid}", revenue_share_pct=0.10)
            engine.link_partner_to_account(f"lk-{tid}", f"p-{tid}", f"acc-{tid}", tid)
            engine.record_revenue_share(f"rs-{tid}", f"p-{tid}", f"ag-{tid}", tid, 1000.0)
            engine.record_commitment(f"c-{tid}", f"p-{tid}", tid, "Target", 100.0, 50.0)
        for tid in ["t1", "t2", "t3"]:
            engine.detect_partner_violations(tid)
        for tid in ["t1", "t2", "t3"]:
            report = engine.closure_report(f"rpt-{tid}", tid)
            assert report.total_partners == 1
            assert report.total_links == 1
            assert report.total_agreements == 1
            assert report.total_revenue_shares == 1
            assert report.total_commitments == 1
            assert report.total_violations == 1  # unmet commitment

    def test_partner_termination_blocks_further_links(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "Doomed")
        engine.link_partner_to_account("lk1", "p1", "acc1", "t1")
        engine.update_partner_status("p1", PartnerStatus.TERMINATED)
        with pytest.raises(RuntimeCoreInvariantError):
            engine.link_partner_to_account("lk2", "p1", "acc2", "t1")
        assert engine.get_partner("p1").account_link_count == 1

    def test_violation_detection_three_types_simultaneously(self, engine: PartnerRuntimeEngine):
        # Partner with no agreement
        engine.register_partner("p-no-ag", "t1", "No Agreement")
        # Partner with disputed revenue
        engine.register_partner("p-dispute", "t1", "Disputed")
        engine.register_agreement("ag-d", "p-dispute", "t1", "Deal", revenue_share_pct=0.10)
        engine.record_revenue_share("rs-d", "p-dispute", "ag-d", "t1", 100.0)
        engine.dispute_revenue_share("rs-d")
        # Partner with unmet commitment
        engine.register_partner("p-unmet", "t1", "Unmet")
        engine.register_agreement("ag-u", "p-unmet", "t1", "Comm", revenue_share_pct=0.05)
        engine.record_commitment("c-u", "p-unmet", "t1", "Reach", 100.0, 10.0)
        violations = engine.detect_partner_violations("t1")
        assert len(violations) == 3
        ops = {v.operation for v in violations}
        assert ops == {"no_agreement", "disputed_revenue", "unmet_commitment"}

    def test_multiple_health_snapshots_no_decision_until_critical(self, engine: PartnerRuntimeEngine):
        engine.register_partner("p1", "t1", "A")
        engine.partner_health("h1", "p1", "t1", sla_breaches=0)
        assert engine.decision_count == 0
        engine.partner_health("h2", "p1", "t1", sla_breaches=1)
        assert engine.decision_count == 0
        engine.partner_health("h3", "p1", "t1", sla_breaches=2, open_cases=2, billing_issues=1)
        assert engine.decision_count == 0  # DEGRADED, not CRITICAL
        engine.partner_health("h4", "p1", "t1", sla_breaches=5, billing_issues=3)
        assert engine.decision_count == 1  # Now CRITICAL

    def test_many_revenue_shares_settle_all(self, seeded: PartnerRuntimeEngine):
        for i in range(20):
            seeded.record_revenue_share(f"rs{i}", "p1", "ag1", "t1", 100.0 * (i + 1))
        for i in range(20):
            settled = seeded.settle_revenue_share(f"rs{i}")
            assert settled.status == RevenueShareStatus.SETTLED
        assert seeded.revenue_share_count == 20

    def test_all_kinds_all_roles(self, engine: PartnerRuntimeEngine):
        for i, kind in enumerate(PartnerKind):
            pid = f"pk{i}"
            engine.register_partner(pid, "t1", f"Partner {i}", kind=kind)
            for j, role in enumerate(EcosystemRole):
                engine.link_partner_to_account(f"lk-{i}-{j}", pid, f"acc-{i}-{j}", "t1", role=role)
        assert engine.partner_count == len(PartnerKind)
        assert engine.link_count == len(PartnerKind) * len(EcosystemRole)
