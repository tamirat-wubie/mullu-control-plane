use mind_core::{EditProposal, EvolutionEngine, Identity, Mind, StatePatch, SymbolValue};

#[test]
fn accepted_patch_creates_commit_and_updates_state() {
    let mut mind = Mind::new_root("root");
    let patch = StatePatch::new().set("goal", SymbolValue::from("nested symbolic minds"));
    let proposal = EditProposal::new(mind.id(), "test", "set goal", patch);

    let commit = EvolutionEngine::evolve(&mut mind, proposal).expect("patch should pass");

    assert!(commit.judgment.accepted);
    assert_eq!(mind.history().len(), 1);
    assert_eq!(
        mind.state().get("goal"),
        Some(&SymbolValue::from("nested symbolic minds"))
    );
    assert_ne!(commit.before_hash, commit.after_hash);
}

#[test]
fn immutable_identity_key_is_rejected() {
    let mut mind = Mind::new_root("root");
    let patch = StatePatch::new().set("identity.kind", SymbolValue::from("changed"));
    let proposal = EditProposal::new(mind.id(), "test", "attempt invalid mutation", patch);

    let error = EvolutionEngine::evolve(&mut mind, proposal).expect_err("patch must fail");

    assert!(error.to_string().contains("immutable key"));
    assert_eq!(mind.history().len(), 0);
}

#[test]
fn child_mind_must_reference_parent() {
    let mut parent = Mind::new_root("parent");
    let child_identity = Identity::child(parent.id(), "child");
    let plan =
        EvolutionEngine::evaluate_child_attachment(&parent, child_identity, "test", "attach child")
            .expect("child attachment should pass");

    EvolutionEngine::apply_plan(&mut parent, plan).expect("child should attach");
    assert_eq!(parent.children().len(), 1);
}
