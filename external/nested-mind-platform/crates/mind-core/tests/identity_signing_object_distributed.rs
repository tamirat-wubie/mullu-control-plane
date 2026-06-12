use mind_core::{
    AppendOnlyEventStore, ClusterHealthReport, CommitSigningService, DistributedEventStorePlan,
    Ed25519CommitSigner, EditProposal, EventId, EvolutionEngine, ExternalIdentityAssertion,
    ExternalRequestSigningService, FileObjectBackupStore, IdentityBindingPolicy, IdentitySource,
    InMemoryEventStore, LocalEd25519SigningService, Mind, MindBackup, Role, SignatureRequirement,
    SigningBackendKind, StatePatch, SymbolValue, PLATFORM_SCHEMA_VERSION,
};

#[test]
fn identity_binding_policy_maps_oidc_and_mtls_claims() {
    let policy = IdentityBindingPolicy::default()
        .allow_issuer("https://issuer.example")
        .require_audience("nested-mind-api")
        .require_client_certificate_sha256("abc123")
        .with_default_role(None);

    let assertion = ExternalIdentityAssertion::new(IdentitySource::OidcJwt, "tamirat")
        .with_issuer("https://issuer.example")
        .with_audience("nested-mind-api")
        .with_role(Role::Maintainer)
        .with_client_certificate_sha256("ABC123");

    let principal = policy.verify(assertion).unwrap().into_principal();
    assert_eq!(principal.id, "tamirat");
    assert!(principal.roles.contains(&Role::Maintainer));
    assert_eq!(
        principal.attributes.get("identity.issuer").unwrap(),
        "https://issuer.example"
    );
}

#[test]
fn external_signing_request_and_local_signing_service_are_consistent() {
    let mind = Mind::new_root("root");
    let proposal = EditProposal::new(
        mind.id(),
        "tester",
        "set goal",
        StatePatch::new().set("goal", SymbolValue::from("signed external payload")),
    );
    let mut plan = EvolutionEngine::evaluate(&mind, proposal).unwrap();
    let external = ExternalRequestSigningService::new(SigningBackendKind::Hsm, "hsm-key-1");
    let request = external.request_for_commit(plan.commit()).unwrap();
    assert_eq!(request.key_id, "hsm-key-1");
    assert!(!request.payload_hash.is_empty());
    assert!(!request.signable_payload_hex.is_empty());

    let signer =
        LocalEd25519SigningService::new(Ed25519CommitSigner::from_seed("local-test", [9_u8; 32]));
    signer.sign_commit(plan.commit_mut()).unwrap();
    assert!(plan.commit().verify_signature().is_ok());
}

#[test]
fn file_object_backup_store_round_trips_backup() {
    let mind = Mind::new_root("root");
    let backup = MindBackup::capture(
        Some(mind.id()),
        Vec::new(),
        Vec::new(),
        Vec::new(),
        Vec::new(),
        PLATFORM_SCHEMA_VERSION,
    )
    .unwrap();
    let dir = std::env::temp_dir().join(format!("nested-mind-object-test-{}", EventId::new()));
    let store = FileObjectBackupStore::new(dir.clone()).unwrap();
    let pointer = store
        .put_backup(
            "mind-backups",
            format!("{}/{}.json", mind.id(), backup.manifest.backup_id),
            &backup,
        )
        .unwrap();
    let report = store
        .verify_pointer(&pointer, SignatureRequirement::Optional)
        .unwrap();
    assert!(report.valid);
    assert_eq!(report.backup_hash, backup.manifest.backup_hash);
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn distributed_follower_rejects_local_append_authority() {
    let plan = DistributedEventStorePlan::follower("node-b", 3);
    let report = ClusterHealthReport::from_plan(plan.clone()).unwrap();
    assert!(!report.event_store_writable);
    assert!(plan.validate_append_authority().is_err());

    let leader = DistributedEventStorePlan::leader("node-a", 3);
    leader.validate_append_authority().unwrap();
}

#[test]
fn append_still_requires_signature_under_required_mode() {
    let mind = Mind::new_root("root");
    let proposal = EditProposal::new(
        mind.id(),
        "tester",
        "set goal",
        StatePatch::new().set("goal", SymbolValue::from("required signature")),
    );
    let plan = EvolutionEngine::evaluate(&mind, proposal).unwrap();
    let mut store =
        InMemoryEventStore::new().with_signature_requirement(SignatureRequirement::Required);
    assert!(store.append(plan.commit().clone()).is_err());
}
