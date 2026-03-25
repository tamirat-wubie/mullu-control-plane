"""Purpose: comprehensive tests for LlmRuntimeIntegration bridge.
Governance scope: validates all 8 integration methods — 6 generate_for_* bridge
    methods, attach_llm_state_to_memory_mesh, and attach_llm_state_to_graph.
Dependencies: pytest, mcoi_runtime engines and contracts.
Invariants:
  - Constructor validates all 3 engine types.
  - Each bridge method returns a frozen dict with 8 keys.
  - Events are emitted for every bridge call.
  - Memory records carry correct tags and content keys.
  - Graph dicts carry correct scope_ref_id and 7 total_ counts.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.llm_runtime import LlmRuntimeEngine
from mcoi_runtime.core.llm_runtime_integration import LlmRuntimeIntegration
from mcoi_runtime.contracts.llm_runtime import *
from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def engines():
    """Return (LlmRuntimeEngine, EventSpineEngine, MemoryMeshEngine) with
    a model, prompt template (approved), and context pack pre-registered."""
    es = EventSpineEngine()
    eng = LlmRuntimeEngine(es)
    mem = MemoryMeshEngine()

    eng.register_model("m1", "T1", "GPT-4", "openai", max_tokens=8000)
    eng.register_prompt_template("pt1", "T1", "Sum", "text")
    eng.approve_template("pt1")
    eng.build_context_pack("cp1", "T1", "pt1", "m1", token_count=500)

    return eng, es, mem


@pytest.fixture()
def bridge(engines):
    eng, es, mem = engines
    return LlmRuntimeIntegration(eng, es, mem)


@pytest.fixture()
def full(engines):
    """Return (bridge, eng, es, mem) for tests needing access to all."""
    eng, es, mem = engines
    return LlmRuntimeIntegration(eng, es, mem), eng, es, mem


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    def test_valid_construction(self, engines):
        eng, es, mem = engines
        b = LlmRuntimeIntegration(eng, es, mem)
        assert b is not None

    def test_invalid_llm_engine(self, engines):
        _, es, mem = engines
        with pytest.raises(RuntimeCoreInvariantError, match="llm_engine"):
            LlmRuntimeIntegration("bad", es, mem)

    def test_invalid_event_spine(self, engines):
        eng, _, mem = engines
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            LlmRuntimeIntegration(eng, "bad", mem)

    def test_invalid_memory_engine(self, engines):
        eng, es, _ = engines
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            LlmRuntimeIntegration(eng, es, "bad")

    def test_none_llm_engine(self, engines):
        _, es, mem = engines
        with pytest.raises(RuntimeCoreInvariantError):
            LlmRuntimeIntegration(None, es, mem)

    def test_none_event_spine(self, engines):
        eng, _, mem = engines
        with pytest.raises(RuntimeCoreInvariantError):
            LlmRuntimeIntegration(eng, None, mem)

    def test_none_memory_engine(self, engines):
        eng, es, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            LlmRuntimeIntegration(eng, es, None)


# ---------------------------------------------------------------------------
# generate_for_service_request
# ---------------------------------------------------------------------------


class TestGenerateForServiceRequest:
    def test_basic_return_keys(self, full):
        b, eng, es, mem = full
        r = b.generate_for_service_request("sr1", "T1", "m1", "cp1", service_ref="svc-a")
        assert set(r.keys()) == {
            "request_id", "tenant_id", "model_id", "service_ref",
            "status", "token_budget", "cost_budget", "source_type",
        }

    def test_source_type(self, full):
        b, *_ = full
        r = b.generate_for_service_request("sr2", "T1", "m1", "cp1")
        assert r["source_type"] == "service_request"

    def test_default_service_ref(self, full):
        b, *_ = full
        r = b.generate_for_service_request("sr3", "T1", "m1", "cp1")
        assert r["service_ref"] == "none"

    def test_custom_service_ref(self, full):
        b, *_ = full
        r = b.generate_for_service_request("sr4", "T1", "m1", "cp1", service_ref="ref-x")
        assert r["service_ref"] == "ref-x"

    def test_default_token_budget(self, full):
        b, *_ = full
        r = b.generate_for_service_request("sr5", "T1", "m1", "cp1")
        assert r["token_budget"] == 4096

    def test_custom_token_budget(self, full):
        b, *_ = full
        r = b.generate_for_service_request("sr6", "T1", "m1", "cp1", token_budget=2048)
        assert r["token_budget"] == 2048

    def test_default_cost_budget(self, full):
        b, *_ = full
        r = b.generate_for_service_request("sr7", "T1", "m1", "cp1")
        assert r["cost_budget"] == 1.0

    def test_custom_cost_budget(self, full):
        b, *_ = full
        r = b.generate_for_service_request("sr8", "T1", "m1", "cp1", cost_budget=5.0)
        assert r["cost_budget"] == 5.0

    def test_status_pending(self, full):
        b, *_ = full
        r = b.generate_for_service_request("sr9", "T1", "m1", "cp1")
        assert r["status"] == "pending"

    def test_emits_event(self, full):
        b, eng, es, mem = full
        before = es.event_count
        b.generate_for_service_request("sr10", "T1", "m1", "cp1")
        assert es.event_count > before

    def test_duplicate_request_id_rejected(self, full):
        b, *_ = full
        b.generate_for_service_request("sr11", "T1", "m1", "cp1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            b.generate_for_service_request("sr11", "T1", "m1", "cp1")


# ---------------------------------------------------------------------------
# generate_for_case_review
# ---------------------------------------------------------------------------


class TestGenerateForCaseReview:
    def test_basic_return_keys(self, full):
        b, *_ = full
        r = b.generate_for_case_review("cr1", "T1", "m1", "cp1", case_ref="case-a")
        assert set(r.keys()) == {
            "request_id", "tenant_id", "model_id", "case_ref",
            "status", "token_budget", "cost_budget", "source_type",
        }

    def test_source_type(self, full):
        b, *_ = full
        r = b.generate_for_case_review("cr2", "T1", "m1", "cp1")
        assert r["source_type"] == "case_review"

    def test_default_case_ref(self, full):
        b, *_ = full
        r = b.generate_for_case_review("cr3", "T1", "m1", "cp1")
        assert r["case_ref"] == "none"

    def test_custom_case_ref(self, full):
        b, *_ = full
        r = b.generate_for_case_review("cr4", "T1", "m1", "cp1", case_ref="case-z")
        assert r["case_ref"] == "case-z"

    def test_default_budgets(self, full):
        b, *_ = full
        r = b.generate_for_case_review("cr5", "T1", "m1", "cp1")
        assert r["token_budget"] == 4096
        assert r["cost_budget"] == 1.0

    def test_custom_budgets(self, full):
        b, *_ = full
        r = b.generate_for_case_review("cr6", "T1", "m1", "cp1", token_budget=1024, cost_budget=0.5)
        assert r["token_budget"] == 1024
        assert r["cost_budget"] == 0.5

    def test_status_pending(self, full):
        b, *_ = full
        r = b.generate_for_case_review("cr7", "T1", "m1", "cp1")
        assert r["status"] == "pending"

    def test_emits_event(self, full):
        b, eng, es, mem = full
        before = es.event_count
        b.generate_for_case_review("cr8", "T1", "m1", "cp1")
        assert es.event_count > before

    def test_duplicate_rejected(self, full):
        b, *_ = full
        b.generate_for_case_review("cr9", "T1", "m1", "cp1")
        with pytest.raises(RuntimeCoreInvariantError):
            b.generate_for_case_review("cr9", "T1", "m1", "cp1")


# ---------------------------------------------------------------------------
# generate_for_research
# ---------------------------------------------------------------------------


class TestGenerateForResearch:
    def test_basic_return_keys(self, full):
        b, *_ = full
        r = b.generate_for_research("rs1", "T1", "m1", "cp1")
        assert set(r.keys()) == {
            "request_id", "tenant_id", "model_id", "research_ref",
            "status", "token_budget", "cost_budget", "source_type",
        }

    def test_source_type(self, full):
        b, *_ = full
        r = b.generate_for_research("rs2", "T1", "m1", "cp1")
        assert r["source_type"] == "research"

    def test_default_research_ref(self, full):
        b, *_ = full
        r = b.generate_for_research("rs3", "T1", "m1", "cp1")
        assert r["research_ref"] == "none"

    def test_custom_research_ref(self, full):
        b, *_ = full
        r = b.generate_for_research("rs4", "T1", "m1", "cp1", research_ref="proj-42")
        assert r["research_ref"] == "proj-42"

    def test_default_token_budget_8192(self, full):
        b, *_ = full
        r = b.generate_for_research("rs5", "T1", "m1", "cp1")
        assert r["token_budget"] == 8192

    def test_default_cost_budget_2(self, full):
        b, *_ = full
        r = b.generate_for_research("rs6", "T1", "m1", "cp1")
        assert r["cost_budget"] == 2.0

    def test_custom_budgets(self, full):
        b, *_ = full
        r = b.generate_for_research("rs7", "T1", "m1", "cp1", token_budget=512, cost_budget=0.25)
        assert r["token_budget"] == 512
        assert r["cost_budget"] == 0.25

    def test_status_pending(self, full):
        b, *_ = full
        r = b.generate_for_research("rs8", "T1", "m1", "cp1")
        assert r["status"] == "pending"

    def test_emits_event(self, full):
        b, eng, es, mem = full
        before = es.event_count
        b.generate_for_research("rs9", "T1", "m1", "cp1")
        assert es.event_count > before

    def test_duplicate_rejected(self, full):
        b, *_ = full
        b.generate_for_research("rs10", "T1", "m1", "cp1")
        with pytest.raises(RuntimeCoreInvariantError):
            b.generate_for_research("rs10", "T1", "m1", "cp1")


# ---------------------------------------------------------------------------
# generate_for_reporting
# ---------------------------------------------------------------------------


class TestGenerateForReporting:
    def test_basic_return_keys(self, full):
        b, *_ = full
        r = b.generate_for_reporting("rp1", "T1", "m1", "cp1")
        assert set(r.keys()) == {
            "request_id", "tenant_id", "model_id", "report_ref",
            "status", "token_budget", "cost_budget", "source_type",
        }

    def test_source_type(self, full):
        b, *_ = full
        r = b.generate_for_reporting("rp2", "T1", "m1", "cp1")
        assert r["source_type"] == "reporting"

    def test_default_report_ref(self, full):
        b, *_ = full
        r = b.generate_for_reporting("rp3", "T1", "m1", "cp1")
        assert r["report_ref"] == "none"

    def test_custom_report_ref(self, full):
        b, *_ = full
        r = b.generate_for_reporting("rp4", "T1", "m1", "cp1", report_ref="q4-report")
        assert r["report_ref"] == "q4-report"

    def test_default_budgets(self, full):
        b, *_ = full
        r = b.generate_for_reporting("rp5", "T1", "m1", "cp1")
        assert r["token_budget"] == 4096
        assert r["cost_budget"] == 1.0

    def test_custom_budgets(self, full):
        b, *_ = full
        r = b.generate_for_reporting("rp6", "T1", "m1", "cp1", token_budget=6000, cost_budget=3.0)
        assert r["token_budget"] == 6000
        assert r["cost_budget"] == 3.0

    def test_emits_event(self, full):
        b, eng, es, mem = full
        before = es.event_count
        b.generate_for_reporting("rp7", "T1", "m1", "cp1")
        assert es.event_count > before

    def test_duplicate_rejected(self, full):
        b, *_ = full
        b.generate_for_reporting("rp8", "T1", "m1", "cp1")
        with pytest.raises(RuntimeCoreInvariantError):
            b.generate_for_reporting("rp8", "T1", "m1", "cp1")


# ---------------------------------------------------------------------------
# generate_for_remediation
# ---------------------------------------------------------------------------


class TestGenerateForRemediation:
    def test_basic_return_keys(self, full):
        b, *_ = full
        r = b.generate_for_remediation("rm1", "T1", "m1", "cp1")
        assert set(r.keys()) == {
            "request_id", "tenant_id", "model_id", "remediation_ref",
            "status", "token_budget", "cost_budget", "source_type",
        }

    def test_source_type(self, full):
        b, *_ = full
        r = b.generate_for_remediation("rm2", "T1", "m1", "cp1")
        assert r["source_type"] == "remediation"

    def test_default_remediation_ref(self, full):
        b, *_ = full
        r = b.generate_for_remediation("rm3", "T1", "m1", "cp1")
        assert r["remediation_ref"] == "none"

    def test_custom_remediation_ref(self, full):
        b, *_ = full
        r = b.generate_for_remediation("rm4", "T1", "m1", "cp1", remediation_ref="fix-99")
        assert r["remediation_ref"] == "fix-99"

    def test_default_budgets(self, full):
        b, *_ = full
        r = b.generate_for_remediation("rm5", "T1", "m1", "cp1")
        assert r["token_budget"] == 4096
        assert r["cost_budget"] == 1.0

    def test_custom_budgets(self, full):
        b, *_ = full
        r = b.generate_for_remediation("rm6", "T1", "m1", "cp1", token_budget=7000, cost_budget=4.0)
        assert r["token_budget"] == 7000
        assert r["cost_budget"] == 4.0

    def test_emits_event(self, full):
        b, eng, es, mem = full
        before = es.event_count
        b.generate_for_remediation("rm7", "T1", "m1", "cp1")
        assert es.event_count > before

    def test_duplicate_rejected(self, full):
        b, *_ = full
        b.generate_for_remediation("rm8", "T1", "m1", "cp1")
        with pytest.raises(RuntimeCoreInvariantError):
            b.generate_for_remediation("rm8", "T1", "m1", "cp1")


# ---------------------------------------------------------------------------
# generate_for_orchestration
# ---------------------------------------------------------------------------


class TestGenerateForOrchestration:
    def test_basic_return_keys(self, full):
        b, *_ = full
        r = b.generate_for_orchestration("oc1", "T1", "m1", "cp1")
        assert set(r.keys()) == {
            "request_id", "tenant_id", "model_id", "step_ref",
            "status", "token_budget", "cost_budget", "source_type",
        }

    def test_source_type(self, full):
        b, *_ = full
        r = b.generate_for_orchestration("oc2", "T1", "m1", "cp1")
        assert r["source_type"] == "orchestration"

    def test_default_step_ref(self, full):
        b, *_ = full
        r = b.generate_for_orchestration("oc3", "T1", "m1", "cp1")
        assert r["step_ref"] == "none"

    def test_custom_step_ref(self, full):
        b, *_ = full
        r = b.generate_for_orchestration("oc4", "T1", "m1", "cp1", step_ref="step-7")
        assert r["step_ref"] == "step-7"

    def test_default_budgets(self, full):
        b, *_ = full
        r = b.generate_for_orchestration("oc5", "T1", "m1", "cp1")
        assert r["token_budget"] == 4096
        assert r["cost_budget"] == 1.0

    def test_custom_budgets(self, full):
        b, *_ = full
        r = b.generate_for_orchestration("oc6", "T1", "m1", "cp1", token_budget=256, cost_budget=0.1)
        assert r["token_budget"] == 256
        assert r["cost_budget"] == 0.1

    def test_emits_event(self, full):
        b, eng, es, mem = full
        before = es.event_count
        b.generate_for_orchestration("oc7", "T1", "m1", "cp1")
        assert es.event_count > before

    def test_duplicate_rejected(self, full):
        b, *_ = full
        b.generate_for_orchestration("oc8", "T1", "m1", "cp1")
        with pytest.raises(RuntimeCoreInvariantError):
            b.generate_for_orchestration("oc8", "T1", "m1", "cp1")


# ---------------------------------------------------------------------------
# attach_llm_state_to_memory_mesh
# ---------------------------------------------------------------------------


class TestAttachLlmStateToMemoryMesh:
    def test_returns_memory_record(self, full):
        b, *_ = full
        rec = b.attach_llm_state_to_memory_mesh("scope-1")
        assert isinstance(rec, MemoryRecord)

    def test_tags(self, full):
        b, *_ = full
        rec = b.attach_llm_state_to_memory_mesh("scope-2")
        assert "llm_runtime" in rec.tags
        assert "model_execution" in rec.tags
        assert "generation" in rec.tags

    def test_content_has_7_keys(self, full):
        b, *_ = full
        rec = b.attach_llm_state_to_memory_mesh("scope-3")
        assert len(rec.content) == 7
        expected_keys = {
            "total_models", "total_routes", "total_templates",
            "total_requests", "total_results", "total_permissions",
            "total_violations",
        }
        assert set(rec.content.keys()) == expected_keys

    def test_scope_ref_id(self, full):
        b, *_ = full
        rec = b.attach_llm_state_to_memory_mesh("scope-4")
        assert rec.scope_ref_id == "scope-4"

    def test_total_models_reflects_engine(self, full):
        b, eng, es, mem = full
        rec = b.attach_llm_state_to_memory_mesh("scope-5")
        assert rec.content["total_models"] == eng.model_count

    def test_total_templates_reflects_engine(self, full):
        b, eng, es, mem = full
        rec = b.attach_llm_state_to_memory_mesh("scope-6")
        assert rec.content["total_templates"] == eng.template_count

    def test_emits_event(self, full):
        b, eng, es, mem = full
        before = es.event_count
        b.attach_llm_state_to_memory_mesh("scope-7")
        assert es.event_count > before

    def test_memory_stored_in_mesh(self, full):
        b, eng, es, mem = full
        before = mem.memory_count
        b.attach_llm_state_to_memory_mesh("scope-8")
        assert mem.memory_count == before + 1

    def test_title_contains_scope_ref(self, full):
        b, *_ = full
        rec = b.attach_llm_state_to_memory_mesh("scope-9")
        assert "scope-9" in rec.title

    def test_after_generation_counts_update(self, full):
        b, eng, es, mem = full
        b.generate_for_service_request("mem-sr1", "T1", "m1", "cp1")
        rec = b.attach_llm_state_to_memory_mesh("scope-10")
        assert rec.content["total_requests"] >= 1


# ---------------------------------------------------------------------------
# attach_llm_state_to_graph
# ---------------------------------------------------------------------------


class TestAttachLlmStateToGraph:
    def test_returns_dict(self, full):
        b, *_ = full
        g = b.attach_llm_state_to_graph("graph-1")
        assert isinstance(g, dict)

    def test_has_8_keys(self, full):
        b, *_ = full
        g = b.attach_llm_state_to_graph("graph-2")
        assert len(g) == 8

    def test_scope_ref_id_in_result(self, full):
        b, *_ = full
        g = b.attach_llm_state_to_graph("graph-3")
        assert g["scope_ref_id"] == "graph-3"

    def test_total_keys_present(self, full):
        b, *_ = full
        g = b.attach_llm_state_to_graph("graph-4")
        expected = {
            "scope_ref_id", "total_models", "total_routes", "total_templates",
            "total_requests", "total_results", "total_permissions",
            "total_violations",
        }
        assert set(g.keys()) == expected

    def test_total_models(self, full):
        b, eng, *_ = full
        g = b.attach_llm_state_to_graph("graph-5")
        assert g["total_models"] == eng.model_count

    def test_total_requests_after_generation(self, full):
        b, eng, es, mem = full
        b.generate_for_case_review("graph-cr1", "T1", "m1", "cp1")
        g = b.attach_llm_state_to_graph("graph-6")
        assert g["total_requests"] >= 1

    def test_total_violations_initially_zero(self, full):
        b, *_ = full
        g = b.attach_llm_state_to_graph("graph-7")
        assert g["total_violations"] == 0


# ---------------------------------------------------------------------------
# Cross-method integration
# ---------------------------------------------------------------------------


class TestCrossMethodIntegration:
    def test_all_six_methods_use_unique_source_types(self, full):
        b, *_ = full
        source_types = set()
        r1 = b.generate_for_service_request("xm1", "T1", "m1", "cp1")
        source_types.add(r1["source_type"])
        r2 = b.generate_for_case_review("xm2", "T1", "m1", "cp1")
        source_types.add(r2["source_type"])
        r3 = b.generate_for_research("xm3", "T1", "m1", "cp1")
        source_types.add(r3["source_type"])
        r4 = b.generate_for_reporting("xm4", "T1", "m1", "cp1")
        source_types.add(r4["source_type"])
        r5 = b.generate_for_remediation("xm5", "T1", "m1", "cp1")
        source_types.add(r5["source_type"])
        r6 = b.generate_for_orchestration("xm6", "T1", "m1", "cp1")
        source_types.add(r6["source_type"])
        assert len(source_types) == 6

    def test_multiple_generations_increase_event_count(self, full):
        b, eng, es, mem = full
        before = es.event_count
        b.generate_for_service_request("ev1", "T1", "m1", "cp1")
        b.generate_for_case_review("ev2", "T1", "m1", "cp1")
        b.generate_for_research("ev3", "T1", "m1", "cp1")
        # Each bridge call emits at least 1 event (from _emit), plus the
        # underlying request_generation also emits. So count grows.
        assert es.event_count > before

    def test_graph_and_memory_agree_on_counts(self, full):
        b, eng, es, mem = full
        b.generate_for_reporting("am1", "T1", "m1", "cp1")
        rec = b.attach_llm_state_to_memory_mesh("agree-1")
        g = b.attach_llm_state_to_graph("agree-2")
        # Both read from the same engine properties
        assert rec.content["total_models"] == g["total_models"]
        assert rec.content["total_routes"] == g["total_routes"]
        assert rec.content["total_templates"] == g["total_templates"]
        assert rec.content["total_requests"] == g["total_requests"]
        assert rec.content["total_results"] == g["total_results"]
        assert rec.content["total_permissions"] == g["total_permissions"]
        assert rec.content["total_violations"] == g["total_violations"]

    def test_request_id_echoed_back(self, full):
        b, *_ = full
        r = b.generate_for_service_request("echo-1", "T1", "m1", "cp1")
        assert r["request_id"] == "echo-1"

    def test_tenant_id_echoed_back(self, full):
        b, *_ = full
        r = b.generate_for_orchestration("echo-2", "T1", "m1", "cp1")
        assert r["tenant_id"] == "T1"

    def test_model_id_echoed_back(self, full):
        b, *_ = full
        r = b.generate_for_remediation("echo-3", "T1", "m1", "cp1")
        assert r["model_id"] == "m1"
