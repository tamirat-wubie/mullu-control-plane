use mind_core::*;
use std::collections::BTreeSet;

fn sample_discovery_document() -> OidcDiscoveryDocument {
    OidcDiscoveryDocument {
        issuer: "https://issuer.example".to_owned(),
        jwks_uri: "https://issuer.example/.well-known/jwks.json".to_owned(),
        authorization_endpoint: None,
        token_endpoint: None,
        userinfo_endpoint: None,
        response_types_supported: vec!["code".to_owned()],
        id_token_signing_alg_values_supported: vec!["HS256".to_owned()],
        metadata: Default::default(),
    }
}

#[test]
fn live_oidc_refresh_report_builds_cache_and_verifier_config() {
    let mut config =
        OidcDiscoveryConfig::new("https://issuer.example").with_audience("nested-mind-api");
    config.allowed_algorithms = BTreeSet::from(["HS256".to_owned()]);
    let request = LiveOidcRefreshRequest::from_config(&config, ConnectorExecutionMode::LiveHttp)
        .expect("request");
    let report = LiveOidcRefreshReport::from_parts(
        request,
        &config,
        &sample_discovery_document(),
        r#"{"keys":[{"kty":"oct","kid":"local","k":"c2VjcmV0","alg":"HS256"}]}"#,
    )
    .expect("report");
    assert_eq!(report.key_count, 1);
    assert!(report.verifier_config.audiences.contains("nested-mind-api"));
    assert!(!report.discovery_hash.is_empty());
}

#[test]
fn retry_policy_caps_exponential_delay() {
    let policy = ReplicationRetryPolicy {
        max_attempts: 5,
        initial_delay_ms: 100,
        max_delay_ms: 350,
        multiplier: 2,
    };
    policy.validate().expect("valid policy");
    assert_eq!(policy.delay_for_attempt_ms(1), 100);
    assert_eq!(policy.delay_for_attempt_ms(2), 200);
    assert_eq!(policy.delay_for_attempt_ms(3), 350);
    assert_eq!(policy.delay_for_attempt_ms(5), 350);
}

#[test]
fn consensus_change_proposal_produces_verifiable_judgment() {
    let membership = ConsensusMembership::new("cluster-a", vec![ConsensusMember::voter("node-a")]);
    let proposal = ConsensusChangeProposal::new(
        &membership,
        "maintainer",
        "add learner for catch-up",
        vec![ConsensusMembershipChange::AddMember {
            member: ConsensusMember::learner("node-b"),
        }],
    );
    let judgment = proposal.evaluate(&membership).expect("judgment");
    judgment
        .verify_transition(&membership)
        .expect("verified transition");
    assert!(judgment.accepted);
    assert_eq!(judgment.resulting_membership.members.len(), 2);
    assert_ne!(judgment.before_hash, judgment.after_hash);
}

#[test]
fn cloud_signed_url_request_hashes_backup_body() {
    let mind = Mind::new_root("root");
    let backup = MindBackup::capture(
        Some(mind.id()),
        Vec::new(),
        Vec::new(),
        Vec::new(),
        Vec::new(),
        PLATFORM_SCHEMA_VERSION,
    )
    .expect("backup");
    let request = CloudSignedUrlRequest::put_backup(
        CloudObjectProvider::S3Compatible,
        "https://upload.example/signed",
        "bucket",
        "root/backup.json",
        &backup,
    )
    .expect("request");
    request.validate().expect("valid request");
    let receipt = CloudSignedUrlReceipt::from_request(
        &request,
        200,
        request.expected_body_sha256_hex.clone(),
    );
    assert!(receipt.verified);
}
