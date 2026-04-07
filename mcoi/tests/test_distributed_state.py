"""Distributed State Store Tests."""

import pytest
from mcoi_runtime.core.distributed_state import (
    DistributedStateStore,
    InMemoryStateStore,
)


def _store(**kw):
    return InMemoryStateStore(clock=kw.pop("clock", lambda: 0.0), **kw)


class TestBasicOperations:
    def test_set_and_get(self):
        s = _store()
        assert s.set("key1", "value1") is True
        assert s.get("key1") == "value1"

    def test_get_missing(self):
        s = _store()
        assert s.get("nonexistent") is None

    def test_delete(self):
        s = _store()
        s.set("key1", "value1")
        assert s.delete("key1") is True
        assert s.get("key1") is None

    def test_delete_missing(self):
        s = _store()
        assert s.delete("nonexistent") is False

    def test_exists(self):
        s = _store()
        s.set("key1", "value1")
        assert s.exists("key1") is True
        assert s.exists("nonexistent") is False

    def test_overwrite(self):
        s = _store()
        s.set("key1", "v1")
        s.set("key1", "v2")
        assert s.get("key1") == "v2"


class TestIncrement:
    def test_increment_new_key(self):
        s = _store()
        assert s.increment("counter") == 1
        assert s.increment("counter") == 2
        assert s.increment("counter") == 3

    def test_increment_by_amount(self):
        s = _store()
        assert s.increment("counter", 5) == 5
        assert s.increment("counter", 3) == 8

    def test_increment_existing(self):
        s = _store()
        s.set("counter", 10)
        assert s.increment("counter") == 11


class TestTTL:
    def test_expired_key_returns_none(self):
        now = [0.0]
        s = InMemoryStateStore(clock=lambda: now[0], default_ttl=5.0)
        s.set("key1", "value1")
        now[0] = 10.0
        assert s.get("key1") is None

    def test_within_ttl_returns_value(self):
        now = [0.0]
        s = InMemoryStateStore(clock=lambda: now[0], default_ttl=10.0)
        s.set("key1", "value1")
        now[0] = 5.0
        assert s.get("key1") == "value1"

    def test_custom_ttl(self):
        now = [0.0]
        s = InMemoryStateStore(clock=lambda: now[0], default_ttl=60.0)
        s.set("key1", "value1", ttl=2.0)
        now[0] = 3.0
        assert s.get("key1") is None

    def test_expired_not_in_exists(self):
        now = [0.0]
        s = InMemoryStateStore(clock=lambda: now[0], default_ttl=1.0)
        s.set("key1", "value1")
        now[0] = 5.0
        assert s.exists("key1") is False

    def test_expired_cleaned_from_keys(self):
        now = [0.0]
        s = InMemoryStateStore(clock=lambda: now[0], default_ttl=1.0)
        s.set("key1", "value1")
        now[0] = 5.0
        assert "key1" not in s.keys()

    def test_increment_expired_resets(self):
        now = [0.0]
        s = InMemoryStateStore(clock=lambda: now[0], default_ttl=1.0)
        s.increment("counter")
        now[0] = 5.0
        assert s.increment("counter") == 1  # Reset, not 2


class TestCapacity:
    def test_bounded(self):
        s = _store(max_keys=5)
        for i in range(10):
            s.set(f"key{i}", f"val{i}")
        assert s.key_count <= 5

    def test_eviction_frees_space(self):
        now = [0.0]
        s = InMemoryStateStore(clock=lambda: now[0], max_keys=3, default_ttl=1.0)
        s.set("a", "1")
        s.set("b", "2")
        s.set("c", "3")
        now[0] = 5.0  # All expired
        s.set("d", "4")  # Should reap expired and fit
        assert s.get("d") == "4"


class TestKeys:
    def test_list_all_keys(self):
        s = _store()
        s.set("a", 1)
        s.set("b", 2)
        s.set("c", 3)
        assert s.keys() == ["a", "b", "c"]

    def test_filter_keys(self):
        s = _store()
        s.set("t1:rate:u1", 1)
        s.set("t1:rate:u2", 2)
        s.set("t2:rate:u1", 3)
        assert len(s.keys("t1:rate")) == 2

    def test_empty_keys(self):
        s = _store()
        assert s.keys() == []


class TestSummary:
    def test_summary_fields(self):
        s = _store()
        s.set("k", "v")
        sm = s.summary()
        assert sm["keys"] == 1
        assert sm["backend"] == "in_memory"


class TestBaseStore:
    def test_defaults(self):
        s = DistributedStateStore()
        assert s.get("k") is None
        assert s.set("k", "v") is False
        assert s.delete("k") is False
        assert s.exists("k") is False
        assert s.increment("k") == 0
        assert s.keys() == []
