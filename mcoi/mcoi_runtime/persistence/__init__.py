"""Purpose: MCOI persistence-core layer for deterministic, local, inspectable storage.
Governance scope: persistence API surface for runtime snapshots, traces, and registry state.
Dependencies: runtime-local contracts package, runtime-core invariants.
Invariants: persistence is explicit, deterministic, local, and fail-closed.
"""

from .errors import (
    CorruptedDataError,
    PersistenceError,
    PersistenceWriteError,
    SnapshotNotFoundError,
    TraceNotFoundError,
)
from .registry_backend import RegistryBackend
from .replay_store import ReplayStore
from .skill_store import SkillStore
from .snapshot_store import SnapshotMetadata, SnapshotStore
from .trace_store import TraceStore
from ._serialization import deserialize_record, serialize_record

__all__ = [
    "CorruptedDataError",
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
    "deserialize_record",
    "serialize_record",
]
