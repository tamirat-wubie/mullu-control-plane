use mind_core::{
    AppendOnlyEventStore, EditProposal, EvolutionEngine, Mind, SignatureRequirement,
    SnapshotRecord, SnapshotStore, StatePatch, SymbolValue,
};
use mind_store_sqlite::SqliteEventStore;

#[test]
fn sqlite_store_persists_snapshot_records_transactionally() {
    let mut mind = Mind::new_root("root");
    let mut store = SqliteEventStore::in_memory()
        .expect("store opens")
        .with_signature_requirement(SignatureRequirement::Optional);
    let proposal = EditProposal::new(
        mind.id(),
        "test",
        "set goal",
        StatePatch::new().set("goal", SymbolValue::from("sqlite snapshot")),
    );
    let plan = EvolutionEngine::evaluate(&mind, proposal).expect("proposal evaluates");
    store.append(plan.commit().clone()).expect("event appends");
    EvolutionEngine::apply_plan(&mut mind, plan).expect("plan applies");

    let records = store.records_for_mind(mind.id()).expect("records load");
    let snapshot = SnapshotRecord::capture(&mind, records.last()).expect("snapshot captures");
    store
        .save_snapshot(snapshot.clone())
        .expect("snapshot saves");
    let loaded = store
        .latest_snapshot_for_mind(mind.id())
        .expect("snapshot loads")
        .expect("latest exists");
    assert_eq!(loaded.snapshot_hash, snapshot.snapshot_hash);
}
