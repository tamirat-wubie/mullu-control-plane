"""Purpose: verify Life-Meaning Governance validator closure.

Governance scope: OCE artifact completeness, RAG docs-schema-example-runtime
binding, CDCV validator causality, CQTE deterministic checks, UWMA witness
coverage, and PRS pass/fail reporting.
Dependencies: scripts.validate_life_meaning_governance.
Invariants: doctrine docs, AGENTS notice, schema, examples, contract, and
kernel remain present and mutually consistent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
MCOI_ROOT = WORKSPACE_ROOT / "mcoi"
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from scripts.validate_life_meaning_governance import (  # noqa: E402
    AGENTS_PATH,
    EXAMPLE_PATHS,
    SCHEMA_PATH,
    validate_life_meaning_governance,
)


def test_life_meaning_governance_validator_passes() -> None:
    validation = validate_life_meaning_governance()

    assert validation.ok is True
    assert validation.errors == ()
    assert SCHEMA_PATH.exists()
    assert len(EXAMPLE_PATHS) == 4


def test_agents_notice_contains_life_meaning_boundary() -> None:
    text = AGENTS_PATH.read_text(encoding="utf-8")

    assert "## Life-Meaning Governance" in text
    assert "Effect-bearing work must consider affected symbols" in text
    assert "missing_life_meaning_judgment" in text
    assert "not automatically classified as life or feeling observers" in text


def test_unknown_life_environment_example_escalates() -> None:
    payload = json.loads(
        (WORKSPACE_ROOT / "examples" / "life_meaning_judgment.unknown_life_environment.json").read_text(
            encoding="utf-8"
        )
    )

    assert payload["decision"] == "escalate"
    assert payload["life_impact"] == "unknown"
    assert payload["irreversible"] is True
    assert payload["rollback_required"] is True


def test_finance_example_remains_handoff_not_live_payment_claim() -> None:
    payload_text = (
        WORKSPACE_ROOT / "examples" / "life_meaning_judgment.finance_payment.json"
    ).read_text(encoding="utf-8").lower()

    assert "finance-payment-handoff" in payload_text
    assert "live payment executed" not in payload_text
    assert "bank settlement completed" not in payload_text
    assert "autonomous payment execution" not in payload_text
