use mind_core::{
    AppendOnlyEventStore, EditProposal, EvolutionEngine, InMemoryEventStore, Mind, MindProjection,
    ProjectionPolicy, ReplayEngine, StatePatch, SymbolValue,
};

#[test]
fn event_store_replay_reconstructs_the_same_state() {
    let mut mind = Mind::new_root("root");
    let identity = mind.identity().clone();
    let mut store = InMemoryEventStore::new();

    let first_patch = StatePatch::new().set("goal", SymbolValue::from("nested symbolic minds"));
    let first_proposal = EditProposal::new(mind.id(), "test", "set goal", first_patch);
    let first_plan = EvolutionEngine::evaluate(&mind, first_proposal).expect("valid first plan");
    store
        .append(first_plan.commit().clone())
        .expect("first commit should append");
    EvolutionEngine::apply_plan(&mut mind, first_plan).expect("first plan should apply");

    let second_patch = StatePatch::new().set("status", SymbolValue::from("running"));
    let second_proposal = EditProposal::new(mind.id(), "test", "set status", second_patch);
    let second_plan = EvolutionEngine::evaluate(&mind, second_proposal).expect("valid second plan");
    store
        .append(second_plan.commit().clone())
        .expect("second commit should append");
    EvolutionEngine::apply_plan(&mut mind, second_plan).expect("second plan should apply");

    let records = store
        .records_for_mind(mind.id())
        .expect("stored records should load");
    let (replayed, report) =
        ReplayEngine::replay(identity, &records).expect("records should replay");

    assert_eq!(report.commit_count, 2);
    assert_eq!(replayed.state(), mind.state());
    assert_eq!(replayed.history().len(), mind.history().len());
}

#[test]
fn public_projection_omits_sensitive_state_keys() {
    let mut mind = Mind::new_root("root");
    let patch = StatePatch::new()
        .set("goal", SymbolValue::from("safe to expose"))
        .set("secret.api_key", SymbolValue::from("must-not-leak"))
        .set("auth.access_token", SymbolValue::from("must-not-leak"));
    let proposal = EditProposal::new(mind.id(), "test", "set public and private values", patch);

    EvolutionEngine::evolve(&mut mind, proposal).expect("patch should pass");

    let public = MindProjection::with_policy(&mind, &ProjectionPolicy::public_default());
    let internal = MindProjection::with_policy(&mind, &ProjectionPolicy::internal());

    assert_eq!(
        public.state.get("goal"),
        Some(&SymbolValue::from("safe to expose"))
    );
    assert!(public.state.get("secret.api_key").is_none());
    assert!(public.state.get("auth.access_token").is_none());
    assert_eq!(
        internal.state.get("secret.api_key"),
        Some(&SymbolValue::from("must-not-leak"))
    );
}

#[test]
fn child_attachment_is_replayable_topology() {
    let mut parent = Mind::new_root("parent");
    let identity = parent.identity().clone();
    let child_identity = mind_core::Identity::child(parent.id(), "child");
    let mut store = InMemoryEventStore::new();

    let plan =
        EvolutionEngine::evaluate_child_attachment(&parent, child_identity, "test", "attach child")
            .expect("child attachment should evaluate");
    store
        .append(plan.commit().clone())
        .expect("child attachment should append");
    EvolutionEngine::apply_plan(&mut parent, plan).expect("child attachment should apply");

    let records = store
        .records_for_mind(parent.id())
        .expect("stored records should load");
    let (replayed, report) =
        ReplayEngine::replay(identity, &records).expect("records should replay");

    assert_eq!(parent.children().len(), 1);
    assert_eq!(replayed.children().len(), 1);
    assert_eq!(report.child_count, 1);
}
