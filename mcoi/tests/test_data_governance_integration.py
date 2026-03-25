"""Purpose: verify DataGovernanceIntegration bridge — governance methods,
    memory mesh attachment, graph attachment, event emission, and end-to-end
    golden path.
Governance scope: data governance integration tests only.
Dependencies: data_governance engine, event_spine, memory_mesh, core invariants,
    and real data governance contracts.
Invariants:
  - All tests are deterministic.
  - No network. No real persistence.
  - Uses real contract types and engine implementations.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.data_governance import DataGovernanceEngine
from mcoi_runtime.core.data_governance_integration import DataGovernanceIntegration
from mcoi_runtime.contracts.data_governance import (
    DataClassification,
    ResidencyRegion,
    HandlingDisposition,
    PrivacyBasis,
    RedactionLevel,
    GovernanceDecision,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RETURN_KEYS = frozenset({
    "data_id", "operation", "decision", "disposition", "redaction_level", "reason",
})

GRAPH_KEYS = frozenset({
    "scope_ref_id", "total_records", "total_policies",
    "total_residency_constraints", "total_privacy_rules",
    "total_redaction_rules", "total_retention_rules",
    "total_decisions", "total_violations",
})


@pytest.fixture()
def es() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def mm() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def eng(es: EventSpineEngine) -> DataGovernanceEngine:
    return DataGovernanceEngine(event_spine=es)


@pytest.fixture()
def bridge(eng: DataGovernanceEngine, es: EventSpineEngine, mm: MemoryMeshEngine) -> DataGovernanceIntegration:
    return DataGovernanceIntegration(eng, es, mm)


@pytest.fixture()
def seeded(eng: DataGovernanceEngine, bridge: DataGovernanceIntegration) -> DataGovernanceIntegration:
    """Fixture with data 'd1' classified as INTERNAL in tenant 't1',
    plus an ALLOW policy for INTERNAL."""
    eng.classify_data("d1", "t1", classification=DataClassification.INTERNAL)
    eng.register_policy(
        "p1", "t1",
        classification=DataClassification.INTERNAL,
        disposition=HandlingDisposition.ALLOW,
    )
    return bridge


# ---------------------------------------------------------------------------
# Constructor validation (3 tests)
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    """Constructor rejects non-engine arguments."""

    def test_rejects_non_governance_engine(self, es: EventSpineEngine, mm: MemoryMeshEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="governance_engine"):
            DataGovernanceIntegration("not-an-engine", es, mm)  # type: ignore[arg-type]

    def test_rejects_non_event_spine(self, eng: DataGovernanceEngine, mm: MemoryMeshEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            DataGovernanceIntegration(eng, "not-an-engine", mm)  # type: ignore[arg-type]

    def test_rejects_non_memory_engine(self, eng: DataGovernanceEngine, es: EventSpineEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            DataGovernanceIntegration(eng, es, "not-an-engine")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# govern_artifact_ingestion — allowed + denied (2 tests)
# ---------------------------------------------------------------------------


class TestGovernArtifactIngestion:
    def test_allowed(self, seeded: DataGovernanceIntegration) -> None:
        result = seeded.govern_artifact_ingestion("d1")
        assert result["operation"] == "artifact_ingestion"
        assert result["decision"] == GovernanceDecision.ALLOWED.value

    def test_denied_restricted_no_policy(
        self, eng: DataGovernanceEngine, bridge: DataGovernanceIntegration,
    ) -> None:
        eng.classify_data("dr", "t1", classification=DataClassification.RESTRICTED)
        result = bridge.govern_artifact_ingestion("dr")
        assert result["decision"] == GovernanceDecision.DENIED.value


# ---------------------------------------------------------------------------
# govern_communication_payload — allowed + denied (2 tests)
# ---------------------------------------------------------------------------


class TestGovernCommunicationPayload:
    def test_allowed(self, seeded: DataGovernanceIntegration) -> None:
        result = seeded.govern_communication_payload("d1")
        assert result["operation"] == "communication"
        assert result["decision"] == GovernanceDecision.ALLOWED.value

    def test_denied_restricted_no_policy(
        self, eng: DataGovernanceEngine, bridge: DataGovernanceIntegration,
    ) -> None:
        eng.classify_data("dr", "t1", classification=DataClassification.RESTRICTED)
        result = bridge.govern_communication_payload("dr")
        assert result["decision"] == GovernanceDecision.DENIED.value


# ---------------------------------------------------------------------------
# govern_memory_write — allowed + denied (2 tests)
# ---------------------------------------------------------------------------


class TestGovernMemoryWrite:
    def test_allowed(self, seeded: DataGovernanceIntegration) -> None:
        result = seeded.govern_memory_write("d1")
        assert result["operation"] == "memory_storage"
        assert result["decision"] == GovernanceDecision.ALLOWED.value

    def test_denied_restricted_no_policy(
        self, eng: DataGovernanceEngine, bridge: DataGovernanceIntegration,
    ) -> None:
        eng.classify_data("dr", "t1", classification=DataClassification.RESTRICTED)
        result = bridge.govern_memory_write("dr")
        assert result["decision"] == GovernanceDecision.DENIED.value


# ---------------------------------------------------------------------------
# govern_connector_payload — allowed + denied (2 tests)
# ---------------------------------------------------------------------------


class TestGovernConnectorPayload:
    def test_allowed(self, seeded: DataGovernanceIntegration) -> None:
        result = seeded.govern_connector_payload("d1")
        assert result["operation"] == "connector_transfer"
        assert result["decision"] == GovernanceDecision.ALLOWED.value

    def test_denied_residency(
        self, eng: DataGovernanceEngine, bridge: DataGovernanceIntegration,
    ) -> None:
        eng.classify_data("deu", "t1", classification=DataClassification.INTERNAL)
        eng.register_policy(
            "p-allow", "t1",
            classification=DataClassification.INTERNAL,
            disposition=HandlingDisposition.ALLOW,
        )
        eng.register_residency_constraint(
            "rc1", "t1", denied_regions=["eu"],
        )
        result = bridge.govern_connector_payload("deu", connector_region=ResidencyRegion.EU)
        assert result["decision"] == GovernanceDecision.DENIED.value


# ---------------------------------------------------------------------------
# govern_campaign_artifact_step — allowed + denied (2 tests)
# ---------------------------------------------------------------------------


class TestGovernCampaignArtifactStep:
    def test_allowed(self, seeded: DataGovernanceIntegration) -> None:
        result = seeded.govern_campaign_artifact_step("d1")
        assert result["operation"] == "campaign_artifact"
        assert result["decision"] == GovernanceDecision.ALLOWED.value

    def test_denied_restricted_no_policy(
        self, eng: DataGovernanceEngine, bridge: DataGovernanceIntegration,
    ) -> None:
        eng.classify_data("dr", "t1", classification=DataClassification.RESTRICTED)
        result = bridge.govern_campaign_artifact_step("dr")
        assert result["decision"] == GovernanceDecision.DENIED.value


# ---------------------------------------------------------------------------
# govern_program_reporting_output — allowed + denied (2 tests)
# ---------------------------------------------------------------------------


class TestGovernProgramReportingOutput:
    def test_allowed(self, seeded: DataGovernanceIntegration) -> None:
        result = seeded.govern_program_reporting_output("d1")
        assert result["operation"] == "program_reporting"
        assert result["decision"] == GovernanceDecision.ALLOWED.value

    def test_denied_restricted_no_policy(
        self, eng: DataGovernanceEngine, bridge: DataGovernanceIntegration,
    ) -> None:
        eng.classify_data("dr", "t1", classification=DataClassification.RESTRICTED)
        result = bridge.govern_program_reporting_output("dr")
        assert result["decision"] == GovernanceDecision.DENIED.value


# ---------------------------------------------------------------------------
# Return shape for each method (6 tests)
# ---------------------------------------------------------------------------


class TestReturnShape:
    """Each govern method returns a dict with exactly the expected keys."""

    def test_artifact_ingestion_shape(self, seeded: DataGovernanceIntegration) -> None:
        result = seeded.govern_artifact_ingestion("d1")
        assert set(result.keys()) == RETURN_KEYS

    def test_communication_payload_shape(self, seeded: DataGovernanceIntegration) -> None:
        result = seeded.govern_communication_payload("d1")
        assert set(result.keys()) == RETURN_KEYS

    def test_memory_write_shape(self, seeded: DataGovernanceIntegration) -> None:
        result = seeded.govern_memory_write("d1")
        assert set(result.keys()) == RETURN_KEYS

    def test_connector_payload_shape(self, seeded: DataGovernanceIntegration) -> None:
        result = seeded.govern_connector_payload("d1")
        assert set(result.keys()) == RETURN_KEYS

    def test_campaign_artifact_step_shape(self, seeded: DataGovernanceIntegration) -> None:
        result = seeded.govern_campaign_artifact_step("d1")
        assert set(result.keys()) == RETURN_KEYS

    def test_program_reporting_output_shape(self, seeded: DataGovernanceIntegration) -> None:
        result = seeded.govern_program_reporting_output("d1")
        assert set(result.keys()) == RETURN_KEYS


# ---------------------------------------------------------------------------
# Memory mesh attachment (1 test)
# ---------------------------------------------------------------------------


class TestMemoryMeshAttachment:
    def test_correct_tags_and_type(self, seeded: DataGovernanceIntegration) -> None:
        mem = seeded.attach_data_governance_to_memory_mesh("scope-1")
        assert isinstance(mem, MemoryRecord)
        assert mem.tags == ("data", "governance", "privacy")
        assert mem.scope_ref_id == "scope-1"
        assert mem.confidence == 1.0


# ---------------------------------------------------------------------------
# Graph attachment (1 test)
# ---------------------------------------------------------------------------


class TestGraphAttachment:
    def test_all_expected_keys(self, seeded: DataGovernanceIntegration) -> None:
        result = seeded.attach_data_governance_to_graph("scope-2")
        assert set(result.keys()) == GRAPH_KEYS
        assert result["scope_ref_id"] == "scope-2"
        assert result["total_records"] == 1
        assert result["total_policies"] == 1


# ---------------------------------------------------------------------------
# Events emitted count (1 test)
# ---------------------------------------------------------------------------


class TestEventsEmitted:
    def test_govern_operations_emit_events(
        self, es: EventSpineEngine, seeded: DataGovernanceIntegration,
    ) -> None:
        count_before = es.event_count
        seeded.govern_artifact_ingestion("d1")
        seeded.govern_communication_payload("d1")
        seeded.govern_memory_write("d1")
        seeded.govern_connector_payload("d1")
        seeded.govern_campaign_artifact_step("d1")
        seeded.govern_program_reporting_output("d1")
        # Each govern call emits exactly one event from the integration bridge,
        # plus the underlying engine emits its own event per decision.
        count_after = es.event_count
        # 6 integration events + 6 engine events = at least 12
        assert count_after - count_before >= 12


# ---------------------------------------------------------------------------
# Privacy rule blocks memory write (1 test)
# ---------------------------------------------------------------------------


class TestPrivacyRuleBlocksMemoryWrite:
    def test_privacy_basis_mismatch_denies_memory_write(
        self, eng: DataGovernanceEngine, bridge: DataGovernanceIntegration,
    ) -> None:
        # Classify data as PII with LEGITIMATE_INTEREST basis
        eng.classify_data(
            "d-pii", "t1",
            classification=DataClassification.PII,
            privacy_basis=PrivacyBasis.LEGITIMATE_INTEREST,
        )
        # Register a privacy rule that requires CONSENT for PII
        eng.register_privacy_rule(
            "priv-1", "t1",
            classification=DataClassification.PII,
            required_basis=PrivacyBasis.CONSENT,
        )
        result = bridge.govern_memory_write("d-pii")
        assert result["decision"] == GovernanceDecision.DENIED.value
        assert "privacy" in result["reason"].lower()


# ---------------------------------------------------------------------------
# Residency blocks connector payload (1 test)
# ---------------------------------------------------------------------------


class TestResidencyBlocksConnector:
    def test_denied_region_blocks_connector(
        self, eng: DataGovernanceEngine, bridge: DataGovernanceIntegration,
    ) -> None:
        eng.classify_data("d-res", "t1", classification=DataClassification.INTERNAL)
        eng.register_policy(
            "p-res", "t1",
            classification=DataClassification.INTERNAL,
            disposition=HandlingDisposition.ALLOW,
        )
        eng.register_residency_constraint(
            "rc-res", "t1", denied_regions=["apac"],
        )
        result = bridge.govern_connector_payload(
            "d-res", connector_region=ResidencyRegion.APAC,
        )
        assert result["decision"] == GovernanceDecision.DENIED.value
        assert "residency" in result["reason"].lower()


# ---------------------------------------------------------------------------
# Redaction applied to communication payload (1 test)
# ---------------------------------------------------------------------------


class TestRedactionApplied:
    def test_redaction_rule_applied_to_communication(
        self, eng: DataGovernanceEngine, bridge: DataGovernanceIntegration,
    ) -> None:
        eng.classify_data(
            "d-sens", "t1",
            classification=DataClassification.SENSITIVE,
        )
        eng.register_redaction_rule(
            "red-1", "t1",
            classification=DataClassification.SENSITIVE,
            redaction_level=RedactionLevel.FULL,
        )
        result = bridge.govern_communication_payload("d-sens")
        # With no explicit ALLOW policy but a redaction rule, the engine
        # should apply redaction (REDACTED decision with non-NONE redaction).
        assert result["redaction_level"] != RedactionLevel.NONE.value


# ---------------------------------------------------------------------------
# End-to-end golden path (1 test)
# ---------------------------------------------------------------------------


class TestEndToEndGoldenPath:
    def test_classify_govern_deny_redact_attach(
        self,
        es: EventSpineEngine,
        mm: MemoryMeshEngine,
        eng: DataGovernanceEngine,
        bridge: DataGovernanceIntegration,
    ) -> None:
        # 1. Classify multiple data records
        eng.classify_data("pub", "t1", classification=DataClassification.PUBLIC)
        eng.classify_data("intl", "t1", classification=DataClassification.INTERNAL)
        eng.classify_data("conf", "t1", classification=DataClassification.CONFIDENTIAL)
        eng.classify_data("sens", "t1", classification=DataClassification.SENSITIVE)
        eng.classify_data("restr", "t1", classification=DataClassification.RESTRICTED)
        eng.classify_data("pii", "t1", classification=DataClassification.PII,
                          privacy_basis=PrivacyBasis.CONSENT)

        # 2. Register an ALLOW policy for INTERNAL (covers PUBLIC and INTERNAL)
        eng.register_policy(
            "p-golden", "t1",
            classification=DataClassification.INTERNAL,
            disposition=HandlingDisposition.ALLOW,
        )

        # 3. Register a redaction rule for SENSITIVE data
        eng.register_redaction_rule(
            "red-golden", "t1",
            classification=DataClassification.SENSITIVE,
            redaction_level=RedactionLevel.PARTIAL,
        )

        # 4. Govern all 6 operation types on allowed data
        r1 = bridge.govern_artifact_ingestion("intl")
        assert r1["decision"] == GovernanceDecision.ALLOWED.value

        r2 = bridge.govern_communication_payload("intl")
        assert r2["decision"] == GovernanceDecision.ALLOWED.value

        r3 = bridge.govern_memory_write("intl")
        assert r3["decision"] == GovernanceDecision.ALLOWED.value

        r4 = bridge.govern_connector_payload("intl")
        assert r4["decision"] == GovernanceDecision.ALLOWED.value

        r5 = bridge.govern_campaign_artifact_step("intl")
        assert r5["decision"] == GovernanceDecision.ALLOWED.value

        r6 = bridge.govern_program_reporting_output("intl")
        assert r6["decision"] == GovernanceDecision.ALLOWED.value

        # 5. Deny restricted data (no policy covering RESTRICTED level)
        r_deny = bridge.govern_artifact_ingestion("restr")
        assert r_deny["decision"] == GovernanceDecision.DENIED.value

        # 6. Redact sensitive data — redaction rule triggers on communication
        r_redact = bridge.govern_communication_payload("sens")
        assert r_redact["redaction_level"] != RedactionLevel.NONE.value

        # 7. Memory mesh attachment
        mem = bridge.attach_data_governance_to_memory_mesh("golden-scope")
        assert isinstance(mem, MemoryRecord)
        assert mem.tags == ("data", "governance", "privacy")
        assert mem.content["total_records"] == 6

        # 8. Graph attachment
        graph = bridge.attach_data_governance_to_graph("golden-scope")
        assert set(graph.keys()) == GRAPH_KEYS
        assert graph["total_records"] == 6
        assert graph["total_policies"] == 1
        assert graph["total_redaction_rules"] == 1

        # 9. Verify events were emitted throughout
        assert es.event_count > 0
