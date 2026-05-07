"""Purpose: app-builder planning contracts for governed software tasks.
Governance scope: product intent, architecture boundaries, task DAGs, gates,
    review obligations, and proof references before any software change runs.
Dependencies: dataclasses, enum, pathlib, typing, and shared contract helpers.
Invariants:
  - Product and architecture specs reject undefined core surfaces.
  - App tasks carry explicit affected files, acceptance criteria, gates, risk,
    dependencies, and review obligations.
  - App task graphs are acyclic and reference only known task identifiers.
  - App-builder contracts are planning receipts only and never deploy code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text


class AppTaskKind(StrEnum):
    """Small governed task categories emitted by the app builder."""

    DATA_MODEL = "data_model"
    API_CONTRACT = "api_contract"
    UI_SURFACE = "ui_surface"
    VALIDATION_SECURITY = "validation_security"
    TESTS = "tests"
    INTEGRATION_WIRING = "integration_wiring"
    PREVIEW_REVIEW = "preview_review"


class AppTaskRisk(StrEnum):
    """Risk level for one app-builder task."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class ProductSpec(ContractRecord):
    """Bounded product intent compiled before any architecture or code task."""

    app_name: str
    users: tuple[str, ...]
    jobs_to_be_done: tuple[str, ...]
    core_flows: tuple[str, ...]
    non_goals: tuple[str, ...]
    security_requirements: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "app_name", require_non_empty_text(self.app_name, "app_name"))
        object.__setattr__(self, "users", _normalize_text_tuple(tuple(self.users), "users"))
        object.__setattr__(self, "jobs_to_be_done", _normalize_text_tuple(tuple(self.jobs_to_be_done), "jobs_to_be_done"))
        object.__setattr__(self, "core_flows", _normalize_text_tuple(tuple(self.core_flows), "core_flows"))
        object.__setattr__(self, "non_goals", _normalize_text_tuple(tuple(self.non_goals), "non_goals"))
        object.__setattr__(self, "security_requirements", _normalize_text_tuple(tuple(self.security_requirements), "security_requirements"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ArchitectureSpec(ContractRecord):
    """Deterministic architecture target derived from a ProductSpec."""

    app_name: str
    runtime_stack: str
    data_entities: tuple[str, ...]
    api_routes: tuple[str, ...]
    ui_surfaces: tuple[str, ...]
    modules: tuple[str, ...]
    integration_points: tuple[str, ...]
    security_controls: tuple[str, ...]
    quality_gate_profile: str = "standard_app"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "app_name", require_non_empty_text(self.app_name, "app_name"))
        object.__setattr__(self, "runtime_stack", require_non_empty_text(self.runtime_stack, "runtime_stack"))
        object.__setattr__(self, "data_entities", _normalize_text_tuple(tuple(self.data_entities), "data_entities"))
        object.__setattr__(self, "api_routes", _normalize_text_tuple(tuple(self.api_routes), "api_routes"))
        object.__setattr__(self, "ui_surfaces", _normalize_text_tuple(tuple(self.ui_surfaces), "ui_surfaces"))
        object.__setattr__(self, "modules", _normalize_text_tuple(tuple(self.modules), "modules"))
        object.__setattr__(self, "integration_points", _normalize_text_tuple(tuple(self.integration_points), "integration_points"))
        object.__setattr__(self, "security_controls", _normalize_text_tuple(tuple(self.security_controls), "security_controls"))
        object.__setattr__(self, "quality_gate_profile", require_non_empty_text(self.quality_gate_profile, "quality_gate_profile"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AppTask(ContractRecord):
    """One small software-change candidate in an app-builder task graph."""

    task_id: str
    title: str
    kind: AppTaskKind
    affected_files: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    dependencies: tuple[str, ...]
    quality_gates: tuple[str, ...]
    risk: AppTaskRisk
    review_required: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", require_non_empty_text(self.task_id, "task_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.kind, AppTaskKind):
            raise ValueError("kind must be an AppTaskKind")
        object.__setattr__(self, "affected_files", _normalize_path_tuple(tuple(self.affected_files), "affected_files"))
        object.__setattr__(self, "acceptance_criteria", _normalize_text_tuple(tuple(self.acceptance_criteria), "acceptance_criteria"))
        object.__setattr__(self, "dependencies", _normalize_text_tuple(tuple(self.dependencies), "dependencies", allow_empty=True))
        object.__setattr__(self, "quality_gates", _normalize_text_tuple(tuple(self.quality_gates), "quality_gates"))
        if not isinstance(self.risk, AppTaskRisk):
            raise ValueError("risk must be an AppTaskRisk")
        if not isinstance(self.review_required, bool):
            raise ValueError("review_required must be a bool")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AppTaskGraph(ContractRecord):
    """Acyclic app-builder task graph with proof references and no deploy edge."""

    graph_id: str
    app_name: str
    tasks: tuple[AppTask, ...]
    root_task_ids: tuple[str, ...] = ()
    terminal_task_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "graph_id", require_non_empty_text(self.graph_id, "graph_id"))
        object.__setattr__(self, "app_name", require_non_empty_text(self.app_name, "app_name"))
        if not self.tasks:
            raise ValueError("tasks must contain at least one item")
        task_tuple = tuple(self.tasks)
        for task in task_tuple:
            if not isinstance(task, AppTask):
                raise ValueError("tasks must contain AppTask records")
        _validate_task_graph(task_tuple)
        referenced = frozenset(dep for task in task_tuple for dep in task.dependencies)
        roots = tuple(task.task_id for task in task_tuple if not task.dependencies)
        terminals = tuple(task.task_id for task in task_tuple if task.task_id not in referenced)
        object.__setattr__(self, "tasks", freeze_value(list(task_tuple)))
        object.__setattr__(self, "root_task_ids", _validate_graph_task_refs(self.root_task_ids or roots, task_tuple, "root_task_ids"))
        object.__setattr__(self, "terminal_task_ids", _validate_graph_task_refs(self.terminal_task_ids or terminals, task_tuple, "terminal_task_ids"))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(tuple(self.evidence_refs), "evidence_refs"))
        metadata = dict(self.metadata)
        if metadata.get("direct_deployment_allowed") is not False:
            raise ValueError("direct_deployment_allowed_must_be_false")
        if metadata.get("commit_candidate_allowed") is not False:
            raise ValueError("commit_candidate_allowed_must_be_false")
        object.__setattr__(self, "metadata", freeze_value(metadata))


def app_task_graph_to_json_dict(graph: AppTaskGraph) -> dict[str, Any]:
    """Return the JSON-contract representation of an app task graph."""
    return graph.to_json_dict()


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    normalized: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str):
            raise ValueError(f"{field_name}[{index}] must be a string")
        stripped = value.strip()
        if stripped and stripped not in normalized:
            normalized.append(stripped)
    if not normalized and not allow_empty:
        raise ValueError(f"{field_name} must contain at least one item")
    return freeze_value(normalized)


def _normalize_path_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str):
            raise ValueError(f"{field_name}[{index}] must be a string")
        path = value.replace("\\", "/").strip()
        if not path:
            continue
        parts = PurePosixPath(path).parts
        if path.startswith("/") or (parts and ":" in parts[0]):
            raise ValueError(f"{field_name}[{index}] must be repository-relative")
        if ".." in parts:
            raise ValueError(f"{field_name}[{index}] must not traverse parent directories")
        if path not in normalized:
            normalized.append(path)
    if not normalized:
        raise ValueError(f"{field_name} must contain at least one item")
    return freeze_value(normalized)


def _validate_graph_task_refs(task_ids: tuple[str, ...], tasks: tuple[AppTask, ...], field_name: str) -> tuple[str, ...]:
    normalized = _normalize_text_tuple(tuple(task_ids), field_name)
    known = {task.task_id for task in tasks}
    missing = tuple(task_id for task_id in normalized if task_id not in known)
    if missing:
        raise ValueError(f"{field_name}_unknown:{','.join(missing)}")
    return normalized


def _validate_task_graph(tasks: tuple[AppTask, ...]) -> None:
    task_ids = [task.task_id for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("duplicate_app_task_id")
    known = set(task_ids)
    for task in tasks:
        missing = tuple(dep for dep in task.dependencies if dep not in known)
        if missing:
            raise ValueError(f"missing_app_task_dependency:{','.join(missing)}")
    visiting: set[str] = set()
    visited: set[str] = set()
    adjacency = {task.task_id: task.dependencies for task in tasks}
    for task_id in task_ids:
        _visit_task(task_id, adjacency, visiting, visited)


def _visit_task(task_id: str, adjacency: dict[str, tuple[str, ...]], visiting: set[str], visited: set[str]) -> None:
    if task_id in visited:
        return
    if task_id in visiting:
        raise ValueError("app_task_dependency_cycle")
    visiting.add(task_id)
    for dependency_id in adjacency[task_id]:
        _visit_task(dependency_id, adjacency, visiting, visited)
    visiting.remove(task_id)
    visited.add(task_id)
