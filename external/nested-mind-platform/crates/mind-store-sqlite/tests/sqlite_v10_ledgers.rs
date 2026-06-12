use mind_core::*;
use mind_store_sqlite::SqliteEventStore;

#[test]
fn sqlite_v10_records_live_connector_and_consensus_ledgers() {
    let mut store = SqliteEventStore::in_memory().expect("sqlite");
    assert_eq!(
        store.current_schema_version().expect("schema"),
        PLATFORM_SCHEMA_VERSION
    );

    let mut config =
        OidcDiscoveryConfig::new("https://issuer.example").with_audience("nested-mind-api");
    config.allowed_algorithms = std::collections::BTreeSet::from(["HS256".to_owned()]);
    let document = OidcDiscoveryDocument {
        issuer: "https://issuer.example".to_owned(),
        jwks_uri: "https://issuer.example/jwks.json".to_owned(),
        authorization_endpoint: None,
        token_endpoint: None,
        userinfo_endpoint: None,
        response_types_supported: Vec::new(),
        id_token_signing_alg_values_supported: vec!["HS256".to_owned()],
        metadata: Default::default(),
    };
    let request = LiveOidcRefreshRequest::from_config(&config, ConnectorExecutionMode::LiveHttp)
        .expect("request");
    let report = LiveOidcRefreshReport::from_parts(
        request,
        &config,
        &document,
        r#"{"keys":[{"kty":"oct","kid":"local","k":"c2VjcmV0","alg":"HS256"}]}"#,
    )
    .expect("report");
    store
        .record_live_oidc_refresh(&report)
        .expect("record refresh");
    assert_eq!(store.live_oidc_refreshes().expect("refreshes").len(), 1);

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
        vec![record],
        SignatureRequirement::Optional,
    )
    .expect("batch");
    let envelope = ReplicationEnvelope::from_batch(batch).expect("envelope");
    let receipt = ReplicationDeliveryReceipt::new(
        "follower-a",
        "http://follower-a/system/replication/follower/batches",
        &envelope,
    );
    store
        .record_replication_delivery_receipt(&receipt)
        .expect("record delivery");
    assert_eq!(
        store
            .replication_delivery_receipts()
            .expect("deliveries")
            .len(),
        1
    );

    let membership = ConsensusMembership::new("cluster-a", vec![ConsensusMember::voter("node-a")]);
    let change = ConsensusChangeProposal::new(
        &membership,
        "admin",
        "add learner",
        vec![ConsensusMembershipChange::AddMember {
            member: ConsensusMember::learner("node-b"),
        }],
    );
    let judgment = change.evaluate(&membership).expect("judgment");
    store
        .record_consensus_change_judgment(&judgment)
        .expect("record judgment");
    assert_eq!(
        store.consensus_change_judgments().expect("judgments").len(),
        1
    );

    let backup = MindBackup::capture(
        Some(mind.id()),
        Vec::new(),
        Vec::new(),
        Vec::new(),
        Vec::new(),
        PLATFORM_SCHEMA_VERSION,
    )
    .expect("backup");
    let upload = CloudSignedUrlRequest::put_backup(
        CloudObjectProvider::S3Compatible,
        "https://upload.example/signed",
        "bucket",
        "key",
        &backup,
    )
    .expect("upload");
    let upload_receipt =
        CloudSignedUrlReceipt::from_request(&upload, 200, upload.expected_body_sha256_hex.clone());
    store
        .record_cloud_signed_url_receipt(&upload_receipt)
        .expect("signed url receipt");
    assert_eq!(
        store
            .cloud_signed_url_receipts()
            .expect("signed receipts")
            .len(),
        1
    );
}
