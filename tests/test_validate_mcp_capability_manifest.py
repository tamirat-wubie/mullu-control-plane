"""MCP capability manifest validation tests.

Tests: operator-facing MCP manifest validation and CLI evidence output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_mcp_capability_manifest import (  # noqa: E402
    main,
    validate_mcp_capability_manifest,
)


def test_validate_mcp_capability_manifest_accepts_example() -> None:
    manifest_path = Path("examples") / "mcp_capability_manifest.json"

    result = validate_mcp_capability_manifest(manifest_path)

    assert result.ok is True
    assert result.capability_ids == ("mcp.docs_search_docs",)
    assert result.ownership_resource_refs == ("mcp.docs_search_docs",)
    assert len(result.approval_policy_ids) == 1
    assert result.escalation_policy_ids == ("mcp-escalation-tenant-1",)
    assert result.errors == ()


def test_validate_mcp_capability_manifest_rejects_missing_certification(tmp_path: Path) -> None:
    manifest_path = tmp_path / "mcp_manifest_missing_certification.json"
    manifest_path.write_text(
        json.dumps({
            "tenant_id": "tenant-1",
            "primary_owner_id": "owner-1",
            "fallback_owner_id": "owner-2",
            "escalation_team": "platform-ops",
            "certification_evidence_ref": "evidence:mcp-docs-search",
            "tools": [{
                "server_id": "Docs",
                "name": "Search Docs",
                "description": "Search internal documents.",
                "input_schema": {"type": "object"},
            }],
        }),
        encoding="utf-8",
    )

    result = validate_mcp_capability_manifest(manifest_path)

    assert result.ok is False
    assert result.capability_ids == ()
    assert result.ownership_resource_refs == ()
    assert result.approval_policy_ids == ()
    assert result.escalation_policy_ids == ()
    assert result.errors == ("MCP manifest requires a configured string field",)


def test_validate_mcp_capability_manifest_cli_outputs_json(capsys) -> None:
    exit_code = main([
        "--manifest",
        str(Path("examples") / "mcp_capability_manifest.json"),
        "--json",
    ])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["capability_count"] == 1
    assert payload["ownership_count"] == 1
    assert payload["approval_policy_count"] == 1
    assert payload["capability_ids"] == ["mcp.docs_search_docs"]


def test_validate_mcp_capability_manifest_cli_fails_invalid(tmp_path: Path, capsys) -> None:
    manifest_path = tmp_path / "invalid_mcp_manifest.json"
    manifest_path.write_text(json.dumps({"tools": []}), encoding="utf-8")

    exit_code = main(["--manifest", str(manifest_path)])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "error:" in captured.out
    assert "MCP manifest requires at least one tool" in captured.out
    assert captured.err == ""
