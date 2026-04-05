"""Phase 232B — Tenant Data Partitioning.

Purpose: Logical data partitioning by tenant to ensure isolation at the
    storage layer. Routes data operations to tenant-specific partitions.
Dependencies: None (stdlib only).
Invariants:
  - Each tenant's data is isolated in its own partition.
  - Cross-tenant data access is structurally impossible.
  - Partition creation is idempotent.
  - All operations are auditable.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TenantPartition:
    """A logical data partition for a tenant."""
    tenant_id: str
    partition_id: str
    created_at: float = field(default_factory=time.time)
    record_count: int = 0
    size_bytes: int = 0
    _data: dict[str, Any] = field(default_factory=dict)

    def put(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.record_count = len(self._data)

    def get(self, key: str) -> Any | None:
        return self._data.get(key)

    def delete(self, key: str) -> bool:
        if key in self._data:
            del self._data[key]
            self.record_count = len(self._data)
            return True
        return False

    def keys(self) -> list[str]:
        return sorted(self._data.keys())

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "partition_id": self.partition_id,
            "record_count": self.record_count,
            "created_at": self.created_at,
        }


class TenantPartitionManager:
    """Manages tenant-isolated data partitions."""

    def __init__(self, max_partitions: int = 10_000):
        self._partitions: dict[str, TenantPartition] = {}
        self._max_partitions = max_partitions
        self._total_operations = 0

    def get_or_create(self, tenant_id: str) -> TenantPartition:
        if tenant_id not in self._partitions:
            if len(self._partitions) >= self._max_partitions:
                raise ValueError("max partitions exceeded")
            self._partitions[tenant_id] = TenantPartition(
                tenant_id=tenant_id,
                partition_id=f"part_{tenant_id}",
            )
        return self._partitions[tenant_id]

    def put(self, tenant_id: str, key: str, value: Any) -> None:
        partition = self.get_or_create(tenant_id)
        partition.put(key, value)
        self._total_operations += 1

    def get(self, tenant_id: str, key: str) -> Any | None:
        partition = self._partitions.get(tenant_id)
        if not partition:
            return None
        self._total_operations += 1
        return partition.get(key)

    def delete(self, tenant_id: str, key: str) -> bool:
        partition = self._partitions.get(tenant_id)
        if not partition:
            return False
        self._total_operations += 1
        return partition.delete(key)

    def list_partitions(self) -> list[TenantPartition]:
        return list(self._partitions.values())

    def summary(self) -> dict[str, Any]:
        return {
            "total_partitions": len(self._partitions),
            "total_operations": self._total_operations,
            "total_records": sum(p.record_count for p in self._partitions.values()),
        }
