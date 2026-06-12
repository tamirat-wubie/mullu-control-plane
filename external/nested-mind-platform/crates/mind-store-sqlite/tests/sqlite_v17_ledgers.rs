use mind_core::{
    evaluate_production_readiness_gate, generate_creative_engineering_report,
    generate_invariant_fuzz_run, production_chaos_rehearsal_plan, CreativeEngineeringReportInput,
    InvariantFuzzRunConfig, MindId, ProductionReadinessGatePolicy,
};
use mind_store_sqlite::SqliteEventStore;

#[test]
fn sqlite_v17_ledgers_persist_creative_rehearsal_fuzz_and_gate_reports() {
    let mut store = SqliteEventStore::in_memory().expect("store");
    let mind_id = MindId::new();
    let creative = generate_creative_engineering_report(CreativeEngineeringReportInput::default())
        .expect("creative");
    let chaos = production_chaos_rehearsal_plan(Some(mind_id)).expect("chaos");
    let fuzz = generate_invariant_fuzz_run(
        mind_id,
        InvariantFuzzRunConfig {
            cases: 16,
            ..InvariantFuzzRunConfig::default()
        },
    )
    .expect("fuzz");
    let gate = evaluate_production_readiness_gate(
        &creative,
        Some(&chaos),
        Some(&fuzz),
        ProductionReadinessGatePolicy::default(),
    )
    .expect("gate");

    store
        .record_creative_engineering_report(&creative)
        .expect("record creative");
    store
        .record_chaos_rehearsal_plan(&chaos)
        .expect("record chaos");
    store
        .record_invariant_fuzz_run_report(&fuzz)
        .expect("record fuzz");
    store
        .record_production_readiness_gate_report(&gate)
        .expect("record gate");

    assert_eq!(store.creative_engineering_reports().unwrap().len(), 1);
    assert_eq!(store.chaos_rehearsal_plans().unwrap().len(), 1);
    assert_eq!(store.invariant_fuzz_run_reports().unwrap().len(), 1);
    assert_eq!(store.production_readiness_gate_reports().unwrap().len(), 1);
}
