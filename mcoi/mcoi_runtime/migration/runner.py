"""
Bulk proof migration runner — v1 → v2.

Reads JSON proof records in the v1 format, synthesizes the v2 fields
(construct_id, tier, mfidel_sig, cascade_chain, tension_snap, phi_level,
schema_ver), recomputes the v2 hash chain, and writes v2 records to a
target directory. v1 records are NOT deleted; they are marked
``migrated_to: <v2_uuid>`` in a sidecar manifest.

Reference: ``mcoi/mcoi_runtime/migration/PROOF_V1_TO_V2.md`` §3.2 — bulk
migration tool semantics. Mapping table: ``v1_to_v2_mapping.py``.

This runner is what fulfills the "bulk migration tool binary" line item
the v4.0.0 release notes promised but did not yet deliver.

CLI entry point: ``mcoi migrate-proofs`` (see [project.scripts] in
pyproject.toml). Programmatic use: ``MigrationRunner(...).run()``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

from mcoi_runtime.migration.v1_to_v2_mapping import map_action_to_construct


_log = logging.getLogger(__name__)


V1_SCHEMA_VERSION_IMPLICIT = "1"
V2_SCHEMA_VERSION = "2"
V2_GENESIS_MARKER = "v2_genesis"


# ---- Dataclasses ----


@dataclass(frozen=True)
class V1Proof:
    """Minimal v1 proof shape. Extra fields are preserved verbatim."""

    proof_id: str
    tenant_id: str
    action: str
    timestamp: str
    verdict: str  # "pass" | "fail"
    reason: str = ""
    prev_hash: str = ""
    proof_hash: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class V2Proof:
    """v2 proof shape per PROOF_V1_TO_V2.md §1."""

    proof_id: str
    tenant_id: str
    action: str
    timestamp: str
    proof_state: str  # "Pass" | "Fail" | "Unknown" | "BudgetUnknown"
    reason: str
    prev_hash: str
    proof_hash: str
    construct_id: str
    tier: int
    mfidel_sig: list[list[int]]  # empty for legacy
    cascade_chain: list[str]  # empty for legacy
    tension_snap: float | None
    phi_level: int
    schema_ver: str
    lineage_parent_ids: list[str]


@dataclass
class MigrationStats:
    examined: int = 0
    migrated: int = 0
    skipped_already_migrated: int = 0
    failed: int = 0
    halted_chain_break: bool = False


# ---- v1 → v2 transformation ----


def _v1_pass_to_v2_state(v1_verdict: str, v1_reason: str) -> tuple[str, str]:
    """Map v1 verdict + reason → v2 ProofState + reason.

    v1 had only pass/fail. v2 has Pass/Fail/Unknown/BudgetUnknown.
    The migration is conservative: pass → Pass; fail → Fail with
    reason (synthesized if v1 had no reason).
    """
    if v1_verdict == "pass":
        return "Pass", v1_reason
    if v1_verdict == "fail":
        reason = v1_reason or "v1_migration_no_reason"
        return "Fail", reason
    raise ValueError(f"unrecognized v1 verdict: {v1_verdict!r}")


def _compute_v2_hash(
    proof_id: str,
    tenant_id: str,
    action: str,
    timestamp: str,
    proof_state: str,
    reason: str,
    prev_hash: str,
    construct_id: str,
    tier: int,
    schema_ver: str,
) -> str:
    """SHA-256 over a canonical v2 payload. Same algorithm any v1 reader
    expects (canonical JSON of the fields it knows about) extended with
    the new v2 fields. Field order is fixed for reproducibility."""
    canonical = json.dumps(
        {
            "proof_id": proof_id,
            "tenant_id": tenant_id,
            "action": action,
            "timestamp": timestamp,
            "proof_state": proof_state,
            "reason": reason,
            "prev_hash": prev_hash,
            "construct_id": construct_id,
            "tier": tier,
            "schema_ver": schema_ver,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def transform_v1_to_v2(
    v1: V1Proof,
    *,
    chain_prev_hash: str,
) -> V2Proof:
    """Transform one v1 proof to v2.

    `chain_prev_hash` is the prev_hash to record. For the first record in
    a tenant's v2 chain, the spec recommends
    ``H(last_v1_proof_hash || "v2_genesis")``; the runner is responsible
    for computing that and supplying it here.
    """
    proof_state, reason = _v1_pass_to_v2_state(v1.verdict, v1.reason)
    construct_type, tier = map_action_to_construct(v1.action)

    # Synthesized v2 fields per migration spec §3.2
    construct_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"v1:{v1.proof_id}"))

    proof_hash = _compute_v2_hash(
        proof_id=v1.proof_id,
        tenant_id=v1.tenant_id,
        action=v1.action,
        timestamp=v1.timestamp,
        proof_state=proof_state,
        reason=reason,
        prev_hash=chain_prev_hash,
        construct_id=construct_id,
        tier=tier,
        schema_ver=V2_SCHEMA_VERSION,
    )

    return V2Proof(
        proof_id=v1.proof_id,
        tenant_id=v1.tenant_id,
        action=v1.action,
        timestamp=v1.timestamp,
        proof_state=proof_state,
        reason=reason,
        prev_hash=chain_prev_hash,
        proof_hash=proof_hash,
        construct_id=construct_id,
        tier=tier,
        mfidel_sig=[],
        cascade_chain=[],
        tension_snap=None,
        phi_level=3,
        schema_ver=V2_SCHEMA_VERSION,
        lineage_parent_ids=[v1.proof_id],
    )


# ---- I/O helpers ----


def _atomic_write_json(target: Path, payload: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=target.name + ".",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def _read_v1_proof(path: Path) -> V1Proof:
    payload = json.loads(path.read_text(encoding="utf-8"))
    known = {"proof_id", "tenant_id", "action", "timestamp", "verdict",
             "reason", "prev_hash", "proof_hash"}
    extra = {k: v for k, v in payload.items() if k not in known}
    return V1Proof(
        proof_id=payload["proof_id"],
        tenant_id=payload["tenant_id"],
        action=payload["action"],
        timestamp=payload["timestamp"],
        verdict=payload["verdict"],
        reason=payload.get("reason", ""),
        prev_hash=payload.get("prev_hash", ""),
        proof_hash=payload.get("proof_hash", ""),
        extra=extra,
    )


def _v2_proof_to_dict(v2: V2Proof) -> dict[str, Any]:
    return {
        "proof_id":      v2.proof_id,
        "tenant_id":     v2.tenant_id,
        "action":        v2.action,
        "timestamp":     v2.timestamp,
        "proof_state":   v2.proof_state,
        "reason":        v2.reason,
        "prev_hash":     v2.prev_hash,
        "proof_hash":    v2.proof_hash,
        "construct_id":  v2.construct_id,
        "tier":          v2.tier,
        "mfidel_sig":    v2.mfidel_sig,
        "cascade_chain": v2.cascade_chain,
        "tension_snap":  v2.tension_snap,
        "phi_level":     v2.phi_level,
        "schema_ver":    v2.schema_ver,
        "lineage": {
            "parent_ids": v2.lineage_parent_ids,
        },
    }


# ---- Hash-chain integrity ----


class HashChainBroken(Exception):
    """Raised when a v1 record's prev_hash does not match the previous record."""


def _verify_v1_chain(proofs: list[V1Proof]) -> None:
    """Verify the v1 chain is self-consistent before migration begins.

    Per spec §3.2 step 2: halt batch on first chain break.

    Note: this does NOT verify the v1 hash content (we don't know which
    fields v1 hashed). It verifies the prev_hash linkage: each record's
    prev_hash equals the previous record's proof_hash (or empty for the
    first).
    """
    expected_prev = ""
    for i, p in enumerate(proofs):
        if p.prev_hash != expected_prev:
            raise HashChainBroken(
                f"v1 chain break at record {i} (proof_id={p.proof_id}): "
                f"prev_hash={p.prev_hash!r} expected={expected_prev!r}"
            )
        expected_prev = p.proof_hash


# ---- Migration runner ----


@dataclass
class MigrationRunner:
    """Migrate a directory of v1 proofs to v2.

    Layout assumption (configurable):

      v1_dir/<tenant_id>/<proof_id>.json    # v1 proofs
      v2_dir/<tenant_id>/<proof_id>.json    # v2 proofs (output)
      manifest_dir/<tenant_id>.json         # one manifest per tenant

    Per-tenant chain isolation: each tenant has its own chain. Migration
    halts that tenant's batch on the first chain break and records the
    break in stats; other tenants continue.
    """

    v1_dir: Path
    v2_dir: Path
    manifest_dir: Path
    dry_run: bool = False
    tenant_filter: str | None = None  # if set, only migrate this tenant

    def _tenant_dirs(self) -> list[str]:
        if not self.v1_dir.exists():
            return []
        return sorted(p.name for p in self.v1_dir.iterdir() if p.is_dir())

    def _v1_proofs_for_tenant(self, tenant_id: str) -> list[V1Proof]:
        tenant_dir = self.v1_dir / tenant_id
        if not tenant_dir.exists():
            return []
        # Sort by filename to get deterministic ordering. Production v1
        # deployments encoded ordering in the filename or in the timestamp;
        # we use lexicographic sort which works for both UUIDv7-style names
        # and ISO-8601 timestamps.
        proofs: list[V1Proof] = []
        for p in sorted(tenant_dir.glob("*.json")):
            try:
                proofs.append(_read_v1_proof(p))
            except (OSError, KeyError, json.JSONDecodeError) as e:
                _log.warning(
                    "skipping unreadable v1 proof %s: %s", p, e
                )
        return proofs

    def _load_manifest(self, tenant_id: str) -> dict[str, Any]:
        path = self.manifest_dir / f"{tenant_id}.json"
        if not path.exists():
            return {
                "tenant_id": tenant_id,
                "migrated": {},  # v1_proof_id -> v2_proof_id
                "last_v1_hash": "",
                "last_v2_hash": "",
                "completed_at": None,
            }
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_manifest(self, tenant_id: str, manifest: dict[str, Any]) -> None:
        if self.dry_run:
            return
        _atomic_write_json(
            self.manifest_dir / f"{tenant_id}.json",
            manifest,
        )

    def _migrate_tenant(self, tenant_id: str) -> MigrationStats:
        stats = MigrationStats()
        proofs = self._v1_proofs_for_tenant(tenant_id)
        if not proofs:
            return stats

        try:
            _verify_v1_chain(proofs)
        except HashChainBroken as e:
            _log.error("tenant %s: %s", tenant_id, e)
            stats.halted_chain_break = True
            stats.examined = len(proofs)
            return stats

        manifest = self._load_manifest(tenant_id)
        already_migrated = manifest.get("migrated", {})

        # Genesis prev_hash for v2 chain per spec §3.3:
        # H(last_v1_proof_hash || "v2_genesis")
        if proofs and not manifest.get("last_v1_hash"):
            last_v1_hash = proofs[-1].proof_hash
            genesis_input = f"{last_v1_hash}{V2_GENESIS_MARKER}".encode("utf-8")
            chain_prev = hashlib.sha256(genesis_input).hexdigest()
            manifest["last_v1_hash"] = last_v1_hash
        else:
            chain_prev = manifest.get("last_v2_hash", "")

        for v1 in proofs:
            stats.examined += 1
            if v1.proof_id in already_migrated:
                stats.skipped_already_migrated += 1
                continue
            try:
                v2 = transform_v1_to_v2(v1, chain_prev_hash=chain_prev)
            except Exception as e:
                _log.error(
                    "tenant %s proof %s: transform failed: %s",
                    tenant_id, v1.proof_id, e,
                )
                stats.failed += 1
                continue

            if not self.dry_run:
                target = self.v2_dir / tenant_id / f"{v1.proof_id}.json"
                _atomic_write_json(target, _v2_proof_to_dict(v2))

            already_migrated[v1.proof_id] = v2.proof_id
            chain_prev = v2.proof_hash
            stats.migrated += 1

        manifest["migrated"] = already_migrated
        manifest["last_v2_hash"] = chain_prev
        manifest["completed_at"] = time.time()
        self._save_manifest(tenant_id, manifest)
        return stats

    def run(self) -> dict[str, MigrationStats]:
        """Run migration for all (or one filtered) tenant. Returns per-tenant stats."""
        out: dict[str, MigrationStats] = {}
        tenants = self._tenant_dirs()
        if self.tenant_filter:
            tenants = [t for t in tenants if t == self.tenant_filter]
        for tenant_id in tenants:
            out[tenant_id] = self._migrate_tenant(tenant_id)
        return out


# ---- CLI ----


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mcoi migrate-proofs",
        description="Migrate v1 proof records to v2 format. Halts a tenant's "
                    "batch on chain break; other tenants continue.",
    )
    p.add_argument("--v1-dir", required=True, help="directory of v1 proofs (per-tenant subdirs)")
    p.add_argument("--v2-dir", required=True, help="output directory for v2 proofs")
    p.add_argument("--manifest-dir", required=True, help="directory for per-tenant migration manifests")
    p.add_argument("--tenant", default=None, help="if set, migrate only this tenant")
    p.add_argument("--dry-run", action="store_true", help="examine + transform but do not write")
    p.add_argument("--from", dest="from_version", default="v1", help="source schema version (default: v1)")
    p.add_argument("--to", dest="to_version", default="v2", help="target schema version (default: v2)")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.from_version != "v1" or args.to_version != "v2":
        print(
            f"only --from v1 --to v2 supported in this build "
            f"(asked for --from {args.from_version} --to {args.to_version})",
            file=sys.stderr,
        )
        return 2

    runner = MigrationRunner(
        v1_dir=Path(args.v1_dir),
        v2_dir=Path(args.v2_dir),
        manifest_dir=Path(args.manifest_dir),
        dry_run=args.dry_run,
        tenant_filter=args.tenant,
    )
    results = runner.run()
    if not results:
        print("no tenants found")
        return 0

    chain_breaks = sum(1 for s in results.values() if s.halted_chain_break)
    failed_total = sum(s.failed for s in results.values())
    migrated_total = sum(s.migrated for s in results.values())

    print(f"migration {'(dry-run) ' if args.dry_run else ''}complete:")
    for tenant_id, s in sorted(results.items()):
        marker = " [CHAIN-BREAK]" if s.halted_chain_break else ""
        print(
            f"  {tenant_id}: examined={s.examined} migrated={s.migrated} "
            f"skipped={s.skipped_already_migrated} failed={s.failed}{marker}"
        )
    print(
        f"totals: migrated={migrated_total} failed={failed_total} "
        f"chain_breaks={chain_breaks}"
    )

    return 1 if (chain_breaks or failed_total) else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
