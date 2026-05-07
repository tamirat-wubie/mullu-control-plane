"""Physical worker canary tests.

Purpose: verify the sandbox physical worker canary blocks missing boundary
receipts and admits only no-effect sandbox replay.
Governance scope: physical-action boundary, worker mesh admission, and runtime
conformance artifact projection.
Dependencies: gateway.physical_worker_canary.
Invariants:
  - Missing physical receipts block before handler execution.
  - Admitted sandbox dispatch requires a valid boundary receipt.
  - The canary artifact is hash-bound.
"""

from __future__ import annotations

from gateway.physical_worker_canary import run_physical_worker_canary


def test_physical_worker_canary_blocks_missing_receipt_and_allows_sandbox_replay() -> None:
    artifact = run_physical_worker_canary()

    assert artifact.passed is True
    assert artifact.status == "passed"
    assert artifact.blockers == ()
    assert artifact.handler_calls == 1
    assert artifact.canary_id.startswith("physical-worker-canary-")


def test_physical_worker_canary_artifact_preserves_no_effect_proof() -> None:
    artifact = run_physical_worker_canary()
    payload = artifact.to_json_dict()

    assert payload["boundary_receipt"]["status"] == "allowed"
    assert payload["boundary_receipt"]["no_physical_effect_applied"] is True
    assert payload["blocked_dispatch_receipt"]["reason"] == "physical_action_receipt_required"
    assert payload["worker_mesh_envelope"]["receipt"]["status"] == "succeeded"
    assert payload["worker_mesh_envelope"]["receipt"]["metadata"]["physical_action_receipt_validated"] is True


def test_physical_worker_canary_evidence_and_hash_are_stable() -> None:
    artifact = run_physical_worker_canary()

    assert len(artifact.evidence_refs) == 3
    assert all(ref for ref in artifact.evidence_refs)
    assert len(artifact.artifact_hash) == 64
    assert artifact.artifact_hash == run_physical_worker_canary().artifact_hash
    assert artifact.metadata["production_admissible"] is False
