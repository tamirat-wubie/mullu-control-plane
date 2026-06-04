"""Regression tests for the InceptaDive note-memory architecture status.

Purpose: prevent the note-memory architecture document from regressing to a
pre-verification status after the runtime module surface is present.
Governance scope: documentation drift, runtime module reachability, focused
test visibility, and no stale follow-up closure claims.
Dependencies: pathlib and repository-local note-memory runtime/test files.
Invariants: architecture status reflects verified modules, tests remain
reachable, and stale "verify later" wording cannot return silently.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE_DOC = REPO_ROOT / "docs" / "inceptadive-note-memory-architecture.md"

RUNTIME_MODULES = (
    "concept_box_ledger.py",
    "inceptadive_axis_traversal.py",
    "incepta_scoring_adapter.py",
    "note_memory_projection.py",
    "inceptadive_interrogation_queue.py",
    "memory_repair_queue.py",
    "memory_action_compiler.py",
    "decision_use_receipts.py",
    "note_memory_world_state_bridge.py",
    "note_memory_temporal_bridge.py",
    "outcome_learning_bridge.py",
    "operational_dashboard_intelligence.py",
)


def test_inceptadive_note_memory_architecture_status_records_verified_surface() -> None:
    doc_text = ARCHITECTURE_DOC.read_text(encoding="utf-8")

    assert "Completeness: 100%" in doc_text
    assert "runtime module surface verified" in doc_text
    assert "focused projection-intelligence tests verified" in doc_text
    assert "Next action: verify runtime modules and focused tests" not in doc_text
    assert (
        "Next action: keep future production backing or provider changes "
        "behind governed note-memory verification"
    ) in doc_text


def test_inceptadive_note_memory_runtime_modules_remain_present() -> None:
    core_dir = REPO_ROOT / "mcoi" / "mcoi_runtime" / "core"
    missing_modules = [module_name for module_name in RUNTIME_MODULES if not (core_dir / module_name).is_file()]

    assert core_dir.is_dir()
    assert len(RUNTIME_MODULES) == 12
    assert missing_modules == []


def test_inceptadive_note_memory_focused_test_remains_present() -> None:
    focused_test = REPO_ROOT / "mcoi" / "tests" / "test_note_memory_projection_intelligence.py"
    focused_text = focused_test.read_text(encoding="utf-8")

    assert focused_test.is_file()
    assert "test_scoring_adapter_uses_mesh_denominator_guard_for_sigma_memory_kernel" in focused_text
    assert "test_projection_blocks_deploy_candidates_and_records_receipt" in focused_text
    assert "operational_dashboard_intelligence" in focused_text
