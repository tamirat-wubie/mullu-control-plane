"""Purpose: test governed code context bundle construction.
Governance scope: validates request contracts, RepoMap-based context selection,
    token/cost estimates, selection limits, receipts, and fail-closed paths.
Dependencies: pytest plus MCOI code_intelligence and code_context layers.
Invariants:
  - Context requests reject missing affected-file boundaries.
  - Context bundles select affected files, dependency neighbors, mapped tests,
    symbols, risks, and evidence references deterministically.
  - Limits bound selected symbols, tests, and dependency edges.
  - Missing affected files never produce a partial prompt context.
"""

from pathlib import Path
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.code_context import CodeContextRequest
from mcoi_runtime.contracts.code_intelligence import CodeSymbolKind
from mcoi_runtime.core.code_context_builder import (
    CodeContextBuilderError,
    build_code_context,
    create_code_context_receipt,
)
from mcoi_runtime.core.code_intelligence import build_repo_map


def _write_fixture_file(file_path: Path, source_text: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(source_text, encoding="utf-8")


def _write_context_fixture(repository_root: Path) -> None:
    _write_fixture_file(repository_root / "app" / "__init__.py", "")
    _write_fixture_file(
        repository_root / "app" / "models.py",
        """
from pydantic import BaseModel


class Invoice(BaseModel):
    id: str
    total: int
""".strip()
        + "\n",
    )
    _write_fixture_file(
        repository_root / "app" / "api.py",
        """
from fastapi import APIRouter
from .models import Invoice

router = APIRouter()


@router.get("/invoices/{invoice_id}")
def read_invoice(invoice_id: str) -> Invoice:
    return Invoice(id=invoice_id, total=1)
""".strip()
        + "\n",
    )
    _write_fixture_file(
        repository_root / "app" / "service.py",
        """
from app.api import read_invoice


def invoice_total(invoice_id: str) -> int:
    return read_invoice(invoice_id).total
""".strip()
        + "\n",
    )
    _write_fixture_file(
        repository_root / "tests" / "test_api.py",
        """
from app.api import read_invoice


def test_read_invoice_contract():
    invoice = read_invoice("inv-1")
    assert invoice.id == "inv-1"
    assert invoice.total == 1
    assert invoice.__class__.__name__ == "Invoice"
""".strip()
        + "\n",
    )


def test_code_context_request_contract_is_explicit_frozen_and_json_safe() -> None:
    request = CodeContextRequest(
        task_summary="Add invoice lookup validation",
        affected_files=("app/api.py",),
        acceptance_criteria=("unknown invoice returns 404",),
        target_model="coding",
        metadata={"input_cost_microusd_per_1k": 200},
    )
    payload = request.to_json_dict()

    assert request.affected_files == ("app/api.py",)
    assert payload["acceptance_criteria"] == ["unknown invoice returns 404"]
    assert request.target_model == "coding"
    assert isinstance(request.metadata, MappingProxyType)
    with pytest.raises(ValueError):
        CodeContextRequest(task_summary="x", affected_files=())
    with pytest.raises(ValueError):
        CodeContextRequest(task_summary="", affected_files=("app/api.py",))
    with pytest.raises(Exception):
        request.affected_files += ("app/extra.py",)  # type: ignore[misc]


def test_build_code_context_selects_repo_evidence_tests_and_receipt(tmp_path: Path) -> None:
    _write_context_fixture(tmp_path)
    repo_map = build_repo_map(tmp_path, repository_name="invoice-app", commit_sha="abc123")
    request = CodeContextRequest(
        task_summary="Add missing invoice validation to route",
        affected_files=("app/api.py",),
        acceptance_criteria=("missing invoice returns 404", "existing invoice still returns 200"),
        max_symbol_count=20,
        max_test_count=5,
        max_dependency_edges=10,
        target_model="coding",
    )

    bundle = build_code_context(repo_map, request)
    receipt = create_code_context_receipt(bundle)
    file_reasons = {selection.file_path: selection.reason for selection in bundle.selected_files}
    route_symbols = [symbol for symbol in bundle.selected_symbols if symbol.kind is CodeSymbolKind.FASTAPI_ROUTE]
    schema_symbols = [symbol for symbol in bundle.selected_symbols if symbol.kind is CodeSymbolKind.PYDANTIC_SCHEMA]
    risk_by_path = {assessment.file_path: assessment.risk.value for assessment in bundle.risk_assessments}

    assert bundle.repository == "invoice-app"
    assert bundle.commit_sha == "abc123"
    assert file_reasons["app/api.py"] == "affected_file"
    assert file_reasons["app/models.py"] == "direct_dependency"
    assert file_reasons["app/service.py"] == "reverse_dependent"
    assert file_reasons["tests/test_api.py"] == "mapped_test"
    assert bundle.selected_tests == ("tests/test_api.py",)
    assert ("app/api.py", "app/models.py") in bundle.dependency_edges
    assert ("app/service.py", "app/api.py") in bundle.dependency_edges
    assert route_symbols[0].name == "GET /invoices/{invoice_id} -> read_invoice"
    assert schema_symbols[0].name == "Invoice"
    assert risk_by_path["app/api.py"] == "medium"
    assert receipt.selected_file_count == len(bundle.selected_files)
    assert receipt.selected_symbol_count == len(bundle.selected_symbols)
    assert receipt.evidence_refs[0] == f"bundle:{bundle.bundle_id}"


def test_build_code_context_respects_limits_and_cost_override(tmp_path: Path) -> None:
    _write_context_fixture(tmp_path)
    repo_map = build_repo_map(tmp_path, repository_name="invoice-app", commit_sha="abc123")
    request = CodeContextRequest(
        task_summary="Tight context for invoice route",
        affected_files=("app/api.py",),
        acceptance_criteria=("route behavior preserved",),
        max_symbol_count=1,
        max_test_count=0,
        max_dependency_edges=1,
        metadata={"input_cost_microusd_per_1k": 2_000},
    )

    bundle = build_code_context(repo_map, request)
    receipt = create_code_context_receipt(bundle)

    assert len(bundle.selected_symbols) == 1
    assert bundle.selected_symbols[0].kind is CodeSymbolKind.FASTAPI_ROUTE
    assert bundle.selected_tests == ()
    assert len(bundle.dependency_edges) == 1
    assert "tests/test_api.py" not in {selection.file_path for selection in bundle.selected_files}
    assert bundle.estimate.token_estimate > 0
    assert bundle.estimate.cost_microusd_estimate == (bundle.estimate.token_estimate * 2_000 + 999) // 1000
    assert "cost_rate=2000_microusd_per_1k_input_tokens" in bundle.estimate.estimation_method
    assert receipt.cost_microusd_estimate == bundle.estimate.cost_microusd_estimate


def test_build_code_context_fails_closed_for_missing_affected_file(tmp_path: Path) -> None:
    _write_context_fixture(tmp_path)
    repo_map = build_repo_map(tmp_path, repository_name="invoice-app", commit_sha="abc123")
    request = CodeContextRequest(
        task_summary="Change absent file",
        affected_files=("app/missing.py",),
        acceptance_criteria=("no partial context emitted",),
    )

    with pytest.raises(CodeContextBuilderError) as exc_info:
        build_code_context(repo_map, request)

    assert "affected files are absent from RepoMap" in str(exc_info.value)
    assert "app/missing.py" in str(exc_info.value)
    assert repo_map.repository == "invoice-app"
