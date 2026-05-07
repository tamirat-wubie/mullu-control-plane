"""Purpose: HTTP access to MIL audit replay and runbook admission.
Governance scope: MIL audit records, replay persistence, and procedural memory admission.
Dependencies: FastAPI, MIL audit store, trace/replay stores, persisted replay validator, runbook library.
Invariants:
  - MIL audit stores must be explicit and existing before reads.
  - Replay bundles persist trace spine before replay records.
  - Runbook admission requires persisted replay validation and explicit learning admission.
  - HTTP errors expose bounded symbolic failure classes only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.contracts.learning import LearningAdmissionDecision, LearningAdmissionStatus
from mcoi_runtime.contracts.policy import DecisionReason
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.persisted_replay import PersistedReplayValidator
from mcoi_runtime.core.replay_engine import ReplayContext
from mcoi_runtime.core.runbook import RunbookAdmissionResult, RunbookLibrary, RunbookProvenance
from mcoi_runtime.persistence.errors import PersistenceError
from mcoi_runtime.persistence._serialization import serialize_record
from mcoi_runtime.persistence.mil_audit_store import MILAuditReplayPersistence, MILAuditStore
from mcoi_runtime.persistence.replay_store import ReplayStore
from mcoi_runtime.persistence.runbook_store import RunbookStore
from mcoi_runtime.persistence.trace_store import TraceStore

router = APIRouter(tags=["mil-audit"])


class MILAuditAdmitRunbookRequest(BaseModel):
    """HTTP request for admitting a replay-backed MIL audit runbook."""

    record_id: str = Field(..., min_length=1)
    mil_audit_store_path: str = Field(..., min_length=1)
    trace_store_path: str = Field(..., min_length=1)
    replay_store_path: str = Field(..., min_length=1)
    runbook_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    runbook_store_path: str | None = Field(default=None, min_length=1)


class MILAuditRunbookEnvelope(BaseModel):
    """HTTP response envelope for MIL audit runbook admission."""

    operation: str
    record_id: str
    program_id: str
    goal_id: str
    execution_id: str
    policy_decision_id: str
    verification_passed: bool
    replay_id: str
    replay_mode: str
    chain_sequence: int
    source_hash: str
    trace_ids: list[str]
    runbook_id: str
    runbook_status: str
    runbook_persisted: bool
    reasons: list[str]
    provenance: dict[str, Any] | None
    governed: bool = True


class MILAuditStoredRunbookEnvelope(BaseModel):
    """HTTP response envelope for persisted MIL-derived runbooks."""

    operation: str
    count: int
    runbook_id: str | None = None
    found: bool | None = None
    runbooks: list[dict[str, Any]]
    governed: bool = True


def _bounded_http_error(summary: str, exc: Exception) -> dict[str, str | bool]:
    """Return a bounded HTTP error payload without leaking local paths."""
    return {"error": summary, "type": type(exc).__name__, "governed": True}


def _existing_store_path(value: str) -> Path:
    """Resolve an existing MIL audit store path."""
    path = Path(value)
    if not path.exists():
        raise FileNotFoundError("MIL audit store path not found")
    return path


def _provenance_dict(provenance: RunbookProvenance | None) -> dict[str, Any] | None:
    """Project runbook provenance into JSON-safe fields."""
    if provenance is None:
        return None
    return {
        "execution_id": provenance.execution_id,
        "verification_id": provenance.verification_id,
        "replay_id": provenance.replay_id,
        "trace_id": provenance.trace_id,
        "learning_admission_id": provenance.learning_admission_id,
    }


def _runbook_entry_dict(entry: Any) -> dict[str, Any]:
    """Project a persisted runbook entry into deterministic JSON fields."""
    raw = json.loads(serialize_record(entry))
    if not isinstance(raw, dict):
        raise ValueError("serialized runbook entry must be a JSON object")
    return raw


def _admit_mil_audit_runbook(
    req: MILAuditAdmitRunbookRequest,
) -> tuple[MILAuditReplayPersistence, RunbookAdmissionResult, bool]:
    """Persist a MIL audit replay bundle and admit it through the runbook library."""
    audit_store = MILAuditStore(_existing_store_path(req.mil_audit_store_path))
    trace_store = TraceStore(Path(req.trace_store_path))
    replay_store = ReplayStore(Path(req.replay_store_path))
    bundle = audit_store.persist_replay_bundle(
        req.record_id,
        trace_store=trace_store,
        replay_store=replay_store,
    )
    record = bundle.replay_lookup.record
    learning = LearningAdmissionDecision(
        admission_id=stable_identifier(
            "mil-audit-runbook-admission",
            {"record_id": record.record_id, "runbook_id": req.runbook_id},
        ),
        knowledge_id=req.runbook_id,
        status=LearningAdmissionStatus.ADMIT,
        reasons=(DecisionReason("MIL audit replay verified", "mil_audit_replay_verified"),),
        issued_at=datetime.now(timezone.utc).isoformat(),
    )
    library = RunbookLibrary(
        replay_validator=PersistedReplayValidator(
            replay_store=replay_store,
            trace_store=trace_store,
        ),
        clock=lambda: datetime.now(timezone.utc).isoformat(),
    )
    admission = library.admit(
        runbook_id=req.runbook_id,
        name=req.name,
        description=req.description,
        template={
            "action_type": "mil_audit_replay",
            "program_id": record.program_id,
            "goal_id": record.goal_id,
        },
        bindings_schema={},
        replay_id=bundle.replay_id,
        execution_id=record.execution_id,
        verification_id=record.record_id,
        execution_succeeded=True,
        verification_passed=record.verification_passed,
        learning_admission=learning,
        context=ReplayContext(
            state_hash=bundle.replay_record.state_hash,
            environment_digest=bundle.replay_record.environment_digest,
        ),
    )
    runbook_persisted = False
    if req.runbook_store_path is not None and admission.entry is not None:
        runbook_persisted = RunbookStore(Path(req.runbook_store_path)).save(admission.entry)
    return bundle, admission, runbook_persisted


@router.post("/api/v1/mil-audit/admit-runbook", response_model=MILAuditRunbookEnvelope)
def admit_mil_audit_runbook(req: MILAuditAdmitRunbookRequest) -> MILAuditRunbookEnvelope:
    """Admit a MIL audit replay bundle as a verified procedural runbook."""
    try:
        bundle, admission, runbook_persisted = _admit_mil_audit_runbook(req)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=_bounded_http_error("MIL audit store unavailable", exc),
        ) from exc
    except (PersistenceError, RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=_bounded_http_error("MIL audit runbook admission rejected", exc),
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=400,
            detail=_bounded_http_error("MIL audit store access failed", exc),
        ) from exc

    record = bundle.replay_lookup.record
    return MILAuditRunbookEnvelope(
        operation="admit-runbook",
        record_id=record.record_id,
        program_id=record.program_id,
        goal_id=record.goal_id,
        execution_id=record.execution_id,
        policy_decision_id=record.policy_decision_id,
        verification_passed=record.verification_passed,
        replay_id=bundle.replay_id,
        replay_mode=bundle.replay_record.mode.value,
        chain_sequence=bundle.replay_lookup.chain_entry.sequence_number,
        source_hash=bundle.replay_record.source_hash,
        trace_ids=list(bundle.trace_ids),
        runbook_id=admission.runbook_id,
        runbook_status=admission.status.value,
        runbook_persisted=runbook_persisted,
        reasons=list(admission.reasons),
        provenance=_provenance_dict(admission.entry.provenance if admission.entry else None),
    )


@router.get("/api/v1/mil-audit/runbooks", response_model=MILAuditStoredRunbookEnvelope)
def list_mil_audit_runbooks(runbook_store_path: str) -> MILAuditStoredRunbookEnvelope:
    """List persisted MIL-derived runbooks from an explicit runbook store."""
    try:
        entries = RunbookStore(Path(runbook_store_path)).load_all()
    except (PersistenceError, RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=_bounded_http_error("MIL audit runbook query rejected", exc),
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=400,
            detail=_bounded_http_error("MIL audit runbook store access failed", exc),
        ) from exc
    return MILAuditStoredRunbookEnvelope(
        operation="runbook-list",
        count=len(entries),
        runbooks=[_runbook_entry_dict(entry) for entry in entries],
    )


@router.get("/api/v1/mil-audit/runbooks/{runbook_id}", response_model=MILAuditStoredRunbookEnvelope)
def get_mil_audit_runbook(runbook_id: str, runbook_store_path: str) -> MILAuditStoredRunbookEnvelope:
    """Fetch one persisted MIL-derived runbook from an explicit runbook store."""
    try:
        entry = RunbookStore(Path(runbook_store_path)).load(runbook_id)
    except PersistenceError as exc:
        raise HTTPException(
            status_code=404,
            detail=_bounded_http_error("MIL audit runbook unavailable", exc),
        ) from exc
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=_bounded_http_error("MIL audit runbook query rejected", exc),
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=400,
            detail=_bounded_http_error("MIL audit runbook store access failed", exc),
        ) from exc
    return MILAuditStoredRunbookEnvelope(
        operation="runbook-get",
        count=1,
        runbook_id=entry.runbook_id,
        found=True,
        runbooks=[_runbook_entry_dict(entry)],
    )
