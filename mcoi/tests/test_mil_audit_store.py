"""Purpose: verify MIL audit records persist with hash-chain integrity.
Governance scope: persistence-only tests for MIL program audit payloads.
Dependencies: MIL contracts, policy contracts, static verifier, and MIL audit store.
Invariants: stored records round-trip; chain hashes validate; tampered payloads are not accepted as anchored.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.learning import LearningAdmissionDecision, LearningAdmissionStatus
from mcoi_runtime.contracts.mil import MILInstruction, MILOpcode, MILProgram
from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.contracts.replay import ReplayMode
from mcoi_runtime.core.mil_static_verifier import verify_mil_program
from mcoi_runtime.core.persisted_replay import PersistedReplayValidator
from mcoi_runtime.core.replay_engine import ReplayContext, ReplayVerdict
from mcoi_runtime.core.runbook import RunbookAdmissionStatus, RunbookLibrary
from mcoi_runtime.persistence.errors import CorruptedDataError
from mcoi_runtime.persistence.errors import PersistenceWriteError
from mcoi_runtime.persistence.mil_audit_store import MILAuditStore
from mcoi_runtime.persistence.replay_store import ReplayStore
from mcoi_runtime.persistence.trace_store import TraceStore


def _program() -> MILProgram:
    decision = PolicyDecision(
        "policy:allow:goal-1",
        "operator",
        "goal-1",
        PolicyDecisionStatus.ALLOW,
        (DecisionReason("allowed", "allow"),),
        "2026-05-06T12:00:00Z",
    )
    instructions = (
        MILInstruction("check", MILOpcode.CHECK_POLICY, "goal-1"),
        MILInstruction("call", MILOpcode.CALL_CAPABILITY, "shell_command", depends_on=("check",)),
        MILInstruction("verify", MILOpcode.VERIFY_EFFECT, "shell_command", depends_on=("call",)),
        MILInstruction("proof", MILOpcode.EMIT_PROOF, "goal-1", depends_on=("verify",)),
    )
    return MILProgram(
        "mil:goal-1:shell_command",
        "goal-1",
        decision,
        instructions,
        "2026-05-06T12:00:01Z",
    )


def test_append_round_trips_mil_audit_record(tmp_path) -> None:
    program = _program()
    verification = verify_mil_program(program)
    store = MILAuditStore(tmp_path)

    result = store.append(
        program=program,
        verification=verification,
        execution_id="exec-1",
        instruction_trace=("check:check_policy:goal-1", "call:call_capability:shell_command"),
        recorded_at="2026-05-06T12:00:02Z",
    )
    loaded = store.load(result.record.record_id)

    assert loaded.record_id == result.record.record_id
    assert loaded.program_id == program.program_id
    assert loaded.verification_passed is True
    assert loaded.instruction_trace[1] == "call:call_capability:shell_command"


def test_append_anchors_record_content_to_hash_chain(tmp_path) -> None:
    program = _program()
    verification = verify_mil_program(program)
    store = MILAuditStore(tmp_path)

    result = store.append(
        program=program,
        verification=verification,
        execution_id="exec-1",
        instruction_trace=("proof:emit_proof:goal-1",),
        recorded_at="2026-05-06T12:00:02Z",
    )
    chain_validation = store.chain.validate()

    assert chain_validation.valid is True
    assert store.validate_record(result.record.record_id) is True
    assert result.chain_entry.sequence_number == 0


def test_tampered_record_no_longer_matches_chain_anchor(tmp_path) -> None:
    program = _program()
    verification = verify_mil_program(program)
    store = MILAuditStore(tmp_path)
    result = store.append(
        program=program,
        verification=verification,
        execution_id="exec-1",
        instruction_trace=("proof:emit_proof:goal-1",),
        recorded_at="2026-05-06T12:00:02Z",
    )
    record_path = tmp_path / "records" / f"{result.record.record_id}.json"
    raw = record_path.read_text(encoding="utf-8")
    record_path.write_text(raw.replace("exec-1", "exec-2"), encoding="utf-8")

    assert store.chain.validate().valid is True
    assert store.validate_record(result.record.record_id) is False
    assert store.load(result.record.record_id).execution_id == "exec-2"


def test_duplicate_record_append_fails_closed(tmp_path) -> None:
    program = _program()
    verification = verify_mil_program(program)
    store = MILAuditStore(tmp_path)
    kwargs = {
        "program": program,
        "verification": verification,
        "execution_id": "exec-1",
        "instruction_trace": ("proof:emit_proof:goal-1",),
        "recorded_at": "2026-05-06T12:00:02Z",
    }

    first = store.append(**kwargs)
    with pytest.raises(PersistenceWriteError, match="already exists"):
        store.append(**kwargs)

    assert store.load(first.record.record_id).execution_id == "exec-1"
    assert store.chain.validate().valid is True


def test_replay_lookup_returns_observation_only_replay_record(tmp_path) -> None:
    program = _program()
    verification = verify_mil_program(program)
    store = MILAuditStore(tmp_path)
    result = store.append(
        program=program,
        verification=verification,
        execution_id="exec-1",
        instruction_trace=("proof:emit_proof:goal-1",),
        recorded_at="2026-05-06T12:00:02Z",
    )

    lookup = store.replay_lookup(result.record.record_id)

    assert lookup.record.record_id == result.record.record_id
    assert lookup.replay_record.mode is ReplayMode.OBSERVATION_ONLY
    assert lookup.replay_record.source_hash == result.chain_entry.chain_hash
    assert lookup.replay_record.metadata["program_id"] == program.program_id
    assert lookup.replay_record.trace_id == lookup.trace_entries[-1].trace_id


def test_replay_lookup_reconstructs_parent_linked_trace_spine(tmp_path) -> None:
    program = _program()
    verification = verify_mil_program(program)
    store = MILAuditStore(tmp_path)
    result = store.append(
        program=program,
        verification=verification,
        execution_id="exec-1",
        instruction_trace=("proof:emit_proof:goal-1",),
        recorded_at="2026-05-06T12:00:02Z",
    )

    lookup = store.replay_lookup(result.record.record_id)
    event_types = tuple(entry.event_type for entry in lookup.trace_entries)

    assert event_types == (
        "whqr_policy_decision",
        "policy_decision",
        "mil_program",
        "mil_static_verification",
        "dispatch_execution",
        "mil_audit_record",
    )
    assert lookup.trace_entries[0].parent_trace_id is None
    assert lookup.trace_entries[-1].parent_trace_id == lookup.trace_entries[-2].trace_id
    assert lookup.trace_entries[-1].metadata["chain_hash"] == result.chain_entry.chain_hash


def test_replay_lookup_fails_closed_when_record_is_unanchored(tmp_path) -> None:
    program = _program()
    verification = verify_mil_program(program)
    store = MILAuditStore(tmp_path)
    result = store.append(
        program=program,
        verification=verification,
        execution_id="exec-1",
        instruction_trace=("proof:emit_proof:goal-1",),
        recorded_at="2026-05-06T12:00:02Z",
    )
    chain_path = tmp_path / "chain" / f"{result.chain_entry.sequence_number:012d}.json"
    chain_path.unlink()

    with pytest.raises(CorruptedDataError, match="not anchored"):
        store.replay_lookup(result.record.record_id)


def test_persist_replay_bundle_validates_with_persisted_replay(tmp_path) -> None:
    program = _program()
    verification = verify_mil_program(program)
    audit_store = MILAuditStore(tmp_path / "mil-audit")
    trace_store = TraceStore(tmp_path / "traces")
    replay_store = ReplayStore(tmp_path / "replays")
    result = audit_store.append(
        program=program,
        verification=verification,
        execution_id="exec-1",
        instruction_trace=("proof:emit_proof:goal-1",),
        recorded_at="2026-05-06T12:00:02Z",
    )

    bundle = audit_store.persist_replay_bundle(
        result.record.record_id,
        trace_store=trace_store,
        replay_store=replay_store,
    )
    replay_result = PersistedReplayValidator(
        replay_store=replay_store,
        trace_store=trace_store,
    ).validate(
        bundle.replay_id,
        context=ReplayContext(
            state_hash=bundle.replay_record.state_hash,
            environment_digest=bundle.replay_record.environment_digest,
        ),
    )

    assert replay_result.validation.ready is True
    assert replay_result.validation.verdict is ReplayVerdict.MATCH
    assert replay_result.trace_found is True
    assert replay_result.trace_hash_matches is True


def test_mil_audit_replay_can_feed_runbook_admission(tmp_path) -> None:
    program = _program()
    verification = verify_mil_program(program)
    audit_store = MILAuditStore(tmp_path / "mil-audit")
    trace_store = TraceStore(tmp_path / "traces")
    replay_store = ReplayStore(tmp_path / "replays")
    result = audit_store.append(
        program=program,
        verification=verification,
        execution_id="exec-1",
        instruction_trace=("proof:emit_proof:goal-1",),
        recorded_at="2026-05-06T12:00:02Z",
    )
    bundle = audit_store.persist_replay_bundle(
        result.record.record_id,
        trace_store=trace_store,
        replay_store=replay_store,
    )
    library = RunbookLibrary(
        replay_validator=PersistedReplayValidator(
            replay_store=replay_store,
            trace_store=trace_store,
        ),
        clock=lambda: "2026-05-06T12:00:03Z",
    )
    learning = LearningAdmissionDecision(
        admission_id="learn-runbook-1",
        knowledge_id="runbook-mil-1",
        status=LearningAdmissionStatus.ADMIT,
        reasons=(DecisionReason("admit", "mil_audit_replay_verified"),),
        issued_at="2026-05-06T12:00:04Z",
    )

    admission = library.admit(
        runbook_id="runbook-mil-1",
        name="MIL governed shell run",
        description="Reusable governed procedure derived from MIL audit replay.",
        template={"action_type": "shell_command"},
        bindings_schema={"msg": "str"},
        replay_id=bundle.replay_id,
        execution_id=result.record.execution_id,
        verification_id=result.record.record_id,
        execution_succeeded=True,
        verification_passed=True,
        learning_admission=learning,
        context=ReplayContext(
            state_hash=bundle.replay_record.state_hash,
            environment_digest=bundle.replay_record.environment_digest,
        ),
    )

    assert admission.status is RunbookAdmissionStatus.ADMITTED
    assert admission.entry is not None
    assert admission.entry.provenance.replay_id == bundle.replay_id
    assert admission.entry.provenance.trace_id == bundle.replay_record.trace_id
