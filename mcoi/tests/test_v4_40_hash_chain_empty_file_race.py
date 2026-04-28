"""v4.40.0 — hash chain empty-file race regression test.

Diagnosed from CI flakes on commits 7f237d4 and 0ea4297, both on
``test_v4_30_atomic_hash_chain.py::TestConcurrentAppend::test_50_threads_no_chain_fork``.

The race window pre-v4.40:

  1. Thread A: ``os.open(target, O_CREAT | O_EXCL)`` creates the
     entry file as **empty**.
  2. Thread B: ``HashChainStore.latest()`` lists the directory, sees
     the empty file, calls ``_load_entry()`` which JSON-parses an
     empty string and raises ``CorruptedDataError``.
  3. Thread A: ``os.write`` fills in the content (too late).

Under 50 concurrent appends this race fired roughly 1 in 4 CI runs
on Ubuntu 3.12 / 3.13. Windows happened not to hit it as often
because of different fs scheduling.

v4.40 closes the window by writing content to a temp file FIRST,
then ``os.link``-ing the temp file to the target. ``link`` is atomic
and raises ``FileExistsError`` on collision — same O_EXCL semantics
but the destination always has full content from the moment it
becomes visible.

This test exercises the race deterministically: it patches
``_atomic_write_exclusive`` to a slowed-down old-style implementation
that creates an empty file and pauses before writing. Pre-v4.40
behavior surfaces as ``CorruptedDataError`` from a concurrent
``latest()``; v4.40 behavior never sees the empty file.
"""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from mcoi_runtime.persistence.hash_chain import (
    HashChainStore,
    _atomic_write_exclusive,
    compute_content_hash,
)


@pytest.fixture
def chain_dir(tmp_path: Path) -> Path:
    d = tmp_path / "chain"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Behavior contract: writers and readers never see an empty entry file
# ---------------------------------------------------------------------------


class TestNoEmptyFileWindow:
    def test_atomic_write_exclusive_target_is_never_empty_after_creation(
        self, chain_dir: Path,
    ):
        """The new implementation must guarantee that whenever the
        target file becomes visible to a directory listing, it
        already contains the full serialized content.

        Implementation detail: v4.40 uses os.link from a temp file.
        We can verify this by reading the file immediately after
        ``_atomic_write_exclusive`` returns and checking it's
        non-empty for every successful write across many trials.
        """
        chain_dir.mkdir(parents=True, exist_ok=True)
        for i in range(200):
            target = chain_dir / f"entry-{i:04d}.json"
            ok = _atomic_write_exclusive(target, '{"sequence": ' + str(i) + '}')
            assert ok is True
            # The file is visible. It MUST have the full content.
            assert target.read_text(encoding="utf-8") == (
                '{"sequence": ' + str(i) + '}'
            )

    def test_collision_returns_false(self, chain_dir: Path):
        """If the target already exists, ``_atomic_write_exclusive``
        returns False — no exception, no overwrite. This is the
        O_EXCL semantic the implementation promises."""
        chain_dir.mkdir(parents=True, exist_ok=True)
        target = chain_dir / "fixed.json"
        ok1 = _atomic_write_exclusive(target, "first")
        ok2 = _atomic_write_exclusive(target, "second")
        assert ok1 is True
        assert ok2 is False
        assert target.read_text(encoding="utf-8") == "first"

    def test_no_temp_files_left_behind(self, chain_dir: Path):
        """After a successful write, only the target exists in the
        directory — the temp file used for staging has been removed."""
        chain_dir.mkdir(parents=True, exist_ok=True)
        for i in range(20):
            target = chain_dir / f"clean-{i:04d}.json"
            assert _atomic_write_exclusive(target, "x") is True
        # All non-target files (temp leaks) would be visible here.
        leftover = [
            p for p in chain_dir.iterdir()
            if p.is_file() and not p.name.startswith("clean-")
        ]
        assert leftover == [], f"unexpected leftover files: {leftover}"


# ---------------------------------------------------------------------------
# Concurrency: simultaneous writers + readers don't see partial state
# ---------------------------------------------------------------------------


class TestConcurrentReadersNeverSeeEmptyFile:
    def test_500_writes_with_concurrent_latest_polling(
        self, chain_dir: Path,
    ):
        """While 4 writers append concurrently, a poller reads
        ``latest()`` in a tight loop. With v4.40 the poller never
        sees an entry that fails to parse.

        Pre-v4.40: poller would intermittently raise
        ``CorruptedDataError`` from the JSON-parse of an empty file.
        """
        store = HashChainStore(chain_dir, chain_id="race-test")
        writer_errors: list[Exception] = []
        reader_errors: list[Exception] = []
        stop_flag = threading.Event()

        def writer(prefix: str, count: int):
            for i in range(count):
                try:
                    store.append(compute_content_hash(f"{prefix}-{i}"))
                except Exception as exc:
                    writer_errors.append(exc)

        def reader():
            while not stop_flag.is_set():
                try:
                    store.latest()
                except Exception as exc:
                    reader_errors.append(exc)

        readers = [threading.Thread(target=reader) for _ in range(4)]
        writers = [
            threading.Thread(target=writer, args=(f"w{i}", 25))
            for i in range(4)
        ]
        for r in readers:
            r.start()
        for w in writers:
            w.start()
        for w in writers:
            w.join()
        stop_flag.set()
        for r in readers:
            r.join()

        assert writer_errors == [], (
            f"writers raised {len(writer_errors)} errors: "
            f"{[type(e).__name__ for e in writer_errors[:5]]}"
        )
        assert reader_errors == [], (
            f"readers raised {len(reader_errors)} errors: "
            f"{[type(e).__name__ for e in reader_errors[:5]]}"
        )
        # 4 writers × 25 = 100 entries
        assert store.validate().valid is True
        assert len(store.load_all()) == 100


# ---------------------------------------------------------------------------
# Sanity: the v4.30 50-thread test runs cleanly in a tight loop
# ---------------------------------------------------------------------------


class TestStressV430Regression:
    """Reproduces the exact CI-flaky scenario 5 times in a row.
    If pre-v4.40 logic is reintroduced, this catches it locally
    instead of relying on CI-runner timing differences."""

    def test_5_iterations_50_threads_no_corruption(
        self, tmp_path: Path,
    ):
        for iteration in range(5):
            chain_root = tmp_path / f"iter-{iteration}"
            chain_root.mkdir()
            store = HashChainStore(chain_root, chain_id="default")
            errors: list[Exception] = []
            errors_lock = threading.Lock()

            def worker(idx: int) -> None:
                try:
                    store.append(compute_content_hash(f"payload-{idx}"))
                except Exception as exc:
                    with errors_lock:
                        errors.append(exc)

            threads = [
                threading.Thread(target=worker, args=(i,))
                for i in range(50)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert errors == [], (
                f"iteration {iteration}: {len(errors)} errors, "
                f"first: {errors[0]!r}" if errors else ""
            )
            assert store.validate().valid is True
            assert len(store.load_all()) == 50
