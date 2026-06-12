use mind_core::*;
use time::OffsetDateTime;

fn signed_demo_commit() -> (Mind, Commit, Ed25519CommitSigner) {
    let root = Mind::new_root("root");
    let proposal = EditProposal::new(
        root.id(),
        "tester",
        "set goal",
        StatePatch::new().set("goal", SymbolValue::from("v8")),
    );
    let mut plan = EvolutionEngine::evaluate(&root, proposal).expect("plan");
    let signer = Ed25519CommitSigner::from_seed("managed-ed25519", [8_u8; 32]);
    plan.commit_mut().sign_with(&signer).expect("sign");
    let commit = plan.commit().clone();
    (root, commit, signer)
}

#[test]
fn oidc_jwks_verifier_accepts_signed_jwt_and_maps_role() {
    let mut header = jsonwebtoken::Header::new(jsonwebtoken::Algorithm::HS256);
    header.kid = Some("local-test".to_owned());
    let claims = serde_json::json!({
        "iss": "https://issuer.example",
        "sub": "subject-1",
        "aud": "nested-mind-api",
        "exp": 4_102_444_800_u64,
        "roles": ["operator"]
    });
    let token = jsonwebtoken::encode(
        &header,
        &claims,
        &jsonwebtoken::EncodingKey::from_secret(b"secret"),
    )
    .expect("token");
    let jwks = r#"{"keys":[{"kty":"oct","kid":"local-test","k":"c2VjcmV0","alg":"HS256"}]}"#;
    let mut config =
        OidcJwksVerifierConfig::new("https://issuer.example").with_audience("nested-mind-api");
    config.allowed_algorithms = std::collections::BTreeSet::from(["HS256".to_owned()]);
    let binding = IdentityBindingPolicy::default()
        .allow_issuer("https://issuer.example")
        .require_audience("nested-mind-api");
    let report = OidcJwksVerifier::from_jwks_json(config, jwks)
        .expect("verifier")
        .verify_with_report(&token, &binding)
        .expect("verified");
    assert!(report.signature_verified);
    assert_eq!(report.subject, "subject-1");
    assert!(report.roles.contains(&Role::Operator));
}

#[test]
fn managed_signing_adapter_prepares_and_completes_ed25519_signature() {
    let (_root, commit, signer) = signed_demo_commit();
    let mut unsigned = commit.clone();
    unsigned.signature = None;
    let key = ManagedSigningKey::ed25519(
        ManagedSigningProvider::AwsKms,
        "aws-ed25519-key",
        "arn:aws:kms:us-east-1:111122223333:key/demo",
        signer.public_key_hex(),
    );
    let adapter = ManagedSigningAdapter::new(key).expect("adapter");
    let request = adapter.prepare(&unsigned).expect("request");
    let signature = signer.sign_commit(&unsigned).expect("signature");
    let completion = ManagedSigningCompletion {
        request_id: request.request_id,
        commit_id: request.commit_id,
        key_id: request.key.key_id.clone(),
        provider: request.key.provider,
        payload_hash: request.payload_hash.clone(),
        signature_hex: signature.signature_hex,
        public_key_hex: signer.public_key_hex(),
        signer_identity: "aws-kms:demo".to_owned(),
        attestation_id: Some("attestation-1".to_owned()),
        signed_at: OffsetDateTime::now_utc(),
    };
    adapter
        .complete(&mut unsigned, &request, completion)
        .expect("complete");
    unsigned.verify_signature().expect("verified signature");
}

#[test]
fn cloud_object_adapter_builds_s3_backup_put_plan() {
    let (root, commit, _signer) = signed_demo_commit();
    let record = EventRecord::new(1, None, commit).expect("record");
    let backup = MindBackup::capture(
        Some(root.id()),
        vec![record],
        Vec::new(),
        Vec::new(),
        Vec::new(),
        PLATFORM_SCHEMA_VERSION,
    )
    .expect("backup");
    let target = CloudObjectStoreTarget::s3("mind-backups", "root")
        .with_region("us-east-1")
        .with_kms_key("alias/mind-backups");
    let plan = CloudObjectAdapter::new(target)
        .expect("adapter")
        .plan_backup_put(&backup, SignatureRequirement::Optional)
        .expect("plan");
    assert_eq!(plan.put_request.provider, CloudObjectProvider::S3Compatible);
    assert!(plan.put_request.key.ends_with(".backup.json"));
    assert_eq!(
        plan.put_request.headers.get("x-mind-backup-id"),
        Some(&backup.manifest.backup_id.to_string())
    );
}

#[test]
fn leader_replication_batch_validates_on_follower_cursor() {
    let (root, commit, _signer) = signed_demo_commit();
    let mut store =
        InMemoryEventStore::new().with_signature_requirement(SignatureRequirement::Optional);
    let record = store.append(commit).expect("append");
    let leader = LeaderReplicationProtocol::new(ReplicationTerm::new(1, "leader-a"), 10, 1);
    let cursor = ReplicationCursor::start(root.id());
    let batch = leader
        .prepare_batch(cursor.clone(), &[record], SignatureRequirement::Optional)
        .expect("batch");
    let follower =
        FollowerReplicationProtocol::new("follower-a", cursor, SignatureRequirement::Optional);
    let ack = follower.validate_batch(&batch).expect("ack");
    assert!(ack.accepted);
    assert_eq!(ack.next_sequence, 2);
}
