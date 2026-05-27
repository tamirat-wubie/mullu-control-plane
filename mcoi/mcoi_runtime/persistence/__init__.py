"""Purpose: MCOI persistence-core layer for deterministic, local, inspectable storage.
Governance scope: persistence API surface for runtime snapshots, traces, and registry state.
Dependencies: runtime-local contracts package, runtime-core invariants.
Invariants: persistence is explicit, deterministic, local, and fail-closed.
"""

from .errors import (
    CorruptedDataError,
    PathTraversalError,
    PersistenceError,
    PersistenceWriteError,
    SnapshotNotFoundError,
    TraceNotFoundError,
)
from .hash_chain import HashChainStore, compute_chain_hash, compute_content_hash
from .coordination_store import CoordinationStore
from .goal_store import GoalStore
from .memory_store import MemoryStore
from .mil_audit_store import (
    MILAuditAppendResult,
    MILAuditRecord,
    MILAuditReplayLookup,
    MILAuditReplayPersistence,
    MILAuditStore,
    MILAuditTracePersistence,
)
from .registry_backend import RegistryBackend
from .replay_store import ReplayStore
from .skill_store import SkillStore
from .skill_promotion_store import (
    FileSkillPromotionStore,
    SkillPromotionRuntimeState,
    SkillPromotionStore,
)
from .snapshot_store import SnapshotMetadata, SnapshotStore
from .software_change_receipt_store import (
    FileSoftwareChangeReceiptStore,
    SoftwareChangeReceiptStore,
)
from .operational_math_receipt_store import (
    FileOperationalMathReceiptStore,
    OperationalMathReceiptStore,
)
from .team_registry_store import TeamRegistryState, TeamRegistryStore
from .team_queue_store import TeamQueueStore
from .temporal_scheduler_store import (
    FileTemporalSchedulerStore,
    TemporalSchedulerStore,
)
from .trace_store import TraceStore
from .workforce_store import WorkforceRuntimeState, WorkforceStore
from .workflow_store import WorkflowStore
from .state_persistence import StatePersistence, StateSnapshot
from ._serialization import deserialize_record, serialize_record

__all__ = [
    "CoordinationStore",
    "CorruptedDataError",
    "HashChainStore",
    "compute_chain_hash",
    "compute_content_hash",
    "GoalStore",
    "MemoryStore",
    "MILAuditAppendResult",
    "MILAuditRecord",
    "MILAuditReplayLookup",
    "MILAuditReplayPersistence",
    "MILAuditStore",
    "MILAuditTracePersistence",
    "PathTraversalError",
    "PersistenceError",
    "PersistenceWriteError",
    "RegistryBackend",
    "ReplayStore",
    "SnapshotMetadata",
    "SkillStore",
    "FileSkillPromotionStore",
    "SkillPromotionRuntimeState",
    "SkillPromotionStore",
    "SnapshotNotFoundError",
    "SnapshotStore",
    "FileSoftwareChangeReceiptStore",
    "FileOperationalMathReceiptStore",
    "FileTemporalSchedulerStore",
    "OperationalMathReceiptStore",
    "SoftwareChangeReceiptStore",
    "TeamRegistryState",
    "TeamRegistryStore",
    "TeamQueueStore",
    "TemporalSchedulerStore",
    "StatePersistence",
    "StateSnapshot",
    "TraceNotFoundError",
    "TraceStore",
    "WorkforceRuntimeState",
    "WorkforceStore",
    "WorkflowStore",
    "deserialize_record",
    "serialize_record",
]
