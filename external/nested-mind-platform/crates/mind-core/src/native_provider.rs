use crate::{
    DirectProviderSdk, EventId, MindError, MindResult, ProviderCommandKind,
    ProviderExecutionRequest, ProviderSdkFeature, ProviderSdkFeatureMatrix,
    ProviderSdkFeatureState, ProviderSdkInvocation,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum NativeProviderExecutionMode {
    Disabled,
    DryRunOnly,
    ExternalGateway,
    NativeFeature,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct NativeProviderAdapterCapability {
    pub sdk: DirectProviderSdk,
    pub cargo_feature: String,
    pub compiled: bool,
    pub mode: NativeProviderExecutionMode,
    #[serde(default)]
    pub supported_commands: Vec<ProviderCommandKind>,
    #[serde(default)]
    pub required_environment: Vec<String>,
    #[serde(default)]
    pub reasons: Vec<String>,
    pub production_ready: bool,
}

impl NativeProviderAdapterCapability {
    #[must_use]
    pub fn from_feature(feature: &ProviderSdkFeature, compiled: bool) -> Self {
        let mode = match feature.state {
            ProviderSdkFeatureState::Disabled if compiled => {
                NativeProviderExecutionMode::NativeFeature
            }
            ProviderSdkFeatureState::Disabled => NativeProviderExecutionMode::Disabled,
            ProviderSdkFeatureState::DryRunOnly => NativeProviderExecutionMode::DryRunOnly,
            ProviderSdkFeatureState::ExternalGateway => {
                NativeProviderExecutionMode::ExternalGateway
            }
            ProviderSdkFeatureState::NativeSdk => NativeProviderExecutionMode::NativeFeature,
        };
        let mut reasons = Vec::new();
        if compiled {
            reasons.push(format!(
                "cargo feature `{}` is enabled",
                feature.cargo_feature
            ));
        } else if feature.state == ProviderSdkFeatureState::Disabled {
            reasons.push(format!(
                "cargo feature `{}` is not enabled",
                feature.cargo_feature
            ));
        }
        if !feature.production_ready {
            reasons.push(
                "provider receipt verification must be reviewed before production use".to_owned(),
            );
        }
        Self {
            sdk: feature.sdk,
            cargo_feature: feature.cargo_feature.clone(),
            compiled,
            mode,
            supported_commands: feature.supported_commands.clone(),
            required_environment: feature.required_environment.clone(),
            reasons,
            production_ready: feature.production_ready && compiled,
        }
    }

    #[must_use]
    pub fn supports(&self, command: ProviderCommandKind) -> bool {
        self.supported_commands.contains(&command)
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct NativeProviderAdapterRegistry {
    pub registry_id: EventId,
    #[serde(default)]
    pub capabilities: Vec<NativeProviderAdapterCapability>,
    pub generated_at: OffsetDateTime,
}

impl NativeProviderAdapterRegistry {
    #[must_use]
    pub fn from_feature_matrix(matrix: &ProviderSdkFeatureMatrix) -> Self {
        let capabilities = matrix
            .features
            .iter()
            .map(|feature| {
                NativeProviderAdapterCapability::from_feature(
                    feature,
                    feature_compiled(&feature.cargo_feature),
                )
            })
            .collect();
        Self {
            registry_id: EventId::new(),
            capabilities,
            generated_at: OffsetDateTime::now_utc(),
        }
    }

    #[must_use]
    pub fn conservative_default() -> Self {
        Self::from_feature_matrix(&ProviderSdkFeatureMatrix::conservative_default())
    }

    #[must_use]
    pub fn capability_for(
        &self,
        sdk: DirectProviderSdk,
    ) -> Option<&NativeProviderAdapterCapability> {
        self.capabilities
            .iter()
            .find(|capability| capability.sdk == sdk)
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct NativeProviderAdapterReport {
    pub report_id: EventId,
    pub invocation_id: EventId,
    pub sdk: DirectProviderSdk,
    pub command_kind: ProviderCommandKind,
    pub target: String,
    pub mode: NativeProviderExecutionMode,
    pub accepted: bool,
    pub request_hash: String,
    #[serde(default)]
    pub reasons: Vec<String>,
    pub evaluated_at: OffsetDateTime,
}

pub fn native_provider_adapter_registry() -> NativeProviderAdapterRegistry {
    NativeProviderAdapterRegistry::conservative_default()
}

pub fn evaluate_native_provider_request(
    request: &ProviderExecutionRequest,
    registry: &NativeProviderAdapterRegistry,
) -> MindResult<NativeProviderAdapterReport> {
    let invocation = ProviderSdkInvocation::from_execution_request(request)?;
    let Some(capability) = registry.capability_for(invocation.sdk) else {
        return Err(MindError::Store(
            "native provider capability is missing".to_owned(),
        ));
    };
    let mut reasons = capability.reasons.clone();
    let accepted = capability.supports(invocation.command_kind)
        && capability.mode != NativeProviderExecutionMode::Disabled;
    if !capability.supports(invocation.command_kind) {
        reasons.push("provider does not support requested command".to_owned());
    }
    if capability.mode == NativeProviderExecutionMode::Disabled {
        reasons.push("provider adapter is disabled".to_owned());
    }
    Ok(NativeProviderAdapterReport {
        report_id: EventId::new(),
        invocation_id: invocation.invocation_id,
        sdk: invocation.sdk,
        command_kind: invocation.command_kind,
        target: invocation.target,
        mode: capability.mode,
        accepted,
        request_hash: invocation.request_hash,
        reasons,
        evaluated_at: OffsetDateTime::now_utc(),
    })
}

fn feature_compiled(feature: &str) -> bool {
    match feature {
        "provider-aws-kms" => cfg!(feature = "provider-aws-kms"),
        "provider-aws-s3" => cfg!(feature = "provider-aws-s3"),
        "provider-gcp-kms" => cfg!(feature = "provider-gcp-kms"),
        "provider-gcs" => cfg!(feature = "provider-gcs"),
        "provider-azure-key-vault" => cfg!(feature = "provider-azure-key-vault"),
        "provider-azure-blob" => cfg!(feature = "provider-azure-blob"),
        "provider-vault" => cfg!(feature = "provider-vault"),
        "provider-pkcs11" => cfg!(feature = "provider-pkcs11"),
        "provider-http-gateway" => cfg!(feature = "provider-http-gateway"),
        "provider-local-mirror" => cfg!(feature = "provider-local-mirror"),
        _ => false,
    }
}
