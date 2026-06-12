use crate::{
    evaluate_native_provider_request, EventId, MindError, MindResult,
    NativeProviderAdapterRegistry, NativeProviderAdapterReport, NativeProviderExecutionMode,
    ProviderExecutionReceipt, ProviderExecutionRequest, ProviderExecutionStatus,
    ProviderSdkInvocation, ProviderSdkReceipt,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum NativeProviderExecutionStatus {
    Planned,
    Executed,
    Rejected,
    Failed,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct NativeProviderExecutionReceipt {
    pub receipt_id: EventId,
    pub execution_id: EventId,
    pub adapter_report: NativeProviderAdapterReport,
    pub sdk_invocation: ProviderSdkInvocation,
    pub sdk_receipt: ProviderSdkReceipt,
    pub provider_receipt: ProviderExecutionReceipt,
    pub status: NativeProviderExecutionStatus,
    pub mode: NativeProviderExecutionMode,
    #[serde(default)]
    pub reasons: Vec<String>,
    pub executed_at: OffsetDateTime,
}

impl NativeProviderExecutionReceipt {
    pub fn verify_for(&self, request: &ProviderExecutionRequest) -> MindResult<()> {
        if self.execution_id != request.execution_id {
            return Err(MindError::Store(
                "native provider execution id mismatch".to_owned(),
            ));
        }
        self.sdk_receipt.verify_for(&self.sdk_invocation)?;
        self.provider_receipt.verify_for(request)?;
        if self.adapter_report.invocation_id != self.sdk_invocation.invocation_id {
            return Err(MindError::Store(
                "native provider adapter report invocation mismatch".to_owned(),
            ));
        }
        if self.adapter_report.request_hash != request.payload_hash {
            return Err(MindError::Store(
                "native provider adapter report hash mismatch".to_owned(),
            ));
        }
        if self.status == NativeProviderExecutionStatus::Executed
            && self.provider_receipt.status != ProviderExecutionStatus::Succeeded
        {
            return Err(MindError::Store(
                "native provider executed status without successful receipt".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn execute_native_provider_with_receipt(
    request: &ProviderExecutionRequest,
    registry: &NativeProviderAdapterRegistry,
    allow_dry_run: bool,
) -> MindResult<NativeProviderExecutionReceipt> {
    let adapter_report = evaluate_native_provider_request(request, registry)?;
    let mut sdk_invocation = ProviderSdkInvocation::from_execution_request(request)?;
    sdk_invocation.invocation_id = adapter_report.invocation_id;
    let mut reasons = adapter_report.reasons.clone();
    let accepted_mode = adapter_report.accepted
        && matches!(
            adapter_report.mode,
            NativeProviderExecutionMode::DryRunOnly
                | NativeProviderExecutionMode::ExternalGateway
                | NativeProviderExecutionMode::NativeFeature
        );
    let status = if !accepted_mode {
        reasons.push("native provider adapter rejected execution".to_owned());
        NativeProviderExecutionStatus::Rejected
    } else if adapter_report.mode == NativeProviderExecutionMode::DryRunOnly && !allow_dry_run {
        reasons.push("dry-run provider execution is not allowed by caller".to_owned());
        NativeProviderExecutionStatus::Rejected
    } else {
        NativeProviderExecutionStatus::Executed
    };
    let mode = adapter_report.mode;
    let sdk_receipt = match status {
        NativeProviderExecutionStatus::Executed => {
            ProviderSdkReceipt::dry_run_success(&sdk_invocation)
        }
        _ => rejected_sdk_receipt(
            &sdk_invocation,
            "native provider execution was not accepted",
        ),
    };
    let provider_receipt = match status {
        NativeProviderExecutionStatus::Executed => {
            ProviderExecutionReceipt::succeeded(request, request.payload_hash.clone())
        }
        _ => {
            ProviderExecutionReceipt::failed(request, "native provider execution was not accepted")
        }
    };
    let receipt = NativeProviderExecutionReceipt {
        receipt_id: EventId::new(),
        execution_id: request.execution_id,
        adapter_report,
        sdk_invocation,
        sdk_receipt,
        provider_receipt,
        status,
        mode,
        reasons,
        executed_at: OffsetDateTime::now_utc(),
    };
    receipt.verify_for(request)?;
    Ok(receipt)
}

fn rejected_sdk_receipt(
    invocation: &ProviderSdkInvocation,
    error: impl Into<String>,
) -> ProviderSdkReceipt {
    ProviderSdkReceipt {
        receipt_id: EventId::new(),
        invocation_id: invocation.invocation_id,
        sdk: invocation.sdk,
        command_kind: invocation.command_kind,
        target: invocation.target.clone(),
        status: ProviderExecutionStatus::Failed,
        expected_request_hash: invocation.request_hash.clone(),
        observed_request_hash: String::new(),
        provider_request_id: None,
        error: Some(error.into()),
        metadata: invocation.metadata.clone(),
        completed_at: OffsetDateTime::now_utc(),
    }
}
