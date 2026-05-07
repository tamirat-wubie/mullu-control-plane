"""Purpose: deterministic software quality gate planner.
Governance scope: selects ordered validation gates from RepoMap, SoftwareRequest
    mode, blast radius, affected files, mapped tests, and risk surfaces.
Dependencies: software_gate_plan contracts, code_intelligence contracts, and
    the software_dev domain adapter enums.
Invariants:
  - Planning is read-only and never executes a gate.
  - Affected files must be present in RepoMap before gates are planned.
  - Fast/static gates appear before targeted, integration, and release gates.
  - Commit-candidate mode escalates to full-suite and release-review coverage.
  - Every selected gate carries a causal reason and target references.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import PurePosixPath
from typing import Sequence

from mcoi_runtime.contracts.code_intelligence import CodeFileRisk, CodeSymbolKind, RepoMap
from mcoi_runtime.contracts.software_gate_plan import (
    GateExecutionTier,
    PlannedSoftwareGate,
    SoftwareGatePlan,
)
from mcoi_runtime.domain_adapters.software_dev import (
    SoftwareQualityGate,
    SoftwareRequest,
    SoftwareWorkMode,
)


class SoftwareGatePlannerError(RuntimeError):
    """Raised when a gate plan cannot be built from the requested boundary."""


_TESTING_MODES: frozenset[SoftwareWorkMode] = frozenset(
    {
        SoftwareWorkMode.PATCH_AND_TEST,
        SoftwareWorkMode.PATCH_TEST_REVIEW,
        SoftwareWorkMode.COMMIT_CANDIDATE,
    }
)
_REVIEW_MODES: frozenset[SoftwareWorkMode] = frozenset(
    {
        SoftwareWorkMode.PATCH_TEST_REVIEW,
        SoftwareWorkMode.COMMIT_CANDIDATE,
    }
)
_FULL_SUITE_BLAST_RADII: frozenset[str] = frozenset({"service", "system"})


def plan_software_gates(repo_map: RepoMap, request: SoftwareRequest) -> SoftwareGatePlan:
    """Plan ordered quality gates for a bounded software request.

    Error contract:
      - Raises ValueError when inputs are not typed contract records.
      - Raises SoftwareGatePlannerError when affected files are absent.
    """
    if not isinstance(repo_map, RepoMap):
        raise ValueError("repo_map must be a RepoMap")
    if not isinstance(request, SoftwareRequest):
        raise ValueError("request must be a SoftwareRequest")
    affected_files = tuple(sorted({_normalize_path(path) for path in request.affected_files}))
    if not affected_files:
        raise SoftwareGatePlannerError("affected_files must contain at least one item")

    repo_files = frozenset(repo_map.files)
    missing_files = tuple(path for path in affected_files if path not in repo_files)
    if missing_files:
        raise SoftwareGatePlannerError(
            f"affected files are absent from RepoMap: {', '.join(missing_files)}"
        )

    affected_set = frozenset(affected_files)
    selected_tests = _mapped_tests(repo_map, affected_files)
    affected_python_files = tuple(path for path in affected_files if path.endswith((".py", ".pyi")))
    changed_symbol_kinds = _changed_symbol_kinds(repo_map, affected_set)
    changed_risks = _changed_risks(repo_map, affected_set)
    route_changed = CodeSymbolKind.FASTAPI_ROUTE in changed_symbol_kinds
    schema_changed = _schema_changed(affected_files, changed_symbol_kinds)
    migration_changed = any(_is_migration_path(path) for path in affected_files)
    high_risk_change = any(risk in {CodeFileRisk.HIGH, CodeFileRisk.CRITICAL} for risk in changed_risks)
    full_suite_required = (
        request.mode is SoftwareWorkMode.COMMIT_CANDIDATE
        or request.blast_radius in _FULL_SUITE_BLAST_RADII
        or high_risk_change
    )

    gates: list[PlannedSoftwareGate] = []
    skipped_gate_ids: list[str] = []

    def add_gate(
        gate_id: str,
        tier: GateExecutionTier,
        command: tuple[str, ...],
        reason: str,
        target_refs: Sequence[str],
        *,
        required: bool = True,
        metadata: dict[str, object] | None = None,
    ) -> None:
        if any(gate.gate_id == gate_id for gate in gates):
            return
        gates.append(
            PlannedSoftwareGate(
                gate_id=gate_id,
                tier=tier,
                command=command,
                reason=reason,
                target_refs=tuple(target_refs),
                order=len(gates),
                required=required,
                metadata=metadata or {},
            )
        )

    add_gate(
        "static_patch_validation",
        GateExecutionTier.STATIC,
        _static_validation_command(affected_python_files),
        "validate changed Python files before expensive gates",
        affected_files,
    )
    add_gate(
        SoftwareQualityGate.SECURITY_SCAN.value,
        GateExecutionTier.STATIC,
        ("internal", "secret_scan_diff"),
        "scan changed diff for secret exposure before execution",
        affected_files,
    )
    add_gate(
        "blast_radius_check",
        GateExecutionTier.STATIC,
        ("internal", "blast_radius_check"),
        f"verify requested blast radius {request.blast_radius}",
        affected_files,
        metadata={"blast_radius": request.blast_radius},
    )

    if _should_plan_lint(request, affected_python_files, full_suite_required):
        add_gate(
            SoftwareQualityGate.LINT.value,
            GateExecutionTier.FAST,
            ("ruff", "check", *(affected_python_files or (".",))),
            "lint affected Python surface before tests",
            affected_python_files or affected_files,
        )
    else:
        skipped_gate_ids.append(SoftwareQualityGate.LINT.value)

    if _should_plan_typecheck(request, schema_changed, full_suite_required):
        add_gate(
            SoftwareQualityGate.TYPECHECK.value,
            GateExecutionTier.FAST,
            ("mypy", "."),
            "typecheck required by schema/risk/release candidate surface",
            affected_files,
        )

    if request.mode in _TESTING_MODES or _gate_requested(request, SoftwareQualityGate.UNIT_TESTS):
        add_gate(
            SoftwareQualityGate.UNIT_TESTS.value,
            GateExecutionTier.TARGETED,
            _unit_test_command(selected_tests, full_suite_required),
            _unit_test_reason(selected_tests, full_suite_required),
            selected_tests if selected_tests and not full_suite_required else affected_files,
            metadata={
                "mapped_tests": selected_tests,
                "full_suite_required": full_suite_required,
            },
        )
    else:
        skipped_gate_ids.append(SoftwareQualityGate.UNIT_TESTS.value)

    if route_changed:
        add_gate(
            "changed_route_contract_check",
            GateExecutionTier.TARGETED,
            ("internal", "changed_route_contract_check"),
            "changed FastAPI route surface requires API contract diff",
            affected_files,
        )

    if schema_changed:
        add_gate(
            "schema_compatibility_check",
            GateExecutionTier.TARGETED,
            ("internal", "schema_compatibility_check"),
            "changed schema or contract surface requires compatibility proof",
            affected_files,
        )

    if migration_changed:
        add_gate(
            "migration_safety_check",
            GateExecutionTier.TARGETED,
            ("internal", "migration_safety_check"),
            "migration surface requires rollback and safety proof",
            affected_files,
        )

    if _should_plan_integration(request, route_changed, full_suite_required):
        add_gate(
            SoftwareQualityGate.INTEGRATION_TESTS.value,
            GateExecutionTier.INTEGRATION,
            ("pytest", "tests", "-q", "-m", "integration"),
            "integration coverage required by route/service/release surface",
            affected_files,
            metadata={"route_changed": route_changed, "full_suite_required": full_suite_required},
        )

    if request.mode is SoftwareWorkMode.COMMIT_CANDIDATE or _gate_requested(request, SoftwareQualityGate.BUILD):
        add_gate(
            SoftwareQualityGate.BUILD.value,
            GateExecutionTier.RELEASE,
            ("python", "-m", "build"),
            "release candidate requires build evidence",
            affected_files,
        )

    if request.rollback_required:
        add_gate(
            "rollback_check",
            GateExecutionTier.RELEASE if full_suite_required else GateExecutionTier.TARGETED,
            ("internal", "rollback_check"),
            "rollback is required by software request contract",
            affected_files,
        )

    if request.reviewer_required and request.mode in _REVIEW_MODES:
        add_gate(
            SoftwareQualityGate.REVIEW.value,
            GateExecutionTier.RELEASE,
            ("internal", "review_packet_required"),
            "reviewer is required before terminal closure",
            affected_files,
        )

    plan_id = _plan_id(repo_map, request, affected_files, tuple(gate.gate_id for gate in gates))
    return SoftwareGatePlan(
        plan_id=plan_id,
        repository=repo_map.repository,
        commit_sha=repo_map.commit_sha,
        mode=request.mode.value,
        blast_radius=request.blast_radius,
        affected_files=affected_files,
        gates=tuple(gates),
        skipped_gate_ids=tuple(sorted(set(skipped_gate_ids))),
        full_suite_required=full_suite_required,
        evidence_refs=(
            f"repo:{repo_map.repository}",
            f"commit:{repo_map.commit_sha}",
            f"mode:{request.mode.value}",
            f"affected_files:{len(affected_files)}",
            f"mapped_tests:{len(selected_tests)}",
        ),
        metadata={
            "selected_tests": selected_tests,
            "route_changed": route_changed,
            "schema_changed": schema_changed,
            "migration_changed": migration_changed,
            "high_risk_change": high_risk_change,
        },
    )


def _should_plan_lint(
    request: SoftwareRequest,
    affected_python_files: Sequence[str],
    full_suite_required: bool,
) -> bool:
    return bool(
        affected_python_files
        or full_suite_required
        or _gate_requested(request, SoftwareQualityGate.LINT)
    )


def _should_plan_typecheck(
    request: SoftwareRequest,
    schema_changed: bool,
    full_suite_required: bool,
) -> bool:
    return bool(
        schema_changed
        or full_suite_required
        or _gate_requested(request, SoftwareQualityGate.TYPECHECK)
    )


def _should_plan_integration(
    request: SoftwareRequest,
    route_changed: bool,
    full_suite_required: bool,
) -> bool:
    return bool(
        _gate_requested(request, SoftwareQualityGate.INTEGRATION_TESTS)
        or (route_changed and request.blast_radius in _FULL_SUITE_BLAST_RADII)
        or (full_suite_required and request.mode is SoftwareWorkMode.COMMIT_CANDIDATE)
    )


def _gate_requested(request: SoftwareRequest, gate: SoftwareQualityGate) -> bool:
    return gate in request.quality_gates


def _mapped_tests(repo_map: RepoMap, affected_files: Sequence[str]) -> tuple[str, ...]:
    tests: set[str] = set()
    for path in affected_files:
        tests.update(repo_map.test_map.source_to_tests.get(path, ()))
    return tuple(sorted(tests))


def _changed_symbol_kinds(repo_map: RepoMap, affected_set: frozenset[str]) -> frozenset[CodeSymbolKind]:
    return frozenset(symbol.kind for symbol in repo_map.symbols if symbol.file_path in affected_set)


def _changed_risks(repo_map: RepoMap, affected_set: frozenset[str]) -> frozenset[CodeFileRisk]:
    return frozenset(
        assessment.risk
        for assessment in repo_map.risk_assessments
        if assessment.file_path in affected_set
    )


def _schema_changed(
    affected_files: Sequence[str],
    changed_symbol_kinds: frozenset[CodeSymbolKind],
) -> bool:
    if any(
        path.startswith("schemas/")
        or path.endswith(".schema.json")
        or "/contracts/" in path
        for path in affected_files
    ):
        return True
    return bool(
        changed_symbol_kinds
        & {
            CodeSymbolKind.PYDANTIC_SCHEMA,
            CodeSymbolKind.DATACLASS_SCHEMA,
        }
    )


def _is_migration_path(path: str) -> bool:
    lower_path = path.lower()
    return "migration" in lower_path or lower_path.startswith("migrations/")


def _static_validation_command(affected_python_files: Sequence[str]) -> tuple[str, ...]:
    if affected_python_files:
        return ("python", "-m", "py_compile", *affected_python_files)
    return ("internal", "static_patch_validation")


def _unit_test_command(selected_tests: Sequence[str], full_suite_required: bool) -> tuple[str, ...]:
    if selected_tests and not full_suite_required:
        return ("pytest", *selected_tests, "-q")
    return ("pytest", "-q")


def _unit_test_reason(selected_tests: Sequence[str], full_suite_required: bool) -> str:
    if full_suite_required:
        return "full unit suite required by release/risk/blast-radius escalation"
    if selected_tests:
        return "run mapped tests for affected source files"
    return "no mapped tests available, run default unit suite"


def _plan_id(
    repo_map: RepoMap,
    request: SoftwareRequest,
    affected_files: Sequence[str],
    gate_ids: Sequence[str],
) -> str:
    material = "|".join(
        (
            repo_map.repository,
            repo_map.commit_sha,
            request.mode.value,
            request.blast_radius,
            ",".join(affected_files),
            ",".join(gate_ids),
        )
    )
    return f"gate-plan-{sha256(material.encode('utf-8')).hexdigest()[:16]}"


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if not normalized:
        raise ValueError("path must be non-empty")
    if normalized.startswith("/") or ".." in PurePosixPath(normalized).parts:
        raise ValueError("path must stay inside repository root")
    return normalized
