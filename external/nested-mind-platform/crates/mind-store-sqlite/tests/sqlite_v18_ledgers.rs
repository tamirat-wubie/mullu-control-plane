use mind_core::{
    apply_readiness_waivers_to_gate, certify_readiness_waiver, execute_chaos_rehearsal_plan,
    execute_invariant_fuzz_run, generate_creative_engineering_report, generate_invariant_fuzz_run,
    production_chaos_rehearsal_plan, schedule_engineering_implementation_jobs, ChaosExecutionMode,
    CreativeEngineeringReportInput, InvariantFuzzHarnessConfig, InvariantFuzzRunConfig, MindId,
    ProductionReadinessGatePolicy, ReadinessWaiverProposal, ReadinessWaiverVote,
    ReadinessWaiverVoteDecision,
};
use mind_store_sqlite::SqliteEventStore;

#[test]
fn sqlite_v18_ledgers_persist_executions_waivers_and_implementation_jobs() {
    let mut store = SqliteEventStore::in_memory().expect("store");
    let mind_id = MindId::new();
    let creative = generate_creative_engineering_report(CreativeEngineeringReportInput::default())
        .expect("creative");
    let chaos = production_chaos_rehearsal_plan(Some(mind_id)).expect("chaos");
    let chaos_run = execute_chaos_rehearsal_plan(&chaos, ChaosExecutionMode::DeterministicDryRun)
        .expect("chaos run");
    let fuzz = generate_invariant_fuzz_run(
        mind_id,
        InvariantFuzzRunConfig {
            cases: 24,
            ..InvariantFuzzRunConfig::default()
        },
    )
    .expect("fuzz");
    let fuzz_execution = execute_invariant_fuzz_run(&fuzz, InvariantFuzzHarnessConfig::default())
        .expect("fuzz execution");
    let gate = mind_core::evaluate_production_readiness_gate(
        &creative,
        None,
        None,
        ProductionReadinessGatePolicy::default(),
    )
    .expect("gate");
    let proposal = ReadinessWaiverProposal::new(
        &gate,
        gate.blockers
            .iter()
            .map(|blocker| blocker.blocker_id)
            .collect(),
        "maintainer-a",
        "staging waiver",
        "risk-owner-a",
        None,
    )
    .expect("proposal");
    let vote = ReadinessWaiverVote::new(
        proposal.proposal_id,
        "maintainer-a",
        ReadinessWaiverVoteDecision::Approve,
        "approve",
    )
    .expect("vote");
    let certificate =
        certify_readiness_waiver(proposal.clone(), vec![vote.clone()], 1).expect("certificate");
    let application = apply_readiness_waivers_to_gate(&gate, std::slice::from_ref(&certificate))
        .expect("application");
    let implementation =
        schedule_engineering_implementation_jobs(&creative, 2, 0).expect("implementation jobs");

    store
        .record_chaos_execution_run(&chaos_run)
        .expect("record chaos run");
    store
        .record_invariant_fuzz_execution_report(&fuzz_execution)
        .expect("record fuzz execution");
    store
        .record_readiness_waiver_proposal(&proposal)
        .expect("record waiver proposal");
    store
        .record_readiness_waiver_vote(&vote)
        .expect("record vote");
    store
        .record_readiness_waiver_certificate(&certificate)
        .expect("record certificate");
    store
        .record_readiness_waiver_application_report(&application)
        .expect("record application");
    store
        .record_engineering_implementation_job_plan(&implementation)
        .expect("record implementation plan");

    assert_eq!(store.chaos_execution_runs().unwrap().len(), 1);
    assert_eq!(store.invariant_fuzz_execution_reports().unwrap().len(), 1);
    assert_eq!(store.readiness_waiver_proposals().unwrap().len(), 1);
    assert_eq!(store.readiness_waiver_votes().unwrap().len(), 1);
    assert_eq!(store.readiness_waiver_certificates().unwrap().len(), 1);
    assert_eq!(
        store.readiness_waiver_application_reports().unwrap().len(),
        1
    );
    assert_eq!(
        store.engineering_implementation_job_plans().unwrap().len(),
        1
    );
}
