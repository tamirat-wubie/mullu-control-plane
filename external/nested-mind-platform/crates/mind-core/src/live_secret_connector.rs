use crate::secret_manager_jwt::{ensure_secret_safe_json_value, ensure_secret_safe_serialized};
use crate::{
    hash_serializable, EventId, MindError, MindResult, SecretAccessPlan, SecretAccessReceipt,
    SecretAccessStatus, SecretManagerBackend,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum LiveSecretConnectorMode {
    #[default]
    PlanOnly,
    DryRun,
    ReadApproved,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum LiveSecretConnectorStatus {
    Planned,
    DryRunAccepted,
    Resolved,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct LiveSecretConnectorPlan {
    pub connector_plan_id: EventId,
    pub access_plan_id: EventId,
    pub backend: SecretManagerBackend,
    pub locator_fingerprint: String,
    pub mode: LiveSecretConnectorMode,
    pub request_template: Value,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl LiveSecretConnectorPlan {
    pub fn verify(&self) -> MindResult<()> {
        ensure_secret_safe_serialized("live secret connector plan", self)?;
        if self.locator_fingerprint.trim().is_empty() {
            return Err(MindError::Store(
                "live secret connector plan requires locator fingerprint".to_owned(),
            ));
        }
        let expected = hash_serializable(&(
            self.connector_plan_id,
            self.access_plan_id,
            self.backend,
            &self.locator_fingerprint,
            self.mode,
            &self.request_template,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "live secret connector plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct LiveSecretConnectorReceipt {
    pub connector_receipt_id: EventId,
    pub connector_plan_id: EventId,
    pub access_receipt_id: EventId,
    pub backend: SecretManagerBackend,
    pub status: LiveSecretConnectorStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub material_fingerprint: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provider_request_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provider_response_hash: Option<String>,
    #[serde(default)]
    pub warnings: Vec<String>,
    pub receipt_hash: String,
    pub completed_at: OffsetDateTime,
}

impl LiveSecretConnectorReceipt {
    pub fn verify(&self) -> MindResult<()> {
        ensure_secret_safe_serialized("live secret connector receipt", self)?;
        if self.status == LiveSecretConnectorStatus::Resolved && self.material_fingerprint.is_none()
        {
            return Err(MindError::Store(
                "resolved live secret connector receipt requires material fingerprint".to_owned(),
            ));
        }
        let expected = hash_serializable(&(
            self.connector_receipt_id,
            self.connector_plan_id,
            self.access_receipt_id,
            self.backend,
            self.status,
            &self.material_fingerprint,
            &self.provider_request_id,
            &self.provider_response_hash,
            &self.warnings,
            self.completed_at,
        ))?;
        if expected != self.receipt_hash {
            return Err(MindError::Store(
                "live secret connector receipt hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }

    pub fn verify_against(
        &self,
        plan: &LiveSecretConnectorPlan,
        access_receipt: &SecretAccessReceipt,
    ) -> MindResult<()> {
        plan.verify()?;
        access_receipt.verify()?;
        self.verify()?;
        if self.connector_plan_id != plan.connector_plan_id
            || self.access_receipt_id != access_receipt.receipt_id
            || self.backend != plan.backend
        {
            return Err(MindError::Store(
                "live secret connector receipt does not match plan/access receipt".to_owned(),
            ));
        }
        if self.material_fingerprint != access_receipt.material_fingerprint {
            return Err(MindError::Store(
                "live secret connector material fingerprint mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn plan_live_secret_connector(
    access_plan: &SecretAccessPlan,
    mode: LiveSecretConnectorMode,
    request_template: Value,
) -> MindResult<LiveSecretConnectorPlan> {
    access_plan.verify()?;
    ensure_secret_safe_json_value("live secret connector request template", &request_template)?;
    let connector_plan_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let locator_fingerprint = hash_serializable(&(
        &access_plan.reference.backend,
        &access_plan.reference.locator,
        &access_plan.reference.key_id,
        &access_plan.reference.version,
    ))?;
    let plan_hash = hash_serializable(&(
        connector_plan_id,
        access_plan.plan_id,
        access_plan.reference.backend,
        &locator_fingerprint,
        mode,
        &request_template,
        created_at,
    ))?;
    let plan = LiveSecretConnectorPlan {
        connector_plan_id,
        access_plan_id: access_plan.plan_id,
        backend: access_plan.reference.backend,
        locator_fingerprint,
        mode,
        request_template,
        plan_hash,
        created_at,
    };
    plan.verify()?;
    Ok(plan)
}

pub fn record_live_secret_connector_receipt(
    plan: &LiveSecretConnectorPlan,
    access_receipt: &SecretAccessReceipt,
    provider_request_id: Option<String>,
    provider_response_hash: Option<String>,
    warnings: Vec<String>,
) -> MindResult<LiveSecretConnectorReceipt> {
    plan.verify()?;
    access_receipt.verify()?;
    if access_receipt.plan_id != plan.access_plan_id || access_receipt.backend != plan.backend {
        return Err(MindError::Store(
            "live secret connector access receipt does not match plan".to_owned(),
        ));
    }
    let status = match access_receipt.status {
        SecretAccessStatus::Resolved => LiveSecretConnectorStatus::Resolved,
        SecretAccessStatus::DryRunAccepted => LiveSecretConnectorStatus::DryRunAccepted,
        SecretAccessStatus::Planned => LiveSecretConnectorStatus::Planned,
        SecretAccessStatus::Rejected => LiveSecretConnectorStatus::Rejected,
    };
    let connector_receipt_id = EventId::new();
    let completed_at = OffsetDateTime::now_utc();
    let material_fingerprint = access_receipt.material_fingerprint.clone();
    let receipt_hash = hash_serializable(&(
        connector_receipt_id,
        plan.connector_plan_id,
        access_receipt.receipt_id,
        plan.backend,
        status,
        &material_fingerprint,
        &provider_request_id,
        &provider_response_hash,
        &warnings,
        completed_at,
    ))?;
    let receipt = LiveSecretConnectorReceipt {
        connector_receipt_id,
        connector_plan_id: plan.connector_plan_id,
        access_receipt_id: access_receipt.receipt_id,
        backend: plan.backend,
        status,
        material_fingerprint,
        provider_request_id,
        provider_response_hash,
        warnings,
        receipt_hash,
        completed_at,
    };
    receipt.verify_against(plan, access_receipt)?;
    Ok(receipt)
}
