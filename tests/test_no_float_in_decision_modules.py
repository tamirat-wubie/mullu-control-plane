"""Tests for the no-float-in-decision-modules lint (spec invariant I-PRED-17).

Verifies the decision modules are float-clean against the documented
allowlist, and that the lint is not vacuous — it must detect a float token
injected into a decision module.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.check_no_float_in_decision_modules import (  # noqa: E402
    ALLOWLIST,
    DECISION_MODULES,
    find_violations,
    main,
)


def test_decision_modules_are_float_clean() -> None:
    # The shipped tree must pass: every float token in a decision module is
    # either absent or explicitly allowlisted with justification.
    violations = find_violations()
    assert violations == [], "unexpected float tokens in decision modules:\n" + "\n".join(violations)


def test_lint_main_returns_zero_on_clean_tree() -> None:
    assert main() == 0


def test_lint_detects_injected_float(tmp_path, monkeypatch) -> None:
    # The lint must not be vacuous: a float token injected into a decision
    # module (and not allowlisted) is reported as a violation.
    import scripts.check_no_float_in_decision_modules as checker

    fake_gateway = tmp_path / "gateway"
    fake_gateway.mkdir()
    target = fake_gateway / "causal_closure_kernel.py"
    target.write_text(
        "def decide(score):\n"
        "    threshold = 0.75\n"
        "    return score > threshold\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(checker, "GATEWAY_DIR", fake_gateway)
    monkeypatch.setattr(checker, "DECISION_MODULES", ("causal_closure_kernel.py",))
    monkeypatch.setattr(checker, "ALLOWLIST", {})

    violations = checker.find_violations()
    assert any("0.75" in v for v in violations)
    assert checker.main() == 1


def test_lint_respects_allowlist(tmp_path, monkeypatch) -> None:
    # An allowlisted line carrying a float must NOT be reported.
    import scripts.check_no_float_in_decision_modules as checker

    fake_gateway = tmp_path / "gateway"
    fake_gateway.mkdir()
    target = fake_gateway / "command_spine.py"
    target.write_text(
        "class Claim:\n"
        "    confidence: float\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(checker, "GATEWAY_DIR", fake_gateway)
    monkeypatch.setattr(checker, "DECISION_MODULES", ("command_spine.py",))
    monkeypatch.setattr(checker, "ALLOWLIST", {"command_spine.py": {"confidence: float"}})

    assert checker.find_violations() == []


def test_lint_flags_missing_decision_module(tmp_path, monkeypatch) -> None:
    # A decision module that disappears is itself a violation (the lint must
    # fail closed rather than silently skip a renamed/removed surface).
    import scripts.check_no_float_in_decision_modules as checker

    fake_gateway = tmp_path / "gateway"
    fake_gateway.mkdir()
    monkeypatch.setattr(checker, "GATEWAY_DIR", fake_gateway)
    monkeypatch.setattr(checker, "DECISION_MODULES", ("does_not_exist.py",))
    monkeypatch.setattr(checker, "ALLOWLIST", {})

    violations = checker.find_violations()
    assert any("MISSING decision module" in v for v in violations)


def test_allowlist_entries_target_known_decision_modules() -> None:
    # Guard against allowlist drift: every allowlisted module must be a
    # declared decision module.
    for module in ALLOWLIST:
        assert module in DECISION_MODULES, f"allowlist references unknown module: {module}"
