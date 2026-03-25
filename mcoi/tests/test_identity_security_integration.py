"""Purpose: verify IdentitySecurityIntegration bridge enforces invariants.
Governance scope: identity_security integration tests only.
Dependencies: identity_security engine + integration, event_spine, memory_mesh.
Invariants:
  - Constructor validates all three engine types.
  - Bridge methods register identities with correct IdentityType.
  - Memory mesh attachment creates a MemoryRecord.
  - Graph attachment returns a dict with counts.
  - MemoryMeshEngine() takes NO arguments.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.identity_security import IdentityType
from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.identity_security import IdentitySecurityEngine
from mcoi_runtime.core.identity_security_integration import IdentitySecurityIntegration
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def es():
    return EventSpineEngine()


@pytest.fixture
def sec(es):
    return IdentitySecurityEngine(es)


@pytest.fixture
def mem():
    return MemoryMeshEngine()


@pytest.fixture
def integration(sec, es, mem):
    return IdentitySecurityIntegration(sec, es, mem)


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


class TestIntegrationConstructor:
    def test_valid(self, sec, es, mem) -> None:
        integ = IdentitySecurityIntegration(sec, es, mem)
        assert integ is not None

    def test_rejects_bad_security_engine(self, es, mem) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="security_engine"):
            IdentitySecurityIntegration("bad", es, mem)

    def test_rejects_none_security_engine(self, es, mem) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="security_engine"):
            IdentitySecurityIntegration(None, es, mem)

    def test_rejects_bad_event_spine(self, sec, mem) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            IdentitySecurityIntegration(sec, "bad", mem)

    def test_rejects_none_event_spine(self, sec, mem) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            IdentitySecurityIntegration(sec, None, mem)

    def test_rejects_bad_memory_engine(self, sec, es) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            IdentitySecurityIntegration(sec, es, "bad")

    def test_rejects_none_memory_engine(self, sec, es) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            IdentitySecurityIntegration(sec, es, None)


# ---------------------------------------------------------------------------
# identity_from_workforce
# ---------------------------------------------------------------------------


class TestIdentityFromWorkforce:
    def test_basic(self, integration) -> None:
        result = integration.identity_from_workforce("wf-1", "t-1", "Alice")
        assert result["identity_id"] == "wf-1"
        assert result["tenant_id"] == "t-1"
        assert result["display_name"] == "Alice"
        assert result["identity_type"] == "human"
        assert result["source_type"] == "workforce"
        assert result["workforce_ref"] == "none"

    def test_custom_workforce_ref(self, integration) -> None:
        result = integration.identity_from_workforce("wf-1", "t-1", "Alice", workforce_ref="dept-eng")
        assert result["workforce_ref"] == "dept-eng"

    def test_registers_identity(self, integration, sec) -> None:
        integration.identity_from_workforce("wf-1", "t-1", "Alice")
        identity = sec.get_identity("wf-1")
        assert identity.identity_type is IdentityType.HUMAN

    def test_emits_event(self, integration, es) -> None:
        before = es.event_count
        integration.identity_from_workforce("wf-1", "t-1", "Alice")
        assert es.event_count > before

    def test_duplicate_rejected(self, integration) -> None:
        integration.identity_from_workforce("wf-1", "t-1", "Alice")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            integration.identity_from_workforce("wf-1", "t-1", "Bob")


# ---------------------------------------------------------------------------
# identity_from_customer
# ---------------------------------------------------------------------------


class TestIdentityFromCustomer:
    def test_basic(self, integration) -> None:
        result = integration.identity_from_customer("cust-1", "t-1", "Bob")
        assert result["identity_id"] == "cust-1"
        assert result["identity_type"] == "human"
        assert result["source_type"] == "customer"
        assert result["customer_ref"] == "none"

    def test_custom_customer_ref(self, integration) -> None:
        result = integration.identity_from_customer("cust-1", "t-1", "Bob", customer_ref="acme-corp")
        assert result["customer_ref"] == "acme-corp"

    def test_registers_identity(self, integration, sec) -> None:
        integration.identity_from_customer("cust-1", "t-1", "Bob")
        identity = sec.get_identity("cust-1")
        assert identity.identity_type is IdentityType.HUMAN

    def test_emits_event(self, integration, es) -> None:
        before = es.event_count
        integration.identity_from_customer("cust-1", "t-1", "Bob")
        assert es.event_count > before


# ---------------------------------------------------------------------------
# identity_from_partner
# ---------------------------------------------------------------------------


class TestIdentityFromPartner:
    def test_basic(self, integration) -> None:
        result = integration.identity_from_partner("ptr-1", "t-1", "Carol")
        assert result["identity_id"] == "ptr-1"
        assert result["identity_type"] == "delegated"
        assert result["source_type"] == "partner"
        assert result["partner_ref"] == "none"

    def test_custom_partner_ref(self, integration) -> None:
        result = integration.identity_from_partner("ptr-1", "t-1", "Carol", partner_ref="vendor-x")
        assert result["partner_ref"] == "vendor-x"

    def test_registers_delegated_type(self, integration, sec) -> None:
        integration.identity_from_partner("ptr-1", "t-1", "Carol")
        identity = sec.get_identity("ptr-1")
        assert identity.identity_type is IdentityType.DELEGATED

    def test_emits_event(self, integration, es) -> None:
        before = es.event_count
        integration.identity_from_partner("ptr-1", "t-1", "Carol")
        assert es.event_count > before


# ---------------------------------------------------------------------------
# identity_from_external_execution
# ---------------------------------------------------------------------------


class TestIdentityFromExternalExecution:
    def test_basic(self, integration) -> None:
        result = integration.identity_from_external_execution("ext-1", "t-1", "Lambda")
        assert result["identity_id"] == "ext-1"
        assert result["identity_type"] == "service"
        assert result["source_type"] == "external_execution"
        assert result["execution_ref"] == "none"

    def test_custom_execution_ref(self, integration) -> None:
        result = integration.identity_from_external_execution("ext-1", "t-1", "Lambda", execution_ref="arn:aws:lambda")
        assert result["execution_ref"] == "arn:aws:lambda"

    def test_registers_service_type(self, integration, sec) -> None:
        integration.identity_from_external_execution("ext-1", "t-1", "Lambda")
        identity = sec.get_identity("ext-1")
        assert identity.identity_type is IdentityType.SERVICE

    def test_emits_event(self, integration, es) -> None:
        before = es.event_count
        integration.identity_from_external_execution("ext-1", "t-1", "Lambda")
        assert es.event_count > before


# ---------------------------------------------------------------------------
# identity_from_llm_runtime
# ---------------------------------------------------------------------------


class TestIdentityFromLLMRuntime:
    def test_basic(self, integration) -> None:
        result = integration.identity_from_llm_runtime("llm-1", "t-1", "GPT-4")
        assert result["identity_id"] == "llm-1"
        assert result["identity_type"] == "machine"
        assert result["source_type"] == "llm_runtime"
        assert result["model_ref"] == "none"

    def test_custom_model_ref(self, integration) -> None:
        result = integration.identity_from_llm_runtime("llm-1", "t-1", "GPT-4", model_ref="gpt-4-turbo")
        assert result["model_ref"] == "gpt-4-turbo"

    def test_registers_machine_type(self, integration, sec) -> None:
        integration.identity_from_llm_runtime("llm-1", "t-1", "GPT-4")
        identity = sec.get_identity("llm-1")
        assert identity.identity_type is IdentityType.MACHINE

    def test_emits_event(self, integration, es) -> None:
        before = es.event_count
        integration.identity_from_llm_runtime("llm-1", "t-1", "GPT-4")
        assert es.event_count > before


# ---------------------------------------------------------------------------
# identity_from_operator_workspace
# ---------------------------------------------------------------------------


class TestIdentityFromOperatorWorkspace:
    def test_basic(self, integration) -> None:
        result = integration.identity_from_operator_workspace("op-1", "t-1", "DevOps")
        assert result["identity_id"] == "op-1"
        assert result["identity_type"] == "human"
        assert result["source_type"] == "operator_workspace"
        assert result["workspace_ref"] == "none"

    def test_custom_workspace_ref(self, integration) -> None:
        result = integration.identity_from_operator_workspace("op-1", "t-1", "DevOps", workspace_ref="ws-prod")
        assert result["workspace_ref"] == "ws-prod"

    def test_registers_human_type(self, integration, sec) -> None:
        integration.identity_from_operator_workspace("op-1", "t-1", "DevOps")
        identity = sec.get_identity("op-1")
        assert identity.identity_type is IdentityType.HUMAN

    def test_emits_event(self, integration, es) -> None:
        before = es.event_count
        integration.identity_from_operator_workspace("op-1", "t-1", "DevOps")
        assert es.event_count > before


# ---------------------------------------------------------------------------
# Memory mesh attachment
# ---------------------------------------------------------------------------


class TestAttachSecurityStateToMemoryMesh:
    def test_basic(self, integration) -> None:
        record = integration.attach_security_state_to_memory_mesh("scope-1")
        assert isinstance(record, MemoryRecord)
        assert "identity" in record.tags or "identity" in list(record.tags)

    def test_content_keys(self, integration) -> None:
        record = integration.attach_security_state_to_memory_mesh("scope-1")
        content = record.content
        assert "total_identities" in content
        assert "total_credentials" in content
        assert "total_chains" in content
        assert "total_elevations" in content
        assert "total_sessions" in content
        assert "total_vault_accesses" in content
        assert "total_recertifications" in content
        assert "total_break_glass" in content
        assert "total_violations" in content

    def test_reflects_engine_state(self, integration, sec) -> None:
        sec.register_identity("id-1", "t-1", "Alice")
        sec.register_credential("cred-1", "t-1", "id-1")
        record = integration.attach_security_state_to_memory_mesh("scope-1")
        assert record.content["total_identities"] == 1
        assert record.content["total_credentials"] == 1

    def test_emits_event(self, integration, es) -> None:
        before = es.event_count
        integration.attach_security_state_to_memory_mesh("scope-1")
        assert es.event_count > before

    def test_adds_to_memory_engine(self, integration, mem) -> None:
        before = mem.memory_count
        integration.attach_security_state_to_memory_mesh("scope-1")
        assert mem.memory_count == before + 1

    def test_multiple_scopes(self, integration, mem) -> None:
        integration.attach_security_state_to_memory_mesh("scope-1")
        integration.attach_security_state_to_memory_mesh("scope-2")
        assert mem.memory_count >= 2


# ---------------------------------------------------------------------------
# Graph attachment
# ---------------------------------------------------------------------------


class TestAttachSecurityStateToGraph:
    def test_basic(self, integration) -> None:
        result = integration.attach_security_state_to_graph("scope-1")
        assert isinstance(result, dict)
        assert result["scope_ref_id"] == "scope-1"

    def test_count_keys(self, integration) -> None:
        result = integration.attach_security_state_to_graph("scope-1")
        assert "total_identities" in result
        assert "total_credentials" in result
        assert "total_chains" in result
        assert "total_elevations" in result
        assert "total_sessions" in result
        assert "total_vault_accesses" in result
        assert "total_recertifications" in result
        assert "total_break_glass" in result
        assert "total_violations" in result

    def test_reflects_engine_state(self, integration, sec) -> None:
        sec.register_identity("id-1", "t-1", "Alice")
        result = integration.attach_security_state_to_graph("scope-1")
        assert result["total_identities"] == 1

    def test_empty_state(self, integration) -> None:
        result = integration.attach_security_state_to_graph("scope-1")
        assert result["total_identities"] == 0
        assert result["total_credentials"] == 0


# ---------------------------------------------------------------------------
# Cross-bridge: all source types register distinct identity types
# ---------------------------------------------------------------------------


class TestCrossBridgeIdentityTypes:
    def test_workforce_is_human(self, integration, sec) -> None:
        integration.identity_from_workforce("a", "t", "A")
        assert sec.get_identity("a").identity_type is IdentityType.HUMAN

    def test_customer_is_human(self, integration, sec) -> None:
        integration.identity_from_customer("b", "t", "B")
        assert sec.get_identity("b").identity_type is IdentityType.HUMAN

    def test_partner_is_delegated(self, integration, sec) -> None:
        integration.identity_from_partner("c", "t", "C")
        assert sec.get_identity("c").identity_type is IdentityType.DELEGATED

    def test_external_is_service(self, integration, sec) -> None:
        integration.identity_from_external_execution("d", "t", "D")
        assert sec.get_identity("d").identity_type is IdentityType.SERVICE

    def test_llm_is_machine(self, integration, sec) -> None:
        integration.identity_from_llm_runtime("e", "t", "E")
        assert sec.get_identity("e").identity_type is IdentityType.MACHINE

    def test_operator_is_human(self, integration, sec) -> None:
        integration.identity_from_operator_workspace("f", "t", "F")
        assert sec.get_identity("f").identity_type is IdentityType.HUMAN


# ---------------------------------------------------------------------------
# End-to-end: bridge + engine + memory
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_full_flow(self) -> None:
        """Register from multiple sources, attach to memory, verify counts."""
        es = EventSpineEngine()
        sec = IdentitySecurityEngine(es)
        mem = MemoryMeshEngine()
        integ = IdentitySecurityIntegration(sec, es, mem)

        integ.identity_from_workforce("wf-1", "t-1", "Alice")
        integ.identity_from_customer("cust-1", "t-1", "Bob")
        integ.identity_from_partner("ptr-1", "t-1", "Carol")
        integ.identity_from_external_execution("ext-1", "t-1", "Lambda")
        integ.identity_from_llm_runtime("llm-1", "t-1", "GPT")
        integ.identity_from_operator_workspace("op-1", "t-1", "Ops")

        assert sec.identity_count == 6

        record = integ.attach_security_state_to_memory_mesh("scope-all")
        assert record.content["total_identities"] == 6

        graph = integ.attach_security_state_to_graph("scope-all")
        assert graph["total_identities"] == 6

    def test_bridge_then_break_glass(self) -> None:
        """Register via bridge, then break-glass, verify violation."""
        es = EventSpineEngine()
        sec = IdentitySecurityEngine(es)
        mem = MemoryMeshEngine()
        integ = IdentitySecurityIntegration(sec, es, mem)

        integ.identity_from_workforce("ops-1", "t-1", "Ops")
        sec.record_break_glass("bg-1", "t-1", "ops-1", "incident", "vp")
        assert sec.violation_count >= 1

        record = integ.attach_security_state_to_memory_mesh("scope-sec")
        assert record.content["total_violations"] >= 1
