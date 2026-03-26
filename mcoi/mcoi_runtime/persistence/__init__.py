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
from .goal_store import GoalStore
from .memory_store import MemoryStore
from .registry_backend import RegistryBackend
from .replay_store import ReplayStore
from .skill_store import SkillStore
from .snapshot_store import SnapshotMetadata, SnapshotStore
from .trace_store import TraceStore
from .workflow_store import WorkflowStore
from ._serialization import deserialize_record, serialize_record

__all__ = [
    "CorruptedDataError",
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
    "TraceNotFoundError",
    "TraceStore",
    "WorkflowStore",
    "deserialize_record",
    "serialize_record",
]
