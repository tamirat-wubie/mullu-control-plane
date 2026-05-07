"""Tests for code-intelligence operator read models.

Purpose: verify repository intelligence is exposed as a bounded read-only
    operator projection.
Governance scope: repository summaries, context selection receipts, route
    guarding, and no source-content or execution authority exposure.
Dependencies: gateway.code_intelligence_read_model and gateway server.
Invariants:
  - Read models expose counts, symbols, risks, and receipts, not raw source.
  - Context selection is bounded by explicit affected-file requests.
  - Missing affected files fail closed.
  - Gateway route stays behind the authority-operator read boundary.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.code_intelligence_read_model import (  # noqa: E402
    build_code_intelligence_operator_read_model,
    parse_affected_files,
)
from gateway.server import create_gateway_app  # noqa: E402


class StubPlatform:
    """Minimal gateway platform fixture."""

    def process_message(self, message, tenant_id: str, identity_id: str):  # noqa: ANN001
        return {"response": "ok", "tenant_id": tenant_id, "identity_id": identity_id}


def test_code_intelligence_read_model_projects_context_without_source(tmp_path: Path) -> None:
    _write_fixture_repo(tmp_path)

    read_model = build_code_intelligence_operator_read_model(
        repository_root=tmp_path,
        repository_name="invoice-app",
        task_summary="Add missing invoice validation",
        affected_files=("app/api.py",),
        max_symbol_count=10,
        max_test_count=1,
        max_dependency_edges=10,
        target_model="coding",
    )
    context = read_model["context"]

    assert read_model["surface"] == "read_only_repository_intelligence"
    assert read_model["raw_source_content_exposed"] is False
    assert read_model["raw_filesystem_write_exposed"] is False
    assert read_model["execution_authority_granted"] is False
    assert read_model["repository"] == "invoice-app"
    assert read_model["route_count"] == 1
    assert read_model["schema_count"] == 1
    assert context["receipt"]["selected_file_count"] >= 2
    assert context["selected_tests"] == ["tests/test_api.py"]
    assert any(symbol["kind"] == "fastapi_route" for symbol in context["selected_symbols"])
    assert "return Invoice" not in str(read_model)


def test_code_intelligence_operator_endpoint_uses_configured_root(monkeypatch, tmp_path: Path) -> None:
    _write_fixture_repo(tmp_path)
    monkeypatch.setenv("MULLU_CODE_INTELLIGENCE_ROOT", str(tmp_path))
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.get(
        "/operator/code-intelligence/read-model",
        params={
            "affected_files": "app/api.py",
            "task_summary": "Inspect invoice route",
            "max_test_count": 1,
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["enabled"] is True
    assert payload["context"]["selected_tests"] == ["tests/test_api.py"]
    assert payload["repo_receipt"]["repository"] == tmp_path.name
    assert payload["execution_authority_granted"] is False


def test_code_intelligence_operator_endpoint_fails_closed_for_missing_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_fixture_repo(tmp_path)
    monkeypatch.setenv("MULLU_CODE_INTELLIGENCE_ROOT", str(tmp_path))
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.get(
        "/operator/code-intelligence/read-model",
        params={"affected_files": "app/missing.py", "task_summary": "Missing file"},
    )

    assert response.status_code == 400
    assert "affected files are absent from RepoMap" in response.json()["detail"]
    assert "app/missing.py" in response.json()["detail"]


def test_parse_affected_files_normalizes_commas_and_slashes() -> None:
    parsed = parse_affected_files(" ./app/api.py, app\\models.py, app/api.py ")

    assert parsed == ("app/api.py", "app/models.py")
    assert len(parsed) == 2
    assert all(not path.startswith("./") for path in parsed)


def _write_fixture_repo(root: Path) -> None:
    _write_file(root / "app" / "__init__.py", "")
    _write_file(
        root / "app" / "models.py",
        """
from pydantic import BaseModel


class Invoice(BaseModel):
    id: str
""".strip()
        + "\n",
    )
    _write_file(
        root / "app" / "api.py",
        """
from fastapi import APIRouter
from .models import Invoice

router = APIRouter()


@router.get("/invoices/{invoice_id}")
def read_invoice(invoice_id: str) -> Invoice:
    return Invoice(id=invoice_id)
""".strip()
        + "\n",
    )
    _write_file(
        root / "tests" / "test_api.py",
        """
from app.api import read_invoice


def test_read_invoice_contract():
    invoice = read_invoice("inv-1")
    assert invoice.id == "inv-1"
    assert invoice.__class__.__name__ == "Invoice"
    assert read_invoice("inv-2").id == "inv-2"
""".strip()
        + "\n",
    )


def _write_file(path: Path, source_text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source_text, encoding="utf-8")
