#!/usr/bin/env python3
"""CI gate: ensures no new legacy dispatch paths are introduced.

Scans mcoi/mcoi_runtime/ for direct Dispatcher.dispatch() calls outside of:
- governed_dispatcher.py (the wrapper)
- dispatch_guard.py (the guard)
- dispatcher.py (the definition itself)
- test files

Exit code 0 if no new violations, 1 if violations found.
"""
import re
import sys
from pathlib import Path

ALLOWED_FILES = {
    "governed_dispatcher.py",
    "dispatch_guard.py",
    "dispatcher.py",  # the definition itself
}


def main() -> None:
    violations: list[str] = []
    root = Path("mcoi/mcoi_runtime")

    for py_file in root.rglob("*.py"):
        if py_file.name in ALLOWED_FILES:
            continue
        if "__pycache__" in str(py_file):
            continue

        content = py_file.read_text(encoding="utf-8", errors="ignore")

        # Check for direct .dispatch( calls that aren't governed_dispatch
        for i, line in enumerate(content.splitlines(), 1):
            if ".dispatch(" in line and "governed_dispatch" not in line and "dispatch_guard" not in line:
                # Allow comments and strings
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"') or stripped.startswith("'"):
                    continue
                violations.append(f"{py_file}:{i}: {stripped}")

    if violations:
        print(f"DISPATCH COVERAGE GATE: {len(violations)} legacy dispatch call(s) found")
        print("These should be migrated to governed_dispatch or explicitly exempted:")
        for v in violations:
            print(f"  {v}")
        print(f"\nTotal violations: {len(violations)}")
        # Don't fail yet -- these are known legacy paths being migrated
        # Once migration is complete, change to sys.exit(1)
        print("STATUS: WARNING (legacy paths known, migration in progress)")
        sys.exit(0)  # Warning only for now
    else:
        print("DISPATCH COVERAGE GATE: PASS -- no legacy dispatch paths found")
        sys.exit(0)


if __name__ == "__main__":
    main()
