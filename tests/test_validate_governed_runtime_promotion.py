"""Tests for governed runtime promotion validation aliases.

Purpose: prove domain-neutral runtime promotion commands reuse the governed
promotion readiness contract without breaking existing evidence schemas.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_governed_runtime_promotion.
Invariants:
  - Alias readiness matches the compatibility validator output.
  - CLI output names governed runtime promotion.
  - Strict mode remains fail-closed while blockers remain.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_MCOI_ROOT = _ROOT / "mcoi"
if str(_MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(_MCOI_ROOT))

from scripts.validate_general_agent_promotion import (  # noqa: E402
    validate_general_agent_promotion,
)
from scripts.validate_governed_runtime_promotion import (  # noqa: E402
    main,
    validate_governed_runtime_promotion,
    write_governed_runtime_promotion_readiness,
)


def test_governed_runtime_promotion_alias_matches_existing_readiness() -> None:
    compatibility = validate_general_agent_promotion(repo_root=_ROOT)
    governed = validate_governed_runtime_promotion(repo_root=_ROOT)

    assert governed.as_dict() == compatibility.as_dict()
    assert governed.readiness_level == "pilot-governed-core"
    assert governed.capability_count >= 52
    assert "deployment_witness_not_published" in governed.blockers


def test_governed_runtime_cli_json_fails_closed_in_strict_mode(tmp_path: Path, capsys) -> None:
    missing_witness = tmp_path / "missing_deployment_witness.json"

    exit_code = main(
        [
            "--repo-root",
            str(_ROOT),
            "--deployment-witness",
            str(missing_witness),
            "--strict",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 2
    assert payload["ready"] is False
    assert payload["readiness_level"] == "pilot-governed-core"
    assert "production_health_not_declared" in payload["blockers"]
    assert captured.err == ""


def test_governed_runtime_cli_output_uses_domain_neutral_label(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "governed_runtime_promotion_readiness.json"

    exit_code = main(
        [
            "--repo-root",
            str(_ROOT),
            "--output",
            str(output_path),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "GOVERNED RUNTIME PROMOTION BLOCKED" in captured.out
    assert "governed_runtime_promotion_readiness_written:" in captured.out
    assert payload["ready"] is False
    assert payload["capability_count"] >= 52


def test_write_governed_runtime_promotion_readiness_persists_report(tmp_path: Path) -> None:
    readiness = validate_governed_runtime_promotion(repo_root=_ROOT)
    output_path = tmp_path / "governed_runtime_promotion_readiness.json"

    written = write_governed_runtime_promotion_readiness(readiness, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert payload == json.loads(json.dumps(readiness.as_dict()))
    assert payload["readiness_level"] == "pilot-governed-core"
    assert "deployment_witness_not_published" in payload["blockers"]
