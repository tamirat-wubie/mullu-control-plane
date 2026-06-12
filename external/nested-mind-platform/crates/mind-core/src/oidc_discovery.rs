use crate::{hash_serializable, MindError, MindResult, OidcJwksVerifierConfig, Role};
use jsonwebtoken::jwk::JwkSet;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use time::{Duration, OffsetDateTime};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct OidcDiscoveryConfig {
    pub issuer: String,
    #[serde(default)]
    pub audiences: BTreeSet<String>,
    #[serde(default)]
    pub allowed_algorithms: BTreeSet<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub default_role: Option<Role>,
    pub refresh_ttl_seconds: u64,
}

impl OidcDiscoveryConfig {
    #[must_use]
    pub fn new(issuer: impl Into<String>) -> Self {
        Self {
            issuer: issuer.into(),
            audiences: BTreeSet::new(),
            allowed_algorithms: BTreeSet::from(["RS256".to_owned()]),
            default_role: Some(Role::Observer),
            refresh_ttl_seconds: 3600,
        }
    }

    #[must_use]
    pub fn with_audience(mut self, audience: impl Into<String>) -> Self {
        self.audiences.insert(audience.into());
        self
    }

    #[must_use]
    pub fn allow_algorithm(mut self, algorithm: impl Into<String>) -> Self {
        self.allowed_algorithms.insert(algorithm.into());
        self
    }

    pub fn validate(&self) -> MindResult<()> {
        if self.issuer.trim().is_empty() {
            return Err(MindError::Identity(
                "OIDC discovery issuer is required".to_owned(),
            ));
        }
        if self.audiences.is_empty() {
            return Err(MindError::Identity(
                "OIDC discovery requires at least one audience".to_owned(),
            ));
        }
        if self.allowed_algorithms.is_empty() {
            return Err(MindError::Identity(
                "OIDC discovery requires at least one allowed algorithm".to_owned(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn discovery_url(&self) -> String {
        oidc_discovery_url(&self.issuer)
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct OidcDiscoveryDocument {
    pub issuer: String,
    pub jwks_uri: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub authorization_endpoint: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub token_endpoint: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub userinfo_endpoint: Option<String>,
    #[serde(default)]
    pub response_types_supported: Vec<String>,
    #[serde(default)]
    pub id_token_signing_alg_values_supported: Vec<String>,
    #[serde(flatten)]
    pub metadata: BTreeMap<String, Value>,
}

impl OidcDiscoveryDocument {
    pub fn validate_for(&self, config: &OidcDiscoveryConfig) -> MindResult<()> {
        config.validate()?;
        if self.issuer != config.issuer {
            return Err(MindError::IdentityRejected {
                reason: format!(
                    "discovered issuer `{}` does not match configured issuer `{}`",
                    self.issuer, config.issuer
                ),
            });
        }
        if self.jwks_uri.trim().is_empty() {
            return Err(MindError::IdentityRejected {
                reason: "discovered OIDC document has no jwks_uri".to_owned(),
            });
        }
        if !self.id_token_signing_alg_values_supported.is_empty() {
            let supported: BTreeSet<&str> = self
                .id_token_signing_alg_values_supported
                .iter()
                .map(String::as_str)
                .collect();
            if !config
                .allowed_algorithms
                .iter()
                .any(|alg| supported.contains(alg.as_str()))
            {
                return Err(MindError::IdentityRejected {
                    reason:
                        "discovered OIDC document does not advertise an allowed ID-token algorithm"
                            .to_owned(),
                });
            }
        }
        Ok(())
    }

    pub fn verifier_config(
        &self,
        config: &OidcDiscoveryConfig,
    ) -> MindResult<OidcJwksVerifierConfig> {
        self.validate_for(config)?;
        let mut verifier = OidcJwksVerifierConfig::new(self.issuer.clone());
        verifier.audiences = config.audiences.clone();
        verifier.allowed_algorithms = config.allowed_algorithms.clone();
        verifier.default_role = config.default_role.clone();
        Ok(verifier)
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct OidcJwksRefreshRequest {
    pub request_id: crate::EventId,
    pub issuer: String,
    pub discovery_url: String,
    pub jwks_uri: String,
    pub created_at: OffsetDateTime,
}

impl OidcJwksRefreshRequest {
    pub fn from_document(
        config: &OidcDiscoveryConfig,
        document: &OidcDiscoveryDocument,
    ) -> MindResult<Self> {
        document.validate_for(config)?;
        Ok(Self {
            request_id: crate::EventId::new(),
            issuer: config.issuer.clone(),
            discovery_url: config.discovery_url(),
            jwks_uri: document.jwks_uri.clone(),
            created_at: OffsetDateTime::now_utc(),
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct OidcJwksCacheEntry {
    pub issuer: String,
    pub jwks_uri: String,
    pub jwks_hash: String,
    pub key_count: usize,
    pub cached_at: OffsetDateTime,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub expires_at: Option<OffsetDateTime>,
    pub jwks_json: String,
}

impl OidcJwksCacheEntry {
    pub fn from_jwks_json(
        issuer: impl Into<String>,
        jwks_uri: impl Into<String>,
        jwks_json: impl Into<String>,
        ttl_seconds: Option<u64>,
    ) -> MindResult<Self> {
        let jwks_json = jwks_json.into();
        let jwks = serde_json::from_str::<JwkSet>(&jwks_json)?;
        let normalized: Value = serde_json::from_str(&jwks_json)?;
        let cached_at = OffsetDateTime::now_utc();
        let expires_at =
            ttl_seconds.and_then(|ttl| cached_at.checked_add(Duration::seconds(ttl as i64)));
        Ok(Self {
            issuer: issuer.into(),
            jwks_uri: jwks_uri.into(),
            jwks_hash: hash_serializable(&normalized)?,
            key_count: jwks.keys.len(),
            cached_at,
            expires_at,
            jwks_json,
        })
    }

    #[must_use]
    pub fn is_expired_at(&self, at: OffsetDateTime) -> bool {
        self.expires_at.is_some_and(|expires_at| at >= expires_at)
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct OidcDiscoveryRefreshReport {
    pub issuer: String,
    pub discovery_url: String,
    pub jwks_uri: String,
    pub cache_updated: bool,
    pub jwks_hash: String,
    pub key_count: usize,
    #[serde(default)]
    pub notes: Vec<String>,
}

impl OidcDiscoveryRefreshReport {
    pub fn refreshed(
        config: &OidcDiscoveryConfig,
        document: &OidcDiscoveryDocument,
        cache: &OidcJwksCacheEntry,
    ) -> MindResult<Self> {
        document.validate_for(config)?;
        Ok(Self {
            issuer: config.issuer.clone(),
            discovery_url: config.discovery_url(),
            jwks_uri: document.jwks_uri.clone(),
            cache_updated: true,
            jwks_hash: cache.jwks_hash.clone(),
            key_count: cache.key_count,
            notes: Vec::new(),
        })
    }
}

#[must_use]
pub fn oidc_discovery_url(issuer: &str) -> String {
    format!(
        "{}/.well-known/openid-configuration",
        issuer.trim_end_matches('/')
    )
}
