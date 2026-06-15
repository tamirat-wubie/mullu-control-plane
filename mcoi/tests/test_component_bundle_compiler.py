"""Tests for the Component Harness bundle compiler.

Purpose: prove product-bundle compilation joins registry, read-model, and
simulation evidence without granting execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component_bundle_compiler runtime module.
Invariants: bundle compilation is preview-only, deterministic, and fail-closed
for unknown bundles or live-authority drift.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.app.component_bundle_compiler import (
    ComponentBundleCompilationError,
    compile_component_bundle,
    compile_foundation_component_bundles,
)
from mcoi_runtime.app.component_read_model import build_component_read_model


def test_component_bundle_compiler_compiles_personal_assistant_v0_preview() -> None:
    report = compile_component_bundle("personal_assistant_v0")

    assert report["bundle_id"] == "personal_assistant_v0"
    assert report["outcome"] == "GovernanceBlocked"
    assert report["compiler_is_not_execution_authority"] is True
    assert report["summary"]["component_count"] == 5
    assert report["summary"]["simulation_count"] == 3
    assert report["summary"]["live_action_ready"] is False
    assert "send_email" in report["blocked_actions"]
    assert "live_gmail_enabled" in report["forbidden_claims"]


def test_component_bundle_compiler_compiles_all_foundation_bundles() -> None:
    reports = compile_foundation_component_bundles()
    reports_by_id = {report["bundle_id"]: report for report in reports}

    assert sorted(reports_by_id) == [
        "personal_assistant_v0",
        "symbolic_reasoning_read_only",
        "worker_runtime_foundation",
    ]
    assert reports_by_id["symbolic_reasoning_read_only"]["outcome"] == "SolvedUnverified"
    assert reports_by_id["worker_runtime_foundation"]["outcome"] == "GovernanceBlocked"
    assert all(report["can_execute"] is False for report in reports)
    assert all(report["terminal_closure_required"] is True for report in reports)
    assert all("terminal_closure" in report["blocked_actions"] for report in reports)


def test_component_bundle_compiler_rejects_unknown_bundle() -> None:
    with pytest.raises(ComponentBundleCompilationError) as exc_info:
        compile_component_bundle("missing_bundle")

    assert "missing_bundle" in str(exc_info.value)
    assert "not registered" in str(exc_info.value)
    assert "component bundle" in str(exc_info.value)


def test_component_bundle_compiler_rejects_live_authority_drift() -> None:
    read_model = build_component_read_model()
    components = read_model["components"]
    assert isinstance(components, list)
    first_component = components[0]
    assert isinstance(first_component, dict)
    authority = first_component["authority"]
    assert isinstance(authority, dict)
    authority["can_execute"] = True

    with pytest.raises(ComponentBundleCompilationError) as exc_info:
        compile_component_bundle("personal_assistant_v0", read_model=read_model)

    assert "can_execute=true" in str(exc_info.value)
    assert "personal_assistant_v0" in str(exc_info.value)
    assert "governance_core" in str(exc_info.value)
