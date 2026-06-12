use mind_core::{
    AppendOnlyEventStore, Ed25519CommitSigner, EditProposal, EvolutionEngine, Mind, ReplayEngine,
    SignatureRequirement, StatePatch, SymbolValue,
};
use mind_store_sqlite::SqliteEventStore;

#[test]
fn sqlite_store_persists_signed_records_transactionally() {
    let mut mind = Mind::new_root("root");
    let identity = mind.identity().clone();
    let signer = Ed25519CommitSigner::from_seed("sqlite-test", [11_u8; 32]);
    let mut store = SqliteEventStore::in_memory()
        .expect("store opens")
        .with_signature_requirement(SignatureRequirement::Required);
    let proposal = EditProposal::new(
        mind.id(),
        "test",
        "set goal",
        StatePatch::new().set("goal", SymbolValue::from("sqlite event store")),
    );
    let mut plan = EvolutionEngine::evaluate(&mind, proposal).expect("proposal evaluates");
    plan.commit_mut().sign_with(&signer).expect("commit signs");
    store.append(plan.commit().clone()).expect("commit appends");
    EvolutionEngine::apply_plan(&mut mind, plan).expect("plan applies");
    let records = store.records_for_mind(mind.id()).expect("records load");
    let (replayed, report) = ReplayEngine::replay_with_signature_requirement(
        identity,
        &records,
        SignatureRequirement::Required,
    )
    .expect("records replay");
    assert_eq!(records.len(), 1);
    assert_eq!(report.commit_count, 1);
    assert_eq!(replayed.state(), mind.state());
}
