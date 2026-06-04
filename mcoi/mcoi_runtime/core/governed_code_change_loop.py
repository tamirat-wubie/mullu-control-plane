"""Purpose: bind sandboxed code-worker execution to SDLC closure gates.
Governance scope: UAO-style action refs, code-worker lease dispatch,
    non-terminal worker receipts, SDLC receipt requirements, and closure blocks.
Dependencies: code_worker contracts/runtime and stable identifier utilities.
Invariants:
  - Code-worker receipts are execution evidence, not terminal closure.
  - Closure requires implementation, verification, and recovery handoff receipts.
  - Missing SDLC receipts produce explicit blockers and no silent success.
  - Worker authority remains lease-bound by repository, command, path, and time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from mcoi_runtime.contracts._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
)
from mcoi_runtime.contracts.code_worker import (
    CodeWorkerCommandResult,
    CodeWorkerLease,
    CodeWorkerReceiptStatus,
)
from mcoi_runtime.core.invariants import stable_identifier
from mcoi_runtime.workers.code_worker import SandboxedCodeWorker


REQUIRED_SDLC_RECEIPT_KINDS: tuple[str, ...] = (
    "implementation_receipt",
    "verification_receipt",
    "recovery_handoff",
)


@dataclass(frozen=True, slots=True)
class GovernedCodeChangeRequest(ContractRecord):
    """Request for one bounded governed code-worker command."""

    action_id: str
    tenant_id: str
    actor_id: str
    repository: str
    commit_sha: str
    command_id: str
    argv: tuple[str, ...]
    allowed_paths: tuple[str, ...]
    allowed_commands: tuple[tuple[str, ...], ...]
    expires_at: str
    cwd: str = "."
    timeout_seconds: int = 120
    memory_mb: int = 1024
    observed_sdlc_receipt_refs: Mapping[str, str] = field(default_factory=dict)
    required_sdlc_receipt_kinds: tuple[str, ...] = REQUIRED_SDLC_RECEIPT_KINDS
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "action_id",
            "tenant_id",
            "actor_id",
            "repository",
            "commit_sha",
            "command_id",
            "cwd",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        object.__setattr__(self, "expires_at", require_datetime_text(self.expires_at, "expires_at"))
        object.__setattr__(self, "argv", _freeze_string_tuple(self.argv, "argv"))
        object.__setattr__(
            self,
            "allowed_paths",
            _freeze_string_tuple(self.allowed_paths, "allowed_paths"),
        )
        object.__setattr__(
            self,
            "allowed_commands",
            _freeze_command_tuple(self.allowed_commands, "allowed_commands"),
        )
        object.__setattr__(
            self,
            "required_sdlc_receipt_kinds",
            _freeze_string_tuple(
                self.required_sdlc_receipt_kinds,
                "required_sdlc_receipt_kinds",
            ),
        )
        _validate_positive_int(self.timeout_seconds, "timeout_seconds")
        _validate_positive_int(self.memory_mb, "memory_mb")
        object.__setattr__(
            self,
            "observed_sdlc_receipt_refs",
            _freeze_receipt_mapping(self.observed_sdlc_receipt_refs),
        )
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class GovernedCodeChangeLoopResult(ContractRecord):
    """Result for one governed code-change dry-run bridge."""

    action_id: str
    uao_ref: str
    causal_decision_trace_ref: str
    lease: CodeWorkerLease
    command_result: CodeWorkerCommandResult
    code_worker_receipt_ref: str
    required_sdlc_receipt_kinds: tuple[str, ...]
    observed_sdlc_receipt_refs: Mapping[str, str]
    missing_sdlc_receipt_kinds: tuple[str, ...]
    closure_allowed: bool
    solver_outcome: str
    next_action: str
    closure_blockers: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "action_id",
            "uao_ref",
            "causal_decision_trace_ref",
            "code_worker_receipt_ref",
            "solver_outcome",
            "next_action",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        if not isinstance(self.lease, CodeWorkerLease):
            raise ValueError("lease must be a CodeWorkerLease")
        if not isinstance(self.command_result, CodeWorkerCommandResult):
            raise ValueError("command_result must be a CodeWorkerCommandResult")
        if not isinstance(self.closure_allowed, bool):
            raise ValueError("closure_allowed must be a bool")
        object.__setattr__(
            self,
            "required_sdlc_receipt_kinds",
            _freeze_string_tuple(
                self.required_sdlc_receipt_kinds,
                "required_sdlc_receipt_kinds",
            ),
        )
        object.__setattr__(
            self,
            "missing_sdlc_receipt_kinds",
            _freeze_string_tuple(
                self.missing_sdlc_receipt_kinds,
                "missing_sdlc_receipt_kinds",
                allow_empty=True,
            ),
        )
        object.__setattr__(
            self,
            "closure_blockers",
            _freeze_string_tuple(self.closure_blockers, "closure_blockers", allow_empty=True),
        )
        object.__setattr__(
            self,
            "observed_sdlc_receipt_refs",
            _freeze_receipt_mapping(self.observed_sdlc_receipt_refs),
        )
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


def build_code_worker_lease(request: GovernedCodeChangeRequest) -> CodeWorkerLease:
    """Build the exact code-worker lease for a governed code-change request."""

    if not isinstance(request, GovernedCodeChangeRequest):
        raise ValueError("request must be a GovernedCodeChangeRequest")
    lease_id = stable_identifier(
        "code-worker-lease",
        {
            "action_id": request.action_id,
            "tenant_id": request.tenant_id,
            "repository": request.repository,
            "commit_sha": request.commit_sha,
            "command_id": request.command_id,
            "argv": request.argv,
            "allowed_paths": request.allowed_paths,
        },
    )
    return CodeWorkerLease(
        lease_id=lease_id,
        tenant_id=request.tenant_id,
        repository=request.repository,
        commit_sha=request.commit_sha,
        allowed_paths=request.allowed_paths,
        allowed_commands=request.allowed_commands,
        network_enabled=False,
        timeout_seconds=request.timeout_seconds,
        memory_mb=request.memory_mb,
        expires_at=request.expires_at,
        metadata={
            "action_id": request.action_id,
            "actor_id": request.actor_id,
            "uao_ref": _uao_ref(request.action_id),
            "receipt_is_not_terminal_closure": True,
        },
    )


def run_governed_code_change_loop(
    request: GovernedCodeChangeRequest,
    worker: SandboxedCodeWorker,
) -> GovernedCodeChangeLoopResult:
    """Run one lease-bound worker command and evaluate SDLC closure readiness."""

    if not isinstance(request, GovernedCodeChangeRequest):
        raise ValueError("request must be a GovernedCodeChangeRequest")
    if not isinstance(worker, SandboxedCodeWorker):
        raise ValueError("worker must be a SandboxedCodeWorker")
    lease = build_code_worker_lease(request)
    command_result = worker.execute_command(
        lease,
        command_id=request.command_id,
        argv=request.argv,
        cwd=request.cwd,
    )
    missing_receipts = _missing_sdlc_receipts(
        required=request.required_sdlc_receipt_kinds,
        observed=request.observed_sdlc_receipt_refs,
    )
    blockers = _closure_blockers(
        command_result=command_result,
        missing_sdlc_receipt_kinds=missing_receipts,
    )
    closure_allowed = not blockers
    solver_outcome = _solver_outcome(
        command_result=command_result,
        missing_sdlc_receipt_kinds=missing_receipts,
    )
    return GovernedCodeChangeLoopResult(
        action_id=request.action_id,
        uao_ref=_uao_ref(request.action_id),
        causal_decision_trace_ref=f"trace://governed-code-change/{request.action_id}",
        lease=lease,
        command_result=command_result,
        code_worker_receipt_ref=f"receipt://{command_result.receipt.receipt_id}",
        required_sdlc_receipt_kinds=request.required_sdlc_receipt_kinds,
        observed_sdlc_receipt_refs=request.observed_sdlc_receipt_refs,
        missing_sdlc_receipt_kinds=missing_receipts,
        closure_allowed=closure_allowed,
        solver_outcome=solver_outcome,
        next_action=_next_action(
            command_result=command_result,
            missing_sdlc_receipt_kinds=missing_receipts,
        ),
        closure_blockers=blockers,
        metadata={
            "worker_receipt_not_terminal_closure": True,
            "sdlc_receipts_required_for_terminal_closure": True,
        },
    )


def _uao_ref(action_id: str) -> str:
    return f"uao://governed-code-change/{action_id}"


def _missing_sdlc_receipts(
    *,
    required: tuple[str, ...],
    observed: Mapping[str, str],
) -> tuple[str, ...]:
    return tuple(kind for kind in required if kind not in observed)


def _closure_blockers(
    *,
    command_result: CodeWorkerCommandResult,
    missing_sdlc_receipt_kinds: tuple[str, ...],
) -> tuple[str, ...]:
    blockers: list[str] = []
    if command_result.status is not CodeWorkerReceiptStatus.SUCCEEDED:
        blockers.append(f"code_worker_status_{command_result.status.value}")
    blockers.extend(
        f"missing_sdlc_{kind}" for kind in missing_sdlc_receipt_kinds
    )
    return tuple(blockers)


def _solver_outcome(
    *,
    command_result: CodeWorkerCommandResult,
    missing_sdlc_receipt_kinds: tuple[str, ...],
) -> str:
    if command_result.status is CodeWorkerReceiptStatus.BLOCKED:
        return "GovernanceBlocked"
    if command_result.status is CodeWorkerReceiptStatus.SUCCEEDED and not missing_sdlc_receipt_kinds:
        return "SolvedVerified"
    if command_result.status is CodeWorkerReceiptStatus.SUCCEEDED:
        return "AwaitingEvidence"
    return "SolvedUnverified"


def _next_action(
    *,
    command_result: CodeWorkerCommandResult,
    missing_sdlc_receipt_kinds: tuple[str, ...],
) -> str:
    if command_result.status is CodeWorkerReceiptStatus.BLOCKED:
        return "repair_or_reduce_code_worker_lease"
    if missing_sdlc_receipt_kinds:
        return "emit_required_sdlc_receipts"
    if command_result.status is CodeWorkerReceiptStatus.SUCCEEDED:
        return "prepare_terminal_closure_review"
    return "inspect_code_worker_execution_result"


def _freeze_string_tuple(
    values: Sequence[str],
    field_name: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if isinstance(values, str) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be a tuple of strings")
    frozen = tuple(require_non_empty_text(value, f"{field_name}[{index}]") for index, value in enumerate(values))
    if not frozen and not allow_empty:
        raise ValueError(f"{field_name} must contain at least one item")
    return freeze_value(frozen)


def _freeze_command_tuple(
    values: Sequence[Sequence[str]],
    field_name: str,
) -> tuple[tuple[str, ...], ...]:
    if not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be a tuple of argv tuples")
    commands = tuple(
        _freeze_string_tuple(tuple(command), f"{field_name}[{index}]")
        for index, command in enumerate(values)
    )
    if not commands:
        raise ValueError(f"{field_name} must contain at least one command")
    return freeze_value(commands)


def _freeze_receipt_mapping(value: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("observed_sdlc_receipt_refs must be a mapping")
    normalized: dict[str, str] = {}
    for key, receipt_ref in value.items():
        normalized_key = require_non_empty_text(str(key), "observed_sdlc_receipt_refs.key")
        normalized_ref = require_non_empty_text(
            receipt_ref,
            f"observed_sdlc_receipt_refs[{normalized_key}]",
        )
        if not normalized_ref.startswith("receipt://"):
            raise ValueError("observed_sdlc_receipt_refs values must use receipt:// refs")
        normalized[normalized_key] = normalized_ref
    return freeze_value(normalized)


def _validate_positive_int(value: int, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{field_name} must be a positive integer")
