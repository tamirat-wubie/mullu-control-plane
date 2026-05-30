#!/usr/bin/env python3
"""Install Mullu's opt-in git hooks into the local clone.

Copies scripts/githooks/* into the repository's resolved hooks directory
(honoring `core.hooksPath` if set, else `.git/hooks`) and marks them
executable. Idempotent. Opt-in by design: nothing installs hooks automatically;
a developer runs this deliberately.

  python scripts/install_git_hooks.py            # install
  python scripts/install_git_hooks.py --check     # report status, exit 1 if not installed
  python scripts/install_git_hooks.py --uninstall # remove hooks this installer manages

The pre-push hook runs scripts/validate_release_status.py (the same aggregate
gate CI runs) before each push. Bypass once with `git push --no-verify`.
"""
from __future__ import annotations

import argparse
import shutil
import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "scripts" / "githooks"
MANAGED_HOOKS = ("pre-push",)
MARKER = "Mullu pre-push gate hook"  # identifies hooks this installer owns


def _hooks_dir() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--git-path", "hooks"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        out = ".git/hooks"
    p = Path(out)
    return p if p.is_absolute() else (REPO_ROOT / p)


def install() -> int:
    hooks = _hooks_dir()
    hooks.mkdir(parents=True, exist_ok=True)
    for name in MANAGED_HOOKS:
        src = SOURCE_DIR / name
        if not src.exists():
            print(f"source hook missing: {src}")
            return 1
        dst = hooks / name
        shutil.copyfile(src, dst)
        dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"installed {name} -> {dst}")
    print("done. bypass one push with: git push --no-verify")
    return 0


def check() -> int:
    hooks = _hooks_dir()
    missing = []
    for name in MANAGED_HOOKS:
        dst = hooks / name
        if not dst.exists() or MARKER not in dst.read_text(encoding="utf-8", errors="replace"):
            missing.append(name)
    if missing:
        print(f"NOT installed: {missing} (run: python scripts/install_git_hooks.py)")
        return 1
    print(f"installed: {list(MANAGED_HOOKS)} in {hooks}")
    return 0


def uninstall() -> int:
    hooks = _hooks_dir()
    for name in MANAGED_HOOKS:
        dst = hooks / name
        if dst.exists() and MARKER in dst.read_text(encoding="utf-8", errors="replace"):
            dst.unlink()
            print(f"removed {name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true", help="report install status; exit 1 if not installed")
    p.add_argument("--uninstall", action="store_true", help="remove hooks this installer manages")
    args = p.parse_args(argv)
    if args.check:
        return check()
    if args.uninstall:
        return uninstall()
    return install()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
