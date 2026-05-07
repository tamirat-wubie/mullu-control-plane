"""Purpose: software-outcome learning candidate contracts.
Governance scope: closure-derived coding patterns, failure signatures,
    receipt references, gate references, raw-log exclusion, and planning use.
Dependencies: dataclasses, enum, pathlib, typing, and shared contract helpers.
Invariants:
  - Candidates are derived from structured software evidence, not raw logs.
  - Raw log payloads are never admissible as planning knowledge.
  - Procedural candidates and risk candidates have explicit memory targets.
  - Planning use still requires a LearningAdmissionDecision(status=admit).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text


class SoftwareLearningKind(StrEnum):
    """Kinds of software outcome learning candidates."""

    PROCEDURAL_FIX_PATTERN = "procedural_fix_pattern"
    RISK_FAILURE_SIGNATURE = "risk_failure_signature"


class SoftwareMemoryTarget(StrEnum):
    """Memory class a software learning candidate may enter after admission."""

    PROCEDURAL_MEMORY = "procedural_memory"
    RISK_MEMORY = "risk_memory"


@dataclass(frozen=True, slots=True)
class SoftwareOutcomeLearningCandidate(ContractRecord):
    """Sanitized knowledge candidate derived from a governed software outcome."""

    knowledge_id: str
    kind: SoftwareLearningKind
    memory_target: SoftwareMemoryTarget
    request_id: str
    repository: str
    summary: str
    pattern: str
    affected_files: tuple[str, ...]
    receipt_refs: tuple[str, ...]
    gate_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    error_signature: str = ""
    raw_log_included: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "knowledge_id", require_non_empty_text(self.knowledge_id, "knowledge_id"))
        if not isinstance(self.kind, SoftwareLearningKind):
            raise ValueError("kind must be a SoftwareLearningKind")
        if not isinstance(self.memory_target, SoftwareMemoryTarget):
            raise ValueError("memory_target must be a SoftwareMemoryTarget")
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "repository", require_non_empty_text(self.repository, "repository"))
        object.__setattr__(self, "summary", require_non_empty_text(self.summary, "summary"))
        object.__setattr__(self, "pattern", require_non_empty_text(self.pattern, "pattern"))
        object.__setattr__(self, "affected_files", _normalize_path_tuple(tuple(self.affected_files), "affected_files"))
        object.__setattr__(self, "receipt_refs", _normalize_text_tuple(tuple(self.receipt_refs), "receipt_refs"))
        object.__setattr__(self, "gate_refs", _normalize_text_tuple(tuple(self.gate_refs), "gate_refs"))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(tuple(self.evidence_refs), "evidence_refs"))
        object.__setattr__(self, "error_signature", str(self.error_signature).strip())
        if self.kind is SoftwareLearningKind.RISK_FAILURE_SIGNATURE and not self.error_signature:
            raise ValueError("risk_failure_signature_requires_error_signature")
        if not isinstance(self.raw_log_included, bool):
            raise ValueError("raw_log_included must be a bool")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


def software_learning_candidate_to_json_dict(candidate: SoftwareOutcomeLearningCandidate) -> dict[str, Any]:
    """Return the JSON-contract representation of a software learning candidate."""
    return candidate.to_json_dict()


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str):
            raise ValueError(f"{field_name}[{index}] must be a string")
        stripped = value.strip()
        if stripped and stripped not in normalized:
            normalized.append(stripped)
    if not normalized:
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
        if path.startswith("/") or (parts and ":" in parts[0]) or ".." in parts:
            raise ValueError(f"{field_name}[{index}] must be repository-relative")
        if path not in normalized:
            normalized.append(path)
    if not normalized:
        raise ValueError(f"{field_name} must contain at least one item")
    return freeze_value(normalized)
