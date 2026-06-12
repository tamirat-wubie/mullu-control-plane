use mind_core::*;
use time::OffsetDateTime;

fn signed_record() -> (Mind, EventRecord, Ed25519CommitSigner) {
    let mind = Mind::new_root("root");
    let proposal = EditProposal::new(
        mind.id(),
        "tester",
        "set v9",
        StatePatch::new().set("v", SymbolValue::from("9")),
    );
    let mut plan = EvolutionEngine::evaluate(&mind, proposal).expect("plan");
    let signer = Ed25519CommitSigner::from_seed("v9-ed25519", [9_u8; 32]);
    plan.commit_mut().sign_with(&signer).expect("sign");
    let record = EventRecord::new(1, None, plan.commit().clone()).expect("record");
    (mind, record, signer)
}

#[test]
fn oidc_discovery_document_yields_cache_and_verifier_config() {
    let document = OidcDiscoveryDocument {
        issuer: "https://issuer.example".to_owned(),
        jwks_uri: "https://issuer.example/.well-known/jwks.json".to_owned(),
        authorization_endpoint: None,
        token_endpoint: None,
        userinfo_endpoint: None,
        response_types_supported: vec!["code".to_owned()],
        id_token_signing_alg_values_supported: vec!["HS256".to_owned()],
        metadata: Default::default(),
    };
    let mut config =
        OidcDiscoveryConfig::new("https://issuer.example").with_audience("nested-mind-api");
    config.allowed_algorithms = std::collections::BTreeSet::from(["HS256".to_owned()]);
    document.validate_for(&config).expect("document validates");
    let verifier = document.verifier_config(&config).expect("verifier config");
    assert!(verifier.audiences.contains("nested-mind-api"));
    let cache = OidcJwksCacheEntry::from_jwks_json(
        document.issuer.clone(),
        document.jwks_uri.clone(),
        r#"{"keys":[{"kty":"oct","kid":"local","k":"c2VjcmV0","alg":"HS256"}]}"#,
        Some(60),
    )
    .expect("cache");
    assert_eq!(cache.key_count, 1);
    assert!(!cache.jwks_hash.is_empty());
}

#[test]
fn vendor_signing_execution_receipt_converts_to_managed_completion() {
    let (_mind, record, signer) = signed_record();
    let mut unsigned = record.commit.clone();
    unsigned.signature = None;
    let key = ManagedSigningKey::ed25519(
        ManagedSigningProvider::AwsKms,
        "key",
        "arn:aws:kms:demo",
        signer.public_key_hex(),
    );
    let adapter = ManagedSigningAdapter::new(key).expect("adapter");
    let request = adapter.prepare(&unsigned).expect("request");
    let execution = VendorSigningExecutionRequest::from_request(&request);
    let signature = signer.sign_commit(&unsigned).expect("signature");
    let receipt = VendorSigningReceipt {
        execution_id: execution.execution_id,
        request_id: request.request_id,
        commit_id: request.commit_id,
        provider: request.key.provider,
        key_id: request.key.key_id.clone(),
        payload_hash: request.payload_hash.clone(),
        signature_hex: signature.signature_hex,
        public_key_hex: signer.public_key_hex(),
        signer_identity: "aws-kms:test".to_owned(),
        attestation_id: None,
        completed_at: OffsetDateTime::now_utc(),
    };
    let completion = receipt.into_completion(&request).expect("completion");
    adapter
        .complete(&mut unsigned, &request, completion)
        .expect("complete");
    unsigned.verify_signature().expect("verify");
}

#[test]
fn local_cloud_mirror_uploads_and_downloads_verified_backup() {
    let (mind, record, _signer) = signed_record();
    let backup = MindBackup::capture(
        Some(mind.id()),
        vec![record],
        Vec::new(),
        Vec::new(),
        Vec::new(),
        PLATFORM_SCHEMA_VERSION,
    )
    .expect("backup");
    let target = CloudObjectStoreTarget::s3("mind-backups", "root");
    let plan = CloudObjectAdapter::new(target)
        .expect("adapter")
        .plan_backup_put(&backup, SignatureRequirement::Optional)
        .expect("plan");
    let dir = std::env::temp_dir().join(format!("mind-cloud-mirror-{}", EventId::new()));
    let mirror = LocalCloudMirrorStore::new(dir.clone()).expect("mirror");
    let receipt = mirror
        .put_backup(&plan, &backup, SignatureRequirement::Optional)
        .expect("upload");
    let (loaded, download) = mirror
        .load_backup(&receipt, SignatureRequirement::Optional)
        .expect("download");
    assert_eq!(loaded.manifest.backup_hash, backup.manifest.backup_hash);
    assert!(download.verified);
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn durable_follower_ingest_preserves_leader_record_hash() {
    let (mind, leader_record, _signer) = signed_record();
    let cursor = ReplicationCursor::start(mind.id());
    let batch = ReplicationBatch::new(
        ReplicationTerm::new(1, "leader-a"),
        cursor,
        vec![leader_record.clone()],
        SignatureRequirement::Optional,
    )
    .expect("batch");
    let mut follower_store = InMemoryEventStore::new();
    let report = apply_replication_batch(&mut follower_store, "follower-a", &batch).expect("apply");
    assert!(report.accepted);
    assert_eq!(report.appended_records, 1);
    let stored = follower_store.records_for_mind(mind.id()).expect("records");
    assert_eq!(stored[0].record_hash, leader_record.record_hash);
}

#[test]
fn consensus_membership_validates_quorum_and_election() {
    let membership = ConsensusMembership::new(
        "cluster-a",
        vec![
            ConsensusMember::voter("node-a"),
            ConsensusMember::voter("node-b"),
            ConsensusMember::voter("node-c"),
        ],
    );
    membership.validate().expect("membership");
    assert_eq!(membership.quorum_size(), 2);
    let votes = vec![
        ElectionVote::grant(1, "node-a", "node-a"),
        ElectionVote::grant(1, "node-b", "node-a"),
    ];
    let tally = ElectionTally::tally(&membership, 1, "node-a", &votes).expect("tally");
    assert!(tally.elected);
}
