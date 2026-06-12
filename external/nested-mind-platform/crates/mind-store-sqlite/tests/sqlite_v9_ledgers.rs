use mind_core::*;
use mind_store_sqlite::SqliteEventStore;
use time::OffsetDateTime;

#[test]
fn sqlite_v9_records_cache_transfer_replication_and_consensus_ledgers() {
    let mut store = SqliteEventStore::in_memory()
        .expect("sqlite")
        .with_signature_requirement(SignatureRequirement::Optional);
    assert_eq!(
        store.current_schema_version().expect("schema"),
        PLATFORM_SCHEMA_VERSION
    );

    let cache = OidcJwksCacheEntry::from_jwks_json(
        "https://issuer.example",
        "https://issuer.example/jwks.json",
        r#"{"keys":[{"kty":"oct","kid":"local","k":"c2VjcmV0","alg":"HS256"}]}"#,
        Some(60),
    )
    .expect("cache");
    store.record_oidc_jwks_cache(&cache).expect("record cache");
    assert_eq!(store.oidc_jwks_caches().expect("caches").len(), 1);

    let mind = Mind::new_root("root");
    let proposal = EditProposal::new(
        mind.id(),
        "tester",
        "set key",
        StatePatch::new().set("k", SymbolValue::from("v")),
    );
    let plan = EvolutionEngine::evaluate(&mind, proposal).expect("plan");
    let record = EventRecord::new(1, None, plan.commit().clone()).expect("record");
    let batch = ReplicationBatch::new(
        ReplicationTerm::new(1, "leader-a"),
        ReplicationCursor::start(mind.id()),
        vec![record.clone()],
        SignatureRequirement::Optional,
    )
    .expect("batch");
    let envelope = ReplicationEnvelope::from_batch(batch.clone()).expect("envelope");
    store
        .record_replication_envelope(&envelope)
        .expect("record envelope");
    assert_eq!(store.replication_envelopes().expect("envelopes").len(), 1);
    store
        .append_replicated_records(vec![record])
        .expect("replicated append");
    assert_eq!(store.records_for_mind(mind.id()).expect("records").len(), 1);

    let receipt = CloudUploadReceipt {
        receipt_id: EventId::new(),
        execution_id: EventId::new(),
        provider: CloudObjectProvider::S3Compatible,
        bucket: "mind-backups".to_owned(),
        key: "root/backup.json".to_owned(),
        object_uri: "s3://mind-backups/root/backup.json".to_owned(),
        body_sha256_hex: "abc".to_owned(),
        body_bytes: 3,
        uploaded_at: OffsetDateTime::now_utc(),
        verified: true,
    };
    store
        .record_cloud_upload_receipt(&receipt)
        .expect("receipt");
    assert_eq!(store.cloud_upload_receipts().expect("receipts").len(), 1);

    let membership = ConsensusMembership::new("cluster-a", vec![ConsensusMember::voter("node-a")]);
    store
        .record_consensus_membership(&membership)
        .expect("membership");
    assert_eq!(store.consensus_memberships().expect("memberships").len(), 1);
}
