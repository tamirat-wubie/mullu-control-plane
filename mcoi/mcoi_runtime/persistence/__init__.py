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
from .registry_backend import RegistryBackend
from .replay_store import ReplayStore
from .skill_store import SkillStore
from .snapshot_store import SnapshotMetadata, SnapshotStore
from .software_change_receipt_store import (
    FileSoftwareChangeReceiptStore,
    SoftwareChangeReceiptStore,
)
from .trace_store import TraceStore
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
    "PathTraversalError",
    "PersistenceError",
    "PersistenceWriteError",
    "RegistryBackend",
    "ReplayStore",
    "SnapshotMetadata",
    "SkillStore",
    "SnapshotNotFoundError",
    "SnapshotStore",
    "FileSoftwareChangeReceiptStore",
    "SoftwareChangeReceiptStore",
    "StatePersistence",
    "StateSnapshot",
    "TraceNotFoundError",
    "TraceStore",
    "WorkflowStore",
    "deserialize_record",
    "serialize_record",
]
