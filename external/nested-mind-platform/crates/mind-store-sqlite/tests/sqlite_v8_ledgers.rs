use mind_core::*;
use mind_store_sqlite::SqliteEventStore;
use time::OffsetDateTime;

#[test]
fn sqlite_persists_v8_managed_cloud_replication_ledgers() {
    let mut sqlite = SqliteEventStore::in_memory().expect("sqlite");
    assert_eq!(
        sqlite.current_schema_version().expect("schema"),
        PLATFORM_SCHEMA_VERSION
    );

    let root = Mind::new_root("root");
    let proposal = EditProposal::new(
        root.id(),
        "tester",
        "set goal",
        StatePatch::new().set("goal", SymbolValue::from("v8")),
    );
    let plan = EvolutionEngine::evaluate(&root, proposal).expect("plan");
    let key = ManagedSigningKey::ed25519(
        ManagedSigningProvider::Pkcs11Hsm,
        "pkcs11-demo",
        "token=demo;object=mind",
        "00",
    );
    let request = ManagedSigningRequest::from_commit(plan.commit(), key).expect("request");
    sqlite
        .record_managed_signing_request(&request)
        .expect("record request");
    assert_eq!(
        sqlite.managed_signing_requests().expect("requests").len(),
        1
    );

    let record = EventRecord::new(1, None, plan.commit().clone()).expect("record");
    let backup = MindBackup::capture(
        Some(root.id()),
        vec![record.clone()],
        Vec::new(),
        Vec::new(),
        Vec::new(),
        PLATFORM_SCHEMA_VERSION,
    )
    .expect("backup");
    let plan = CloudObjectAdapter::new(CloudObjectStoreTarget::gcs("mind-backups", "root"))
        .expect("adapter")
        .plan_backup_put(&backup, SignatureRequirement::Optional)
        .expect("cloud plan");
    sqlite
        .record_cloud_object_backup_plan(&plan)
        .expect("record cloud plan");
    assert_eq!(sqlite.cloud_object_backup_plans().expect("plans").len(), 1);

    let leader = LeaderReplicationProtocol::new(ReplicationTerm::new(1, "leader-a"), 10, 1);
    let cursor = ReplicationCursor::start(root.id());
    let batch = leader
        .prepare_batch(cursor, &[record], SignatureRequirement::Optional)
        .expect("batch");
    let ack = ReplicationAck {
        batch_id: batch.batch_id,
        follower_id: "follower-a".to_owned(),
        accepted: true,
        next_sequence: 2,
        last_record_hash: batch
            .records
            .last()
            .map(|record| record.record_hash.clone()),
        error: None,
        acknowledged_at: OffsetDateTime::now_utc(),
    };
    sqlite
        .record_replication_batch(&batch)
        .expect("record batch");
    sqlite.record_replication_ack(&ack).expect("record ack");
    assert_eq!(sqlite.replication_batches().expect("batches").len(), 1);
    assert_eq!(sqlite.replication_acks().expect("acks").len(), 1);
}
