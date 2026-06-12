use crate::{
    hash_serializable, ChaosRehearsalPlan, EventId, LiveStagingChaosAdapterPlan, MindError,
    MindResult,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum KubernetesChaosExecutionMode {
    #[default]
    PlanOnly,
    ServerDryRun,
    LiveApproved,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum KubernetesChaosReceiptStatus {
    Planned,
    ServerDryRunAccepted,
    LiveSubmitted,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct KubernetesChaosManifest {
    pub manifest_id: EventId,
    pub api_version: String,
    pub kind: String,
    pub namespace: String,
    pub name: String,
    #[serde(default)]
    pub labels: BTreeMap<String, String>,
    pub spec: Value,
    pub manifest_hash: String,
}

impl KubernetesChaosManifest {
    pub fn new(
        api_version: impl Into<String>,
        kind: impl Into<String>,
        namespace: impl Into<String>,
        name: impl Into<String>,
        labels: BTreeMap<String, String>,
        spec: Value,
    ) -> MindResult<Self> {
        let api_version = api_version.into();
        let kind = kind.into();
        let namespace = namespace.into();
        let name = name.into();
        if api_version.trim().is_empty()
            || kind.trim().is_empty()
            || namespace.trim().is_empty()
            || name.trim().is_empty()
        {
            return Err(MindError::Store(
                "Kubernetes chaos manifest requires apiVersion, kind, namespace, and name"
                    .to_owned(),
            ));
        }
        let manifest_id = EventId::new();
        let manifest_hash = hash_serializable(&(
            manifest_id,
            &api_version,
            &kind,
            &namespace,
            &name,
            &labels,
            &spec,
        ))?;
        Ok(Self {
            manifest_id,
            api_version,
            kind,
            namespace,
            name,
            labels,
            spec,
            manifest_hash,
        })
    }

    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.manifest_id,
            &self.api_version,
            &self.kind,
            &self.namespace,
            &self.name,
            &self.labels,
            &self.spec,
        ))?;
        if expected != self.manifest_hash {
            return Err(MindError::Store(
                "Kubernetes chaos manifest hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn as_kubernetes_object(&self) -> Value {
        json!({
            "apiVersion": &self.api_version,
            "kind": &self.kind,
            "metadata": { "name": &self.name, "namespace": &self.namespace, "labels": &self.labels },
            "spec": &self.spec,
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct KubernetesStagingChaosPlan {
    pub plan_id: EventId,
    pub rehearsal_plan_id: EventId,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub adapter_plan_id: Option<EventId>,
    pub namespace: String,
    pub service_account: String,
    pub mode: KubernetesChaosExecutionMode,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub approval_certificate_hash: Option<String>,
    #[serde(default)]
    pub manifests: Vec<KubernetesChaosManifest>,
    #[serde(default)]
    pub kubectl_commands: Vec<String>,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl KubernetesStagingChaosPlan {
    pub fn verify(&self) -> MindResult<()> {
        for manifest in &self.manifests {
            manifest.verify()?;
        }
        let expected = hash_serializable(&(
            self.plan_id,
            self.rehearsal_plan_id,
            self.adapter_plan_id,
            &self.namespace,
            &self.service_account,
            self.mode,
            &self.approval_certificate_hash,
            &self.manifests,
            &self.kubectl_commands,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "Kubernetes staging chaos plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct KubernetesStagingChaosReceipt {
    pub receipt_id: EventId,
    pub plan_id: EventId,
    pub rehearsal_plan_id: EventId,
    pub mode: KubernetesChaosExecutionMode,
    pub status: KubernetesChaosReceiptStatus,
    pub namespace: String,
    #[serde(default)]
    pub applied_manifest_hashes: Vec<String>,
    pub server_dry_run: bool,
    pub live_side_effects: bool,
    #[serde(default)]
    pub observed_signals: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub response_hash: Option<String>,
    pub receipt_hash: String,
    pub executed_at: OffsetDateTime,
}

impl KubernetesStagingChaosReceipt {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.receipt_id,
            self.plan_id,
            self.rehearsal_plan_id,
            self.mode,
            self.status,
            &self.namespace,
            &self.applied_manifest_hashes,
            self.server_dry_run,
            self.live_side_effects,
            &self.observed_signals,
            &self.response_hash,
            self.executed_at,
        ))?;
        if expected != self.receipt_hash {
            return Err(MindError::Store(
                "Kubernetes staging chaos receipt hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn plan_kubernetes_staging_chaos(
    rehearsal: &ChaosRehearsalPlan,
    adapter_plan: Option<&LiveStagingChaosAdapterPlan>,
    namespace: impl Into<String>,
    service_account: impl Into<String>,
    mode: KubernetesChaosExecutionMode,
    approval_certificate_hash: Option<String>,
) -> MindResult<KubernetesStagingChaosPlan> {
    rehearsal.verify()?;
    if let Some(plan) = adapter_plan {
        plan.verify()?;
        if plan.rehearsal_plan_id != rehearsal.plan_id {
            return Err(MindError::Store(
                "Kubernetes chaos adapter plan belongs to a different rehearsal".to_owned(),
            ));
        }
    }
    let namespace = namespace.into();
    let service_account = service_account.into();
    if !namespace.starts_with("nested-mind-staging") && !namespace.contains("staging") {
        return Err(MindError::Store(
            "Kubernetes live chaos plan requires an explicit staging namespace".to_owned(),
        ));
    }
    if service_account.trim().is_empty() {
        return Err(MindError::Store(
            "Kubernetes chaos plan requires a service account".to_owned(),
        ));
    }
    if mode == KubernetesChaosExecutionMode::LiveApproved
        && approval_certificate_hash
            .as_deref()
            .unwrap_or_default()
            .trim()
            .is_empty()
    {
        return Err(MindError::Store(
            "live Kubernetes chaos requires an approval certificate hash".to_owned(),
        ));
    }
    let manifests = rehearsal.experiments.iter().map(|experiment| {
        let suffix = experiment.experiment_id.to_string().replace('-', "").chars().take(12).collect::<String>();
        let name = format!("mind-chaos-{suffix}");
        let labels = BTreeMap::from([
            ("app.kubernetes.io/name".to_owned(), "nested-mind-chaos".to_owned()),
            ("mind.mullusi.com/rehearsal".to_owned(), rehearsal.plan_id.to_string()),
            ("mind.mullusi.com/experiment".to_owned(), experiment.experiment_id.to_string()),
            ("mind.mullusi.com/severity".to_owned(), format!("{:?}", experiment.severity).to_lowercase()),
        ]);
        let spec = json!({
            "backoffLimit": 0,
            "template": {
                "metadata": { "labels": labels.clone() },
                "spec": {
                    "restartPolicy": "Never",
                    "serviceAccountName": service_account.clone(),
                    "containers": [{
                        "name": "chaos-rehearsal",
                        "image": "busybox:1.36",
                        "command": ["/bin/sh", "-c", "echo nested-mind-chaos-rehearsal && sleep 1"],
                        "env": [
                            { "name": "EXPERIMENT_ID", "value": experiment.experiment_id.to_string() },
                            { "name": "EXPECTED_CONTAINMENT", "value": experiment.expected_containment.clone() },
                            { "name": "EXPECTED_SIGNAL", "value": experiment.expected_signal.clone() }
                        ]
                    }]
                }
            }
        });
        KubernetesChaosManifest::new("batch/v1", "Job", &namespace, name, labels, spec)
    }).collect::<MindResult<Vec<_>>>()?;
    let dry_run_flag = match mode {
        KubernetesChaosExecutionMode::PlanOnly => "--dry-run=client",
        KubernetesChaosExecutionMode::ServerDryRun => "--dry-run=server",
        KubernetesChaosExecutionMode::LiveApproved => "",
    };
    let kubectl_commands = manifests
        .iter()
        .map(|manifest| {
            if dry_run_flag.is_empty() {
                format!(
                    "kubectl apply -n {} -f manifests/{}.json",
                    namespace, manifest.name
                )
            } else {
                format!(
                    "kubectl apply -n {} {dry_run_flag} -f manifests/{}.json",
                    namespace, manifest.name
                )
            }
        })
        .collect::<Vec<_>>();
    let plan_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let adapter_plan_id = adapter_plan.map(|plan| plan.adapter_plan_id);
    let plan_hash = hash_serializable(&(
        plan_id,
        rehearsal.plan_id,
        adapter_plan_id,
        &namespace,
        &service_account,
        mode,
        &approval_certificate_hash,
        &manifests,
        &kubectl_commands,
        created_at,
    ))?;
    Ok(KubernetesStagingChaosPlan {
        plan_id,
        rehearsal_plan_id: rehearsal.plan_id,
        adapter_plan_id,
        namespace,
        service_account,
        mode,
        approval_certificate_hash,
        manifests,
        kubectl_commands,
        plan_hash,
        created_at,
    })
}

pub fn record_kubernetes_staging_chaos_receipt(
    plan: &KubernetesStagingChaosPlan,
    response_payload: Option<Value>,
) -> MindResult<KubernetesStagingChaosReceipt> {
    plan.verify()?;
    let response_hash = response_payload
        .as_ref()
        .map(hash_serializable)
        .transpose()?;
    let status = match plan.mode {
        KubernetesChaosExecutionMode::PlanOnly => KubernetesChaosReceiptStatus::Planned,
        KubernetesChaosExecutionMode::ServerDryRun => {
            KubernetesChaosReceiptStatus::ServerDryRunAccepted
        }
        KubernetesChaosExecutionMode::LiveApproved => {
            if plan.approval_certificate_hash.is_some() {
                KubernetesChaosReceiptStatus::LiveSubmitted
            } else {
                KubernetesChaosReceiptStatus::Rejected
            }
        }
    };
    let server_dry_run = plan.mode == KubernetesChaosExecutionMode::ServerDryRun;
    let live_side_effects = matches!(status, KubernetesChaosReceiptStatus::LiveSubmitted);
    let observed_signals = match status {
        KubernetesChaosReceiptStatus::Planned => {
            vec!["Kubernetes chaos manifest plan created without cluster mutation".to_owned()]
        }
        KubernetesChaosReceiptStatus::ServerDryRunAccepted => {
            vec!["server dry-run receipt accepted; no resources persisted".to_owned()]
        }
        KubernetesChaosReceiptStatus::LiveSubmitted => {
            vec!["approved staging chaos submission recorded".to_owned()]
        }
        KubernetesChaosReceiptStatus::Rejected => {
            vec!["live staging chaos rejected without approval certificate".to_owned()]
        }
    };
    let applied_manifest_hashes = plan
        .manifests
        .iter()
        .map(|manifest| manifest.manifest_hash.clone())
        .collect::<Vec<_>>();
    let receipt_id = EventId::new();
    let executed_at = OffsetDateTime::now_utc();
    let receipt_hash = hash_serializable(&(
        receipt_id,
        plan.plan_id,
        plan.rehearsal_plan_id,
        plan.mode,
        status,
        &plan.namespace,
        &applied_manifest_hashes,
        server_dry_run,
        live_side_effects,
        &observed_signals,
        &response_hash,
        executed_at,
    ))?;
    Ok(KubernetesStagingChaosReceipt {
        receipt_id,
        plan_id: plan.plan_id,
        rehearsal_plan_id: plan.rehearsal_plan_id,
        mode: plan.mode,
        status,
        namespace: plan.namespace.clone(),
        applied_manifest_hashes,
        server_dry_run,
        live_side_effects,
        observed_signals,
        response_hash,
        receipt_hash,
        executed_at,
    })
}
