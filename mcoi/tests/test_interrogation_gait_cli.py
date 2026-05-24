"""Purpose: verify the side-effect-free gait CLI surface.
Governance scope: deterministic envelope, fail-closed parsing, and mcoi dispatch.
Dependencies: the gait CLI module and the mcoi CLI parser/dispatch.
Invariants: identical input yields an identical envelope; bad input fails closed
with a non-zero exit and no traceback leak.
"""

from __future__ import annotations

import json

import pytest

from mcoi_runtime.app.cli import build_parser, main
from mcoi_runtime.core.interrogation_gait_cli import build_gait_envelope

BASE = ["gait", "--roles", "why,what,how", "--phase", "verify"]


def _ns(extra: list[str]):
    return build_parser().parse_args(BASE + extra)


def test_envelope_is_deterministic_and_proofless_by_default() -> None:
    a = build_gait_envelope(_ns(["--topology", "cycle"]))
    b = build_gait_envelope(_ns(["--topology", "cycle"]))

    assert a == b
    assert a["proof"] is None
    assert a["active_count"] == 3
    assert a["witness"].startswith("sha256:")
    assert a["spec"]["roles"] == ["why", "what", "how"]


def test_certify_flag_attaches_a_real_proof() -> None:
    env = build_gait_envelope(_ns(["--certify", "--at", "2026-05-19T12:00:00+00:00"]))

    assert env["proof"] is not None
    assert env["proof"]["verdict"] == "allowed"
    assert env["proof"]["machine_id"] == "interrogation-gait"
    assert env["proof"]["receipt_hash"]


def test_certify_without_timestamp_fails_closed() -> None:
    from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

    with pytest.raises(RuntimeCoreInvariantError, match="requires --at"):
        build_gait_envelope(_ns(["--certify"]))


def test_dispatch_returns_zero_and_emits_parseable_json(capsys) -> None:
    rc = main(["gait", "--roles", "why,what", "--phase", "define", "--json"])
    out = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert out["operation"] == "gait"
    assert out["active_count"] == 2
    assert out["witness"].startswith("sha256:")


def test_dispatch_fails_closed_on_bad_role(capsys) -> None:
    rc = main(["gait", "--roles", "not_a_role", "--phase", "define"])
    captured = capsys.readouterr().out

    assert rc == 1
    assert "rejected input" in captured
    assert "Traceback" not in captured


def test_dispatch_fails_closed_on_stochastic_determinism(capsys) -> None:
    rc = main(["gait", "--roles", "why", "--phase", "define", "--determinism", "stochastic"])

    assert rc == 1
    assert "rejected input" in capsys.readouterr().out
