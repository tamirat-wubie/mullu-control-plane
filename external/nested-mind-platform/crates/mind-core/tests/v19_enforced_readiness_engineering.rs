use mind_core::*;
use std::collections::BTreeMap;
use time::{Duration, OffsetDateTime};

#[test]
fn staging_chaos_and_ci_gate_produce_hash_bound_evidence() {
    let mind_id = MindId::new();
    let chaos_plan = production_chaos_rehearsal_plan(Some(mind_id)).expect("chaos plan");
    let staging = run_staging_chaos_rehearsal(
        &chaos_plan,
        StagingChaosEnvironment::staging("nested-mind-staging"),
        StagingChaosRunMode::GuardedDryRun,
        StagingChaosSafetyPolicy::default(),
    )
    .expect("staging chaos");
    staging.verify(&chaos_plan).expect("staging chaos verifies");

    let fuzz =
        generate_invariant_fuzz_run(mind_id, InvariantFuzzRunConfig::default()).expect("fuzz bank");
    let fuzz_execution = execute_invariant_fuzz_run(&fuzz, InvariantFuzzHarnessConfig::default())
        .expect("fuzz exec");
    fuzz_execution.verify().expect("fuzz execution verifies");

    let creative = generate_creative_engineering_report(CreativeEngineeringReportInput::default())
        .expect("creative");
    let readiness = evaluate_production_readiness_gate(
        &creative,
        Some(&chaos_plan),
        Some(&fuzz),
        ProductionReadinessGatePolicy::default(),
    )
    .expect("readiness gate");

    let input = MandatoryCiGateInput {
        rust_format: CiCheckStatus::Passed,
        clippy: CiCheckStatus::Passed,
        unit_tests: CiCheckStatus::Passed,
        executable_readiness_tests: CiCheckStatus::Passed,
        readiness_gate: Some(readiness),
        chaos_execution: Some(staging.inner_run.clone()),
        invariant_fuzz_execution: Some(fuzz_execution),
        staging_chaos: Some(staging),
        pull_request: Some("PR-19".to_owned()),
    };
    let report =
        evaluate_mandatory_ci_gate(input, MandatoryCiGatePolicy::default()).expect("ci gate");
    report.verify().expect("ci gate verifies");
}

#[test]
fn multi_operator_waiver_requires_role_and_team_separation() {
    let creative = generate_creative_engineering_report(CreativeEngineeringReportInput::default())
        .expect("creative");
    let gate = evaluate_production_readiness_gate(
        &creative,
        None,
        None,
        ProductionReadinessGatePolicy::default(),
    )
    .expect("blocked gate");
    let blocker_ids = gate
        .blockers
        .iter()
        .map(|blocker| blocker.blocker_id)
        .collect::<Vec<_>>();
    let proposal = ReadinessWaiverProposal::new(
        &gate,
        blocker_ids,
        "maintainer-a",
        "staging-only exception with follow-up implementation jobs",
        "risk-owner-a",
        Some(OffsetDateTime::now_utc() + Duration::days(3)),
    )
    .expect("proposal");
    let votes = vec![
        MultiOperatorWaiverVote::new(
            proposal.proposal_id,
            "maintainer-a",
            WaiverOperatorRole::Maintainer,
            "platform",
            ReadinessWaiverVoteDecision::Approve,
            "platform approval",
        )
        .expect("maintainer vote"),
        MultiOperatorWaiverVote::new(
            proposal.proposal_id,
            "security-a",
            WaiverOperatorRole::Security,
            "security",
            ReadinessWaiverVoteDecision::Approve,
            "security approval",
        )
        .expect("security vote"),
    ];
    let certificate = certify_multi_operator_readiness_waiver(
        proposal,
        &gate,
        votes,
        MultiOperatorWaiverPolicy::default(),
    )
    .expect("certificate");
    certificate.verify().expect("certificate verifies");
    assert_eq!(certificate.status, ReadinessWaiverStatus::Approved);
}

#[test]
fn implementation_evidence_requires_pr_tests_readiness_and_rollback() {
    let report = generate_creative_engineering_report(CreativeEngineeringReportInput::default())
        .expect("creative");
    let plan = schedule_engineering_implementation_jobs(&report, 1, 0).expect("job plan");
    let automation =
        plan_implementation_evidence_automation(&plan, "mullusi/nested-mind-platform", "main")
            .expect("automation plan");
    automation.verify().expect("automation verifies");
    let job = plan.jobs.first().expect("job");
    let target = automation.targets.first().expect("target");
    let mut artifacts =
        synthetic_pull_request_evidence(target, "test-runner").expect("synthetic evidence");
    artifacts.push(
        ImplementationEvidenceArtifact::new(
            ImplementationEvidenceKind::ReadinessGate,
            "mandatory readiness gate",
            "ci://readiness/v19",
            "test-runner",
            BTreeMap::from([("status".to_owned(), "passed".to_owned())]),
        )
        .expect("readiness evidence"),
    );
    artifacts.push(
        ImplementationEvidenceArtifact::new(
            ImplementationEvidenceKind::RollbackPlan,
            "rollback plan",
            "docs://rollback/v19",
            "test-runner",
            BTreeMap::from([("status".to_owned(), "passed".to_owned())]),
        )
        .expect("rollback evidence"),
    );
    let bundle = attach_implementation_evidence(
        job,
        artifacts,
        default_implementation_evidence_requirements(),
    )
    .expect("bundle");
    bundle.verify().expect("bundle verifies");
    assert_eq!(bundle.status, ImplementationEvidenceStatus::Satisfied);
}
