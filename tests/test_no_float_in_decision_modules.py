"""Tests for the no-float-in-decision-modules lint (I-PRED-17).

Verifies the lint is both correct (real decision modules are clean) and
non-vacuous (it actually detects an injected float token).
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.check_no_float_in_decision_modules as lint  # noqa: E402


def test_decision_modules_are_float_clean() -> None:
    # The real gateway decision modules must carry no float tokens beyond
    # the documented allowlist. A failure here means a new float entered a
    # decision path (or the allowlist drifted) — investigate before merging.
    violations = lint.find_violations()
    assert violations == [], "\n".join(violations)


def test_lint_covers_the_core_decision_surfaces() -> None:
    # Guard against silently shrinking the scanned set: the core
    # prediction / judgement / governance surfaces must stay covered.
    required = {
        "causal_closure_kernel.py",
        "command_spine.py",
        "plan_ledger.py",
        "audit_trace_verifier.py",
        "conformance.py",
        "authority_obligation_mesh.py",
    }
    assert required <= set(lint.DECISION_MODULES)


def test_float_token_regex_detects_real_float_forms() -> None:
    # Positive cases: every form the lint is meant to catch.
    for sample in (
        "x: float = 1.0",
        "weight = float(value)",
        "ratio = 0.5",
        "scaled = 1.25 * n",
        "let w: f32 = 1.0;",
        "let d: f64 = 2.0;",
    ):
        assert lint._FLOAT_TOKEN.search(sample), sample


def test_float_token_regex_ignores_non_float_forms() -> None:
    # Negative cases: integer / version / timestamp / attribute forms must
    # not trip the lint.
    for sample in (
        "count: int = 0",
        "verified: bool = True",
        "created_at = '2026-04-24T12:00:00+00:00'",
        "value = obj.attr",
        "total = a + b",
        "ledger_hash = '...'",
    ):
        assert not lint._FLOAT_TOKEN.search(sample), sample


def test_lint_detects_injected_float(tmp_path, monkeypatch) -> None:
    # Non-vacuity: point the lint at a temp gateway dir containing a module
    # with an unallowlisted float, and confirm it is reported.
    fake_gateway = tmp_path / "gateway"
    fake_gateway.mkdir()
    (fake_gateway / "causal_closure_kernel.py").write_text(
        "def decide(score):\n    threshold = 0.75\n    return score > threshold\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(lint, "GATEWAY_DIR", fake_gateway)
    monkeypatch.setattr(lint, "DECISION_MODULES", ("causal_closure_kernel.py",))
    monkeypatch.setattr(lint, "ALLOWLIST", {})

    violations = lint.find_violations()
    assert any("0.75" in v for v in violations), violations


def test_lint_honours_allowlist(tmp_path, monkeypatch) -> None:
    # A float on an exactly-allowlisted line is accepted; the same float on
    # any other line is still reported.
    fake_gateway = tmp_path / "gateway"
    fake_gateway.mkdir()
    (fake_gateway / "command_spine.py").write_text(
        "        confidence: float = 1.0,\n        weight: float = 1.0,\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(lint, "GATEWAY_DIR", fake_gateway)
    monkeypatch.setattr(lint, "DECISION_MODULES", ("command_spine.py",))
    monkeypatch.setattr(lint, "ALLOWLIST", {"command_spine.py": {"confidence: float = 1.0,"}})

    violations = lint.find_violations()
    assert len(violations) == 1
    assert "weight: float = 1.0" in violations[0]
