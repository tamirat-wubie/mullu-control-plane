use crate::{MindError, MindId, MindResult, ProjectionScope};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Principal {
    pub id: String,
    #[serde(default)]
    pub roles: BTreeSet<Role>,
    #[serde(default)]
    pub attributes: BTreeMap<String, String>,
}

impl Principal {
    #[must_use]
    pub fn new(id: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            roles: BTreeSet::new(),
            attributes: BTreeMap::new(),
        }
    }

    #[must_use]
    pub fn with_role(mut self, role: Role) -> Self {
        self.roles.insert(role);
        self
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum Role {
    Observer,
    Operator,
    Auditor,
    Maintainer,
    Admin,
}

impl Role {
    #[must_use]
    pub fn as_claim(&self) -> &'static str {
        match self {
            Self::Observer => "observer",
            Self::Operator => "operator",
            Self::Auditor => "auditor",
            Self::Maintainer => "maintainer",
            Self::Admin => "admin",
        }
    }

    #[must_use]
    pub fn from_claim(value: &str) -> Option<Self> {
        match value.trim().to_ascii_lowercase().as_str() {
            "observer" | "read_public" => Some(Self::Observer),
            "operator" | "writer" => Some(Self::Operator),
            "auditor" | "audit" => Some(Self::Auditor),
            "maintainer" | "maintenance" => Some(Self::Maintainer),
            "admin" | "administrator" => Some(Self::Admin),
            _ => None,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum Permission {
    ReadPublicProjection,
    ReadInternalProjection,
    ReadEvents,
    Replay,
    AuditReplay,
    ReadSnapshots,
    CreateSnapshot,
    CompactSnapshots,
    ReadObservability,
    ReadSchema,
    RunSchemaMigration,
    ReadIdentityPolicy,
    RefreshIdentityKeys,
    ReadSigningPolicy,
    ExecuteSigningAdapter,
    ReadEventStoreStrategy,
    ReadReplication,
    IngestReplication,
    ManageConsensus,
    ExportTelemetry,
    ReadBackups,
    CreateBackup,
    CreateObjectBackup,
    VerifyBackup,
    RestoreBackup,
    ProposePatch,
    AttachChild,
    MigrateLawbook,
    Administer,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "action", rename_all = "snake_case")]
pub enum MindAction {
    ReadProjection { scope: ProjectionScope },
    ReadEvents,
    Replay,
    AuditReplay,
    ReadSnapshots,
    CreateSnapshot,
    CompactSnapshots,
    ReadObservability,
    ReadSchema,
    RunSchemaMigration,
    ReadIdentityPolicy,
    RefreshIdentityKeys,
    ReadSigningPolicy,
    ExecuteSigningAdapter,
    ReadEventStoreStrategy,
    ReadReplication,
    IngestReplication,
    ManageConsensus,
    ExportTelemetry,
    ReadBackups,
    CreateBackup,
    CreateObjectBackup,
    VerifyBackup,
    RestoreBackup,
    ProposePatch,
    AttachChild,
    MigrateLawbook,
    Administer,
}

impl MindAction {
    #[must_use]
    pub fn required_permission(&self) -> Permission {
        match self {
            Self::ReadProjection {
                scope: ProjectionScope::Summary | ProjectionScope::Public,
            } => Permission::ReadPublicProjection,
            Self::ReadProjection {
                scope: ProjectionScope::Internal,
            } => Permission::ReadInternalProjection,
            Self::ReadEvents => Permission::ReadEvents,
            Self::Replay => Permission::Replay,
            Self::AuditReplay => Permission::AuditReplay,
            Self::ReadSnapshots => Permission::ReadSnapshots,
            Self::CreateSnapshot => Permission::CreateSnapshot,
            Self::CompactSnapshots => Permission::CompactSnapshots,
            Self::ReadObservability => Permission::ReadObservability,
            Self::ReadSchema => Permission::ReadSchema,
            Self::RunSchemaMigration => Permission::RunSchemaMigration,
            Self::ReadIdentityPolicy => Permission::ReadIdentityPolicy,
            Self::RefreshIdentityKeys => Permission::RefreshIdentityKeys,
            Self::ReadSigningPolicy => Permission::ReadSigningPolicy,
            Self::ExecuteSigningAdapter => Permission::ExecuteSigningAdapter,
            Self::ReadEventStoreStrategy => Permission::ReadEventStoreStrategy,
            Self::ReadReplication => Permission::ReadReplication,
            Self::IngestReplication => Permission::IngestReplication,
            Self::ManageConsensus => Permission::ManageConsensus,
            Self::ExportTelemetry => Permission::ExportTelemetry,
            Self::ReadBackups => Permission::ReadBackups,
            Self::CreateBackup => Permission::CreateBackup,
            Self::CreateObjectBackup => Permission::CreateObjectBackup,
            Self::VerifyBackup => Permission::VerifyBackup,
            Self::RestoreBackup => Permission::RestoreBackup,
            Self::ProposePatch => Permission::ProposePatch,
            Self::AttachChild => Permission::AttachChild,
            Self::MigrateLawbook => Permission::MigrateLawbook,
            Self::Administer => Permission::Administer,
        }
    }

    #[must_use]
    pub fn name(&self) -> &'static str {
        match self {
            Self::ReadProjection { .. } => "read_projection",
            Self::ReadEvents => "read_events",
            Self::Replay => "replay",
            Self::AuditReplay => "audit_replay",
            Self::ReadSnapshots => "read_snapshots",
            Self::CreateSnapshot => "create_snapshot",
            Self::CompactSnapshots => "compact_snapshots",
            Self::ReadObservability => "read_observability",
            Self::ReadSchema => "read_schema",
            Self::RunSchemaMigration => "run_schema_migration",
            Self::ReadIdentityPolicy => "read_identity_policy",
            Self::RefreshIdentityKeys => "refresh_identity_keys",
            Self::ReadSigningPolicy => "read_signing_policy",
            Self::ExecuteSigningAdapter => "execute_signing_adapter",
            Self::ReadEventStoreStrategy => "read_event_store_strategy",
            Self::ReadReplication => "read_replication",
            Self::IngestReplication => "ingest_replication",
            Self::ManageConsensus => "manage_consensus",
            Self::ExportTelemetry => "export_telemetry",
            Self::ReadBackups => "read_backups",
            Self::CreateBackup => "create_backup",
            Self::CreateObjectBackup => "create_object_backup",
            Self::VerifyBackup => "verify_backup",
            Self::RestoreBackup => "restore_backup",
            Self::ProposePatch => "propose_patch",
            Self::AttachChild => "attach_child",
            Self::MigrateLawbook => "migrate_lawbook",
            Self::Administer => "administer",
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AuthorizationPolicy {
    role_permissions: BTreeMap<Role, BTreeSet<Permission>>,
    allow_anonymous_public_projection: bool,
}

impl Default for AuthorizationPolicy {
    fn default() -> Self {
        Self::production_default()
    }
}

impl AuthorizationPolicy {
    #[must_use]
    pub fn production_default() -> Self {
        let mut role_permissions = BTreeMap::new();
        role_permissions.insert(
            Role::Observer,
            BTreeSet::from([Permission::ReadPublicProjection]),
        );
        role_permissions.insert(
            Role::Operator,
            BTreeSet::from([
                Permission::ReadPublicProjection,
                Permission::ProposePatch,
                Permission::AttachChild,
            ]),
        );
        role_permissions.insert(
            Role::Auditor,
            BTreeSet::from([
                Permission::ReadPublicProjection,
                Permission::ReadInternalProjection,
                Permission::ReadEvents,
                Permission::Replay,
                Permission::AuditReplay,
                Permission::ReadSnapshots,
                Permission::ReadObservability,
                Permission::ReadSchema,
                Permission::ReadIdentityPolicy,
                Permission::ReadSigningPolicy,
                Permission::ReadEventStoreStrategy,
                Permission::ReadReplication,
                Permission::ExportTelemetry,
                Permission::ReadBackups,
                Permission::VerifyBackup,
            ]),
        );
        role_permissions.insert(
            Role::Maintainer,
            BTreeSet::from([
                Permission::ReadPublicProjection,
                Permission::ReadInternalProjection,
                Permission::ReadEvents,
                Permission::Replay,
                Permission::AuditReplay,
                Permission::ReadSnapshots,
                Permission::CreateSnapshot,
                Permission::CompactSnapshots,
                Permission::ReadObservability,
                Permission::ReadSchema,
                Permission::RunSchemaMigration,
                Permission::ReadIdentityPolicy,
                Permission::RefreshIdentityKeys,
                Permission::ReadSigningPolicy,
                Permission::ExecuteSigningAdapter,
                Permission::ReadEventStoreStrategy,
                Permission::ReadReplication,
                Permission::IngestReplication,
                Permission::ManageConsensus,
                Permission::ExportTelemetry,
                Permission::ReadBackups,
                Permission::CreateBackup,
                Permission::CreateObjectBackup,
                Permission::VerifyBackup,
                Permission::RestoreBackup,
                Permission::ProposePatch,
                Permission::AttachChild,
                Permission::MigrateLawbook,
            ]),
        );
        role_permissions.insert(
            Role::Admin,
            BTreeSet::from([
                Permission::ReadPublicProjection,
                Permission::ReadInternalProjection,
                Permission::ReadEvents,
                Permission::Replay,
                Permission::AuditReplay,
                Permission::ReadSnapshots,
                Permission::CreateSnapshot,
                Permission::CompactSnapshots,
                Permission::ReadObservability,
                Permission::ReadSchema,
                Permission::RunSchemaMigration,
                Permission::ReadIdentityPolicy,
                Permission::RefreshIdentityKeys,
                Permission::ReadSigningPolicy,
                Permission::ExecuteSigningAdapter,
                Permission::ReadEventStoreStrategy,
                Permission::ReadReplication,
                Permission::IngestReplication,
                Permission::ManageConsensus,
                Permission::ExportTelemetry,
                Permission::ReadBackups,
                Permission::CreateBackup,
                Permission::CreateObjectBackup,
                Permission::VerifyBackup,
                Permission::RestoreBackup,
                Permission::ProposePatch,
                Permission::AttachChild,
                Permission::MigrateLawbook,
                Permission::Administer,
            ]),
        );
        Self {
            role_permissions,
            allow_anonymous_public_projection: true,
        }
    }

    pub fn require(
        &self,
        principal: Option<&Principal>,
        mind_id: MindId,
        action: &MindAction,
    ) -> MindResult<()> {
        if self.is_allowed(principal, action) {
            return Ok(());
        }
        let principal_id = principal
            .map(|p| p.id.clone())
            .unwrap_or_else(|| "anonymous".to_owned());
        Err(MindError::Unauthorized {
            principal: principal_id,
            action: action.name().to_owned(),
            mind_id,
            required: action.required_permission(),
        })
    }

    #[must_use]
    pub fn is_allowed(&self, principal: Option<&Principal>, action: &MindAction) -> bool {
        if principal.is_none() {
            return matches!(
                action,
                MindAction::ReadProjection {
                    scope: ProjectionScope::Summary | ProjectionScope::Public
                }
            ) && self.allow_anonymous_public_projection;
        }
        let required = action.required_permission();
        let principal = principal.expect("principal checked above");
        principal.roles.iter().any(|role| {
            self.role_permissions
                .get(role)
                .is_some_and(|permissions| permissions.contains(&required))
        })
    }
}
