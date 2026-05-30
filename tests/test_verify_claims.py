"""Tests for scripts/verify_claims.py (status-claim receipts)."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "verify_claims.py"
FIX = REPO_ROOT / "tests" / "fixtures" / "claim_receipts"
CORPUS = FIX / "corpus.json"

_spec = importlib.util.spec_from_file_location("verify_claims", SCRIPT)
verify_claims = importlib.util.module_from_spec(_spec)
sys.modules["verify_claims"] = verify_claims  # register before exec so @dataclass resolves
_spec.loader.exec_module(verify_claims)
evaluate_claim = verify_claims.evaluate_claim


def _claim(mode, value, cmd, **check_extra):
    return {
        "id": "t",
        "assertion": "x",
        "capture_command": cmd,
        "check": {"mode": mode, "value": value, **check_extra},
    }


def test_sha_prefix_match_supported():
    cmd = ["python", "-c", "import pathlib,sys; sys.stdout.write(pathlib.Path('fixtures/head.txt').read_text())"]
    r = evaluate_claim(_claim("sha_equals", "c4ed7f86", cmd), FIX)
    assert r.supported, r.detail
    assert r.captured  # receipt carries the evidence


def test_sha_wrong_unsupported():
    cmd = ["python", "-c", "import pathlib,sys; sys.stdout.write(pathlib.Path('fixtures/head.txt').read_text())"]
    r = evaluate_claim(_claim("sha_equals", "8d9f9da9", cmd), FIX)
    assert not r.supported


def test_state_all_green_supported():
    cmd = ["python", "-c", "import pathlib,sys; sys.stdout.write(pathlib.Path('fixtures/checks_green.json').read_text())"]
    r = evaluate_claim(_claim("state_all", "SUCCESS", cmd, field="state"), FIX)
    assert r.supported, r.detail


def test_state_all_running_unsupported():
    cmd = ["python", "-c", "import pathlib,sys; sys.stdout.write(pathlib.Path('fixtures/checks_running.json').read_text())"]
    r = evaluate_claim(_claim("state_all", "SUCCESS", cmd, field="state"), FIX)
    assert not r.supported


def test_count_match_and_mismatch():
    cmd = ["python", "-c", "import json,pathlib,sys; sys.stdout.write(json.dumps({'total': len(json.loads(pathlib.Path('fixtures/checks_green.json').read_text()))}))"]
    assert evaluate_claim(_claim("count_from_json", "3", cmd, path="total"), FIX).supported
    assert not evaluate_claim(_claim("count_from_json", "65", cmd, path="total"), FIX).supported


def test_shell_string_command_rejected():
    r = evaluate_claim(_claim("contains", "x", "echo x | grep x"), FIX)
    assert not r.supported
    assert "argv array" in r.detail


def test_disallowed_executable_rejected():
    r = evaluate_claim(_claim("contains", "x", ["rm", "-rf", "/"]), FIX)
    assert not r.supported
    assert "not allowed" in r.detail


def test_malformed_claim_unsupported():
    r = evaluate_claim({"id": "m", "assertion": "x"}, FIX)
    assert not r.supported
    assert "malformed" in r.detail


def test_calibration_reproduces_all_verdicts():
    # calibrate() resolves capture cwd to the corpus's own directory, so the
    # subprocess cwd does not matter for the relative fixture paths; run from
    # the corpus dir anyway to mirror real usage.
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "corpus.json", "--calibrate"],
        capture_output=True, text=True, cwd=str(FIX),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CALIBRATION PASS" in proc.stdout
