"""Phase 215C — Task queue tests."""

import pytest

from mcoi_runtime.contracts.effect_assurance import ExpectedEffect, ReconciliationStatus
from mcoi_runtime.contracts.execution import ExecutionOutcome, ExecutionResult
from mcoi_runtime.core.effect_assurance import EffectAssuranceGate
from mcoi_runtime.core.task_queue import TaskQueue


def FIXED_CLOCK() -> str:
    return "2026-03-26T12:00:00Z"


class TestTaskQueue:
    def test_submit_and_pop(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        q.submit("t1", {"data": "hello"})
        task = q.pop()
        assert task is not None
        assert task.task_id == "t1"
        assert q.mutation_receipts()[-1].effect_name == "task_queue_item_dequeued"

    def test_priority_order(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        q.submit("low", {}, priority=1)
        q.submit("high", {}, priority=10)
        q.submit("mid", {}, priority=5)
        assert q.pop().task_id == "high"
        assert q.pop().task_id == "mid"
        assert q.pop().task_id == "low"

    def test_pop_empty(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        assert q.pop() is None

    def test_peek(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        q.submit("t1", {}, priority=5)
        assert q.peek().task_id == "t1"
        assert q.depth == 1  # Not removed

    def test_max_depth(self):
        q = TaskQueue(clock=FIXED_CLOCK, max_depth=2)
        q.submit("t1", {})
        q.submit("t2", {})
        with pytest.raises(ValueError, match="queue full"):
            q.submit("t3", {})

    def test_max_depth_error_is_bounded(self):
        q = TaskQueue(clock=FIXED_CLOCK, max_depth=2)
        q.submit("t1", {})
        q.submit("t2", {})
        with pytest.raises(ValueError, match="queue full") as excinfo:
            q.submit("t3", {})
        assert str(excinfo.value) == "queue full"
        assert "2" not in str(excinfo.value)

    def test_process_one(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        q.submit("t1", {"x": 1})
        result = q.process_one(lambda payload: {"result": payload["x"] + 1})
        assert result is not None
        assert result.succeeded is True
        assert result.output["result"] == 2
        assert q.mutation_receipts()[-1].effect_name == "task_queue_result_recorded"

    def test_process_empty(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        assert q.process_one(lambda p: {}) is None

    def test_process_failure(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        q.submit("t1", {})
        result = q.process_one(lambda p: (_ for _ in ()).throw(RuntimeError("fail")))
        assert result.succeeded is False
        assert result.error == "task handler error (RuntimeError)"
        assert "fail" not in result.error

    def test_process_timeout_failure_is_sanitized(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        q.submit("t1", {})
        result = q.process_one(lambda p: (_ for _ in ()).throw(TimeoutError("secret timeout detail")))
        assert result.succeeded is False
        assert result.error == "task timeout (TimeoutError)"
        assert "secret timeout detail" not in result.error

    def test_record_result_sanitizes_manual_error(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        result = q.record_result("t1", {}, succeeded=False, error="secret manual detail")
        assert result.succeeded is False
        assert result.error == "task failed"
        assert "secret manual detail" not in result.error

    def test_get_result(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        q.submit("t1", {})
        q.process_one(lambda p: {"done": True})
        result = q.get_result("t1")
        assert result is not None
        assert result.output["done"] is True

    def test_summary(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        q.submit("t1", {})
        q.process_one(lambda p: {})
        s = q.summary()
        assert s["submitted"] == 1
        assert s["processed"] == 1
        assert s["depth"] == 0
        assert s["mutation_receipts"] == 3

    def test_submit_records_bounded_mutation_receipt(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        q.submit("t1", {"secret": "payload"}, tenant_id="tenant-1", priority=7)

        receipt = q.mutation_receipts()[-1]

        assert receipt.effect_name == "task_queue_item_submitted"
        assert receipt.before_depth == 0
        assert receipt.after_depth == 1
        assert receipt.tenant_id == "tenant-1"
        assert receipt.metadata["priority"] == 7
        assert "payload_hash" in receipt.metadata
        assert "secret" not in str(receipt.to_dict())

    def test_process_records_dequeue_and_result_receipts(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        q.submit("t1", {"x": 1}, tenant_id="tenant-1")

        result = q.process_one(lambda payload: {"result": payload["x"] + 1})
        receipts = q.mutation_receipts()

        assert result is not None
        assert tuple(receipt.effect_name for receipt in receipts) == (
            "task_queue_item_submitted",
            "task_queue_item_dequeued",
            "task_queue_result_recorded",
        )
        assert receipts[-2].tenant_id == "tenant-1"
        assert receipts[-1].metadata["succeeded"] is True
        assert receipts[-1].metadata["error_present"] is False
        assert "output_hash" in receipts[-1].metadata

    def test_mutation_receipts_convert_to_effect_records(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        q.submit("t1", {"x": 1}, tenant_id="tenant-1")

        effects = q.effect_records()
        effect = effects[-1]

        assert effect.name == "task_queue_item_submitted"
        assert effect.details["source"] == "task_queue"
        assert effect.details["tenant_id"] == "tenant-1"
        assert effect.details["evidence_ref"].startswith("task-queue-receipt:")
        assert effect.details["after_depth"] == 1
        assert effect.details["metadata"]["payload_hash"]

    def test_task_queue_mutation_receipt_closes_effect_assurance(self):
        q = TaskQueue(clock=FIXED_CLOCK)
        gate = EffectAssuranceGate(clock=FIXED_CLOCK)
        plan = gate.create_plan(
            command_id="cmd-task-submit",
            tenant_id="tenant-1",
            capability_id="task_queue.submit",
            expected_effects=(
                ExpectedEffect(
                    effect_id="task_queue_item_submitted",
                    name="task_queue_item_submitted",
                    target_ref="task:t1",
                    required=True,
                    verification_method="task_queue_mutation_receipt",
                ),
            ),
            forbidden_effects=("task_queue_duplicate_submission",),
        )

        q.submit("t1", {"x": 1}, tenant_id="tenant-1")
        execution = ExecutionResult(
            execution_id="exec-task-submit",
            goal_id="goal-task-submit",
            status=ExecutionOutcome.SUCCEEDED,
            actual_effects=q.effect_records(limit=1),
            assumed_effects=(),
            started_at="2026-03-26T12:00:00+00:00",
            finished_at="2026-03-26T12:00:01+00:00",
        )
        observed = gate.observe(execution)
        verification = gate.verify(plan=plan, execution_result=execution, observed_effects=observed)
        reconciliation = gate.reconcile(
            plan=plan,
            observed_effects=observed,
            verification_result=verification,
        )

        assert reconciliation.status is ReconciliationStatus.MATCH
        assert reconciliation.matched_effects == ("task_queue_item_submitted",)
        assert reconciliation.missing_effects == ()
        assert reconciliation.unexpected_effects == ()
        assert verification.evidence[0].uri.startswith("task-queue-receipt:")
