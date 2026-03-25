"""Edge case tests for Holistic Audit #5 fixes.

Covers:
- RoleDescriptor/WorkerProfile/WorkloadSnapshot removed misleading empty-tuple defaults
- WorkflowDescriptor created_at validation
- StageExecutionResult timestamp validation
- HandoffRecord handoff_at conditional validation
- GoalExecutionState duplicate sub-goal detection
- ContractRecord.to_dict() nested dataclass serialization
- KnowledgeRegistry immutable returns
- obligation_runtime module-level _TERMINAL_STATES
"""

from __future__ import annotations

import pytest

# =====================================================================
# 1. RoleDescriptor / WorkerProfile / WorkloadSnapshot — no empty defaults
# =====================================================================


class TestRoleDescriptorRequiredSkillsRequired:
    """required_skills has no default; omitting it raises TypeError."""

    def test_omitting_required_skills_raises(self) -> None:
        from mcoi_runtime.contracts.roles import RoleDescriptor

        with pytest.raises(TypeError):
            RoleDescriptor(role_id="r1", name="R", description="D")  # type: ignore[call-arg]

    def test_empty_required_skills_raises(self) -> None:
        from mcoi_runtime.contracts.roles import RoleDescriptor

        with pytest.raises(ValueError, match="required_skills"):
            RoleDescriptor(role_id="r1", name="R", description="D", required_skills=())

    def test_valid_required_skills(self) -> None:
        from mcoi_runtime.contracts.roles import RoleDescriptor

        rd = RoleDescriptor(role_id="r1", name="R", description="D", required_skills=("python",))
        assert rd.required_skills == ("python",)


class TestWorkerProfileRolesRequired:
    """roles has no default; omitting it raises TypeError."""

    def test_omitting_roles_raises(self) -> None:
        from mcoi_runtime.contracts.roles import WorkerProfile

        with pytest.raises(TypeError):
            WorkerProfile(worker_id="w1", name="W")  # type: ignore[call-arg]

    def test_empty_roles_raises(self) -> None:
        from mcoi_runtime.contracts.roles import WorkerProfile

        with pytest.raises(ValueError, match="roles"):
            WorkerProfile(worker_id="w1", name="W", roles=())

    def test_valid_roles(self) -> None:
        from mcoi_runtime.contracts.roles import WorkerProfile

        wp = WorkerProfile(worker_id="w1", name="W", roles=("admin",))
        assert wp.roles == ("admin",)


class TestWorkloadSnapshotCapacitiesRequired:
    """worker_capacities has no default; omitting it raises TypeError."""

    def test_omitting_worker_capacities_raises(self) -> None:
        from mcoi_runtime.contracts.roles import WorkloadSnapshot

        with pytest.raises(TypeError):
            WorkloadSnapshot(  # type: ignore[call-arg]
                snapshot_id="s1",
                team_id="t1",
                captured_at="2025-01-01T00:00:00+00:00",
            )

    def test_empty_worker_capacities_raises(self) -> None:
        from mcoi_runtime.contracts.roles import WorkloadSnapshot

        with pytest.raises(ValueError, match="worker_capacities"):
            WorkloadSnapshot(
                snapshot_id="s1",
                team_id="t1",
                worker_capacities=(),
                captured_at="2025-01-01T00:00:00+00:00",
            )


# =====================================================================
# 2. WorkflowDescriptor — created_at validation
# =====================================================================


class TestWorkflowDescriptorCreatedAt:
    """created_at is always validated as ISO datetime."""

    def _stage(self):
        from mcoi_runtime.contracts.workflow import StageType, WorkflowStage

        return WorkflowStage(stage_id="s1", stage_type=StageType.OBSERVATION)

    def test_empty_created_at_rejected(self) -> None:
        from mcoi_runtime.contracts.workflow import WorkflowDescriptor

        with pytest.raises(ValueError, match="created_at"):
            WorkflowDescriptor(
                workflow_id="w1", name="W", stages=(self._stage(),), created_at=""
            )

    def test_valid_created_at(self) -> None:
        from mcoi_runtime.contracts.workflow import WorkflowDescriptor

        wd = WorkflowDescriptor(
            workflow_id="w1",
            name="W",
            stages=(self._stage(),),
            created_at="2025-01-01T00:00:00+00:00",
        )
        assert wd.created_at == "2025-01-01T00:00:00+00:00"

    def test_invalid_created_at_rejected(self) -> None:
        from mcoi_runtime.contracts.workflow import WorkflowDescriptor

        with pytest.raises(ValueError, match="created_at"):
            WorkflowDescriptor(
                workflow_id="w1",
                name="W",
                stages=(self._stage(),),
                created_at="not-a-date",
            )


# =====================================================================
# 3. StageExecutionResult — timestamp validation
# =====================================================================


class TestStageExecutionResultTimestamps:
    """started_at and completed_at are validated when non-empty."""

    def test_empty_timestamps_rejected(self) -> None:
        from mcoi_runtime.contracts.workflow import StageExecutionResult, StageStatus

        with pytest.raises(ValueError):
            StageExecutionResult(
                stage_id="s1", status=StageStatus.COMPLETED,
                started_at="", completed_at="2025-01-01T00:00:00+00:00",
            )
        with pytest.raises(ValueError):
            StageExecutionResult(
                stage_id="s1", status=StageStatus.COMPLETED,
                started_at="2025-01-01T00:00:00+00:00", completed_at="",
            )

    def test_valid_timestamps(self) -> None:
        from mcoi_runtime.contracts.workflow import StageExecutionResult, StageStatus

        r = StageExecutionResult(
            stage_id="s1",
            status=StageStatus.COMPLETED,
            started_at="2025-01-01T00:00:00+00:00",
            completed_at="2025-01-01T00:01:00+00:00",
        )
        assert r.started_at == "2025-01-01T00:00:00+00:00"

    def test_invalid_started_at_rejected(self) -> None:
        from mcoi_runtime.contracts.workflow import StageExecutionResult, StageStatus

        with pytest.raises(ValueError, match="started_at"):
            StageExecutionResult(
                stage_id="s1", status=StageStatus.COMPLETED,
                started_at="bad", completed_at="2025-01-01T00:00:00+00:00",
            )

    def test_invalid_completed_at_rejected(self) -> None:
        from mcoi_runtime.contracts.workflow import StageExecutionResult, StageStatus

        with pytest.raises(ValueError, match="completed_at"):
            StageExecutionResult(
                stage_id="s1", status=StageStatus.COMPLETED,
                started_at="2025-01-01T00:00:00+00:00", completed_at="bad",
            )


# =====================================================================
# 4. HandoffRecord — handoff_at conditional validation
# =====================================================================


class TestHandoffRecordHandoffAt:
    """handoff_at is validated only when non-empty."""

    def test_empty_handoff_at_rejected(self) -> None:
        from mcoi_runtime.contracts.roles import HandoffReason, HandoffRecord

        with pytest.raises(ValueError):
            HandoffRecord(
                handoff_id="h1",
                job_id="j1",
                from_worker_id="w1",
                to_worker_id="w2",
                reason=HandoffReason.ESCALATION,
                handoff_at="",
            )

    def test_valid_handoff_at(self) -> None:
        from mcoi_runtime.contracts.roles import HandoffReason, HandoffRecord

        h = HandoffRecord(
            handoff_id="h1",
            job_id="j1",
            from_worker_id="w1",
            to_worker_id="w2",
            reason=HandoffReason.ESCALATION,
            handoff_at="2025-01-01T00:00:00+00:00",
        )
        assert h.handoff_at == "2025-01-01T00:00:00+00:00"

    def test_invalid_handoff_at_rejected(self) -> None:
        from mcoi_runtime.contracts.roles import HandoffReason, HandoffRecord

        with pytest.raises(ValueError, match="handoff_at"):
            HandoffRecord(
                handoff_id="h1",
                job_id="j1",
                from_worker_id="w1",
                to_worker_id="w2",
                reason=HandoffReason.ESCALATION,
                handoff_at="garbage",
            )


# =====================================================================
# 5. GoalExecutionState — duplicate sub-goal detection
# =====================================================================


class TestGoalExecutionStateDuplicates:
    """Duplicate or overlapping sub-goal IDs are rejected."""

    TS = "2025-01-01T00:00:00+00:00"

    def test_duplicate_completed_sub_goals(self) -> None:
        from mcoi_runtime.contracts.goal import GoalExecutionState, GoalStatus

        with pytest.raises(ValueError, match="completed_sub_goals.*duplicates"):
            GoalExecutionState(
                goal_id="g1",
                status=GoalStatus.EXECUTING,
                updated_at=self.TS,
                completed_sub_goals=("sg1", "sg1"),
            )

    def test_duplicate_failed_sub_goals(self) -> None:
        from mcoi_runtime.contracts.goal import GoalExecutionState, GoalStatus

        with pytest.raises(ValueError, match="failed_sub_goals.*duplicates"):
            GoalExecutionState(
                goal_id="g1",
                status=GoalStatus.FAILED,
                updated_at=self.TS,
                failed_sub_goals=("sg1", "sg1"),
            )

    def test_overlap_completed_and_failed(self) -> None:
        from mcoi_runtime.contracts.goal import GoalExecutionState, GoalStatus

        with pytest.raises(ValueError, match="both completed and failed"):
            GoalExecutionState(
                goal_id="g1",
                status=GoalStatus.FAILED,
                updated_at=self.TS,
                completed_sub_goals=("sg1", "sg2"),
                failed_sub_goals=("sg2", "sg3"),
            )

    def test_disjoint_completed_and_failed_ok(self) -> None:
        from mcoi_runtime.contracts.goal import GoalExecutionState, GoalStatus

        state = GoalExecutionState(
            goal_id="g1",
            status=GoalStatus.FAILED,
            updated_at=self.TS,
            completed_sub_goals=("sg1",),
            failed_sub_goals=("sg2",),
        )
        assert state.completed_sub_goals == ("sg1",)
        assert state.failed_sub_goals == ("sg2",)

    def test_empty_sub_goals_ok(self) -> None:
        from mcoi_runtime.contracts.goal import GoalExecutionState, GoalStatus

        state = GoalExecutionState(
            goal_id="g1",
            status=GoalStatus.ACCEPTED,
            updated_at=self.TS,
        )
        assert state.completed_sub_goals == ()
        assert state.failed_sub_goals == ()


# =====================================================================
# 6. ContractRecord.to_dict() — nested dataclass serialization
# =====================================================================


class TestContractRecordNestedSerialization:
    """to_dict() recursively serializes nested ContractRecord instances."""

    def test_nested_dataclass_serialized(self) -> None:
        from mcoi_runtime.contracts.roles import (
            HandoffReason,
            HandoffRecord,
            WorkerCapacity,
            WorkloadSnapshot,
        )

        cap = WorkerCapacity(
            worker_id="w1",
            max_concurrent=5,
            current_load=2,
            available_slots=3,
            updated_at="2025-01-01T00:00:00+00:00",
        )
        snap = WorkloadSnapshot(
            snapshot_id="s1",
            team_id="t1",
            worker_capacities=(cap,),
            captured_at="2025-01-01T00:00:00+00:00",
        )
        d = snap.to_dict()
        # worker_capacities should be a list of dicts, not a list of dataclass instances
        assert isinstance(d["worker_capacities"], list)
        assert isinstance(d["worker_capacities"][0], dict)
        assert d["worker_capacities"][0]["worker_id"] == "w1"

    def test_nested_to_json_roundtrip(self) -> None:
        import json

        from mcoi_runtime.contracts.roles import WorkerCapacity, WorkloadSnapshot

        cap = WorkerCapacity(
            worker_id="w1",
            max_concurrent=3,
            current_load=1,
            available_slots=2,
            updated_at="2025-01-01T00:00:00+00:00",
        )
        snap = WorkloadSnapshot(
            snapshot_id="s1",
            team_id="t1",
            worker_capacities=(cap,),
            captured_at="2025-01-01T00:00:00+00:00",
        )
        # Should not raise — nested dataclass is serializable
        parsed = json.loads(snap.to_json())
        assert parsed["worker_capacities"][0]["available_slots"] == 2

    def test_simple_contract_to_dict_unchanged(self) -> None:
        """Flat dataclass to_dict still works after nested fix."""
        from mcoi_runtime.contracts.roles import (
            AssignmentDecision,
        )

        ad = AssignmentDecision(
            decision_id="d1",
            job_id="j1",
            worker_id="w1",
            role_id="r1",
            reason="capacity",
            decided_at="2025-01-01T00:00:00+00:00",
        )
        d = ad.to_dict()
        assert d["decision_id"] == "d1"
        assert isinstance(d, dict)


# =====================================================================
# 7. KnowledgeRegistry — immutable returns
# =====================================================================


class TestKnowledgeRegistryImmutableReturns:
    """list_by_lifecycle and list_by_source return tuples, not lists."""

    def _registry(self):
        from mcoi_runtime.contracts.knowledge_ingestion import (
            ConfidenceLevel,
            KnowledgeLifecycle,
            KnowledgeSource,
            KnowledgeSourceType,
            ProcedureCandidate,
            ProcedureStep,
        )
        from mcoi_runtime.core.knowledge import KnowledgeRegistry

        clk = lambda: "2025-01-01T00:00:00+00:00"
        reg = KnowledgeRegistry(clock=clk)

        artifact = ProcedureCandidate(
            candidate_id="pc1",
            source_id="src1",
            name="test",
            steps=(ProcedureStep(step_order=0, description="do"),),
            missing_parts=(),
            confidence=ConfidenceLevel(
                value=0.9, reason="test", assessed_at=clk()
            ),
            created_at=clk(),
        )
        reg.register(artifact)
        return reg

    def test_list_by_lifecycle_returns_tuple(self) -> None:
        from mcoi_runtime.contracts.knowledge_ingestion import KnowledgeLifecycle

        reg = self._registry()
        result = reg.list_by_lifecycle(KnowledgeLifecycle.CANDIDATE)
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_list_by_source_returns_tuple(self) -> None:
        reg = self._registry()
        result = reg.list_by_source("src1")
        assert isinstance(result, tuple)
        assert len(result) == 1


# =====================================================================
# 8. obligation_runtime module-level _TERMINAL_STATES
# =====================================================================


class TestObligationTerminalStatesModuleLevel:
    """Module-level _TERMINAL_STATES is accessible and consistent."""

    def test_terminal_states_accessible(self) -> None:
        from mcoi_runtime.core.obligation_runtime import _TERMINAL_STATES
        from mcoi_runtime.contracts.obligation import ObligationState

        assert ObligationState.COMPLETED in _TERMINAL_STATES
        assert ObligationState.EXPIRED in _TERMINAL_STATES
        assert ObligationState.CANCELLED in _TERMINAL_STATES
        assert len(_TERMINAL_STATES) == 3

    def test_non_terminal_not_in_set(self) -> None:
        from mcoi_runtime.core.obligation_runtime import _TERMINAL_STATES
        from mcoi_runtime.contracts.obligation import ObligationState

        assert ObligationState.PENDING not in _TERMINAL_STATES
        assert ObligationState.ACTIVE not in _TERMINAL_STATES
        assert ObligationState.ESCALATED not in _TERMINAL_STATES
