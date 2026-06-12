use mind_core::{
    AppendOnlyEventStore, EditProposal, EvolutionEngine, InMemoryEventStore, LawRule,
    LawbookMigration, LawbookMigrationOp, Mind, ReplayAudit, ReplayEngine, SignatureRequirement,
    SnapshotRecord, StatePatch, SymbolValue,
};

#[test]
fn lawbook_migration_adds_forbid_rule_and_replay_preserves_it() {
    let mut mind = Mind::new_root("root");
    let identity = mind.identity().clone();
    let mut store = InMemoryEventStore::new();

    let migration = LawbookMigration::new(
        mind.lawbook().version(),
        mind.lawbook().version() + 1,
        "test",
        "forbid password cells",
        vec![LawbookMigrationOp::AddRule {
            rule: LawRule::ForbidKey {
                key: "password".to_owned(),
            },
        }],
    );
    let plan =
        EvolutionEngine::evaluate_lawbook_migration(&mind, migration).expect("migration evaluates");
    store
        .append(plan.commit().clone())
        .expect("migration appends");
    EvolutionEngine::apply_plan(&mut mind, plan).expect("migration applies");

    assert_eq!(mind.lawbook().version(), 2);
    let proposal = EditProposal::new(
        mind.id(),
        "test",
        "try forbidden key",
        StatePatch::new().set("password", SymbolValue::from("not allowed")),
    );
    assert!(EvolutionEngine::evaluate(&mind, proposal).is_err());

    let records = store.records_for_mind(mind.id()).expect("records load");
    let (replayed, _) = ReplayEngine::replay(identity, &records).expect("replay succeeds");
    assert_eq!(replayed.lawbook().version(), 2);
}

#[test]
fn snapshot_replay_with_tail_reaches_full_replay_hash() {
    let mut mind = Mind::new_root("root");
    let identity = mind.identity().clone();
    let mut store = InMemoryEventStore::new();

    let first = EvolutionEngine::evaluate(
        &mind,
        EditProposal::new(
            mind.id(),
            "test",
            "set one",
            StatePatch::new().set("one", SymbolValue::from("1")),
        ),
    )
    .unwrap();
    store.append(first.commit().clone()).unwrap();
    EvolutionEngine::apply_plan(&mut mind, first).unwrap();
    let snapshot =
        SnapshotRecord::capture(&mind, store.records_for_mind(mind.id()).unwrap().last()).unwrap();

    let second = EvolutionEngine::evaluate(
        &mind,
        EditProposal::new(
            mind.id(),
            "test",
            "set two",
            StatePatch::new().set("two", SymbolValue::from("2")),
        ),
    )
    .unwrap();
    store.append(second.commit().clone()).unwrap();
    EvolutionEngine::apply_plan(&mut mind, second).unwrap();

    let records = store.records_for_mind(mind.id()).unwrap();
    let (_, full_report) = ReplayEngine::replay(identity, &records).unwrap();
    let tail: Vec<_> = records
        .into_iter()
        .filter(|record| record.sequence > snapshot.after_sequence)
        .collect();
    let (_, snapshot_report) =
        ReplayEngine::replay_from_snapshot(&snapshot, &tail, SignatureRequirement::Optional)
            .unwrap();
    assert_eq!(snapshot_report.final_hash, full_report.final_hash);
    assert_eq!(snapshot_report.commit_count, full_report.commit_count);
}

#[test]
fn audit_from_snapshot_passes_for_matching_tail() {
    let mut mind = Mind::new_root("root");
    let mut store = InMemoryEventStore::new();
    let plan = EvolutionEngine::evaluate(
        &mind,
        EditProposal::new(
            mind.id(),
            "test",
            "set goal",
            StatePatch::new().set("goal", SymbolValue::from("audit")),
        ),
    )
    .unwrap();
    store.append(plan.commit().clone()).unwrap();
    EvolutionEngine::apply_plan(&mut mind, plan).unwrap();
    let records = store.records_for_mind(mind.id()).unwrap();
    let snapshot = SnapshotRecord::capture(&mind, records.last()).unwrap();
    let audit = ReplayAudit::audit_from_snapshot(&snapshot, &[], SignatureRequirement::Optional);
    assert!(audit.passed);
    assert!(audit.failure.is_none());
}
