"""Phase 127 — Lighthouse Pilot Execution Tests."""
import pytest
from mcoi_runtime.pilot.customer_profile import PilotCustomerProfile
from mcoi_runtime.pilot.target_list import TargetListBuilder
from mcoi_runtime.pilot.pilot_charter import PilotCharter
from mcoi_runtime.pilot.live_deployment import LivePilotDeployment
from mcoi_runtime.pilot.dry_run import PilotDryRunner, DryRunReport
from mcoi_runtime.pilot.weekly_tracker import WeeklyPilotTracker, WeeklySnapshot, FeedbackEntry

def _profiles():
    return [
        PilotCustomerProfile("c1", "Acme Financial", "finance", "compliance", 10, "VP Compliance", "Sr Analyst", 200,
                           ("slow_approvals", "missing_evidence", "late_reports"), ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
        PilotCustomerProfile("c2", "Beta Healthcare", "healthcare", "audit", 6, "Chief Audit", "Audit Lead", 80,
                           ("poor_tracking", "evidence_gaps"), ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
        PilotCustomerProfile("c3", "Gamma Retail", "retail", "service_governance", 3, "", "Manager", 10,
                           ("slow_response",), ("email", "ticketing")),
        PilotCustomerProfile("c4", "Delta Energy", "energy", "remediation", 15, "COO", "Remediation Lead", 300,
                           ("regulatory_pressure", "audit_findings", "evidence_collection"), ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")),
        PilotCustomerProfile("c5", "Epsilon Tech", "technology", "compliance", 4, "CTO", "Compliance Mgr", 25,
                           ("manual_processes", "reporting_delays"), ("email", "identity_sso", "document_storage")),
    ]

class TestTargetList:
    def test_rank_5_candidates(self):
        builder = TargetListBuilder()
        for p in _profiles():
            builder.add_candidate(p)
        ranked = builder.rank_and_designate()
        assert len(ranked) == 5
        assert ranked[0].designation == "primary"
        assert ranked[0].fit_level == "strong"

    def test_primary_is_strongest(self):
        builder = TargetListBuilder()
        for p in _profiles():
            builder.add_candidate(p)
        builder.rank_and_designate()
        primary = builder.primary
        assert primary is not None
        assert primary.fit_score >= 5

    def test_backups_exist(self):
        builder = TargetListBuilder()
        for p in _profiles():
            builder.add_candidate(p)
        builder.rank_and_designate()
        assert len(builder.backups) == 2

    def test_summary(self):
        builder = TargetListBuilder()
        for p in _profiles():
            builder.add_candidate(p)
        builder.rank_and_designate()
        s = builder.summary()
        assert s["total_candidates"] == 5
        assert s["primary"] is not None

class TestPilotCharter:
    def test_charter_creation(self):
        profile = _profiles()[0]
        charter = PilotCharter(charter_id="charter-001", customer=profile)
        assert len(charter.scope) == 8
        assert len(charter.excluded_scope) == 5
        assert charter.duration_weeks == 6

    def test_success_metrics(self):
        charter = PilotCharter(charter_id="ch1", customer=_profiles()[0])
        assert len(charter.success_metrics) >= 6

    def test_stakeholder_list(self):
        charter = PilotCharter(charter_id="ch1", customer=_profiles()[0])
        stakeholders = charter.stakeholder_list()
        assert stakeholders["executive_sponsor"]
        assert stakeholders["operator_lead"]

    def test_kickoff_agenda(self):
        charter = PilotCharter(charter_id="ch1", customer=_profiles()[0])
        agenda = charter.kickoff_agenda()
        assert len(agenda) == 10

    def test_weekly_review(self):
        charter = PilotCharter(charter_id="ch1", customer=_profiles()[0])
        review = charter.weekly_review_template()
        assert len(review["sections"]) >= 5
        assert review["duration_minutes"] == 30

class TestDryRun:
    def test_go_decision(self):
        deployment = LivePilotDeployment()
        profile = _profiles()[0]
        deployment.deploy(profile)
        engines = deployment.bootstrap.engines

        runner = PilotDryRunner()
        report = runner.run(profile.customer_id, engines)
        assert report.go_decision == "go"
        assert len(report.defects) == 0

    def test_no_go_empty(self):
        runner = PilotDryRunner()
        report = runner.run("empty", {})
        assert report.go_decision == "no_go"

class TestFullLighthousePilot:
    """Golden: Complete lighthouse pilot lifecycle."""

    def test_end_to_end_lighthouse(self):
        # 1. Build target list
        builder = TargetListBuilder()
        for p in _profiles():
            builder.add_candidate(p)
        ranked = builder.rank_and_designate()
        primary = builder.primary
        assert primary.fit_level == "strong"

        # 2. Create charter
        charter = PilotCharter(charter_id="charter-lighthouse", customer=primary.profile)
        assert len(charter.scope) == 8

        # 3. Deploy
        deployment = LivePilotDeployment()
        report = deployment.deploy(primary.profile)
        assert report.is_ready

        # 4. Import data
        dataset = {
            "cases": [{"case_id": f"lh-c-{i}", "title": f"Case {i}"} for i in range(20)],
            "remediations": [{"remediation_id": f"lh-r-{i}", "case_ref": f"lh-c-{i}", "title": f"Rem {i}"} for i in range(10)],
            "records": [{"record_id": f"lh-rec-{i}", "title": f"Evidence {i}"} for i in range(15)],
        }
        import_results = deployment.load_data(primary.profile.customer_id, dataset)
        assert import_results["cases"].accepted == 20

        # 5. Dry run
        runner = PilotDryRunner()
        dry = runner.run(primary.profile.customer_id, deployment.bootstrap.engines)
        assert dry.go_decision == "go"

        # 6. Weekly tracking (simulate 6 weeks)
        tracker = WeeklyPilotTracker(primary.profile.customer_id)
        for week in range(1, 7):
            tracker.record_week(WeeklySnapshot(
                week_number=week, tenant_id=primary.profile.customer_id,
                cases_created=8+week*2, cases_closed=5+week*2,
                remediations_completed=3+week, approvals_processed=6+week*2,
                evidence_bundles_generated=4+week, reports_generated=2+week,
                connector_uptime_percent=99.9, connector_failures=0,
                dashboard_views=30+week*10, copilot_queries=15+week*5,
                time_saved_hours=8+week*3, missed_work_reduction_percent=20+week*5,
                operator_satisfaction=7.5+week*0.2, executive_satisfaction=8.0+week*0.15,
            ))

        # 7. Collect feedback
        tracker.record_feedback(FeedbackEntry("operator", "Highest value?", "Evidence retrieval + copilot drafting", "positive", 6))
        tracker.record_feedback(FeedbackEntry("executive", "Highest value?", "Compliance visibility + reporting speed", "positive", 6))
        tracker.record_feedback(FeedbackEntry("operator", "What was confusing?", "Initial connector setup", "negative", 2))

        # 8. Promotion decision
        decision = tracker.evaluate_promotion()
        assert decision.decision == "promote"

        # Summary
        summary = tracker.summary()
        assert summary["weeks_tracked"] == 6
        assert summary["feedback_entries"] == 3
        assert summary["latest_decision"] == "promote"
