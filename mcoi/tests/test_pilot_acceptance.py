"""Phase 124G — Pilot Acceptance Test Suite."""
import pytest
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.pilot.tenant_bootstrap import PilotTenantBootstrap
from mcoi_runtime.pilot.data_import import PilotDataImporter
from mcoi_runtime.pilot.acceptance_test import PilotAcceptanceTest
from mcoi_runtime.pilot.scope_config import PILOT_CAPABILITIES, PILOT_CONNECTORS
from mcoi_runtime.pilot.connector_profiles import ALL_REQUIRED_PROFILES
from mcoi_runtime.pilot.slo_config import PILOT_SLOS, PILOT_RUNBOOKS

TENANT = "pilot-tenant-001"

class TestScopeConfig:
    def test_pilot_capabilities(self):
        assert len(PILOT_CAPABILITIES) == 8
        assert "intake" in PILOT_CAPABILITIES
        assert "copilot" in PILOT_CAPABILITIES

    def test_pilot_connectors(self):
        assert len(PILOT_CONNECTORS) == 5
        assert "email" in PILOT_CONNECTORS

class TestConnectorProfiles:
    def test_all_required_profiles(self):
        assert len(ALL_REQUIRED_PROFILES) == 5

    def test_each_profile_has_health_check(self):
        for p in ALL_REQUIRED_PROFILES:
            assert p.health_check_path
            assert p.timeout_ms > 0
            assert p.max_retries >= 1

class TestTenantBootstrap:
    def test_bootstrap_succeeds(self):
        es = EventSpineEngine()
        bootstrap = PilotTenantBootstrap(es)
        result = bootstrap.bootstrap(TENANT)
        assert result["status"] == "ready"
        assert result["total_steps"] >= 7
        assert len(result["connectors_activated"]) == 5
        assert len(result["personas"]) == 4
        assert len(result["governance_rules"]) == 3

    def test_bootstrap_creates_pack(self):
        es = EventSpineEngine()
        bootstrap = PilotTenantBootstrap(es)
        result = bootstrap.bootstrap(TENANT)
        assert result["pack"]["capability_count"] == 10

    def test_engines_accessible(self):
        es = EventSpineEngine()
        bootstrap = PilotTenantBootstrap(es)
        bootstrap.bootstrap(TENANT)
        engines = bootstrap.engines
        assert "pack" in engines
        assert "pilot" in engines
        assert "persona" in engines
        assert "governance" in engines

class TestDataImport:
    def test_import_cases(self):
        es = EventSpineEngine()
        importer = PilotDataImporter(es)
        cases = [{"case_id": f"c-{i}", "title": f"Case {i}"} for i in range(5)]
        result = importer.import_cases(TENANT, cases)
        assert result.accepted == 5
        assert result.rejected == 0

    def test_import_duplicates_counted(self):
        es = EventSpineEngine()
        importer = PilotDataImporter(es)
        cases = [{"case_id": "dup-1", "title": "Case"}]
        r1 = importer.import_cases(TENANT, cases)
        r2 = importer.import_cases(TENANT, cases)
        assert r1.accepted == 1
        assert r2.conflicts == 1

    def test_import_all(self):
        es = EventSpineEngine()
        importer = PilotDataImporter(es)
        dataset = {
            "cases": [{"case_id": f"ia-c-{i}", "title": f"C{i}"} for i in range(3)],
            "records": [{"record_id": f"ia-r-{i}", "title": f"R{i}"} for i in range(4)],
        }
        results = importer.import_all(TENANT, dataset)
        assert results["cases"].accepted == 3
        assert results["records"].accepted == 4

class TestSloConfig:
    def test_slo_definitions(self):
        assert len(PILOT_SLOS) == 5
        assert "availability" in PILOT_SLOS
        assert PILOT_SLOS["availability"]["target"] == 99.5

    def test_runbooks(self):
        assert len(PILOT_RUNBOOKS) == 5
        assert "connector_failure" in PILOT_RUNBOOKS
        for rb in PILOT_RUNBOOKS.values():
            assert rb["title"]
            assert rb["procedure"]

class TestFullAcceptance:
    """The 10-point acceptance test."""

    def test_full_pilot_acceptance(self):
        es = EventSpineEngine()
        bootstrap = PilotTenantBootstrap(es)
        bootstrap_result = bootstrap.bootstrap(TENANT)
        assert bootstrap_result["status"] == "ready"

        importer = PilotDataImporter(es)
        acceptance = PilotAcceptanceTest(bootstrap, importer)
        results = acceptance.run_all(TENANT)
        summary = acceptance.summary

        assert summary["total"] == 10
        # Print results for visibility
        for r in results:
            print(f"  {'PASS' if r.passed else 'FAIL'} {r.test_name}: {r.detail}")

        assert summary["all_green"], f"Failed: {[r.test_name for r in results if not r.passed]}"
