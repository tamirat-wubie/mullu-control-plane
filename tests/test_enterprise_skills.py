"""Enterprise Skills Tests — RAG, Notifications, Task Scheduler."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest
from skills.enterprise.knowledge_base import KnowledgeBase, Document, RetrievalResult
from skills.enterprise.notifications import (
    NotificationEngine, NotificationRule, NotificationChannel,
    NotificationPriority, NotificationType,
)
from skills.enterprise.task_scheduler import (
    TaskScheduler, ScheduleInterval, TaskStatus,
)


# ═══ RAG Knowledge Base ═══


class TestKnowledgeBaseIngestion:
    def test_ingest_document(self):
        kb = KnowledgeBase()
        doc = kb.ingest(tenant_id="t1", title="Test Doc", content="This is test content about Python programming.")
        assert doc.doc_id != ""
        assert doc.tenant_id == "t1"
        assert doc.content_hash != ""
        assert kb.document_count("t1") == 1

    def test_ingest_chunks_created(self):
        kb = KnowledgeBase()
        kb.ingest(tenant_id="t1", title="Doc", content="Word " * 600)
        assert kb.chunk_count("t1") >= 2  # 600 words > MAX_CHUNK_SIZE

    def test_empty_content_raises(self):
        kb = KnowledgeBase()
        with pytest.raises(ValueError, match="content must not be empty"):
            kb.ingest(tenant_id="t1", title="Empty", content="")

    def test_tenant_isolation(self):
        kb = KnowledgeBase()
        kb.ingest(tenant_id="t1", title="T1 Doc", content="Tenant one data")
        kb.ingest(tenant_id="t2", title="T2 Doc", content="Tenant two data")
        assert kb.document_count("t1") == 1
        assert kb.document_count("t2") == 1
        assert kb.chunk_count("t1") > 0
        assert kb.chunk_count("t2") > 0


class TestKnowledgeBaseRetrieval:
    def test_query_returns_results(self):
        kb = KnowledgeBase()
        kb.ingest(tenant_id="t1", title="Python Guide", content="Python is a programming language used for data science and web development.")
        result = kb.query("t1", "What is Python?")
        assert len(result.chunks) >= 1
        assert result.tenant_id == "t1"

    def test_query_empty_tenant(self):
        kb = KnowledgeBase()
        result = kb.query("empty", "anything")
        assert len(result.chunks) == 0

    def test_query_relevance_ordering(self):
        kb = KnowledgeBase()
        kb.ingest(tenant_id="t1", title="Python", content="Python is great for machine learning and AI development.")
        kb.ingest(tenant_id="t1", title="Cooking", content="The best recipe for chocolate cake requires butter and eggs.")
        result = kb.query("t1", "machine learning")
        assert len(result.scores) >= 1
        # Scores should be descending
        for i in range(len(result.scores) - 1):
            assert result.scores[i] >= result.scores[i + 1]

    def test_top_k_limit(self):
        kb = KnowledgeBase()
        for i in range(10):
            kb.ingest(tenant_id="t1", title=f"Doc {i}", content=f"Document number {i} with unique content about topic {i}.")
        result = kb.query("t1", "document", top_k=3)
        assert len(result.chunks) <= 3


class TestRAGPromptBuilding:
    def test_build_prompt_with_context(self):
        kb = KnowledgeBase()
        kb.ingest(tenant_id="t1", title="FAQ", content="Our refund policy allows returns within 30 days.")
        result = kb.query("t1", "What is the refund policy?")
        prompt = kb.build_rag_prompt("What is the refund policy?", result)
        assert "refund" in prompt.lower()
        assert "Context:" in prompt
        assert "Question:" in prompt

    def test_build_prompt_no_context(self):
        kb = KnowledgeBase()
        result = kb.query("t1", "anything")
        prompt = kb.build_rag_prompt("What is this?", result)
        assert prompt == "What is this?"  # No context → plain prompt


class TestKnowledgeBaseSummary:
    def test_summary(self):
        kb = KnowledgeBase()
        kb.ingest(tenant_id="t1", title="Doc", content="Some content here")
        summary = kb.summary()
        assert summary["total_documents"] == 1
        assert summary["total_chunks"] > 0


# ═══ Notification System ═══


class TestNotificationRules:
    def test_add_rule(self):
        engine = NotificationEngine()
        engine.add_rule(NotificationRule(
            rule_id="r1", tenant_id="t1",
            notification_type=NotificationType.APPROVAL_NEEDED,
            channel=NotificationChannel.SLACK, recipient="#approvals",
        ))
        assert engine.rule_count == 1

    def test_remove_rule(self):
        engine = NotificationEngine()
        engine.add_rule(NotificationRule(
            rule_id="r1", tenant_id="t1",
            notification_type=NotificationType.BUDGET_WARNING,
            channel=NotificationChannel.EMAIL, recipient="admin@co.com",
        ))
        assert engine.remove_rule("r1", "t1")
        assert engine.rule_count == 0

    def test_remove_nonexistent(self):
        engine = NotificationEngine()
        assert not engine.remove_rule("nope", "t1")


class TestNotificationDelivery:
    def test_notify_matching_rule(self):
        engine = NotificationEngine()
        engine.add_rule(NotificationRule(
            rule_id="r1", tenant_id="t1",
            notification_type=NotificationType.APPROVAL_NEEDED,
            channel=NotificationChannel.SLACK, recipient="#approvals",
        ))
        notifications = engine.notify(
            tenant_id="t1",
            notification_type=NotificationType.APPROVAL_NEEDED,
            priority=NotificationPriority.HIGH,
            title="Payment Approval",
            body="$500 payment requires approval",
        )
        assert len(notifications) == 1
        assert notifications[0].channel == NotificationChannel.SLACK
        assert engine.delivered_count == 1

    def test_no_matching_rule(self):
        engine = NotificationEngine()
        engine.add_rule(NotificationRule(
            rule_id="r1", tenant_id="t1",
            notification_type=NotificationType.BUDGET_WARNING,
            channel=NotificationChannel.EMAIL, recipient="admin@co.com",
        ))
        # Notify about approval (doesn't match budget rule)
        notifications = engine.notify(
            tenant_id="t1",
            notification_type=NotificationType.APPROVAL_NEEDED,
            priority=NotificationPriority.HIGH,
            title="Approval", body="Need approval",
        )
        assert len(notifications) == 0

    def test_priority_filter(self):
        engine = NotificationEngine()
        engine.add_rule(NotificationRule(
            rule_id="r1", tenant_id="t1",
            notification_type=NotificationType.BUDGET_WARNING,
            channel=NotificationChannel.SLACK, recipient="#budget",
            min_priority=NotificationPriority.HIGH,
        ))
        # LOW priority → should NOT match
        notifications = engine.notify(
            tenant_id="t1",
            notification_type=NotificationType.BUDGET_WARNING,
            priority=NotificationPriority.LOW,
            title="Low Alert", body="Minor budget concern",
        )
        assert len(notifications) == 0

        # HIGH priority → should match
        notifications = engine.notify(
            tenant_id="t1",
            notification_type=NotificationType.BUDGET_WARNING,
            priority=NotificationPriority.HIGH,
            title="High Alert", body="Budget nearly exhausted",
        )
        assert len(notifications) == 1

    def test_multiple_rules_multiple_notifications(self):
        engine = NotificationEngine()
        engine.add_rule(NotificationRule(
            rule_id="r1", tenant_id="t1",
            notification_type=NotificationType.PAYMENT_SETTLED,
            channel=NotificationChannel.SLACK, recipient="#finance",
        ))
        engine.add_rule(NotificationRule(
            rule_id="r2", tenant_id="t1",
            notification_type=NotificationType.PAYMENT_SETTLED,
            channel=NotificationChannel.EMAIL, recipient="cfo@co.com",
        ))
        notifications = engine.notify(
            tenant_id="t1",
            notification_type=NotificationType.PAYMENT_SETTLED,
            priority=NotificationPriority.MEDIUM,
            title="Payment", body="$500 settled",
        )
        assert len(notifications) == 2


# ═══ Task Scheduler ═══


class TestTaskRegistration:
    def test_register_task(self):
        scheduler = TaskScheduler()
        task = scheduler.register_task(
            tenant_id="t1", name="Daily Report",
            description="Generate daily summary",
            interval=ScheduleInterval.DAILY,
            action="generate_report",
        )
        assert task.task_id != ""
        assert task.tenant_id == "t1"
        assert task.enabled
        assert scheduler.task_count == 1

    def test_list_tasks_by_tenant(self):
        scheduler = TaskScheduler()
        scheduler.register_task(tenant_id="t1", name="Task A", action="a")
        scheduler.register_task(tenant_id="t2", name="Task B", action="b")
        assert len(scheduler.list_tasks("t1")) == 1
        assert len(scheduler.list_tasks("t2")) == 1
        assert len(scheduler.list_tasks()) == 2

    def test_disable_task(self):
        scheduler = TaskScheduler()
        task = scheduler.register_task(tenant_id="t1", name="T", action="a")
        assert scheduler.disable_task(task.task_id)
        assert not scheduler.get_task(task.task_id).enabled


class TestTaskExecution:
    def test_execute_task(self):
        scheduler = TaskScheduler()
        task = scheduler.register_task(tenant_id="t1", name="Test", action="test_action")
        execution = scheduler.execute_task(task.task_id)
        assert execution.status == TaskStatus.COMPLETED
        assert scheduler.get_task(task.task_id).run_count == 1

    def test_execute_with_executor(self):
        scheduler = TaskScheduler()
        task = scheduler.register_task(tenant_id="t1", name="Test", action="greet")
        execution = scheduler.execute_task(
            task.task_id,
            executor=lambda action, params: {"result": f"executed {action}"},
        )
        assert execution.status == TaskStatus.COMPLETED
        assert execution.result["result"] == "executed greet"

    def test_execute_disabled_task(self):
        scheduler = TaskScheduler()
        task = scheduler.register_task(tenant_id="t1", name="T", action="a")
        scheduler.disable_task(task.task_id)
        execution = scheduler.execute_task(task.task_id)
        assert execution.status == TaskStatus.SKIPPED
        assert "disabled" in execution.error

    def test_concurrent_execution_prevented(self):
        scheduler = TaskScheduler()
        task = scheduler.register_task(tenant_id="t1", name="T", action="a")
        # Simulate concurrent by adding to running set
        scheduler._running.add(task.task_id)
        execution = scheduler.execute_task(task.task_id)
        assert execution.status == TaskStatus.SKIPPED
        assert "already running" in execution.error
        scheduler._running.discard(task.task_id)

    def test_executor_failure_tracked(self):
        scheduler = TaskScheduler()
        task = scheduler.register_task(tenant_id="t1", name="T", action="a")

        def failing_executor(action, params):
            raise RuntimeError("task exploded")

        execution = scheduler.execute_task(task.task_id, executor=failing_executor)
        assert execution.status == TaskStatus.FAILED
        assert "exploded" in execution.error
        assert scheduler.get_task(task.task_id).fail_count == 1

    def test_execution_history(self):
        scheduler = TaskScheduler()
        task = scheduler.register_task(tenant_id="t1", name="T", action="a")
        scheduler.execute_task(task.task_id)
        scheduler.execute_task(task.task_id)
        execs = scheduler.get_executions(task.task_id)
        assert len(execs) == 2


class TestTaskSummary:
    def test_summary(self):
        scheduler = TaskScheduler()
        scheduler.register_task(tenant_id="t1", name="A", action="a")
        scheduler.register_task(tenant_id="t1", name="B", action="b")
        summary = scheduler.summary()
        assert summary["total_tasks"] == 2
        assert summary["enabled_tasks"] == 2
