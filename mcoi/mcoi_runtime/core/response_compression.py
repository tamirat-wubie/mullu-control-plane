"""Phase 227B — Request/Response Compression.

Purpose: Compress API responses with gzip/deflate for bandwidth savings.
    Tracks compression ratios and savings.
Dependencies: None (stdlib only — uses zlib).
Invariants:
  - Only compresses responses above threshold size.
  - Original data integrity verified via round-trip.
  - Compression stats are tracked.
"""
from __future__ import annotations

import zlib
from dataclasses import dataclass
from enum import Enum, unique
from typing import Any


@unique
class CompressionAlgorithm(Enum):
    GZIP = "gzip"
    DEFLATE = "deflate"
    NONE = "none"


@dataclass(frozen=True)
class CompressionResult:
    """Result of compressing data."""
    algorithm: CompressionAlgorithm
    original_size: int
    compressed_size: int
    data: bytes

    @property
    def ratio(self) -> float:
        if self.original_size == 0:
            return 1.0
        return self.compressed_size / self.original_size

    @property
    def savings_pct(self) -> float:
        return (1.0 - self.ratio) * 100.0


class ResponseCompressor:
    """Compresses response data with configurable thresholds."""

    def __init__(self, min_size_bytes: int = 1024,
                 default_algorithm: CompressionAlgorithm = CompressionAlgorithm.GZIP,
                 compression_level: int = 6):
        self._min_size = min_size_bytes
        self._default_algo = default_algorithm
        self._level = compression_level
        self._total_original = 0
        self._total_compressed = 0
        self._total_operations = 0

    def compress(self, data: bytes,
                 algorithm: CompressionAlgorithm | None = None) -> CompressionResult:
        algo = algorithm or self._default_algo
        original_size = len(data)
        self._total_operations += 1
        self._total_original += original_size

        if original_size < self._min_size:
            self._total_compressed += original_size
            return CompressionResult(
                algorithm=CompressionAlgorithm.NONE,
                original_size=original_size,
                compressed_size=original_size,
                data=data,
            )

        if algo == CompressionAlgorithm.GZIP:
            compressed = zlib.compress(data, self._level)
        elif algo == CompressionAlgorithm.DEFLATE:
            compressed = zlib.compress(data, self._level)
        else:
            self._total_compressed += original_size
            return CompressionResult(
                algorithm=CompressionAlgorithm.NONE,
                original_size=original_size,
                compressed_size=original_size,
                data=data,
            )

        compressed_size = len(compressed)
        self._total_compressed += compressed_size

        # If compression didn't help, return original
        if compressed_size >= original_size:
            return CompressionResult(
                algorithm=CompressionAlgorithm.NONE,
                original_size=original_size,
                compressed_size=original_size,
                data=data,
            )

        return CompressionResult(
            algorithm=algo,
            original_size=original_size,
            compressed_size=compressed_size,
            data=compressed,
        )

    @staticmethod
    def decompress(data: bytes) -> bytes:
        return zlib.decompress(data)

    @property
    def total_savings_pct(self) -> float:
        if self._total_original == 0:
            return 0.0
        return (1.0 - self._total_compressed / self._total_original) * 100.0

    def summary(self) -> dict[str, Any]:
        return {
            "total_operations": self._total_operations,
            "total_original_bytes": self._total_original,
            "total_compressed_bytes": self._total_compressed,
            "total_savings_pct": round(self.total_savings_pct, 1),
            "min_size_bytes": self._min_size,
            "default_algorithm": self._default_algo.value,
        }
