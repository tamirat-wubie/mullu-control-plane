use crate::{
    parse_role, ExternalIdentityAssertion, IdentityBindingPolicy, IdentitySource, MindError,
    MindResult, Role, VerifiedIdentity,
};
use jsonwebtoken::jwk::{Jwk, JwkSet};
use jsonwebtoken::{decode, decode_header, Algorithm, DecodingKey, Validation};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct OidcJwksVerifierConfig {
    pub issuer: String,
    #[serde(default)]
    pub audiences: BTreeSet<String>,
    #[serde(default)]
    pub allowed_algorithms: BTreeSet<String>,
    #[serde(default)]
    pub role_claims: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub default_role: Option<Role>,
    pub leeway_seconds: u64,
}

impl OidcJwksVerifierConfig {
    #[must_use]
    pub fn new(issuer: impl Into<String>) -> Self {
        Self {
            issuer: issuer.into(),
            audiences: BTreeSet::new(),
            allowed_algorithms: BTreeSet::from(["RS256".to_owned()]),
            role_claims: vec!["roles".to_owned(), "groups".to_owned()],
            default_role: Some(Role::Observer),
            leeway_seconds: 60,
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

    #[must_use]
    pub fn with_default_role(mut self, role: Option<Role>) -> Self {
        self.default_role = role;
        self
    }

    pub fn validate(&self) -> MindResult<()> {
        if self.issuer.trim().is_empty() {
            return Err(MindError::Identity("OIDC issuer is required".to_owned()));
        }
        if self.audiences.is_empty() {
            return Err(MindError::Identity(
                "at least one OIDC audience is required".to_owned(),
            ));
        }
        if self.allowed_algorithms.is_empty() {
            return Err(MindError::Identity(
                "at least one JWT signing algorithm must be allowed".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct OidcJwtClaimsSet {
    #[serde(rename = "iss")]
    pub issuer: String,
    #[serde(rename = "sub")]
    pub subject: String,
    #[serde(rename = "aud")]
    pub audience: JwtAudience,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub email: Option<String>,
    #[serde(default)]
    pub roles: Vec<String>,
    #[serde(default)]
    pub groups: Vec<String>,
    pub exp: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub iat: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub nbf: Option<u64>,
    #[serde(flatten)]
    pub extra: BTreeMap<String, Value>,
}

impl OidcJwtClaimsSet {
    #[must_use]
    pub fn audience_set(&self) -> BTreeSet<String> {
        self.audience.to_set()
    }

    #[must_use]
    pub fn role_set(&self, claim_names: &[String], fallback: Option<Role>) -> BTreeSet<Role> {
        let mut roles: BTreeSet<Role> = self
            .roles
            .iter()
            .chain(self.groups.iter())
            .filter_map(|value| parse_role(value))
            .collect();
        for claim_name in claim_names {
            if let Some(value) = self.extra.get(claim_name) {
                collect_roles_from_json(value, &mut roles);
            }
        }
        if roles.is_empty() {
            if let Some(role) = fallback {
                roles.insert(role);
            }
        }
        roles
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(untagged)]
pub enum JwtAudience {
    One(String),
    Many(Vec<String>),
}

impl JwtAudience {
    #[must_use]
    pub fn to_set(&self) -> BTreeSet<String> {
        match self {
            Self::One(value) => BTreeSet::from([value.clone()]),
            Self::Many(values) => values.iter().cloned().collect(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct OidcJwtVerificationReport {
    pub issuer: String,
    pub subject: String,
    #[serde(default)]
    pub audiences: BTreeSet<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub key_id: Option<String>,
    pub algorithm: String,
    pub signature_verified: bool,
    pub expires_at: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub issued_at: Option<u64>,
    #[serde(default)]
    pub roles: BTreeSet<Role>,
    pub verified_identity: VerifiedIdentity,
}

pub struct OidcJwksVerifier {
    config: OidcJwksVerifierConfig,
    jwks: JwkSet,
}

impl OidcJwksVerifier {
    pub fn from_jwks_json(config: OidcJwksVerifierConfig, jwks_json: &str) -> MindResult<Self> {
        config.validate()?;
        let jwks = serde_json::from_str::<JwkSet>(jwks_json)?;
        Ok(Self { config, jwks })
    }

    #[must_use]
    pub fn config(&self) -> &OidcJwksVerifierConfig {
        &self.config
    }

    pub fn verify(
        &self,
        jwt: &str,
        binding_policy: &IdentityBindingPolicy,
    ) -> MindResult<VerifiedIdentity> {
        Ok(self
            .verify_with_report(jwt, binding_policy)?
            .verified_identity)
    }

    pub fn verify_with_report(
        &self,
        jwt: &str,
        binding_policy: &IdentityBindingPolicy,
    ) -> MindResult<OidcJwtVerificationReport> {
        let header = decode_header(jwt)
            .map_err(|error| MindError::Identity(format!("JWT header decode failed: {error}")))?;
        let jwt_algorithm = header.alg;
        let algorithm = algorithm_name(&jwt_algorithm).to_owned();
        if !self.config.allowed_algorithms.contains(&algorithm) {
            return Err(MindError::IdentityRejected {
                reason: format!("JWT algorithm `{algorithm}` is not allowed"),
            });
        }
        let key_id = header.kid.clone();
        let key = match key_id.as_deref() {
            Some(kid) => {
                jwk_for_kid(&self.jwks, kid).ok_or_else(|| MindError::IdentityRejected {
                    reason: format!("JWKS key `{kid}` not found"),
                })?
            }
            None => {
                return Err(MindError::IdentityEvidenceRejected {
                    reason: "JWT header has no kid".to_owned(),
                })
            }
        };
        let decoding_key = DecodingKey::from_jwk(key).map_err(|error| {
            MindError::Identity(format!("JWKS decoding key creation failed: {error}"))
        })?;
        let mut validation = Validation::new(jwt_algorithm);
        validation.leeway = self.config.leeway_seconds;
        let audiences: Vec<&str> = self.config.audiences.iter().map(String::as_str).collect();
        validation.set_audience(&audiences);
        let issuers = [self.config.issuer.as_str()];
        validation.set_issuer(&issuers);
        let token = decode::<OidcJwtClaimsSet>(jwt, &decoding_key, &validation)
            .map_err(|error| MindError::Identity(format!("JWT verification failed: {error}")))?;
        let claims = token.claims;
        let audiences = claims.audience_set();
        let roles = claims.role_set(&self.config.role_claims, self.config.default_role.clone());
        let mut assertion =
            ExternalIdentityAssertion::new(IdentitySource::OidcJwt, claims.subject.clone())
                .with_issuer(claims.issuer.clone());
        for audience in &audiences {
            assertion = assertion.with_audience(audience.clone());
        }
        for role in &roles {
            assertion = assertion.with_role(role.clone());
        }
        assertion
            .attributes
            .insert("jwt.kid".to_owned(), key_id.clone().unwrap_or_default());
        assertion
            .attributes
            .insert("jwt.algorithm".to_owned(), algorithm.clone());
        assertion
            .attributes
            .insert("jwt.signature_verified".to_owned(), "true".to_owned());
        if let Some(email) = claims.email.clone() {
            assertion.attributes.insert("email".to_owned(), email);
        }
        let verified_identity = binding_policy.verify(assertion)?;
        Ok(OidcJwtVerificationReport {
            issuer: claims.issuer,
            subject: claims.subject,
            audiences,
            key_id,
            algorithm,
            signature_verified: true,
            expires_at: claims.exp,
            issued_at: claims.iat,
            roles,
            verified_identity,
        })
    }
}

fn jwk_for_kid<'a>(jwks: &'a JwkSet, kid: &str) -> Option<&'a Jwk> {
    jwks.keys
        .iter()
        .find(|jwk| jwk.common.key_id.as_deref() == Some(kid))
}

#[must_use]
pub fn algorithm_name(algorithm: &Algorithm) -> &'static str {
    match algorithm {
        Algorithm::HS256 => "HS256",
        Algorithm::HS384 => "HS384",
        Algorithm::HS512 => "HS512",
        Algorithm::ES256 => "ES256",
        Algorithm::ES384 => "ES384",
        Algorithm::RS256 => "RS256",
        Algorithm::RS384 => "RS384",
        Algorithm::RS512 => "RS512",
        Algorithm::PS256 => "PS256",
        Algorithm::PS384 => "PS384",
        Algorithm::PS512 => "PS512",
        Algorithm::EdDSA => "EdDSA",
    }
}

fn collect_roles_from_json(value: &Value, roles: &mut BTreeSet<Role>) {
    match value {
        Value::String(role) => {
            if let Some(parsed) = parse_role(role) {
                roles.insert(parsed);
            }
        }
        Value::Array(values) => values
            .iter()
            .for_each(|item| collect_roles_from_json(item, roles)),
        _ => {}
    }
}
