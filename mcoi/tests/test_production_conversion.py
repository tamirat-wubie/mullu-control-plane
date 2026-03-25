"""Phase 128 — Production Conversion Tests."""
import pytest
from mcoi_runtime.pilot.production_offer import ProductionOffer, SCOPE_DOCUMENT, SUPPORT_SLA
from mcoi_runtime.pilot.customer_success import (
    ADMIN_ONBOARDING_CHECKLIST, OPERATOR_ENABLEMENT_CHECKLIST,
    WEEKLY_SUCCESS_REVIEW, INCIDENT_WORKFLOW, ESCALATION_PATH, RENEWAL_REVIEW,
)
from mcoi_runtime.pilot.deployment_path import PaidDeploymentPath, ReferenceDeployment, DeploymentMilestone

class TestProductionOffer:
    def test_create_offer(self):
        offer = ProductionOffer(offer_id="offer-001", customer_id="cust-001")
        assert offer.product_name == "Regulated Operations Control Tower"
        assert offer.monthly_price == 2500.0
        assert offer.annual_value == 30000.0

    def test_enterprise_offer(self):
        offer = ProductionOffer(offer_id="o2", customer_id="c2", tier="enterprise", monthly_price=7500.0, included_operator_seats=999)
        assert offer.annual_value == 90000.0

    def test_scope_document(self):
        assert len(SCOPE_DOCUMENT["included"]) == 10
        assert len(SCOPE_DOCUMENT["excluded"]) >= 5

    def test_support_sla(self):
        assert "standard" in SUPPORT_SLA
        assert "premium" in SUPPORT_SLA
        assert SUPPORT_SLA["premium"]["dedicated_csm"] is True

class TestCustomerSuccess:
    def test_admin_checklist(self):
        assert len(ADMIN_ONBOARDING_CHECKLIST) == 10

    def test_operator_checklist(self):
        assert len(OPERATOR_ENABLEMENT_CHECKLIST) == 10

    def test_weekly_review(self):
        assert len(WEEKLY_SUCCESS_REVIEW["sections"]) >= 6
        assert WEEKLY_SUCCESS_REVIEW["cadence"] == "weekly"

    def test_incident_workflow(self):
        assert len(INCIDENT_WORKFLOW) >= 7

    def test_escalation_path(self):
        assert len(ESCALATION_PATH) == 4

    def test_renewal_review(self):
        assert RENEWAL_REVIEW["timing"] == "60 days before contract renewal"
        assert len(RENEWAL_REVIEW["review_items"]) >= 6

class TestDeploymentPath:
    def test_7_milestones(self):
        path = PaidDeploymentPath("cust-001", "offer-001")
        assert len(path.milestones) == 7

    def test_initial_progress(self):
        path = PaidDeploymentPath("c1", "o1")
        p = path.progress
        assert p["completed"] == 0
        assert p["percent"] == 0.0
        assert p["next_step"] == "contract_signed"
        assert not p["is_live"]

    def test_complete_milestones(self):
        path = PaidDeploymentPath("c1", "o1")
        for step in range(1, 8):
            path.complete_milestone(step)
        p = path.progress
        assert p["completed"] == 7
        assert p["is_live"]
        assert p["next_step"] == "all_complete"

    def test_partial_progress(self):
        path = PaidDeploymentPath("c1", "o1")
        path.complete_milestone(1)
        path.complete_milestone(2)
        p = path.progress
        assert p["completed"] == 2
        assert p["percent"] == pytest.approx(28.6, abs=0.1)

    def test_invalid_step_raises(self):
        path = PaidDeploymentPath("c1", "o1")
        with pytest.raises(ValueError):
            path.complete_milestone(99)

class TestReferenceDeployment:
    def test_reference(self):
        ref = ReferenceDeployment()
        assert ref.timeline_weeks == 3
        assert ref.hypercare_days == 30
        assert len(ref.connector_set) == 5
        assert len(ref.common_issues) >= 4
        assert len(ref.kpi_baseline) >= 4

class TestEndToEndConversion:
    """Golden: Full pilot-to-production conversion."""

    def test_complete_conversion_lifecycle(self):
        # 1. Create production offer
        offer = ProductionOffer(offer_id="offer-lh-001", customer_id="cust-acme", tier="standard")
        assert offer.annual_value == 30000.0

        # 2. Verify scope
        assert len(SCOPE_DOCUMENT["included"]) == 10

        # 3. Verify support SLA
        sla = SUPPORT_SLA[offer.support_level]
        assert sla["availability"] == "99.5%"

        # 4. Execute deployment path
        path = PaidDeploymentPath(offer.customer_id, offer.offer_id)

        # Contract signed
        path.complete_milestone(1)
        assert path.progress["next_step"] == "tenant_created"

        # Tenant + connectors + data
        path.complete_milestone(2)
        path.complete_milestone(3)
        path.complete_milestone(4)

        # Training
        assert len(OPERATOR_ENABLEMENT_CHECKLIST) == 10
        path.complete_milestone(5)

        # Go-live
        path.complete_milestone(6)

        # Hypercare
        path.complete_milestone(7)
        assert path.progress["is_live"]

        # 5. Reference deployment matches
        ref = ReferenceDeployment()
        assert ref.timeline_weeks == 3

        # 6. Renewal review exists
        assert RENEWAL_REVIEW["timing"] == "60 days before contract renewal"
