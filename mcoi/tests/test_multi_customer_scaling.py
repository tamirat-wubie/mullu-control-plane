"""Phase 129 — Multi-Customer Deployment Scaling Tests."""
import pytest
from mcoi_runtime.pilot.customer_profile import PilotCustomerProfile
from mcoi_runtime.pilot.deployment_factory import DeploymentFactory, REGULATED_OPS_TEMPLATE
from mcoi_runtime.pilot.multi_tenant_ops import MultiTenantOperations, TenantHealthScore, RenewalRisk
from mcoi_runtime.pilot.revenue_funnel import RevenueFunnel

def _profile(cid: str, name: str) -> PilotCustomerProfile:
    return PilotCustomerProfile(cid, name, "finance", "compliance", 10, "VP", "Lead", 100,
                                ("slow_approvals", "missing_evidence"), ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"))

class TestDeploymentFactory:
    def test_deploy_first_customer(self):
        factory = DeploymentFactory()
        fd = factory.deploy_customer(_profile("c1", "Acme Corp"))
        assert fd.verification_passed
        assert factory.deployment_count == 1

    def test_deploy_three_customers(self):
        factory = DeploymentFactory()
        for i in range(3):
            fd = factory.deploy_customer(_profile(f"c{i}", f"Corp {i}"))
            assert fd.verification_passed
        assert factory.deployment_count == 3
        assert factory.success_rate == 1.0

    def test_summary(self):
        factory = DeploymentFactory()
        factory.deploy_customer(_profile("c1", "A"))
        factory.deploy_customer(_profile("c2", "B"))
        s = factory.summary()
        assert s["deployments"] == 2
        assert len(s["customers"]) == 2

class TestMultiTenantOps:
    def test_register_and_health(self):
        ops = MultiTenantOperations()
        ops.register_tenant("t1")
        ops.register_tenant("t2")
        assert ops.tenant_count == 2

    def test_health_scoring(self):
        h = TenantHealthScore("t1", connector_health=1.0, workflow_completion_rate=0.95, slo_compliance=1.0, operator_satisfaction=9.0)
        assert h.status == "healthy"
        assert h.composite_score >= 0.9

    def test_at_risk_detection(self):
        ops = MultiTenantOperations()
        ops.register_tenant("t1")
        ops.update_health("t1", connector_health=0.3, workflow_completion_rate=0.4, slo_compliance=0.3, operator_satisfaction=3.0)
        assert "t1" in ops.at_risk_tenants

    def test_renewal_risk(self):
        ops = MultiTenantOperations()
        ops.register_tenant("t1")
        ops.update_health("t1", connector_health=0.5)
        risk = ops.register_renewal("t1", days_until=30, satisfaction_trend="declining")
        assert risk.risk_level == "high"

    def test_support_tickets(self):
        ops = MultiTenantOperations()
        ops.register_tenant("t1")
        ops.add_support_ticket("t1", "Connector down", "critical")
        ops.add_support_ticket("t1", "Dashboard slow", "low")
        assert ops._tenants["t1"].support_ticket_count == 2

    def test_dashboard(self):
        ops = MultiTenantOperations()
        ops.register_tenant("t1")
        ops.register_tenant("t2")
        ops.update_health("t2", connector_health=0.3, slo_compliance=0.2, operator_satisfaction=2.0)
        d = ops.dashboard()
        assert d["total_tenants"] == 2
        assert d["at_risk"] >= 1

class TestRevenueFunnel:
    def test_full_funnel(self):
        funnel = RevenueFunnel()
        funnel.record_demo("c1")
        funnel.record_demo("c2")
        funnel.record_demo("c3")
        funnel.convert_to_pilot("c1")
        funnel.convert_to_pilot("c2")
        funnel.convert_to_paid("c1", 2500.0)
        funnel.convert_to_paid("c2", 7500.0)
        funnel.record_renewal("c1")
        funnel.record_expansion("c1", 1000.0)

        s = funnel.funnel_summary()
        assert s["stages"]["demo"]["count"] == 3
        assert s["stages"]["demo"]["converted"] == 2
        assert s["stages"]["paid"]["count"] == 2
        assert s["total_mrr"] == 10000.0
        assert s["total_arr"] == 120000.0

    def test_conversion_rates(self):
        funnel = RevenueFunnel()
        for i in range(10):
            funnel.record_demo(f"d{i}")
        for i in range(4):
            funnel.convert_to_pilot(f"d{i}")
        for i in range(2):
            funnel.convert_to_paid(f"d{i}", 2500.0)

        s = funnel.funnel_summary()
        assert s["stages"]["demo"]["rate"] == pytest.approx(0.4, abs=0.01)
        assert s["stages"]["pilot"]["rate"] == pytest.approx(0.5, abs=0.01)

class TestEndToEndScaling:
    """Golden: Deploy 3 customers, track health, measure revenue."""

    def test_three_customer_scaling(self):
        # 1. Deploy 3 customers
        factory = DeploymentFactory()
        customers = [_profile(f"scale-{i}", f"Scale Corp {i}") for i in range(3)]
        for c in customers:
            fd = factory.deploy_customer(c)
            assert fd.verification_passed
        assert factory.success_rate == 1.0

        # 2. Track tenant health
        ops = MultiTenantOperations()
        for c in customers:
            ops.register_tenant(c.customer_id)
        ops.update_health("scale-0", operator_satisfaction=9.0)
        ops.update_health("scale-1", operator_satisfaction=7.5)
        ops.update_health("scale-2", connector_health=0.6, operator_satisfaction=5.0)

        d = ops.dashboard()
        assert d["total_tenants"] == 3
        assert d["healthy"] >= 1

        # 3. Revenue funnel
        funnel = RevenueFunnel()
        for c in customers:
            funnel.record_demo(c.customer_id)
            funnel.convert_to_pilot(c.customer_id)
            funnel.convert_to_paid(c.customer_id, 2500.0)

        s = funnel.funnel_summary()
        assert s["total_mrr"] == 7500.0
        assert s["total_arr"] == 90000.0
        assert s["stages"]["paid"]["count"] == 3

        # 4. Renewal tracking
        ops.register_renewal("scale-0", 60, "improving")
        ops.register_renewal("scale-2", 30, "declining")
        assert len(ops.high_risk_renewals) >= 1
