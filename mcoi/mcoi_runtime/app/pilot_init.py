"""Purpose: one-command pilot bring-up artifact scaffolding.

Governance scope: local pilot bootstrap files only; no network calls, no live
tenant mutation, and no provider credentials.
Dependencies: runtime invariant helpers and standard JSON serialization.
Invariants: generated artifacts are deterministic for identical inputs; existing
files are not overwritten unless explicitly forced; every pilot has tenant,
policy, budget, dashboard, audit, and lineage examples.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from threading import RLock
import tempfile
from typing import Any

from mcoi_runtime.core.invariants import ensure_non_empty_text, stable_identifier


PILOT_FILE_NAMES = (
    "pilot.manifest.json",
    "tenant.json",
    "policy.json",
    "budget.json",
    "dashboard.json",
    "audit_queries.json",
    "lineage_examples.json",
    "README.md",
)


@dataclass(frozen=True, slots=True)
class PilotInitRequest:
    """Input contract for pilot scaffold generation."""

    tenant_id: str
    pilot_name: str
    output_dir: Path
    policy_pack_id: str = "default-safe"
    policy_version: str = "v0.1"
    max_cost: float = 100.0
    max_calls: int = 1000
    dashboard_url: str = "https://dashboard.mullusi.com"
    sandbox_url: str = "https://sandbox.mullusi.com"
    force: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", ensure_non_empty_text("tenant_id", self.tenant_id))
        object.__setattr__(self, "pilot_name", ensure_non_empty_text("pilot_name", self.pilot_name))
        object.__setattr__(self, "policy_pack_id", ensure_non_empty_text("policy_pack_id", self.policy_pack_id))
        object.__setattr__(self, "policy_version", ensure_non_empty_text("policy_version", self.policy_version))
        object.__setattr__(self, "dashboard_url", ensure_non_empty_text("dashboard_url", self.dashboard_url))
        object.__setattr__(self, "sandbox_url", ensure_non_empty_text("sandbox_url", self.sandbox_url))
        if self.max_cost < 0:
            raise ValueError("max_cost must be non-negative")
        if self.max_calls < 1:
            raise ValueError("max_calls must be at least 1")


@dataclass(frozen=True, slots=True)
class PilotInitResult:
    """Result contract for pilot scaffold generation."""

    pilot_id: str
    output_dir: Path
    files_written: tuple[Path, ...]
    manifest_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "pilot_id": self.pilot_id,
            "output_dir": str(self.output_dir),
            "files_written": [str(path) for path in self.files_written],
            "manifest_path": str(self.manifest_path),
            "governed": True,
        }


@dataclass(frozen=True, slots=True)
class PilotScaffoldBundle:
    """Provisionable pilot scaffold payload without filesystem side effects."""

    pilot_id: str
    artifacts: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "pilot_id": self.pilot_id,
            "artifacts": self.artifacts,
            "artifact_names": tuple(self.artifacts),
            "governed": True,
        }


@dataclass(frozen=True, slots=True)
class PilotProvisionRecord:
    """Accepted hosted pilot provisioning record."""

    pilot_id: str
    tenant_id: str
    pilot_name: str
    policy_pack_id: str
    policy_version: str
    artifact_names: tuple[str, ...]
    artifact_count: int
    accepted_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "pilot_id": self.pilot_id,
            "tenant_id": self.tenant_id,
            "pilot_name": self.pilot_name,
            "policy_pack_id": self.policy_pack_id,
            "policy_version": self.policy_version,
            "artifact_names": list(self.artifact_names),
            "artifact_count": self.artifact_count,
            "accepted_at": self.accepted_at,
            "governed": True,
        }


class PilotProvisionRegistry:
    """Bounded in-memory read model of accepted hosted pilot provisions."""

    def __init__(self, *, max_records: int = 500) -> None:
        if max_records < 1:
            raise ValueError("max_records must be at least 1")
        self._max_records = max_records
        self._records: dict[str, PilotProvisionRecord] = {}
        self._order: list[str] = []
        self._lock = RLock()

    def accept(
        self,
        *,
        request: PilotInitRequest,
        bundle: PilotScaffoldBundle,
        accepted_at: str | None = None,
    ) -> PilotProvisionRecord:
        """Persist one accepted hosted provision in the bounded read model."""
        timestamp = accepted_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
        record = PilotProvisionRecord(
            pilot_id=bundle.pilot_id,
            tenant_id=request.tenant_id,
            pilot_name=request.pilot_name,
            policy_pack_id=request.policy_pack_id,
            policy_version=request.policy_version,
            artifact_names=tuple(bundle.artifacts),
            artifact_count=len(bundle.artifacts),
            accepted_at=timestamp,
        )
        with self._lock:
            self._store_record(record)
            self._after_records_changed()
        return record

    def _store_record(self, record: PilotProvisionRecord) -> None:
        """Store one already validated provision record in insertion order."""
        if record.pilot_id not in self._records:
            self._order.append(record.pilot_id)
        self._records[record.pilot_id] = record
        while len(self._order) > self._max_records:
            oldest = self._order.pop(0)
            self._records.pop(oldest, None)

    def _after_records_changed(self) -> None:
        """Mutation hook for persistent registry variants."""

    def get(self, pilot_id: str) -> PilotProvisionRecord | None:
        """Fetch one accepted pilot provision by pilot id."""
        with self._lock:
            return self._records.get(pilot_id)

    def list_records(
        self,
        *,
        tenant_id: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[PilotProvisionRecord, ...]:
        """List accepted provisions newest-first with bounded paging."""
        bounded_limit = min(max(limit, 1), 100)
        bounded_offset = max(offset, 0)
        with self._lock:
            records = [
                self._records[pilot_id]
                for pilot_id in reversed(self._order)
                if pilot_id in self._records and (not tenant_id or self._records[pilot_id].tenant_id == tenant_id)
            ]
        return tuple(records[bounded_offset : bounded_offset + bounded_limit])

    def count(self, *, tenant_id: str = "") -> int:
        """Count accepted provision records, optionally scoped to a tenant."""
        with self._lock:
            if not tenant_id:
                return len(self._records)
            return sum(1 for record in self._records.values() if record.tenant_id == tenant_id)


class FilePilotProvisionRegistry(PilotProvisionRegistry):
    """JSON-file backed pilot provision registry.

    The store rewrites one deterministic JSON document after each accepted
    provision. Startup loads fail closed when the payload is malformed,
    duplicates pilot ids, or carries an artifact-count mismatch.
    """

    def __init__(self, path: Path, *, max_records: int = 500) -> None:
        if not isinstance(path, Path):
            raise ValueError("path must be a Path instance")
        self._path = path
        super().__init__(max_records=max_records)
        self._load_if_present()

    def _after_records_changed(self) -> None:
        self._persist()

    def _persist(self) -> None:
        payload = {
            "schema_version": 1,
            "max_records": self._max_records,
            "records": [
                _record_to_json(self._records[pilot_id])
                for pilot_id in self._order
                if pilot_id in self._records
            ],
        }
        _atomic_write(self._path, _deterministic_json(payload))

    def _load_if_present(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            raise ValueError(_bounded_registry_error("malformed pilot provision registry file", exc)) from exc
        if not isinstance(raw, dict):
            raise ValueError("pilot provision registry payload must be an object")
        if raw.get("schema_version") != 1:
            raise ValueError("pilot provision registry schema version unsupported")
        records_raw = raw.get("records")
        if not isinstance(records_raw, list):
            raise ValueError("pilot provision registry records must be a list")
        with self._lock:
            for item in records_raw:
                record = _record_from_json(item)
                if record.pilot_id in self._records:
                    raise ValueError("duplicate pilot provision record in registry file")
                self._store_record(record)


def _record_to_json(record: PilotProvisionRecord) -> dict[str, Any]:
    return {
        "pilot_id": record.pilot_id,
        "tenant_id": record.tenant_id,
        "pilot_name": record.pilot_name,
        "policy_pack_id": record.policy_pack_id,
        "policy_version": record.policy_version,
        "artifact_names": list(record.artifact_names),
        "artifact_count": record.artifact_count,
        "accepted_at": record.accepted_at,
    }


def _record_from_json(raw: Any) -> PilotProvisionRecord:
    if not isinstance(raw, dict):
        raise ValueError("pilot provision record payload must be an object")
    try:
        artifact_names_raw = raw["artifact_names"]
        if not isinstance(artifact_names_raw, list):
            raise ValueError("pilot provision artifact_names must be a list")
        artifact_names = tuple(
            ensure_non_empty_text("artifact_name", artifact_name)
            for artifact_name in artifact_names_raw
        )
        artifact_count = raw["artifact_count"]
        if not isinstance(artifact_count, int):
            raise ValueError("pilot provision artifact_count must be an integer")
        record = PilotProvisionRecord(
            pilot_id=ensure_non_empty_text("pilot_id", raw["pilot_id"]),
            tenant_id=ensure_non_empty_text("tenant_id", raw["tenant_id"]),
            pilot_name=ensure_non_empty_text("pilot_name", raw["pilot_name"]),
            policy_pack_id=ensure_non_empty_text("policy_pack_id", raw["policy_pack_id"]),
            policy_version=ensure_non_empty_text("policy_version", raw["policy_version"]),
            artifact_names=artifact_names,
            artifact_count=artifact_count,
            accepted_at=ensure_non_empty_text("accepted_at", raw["accepted_at"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(_bounded_registry_error("invalid pilot provision record payload", exc)) from exc
    if record.artifact_count != len(record.artifact_names):
        raise ValueError("pilot provision artifact count mismatch")
    return record


def _deterministic_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def _bounded_registry_error(summary: str, exc: BaseException) -> str:
    return f"{summary} ({type(exc).__name__})"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            fd = -1
            os.replace(tmp_path, str(path))
        except BaseException:
            if fd >= 0:
                os.close(fd)
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    except OSError as exc:
        raise ValueError(_bounded_registry_error("pilot provision registry persistence failed", exc)) from exc


def initialize_pilot(request: PilotInitRequest) -> PilotInitResult:
    """Create a complete local pilot scaffold."""
    bundle = build_pilot_scaffold(request)
    pilot_id = bundle.pilot_id
    payloads = bundle.artifacts
    output_dir = request.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    target_paths = tuple(output_dir / file_name for file_name in PILOT_FILE_NAMES)
    existing = tuple(path for path in target_paths if path.exists())
    if existing and not request.force:
        raise FileExistsError("pilot scaffold target contains existing files")

    written: list[Path] = []
    for file_name, payload in payloads.items():
        path = output_dir / file_name
        if file_name.endswith(".md"):
            path.write_text(str(payload), encoding="utf-8")
        else:
            path.write_text(_stable_json(payload), encoding="utf-8")
        written.append(path)

    return PilotInitResult(
        pilot_id=pilot_id,
        output_dir=output_dir,
        files_written=tuple(written),
        manifest_path=output_dir / "pilot.manifest.json",
    )


def build_pilot_scaffold(request: PilotInitRequest) -> PilotScaffoldBundle:
    """Build deterministic pilot artifacts without writing to disk."""
    pilot_id = stable_identifier(
        "pilot",
        {
            "tenant_id": request.tenant_id,
            "pilot_name": request.pilot_name,
            "policy_pack_id": request.policy_pack_id,
            "policy_version": request.policy_version,
        },
    )
    return PilotScaffoldBundle(
        pilot_id=pilot_id,
        artifacts=_pilot_payloads(request, pilot_id),
    )


def _pilot_payloads(request: PilotInitRequest, pilot_id: str) -> dict[str, Any]:
    budget_id = f"{request.tenant_id}-pilot-budget"
    manifest = {
        "pilot_id": pilot_id,
        "tenant_id": request.tenant_id,
        "pilot_name": request.pilot_name,
        "artifacts": list(PILOT_FILE_NAMES),
        "entrypoints": {
            "api": "https://api.mullusi.com",
            "docs": "https://docs.mullusi.com",
            "dashboard": request.dashboard_url,
            "sandbox": request.sandbox_url,
        },
        "governance": {
            "policy_pack_id": request.policy_pack_id,
            "policy_version": request.policy_version,
            "budget_id": budget_id,
            "lineage_enabled": True,
            "audit_required": True,
        },
    }
    return {
        "pilot.manifest.json": manifest,
        "tenant.json": {
            "tenant_id": request.tenant_id,
            "display_name": request.pilot_name,
            "environment": "pilot",
            "status": "scaffolded",
        },
        "policy.json": {
            "policy_pack_id": request.policy_pack_id,
            "policy_version": request.policy_version,
            "mode": "enforced",
            "shadow_policy": {
                "enabled": True,
                "candidate_version": f"{request.policy_version}-shadow",
            },
        },
        "budget.json": {
            "tenant_id": request.tenant_id,
            "budget_id": budget_id,
            "max_cost": request.max_cost,
            "max_calls": request.max_calls,
            "streaming_enforcement": "predictive_debit",
        },
        "dashboard.json": {
            "dashboard_url": request.dashboard_url,
            "sandbox_url": request.sandbox_url,
            "views": ["budget", "policy_decisions", "audit_trail", "lineage", "proof_coverage"],
        },
        "audit_queries.json": {
            "queries": [
                {
                    "name": "recent_policy_decisions",
                    "path": f"/api/v1/audit?tenant_id={request.tenant_id}&action=policy.decision&limit=25",
                },
                {
                    "name": "budget_events",
                    "path": f"/api/v1/audit?tenant_id={request.tenant_id}&action=budget.debit&limit=25",
                },
                {
                    "name": "tool_invocations",
                    "path": f"/api/v1/audit?tenant_id={request.tenant_id}&action=tool.invoke&limit=25",
                },
            ]
        },
        "lineage_examples.json": {
            "examples": [
                "lineage://trace/{trace_id}?depth=25&verify=true",
                "lineage://output/{output_id}?include=policy,model,tenant,budget,replay",
                "lineage://command/{command_id}?include=policy,tool",
            ]
        },
        "README.md": _readme(request=request, pilot_id=pilot_id),
    }


def _readme(*, request: PilotInitRequest, pilot_id: str) -> str:
    return (
        f"# {request.pilot_name} Pilot\n\n"
        f"Pilot ID: `{pilot_id}`\n\n"
        "## Bring-Up\n\n"
        "1. Review `tenant.json`, `policy.json`, and `budget.json`.\n"
        "2. Start the local governed API service.\n"
        "3. Use `audit_queries.json` to verify policy, budget, and tool-call events.\n"
        "4. Use `lineage_examples.json` to inspect causal proof paths.\n\n"
        "## Invariants\n\n"
        "- Tenant, policy, and budget are explicit.\n"
        "- Audit is required for pilot execution.\n"
        "- Lineage examples are present before the pilot demo.\n"
        "- Generated files are deterministic for the same pilot inputs.\n"
    )


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, separators=(",", ": ")) + "\n"
