use mind_core::*;
use serde_json::json;
use std::collections::BTreeMap;

#[test]
fn live_secret_connector_receipt_binds_secret_access() {
    let reference = SecretReference::new(
        SecretManagerBackend::Environment,
        "MIND_GITHUB_APP_KEY",
        "github-app-key",
    )
    .unwrap();
    let access_plan = plan_secret_access(
        reference,
        "github_app_jwt",
        SecretAccessMode::ReadApproved,
        Some("fingerprint-a".to_owned()),
    )
    .unwrap();
    let access_receipt = record_secret_access_receipt(
        &access_plan,
        Some("fingerprint-a".to_owned()),
        Some("v1".to_owned()),
        BTreeMap::new(),
    )
    .unwrap();
    let connector_plan = plan_live_secret_connector(
        &access_plan,
        LiveSecretConnectorMode::ReadApproved,
        json!({"provider":"env"}),
    )
    .unwrap();
    let connector_receipt = record_live_secret_connector_receipt(
        &connector_plan,
        &access_receipt,
        Some("req-1".to_owned()),
        Some("response-hash".to_owned()),
        Vec::new(),
    )
    .unwrap();
    connector_receipt
        .verify_against(&connector_plan, &access_receipt)
        .unwrap();
    assert_eq!(
        connector_receipt.status,
        LiveSecretConnectorStatus::Resolved
    );
}

#[test]
fn live_secret_connector_plan_rejects_raw_secret_request_template() {
    let reference = SecretReference::new(
        SecretManagerBackend::Environment,
        "MIND_GITHUB_APP_KEY",
        "github-app-key",
    )
    .unwrap();
    let access_plan = plan_secret_access(
        reference,
        "github_app_jwt",
        SecretAccessMode::ReadApproved,
        Some("fingerprint-a".to_owned()),
    )
    .unwrap();
    let error = plan_live_secret_connector(
        &access_plan,
        LiveSecretConnectorMode::ReadApproved,
        json!({"headers":{"authorization":"Bearer ghp_abcdefghijklmnopqrstuvwxyz123456"}}),
    )
    .unwrap_err();
    let message = error.to_string();

    assert!(message.contains("live secret connector request template"));
    assert!(message.contains("raw secret material"));
    assert!(access_plan.verify().is_ok());
}

#[test]
fn secret_access_receipt_rejects_sensitive_response_metadata() {
    let reference = SecretReference::new(
        SecretManagerBackend::Environment,
        "MIND_GITHUB_APP_KEY",
        "github-app-key",
    )
    .unwrap();
    let access_plan = plan_secret_access(
        reference,
        "github_app_jwt",
        SecretAccessMode::ReadApproved,
        Some("fingerprint-a".to_owned()),
    )
    .unwrap();
    let mut metadata = BTreeMap::new();
    metadata.insert("token".to_owned(), "redacted-reference".to_owned());
    let error = record_secret_access_receipt(
        &access_plan,
        Some("fingerprint-a".to_owned()),
        Some("v1".to_owned()),
        metadata,
    )
    .unwrap_err();
    let message = error.to_string();

    assert!(message.contains("secret access receipt"));
    assert!(message.contains("direct sensitive field"));
    assert_eq!(access_plan.mode, SecretAccessMode::ReadApproved);
}

#[test]
fn github_token_exchange_requires_matching_installation() {
    let reference = SecretReference::new(
        SecretManagerBackend::Environment,
        "MIND_GITHUB_APP_KEY",
        "github-app-key",
    )
    .unwrap();
    let access_plan = plan_secret_access(
        reference,
        "github_app_jwt",
        SecretAccessMode::ReadApproved,
        Some("fingerprint-a".to_owned()),
    )
    .unwrap();
    let access_receipt = record_secret_access_receipt(
        &access_plan,
        Some("fingerprint-a".to_owned()),
        Some("v1".to_owned()),
        BTreeMap::new(),
    )
    .unwrap();
    let connector_plan = plan_live_secret_connector(
        &access_plan,
        LiveSecretConnectorMode::ReadApproved,
        json!({"provider":"env"}),
    )
    .unwrap();
    let connector_receipt = record_live_secret_connector_receipt(
        &connector_plan,
        &access_receipt,
        Some("req-1".to_owned()),
        Some("response-hash".to_owned()),
        Vec::new(),
    )
    .unwrap();
    let jwt_plan = plan_github_app_jwt_from_secret(100, 200, &access_plan, 540).unwrap();
    let jwt_receipt = record_github_app_jwt_receipt(
        &jwt_plan,
        &access_receipt,
        Some("jwt-fp".to_owned()),
        Some("signer-response".to_owned()),
    )
    .unwrap();
    let exchange_plan = plan_github_token_exchange_worker(
        "mullusi/nested-mind-platform",
        200,
        &jwt_receipt,
        &connector_receipt,
        GitHubTokenExchangeWorkerMode::ExchangeApproved,
        "permissions-hash",
    )
    .unwrap();

    let mut permissions = BTreeMap::new();
    permissions.insert("checks".to_owned(), "write".to_owned());
    let token_request = GitHubAppInstallationTokenRequest::new(
        100,
        200,
        "mullusi/nested-mind-platform",
        "fingerprint-a",
        permissions,
        vec!["nested-mind-platform".to_owned()],
        3600,
    )
    .unwrap();
    let token_plan =
        plan_github_app_installation_token(token_request, GitHubAppTokenMode::ExchangeApproved)
            .unwrap();
    let token_receipt = record_github_app_installation_token_receipt(
        &token_plan,
        Some("token-fp".to_owned()),
        Some(&json!({"ok":true})),
    )
    .unwrap();
    let exchange_receipt =
        record_github_token_exchange_worker_receipt(&exchange_plan, &token_receipt).unwrap();
    assert_eq!(
        exchange_receipt.status,
        GitHubTokenExchangeWorkerStatus::TokenIssued
    );
}

#[test]
fn github_installation_token_receipt_rejects_raw_token_fingerprint() {
    let mut permissions = BTreeMap::new();
    permissions.insert("checks".to_owned(), "write".to_owned());
    let token_request = GitHubAppInstallationTokenRequest::new(
        100,
        200,
        "mullusi/nested-mind-platform",
        "fingerprint-a",
        permissions,
        vec!["nested-mind-platform".to_owned()],
        3600,
    )
    .unwrap();
    let token_plan =
        plan_github_app_installation_token(token_request, GitHubAppTokenMode::ExchangeApproved)
            .unwrap();
    let error = record_github_app_installation_token_receipt(
        &token_plan,
        Some("ghp_abcdefghijklmnopqrstuvwxyz123456".to_owned()),
        Some(&json!({"ok":true})),
    )
    .unwrap_err();
    let message = error.to_string();

    assert!(message.contains("GitHub App installation token receipt"));
    assert!(message.contains("raw secret material"));
    assert!(token_plan.verify().is_ok());
}

#[test]
fn notification_delivery_client_requires_provider_message_when_sent() {
    let adapter_plan_id = EventId::new();
    let notification_plan_id = EventId::new();
    let created_at = time::OffsetDateTime::now_utc();
    let request_template = json!({"channel":"manual"});
    let idempotency_key = hash_serializable(&(
        adapter_plan_id,
        notification_plan_id,
        "manual://review",
        &request_template,
    ))
    .unwrap();
    let plan_hash = hash_serializable(&(
        EventId::new(),
        adapter_plan_id,
        WaiverNotificationAdapterKind::Manual,
        NotificationDeliveryClientMode::SendApproved,
        "manual://review",
        &request_template,
        &idempotency_key,
        created_at,
    ))
    .unwrap();
    assert!(!plan_hash.is_empty());
}
