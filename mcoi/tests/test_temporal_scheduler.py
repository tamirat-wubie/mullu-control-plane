"""Purpose: tests for the in-memory TemporalSchedulerEngine.
Governance scope: frozen-clock scheduling, leases, wake-time temporal policy,
    closure receipts, and bounded denial reasons.
Dependencies: temporal_scheduler, temporal_runtime, event_spine.
Invariants:
  - Future actions are not due.
  - Leases prevent duplicate due dispatch.
  - Wake-time policy is re-checked.
  - Expired and missed actions emit receipts.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.temporal_runtime import (
    TemporalActionRequest,
    TemporalPolicyVerdict,
    TemporalSkillPlan,
    TemporalSkillStage,
    TemporalSkillStageType,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.temporal_runtime import TemporalRuntimeEngine
from mcoi_runtime.core.temporal_scheduler import (
    ScheduleDecisionVerdict,
    ScheduledActionState,
    TemporalSchedulerEngine,
)


class MutableClock:
    def __init__(self, now: str) -> None:
        self.now = now

    def __call__(self) -> str:
        return self.now

    def set(self, now: str) -> None:
        self.now = now


def _engine(clock: MutableClock, *, skill_stage_provider: object | None = None) -> TemporalSchedulerEngine:
    temporal = TemporalRuntimeEngine(EventSpineEngine(), clock=clock)
    return TemporalSchedulerEngine(temporal, clock=clock, skill_stage_provider=skill_stage_provider)


def _action(
    *,
    execute_at: str = "2026-05-04T14:00:00+00:00",
    temporal_phrase: str = "",
    temporal_phrase_locale: str = "en",
    temporal_phrase_policy: str = "ignore",
    metadata: dict[str, object] | None = None,
    expires_at: str = "",
    approval_expires_at: str = "",
    evidence_fresh_until: str = "",
    retry_after: str = "",
    max_attempts: int = 0,
    attempt_count: int = 0,
    skill_plan: TemporalSkillPlan | None = None,
) -> TemporalActionRequest:
    return TemporalActionRequest(
        action_id="act-1",
        tenant_id="tenant-a",
        actor_id="user-a",
        action_type="reminder",
        requested_at="2026-05-04T13:00:00+00:00",
        execute_at=execute_at,
        temporal_phrase=temporal_phrase,
        temporal_phrase_locale=temporal_phrase_locale,
        temporal_phrase_policy=temporal_phrase_policy,
        expires_at=expires_at,
        approval_expires_at=approval_expires_at,
        evidence_fresh_until=evidence_fresh_until,
        retry_after=retry_after,
        max_attempts=max_attempts,
        attempt_count=attempt_count,
        skill_plan=skill_plan,
        metadata=metadata or {},
    )


def _valid_skill_plan() -> TemporalSkillPlan:
    return TemporalSkillPlan(
        plan_id="plan-1",
        terminal_condition="final_receipt",
        stages=(
            TemporalSkillStage(
                stage_id="observe",
                stage_type=TemporalSkillStageType.OBSERVE,
                output_keys=("observation",),
            ),
            TemporalSkillStage(
                stage_id="approve",
                stage_type=TemporalSkillStageType.APPROVAL,
                predecessor_ids=("observe",),
                input_bindings={"observation": "observe.observation"},
                output_keys=("approval",),
                requires_operator_approval=True,
            ),
            TemporalSkillStage(
                stage_id="execute",
                stage_type=TemporalSkillStageType.EFFECT,
                predecessor_ids=("approve",),
                input_bindings={"approval": "approve.approval"},
                output_keys=("final_receipt",),
                rollback_required=True,
            ),
        ),
    )


class RecordingSkillStageProvider:
    """Deterministic test provider for temporal skill plan execution."""

    def __init__(self, outputs_by_stage: dict[str, dict[str, object]]) -> None:
        self.outputs_by_stage = outputs_by_stage
        self.calls: list[tuple[str, dict[str, object]]] = []

    def execute_stage(
        self,
        plan: TemporalSkillPlan,
        stage: TemporalSkillStage,
        input_values: dict[str, object],
        executed_at: str,
    ) -> dict[str, object]:
        self.calls.append((stage.stage_id, dict(input_values)))
        return dict(self.outputs_by_stage.get(stage.stage_id, {}))


def test_register_requires_execute_at() -> None:
    clock = MutableClock("2026-05-04T13:00:00+00:00")
    scheduler = _engine(clock)
    action = _action(execute_at="")

    with pytest.raises(RuntimeCoreInvariantError, match="execute_at is required"):
        scheduler.register("sched-1", action)
    assert scheduler.action_count == 0
    assert scheduler.receipt_count == 0


def test_temporal_phrase_english_relative_resolves_before_registration() -> None:
    clock = MutableClock("2026-05-04T13:00:00+00:00")
    scheduler = _engine(clock)
    action = _action(
        execute_at="",
        temporal_phrase="in 2 hours",
        temporal_phrase_policy="require_exact",
    )

    scheduled = scheduler.register("sched-1", action)

    assert scheduled.execute_at == "2026-05-04T15:00:00+00:00"
    assert scheduled.action.metadata["temporal_phrase_admission_verdict"] == "exact"
    assert scheduled.action.metadata["temporal_phrase_resolved_execute_at"] == "2026-05-04T15:00:00+00:00"


def test_temporal_phrase_ignore_policy_does_not_supply_execute_at() -> None:
    clock = MutableClock("2026-05-04T13:00:00+00:00")
    scheduler = _engine(clock)
    action = _action(
        execute_at="",
        temporal_phrase="in 2 hours",
        temporal_phrase_policy="ignore",
    )

    with pytest.raises(RuntimeCoreInvariantError, match="execute_at is required"):
        scheduler.register("sched-1", action)
    assert scheduler.action_count == 0
    assert scheduler.receipt_count == 0


def test_temporal_phrase_ignore_policy_preserves_explicit_execute_at() -> None:
    clock = MutableClock("2026-05-04T13:00:00+00:00")
    scheduler = _engine(clock)
    action = _action(
        execute_at="2026-05-04T16:00:00+00:00",
        temporal_phrase="in 2 hours",
        temporal_phrase_policy="ignore",
    )

    scheduled = scheduler.register("sched-1", action)

    assert scheduled.execute_at == "2026-05-04T16:00:00+00:00"
    assert "temporal_phrase_admission_verdict" not in scheduled.action.metadata
    assert "temporal_phrase_resolved_execute_at" not in scheduled.action.metadata


def test_temporal_phrase_dutch_wall_time_resolves_before_registration() -> None:
    clock = MutableClock("2026-05-04T13:00:00+00:00")
    scheduler = _engine(clock)
    action = _action(
        execute_at="",
        temporal_phrase="morgen om 09:30 UTC",
        temporal_phrase_locale="nl-BE",
        temporal_phrase_policy="require_exact",
    )

    scheduled = scheduler.register("sched-1", action)

    assert scheduled.execute_at == "2026-05-05T09:30:00+00:00"
    assert scheduled.action.metadata["temporal_phrase_admission_verdict"] == "exact"
    assert scheduled.action.metadata["temporal_phrase_admission_reason"] == "temporal_phrase_exact_utc_wall_time"


def test_temporal_phrase_swedish_next_weekday_local_resolves_before_registration() -> None:
    clock = MutableClock("2026-05-04T13:00:00+00:00")
    scheduler = _engine(clock)
    action = _action(
        execute_at="",
        temporal_phrase="nasta mandag klockan 08:15 local",
        temporal_phrase_locale="sv",
        temporal_phrase_policy="require_exact",
        metadata={"original_timezone": "America/New_York"},
    )

    scheduled = scheduler.register("sched-1", action)

    assert scheduled.execute_at == "2026-05-11T12:15:00+00:00"
    assert scheduled.action.metadata["temporal_phrase_admission_verdict"] == "exact"
    assert scheduled.action.metadata["temporal_phrase_admission_reason"] == "temporal_phrase_exact_local_weekday_wall_time"


@pytest.mark.parametrize(
    ("phrase", "locale"),
    (
        ("om 2 timer", "da-DK"),
        ("om 2 timer", "nb-NO"),
        ("2 tuntia kuluttua", "fi-FI"),
        ("za 2 godziny", "pl-PL"),
        ("za 2 hodiny", "cs-CZ"),
        ("za 2 hodiny", "sk-SK"),
        ("2 ora mulva", "hu-HU"),
        ("peste 2 ore", "ro-RO"),
        ("2 saat sonra", "tr-TR"),
        ("dalam 2 jam", "id-ID"),
        ("dalam 2 jam", "ms-MY"),
        ("sau 2 gio", "vi-VN"),
        ("sa loob ng 2 oras", "fil-PH"),
        ("baada ya 2 saa", "sw-KE"),
        ("oor 2 ure", "af-ZA"),
        ("za 2 sata", "hr-HR"),
        ("cez 2 uri", "sl-SI"),
        ("za 2 sata", "sr-RS"),
        ("sled 2 chasa", "bg"),
        ("za 2 sata", "bs-BA"),
        ("za 2 chasa", "mk-MK"),
        ("pas 2 oresh", "sq-AL"),
        ("se 2 ores", "el-GR"),
        ("2 tundi parast", "et-EE"),
        ("po 2 valandu", "lt-LT"),
        ("i gceann 2 uair", "ga-IE"),
        ("mewn 2 awr", "cy-GB"),
        ("ann an 2 uair", "gd-GB"),
        ("eftir 2 klukkustundir", "is-IS"),
        ("fi 2 sieghat", "mt-MT"),
        ("an 2 stonnen", "lb-LU"),
        ("en 2 horas", "gl-ES"),
    ),
)
def test_temporal_phrase_extended_locale_relative_resolves_before_registration(
    phrase: str,
    locale: str,
) -> None:
    clock = MutableClock("2026-05-04T13:00:00+00:00")
    scheduler = _engine(clock)
    action = _action(
        execute_at="",
        temporal_phrase=phrase,
        temporal_phrase_locale=locale,
        temporal_phrase_policy="require_exact",
    )

    scheduled = scheduler.register("sched-1", action)

    assert scheduled.execute_at == "2026-05-04T15:00:00+00:00"
    assert scheduled.action.metadata["temporal_phrase_admission_verdict"] == "exact"
    assert scheduled.action.metadata["temporal_phrase_admission_reason"] == "temporal_phrase_exact_relative"


@pytest.mark.parametrize(
    ("phrase", "locale", "expected_execute_at"),
    (
        ("eftir 2 minuta", "is-IS", "2026-05-04T13:02:00+00:00"),
        ("eftir 2 dag", "is", "2026-05-06T13:00:00+00:00"),
        ("fi 2 minuti", "mt-MT", "2026-05-04T13:02:00+00:00"),
        ("an 1 minutt", "lb-LU", "2026-05-04T13:01:00+00:00"),
        ("an 2 minutten", "lb-LU", "2026-05-04T13:02:00+00:00"),
        ("an 2 deeg", "lb", "2026-05-06T13:00:00+00:00"),
        ("en 2 minutos", "gl-ES", "2026-05-04T13:02:00+00:00"),
        ("en 2 dias", "gl", "2026-05-06T13:00:00+00:00"),
    ),
)
def test_temporal_phrase_new_locale_relative_unit_variants_resolve_before_registration(
    phrase: str,
    locale: str,
    expected_execute_at: str,
) -> None:
    clock = MutableClock("2026-05-04T13:00:00+00:00")
    scheduler = _engine(clock)
    action = _action(
        execute_at="",
        temporal_phrase=phrase,
        temporal_phrase_locale=locale,
        temporal_phrase_policy="require_exact",
    )

    scheduled = scheduler.register("sched-1", action)

    assert scheduled.execute_at == expected_execute_at
    assert scheduled.action.metadata["temporal_phrase_admission_verdict"] == "exact"
    assert scheduled.action.metadata["temporal_phrase_admission_reason"] == "temporal_phrase_exact_relative"


@pytest.mark.parametrize(
    ("phrase", "locale"),
    (
        ("i morgen klokken 09:30 UTC", "da-GL"),
        ("i morgen klokken 09:30 UTC", "nn-NO"),
        ("huomenna kello 09:30 UTC", "fi"),
        ("jutro o 09:30 UTC", "pl"),
        ("zitra v 09:30 UTC", "cs"),
        ("zajtra o 09:30 UTC", "sk"),
        ("holnap 09:30 UTC", "hu"),
        ("maine la 09:30 UTC", "ro-MD"),
        ("yarin saat 09:30 UTC", "tr-CY"),
        ("besok pukul 09:30 UTC", "id"),
        ("esok pukul 09:30 UTC", "ms-BN"),
        ("ngay mai luc 09:30 UTC", "vi"),
        ("bukas sa 09:30 UTC", "tl"),
        ("kesho saa 09:30 UTC", "sw-TZ"),
        ("more om 09:30 UTC", "af"),
        ("sutra u 09:30 UTC", "hr"),
        ("jutri ob 09:30 UTC", "sl"),
        ("sutra u 09:30 UTC", "sr-BA"),
        ("utre v 09:30 UTC", "bg-BG"),
        ("sutra u 09:30 UTC", "bs"),
        ("utre vo 09:30 UTC", "mk"),
        ("neser ne 09:30 UTC", "sq-XK"),
        ("avrio stis 09:30 UTC", "el-CY"),
        ("homme kell 09:30 UTC", "et"),
        ("rytoj 09:30 UTC", "lt"),
        ("amarach 09:30 UTC", "ga"),
        ("yfory 09:30 UTC", "cy"),
        ("a-maireach 09:30 UTC", "gd"),
        ("a morgun 09:30 UTC", "is"),
        ("ghada 09:30 UTC", "mt"),
        ("muer 09:30 UTC", "lb"),
        ("mana 09:30 UTC", "gl"),
    ),
)
def test_temporal_phrase_extended_locale_tomorrow_wall_time_resolves_before_registration(
    phrase: str,
    locale: str,
) -> None:
    clock = MutableClock("2026-05-04T13:00:00+00:00")
    scheduler = _engine(clock)
    action = _action(
        execute_at="",
        temporal_phrase=phrase,
        temporal_phrase_locale=locale,
        temporal_phrase_policy="require_exact",
    )

    scheduled = scheduler.register("sched-1", action)

    assert scheduled.execute_at == "2026-05-05T09:30:00+00:00"
    assert scheduled.action.metadata["temporal_phrase_admission_verdict"] == "exact"
    assert scheduled.action.metadata["temporal_phrase_admission_reason"] == "temporal_phrase_exact_utc_wall_time"


@pytest.mark.parametrize(
    ("phrase", "locale"),
    (
        ("naeste mandag klokken 08:15 local", "da"),
        ("neste mandag klokken 08:15 local", "no"),
        ("ensi maanantai kello 08:15 local", "fi-FI"),
        ("nastepny poniedzialek o 08:15 local", "pl-PL"),
        ("pristi pondeli v 08:15 local", "cs-CZ"),
        ("buduci pondelok o 08:15 local", "sk-SK"),
        ("kovetkezo hetfo 08:15 local", "hu-HU"),
        ("urmatoarea luni la 08:15 local", "ro-RO"),
        ("gelecek pazartesi saat 08:15 local", "tr-TR"),
        ("senin depan pukul 08:15 local", "id-ID"),
        ("isnin depan pukul 08:15 local", "ms-MY"),
        ("thu hai tiep theo luc 08:15 local", "vi-VN"),
        ("susunod na lunes sa 08:15 local", "tl-PH"),
        ("jumatatu ijayo saa 08:15 local", "sw-UG"),
        ("volgende maandag om 08:15 local", "af-ZA"),
        ("sljedeci ponedjeljak u 08:15 local", "hr-HR"),
        ("naslednji ponedeljek ob 08:15 local", "sl-SI"),
        ("sledeci ponedeljak u 08:15 local", "sr-Latn-RS"),
        ("sledvasht ponedelnik v 08:15 local", "bg-BG"),
        ("sljedeci ponedjeljak u 08:15 local", "bs-BA"),
        ("sleden ponedelnik vo 08:15 local", "mk-MK"),
        ("te henen e ardhshme ne 08:15 local", "sq-AL"),
        ("tin epomeni deftera stis 08:15 local", "el-GR"),
        ("jargmisel esmaspaeval kell 08:15 local", "et-EE"),
        ("kita pirmadieni 08:15 local", "lt-LT"),
        ("an chead luan eile 08:15 local", "ga-IE"),
        ("dydd llun nesaf 08:15 local", "cy-GB"),
        ("an ath diluain 08:15 local", "gd-GB"),
        ("naesta manudag 08:15 local", "is-IS"),
        ("it-tnejn li gej 08:15 local", "mt-MT"),
        ("naechste meindeg 08:15 local", "lb-LU"),
        ("proximo luns 08:15 local", "gl-ES"),
    ),
)
def test_temporal_phrase_extended_locale_next_weekday_local_resolves_before_registration(
    phrase: str,
    locale: str,
) -> None:
    clock = MutableClock("2026-05-04T13:00:00+00:00")
    scheduler = _engine(clock)
    action = _action(
        execute_at="",
        temporal_phrase=phrase,
        temporal_phrase_locale=locale,
        temporal_phrase_policy="require_exact",
        metadata={"original_timezone": "America/New_York"},
    )

    scheduled = scheduler.register("sched-1", action)

    assert scheduled.execute_at == "2026-05-11T12:15:00+00:00"
    assert scheduled.action.metadata["temporal_phrase_admission_verdict"] == "exact"
    assert scheduled.action.metadata["temporal_phrase_admission_reason"] == "temporal_phrase_exact_local_weekday_wall_time"


def test_temporal_phrase_ambiguous_blocks_before_registration() -> None:
    clock = MutableClock("2026-05-04T13:00:00+00:00")
    scheduler = _engine(clock)
    action = _action(
        execute_at="",
        temporal_phrase="tomorrow",
        temporal_phrase_policy="require_exact",
    )

    with pytest.raises(RuntimeCoreInvariantError, match="temporal_phrase_ambiguous"):
        scheduler.register("sched-1", action)
    assert scheduler.action_count == 0
    assert scheduler.receipt_count == 0


def test_temporal_phrase_mismatch_blocks_before_registration() -> None:
    clock = MutableClock("2026-05-04T13:00:00+00:00")
    scheduler = _engine(clock)
    action = _action(
        execute_at="2026-05-04T16:00:00+00:00",
        temporal_phrase="in 2 hours",
        temporal_phrase_policy="require_exact",
    )

    with pytest.raises(RuntimeCoreInvariantError, match="temporal_phrase_execute_at_mismatch"):
        scheduler.register("sched-1", action)
    assert scheduler.action_count == 0
    assert scheduler.receipt_count == 0


def test_future_action_is_stored_but_not_due() -> None:
    clock = MutableClock("2026-05-04T13:00:00+00:00")
    scheduler = _engine(clock)
    scheduled = scheduler.register("sched-1", _action())

    assert scheduled.state == ScheduledActionState.PENDING
    assert scheduler.due_actions() == ()
    assert scheduler.summary()["pending"] == 1


def test_due_action_becomes_visible_at_execute_at() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _engine(clock)
    scheduler.register("sched-1", _action())

    due = scheduler.due_actions()
    assert len(due) == 1
    assert due[0].schedule_id == "sched-1"
    assert due[0].execute_at == "2026-05-04T14:00:00+00:00"


def test_lease_prevents_duplicate_worker_execution() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _engine(clock)
    scheduler.register("sched-1", _action())

    lease = scheduler.acquire_lease("sched-1", "worker-a")
    duplicate = scheduler.acquire_lease("sched-1", "worker-b")

    assert lease is not None
    assert duplicate is None
    assert scheduler.due_actions() == ()
    assert scheduler.get("sched-1").state == ScheduledActionState.RUNNING


def test_wake_time_policy_allows_due_action() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _engine(clock)
    scheduler.register("sched-1", _action())

    receipt = scheduler.evaluate_due_action("sched-1", worker_id="worker-a")

    assert receipt.verdict == ScheduleDecisionVerdict.DUE
    assert receipt.reason == "temporal_policy_passed"
    assert receipt.temporal_verdict == TemporalPolicyVerdict.ALLOW.value
    assert receipt.temporal_decision_id.startswith("dec-temp-action")


def test_expired_action_never_runs() -> None:
    clock = MutableClock("2026-05-04T15:01:00+00:00")
    scheduler = _engine(clock)
    scheduler.register(
        "sched-1",
        _action(
            execute_at="2026-05-04T14:00:00+00:00",
            expires_at="2026-05-04T15:00:00+00:00",
        ),
    )

    receipt = scheduler.evaluate_due_action("sched-1", worker_id="worker-a")

    assert receipt.verdict == ScheduleDecisionVerdict.EXPIRED
    assert receipt.reason == "command_expired"
    assert scheduler.get("sched-1").state == ScheduledActionState.EXPIRED


def test_approval_expired_at_wake_time_blocks_action() -> None:
    clock = MutableClock("2026-05-04T15:01:00+00:00")
    scheduler = _engine(clock)
    scheduler.register(
        "sched-1",
        _action(
            execute_at="2026-05-04T14:00:00+00:00",
            approval_expires_at="2026-05-04T15:00:00+00:00",
        ),
    )

    receipt = scheduler.evaluate_due_action("sched-1", worker_id="worker-a")

    assert receipt.verdict == ScheduleDecisionVerdict.BLOCKED
    assert receipt.reason == "approval_expired"
    assert receipt.temporal_verdict == TemporalPolicyVerdict.DENY.value
    assert scheduler.get("sched-1").state == ScheduledActionState.BLOCKED


def test_retry_before_retry_after_defers_again() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _engine(clock)
    scheduler.register(
        "sched-1",
        _action(
            execute_at="2026-05-04T14:00:00+00:00",
            retry_after="2026-05-04T14:10:00+00:00",
        ),
    )

    receipt = scheduler.evaluate_due_action("sched-1", worker_id="worker-a")

    assert receipt.verdict == ScheduleDecisionVerdict.NOT_DUE
    assert receipt.reason == "retry_window_not_open"
    assert receipt.temporal_verdict == TemporalPolicyVerdict.DEFER.value
    assert scheduler.get("sched-1").state == ScheduledActionState.PENDING


def test_max_attempts_denies_at_wake_time() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _engine(clock)
    scheduler.register(
        "sched-1",
        _action(max_attempts=3, attempt_count=3),
    )

    receipt = scheduler.evaluate_due_action("sched-1", worker_id="worker-a")

    assert receipt.verdict == ScheduleDecisionVerdict.BLOCKED
    assert receipt.reason == "retry_attempts_exhausted"
    assert receipt.temporal_verdict == TemporalPolicyVerdict.DENY.value
    assert scheduler.receipt_count == 1


def test_completed_action_does_not_run_twice() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _engine(clock)
    scheduler.register("sched-1", _action())

    completed = scheduler.mark_completed("sched-1", worker_id="worker-a")
    receipt = scheduler.evaluate_due_action("sched-1", worker_id="worker-b")

    assert completed.verdict == ScheduleDecisionVerdict.COMPLETED
    assert receipt.reason == "already_completed"
    assert scheduler.due_actions() == ()
    assert scheduler.get("sched-1").state == ScheduledActionState.COMPLETED


def test_stale_evidence_escalates_and_blocks() -> None:
    clock = MutableClock("2026-05-04T14:01:00+00:00")
    scheduler = _engine(clock)
    scheduler.register(
        "sched-1",
        _action(evidence_fresh_until="2026-05-04T14:00:00+00:00"),
    )

    receipt = scheduler.evaluate_due_action("sched-1", worker_id="worker-a")

    assert receipt.verdict == ScheduleDecisionVerdict.BLOCKED
    assert receipt.reason == "evidence_stale"
    assert receipt.temporal_verdict == TemporalPolicyVerdict.ESCALATE.value
    assert scheduler.get("sched-1").state == ScheduledActionState.BLOCKED


def test_missed_action_records_missed_run_receipt() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _engine(clock)
    scheduler.register("sched-1", _action())

    receipt = scheduler.mark_missed("sched-1", worker_id="worker-a")

    assert receipt.verdict == ScheduleDecisionVerdict.BLOCKED
    assert receipt.reason == "missed_run"
    assert scheduler.get("sched-1").state == ScheduledActionState.MISSED
    assert scheduler.recent_receipts()[0].receipt_id == receipt.receipt_id


def test_temporal_skill_plan_executes_through_provider_receipts() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    provider = RecordingSkillStageProvider(
        {
            "observe": {"observation": "ready"},
            "approve": {"approval": "approved"},
            "execute": {"final_receipt": "receipt-001"},
        }
    )
    scheduler = _engine(clock, skill_stage_provider=provider)
    scheduler.register("sched-1", _action(skill_plan=_valid_skill_plan()))
    lease = scheduler.acquire_lease("sched-1", "worker-a")

    execution = scheduler.execute_skill_plan("sched-1", worker_id="worker-a")

    assert lease is not None
    assert execution.verdict.value == "pass"
    assert execution.reason == "skill_plan_executed"
    assert execution.terminal_outputs["final_receipt"] == "receipt-001"
    assert [call[0] for call in provider.calls] == ["observe", "approve", "execute"]
    assert provider.calls[1][1] == {"observation": "ready"}
    assert provider.calls[2][1] == {"approval": "approved"}
    assert scheduler.get("sched-1").state == ScheduledActionState.COMPLETED
    assert scheduler.skill_plan_execution_count == 1
    assert scheduler.receipt_count == 1
    assert scheduler.summary()["skill_plan_executions"] == 1


def test_temporal_skill_plan_execution_is_idempotent_after_terminal_state() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    provider = RecordingSkillStageProvider(
        {
            "observe": {"observation": "ready"},
            "approve": {"approval": "approved"},
            "execute": {"final_receipt": "receipt-001"},
        }
    )
    scheduler = _engine(clock, skill_stage_provider=provider)
    scheduler.register("sched-1", _action(skill_plan=_valid_skill_plan()))
    scheduler.acquire_lease("sched-1", "worker-a")

    first = scheduler.execute_skill_plan("sched-1", worker_id="worker-a")
    second = scheduler.execute_skill_plan("sched-1", worker_id="worker-a")

    assert second == first
    assert scheduler.get("sched-1").state == ScheduledActionState.COMPLETED
    assert scheduler.receipt_count == 1
    assert scheduler.skill_plan_execution_count == 1


def test_temporal_skill_plan_execution_blocks_on_missing_stage_output() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    provider = RecordingSkillStageProvider(
        {
            "observe": {"observation": "ready"},
            "approve": {},
            "execute": {"final_receipt": "receipt-001"},
        }
    )
    scheduler = _engine(clock, skill_stage_provider=provider)
    scheduler.register("sched-1", _action(skill_plan=_valid_skill_plan()))
    scheduler.acquire_lease("sched-1", "worker-a")

    execution = scheduler.execute_skill_plan("sched-1", worker_id="worker-a")

    assert execution.verdict.value == "fail"
    assert execution.reason == "stage_output_missing"
    assert execution.stage_receipts[-1].metadata["missing_output_keys"] == ("approval",)
    assert [call[0] for call in provider.calls] == ["observe", "approve"]
    assert scheduler.get("sched-1").state == ScheduledActionState.BLOCKED
    assert scheduler.receipt_count == 1
    assert scheduler.skill_plan_execution_count == 1


def test_temporal_skill_plan_execution_accepts_simple_input_binding() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    provider = RecordingSkillStageProvider(
        {
            "observe": {"observation": "ready"},
            "approve": {"approval": "approved"},
        }
    )
    plan = TemporalSkillPlan(
        plan_id="plan-1",
        terminal_condition="approval",
        stages=(
            TemporalSkillStage(
                stage_id="observe",
                stage_type=TemporalSkillStageType.OBSERVE,
                output_keys=("observation",),
            ),
            TemporalSkillStage(
                stage_id="approve",
                stage_type=TemporalSkillStageType.APPROVAL,
                predecessor_ids=("observe",),
                input_bindings={"evidence": "observation"},
                output_keys=("approval",),
            ),
        ),
    )
    scheduler = _engine(clock, skill_stage_provider=provider)
    scheduler.register("sched-1", _action(skill_plan=plan))
    scheduler.acquire_lease("sched-1", "worker-a")

    execution = scheduler.execute_skill_plan("sched-1", worker_id="worker-a")

    assert execution.verdict.value == "pass"
    assert execution.terminal_outputs["approval"] == "approved"
    assert provider.calls[1][1] == {"evidence": "ready"}
    assert scheduler.get("sched-1").state == ScheduledActionState.COMPLETED
    assert scheduler.receipt_count == 1


def test_temporal_skill_plan_execution_blocks_on_dangling_input_binding() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    provider = RecordingSkillStageProvider(
        {
            "observe": {"observation": "ready"},
            "approve": {"approval": "approved"},
        }
    )
    plan = TemporalSkillPlan(
        plan_id="plan-1",
        terminal_condition="approval",
        stages=(
            TemporalSkillStage(
                stage_id="observe",
                stage_type=TemporalSkillStageType.OBSERVE,
                output_keys=("observation",),
            ),
            TemporalSkillStage(
                stage_id="approve",
                stage_type=TemporalSkillStageType.APPROVAL,
                predecessor_ids=("observe",),
                input_bindings={"evidence": "missing_output"},
                output_keys=("approval",),
            ),
        ),
    )
    scheduler = _engine(clock, skill_stage_provider=provider)
    scheduler.register("sched-1", _action(skill_plan=plan))
    scheduler.acquire_lease("sched-1", "worker-a")

    execution = scheduler.execute_skill_plan("sched-1", worker_id="worker-a")

    assert execution.verdict.value == "fail"
    assert execution.reason == "dangling_input_binding"
    assert [call[0] for call in provider.calls] == ["observe"]
    assert scheduler.get("sched-1").state == ScheduledActionState.BLOCKED
    assert scheduler.receipt_count == 1


def test_temporal_skill_plan_execution_requires_provider_and_running_state() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _engine(clock)
    scheduler.register("sched-1", _action(skill_plan=_valid_skill_plan()))

    with pytest.raises(RuntimeCoreInvariantError, match="schedule must be running"):
        scheduler.execute_skill_plan("sched-1", worker_id="worker-a")

    scheduler.acquire_lease("sched-1", "worker-a")
    with pytest.raises(RuntimeCoreInvariantError, match="skill_stage_provider is required"):
        scheduler.execute_skill_plan("sched-1", worker_id="worker-a")

    assert scheduler.get("sched-1").state == ScheduledActionState.RUNNING
    assert scheduler.receipt_count == 0
    assert scheduler.skill_plan_execution_count == 0
