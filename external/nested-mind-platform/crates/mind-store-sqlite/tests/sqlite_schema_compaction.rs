use mind_core::{
    AppendOnlyEventStore, CompactingSnapshotStore, Ed25519CommitSigner, EditProposal,
    EvolutionEngine, Mind, SignatureRequirement, SnapshotCompactionPolicy, SnapshotRecord,
    SnapshotStore, StatePatch, SymbolValue, PLATFORM_SCHEMA_VERSION,
};
use mind_store_sqlite::SqliteEventStore;

#[test]
fn sqlite_store_records_platform_schema_version() {
    let store = SqliteEventStore::in_memory().unwrap();
    assert_eq!(
        store.schema_report().unwrap().current_version_after,
        PLATFORM_SCHEMA_VERSION
    );
}

#[test]
fn sqlite_compaction_deletes_older_snapshots() {
    let mut mind = Mind::new_root("root");
    let signer = Ed25519CommitSigner::from_seed("test", [8_u8; 32]);
    let mut store = SqliteEventStore::in_memory()
        .unwrap()
        .with_signature_requirement(SignatureRequirement::Required);

    for i in 0..3 {
        let patch =
            StatePatch::new().set(format!("sqlite.k{i}"), SymbolValue::from(format!("v{i}")));
        let proposal = EditProposal::new(mind.id(), "test", format!("patch {i}"), patch);
        let mut plan = EvolutionEngine::evaluate(&mind, proposal).unwrap();
        plan.commit_mut().sign_with(&signer).unwrap();
        let record = store.append(plan.commit().clone()).unwrap();
        EvolutionEngine::apply_plan(&mut mind, plan).unwrap();
        store
            .save_snapshot(SnapshotRecord::capture(&mind, Some(&record)).unwrap())
            .unwrap();
    }

    let decision = store
        .compact_snapshots(mind.id(), &SnapshotCompactionPolicy::new(1, 2), 3)
        .unwrap();
    assert_eq!(decision.remove_snapshot_ids.len(), 2);
    assert_eq!(store.snapshots_for_mind(mind.id()).unwrap().len(), 1);
}
