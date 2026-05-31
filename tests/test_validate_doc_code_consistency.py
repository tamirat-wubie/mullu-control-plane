"""The anti-fabrication doc/code consistency gate must stay green.

This gate is now wired into CI (schema-validation job): a doc that references a
nonexistent module path or an unwired ``*_MODE`` flag fails the build. Inherited
debt is acknowledged in ``scripts/doc_code_consistency_baseline.txt``; anything
new must be fixed or explicitly baselined. This test locks the current green
state and the cross-platform path normalization.
"""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "validate_doc_code_consistency.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_doc_code_consistency", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_doc_code_consistency_gate_passes():
    """All current detections are baselined, so the gate exits 0."""
    module = _load_module()
    assert module.main() == 0


def test_failure_strings_are_posix_normalized():
    """Failure strings must use forward slashes so a baseline generated on any
    OS (including Windows) matches the Linux CI runner."""
    module = _load_module()
    docs = module._gather(module.DOC_GLOBS)
    failures = (
        module.check_module_paths(docs)
        + module.check_flags(docs, module._all_code_text())
    )
    offenders = [f for f in failures if "\\" in f]
    assert not offenders, f"backslash in failure strings (not CI-portable): {offenders}"
