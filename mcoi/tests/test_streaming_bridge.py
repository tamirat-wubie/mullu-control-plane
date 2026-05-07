"""Streaming Response Bridge Tests."""

from gateway.streaming_bridge import StreamingBridge


def _bridge(**kw):
    return StreamingBridge(clock=kw.pop("clock", lambda: 0.0), **kw)


class TestBasicStreaming:
    def test_start_and_push(self):
        b = _bridge()
        sid = b.start_stream("wa", "+1", "t1")
        assert b.push_chunk(sid, "Hello ") is True
        assert b.push_chunk(sid, "world!") is True
        assert b.get_assembled(sid) == "Hello world!"

    def test_finalize(self):
        b = _bridge()
        sid = b.start_stream("wa", "+1", "t1")
        b.push_chunk(sid, "Done")
        session = b.finalize(sid)
        assert session is not None
        assert session.finalized is True
        assert session.assembled_content == "Done"

    def test_push_after_finalize_rejected(self):
        b = _bridge()
        sid = b.start_stream("wa", "+1", "t1")
        b.finalize(sid)
        assert b.push_chunk(sid, "late") is False

    def test_push_unknown_stream(self):
        b = _bridge()
        assert b.push_chunk("nonexistent", "data") is False

    def test_finalize_unknown(self):
        b = _bridge()
        assert b.finalize("nonexistent") is None

    def test_get_assembled_unknown(self):
        b = _bridge()
        assert b.get_assembled("nonexistent") is None


class TestChunkCallback:
    def test_callback_receives_chunks(self):
        received = []
        b = _bridge()
        sid = b.start_stream("wa", "+1", "t1")
        b.set_chunk_callback(sid, lambda c: received.append(c.content))
        b.push_chunk(sid, "A")
        b.push_chunk(sid, "B")
        assert received == ["A", "B"]

    def test_final_callback(self):
        finals = []
        b = _bridge()
        sid = b.start_stream("wa", "+1", "t1")
        b.set_chunk_callback(sid, lambda c: finals.append(c.is_final) if c.is_final else None)
        b.push_chunk(sid, "text")
        b.finalize(sid)
        assert True in finals

    def test_callback_exception_doesnt_fail_stream(self):
        def bad_callback(chunk):
            raise RuntimeError("callback crashed")
        b = _bridge()
        sid = b.start_stream("wa", "+1", "t1")
        b.set_chunk_callback(sid, bad_callback)
        assert b.push_chunk(sid, "data") is True  # Should not raise
        session = b.get_session(sid)
        assert session.assembled_content == "data"
        assert session.error == "callback delivery failed"
        assert b.callback_errors == 1

    def test_false_callback_result_is_counted(self):
        b = _bridge()
        sid = b.start_stream("wa", "+1", "t1")
        b.set_chunk_callback(sid, lambda chunk: False)
        assert b.push_chunk(sid, "data") is True
        session = b.get_session(sid)
        assert session.assembled_content == "data"
        assert session.error == "callback delivery failed"
        assert b.summary()["callback_errors"] == 1

    def test_false_final_callback_result_is_counted(self):
        b = _bridge()
        sid = b.start_stream("wa", "+1", "t1")
        b.set_chunk_callback(sid, lambda chunk: False)
        session = b.finalize(sid)
        assert session is not None
        assert session.finalized is True
        assert session.error == "callback delivery failed"
        assert b.summary()["callback_errors"] == 1

    def test_final_callback_exception_is_counted(self):
        def bad_callback(chunk):
            raise RuntimeError("callback crashed")
        b = _bridge()
        sid = b.start_stream("wa", "+1", "t1")
        b.set_chunk_callback(sid, bad_callback)
        session = b.finalize(sid)
        assert session is not None
        assert session.finalized is True
        assert session.error == "callback delivery failed"
        assert b.summary()["callback_errors"] == 1

    def test_set_callback_unknown(self):
        b = _bridge()
        assert b.set_chunk_callback("nonexistent", lambda c: None) is False


class TestTimeout:
    def test_stream_timeout(self):
        now = [0.0]
        b = StreamingBridge(clock=lambda: now[0], stream_timeout=5.0)
        sid = b.start_stream("wa", "+1", "t1")
        b.push_chunk(sid, "start")
        now[0] = 10.0  # Past timeout
        assert b.push_chunk(sid, "late") is False
        session = b.get_session(sid)
        assert session.finalized is True
        assert "timed out" in session.error


class TestSessionManagement:
    def test_active_count(self):
        b = _bridge()
        s1 = b.start_stream("wa", "+1", "t1")
        b.start_stream("wa", "+2", "t1")
        assert b.active_count == 2
        b.finalize(s1)
        assert b.active_count == 1

    def test_is_active(self):
        b = _bridge()
        sid = b.start_stream("wa", "+1", "t1")
        assert b.is_active(sid) is True
        b.finalize(sid)
        assert b.is_active(sid) is False
        assert b.is_active("nonexistent") is False

    def test_cleanup_finalized(self):
        b = _bridge()
        s1 = b.start_stream("wa", "+1", "t1")
        s2 = b.start_stream("wa", "+2", "t1")
        b.finalize(s1)
        removed = b.cleanup_finalized()
        assert removed == 1
        assert b.get_session(s1) is None
        assert b.get_session(s2) is not None

    def test_capacity_eviction(self):
        b = _bridge()
        b.MAX_STREAMS = 3
        for i in range(5):
            b.start_stream("wa", f"+{i}", "t1")
        assert len(b._streams) <= 3

    def test_session_to_dict(self):
        b = _bridge()
        sid = b.start_stream("wa", "+1", "t1")
        b.push_chunk(sid, "hello")
        session = b.get_session(sid)
        d = session.to_dict()
        assert d["chunk_count"] == 1
        assert d["total_chars"] == 5

    def test_summary(self):
        b = _bridge()
        b.start_stream("wa", "+1", "t1")
        s = b.summary()
        assert s["active_streams"] == 1
        assert s["stream_timeout"] > 0
        assert s["callback_errors"] == 0
