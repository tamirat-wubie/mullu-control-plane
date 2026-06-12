use mind_core::*;
use mind_store_sqlite::SqliteEventStore;
use std::collections::BTreeMap;
use time::{Duration, OffsetDateTime};

#[test]
fn sqlite_v19_persists_enforced_readiness_ledgers() {
    let mut store = SqliteEventStore::in_memory().expect("store");
    let schema = store.schema_report().expect("schema");
    assert_eq!(schema.current_version_after, PLATFORM_SCHEMA_VERSION);

    let mind_id = MindId::new();
    let chaos_plan = production_chaos_rehearsal_plan(Some(mind_id)).expect("chaos plan");
    let staging = run_staging_chaos_rehearsal(
        &chaos_plan,
        StagingChaosEnvironment::staging("nested-mind-staging"),
        StagingChaosRunMode::GuardedDryRun,
        StagingChaosSafetyPolicy::default(),
    )
    .expect("staging chaos");
    store
        .record_staging_chaos_run_report(&staging)
        .expect("record staging");
    assert_eq!(
        store
            .staging_chaos_run_reports()
            .expect("staging reports")
            .len(),
        1
    );

    let fuzz =
        generate_invariant_fuzz_run(mind_id, InvariantFuzzRunConfig::default()).expect("fuzz");
    let fuzz_execution = execute_invariant_fuzz_run(&fuzz, InvariantFuzzHarnessConfig::default())
        .expect("fuzz exec");
    let creative = generate_creative_engineering_report(CreativeEngineeringReportInput::default())
        .expect("creative");
    let gate = evaluate_production_readiness_gate(
        &creative,
        Some(&chaos_plan),
        Some(&fuzz),
        ProductionReadinessGatePolicy::default(),
    )
    .expect("gate");
    let ci = evaluate_mandatory_ci_gate(
        MandatoryCiGateInput {
            rust_format: CiCheckStatus::Passed,
            clippy: CiCheckStatus::Passed,
            unit_tests: CiCheckStatus::Passed,
            executable_readiness_tests: CiCheckStatus::Passed,
            readiness_gate: Some(gate.clone()),
            chaos_execution: Some(staging.inner_run.clone()),
            invariant_fuzz_execution: Some(fuzz_execution),
            staging_chaos: Some(staging),
            pull_request: Some("PR-19".to_owned()),
        },
        MandatoryCiGatePolicy::default(),
    )
    .expect("ci");
    store
        .record_mandatory_ci_gate_report(&ci)
        .expect("record ci");
    assert_eq!(
        store.mandatory_ci_gate_reports().expect("ci reports").len(),
        1
    );

    let proposal = ReadinessWaiverProposal::new(
        &gate,
        gate.blockers
            .iter()
            .map(|blocker| blocker.blocker_id)
            .collect(),
        "maintainer-a",
        "waiver",
        "risk-owner-a",
        Some(OffsetDateTime::now_utc() + Duration::days(1)),
    )
    .expect("proposal");
    let votes = vec![
        MultiOperatorWaiverVote::new(
            proposal.proposal_id,
            "maintainer-a",
            WaiverOperatorRole::Maintainer,
            "platform",
            ReadinessWaiverVoteDecision::Approve,
            "ok",
        )
        .expect("vote"),
        MultiOperatorWaiverVote::new(
            proposal.proposal_id,
            "security-a",
            WaiverOperatorRole::Security,
            "security",
            ReadinessWaiverVoteDecision::Approve,
            "ok",
        )
        .expect("vote"),
    ];
    let certificate = certify_multi_operator_readiness_waiver(
        proposal,
        &gate,
        votes,
        MultiOperatorWaiverPolicy::default(),
    )
    .expect("cert");
    store
        .record_multi_operator_waiver_certificate(&certificate)
        .expect("record cert");
    assert_eq!(
        store
            .multi_operator_waiver_certificates()
            .expect("certs")
            .len(),
        1
    );

    let impl_plan = schedule_engineering_implementation_jobs(&creative, 1, 0).expect("impl plan");
    let automation =
        plan_implementation_evidence_automation(&impl_plan, "mullusi/nested-mind-platform", "main")
            .expect("automation");
    store
        .record_implementation_evidence_automation_plan(&automation)
        .expect("record automation");
    assert_eq!(
        store
            .implementation_evidence_automation_plans()
            .expect("automation plans")
            .len(),
        1
    );
    let job = impl_plan.jobs.first().expect("job");
    let target = automation.targets.first().expect("target");
    let mut artifacts = synthetic_pull_request_evidence(target, "sqlite-test").expect("evidence");
    artifacts.push(
        ImplementationEvidenceArtifact::new(
            ImplementationEvidenceKind::ReadinessGate,
            "readiness",
            "ci://readiness",
            "sqlite-test",
            BTreeMap::from([("status".to_owned(), "passed".to_owned())]),
        )
        .expect("readiness artifact"),
    );
    artifacts.push(
        ImplementationEvidenceArtifact::new(
            ImplementationEvidenceKind::RollbackPlan,
            "rollback",
            "docs://rollback",
            "sqlite-test",
            BTreeMap::from([("status".to_owned(), "passed".to_owned())]),
        )
        .expect("rollback artifact"),
    );
    let bundle = attach_implementation_evidence(
        job,
        artifacts,
        default_implementation_evidence_requirements(),
    )
    .expect("bundle");
    store
        .record_implementation_job_evidence_bundle(&bundle)
        .expect("record bundle");
    assert_eq!(
        store
            .implementation_job_evidence_bundles()
            .expect("bundles")
            .len(),
        1
    );
}
