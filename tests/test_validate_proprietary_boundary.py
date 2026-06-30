"""Purpose: verify proprietary boundary validation fails closed.
Governance scope: NOTICE, CODEOWNERS, package metadata, Rust crate license
metadata, and obsolete license wording scans.
Dependencies: scripts.validate_proprietary_boundary and repository fixtures.
Invariants:
  - Current repository boundary passes.
  - Missing owner review rules are rejected.
  - Obsolete license grant wording is rejected.
  - Package metadata remains non-publishable and proprietary.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import validate_proprietary_boundary  # noqa: E402


def test_current_repository_proprietary_boundary_passes() -> None:
    errors = validate_proprietary_boundary.validate_proprietary_boundary()

    assert errors == []
    assert len(errors) == 0
    assert validate_proprietary_boundary.NOTICE_PATH.exists()


def test_notice_rejects_missing_required_literals(tmp_path: Path) -> None:
    notice = tmp_path / "NOTICE"
    notice.write_text("Mullusi Proprietary Notice\n", encoding="utf-8")

    errors = validate_proprietary_boundary.validate_required_literals(
        path=notice,
        required_literals=validate_proprietary_boundary.NOTICE_REQUIRED_LITERALS,
        label="NOTICE",
    )

    assert len(errors) == 1
    assert "NOTICE missing required literals" in errors[0]
    assert "Tamirat Wubie" in errors[0]


def test_codeowners_rejects_missing_owner_rules(tmp_path: Path) -> None:
    codeowners = tmp_path / "CODEOWNERS"
    codeowners.write_text("/LICENSE @tamirat-wubie\n", encoding="utf-8")

    errors = validate_proprietary_boundary.validate_codeowners(codeowners)

    assert len(errors) == 1
    assert "CODEOWNERS missing required owner rules" in errors[0]
    assert "/NOTICE @tamirat-wubie" in errors[0]


def test_forbidden_scan_rejects_obsolete_license_grant(tmp_path: Path) -> None:
    stale_license = tmp_path / "README.md"
    stale_license.write_text("Header\n" + "MIT" + " License\n", encoding="utf-8")

    errors = validate_proprietary_boundary.scan_forbidden_text_patterns(root=tmp_path)

    assert len(errors) == 1
    assert "README.md contains forbidden boundary text" in errors[0]
    assert "MIT" in errors[0]


def test_forbidden_scan_skips_nested_git_worktree(tmp_path: Path) -> None:
    nested_repo = tmp_path / "mullu-control-plane-shadow"
    nested_repo.mkdir()
    (nested_repo / ".git").write_text("gitdir: ../.git/worktrees/shadow\n", encoding="utf-8")
    (nested_repo / "README.md").write_text("Header\n" + "MIT" + " License\n", encoding="utf-8")
    active_doc = tmp_path / "README.md"
    active_doc.write_text("Mullusi proprietary boundary text.\n", encoding="utf-8")

    errors = validate_proprietary_boundary.scan_forbidden_text_patterns(root=tmp_path)

    assert errors == []


def test_forbidden_scan_skips_local_control_plane_scratch_directory(tmp_path: Path) -> None:
    scratch_dir = tmp_path / "mullu-control-plane-terminal-approval-command-preview-v2"
    scratch_dir.mkdir()
    (scratch_dir / "README.md").write_text("Header\n" + "MIT" + " License\n", encoding="utf-8")
    active_doc = tmp_path / "README.md"
    active_doc.write_text("Mullusi proprietary boundary text.\n", encoding="utf-8")

    errors = validate_proprietary_boundary.scan_forbidden_text_patterns(root=tmp_path)

    assert errors == []
    assert len(errors) == 0


def test_forbidden_scan_skips_patch_artifacts(tmp_path: Path) -> None:
    patch_artifact = tmp_path / "review.patch"
    patch_artifact.write_bytes(b"\xff\xfeM\x00I\x00T\x00 \x00L\x00i\x00c\x00e\x00n\x00s\x00e\x00")

    errors = validate_proprietary_boundary.scan_forbidden_text_patterns(root=tmp_path)

    assert errors == []


def test_typescript_package_rejects_publishable_metadata(tmp_path: Path) -> None:
    package = tmp_path / "package.json"
    package.write_text('{"private": false, "license": "' + "MIT" + '"}', encoding="utf-8")

    errors = validate_proprietary_boundary.validate_typescript_package(package)

    assert len(errors) == 2
    assert any("private=true" in error for error in errors)
    assert any("license=UNLICENSED" in error for error in errors)
