"""Purpose: verify governed SDLC release readiness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_sdlc_release_readiness.
Invariants:
  - Release candidates are evidence-bound.
  - Not-published releases cannot carry production claims.
  - Published production claims require witness and public health evidence.
"""

from __future__ import annotations

import copy
import io
from contextlib import redirect_stdout

from scripts import validate_sdlc_artifact
from scripts import validate_sdlc_release_readiness as validator


def test_current_sdlc_release_readiness_passes_strict() -> None:
    errors = validator.validate_contract(strict=True)

    assert errors == []
    assert validate_sdlc_artifact.ARTIFACT_SPEC_BY_KIND["release_candidate"].example_path.exists()
    assert validate_sdlc_artifact.ARTIFACT_SPEC_BY_KIND["deployment_candidate"].example_path.exists()


def test_not_published_release_rejects_production_claim() -> None:
    records = validate_sdlc_artifact.load_example_records()
    release = copy.deepcopy(records["release_candidate"])
    deployment = copy.deepcopy(records["deployment_candidate"])
    deployment["public_production_claim"] = True

    errors = validator.validate_release_deployment_pair(release, deployment, strict=True)

    assert "release_readiness: not_published release cannot carry production claim" in errors
    assert any("production claim requires production environment" in error for error in errors)
    assert len(errors) >= 2


def test_published_release_requires_witness_evidence() -> None:
    records = validate_sdlc_artifact.load_example_records()
    release = copy.deepcopy(records["release_candidate"])
    deployment = copy.deepcopy(records["deployment_candidate"])
    release["deployment_status"] = "published"
    deployment["environment"] = "production"
    deployment["public_production_claim"] = True

    errors = validator.validate_release_deployment_pair(release, deployment, strict=True)

    assert any("production claim requires deployment_witness evidence" in error for error in errors)
    assert any("production claim requires public_health evidence" in error for error in errors)
    assert len(errors) >= 2


def test_non_published_release_notes_reject_production_overclaim() -> None:
    release = copy.deepcopy(validate_sdlc_artifact.load_example_records()["release_candidate"])
    release["release_notes"] = "Production release is available."

    errors = validate_sdlc_artifact.validate_release_candidate_record(release, strict=True)

    assert "release_candidate: non-published release notes must not claim production" in errors
    assert len(errors) >= 1
    assert release["deployment_status"] == "not_published"


def test_release_readiness_cli_reports_passed() -> None:
    stdout_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer):
        exit_code = validator.main(["--strict"])

    output = stdout_buffer.getvalue()
    assert exit_code == 0
    assert "sdlc_release_candidate" in output
    assert "STATUS: passed" in output
