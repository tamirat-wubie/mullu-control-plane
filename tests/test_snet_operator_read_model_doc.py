"""Purpose: verify SNet operator read-model documentation.
Governance scope: SNet no-authority boundary, receipt validation commands,
    promotion gate, and operator-facing documentation drift.
Dependencies: docs/73_snet_operator_read_model.md.
Invariants:
  - SNet exposes only the bounded read-only operator route.
  - Operator docs must not imply connector, filesystem, execution, gateway, or terminal-closure authority.
  - Validation commands remain visible to operators.
"""

from __future__ import annotations

from pathlib import Path


DOC_PATH = Path(__file__).resolve().parents[1] / "docs" / "73_snet_operator_read_model.md"
START_HERE_PATH = Path(__file__).resolve().parents[1] / "docs" / "START_HERE.md"


def test_snet_operator_doc_declares_read_only_boundary() -> None:
    assert DOC_PATH.exists()
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "read_only_snet_recursive_mesh" in text
    assert "SNet mesh receipts are non-terminal evidence" in text
    assert "GET /api/v1/snet/operator/read-model" in text
    assert "SNet runtime routing is limited" in text
    assert "connector, filesystem, execution, and terminal-closure integration remain AwaitingEvidence" in text


def test_snet_operator_doc_names_blocked_authorities() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "raw answers" in text
    assert "execution authority" in text
    assert "connector authority" in text
    assert "route authority" in text
    assert "filesystem authority" in text
    assert "terminal closure authority" in text


def test_snet_operator_doc_lists_verification_commands() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "python scripts/validate_snet_operator_read_model.py" in text
    assert "python scripts/validate_snet_mesh_receipt.py" in text
    assert "tests/test_validate_snet_operator_read_model.py" in text
    assert "python -m pytest mcoi/tests/test_snet_recursive_mesh.py mcoi/tests/test_snet_router.py tests/test_validate_snet_mesh_receipt.py tests/test_validate_snet_operator_read_model.py -q" in text
    assert "[PASS] snet_operator_read_model_no_authority_boundary" in text
    assert "python scripts/validate_sdlc_artifact.py" in text
    assert "[PASS] snet_mesh_receipt_no_authority_boundary" in text


def test_start_here_links_snet_operator_doc() -> None:
    start_here = START_HERE_PATH.read_text(encoding="utf-8")

    assert "SNet operator read model" in start_here
    assert "73_snet_operator_read_model.md" in start_here
