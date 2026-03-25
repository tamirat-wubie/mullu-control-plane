"""Tests for organizational function runtime contracts."""

import json

import pytest

from mcoi_runtime.contracts.function import (
    CommunicationStyle,
    FunctionMetricsSnapshot,
    FunctionOutcomeRecord,
    FunctionPolicyBinding,
    FunctionQueueProfile,
    FunctionSlaProfile,
    FunctionStatus,
    FunctionType,
    ServiceFunctionTemplate,
)


TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-06-01T13:00:00+00:00"
TS3 = "2025-06-01T14:00:00+00:00"


# --- Helpers ---


def _template(**overrides):
    defaults = dict(
        function_id="func-001",
        name="Incident Response",
        function_type=FunctionType.INCIDENT_RESPONSE,
        description="Handles production incidents",
        created_at=TS,
    )
    defaults.update(overrides)
    return ServiceFunctionTemplate(**defaults)


def _binding(**overrides):
    defaults = dict(
        binding_id="bind-001",
        function_id="func-001",
        policy_pack_id="pack-001",
        autonomy_mode="supervised",
        review_required=True,
    )
    defaults.update(overrides)
    return FunctionPolicyBinding(**defaults)


def _sla(**overrides):
    defaults = dict(
        function_id="func-001",
        target_completion_minutes=60,
        approval_latency_minutes=10,
        escalation_threshold_minutes=45,
    )
    defaults.update(overrides)
    return FunctionSlaProfile(**defaults)


def _queue(**overrides):
    defaults = dict(
        function_id="func-001",
        team_id="team-001",
        default_role_id="role-001",
        communication_style=CommunicationStyle.STANDARD,
        max_concurrent_jobs=5,
    )
    defaults.update(overrides)
    return FunctionQueueProfile(**defaults)


def _outcome(**overrides):
    defaults = dict(
        outcome_id="out-001",
        function_id="func-001",
        job_id="job-001",
        completed=True,
        completion_minutes=30,
        escalated=False,
        drift_detected=False,
        recorded_at=TS,
    )
    defaults.update(overrides)
    return FunctionOutcomeRecord(**defaults)


def _metrics(**overrides):
    defaults = dict(
        function_id="func-001",
        period_start=TS,
        period_end=TS2,
        total_jobs=100,
        completed_jobs=90,
        failed_jobs=5,
        avg_completion_minutes=25.5,
        escalation_count=3,
        drift_count=2,
        captured_at=TS3,
    )
    defaults.update(overrides)
    return FunctionMetricsSnapshot(**defaults)


# === FunctionStatus enum ===


class TestFunctionStatus:
    def test_values(self):
        assert FunctionStatus.DRAFT == "draft"
        assert FunctionStatus.ACTIVE == "active"
        assert FunctionStatus.PAUSED == "paused"
        assert FunctionStatus.RETIRED == "retired"

    def test_all_members(self):
        assert len(FunctionStatus) == 4


# === FunctionType enum ===


class TestFunctionType:
    def test_values(self):
        assert FunctionType.INCIDENT_RESPONSE == "incident_response"
        assert FunctionType.DEPLOYMENT_REVIEW == "deployment_review"
        assert FunctionType.DOCUMENT_INTAKE == "document_intake"
        assert FunctionType.APPROVAL_DESK == "approval_desk"
        assert FunctionType.CODE_REVIEW == "code_review"
        assert FunctionType.CUSTOM == "custom"

    def test_all_members(self):
        assert len(FunctionType) == 6


# === CommunicationStyle enum ===


class TestCommunicationStyle:
    def test_values(self):
        assert CommunicationStyle.FORMAL == "formal"
        assert CommunicationStyle.STANDARD == "standard"
        assert CommunicationStyle.URGENT == "urgent"
        assert CommunicationStyle.SILENT == "silent"

    def test_all_members(self):
        assert len(CommunicationStyle) == 4


# === ServiceFunctionTemplate ===


class TestServiceFunctionTemplate:
    def test_valid_construction(self):
        t = _template()
        assert t.function_id == "func-001"
        assert t.name == "Incident Response"
        assert t.function_type == FunctionType.INCIDENT_RESPONSE
        assert t.description == "Handles production incidents"
        assert t.created_at == TS

    def test_frozen(self):
        t = _template()
        with pytest.raises(AttributeError):
            t.name = "other"

    def test_empty_function_id_rejected(self):
        with pytest.raises(ValueError, match="function_id"):
            _template(function_id="")

    def test_whitespace_function_id_rejected(self):
        with pytest.raises(ValueError, match="function_id"):
            _template(function_id="   ")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="name"):
            _template(name="")

    def test_invalid_function_type_rejected(self):
        with pytest.raises(ValueError, match="function_type"):
            _template(function_type="not_a_type")

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError, match="description"):
            _template(description="")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _template(created_at="not-a-date")

    def test_metadata_frozen(self):
        t = _template(metadata={"key": [1, 2]})
        assert t.metadata["key"] == (1, 2)
        with pytest.raises(TypeError):
            t.metadata["new"] = "value"

    def test_to_dict(self):
        t = _template()
        d = t.to_dict()
        assert d["function_id"] == "func-001"
        assert d["function_type"] == "incident_response"

    def test_to_json_roundtrip(self):
        t = _template()
        j = t.to_json()
        parsed = json.loads(j)
        assert parsed["function_id"] == "func-001"

    def test_all_function_types_accepted(self):
        for ft in FunctionType:
            t = _template(function_type=ft)
            assert t.function_type == ft


# === FunctionPolicyBinding ===


class TestFunctionPolicyBinding:
    def test_valid_construction(self):
        b = _binding()
        assert b.binding_id == "bind-001"
        assert b.function_id == "func-001"
        assert b.policy_pack_id == "pack-001"
        assert b.autonomy_mode == "supervised"
        assert b.review_required is True
        assert b.deployment_profile_id is None

    def test_frozen(self):
        b = _binding()
        with pytest.raises(AttributeError):
            b.review_required = False

    def test_empty_binding_id_rejected(self):
        with pytest.raises(ValueError, match="binding_id"):
            _binding(binding_id="")

    def test_empty_function_id_rejected(self):
        with pytest.raises(ValueError, match="function_id"):
            _binding(function_id="")

    def test_empty_policy_pack_id_rejected(self):
        with pytest.raises(ValueError, match="policy_pack_id"):
            _binding(policy_pack_id="")

    def test_empty_autonomy_mode_rejected(self):
        with pytest.raises(ValueError, match="autonomy_mode"):
            _binding(autonomy_mode="")

    def test_non_bool_review_required_rejected(self):
        with pytest.raises(ValueError, match="review_required"):
            _binding(review_required="yes")

    def test_optional_deployment_profile(self):
        b = _binding(deployment_profile_id="deploy-001")
        assert b.deployment_profile_id == "deploy-001"

    def test_empty_deployment_profile_rejected(self):
        with pytest.raises(ValueError, match="deployment_profile_id"):
            _binding(deployment_profile_id="")

    def test_to_dict(self):
        b = _binding()
        d = b.to_dict()
        assert d["review_required"] is True
        assert d["deployment_profile_id"] is None

    def test_to_json_roundtrip(self):
        b = _binding(deployment_profile_id="dp-001")
        parsed = json.loads(b.to_json())
        assert parsed["deployment_profile_id"] == "dp-001"


# === FunctionSlaProfile ===


class TestFunctionSlaProfile:
    def test_valid_construction(self):
        s = _sla()
        assert s.function_id == "func-001"
        assert s.target_completion_minutes == 60
        assert s.approval_latency_minutes == 10
        assert s.escalation_threshold_minutes == 45

    def test_frozen(self):
        s = _sla()
        with pytest.raises(AttributeError):
            s.target_completion_minutes = 120

    def test_empty_function_id_rejected(self):
        with pytest.raises(ValueError, match="function_id"):
            _sla(function_id="")

    def test_zero_target_completion_rejected(self):
        with pytest.raises(ValueError, match="target_completion_minutes"):
            _sla(target_completion_minutes=0)

    def test_negative_target_completion_rejected(self):
        with pytest.raises(ValueError, match="target_completion_minutes"):
            _sla(target_completion_minutes=-1)

    def test_zero_approval_latency_rejected(self):
        with pytest.raises(ValueError, match="approval_latency_minutes"):
            _sla(approval_latency_minutes=0)

    def test_zero_escalation_threshold_rejected(self):
        with pytest.raises(ValueError, match="escalation_threshold_minutes"):
            _sla(escalation_threshold_minutes=0)

    def test_escalation_exceeds_target_rejected(self):
        with pytest.raises(ValueError, match="escalation_threshold_minutes must not exceed"):
            _sla(target_completion_minutes=30, escalation_threshold_minutes=45)

    def test_escalation_equals_target_allowed(self):
        s = _sla(target_completion_minutes=45, escalation_threshold_minutes=45)
        assert s.escalation_threshold_minutes == 45

    def test_non_int_target_rejected(self):
        with pytest.raises(ValueError, match="target_completion_minutes"):
            _sla(target_completion_minutes=60.5)

    def test_to_dict(self):
        s = _sla()
        d = s.to_dict()
        assert d["target_completion_minutes"] == 60

    def test_to_json_roundtrip(self):
        s = _sla()
        parsed = json.loads(s.to_json())
        assert parsed["escalation_threshold_minutes"] == 45


# === FunctionQueueProfile ===


class TestFunctionQueueProfile:
    def test_valid_construction(self):
        q = _queue()
        assert q.function_id == "func-001"
        assert q.team_id == "team-001"
        assert q.default_role_id == "role-001"
        assert q.communication_style == CommunicationStyle.STANDARD
        assert q.max_concurrent_jobs == 5
        assert q.escalation_chain_id is None

    def test_frozen(self):
        q = _queue()
        with pytest.raises(AttributeError):
            q.max_concurrent_jobs = 10

    def test_empty_function_id_rejected(self):
        with pytest.raises(ValueError, match="function_id"):
            _queue(function_id="")

    def test_empty_team_id_rejected(self):
        with pytest.raises(ValueError, match="team_id"):
            _queue(team_id="")

    def test_empty_role_id_rejected(self):
        with pytest.raises(ValueError, match="default_role_id"):
            _queue(default_role_id="")

    def test_invalid_communication_style_rejected(self):
        with pytest.raises(ValueError, match="communication_style"):
            _queue(communication_style="whisper")

    def test_zero_max_concurrent_rejected(self):
        with pytest.raises(ValueError, match="max_concurrent_jobs"):
            _queue(max_concurrent_jobs=0)

    def test_negative_max_concurrent_rejected(self):
        with pytest.raises(ValueError, match="max_concurrent_jobs"):
            _queue(max_concurrent_jobs=-1)

    def test_optional_escalation_chain(self):
        q = _queue(escalation_chain_id="esc-001")
        assert q.escalation_chain_id == "esc-001"

    def test_empty_escalation_chain_rejected(self):
        with pytest.raises(ValueError, match="escalation_chain_id"):
            _queue(escalation_chain_id="")

    def test_all_communication_styles(self):
        for style in CommunicationStyle:
            q = _queue(communication_style=style)
            assert q.communication_style == style

    def test_to_dict(self):
        q = _queue()
        d = q.to_dict()
        assert d["communication_style"] == "standard"

    def test_to_json_roundtrip(self):
        q = _queue(escalation_chain_id="esc-002")
        parsed = json.loads(q.to_json())
        assert parsed["escalation_chain_id"] == "esc-002"


# === FunctionOutcomeRecord ===


class TestFunctionOutcomeRecord:
    def test_valid_construction(self):
        o = _outcome()
        assert o.outcome_id == "out-001"
        assert o.function_id == "func-001"
        assert o.job_id == "job-001"
        assert o.completed is True
        assert o.completion_minutes == 30
        assert o.escalated is False
        assert o.drift_detected is False
        assert o.recorded_at == TS

    def test_frozen(self):
        o = _outcome()
        with pytest.raises(AttributeError):
            o.completed = False

    def test_empty_outcome_id_rejected(self):
        with pytest.raises(ValueError, match="outcome_id"):
            _outcome(outcome_id="")

    def test_empty_function_id_rejected(self):
        with pytest.raises(ValueError, match="function_id"):
            _outcome(function_id="")

    def test_empty_job_id_rejected(self):
        with pytest.raises(ValueError, match="job_id"):
            _outcome(job_id="")

    def test_non_bool_completed_rejected(self):
        with pytest.raises(ValueError, match="completed"):
            _outcome(completed=1)

    def test_negative_completion_minutes_rejected(self):
        with pytest.raises(ValueError, match="completion_minutes"):
            _outcome(completion_minutes=-1)

    def test_zero_completion_minutes_allowed(self):
        o = _outcome(completion_minutes=0)
        assert o.completion_minutes == 0

    def test_non_bool_escalated_rejected(self):
        with pytest.raises(ValueError, match="escalated"):
            _outcome(escalated="yes")

    def test_non_bool_drift_detected_rejected(self):
        with pytest.raises(ValueError, match="drift_detected"):
            _outcome(drift_detected=0)

    def test_invalid_recorded_at_rejected(self):
        with pytest.raises(ValueError, match="recorded_at"):
            _outcome(recorded_at="bad-date")

    def test_escalated_outcome(self):
        o = _outcome(completed=False, escalated=True, drift_detected=True)
        assert o.completed is False
        assert o.escalated is True
        assert o.drift_detected is True

    def test_to_dict(self):
        o = _outcome()
        d = o.to_dict()
        assert d["completed"] is True
        assert d["escalated"] is False

    def test_to_json_roundtrip(self):
        o = _outcome()
        parsed = json.loads(o.to_json())
        assert parsed["completion_minutes"] == 30


# === FunctionMetricsSnapshot ===


class TestFunctionMetricsSnapshot:
    def test_valid_construction(self):
        m = _metrics()
        assert m.function_id == "func-001"
        assert m.period_start == TS
        assert m.period_end == TS2
        assert m.total_jobs == 100
        assert m.completed_jobs == 90
        assert m.failed_jobs == 5
        assert m.avg_completion_minutes == 25.5
        assert m.escalation_count == 3
        assert m.drift_count == 2
        assert m.captured_at == TS3

    def test_frozen(self):
        m = _metrics()
        with pytest.raises(AttributeError):
            m.total_jobs = 200

    def test_empty_function_id_rejected(self):
        with pytest.raises(ValueError, match="function_id"):
            _metrics(function_id="")

    def test_invalid_period_start_rejected(self):
        with pytest.raises(ValueError, match="period_start"):
            _metrics(period_start="bad")

    def test_invalid_period_end_rejected(self):
        with pytest.raises(ValueError, match="period_end"):
            _metrics(period_end="bad")

    def test_negative_total_jobs_rejected(self):
        with pytest.raises(ValueError, match="total_jobs"):
            _metrics(total_jobs=-1)

    def test_negative_completed_jobs_rejected(self):
        with pytest.raises(ValueError, match="completed_jobs"):
            _metrics(completed_jobs=-1)

    def test_negative_failed_jobs_rejected(self):
        with pytest.raises(ValueError, match="failed_jobs"):
            _metrics(failed_jobs=-1)

    def test_negative_avg_completion_rejected(self):
        with pytest.raises(ValueError, match="avg_completion_minutes"):
            _metrics(avg_completion_minutes=-0.1)

    def test_negative_escalation_count_rejected(self):
        with pytest.raises(ValueError, match="escalation_count"):
            _metrics(escalation_count=-1)

    def test_negative_drift_count_rejected(self):
        with pytest.raises(ValueError, match="drift_count"):
            _metrics(drift_count=-1)

    def test_invalid_captured_at_rejected(self):
        with pytest.raises(ValueError, match="captured_at"):
            _metrics(captured_at="bad")

    def test_zero_counts_allowed(self):
        m = _metrics(
            total_jobs=0,
            completed_jobs=0,
            failed_jobs=0,
            avg_completion_minutes=0.0,
            escalation_count=0,
            drift_count=0,
        )
        assert m.total_jobs == 0
        assert m.avg_completion_minutes == 0.0

    def test_int_avg_coerced_to_float(self):
        m = _metrics(avg_completion_minutes=25)
        assert isinstance(m.avg_completion_minutes, float)
        assert m.avg_completion_minutes == 25.0

    def test_to_dict(self):
        m = _metrics()
        d = m.to_dict()
        assert d["total_jobs"] == 100
        assert d["avg_completion_minutes"] == 25.5

    def test_to_json_roundtrip(self):
        m = _metrics()
        parsed = json.loads(m.to_json())
        assert parsed["escalation_count"] == 3
        assert parsed["drift_count"] == 2

    def test_non_int_total_jobs_rejected(self):
        with pytest.raises(ValueError, match="total_jobs"):
            _metrics(total_jobs=10.5)
