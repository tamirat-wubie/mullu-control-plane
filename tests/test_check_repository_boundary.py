"""Purpose: verify the repository boundary guard for canonical and extraction checkouts.

Governance scope: repository identity, deployment extraction detection, and push-safety classification.
Dependencies: pytest and scripts.check_repository_boundary.
Invariants: tests use temporary paths only and never mutate Git remotes.
"""

from pathlib import Path

from scripts.check_repository_boundary import (
    CANONICAL_REPO,
    DEPLOYMENT_EXTRACTION_REPO,
    classify_repository,
    normalize_remote_url,
)


def test_normalize_remote_url_accepts_https_and_ssh() -> None:
    """Input contract: GitHub URLs. Output contract: owner/repo slug. Error contract: assertion failure."""

    assert normalize_remote_url(f"https://github.com/{CANONICAL_REPO}.git") == CANONICAL_REPO
    assert normalize_remote_url(f"git@github.com:{CANONICAL_REPO}.git") == CANONICAL_REPO
    assert normalize_remote_url(f"https://github.com/{DEPLOYMENT_EXTRACTION_REPO}") == (
        DEPLOYMENT_EXTRACTION_REPO
    )


def test_classify_repository_accepts_canonical_full_platform(tmp_path: Path) -> None:
    """Input contract: canonical paths. Output contract: canonical boundary. Error contract: assertion failure."""

    for relative_path in ("gateway", "governance", "capabilities", "mcoi", "maf"):
        (tmp_path / relative_path).mkdir()

    report = classify_repository(tmp_path, f"https://github.com/{CANONICAL_REPO}.git")

    assert report.boundary == "canonical"
    assert report.push_allowed_for_full_platform is True
    assert report.missing_canonical_paths == ()


def test_classify_repository_accepts_named_canonical_remote(tmp_path: Path) -> None:
    """Input contract: multiple remotes. Output contract: canonical boundary."""

    for relative_path in ("gateway", "governance", "capabilities", "mcoi", "maf"):
        (tmp_path / relative_path).mkdir()

    report = classify_repository(
        tmp_path,
        (
            "https://github.com/tamirat-wubie/mullu-governed-swarm.git",
            f"https://github.com/{CANONICAL_REPO}.git",
        ),
    )

    assert report.boundary == "canonical"
    assert report.push_allowed_for_full_platform is True
    assert CANONICAL_REPO in report.origin


def test_classify_repository_blocks_deployment_extraction(tmp_path: Path) -> None:
    """Input contract: extraction indicators. Output contract: blocked boundary. Error contract: assertion failure."""

    (tmp_path / "apps" / "api").mkdir(parents=True)
    (tmp_path / "apps" / "dashboard").mkdir(parents=True)

    report = classify_repository(tmp_path, f"https://github.com/{DEPLOYMENT_EXTRACTION_REPO}.git")

    assert report.boundary == "deployment_extraction"
    assert report.push_allowed_for_full_platform is False
    assert "apps/api" in report.extraction_indicators
    assert "canonical checkout" in report.required_action


def test_classify_repository_marks_unknown_when_paths_and_origin_disagree(tmp_path: Path) -> None:
    """Input contract: unknown repo facts. Output contract: unknown boundary. Error contract: assertion failure."""

    report = classify_repository(tmp_path, "https://github.com/example/unknown.git")

    assert report.boundary == "unknown"
    assert report.push_allowed_for_full_platform is False
    assert "Inspect remotes" in report.required_action
