"""Purpose: test deterministic software gate planning.
Governance scope: validates gate-plan contracts, fast-to-release ordering,
    mapped test selection, release-candidate escalation, schema/migration
    checks, and fail-closed missing-file handling.
Dependencies: pytest plus MCOI code_intelligence and software_gate_planner.
Invariants:
  - Gate plans are immutable typed planning receipts.
  - Static and fast gates are ordered before targeted/integration/release gates.
  - Commit-candidate mode requires full-suite and release evidence.
  - Missing affected files never produce a partial gate plan.
"""

from pathlib import Path
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.software_gate_plan import (
    GateExecutionTier,
    PlannedSoftwareGate,
    SoftwareGatePlan,
)
from mcoi_runtime.core.code_intelligence import build_repo_map
from mcoi_runtime.core.software_gate_planner import (
    SoftwareGatePlannerError,
    plan_software_gates,
)
from mcoi_runtime.domain_adapters.software_dev import (
    SoftwareQualityGate,
    SoftwareRequest,
    SoftwareWorkKind,
    SoftwareWorkMode,
)


def _write_fixture_file(file_path: Path, source_text: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(source_text, encoding="utf-8")


def _write_gate_fixture(repository_root: Path) -> None:
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
    _write_fixture_file(
        repository_root / "mcoi" / "mcoi_runtime" / "contracts" / "invoice.py",
        """
from dataclasses import dataclass


@dataclass(frozen=True)
class InvoiceContract:
    invoice_id: str
""".strip()
        + "\n",
    )
    _write_fixture_file(
        repository_root / "migrations" / "001_invoice.py",
        "def upgrade() -> None:\n    return None\n",
    )


def _software_request(**overrides: object) -> SoftwareRequest:
    values = {
        "kind": SoftwareWorkKind.FEATURE,
        "summary": "Update invoice route",
        "repository": "invoice-app",
        "affected_files": ("app/api.py",),
        "acceptance_criteria": ("route still returns invoice",),
        "mode": SoftwareWorkMode.PATCH_TEST_REVIEW,
        "quality_gates": (SoftwareQualityGate.UNIT_TESTS, SoftwareQualityGate.LINT),
    }
    values.update(overrides)
    return SoftwareRequest(**values)


def test_gate_plan_contract_is_explicit_frozen_and_json_safe() -> None:
    gate = PlannedSoftwareGate(
        gate_id="unit_tests",
        tier=GateExecutionTier.TARGETED,
        command=("pytest", "tests/test_api.py", "-q"),
        reason="mapped test",
        target_refs=("tests/test_api.py",),
        order=0,
        metadata={"mapped": True},
    )
    plan = SoftwareGatePlan(
        plan_id="gate-plan-1",
        repository="invoice-app",
        commit_sha="abc123",
        mode="patch_test_review",
        blast_radius="module",
        affected_files=("app/api.py",),
        gates=(gate,),
        evidence_refs=("repo:invoice-app",),
    )
    payload = plan.to_json_dict()

    assert payload["gates"][0]["tier"] == "targeted"
    assert plan.gates[0].command == ("pytest", "tests/test_api.py", "-q")
    assert isinstance(plan.gates[0].metadata, MappingProxyType)
    assert plan.full_suite_required is False
    with pytest.raises(ValueError):
        PlannedSoftwareGate(
            gate_id="",
            tier=GateExecutionTier.FAST,
            command=("ruff", "check", "."),
            reason="x",
            target_refs=("app/api.py",),
            order=0,
        )
    with pytest.raises(ValueError):
        SoftwareGatePlan(
            plan_id="gate-plan-2",
            repository="invoice-app",
            commit_sha="abc123",
            mode="patch_test_review",
            blast_radius="module",
            affected_files=(),
            gates=(gate,),
            evidence_refs=("repo:invoice-app",),
        )
    with pytest.raises(Exception):
        plan.gates += (gate,)  # type: ignore[misc]


def test_gate_planner_selects_targeted_route_gates_and_mapped_tests(tmp_path: Path) -> None:
    _write_gate_fixture(tmp_path)
    repo_map = build_repo_map(tmp_path, repository_name="invoice-app", commit_sha="abc123")
    request = _software_request()

    plan = plan_software_gates(repo_map, request)
    gate_ids = tuple(gate.gate_id for gate in plan.gates)
    unit_gate = next(gate for gate in plan.gates if gate.gate_id == "unit_tests")
    route_gate = next(gate for gate in plan.gates if gate.gate_id == "changed_route_contract_check")

    assert gate_ids == (
        "static_patch_validation",
        "security_scan",
        "blast_radius_check",
        "lint",
        "unit_tests",
        "changed_route_contract_check",
        "rollback_check",
        "review",
    )
    assert unit_gate.command == ("pytest", "tests/test_api.py", "-q")
    assert unit_gate.tier is GateExecutionTier.TARGETED
    assert route_gate.reason == "changed FastAPI route surface requires API contract diff"
    assert plan.full_suite_required is False
    assert plan.metadata["route_changed"] is True
    assert plan.metadata["selected_tests"] == ("tests/test_api.py",)
    assert plan.evidence_refs[2] == "mode:patch_test_review"


def test_gate_planner_escalates_commit_candidate_to_full_release_gates(tmp_path: Path) -> None:
    _write_gate_fixture(tmp_path)
    repo_map = build_repo_map(tmp_path, repository_name="invoice-app", commit_sha="abc123")
    request = _software_request(
        mode=SoftwareWorkMode.COMMIT_CANDIDATE,
        blast_radius="service",
    )

    plan = plan_software_gates(repo_map, request)
    gate_ids = tuple(gate.gate_id for gate in plan.gates)
    unit_gate = next(gate for gate in plan.gates if gate.gate_id == "unit_tests")
    build_gate = next(gate for gate in plan.gates if gate.gate_id == "build")
    review_gate = next(gate for gate in plan.gates if gate.gate_id == "review")

    assert plan.full_suite_required is True
    assert "typecheck" in gate_ids
    assert "integration_tests" in gate_ids
    assert "build" in gate_ids
    assert unit_gate.command == ("pytest", "-q")
    assert unit_gate.metadata["full_suite_required"] is True
    assert build_gate.tier is GateExecutionTier.RELEASE
    assert review_gate.tier is GateExecutionTier.RELEASE
    assert gate_ids.index("lint") < gate_ids.index("unit_tests") < gate_ids.index("integration_tests")


def test_gate_planner_adds_schema_and_migration_safety_gates(tmp_path: Path) -> None:
    _write_gate_fixture(tmp_path)
    repo_map = build_repo_map(tmp_path, repository_name="invoice-app", commit_sha="abc123")
    request = _software_request(
        affected_files=(
            "mcoi/mcoi_runtime/contracts/invoice.py",
            "migrations/001_invoice.py",
        ),
        mode=SoftwareWorkMode.PATCH_AND_TEST,
        quality_gates=(SoftwareQualityGate.UNIT_TESTS,),
    )

    plan = plan_software_gates(repo_map, request)
    gate_ids = tuple(gate.gate_id for gate in plan.gates)
    schema_gate = next(gate for gate in plan.gates if gate.gate_id == "schema_compatibility_check")
    migration_gate = next(gate for gate in plan.gates if gate.gate_id == "migration_safety_check")

    assert plan.full_suite_required is True
    assert "typecheck" in gate_ids
    assert "schema_compatibility_check" in gate_ids
    assert "migration_safety_check" in gate_ids
    assert schema_gate.tier is GateExecutionTier.TARGETED
    assert migration_gate.command == ("internal", "migration_safety_check")
    assert plan.metadata["schema_changed"] is True
    assert plan.metadata["migration_changed"] is True


def test_gate_planner_fails_closed_for_missing_affected_file(tmp_path: Path) -> None:
    _write_gate_fixture(tmp_path)
    repo_map = build_repo_map(tmp_path, repository_name="invoice-app", commit_sha="abc123")
    request = _software_request(affected_files=("app/missing.py",))

    with pytest.raises(SoftwareGatePlannerError) as exc_info:
        plan_software_gates(repo_map, request)

    assert "affected files are absent from RepoMap" in str(exc_info.value)
    assert "app/missing.py" in str(exc_info.value)
    assert repo_map.repository == "invoice-app"
