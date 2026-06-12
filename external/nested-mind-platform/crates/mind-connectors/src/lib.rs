use mind_core::{
    CloudSignedUrlReceipt, CloudSignedUrlRequest, ConnectorExecutionMode, LiveOidcRefreshReport,
    LiveOidcRefreshRequest, MindBackup, MindError, MindResult, OidcDiscoveryConfig,
    OidcDiscoveryDocument, ReplicationAck, ReplicationApplyReport, ReplicationDeliveryAttempt,
    ReplicationDeliveryReceipt, ReplicationEndpoint, ReplicationEnvelope, ReplicationRetryPolicy,
    SigningGatewayEndpoint, VendorSigningExecutionRequest, VendorSigningReceipt,
};
use reqwest::{Client, StatusCode};
use sha2::{Digest, Sha256};
use std::time::Duration;
use time::OffsetDateTime;
use tokio::time::sleep;

#[derive(Clone)]
pub struct HttpOidcDiscoveryClient {
    client: Client,
}

impl HttpOidcDiscoveryClient {
    #[must_use]
    pub fn new() -> Self {
        Self {
            client: Client::new(),
        }
    }

    pub async fn refresh(&self, config: &OidcDiscoveryConfig) -> MindResult<LiveOidcRefreshReport> {
        let request =
            LiveOidcRefreshRequest::from_config(config, ConnectorExecutionMode::LiveHttp)?;
        let document = self
            .client
            .get(&request.discovery_url)
            .send()
            .await
            .map_err(http_error)?
            .error_for_status()
            .map_err(http_error)?
            .json::<OidcDiscoveryDocument>()
            .await
            .map_err(http_error)?;
        document.validate_for(config)?;
        let jwks_json = self
            .client
            .get(&document.jwks_uri)
            .send()
            .await
            .map_err(http_error)?
            .error_for_status()
            .map_err(http_error)?
            .text()
            .await
            .map_err(http_error)?;
        LiveOidcRefreshReport::from_parts(request, config, &document, jwks_json)
    }
}

impl Default for HttpOidcDiscoveryClient {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Clone)]
pub struct HttpSigningGatewayClient {
    client: Client,
    endpoint: SigningGatewayEndpoint,
    bearer_token: Option<String>,
}

impl HttpSigningGatewayClient {
    pub fn new(endpoint: SigningGatewayEndpoint, bearer_token: Option<String>) -> MindResult<Self> {
        endpoint.validate()?;
        Ok(Self {
            client: Client::new(),
            endpoint,
            bearer_token,
        })
    }

    pub async fn execute(
        &self,
        request: &VendorSigningExecutionRequest,
    ) -> MindResult<VendorSigningReceipt> {
        if request.provider != self.endpoint.provider {
            return Err(MindError::Signing(
                "signing gateway provider mismatch".to_owned(),
            ));
        }
        let url = format!("{}/sign", self.endpoint.base_url.trim_end_matches('/'));
        let mut builder = self
            .client
            .post(url)
            .timeout(Duration::from_secs(self.endpoint.timeout_seconds))
            .json(request);
        if let Some(token) = &self.bearer_token {
            builder = builder.bearer_auth(token);
        }
        builder
            .send()
            .await
            .map_err(http_error)?
            .error_for_status()
            .map_err(http_error)?
            .json::<VendorSigningReceipt>()
            .await
            .map_err(http_error)
    }
}

#[derive(Clone)]
pub struct HttpSignedUrlObjectClient {
    client: Client,
}

impl HttpSignedUrlObjectClient {
    #[must_use]
    pub fn new() -> Self {
        Self {
            client: Client::new(),
        }
    }

    pub async fn put_backup(
        &self,
        request: &CloudSignedUrlRequest,
        backup: &MindBackup,
    ) -> MindResult<CloudSignedUrlReceipt> {
        request.validate()?;
        let body = serde_json::to_vec(backup)?;
        let observed_hash = hex::encode(Sha256::digest(&body));
        if observed_hash != request.expected_body_sha256_hex {
            return Err(MindError::ObjectBackupHashMismatch {
                expected: request.expected_body_sha256_hex.clone(),
                actual: observed_hash,
            });
        }
        let response = self
            .client
            .put(&request.url)
            .body(body)
            .send()
            .await
            .map_err(http_error)?;
        Ok(CloudSignedUrlReceipt::from_request(
            request,
            response.status().as_u16(),
            request.expected_body_sha256_hex.clone(),
        ))
    }
}

impl Default for HttpSignedUrlObjectClient {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Clone)]
pub struct HttpReplicationTransportClient {
    client: Client,
    policy: ReplicationRetryPolicy,
    bearer_token: Option<String>,
}

impl HttpReplicationTransportClient {
    pub fn new(policy: ReplicationRetryPolicy, bearer_token: Option<String>) -> MindResult<Self> {
        policy.validate()?;
        Ok(Self {
            client: Client::new(),
            policy,
            bearer_token,
        })
    }

    pub async fn deliver(
        &self,
        endpoint: &ReplicationEndpoint,
        push_path: &str,
        envelope: &ReplicationEnvelope,
    ) -> MindResult<ReplicationDeliveryReceipt> {
        envelope.verify()?;
        let url = format!("{}{}", endpoint.base_url.trim_end_matches('/'), push_path);
        let mut receipt =
            ReplicationDeliveryReceipt::new(endpoint.node_id.clone(), url.clone(), envelope);
        for attempt in 1..=self.policy.max_attempts {
            let mut builder = self.client.post(&url).json(&envelope.batch);
            if let Some(token) = &self.bearer_token {
                builder = builder.bearer_auth(token);
            }
            let response = builder.send().await;
            match response {
                Ok(response) => {
                    let status = response.status();
                    if status.is_success() {
                        let report = response
                            .json::<ReplicationApplyReport>()
                            .await
                            .map_err(http_error)?;
                        let ack = ReplicationAck {
                            batch_id: report.batch_id,
                            follower_id: endpoint.node_id.clone(),
                            accepted: report.accepted,
                            next_sequence: report.next_sequence,
                            last_record_hash: report.last_record_hash.clone(),
                            error: report.error.clone(),
                            acknowledged_at: OffsetDateTime::now_utc(),
                        };
                        let accepted = ack.accepted;
                        let attempt_record = ReplicationDeliveryAttempt {
                            attempt,
                            status_code: Some(status.as_u16()),
                            accepted,
                            error: ack.error.clone(),
                            attempted_at: OffsetDateTime::now_utc(),
                        };
                        receipt = receipt.with_attempt(attempt_record, Some(ack), &self.policy);
                        if accepted {
                            return Ok(receipt);
                        }
                    } else {
                        let attempt_record = ReplicationDeliveryAttempt {
                            attempt,
                            status_code: Some(status.as_u16()),
                            accepted: false,
                            error: Some(status_error(status)),
                            attempted_at: OffsetDateTime::now_utc(),
                        };
                        receipt = receipt.with_attempt(attempt_record, None, &self.policy);
                    }
                }
                Err(error) => {
                    let attempt_record = ReplicationDeliveryAttempt {
                        attempt,
                        status_code: None,
                        accepted: false,
                        error: Some(error.to_string()),
                        attempted_at: OffsetDateTime::now_utc(),
                    };
                    receipt = receipt.with_attempt(attempt_record, None, &self.policy);
                }
            }
            if attempt < self.policy.max_attempts {
                sleep(Duration::from_millis(
                    self.policy.delay_for_attempt_ms(attempt),
                ))
                .await;
            }
        }
        Ok(receipt)
    }
}

fn http_error(error: reqwest::Error) -> MindError {
    MindError::Store(error.to_string())
}
fn status_error(status: StatusCode) -> String {
    format!("HTTP status {}", status.as_u16())
}

#[derive(Clone, Debug, Default)]
pub struct ProviderExecutionDryRunClient;

impl ProviderExecutionDryRunClient {
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    #[must_use]
    pub fn complete_success(
        &self,
        request: &mind_core::ProviderExecutionRequest,
    ) -> mind_core::ProviderExecutionReceipt {
        mind_core::ProviderExecutionReceipt::succeeded(request, request.payload_hash.clone())
    }

    #[must_use]
    pub fn complete_failure(
        &self,
        request: &mind_core::ProviderExecutionRequest,
        error: impl Into<String>,
    ) -> mind_core::ProviderExecutionReceipt {
        mind_core::ProviderExecutionReceipt::failed(request, error)
    }
}

#[derive(Clone, Debug, Default)]
pub struct NativeProviderFeatureProbe;

impl NativeProviderFeatureProbe {
    #[must_use]
    pub fn registry(&self) -> mind_core::NativeProviderAdapterRegistry {
        mind_core::native_provider_adapter_registry()
    }

    pub fn evaluate(
        &self,
        request: &mind_core::ProviderExecutionRequest,
    ) -> mind_core::MindResult<mind_core::NativeProviderAdapterReport> {
        let registry = self.registry();
        mind_core::evaluate_native_provider_request(request, &registry)
    }
}

#[cfg(feature = "provider-aws-kms")]
pub type AwsKmsNativeAdapter = NativeProviderFeatureProbe;
#[cfg(feature = "provider-aws-s3")]
pub type AwsS3NativeAdapter = NativeProviderFeatureProbe;
#[cfg(feature = "provider-gcp-kms")]
pub type GcpKmsNativeAdapter = NativeProviderFeatureProbe;
#[cfg(feature = "provider-gcs")]
pub type GcsNativeAdapter = NativeProviderFeatureProbe;
#[cfg(feature = "provider-azure-key-vault")]
pub type AzureKeyVaultNativeAdapter = NativeProviderFeatureProbe;
#[cfg(feature = "provider-azure-blob")]
pub type AzureBlobNativeAdapter = NativeProviderFeatureProbe;
#[cfg(feature = "provider-vault")]
pub type VaultNativeAdapter = NativeProviderFeatureProbe;
#[cfg(feature = "provider-pkcs11")]
pub type Pkcs11NativeAdapter = NativeProviderFeatureProbe;

#[derive(Clone, Debug, Default)]
pub struct NativeProviderReceiptExecutor;

impl NativeProviderReceiptExecutor {
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    pub fn execute(
        &self,
        request: &mind_core::ProviderExecutionRequest,
        allow_dry_run: bool,
    ) -> mind_core::MindResult<mind_core::NativeProviderExecutionReceipt> {
        let registry = mind_core::native_provider_adapter_registry();
        mind_core::execute_native_provider_with_receipt(request, &registry, allow_dry_run)
    }
}

#[derive(Clone, Debug, Default)]
pub struct DistributedLeaseAdapterProbe;

impl DistributedLeaseAdapterProbe {
    #[must_use]
    pub fn registry(&self) -> mind_core::DistributedLeaseAdapterRegistry {
        mind_core::distributed_lease_adapter_registry()
    }

    pub fn evaluate(
        &self,
        boundary: &mind_core::DistributedLeaseServiceBoundary,
        job: &mind_core::ScheduledJob,
        worker_id: impl Into<String>,
        policy: &mind_core::SchedulerLeasePolicy,
    ) -> mind_core::MindResult<mind_core::DistributedLeaseAdapterReport> {
        let registry = self.registry();
        mind_core::evaluate_distributed_lease_adapter_claim(
            boundary, job, worker_id, policy, &registry,
        )
    }
}

#[derive(Clone)]
pub struct GitHubEvidenceHttpClient {
    client: Client,
    token: Option<String>,
    api_base: String,
}

impl GitHubEvidenceHttpClient {
    #[must_use]
    pub fn new(token: Option<String>) -> Self {
        Self {
            client: Client::new(),
            token,
            api_base: "https://api.github.com".to_owned(),
        }
    }

    #[must_use]
    pub fn with_api_base(mut self, api_base: impl Into<String>) -> Self {
        self.api_base = api_base.into();
        self
    }

    pub async fn collect_pull_request_checks(
        &self,
        repository: &str,
        pull_request_number: u64,
        required_check_names: std::collections::BTreeSet<String>,
    ) -> mind_core::MindResult<mind_core::GitHubReadinessEvidenceBundle> {
        let pr_url = format!(
            "{}/repos/{}/pulls/{}",
            self.api_base.trim_end_matches('/'),
            repository,
            pull_request_number
        );
        let pr_json = self.get_json(&pr_url).await?;
        let head_sha = pr_json
            .get("head")
            .and_then(|head| head.get("sha"))
            .and_then(serde_json::Value::as_str)
            .unwrap_or_default()
            .to_owned();
        let pull_request = mind_core::GitHubPullRequestEvidence::new(
            repository,
            pull_request_number,
            pr_json
                .get("title")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("untitled"),
            pr_json
                .get("user")
                .and_then(|user| user.get("login"))
                .and_then(serde_json::Value::as_str)
                .unwrap_or("unknown"),
            pr_json
                .get("base")
                .and_then(|base| base.get("ref"))
                .and_then(serde_json::Value::as_str)
                .unwrap_or("main"),
            pr_json
                .get("head")
                .and_then(|head| head.get("ref"))
                .and_then(serde_json::Value::as_str)
                .unwrap_or("unknown"),
            head_sha.clone(),
            pr_json
                .get("draft")
                .and_then(serde_json::Value::as_bool)
                .unwrap_or(false),
            pr_json
                .get("merged")
                .and_then(serde_json::Value::as_bool)
                .unwrap_or(false),
            pr_json
                .get("review_decision")
                .and_then(serde_json::Value::as_str)
                .map(ToOwned::to_owned),
            pr_json
                .get("labels")
                .and_then(serde_json::Value::as_array)
                .map(|labels| {
                    labels
                        .iter()
                        .filter_map(|label| {
                            label
                                .get("name")
                                .and_then(serde_json::Value::as_str)
                                .map(ToOwned::to_owned)
                        })
                        .collect::<Vec<_>>()
                })
                .unwrap_or_default(),
            mind_core::GitHubEvidenceSource::RestApi,
        )?;

        let checks_url = format!(
            "{}/repos/{}/commits/{}/check-runs",
            self.api_base.trim_end_matches('/'),
            repository,
            head_sha
        );
        let checks_json = self.get_json(&checks_url).await?;
        let check_runs = checks_json
            .get("check_runs")
            .and_then(serde_json::Value::as_array)
            .map(|runs| {
                runs.iter()
                    .filter_map(|run| {
                        mind_core::GitHubCheckRunEvidence::new(
                            repository,
                            head_sha.clone(),
                            run.get("name")
                                .and_then(serde_json::Value::as_str)
                                .unwrap_or("unnamed-check"),
                            run.get("status")
                                .and_then(serde_json::Value::as_str)
                                .unwrap_or("unknown"),
                            mind_core::GitHubCheckConclusion::from_github(
                                run.get("conclusion").and_then(serde_json::Value::as_str),
                            ),
                            run.get("app")
                                .and_then(|app| app.get("slug"))
                                .and_then(serde_json::Value::as_str)
                                .map(ToOwned::to_owned),
                            run.get("details_url")
                                .and_then(serde_json::Value::as_str)
                                .map(ToOwned::to_owned),
                            mind_core::GitHubEvidenceSource::RestApi,
                        )
                        .ok()
                    })
                    .collect::<Vec<_>>()
            })
            .unwrap_or_default();
        mind_core::collect_github_readiness_evidence(pull_request, check_runs, required_check_names)
    }

    async fn get_json(&self, url: &str) -> mind_core::MindResult<serde_json::Value> {
        let mut builder = self
            .client
            .get(url)
            .header("Accept", "application/vnd.github+json")
            .header("X-GitHub-Api-Version", "2022-11-28")
            .header("User-Agent", "nested-mind-platform");
        if let Some(token) = &self.token {
            builder = builder.bearer_auth(token);
        }
        builder
            .send()
            .await
            .map_err(http_error)?
            .error_for_status()
            .map_err(http_error)?
            .json::<serde_json::Value>()
            .await
            .map_err(http_error)
    }
}

#[derive(Clone)]
pub struct GitHubCheckRunWriterHttpClient {
    client: Client,
    token: String,
    api_base: String,
}

impl GitHubCheckRunWriterHttpClient {
    pub fn new(token: impl Into<String>) -> mind_core::MindResult<Self> {
        let token = token.into();
        if token.trim().is_empty() {
            return Err(MindError::Store(
                "GitHub check-run writer requires a GitHub App installation token".to_owned(),
            ));
        }
        Ok(Self {
            client: Client::new(),
            token,
            api_base: "https://api.github.com".to_owned(),
        })
    }

    #[must_use]
    pub fn with_api_base(mut self, api_base: impl Into<String>) -> Self {
        self.api_base = api_base.into();
        self
    }

    pub async fn write_check_run(
        &self,
        plan: &mind_core::GitHubCheckRunWritePlan,
    ) -> mind_core::MindResult<mind_core::GitHubCheckRunWriteReceipt> {
        plan.verify()?;
        if plan.mode != mind_core::GitHubCheckRunWriteMode::WriteApproved {
            return mind_core::record_github_check_run_write_receipt(
                plan,
                None,
                None,
                Some(plan.rest_payload.clone()),
            );
        }
        let url = format!(
            "{}{}",
            self.api_base.trim_end_matches('/'),
            plan.rest_endpoint
        );
        let response_json = self
            .client
            .post(url)
            .bearer_auth(&self.token)
            .header("Accept", "application/vnd.github+json")
            .header("X-GitHub-Api-Version", "2022-11-28")
            .header("User-Agent", "nested-mind-platform")
            .json(&plan.rest_payload)
            .send()
            .await
            .map_err(http_error)?
            .error_for_status()
            .map_err(http_error)?
            .json::<serde_json::Value>()
            .await
            .map_err(http_error)?;
        let check_run_id = response_json.get("id").and_then(serde_json::Value::as_u64);
        let html_url = response_json
            .get("html_url")
            .and_then(serde_json::Value::as_str)
            .map(ToOwned::to_owned);
        mind_core::record_github_check_run_write_receipt(
            plan,
            check_run_id,
            html_url,
            Some(response_json),
        )
    }
}

#[derive(Clone)]
pub struct GitHubBranchProtectionReconcileHttpClient {
    client: Client,
    token: String,
    api_base: String,
}

impl GitHubBranchProtectionReconcileHttpClient {
    pub fn new(token: impl Into<String>) -> mind_core::MindResult<Self> {
        let token = token.into();
        if token.trim().is_empty() {
            return Err(MindError::Store(
                "branch-protection reconciler requires a GitHub token".to_owned(),
            ));
        }
        Ok(Self {
            client: Client::new(),
            token,
            api_base: "https://api.github.com".to_owned(),
        })
    }

    #[must_use]
    pub fn with_api_base(mut self, api_base: impl Into<String>) -> Self {
        self.api_base = api_base.into();
        self
    }

    pub async fn reconcile(
        &self,
        plan: &mind_core::BranchProtectionReconcilePlan,
    ) -> mind_core::MindResult<mind_core::BranchProtectionReconcileReceipt> {
        plan.verify()?;
        if plan.mode != mind_core::BranchProtectionReconcileMode::ApplyApproved {
            return mind_core::record_branch_protection_reconcile_receipt(
                plan,
                Some(plan.rest_payload.clone()),
            );
        }
        let url = format!(
            "{}{}",
            self.api_base.trim_end_matches('/'),
            plan.rest_endpoint
        );
        let response_json = self
            .client
            .put(url)
            .bearer_auth(&self.token)
            .header("Accept", "application/vnd.github+json")
            .header("X-GitHub-Api-Version", "2022-11-28")
            .header("User-Agent", "nested-mind-platform")
            .json(&plan.rest_payload)
            .send()
            .await
            .map_err(http_error)?
            .error_for_status()
            .map_err(http_error)?
            .json::<serde_json::Value>()
            .await
            .map_err(http_error)?;
        mind_core::record_branch_protection_reconcile_receipt(plan, Some(response_json))
    }
}

#[derive(Clone, Debug, Default)]
pub struct KubernetesStagingChaosReceiptClient {
    pub allow_live_side_effects: bool,
}

impl KubernetesStagingChaosReceiptClient {
    #[must_use]
    pub fn new(allow_live_side_effects: bool) -> Self {
        Self {
            allow_live_side_effects,
        }
    }

    pub fn execute(
        &self,
        plan: &mind_core::KubernetesStagingChaosPlan,
    ) -> mind_core::MindResult<mind_core::KubernetesStagingChaosReceipt> {
        if plan.mode == mind_core::KubernetesChaosExecutionMode::LiveApproved
            && !self.allow_live_side_effects
        {
            return Err(MindError::Store(
                "live Kubernetes chaos execution disabled for this connector".to_owned(),
            ));
        }
        let response = serde_json::json!({
            "connector": "kubernetes_staging_chaos_receipt_client",
            "allow_live_side_effects": self.allow_live_side_effects,
            "command_count": plan.kubectl_commands.len(),
            "manifest_hashes": plan.manifests.iter().map(|manifest| manifest.manifest_hash.clone()).collect::<Vec<_>>(),
        });
        mind_core::record_kubernetes_staging_chaos_receipt(plan, Some(response))
    }
}

#[derive(Clone)]
pub struct GitHubAppInstallationTokenHttpClient {
    client: Client,
    app_jwt: String,
    api_base: String,
}

impl GitHubAppInstallationTokenHttpClient {
    pub fn new(app_jwt: impl Into<String>) -> mind_core::MindResult<Self> {
        let app_jwt = app_jwt.into();
        if app_jwt.trim().is_empty() {
            return Err(MindError::Store(
                "GitHub App installation token exchange requires an app JWT".to_owned(),
            ));
        }
        Ok(Self {
            client: Client::new(),
            app_jwt,
            api_base: "https://api.github.com".to_owned(),
        })
    }

    #[must_use]
    pub fn with_api_base(mut self, api_base: impl Into<String>) -> Self {
        self.api_base = api_base.into();
        self
    }

    pub async fn exchange_installation_token(
        &self,
        plan: &mind_core::GitHubAppInstallationTokenPlan,
    ) -> mind_core::MindResult<mind_core::GitHubAppInstallationTokenReceipt> {
        plan.verify()?;
        if plan.mode != mind_core::GitHubAppTokenMode::ExchangeApproved {
            return mind_core::record_github_app_installation_token_receipt(
                plan,
                None,
                Some(&plan.rest_payload),
            );
        }
        let url = format!(
            "{}{}",
            self.api_base.trim_end_matches('/'),
            plan.rest_endpoint
        );
        let response_json = self
            .client
            .post(url)
            .bearer_auth(&self.app_jwt)
            .header("Accept", "application/vnd.github+json")
            .header("X-GitHub-Api-Version", "2022-11-28")
            .header("User-Agent", "nested-mind-platform")
            .json(&plan.rest_payload)
            .send()
            .await
            .map_err(http_error)?
            .error_for_status()
            .map_err(http_error)?
            .json::<serde_json::Value>()
            .await
            .map_err(http_error)?;
        let token = response_json
            .get("token")
            .and_then(serde_json::Value::as_str)
            .ok_or_else(|| {
                MindError::Store(
                    "GitHub installation token response did not contain token".to_owned(),
                )
            })?;
        let token_fingerprint = hex::encode(Sha256::digest(token.as_bytes()));
        mind_core::record_github_app_installation_token_receipt(
            plan,
            Some(token_fingerprint),
            Some(&response_json),
        )
    }
}

#[derive(Clone)]
pub struct GitHubActionExecutionHttpClient {
    client: Client,
    installation_token: String,
    api_base: String,
}

impl GitHubActionExecutionHttpClient {
    pub fn new(installation_token: impl Into<String>) -> mind_core::MindResult<Self> {
        let installation_token = installation_token.into();
        if installation_token.trim().is_empty() {
            return Err(MindError::Store(
                "GitHub action execution requires an installation token".to_owned(),
            ));
        }
        Ok(Self {
            client: Client::new(),
            installation_token,
            api_base: "https://api.github.com".to_owned(),
        })
    }

    #[must_use]
    pub fn with_api_base(mut self, api_base: impl Into<String>) -> Self {
        self.api_base = api_base.into();
        self
    }

    pub async fn execute(
        &self,
        plan: &mind_core::GitHubActionExecutionPlan,
        token_receipt: &mind_core::GitHubAppInstallationTokenReceipt,
    ) -> mind_core::MindResult<mind_core::GitHubActionExecutionReceipt> {
        plan.verify()?;
        token_receipt.verify()?;
        if plan.mode != mind_core::GitHubActionExecutionMode::ExecuteApproved {
            return mind_core::record_github_action_execution_receipt(
                plan,
                token_receipt,
                None,
                Some(&plan.rest_payload),
            );
        }
        let url = format!(
            "{}{}",
            self.api_base.trim_end_matches('/'),
            plan.rest_endpoint
        );
        let builder = match plan.rest_method.as_str() {
            "PUT" => self.client.put(url),
            "PATCH" => self.client.patch(url),
            _ => self.client.post(url),
        };
        let response = builder
            .bearer_auth(&self.installation_token)
            .header("Accept", "application/vnd.github+json")
            .header("X-GitHub-Api-Version", "2022-11-28")
            .header("User-Agent", "nested-mind-platform")
            .json(&plan.rest_payload)
            .send()
            .await
            .map_err(http_error)?;
        let status = response.status().as_u16();
        let response_json = response
            .json::<serde_json::Value>()
            .await
            .unwrap_or_else(|_| serde_json::json!({ "status": status }));
        mind_core::record_github_action_execution_receipt(
            plan,
            token_receipt,
            Some(status),
            Some(&response_json),
        )
    }
}

#[derive(Clone, Debug, Default)]
pub struct KubernetesServerDryRunReceiptClient;

impl KubernetesServerDryRunReceiptClient {
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    pub fn execute(
        &self,
        plan: &mind_core::KubernetesStagingChaosPlan,
        context_name: impl Into<String>,
    ) -> mind_core::MindResult<(
        mind_core::KubernetesDryRunExecutionRequest,
        mind_core::KubernetesDryRunExecutionReceipt,
    )> {
        let request = mind_core::plan_kubernetes_server_dry_run_execution(
            plan,
            context_name,
            "nested-mind-chaos-runner",
        )?;
        let response = serde_json::json!({
            "dry_run": "server",
            "namespace": &plan.namespace,
            "manifest_count": plan.manifests.len(),
            "commands": &plan.kubectl_commands,
        });
        let receipt = mind_core::record_kubernetes_server_dry_run_receipt(
            &request,
            plan,
            Some(&response),
            Vec::new(),
        )?;
        Ok((request, receipt))
    }
}

#[derive(Clone, Debug, Default)]
pub struct WaiverNotificationDryRunClient;

impl WaiverNotificationDryRunClient {
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    pub fn deliver(
        &self,
        plan: &mind_core::WaiverNotificationPlan,
    ) -> mind_core::MindResult<mind_core::WaiverNotificationReceipt> {
        let response_hash = Some(hex::encode(Sha256::digest(
            serde_json::to_vec(plan)?.as_slice(),
        )));
        mind_core::record_waiver_notification_receipt(
            plan,
            plan.recipients.clone(),
            Some("dry-run-message".to_owned()),
            response_hash,
            Vec::new(),
        )
    }
}

#[derive(Clone, Debug, Default)]
pub struct SecretManagerDryRunClient;

impl SecretManagerDryRunClient {
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    pub fn resolve(
        &self,
        plan: &mind_core::SecretAccessPlan,
        material_fingerprint: impl Into<String>,
    ) -> mind_core::MindResult<mind_core::SecretAccessReceipt> {
        let mut metadata = std::collections::BTreeMap::new();
        metadata.insert("connector".to_owned(), "secret-manager-dry-run".to_owned());
        mind_core::record_secret_access_receipt(
            plan,
            Some(material_fingerprint.into()),
            plan.reference
                .version
                .clone()
                .or_else(|| Some("dry-run".to_owned())),
            metadata,
        )
    }
}

#[derive(Clone, Debug, Default)]
pub struct GitHubAppJwtDryRunSigner;

impl GitHubAppJwtDryRunSigner {
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    pub fn sign(
        &self,
        plan: &mind_core::GitHubAppJwtPlan,
        secret_receipt: &mind_core::SecretAccessReceipt,
    ) -> mind_core::MindResult<mind_core::GitHubAppJwtReceipt> {
        let fingerprint = hex::encode(Sha256::digest(
            serde_json::to_vec(&(plan, secret_receipt))?.as_slice(),
        ));
        mind_core::record_github_app_jwt_receipt(
            plan,
            secret_receipt,
            Some(fingerprint),
            Some(plan.claims_hash.clone()),
        )
    }
}

#[derive(Clone, Debug, Default)]
pub struct ConnectorWorkerDryRunClient;

impl ConnectorWorkerDryRunClient {
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    pub fn execute(
        &self,
        plan: &mind_core::ConnectorWorkerJobPlan,
    ) -> mind_core::MindResult<mind_core::ConnectorWorkerExecutionReceipt> {
        let response_hash = Some(hex::encode(Sha256::digest(
            serde_json::to_vec(plan)?.as_slice(),
        )));
        mind_core::record_connector_worker_execution_receipt(
            plan,
            Some(plan.plan_hash.clone()),
            response_hash,
            Vec::new(),
        )
    }
}

#[derive(Clone, Debug, Default)]
pub struct KubernetesAdmissionAuditDryRunClient;

impl KubernetesAdmissionAuditDryRunClient {
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    pub fn capture(
        &self,
        request: &mind_core::KubernetesAdmissionAuditRequest,
        dry_run_receipt: &mind_core::KubernetesDryRunExecutionReceipt,
    ) -> mind_core::MindResult<(
        mind_core::KubernetesAdmissionAuditReceipt,
        mind_core::KubernetesAdmissionAuditReport,
    )> {
        let mut annotations = std::collections::BTreeMap::new();
        annotations.insert("nested.mind/rehearsal".to_owned(), "true".to_owned());
        mind_core::record_kubernetes_admission_audit_receipt(
            request,
            dry_run_receipt,
            &mind_core::KubernetesAdmissionAuditPolicy::default(),
            Some("dry-run-audit-uid".to_owned()),
            annotations,
            Vec::new(),
            true,
        )
    }
}

#[derive(Clone, Debug, Default)]
pub struct WaiverNotificationAdapterDryRunClient;

impl WaiverNotificationAdapterDryRunClient {
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    pub fn deliver(
        &self,
        plan: &mind_core::WaiverNotificationAdapterPlan,
        notification_receipt: Option<&mind_core::WaiverNotificationReceipt>,
    ) -> mind_core::MindResult<mind_core::WaiverNotificationAdapterReceipt> {
        mind_core::record_waiver_notification_adapter_receipt(
            plan,
            notification_receipt,
            Some("dry-run-adapter-message".to_owned()),
            Some(plan.plan_hash.clone()),
            Vec::new(),
        )
    }
}

#[derive(Clone, Debug, Default)]
pub struct LiveSecretConnectorDryRunClient;

impl LiveSecretConnectorDryRunClient {
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    pub fn complete(
        &self,
        plan: &mind_core::LiveSecretConnectorPlan,
        access_receipt: &mind_core::SecretAccessReceipt,
    ) -> mind_core::MindResult<mind_core::LiveSecretConnectorReceipt> {
        mind_core::record_live_secret_connector_receipt(
            plan,
            access_receipt,
            Some("dry-run-secret-request".to_owned()),
            Some(plan.plan_hash.clone()),
            Vec::new(),
        )
    }
}

#[derive(Clone, Debug, Default)]
pub struct GitHubTokenExchangeDryRunClient;

impl GitHubTokenExchangeDryRunClient {
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    pub fn exchange(
        &self,
        plan: &mind_core::GitHubTokenExchangeWorkerPlan,
        token_receipt: &mind_core::GitHubAppInstallationTokenReceipt,
    ) -> mind_core::MindResult<mind_core::GitHubTokenExchangeWorkerReceipt> {
        mind_core::record_github_token_exchange_worker_receipt(plan, token_receipt)
    }
}

#[derive(Clone, Debug, Default)]
pub struct KubernetesAuditLogCollectorDryRunClient;

impl KubernetesAuditLogCollectorDryRunClient {
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    pub fn collect(
        &self,
        plan: &mind_core::KubernetesAuditLogCollectorPlan,
        admission_receipt: &mind_core::KubernetesAdmissionAuditReceipt,
    ) -> mind_core::MindResult<mind_core::KubernetesAuditLogCollectorReport> {
        mind_core::record_kubernetes_audit_log_collector_report(
            plan,
            admission_receipt,
            1,
            vec!["dry-run-audit-uid".to_owned()],
            Some("dry-run-watermark".to_owned()),
            Vec::new(),
        )
    }
}

#[derive(Clone, Debug, Default)]
pub struct NotificationDeliveryClientDryRun;

impl NotificationDeliveryClientDryRun {
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    pub fn send(
        &self,
        plan: &mind_core::NotificationDeliveryClientPlan,
        adapter_receipt: &mind_core::WaiverNotificationAdapterReceipt,
    ) -> mind_core::MindResult<mind_core::NotificationDeliveryClientReceipt> {
        mind_core::record_notification_delivery_client_receipt(
            plan,
            adapter_receipt,
            adapter_receipt
                .provider_message_id
                .clone()
                .or_else(|| Some("dry-run-delivery".to_owned())),
            adapter_receipt
                .provider_response_hash
                .clone()
                .or_else(|| Some(plan.plan_hash.clone())),
            Vec::new(),
        )
    }
}

#[derive(Clone, Debug, Default)]
pub struct ConnectorOrchestrationDryRunClient;

impl ConnectorOrchestrationDryRunClient {
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    pub fn evaluate(
        &self,
        plan: &mind_core::ConnectorOrchestrationPlan,
        artifacts: std::collections::BTreeMap<String, String>,
    ) -> mind_core::MindResult<mind_core::ConnectorOrchestrationReport> {
        mind_core::evaluate_connector_orchestration(plan, &[], &[], &[], &[], artifacts)
    }
}

#[derive(Clone, Debug, Default)]
pub struct KubernetesAuditSourceAdapterDryRunClient;

impl KubernetesAuditSourceAdapterDryRunClient {
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    pub fn collect(
        &self,
        plan: &mind_core::KubernetesAuditSourceAdapterPlan,
        collector_report: &mind_core::KubernetesAuditLogCollectorReport,
    ) -> mind_core::MindResult<mind_core::KubernetesAuditSourceAdapterReceipt> {
        mind_core::record_kubernetes_audit_source_adapter_receipt(
            plan,
            collector_report,
            Some(plan.plan_hash.clone()),
            Vec::new(),
        )
    }
}

#[derive(Clone, Debug, Default)]
pub struct NotificationProviderDeliveryDryRunClient;

impl NotificationProviderDeliveryDryRunClient {
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    pub fn deliver(
        &self,
        plan: &mind_core::NotificationProviderDeliveryPlan,
        client_receipt: &mind_core::NotificationDeliveryClientReceipt,
    ) -> mind_core::MindResult<mind_core::NotificationProviderDeliveryReceipt> {
        mind_core::record_notification_provider_delivery_receipt(
            plan,
            client_receipt,
            client_receipt
                .provider_message_id
                .clone()
                .or_else(|| Some("dry-run-provider-message".to_owned())),
            client_receipt
                .provider_response_hash
                .clone()
                .or_else(|| Some(plan.plan_hash.clone())),
            Vec::new(),
        )
    }
}
