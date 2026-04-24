"""Task Store Persistence Tests — Save and restore scheduled tasks."""

from skills.enterprise.task_scheduler import (
    ScheduleInterval,
    ScheduledTask,
    TaskExecution,
    TaskScheduler,
    TaskStatus,
)
from skills.enterprise.task_store import (
    FileTaskStore,
    InMemoryTaskStore,
    TaskStore,
    _task_from_dict,
    _task_to_dict,
    _exec_from_dict,
    _exec_to_dict,
)


# ── Serialization roundtrip ───────────────────────────────────

class TestSerialization:
    def test_task_roundtrip(self):
        task = ScheduledTask(
            task_id="t1", tenant_id="tenant-1", name="daily-report",
            description="Generate daily report", interval=ScheduleInterval.DAILY,
            action="generate_report", action_params={"format": "pdf"},
            enabled=True, created_at="2026-04-07T12:00:00Z",
            run_count=5, fail_count=1,
        )
        d = _task_to_dict(task)
        restored = _task_from_dict(d)
        assert restored.task_id == task.task_id
        assert restored.name == task.name
        assert restored.interval == ScheduleInterval.DAILY
        assert restored.run_count == 5
        assert restored.action_params == {"format": "pdf"}

    def test_execution_roundtrip(self):
        ex = TaskExecution(
            execution_id="exec-1", task_id="t1", tenant_id="tenant-1",
            status=TaskStatus.COMPLETED, started_at="2026-04-07T12:00:00Z",
            completed_at="2026-04-07T12:01:00Z",
            result={"rows": 42}, duration_ms=60000.0,
        )
        d = _exec_to_dict(ex)
        restored = _exec_from_dict(d)
        assert restored.execution_id == ex.execution_id
        assert restored.status == TaskStatus.COMPLETED
        assert restored.result == {"rows": 42}
        assert restored.duration_ms == 60000.0


# ── InMemoryTaskStore ──────────────────────────────────────────

class TestInMemoryStore:
    def test_save_and_load_tasks(self):
        store = InMemoryTaskStore()
        tasks = [
            ScheduledTask(task_id="t1", tenant_id="t", name="a", description="",
                          interval=ScheduleInterval.DAILY, action="act1"),
            ScheduledTask(task_id="t2", tenant_id="t", name="b", description="",
                          interval=ScheduleInterval.HOURLY, action="act2"),
        ]
        assert store.save_tasks(tasks) is True
        loaded = store.load_tasks()
        assert len(loaded) == 2
        assert loaded[0].task_id == "t1"

    def test_save_and_load_executions(self):
        store = InMemoryTaskStore()
        execs = [
            TaskExecution(execution_id="e1", task_id="t1", tenant_id="t",
                          status=TaskStatus.COMPLETED, started_at="now"),
        ]
        assert store.save_executions(execs) is True
        loaded = store.load_executions()
        assert len(loaded) == 1

    def test_empty_load(self):
        store = InMemoryTaskStore()
        assert store.load_tasks() == []
        assert store.load_executions() == []


# ── FileTaskStore ──────────────────────────────────────────────

class TestFileStore:
    def test_save_and_load_tasks(self, tmp_path):
        store = FileTaskStore(base_dir=str(tmp_path))
        tasks = [
            ScheduledTask(task_id="t1", tenant_id="t", name="report",
                          description="daily", interval=ScheduleInterval.DAILY,
                          action="gen", run_count=3),
        ]
        assert store.save_tasks(tasks) is True
        loaded = store.load_tasks()
        assert len(loaded) == 1
        assert loaded[0].task_id == "t1"
        assert loaded[0].run_count == 3

    def test_save_and_load_executions(self, tmp_path):
        store = FileTaskStore(base_dir=str(tmp_path))
        execs = [
            TaskExecution(execution_id="e1", task_id="t1", tenant_id="t",
                          status=TaskStatus.FAILED, started_at="now", error="boom"),
        ]
        assert store.save_executions(execs) is True
        loaded = store.load_executions()
        assert len(loaded) == 1
        assert loaded[0].status == TaskStatus.FAILED
        assert loaded[0].error == "boom"

    def test_file_created(self, tmp_path):
        store = FileTaskStore(base_dir=str(tmp_path))
        store.save_tasks([
            ScheduledTask(task_id="t1", tenant_id="t", name="x",
                          description="", interval=ScheduleInterval.DAILY, action="a"),
        ])
        assert (tmp_path / "scheduled_tasks.json").exists()

    def test_empty_load(self, tmp_path):
        store = FileTaskStore(base_dir=str(tmp_path))
        assert store.load_tasks() == []
        assert store.load_executions() == []

    def test_corrupted_file(self, tmp_path):
        store = FileTaskStore(base_dir=str(tmp_path))
        (tmp_path / "scheduled_tasks.json").write_text("not json{{{")
        assert store.load_tasks() == []

    def test_execution_limit(self, tmp_path):
        store = FileTaskStore(base_dir=str(tmp_path))
        execs = [
            TaskExecution(execution_id=f"e{i}", task_id="t1", tenant_id="t",
                          status=TaskStatus.COMPLETED, started_at="now")
            for i in range(100)
        ]
        store.save_executions(execs, limit=10)
        loaded = store.load_executions()
        assert len(loaded) == 10

    def test_summary(self, tmp_path):
        store = FileTaskStore(base_dir=str(tmp_path))
        s = store.summary()
        assert str(tmp_path) in s["base_dir"]
        assert s["tasks_file_exists"] is False


# ── TaskScheduler + Store integration ──────────────────────────

class TestSchedulerStoreIntegration:
    def test_register_persists(self):
        store = InMemoryTaskStore()
        sched = TaskScheduler(clock=lambda: "2026-04-07T12:00:00Z", store=store)
        sched.register_task(
            tenant_id="t1", name="report", action="gen",
            interval=ScheduleInterval.DAILY,
        )
        # Verify store received the task
        loaded = store.load_tasks()
        assert len(loaded) == 1
        assert loaded[0].name == "report"

    def test_execute_persists(self):
        store = InMemoryTaskStore()
        sched = TaskScheduler(clock=lambda: "2026-04-07T12:00:00Z", store=store)
        task = sched.register_task(
            tenant_id="t1", name="job", action="run",
        )
        sched.execute_task(task.task_id)
        # Verify execution persisted
        execs = store.load_executions()
        assert len(execs) == 1
        # Verify task stats updated
        tasks = store.load_tasks()
        assert tasks[0].run_count == 1

    def test_disable_persists(self):
        store = InMemoryTaskStore()
        sched = TaskScheduler(clock=lambda: "2026-04-07T12:00:00Z", store=store)
        task = sched.register_task(tenant_id="t1", name="job", action="run")
        sched.disable_task(task.task_id)
        loaded = store.load_tasks()
        assert loaded[0].enabled is False

    def test_restore_on_init(self):
        store = InMemoryTaskStore()
        # First scheduler: register tasks
        s1 = TaskScheduler(clock=lambda: "2026-04-07T12:00:00Z", store=store)
        s1.register_task(tenant_id="t1", name="daily", action="gen")
        s1.register_task(tenant_id="t1", name="weekly", action="report")
        assert s1.task_count == 2

        # Second scheduler: should restore from store
        s2 = TaskScheduler(clock=lambda: "2026-04-07T13:00:00Z", store=store)
        assert s2.task_count == 2
        tasks = s2.list_tasks()
        names = {t.name for t in tasks}
        assert "daily" in names
        assert "weekly" in names

    def test_file_store_roundtrip(self, tmp_path):
        store = FileTaskStore(base_dir=str(tmp_path))
        s1 = TaskScheduler(clock=lambda: "2026-04-07T12:00:00Z", store=store)
        task = s1.register_task(tenant_id="t1", name="backup", action="backup_db")
        s1.execute_task(task.task_id)

        # "Restart" with new scheduler
        s2 = TaskScheduler(clock=lambda: "2026-04-07T13:00:00Z", store=store)
        assert s2.task_count == 1
        restored = s2.get_task(task.task_id)
        assert restored is not None
        assert restored.name == "backup"
        assert restored.run_count == 1

    def test_no_store_works(self):
        """Scheduler works without store (backward compatible)."""
        sched = TaskScheduler(clock=lambda: "2026-04-07T12:00:00Z")
        task = sched.register_task(tenant_id="t1", name="job", action="run")
        sched.execute_task(task.task_id)
        assert sched.task_count == 1

    def test_store_failure_non_fatal(self):
        """Store write failure doesn't crash the scheduler."""
        class BrokenStore(TaskStore):
            def save_tasks(self, tasks):
                raise IOError("disk full")
            def load_tasks(self):
                return []
            def save_executions(self, executions, *, limit=1000):
                raise IOError("disk full")
            def load_executions(self):
                return []

        sched = TaskScheduler(clock=lambda: "2026-04-07T12:00:00Z", store=BrokenStore())
        task = sched.register_task(tenant_id="t1", name="job", action="run")
        sched.execute_task(task.task_id)  # Should not raise
        summary = sched.summary()
        assert sched.task_count == 1
        assert summary["store_load_failures"] == 0
        assert summary["store_task_save_failures"] == 2
        assert summary["store_execution_save_failures"] == 1

    def test_store_load_failure_counted_and_non_fatal(self):
        """Store load failure is visible but does not block startup."""
        class BrokenLoadStore(TaskStore):
            def load_tasks(self):
                raise IOError("disk unavailable")

        sched = TaskScheduler(clock=lambda: "2026-04-07T12:00:00Z", store=BrokenLoadStore())
        summary = sched.summary()
        assert sched.task_count == 0
        assert sched.execution_count == 0
        assert sched.store_load_failures == 1
        assert summary["store_load_failures"] == 1
        assert summary["store_task_save_failures"] == 0
        assert summary["store_execution_save_failures"] == 0

    def test_false_store_save_result_counted_and_non_fatal(self):
        """False store writes are visible but do not block scheduling."""
        sched = TaskScheduler(clock=lambda: "2026-04-07T12:00:00Z", store=TaskStore())
        task = sched.register_task(tenant_id="t1", name="job", action="run")
        execution = sched.execute_task(task.task_id)
        summary = sched.summary()
        assert execution.status == TaskStatus.COMPLETED
        assert sched.task_count == 1
        assert sched.execution_count == 1
        assert sched.store_load_failures == 0
        assert summary["store_task_save_failures"] == 2
        assert summary["store_execution_save_failures"] == 1


# ── Base TaskStore ─────────────────────────────────────────────

class TestBaseStore:
    def test_base_returns_defaults(self):
        store = TaskStore()
        assert store.save_tasks([]) is False
        assert store.load_tasks() == []
        assert store.save_executions([]) is False
        assert store.load_executions() == []
