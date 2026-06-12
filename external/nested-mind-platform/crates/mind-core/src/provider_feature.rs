use crate::{DirectProviderSdk, EventId, ProviderCommandKind};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ProviderSdkFeatureState {
    Disabled,
    DryRunOnly,
    ExternalGateway,
    NativeSdk,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProviderSdkFeature {
    pub sdk: DirectProviderSdk,
    pub cargo_feature: String,
    pub state: ProviderSdkFeatureState,
    #[serde(default)]
    pub supported_commands: Vec<ProviderCommandKind>,
    #[serde(default)]
    pub required_environment: Vec<String>,
    pub production_ready: bool,
}

impl ProviderSdkFeature {
    #[must_use]
    pub fn new(
        sdk: DirectProviderSdk,
        cargo_feature: impl Into<String>,
        state: ProviderSdkFeatureState,
        supported_commands: Vec<ProviderCommandKind>,
        required_environment: Vec<String>,
        production_ready: bool,
    ) -> Self {
        Self {
            sdk,
            cargo_feature: cargo_feature.into(),
            state,
            supported_commands,
            required_environment,
            production_ready,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProviderSdkFeatureMatrix {
    pub matrix_id: EventId,
    #[serde(default)]
    pub features: Vec<ProviderSdkFeature>,
    pub generated_at: OffsetDateTime,
}

impl ProviderSdkFeatureMatrix {
    #[must_use]
    pub fn conservative_default() -> Self {
        use ProviderCommandKind::{KmsSign, ObjectGet, ObjectPut, ReplicationPush};
        use ProviderSdkFeatureState::{Disabled, DryRunOnly, ExternalGateway};
        Self {
            matrix_id: EventId::new(),
            features: vec![
                ProviderSdkFeature::new(
                    DirectProviderSdk::AwsKms,
                    "provider-aws-kms",
                    Disabled,
                    vec![KmsSign],
                    vec!["AWS_REGION".to_owned(), "MIND_AWS_KMS_KEY_ID".to_owned()],
                    false,
                ),
                ProviderSdkFeature::new(
                    DirectProviderSdk::AwsS3,
                    "provider-aws-s3",
                    Disabled,
                    vec![ObjectPut, ObjectGet],
                    vec!["AWS_REGION".to_owned(), "MIND_BACKUP_BUCKET".to_owned()],
                    false,
                ),
                ProviderSdkFeature::new(
                    DirectProviderSdk::GcpCloudKms,
                    "provider-gcp-kms",
                    Disabled,
                    vec![KmsSign],
                    vec!["GOOGLE_APPLICATION_CREDENTIALS".to_owned()],
                    false,
                ),
                ProviderSdkFeature::new(
                    DirectProviderSdk::Gcs,
                    "provider-gcs",
                    Disabled,
                    vec![ObjectPut, ObjectGet],
                    vec!["GOOGLE_APPLICATION_CREDENTIALS".to_owned()],
                    false,
                ),
                ProviderSdkFeature::new(
                    DirectProviderSdk::AzureKeyVault,
                    "provider-azure-key-vault",
                    Disabled,
                    vec![KmsSign],
                    vec!["AZURE_CLIENT_ID".to_owned(), "AZURE_TENANT_ID".to_owned()],
                    false,
                ),
                ProviderSdkFeature::new(
                    DirectProviderSdk::AzureBlob,
                    "provider-azure-blob",
                    Disabled,
                    vec![ObjectPut, ObjectGet],
                    vec!["AZURE_STORAGE_ACCOUNT".to_owned()],
                    false,
                ),
                ProviderSdkFeature::new(
                    DirectProviderSdk::HashicorpVault,
                    "provider-vault",
                    Disabled,
                    vec![KmsSign],
                    vec!["VAULT_ADDR".to_owned()],
                    false,
                ),
                ProviderSdkFeature::new(
                    DirectProviderSdk::Pkcs11Hsm,
                    "provider-pkcs11",
                    Disabled,
                    vec![KmsSign],
                    vec!["PKCS11_MODULE_PATH".to_owned()],
                    false,
                ),
                ProviderSdkFeature::new(
                    DirectProviderSdk::HttpGateway,
                    "provider-http-gateway",
                    ExternalGateway,
                    vec![KmsSign, ObjectPut, ObjectGet, ReplicationPush],
                    vec!["MIND_PROVIDER_GATEWAY_URL".to_owned()],
                    false,
                ),
                ProviderSdkFeature::new(
                    DirectProviderSdk::LocalMirror,
                    "provider-local-mirror",
                    DryRunOnly,
                    vec![ObjectPut, ObjectGet],
                    vec!["MIND_CLOUD_OBJECT_MIRROR_DIR".to_owned()],
                    true,
                ),
            ],
            generated_at: OffsetDateTime::now_utc(),
        }
    }

    #[must_use]
    pub fn enabled_features(&self) -> Vec<&ProviderSdkFeature> {
        self.features
            .iter()
            .filter(|feature| feature.state != ProviderSdkFeatureState::Disabled)
            .collect()
    }

    #[must_use]
    pub fn native_features(&self) -> Vec<&ProviderSdkFeature> {
        self.features
            .iter()
            .filter(|feature| feature.state == ProviderSdkFeatureState::NativeSdk)
            .collect()
    }
}
