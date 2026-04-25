"""Purpose: verify runbook library admission from verified replayable runs.
Governance scope: procedural memory admission tests only.
Dependencies: runbook module, persisted replay, persistence stores.
Invariants:
  - Only verified, replay-matching runs get admitted.
  - Unverified, failed, or mismatched runs are rejected.
  - Provenance is preserved.
"""

from __future__ import annotations

from pathlib import Path
import sys

from mcoi_runtime.contracts.learning import LearningAdmissionDecision, LearningAdmissionStatus
from mcoi_runtime.contracts.policy import DecisionReason
from mcoi_runtime.contracts.trace import TraceEntry
from mcoi_runtime.core.persisted_replay import PersistedReplayValidator
from mcoi_runtime.core.replay_engine import (
    EffectControl,
    ReplayArtifact,
    ReplayContext,
    ReplayEffect,
    ReplayMode,
    ReplayRecord,
)
from mcoi_runtime.core.runbook import (
    RunbookAdmissionStatus,
    RunbookLibrary,
)
from mcoi_runtime.persistence import ReplayStore, TraceStore


def _make_replay_record(replay_id: str = "replay-1") -> ReplayRecord:
    return ReplayRecord(
        replay_id=replay_id,
        trace_id="trace-1",
        source_hash="source-hash-1",
        approved_effects=(
            ReplayEffect(
                effect_id="eff-1",
                control=EffectControl.CONTROLLED,
                artifact_id="art-1",
            ),
        ),
        blocked_effects=(),
        mode=ReplayMode.OBSERVATION_ONLY,
        recorded_at="2026-03-19T00:00:00+00:00",
        artifacts=(ReplayArtifact(artifact_id="art-1", payload_digest="d-1"),),
        state_hash="state-abc",
        environment_digest="env-xyz",
    )


def _make_trace() -> TraceEntry:
    return TraceEntry(
        trace_id="trace-1",
        parent_trace_id=None,
        event_type="execution",
        subject_id="subject-1",
        goal_id="goal-1",
        state_hash="source-hash-1",
        registry_hash="reg-1",
        timestamp="2026-03-19T00:00:00+00:00",
    )


def _setup(tmp_path: Path) -> tuple[RunbookLibrary, ReplayStore, TraceStore]:
    replay_store = ReplayStore(tmp_path / "replays")
    trace_store = TraceStore(tmp_path / "traces")
    validator = PersistedReplayValidator(
        replay_store=replay_store,
        trace_store=trace_store,
    )
    library = RunbookLibrary(replay_validator=validator)
    return library, replay_store, trace_store


_TEMPLATE = {
    "template_id": "tpl-1",
    "action_type": "shell_command",
    "command_argv": [sys.executable, "-c", "print('ok')"],
}
_BINDINGS = {"output": "string"}
_CONTEXT = ReplayContext(state_hash="state-abc", environment_digest="env-xyz")


def _admission(
    runbook_id: str = "rb-1",
    status: LearningAdmissionStatus = LearningAdmissionStatus.ADMIT,
) -> LearningAdmissionDecision:
    return LearningAdmissionDecision(
        admission_id=f"admission-{runbook_id}-{status.value}",
        knowledge_id=runbook_id,
        status=status,
        reasons=(DecisionReason(message="runbook learning admission"),),
        issued_at="2026-03-19T00:00:00+00:00",
    )


def test_admit_verified_run(tmp_path: Path) -> None:
    library, replay_store, trace_store = _setup(tmp_path)
    replay_store.save(_make_replay_record())
    trace_store.append(_make_trace())

    result = library.admit(
        runbook_id="rb-1",
        name="portable print test",
        description="runs a portable Python print command",
        template=_TEMPLATE,
        bindings_schema=_BINDINGS,
        replay_id="replay-1",
        execution_id="exec-1",
        verification_id="ver-1",
        execution_succeeded=True,
        verification_passed=True,
        learning_admission=_admission("rb-1"),
        context=_CONTEXT,
    )

    assert result.status is RunbookAdmissionStatus.ADMITTED
    assert result.entry is not None
    assert result.entry.provenance.execution_id == "exec-1"
    assert result.entry.provenance.verification_id == "ver-1"
    assert result.entry.provenance.replay_id == "replay-1"
    assert result.entry.provenance.trace_id == "trace-1"
    assert result.entry.provenance.learning_admission_id == "admission-rb-1-admit"
    assert library.size == 1


def test_reject_missing_learning_admission(tmp_path: Path) -> None:
    library, replay_store, trace_store = _setup(tmp_path)
    replay_store.save(_make_replay_record())
    trace_store.append(_make_trace())

    result = library.admit(
        runbook_id="rb-1",
        name="no learning admission",
        description="missing admission",
        template=_TEMPLATE,
        bindings_schema=_BINDINGS,
        replay_id="replay-1",
        execution_id="exec-1",
        verification_id="ver-1",
        execution_succeeded=True,
        verification_passed=True,
        context=_CONTEXT,
    )

    assert result.status is RunbookAdmissionStatus.REJECTED
    assert "learning_admission_missing" in result.reasons
    assert result.entry is None
    assert library.size == 0


def test_reject_non_admitted_learning_decision(tmp_path: Path) -> None:
    library, replay_store, trace_store = _setup(tmp_path)
    replay_store.save(_make_replay_record())
    trace_store.append(_make_trace())

    result = library.admit(
        runbook_id="rb-1",
        name="deferred learning admission",
        description="deferred admission",
        template=_TEMPLATE,
        bindings_schema=_BINDINGS,
        replay_id="replay-1",
        execution_id="exec-1",
        verification_id="ver-1",
        execution_succeeded=True,
        verification_passed=True,
        learning_admission=_admission("rb-1", LearningAdmissionStatus.DEFER),
        context=_CONTEXT,
    )

    assert result.status is RunbookAdmissionStatus.REJECTED
    assert "learning_admission_status:defer" in result.reasons
    assert result.entry is None
    assert library.size == 0


def test_reject_learning_admission_for_different_knowledge(tmp_path: Path) -> None:
    library, replay_store, trace_store = _setup(tmp_path)
    replay_store.save(_make_replay_record())
    trace_store.append(_make_trace())

    result = library.admit(
        runbook_id="rb-1",
        name="mismatched learning admission",
        description="mismatched admission",
        template=_TEMPLATE,
        bindings_schema=_BINDINGS,
        replay_id="replay-1",
        execution_id="exec-1",
        verification_id="ver-1",
        execution_succeeded=True,
        verification_passed=True,
        learning_admission=_admission("other-runbook"),
        context=_CONTEXT,
    )

    assert result.status is RunbookAdmissionStatus.REJECTED
    assert "learning_admission_knowledge_mismatch" in result.reasons
    assert result.entry is None
    assert library.size == 0


def test_reject_failed_execution(tmp_path: Path) -> None:
    library, replay_store, trace_store = _setup(tmp_path)
    replay_store.save(_make_replay_record())

    result = library.admit(
        runbook_id="rb-1",
        name="failed",
        description="failed run",
        template=_TEMPLATE,
        bindings_schema=_BINDINGS,
        replay_id="replay-1",
        execution_id="exec-1",
        verification_id="ver-1",
        execution_succeeded=False,
        verification_passed=True,
        learning_admission=_admission("rb-1"),
        context=_CONTEXT,
    )

    assert result.status is RunbookAdmissionStatus.REJECTED
    assert "execution_did_not_succeed" in result.reasons
    assert library.size == 0


def test_reject_failed_verification(tmp_path: Path) -> None:
    library, replay_store, trace_store = _setup(tmp_path)
    replay_store.save(_make_replay_record())

    result = library.admit(
        runbook_id="rb-1",
        name="unverified",
        description="unverified run",
        template=_TEMPLATE,
        bindings_schema=_BINDINGS,
        replay_id="replay-1",
        execution_id="exec-1",
        verification_id="ver-1",
        execution_succeeded=True,
        verification_passed=False,
        learning_admission=_admission("rb-1"),
        context=_CONTEXT,
    )

    assert result.status is RunbookAdmissionStatus.REJECTED
    assert "verification_did_not_pass" in result.reasons


def test_reject_replay_mismatch(tmp_path: Path) -> None:
    library, replay_store, _ = _setup(tmp_path)
    replay_store.save(_make_replay_record())

    # Supply different state_hash to trigger mismatch
    result = library.admit(
        runbook_id="rb-1",
        name="mismatched",
        description="state mismatch",
        template=_TEMPLATE,
        bindings_schema=_BINDINGS,
        replay_id="replay-1",
        execution_id="exec-1",
        verification_id="ver-1",
        execution_succeeded=True,
        verification_passed=True,
        learning_admission=_admission("rb-1"),
        context=ReplayContext(state_hash="DIFFERENT", environment_digest="env-xyz"),
    )

    assert result.status is RunbookAdmissionStatus.REJECTED
    assert any("replay" in r for r in result.reasons)


def test_reject_missing_replay(tmp_path: Path) -> None:
    library, _, _ = _setup(tmp_path)

    result = library.admit(
        runbook_id="rb-1",
        name="missing",
        description="no replay",
        template=_TEMPLATE,
        bindings_schema=_BINDINGS,
        replay_id="nonexistent",
        execution_id="exec-1",
        verification_id="ver-1",
        execution_succeeded=True,
        verification_passed=True,
        learning_admission=_admission("rb-1"),
    )

    assert result.status is RunbookAdmissionStatus.REJECTED
    assert any("replay_not_ready" in r for r in result.reasons)


def test_reject_duplicate_runbook_id(tmp_path: Path) -> None:
    library, replay_store, trace_store = _setup(tmp_path)
    replay_store.save(_make_replay_record())
    trace_store.append(_make_trace())

    library.admit(
        runbook_id="rb-1",
        name="first",
        description="first run",
        template=_TEMPLATE,
        bindings_schema=_BINDINGS,
        replay_id="replay-1",
        execution_id="exec-1",
        verification_id="ver-1",
        execution_succeeded=True,
        verification_passed=True,
        learning_admission=_admission("rb-1"),
        context=_CONTEXT,
    )

    result = library.admit(
        runbook_id="rb-1",
        name="duplicate",
        description="duplicate",
        template=_TEMPLATE,
        bindings_schema=_BINDINGS,
        replay_id="replay-1",
        execution_id="exec-2",
        verification_id="ver-2",
        execution_succeeded=True,
        verification_passed=True,
        learning_admission=_admission("rb-1"),
        context=_CONTEXT,
    )

    assert result.status is RunbookAdmissionStatus.REJECTED
    assert "runbook_id_already_exists" in result.reasons
    assert library.size == 1


def test_get_and_list_runbooks(tmp_path: Path) -> None:
    library, replay_store, trace_store = _setup(tmp_path)
    replay_store.save(_make_replay_record("replay-a"))
    replay_store.save(_make_replay_record("replay-b"))
    trace_store.append(_make_trace())

    library.admit(
        runbook_id="rb-a",
        name="alpha",
        description="first",
        template=_TEMPLATE,
        bindings_schema=_BINDINGS,
        replay_id="replay-a",
        execution_id="exec-a",
        verification_id="ver-a",
        execution_succeeded=True,
        verification_passed=True,
        learning_admission=_admission("rb-a"),
        context=_CONTEXT,
    )
    library.admit(
        runbook_id="rb-b",
        name="beta",
        description="second",
        template=_TEMPLATE,
        bindings_schema=_BINDINGS,
        replay_id="replay-b",
        execution_id="exec-b",
        verification_id="ver-b",
        execution_succeeded=True,
        verification_passed=True,
        learning_admission=_admission("rb-b"),
        context=_CONTEXT,
    )

    assert library.get("rb-a") is not None
    assert library.get("rb-b") is not None
    assert library.get("rb-c") is None

    listed = library.list_runbooks()
    assert len(listed) == 2
    assert listed[0].runbook_id == "rb-a"
    assert listed[1].runbook_id == "rb-b"


def test_runbook_carries_preconditions_postconditions(tmp_path: Path) -> None:
    library, replay_store, trace_store = _setup(tmp_path)
    replay_store.save(_make_replay_record())
    trace_store.append(_make_trace())

    result = library.admit(
        runbook_id="rb-1",
        name="guarded",
        description="has guards",
        template=_TEMPLATE,
        bindings_schema=_BINDINGS,
        replay_id="replay-1",
        execution_id="exec-1",
        verification_id="ver-1",
        execution_succeeded=True,
        verification_passed=True,
        learning_admission=_admission("rb-1"),
        context=_CONTEXT,
        preconditions=("file_exists:/tmp/input",),
        postconditions=("file_exists:/tmp/output",),
    )

    assert result.status is RunbookAdmissionStatus.ADMITTED
    assert result.entry.preconditions == ("file_exists:/tmp/input",)
    assert result.entry.postconditions == ("file_exists:/tmp/output",)
