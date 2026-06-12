use crate::{
    hash_serializable, CloudObjectProvider, EventId, ManagedSigningProvider, MindBackup, MindError,
    MindResult, OidcDiscoveryConfig, OidcDiscoveryDocument, OidcJwksCacheEntry,
    OidcJwksVerifierConfig, ReplicationAck, ReplicationEnvelope,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ConnectorExecutionMode {
    PlanOnly,
    LiveHttp,
    VendorSdk,
    SignedUrl,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct LiveOidcRefreshRequest {
    pub request_id: EventId,
    pub issuer: String,
    pub discovery_url: String,
    pub expected_audiences: Vec<String>,
    pub allowed_algorithms: Vec<String>,
    pub mode: ConnectorExecutionMode,
    pub requested_at: OffsetDateTime,
}

impl LiveOidcRefreshRequest {
    pub fn from_config(
        config: &OidcDiscoveryConfig,
        mode: ConnectorExecutionMode,
    ) -> MindResult<Self> {
        config.validate()?;
        Ok(Self {
            request_id: EventId::new(),
            issuer: config.issuer.clone(),
            discovery_url: config.discovery_url(),
            expected_audiences: config.audiences.iter().cloned().collect(),
            allowed_algorithms: config.allowed_algorithms.iter().cloned().collect(),
            mode,
            requested_at: OffsetDateTime::now_utc(),
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct LiveOidcRefreshReport {
    pub refresh_id: EventId,
    pub request: LiveOidcRefreshRequest,
    pub discovery_hash: String,
    pub jwks_hash: String,
    pub key_count: usize,
    pub verifier_config: OidcJwksVerifierConfig,
    pub cache: OidcJwksCacheEntry,
    pub completed_at: OffsetDateTime,
    #[serde(default)]
    pub notes: Vec<String>,
}

impl LiveOidcRefreshReport {
    pub fn from_parts(
        request: LiveOidcRefreshRequest,
        config: &OidcDiscoveryConfig,
        document: &OidcDiscoveryDocument,
        jwks_json: impl Into<String>,
    ) -> MindResult<Self> {
        document.validate_for(config)?;
        let jwks_json = jwks_json.into();
        let cache = OidcJwksCacheEntry::from_jwks_json(
            config.issuer.clone(),
            document.jwks_uri.clone(),
            jwks_json,
            Some(config.refresh_ttl_seconds),
        )?;
        let verifier_config = document.verifier_config(config)?;
        Ok(Self {
            refresh_id: EventId::new(),
            request,
            discovery_hash: hash_serializable(document)?,
            jwks_hash: cache.jwks_hash.clone(),
            key_count: cache.key_count,
            verifier_config,
            cache,
            completed_at: OffsetDateTime::now_utc(),
            notes: Vec::new(),
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SigningGatewayEndpoint {
    pub endpoint_id: String,
    pub provider: ManagedSigningProvider,
    pub base_url: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub bearer_token_ref: Option<String>,
    pub timeout_seconds: u64,
}

impl SigningGatewayEndpoint {
    #[must_use]
    pub fn new(
        endpoint_id: impl Into<String>,
        provider: ManagedSigningProvider,
        base_url: impl Into<String>,
    ) -> Self {
        Self {
            endpoint_id: endpoint_id.into(),
            provider,
            base_url: base_url.into(),
            bearer_token_ref: None,
            timeout_seconds: 30,
        }
    }

    pub fn validate(&self) -> MindResult<()> {
        if self.endpoint_id.trim().is_empty() {
            return Err(MindError::Signing(
                "signing gateway endpoint id is required".to_owned(),
            ));
        }
        if self.base_url.trim().is_empty() {
            return Err(MindError::Signing(
                "signing gateway base URL is required".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CloudSignedUrlRequest {
    pub request_id: EventId,
    pub provider: CloudObjectProvider,
    pub method: String,
    pub url: String,
    pub bucket: String,
    pub key: String,
    pub expected_body_sha256_hex: String,
    pub body_bytes: usize,
    pub created_at: OffsetDateTime,
}

impl CloudSignedUrlRequest {
    pub fn put_backup(
        provider: CloudObjectProvider,
        url: impl Into<String>,
        bucket: impl Into<String>,
        key: impl Into<String>,
        backup: &MindBackup,
    ) -> MindResult<Self> {
        let body = serde_json::to_vec(backup)?;
        Ok(Self {
            request_id: EventId::new(),
            provider,
            method: "PUT".to_owned(),
            url: url.into(),
            bucket: bucket.into(),
            key: key.into(),
            expected_body_sha256_hex: hex::encode(Sha256::digest(&body)),
            body_bytes: body.len(),
            created_at: OffsetDateTime::now_utc(),
        })
    }

    pub fn validate(&self) -> MindResult<()> {
        if self.url.trim().is_empty() {
            return Err(MindError::ObjectStorage {
                reason: "signed URL is required".to_owned(),
            });
        }
        if self.bucket.trim().is_empty() || self.key.trim().is_empty() {
            return Err(MindError::ObjectStorage {
                reason: "signed URL bucket/key is required".to_owned(),
            });
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CloudSignedUrlReceipt {
    pub receipt_id: EventId,
    pub request_id: EventId,
    pub provider: CloudObjectProvider,
    pub method: String,
    pub bucket: String,
    pub key: String,
    pub status_code: u16,
    pub expected_body_sha256_hex: String,
    pub observed_body_sha256_hex: String,
    pub verified: bool,
    pub completed_at: OffsetDateTime,
}

impl CloudSignedUrlReceipt {
    #[must_use]
    pub fn from_request(
        request: &CloudSignedUrlRequest,
        status_code: u16,
        observed_body_sha256_hex: impl Into<String>,
    ) -> Self {
        let observed = observed_body_sha256_hex.into();
        Self {
            receipt_id: EventId::new(),
            request_id: request.request_id,
            provider: request.provider,
            method: request.method.clone(),
            bucket: request.bucket.clone(),
            key: request.key.clone(),
            status_code,
            expected_body_sha256_hex: request.expected_body_sha256_hex.clone(),
            verified: observed == request.expected_body_sha256_hex
                && (200..300).contains(&status_code),
            observed_body_sha256_hex: observed,
            completed_at: OffsetDateTime::now_utc(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReplicationRetryPolicy {
    pub max_attempts: u32,
    pub initial_delay_ms: u64,
    pub max_delay_ms: u64,
    pub multiplier: u32,
}

impl Default for ReplicationRetryPolicy {
    fn default() -> Self {
        Self {
            max_attempts: 3,
            initial_delay_ms: 250,
            max_delay_ms: 5_000,
            multiplier: 2,
        }
    }
}

impl ReplicationRetryPolicy {
    pub fn validate(&self) -> MindResult<()> {
        if self.max_attempts == 0 {
            return Err(MindError::DistributedPlanInvalid {
                reason: "replication retry policy must allow at least one attempt".to_owned(),
            });
        }
        if self.initial_delay_ms == 0 || self.max_delay_ms == 0 {
            return Err(MindError::DistributedPlanInvalid {
                reason: "replication retry delays must be greater than zero".to_owned(),
            });
        }
        if self.initial_delay_ms > self.max_delay_ms {
            return Err(MindError::DistributedPlanInvalid {
                reason: "initial retry delay cannot exceed max delay".to_owned(),
            });
        }
        Ok(())
    }

    #[must_use]
    pub fn delay_for_attempt_ms(&self, attempt: u32) -> u64 {
        let exponent = attempt.saturating_sub(1);
        let mut delay = self.initial_delay_ms;
        for _ in 0..exponent {
            delay = delay
                .saturating_mul(self.multiplier as u64)
                .min(self.max_delay_ms);
        }
        delay.min(self.max_delay_ms)
    }
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ReplicationDeliveryStatus {
    Pending,
    Accepted,
    Rejected,
    RetryScheduled,
    Exhausted,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReplicationDeliveryAttempt {
    pub attempt: u32,
    pub status_code: Option<u16>,
    pub accepted: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    pub attempted_at: OffsetDateTime,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReplicationDeliveryReceipt {
    pub delivery_id: EventId,
    pub endpoint_node_id: String,
    pub endpoint_url: String,
    pub envelope_id: EventId,
    pub batch_id: EventId,
    pub status: ReplicationDeliveryStatus,
    #[serde(default)]
    pub attempts: Vec<ReplicationDeliveryAttempt>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ack: Option<ReplicationAck>,
    pub completed_at: OffsetDateTime,
}

impl ReplicationDeliveryReceipt {
    #[must_use]
    pub fn new(
        endpoint_node_id: impl Into<String>,
        endpoint_url: impl Into<String>,
        envelope: &ReplicationEnvelope,
    ) -> Self {
        Self {
            delivery_id: EventId::new(),
            endpoint_node_id: endpoint_node_id.into(),
            endpoint_url: endpoint_url.into(),
            envelope_id: envelope.envelope_id,
            batch_id: envelope.batch.batch_id,
            status: ReplicationDeliveryStatus::Pending,
            attempts: Vec::new(),
            ack: None,
            completed_at: OffsetDateTime::now_utc(),
        }
    }

    #[must_use]
    pub fn with_attempt(
        mut self,
        attempt: ReplicationDeliveryAttempt,
        ack: Option<ReplicationAck>,
        policy: &ReplicationRetryPolicy,
    ) -> Self {
        self.ack = ack;
        let accepted = self.ack.as_ref().is_some_and(|ack| ack.accepted);
        self.status = if accepted {
            ReplicationDeliveryStatus::Accepted
        } else if attempt.attempt >= policy.max_attempts {
            ReplicationDeliveryStatus::Exhausted
        } else if attempt.accepted {
            ReplicationDeliveryStatus::Rejected
        } else {
            ReplicationDeliveryStatus::RetryScheduled
        };
        self.attempts.push(attempt);
        self.completed_at = OffsetDateTime::now_utc();
        self
    }
}
