#!/usr/bin/env python3
"""Produce a live read-only RepositoryObservationEvidencePacket.

Purpose: collect digest-only local repository observation evidence from an
allowlisted read-only git command set and persist a packet without serializing
raw command output.
Governance scope: OCE schema completeness, RAG command-to-digest relations,
CDCV observation-to-admission causality, CQTE proof-state gates, UWMA receipt
anchoring, SRCA finite command execution, and PRS focused closure.
Dependencies: Python standard library,
scripts.validate_repository_observation_evidence_packet, and local git.
Invariants:
  - Only the fixed repository observation command set can run.
  - Commands run without shell expansion.
  - Raw git status, diff, file inventory, file contents, and secret values are
    not serialized.
  - Source observation grants no filesystem mutation, connector, runtime
    dispatch, deployment mutation, terminal closure, or success-claim authority.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Protocol


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_repository_observation_evidence_packet import (  # noqa: E402
    DEFAULT_SCHEMA_PATH,
    EXPECTED_PACKET_VERSION,
    REQUIRED_ARTIFACT_REFS,
    REQUIRED_RECEIPT_REFS,
    validate_repository_observation_evidence_packet_record,
)
from scripts.validate_schemas import _load_schema  # noqa: E402


DEFAULT_OUTPUT = WORKSPACE_ROOT / ".change_assurance" / "repository_observation_evidence_packet.live.json"
DEFAULT_FRESHNESS_MINUTES = 15
COMMAND_SET_REF = "command-set://repository-observation/read-only-git-status-v1"
LIVE_COLLECTOR_REF = "collector://repository-observation/local-read-only-git-status"
LIVE_UAO_REF = "uao://repository-observation/local-read-only-git-status"
LIVE_LIFE_MEANING_REF = "life-meaning://repository-observation/local-read-only-git-status"
READ_ONLY_GIT_COMMANDS: dict[str, tuple[str, ...]] = {
    "branch": ("git", "rev-parse", "--abbrev-ref", "HEAD"),
    "git_status": ("git", "status", "--short", "--branch", "--untracked-files=all"),
    "diff": ("git", "diff", "--name-status", "--no-ext-diff", "--"),
    "file_inventory": ("git", "ls-files", "-z"),
}
FORBIDDEN_RAW_MARKERS = (
    "BEGIN PRIVATE KEY",
    "PRIVATE_KEY",
    "ACCESS_TOKEN",
    "SECRET_KEY",
    "PASSWORD=",
    "TOKEN=",
)


@dataclass(frozen=True, slots=True)
class RepositoryCommandObservation:
    """Digest-only observation of one allowlisted repository command."""

    command_name: str
    argv: tuple[str, ...]
    returncode: int
    stdout_digest_ref: str
    stderr_digest_ref: str

    @property
    def passed(self) -> bool:
        """Return whether the command completed without an exit error."""

        return self.returncode == 0


@dataclass(frozen=True, slots=True)
class RepositoryCommandResult:
    """Raw command result kept in memory only for digest calculation."""

    returncode: int
    stdout: bytes
    stderr: bytes


class RepositoryCommandRunner(Protocol):
    """Callable command runner for live git observation and tests."""

    def __call__(self, argv: tuple[str, ...], cwd: Path, timeout_seconds: int) -> RepositoryCommandResult:
        """Execute one command without a shell and return raw bytes."""


@dataclass(frozen=True, slots=True)
class RepositoryObservationProductionResult:
    """Summary of one repository observation packet production run."""

    packet_id: str
    status: str
    solver_outcome: str
    proof_state: str
    output_path: str
    validation_errors: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """Return whether packet production and validation passed."""

        return self.status == "passed" and not self.validation_errors

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready production summary."""

        return {
            "packet_id": self.packet_id,
            "status": self.status,
            "solver_outcome": self.solver_outcome,
            "proof_state": self.proof_state,
            "output_path": self.output_path,
            "validation_errors": list(self.validation_errors),
        }


def produce_repository_observation_evidence_packet(
    *,
    workspace_root: Path = WORKSPACE_ROOT,
    output_path: Path = DEFAULT_OUTPUT,
    clock: Callable[[], datetime] | None = None,
    command_runner: RepositoryCommandRunner | None = None,
    timeout_seconds: int = 10,
) -> tuple[dict[str, Any], RepositoryObservationProductionResult]:
    """Produce, validate, and persist one live repository observation packet."""

    resolved_workspace = _resolve_workspace_root(workspace_root)
    resolved_clock = clock or _utc_now
    observed_at = _coerce_utc(resolved_clock()).replace(microsecond=0)
    command_observations = _collect_command_observations(
        workspace_root=resolved_workspace,
        command_runner=command_runner or _run_subprocess,
        timeout_seconds=timeout_seconds,
    )
    packet = build_repository_observation_evidence_packet(
        workspace_root=resolved_workspace,
        observed_at=observed_at,
        command_observations=command_observations,
    )
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    validation_errors = tuple(validate_repository_observation_evidence_packet_record(packet, schema))
    if validation_errors:
        result = RepositoryObservationProductionResult(
            packet_id=str(packet.get("packet_id", "")),
            status="failed",
            solver_outcome=str(packet.get("evidence_admission", {}).get("solver_outcome", "GovernanceBlocked")),
            proof_state=str(packet.get("evidence_admission", {}).get("proof_state", "Fail")),
            output_path=_workspace_display_path(output_path, resolved_workspace),
            validation_errors=validation_errors,
        )
        return packet, result

    write_repository_observation_evidence_packet(packet, output_path, workspace_root=resolved_workspace)
    result = RepositoryObservationProductionResult(
        packet_id=str(packet["packet_id"]),
        status="passed" if packet["evidence_admission"]["proof_state"] == "Pass" else "blocked",
        solver_outcome=str(packet["evidence_admission"]["solver_outcome"]),
        proof_state=str(packet["evidence_admission"]["proof_state"]),
        output_path=_workspace_display_path(output_path, resolved_workspace),
        validation_errors=(),
    )
    return packet, result


def build_repository_observation_evidence_packet(
    *,
    workspace_root: Path,
    observed_at: datetime,
    command_observations: tuple[RepositoryCommandObservation, ...],
) -> dict[str, Any]:
    """Build a digest-only live repository observation packet."""

    _assert_complete_command_set(command_observations)
    failed_commands = tuple(command.command_name for command in command_observations if not command.passed)
    proof_state = "Pass" if not failed_commands else "Fail"
    hard_constraint_allowed = proof_state == "Pass"
    branch_observation = _observation_by_name(command_observations, "branch")
    status_observation = _observation_by_name(command_observations, "git_status")
    diff_observation = _observation_by_name(command_observations, "diff")
    inventory_observation = _observation_by_name(command_observations, "file_inventory")
    packet_material = {
        "workspace": _workspace_digest_ref(workspace_root),
        "observed_at": _format_datetime(observed_at),
        "commands": [
            {
                "name": command.command_name,
                "argv_digest_ref": _hash_json_ref(list(command.argv)),
                "returncode": command.returncode,
                "stdout_digest_ref": command.stdout_digest_ref,
                "stderr_digest_ref": command.stderr_digest_ref,
            }
            for command in command_observations
        ],
    }
    packet_id = f"repository-observation-evidence-packet-live-{_hash_json(packet_material)[:16]}"
    freshness_until = observed_at + timedelta(minutes=DEFAULT_FRESHNESS_MINUTES)
    admission_reason_refs = [
        "observation://repository/local-read-only-git-status/live",
        "policy://observation-evidence/read-only-command-allowlist",
        "policy://observation-evidence/digest-only-retention",
    ]
    if failed_commands:
        admission_reason_refs.append("policy://observation-evidence/command-failure-blocks-hard-planning")
    return {
        "packet_id": packet_id,
        "packet_version": EXPECTED_PACKET_VERSION,
        "generated_at": _format_datetime(observed_at),
        "observation_scope": {
            "repository_ref": "repo://mullu-control-plane/local-foundation",
            "worktree_ref": _workspace_digest_ref(workspace_root),
            "observation_mode": "local_read_only_git_status",
            "source_kind": "repository",
            "tenant_scope": "foundation-local-only",
            "collector_ref": LIVE_COLLECTOR_REF,
            "uao_ref": LIVE_UAO_REF,
            "life_meaning_judgment_ref": LIVE_LIFE_MEANING_REF,
        },
        "observed_state": {
            "observed_at": _format_datetime(observed_at),
            "fresh_until": _format_datetime(freshness_until),
            "freshness_state": "fresh" if hard_constraint_allowed else "stale",
            "branch_digest_ref": branch_observation.stdout_digest_ref,
            "git_status_digest_ref": status_observation.stdout_digest_ref,
            "diff_digest_ref": diff_observation.stdout_digest_ref,
            "file_inventory_digest_ref": inventory_observation.stdout_digest_ref,
            "command_set_ref": COMMAND_SET_REF,
            "contradiction_refs": [
                f"command://repository-observation/{command_name}/nonzero-exit" for command_name in failed_commands
            ],
            "recovery_actions": _recovery_actions(failed_commands),
        },
        "evidence_admission": {
            "planning_admission": "admit" if hard_constraint_allowed else "reject",
            "proof_state": proof_state,
            "solver_outcome": "SolvedVerified" if hard_constraint_allowed else "GovernanceBlocked",
            "hard_constraint_planning_allowed": hard_constraint_allowed,
            "soft_utility_planning_allowed": hard_constraint_allowed,
            "live_evidence_required": True,
            "live_evidence_state": "SolvedVerified" if hard_constraint_allowed else "AwaitingEvidence",
            "admission_reason_refs": admission_reason_refs,
        },
        "authority_boundary": {
            "live_repository_read_performed": True,
            "filesystem_write_performed": False,
            "file_content_read_performed": False,
            "secret_read_performed": False,
            "connector_call_performed": False,
            "external_write_performed": False,
            "runtime_dispatch_performed": False,
            "deployment_mutation_allowed": False,
            "terminal_closure_allowed": False,
            "success_claim_allowed": False,
        },
        "privacy_guard": {
            "raw_git_status_stored": False,
            "raw_diff_stored": False,
            "raw_file_inventory_stored": False,
            "raw_file_contents_stored": False,
            "raw_secret_value_stored": False,
            "private_payload_redacted": True,
            "operator_review_required": True,
            "retention_policy_ref": "retention://repository-observation/digest-only",
        },
        "receipt_refs": dict(REQUIRED_RECEIPT_REFS),
        "contract_summary": {
            "digest_only": True,
            "authority_denied": True,
            "hard_constraint_blocked": not hard_constraint_allowed,
            "authority_denial_count": 9,
            "privacy_guard_count": 8,
            "receipt_ref_count": len(REQUIRED_RECEIPT_REFS),
            "evidence_ref_count": len(REQUIRED_ARTIFACT_REFS),
        },
        "evidence_refs": list(REQUIRED_ARTIFACT_REFS),
    }


def write_repository_observation_evidence_packet(
    packet: dict[str, Any],
    output_path: Path,
    *,
    workspace_root: Path = WORKSPACE_ROOT,
) -> Path:
    """Persist one packet to a workspace-local JSON file."""

    resolved_workspace = _resolve_workspace_root(workspace_root)
    resolved_output = output_path if output_path.is_absolute() else resolved_workspace / output_path
    resolved_output = resolved_output.resolve(strict=False)
    if not _is_relative_to(resolved_output, resolved_workspace):
        raise ValueError("repository observation packet output must stay within workspace_root")
    serialized = json.dumps(packet, indent=2, sort_keys=True) + "\n"
    _assert_no_forbidden_raw_markers(serialized)
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(serialized, encoding="utf-8")
    return resolved_output


def is_allowed_repository_observation_command(argv: tuple[str, ...]) -> bool:
    """Return whether argv exactly matches the fixed read-only command set."""

    return argv in READ_ONLY_GIT_COMMANDS.values()


def _collect_command_observations(
    *,
    workspace_root: Path,
    command_runner: RepositoryCommandRunner,
    timeout_seconds: int,
) -> tuple[RepositoryCommandObservation, ...]:
    observations: list[RepositoryCommandObservation] = []
    for command_name, argv in READ_ONLY_GIT_COMMANDS.items():
        if not is_allowed_repository_observation_command(argv):
            raise ValueError(f"repository observation command is not allowlisted: {command_name}")
        result = command_runner(argv, workspace_root, timeout_seconds)
        observations.append(
            RepositoryCommandObservation(
                command_name=command_name,
                argv=argv,
                returncode=int(result.returncode),
                stdout_digest_ref=_hash_bytes_ref(result.stdout),
                stderr_digest_ref=_hash_bytes_ref(result.stderr),
            )
        )
    return tuple(observations)


def _run_subprocess(argv: tuple[str, ...], cwd: Path, timeout_seconds: int) -> RepositoryCommandResult:
    if not is_allowed_repository_observation_command(argv):
        raise ValueError("refusing non-allowlisted repository observation command")
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            check=False,
            shell=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return RepositoryCommandResult(
            returncode=124,
            stdout=exc.stdout or b"",
            stderr=b"repository observation command timed out",
        )
    except OSError:
        return RepositoryCommandResult(
            returncode=127,
            stdout=b"",
            stderr=b"repository observation command unavailable",
        )
    return RepositoryCommandResult(
        returncode=int(completed.returncode),
        stdout=completed.stdout if isinstance(completed.stdout, bytes) else str(completed.stdout).encode("utf-8"),
        stderr=completed.stderr if isinstance(completed.stderr, bytes) else str(completed.stderr).encode("utf-8"),
    )


def _assert_complete_command_set(observations: tuple[RepositoryCommandObservation, ...]) -> None:
    observed_names = {observation.command_name for observation in observations}
    expected_names = set(READ_ONLY_GIT_COMMANDS)
    if observed_names != expected_names:
        raise ValueError(f"repository observation command set drift: expected={sorted(expected_names)} observed={sorted(observed_names)}")
    for observation in observations:
        if READ_ONLY_GIT_COMMANDS[observation.command_name] != observation.argv:
            raise ValueError(f"repository observation argv drift: {observation.command_name}")


def _observation_by_name(
    observations: tuple[RepositoryCommandObservation, ...],
    command_name: str,
) -> RepositoryCommandObservation:
    for observation in observations:
        if observation.command_name == command_name:
            return observation
    raise ValueError(f"missing repository observation command: {command_name}")


def _recovery_actions(failed_commands: tuple[str, ...]) -> list[str]:
    if not failed_commands:
        return ["rerun read-only repository observation when planning evidence becomes stale"]
    return [
        "inspect local git availability and repository root before retrying read-only observation",
        "rerun read-only repository observation after command failures are resolved",
    ]


def _resolve_workspace_root(workspace_root: Path) -> Path:
    resolved = workspace_root.resolve(strict=True)
    if not resolved.is_dir():
        raise NotADirectoryError(f"workspace_root is not a directory: {resolved}")
    if not (resolved / ".git").exists():
        raise ValueError(f"workspace_root is not a git worktree: {resolved}")
    return resolved


def _workspace_digest_ref(path: Path) -> str:
    return _hash_text_ref(str(path.resolve(strict=False)))


def _workspace_display_path(path: Path, workspace_root: Path) -> str:
    resolved_path = path if path.is_absolute() else workspace_root / path
    try:
        return resolved_path.resolve(strict=False).relative_to(workspace_root).as_posix()
    except ValueError:
        return path.name


def _hash_bytes_ref(value: bytes) -> str:
    return f"hash://sha256/{hashlib.sha256(value).hexdigest()}"


def _hash_text_ref(value: str) -> str:
    return _hash_bytes_ref(value.encode("utf-8", errors="replace"))


def _hash_json_ref(value: Any) -> str:
    return _hash_bytes_ref(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _hash_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _assert_no_forbidden_raw_markers(serialized: str) -> None:
    upper_serialized = serialized.upper()
    for marker in FORBIDDEN_RAW_MARKERS:
        if marker in upper_serialized:
            raise ValueError(f"repository observation packet contains forbidden raw marker: {marker}")


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _format_datetime(value: datetime) -> str:
    return _coerce_utc(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse repository observation producer arguments."""

    parser = argparse.ArgumentParser(description="Produce a live read-only repository observation evidence packet.")
    parser.add_argument("--workspace-root", default=str(WORKSPACE_ROOT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--timeout-seconds", type=int, default=10)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable production summary")
    parser.add_argument("--strict", action="store_true", help="exit non-zero when live observation is blocked")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for live read-only repository observation production."""

    args = parse_args(argv)
    try:
        _packet, result = produce_repository_observation_evidence_packet(
            workspace_root=Path(args.workspace_root),
            output_path=Path(args.output),
            timeout_seconds=max(1, int(args.timeout_seconds)),
        )
    except (OSError, ValueError) as exc:
        result = RepositoryObservationProductionResult(
            packet_id="",
            status="failed",
            solver_outcome="GovernanceBlocked",
            proof_state="Fail",
            output_path=_workspace_display_path(Path(args.output), Path(args.workspace_root).resolve(strict=False)),
            validation_errors=(str(exc),),
        )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.passed:
        print(f"REPOSITORY OBSERVATION EVIDENCE PACKET PASSED packet_id={result.packet_id}")
    else:
        print(f"REPOSITORY OBSERVATION EVIDENCE PACKET BLOCKED errors={list(result.validation_errors)}")
    return 0 if result.passed or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
