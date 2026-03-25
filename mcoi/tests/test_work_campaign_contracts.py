"""Tests for mcoi_runtime.contracts.work_campaign contract types.

Covers all 7 enums and 9 frozen dataclasses: enum member counts and values,
frozen immutability, freeze_value semantics, to_dict serialization, and
field validation (non-empty text, non-negative ints, booleans, severity,
datetime text).
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.work_campaign import (
    CampaignCheckpoint,
    CampaignClosureReport,
    CampaignDependency,
    CampaignDescriptor,
    CampaignEscalation,
    CampaignEscalationReason,
    CampaignExecutionRecord,
    CampaignOutcome,
    CampaignOutcomeVerdict,
    CampaignPriority,
    CampaignRun,
    CampaignStatus,
    CampaignStep,
    CampaignStepStatus,
    CampaignStepType,
    CampaignTrigger,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW_ISO = datetime.now(timezone.utc).isoformat()


def _make_dependency(**overrides):
    defaults = dict(
        dependency_id="dep-1",
        campaign_id="camp-1",
        source_step_id="step-a",
        target_step_id="step-b",
        required=True,
    )
    defaults.update(overrides)
    return CampaignDependency(**defaults)


def _make_step(**overrides):
    defaults = dict(
        step_id="step-1",
        campaign_id="camp-1",
        step_type=CampaignStepType.SEND_COMMUNICATION,
        status=CampaignStepStatus.PENDING,
        order=0,
        name="Send email",
    )
    defaults.update(overrides)
    return CampaignStep(**defaults)


def _make_checkpoint(**overrides):
    defaults = dict(
        checkpoint_id="chk-1",
        campaign_id="camp-1",
        run_id="run-1",
        status=CampaignStatus.ACTIVE,
        created_at=NOW_ISO,
    )
    defaults.update(overrides)
    return CampaignCheckpoint(**defaults)


def _make_escalation(**overrides):
    defaults = dict(
        escalation_id="esc-1",
        campaign_id="camp-1",
        run_id="run-1",
        reason=CampaignEscalationReason.STEP_FAILURE,
        severity="high",
        escalated_at=NOW_ISO,
    )
    defaults.update(overrides)
    return CampaignEscalation(**defaults)


def _make_execution_record(**overrides):
    defaults = dict(
        record_id="rec-1",
        campaign_id="camp-1",
        run_id="run-1",
        step_id="step-1",
        step_type=CampaignStepType.RUN_JOB,
        success=True,
        executed_at=NOW_ISO,
    )
    defaults.update(overrides)
    return CampaignExecutionRecord(**defaults)


def _make_outcome(**overrides):
    defaults = dict(
        outcome_id="out-1",
        campaign_id="camp-1",
        run_id="run-1",
        verdict=CampaignOutcomeVerdict.SUCCESS,
        recorded_at=NOW_ISO,
    )
    defaults.update(overrides)
    return CampaignOutcome(**defaults)


def _make_closure_report(**overrides):
    defaults = dict(
        report_id="rpt-1",
        campaign_id="camp-1",
        run_id="run-1",
        final_status=CampaignStatus.COMPLETED,
        outcome=CampaignOutcomeVerdict.SUCCESS,
        created_at=NOW_ISO,
    )
    defaults.update(overrides)
    return CampaignClosureReport(**defaults)


def _make_descriptor(**overrides):
    defaults = dict(
        campaign_id="camp-1",
        name="My Campaign",
        status=CampaignStatus.DRAFT,
        priority=CampaignPriority.NORMAL,
        trigger=CampaignTrigger.MANUAL,
        created_at=NOW_ISO,
    )
    defaults.update(overrides)
    return CampaignDescriptor(**defaults)


def _make_run(**overrides):
    defaults = dict(
        run_id="run-1",
        campaign_id="camp-1",
        status=CampaignStatus.PENDING,
    )
    defaults.update(overrides)
    return CampaignRun(**defaults)


# ===================================================================
# Enum tests
# ===================================================================


class TestCampaignStatusEnum:
    def test_member_count(self):
        assert len(CampaignStatus) == 10

    def test_values(self):
        expected = {
            "draft", "pending", "active", "paused", "waiting",
            "escalated", "completing", "completed", "failed", "aborted",
        }
        assert {m.value for m in CampaignStatus} == expected

    def test_lookup_by_value(self):
        assert CampaignStatus("active") is CampaignStatus.ACTIVE


class TestCampaignPriorityEnum:
    def test_member_count(self):
        assert len(CampaignPriority) == 5

    def test_values(self):
        expected = {"low", "normal", "high", "urgent", "critical"}
        assert {m.value for m in CampaignPriority} == expected


class TestCampaignTriggerEnum:
    def test_member_count(self):
        assert len(CampaignTrigger) == 10

    def test_values(self):
        expected = {
            "manual", "inbound_message", "artifact_ingested",
            "commitment_extracted", "obligation_created",
            "incident_detected", "scheduled", "domain_pack",
            "supervisor_tick", "escalation",
        }
        assert {m.value for m in CampaignTrigger} == expected


class TestCampaignStepTypeEnum:
    def test_member_count(self):
        assert len(CampaignStepType) == 14

    def test_values(self):
        expected = {
            "send_communication", "wait_for_reply", "ingest_artifact",
            "extract_commitments", "create_obligation", "run_workflow",
            "run_job", "call_connector", "route_to_identity",
            "request_approval", "apply_recovery", "check_condition",
            "escalate", "close",
        }
        assert {m.value for m in CampaignStepType} == expected


class TestCampaignStepStatusEnum:
    def test_member_count(self):
        assert len(CampaignStepStatus) == 7

    def test_values(self):
        expected = {
            "pending", "active", "waiting", "completed",
            "skipped", "failed", "retrying",
        }
        assert {m.value for m in CampaignStepStatus} == expected


class TestCampaignOutcomeVerdictEnum:
    def test_member_count(self):
        assert len(CampaignOutcomeVerdict) == 6

    def test_values(self):
        expected = {
            "success", "partial_success", "failure",
            "timeout", "aborted", "escalated",
        }
        assert {m.value for m in CampaignOutcomeVerdict} == expected


class TestCampaignEscalationReasonEnum:
    def test_member_count(self):
        assert len(CampaignEscalationReason) == 7

    def test_values(self):
        expected = {
            "step_failure", "deadline_exceeded", "approval_timeout",
            "connector_failure", "human_unavailable", "policy_violation",
            "manual",
        }
        assert {m.value for m in CampaignEscalationReason} == expected


# ===================================================================
# CampaignDependency
# ===================================================================


class TestCampaignDependencyConstruction:
    def test_valid_creation(self):
        dep = _make_dependency()
        assert dep.dependency_id == "dep-1"
        assert dep.required is True

    def test_empty_dependency_id_raises(self):
        with pytest.raises(ValueError):
            _make_dependency(dependency_id="")

    def test_empty_campaign_id_raises(self):
        with pytest.raises(ValueError):
            _make_dependency(campaign_id="")

    def test_empty_source_step_id_raises(self):
        with pytest.raises(ValueError):
            _make_dependency(source_step_id="")

    def test_empty_target_step_id_raises(self):
        with pytest.raises(ValueError):
            _make_dependency(target_step_id="")

    def test_required_must_be_bool(self):
        with pytest.raises(ValueError, match="required must be a boolean"):
            _make_dependency(required=1)


class TestCampaignDependencyFrozen:
    def test_cannot_mutate(self):
        dep = _make_dependency()
        with pytest.raises((TypeError, AttributeError)):
            dep.dependency_id = "other"


class TestCampaignDependencySerialization:
    def test_to_dict_roundtrip(self):
        dep = _make_dependency()
        d = dep.to_dict()
        assert d["dependency_id"] == "dep-1"
        assert d["required"] is True


# ===================================================================
# CampaignStep
# ===================================================================


class TestCampaignStepConstruction:
    def test_valid_creation(self):
        step = _make_step()
        assert step.step_id == "step-1"
        assert step.step_type is CampaignStepType.SEND_COMMUNICATION

    def test_empty_step_id_raises(self):
        with pytest.raises(ValueError):
            _make_step(step_id="")

    def test_empty_campaign_id_raises(self):
        with pytest.raises(ValueError):
            _make_step(campaign_id="")

    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            _make_step(name="")

    def test_invalid_step_type_raises(self):
        with pytest.raises(ValueError, match="step_type must be a CampaignStepType"):
            _make_step(step_type="not_a_type")

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError, match="status must be a CampaignStepStatus"):
            _make_step(status="bad")

    def test_negative_order_raises(self):
        with pytest.raises(ValueError):
            _make_step(order=-1)

    def test_negative_retry_count_raises(self):
        with pytest.raises(ValueError):
            _make_step(retry_count=-1)

    def test_negative_max_retries_raises(self):
        with pytest.raises(ValueError):
            _make_step(max_retries=-1)

    def test_negative_timeout_seconds_raises(self):
        with pytest.raises(ValueError):
            _make_step(timeout_seconds=-1)


class TestCampaignStepFrozen:
    def test_cannot_mutate_field(self):
        step = _make_step()
        with pytest.raises((TypeError, AttributeError)):
            step.step_id = "other"

    def test_input_payload_is_mapping_proxy(self):
        step = _make_step(input_payload={"key": "val"})
        assert isinstance(step.input_payload, MappingProxyType)

    def test_output_payload_is_mapping_proxy(self):
        step = _make_step(output_payload={"out": 1})
        assert isinstance(step.output_payload, MappingProxyType)

    def test_metadata_is_mapping_proxy(self):
        step = _make_step(metadata={"m": True})
        assert isinstance(step.metadata, MappingProxyType)

    def test_tags_is_tuple(self):
        step = _make_step(tags=["a", "b"])
        assert isinstance(step.tags, tuple)
        assert step.tags == ("a", "b")

    def test_input_payload_cannot_be_mutated(self):
        step = _make_step(input_payload={"k": "v"})
        with pytest.raises(TypeError):
            step.input_payload["k"] = "new"

    def test_metadata_cannot_be_mutated(self):
        step = _make_step(metadata={"k": "v"})
        with pytest.raises(TypeError):
            step.metadata["k"] = "new"


class TestCampaignStepSerialization:
    def test_to_dict_preserves_enum_objects(self):
        step = _make_step()
        d = step.to_dict()
        assert d["step_type"] is CampaignStepType.SEND_COMMUNICATION
        assert d["status"] is CampaignStepStatus.PENDING

    def test_to_dict_thaws_payload_to_dict(self):
        step = _make_step(input_payload={"a": 1})
        d = step.to_dict()
        assert isinstance(d["input_payload"], dict)

    def test_to_dict_thaws_tags_to_list(self):
        step = _make_step(tags=["x", "y"])
        d = step.to_dict()
        assert isinstance(d["tags"], list)
        assert d["tags"] == ["x", "y"]


# ===================================================================
# CampaignCheckpoint
# ===================================================================


class TestCampaignCheckpointConstruction:
    def test_valid_creation(self):
        cp = _make_checkpoint()
        assert cp.checkpoint_id == "chk-1"

    def test_empty_checkpoint_id_raises(self):
        with pytest.raises(ValueError):
            _make_checkpoint(checkpoint_id="")

    def test_empty_campaign_id_raises(self):
        with pytest.raises(ValueError):
            _make_checkpoint(campaign_id="")

    def test_empty_run_id_raises(self):
        with pytest.raises(ValueError):
            _make_checkpoint(run_id="")

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError, match="status must be a CampaignStatus"):
            _make_checkpoint(status="bad")

    def test_invalid_created_at_raises(self):
        with pytest.raises(ValueError):
            _make_checkpoint(created_at="not-a-date")

    def test_empty_created_at_raises(self):
        with pytest.raises(ValueError):
            _make_checkpoint(created_at="")


class TestCampaignCheckpointFrozen:
    def test_cannot_mutate(self):
        cp = _make_checkpoint()
        with pytest.raises((TypeError, AttributeError)):
            cp.checkpoint_id = "other"

    def test_completed_step_ids_is_tuple(self):
        cp = _make_checkpoint(completed_step_ids=["s1", "s2"])
        assert isinstance(cp.completed_step_ids, tuple)

    def test_failed_step_ids_is_tuple(self):
        cp = _make_checkpoint(failed_step_ids=["s3"])
        assert isinstance(cp.failed_step_ids, tuple)

    def test_step_outputs_is_mapping_proxy(self):
        cp = _make_checkpoint(step_outputs={"s1": {"result": 42}})
        assert isinstance(cp.step_outputs, MappingProxyType)

    def test_step_outputs_immutable(self):
        cp = _make_checkpoint(step_outputs={"s1": "done"})
        with pytest.raises(TypeError):
            cp.step_outputs["s1"] = "changed"


class TestCampaignCheckpointSerialization:
    def test_to_dict_preserves_status_enum(self):
        cp = _make_checkpoint()
        d = cp.to_dict()
        assert d["status"] is CampaignStatus.ACTIVE


# ===================================================================
# CampaignEscalation
# ===================================================================


class TestCampaignEscalationConstruction:
    def test_valid_creation(self):
        esc = _make_escalation()
        assert esc.severity == "high"

    def test_empty_escalation_id_raises(self):
        with pytest.raises(ValueError):
            _make_escalation(escalation_id="")

    def test_empty_campaign_id_raises(self):
        with pytest.raises(ValueError):
            _make_escalation(campaign_id="")

    def test_empty_run_id_raises(self):
        with pytest.raises(ValueError):
            _make_escalation(run_id="")

    def test_invalid_reason_raises(self):
        with pytest.raises(ValueError, match="reason must be a CampaignEscalationReason"):
            _make_escalation(reason="bad")

    def test_invalid_severity_raises(self):
        with pytest.raises(ValueError, match="severity must be low, medium, high, or critical"):
            _make_escalation(severity="extreme")

    @pytest.mark.parametrize("sev", ["low", "medium", "high", "critical"])
    def test_valid_severities(self, sev):
        esc = _make_escalation(severity=sev)
        assert esc.severity == sev

    def test_resolved_must_be_bool(self):
        with pytest.raises(ValueError, match="resolved must be a boolean"):
            _make_escalation(resolved=1)

    def test_invalid_escalated_at_raises(self):
        with pytest.raises(ValueError):
            _make_escalation(escalated_at="nope")

    def test_empty_escalated_at_raises(self):
        with pytest.raises(ValueError):
            _make_escalation(escalated_at="")


class TestCampaignEscalationFrozen:
    def test_cannot_mutate(self):
        esc = _make_escalation()
        with pytest.raises((TypeError, AttributeError)):
            esc.severity = "low"


class TestCampaignEscalationSerialization:
    def test_to_dict_preserves_reason_enum(self):
        esc = _make_escalation()
        d = esc.to_dict()
        assert d["reason"] is CampaignEscalationReason.STEP_FAILURE


# ===================================================================
# CampaignExecutionRecord
# ===================================================================


class TestCampaignExecutionRecordConstruction:
    def test_valid_creation(self):
        rec = _make_execution_record()
        assert rec.record_id == "rec-1"
        assert rec.success is True

    def test_empty_record_id_raises(self):
        with pytest.raises(ValueError):
            _make_execution_record(record_id="")

    def test_empty_campaign_id_raises(self):
        with pytest.raises(ValueError):
            _make_execution_record(campaign_id="")

    def test_empty_run_id_raises(self):
        with pytest.raises(ValueError):
            _make_execution_record(run_id="")

    def test_empty_step_id_raises(self):
        with pytest.raises(ValueError):
            _make_execution_record(step_id="")

    def test_invalid_step_type_raises(self):
        with pytest.raises(ValueError):
            _make_execution_record(step_type="bad")

    def test_success_must_be_bool(self):
        with pytest.raises(ValueError, match="success must be a boolean"):
            _make_execution_record(success=1)

    def test_invalid_executed_at_raises(self):
        with pytest.raises(ValueError):
            _make_execution_record(executed_at="bad")

    def test_empty_executed_at_raises(self):
        with pytest.raises(ValueError):
            _make_execution_record(executed_at="")


class TestCampaignExecutionRecordFrozen:
    def test_cannot_mutate(self):
        rec = _make_execution_record()
        with pytest.raises((TypeError, AttributeError)):
            rec.record_id = "other"

    def test_metadata_is_mapping_proxy(self):
        rec = _make_execution_record(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_metadata_immutable(self):
        rec = _make_execution_record(metadata={"k": "v"})
        with pytest.raises(TypeError):
            rec.metadata["k"] = "new"


class TestCampaignExecutionRecordSerialization:
    def test_to_dict_preserves_step_type_enum(self):
        rec = _make_execution_record()
        d = rec.to_dict()
        assert d["step_type"] is CampaignStepType.RUN_JOB

    def test_to_dict_thaws_metadata(self):
        rec = _make_execution_record(metadata={"a": 1})
        d = rec.to_dict()
        assert isinstance(d["metadata"], dict)


# ===================================================================
# CampaignOutcome
# ===================================================================


class TestCampaignOutcomeConstruction:
    def test_valid_creation(self):
        out = _make_outcome()
        assert out.outcome_id == "out-1"

    def test_empty_outcome_id_raises(self):
        with pytest.raises(ValueError):
            _make_outcome(outcome_id="")

    def test_empty_campaign_id_raises(self):
        with pytest.raises(ValueError):
            _make_outcome(campaign_id="")

    def test_empty_run_id_raises(self):
        with pytest.raises(ValueError):
            _make_outcome(run_id="")

    def test_invalid_verdict_raises(self):
        with pytest.raises(ValueError, match="verdict must be a CampaignOutcomeVerdict"):
            _make_outcome(verdict="bad")

    def test_negative_steps_completed_raises(self):
        with pytest.raises(ValueError):
            _make_outcome(steps_completed=-1)

    def test_negative_steps_failed_raises(self):
        with pytest.raises(ValueError):
            _make_outcome(steps_failed=-1)

    def test_negative_steps_skipped_raises(self):
        with pytest.raises(ValueError):
            _make_outcome(steps_skipped=-1)

    def test_negative_total_steps_raises(self):
        with pytest.raises(ValueError):
            _make_outcome(total_steps=-1)

    def test_invalid_recorded_at_raises(self):
        with pytest.raises(ValueError):
            _make_outcome(recorded_at="bad")


class TestCampaignOutcomeFrozen:
    def test_cannot_mutate(self):
        out = _make_outcome()
        with pytest.raises((TypeError, AttributeError)):
            out.outcome_id = "other"


class TestCampaignOutcomeSerialization:
    def test_to_dict_preserves_verdict_enum(self):
        out = _make_outcome()
        d = out.to_dict()
        assert d["verdict"] is CampaignOutcomeVerdict.SUCCESS


# ===================================================================
# CampaignClosureReport
# ===================================================================


class TestCampaignClosureReportConstruction:
    def test_valid_creation(self):
        rpt = _make_closure_report()
        assert rpt.report_id == "rpt-1"

    def test_empty_report_id_raises(self):
        with pytest.raises(ValueError):
            _make_closure_report(report_id="")

    def test_empty_campaign_id_raises(self):
        with pytest.raises(ValueError):
            _make_closure_report(campaign_id="")

    def test_empty_run_id_raises(self):
        with pytest.raises(ValueError):
            _make_closure_report(run_id="")

    def test_invalid_final_status_raises(self):
        with pytest.raises(ValueError, match="final_status must be a CampaignStatus"):
            _make_closure_report(final_status="bad")

    def test_invalid_outcome_raises(self):
        with pytest.raises(ValueError, match="outcome must be a CampaignOutcomeVerdict"):
            _make_closure_report(outcome="bad")

    def test_negative_total_steps_raises(self):
        with pytest.raises(ValueError):
            _make_closure_report(total_steps=-1)

    def test_negative_completed_steps_raises(self):
        with pytest.raises(ValueError):
            _make_closure_report(completed_steps=-1)

    def test_negative_failed_steps_raises(self):
        with pytest.raises(ValueError):
            _make_closure_report(failed_steps=-1)

    def test_negative_skipped_steps_raises(self):
        with pytest.raises(ValueError):
            _make_closure_report(skipped_steps=-1)

    def test_negative_escalation_count_raises(self):
        with pytest.raises(ValueError):
            _make_closure_report(escalation_count=-1)

    def test_negative_retry_count_raises(self):
        with pytest.raises(ValueError):
            _make_closure_report(retry_count=-1)

    def test_negative_obligations_created_raises(self):
        with pytest.raises(ValueError):
            _make_closure_report(obligations_created=-1)

    def test_negative_messages_sent_raises(self):
        with pytest.raises(ValueError):
            _make_closure_report(messages_sent=-1)

    def test_negative_artifacts_processed_raises(self):
        with pytest.raises(ValueError):
            _make_closure_report(artifacts_processed=-1)

    def test_negative_connector_calls_raises(self):
        with pytest.raises(ValueError):
            _make_closure_report(connector_calls=-1)

    def test_invalid_created_at_raises(self):
        with pytest.raises(ValueError):
            _make_closure_report(created_at="bad")


class TestCampaignClosureReportFrozen:
    def test_cannot_mutate(self):
        rpt = _make_closure_report()
        with pytest.raises((TypeError, AttributeError)):
            rpt.report_id = "other"

    def test_step_summaries_is_tuple(self):
        rpt = _make_closure_report(step_summaries=[{"name": "s1"}, {"name": "s2"}])
        assert isinstance(rpt.step_summaries, tuple)
        assert len(rpt.step_summaries) == 2

    def test_step_summaries_inner_dicts_frozen(self):
        rpt = _make_closure_report(step_summaries=[{"name": "s1"}])
        assert isinstance(rpt.step_summaries[0], MappingProxyType)

    def test_step_summaries_inner_immutable(self):
        rpt = _make_closure_report(step_summaries=[{"name": "s1"}])
        with pytest.raises(TypeError):
            rpt.step_summaries[0]["name"] = "changed"


class TestCampaignClosureReportSerialization:
    def test_to_dict_preserves_final_status_enum(self):
        rpt = _make_closure_report()
        d = rpt.to_dict()
        assert d["final_status"] is CampaignStatus.COMPLETED

    def test_to_dict_preserves_outcome_enum(self):
        rpt = _make_closure_report()
        d = rpt.to_dict()
        assert d["outcome"] is CampaignOutcomeVerdict.SUCCESS

    def test_to_dict_thaws_step_summaries_to_list(self):
        rpt = _make_closure_report(step_summaries=[{"n": 1}])
        d = rpt.to_dict()
        assert isinstance(d["step_summaries"], list)
        assert isinstance(d["step_summaries"][0], dict)


# ===================================================================
# CampaignDescriptor
# ===================================================================


class TestCampaignDescriptorConstruction:
    def test_valid_creation(self):
        desc = _make_descriptor()
        assert desc.campaign_id == "camp-1"
        assert desc.name == "My Campaign"

    def test_empty_campaign_id_raises(self):
        with pytest.raises(ValueError):
            _make_descriptor(campaign_id="")

    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            _make_descriptor(name="")

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError, match="status must be a CampaignStatus"):
            _make_descriptor(status="bad")

    def test_invalid_priority_raises(self):
        with pytest.raises(ValueError, match="priority must be a CampaignPriority"):
            _make_descriptor(priority="bad")

    def test_invalid_trigger_raises(self):
        with pytest.raises(ValueError, match="trigger must be a CampaignTrigger"):
            _make_descriptor(trigger="bad")

    def test_negative_step_count_raises(self):
        with pytest.raises(ValueError):
            _make_descriptor(step_count=-1)

    def test_invalid_created_at_raises(self):
        with pytest.raises(ValueError):
            _make_descriptor(created_at="bad")


class TestCampaignDescriptorFrozen:
    def test_cannot_mutate(self):
        desc = _make_descriptor()
        with pytest.raises((TypeError, AttributeError)):
            desc.campaign_id = "other"

    def test_tags_is_tuple(self):
        desc = _make_descriptor(tags=["a", "b"])
        assert isinstance(desc.tags, tuple)

    def test_metadata_is_mapping_proxy(self):
        desc = _make_descriptor(metadata={"k": "v"})
        assert isinstance(desc.metadata, MappingProxyType)

    def test_metadata_immutable(self):
        desc = _make_descriptor(metadata={"k": "v"})
        with pytest.raises(TypeError):
            desc.metadata["k"] = "new"


class TestCampaignDescriptorSerialization:
    def test_to_dict_preserves_status_enum(self):
        desc = _make_descriptor()
        d = desc.to_dict()
        assert d["status"] is CampaignStatus.DRAFT

    def test_to_dict_preserves_priority_enum(self):
        desc = _make_descriptor()
        d = desc.to_dict()
        assert d["priority"] is CampaignPriority.NORMAL

    def test_to_dict_preserves_trigger_enum(self):
        desc = _make_descriptor()
        d = desc.to_dict()
        assert d["trigger"] is CampaignTrigger.MANUAL

    def test_to_dict_thaws_tags(self):
        desc = _make_descriptor(tags=["x"])
        d = desc.to_dict()
        assert isinstance(d["tags"], list)

    def test_to_dict_thaws_metadata(self):
        desc = _make_descriptor(metadata={"k": 1})
        d = desc.to_dict()
        assert isinstance(d["metadata"], dict)


# ===================================================================
# CampaignRun
# ===================================================================


class TestCampaignRunConstruction:
    def test_valid_creation(self):
        run = _make_run()
        assert run.run_id == "run-1"

    def test_empty_run_id_raises(self):
        with pytest.raises(ValueError):
            _make_run(run_id="")

    def test_empty_campaign_id_raises(self):
        with pytest.raises(ValueError):
            _make_run(campaign_id="")

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError, match="status must be a CampaignStatus"):
            _make_run(status="bad")

    def test_negative_current_step_index_raises(self):
        with pytest.raises(ValueError):
            _make_run(current_step_index=-1)

    def test_negative_retry_count_raises(self):
        with pytest.raises(ValueError):
            _make_run(retry_count=-1)


class TestCampaignRunFrozen:
    def test_cannot_mutate(self):
        run = _make_run()
        with pytest.raises((TypeError, AttributeError)):
            run.run_id = "other"

    def test_metadata_is_mapping_proxy(self):
        run = _make_run(metadata={"k": "v"})
        assert isinstance(run.metadata, MappingProxyType)

    def test_metadata_immutable(self):
        run = _make_run(metadata={"k": "v"})
        with pytest.raises(TypeError):
            run.metadata["k"] = "new"


class TestCampaignRunSerialization:
    def test_to_dict_preserves_status_enum(self):
        run = _make_run()
        d = run.to_dict()
        assert d["status"] is CampaignStatus.PENDING

    def test_to_dict_thaws_metadata(self):
        run = _make_run(metadata={"k": 1})
        d = run.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_to_dict_contains_all_fields(self):
        run = _make_run()
        d = run.to_dict()
        expected_keys = {
            "run_id", "campaign_id", "status", "current_step_index",
            "started_at", "completed_at", "paused_at", "aborted_at",
            "retry_count", "checkpoint_id", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# Cross-cutting: nested freeze_value depth
# ===================================================================


class TestNestedFreezeDepth:
    def test_nested_dict_in_payload_frozen(self):
        step = _make_step(input_payload={"outer": {"inner": "val"}})
        assert isinstance(step.input_payload, MappingProxyType)
        assert isinstance(step.input_payload["outer"], MappingProxyType)

    def test_nested_list_in_payload_becomes_tuple(self):
        step = _make_step(input_payload={"items": [1, 2, 3]})
        assert isinstance(step.input_payload["items"], tuple)
        assert step.input_payload["items"] == (1, 2, 3)

    def test_nested_dict_in_step_outputs_frozen(self):
        cp = _make_checkpoint(step_outputs={"s1": {"data": [1, 2]}})
        inner = cp.step_outputs["s1"]
        assert isinstance(inner, MappingProxyType)
        assert isinstance(inner["data"], tuple)

    def test_deeply_nested_metadata_frozen(self):
        rec = _make_execution_record(metadata={"l1": {"l2": {"l3": "deep"}}})
        assert isinstance(rec.metadata["l1"], MappingProxyType)
        assert isinstance(rec.metadata["l1"]["l2"], MappingProxyType)
        assert rec.metadata["l1"]["l2"]["l3"] == "deep"


# ===================================================================
# Datetime validation
# ===================================================================


class TestDatetimeValidation:
    def test_valid_iso_utc(self):
        cp = _make_checkpoint(created_at=datetime.now(timezone.utc).isoformat())
        assert cp.created_at != ""

    def test_valid_iso_with_z_suffix(self):
        cp = _make_checkpoint(created_at="2025-01-15T10:30:00Z")
        assert cp.created_at == "2025-01-15T10:30:00Z"

    def test_garbage_string_rejected(self):
        with pytest.raises(ValueError):
            _make_checkpoint(created_at="not-a-datetime")

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError):
            _make_escalation(escalated_at="")

    def test_partial_date_rejected(self):
        with pytest.raises(ValueError):
            _make_outcome(recorded_at="2025-13-01")
