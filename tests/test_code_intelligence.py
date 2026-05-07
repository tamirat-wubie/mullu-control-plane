"""Purpose: test repository intelligence contracts and read-only indexing.
Governance scope: validates symbol extraction, dependency/test mapping, risk
    classification, parse failure behavior, and receipt emission.
Dependencies: pytest plus MCOI code_intelligence contract/core layers.
Invariants:
  - Contract records are frozen and reject invalid symbol/risk state.
  - Python AST indexing detects symbols, routes, schemas, imports, and tests.
  - Syntax errors fail closed with causal file context.
  - Receipts are deterministic summaries, not execution authority.
"""

from pathlib import Path
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.code_intelligence import (
    CodeFileRisk,
    CodeSymbol,
    CodeSymbolKind,
    RepoMap,
)
from mcoi_runtime.core.code_intelligence import (
    CodeIntelligenceError,
    assess_changed_file_risks,
    assess_file_risk,
    build_repo_map,
    create_repo_intelligence_receipt,
)


def _write_fixture_file(file_path: Path, source_text: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(source_text, encoding="utf-8")


def test_code_symbol_contract_is_explicit_frozen_and_json_safe() -> None:
    symbol = CodeSymbol(
        name="GET /status -> status",
        kind=CodeSymbolKind.FASTAPI_ROUTE,
        file_path="app/api.py",
        line_start=4,
        line_end=6,
        imports=("fastapi",),
        referenced_by=("tests/test_api.py",),
        metadata={"route_path": "/status", "http_method": "GET"},
    )
    payload = symbol.to_json_dict()

    assert payload["kind"] == "fastapi_route"
    assert isinstance(symbol.metadata, MappingProxyType)
    assert symbol.imports == ("fastapi",)
    assert symbol.referenced_by == ("tests/test_api.py",)
    with pytest.raises(ValueError):
        CodeSymbol(
            name="broken",
            kind=CodeSymbolKind.FUNCTION,
            file_path="app/api.py",
            line_start=7,
            line_end=6,
        )
    with pytest.raises(ValueError):
        CodeSymbol(
            name="broken",
            kind="function",  # type: ignore[arg-type]
            file_path="app/api.py",
            line_start=1,
            line_end=1,
        )
    with pytest.raises(Exception):
        symbol.imports += ("extra",)  # type: ignore[misc]


def test_build_repo_map_detects_routes_schemas_dependencies_and_tests(tmp_path: Path) -> None:
    _write_fixture_file(tmp_path / "app" / "__init__.py", "")
    _write_fixture_file(
        tmp_path / "app" / "models.py",
        """
from dataclasses import dataclass
from pydantic import BaseModel


class Invoice(BaseModel):
    id: str
    total: int


@dataclass(frozen=True)
class LedgerEntry:
    id: str
    amount: int
""".strip()
        + "\n",
    )
    _write_fixture_file(
        tmp_path / "app" / "api.py",
        """
from fastapi import APIRouter
from .models import Invoice, LedgerEntry

router = APIRouter()


@router.get("/invoices/{invoice_id}")
def read_invoice(invoice_id: str) -> Invoice:
    return Invoice(id=invoice_id, total=1)


@router.api_route("/ledger", methods=["POST"])
def create_ledger(entry: LedgerEntry) -> LedgerEntry:
    return entry
""".strip()
        + "\n",
    )
    _write_fixture_file(
        tmp_path / "tests" / "test_api.py",
        """
from app.api import read_invoice
from app.models import Invoice


def test_read_invoice_contract():
    invoice = read_invoice("inv-1")
    assert invoice.id == "inv-1"
    assert isinstance(invoice, Invoice)
    assert invoice.total == 1
""".strip()
        + "\n",
    )

    repo_map = build_repo_map(tmp_path, repository_name="sample", commit_sha="abc123")
    route_names = {
        symbol.name
        for symbol in repo_map.symbols
        if symbol.kind is CodeSymbolKind.FASTAPI_ROUTE
    }
    schema_symbols = {
        (symbol.name, symbol.kind)
        for symbol in repo_map.symbols
        if symbol.kind in {CodeSymbolKind.PYDANTIC_SCHEMA, CodeSymbolKind.DATACLASS_SCHEMA}
    }
    invoice_symbol = next(symbol for symbol in repo_map.symbols if symbol.name == "Invoice")
    receipt = create_repo_intelligence_receipt(repo_map)

    assert repo_map.repository == "sample"
    assert repo_map.commit_sha == "abc123"
    assert "app/api.py" in repo_map.files
    assert "tests/test_api.py" in repo_map.files
    assert ("app/api.py", "app/models.py") in repo_map.dependency_edges
    assert ("tests/test_api.py", "app/api.py") in repo_map.dependency_edges
    assert "GET /invoices/{invoice_id} -> read_invoice" in route_names
    assert "POST /ledger -> create_ledger" in route_names
    assert ("Invoice", CodeSymbolKind.PYDANTIC_SCHEMA) in schema_symbols
    assert ("LedgerEntry", CodeSymbolKind.DATACLASS_SCHEMA) in schema_symbols
    assert repo_map.test_map.source_to_tests["app/api.py"] == ("tests/test_api.py",)
    assert repo_map.test_map.source_to_tests["app/models.py"] == ("tests/test_api.py",)
    assert "app/api.py" in invoice_symbol.referenced_by
    assert receipt.file_count == len(repo_map.files)
    assert receipt.route_count == 2
    assert receipt.schema_count == 2
    assert receipt.evidence_refs[0] == "repo:sample"


def test_file_risk_assessment_classifies_changed_surfaces() -> None:
    route_symbol = CodeSymbol(
        name="GET /status -> status",
        kind=CodeSymbolKind.FASTAPI_ROUTE,
        file_path="gateway/server.py",
        line_start=1,
        line_end=2,
    )
    repo_map = RepoMap(
        repository="sample",
        commit_sha="unknown",
        files=("gateway/server.py",),
        risk_assessments=(assess_file_risk("gateway/server.py", (route_symbol,)),),
    )

    route_risk = assess_file_risk("gateway/server.py", (route_symbol,))
    schema_risk = assess_file_risk("schemas/invoice.schema.json")
    secret_risk = assess_file_risk("mcoi/mcoi_runtime/core/secrets.py")
    changed_risks = assess_changed_file_risks(
        repo_map,
        ("schemas/invoice.schema.json", "gateway/server.py"),
    )

    assert route_risk.risk is CodeFileRisk.MEDIUM
    assert "route_surface" in route_risk.reasons
    assert schema_risk.risk is CodeFileRisk.HIGH
    assert "schema_or_contract_surface" in schema_risk.reasons
    assert secret_risk.risk is CodeFileRisk.CRITICAL
    assert "secret_or_credential_surface" in secret_risk.reasons
    assert tuple(risk.file_path for risk in changed_risks) == (
        "gateway/server.py",
        "schemas/invoice.schema.json",
    )


def test_build_repo_map_fails_closed_on_python_syntax_error(tmp_path: Path) -> None:
    _write_fixture_file(tmp_path / "good.py", "def ok() -> int:\n    return 1\n")
    _write_fixture_file(tmp_path / "bad.py", "def broken(:\n    return 1\n")

    with pytest.raises(CodeIntelligenceError) as exc_info:
        build_repo_map(tmp_path, repository_name="broken", commit_sha="abc123")

    assert "failed to parse Python file bad.py" in str(exc_info.value)
    assert "line 1" in str(exc_info.value)
    assert "invalid syntax" in str(exc_info.value)
