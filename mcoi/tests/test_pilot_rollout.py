"""Phase 126 — Live Pilot Rollout Tests."""
import pytest
from mcoi_runtime.pilot.customer_profile import PilotCustomerProfile, SELECTION_CRITERIA, evaluate_fit
from mcoi_runtime.pilot.live_deployment import LivePilotDeployment, DeploymentReport
from mcoi_runtime.pilot.weekly_tracker import WeeklyPilotTracker, WeeklySnapshot, FeedbackEntry

def _good_profile() -> PilotCustomerProfile:
    return PilotCustomerProfile(
        customer_id="cust-001",
        organization_name="Acme Regulated Corp",
        industry="financial_services",
        team_type="compliance",
        operator_count=8,
        executive_sponsor="Jane Smith, VP Compliance",
        operator_lead="John Doe, Sr. Analyst",
        historical_case_count=150,
        pain_points=("slow_approvals", "missing_evidence", "late_reports"),
        connector_surface=("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
    )

class TestCustomerProfile:
    def test_strong_fit(self):
        result = evaluate_fit(_good_profile())
        assert result["fit"] == "strong"
        assert result["score"] >= 5

    def test_weak_fit(self):
        weak = PilotCustomerProfile(
            customer_id="w1", organization_name="Small Co", industry="retail",
            team_type="service", operator_count=1, executive_sponsor="",
            operator_lead="", historical_case_count=5, pain_points=(),
            connector_surface=("email", "sso", "storage", "ticket", "report", "chat", "calendar"),
        )
        result = evaluate_fit(weak)
        assert result["fit"] == "weak"

    def test_selection_criteria_exist(self):
        assert len(SELECTION_CRITERIA) == 6

class TestLiveDeployment:
    def test_deploy_succeeds(self):
        deployment = LivePilotDeployment()
        report = deployment.deploy(_good_profile())
        assert report.bootstrap_status == "ready"
        assert report.connectors_activated == 5
        assert report.personas_created == 4
        assert report.governance_rules == 3
        assert report.is_ready

    def test_deploy_report_fields(self):
        deployment = LivePilotDeployment()
        report = deployment.deploy(_good_profile())
        assert report.tenant_id == "cust-001"

    def test_load_data(self):
        deployment = LivePilotDeployment()
        deployment.deploy(_good_profile())
        dataset = {
            "cases": [{"case_id": f"real-c-{i}", "title": f"Case {i}"} for i in range(10)],
            "remediations": [{"remediation_id": f"real-r-{i}", "case_ref": f"real-c-{i}", "title": f"Rem {i}"} for i in range(5)],
        }
        results = deployment.load_data("cust-001", dataset)
        assert results["cases"].accepted == 10
        assert results["remediations"].accepted == 5

class TestWeeklyTracker:
    def test_record_and_evaluate(self):
        tracker = WeeklyPilotTracker("cust-001")
        snap = WeeklySnapshot(
            week_number=1, tenant_id="cust-001",
            cases_created=15, cases_closed=8, remediations_completed=5,
            approvals_processed=12, evidence_bundles_generated=6, reports_generated=3,
            connector_uptime_percent=99.8, connector_failures=0,
            dashboard_views=45, copilot_queries=20,
            time_saved_hours=12.5, missed_work_reduction_percent=30.0,
            operator_satisfaction=8.5, executive_satisfaction=9.0,
        )
        tracker.record_week(snap)
        decision = tracker.evaluate_promotion()
        assert decision.decision == "promote"

    def test_extend_decision(self):
        tracker = WeeklyPilotTracker("cust-002")
        snap = WeeklySnapshot(
            week_number=1, tenant_id="cust-002",
            cases_created=5, cases_closed=2,
            connector_uptime_percent=99.5, dashboard_views=15,
            executive_satisfaction=5.0,
        )
        tracker.record_week(snap)
        decision = tracker.evaluate_promotion()
        assert decision.decision == "extend"

    def test_stop_decision(self):
        tracker = WeeklyPilotTracker("cust-003")
        snap = WeeklySnapshot(week_number=1, tenant_id="cust-003")
        tracker.record_week(snap)
        decision = tracker.evaluate_promotion()
        assert decision.decision == "stop"

    def test_feedback(self):
        tracker = WeeklyPilotTracker("cust-001")
        tracker.record_feedback(FeedbackEntry("operator", "What was confusing?", "Connector setup was unclear", "negative", 1))
        tracker.record_feedback(FeedbackEntry("executive", "What felt high value?", "Evidence completeness dashboard", "positive", 1))
        assert len(tracker.feedback) == 2

    def test_summary(self):
        tracker = WeeklyPilotTracker("cust-001")
        s = tracker.summary()
        assert s["tenant_id"] == "cust-001"
        assert s["latest_decision"] == "no_data"

    def test_no_data_stops(self):
        tracker = WeeklyPilotTracker("empty")
        assert tracker.evaluate_promotion().decision == "stop"

class TestEndToEndPilotRollout:
    """Golden scenario: full pilot lifecycle."""

    def test_complete_pilot_lifecycle(self):
        # 1. Evaluate customer fit
        profile = _good_profile()
        fit = evaluate_fit(profile)
        assert fit["fit"] == "strong"

        # 2. Deploy tenant
        deployment = LivePilotDeployment()
        report = deployment.deploy(profile)
        assert report.is_ready

        # 3. Load historical data
        dataset = {
            "cases": [{"case_id": f"hist-{i}", "title": f"Historical case {i}"} for i in range(20)],
            "remediations": [{"remediation_id": f"hist-r-{i}", "case_ref": f"hist-{i}", "title": f"Rem {i}"} for i in range(10)],
            "records": [{"record_id": f"hist-rec-{i}", "title": f"Evidence {i}"} for i in range(15)],
        }
        import_results = deployment.load_data(profile.customer_id, dataset)
        assert import_results["cases"].accepted == 20

        # 4. Track weekly metrics
        tracker = WeeklyPilotTracker(profile.customer_id)
        for week in range(1, 5):
            tracker.record_week(WeeklySnapshot(
                week_number=week, tenant_id=profile.customer_id,
                cases_created=10+week, cases_closed=5+week,
                remediations_completed=3+week, approvals_processed=8+week,
                evidence_bundles_generated=4+week, reports_generated=2,
                connector_uptime_percent=99.9, connector_failures=0,
                dashboard_views=30+week*5, copilot_queries=15+week*3,
                time_saved_hours=10+week*2, missed_work_reduction_percent=25+week*5,
                operator_satisfaction=7.5+week*0.3, executive_satisfaction=8.0+week*0.2,
            ))

        # 5. Collect feedback
        tracker.record_feedback(FeedbackEntry("operator", "What was high value?", "Evidence retrieval saved hours", "positive", 4))
        tracker.record_feedback(FeedbackEntry("executive", "What was high value?", "Compliance dashboard gives real visibility", "positive", 4))

        # 6. Evaluate promotion
        decision = tracker.evaluate_promotion()
        assert decision.decision == "promote"
        assert decision.criteria_met["connectors_stable"]
        assert decision.criteria_met["workflows_completing"]

        # Summary
        summary = tracker.summary()
        assert summary["weeks_tracked"] == 4
        assert summary["feedback_entries"] == 2
        assert summary["latest_decision"] == "promote"
