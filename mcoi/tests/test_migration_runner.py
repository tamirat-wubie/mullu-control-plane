"""Bulk proof migration runner — v1 → v2.

Verifies the contract from PROOF_V1_TO_V2.md:
  - idempotency
  - hash chain integrity (halt on first break)
  - cross-link integrity (lineage.parent_ids)
  - dry-run produces no side effects
  - tenant isolation
  - pass/fail mapping
  - synthesized fields per spec
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Iterable

import pytest

from mcoi_runtime.migration.runner import (
    HashChainBroken,
    MigrationRunner,
    V2_GENESIS_MARKER,
    V2_SCHEMA_VERSION,
    _verify_v1_chain,
    transform_v1_to_v2,
    V1Proof,
)


# ---- Helpers ----


def _v1_hash(p: V1Proof) -> str:
    """Compute a deterministic v1-style hash for synthetic test data.

    The actual production v1 hash algorithm isn't specified in the runner —
    the runner only verifies prev_hash linkage. So tests can use any
    deterministic hash; the chain still has to be self-consistent.
    """
    payload = json.dumps(
        {
            "proof_id": p.proof_id,
            "tenant_id": p.tenant_id,
            "action": p.action,
            "timestamp": p.timestamp,
            "verdict": p.verdict,
            "reason": p.reason,
            "prev_hash": p.prev_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _make_chain(
    tenant_id: str,
    actions_and_verdicts: Iterable[tuple[str, str]],
) -> list[V1Proof]:
    """Build a self-consistent v1 chain."""
    out: list[V1Proof] = []
    prev_hash = ""
    for i, (action, verdict) in enumerate(actions_and_verdicts):
        p = V1Proof(
            proof_id=f"{tenant_id}-{i:04d}",
            tenant_id=tenant_id,
            action=action,
            timestamp=f"2026-04-26T{i:02d}:00:00Z",
            verdict=verdict,
            reason=f"reason-{i}" if verdict == "fail" else "",
            prev_hash=prev_hash,
            proof_hash="",
        )
        # Compute the proof_hash on a copy with empty proof_hash
        h = _v1_hash(p)
        p = V1Proof(
            proof_id=p.proof_id,
            tenant_id=p.tenant_id,
            action=p.action,
            timestamp=p.timestamp,
            verdict=p.verdict,
            reason=p.reason,
            prev_hash=p.prev_hash,
            proof_hash=h,
        )
        out.append(p)
        prev_hash = h
    return out


def _write_v1_chain(v1_dir: Path, proofs: list[V1Proof]) -> None:
    """Write a chain to disk under v1_dir/<tenant>/<proof_id>.json."""
    for p in proofs:
        target = v1_dir / p.tenant_id / f"{p.proof_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "proof_id": p.proof_id,
                    "tenant_id": p.tenant_id,
                    "action": p.action,
                    "timestamp": p.timestamp,
                    "verdict": p.verdict,
                    "reason": p.reason,
                    "prev_hash": p.prev_hash,
                    "proof_hash": p.proof_hash,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )


# ---- Unit tests ----


def test_transform_pass_to_pass():
    v1 = V1Proof(
        proof_id="p1",
        tenant_id="t1",
        action="budget.consume",
        timestamp="2026-04-26T00:00:00Z",
        verdict="pass",
    )
    v2 = transform_v1_to_v2(v1, chain_prev_hash="prevhash")
    assert v2.proof_state == "Pass"
    assert v2.tier == 1  # budget.* → constraint, tier 1
    assert v2.schema_ver == V2_SCHEMA_VERSION
    assert v2.lineage_parent_ids == [v1.proof_id]
    assert v2.phi_level == 3
    assert v2.tension_snap is None
    assert v2.mfidel_sig == []
    assert v2.cascade_chain == []


def test_transform_fail_keeps_reason():
    v1 = V1Proof(
        proof_id="p1",
        tenant_id="t1",
        action="policy.deny",
        timestamp="2026-04-26T00:00:00Z",
        verdict="fail",
        reason="quota_exceeded",
    )
    v2 = transform_v1_to_v2(v1, chain_prev_hash="prev")
    assert v2.proof_state == "Fail"
    assert v2.reason == "quota_exceeded"


def test_transform_fail_synthesizes_reason_when_v1_lacks_one():
    v1 = V1Proof(
        proof_id="p1",
        tenant_id="t1",
        action="policy.deny",
        timestamp="2026-04-26T00:00:00Z",
        verdict="fail",
        reason="",
    )
    v2 = transform_v1_to_v2(v1, chain_prev_hash="prev")
    assert v2.reason == "v1_migration_no_reason"


def test_transform_action_maps_to_correct_construct():
    cases = [
        ("budget.consume",      "constraint",     1),
        ("tenant.create",       "boundary",       1),
        ("agent.invoke.tool",   "execution",      5),
        ("workflow.step.run",   "transformation", 2),
        ("audit.write.entry",   "validation",     4),
        ("health.check.deep",   "observation",    5),
        ("unknown.action.foo",  "execution",      5),  # default fallback
    ]
    for action, _expected_type, expected_tier in cases:
        v1 = V1Proof(
            proof_id="x",
            tenant_id="t",
            action=action,
            timestamp="2026-04-26T00:00:00Z",
            verdict="pass",
        )
        v2 = transform_v1_to_v2(v1, chain_prev_hash="")
        assert v2.tier == expected_tier, f"{action} → tier {v2.tier}, expected {expected_tier}"


def test_transform_unknown_verdict_rejected():
    v1 = V1Proof(
        proof_id="x", tenant_id="t", action="a",
        timestamp="2026-04-26T00:00:00Z", verdict="indeterminate",
    )
    with pytest.raises(ValueError, match="verdict"):
        transform_v1_to_v2(v1, chain_prev_hash="")


def test_transform_construct_id_is_deterministic():
    """Same v1 proof_id always produces the same v2 construct_id."""
    v1 = V1Proof(
        proof_id="stable-id",
        tenant_id="t",
        action="budget.consume",
        timestamp="2026-04-26T00:00:00Z",
        verdict="pass",
    )
    v2a = transform_v1_to_v2(v1, chain_prev_hash="")
    v2b = transform_v1_to_v2(v1, chain_prev_hash="different-prev")
    assert v2a.construct_id == v2b.construct_id


def test_v1_chain_verification_passes_on_consistent_chain():
    proofs = _make_chain("t", [("budget.x", "pass"), ("policy.y", "fail")])
    _verify_v1_chain(proofs)  # no exception


def test_v1_chain_verification_detects_break():
    proofs = _make_chain("t", [("budget.x", "pass"), ("policy.y", "fail")])
    # Tamper: corrupt the second record's prev_hash
    proofs[1] = V1Proof(
        proof_id=proofs[1].proof_id,
        tenant_id=proofs[1].tenant_id,
        action=proofs[1].action,
        timestamp=proofs[1].timestamp,
        verdict=proofs[1].verdict,
        reason=proofs[1].reason,
        prev_hash="WRONG",
        proof_hash=proofs[1].proof_hash,
    )
    with pytest.raises(HashChainBroken, match="record 1"):
        _verify_v1_chain(proofs)


# ---- Runner integration tests ----


@pytest.fixture
def dirs(tmp_path: Path) -> tuple[Path, Path, Path]:
    v1 = tmp_path / "v1"
    v2 = tmp_path / "v2"
    manifest = tmp_path / "manifest"
    return v1, v2, manifest


def test_runner_migrates_clean_chain(dirs):
    v1, v2, manifest = dirs
    proofs = _make_chain("acme", [
        ("budget.consume", "pass"),
        ("agent.invoke.tool", "pass"),
        ("policy.deny", "fail"),
    ])
    _write_v1_chain(v1, proofs)

    stats = MigrationRunner(v1, v2, manifest).run()
    assert "acme" in stats
    s = stats["acme"]
    assert s.examined == 3
    assert s.migrated == 3
    assert s.skipped_already_migrated == 0
    assert s.failed == 0
    assert not s.halted_chain_break

    # Each v1 proof has a matching v2 file
    for p in proofs:
        v2_file = v2 / "acme" / f"{p.proof_id}.json"
        assert v2_file.exists()
        v2_payload = json.loads(v2_file.read_text("utf-8"))
        assert v2_payload["schema_ver"] == V2_SCHEMA_VERSION
        assert v2_payload["lineage"]["parent_ids"] == [p.proof_id]


def test_runner_idempotent(dirs):
    """Running twice produces no new records on the second run."""
    v1, v2, manifest = dirs
    proofs = _make_chain("acme", [("budget.x", "pass"), ("budget.y", "pass")])
    _write_v1_chain(v1, proofs)

    runner = MigrationRunner(v1, v2, manifest)
    stats1 = runner.run()["acme"]
    stats2 = runner.run()["acme"]

    assert stats1.migrated == 2
    assert stats2.migrated == 0
    assert stats2.skipped_already_migrated == 2


def test_runner_halts_chain_break_on_one_tenant_continues_others(dirs):
    v1, v2, manifest = dirs
    # Tenant A: clean
    a_proofs = _make_chain("acme", [("budget.x", "pass")])
    _write_v1_chain(v1, a_proofs)
    # Tenant B: corrupted — write a chain then tamper the file on disk
    b_proofs = _make_chain("foo", [
        ("budget.x", "pass"),
        ("policy.y", "fail"),
    ])
    _write_v1_chain(v1, b_proofs)
    bad_file = v1 / "foo" / f"{b_proofs[1].proof_id}.json"
    payload = json.loads(bad_file.read_text("utf-8"))
    payload["prev_hash"] = "TAMPERED"
    bad_file.write_text(json.dumps(payload), encoding="utf-8")

    stats = MigrationRunner(v1, v2, manifest).run()
    assert not stats["acme"].halted_chain_break
    assert stats["acme"].migrated == 1
    assert stats["foo"].halted_chain_break
    assert stats["foo"].migrated == 0


def test_runner_dry_run_writes_nothing(dirs):
    v1, v2, manifest = dirs
    proofs = _make_chain("acme", [("budget.x", "pass")])
    _write_v1_chain(v1, proofs)

    stats = MigrationRunner(v1, v2, manifest, dry_run=True).run()
    assert stats["acme"].migrated == 1
    # No v2 files written, no manifest written
    assert not (v2 / "acme").exists() or not list((v2 / "acme").glob("*.json"))
    assert not (manifest / "acme.json").exists()


def test_runner_tenant_filter(dirs):
    v1, v2, manifest = dirs
    _write_v1_chain(v1, _make_chain("acme", [("budget.x", "pass")]))
    _write_v1_chain(v1, _make_chain("foo", [("budget.x", "pass")]))

    stats = MigrationRunner(v1, v2, manifest, tenant_filter="acme").run()
    assert "acme" in stats
    assert "foo" not in stats
    assert (v2 / "acme").exists()
    assert not (v2 / "foo").exists()


def test_runner_v2_chain_has_continuity_through_genesis(dirs):
    """First v2 record's prev_hash = H(last_v1_hash || 'v2_genesis')."""
    v1, v2, manifest = dirs
    proofs = _make_chain("acme", [
        ("budget.x", "pass"),
        ("policy.y", "pass"),
    ])
    _write_v1_chain(v1, proofs)

    MigrationRunner(v1, v2, manifest).run()

    # Read the first v2 record (in proof_id order, which matches our chain order)
    first_v2 = json.loads(
        (v2 / "acme" / f"{proofs[0].proof_id}.json").read_text("utf-8")
    )
    expected_genesis = hashlib.sha256(
        f"{proofs[-1].proof_hash}{V2_GENESIS_MARKER}".encode("utf-8")
    ).hexdigest()
    assert first_v2["prev_hash"] == expected_genesis


def test_runner_v2_chain_internally_linked(dirs):
    """Each v2 record's prev_hash equals the previous v2 record's proof_hash."""
    v1, v2, manifest = dirs
    proofs = _make_chain("acme", [
        ("budget.x", "pass"),
        ("policy.y", "pass"),
        ("workflow.step.run", "fail"),
    ])
    _write_v1_chain(v1, proofs)

    MigrationRunner(v1, v2, manifest).run()

    # Walk in chain order
    v2_records = []
    for p in proofs:
        v2_records.append(
            json.loads((v2 / "acme" / f"{p.proof_id}.json").read_text("utf-8"))
        )
    for i in range(1, len(v2_records)):
        assert v2_records[i]["prev_hash"] == v2_records[i - 1]["proof_hash"]


def test_runner_no_tenants_returns_empty(dirs):
    v1, v2, manifest = dirs
    v1.mkdir(parents=True, exist_ok=True)
    stats = MigrationRunner(v1, v2, manifest).run()
    assert stats == {}


def test_runner_manifest_records_completion(dirs):
    v1, v2, manifest = dirs
    _write_v1_chain(v1, _make_chain("acme", [("budget.x", "pass")]))

    MigrationRunner(v1, v2, manifest).run()
    m = json.loads((manifest / "acme.json").read_text("utf-8"))
    assert m["tenant_id"] == "acme"
    assert "acme-0000" in m["migrated"]
    assert m["last_v1_hash"]
    assert m["last_v2_hash"]
    assert m["completed_at"] is not None


# ---- CLI ----


def test_cli_help_shows_subcommand_args():
    from mcoi_runtime.migration.runner import _build_parser

    parser = _build_parser()
    help_text = parser.format_help()
    assert "--v1-dir" in help_text
    assert "--v2-dir" in help_text
    assert "--manifest-dir" in help_text
    assert "--dry-run" in help_text


def test_cli_returns_0_on_clean_run(dirs, monkeypatch):
    from mcoi_runtime.migration.runner import main

    v1, v2, manifest = dirs
    _write_v1_chain(v1, _make_chain("acme", [("budget.x", "pass")]))

    rc = main([
        "--v1-dir", str(v1),
        "--v2-dir", str(v2),
        "--manifest-dir", str(manifest),
    ])
    assert rc == 0


def test_cli_returns_1_on_chain_break(dirs):
    from mcoi_runtime.migration.runner import main

    v1, v2, manifest = dirs
    proofs = _make_chain("acme", [
        ("budget.x", "pass"),
        ("policy.y", "fail"),
    ])
    _write_v1_chain(v1, proofs)
    # Tamper
    bad_file = v1 / "acme" / (proofs[1].proof_id + ".json")
    payload = json.loads(bad_file.read_text("utf-8"))
    payload["prev_hash"] = "TAMPERED"
    bad_file.write_text(json.dumps(payload), encoding="utf-8")

    rc = main([
        "--v1-dir", str(v1),
        "--v2-dir", str(v2),
        "--manifest-dir", str(manifest),
    ])
    assert rc == 1


def test_cli_rejects_unsupported_version_combo(dirs):
    from mcoi_runtime.migration.runner import main

    v1, v2, manifest = dirs
    rc = main([
        "--v1-dir", str(v1),
        "--v2-dir", str(v2),
        "--manifest-dir", str(manifest),
        "--from", "v0",
        "--to", "v1",
    ])
    assert rc == 2
