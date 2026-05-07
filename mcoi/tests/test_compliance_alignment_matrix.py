"""Tests for compliance alignment matrix validation.

Purpose: verify compliance mappings remain evidence-backed and avoid certification claims.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: compliance alignment matrix script and JSON fixture.
Invariants: every mapped capability covers all target frameworks with repository evidence.
"""
from __future__ import annotations

from pathlib import Path

from scripts.compliance_alignment_matrix import TARGET_FRAMEWORKS, load_matrix, validate_matrix


def test_compliance_alignment_matrix_is_valid() -> None:
    matrix = load_matrix()
    errors = validate_matrix(matrix)

    assert errors == []
    assert matrix["schema_version"] == 1
    assert matrix["claim_boundary"]["certification_claimed"] is False
    assert matrix["claim_boundary"]["statement"] == "alignment_only"
    assert matrix["claim_boundary"]["review_required_before_external_publication"] is True


def test_each_capability_maps_all_target_frameworks() -> None:
    matrix = load_matrix()

    for capability in matrix["capabilities"]:
        mapped_frameworks = {mapping["framework"] for mapping in capability["mappings"]}
        evidence_files = capability["evidence_files"]

        assert mapped_frameworks == TARGET_FRAMEWORKS
        assert len(evidence_files) >= 2
        assert capability["capability_id"]
        assert capability["capability"]


def test_compliance_alignment_evidence_files_exist() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    matrix = load_matrix()

    for capability in matrix["capabilities"]:
        for evidence_file in capability["evidence_files"]:
            evidence_path = repo_root / evidence_file

            assert evidence_path.exists()
            assert evidence_path.is_file()
            assert evidence_path.stat().st_size > 0


def test_compliance_alignment_rejects_certification_claims() -> None:
    matrix = load_matrix()
    matrix["claim_boundary"] = {
        "certification_claimed": True,
        "statement": "certified",
        "review_required_before_external_publication": False,
    }

    errors = validate_matrix(matrix)

    assert "claim_boundary.certification_claimed must be false" in errors
    assert "claim_boundary.statement must be alignment_only" in errors
    assert "external publication review must be required" in errors
