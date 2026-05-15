"""Phase 203B — Webhook system tests."""

import pytest
from mcoi_runtime.contracts.execution import ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.effect_assurance import ExpectedEffect, ReconciliationStatus
from mcoi_runtime.core.effect_assurance import EffectAssuranceGate
from mcoi_runtime.governance.network.webhook import WebhookManager, WebhookSubscription


def FIXED_CLOCK() -> str:
    return "2026-03-26T12:00:00Z"


class TestWebhookManager:
    def test_subscribe(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        sub = WebhookSubscription(
            subscription_id="sub-1", tenant_id="t1",
            url="https://example.com/hook", events=("task.completed",),
        )
        mgr.subscribe(sub)
        assert mgr.subscription_count == 1
        receipts = mgr.mutation_receipts()
        assert len(receipts) == 1
        assert receipts[0].effect_name == "webhook_subscription_registered"
        assert receipts[0].before_count == 0
        assert receipts[0].after_count == 1

    def test_duplicate_subscribe_raises(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        sub = WebhookSubscription(subscription_id="sub-1", tenant_id="t1", url="https://example.com/hook", events=("task.completed",))
        mgr.subscribe(sub)
        with pytest.raises(ValueError):
            mgr.subscribe(sub)

    def test_duplicate_subscribe_error_is_bounded(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        sub = WebhookSubscription(subscription_id="sub-1", tenant_id="t1", url="https://example.com/hook", events=("task.completed",))
        mgr.subscribe(sub)
        with pytest.raises(ValueError, match="subscription already exists") as excinfo:
            mgr.subscribe(sub)
        assert str(excinfo.value) == "subscription already exists"
        assert "sub-1" not in str(excinfo.value)

    def test_unsubscribe(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        sub = WebhookSubscription(subscription_id="sub-1", tenant_id="t1", url="https://example.com/hook", events=("task.completed",))
        mgr.subscribe(sub)
        assert mgr.unsubscribe("sub-1") is True
        assert mgr.subscription_count == 0
        receipts = mgr.mutation_receipts()
        assert receipts[-1].effect_name == "webhook_subscription_removed"
        assert receipts[-1].before_count == 1
        assert receipts[-1].after_count == 0

    def test_emit_queues_delivery(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        mgr.subscribe(WebhookSubscription(
            subscription_id="sub-1", tenant_id="t1",
            url="https://example.com/hook", events=("task.completed",),
        ))
        deliveries = mgr.emit("task.completed", {"task_id": "t1"}, tenant_id="t1")
        assert len(deliveries) == 1
        assert deliveries[0].event == "task.completed"
        assert deliveries[0].status == "queued"
        receipts = mgr.mutation_receipts()
        assert receipts[-1].effect_name == "webhook_delivery_queued"
        assert receipts[-1].metadata["payload_hash"]
        assert receipts[-1].metadata["signature_present"] is False

    def test_emit_no_match(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        mgr.subscribe(WebhookSubscription(
            subscription_id="sub-1", tenant_id="t1",
            url="https://example.com/hook", events=("task.completed",),
        ))
        deliveries = mgr.emit("task.failed", {"task_id": "t1"}, tenant_id="t1")
        assert len(deliveries) == 0

    def test_emit_tenant_filter(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        mgr.subscribe(WebhookSubscription(
            subscription_id="sub-1", tenant_id="t1",
            url="https://example.com/hook", events=("task.completed",),
        ))
        deliveries = mgr.emit("task.completed", {"task_id": "t1"}, tenant_id="t2")
        assert len(deliveries) == 0

    def test_emit_wildcard_tenant(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        mgr.subscribe(WebhookSubscription(
            subscription_id="sub-1", tenant_id="*",
            url="https://example.com/hook", events=("task.completed",),
        ))
        deliveries = mgr.emit("task.completed", {"task_id": "t1"}, tenant_id="any-tenant")
        assert len(deliveries) == 1

    def test_emit_with_secret_signature(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        mgr.subscribe(WebhookSubscription(
            subscription_id="sub-1", tenant_id="t1",
            url="https://example.com/hook", events=("task.completed",), secret="my-secret",
        ))
        deliveries = mgr.emit("task.completed", {"data": "test"}, tenant_id="t1")
        assert deliveries[0].signature  # Non-empty HMAC
        receipt = mgr.mutation_receipts()[-1]
        assert receipt.metadata["signature_present"] is True
        assert "my-secret" not in str(receipt.to_dict())

    def test_disabled_subscription_skipped(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        mgr.subscribe(WebhookSubscription(
            subscription_id="sub-1", tenant_id="t1",
            url="https://example.com/hook", events=("task.completed",), enabled=False,
        ))
        deliveries = mgr.emit("task.completed", {}, tenant_id="t1")
        assert len(deliveries) == 0

    def test_delivery_history(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        mgr.subscribe(WebhookSubscription(
            subscription_id="sub-1", tenant_id="t1",
            url="https://example.com/hook", events=("task.completed",),
        ))
        mgr.emit("task.completed", {}, tenant_id="t1")
        mgr.emit("task.completed", {}, tenant_id="t1")
        history = mgr.delivery_history()
        assert len(history) == 2

    def test_multiple_subscriptions(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        mgr.subscribe(WebhookSubscription(subscription_id="s1", tenant_id="t1", url="https://example.com/a", events=("task.completed",)))
        mgr.subscribe(WebhookSubscription(subscription_id="s2", tenant_id="t1", url="https://example.com/b", events=("task.completed",)))
        deliveries = mgr.emit("task.completed", {}, tenant_id="t1")
        assert len(deliveries) == 2

    def test_summary(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        summary = mgr.summary()
        assert "subscriptions" in summary
        assert "events" in summary
        assert summary["mutation_receipts"] == 0

    def test_mutation_receipts_convert_to_effect_records(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        mgr.subscribe(WebhookSubscription(
            subscription_id="sub-1", tenant_id="t1",
            url="https://example.com/hook", events=("task.completed",),
        ))

        effects = mgr.effect_records()

        assert len(effects) == 1
        assert effects[0].name == "webhook_subscription_registered"
        assert effects[0].details["evidence_ref"].startswith("webhook-mutation:")
        assert effects[0].details["observed_value"]["subject_ref"] == "webhook-subscription:sub-1"

    def test_webhook_mutation_receipt_closes_effect_assurance(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        gate = EffectAssuranceGate(clock=lambda: "2026-03-26T12:00:01+00:00")
        plan = gate.create_plan(
            command_id="cmd-webhook-1",
            tenant_id="t1",
            capability_id="webhook.subscribe",
            expected_effects=(
                ExpectedEffect(
                    effect_id="webhook_subscription_registered",
                    name="webhook_subscription_registered",
                    target_ref="webhook-subscription:sub-1",
                    required=True,
                    verification_method="webhook_mutation_receipt",
                ),
            ),
            forbidden_effects=("duplicate_subscription",),
        )
        mgr.subscribe(WebhookSubscription(
            subscription_id="sub-1", tenant_id="t1",
            url="https://example.com/hook", events=("task.completed",),
        ))
        result = ExecutionResult(
            execution_id="exec-webhook-1",
            goal_id="cmd-webhook-1",
            status=ExecutionOutcome.SUCCEEDED,
            actual_effects=mgr.effect_records(limit=1),
            assumed_effects=(),
            started_at="2026-03-26T12:00:00+00:00",
            finished_at="2026-03-26T12:00:01+00:00",
        )

        observed = gate.observe(result)
        verification = gate.verify(plan=plan, execution_result=result, observed_effects=observed)
        reconciliation = gate.reconcile(plan=plan, observed_effects=observed, verification_result=verification)

        assert observed[0].effect_id == "webhook_subscription_registered"
        assert observed[0].evidence_ref.startswith("webhook-mutation:")
        assert reconciliation.status is ReconciliationStatus.MATCH
