"""Tests for ContractRuntimeIntegration bridge.

Covers constructor validation, all 4 contract creation methods, all 3 binding
methods, memory mesh attachment, graph attachment, event emission, and a full
lifecycle golden path.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.contract_runtime import ContractRuntimeEngine
from mcoi_runtime.core.contract_runtime_integration import ContractRuntimeIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def event_spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def contract_engine(event_spine: EventSpineEngine) -> ContractRuntimeEngine:
    return ContractRuntimeEngine(event_spine)


@pytest.fixture()
def memory_engine() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def integration(
    contract_engine: ContractRuntimeEngine,
    event_spine: EventSpineEngine,
    memory_engine: MemoryMeshEngine,
) -> ContractRuntimeIntegration:
    return ContractRuntimeIntegration(contract_engine, event_spine, memory_engine)


def _add_contract_and_clause(
    contract_engine: ContractRuntimeEngine,
    contract_id: str = "c-1",
    tenant_id: str = "t-1",
    clause_id: str = "cl-1",
) -> None:
    """Helper: register a contract and a clause so binding methods work."""
    contract_engine.register_contract(contract_id, tenant_id, "cp-1", "Test contract")
    contract_engine.register_clause(clause_id, contract_id, "Test clause")


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    def test_rejects_wrong_contract_engine_type(
        self, event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="contract_engine"):
            ContractRuntimeIntegration("not-an-engine", event_spine, memory_engine)

    def test_rejects_wrong_event_spine_type(
        self, contract_engine: ContractRuntimeEngine, memory_engine: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            ContractRuntimeIntegration(contract_engine, "not-a-spine", memory_engine)

    def test_rejects_wrong_memory_engine_type(
        self, contract_engine: ContractRuntimeEngine, event_spine: EventSpineEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            ContractRuntimeIntegration(contract_engine, event_spine, 42)

    def test_accepts_valid_arguments(
        self,
        contract_engine: ContractRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        cri = ContractRuntimeIntegration(contract_engine, event_spine, memory_engine)
        assert cri is not None


# ---------------------------------------------------------------------------
# Contract creation methods
# ---------------------------------------------------------------------------


class TestContractFromProgram:
    def test_returns_expected_keys(self, integration: ContractRuntimeIntegration) -> None:
        result = integration.contract_from_program("c-1", "t-1", "prog-1")
        assert set(result.keys()) == {
            "contract_id", "tenant_id", "counterparty", "status", "source_type",
        }

    def test_source_type_is_program(self, integration: ContractRuntimeIntegration) -> None:
        result = integration.contract_from_program("c-1", "t-1", "prog-1")
        assert result["source_type"] == "program"

    def test_status_is_draft(self, integration: ContractRuntimeIntegration) -> None:
        result = integration.contract_from_program("c-1", "t-1", "prog-1")
        assert result["status"] == "draft"

    def test_counterparty_matches_program_id(
        self, integration: ContractRuntimeIntegration
    ) -> None:
        result = integration.contract_from_program("c-1", "t-1", "prog-42")
        assert result["counterparty"] == "prog-42"

    def test_custom_title(self, integration: ContractRuntimeIntegration) -> None:
        result = integration.contract_from_program(
            "c-1", "t-1", "prog-1", title="Custom title"
        )
        assert result["contract_id"] == "c-1"


class TestContractFromCampaign:
    def test_source_type_is_campaign(self, integration: ContractRuntimeIntegration) -> None:
        result = integration.contract_from_campaign("c-1", "t-1", "camp-1")
        assert result["source_type"] == "campaign"

    def test_status_is_draft(self, integration: ContractRuntimeIntegration) -> None:
        result = integration.contract_from_campaign("c-1", "t-1", "camp-1")
        assert result["status"] == "draft"

    def test_counterparty_matches_campaign_id(
        self, integration: ContractRuntimeIntegration
    ) -> None:
        result = integration.contract_from_campaign("c-1", "t-1", "camp-99")
        assert result["counterparty"] == "camp-99"


class TestContractFromReportingRequirement:
    def test_source_type_is_reporting_requirement(
        self, integration: ContractRuntimeIntegration
    ) -> None:
        result = integration.contract_from_reporting_requirement("c-1", "t-1", "req-1")
        assert result["source_type"] == "reporting_requirement"

    def test_status_is_draft(self, integration: ContractRuntimeIntegration) -> None:
        result = integration.contract_from_reporting_requirement("c-1", "t-1", "req-1")
        assert result["status"] == "draft"

    def test_counterparty_matches_requirement_id(
        self, integration: ContractRuntimeIntegration
    ) -> None:
        result = integration.contract_from_reporting_requirement("c-1", "t-1", "req-7")
        assert result["counterparty"] == "req-7"


class TestContractFromAssuranceScope:
    def test_source_type_is_assurance_scope(
        self, integration: ContractRuntimeIntegration
    ) -> None:
        result = integration.contract_from_assurance_scope("c-1", "t-1", "scope-1")
        assert result["source_type"] == "assurance_scope"

    def test_status_is_draft(self, integration: ContractRuntimeIntegration) -> None:
        result = integration.contract_from_assurance_scope("c-1", "t-1", "scope-1")
        assert result["status"] == "draft"

    def test_counterparty_matches_scope_ref_id(
        self, integration: ContractRuntimeIntegration
    ) -> None:
        result = integration.contract_from_assurance_scope("c-1", "t-1", "scope-5")
        assert result["counterparty"] == "scope-5"


# ---------------------------------------------------------------------------
# Binding methods
# ---------------------------------------------------------------------------


class TestBindFinancialPenalty:
    def test_returns_expected_keys(
        self,
        integration: ContractRuntimeIntegration,
        contract_engine: ContractRuntimeEngine,
    ) -> None:
        _add_contract_and_clause(contract_engine)
        result = integration.bind_financial_penalty("cm-1", "c-1", "cl-1", "t-1", "$10000")
        assert set(result.keys()) == {
            "commitment_id", "contract_id", "kind", "target_value", "binding_type",
        }

    def test_binding_type_is_financial_penalty(
        self,
        integration: ContractRuntimeIntegration,
        contract_engine: ContractRuntimeEngine,
    ) -> None:
        _add_contract_and_clause(contract_engine)
        result = integration.bind_financial_penalty("cm-1", "c-1", "cl-1", "t-1", "$500")
        assert result["binding_type"] == "financial_penalty"

    def test_kind_is_compliance(
        self,
        integration: ContractRuntimeIntegration,
        contract_engine: ContractRuntimeEngine,
    ) -> None:
        _add_contract_and_clause(contract_engine)
        result = integration.bind_financial_penalty("cm-1", "c-1", "cl-1", "t-1", "$500")
        assert result["kind"] == "compliance"

    def test_target_value_matches(
        self,
        integration: ContractRuntimeIntegration,
        contract_engine: ContractRuntimeEngine,
    ) -> None:
        _add_contract_and_clause(contract_engine)
        result = integration.bind_financial_penalty("cm-1", "c-1", "cl-1", "t-1", "$9999")
        assert result["target_value"] == "$9999"


class TestBindAvailabilityWindow:
    def test_binding_type_is_availability_window(
        self,
        integration: ContractRuntimeIntegration,
        contract_engine: ContractRuntimeEngine,
    ) -> None:
        _add_contract_and_clause(contract_engine)
        result = integration.bind_availability_window("cm-1", "c-1", "cl-1", "t-1", "99.9%")
        assert result["binding_type"] == "availability_window"

    def test_kind_is_availability(
        self,
        integration: ContractRuntimeIntegration,
        contract_engine: ContractRuntimeEngine,
    ) -> None:
        _add_contract_and_clause(contract_engine)
        result = integration.bind_availability_window("cm-1", "c-1", "cl-1", "t-1", "99.9%")
        assert result["kind"] == "availability"


class TestBindRemediationRequirement:
    def test_binding_type_is_remediation_requirement(
        self,
        integration: ContractRuntimeIntegration,
        contract_engine: ContractRuntimeEngine,
    ) -> None:
        _add_contract_and_clause(contract_engine)
        result = integration.bind_remediation_requirement(
            "cm-1", "c-1", "cl-1", "t-1", "4h"
        )
        assert result["binding_type"] == "remediation_requirement"

    def test_kind_is_response_time(
        self,
        integration: ContractRuntimeIntegration,
        contract_engine: ContractRuntimeEngine,
    ) -> None:
        _add_contract_and_clause(contract_engine)
        result = integration.bind_remediation_requirement(
            "cm-1", "c-1", "cl-1", "t-1", "4h"
        )
        assert result["kind"] == "response_time"


# ---------------------------------------------------------------------------
# Memory mesh attachment
# ---------------------------------------------------------------------------


class TestAttachContractStateToMemoryMesh:
    def test_returns_memory_record(
        self, integration: ContractRuntimeIntegration
    ) -> None:
        from mcoi_runtime.contracts.memory_mesh import MemoryRecord

        mem = integration.attach_contract_state_to_memory_mesh("scope-1")
        assert isinstance(mem, MemoryRecord)

    def test_tags_contain_expected_values(
        self, integration: ContractRuntimeIntegration
    ) -> None:
        mem = integration.attach_contract_state_to_memory_mesh("scope-1")
        assert "contract" in mem.tags
        assert "sla" in mem.tags
        assert "commitment" in mem.tags

    def test_memory_added_to_engine(
        self,
        integration: ContractRuntimeIntegration,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        mem = integration.attach_contract_state_to_memory_mesh("scope-1")
        retrieved = memory_engine.get_memory(mem.memory_id)
        assert retrieved is not None
        assert retrieved.memory_id == mem.memory_id


# ---------------------------------------------------------------------------
# Graph attachment
# ---------------------------------------------------------------------------


class TestAttachContractStateToGraph:
    def test_returns_expected_keys(
        self, integration: ContractRuntimeIntegration
    ) -> None:
        result = integration.attach_contract_state_to_graph("scope-1")
        expected_keys = {
            "scope_ref_id",
            "total_contracts",
            "active_contracts",
            "total_commitments",
            "total_sla_windows",
            "total_breaches",
            "total_remedies",
            "total_renewals",
            "total_violations",
        }
        assert set(result.keys()) == expected_keys

    def test_values_match_engine_state_empty(
        self, integration: ContractRuntimeIntegration
    ) -> None:
        result = integration.attach_contract_state_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"
        assert result["total_contracts"] == 0
        assert result["active_contracts"] == 0
        assert result["total_commitments"] == 0

    def test_values_reflect_registered_contract(
        self,
        integration: ContractRuntimeIntegration,
        contract_engine: ContractRuntimeEngine,
    ) -> None:
        integration.contract_from_program("c-1", "t-1", "prog-1")
        result = integration.attach_contract_state_to_graph("scope-1")
        assert result["total_contracts"] == 1


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------


class TestEventEmission:
    def test_contract_creation_emits_events(
        self,
        integration: ContractRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.contract_from_program("c-1", "t-1", "prog-1")
        after = event_spine.event_count
        # register_contract emits 1, contract_from_program emits 1 => at least +2
        assert after > before

    def test_binding_emits_events(
        self,
        integration: ContractRuntimeIntegration,
        event_spine: EventSpineEngine,
        contract_engine: ContractRuntimeEngine,
    ) -> None:
        _add_contract_and_clause(contract_engine)
        before = event_spine.event_count
        integration.bind_financial_penalty("cm-1", "c-1", "cl-1", "t-1", "$100")
        after = event_spine.event_count
        assert after > before

    def test_memory_mesh_attachment_emits_event(
        self,
        integration: ContractRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.attach_contract_state_to_memory_mesh("scope-1")
        after = event_spine.event_count
        assert after > before


# ---------------------------------------------------------------------------
# Golden path: full lifecycle
# ---------------------------------------------------------------------------


class TestGoldenPathFullLifecycle:
    def test_full_lifecycle(
        self,
        integration: ContractRuntimeIntegration,
        contract_engine: ContractRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        # 1. Create contracts from different sources
        c_prog = integration.contract_from_program("c-prog", "t-1", "prog-1")
        assert c_prog["source_type"] == "program"
        assert c_prog["status"] == "draft"

        c_camp = integration.contract_from_campaign("c-camp", "t-1", "camp-1")
        assert c_camp["source_type"] == "campaign"

        c_rep = integration.contract_from_reporting_requirement("c-rep", "t-1", "req-1")
        assert c_rep["source_type"] == "reporting_requirement"

        c_asc = integration.contract_from_assurance_scope("c-asc", "t-1", "scope-1")
        assert c_asc["source_type"] == "assurance_scope"

        # 2. Register clauses for binding
        contract_engine.register_clause("cl-prog", "c-prog", "SLA clause")
        contract_engine.register_clause("cl-camp", "c-camp", "Campaign clause")
        contract_engine.register_clause("cl-rep", "c-rep", "Reporting clause")

        # 3. Bind commitments
        fp = integration.bind_financial_penalty(
            "cm-fp", "c-prog", "cl-prog", "t-1", "$5000"
        )
        assert fp["binding_type"] == "financial_penalty"
        assert fp["kind"] == "compliance"

        aw = integration.bind_availability_window(
            "cm-aw", "c-camp", "cl-camp", "t-1", "99.95%"
        )
        assert aw["binding_type"] == "availability_window"
        assert aw["kind"] == "availability"

        rr = integration.bind_remediation_requirement(
            "cm-rr", "c-rep", "cl-rep", "t-1", "2h"
        )
        assert rr["binding_type"] == "remediation_requirement"
        assert rr["kind"] == "response_time"

        # 4. Attach state to memory mesh
        mem = integration.attach_contract_state_to_memory_mesh("lifecycle-scope")
        assert "contract" in mem.tags
        assert "sla" in mem.tags
        assert "commitment" in mem.tags
        assert memory_engine.get_memory(mem.memory_id) is not None

        # 5. Attach state to graph
        graph = integration.attach_contract_state_to_graph("lifecycle-scope")
        assert graph["total_contracts"] == 4
        assert graph["total_commitments"] == 3
        assert graph["scope_ref_id"] == "lifecycle-scope"

        # 6. Verify events were emitted throughout
        # 4 contract registrations (engine) + 4 integration events
        # 3 clause registrations (engine)
        # 3 commitment registrations (engine) + 3 integration events
        # 1 memory attachment event
        # Total should be significant
        assert event_spine.event_count >= 15
