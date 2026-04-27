"""Tests for HTTP connector read-timeout enforcement.

Proves the connector terminates slow-trickle responses that exceed
the read_timeout_seconds deadline, even if the connection was established.
"""
from __future__ import annotations

import threading
import http.server
import time
import pytest

from mcoi_runtime.adapters.http_connector import HttpConnector, HttpConnectorConfig
from mcoi_runtime.contracts.integration import ConnectorDescriptor, ConnectorStatus
from mcoi_runtime.contracts._shared_enums import EffectClass, TrustClass


CLOCK = lambda: "2026-03-27T12:00:00Z"


def _make_descriptor(connector_id: str = "test-http") -> ConnectorDescriptor:
    return ConnectorDescriptor(
        connector_id=connector_id, name="Test HTTP",
        provider="test", effect_class=EffectClass.EXTERNAL_READ,
        trust_class=TrustClass.TRUSTED_INTERNAL, credential_scope_id="test",
        enabled=True,
    )


class _SlowTrickleHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that sends response headers immediately, then trickles body slowly."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        # Send one byte per 0.5 seconds — a slow trickle
        for i in range(100):
            try:
                self.wfile.write(b"x")
                self.wfile.flush()
                time.sleep(0.5)
            except (BrokenPipeError, ConnectionResetError, OSError):
                break

    def log_message(self, format, *args):
        pass  # Suppress server logs during tests


class _FastHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that responds immediately."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"hello world")

    def log_message(self, format, *args):
        pass


def _start_server(handler_class, port=0):
    server = http.server.HTTPServer(("127.0.0.1", port), handler_class)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


class TestReadTimeoutConfig:
    def test_default_read_timeout(self):
        config = HttpConnectorConfig()
        assert config.read_timeout_seconds == 60.0

    def test_custom_read_timeout(self):
        config = HttpConnectorConfig(read_timeout_seconds=5.0)
        assert config.read_timeout_seconds == 5.0

    def test_invalid_read_timeout(self):
        with pytest.raises(ValueError, match="read_timeout_seconds"):
            HttpConnectorConfig(read_timeout_seconds=0)

    def test_negative_read_timeout(self):
        with pytest.raises(ValueError, match="read_timeout_seconds"):
            HttpConnectorConfig(read_timeout_seconds=-1)


class TestReadTimeoutEnforcement:
    def test_slow_trickle_terminated_via_mock(self):
        """Read timeout terminates slow body reads (mock bypasses SSRF check)."""
        import io
        import unittest.mock as mock

        class SlowReader(io.RawIOBase):
            """Simulates a slow response body — reads block for 0.5s each."""
            def __init__(self):
                self._data = b"x" * 1000
                self._pos = 0
            def readinto(self, b):
                if self._pos >= len(self._data):
                    return 0
                time.sleep(0.5)  # Slow trickle
                chunk = min(len(b), 1)
                b[:chunk] = self._data[self._pos:self._pos + chunk]
                self._pos += chunk
                return chunk
            def readable(self):
                return True

        connector = HttpConnector(
            clock=CLOCK,
            config=HttpConnectorConfig(
                timeout_seconds=5.0,
                read_timeout_seconds=1.0,  # 1 second read deadline
            ),
        )
        desc = _make_descriptor()

        # Mock the opener to bypass SSRF and return a slow body.
        # v4.29.0 (audit F10): also mock _resolve_and_check + the
        # per-request pinned-opener factory.
        fake_response = mock.MagicMock()
        fake_response.status = 200
        fake_response.headers = {"Content-Type": "text/plain"}
        fake_response.read = SlowReader().read
        fake_response.__enter__ = lambda s: s
        fake_response.__exit__ = mock.MagicMock(return_value=False)

        fake_opener = mock.MagicMock()
        fake_opener.open = mock.MagicMock(return_value=fake_response)
        with (
            mock.patch(
                "mcoi_runtime.adapters.http_connector._resolve_and_check",
                return_value=(False, "93.184.216.34"),
            ),
            mock.patch(
                "mcoi_runtime.adapters.http_connector._build_pinned_opener",
                return_value=fake_opener,
            ),
        ):
            start = time.monotonic()
            result = connector.invoke(desc, {"url": "https://example.com/slow"})
            elapsed = time.monotonic() - start

        assert result.status == ConnectorStatus.TIMEOUT
        assert result.error_code == "read_timeout"
        assert elapsed < 3.0  # Should terminate well before full read

    def test_ssrf_blocks_localhost(self):
        """SSRF protection blocks localhost even with valid server."""
        connector = HttpConnector(clock=CLOCK, config=HttpConnectorConfig())
        desc = _make_descriptor()
        result = connector.invoke(desc, {"url": "http://127.0.0.1:9999/"})
        assert result.status == ConnectorStatus.FAILED
        assert result.error_code == "blocked_private_address"
