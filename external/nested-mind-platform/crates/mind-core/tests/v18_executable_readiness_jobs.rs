use mind_core::{
    apply_readiness_waivers_to_gate, certify_readiness_waiver, execute_chaos_rehearsal_plan,
    execute_invariant_fuzz_run, generate_creative_engineering_report, generate_invariant_fuzz_run,
    production_chaos_rehearsal_plan, schedule_engineering_implementation_jobs, ChaosExecutionMode,
    ChaosExecutionRunStatus, CreativeEngineeringReportInput, InvariantFuzzHarnessConfig,
    InvariantFuzzRunConfig, MindId, ProductionReadinessGatePolicy, ProductionReadinessStatus,
    ReadinessWaiverProposal, ReadinessWaiverVote, ReadinessWaiverVoteDecision,
};

#[test]
fn chaos_rehearsal_executes_in_deterministic_dry_run() {
    let plan = production_chaos_rehearsal_plan(Some(MindId::new())).expect("plan");
    let run = execute_chaos_rehearsal_plan(&plan, ChaosExecutionMode::DeterministicDryRun)
        .expect("chaos run");
    assert_eq!(run.status, ChaosExecutionRunStatus::Passed);
    assert_eq!(run.failed_count, 0);
    assert_eq!(run.passed_count, plan.experiments.len());
    run.verify(&plan).expect("run verifies");
}

#[test]
fn invariant_fuzz_execution_honors_strict_oracles() {
    let mind_id = MindId::new();
    let fuzz = generate_invariant_fuzz_run(
        mind_id,
        InvariantFuzzRunConfig {
            seed: 17,
            cases: 28,
            include_valid: true,
            include_projection_probes: true,
        },
    )
    .expect("fuzz run");
    let execution = execute_invariant_fuzz_run(&fuzz, InvariantFuzzHarnessConfig::default())
        .expect("fuzz execution");
    assert_eq!(execution.failed_count, 0);
    assert!(execution.passed_count >= 20);
    execution.verify().expect("execution verifies");
}

#[test]
fn readiness_waiver_can_move_blocked_gate_to_staging_only() {
    let creative = generate_creative_engineering_report(CreativeEngineeringReportInput::default())
        .expect("creative");
    let gate = mind_core::evaluate_production_readiness_gate(
        &creative,
        None,
        None,
        ProductionReadinessGatePolicy::default(),
    )
    .expect("gate");
    assert_eq!(gate.status, ProductionReadinessStatus::Blocked);
    let blocker_ids = gate
        .blockers
        .iter()
        .map(|blocker| blocker.blocker_id)
        .collect();
    let proposal = ReadinessWaiverProposal::new(
        &gate,
        blocker_ids,
        "maintainer-a",
        "staging-only exception while remediation jobs are scheduled",
        "risk-owner-a",
        None,
    )
    .expect("proposal");
    let vote = ReadinessWaiverVote::new(
        proposal.proposal_id,
        "maintainer-a",
        ReadinessWaiverVoteDecision::Approve,
        "approved for staging rehearsal only",
    )
    .expect("vote");
    let certificate = certify_readiness_waiver(proposal, vec![vote], 1).expect("certificate");
    let application = apply_readiness_waivers_to_gate(&gate, &[certificate]).expect("application");
    assert_eq!(application.remaining_blockers.len(), 0);
    assert_eq!(
        application.effective_status,
        ProductionReadinessStatus::ReadyForStaging
    );
}

#[test]
fn creative_suggestions_become_scheduled_implementation_jobs() {
    let input = CreativeEngineeringReportInput {
        observed_fractures: vec![
            "provider sdk pending".to_owned(),
            "consensus loop incomplete".to_owned(),
        ],
        ..CreativeEngineeringReportInput::default()
    };
    let report = generate_creative_engineering_report(input).expect("report");
    let plan = schedule_engineering_implementation_jobs(&report, 3, 0).expect("job plan");
    assert_eq!(plan.jobs.len(), 3);
    assert!(plan
        .jobs
        .iter()
        .all(|job| !job.acceptance_criteria.is_empty()));
    plan.verify().expect("job plan verifies");
}
