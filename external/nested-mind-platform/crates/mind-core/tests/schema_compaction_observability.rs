use mind_core::{
    AppendOnlyEventStore, AuditEvent, AuditEventKind, CompactingSnapshotStore, EditProposal,
    EvolutionEngine, InMemoryEventStore, InMemoryObservabilitySink, InMemorySnapshotStore,
    JsonlObservabilitySink, Mind, ObservabilitySink, SchemaMigration, SchemaMigrationPlan,
    SnapshotCompactionPolicy, SnapshotRecord, SnapshotStore, StatePatch, SymbolValue,
};

#[test]
fn schema_migration_plan_rejects_version_gap() {
    let migration = SchemaMigration::new(3, "skip-two", vec!["SELECT 1".to_owned()]).unwrap();
    let error = SchemaMigrationPlan::new(1, vec![migration]).unwrap_err();
    assert!(error.to_string().contains("schema migration gap"));
}

#[test]
fn compaction_policy_keeps_latest_snapshot_and_removes_older_ones() {
    let mut mind = Mind::new_root("root");
    let mut events = InMemoryEventStore::new();
    let mut snapshots = InMemorySnapshotStore::new();

    for i in 0..4 {
        let patch = StatePatch::new().set(format!("k{i}"), SymbolValue::from(format!("v{i}")));
        let proposal = EditProposal::new(mind.id(), "test", format!("patch {i}"), patch);
        let plan = EvolutionEngine::evaluate(&mind, proposal).unwrap();
        let record = events.append(plan.commit().clone()).unwrap();
        EvolutionEngine::apply_plan(&mut mind, plan).unwrap();
        snapshots
            .save_snapshot(SnapshotRecord::capture(&mind, Some(&record)).unwrap())
            .unwrap();
    }

    let decision = snapshots
        .compact_snapshots(mind.id(), &SnapshotCompactionPolicy::new(1, 2), 4)
        .unwrap();
    assert_eq!(decision.remove_snapshot_ids.len(), 3);
    assert_eq!(snapshots.snapshots_for_mind(mind.id()).unwrap().len(), 1);
}

#[test]
fn in_memory_observability_sink_records_audit_events() {
    let mut sink = InMemoryObservabilitySink::new();
    sink.record_audit(AuditEvent::new(
        AuditEventKind::SnapshotCompacted,
        "compact",
    ))
    .unwrap();
    assert_eq!(sink.audit_events().unwrap().len(), 1);
}

#[test]
fn jsonl_observability_sink_round_trips_audit_events() {
    let path = std::env::temp_dir().join(format!(
        "mind-observability-{}.jsonl",
        mind_core::EventId::new()
    ));
    let mut sink = JsonlObservabilitySink::new(path.clone()).unwrap();
    sink.record_audit(AuditEvent::new(
        AuditEventKind::SchemaMigrated,
        "schema migrated",
    ))
    .unwrap();
    let loaded = JsonlObservabilitySink::new(path.clone())
        .unwrap()
        .audit_events()
        .unwrap();
    std::fs::remove_file(&path).ok();
    assert_eq!(loaded.len(), 1);
    assert_eq!(loaded[0].kind, AuditEventKind::SchemaMigrated);
}
