"""Concept Box ledger for governed note-memory projections.

Purpose: represent notes, projects, workflows, decisions, and processes as
auditable Concept Boxes for InceptaDive-M structural interrogation.
Governance scope: lineage separation, projection-only state, ProofState
retention, deterministic hashing, and source-note traceability.
Dependencies: dataclasses, JSONL persistence, runtime invariant helpers, and
note-memory mesh primitives.
Invariants: a Concept Box is a projection, never the source of truth; every Box
records source evidence, lineage, proof state, and a deterministic snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.note_memory_mesh import NoteMemoryEvent, ProofState


class ConceptBoxType(StrEnum):
    """Allowed Concept Box source classes."""

    NOTE = "note"
    PROJECT = "project"
    WORKFLOW = "workflow"
    DECISION = "decision"
    PROCESS = "process"


def _required_text(value: Mapping[str, object], field_name: str) -> str:
    raw_value = value[field_name]
    if not isinstance(raw_value, str):
        raise RuntimeCoreInvariantError(f"{field_name} must be a string")
    text = raw_value.strip()
    if not text:
        raise RuntimeCoreInvariantError(f"{field_name} must be non-empty")
    return text


def _optional_text(value: Mapping[str, object], field_name: str) -> str:
    raw_value = value.get(field_name, "")
    if raw_value is None:
        return ""
    if not isinstance(raw_value, str):
        raise RuntimeCoreInvariantError(f"{field_name} must be a string")
    return raw_value.strip()


def _required_text_list(value: Mapping[str, object], field_name: str) -> tuple[str, ...]:
    raw_value = value[field_name]
    if not isinstance(raw_value, list):
        raise RuntimeCoreInvariantError(f"{field_name} must be a list")
    text_values: list[str] = []
    for item in raw_value:
        if not isinstance(item, str):
            raise RuntimeCoreInvariantError(f"{field_name} items must be strings")
        text = item.strip()
        if not text:
            raise RuntimeCoreInvariantError(f"{field_name} items must be non-empty")
        text_values.append(text)
    return tuple(text_values)


def _canonical_json(value: Mapping[str, object]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), default=str)


def _snapshot_hash(value: Mapping[str, object]) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ConceptBox:
    """Projection nucleus for concept-field traversal."""

    box_id: str
    box_type: ConceptBoxType
    source_note_ids: tuple[str, ...]
    source_event_ids: tuple[str, ...]
    identity_facets: tuple[str, ...]
    behavior_facets: tuple[str, ...]
    intention_facets: tuple[str, ...]
    cause_facets: tuple[str, ...]
    effect_facets: tuple[str, ...]
    risk_facets: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    created_at: str
    updated_at: str
    lineage: tuple[str, ...]
    proof_state: ProofState
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        if not self.box_id.strip():
            raise RuntimeCoreInvariantError("box_id must be non-empty")
        if not self.identity_facets:
            raise RuntimeCoreInvariantError("Concept Box requires identity_facets")
        if not self.lineage:
            raise RuntimeCoreInvariantError("Concept Box requires lineage")
        if self.snapshot_hash and self.snapshot_hash != self.expected_snapshot_hash():
            raise RuntimeCoreInvariantError("Concept Box snapshot_hash mismatch")

    def to_dict(self, *, include_snapshot_hash: bool = True) -> dict[str, object]:
        """Return a deterministic JSON-compatible Concept Box."""

        value: dict[str, object] = {
            "box_id": self.box_id,
            "box_type": self.box_type.value,
            "source_note_ids": list(self.source_note_ids),
            "source_event_ids": list(self.source_event_ids),
            "identity_facets": list(self.identity_facets),
            "behavior_facets": list(self.behavior_facets),
            "intention_facets": list(self.intention_facets),
            "cause_facets": list(self.cause_facets),
            "effect_facets": list(self.effect_facets),
            "risk_facets": list(self.risk_facets),
            "evidence_refs": list(self.evidence_refs),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "lineage": list(self.lineage),
            "proof_state": self.proof_state.value,
            "projection_only": True,
        }
        if include_snapshot_hash:
            value["snapshot_hash"] = self.snapshot_hash
        return value

    def expected_snapshot_hash(self) -> str:
        """Return the expected deterministic snapshot hash."""

        return _snapshot_hash(self.to_dict(include_snapshot_hash=False))

    def with_integrity(self) -> "ConceptBox":
        """Return the Box with deterministic id and snapshot hash populated."""

        box_id = self.box_id
        if box_id == "pending":
            box_id = stable_identifier(
                "concept-box",
                {
                    "box_type": self.box_type.value,
                    "source_note_ids": self.source_note_ids,
                    "source_event_ids": self.source_event_ids,
                    "identity_facets": self.identity_facets,
                },
            )
        unsigned = replace(self, box_id=box_id, snapshot_hash="")
        return replace(unsigned, snapshot_hash=unsigned.expected_snapshot_hash())

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ConceptBox":
        """Rehydrate a Concept Box from JSON-compatible data."""

        return cls(
            box_id=_required_text(value, "box_id"),
            box_type=ConceptBoxType(_required_text(value, "box_type")),
            source_note_ids=_required_text_list(value, "source_note_ids"),
            source_event_ids=_required_text_list(value, "source_event_ids"),
            identity_facets=_required_text_list(value, "identity_facets"),
            behavior_facets=_required_text_list(value, "behavior_facets"),
            intention_facets=_required_text_list(value, "intention_facets"),
            cause_facets=_required_text_list(value, "cause_facets"),
            effect_facets=_required_text_list(value, "effect_facets"),
            risk_facets=_required_text_list(value, "risk_facets"),
            evidence_refs=_required_text_list(value, "evidence_refs"),
            created_at=_required_text(value, "created_at"),
            updated_at=_required_text(value, "updated_at"),
            lineage=_required_text_list(value, "lineage"),
            proof_state=ProofState(_required_text(value, "proof_state")),
            snapshot_hash=_optional_text(value, "snapshot_hash"),
        )


class ConceptBoxLedger:
    """Append-only local ledger for Concept Box projections."""

    def __init__(self, root_path: str | Path) -> None:
        self.root_path = Path(root_path)

    def append_box(self, box: ConceptBox) -> ConceptBox:
        """Persist one Concept Box projection and return its integrity form."""

        projected_box = box.with_integrity()
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self._ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical_json(projected_box.to_dict()))
            handle.write("\n")
        return projected_box

    def list_boxes(self) -> tuple[ConceptBox, ...]:
        """Return persisted Concept Boxes in append order."""

        if not self._ledger_path.exists():
            return ()
        boxes: list[ConceptBox] = []
        with self._ledger_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    boxes.append(ConceptBox.from_dict(json.loads(stripped)))
                except (KeyError, TypeError, ValueError, json.JSONDecodeError, RuntimeCoreInvariantError) as exc:
                    raise RuntimeCoreInvariantError(
                        f"invalid Concept Box ledger entry at {self._ledger_path}:{line_number}"
                    ) from exc
        return tuple(boxes)

    @property
    def _ledger_path(self) -> Path:
        return self.root_path / "concept-boxes.jsonl"


def build_note_concept_box(event: NoteMemoryEvent, *, updated_at: str | None = None) -> ConceptBox:
    """Build a projection-only Concept Box from one note-memory event."""

    summary = event.content_summary.strip()
    lower_summary = summary.lower()
    risk_markers = ("risk", "block", "blocked", "pending", "unsafe", "missing", "contradict")
    behavior_markers = ("after", "when", "if", "must", "should", "requires", "review", "deploy", "test")
    intention_markers = ("goal", "intent", "wants", "need", "needs", "request", "approve", "release")
    cause_markers = ("because", "due to", "source", "cause", "requested")
    effect_markers = ("therefore", "so ", "blocks", "unlocks", "enables", "prevents")
    return ConceptBox(
        box_id="pending",
        box_type=ConceptBoxType.NOTE,
        source_note_ids=(event.note_id,),
        source_event_ids=(event.event_id,),
        identity_facets=(f"note:{event.note_id}", summary),
        behavior_facets=_selected_facets(summary, lower_summary, behavior_markers),
        intention_facets=_selected_facets(summary, lower_summary, intention_markers),
        cause_facets=_selected_facets(summary, lower_summary, cause_markers),
        effect_facets=_selected_facets(summary, lower_summary, effect_markers),
        risk_facets=_selected_facets(summary, lower_summary, risk_markers),
        evidence_refs=event.evidence_refs,
        created_at=event.created_at,
        updated_at=updated_at or event.created_at,
        lineage=("note-memory", "InceptaDive-M"),
        proof_state=event.proof_state,
    ).with_integrity()


def build_project_concept_box(
    *,
    project_id: str,
    project_label: str,
    source_events: Iterable[NoteMemoryEvent],
    created_at: str,
    updated_at: str,
) -> ConceptBox:
    """Build a project Concept Box from note-memory source events."""

    events = tuple(source_events)
    if not events:
        raise RuntimeCoreInvariantError("project Concept Box requires source_events")
    proof_state = ProofState.PASS if all(event.proof_state == ProofState.PASS for event in events) else ProofState.UNKNOWN
    return ConceptBox(
        box_id="pending",
        box_type=ConceptBoxType.PROJECT,
        source_note_ids=tuple(event.note_id for event in events),
        source_event_ids=tuple(event.event_id for event in events),
        identity_facets=(project_id, project_label),
        behavior_facets=tuple(event.content_summary for event in events if _contains_any(event.content_summary, ("build", "run", "deploy"))),
        intention_facets=(f"project:{project_label}",),
        cause_facets=tuple(event.source_ref for event in events),
        effect_facets=tuple(event.content_summary for event in events if _contains_any(event.content_summary, ("unlocks", "blocks"))),
        risk_facets=tuple(event.content_summary for event in events if _contains_any(event.content_summary, ("risk", "pending", "missing"))),
        evidence_refs=tuple(ref for event in events for ref in event.evidence_refs),
        created_at=created_at,
        updated_at=updated_at,
        lineage=("note-memory", "InceptaDive-M", "project-box"),
        proof_state=proof_state,
    ).with_integrity()


def _selected_facets(summary: str, lower_summary: str, markers: Sequence[str]) -> tuple[str, ...]:
    return (summary,) if any(marker in lower_summary for marker in markers) else ()


def _contains_any(value: str, markers: Sequence[str]) -> bool:
    lower_value = value.lower()
    return any(marker in lower_value for marker in markers)
