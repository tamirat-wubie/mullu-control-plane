"""Purpose: adversarial runtime integration bridge.
Governance scope: connects adversarial reasoning to constitutional governance,
    copilot, external execution, self-tuning, public API, and identity runtimes.
Dependencies: adversarial_runtime engine, event_spine, memory_mesh.
Invariants:
  - Constructor validates all three engine types.
  - All outputs are frozen dicts or MemoryRecord instances.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.adversarial_runtime import AdversarialRuntimeEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict[str, Any], cid: str) -> None:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-advi", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.EXTERNAL,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)


class AdversarialRuntimeIntegration:
    """Integration bridge for red-team / adversarial reasoning."""

    def __init__(
        self,
        adversarial_engine: AdversarialRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(adversarial_engine, AdversarialRuntimeEngine):
            raise RuntimeCoreInvariantError("adversarial_engine must be an AdversarialRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._adv = adversarial_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # -- Bridge helpers --

    def _next_bridge_ids(self, tenant_id: str, source_type: str) -> tuple[str, str]:
        self._bridge_seq += 1
        seq = str(self._bridge_seq)
        scenario_id = stable_identifier("as", {"tenant": tenant_id, "source": source_type, "seq": seq})
        vuln_id = stable_identifier("av", {"tenant": tenant_id, "source": source_type, "seq": seq})
        return scenario_id, vuln_id

    def _bridge(
        self,
        tenant_id: str,
        source_type: str,
        display_prefix: str,
    ) -> dict[str, Any]:
        scenario_id, vuln_id = self._next_bridge_ids(tenant_id, source_type)
        scenario = self._adv.create_attack_scenario(
            scenario_id=scenario_id, tenant_id=tenant_id,
            display_name=f"{display_prefix}-scenario",
            target_runtime=source_type,
        )
        vuln = self._adv.register_vulnerability(
            vulnerability_id=vuln_id, tenant_id=tenant_id,
            target_runtime=source_type,
            description=f"{source_type} bridge vulnerability scan",
        )
        _emit(self._events, f"adversarial_for_{source_type}", {
            "tenant_id": tenant_id, "scenario_id": scenario_id, "vulnerability_id": vuln_id,
        }, scenario_id)
        return {
            "scenario_id": scenario.scenario_id,
            "vulnerability_id": vuln.vulnerability_id,
            "tenant_id": tenant_id,
            "scenario_status": scenario.status.value,
            "vulnerability_status": vuln.status.value,
            "source_type": source_type,
        }

    # -- Bridge methods --

    def adversarial_from_constitutional(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "constitutional", "const")

    def adversarial_from_copilot(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "copilot", "cop")

    def adversarial_from_external_execution(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "external_execution", "ext")

    def adversarial_from_self_tuning(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "self_tuning", "tune")

    def adversarial_from_public_api(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "public_api", "api")

    def adversarial_from_identity(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "identity", "id")

    # -- Memory mesh --

    def attach_adversarial_state_to_memory_mesh(self, scope_ref_id: str) -> MemoryRecord:
        now = _now_iso()
        mid = stable_identifier("mem-adv", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content = {
            "total_scenarios": self._adv.scenario_count,
            "total_vulnerabilities": self._adv.vulnerability_count,
            "total_exploits": self._adv.exploit_count,
            "total_defenses": self._adv.defense_count,
            "total_stress_tests": self._adv.stress_test_count,
            "total_violations": self._adv.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title=f"Adversarial runtime state for {scope_ref_id}",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("adversarial", "red_team", "security"),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "attach_adversarial_state_to_memory_mesh", {
            "scope_ref_id": scope_ref_id,
        }, scope_ref_id)
        return record

    # -- Graph --

    def attach_adversarial_state_to_graph(self, scope_ref_id: str) -> dict[str, Any]:
        return {
            "scope_ref_id": scope_ref_id,
            "total_scenarios": self._adv.scenario_count,
            "total_vulnerabilities": self._adv.vulnerability_count,
            "total_exploits": self._adv.exploit_count,
            "total_defenses": self._adv.defense_count,
            "total_stress_tests": self._adv.stress_test_count,
            "total_violations": self._adv.violation_count,
        }
