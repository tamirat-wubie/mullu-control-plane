"""Tests for Phase 227B — Response Compression."""
from __future__ import annotations
import pytest
from mcoi_runtime.core.response_compression import (
    CompressionAlgorithm, ResponseCompressor,
)


class TestResponseCompressor:
    def test_skip_small_data(self):
        comp = ResponseCompressor(min_size_bytes=1024)
        data = b"small"
        result = comp.compress(data)
        assert result.algorithm == CompressionAlgorithm.NONE
        assert result.data == data
        assert result.original_size == len(data)

    def test_gzip_compression(self):
        comp = ResponseCompressor(min_size_bytes=10)
        data = b"x" * 1000
        result = comp.compress(data)
        assert result.algorithm == CompressionAlgorithm.GZIP
        assert result.compressed_size < result.original_size
        assert result.savings_pct > 0

    def test_deflate_compression(self):
        comp = ResponseCompressor(min_size_bytes=10)
        data = b"y" * 1000
        result = comp.compress(data, algorithm=CompressionAlgorithm.DEFLATE)
        assert result.algorithm == CompressionAlgorithm.DEFLATE
        assert result.compressed_size < result.original_size

    def test_roundtrip(self):
        comp = ResponseCompressor(min_size_bytes=10)
        original = b"Hello, this is a test message " * 50
        result = comp.compress(original)
        decompressed = comp.decompress(result.data)
        assert decompressed == original

    def test_incompressible_data(self):
        comp = ResponseCompressor(min_size_bytes=1)
        # Random-looking data that won't compress well
        import os
        data = os.urandom(100)
        result = comp.compress(data)
        # Either compressed or returned as-is
        assert result.original_size == len(data)

    def test_ratio_small_data(self):
        comp = ResponseCompressor(min_size_bytes=1024)
        result = comp.compress(b"tiny")
        assert result.ratio == 1.0
        assert result.savings_pct == 0.0

    def test_empty_data(self):
        comp = ResponseCompressor(min_size_bytes=0)
        result = comp.compress(b"")
        assert result.original_size == 0

    def test_summary(self):
        comp = ResponseCompressor(min_size_bytes=10)
        comp.compress(b"x" * 1000)
        s = comp.summary()
        assert s["total_operations"] == 1
        assert s["total_original_bytes"] == 1000
        assert s["total_compressed_bytes"] < 1000
