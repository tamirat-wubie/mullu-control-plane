"""Concurrency regressions for WebhookManager (FastAPI threadpool).

Three real races existed before the lock:
  1. emit's ``self._delivery_counter += 1`` (read-modify-write) could emit
     DUPLICATE ``wh-N`` delivery ids under concurrent emits.
  2. emit iterated ``self._subscriptions.values()`` directly, so a concurrent
     subscribe/unsubscribe raised ``RuntimeError: dictionary changed size during
     iteration`` -- a crash, not just a dup id.
  3. subscribe's check-then-set let two threads both register the same id.

These tests drive real threads and assert unique ids, no crash, and a single
winner. The DNS-based SSRF check is patched out so the hot loop exercises the
concurrency, not the resolver.
"""

from __future__ import annotations

import threading

from mcoi_runtime.governance.network import webhook as webhook_mod
from mcoi_runtime.governance.network.webhook import WebhookManager, WebhookSubscription


def _clock() -> str:
    return "2026-06-02T00:00:00Z"


def _sub(sub_id: str, *, tenant: str = "t1") -> WebhookSubscription:
    return WebhookSubscription(
        subscription_id=sub_id,
        tenant_id=tenant,
        url="https://example.com/hook",
        events=("task.completed",),
    )


def test_emit_concurrent_unique_delivery_ids(monkeypatch):
    monkeypatch.setattr(webhook_mod, "_is_private_url", lambda url: False)
    mgr = WebhookManager(clock=_clock)
    mgr.subscribe(_sub("sub-1"))

    collected: list[str] = []
    guard = threading.Lock()

    def worker() -> None:
        local: list[str] = []
        for _ in range(100):
            for delivery in mgr.emit("task.completed", {"k": "v"}, tenant_id="t1"):
                local.append(delivery.delivery_id)
        with guard:
            collected.extend(local)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(collected) == 800
    assert len(set(collected)) == 800  # no lost counter increments -> no dup ids


def test_concurrent_subscribe_unsubscribe_during_emit_no_crash(monkeypatch):
    monkeypatch.setattr(webhook_mod, "_is_private_url", lambda url: False)
    mgr = WebhookManager(clock=_clock)
    for i in range(5):
        mgr.subscribe(_sub(f"stable-{i}"))

    errors: list[BaseException] = []
    guard = threading.Lock()
    stop = threading.Event()

    def emitter() -> None:
        try:
            while not stop.is_set():
                mgr.emit("task.completed", {"k": "v"}, tenant_id="t1")
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(exc)

    def churner(base: str) -> None:
        try:
            for i in range(300):
                sid = f"{base}-{i}"
                mgr.subscribe(_sub(sid))
                mgr.unsubscribe(sid)
        except BaseException as exc:  # noqa: BLE001
            with guard:
                errors.append(exc)

    emitters = [threading.Thread(target=emitter) for _ in range(4)]
    churners = [threading.Thread(target=churner, args=(f"c{n}",)) for n in range(4)]
    for thread in emitters + churners:
        thread.start()
    for thread in churners:
        thread.join()
    stop.set()
    for thread in emitters:
        thread.join()

    # Pre-fix, the emitters raised "dictionary changed size during iteration".
    assert errors == [], f"concurrent emit/subscribe raised: {errors[:1]}"


def test_concurrent_subscribe_same_id_single_winner(monkeypatch):
    monkeypatch.setattr(webhook_mod, "_is_private_url", lambda url: False)
    mgr = WebhookManager(clock=_clock)

    winners: list[bool] = []
    guard = threading.Lock()

    def worker() -> None:
        try:
            mgr.subscribe(_sub("shared"))
        except ValueError:
            return  # lost the race -> correctly rejected as duplicate
        with guard:
            winners.append(True)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(winners) == 1  # exactly one registration succeeded
    assert mgr.subscription_count == 1
