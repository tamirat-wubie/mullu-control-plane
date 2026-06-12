use mind_core::{
    AppendOnlyEventStore, AuthorizationPolicy, Ed25519CommitSigner, EditProposal, EvolutionEngine,
    InMemoryEventStore, Mind, MindAction, Principal, ProjectionScope, Role, SignatureRequirement,
    StatePatch, SymbolValue,
};

#[test]
fn signed_commit_verifies_and_tamper_fails() {
    let mind = Mind::new_root("root");
    let signer = Ed25519CommitSigner::from_seed("test-ed25519", [7_u8; 32]);
    let proposal = EditProposal::new(
        mind.id(),
        "test",
        "set signed goal",
        StatePatch::new().set("goal", SymbolValue::from("signed evolution")),
    );
    let mut plan = EvolutionEngine::evaluate(&mind, proposal).expect("proposal evaluates");
    plan.commit_mut().sign_with(&signer).expect("commit signs");
    plan.commit()
        .verify_signature()
        .expect("signature verifies");
    let mut tampered = plan.commit().clone();
    tampered.reason.push_str(" tampered");
    assert!(tampered.verify_signature().is_err());
}

#[test]
fn required_signature_event_store_rejects_unsigned_commit() {
    let mind = Mind::new_root("root");
    let proposal = EditProposal::new(
        mind.id(),
        "test",
        "set goal",
        StatePatch::new().set("goal", SymbolValue::from("must be signed")),
    );
    let plan = EvolutionEngine::evaluate(&mind, proposal).expect("proposal evaluates");
    let mut store =
        InMemoryEventStore::new().with_signature_requirement(SignatureRequirement::Required);
    let error = store
        .append(plan.commit().clone())
        .expect_err("unsigned commit must not append");
    assert!(error.to_string().contains("unsigned"));
}

#[test]
fn required_signature_event_store_accepts_signed_commit() {
    let mind = Mind::new_root("root");
    let signer = Ed25519CommitSigner::from_seed("test-ed25519", [9_u8; 32]);
    let proposal = EditProposal::new(
        mind.id(),
        "test",
        "set goal",
        StatePatch::new().set("goal", SymbolValue::from("signed append")),
    );
    let mut plan = EvolutionEngine::evaluate(&mind, proposal).expect("proposal evaluates");
    plan.commit_mut().sign_with(&signer).expect("commit signs");
    let mut store =
        InMemoryEventStore::new().with_signature_requirement(SignatureRequirement::Required);
    assert_eq!(
        store
            .append(plan.commit().clone())
            .expect("signed commit appends")
            .sequence,
        1
    );
}

#[test]
fn authorization_policy_separates_operator_and_auditor_capabilities() {
    let mind = Mind::new_root("root");
    let policy = AuthorizationPolicy::production_default();
    let operator = Principal::new("operator").with_role(Role::Operator);
    let auditor = Principal::new("auditor").with_role(Role::Auditor);
    policy
        .require(
            Some(&operator),
            mind.id(),
            &MindAction::ReadProjection {
                scope: ProjectionScope::Public,
            },
        )
        .expect("operator can read public projection");
    assert!(policy
        .require(
            Some(&operator),
            mind.id(),
            &MindAction::ReadProjection {
                scope: ProjectionScope::Internal
            }
        )
        .is_err());
    policy
        .require(Some(&auditor), mind.id(), &MindAction::ReadEvents)
        .expect("auditor can read event trail");
    assert!(policy
        .require(Some(&auditor), mind.id(), &MindAction::ProposePatch)
        .is_err());
}
