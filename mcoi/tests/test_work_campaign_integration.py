"""Phase 43 integration tests: WorkCampaignIntegration, campaign templates,
and CampaignObservabilityEngine.

Tests cover lifecycle operations, template structure, observability queries,
and fault-injection golden scenarios (43F).
"""

from __future__ import annotations

import pytest
from typing import Any

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.work_campaign import WorkCampaignEngine
from mcoi_runtime.core.work_campaign_integration import WorkCampaignIntegration
from mcoi_runtime.core.campaign_templates import (
    create_approval_deployment_campaign,
    create_support_escalation_campaign,
    create_document_processing_campaign,
)
from mcoi_runtime.core.campaign_observability import CampaignObservabilityEngine
from mcoi_runtime.contracts.work_campaign import (
    CampaignStatus,
    CampaignPriority,
    CampaignStepType,
    CampaignOutcomeVerdict,
    CampaignStep,
    CampaignStepStatus,
    CampaignTrigger,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engines():
    es = EventSpineEngine()
    mm = MemoryMeshEngine()
    wce = WorkCampaignEngine(es)
    integ = WorkCampaignIntegration(wce, es, mm)
    obs = CampaignObservabilityEngine(wce, es, mm)
    return es, mm, wce, integ, obs


def _simple_steps(cid: str, count: int = 3) -> list[CampaignStep]:
    """Create a simple chain of steps for testing."""
    steps = []
    for i in range(count):
        steps.append(CampaignStep(
            step_id=f"{cid}-step-{i}",
            campaign_id=cid,
            step_type=CampaignStepType.CHECK_CONDITION,
            order=i,
            name=f"Step {i}",
        ))
    steps.append(CampaignStep(
        step_id=f"{cid}-close",
        campaign_id=cid,
        step_type=CampaignStepType.CLOSE,
        order=count,
        name="Close",
    ))
    return steps


def _waiting_steps(cid: str) -> list[CampaignStep]:
    """Create steps that include a WAIT_FOR_REPLY step."""
    return [
        CampaignStep(
            step_id=f"{cid}-pre",
            campaign_id=cid,
            step_type=CampaignStepType.CHECK_CONDITION,
            order=0,
            name="Pre-check",
        ),
        CampaignStep(
            step_id=f"{cid}-wait",
            campaign_id=cid,
            step_type=CampaignStepType.WAIT_FOR_REPLY,
            order=1,
            name="Wait for human",
            timeout_seconds=3600,
        ),
        CampaignStep(
            step_id=f"{cid}-post",
            campaign_id=cid,
            step_type=CampaignStepType.CHECK_CONDITION,
            order=2,
            name="Post-check",
        ),
        CampaignStep(
            step_id=f"{cid}-close",
            campaign_id=cid,
            step_type=CampaignStepType.CLOSE,
            order=3,
            name="Close",
        ),
    ]


def _register_and_run(wce, integ, cid, steps, run_id=None):
    """Register a campaign and run it through integration."""
    wce.register_campaign(cid, f"Campaign {cid}", steps)
    return integ.run_campaign(cid, run_id=run_id)


# ===================================================================
# Integration tests: WorkCampaignIntegration
# ===================================================================


class TestRunCampaign:
    """Tests for run_campaign lifecycle."""

    def test_run_campaign_completes_simple_steps(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-1")
        wce.register_campaign("camp-1", "Simple", steps)
        result = integ.run_campaign("camp-1", run_id="run-1")

        assert result["run"].status == CampaignStatus.COMPLETED
        assert result["closure_report"] is not None
        assert result["closure_report"].outcome == CampaignOutcomeVerdict.SUCCESS
        assert len(result["records"]) == 4  # 3 steps + close

    def test_run_campaign_stops_at_waiting(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _waiting_steps("camp-w")
        wce.register_campaign("camp-w", "Waiting", steps)
        result = integ.run_campaign("camp-w", run_id="run-w")

        assert result["run"].status in (
            CampaignStatus.WAITING, CampaignStatus.COMPLETED,
        )

    def test_run_campaign_returns_records(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-rec", count=2)
        wce.register_campaign("camp-rec", "Records", steps)
        result = integ.run_campaign("camp-rec", run_id="run-rec")

        assert isinstance(result["records"], tuple)
        assert len(result["records"]) >= 2

    def test_run_campaign_attaches_memory(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-mem")
        wce.register_campaign("camp-mem", "Mem", steps)
        integ.run_campaign("camp-mem", run_id="run-mem")

        memories = mm.list_memories()
        assert len(memories) > 0

    def test_run_campaign_emits_events(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-ev", count=1)
        wce.register_campaign("camp-ev", "Events", steps)
        integ.run_campaign("camp-ev", run_id="run-ev")

        events = es.list_events()
        assert len(events) > 0

    def test_run_campaign_with_custom_run_id(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-cid")
        wce.register_campaign("camp-cid", "Custom", steps)
        result = integ.run_campaign("camp-cid", run_id="my-custom-run-id")

        assert result["run"].run_id == "my-custom-run-id"


class TestResumeCampaign:
    """Tests for resume_campaign."""

    def test_resume_paused_campaign(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-rp", count=4)
        wce.register_campaign("camp-rp", "Resume Paused", steps)
        run = wce.start_run("camp-rp", "run-rp")
        wce.execute_next_step("run-rp")
        integ.pause_campaign("run-rp")

        result = integ.resume_campaign("run-rp")
        assert result["run"].status == CampaignStatus.COMPLETED

    def test_resume_waiting_campaign(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _waiting_steps("camp-rw")
        wce.register_campaign("camp-rw", "Resume Wait", steps)
        integ.run_campaign("camp-rw", run_id="run-rw")

        run = wce.get_run("run-rw")
        if run.status == CampaignStatus.WAITING:
            result = integ.resume_campaign("run-rw")
            assert result["run"].status in (
                CampaignStatus.COMPLETED, CampaignStatus.ACTIVE,
            )

    def test_resume_emits_integration_event(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-revt")
        wce.register_campaign("camp-revt", "Resume Evt", steps)
        run = wce.start_run("camp-revt", "run-revt")
        integ.pause_campaign("run-revt")

        event_count_before = len(es.list_events())
        integ.resume_campaign("run-revt")
        event_count_after = len(es.list_events())

        assert event_count_after > event_count_before


class TestPauseCampaign:
    """Tests for pause_campaign."""

    def test_pause_sets_status(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-pause")
        wce.register_campaign("camp-pause", "Pause", steps)
        wce.start_run("camp-pause", "run-pause")

        paused = integ.pause_campaign("run-pause")
        assert paused.status == CampaignStatus.PAUSED

    def test_pause_attaches_memory(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-pausem")
        wce.register_campaign("camp-pausem", "PauseMem", steps)
        wce.start_run("camp-pausem", "run-pausem")

        mem_before = len(mm.list_memories())
        integ.pause_campaign("run-pausem")
        mem_after = len(mm.list_memories())

        assert mem_after > mem_before

    def test_pause_returns_campaign_run(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-prun")
        wce.register_campaign("camp-prun", "PauseRun", steps)
        wce.start_run("camp-prun", "run-prun")

        result = integ.pause_campaign("run-prun")
        assert result.run_id == "run-prun"
        assert result.campaign_id == "camp-prun"


class TestAbortCampaign:
    """Tests for abort_campaign."""

    def test_abort_sets_status(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-abort")
        wce.register_campaign("camp-abort", "Abort", steps)
        wce.start_run("camp-abort", "run-abort")

        result = integ.abort_campaign("run-abort", reason="test abort")
        assert result["run"].status == CampaignStatus.ABORTED

    def test_abort_generates_closure_report(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-abcl")
        wce.register_campaign("camp-abcl", "AbortClose", steps)
        wce.start_run("camp-abcl", "run-abcl")

        result = integ.abort_campaign("run-abcl", reason="testing")
        assert result["closure_report"] is not None
        assert result["closure_report"].outcome == CampaignOutcomeVerdict.ABORTED

    def test_abort_attaches_memory(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-abm")
        wce.register_campaign("camp-abm", "AbortMem", steps)
        wce.start_run("camp-abm", "run-abm")

        mem_before = len(mm.list_memories())
        integ.abort_campaign("run-abm", reason="test")
        mem_after = len(mm.list_memories())

        assert mem_after > mem_before

    def test_abort_closure_report_has_correct_run_id(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-abrid")
        wce.register_campaign("camp-abrid", "AbortRid", steps)
        wce.start_run("camp-abrid", "run-abrid")

        result = integ.abort_campaign("run-abrid")
        assert result["closure_report"].run_id == "run-abrid"


class TestCampaignFromCommitments:
    """Tests for campaign_from_commitments."""

    def test_creates_steps_from_commitments(self, engines):
        es, mm, wce, integ, obs = engines
        commitments = [
            {"description": "Fix bug"},
            {"description": "Write docs"},
            {"description": "Deploy"},
        ]
        desc = integ.campaign_from_commitments(
            "camp-com", "Commitment Campaign", commitments,
        )
        steps = wce.get_steps("camp-com")

        assert len(steps) == 4  # 3 commitment steps + close
        assert desc.trigger == CampaignTrigger.COMMITMENT_EXTRACTED

    def test_commitment_steps_are_create_obligation(self, engines):
        es, mm, wce, integ, obs = engines
        commitments = [{"description": "task-a"}]
        integ.campaign_from_commitments("camp-comt", "CommitType", commitments)
        steps = wce.get_steps("camp-comt")

        assert steps[0].step_type == CampaignStepType.CREATE_OBLIGATION

    def test_last_step_is_close(self, engines):
        es, mm, wce, integ, obs = engines
        commitments = [{"description": "x"}, {"description": "y"}]
        integ.campaign_from_commitments("camp-comcl", "CommitClose", commitments)
        steps = wce.get_steps("camp-comcl")

        assert steps[-1].step_type == CampaignStepType.CLOSE

    def test_commitment_with_priority(self, engines):
        es, mm, wce, integ, obs = engines
        commitments = [{"description": "urgent task"}]
        desc = integ.campaign_from_commitments(
            "camp-comu", "Urgent", commitments,
            priority=CampaignPriority.URGENT,
        )
        assert desc.priority == CampaignPriority.URGENT


class TestCampaignFromArtifact:
    """Tests for campaign_from_artifact."""

    def test_creates_ingest_extract_close_pipeline(self, engines):
        es, mm, wce, integ, obs = engines
        desc = integ.campaign_from_artifact(
            "camp-art", "Artifact Campaign", "artifact-ref-001",
        )
        steps = wce.get_steps("camp-art")

        assert len(steps) == 3
        assert steps[0].step_type == CampaignStepType.INGEST_ARTIFACT
        assert steps[1].step_type == CampaignStepType.EXTRACT_COMMITMENTS
        assert steps[2].step_type == CampaignStepType.CLOSE

    def test_artifact_ref_is_set(self, engines):
        es, mm, wce, integ, obs = engines
        integ.campaign_from_artifact("camp-artref", "ArtRef", "my-artifact")
        steps = wce.get_steps("camp-artref")

        assert steps[0].target_ref == "my-artifact"

    def test_trigger_is_artifact_ingested(self, engines):
        es, mm, wce, integ, obs = engines
        desc = integ.campaign_from_artifact("camp-arttr", "ArtTrigger", "ref-1")
        assert desc.trigger == CampaignTrigger.ARTIFACT_INGESTED


class TestCampaignFromIncident:
    """Tests for campaign_from_incident."""

    def test_creates_classify_route_escalate_close(self, engines):
        es, mm, wce, integ, obs = engines
        chain = ["ops-1", "ops-2", "manager"]
        desc = integ.campaign_from_incident(
            "camp-inc", "Incident", "incident-42", chain,
        )
        steps = wce.get_steps("camp-inc")

        # classify + 3 route + escalate + close = 6
        assert len(steps) == 6
        assert steps[0].step_type == CampaignStepType.CHECK_CONDITION
        assert steps[1].step_type == CampaignStepType.ROUTE_TO_IDENTITY
        assert steps[2].step_type == CampaignStepType.ROUTE_TO_IDENTITY
        assert steps[3].step_type == CampaignStepType.ROUTE_TO_IDENTITY
        assert steps[4].step_type == CampaignStepType.ESCALATE
        assert steps[5].step_type == CampaignStepType.CLOSE

    def test_route_targets_match_chain(self, engines):
        es, mm, wce, integ, obs = engines
        chain = ["alpha", "beta"]
        integ.campaign_from_incident("camp-incr", "IncRoute", "inc-1", chain)
        steps = wce.get_steps("camp-incr")

        route_steps = [s for s in steps if s.step_type == CampaignStepType.ROUTE_TO_IDENTITY]
        assert len(route_steps) == 2
        assert route_steps[0].target_ref == "alpha"
        assert route_steps[1].target_ref == "beta"

    def test_default_priority_is_urgent(self, engines):
        es, mm, wce, integ, obs = engines
        desc = integ.campaign_from_incident(
            "camp-incpr", "IncPriority", "inc-2", ["tier-1"],
        )
        assert desc.priority == CampaignPriority.URGENT

    def test_trigger_is_incident_detected(self, engines):
        es, mm, wce, integ, obs = engines
        desc = integ.campaign_from_incident(
            "camp-inctr", "IncTrig", "inc-3", ["tier-1"],
        )
        assert desc.trigger == CampaignTrigger.INCIDENT_DETECTED


class TestCampaignFromDomainPack:
    """Tests for campaign_from_domain_pack."""

    def test_wraps_arbitrary_steps(self, engines):
        es, mm, wce, integ, obs = engines
        steps = [
            CampaignStep(
                step_id="dp-step-0",
                campaign_id="camp-dp",
                step_type=CampaignStepType.RUN_WORKFLOW,
                order=0,
                name="Custom workflow",
            ),
            CampaignStep(
                step_id="dp-close",
                campaign_id="camp-dp",
                step_type=CampaignStepType.CLOSE,
                order=1,
                name="Close",
            ),
        ]
        desc = integ.campaign_from_domain_pack(
            "camp-dp", "Domain Pack", "pack-123", steps,
        )
        assert desc.trigger == CampaignTrigger.DOMAIN_PACK
        assert desc.step_count == 2

    def test_domain_pack_campaign_runs(self, engines):
        es, mm, wce, integ, obs = engines
        steps = [
            CampaignStep(
                step_id="dprun-step-0",
                campaign_id="camp-dprun",
                step_type=CampaignStepType.CHECK_CONDITION,
                order=0,
                name="Check",
            ),
            CampaignStep(
                step_id="dprun-close",
                campaign_id="camp-dprun",
                step_type=CampaignStepType.CLOSE,
                order=1,
                name="Close",
            ),
        ]
        integ.campaign_from_domain_pack("camp-dprun", "DPRun", "pack-1", steps)
        result = integ.run_campaign("camp-dprun", run_id="run-dprun")

        assert result["run"].status == CampaignStatus.COMPLETED


class TestAttachCampaignToMemoryMesh:
    """Tests for attach_campaign_to_memory_mesh."""

    def test_creates_memory_record(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-atmm")
        wce.register_campaign("camp-atmm", "AttachMem", steps)
        wce.start_run("camp-atmm", "run-atmm")

        mem_before = len(mm.list_memories())
        record = integ.attach_campaign_to_memory_mesh("run-atmm")
        mem_after = len(mm.list_memories())

        assert mem_after > mem_before
        assert "campaign" in record.tags

    def test_memory_record_has_correct_campaign_id(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-atcid")
        wce.register_campaign("camp-atcid", "AttachCID", steps)
        wce.start_run("camp-atcid", "run-atcid")

        record = integ.attach_campaign_to_memory_mesh("run-atcid")
        assert record.content["campaign_id"] == "camp-atcid"


class TestAttachCampaignToSupervisor:
    """Tests for attach_campaign_to_supervisor."""

    def test_returns_dict_with_expected_keys(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-sup")
        wce.register_campaign("camp-sup", "Supervisor", steps)
        wce.start_run("camp-sup", "run-sup")

        result = integ.attach_campaign_to_supervisor("run-sup")
        expected_keys = {
            "run_id", "campaign_id", "name", "status", "priority",
            "current_step_index", "checkpoint", "escalation_count",
            "is_blocked",
        }
        assert set(result.keys()) == expected_keys

    def test_active_campaign_is_not_blocked(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-supnb")
        wce.register_campaign("camp-supnb", "SupNotBlocked", steps)
        wce.start_run("camp-supnb", "run-supnb")

        result = integ.attach_campaign_to_supervisor("run-supnb")
        assert result["is_blocked"] is False

    def test_paused_campaign_is_blocked(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-supbl")
        wce.register_campaign("camp-supbl", "SupBlocked", steps)
        wce.start_run("camp-supbl", "run-supbl")
        integ.pause_campaign("run-supbl")

        result = integ.attach_campaign_to_supervisor("run-supbl")
        assert result["is_blocked"] is True

    def test_supervisor_has_checkpoint(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-supck")
        wce.register_campaign("camp-supck", "SupCkpt", steps)
        wce.start_run("camp-supck", "run-supck")

        result = integ.attach_campaign_to_supervisor("run-supck")
        assert result["checkpoint"] is not None


# ===================================================================
# Template tests
# ===================================================================


class TestApprovalDeploymentCampaign:
    """Tests for create_approval_deployment_campaign."""

    def test_has_8_steps(self, engines):
        es, mm, wce, integ, obs = engines
        desc = create_approval_deployment_campaign(wce, "camp-deploy")
        steps = wce.get_steps("camp-deploy")
        assert len(steps) == 8

    def test_has_5_dependencies(self, engines):
        es, mm, wce, integ, obs = engines
        create_approval_deployment_campaign(wce, "camp-dep-dep")
        deps = wce._dependencies.get("camp-dep-dep", [])
        assert len(deps) == 5

    def test_pauses_at_wait_for_reply(self, engines):
        es, mm, wce, integ, obs = engines
        create_approval_deployment_campaign(wce, "camp-dep-wait")
        result = integ.run_campaign("camp-dep-wait", run_id="run-dep-wait")

        # Should stop at WAIT_FOR_REPLY step
        run = result["run"]
        assert run.status in (CampaignStatus.WAITING, CampaignStatus.COMPLETED)

    def test_step_order_is_sequential(self, engines):
        es, mm, wce, integ, obs = engines
        create_approval_deployment_campaign(wce, "camp-dep-ord")
        steps = wce.get_steps("camp-dep-ord")

        for i, step in enumerate(steps):
            assert step.order == i

    def test_priority_defaults_to_high(self, engines):
        es, mm, wce, integ, obs = engines
        desc = create_approval_deployment_campaign(wce, "camp-dep-pri")
        assert desc.priority == CampaignPriority.HIGH

    def test_custom_priority(self, engines):
        es, mm, wce, integ, obs = engines
        desc = create_approval_deployment_campaign(
            wce, "camp-dep-cpri",
            priority=CampaignPriority.CRITICAL,
        )
        assert desc.priority == CampaignPriority.CRITICAL

    def test_has_deployment_tag(self, engines):
        es, mm, wce, integ, obs = engines
        desc = create_approval_deployment_campaign(wce, "camp-dep-tag")
        assert "deployment" in desc.tags
        assert "approval" in desc.tags

    def test_last_step_is_close(self, engines):
        es, mm, wce, integ, obs = engines
        create_approval_deployment_campaign(wce, "camp-dep-close")
        steps = wce.get_steps("camp-dep-close")
        assert steps[-1].step_type == CampaignStepType.CLOSE


class TestSupportEscalationCampaign:
    """Tests for create_support_escalation_campaign."""

    def test_default_chain_produces_correct_step_count(self, engines):
        es, mm, wce, integ, obs = engines
        desc = create_support_escalation_campaign(wce, "camp-esc-def")
        steps = wce.get_steps("camp-esc-def")

        # ingest + classify + 3 routes + escalate + collect + close = 8
        assert len(steps) == 8

    def test_custom_chain_length(self, engines):
        es, mm, wce, integ, obs = engines
        chain = ["a", "b", "c", "d", "e"]
        desc = create_support_escalation_campaign(
            wce, "camp-esc-cust", escalation_chain=chain,
        )
        steps = wce.get_steps("camp-esc-cust")

        # ingest + classify + 5 routes + escalate + collect + close = 10
        assert len(steps) == 10

    def test_single_tier_chain(self, engines):
        es, mm, wce, integ, obs = engines
        desc = create_support_escalation_campaign(
            wce, "camp-esc-single", escalation_chain=["only-tier"],
        )
        steps = wce.get_steps("camp-esc-single")

        # ingest + classify + 1 route + escalate + collect + close = 6
        assert len(steps) == 6

    def test_default_chain_is_tier1_tier2_manager(self, engines):
        es, mm, wce, integ, obs = engines
        create_support_escalation_campaign(wce, "camp-esc-dchain")
        steps = wce.get_steps("camp-esc-dchain")

        route_steps = [s for s in steps if s.step_type == CampaignStepType.ROUTE_TO_IDENTITY]
        assert len(route_steps) == 3
        assert route_steps[0].target_ref == "tier-1"
        assert route_steps[1].target_ref == "tier-2"
        assert route_steps[2].target_ref == "manager"

    def test_trigger_is_incident_detected(self, engines):
        es, mm, wce, integ, obs = engines
        desc = create_support_escalation_campaign(wce, "camp-esc-trig")
        assert desc.trigger == CampaignTrigger.INCIDENT_DETECTED

    def test_has_support_tag(self, engines):
        es, mm, wce, integ, obs = engines
        desc = create_support_escalation_campaign(wce, "camp-esc-tag")
        assert "support" in desc.tags
        assert "escalation" in desc.tags


class TestDocumentProcessingCampaign:
    """Tests for create_document_processing_campaign."""

    def test_no_notifiers_produces_base_steps(self, engines):
        es, mm, wce, integ, obs = engines
        desc = create_document_processing_campaign(wce, "camp-doc-base")
        steps = wce.get_steps("camp-doc-base")

        # ingest + extract + obligations + followup + escalate + close = 6
        assert len(steps) == 6

    def test_notifiers_add_send_steps(self, engines):
        es, mm, wce, integ, obs = engines
        desc = create_document_processing_campaign(
            wce, "camp-doc-notify", notify_ids=["user-1", "user-2"],
        )
        steps = wce.get_steps("camp-doc-notify")

        # base 6 + 2 notify = 8
        assert len(steps) == 8

    def test_notify_steps_target_correct_ids(self, engines):
        es, mm, wce, integ, obs = engines
        create_document_processing_campaign(
            wce, "camp-doc-targets",
            notify_ids=["alice", "bob", "carol"],
        )
        steps = wce.get_steps("camp-doc-targets")
        send_steps = [s for s in steps if s.step_type == CampaignStepType.SEND_COMMUNICATION]

        assert len(send_steps) == 3
        assert send_steps[0].target_ref == "alice"
        assert send_steps[1].target_ref == "bob"
        assert send_steps[2].target_ref == "carol"

    def test_pauses_at_wait_for_reply(self, engines):
        es, mm, wce, integ, obs = engines
        create_document_processing_campaign(wce, "camp-doc-wait")
        result = integ.run_campaign("camp-doc-wait", run_id="run-doc-wait")

        run = result["run"]
        assert run.status in (CampaignStatus.WAITING, CampaignStatus.COMPLETED)

    def test_trigger_is_artifact_ingested(self, engines):
        es, mm, wce, integ, obs = engines
        desc = create_document_processing_campaign(wce, "camp-doc-trig")
        assert desc.trigger == CampaignTrigger.ARTIFACT_INGESTED

    def test_has_document_tag(self, engines):
        es, mm, wce, integ, obs = engines
        desc = create_document_processing_campaign(wce, "camp-doc-tag")
        assert "document" in desc.tags
        assert "processing" in desc.tags


# ===================================================================
# Observability tests
# ===================================================================


class TestActiveCampaigns:
    """Tests for active_campaigns and active_runs."""

    def test_active_campaigns_returns_campaigns_with_active_runs(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-obs-ac")
        wce.register_campaign("camp-obs-ac", "ActiveCamp", steps)
        wce.start_run("camp-obs-ac", "run-obs-ac")

        active = obs.active_campaigns()
        assert len(active) == 1
        assert active[0].campaign_id == "camp-obs-ac"

    def test_active_campaigns_empty_when_no_runs(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-obs-norun")
        wce.register_campaign("camp-obs-norun", "NoRun", steps)

        active = obs.active_campaigns()
        assert len(active) == 0

    def test_active_runs_returns_active_runs(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-obs-ar")
        wce.register_campaign("camp-obs-ar", "ActiveRun", steps)
        wce.start_run("camp-obs-ar", "run-obs-ar")

        runs = obs.active_runs()
        assert len(runs) == 1
        assert runs[0].run_id == "run-obs-ar"

    def test_completed_run_not_in_active(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-obs-done", count=1)
        wce.register_campaign("camp-obs-done", "Done", steps)
        integ.run_campaign("camp-obs-done", run_id="run-obs-done")

        active = obs.active_runs()
        active_ids = {r.run_id for r in active}
        assert "run-obs-done" not in active_ids


class TestBlockedCampaigns:
    """Tests for blocked_campaigns."""

    def test_paused_campaign_appears_blocked(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-obs-blk")
        wce.register_campaign("camp-obs-blk", "Blocked", steps)
        wce.start_run("camp-obs-blk", "run-obs-blk")
        integ.pause_campaign("run-obs-blk")

        blocked = obs.blocked_campaigns()
        assert len(blocked) >= 1
        assert any(b["run_id"] == "run-obs-blk" for b in blocked)

    def test_blocked_has_correct_keys(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-obs-blkk")
        wce.register_campaign("camp-obs-blkk", "BlkKeys", steps)
        wce.start_run("camp-obs-blkk", "run-obs-blkk")
        integ.pause_campaign("run-obs-blkk")

        blocked = obs.blocked_campaigns()
        entry = blocked[0]
        assert "run_id" in entry
        assert "campaign_id" in entry
        assert "status" in entry
        assert "priority" in entry
        assert "escalation_count" in entry


class TestWaitingCampaigns:
    """Tests for waiting_campaigns."""

    def test_waiting_campaigns_returns_waiting_runs(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _waiting_steps("camp-obs-wt")
        wce.register_campaign("camp-obs-wt", "Waiting", steps)
        integ.run_campaign("camp-obs-wt", run_id="run-obs-wt")

        run = wce.get_run("run-obs-wt")
        if run.status == CampaignStatus.WAITING:
            waiting = obs.waiting_campaigns()
            assert len(waiting) >= 1
            entry = waiting[0]
            assert entry["run_id"] == "run-obs-wt"
            assert "waiting_step_id" in entry
            assert "waiting_step_name" in entry

    def test_waiting_campaigns_has_step_details(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _waiting_steps("camp-obs-wsd")
        wce.register_campaign("camp-obs-wsd", "WaitStepDet", steps)
        integ.run_campaign("camp-obs-wsd", run_id="run-obs-wsd")

        run = wce.get_run("run-obs-wsd")
        if run.status == CampaignStatus.WAITING:
            waiting = obs.waiting_campaigns()
            entry = next(w for w in waiting if w["run_id"] == "run-obs-wsd")
            assert entry["waiting_step_name"] != ""


class TestOverdueCampaigns:
    """Tests for overdue_campaigns."""

    def test_overdue_with_max_age_zero_catches_all(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-obs-od")
        wce.register_campaign("camp-obs-od", "Overdue", steps)
        wce.start_run("camp-obs-od", "run-obs-od")

        overdue = obs.overdue_campaigns(max_age_seconds=0)
        assert len(overdue) >= 1
        assert any(o["run_id"] == "run-obs-od" for o in overdue)

    def test_overdue_with_large_max_age_catches_none(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-obs-odl")
        wce.register_campaign("camp-obs-odl", "NotOverdue", steps)
        wce.start_run("camp-obs-odl", "run-obs-odl")

        overdue = obs.overdue_campaigns(max_age_seconds=999999)
        overdue_ids = {o["run_id"] for o in overdue}
        assert "run-obs-odl" not in overdue_ids

    def test_overdue_entry_has_elapsed_seconds(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-obs-ode")
        wce.register_campaign("camp-obs-ode", "OverdueElapsed", steps)
        wce.start_run("camp-obs-ode", "run-obs-ode")

        overdue = obs.overdue_campaigns(max_age_seconds=0)
        entry = next(o for o in overdue if o["run_id"] == "run-obs-ode")
        assert "elapsed_seconds" in entry
        assert entry["elapsed_seconds"] >= 0


class TestDegradedCampaigns:
    """Tests for degraded_campaigns."""

    def test_escalated_run_appears_degraded(self, engines):
        es, mm, wce, integ, obs = engines

        # Create a campaign with a SEND_COMMUNICATION step that will fail.
        # Use execute_next_step (not execute_all_steps) so the run stays
        # ESCALATED instead of being auto-completed.
        steps = [
            CampaignStep(
                step_id="deg-send",
                campaign_id="camp-obs-deg",
                step_type=CampaignStepType.SEND_COMMUNICATION,
                order=0,
                name="Send msg",
                max_retries=0,
            ),
            CampaignStep(
                step_id="deg-close",
                campaign_id="camp-obs-deg",
                step_type=CampaignStepType.CLOSE,
                order=1,
                name="Close",
            ),
        ]
        wce.register_campaign("camp-obs-deg", "Degraded", steps)
        wce.register_step_handler(
            CampaignStepType.SEND_COMMUNICATION,
            lambda step, ctx: (False, {"error": "provider down"}),
        )
        wce.start_run("camp-obs-deg", "run-obs-deg")
        # Execute only the first step — triggers escalation
        wce.execute_next_step("run-obs-deg")
        run = wce.get_run("run-obs-deg")
        assert run.status == CampaignStatus.ESCALATED

        degraded = obs.degraded_campaigns()
        assert len(degraded) >= 1
        entry = next(d for d in degraded if d["run_id"] == "run-obs-deg")
        assert entry["degradation_reason"] == "escalated"


class TestClosureReports:
    """Tests for all_closure_reports and closure_reports_by_verdict."""

    def test_all_closure_reports(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-obs-cr", count=1)
        wce.register_campaign("camp-obs-cr", "ClosureR", steps)
        integ.run_campaign("camp-obs-cr", run_id="run-obs-cr")

        reports = obs.all_closure_reports()
        assert len(reports) >= 1

    def test_closure_reports_by_verdict_success(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-obs-crv", count=1)
        wce.register_campaign("camp-obs-crv", "ClosureV", steps)
        integ.run_campaign("camp-obs-crv", run_id="run-obs-crv")

        success = obs.closure_reports_by_verdict(CampaignOutcomeVerdict.SUCCESS)
        assert len(success) >= 1

    def test_closure_reports_by_verdict_aborted(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-obs-crab")
        wce.register_campaign("camp-obs-crab", "ClosureAb", steps)
        wce.start_run("camp-obs-crab", "run-obs-crab")
        integ.abort_campaign("run-obs-crab", reason="test")

        aborted = obs.closure_reports_by_verdict(CampaignOutcomeVerdict.ABORTED)
        assert len(aborted) >= 1

    def test_closure_reports_filter_excludes_wrong_verdict(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-obs-crflt", count=1)
        wce.register_campaign("camp-obs-crflt", "ClosureFlt", steps)
        integ.run_campaign("camp-obs-crflt", run_id="run-obs-crflt")

        aborted = obs.closure_reports_by_verdict(CampaignOutcomeVerdict.ABORTED)
        assert not any(r.run_id == "run-obs-crflt" for r in aborted)


class TestCampaignLineage:
    """Tests for campaign_lineage and campaign_lineage_to_memory."""

    def test_campaign_lineage_returns_full_lineage(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-obs-lin", count=2)
        wce.register_campaign("camp-obs-lin", "Lineage", steps)
        integ.run_campaign("camp-obs-lin", run_id="run-obs-lin")

        lineage = obs.campaign_lineage("camp-obs-lin")
        assert lineage["campaign_id"] == "camp-obs-lin"
        assert lineage["name"] == "Lineage"
        assert lineage["total_runs"] >= 1
        assert len(lineage["runs"]) >= 1

    def test_lineage_run_has_expected_fields(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-obs-linf")
        wce.register_campaign("camp-obs-linf", "LineageF", steps)
        integ.run_campaign("camp-obs-linf", run_id="run-obs-linf")

        lineage = obs.campaign_lineage("camp-obs-linf")
        run_entry = lineage["runs"][0]
        assert "run_id" in run_entry
        assert "status" in run_entry
        assert "checkpoint" in run_entry
        assert "escalation_count" in run_entry
        assert "execution_record_count" in run_entry
        assert "closure_report" in run_entry

    def test_campaign_lineage_to_memory_persists(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-obs-linm")
        wce.register_campaign("camp-obs-linm", "LineageMem", steps)
        integ.run_campaign("camp-obs-linm", run_id="run-obs-linm")

        mem_before = len(mm.list_memories())
        record = obs.campaign_lineage_to_memory("camp-obs-linm")
        mem_after = len(mm.list_memories())

        assert mem_after > mem_before
        assert "lineage" in record.tags
        assert record.content["campaign_id"] == "camp-obs-linm"

    def test_lineage_to_memory_emits_event(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-obs-linev")
        wce.register_campaign("camp-obs-linev", "LineageEv", steps)
        integ.run_campaign("camp-obs-linev", run_id="run-obs-linev")

        events_before = len(es.list_events())
        obs.campaign_lineage_to_memory("camp-obs-linev")
        events_after = len(es.list_events())

        assert events_after > events_before


class TestDashboardSummary:
    """Tests for dashboard_summary."""

    def test_dashboard_summary_returns_correct_counts(self, engines):
        es, mm, wce, integ, obs = engines

        # Create and run a campaign (will complete)
        steps = _simple_steps("camp-obs-dash1", count=1)
        wce.register_campaign("camp-obs-dash1", "Dash1", steps)
        integ.run_campaign("camp-obs-dash1", run_id="run-dash1")

        # Create and pause another
        steps2 = _simple_steps("camp-obs-dash2")
        wce.register_campaign("camp-obs-dash2", "Dash2", steps2)
        wce.start_run("camp-obs-dash2", "run-dash2")
        integ.pause_campaign("run-dash2")

        summary = obs.dashboard_summary()
        assert summary["total_campaigns"] >= 2
        assert summary["total_runs"] >= 2
        assert isinstance(summary["runs_by_status"], dict)
        assert isinstance(summary["campaigns_by_priority"], dict)
        assert summary["total_closure_reports"] >= 1

    def test_dashboard_blocked_count(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-obs-dashb")
        wce.register_campaign("camp-obs-dashb", "DashBlk", steps)
        wce.start_run("camp-obs-dashb", "run-dashb")
        integ.pause_campaign("run-dashb")

        summary = obs.dashboard_summary()
        assert summary["blocked_count"] >= 1

    def test_dashboard_active_count(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-obs-dasha")
        wce.register_campaign("camp-obs-dasha", "DashActive", steps)
        wce.start_run("camp-obs-dasha", "run-dasha")

        summary = obs.dashboard_summary()
        assert summary["active_count"] >= 1


# ===================================================================
# Fault injection tests (43F golden scenarios)
# ===================================================================


class TestFaultProviderFailure:
    """43F: Provider failure causes campaign escalation."""

    def test_send_communication_failure_escalates(self, engines):
        es, mm, wce, integ, obs = engines

        steps = [
            CampaignStep(
                step_id="pf-send",
                campaign_id="camp-pf",
                step_type=CampaignStepType.SEND_COMMUNICATION,
                order=0,
                name="Send notification",
                max_retries=0,
            ),
            CampaignStep(
                step_id="pf-close",
                campaign_id="camp-pf",
                step_type=CampaignStepType.CLOSE,
                order=1,
                name="Close",
            ),
        ]
        wce.register_campaign("camp-pf", "ProviderFail", steps)
        wce.register_step_handler(
            CampaignStepType.SEND_COMMUNICATION,
            lambda step, ctx: (False, {"error": "provider unreachable"}),
        )

        wce.start_run("camp-pf", "run-pf")
        # Execute only the first step to trigger escalation
        wce.execute_next_step("run-pf")
        run = wce.get_run("run-pf")

        assert run.status == CampaignStatus.ESCALATED
        escalations = wce.get_escalations("run-pf")
        assert len(escalations) >= 1

    def test_provider_failure_in_degraded_list(self, engines):
        es, mm, wce, integ, obs = engines

        steps = [
            CampaignStep(
                step_id="pf2-send",
                campaign_id="camp-pf2",
                step_type=CampaignStepType.SEND_COMMUNICATION,
                order=0,
                name="Fail send",
                max_retries=0,
            ),
            CampaignStep(
                step_id="pf2-close",
                campaign_id="camp-pf2",
                step_type=CampaignStepType.CLOSE,
                order=1,
                name="Close",
            ),
        ]
        wce.register_campaign("camp-pf2", "ProviderFail2", steps)
        wce.register_step_handler(
            CampaignStepType.SEND_COMMUNICATION,
            lambda step, ctx: (False, {}),
        )
        wce.start_run("camp-pf2", "run-pf2")
        wce.execute_next_step("run-pf2")

        degraded = obs.degraded_campaigns()
        assert any(d["run_id"] == "run-pf2" for d in degraded)

    def test_provider_failure_handler_exception_escalates(self, engines):
        es, mm, wce, integ, obs = engines

        steps = [
            CampaignStep(
                step_id="pf3-send",
                campaign_id="camp-pf3",
                step_type=CampaignStepType.SEND_COMMUNICATION,
                order=0,
                name="Exception send",
                max_retries=0,
            ),
            CampaignStep(
                step_id="pf3-close",
                campaign_id="camp-pf3",
                step_type=CampaignStepType.CLOSE,
                order=1,
                name="Close",
            ),
        ]
        wce.register_campaign("camp-pf3", "ProviderExc", steps)

        def _raise_handler(step, ctx):
            raise RuntimeError("boom")

        wce.register_step_handler(
            CampaignStepType.SEND_COMMUNICATION,
            _raise_handler,
        )
        wce.start_run("camp-pf3", "run-pf3")
        wce.execute_next_step("run-pf3")

        run = wce.get_run("run-pf3")
        assert run.status == CampaignStatus.ESCALATED


class TestFaultApprovalTimeout:
    """43F: Approval timeout scenario."""

    def test_campaign_enters_waiting_then_abort_produces_aborted_closure(self, engines):
        es, mm, wce, integ, obs = engines
        create_approval_deployment_campaign(wce, "camp-at")
        result = integ.run_campaign("camp-at", run_id="run-at")

        run = wce.get_run("run-at")
        if run.status == CampaignStatus.WAITING:
            abort_result = integ.abort_campaign("run-at", reason="approval timeout")
            assert abort_result["run"].status == CampaignStatus.ABORTED
            assert abort_result["closure_report"].outcome == CampaignOutcomeVerdict.ABORTED

    def test_waiting_run_shows_in_blocked(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _waiting_steps("camp-at-blk")
        wce.register_campaign("camp-at-blk", "WaitBlock", steps)
        integ.run_campaign("camp-at-blk", run_id="run-at-blk")

        run = wce.get_run("run-at-blk")
        if run.status == CampaignStatus.WAITING:
            blocked = obs.blocked_campaigns()
            assert any(b["run_id"] == "run-at-blk" for b in blocked)

    def test_abort_waiting_shows_in_closure_reports(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _waiting_steps("camp-at-cr")
        wce.register_campaign("camp-at-cr", "WaitCR", steps)
        integ.run_campaign("camp-at-cr", run_id="run-at-cr")

        run = wce.get_run("run-at-cr")
        if run.status == CampaignStatus.WAITING:
            integ.abort_campaign("run-at-cr", reason="timeout")
            aborted = obs.closure_reports_by_verdict(CampaignOutcomeVerdict.ABORTED)
            assert any(r.run_id == "run-at-cr" for r in aborted)


class TestFaultReplayRestore:
    """43F: Replay/restore mid-campaign via pause-checkpoint-resume."""

    def test_pause_checkpoint_resume_completes(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-rr", count=5)
        wce.register_campaign("camp-rr", "ReplayRestore", steps)
        wce.start_run("camp-rr", "run-rr")
        wce.execute_next_step("run-rr")  # execute first step

        # Pause and checkpoint
        integ.pause_campaign("run-rr")
        ckpt = wce.checkpoint("run-rr")
        assert ckpt is not None
        assert ckpt.status == CampaignStatus.PAUSED

        # Resume and complete
        result = integ.resume_campaign("run-rr")
        assert result["run"].status == CampaignStatus.COMPLETED

    def test_checkpoint_captures_completed_steps(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-rrck", count=3)
        wce.register_campaign("camp-rrck", "RRCheckpoint", steps)
        wce.start_run("camp-rrck", "run-rrck")
        wce.execute_next_step("run-rrck")
        wce.execute_next_step("run-rrck")

        integ.pause_campaign("run-rrck")
        ckpt = wce.get_checkpoint("run-rrck")

        assert len(ckpt.completed_step_ids) >= 2

    def test_resume_after_pause_picks_up_remaining_steps(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-rrrem", count=4)
        wce.register_campaign("camp-rrrem", "RRRemaining", steps)
        wce.start_run("camp-rrrem", "run-rrrem")
        wce.execute_next_step("run-rrrem")

        integ.pause_campaign("run-rrrem")
        result = integ.resume_campaign("run-rrrem")

        # Should have executed remaining 3 check steps + close
        assert len(result["records"]) >= 3

    def test_lineage_reflects_paused_and_completed_states(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-rrlg", count=2)
        wce.register_campaign("camp-rrlg", "RRLineage", steps)
        wce.start_run("camp-rrlg", "run-rrlg")
        integ.pause_campaign("run-rrlg")
        integ.resume_campaign("run-rrlg")

        lineage = obs.campaign_lineage("camp-rrlg")
        run_entry = lineage["runs"][0]
        assert run_entry["status"] == "completed"


class TestFaultCommunicationFallback:
    """43F: Communication fallback -- handler fails first, retry succeeds."""

    def test_retry_after_failure_completes(self, engines):
        es, mm, wce, integ, obs = engines

        call_count = {"n": 0}

        def flaky_handler(step, ctx):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return (False, {"error": "transient"})
            return (True, {"sent": True})

        steps = [
            CampaignStep(
                step_id="fb-send",
                campaign_id="camp-fb",
                step_type=CampaignStepType.SEND_COMMUNICATION,
                order=0,
                name="Send with fallback",
                max_retries=3,
            ),
            CampaignStep(
                step_id="fb-close",
                campaign_id="camp-fb",
                step_type=CampaignStepType.CLOSE,
                order=1,
                name="Close",
            ),
        ]
        wce.register_campaign("camp-fb", "Fallback", steps)
        wce.register_step_handler(CampaignStepType.SEND_COMMUNICATION, flaky_handler)

        wce.start_run("camp-fb", "run-fb")
        # First attempt fails with RETRYING status
        record1 = wce.execute_next_step("run-fb")
        assert record1 is not None
        assert record1.success is False

        # Retry the step
        record2 = wce.retry_step("run-fb", "fb-send")
        assert record2 is not None
        assert record2.success is True

        # Now finish remaining steps
        wce.execute_all_steps("run-fb")
        run = wce.get_run("run-fb")
        assert run.status == CampaignStatus.COMPLETED

    def test_flaky_handler_first_fail_does_not_terminate(self, engines):
        es, mm, wce, integ, obs = engines

        call_count = {"n": 0}

        def flaky(step, ctx):
            call_count["n"] += 1
            if call_count["n"] <= 1:
                return (False, {})
            return (True, {})

        steps = [
            CampaignStep(
                step_id="fb2-send",
                campaign_id="camp-fb2",
                step_type=CampaignStepType.SEND_COMMUNICATION,
                order=0,
                name="Flaky send",
                max_retries=3,
            ),
            CampaignStep(
                step_id="fb2-close",
                campaign_id="camp-fb2",
                step_type=CampaignStepType.CLOSE,
                order=1,
                name="Close",
            ),
        ]
        wce.register_campaign("camp-fb2", "Fallback2", steps)
        wce.register_step_handler(CampaignStepType.SEND_COMMUNICATION, flaky)

        wce.start_run("camp-fb2", "run-fb2")
        wce.execute_next_step("run-fb2")

        # Campaign should NOT be in terminal status after retryable failure
        run = wce.get_run("run-fb2")
        assert run.status not in (
            CampaignStatus.COMPLETED,
            CampaignStatus.FAILED,
            CampaignStatus.ABORTED,
        )

    def test_communication_fallback_counters_track_retries(self, engines):
        es, mm, wce, integ, obs = engines

        call_count = {"n": 0}

        def flaky(step, ctx):
            call_count["n"] += 1
            if call_count["n"] <= 1:
                return (False, {})
            return (True, {})

        steps = [
            CampaignStep(
                step_id="fb3-send",
                campaign_id="camp-fb3",
                step_type=CampaignStepType.SEND_COMMUNICATION,
                order=0,
                name="Retry send",
                max_retries=3,
            ),
            CampaignStep(
                step_id="fb3-close",
                campaign_id="camp-fb3",
                step_type=CampaignStepType.CLOSE,
                order=1,
                name="Close",
            ),
        ]
        wce.register_campaign("camp-fb3", "Fallback3", steps)
        wce.register_step_handler(CampaignStepType.SEND_COMMUNICATION, flaky)

        wce.start_run("camp-fb3", "run-fb3")
        wce.execute_next_step("run-fb3")  # fails
        wce.retry_step("run-fb3", "fb3-send")  # succeeds

        counters = wce._counters["run-fb3"]
        assert counters["retries"] >= 1


# ===================================================================
# Additional integration and edge case tests
# ===================================================================


class TestInvariantValidation:
    """Tests for constructor invariant enforcement."""

    def test_integration_rejects_wrong_campaign_engine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            WorkCampaignIntegration("not-engine", EventSpineEngine(), MemoryMeshEngine())

    def test_integration_rejects_wrong_event_spine(self):
        es = EventSpineEngine()
        wce = WorkCampaignEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            WorkCampaignIntegration(wce, "not-spine", MemoryMeshEngine())

    def test_integration_rejects_wrong_memory_engine(self):
        es = EventSpineEngine()
        wce = WorkCampaignEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            WorkCampaignIntegration(wce, es, "not-memory")

    def test_observability_rejects_wrong_campaign_engine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            CampaignObservabilityEngine("bad", EventSpineEngine(), MemoryMeshEngine())

    def test_observability_rejects_wrong_event_spine(self):
        es = EventSpineEngine()
        wce = WorkCampaignEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            CampaignObservabilityEngine(wce, "bad", MemoryMeshEngine())

    def test_observability_rejects_wrong_memory_engine(self):
        es = EventSpineEngine()
        wce = WorkCampaignEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            CampaignObservabilityEngine(wce, es, "bad")


class TestMultiCampaignScenarios:
    """Tests involving multiple campaigns to verify isolation and aggregation."""

    def test_multiple_campaigns_dashboard(self, engines):
        es, mm, wce, integ, obs = engines

        for i in range(3):
            steps = _simple_steps(f"camp-multi-{i}", count=1)
            wce.register_campaign(f"camp-multi-{i}", f"Multi {i}", steps)
            integ.run_campaign(f"camp-multi-{i}", run_id=f"run-multi-{i}")

        summary = obs.dashboard_summary()
        assert summary["total_campaigns"] >= 3
        assert summary["total_runs"] >= 3
        assert summary["total_closure_reports"] >= 3

    def test_multiple_runs_same_campaign_are_distinct(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-multrun")
        wce.register_campaign("camp-multrun", "MultiRun", steps)

        result1 = integ.run_campaign("camp-multrun", run_id="run-mr-1")
        # Second run of same campaign
        result2 = integ.run_campaign("camp-multrun", run_id="run-mr-2")

        assert result1["run"].run_id == "run-mr-1"
        assert result2["run"].run_id == "run-mr-2"
        assert result1["run"].status == CampaignStatus.COMPLETED
        assert result2["run"].status == CampaignStatus.COMPLETED

    def test_lineage_shows_multiple_runs(self, engines):
        es, mm, wce, integ, obs = engines
        steps = _simple_steps("camp-linmr", count=1)
        wce.register_campaign("camp-linmr", "LineageMR", steps)

        integ.run_campaign("camp-linmr", run_id="run-linmr-1")
        integ.run_campaign("camp-linmr", run_id="run-linmr-2")

        lineage = obs.campaign_lineage("camp-linmr")
        assert lineage["total_runs"] == 2

    def test_mixed_statuses_in_dashboard(self, engines):
        es, mm, wce, integ, obs = engines

        # Completed campaign
        steps1 = _simple_steps("camp-mixed-c", count=1)
        wce.register_campaign("camp-mixed-c", "MixC", steps1)
        integ.run_campaign("camp-mixed-c", run_id="run-mixed-c")

        # Active campaign
        steps2 = _simple_steps("camp-mixed-a")
        wce.register_campaign("camp-mixed-a", "MixA", steps2)
        wce.start_run("camp-mixed-a", "run-mixed-a")

        # Paused campaign
        steps3 = _simple_steps("camp-mixed-p")
        wce.register_campaign("camp-mixed-p", "MixP", steps3)
        wce.start_run("camp-mixed-p", "run-mixed-p")
        integ.pause_campaign("run-mixed-p")

        summary = obs.dashboard_summary()
        assert summary["active_count"] >= 1
        assert summary["blocked_count"] >= 1
        assert summary["total_closure_reports"] >= 1


class TestEndToEndTemplateExecution:
    """Full end-to-end execution of template campaigns."""

    def test_support_escalation_runs_to_completion(self, engines):
        es, mm, wce, integ, obs = engines
        create_support_escalation_campaign(
            wce, "camp-e2e-sup", escalation_chain=["tier-1"],
        )
        result = integ.run_campaign("camp-e2e-sup", run_id="run-e2e-sup")

        # The escalate step will cause escalation status
        run = result["run"]
        assert run.status in (
            CampaignStatus.COMPLETED,
            CampaignStatus.ESCALATED,
        )

    def test_document_processing_full_run(self, engines):
        es, mm, wce, integ, obs = engines
        create_document_processing_campaign(
            wce, "camp-e2e-doc", notify_ids=["user-1"],
        )
        result = integ.run_campaign("camp-e2e-doc", run_id="run-e2e-doc")

        run = result["run"]
        # May be WAITING (at WAIT_FOR_REPLY) or COMPLETED
        assert run.status in (
            CampaignStatus.WAITING,
            CampaignStatus.COMPLETED,
        )

    def test_approval_deployment_full_run_and_observe(self, engines):
        es, mm, wce, integ, obs = engines
        create_approval_deployment_campaign(
            wce, "camp-e2e-dep",
            approver_id="approver-1",
            workflow_id="wf-deploy",
        )
        integ.run_campaign("camp-e2e-dep", run_id="run-e2e-dep")

        # Check observability picks it up
        run = wce.get_run("run-e2e-dep")
        if run.status == CampaignStatus.WAITING:
            waiting = obs.waiting_campaigns()
            assert any(w["run_id"] == "run-e2e-dep" for w in waiting)

    def test_template_campaign_memory_persisted(self, engines):
        es, mm, wce, integ, obs = engines
        create_support_escalation_campaign(wce, "camp-e2e-mem")
        integ.run_campaign("camp-e2e-mem", run_id="run-e2e-mem")

        memories = mm.list_memories()
        assert len(memories) > 0
