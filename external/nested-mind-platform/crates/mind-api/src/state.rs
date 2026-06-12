//! Purpose: runtime state boundary for the Nested Mind API.
//! Governance scope: shared API state construction and serialized access to non-Sync runtime stores.
//! Dependencies: mind-core runtime contracts, Tokio synchronization primitives, and API-local runtime store adapters.
//! Invariants: SQLite-backed stores are serialized; state cloning preserves shared ownership; handlers receive one governed state handle.

use std::sync::Arc;

use mind_core::{
    AuthorizationPolicy, ConsensusMembership, DistributedEventStorePlan, Ed25519CommitSigner,
    FileObjectBackupStore, InMemoryRateLimiter, JsonlReplicationInbox, LocalCloudMirrorStore, Mind,
    ReplicationTransportPlan, RequestSafetyConfig, SigningBackendStatus,
};
use tokio::sync::{Mutex, MutexGuard, RwLock};

use super::{
    AuthConfig, RuntimeEventStore, RuntimeObservabilitySink, RuntimeOidcDiscovery,
    RuntimeSnapshotStore,
};

#[derive(Clone)]
pub(super) struct AppState {
    pub(super) root: Arc<RwLock<Mind>>,
    pub(super) store: SerializedRuntimeState<RuntimeEventStore>,
    pub(super) snapshots: SerializedRuntimeState<RuntimeSnapshotStore>,
    pub(super) observability: SerializedRuntimeState<RuntimeObservabilitySink>,
    pub(super) safety: Arc<RwLock<InMemoryRateLimiter>>,
    pub(super) safety_config: RequestSafetyConfig,
    pub(super) authn: AuthConfig,
    pub(super) authz: AuthorizationPolicy,
    pub(super) signer: Option<Arc<Ed25519CommitSigner>>,
    pub(super) signing_status: SigningBackendStatus,
    pub(super) object_backups: Option<FileObjectBackupStore>,
    pub(super) oidc_discovery: Option<RuntimeOidcDiscovery>,
    pub(super) cloud_mirror: Option<LocalCloudMirrorStore>,
    pub(super) replication_inbox: Option<JsonlReplicationInbox>,
    pub(super) replication_transport: ReplicationTransportPlan,
    pub(super) consensus: Arc<RwLock<ConsensusMembership>>,
    pub(super) distributed_plan: DistributedEventStorePlan,
}

impl AppState {
    #[allow(clippy::too_many_arguments)]
    pub(super) fn new(
        root: Mind,
        store: RuntimeEventStore,
        snapshots: RuntimeSnapshotStore,
        observability: RuntimeObservabilitySink,
        safety: InMemoryRateLimiter,
        safety_config: RequestSafetyConfig,
        authn: AuthConfig,
        authz: AuthorizationPolicy,
        signer: Option<Arc<Ed25519CommitSigner>>,
        signing_status: SigningBackendStatus,
        object_backups: Option<FileObjectBackupStore>,
        oidc_discovery: Option<RuntimeOidcDiscovery>,
        cloud_mirror: Option<LocalCloudMirrorStore>,
        replication_inbox: Option<JsonlReplicationInbox>,
        replication_transport: ReplicationTransportPlan,
        consensus: ConsensusMembership,
        distributed_plan: DistributedEventStorePlan,
    ) -> Self {
        Self {
            root: Arc::new(RwLock::new(root)),
            store: SerializedRuntimeState::new(store),
            snapshots: SerializedRuntimeState::new(snapshots),
            observability: SerializedRuntimeState::new(observability),
            safety: Arc::new(RwLock::new(safety)),
            safety_config,
            authn,
            authz,
            signer,
            signing_status,
            object_backups,
            oidc_discovery,
            cloud_mirror,
            replication_inbox,
            replication_transport,
            consensus: Arc::new(RwLock::new(consensus)),
            distributed_plan,
        }
    }
}

pub(super) struct SerializedRuntimeState<T> {
    inner: Arc<Mutex<T>>,
}

impl<T> Clone for SerializedRuntimeState<T> {
    fn clone(&self) -> Self {
        Self {
            inner: Arc::clone(&self.inner),
        }
    }
}

impl<T> SerializedRuntimeState<T> {
    fn new(value: T) -> Self {
        Self {
            inner: Arc::new(Mutex::new(value)),
        }
    }

    // SQLite-backed stores are Send but not Sync, so read/write aliases serialize access.
    pub(super) async fn read(&self) -> MutexGuard<'_, T> {
        self.inner.lock().await
    }

    pub(super) async fn write(&self) -> MutexGuard<'_, T> {
        self.inner.lock().await
    }
}
