//! Purpose: runtime configuration and environment helper boundary for the Nested Mind API.
//! Governance scope: environment parsing, bootstrap runtime construction, auth header parsing, and policy defaults.
//! Dependencies: API-local runtime store adapters, mind-core configuration contracts, and process environment variables.
//! Invariants: environment-derived state remains explicit; invalid configuration returns causal MindError values; auth header parsing is behavior-preserving.

use super::*;

#[allow(clippy::type_complexity)]
pub(super) fn initialize_runtime() -> Result<
    (
        Mind,
        RuntimeEventStore,
        RuntimeSnapshotStore,
        RuntimeObservabilitySink,
        Option<Arc<Ed25519CommitSigner>>,
        SigningBackendStatus,
    ),
    MindError,
> {
    let identity = configured_root_identity();
    let signature_requirement = configured_signature_requirement();
    let (signer, signing_status) = configured_signing_from_env()?;
    if signature_requirement == SignatureRequirement::Required && !signing_status.can_sign_inline {
        return Err(MindError::Store("MIND_REQUIRE_SIGNATURES=true requires an inline signing backend; set MIND_SIGNING_BACKEND=env_ed25519 and MIND_COMMIT_SIGNING_SEED_HEX".to_owned()));
    }
    let store = RuntimeEventStore::from_env(signature_requirement)?;
    let snapshots = RuntimeSnapshotStore::from_env(signature_requirement)?;
    let observability = RuntimeObservabilitySink::from_env()?;
    let records = store.records_for_mind(identity.id)?;
    tracing::info!(root_mind_id = %identity.id, event_count = records.len(), "mind_runtime_loaded");
    let root = if records.is_empty() {
        Mind::from_identity(identity)
    } else {
        ReplayEngine::replay_with_signature_requirement(identity, &records, signature_requirement)?
            .0
    };
    Ok((
        root,
        store,
        snapshots,
        observability,
        signer,
        signing_status,
    ))
}

pub(super) fn configured_root_identity() -> Identity {
    let kind = env::var("MIND_ROOT_KIND").unwrap_or_else(|_| "root".to_owned());
    match env::var("MIND_ROOT_ID") {
        Ok(value) if !value.trim().is_empty() => Identity::root_with_id(
            MindId::parse_str(value.trim()).expect("MIND_ROOT_ID must be a valid UUID"),
            kind,
        ),
        _ => Identity::root(kind),
    }
}
pub(super) fn configured_signature_requirement() -> SignatureRequirement {
    match env::var("MIND_REQUIRE_SIGNATURES") {
        Ok(v) if is_truthy(&v) => SignatureRequirement::Required,
        _ => SignatureRequirement::Optional,
    }
}
pub(super) fn configured_signing_from_env(
) -> Result<(Option<Arc<Ed25519CommitSigner>>, SigningBackendStatus), MindError> {
    let backend = env::var("MIND_SIGNING_BACKEND").unwrap_or_else(|_| "env_ed25519".to_owned());
    let key_id =
        env::var("MIND_COMMIT_SIGNING_KEY_ID").unwrap_or_else(|_| "runtime-ed25519".to_owned());
    match backend.trim().to_ascii_lowercase().as_str() {
        "off" | "disabled" | "none" => Ok((None, SigningBackendStatus::disabled())),
        "secret_manager" | "hsm" | "kms" | "external" | "external_request" => {
            let kind = match backend.trim().to_ascii_lowercase().as_str() {
                "secret_manager" => SigningBackendKind::SecretManager,
                "hsm" => SigningBackendKind::Hsm,
                "kms" => SigningBackendKind::Kms,
                _ => SigningBackendKind::ExternalRequest,
            };
            Ok((None, SigningBackendStatus::external(kind, key_id)))
        }
        _ => {
            let Ok(seed_hex) = env::var("MIND_COMMIT_SIGNING_SEED_HEX") else {
                return Ok((None, SigningBackendStatus::disabled()));
            };
            if seed_hex.trim().is_empty() {
                return Ok((None, SigningBackendStatus::disabled()));
            }
            let signer = Ed25519CommitSigner::from_seed_hex(key_id.clone(), seed_hex.trim())?;
            Ok((
                Some(Arc::new(signer)),
                SigningBackendStatus::local_ed25519(key_id),
            ))
        }
    }
}

pub(super) fn init_tracing_from_env() {
    let default_filter = env::var("MIND_LOG_LEVEL")
        .or_else(|_| env::var("MIND_TRACE_LEVEL"))
        .unwrap_or_else(|_| "mind_api=info,tower_http=info".to_owned());
    let filter =
        EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new(default_filter));
    if matches!(env::var("MIND_TRACE_JSON"), Ok(value) if is_truthy(&value)) {
        let _ = tracing_subscriber::fmt()
            .with_env_filter(filter)
            .json()
            .try_init();
    } else {
        let _ = tracing_subscriber::fmt().with_env_filter(filter).try_init();
    }
}

pub(super) fn request_safety_config_from_env() -> Result<RequestSafetyConfig, MindError> {
    let max_body_bytes = env::var("MIND_MAX_BODY_BYTES")
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(64 * 1024);
    let max_requests = env::var("MIND_RATE_LIMIT_REQUESTS")
        .ok()
        .and_then(|value| value.parse::<u32>().ok())
        .unwrap_or(60);
    let window_seconds = env::var("MIND_RATE_LIMIT_WINDOW_SECONDS")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(60);
    let config = RequestSafetyConfig::new(max_body_bytes, max_requests, window_seconds);
    config.validate()?;
    Ok(config)
}

pub(super) fn distributed_lease_boundary_from_env(
) -> Result<DistributedLeaseServiceBoundary, MindError> {
    let service_id = env::var("MIND_DISTRIBUTED_LEASE_SERVICE_ID")
        .unwrap_or_else(|_| "local-scheduler-lease".to_owned());
    let lease_seconds = env::var("MIND_DISTRIBUTED_LEASE_SECONDS")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(60);
    match env::var("MIND_DISTRIBUTED_LEASE_ENDPOINT") {
        Ok(endpoint) if !endpoint.trim().is_empty() => {
            DistributedLeaseServiceBoundary::external_gateway(service_id, endpoint, lease_seconds)
        }
        _ => DistributedLeaseServiceBoundary::sqlite_local(service_id),
    }
}

pub(super) fn scheduler_lease_policy(
    lease_seconds: Option<u64>,
    limit: usize,
) -> Result<SchedulerLeasePolicy, MindError> {
    let mut policy = SchedulerLeasePolicy::default();
    if let Some(lease_seconds) = lease_seconds {
        policy.lease_seconds = lease_seconds;
    }
    policy.max_claims_per_poll = limit.max(1);
    policy.validate()?;
    Ok(policy)
}

pub(super) fn oidc_verifier_from_env() -> Result<Option<RuntimeOidcVerifier>, MindError> {
    if env::var("MIND_OIDC_DISCOVERY_FILE").is_ok() {
        if let Some(discovery) = oidc_discovery_from_env()? {
            let config = discovery.document.verifier_config(&discovery.config)?;
            return Ok(Some(RuntimeOidcVerifier {
                config,
                jwks_json: discovery.jwks_json,
            }));
        }
    }
    let Ok(jwks_file) = env::var("MIND_OIDC_JWKS_FILE") else {
        return Ok(None);
    };
    if jwks_file.trim().is_empty() {
        return Ok(None);
    }
    let issuer = env::var("MIND_OIDC_ISSUER").map_err(|_| {
        MindError::Identity(
            "MIND_OIDC_ISSUER is required when MIND_OIDC_JWKS_FILE is set".to_owned(),
        )
    })?;
    let audience_value = env::var("MIND_OIDC_AUDIENCES")
        .or_else(|_| env::var("MIND_OIDC_AUDIENCE"))
        .map_err(|_| {
            MindError::Identity(
                "MIND_OIDC_AUDIENCES is required when MIND_OIDC_JWKS_FILE is set".to_owned(),
            )
        })?;
    let mut config = OidcJwksVerifierConfig::new(issuer);
    config.audiences = csv_set(&audience_value);
    if let Ok(value) = env::var("MIND_OIDC_ALLOWED_ALGORITHMS") {
        config.allowed_algorithms = csv_set(&value);
    }
    if let Ok(value) = env::var("MIND_OIDC_DEFAULT_ROLE") {
        config.default_role = mind_core::parse_role(&value);
    }
    config.validate()?;
    let jwks_json = std::fs::read_to_string(jwks_file.trim())?;
    Ok(Some(RuntimeOidcVerifier {
        config,
        jwks_json: Arc::new(jwks_json),
    }))
}

pub(super) fn identity_policy_from_env() -> IdentityBindingPolicy {
    let mut policy = IdentityBindingPolicy::default();
    if let Ok(value) = env::var("MIND_IDENTITY_ALLOWED_ISSUERS") {
        policy.allowed_issuers = csv_set(&value);
    }
    if let Ok(value) = env::var("MIND_IDENTITY_REQUIRED_AUDIENCES") {
        policy.required_audiences = csv_set(&value);
    }
    if let Ok(value) = env::var("MIND_IDENTITY_REQUIRED_CLIENT_CERT_SHA256") {
        if !value.trim().is_empty() {
            policy = policy.require_client_certificate_sha256(value.trim());
        }
    }
    policy
}

pub(super) fn distributed_plan_from_env() -> Result<DistributedEventStorePlan, MindError> {
    let node_id = env::var("MIND_NODE_ID").unwrap_or_else(|_| "local".to_owned());
    let strategy =
        env::var("MIND_EVENT_STORE_STRATEGY").unwrap_or_else(|_| "single_writer".to_owned());
    let role = env::var("MIND_NODE_ROLE").unwrap_or_else(|_| "single".to_owned());
    let voting_members = env::var("MIND_VOTING_MEMBERS")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(1);
    let mut plan = match strategy.trim().to_ascii_lowercase().as_str() {
        "leader_replicated" => match role.trim().to_ascii_lowercase().as_str() {
            "leader" => DistributedEventStorePlan::leader(node_id, voting_members),
            _ => DistributedEventStorePlan::follower(node_id, voting_members),
        },
        "consensus" | "consensus_replicated" => {
            let quorum_size = env::var("MIND_QUORUM_SIZE")
                .ok()
                .and_then(|value| value.parse::<u16>().ok())
                .unwrap_or(voting_members / 2 + 1);
            DistributedEventStorePlan {
                strategy: EventStoreStrategy::ConsensusReplicated,
                node_id,
                role: parse_node_role(&role),
                voting_members,
                quorum_size,
                allow_local_appends: matches!(parse_node_role(&role), DistributedNodeRole::Leader),
                replication_lag_limit_events: Some(128),
            }
        }
        "object_archived_follower" => DistributedEventStorePlan {
            strategy: EventStoreStrategy::ObjectArchivedFollower,
            node_id,
            role: DistributedNodeRole::Follower,
            voting_members: 1,
            quorum_size: 1,
            allow_local_appends: false,
            replication_lag_limit_events: Some(0),
        },
        _ => DistributedEventStorePlan::single_writer(node_id),
    };
    if let Ok(value) = env::var("MIND_ALLOW_LOCAL_APPENDS") {
        plan.allow_local_appends = is_truthy(&value);
    }
    plan.validate()?;
    Ok(plan)
}

pub(super) fn parse_node_role(value: &str) -> DistributedNodeRole {
    match value.trim().to_ascii_lowercase().as_str() {
        "leader" => DistributedNodeRole::Leader,
        "follower" => DistributedNodeRole::Follower,
        "witness" => DistributedNodeRole::Witness,
        "learner" => DistributedNodeRole::Learner,
        _ => DistributedNodeRole::Single,
    }
}

pub(super) fn object_backup_store_from_env() -> Result<Option<FileObjectBackupStore>, MindError> {
    match env::var("MIND_BACKUP_OBJECT_DIR") {
        Ok(path) if !path.trim().is_empty() => Ok(Some(FileObjectBackupStore::new(path.trim())?)),
        _ => Ok(None),
    }
}

pub(super) fn oidc_discovery_from_env() -> Result<Option<RuntimeOidcDiscovery>, MindError> {
    let Ok(discovery_file) = env::var("MIND_OIDC_DISCOVERY_FILE") else {
        return Ok(None);
    };
    if discovery_file.trim().is_empty() {
        return Ok(None);
    }
    let jwks_file = env::var("MIND_OIDC_JWKS_FILE").map_err(|_| {
        MindError::Identity(
            "MIND_OIDC_JWKS_FILE is required when MIND_OIDC_DISCOVERY_FILE is set".to_owned(),
        )
    })?;
    let issuer = env::var("MIND_OIDC_ISSUER").map_err(|_| {
        MindError::Identity(
            "MIND_OIDC_ISSUER is required when MIND_OIDC_DISCOVERY_FILE is set".to_owned(),
        )
    })?;
    let audience_value = env::var("MIND_OIDC_AUDIENCES")
        .or_else(|_| env::var("MIND_OIDC_AUDIENCE"))
        .map_err(|_| {
            MindError::Identity(
                "MIND_OIDC_AUDIENCES is required when MIND_OIDC_DISCOVERY_FILE is set".to_owned(),
            )
        })?;
    let mut config = OidcDiscoveryConfig::new(issuer);
    config.audiences = csv_set(&audience_value);
    if let Ok(value) = env::var("MIND_OIDC_ALLOWED_ALGORITHMS") {
        config.allowed_algorithms = csv_set(&value);
    }
    if let Ok(value) = env::var("MIND_OIDC_DEFAULT_ROLE") {
        config.default_role = mind_core::parse_role(&value);
    }
    if let Ok(value) = env::var("MIND_OIDC_REFRESH_TTL_SECONDS") {
        if let Ok(ttl) = value.parse::<u64>() {
            config.refresh_ttl_seconds = ttl;
        }
    }
    let document = serde_json::from_str::<OidcDiscoveryDocument>(&std::fs::read_to_string(
        discovery_file.trim(),
    )?)?;
    document.validate_for(&config)?;
    let jwks_json = std::fs::read_to_string(jwks_file.trim())?;
    Ok(Some(RuntimeOidcDiscovery {
        config,
        document,
        jwks_json: Arc::new(jwks_json),
    }))
}

pub(super) fn cloud_mirror_from_env() -> Result<Option<LocalCloudMirrorStore>, MindError> {
    match env::var("MIND_CLOUD_OBJECT_MIRROR_DIR") {
        Ok(path) if !path.trim().is_empty() => Ok(Some(LocalCloudMirrorStore::new(path.trim())?)),
        _ => Ok(None),
    }
}

pub(super) fn cloud_backup_target_from_env() -> Result<CloudObjectStoreTarget, MindError> {
    let provider = cloud_provider_from_str(
        &env::var("MIND_CLOUD_BACKUP_PROVIDER").unwrap_or_else(|_| "s3".to_owned()),
    );
    let bucket = env::var("MIND_CLOUD_BACKUP_BUCKET").unwrap_or_else(|_| "mind-backups".to_owned());
    let prefix = env::var("MIND_CLOUD_BACKUP_PREFIX").unwrap_or_else(|_| "root".to_owned());
    let mut target = CloudObjectStoreTarget::new(provider, bucket, prefix);
    if let Ok(region) = env::var("MIND_CLOUD_BACKUP_REGION") {
        if !region.trim().is_empty() {
            target = target.with_region(region);
        }
    }
    if let Ok(endpoint) = env::var("MIND_CLOUD_BACKUP_ENDPOINT") {
        if !endpoint.trim().is_empty() {
            target = target.with_endpoint(endpoint);
        }
    }
    if let Ok(kms_key) = env::var("MIND_CLOUD_BACKUP_KMS_KEY_ID") {
        if !kms_key.trim().is_empty() {
            target = target.with_kms_key(kms_key);
        }
    }
    target.validate()?;
    Ok(target)
}

pub(super) fn cloud_provider_from_str(value: &str) -> CloudObjectProvider {
    match value.trim().to_ascii_lowercase().as_str() {
        "gcs" | "google" | "google_cloud_storage" => CloudObjectProvider::Gcs,
        "azure" | "azure_blob" | "blob" => CloudObjectProvider::AzureBlob,
        _ => CloudObjectProvider::S3Compatible,
    }
}

pub(super) fn replication_inbox_from_env() -> Result<Option<JsonlReplicationInbox>, MindError> {
    match env::var("MIND_REPLICATION_INBOX_LOG") {
        Ok(path) if !path.trim().is_empty() => Ok(Some(JsonlReplicationInbox::new(path.trim())?)),
        _ => Ok(None),
    }
}

pub(super) fn replication_transport_from_env() -> Result<ReplicationTransportPlan, MindError> {
    let leader_id = env::var("MIND_REPLICATION_LEADER_ID")
        .unwrap_or_else(|_| env::var("MIND_NODE_ID").unwrap_or_else(|_| "leader-a".to_owned()));
    let followers = env::var("MIND_REPLICATION_FOLLOWERS")
        .unwrap_or_default()
        .split(',')
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(|value| {
            let mut parts = value.splitn(2, '=');
            let node_id = parts.next().unwrap_or("follower").trim();
            let base_url = parts.next().unwrap_or(node_id).trim();
            ReplicationEndpoint::new(node_id, base_url)
        })
        .collect::<Vec<_>>();
    let required_acks = env::var("MIND_REPLICATION_REQUIRED_ACKS")
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(1);
    let mut plan = ReplicationTransportPlan::new(leader_id, followers, required_acks);
    if let Ok(value) = env::var("MIND_REPLICATION_MAX_RECORDS_PER_BATCH") {
        if let Ok(max) = value.parse::<usize>() {
            plan.max_records_per_batch = max.max(1);
        }
    }
    plan.validate()?;
    Ok(plan)
}

pub(super) fn oidc_live_config_from_env() -> Result<OidcDiscoveryConfig, MindError> {
    let issuer = env::var("MIND_OIDC_ISSUER").map_err(|_| {
        MindError::Identity("MIND_OIDC_ISSUER is required for live OIDC refresh".to_owned())
    })?;
    let audience_value = env::var("MIND_OIDC_AUDIENCES")
        .or_else(|_| env::var("MIND_OIDC_AUDIENCE"))
        .map_err(|_| {
            MindError::Identity("MIND_OIDC_AUDIENCES is required for live OIDC refresh".to_owned())
        })?;
    let mut config = OidcDiscoveryConfig::new(issuer);
    config.audiences = csv_set(&audience_value);
    if let Ok(value) = env::var("MIND_OIDC_ALLOWED_ALGORITHMS") {
        config.allowed_algorithms = csv_set(&value);
    }
    if let Ok(value) = env::var("MIND_OIDC_DEFAULT_ROLE") {
        config.default_role = mind_core::parse_role(&value);
    }
    if let Ok(value) = env::var("MIND_OIDC_REFRESH_TTL_SECONDS") {
        if let Ok(ttl) = value.parse::<u64>() {
            config.refresh_ttl_seconds = ttl;
        }
    }
    config.validate()?;
    Ok(config)
}

pub(super) fn replication_retry_policy_from_env() -> Result<ReplicationRetryPolicy, MindError> {
    let mut policy = ReplicationRetryPolicy::default();
    if let Ok(value) = env::var("MIND_REPLICATION_RETRY_MAX_ATTEMPTS") {
        if let Ok(parsed) = value.parse::<u32>() {
            policy.max_attempts = parsed;
        }
    }
    if let Ok(value) = env::var("MIND_REPLICATION_RETRY_INITIAL_DELAY_MS") {
        if let Ok(parsed) = value.parse::<u64>() {
            policy.initial_delay_ms = parsed;
        }
    }
    if let Ok(value) = env::var("MIND_REPLICATION_RETRY_MAX_DELAY_MS") {
        if let Ok(parsed) = value.parse::<u64>() {
            policy.max_delay_ms = parsed;
        }
    }
    if let Ok(value) = env::var("MIND_REPLICATION_RETRY_MULTIPLIER") {
        if let Ok(parsed) = value.parse::<u32>() {
            policy.multiplier = parsed.max(1);
        }
    }
    policy.validate()?;
    Ok(policy)
}

pub(super) fn consensus_from_env() -> Result<ConsensusMembership, MindError> {
    let cluster_id =
        env::var("MIND_CONSENSUS_CLUSTER_ID").unwrap_or_else(|_| "local-cluster".to_owned());
    let members_value = env::var("MIND_CONSENSUS_MEMBERS")
        .unwrap_or_else(|_| env::var("MIND_NODE_ID").unwrap_or_else(|_| "local".to_owned()));
    let members = members_value
        .split(',')
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ConsensusMember::voter)
        .collect::<Vec<_>>();
    let mut membership = ConsensusMembership::new(cluster_id, members);
    if let Ok(leader_id) = env::var("MIND_CONSENSUS_LEADER_ID") {
        if !leader_id.trim().is_empty() {
            membership =
                membership.apply_change(mind_core::ConsensusMembershipChange::SetLeader {
                    member_id: leader_id,
                })?;
        }
    }
    membership.validate()?;
    Ok(membership)
}

pub(super) fn csv_set(value: &str) -> BTreeSet<String> {
    value
        .split(',')
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(str::to_owned)
        .collect()
}

pub(super) fn header_str<'a>(headers: &'a HeaderMap, name: &str) -> Option<&'a str> {
    headers
        .get(name)?
        .to_str()
        .ok()
        .map(str::trim)
        .filter(|value| !value.is_empty())
}

pub(super) fn header_csv(headers: &HeaderMap, name: &str) -> Vec<String> {
    header_str(headers, name).map_or_else(Vec::new, |value| {
        value
            .split(',')
            .map(str::trim)
            .filter(|item| !item.is_empty())
            .map(str::to_owned)
            .collect()
    })
}

pub(super) fn bearer_token(headers: &HeaderMap) -> Option<&str> {
    headers
        .get(AUTHORIZATION)?
        .to_str()
        .ok()?
        .strip_prefix("Bearer ")
}
pub(super) fn insert_token_principal(
    tokens: &mut BTreeMap<String, Principal>,
    token_env: &str,
    principal_env: &str,
    default_principal: &str,
    role: Role,
) {
    let Ok(token) = env::var(token_env) else {
        return;
    };
    if token.trim().is_empty() {
        return;
    }
    let principal_id = env::var(principal_env).unwrap_or_else(|_| default_principal.to_owned());
    tokens.insert(
        token.trim().to_owned(),
        Principal::new(principal_id).with_role(role),
    );
}
pub(super) fn is_truthy(value: &str) -> bool {
    matches!(
        value.trim().to_ascii_lowercase().as_str(),
        "1" | "true" | "yes" | "on" | "required"
    )
}
pub(super) fn snapshot_compaction_policy_from_env() -> SnapshotCompactionPolicy {
    let keep_latest = env::var("MIND_SNAPSHOT_KEEP_LATEST")
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(3);
    let min_events = env::var("MIND_SNAPSHOT_MIN_EVENTS_BETWEEN")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(25);
    SnapshotCompactionPolicy::new(keep_latest, min_events)
}
