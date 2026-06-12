use mind_core::{
    evaluate_production_readiness_gate, generate_creative_engineering_report,
    generate_invariant_fuzz_run, production_chaos_rehearsal_plan, CreativeEngineeringReportInput,
    FuzzMutationClass, InvariantFuzzRunConfig, MindId, ProductionReadinessGatePolicy,
    ProductionReadinessStatus,
};

#[test]
fn creative_engineering_report_ranks_high_leverage_suggestions() {
    let input = CreativeEngineeringReportInput {
        observed_fractures: vec![
            "provider sdk adapters pending".to_owned(),
            "consensus replication loop incomplete".to_owned(),
        ],
        ..CreativeEngineeringReportInput::default()
    };
    let report = generate_creative_engineering_report(input).expect("report");
    assert!(!report.suggestions.is_empty());
    assert!(!report.high_leverage_first.is_empty());
    assert!(report
        .rejected_patterns
        .iter()
        .any(|pattern| pattern.contains("mutation before event append")));
}

#[test]
fn chaos_rehearsal_plan_is_hash_verifiable() {
    let mind_id = MindId::new();
    let plan = production_chaos_rehearsal_plan(Some(mind_id)).expect("plan");
    assert!(plan.experiments.len() >= 8);
    plan.verify().expect("plan hash verifies");
}

#[test]
fn invariant_fuzzer_generates_destructive_and_valid_cases() {
    let report = generate_invariant_fuzz_run(
        MindId::new(),
        InvariantFuzzRunConfig {
            seed: 31,
            cases: 32,
            include_valid: true,
            include_projection_probes: true,
        },
    )
    .expect("fuzz run");
    assert!(report.expected_reject_count > 0);
    assert!(report.expected_accept_count > 0);
    assert!(report
        .cases
        .iter()
        .any(|case| case.class == FuzzMutationClass::ImmutableIdentityChange));
}

#[test]
fn readiness_gate_blocks_missing_fuzz_or_chaos_inputs() {
    let creative = generate_creative_engineering_report(CreativeEngineeringReportInput::default())
        .expect("creative report");
    let gate = evaluate_production_readiness_gate(
        &creative,
        None,
        None,
        ProductionReadinessGatePolicy::default(),
    )
    .expect("gate");
    assert_eq!(gate.status, ProductionReadinessStatus::Blocked);
    assert!(gate.blockers.len() >= 2);
}
