//! Purpose: authentication and OIDC runtime boundary for the Nested Mind API.
//! Governance scope: token authentication, trusted identity headers, and OIDC verification state.
//! Dependencies: API-local environment helpers, request header helpers, and mind-core identity contracts.
//! Invariants: authentication decisions remain explicit; identity binding policy is validated before principal projection.

use super::*;

#[derive(Clone)]
pub(super) struct AuthConfig {
    pub(super) tokens: Arc<BTreeMap<String, Principal>>,
    pub(super) trusted_identity_headers: bool,
    pub(super) identity_policy: IdentityBindingPolicy,
    pub(super) oidc_verifier: Option<Arc<RuntimeOidcVerifier>>,
}

#[derive(Clone)]
pub(super) struct RuntimeOidcVerifier {
    pub(super) config: OidcJwksVerifierConfig,
    pub(super) jwks_json: Arc<String>,
}

impl RuntimeOidcVerifier {
    pub(super) fn verify_with_report(
        &self,
        jwt: &str,
        binding_policy: &IdentityBindingPolicy,
    ) -> Result<OidcJwtVerificationReport, MindError> {
        OidcJwksVerifier::from_jwks_json(self.config.clone(), self.jwks_json.as_str())?
            .verify_with_report(jwt, binding_policy)
    }
}

#[derive(Clone)]
pub(super) struct RuntimeOidcDiscovery {
    pub(super) config: OidcDiscoveryConfig,
    pub(super) document: OidcDiscoveryDocument,
    pub(super) jwks_json: Arc<String>,
}

impl RuntimeOidcDiscovery {
    pub(super) fn cache_entry(&self) -> Result<OidcJwksCacheEntry, MindError> {
        OidcJwksCacheEntry::from_jwks_json(
            self.config.issuer.clone(),
            self.document.jwks_uri.clone(),
            self.jwks_json.as_str(),
            Some(self.config.refresh_ttl_seconds),
        )
    }

    pub(super) fn refresh_report(&self) -> Result<OidcDiscoveryRefreshReport, MindError> {
        let cache = self.cache_entry()?;
        OidcDiscoveryRefreshReport::refreshed(&self.config, &self.document, &cache)
    }
}

impl AuthConfig {
    pub(super) fn from_env() -> Result<Self, MindError> {
        let mut tokens = BTreeMap::new();
        insert_token_principal(
            &mut tokens,
            "MIND_BOOTSTRAP_TOKEN",
            "MIND_BOOTSTRAP_PRINCIPAL",
            "bootstrap-admin",
            Role::Admin,
        );
        insert_token_principal(
            &mut tokens,
            "MIND_OPERATOR_TOKEN",
            "MIND_OPERATOR_PRINCIPAL",
            "operator",
            Role::Operator,
        );
        insert_token_principal(
            &mut tokens,
            "MIND_AUDITOR_TOKEN",
            "MIND_AUDITOR_PRINCIPAL",
            "auditor",
            Role::Auditor,
        );
        insert_token_principal(
            &mut tokens,
            "MIND_MAINTAINER_TOKEN",
            "MIND_MAINTAINER_PRINCIPAL",
            "maintainer",
            Role::Maintainer,
        );
        Ok(Self {
            tokens: Arc::new(tokens),
            trusted_identity_headers: matches!(env::var("MIND_TRUSTED_IDENTITY_HEADERS"), Ok(value) if is_truthy(&value)),
            identity_policy: identity_policy_from_env(),
            oidc_verifier: oidc_verifier_from_env()?.map(Arc::new),
        })
    }

    pub(super) fn authenticate(&self, headers: &HeaderMap) -> Result<Option<Principal>, MindError> {
        if let Some(token) = bearer_token(headers) {
            if let Some(principal) = self.tokens.get(token).cloned() {
                return Ok(Some(principal));
            }
            if let Some(verifier) = &self.oidc_verifier {
                return Ok(Some(
                    verifier
                        .verify_with_report(token, &self.identity_policy)?
                        .verified_identity
                        .into_principal(),
                ));
            }
            return Err(MindError::InvalidCredentials);
        }
        if !self.trusted_identity_headers {
            return Ok(None);
        }
        let Some(subject) = header_str(headers, "x-mind-subject") else {
            return Ok(None);
        };
        let source =
            match header_str(headers, "x-mind-identity-source").unwrap_or("trusted_proxy_header") {
                "oidc" | "oidc_jwt" => IdentitySource::OidcJwt,
                "mtls" | "mtls_client_certificate" => IdentitySource::MtlsClientCertificate,
                "bootstrap" | "bootstrap_token" => IdentitySource::BootstrapToken,
                _ => IdentitySource::TrustedProxyHeader,
            };
        let mut assertion = ExternalIdentityAssertion::new(source, subject);
        if let Some(issuer) = header_str(headers, "x-mind-issuer") {
            assertion = assertion.with_issuer(issuer);
        }
        for audience in header_csv(headers, "x-mind-audience") {
            assertion.audiences.insert(audience);
        }
        for role in header_csv(headers, "x-mind-roles")
            .into_iter()
            .filter_map(|role| mind_core::parse_role(&role))
        {
            assertion.roles.insert(role);
        }
        if let Some(digest) = header_str(headers, "x-mind-client-cert-sha256") {
            assertion = assertion.with_client_certificate_sha256(digest);
        }
        Ok(Some(
            self.identity_policy.verify(assertion)?.into_principal(),
        ))
    }
}
