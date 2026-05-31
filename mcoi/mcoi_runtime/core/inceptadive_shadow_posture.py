"""Read-only posture models for the InceptaDive Shadow Pass.

Purpose: expose health and console-grade summaries for shadow interrogation
without exposing raw request text, private memory, or execution authority.
Governance scope: observability only; posture snapshots cannot approve, mutate,
retrieve, promote, schedule, or execute.
Dependencies: shared shadow types and runtime invariant helpers.
Invariants: posture is deterministic, redacted by construction, and derived only
from bounded config/result/receipt metadata.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
import json
from typing import Mapping, Sequence

from mcoi_runtime.core.inceptadive_shadow_types import (
    ShadowInterrogationConfig,
    ShadowMode,
    ShadowPassResult,
    ShadowReceipt,
    ShadowVerdict,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


def _canonical_json(value: Mapping[str, object]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), default=str)


def _snapshot_hash(value: Mapping[str, object]) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ShadowHealthPosture:
    """Read-only health posture for the shadow subsystem."""

    posture_id: str
    enabled: bool
    light_always_on: bool
    deep_enabled: bool
    strict_preflight_enabled: bool
    receipts_enabled: bool
    max_findings: int
    max_depth: int
    dependency_available: bool
    deep_engine_available: bool
    strict_fail_closed_ready: bool
    created_at: str = "1970-01-01T00:00:00+00:00"
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        if not self.posture_id.strip():
            raise RuntimeCoreInvariantError("posture_id must be non-empty")
        if self.max_findings < 1:
            raise RuntimeCoreInvariantError("max_findings must be positive")
        if self.max_depth < 1:
            raise RuntimeCoreInvariantError("max_depth must be positive")
        if self.snapshot_hash and self.snapshot_hash != self.expected_snapshot_hash():
            raise RuntimeCoreInvariantError("ShadowHealthPosture snapshot_hash mismatch")

    @property
    def status(self) -> str:
        if not self.enabled:
            return "disabled"
        if not self.dependency_available:
            return "degraded"
        if self.strict_preflight_enabled and not self.strict_fail_closed_ready:
            return "degraded"
        return "ready"

    def to_dict(self, *, include_snapshot_hash: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "posture_id": self.posture_id,
            "status": self.status,
            "enabled": self.enabled,
            "light_always_on": self.light_always_on,
            "deep_enabled": self.deep_enabled,
            "strict_preflight_enabled": self.strict_preflight_enabled,
            "receipts_enabled": self.receipts_enabled,
            "max_findings": self.max_findings,
            "max_depth": self.max_depth,
            "dependency_available": self.dependency_available,
            "deep_engine_available": self.deep_engine_available,
            "strict_fail_closed_ready": self.strict_fail_closed_ready,
            "created_at": self.created_at,
            "execution_authority": False,
            "raw_request_text_exposed": False,
            "private_memory_exposed": False,
        }
        if include_snapshot_hash:
            value["snapshot_hash"] = self.snapshot_hash
        return value

    def expected_snapshot_hash(self) -> str:
        return _snapshot_hash(self.to_dict(include_snapshot_hash=False))

    def with_integrity(self) -> "ShadowHealthPosture":
        posture_id = self.posture_id
        if posture_id == "pending":
            posture_id = stable_identifier(
                "shadow-health",
                {
                    "enabled": self.enabled,
                    "deep_enabled": self.deep_enabled,
                    "strict_preflight_enabled": self.strict_preflight_enabled,
                    "receipts_enabled": self.receipts_enabled,
                    "created_at": self.created_at,
                },
            )
        unsigned = replace(self, posture_id=posture_id, snapshot_hash="")
        return replace(unsigned, snapshot_hash=unsigned.expected_snapshot_hash())


@dataclass(frozen=True)
class ShadowConsoleSummary:
    """Read-only operator summary for recent shadow pass activity."""

    summary_id: str
    enabled: bool
    recent_result_count: int
    receipt_count: int
    mode_counts: tuple[str, ...]
    verdict_counts: tuple[str, ...]
    top_finding_kinds: tuple[str, ...]
    deep_trigger_count: int
    repair_required_count: int
    block_recommended_count: int
    escalation_count: int
    constructive_delta_count: int
    fracture_delta_count: int
    last_result_snapshot_hash: str = ""
    created_at: str = "1970-01-01T00:00:00+00:00"
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        if not self.summary_id.strip():
            raise RuntimeCoreInvariantError("summary_id must be non-empty")
        for field_name, value in {
            "recent_result_count": self.recent_result_count,
            "receipt_count": self.receipt_count,
            "deep_trigger_count": self.deep_trigger_count,
            "repair_required_count": self.repair_required_count,
            "block_recommended_count": self.block_recommended_count,
            "escalation_count": self.escalation_count,
            "constructive_delta_count": self.constructive_delta_count,
            "fracture_delta_count": self.fracture_delta_count,
        }.items():
            if value < 0:
                raise RuntimeCoreInvariantError(field_name + " must be non-negative")
        if self.snapshot_hash and self.snapshot_hash != self.expected_snapshot_hash():
            raise RuntimeCoreInvariantError("ShadowConsoleSummary snapshot_hash mismatch")

    def to_dict(self, *, include_snapshot_hash: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "summary_id": self.summary_id,
            "enabled": self.enabled,
            "recent_result_count": self.recent_result_count,
            "receipt_count": self.receipt_count,
            "mode_counts": list(self.mode_counts),
            "verdict_counts": list(self.verdict_counts),
            "top_finding_kinds": list(self.top_finding_kinds),
            "deep_trigger_count": self.deep_trigger_count,
            "repair_required_count": self.repair_required_count,
            "block_recommended_count": self.block_recommended_count,
            "escalation_count": self.escalation_count,
            "constructive_delta_count": self.constructive_delta_count,
            "fracture_delta_count": self.fracture_delta_count,
            "last_result_snapshot_hash": self.last_result_snapshot_hash,
            "created_at": self.created_at,
            "execution_authority": False,
            "raw_request_text_exposed": False,
            "private_memory_exposed": False,
        }
        if include_snapshot_hash:
            value["snapshot_hash"] = self.snapshot_hash
        return value

    def expected_snapshot_hash(self) -> str:
        return _snapshot_hash(self.to_dict(include_snapshot_hash=False))

    def with_integrity(self) -> "ShadowConsoleSummary":
        summary_id = self.summary_id
        if summary_id == "pending":
            summary_id = stable_identifier(
                "shadow-console",
                {
                    "enabled": self.enabled,
                    "recent_result_count": self.recent_result_count,
                    "receipt_count": self.receipt_count,
                    "last_result_snapshot_hash": self.last_result_snapshot_hash,
                    "created_at": self.created_at,
                },
            )
        unsigned = replace(self, summary_id=summary_id, snapshot_hash="")
        return replace(unsigned, snapshot_hash=unsigned.expected_snapshot_hash())


def build_shadow_health_posture(
    config: ShadowInterrogationConfig,
    *,
    receipts_enabled: bool,
    dependency_available: bool = True,
    deep_engine_available: bool = False,
    created_at: str = "1970-01-01T00:00:00+00:00",
) -> ShadowHealthPosture:
    """Build a deterministic health posture snapshot from bounded config."""

    strict_fail_closed_ready = bool(config.enabled and config.strict_preflight_enabled and dependency_available)
    return ShadowHealthPosture(
        posture_id="pending",
        enabled=config.enabled,
        light_always_on=config.light_always_on,
        deep_enabled=config.deep_enabled,
        strict_preflight_enabled=config.strict_preflight_enabled,
        receipts_enabled=receipts_enabled,
        max_findings=config.max_findings,
        max_depth=config.max_depth,
        dependency_available=dependency_available,
        deep_engine_available=deep_engine_available,
        strict_fail_closed_ready=strict_fail_closed_ready,
        created_at=created_at,
    ).with_integrity()


def build_shadow_console_summary(
    config: ShadowInterrogationConfig,
    *,
    results: Sequence[ShadowPassResult] = (),
    receipts: Sequence[ShadowReceipt] = (),
    created_at: str = "1970-01-01T00:00:00+00:00",
) -> ShadowConsoleSummary:
    """Build a redacted operator summary from recent shadow metadata."""

    result_tuple = tuple(results)
    receipt_tuple = tuple(receipts)
    mode_counts = _counter_entries(result.mode.value for result in result_tuple)
    verdict_counts = _counter_entries(result.verdict.value for result in result_tuple)
    finding_counter = Counter(
        finding.kind.value
        for result in result_tuple
        for finding in result.findings
    )
    top_finding_kinds = tuple(
        f"{kind}:{count}" for kind, count in sorted(finding_counter.items(), key=lambda item: (-item[1], item[0]))[:5]
    )
    last_result_snapshot_hash = result_tuple[-1].snapshot_hash if result_tuple else ""
    return ShadowConsoleSummary(
        summary_id="pending",
        enabled=config.enabled,
        recent_result_count=len(result_tuple),
        receipt_count=len(receipt_tuple),
        mode_counts=mode_counts,
        verdict_counts=verdict_counts,
        top_finding_kinds=top_finding_kinds,
        deep_trigger_count=sum(1 for result in result_tuple if result.needs_deep_pass or result.mode == ShadowMode.DEEP),
        repair_required_count=sum(1 for result in result_tuple if result.needs_repair),
        block_recommended_count=sum(1 for result in result_tuple if result.block_recommended),
        escalation_count=sum(1 for result in result_tuple if result.needs_escalation or result.verdict == ShadowVerdict.ESCALATE),
        constructive_delta_count=sum(result.constructive_delta_count for result in result_tuple),
        fracture_delta_count=sum(result.fracture_delta_count for result in result_tuple),
        last_result_snapshot_hash=last_result_snapshot_hash,
        created_at=created_at,
    ).with_integrity()


def _counter_entries(values: Sequence[str] | object) -> tuple[str, ...]:
    counter = Counter(values)
    return tuple(f"{key}:{counter[key]}" for key in sorted(counter))
