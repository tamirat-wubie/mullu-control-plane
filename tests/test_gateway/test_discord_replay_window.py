"""Discord interaction replay-window tests.

Tests: the Discord interaction verifier rejects stale or malformed signed
timestamps, bounding replay of captured valid interactions. Mirrors the Slack
adapter's 5-minute freshness window. The no-key skip path is unaffected.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.channels.discord import (  # noqa: E402
    DiscordAdapter,
    _timestamp_within_replay_window,
)

_KEY = "aa" * 32  # 32-byte hex public key (enables the verification path)


# --- Freshness helper ---


class TestTimestampWithinReplayWindow:
    def test_now_is_fresh(self):
        assert _timestamp_within_replay_window(str(int(time.time()))) is True

    def test_recent_within_window_is_fresh(self):
        assert _timestamp_within_replay_window(str(int(time.time()) - 299)) is True

    def test_stale_past_is_rejected(self):
        assert _timestamp_within_replay_window(str(int(time.time()) - 3600)) is False

    def test_far_future_is_rejected(self):
        assert _timestamp_within_replay_window(str(int(time.time()) + 3600)) is False

    def test_just_outside_window_is_rejected(self):
        assert _timestamp_within_replay_window(str(int(time.time()) - 301)) is False

    def test_malformed_is_rejected(self):
        assert _timestamp_within_replay_window("not-a-timestamp") is False

    def test_empty_is_rejected(self):
        assert _timestamp_within_replay_window("") is False


# --- verify_interaction integration ---


class TestVerifyInteractionReplay:
    def test_no_key_path_still_skips(self):
        # Regression: with no public key, verification is skipped before the
        # freshness check, so a non-timestamp value is still accepted.
        adapter = DiscordAdapter(bot_token="bot-123")
        assert adapter.verify_interaction("sig", "ts", "body") is True

    def test_stale_timestamp_rejected_on_key_path(self):
        adapter = DiscordAdapter(bot_token="bot-123", public_key=_KEY)
        stale = str(int(time.time()) - 3600)
        assert adapter.verify_interaction("00" * 64, stale, "body") is False

    def test_missing_timestamp_rejected_on_key_path(self):
        adapter = DiscordAdapter(bot_token="bot-123", public_key=_KEY)
        assert adapter.verify_interaction("00" * 64, "", "body") is False
