"""Tests for the Agentic Service Harness readiness-map and binding validators.

Purpose: prove the post-readiness harness map and binding plan remain
planning-only, read-only, and complete before any UI, mutation endpoint, or
external adapter implementation begins.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_readiness_map and
scripts.validate_agentic_service_harness_read_model_binding_plan.
Invariants:
  - The default readiness map contains all required sections, statuses,
    denial statements, partial symbols, and ordered next PR markers.
  - The default plan contains all required symbols, source refs, false flags,
    non-goals, and ordered next PR markers.
  - Mutation route strings and missing symbols fail closed.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_read_model_binding_plan import (  # noqa: E402
    REQUIRED_FALSE_FLAGS,
    REQUIRED_NON_GOALS,
    REQUIRED_SECTIONS,
    REQUIRED_SYMBOLS,
    main,
    validate_read_model_binding_plan,
)
from scripts.validate_agentic_service_harness_readiness_map import (  # noqa: E402
    REQUIRED_DENIALS,
    REQUIRED_PARTIAL_SYMBOLS,
    REQUIRED_READY_SYMBOLS,
    REQUIRED_SECTIONS as REQUIRED_MAP_SECTIONS,
    REQUIRED_STATUSES,
    main as readiness_map_main,
    validate_readiness_map,
)


def test_readiness_map_accepts_default_artifact() -> None:
    validation = validate_readiness_map()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.map_path == "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md"
    assert validation.required_section_count == len(REQUIRED_MAP_SECTIONS)
    assert validation.required_status_count == len(REQUIRED_STATUSES)
    assert validation.required_ready_symbol_count == len(REQUIRED_READY_SYMBOLS)
    assert validation.required_partial_symbol_count == len(REQUIRED_PARTIAL_SYMBOLS)
    assert validation.required_denial_count == len(REQUIRED_DENIALS)


def test_readiness_map_rejects_missing_repository_connection_ready_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| RepositoryConnection | READY |",
            "| RepositoryConnection | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing ready row: RepositoryConnection read model" in serialized_errors


def test_readiness_map_rejects_missing_agent_run_first_pr(tmp_path: Path) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| AgentRun | READY |",
            "| AgentRun | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing ready row: AgentRun lifecycle read model" in serialized_errors


def test_readiness_map_rejects_missing_approval_ready_row(tmp_path: Path) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| ApprovalRequest | READY |",
            "| ApprovalRequest | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing ready row: ApprovalRequest projection binding" in serialized_errors


def test_readiness_map_rejects_missing_agent_adapter_ready_row(tmp_path: Path) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| AgentAdapter | READY |",
            "| AgentAdapter | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing ready row: AgentAdapter contract-only registry" in serialized_errors


def test_readiness_map_rejects_missing_evidence_bundle_ready_row(tmp_path: Path) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| EvidenceBundle | READY |",
            "| EvidenceBundle | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing ready row: EvidenceBundle read-only projection" in serialized_errors


def test_readiness_map_rejects_missing_receipt_ready_row(tmp_path: Path) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| Receipt | READY |",
            "| Receipt | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing ready row: Receipt read-only projection" in serialized_errors

def test_readiness_map_rejects_missing_receipt_projection_pr_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| Receipt projection PR | READY |",
            "| Receipt projection PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing ready row: Receipt projection PR" in serialized_errors


def test_readiness_map_rejects_missing_task_creation_admission_ready_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| Task creation admission preflight PR | READY |",
            "| Task creation admission preflight PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: Task creation admission preflight PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_loopstatus_ready_row(tmp_path: Path) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| LoopStatus | READY |",
            "| LoopStatus | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing ready row: LoopStatus read-only projection" in serialized_errors


def test_readiness_map_rejects_missing_approved_branch_workspace_ready_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| Approved branch workspace creation preflight PR | READY |",
            "| Approved branch workspace creation preflight PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: Approved branch workspace creation preflight PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_approved_branch_workspace_authority_ready_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| Approved branch workspace creation authority binding PR | READY |",
            "| Approved branch workspace creation authority binding PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: Approved branch workspace creation authority binding PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_task_record_write_uao_ready_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| Task record write UAO admission preflight PR | READY |",
            "| Task record write UAO admission preflight PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: Task record write UAO admission preflight PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_receipt_store_append_ready_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| Receipt-store append preflight PR | READY |",
            "| Receipt-store append preflight PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: Receipt-store append preflight PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_executed_test_receipt_ready_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| Executed test receipt admission preflight PR | READY |",
            "| Executed test receipt admission preflight PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: Executed test receipt admission preflight PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_github_pr_admission_ready_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| GitHub PR admission preflight PR | READY |",
            "| GitHub PR admission preflight PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: GitHub PR admission preflight PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_github_pr_branch_write_command_preview_ready_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| GitHub PR branch-write authority command-preview operator-response evidence binding PR | READY |",
            "| GitHub PR branch-write authority command-preview operator-response evidence binding PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: GitHub PR branch-write authority command-preview operator-response evidence binding PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_github_pr_ci_gate_ready_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| GitHub PR CI gate before ready-for-review command-preview rollback binding PR | READY |",
            "| GitHub PR CI gate before ready-for-review command-preview rollback binding PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: GitHub PR CI gate before ready-for-review command-preview rollback binding PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_github_pr_rollback_actual_diff_uao_ready_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| GitHub PR repository-effect rollback command-preview UAO binding PR | READY |",
            "| GitHub PR repository-effect rollback command-preview UAO binding PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: GitHub PR repository-effect rollback command-preview UAO binding PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_github_pr_effect_reconciliation_ready_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| GitHub PR effect reconciliation command-preview CI gate binding PR | READY |",
            "| GitHub PR effect reconciliation command-preview CI gate binding PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: GitHub PR effect reconciliation command-preview CI gate binding PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_github_pr_terminal_closure_ready_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| GitHub PR terminal closure certificate command-preview effect reconciliation binding PR | READY |",
            "| GitHub PR terminal closure certificate command-preview effect reconciliation binding PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: GitHub PR terminal closure certificate command-preview effect reconciliation binding PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_github_pr_terminal_candidate_binding_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| GitHub PR terminal closure certificate candidate command-preview certificate binding PR | READY |",
            "| GitHub PR terminal closure certificate candidate command-preview certificate binding PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: GitHub PR terminal closure certificate candidate command-preview certificate binding PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_github_pr_terminal_decision_value_request_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| GitHub PR terminal closure operator decision value request command-preview generic rejection binding PR | READY |",
            "| GitHub PR terminal closure operator decision value request command-preview generic rejection binding PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: GitHub PR terminal closure operator decision value request command-preview generic rejection binding PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_github_pr_terminal_decision_value_record_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| GitHub PR terminal closure operator decision value record command-preview request binding PR | READY |",
            "| GitHub PR terminal closure operator decision value record command-preview request binding PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: GitHub PR terminal closure operator decision value record command-preview request binding PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_github_pr_terminal_certificate_minting_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| GitHub PR terminal closure certificate minting command-preview decision value record binding PR | READY |",
            "| GitHub PR terminal closure certificate minting command-preview decision value record binding PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: GitHub PR terminal closure certificate minting command-preview decision value record binding PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_github_pr_terminal_certificate_read_model_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| GitHub PR terminal closure certificate read model command-preview minting binding PR | READY |",
            "| GitHub PR terminal closure certificate read model command-preview minting binding PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: GitHub PR terminal closure certificate read model command-preview minting binding PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_dry_run_test_execution_observation_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| Dry-run test execution observation receipt PR | READY |",
            "| Dry-run test execution observation receipt PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: Dry-run test execution observation receipt PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_filesystem_write_admission_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| Filesystem write admission preflight PR | READY |",
            "| Filesystem write admission preflight PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: Filesystem write admission preflight PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_actual_diff_collection_receipt_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| Actual diff collection receipt admission PR | READY |",
            "| Actual diff collection receipt admission PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: Actual diff collection receipt admission PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_current_next_pr_marker(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "1. `harness(live-producer): collect governed live producer witness requirements`",
            "1. `harness(live-producer): request live producer execution authority`",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing next PR marker: harness(live-producer): collect governed live producer witness requirements"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_non_empty_diff_file_summary_receipt_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| Non-empty diff file summary receipt PR | READY |",
            "| Non-empty diff file summary receipt PR | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert (
        "missing ready row: Non-empty diff file summary receipt PR"
        in serialized_errors
    )


def test_readiness_map_rejects_missing_current_main_ref(tmp_path: Path) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    mutated_map_text = re.sub(
        r"^Current `origin/main`: `[0-9a-f]{40}`$",
        "Current `origin/main`: `short-ref`",
        map_text,
        flags=re.MULTILINE,
    )
    assert mutated_map_text != map_text
    map_path.write_text(mutated_map_text, encoding="utf-8")

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing current origin main ref" in serialized_errors


def test_readiness_map_rejects_missing_open_pr_queue_boundary(tmp_path: Path) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    mutated_map_text = re.sub(
        r"^Open PRs after readiness-map refresh: .+ outside this PR terminal closure readiness-map closure; .+does not grant harness execution authority\.$",
        "Open PRs after readiness-map refresh: none.",
        map_text,
        flags=re.MULTILINE,
    )
    assert mutated_map_text != map_text
    map_path.write_text(
        mutated_map_text,
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing open PR queue execution-authority boundary" in serialized_errors


def test_readiness_map_rejects_mutation_route_string(tmp_path: Path) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        f"{map_text}\nForbidden route: POST /api/harness/tasks\n",
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden mutation_route" in serialized_errors


def test_readiness_map_cli_json_reports_valid(capsys) -> None:
    exit_code = readiness_map_main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["required_ready_symbol_count"] == len(REQUIRED_READY_SYMBOLS)
    assert payload["required_partial_symbol_count"] == len(REQUIRED_PARTIAL_SYMBOLS)


def test_read_model_binding_plan_accepts_default_artifact() -> None:
    validation = validate_read_model_binding_plan()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.plan_path == "MULLUSI_AGENTIC_SERVICE_HARNESS_READ_MODEL_BINDING_PLAN.md"
    assert validation.required_section_count == len(REQUIRED_SECTIONS)
    assert validation.required_symbol_count == len(REQUIRED_SYMBOLS)
    assert validation.required_false_flag_count == len(REQUIRED_FALSE_FLAGS)
    assert validation.required_non_goal_count == len(REQUIRED_NON_GOALS)


def test_read_model_binding_plan_rejects_missing_required_symbol(tmp_path: Path) -> None:
    plan_text = Path(
        "MULLUSI_AGENTIC_SERVICE_HARNESS_READ_MODEL_BINDING_PLAN.md"
    ).read_text(encoding="utf-8")
    plan_path = tmp_path / "binding-plan.md"
    plan_path.write_text(
        plan_text.replace("RepositoryConnection", "RepoBinding"),
        encoding="utf-8",
    )

    validation = validate_read_model_binding_plan(plan_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing symbol: RepositoryConnection" in serialized_errors


def test_read_model_binding_plan_rejects_mutation_route_string(tmp_path: Path) -> None:
    plan_text = Path(
        "MULLUSI_AGENTIC_SERVICE_HARNESS_READ_MODEL_BINDING_PLAN.md"
    ).read_text(encoding="utf-8")
    plan_path = tmp_path / "binding-plan.md"
    plan_path.write_text(
        f"{plan_text}\nForbidden route: POST /api/harness/tasks\n",
        encoding="utf-8",
    )

    validation = validate_read_model_binding_plan(plan_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden mutation_route" in serialized_errors


def test_read_model_binding_plan_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["required_symbol_count"] == len(REQUIRED_SYMBOLS)
