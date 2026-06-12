use crate::{
    execute_native_provider_with_receipt, hash_serializable, DirectProviderSdk, EventId, MindError,
    MindResult, NativeProviderAdapterRegistry, NativeProviderExecutionMode,
    NativeProviderExecutionReceipt, NativeProviderExecutionStatus, ProviderExecutionRequest,
    ProviderSdkInvocation,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ProviderSdkExecutionPolicy {
    PlanOnly,
    DryRunAllowed,
    NativeFeatureRequired,
    ExternalReceiptRequired,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProviderSpecificSdkExecutionPlan {
    pub plan_id: EventId,
    pub execution_id: EventId,
    pub sdk: DirectProviderSdk,
    pub target: String,
    pub policy: ProviderSdkExecutionPolicy,
    pub invocation: ProviderSdkInvocation,
    #[serde(default)]
    pub required_environment: Vec<String>,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProviderSdkExecutionReport {
    pub report_id: EventId,
    pub plan: ProviderSpecificSdkExecutionPlan,
    pub native_receipt: NativeProviderExecutionReceipt,
    pub accepted: bool,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
    #[serde(default)]
    pub reasons: Vec<String>,
    pub executed_at: OffsetDateTime,
}

impl ProviderSdkExecutionReport {
    pub fn verify_for(&self, request: &ProviderExecutionRequest) -> MindResult<()> {
        if self.plan.execution_id != request.execution_id {
            return Err(MindError::Store(
                "provider SDK execution report id mismatch".to_owned(),
            ));
        }
        self.native_receipt.verify_for(request)?;
        if self.accepted && self.native_receipt.status != NativeProviderExecutionStatus::Executed {
            return Err(MindError::Store(
                "accepted provider SDK execution was not executed".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn plan_provider_sdk_execution(
    request: &ProviderExecutionRequest,
    registry: &NativeProviderAdapterRegistry,
    policy: ProviderSdkExecutionPolicy,
) -> MindResult<ProviderSpecificSdkExecutionPlan> {
    let invocation = ProviderSdkInvocation::from_execution_request(request)?;
    let capability = registry.capability_for(invocation.sdk);
    let required_environment = capability
        .map(|capability| capability.required_environment.clone())
        .unwrap_or_default();
    let plan_hash = hash_serializable(&(
        request.execution_id,
        invocation.sdk,
        invocation.command_kind,
        &invocation.target,
        &invocation.request_hash,
        policy,
        &required_environment,
    ))?;
    Ok(ProviderSpecificSdkExecutionPlan {
        plan_id: EventId::new(),
        execution_id: request.execution_id,
        sdk: invocation.sdk,
        target: invocation.target.clone(),
        policy,
        invocation,
        required_environment,
        plan_hash,
        created_at: OffsetDateTime::now_utc(),
    })
}

pub fn execute_provider_sdk_with_policy(
    request: &ProviderExecutionRequest,
    registry: &NativeProviderAdapterRegistry,
    policy: ProviderSdkExecutionPolicy,
) -> MindResult<ProviderSdkExecutionReport> {
    let plan = plan_provider_sdk_execution(request, registry, policy)?;
    let allow_dry_run = matches!(
        policy,
        ProviderSdkExecutionPolicy::DryRunAllowed | ProviderSdkExecutionPolicy::PlanOnly
    );
    let native_receipt = execute_native_provider_with_receipt(request, registry, allow_dry_run)?;
    let accepted = match policy {
        ProviderSdkExecutionPolicy::PlanOnly => false,
        ProviderSdkExecutionPolicy::DryRunAllowed => {
            native_receipt.status == NativeProviderExecutionStatus::Executed
        }
        ProviderSdkExecutionPolicy::NativeFeatureRequired => {
            native_receipt.status == NativeProviderExecutionStatus::Executed
                && native_receipt.mode == NativeProviderExecutionMode::NativeFeature
        }
        ProviderSdkExecutionPolicy::ExternalReceiptRequired => {
            native_receipt.status == NativeProviderExecutionStatus::Executed
                && native_receipt.mode == NativeProviderExecutionMode::ExternalGateway
        }
    };
    let mut metadata = BTreeMap::new();
    metadata.insert(
        "idempotency_key".to_owned(),
        plan.invocation.idempotency_key.clone(),
    );
    metadata.insert("sdk".to_owned(), format!("{:?}", plan.sdk));
    let mut reasons = native_receipt.reasons.clone();
    reasons.push(format!("provider SDK execution policy {:?}", policy));
    let report = ProviderSdkExecutionReport {
        report_id: EventId::new(),
        plan,
        native_receipt,
        accepted,
        metadata,
        reasons,
        executed_at: OffsetDateTime::now_utc(),
    };
    report.verify_for(request)?;
    Ok(report)
}
