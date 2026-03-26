"""Tests for Phase 223C — Config Hot-Reload File Watcher."""
from __future__ import annotations

import json
import os
import tempfile
import time
import pytest

from mcoi_runtime.core.config_watcher import (
    ConfigFileWatcher,
    WatchedFile,
    json_parser,
)


class TestJsonParser:
    def test_valid_json(self):
        result = json_parser('{"key": "value"}')
        assert result == {"key": "value"}

    def test_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            json_parser("not json")


class TestConfigFileWatcher:
    def test_watch_and_unwatch(self):
        watcher = ConfigFileWatcher()
        wf = WatchedFile(path="/tmp/test.json", parser=json_parser, on_change=lambda c: None)
        watcher.watch(wf)
        assert watcher.watched_count == 1
        watcher.unwatch("/tmp/test.json")
        assert watcher.watched_count == 0

    def test_check_nonexistent_file(self):
        watcher = ConfigFileWatcher()
        wf = WatchedFile(path="/tmp/nonexistent_12345.json", parser=json_parser, on_change=lambda c: None)
        watcher.watch(wf)
        reloaded = watcher.check_once()
        assert reloaded == []

    def test_detect_change(self):
        received = []
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"version": 1}, f)
            path = f.name

        try:
            wf = WatchedFile(path=path, parser=json_parser, on_change=lambda c: received.append(c))
            watcher = ConfigFileWatcher()
            watcher.watch(wf)

            # First check sets baseline mtime (also triggers initial load since mtime was 0)
            watcher.check_once()
            received.clear()  # clear initial load

            # Modify file (ensure mtime changes)
            time.sleep(0.05)
            with open(path, "w") as f:
                json.dump({"version": 2}, f)

            reloaded = watcher.check_once()
            assert path in reloaded
            assert len(received) == 1
            assert received[0]["version"] == 2
        finally:
            os.unlink(path)

    def test_no_change_no_reload(self):
        received = []
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"v": 1}, f)
            path = f.name

        try:
            wf = WatchedFile(path=path, parser=json_parser, on_change=lambda c: received.append(c))
            watcher = ConfigFileWatcher()
            watcher.watch(wf)
            watcher.check_once()
            # Check again without modification
            reloaded = watcher.check_once()
            assert reloaded == []
        finally:
            os.unlink(path)

    def test_summary(self):
        watcher = ConfigFileWatcher(poll_interval=10.0)
        wf = WatchedFile(path="/tmp/test.json", parser=json_parser, on_change=lambda c: None)
        watcher.watch(wf)
        s = watcher.summary()
        assert s["watched_files"] == 1
        assert s["total_reloads"] == 0
        assert s["running"] is False
        assert s["poll_interval"] == 10.0

    def test_error_handling(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json")
            path = f.name

        try:
            wf = WatchedFile(path=path, parser=json_parser, on_change=lambda c: None)
            watcher = ConfigFileWatcher()
            watcher.watch(wf)
            # First check triggers reload (mtime 0 -> file mtime), but parse fails
            reloaded = watcher.check_once()
            assert reloaded == []
            s = watcher.summary()
            assert s["total_errors"] == 1  # parse error on invalid JSON
        finally:
            os.unlink(path)

    def test_start_stop(self):
        watcher = ConfigFileWatcher(poll_interval=0.1)
        watcher.start()
        assert watcher.summary()["running"] is True
        watcher.stop()
        assert watcher.summary()["running"] is False
