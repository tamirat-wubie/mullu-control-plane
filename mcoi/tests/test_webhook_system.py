"""Phase 203B — Webhook system tests."""

import pytest
from mcoi_runtime.contracts.execution import ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.effect_assurance import ExpectedEffect, ReconciliationStatus
from mcoi_runtime.core.effect_assurance import EffectAssuranceGate
from mcoi_runtime.governance.network import webhook as webhook_mod
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

    @pytest.mark.parametrize("url", [
        "ftp://example.com/hook",
        "file:///tmp/hook",
        "gopher://example.com/hook",
        "mailto:ops@example.com",
        "https:///missing-host",
    ])
    def test_subscribe_rejects_non_http_webhook_urls(self, url):
        mgr = WebhookManager(clock=FIXED_CLOCK)

        with pytest.raises(ValueError, match="unsupported scheme or missing host") as excinfo:
            mgr.subscribe(WebhookSubscription(
                subscription_id="sub-1",
                tenant_id="t1",
                url=url,
                events=("task.completed",),
            ))

        assert str(excinfo.value) == "webhook URL rejected: unsupported scheme or missing host"
        assert url not in str(excinfo.value)
        assert mgr.subscription_count == 0

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

    def test_emit_records_delivery_time_ssrf_block(self, monkeypatch):
        checks = iter((False, True))
        monkeypatch.setattr(webhook_mod, "_is_private_url", lambda url: next(checks))
        mgr = WebhookManager(clock=FIXED_CLOCK)
        mgr.subscribe(WebhookSubscription(
            subscription_id="sub-1", tenant_id="t1",
            url="https://example.com/private-after-rebind", events=("task.completed",),
        ))

        deliveries = mgr.emit("task.completed", {"task_id": "task-secret"}, tenant_id="t1")
        history = mgr.delivery_history()
        receipt = mgr.mutation_receipts()[-1]
        summary = mgr.summary()

        assert deliveries == []
        assert history[-1].status == "failed"
        assert history[-1].delivery_id == "wh-1"
        assert receipt.effect_name == "webhook_delivery_blocked"
        assert receipt.metadata["block_reason"] == "delivery_url_private"
        assert receipt.metadata["target_url_hash"]
        assert summary["failed_deliveries"] == 1
        assert "private-after-rebind" not in str(receipt.to_dict())

    def test_emit_blocks_legacy_invalid_webhook_url(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        legacy = WebhookSubscription(
            subscription_id="legacy-invalid",
            tenant_id="t1",
            url="ftp://example.com/hook",
            events=("task.completed",),
        )
        mgr._subscriptions[legacy.subscription_id] = legacy

        deliveries = mgr.emit("task.completed", {"task_id": "task-secret"}, tenant_id="t1")
        history = mgr.delivery_history()
        receipt = mgr.mutation_receipts()[-1]
        summary = mgr.summary()

        assert deliveries == []
        assert history[-1].status == "failed"
        assert history[-1].subscription_id == "legacy-invalid"
        assert receipt.effect_name == "webhook_delivery_blocked"
        assert receipt.metadata["block_reason"] == "delivery_url_invalid"
        assert receipt.metadata["target_url_hash"]
        assert summary["failed_deliveries"] == 1
        assert "ftp://example.com/hook" not in str(receipt.to_dict())

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
        assert mgr.delivery_history(limit=1)[0].delivery_id == history[-1].delivery_id
        assert mgr.delivery_history(limit=0) == []
        assert mgr.delivery_history(limit=-1) == []

        receipts = mgr.mutation_receipts()
        assert len(receipts) == 3
        assert mgr.mutation_receipts(limit=1)[0].effect_name == "webhook_delivery_queued"
        assert mgr.mutation_receipts(limit=0) == ()
        assert mgr.mutation_receipts(limit=-1) == ()

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
        assert summary["failed_deliveries"] == 0
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
        assert mgr.effect_records(limit=0) == ()
        assert mgr.effect_records(limit=-1) == ()

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
