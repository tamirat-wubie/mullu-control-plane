use crate::{MindError, MindResult, Principal, Role};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum IdentityMethod {
    BootstrapToken,
    OidcJwt,
    MtlsClientCertificate,
    WorkloadIdentity,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum IdentityAssurance {
    Low,
    Medium,
    High,
    HardwareBound,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct OidcClaims {
    pub issuer: String,
    pub subject: String,
    pub audience: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub email: Option<String>,
    #[serde(default)]
    pub groups: Vec<String>,
    #[serde(default)]
    pub roles: BTreeSet<Role>,
    #[serde(default)]
    pub claims: BTreeMap<String, String>,
}

impl OidcClaims {
    #[must_use]
    pub fn new(
        issuer: impl Into<String>,
        subject: impl Into<String>,
        audience: impl Into<String>,
    ) -> Self {
        Self {
            issuer: issuer.into(),
            subject: subject.into(),
            audience: audience.into(),
            email: None,
            groups: Vec::new(),
            roles: BTreeSet::new(),
            claims: BTreeMap::new(),
        }
    }
    #[must_use]
    pub fn with_email(mut self, email: impl Into<String>) -> Self {
        self.email = Some(email.into());
        self
    }
    #[must_use]
    pub fn with_role(mut self, role: Role) -> Self {
        self.roles.insert(role);
        self
    }
    #[must_use]
    pub fn with_group(mut self, group: impl Into<String>) -> Self {
        self.groups.push(group.into());
        self
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct MtlsPeerIdentity {
    pub subject_dn: String,
    pub certificate_fingerprint_sha256: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub spiffe_id: Option<String>,
    #[serde(default)]
    pub dns_sans: Vec<String>,
}

impl MtlsPeerIdentity {
    #[must_use]
    pub fn new(
        subject_dn: impl Into<String>,
        certificate_fingerprint_sha256: impl Into<String>,
    ) -> Self {
        Self {
            subject_dn: subject_dn.into(),
            certificate_fingerprint_sha256: certificate_fingerprint_sha256.into(),
            spiffe_id: None,
            dns_sans: Vec::new(),
        }
    }
    #[must_use]
    pub fn with_spiffe_id(mut self, spiffe_id: impl Into<String>) -> Self {
        self.spiffe_id = Some(spiffe_id.into());
        self
    }
    #[must_use]
    pub fn with_dns_san(mut self, san: impl Into<String>) -> Self {
        self.dns_sans.push(san.into());
        self
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct IdentityProviderPolicy {
    #[serde(default)]
    pub trusted_oidc_issuers: BTreeSet<String>,
    #[serde(default)]
    pub trusted_oidc_audiences: BTreeSet<String>,
    #[serde(default)]
    pub trusted_mtls_fingerprints: BTreeSet<String>,
    #[serde(default)]
    pub trusted_spiffe_prefixes: BTreeSet<String>,
    pub default_oidc_role: Role,
    pub default_mtls_role: Role,
    #[serde(default)]
    pub subject_role_overrides: BTreeMap<String, BTreeSet<Role>>,
}

impl Default for IdentityProviderPolicy {
    fn default() -> Self {
        Self::production_default()
    }
}

impl IdentityProviderPolicy {
    #[must_use]
    pub fn production_default() -> Self {
        Self {
            trusted_oidc_issuers: BTreeSet::new(),
            trusted_oidc_audiences: BTreeSet::new(),
            trusted_mtls_fingerprints: BTreeSet::new(),
            trusted_spiffe_prefixes: BTreeSet::new(),
            default_oidc_role: Role::Observer,
            default_mtls_role: Role::Maintainer,
            subject_role_overrides: BTreeMap::new(),
        }
    }
    #[must_use]
    pub fn trust_oidc_issuer(mut self, issuer: impl Into<String>) -> Self {
        self.trusted_oidc_issuers.insert(issuer.into());
        self
    }
    #[must_use]
    pub fn trust_oidc_audience(mut self, audience: impl Into<String>) -> Self {
        self.trusted_oidc_audiences.insert(audience.into());
        self
    }
    #[must_use]
    pub fn trust_mtls_fingerprint(mut self, fingerprint: impl Into<String>) -> Self {
        let value = fingerprint.into();
        self.trusted_mtls_fingerprints
            .insert(normalize_fingerprint(&value));
        self
    }
    #[must_use]
    pub fn trust_spiffe_prefix(mut self, prefix: impl Into<String>) -> Self {
        self.trusted_spiffe_prefixes.insert(prefix.into());
        self
    }
    #[must_use]
    pub fn with_subject_roles(mut self, subject: impl Into<String>, roles: BTreeSet<Role>) -> Self {
        self.subject_role_overrides.insert(subject.into(), roles);
        self
    }

    pub fn map_oidc_claims(&self, claims: OidcClaims) -> MindResult<ExternalIdentityProof> {
        if self.trusted_oidc_issuers.is_empty() {
            return Err(MindError::IdentityRejected {
                reason: "OIDC issuer trust set is empty".to_owned(),
            });
        }
        if !self.trusted_oidc_issuers.contains(&claims.issuer) {
            return Err(MindError::IdentityRejected {
                reason: format!("OIDC issuer `{}` is not trusted", claims.issuer),
            });
        }
        if !self.trusted_oidc_audiences.is_empty()
            && !self.trusted_oidc_audiences.contains(&claims.audience)
        {
            return Err(MindError::IdentityRejected {
                reason: format!("OIDC audience `{}` is not trusted", claims.audience),
            });
        }
        let subject_key = format!("oidc:{}:{}", claims.issuer, claims.subject);
        let roles =
            self.roles_for_subject(&subject_key, &claims.roles, self.default_oidc_role.clone());
        let mut principal = Principal::new(subject_key.clone());
        principal.roles = roles;
        principal
            .attributes
            .insert("identity_method".to_owned(), "oidc_jwt".to_owned());
        principal
            .attributes
            .insert("issuer".to_owned(), claims.issuer.clone());
        principal
            .attributes
            .insert("subject".to_owned(), claims.subject.clone());
        principal
            .attributes
            .insert("audience".to_owned(), claims.audience.clone());
        if let Some(email) = claims.email.clone() {
            principal.attributes.insert("email".to_owned(), email);
        }
        if !claims.groups.is_empty() {
            principal
                .attributes
                .insert("groups".to_owned(), claims.groups.join(","));
        }
        Ok(ExternalIdentityProof {
            method: IdentityMethod::OidcJwt,
            assurance: IdentityAssurance::High,
            issuer: Some(claims.issuer),
            subject: claims.subject,
            audience: Some(claims.audience),
            principal,
        })
    }

    pub fn map_mtls_peer(&self, peer: MtlsPeerIdentity) -> MindResult<ExternalIdentityProof> {
        let fingerprint = normalize_fingerprint(&peer.certificate_fingerprint_sha256);
        let fingerprint_trusted = self.trusted_mtls_fingerprints.contains(&fingerprint);
        let spiffe_trusted = peer.spiffe_id.as_ref().is_some_and(|spiffe| {
            self.trusted_spiffe_prefixes
                .iter()
                .any(|prefix| spiffe.starts_with(prefix))
        });
        if self.trusted_mtls_fingerprints.is_empty() && self.trusted_spiffe_prefixes.is_empty() {
            return Err(MindError::IdentityRejected {
                reason: "mTLS trust anchors are not configured".to_owned(),
            });
        }
        if !fingerprint_trusted && !spiffe_trusted {
            return Err(MindError::IdentityRejected {
                reason: "mTLS peer is not trusted by fingerprint or SPIFFE prefix".to_owned(),
            });
        }
        let subject = peer
            .spiffe_id
            .clone()
            .unwrap_or_else(|| peer.subject_dn.clone());
        let subject_key = format!("mtls:{subject}");
        let empty_roles = BTreeSet::new();
        let roles =
            self.roles_for_subject(&subject_key, &empty_roles, self.default_mtls_role.clone());
        let mut principal = Principal::new(subject_key.clone());
        principal.roles = roles;
        principal.attributes.insert(
            "identity_method".to_owned(),
            "mtls_client_certificate".to_owned(),
        );
        principal
            .attributes
            .insert("subject_dn".to_owned(), peer.subject_dn.clone());
        principal
            .attributes
            .insert("certificate_fingerprint_sha256".to_owned(), fingerprint);
        if let Some(spiffe) = peer.spiffe_id.clone() {
            principal.attributes.insert("spiffe_id".to_owned(), spiffe);
        }
        if !peer.dns_sans.is_empty() {
            principal
                .attributes
                .insert("dns_sans".to_owned(), peer.dns_sans.join(","));
        }
        Ok(ExternalIdentityProof {
            method: IdentityMethod::MtlsClientCertificate,
            assurance: IdentityAssurance::HardwareBound,
            issuer: None,
            subject,
            audience: None,
            principal,
        })
    }

    fn roles_for_subject(
        &self,
        subject_key: &str,
        explicit_roles: &BTreeSet<Role>,
        fallback: Role,
    ) -> BTreeSet<Role> {
        if let Some(roles) = self.subject_role_overrides.get(subject_key) {
            return roles.clone();
        }
        if !explicit_roles.is_empty() {
            return explicit_roles.clone();
        }
        BTreeSet::from([fallback])
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ExternalIdentityProof {
    pub method: IdentityMethod,
    pub assurance: IdentityAssurance,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub issuer: Option<String>,
    pub subject: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub audience: Option<String>,
    pub principal: Principal,
}

#[must_use]
pub fn parse_role(value: &str) -> Option<Role> {
    match value.trim().to_ascii_lowercase().as_str() {
        "observer" => Some(Role::Observer),
        "operator" => Some(Role::Operator),
        "auditor" => Some(Role::Auditor),
        "maintainer" => Some(Role::Maintainer),
        "admin" => Some(Role::Admin),
        _ => None,
    }
}

#[must_use]
pub fn normalize_fingerprint(value: &str) -> String {
    value
        .chars()
        .filter(|ch| !matches!(ch, ':' | ' ' | '-'))
        .flat_map(char::to_lowercase)
        .collect()
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum IdentityEvidenceKind {
    BootstrapBearer,
    OidcJwt,
    MtlsClientCertificate,
    WorkloadIdentity,
    GatewayAssertion,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct IdentityAssertion {
    pub kind: IdentityEvidenceKind,
    pub subject: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub issuer: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub audience: Option<String>,
    #[serde(default)]
    pub claims: BTreeMap<String, String>,
}

impl IdentityAssertion {
    #[must_use]
    pub fn new(kind: IdentityEvidenceKind, subject: impl Into<String>) -> Self {
        Self {
            kind,
            subject: subject.into(),
            issuer: None,
            audience: None,
            claims: BTreeMap::new(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct IdentityGatewayPolicy {
    pub trust_gateway_headers: bool,
    #[serde(default)]
    pub allowed_issuers: BTreeSet<String>,
    #[serde(default)]
    pub allowed_audiences: BTreeSet<String>,
    pub default_role: Role,
}

impl Default for IdentityGatewayPolicy {
    fn default() -> Self {
        Self {
            trust_gateway_headers: false,
            allowed_issuers: BTreeSet::new(),
            allowed_audiences: BTreeSet::new(),
            default_role: Role::Observer,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum IdentitySource {
    BootstrapToken,
    OidcJwt,
    MtlsClientCertificate,
    TrustedProxyHeader,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ExternalIdentityAssertion {
    pub source: IdentitySource,
    pub subject: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub issuer: Option<String>,
    #[serde(default)]
    pub audiences: BTreeSet<String>,
    #[serde(default)]
    pub roles: BTreeSet<Role>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub client_certificate_sha256: Option<String>,
    #[serde(default)]
    pub attributes: BTreeMap<String, String>,
}

impl ExternalIdentityAssertion {
    #[must_use]
    pub fn new(source: IdentitySource, subject: impl Into<String>) -> Self {
        Self {
            source,
            subject: subject.into(),
            issuer: None,
            audiences: BTreeSet::new(),
            roles: BTreeSet::new(),
            client_certificate_sha256: None,
            attributes: BTreeMap::new(),
        }
    }

    #[must_use]
    pub fn with_issuer(mut self, issuer: impl Into<String>) -> Self {
        self.issuer = Some(issuer.into());
        self
    }

    #[must_use]
    pub fn with_audience(mut self, audience: impl Into<String>) -> Self {
        self.audiences.insert(audience.into());
        self
    }

    #[must_use]
    pub fn with_role(mut self, role: Role) -> Self {
        self.roles.insert(role);
        self
    }

    #[must_use]
    pub fn with_client_certificate_sha256(mut self, digest: impl Into<String>) -> Self {
        self.client_certificate_sha256 = Some(normalize_fingerprint(&digest.into()));
        self
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct VerifiedIdentity {
    pub subject: String,
    pub source: IdentitySource,
    #[serde(default)]
    pub roles: BTreeSet<Role>,
    #[serde(default)]
    pub attributes: BTreeMap<String, String>,
}

impl VerifiedIdentity {
    #[must_use]
    pub fn into_principal(self) -> Principal {
        let mut principal = Principal::new(self.subject);
        principal.roles = self.roles;
        principal.attributes = self.attributes;
        principal
            .attributes
            .insert("identity.source".to_owned(), format!("{:?}", self.source));
        principal
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct IdentityBindingPolicy {
    #[serde(default)]
    pub allowed_issuers: BTreeSet<String>,
    #[serde(default)]
    pub required_audiences: BTreeSet<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub required_client_certificate_sha256: Option<String>,
    pub allow_trusted_proxy_headers: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub default_role: Option<Role>,
}

impl Default for IdentityBindingPolicy {
    fn default() -> Self {
        Self {
            allowed_issuers: BTreeSet::new(),
            required_audiences: BTreeSet::new(),
            required_client_certificate_sha256: None,
            allow_trusted_proxy_headers: true,
            default_role: Some(Role::Observer),
        }
    }
}

impl IdentityBindingPolicy {
    #[must_use]
    pub fn allow_issuer(mut self, issuer: impl Into<String>) -> Self {
        self.allowed_issuers.insert(issuer.into());
        self
    }

    #[must_use]
    pub fn require_audience(mut self, audience: impl Into<String>) -> Self {
        self.required_audiences.insert(audience.into());
        self
    }

    #[must_use]
    pub fn require_client_certificate_sha256(mut self, digest: impl Into<String>) -> Self {
        self.required_client_certificate_sha256 = Some(normalize_fingerprint(&digest.into()));
        self
    }

    #[must_use]
    pub fn with_default_role(mut self, role: Option<Role>) -> Self {
        self.default_role = role;
        self
    }

    pub fn verify(&self, assertion: ExternalIdentityAssertion) -> MindResult<VerifiedIdentity> {
        if assertion.subject.trim().is_empty() {
            return Err(MindError::IdentityEvidenceRejected {
                reason: "identity subject is empty".to_owned(),
            });
        }
        if matches!(assertion.source, IdentitySource::TrustedProxyHeader)
            && !self.allow_trusted_proxy_headers
        {
            return Err(MindError::IdentityRejected {
                reason: "trusted proxy identity headers are disabled".to_owned(),
            });
        }
        if !self.allowed_issuers.is_empty() {
            let Some(issuer) = assertion.issuer.as_ref() else {
                return Err(MindError::IdentityEvidenceRejected {
                    reason: "issuer is required".to_owned(),
                });
            };
            if !self.allowed_issuers.contains(issuer) {
                return Err(MindError::IdentityRejected {
                    reason: format!("issuer `{issuer}` is not allowed"),
                });
            }
        }
        if !self.required_audiences.is_empty()
            && self.required_audiences.is_disjoint(&assertion.audiences)
        {
            return Err(MindError::IdentityRejected {
                reason: "required audience is missing".to_owned(),
            });
        }
        if let Some(required_digest) = &self.required_client_certificate_sha256 {
            match &assertion.client_certificate_sha256 {
                Some(actual)
                    if normalize_fingerprint(actual) == normalize_fingerprint(required_digest) => {}
                _ => {
                    return Err(MindError::IdentityRejected {
                        reason: "required client certificate digest is missing or mismatched"
                            .to_owned(),
                    })
                }
            }
        }
        let mut roles = assertion.roles;
        if roles.is_empty() {
            if let Some(default_role) = self.default_role.clone() {
                roles.insert(default_role);
            }
        }
        let mut attributes = assertion.attributes;
        if let Some(issuer) = assertion.issuer {
            attributes.insert("identity.issuer".to_owned(), issuer);
        }
        if !assertion.audiences.is_empty() {
            attributes.insert(
                "identity.audience".to_owned(),
                assertion
                    .audiences
                    .into_iter()
                    .collect::<Vec<_>>()
                    .join(","),
            );
        }
        if let Some(digest) = assertion.client_certificate_sha256 {
            attributes.insert(
                "identity.client_cert_sha256".to_owned(),
                normalize_fingerprint(&digest),
            );
        }
        Ok(VerifiedIdentity {
            subject: assertion.subject,
            source: assertion.source,
            roles,
            attributes,
        })
    }
}

#[must_use]
pub fn parse_roles_csv(value: &str) -> BTreeSet<Role> {
    value.split(',').filter_map(parse_role).collect()
}
