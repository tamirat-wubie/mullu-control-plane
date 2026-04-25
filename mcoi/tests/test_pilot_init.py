"""Purpose: verify one-command pilot bring-up scaffolding.

Governance scope: local pilot artifact generation and CLI routing only.
Dependencies: pilot_init module and CLI parser.
Invariants: generated files are deterministic; existing files fail closed unless
forced; tenant, policy, budget, dashboard, audit, and lineage artifacts exist.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.app.cli import main
from mcoi_runtime.app.pilot_init import PILOT_FILE_NAMES, PilotInitRequest, initialize_pilot


def _request(output_dir: Path, *, force: bool = False) -> PilotInitRequest:
    return PilotInitRequest(
        tenant_id="tenant-pilot",
        pilot_name="Acme Pilot",
        output_dir=output_dir,
        policy_pack_id="default-safe",
        policy_version="v0.1",
        max_cost=250.0,
        max_calls=500,
        force=force,
    )


def test_initialize_pilot_writes_complete_artifact_set(tmp_path: Path) -> None:
    result = initialize_pilot(_request(tmp_path / "pilot"))
    written_names = {path.name for path in result.files_written}

    assert result.pilot_id.startswith("pilot-")
    assert written_names == set(PILOT_FILE_NAMES)
    assert result.manifest_path.exists()
    assert json.loads((tmp_path / "pilot" / "tenant.json").read_text(encoding="utf-8"))["tenant_id"] == "tenant-pilot"
    assert json.loads((tmp_path / "pilot" / "budget.json").read_text(encoding="utf-8"))["max_cost"] == 250.0


def test_initialize_pilot_is_deterministic_for_same_inputs(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    first = initialize_pilot(_request(first_dir))
    second = initialize_pilot(_request(second_dir))

    assert first.pilot_id == second.pilot_id
    assert (first_dir / "pilot.manifest.json").read_text(encoding="utf-8") == (
        second_dir / "pilot.manifest.json"
    ).read_text(encoding="utf-8")
    assert (first_dir / "policy.json").read_text(encoding="utf-8") == (second_dir / "policy.json").read_text(
        encoding="utf-8"
    )


def test_initialize_pilot_fails_closed_on_existing_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "pilot"
    initialize_pilot(_request(output_dir))
    tenant_path = output_dir / "tenant.json"
    original_tenant = tenant_path.read_text(encoding="utf-8")

    with pytest.raises(FileExistsError, match="existing files"):
        initialize_pilot(_request(output_dir))

    assert tenant_path.read_text(encoding="utf-8") == original_tenant
    assert len(list(output_dir.iterdir())) == len(PILOT_FILE_NAMES)


def test_initialize_pilot_force_overwrites_existing_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "pilot"
    initialize_pilot(_request(output_dir))
    (output_dir / "tenant.json").write_text("{}", encoding="utf-8")

    result = initialize_pilot(_request(output_dir, force=True))
    tenant = json.loads((output_dir / "tenant.json").read_text(encoding="utf-8"))

    assert result.manifest_path.exists()
    assert tenant["tenant_id"] == "tenant-pilot"
    assert tenant["status"] == "scaffolded"


def test_cli_pilot_init_routes_to_scaffold(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output_dir = tmp_path / "pilot"

    exit_code = main(
        [
            "pilot",
            "init",
            "--tenant-id",
            "tenant-pilot",
            "--name",
            "Acme Pilot",
            "--output",
            str(output_dir),
        ]
    )
    captured = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert captured["governed"] is True
    assert captured["pilot_id"].startswith("pilot-")
    assert (output_dir / "lineage_examples.json").exists()


def test_cli_pilot_without_subcommand_fails_closed(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["pilot"])
    captured = capsys.readouterr()

    assert exc_info.value.code == 1
    assert "pilot subcommand is required" in captured.err
    assert captured.out == ""
