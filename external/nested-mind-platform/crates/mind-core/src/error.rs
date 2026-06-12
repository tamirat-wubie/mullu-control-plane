use crate::{EventId, LawRule, MindId, Permission};
use thiserror::Error;

pub type MindResult<T> = Result<T, MindError>;

#[derive(Debug, Error)]
pub enum MindError {
    #[error("proposal target {proposal} does not match mind {mind}")]
    WrongTarget { proposal: MindId, mind: MindId },
    #[error("commit {commit_id} target mismatch: expected {expected}, got {actual}")]
    CommitTargetMismatch {
        commit_id: EventId,
        expected: MindId,
        actual: MindId,
    },
    #[error("child parent {child_parent:?} does not match target parent {target_parent}")]
    WrongParent {
        child_parent: Option<MindId>,
        target_parent: MindId,
    },
    #[error("child mind {0} already exists")]
    DuplicateChild(MindId),
    #[error("maximum child count {max_children} exceeded")]
    MaxChildren { max_children: usize },
    #[error("immutable key `{0}` cannot be changed")]
    ImmutableKey(String),
    #[error("required key `{0}` cannot be removed")]
    RequiredKey(String),
    #[error("required key `{0}` missing")]
    MissingRequiredKey(String),
    #[error("forbidden key `{0}` present")]
    ForbiddenKey(String),
    #[error("empty patch is not accepted")]
    EmptyPatch,
    #[error("principal `{principal}` is not authorized for `{action}` on mind {mind_id}; required permission: {required:?}")]
    Unauthorized {
        principal: String,
        action: String,
        mind_id: MindId,
        required: Permission,
    },
    #[error("request actor `{actor}` does not match authenticated principal `{principal}`")]
    ActorPrincipalMismatch { actor: String, principal: String },
    #[error("missing credentials")]
    MissingCredentials,
    #[error("invalid credentials")]
    InvalidCredentials,
    #[error("identity evidence rejected: {reason}")]
    IdentityEvidenceRejected { reason: String },
    #[error("identity rejected: {reason}")]
    IdentityRejected { reason: String },
    #[error("signing policy rejected: {reason}")]
    SigningPolicyRejected { reason: String },
    #[error("identity assertion is invalid: {reason}")]
    IdentityAssertionInvalid { reason: String },
    #[error("identity token for `{subject}` is expired")]
    IdentityTokenExpired { subject: String },
    #[error("mTLS subject is required for this identity assertion")]
    MtlsSubjectRequired,
    #[error("commit {commit_id} is unsigned but signatures are required")]
    CommitUnsigned { commit_id: EventId },
    #[error("commit {commit_id} already has a signature")]
    CommitAlreadySigned { commit_id: EventId },
    #[error("commit {commit_id} signature is invalid: {reason}")]
    CommitSignatureInvalid { commit_id: EventId, reason: String },
    #[error("invalid key material length: expected {expected} bytes, got {actual} bytes")]
    InvalidKeyLength { expected: usize, actual: usize },
    #[error("signing backend `{backend}` is unavailable")]
    SigningBackendUnavailable { backend: String },
    #[error("signing attestation is invalid: {reason}")]
    SigningAttestationInvalid { reason: String },
    #[error("event sequence gap: expected {expected}, got {actual}")]
    EventSequenceGap { expected: u64, actual: u64 },
    #[error("event chain broken at sequence {sequence}: expected {expected:?}, got {actual:?}")]
    EventChainBroken {
        sequence: u64,
        expected: Option<String>,
        actual: Option<String>,
    },
    #[error(
        "event record hash mismatch at sequence {sequence}: expected {expected}, got {actual}"
    )]
    EventRecordHashMismatch {
        sequence: u64,
        expected: String,
        actual: String,
    },
    #[error("commit parent mismatch for {commit_id}: expected {expected:?}, got {actual:?}")]
    CommitParentMismatch {
        commit_id: EventId,
        expected: Option<EventId>,
        actual: Option<EventId>,
    },
    #[error("commit before-hash mismatch for {commit_id}: expected {expected}, got {actual}")]
    CommitBeforeHashMismatch {
        commit_id: EventId,
        expected: String,
        actual: String,
    },
    #[error("commit after-hash mismatch for {commit_id}: expected {expected}, got {actual}")]
    CommitAfterHashMismatch {
        commit_id: EventId,
        expected: String,
        actual: String,
    },
    #[error("lawbook migration from version {from} cannot apply to current version {current}")]
    LawbookMigrationVersionMismatch { current: u64, from: u64 },
    #[error("lawbook migration target version {to} must be exactly {expected}")]
    LawbookMigrationTargetVersion { expected: u64, to: u64 },
    #[error("lawbook migration has no operations")]
    LawbookMigrationEmpty,
    #[error("lawbook migration would remove protected foundation rule {rule:?}")]
    LawbookMigrationUnsafeRemoval { rule: LawRule },
    #[error("lawbook transition hash mismatch: expected {expected}, got {actual}")]
    LawbookTransitionHashMismatch { expected: String, actual: String },

    #[error("schema migration cannot go backward from {current} to {attempted}")]
    SchemaMigrationDowngrade { current: u64, attempted: u64 },
    #[error("schema migration gap: expected version {expected}, got {actual}")]
    SchemaMigrationGap { expected: u64, actual: u64 },
    #[error("schema migration {version} checksum mismatch: expected {expected}, got {actual}")]
    SchemaMigrationChecksumMismatch {
        version: u64,
        expected: String,
        actual: String,
    },
    #[error("schema migration {version} was already applied with checksum {applied_checksum}, but runtime expected {expected_checksum}")]
    SchemaMigrationConflict {
        version: u64,
        applied_checksum: String,
        expected_checksum: String,
    },
    #[error("snapshot compaction policy invalid: {0}")]
    SnapshotCompactionPolicyInvalid(String),
    #[error("snapshot compaction is not supported by this store")]
    SnapshotCompactionNotSupported,
    #[error("observability sink failed: {0}")]
    Observability(String),
    #[error("identity verification failed: {0}")]
    Identity(String),
    #[error("signing backend failed: {0}")]
    Signing(String),
    #[error("object backup store failed: {0}")]
    ObjectStore(String),
    #[error("distributed event-store policy failed: {0}")]
    Distributed(String),
    #[error("node `{node_id}` is not authorized to append events as role `{role}` under strategy `{strategy}`")]
    DistributedWriteRejected {
        node_id: String,
        role: String,
        strategy: String,
    },

    #[error("request safety policy invalid: {0}")]
    RequestSafetyPolicyInvalid(String),
    #[error("request body too large: max {max} bytes, got {actual} bytes")]
    RequestBodyTooLarge { max: u64, actual: u64 },
    #[error("rate limit exceeded for `{key}`: limit {limit} requests per window")]
    RateLimitExceeded { key: String, limit: u32 },
    #[error("backup hash mismatch: expected {expected}, got {actual}")]
    BackupHashMismatch { expected: String, actual: String },
    #[error("backup manifest counts do not match backup contents")]
    BackupManifestMismatch,
    #[error("backup contains records for wrong mind: expected {expected}, got {actual}")]
    BackupMindMismatch { expected: MindId, actual: MindId },
    #[error("backup restore target already exists: {0}")]
    BackupRestoreTargetExists(String),
    #[error("object storage failed: {reason}")]
    ObjectStorage { reason: String },
    #[error("object not found: {bucket}/{key}")]
    ObjectNotFound { bucket: String, key: String },
    #[error("distributed append rejected: {reason}")]
    DistributedAppendRejected { reason: String },
    #[error("event-store quorum not met: required {required}, accepted {accepted}")]
    QuorumNotMet { required: usize, accepted: usize },
    #[error("object backup failed: {reason}")]
    ObjectBackupFailed { reason: String },
    #[error("distributed event-store plan invalid: {reason}")]
    DistributedPlanInvalid { reason: String },
    #[error("object backup location is invalid: {0}")]
    ObjectBackupLocationInvalid(String),
    #[error("object backup hash mismatch: expected {expected}, got {actual}")]
    ObjectBackupHashMismatch { expected: String, actual: String },
    #[error("distributed event-store strategy invalid: {0}")]
    DistributedStrategyInvalid(String),
    #[error("snapshot hash mismatch: expected {expected}, got {actual}")]
    SnapshotHashMismatch { expected: String, actual: String },
    #[error("snapshot state hash mismatch: expected {expected}, got {actual}")]
    SnapshotStateHashMismatch { expected: String, actual: String },
    #[error("snapshot lawbook hash mismatch: expected {expected}, got {actual}")]
    SnapshotLawbookHashMismatch { expected: String, actual: String },
    #[error("no snapshot exists for mind {0}")]
    SnapshotMissing(MindId),
    #[error("event store failed: {0}")]
    Store(String),
    #[error("serialization failed: {0}")]
    Serialization(#[from] serde_json::Error),
    #[error("hex decoding failed: {0}")]
    Hex(#[from] hex::FromHexError),
    #[error("I/O failed: {0}")]
    Io(#[from] std::io::Error),
}
