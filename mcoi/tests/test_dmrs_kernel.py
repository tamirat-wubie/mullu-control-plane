"""Tests for the DMRS Kernel -- routing logic, proof construction, and edge cases."""

from __future__ import annotations

import hashlib
import json

import pytest

from mcoi_runtime.contracts.dmrs import (
    DMRSConstraint,
    DMRSContext,
    DMRSDemand,
    DMRSMemoryVersion,
    DMRSProof,
    DMRSRouteError,
    DMRSRouteResult,
    DMRSRule,
)
from mcoi_runtime.core.dmrs_kernel import DMRSKernel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(depth: int = 0, load: str = "low", flags: tuple[str, ...] = ()) -> DMRSContext:
    return DMRSContext(depth=depth, load=load, flags=flags)


# ---------------------------------------------------------------------------
# Context validation
# ---------------------------------------------------------------------------

class TestDMRSContext:
    def test_valid_context(self) -> None:
        ctx = _ctx(1, "medium", ("trace_enabled",))
        assert ctx.depth == 1
        assert ctx.load == "medium"
        assert ctx.flags == ("trace_enabled",)

    def test_depth_below_zero_rejected(self) -> None:
        with pytest.raises(ValueError, match="depth must be between 0 and 3"):
            _ctx(depth=-1)

    def test_depth_above_three_rejected(self) -> None:
        with pytest.raises(ValueError, match="depth must be between 0 and 3"):
            _ctx(depth=4)

    def test_invalid_load_rejected(self) -> None:
        with pytest.raises(ValueError, match="load must be one of"):
            _ctx(load="extreme")

    def test_invalid_flag_rejected(self) -> None:
        with pytest.raises(ValueError, match="invalid flag"):
            _ctx(flags=("nonexistent",))


# ---------------------------------------------------------------------------
# Demand-based routing
# ---------------------------------------------------------------------------

class TestDemandRouting:
    def test_archive_demand_returns_va_arch(self) -> None:
        result = DMRSKernel.route(_ctx(), DMRSDemand.ARCHIVE)
        assert isinstance(result, DMRSRouteResult)
        assert result.version is DMRSMemoryVersion.VA_ARCH

    def test_recall_low_returns_v1_light(self) -> None:
        result = DMRSKernel.route(_ctx(load="low"), DMRSDemand.RECALL)
        assert result.version is DMRSMemoryVersion.V1_LIGHT

    def test_recall_medium_returns_v2_std(self) -> None:
        result = DMRSKernel.route(_ctx(load="medium"), DMRSDemand.RECALL)
        assert result.version is DMRSMemoryVersion.V2_STD

    def test_recall_high_returns_v2_std(self) -> None:
        result = DMRSKernel.route(_ctx(load="high"), DMRSDemand.RECALL)
        assert result.version is DMRSMemoryVersion.V2_STD

    def test_recall_critical_returns_v2_std(self) -> None:
        result = DMRSKernel.route(_ctx(load="critical"), DMRSDemand.RECALL)
        assert result.version is DMRSMemoryVersion.V2_STD

    def test_analysis_depth_0_returns_v2_std(self) -> None:
        result = DMRSKernel.route(_ctx(depth=0), DMRSDemand.ANALYSIS)
        assert result.version is DMRSMemoryVersion.V2_STD

    def test_analysis_depth_1_returns_v2_std(self) -> None:
        result = DMRSKernel.route(_ctx(depth=1), DMRSDemand.ANALYSIS)
        assert result.version is DMRSMemoryVersion.V2_STD

    def test_analysis_depth_2_returns_v3_deep(self) -> None:
        result = DMRSKernel.route(_ctx(depth=2), DMRSDemand.ANALYSIS)
        assert result.version is DMRSMemoryVersion.V3_DEEP

    def test_analysis_depth_3_returns_v3_deep(self) -> None:
        result = DMRSKernel.route(_ctx(depth=3), DMRSDemand.ANALYSIS)
        assert result.version is DMRSMemoryVersion.V3_DEEP

    def test_reasoning_returns_v2_std(self) -> None:
        result = DMRSKernel.route(_ctx(), DMRSDemand.REASONING)
        assert result.version is DMRSMemoryVersion.V2_STD


# ---------------------------------------------------------------------------
# Flag overrides
# ---------------------------------------------------------------------------

class TestFlagOverrides:
    def test_archive_mode_overrides_recall(self) -> None:
        result = DMRSKernel.route(_ctx(flags=("archive_mode",)), DMRSDemand.RECALL)
        assert result.version is DMRSMemoryVersion.VA_ARCH

    def test_archive_mode_overrides_reasoning(self) -> None:
        result = DMRSKernel.route(_ctx(flags=("archive_mode",)), DMRSDemand.REASONING)
        assert result.version is DMRSMemoryVersion.VA_ARCH

    def test_readonly_overrides_analysis_deep(self) -> None:
        result = DMRSKernel.route(_ctx(depth=3, flags=("readonly",)), DMRSDemand.ANALYSIS)
        assert result.version is DMRSMemoryVersion.V1_LIGHT

    def test_archive_mode_takes_precedence_over_readonly(self) -> None:
        result = DMRSKernel.route(
            _ctx(flags=("archive_mode", "readonly")), DMRSDemand.RECALL
        )
        assert result.version is DMRSMemoryVersion.VA_ARCH


# ---------------------------------------------------------------------------
# Proof construction
# ---------------------------------------------------------------------------

class TestProofConstruction:
    def test_proof_has_sha256_context_hash(self) -> None:
        result = DMRSKernel.route(_ctx(), DMRSDemand.RECALL)
        assert isinstance(result, DMRSRouteResult)
        assert len(result.proof.context_hash) == 64  # SHA-256 hex length

    def test_proof_has_sha256_precedence_hash(self) -> None:
        result = DMRSKernel.route(_ctx(), DMRSDemand.RECALL)
        assert len(result.proof.precedence_hash) == 64

    def test_proof_determinism(self) -> None:
        ctx = _ctx(1, "medium")
        r1 = DMRSKernel.route(ctx, DMRSDemand.ANALYSIS)
        r2 = DMRSKernel.route(ctx, DMRSDemand.ANALYSIS)
        assert r1.proof.context_hash == r2.proof.context_hash
        assert r1.proof.precedence_hash == r2.proof.precedence_hash

    def test_proof_constraints_verified(self) -> None:
        result = DMRSKernel.route(_ctx(), DMRSDemand.RECALL)
        expected = tuple(c.value for c in DMRSConstraint)
        assert result.proof.constraints_verified == expected

    def test_routed_at_is_iso_string(self) -> None:
        result = DMRSKernel.route(_ctx(), DMRSDemand.RECALL)
        assert isinstance(result.routed_at, str)
        assert "T" in result.routed_at  # ISO format includes T separator
