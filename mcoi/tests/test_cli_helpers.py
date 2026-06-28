"""Tests for bounded CLI helper contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.app import cli
from mcoi_runtime.app.cli import CLIDemoError, _load_demo_json_object


def _assert_stage_execution_bindings(body: dict) -> None:
    assert body["stage_execution_bindings"] == [
        {
            "stage_id": stage_id,
            "receipt_ref": receipt_ref,
            "action_class": action_class,
            "boundary": "local_reversible",
            "autonomy_status": "allowed",
            "dispatched": True,
        }
        for stage_id, receipt_ref, action_class in zip(
            body["execution_stage_ids"],
            body["step_receipt_refs"],
            ("execute_read", "plan", "execute_write"),
            strict=True,
        )
    ]


def _assert_stage_verification_bindings(body: dict) -> None:
    assert body["stage_verification_bindings"] == [
        {
            "stage_id": stage_id,
            "receipt_ref": receipt_ref,
            "verification_keys": list(verification_keys),
        }
        for stage_id, receipt_ref, verification_keys in zip(
            body["execution_stage_ids"],
            body["step_receipt_refs"],
            (
                ("operator_run_report", "local_observation"),
                ("operator_run_report", "plan_trace"),
                ("operator_run_report", "local_effect_trace"),
            ),
            strict=True,
        )
    ]


def _assert_stage_policy_bindings(body: dict) -> None:
    expected_bindings = [
        {"stage_id": stage_id, "receipt_ref": receipt_ref}
        for stage_id, receipt_ref in zip(
            body["execution_stage_ids"],
            body["step_receipt_refs"],
            strict=True,
        )
    ]
    assert len(body["stage_policy_bindings"]) == 3
    for binding, expected_binding in zip(body["stage_policy_bindings"], expected_bindings, strict=True):
        assert binding["stage_id"] == expected_binding["stage_id"]
        assert binding["receipt_ref"] == expected_binding["receipt_ref"]
        assert binding["autonomy_decision_id"].startswith("autonomy-")
        assert binding["autonomy_status"] == "allowed"
        assert binding["autonomy_reason"] == "autonomous local mode: local action allowed within scope"


def test_load_demo_json_object_bounds_invalid_root_type() -> None:
    with pytest.raises(CLIDemoError, match="^invalid JSON response root$") as exc_info:
        _load_demo_json_object(b"[]")
    assert "list" not in str(exc_info.value).lower()


def test_autonomous_demo_renders_local_continuation_summary(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main(
        [
            "autonomous-demo",
            "--target",
            "workspace",
            "--objective",
            "prepare local change",
            "--change",
            "apply local patch",
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Autonomous Request Episode Summary" in output
    assert "automation_state:   settled_without_prompt" in output
    assert "workflow_stages:    3" in output
    assert "approval_stages:    0" in output
    assert "external_stages:    0" in output
    assert "prompt_count:       0" in output


def test_autonomous_demo_renders_json_continuation_summary(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main(
        [
            "autonomous-demo",
            "--target",
            "workspace",
            "--objective",
            "prepare local change",
            "--change",
            "apply local patch",
            "--json",
        ]
    )

    body = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert body["operation"] == "autonomous-demo"
    assert body["receipt_schema_version"] == "mcoi.autonomous_demo.receipt.v1"
    assert body["capability_ids"] == ["local.apply"]
    assert body["automation_state"] == "settled_without_prompt"
    assert body["workflow_stage_count"] == 3
    assert body["workflow_approval_stage_count"] == 0
    assert body["workflow_external_stage_count"] == 0
    assert body["execution_stage_ids"] == [
        "stage-local.inspect",
        "stage-local.plan",
        "stage-local.apply",
    ]
    assert len(body["step_receipt_refs"]) == 3
    assert all(ref.startswith("receipt://") for ref in body["step_receipt_refs"])
    assert body["stage_receipt_bindings"] == [
        {"stage_id": stage_id, "receipt_ref": receipt_ref}
        for stage_id, receipt_ref in zip(body["execution_stage_ids"], body["step_receipt_refs"], strict=True)
    ]
    _assert_stage_execution_bindings(body)
    _assert_stage_verification_bindings(body)
    _assert_stage_policy_bindings(body)
    assert body["prompt_count"] == 0
    assert "receipt_path" not in body
    assert body["workflow_descriptor_ref"].startswith("workflow://")
    assert body["rollback_ref"].endswith("/local-effects")


def test_autonomous_demo_writes_json_receipt_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    receipt_path = tmp_path / "autonomous-demo-receipt.json"

    exit_code = cli.main(
        [
            "autonomous-demo",
            "--target",
            "workspace",
            "--objective",
            "prepare local change",
            "--change",
            "apply local patch",
            "--receipt-path",
            str(receipt_path),
        ]
    )

    output = capsys.readouterr().out
    body = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "Autonomous Request Episode Summary" in output
    assert body["operation"] == "autonomous-demo"
    assert body["receipt_schema_version"] == "mcoi.autonomous_demo.receipt.v1"
    assert body["capability_ids"] == ["local.apply"]
    assert body["automation_state"] == "settled_without_prompt"
    assert body["prompt_count"] == 0
    assert body["receipt_path"] == str(receipt_path)
    assert body["execution_stage_ids"] == [
        "stage-local.inspect",
        "stage-local.plan",
        "stage-local.apply",
    ]
    assert len(body["step_receipt_refs"]) == 3
    assert all(ref.startswith("receipt://") for ref in body["step_receipt_refs"])
    assert body["stage_receipt_bindings"] == [
        {"stage_id": stage_id, "receipt_ref": receipt_ref}
        for stage_id, receipt_ref in zip(body["execution_stage_ids"], body["step_receipt_refs"], strict=True)
    ]
    _assert_stage_execution_bindings(body)
    _assert_stage_verification_bindings(body)
    _assert_stage_policy_bindings(body)
    assert body["workflow_descriptor_ref"].startswith("workflow://")
    assert body["rollback_ref"].endswith("/local-effects")


def test_autonomous_demo_quiet_writes_receipt_without_stdout(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    receipt_path = tmp_path / "autonomous-demo-receipt.json"

    exit_code = cli.main(
        [
            "autonomous-demo",
            "--target",
            "workspace",
            "--objective",
            "prepare local change",
            "--change",
            "apply local patch",
            "--receipt-path",
            str(receipt_path),
            "--quiet",
        ]
    )

    captured = capsys.readouterr()
    body = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert captured.out == ""
    assert captured.err == ""
    assert body["operation"] == "autonomous-demo"
    assert body["receipt_schema_version"] == "mcoi.autonomous_demo.receipt.v1"
    assert body["capability_ids"] == ["local.apply"]
    assert body["automation_state"] == "settled_without_prompt"
    assert body["prompt_count"] == 0
    assert body["receipt_path"] == str(receipt_path)
    assert body["execution_stage_ids"] == [
        "stage-local.inspect",
        "stage-local.plan",
        "stage-local.apply",
    ]
    assert len(body["step_receipt_refs"]) == 3
    assert all(ref.startswith("receipt://") for ref in body["step_receipt_refs"])
    assert body["stage_receipt_bindings"] == [
        {"stage_id": stage_id, "receipt_ref": receipt_ref}
        for stage_id, receipt_ref in zip(body["execution_stage_ids"], body["step_receipt_refs"], strict=True)
    ]
    _assert_stage_execution_bindings(body)
    _assert_stage_verification_bindings(body)
    _assert_stage_policy_bindings(body)


def test_autonomous_demo_receipt_dir_derives_filename_and_creates_directory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    receipt_dir = tmp_path / "receipts" / "autonomous"

    exit_code = cli.main(
        [
            "autonomous-demo",
            "--episode-id",
            "episode/demo:local",
            "--receipt-dir",
            str(receipt_dir),
            "--quiet",
        ]
    )

    captured = capsys.readouterr()
    receipt_path = receipt_dir / "episode_demo_local.json"
    body = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert captured.out == ""
    assert captured.err == ""
    assert receipt_path.exists()
    assert body["receipt_schema_version"] == "mcoi.autonomous_demo.receipt.v1"
    assert body["capability_ids"] == ["local.apply"]
    assert body["episode_id"] == "episode/demo:local"
    assert body["receipt_directory_path"] == str(receipt_dir)
    assert body["receipt_path"] == str(receipt_path)
    assert body["execution_stage_ids"] == [
        "stage-local.inspect",
        "stage-local.plan",
        "stage-local.apply",
    ]
    assert len(body["step_receipt_refs"]) == 3
    assert all(ref.startswith("receipt://") for ref in body["step_receipt_refs"])
    assert body["stage_receipt_bindings"] == [
        {"stage_id": stage_id, "receipt_ref": receipt_ref}
        for stage_id, receipt_ref in zip(body["execution_stage_ids"], body["step_receipt_refs"], strict=True)
    ]
    _assert_stage_execution_bindings(body)
    _assert_stage_verification_bindings(body)
    _assert_stage_policy_bindings(body)
    assert body["automation_state"] == "settled_without_prompt"


def test_autonomous_demo_receipt_dir_writes_latest_receipt(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    receipt_dir = tmp_path / "receipts" / "autonomous"

    exit_code = cli.main(
        [
            "autonomous-demo",
            "--episode-id",
            "episode-latest",
            "--receipt-dir",
            str(receipt_dir),
            "--receipt-latest-name",
            "latest.json",
            "--quiet",
        ]
    )

    captured = capsys.readouterr()
    receipt_path = receipt_dir / "episode-latest.json"
    latest_path = receipt_dir / "latest.json"
    receipt_body = json.loads(receipt_path.read_text(encoding="utf-8"))
    latest_body = json.loads(latest_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert captured.out == ""
    assert captured.err == ""
    assert receipt_body["receipt_schema_version"] == "mcoi.autonomous_demo.receipt.v1"
    assert receipt_body["capability_ids"] == ["local.apply"]
    assert receipt_body["receipt_directory_path"] == str(receipt_dir)
    assert receipt_body["receipt_path"] == str(receipt_path)
    assert receipt_body["latest_receipt_path"] == str(latest_path)
    assert receipt_body["execution_stage_ids"] == [
        "stage-local.inspect",
        "stage-local.plan",
        "stage-local.apply",
    ]
    assert len(receipt_body["step_receipt_refs"]) == 3
    assert all(ref.startswith("receipt://") for ref in receipt_body["step_receipt_refs"])
    assert receipt_body["stage_receipt_bindings"] == [
        {"stage_id": stage_id, "receipt_ref": receipt_ref}
        for stage_id, receipt_ref in zip(
            receipt_body["execution_stage_ids"],
            receipt_body["step_receipt_refs"],
            strict=True,
        )
    ]
    _assert_stage_execution_bindings(receipt_body)
    _assert_stage_verification_bindings(receipt_body)
    _assert_stage_policy_bindings(receipt_body)
    assert latest_body["receipt_directory_path"] == str(receipt_dir)
    assert latest_body["receipt_schema_version"] == "mcoi.autonomous_demo.receipt.v1"
    assert latest_body["capability_ids"] == ["local.apply"]
    assert latest_body["receipt_path"] == str(receipt_path)
    assert latest_body["latest_receipt_path"] == str(latest_path)
    assert latest_body["execution_stage_ids"] == [
        "stage-local.inspect",
        "stage-local.plan",
        "stage-local.apply",
    ]
    assert latest_body["step_receipt_refs"] == receipt_body["step_receipt_refs"]
    assert latest_body["stage_receipt_bindings"] == receipt_body["stage_receipt_bindings"]
    assert latest_body["stage_execution_bindings"] == receipt_body["stage_execution_bindings"]
    assert latest_body["stage_verification_bindings"] == receipt_body["stage_verification_bindings"]
    assert latest_body["stage_policy_bindings"] == receipt_body["stage_policy_bindings"]
    assert latest_body["automation_state"] == "settled_without_prompt"


def test_autonomous_demo_latest_receipt_requires_receipt_dir(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["autonomous-demo", "--receipt-latest-name", "latest.json"])

    captured = capsys.readouterr()

    assert exc_info.value.code == 1
    assert "autonomous demo latest receipt requires --receipt-dir" in captured.err
    assert captured.out == ""


def test_autonomous_demo_rejects_unsafe_latest_receipt_name(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "autonomous-demo",
                "--receipt-dir",
                str(tmp_path),
                "--receipt-latest-name",
                "../latest.json",
            ]
        )

    captured = capsys.readouterr()

    assert exc_info.value.code == 1
    assert "autonomous demo latest receipt name must be a filename" in captured.err
    assert captured.out == ""


def test_autonomous_demo_rejects_ambiguous_receipt_targets(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "autonomous-demo",
                "--receipt-path",
                str(tmp_path / "receipt.json"),
                "--receipt-dir",
                str(tmp_path),
            ]
        )

    captured = capsys.readouterr()

    assert exc_info.value.code == 1
    assert "autonomous demo accepts either --receipt-path or --receipt-dir" in captured.err
    assert captured.out == ""


def test_autonomous_demo_quiet_requires_receipt_path(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["autonomous-demo", "--quiet"])

    captured = capsys.readouterr()

    assert exc_info.value.code == 1
    assert "quiet autonomous demo requires --receipt-path or --receipt-dir" in captured.err
    assert captured.out == ""


def test_autonomous_demo_receipt_path_write_failure_is_bounded(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing_parent_path = tmp_path / "missing" / "autonomous-demo-receipt.json"

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["autonomous-demo", "--receipt-path", str(missing_parent_path)])

    captured = capsys.readouterr()

    assert exc_info.value.code == 1
    assert "cannot write autonomous demo receipt: file not found" in captured.err
    assert captured.out == ""


def test_autonomous_demo_rejects_negative_retry_count(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["autonomous-demo", "--max-local-retries", "-1"])

    captured = capsys.readouterr()

    assert exc_info.value.code == 1
    assert "max-local-retries must be non-negative" in captured.err
    assert captured.out == ""


def test_demo_command_blocks_proxy_environment_before_http(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setenv("MULLU_ENV", "production")
    monkeypatch.setenv("HTTPS_PROXY", "http://user:secret@proxy.internal:8080")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("demo command should block before urlopen")

    monkeypatch.setattr("urllib.request.urlopen", fail_if_called)

    result = cli.demo_command(type("Args", (), {"url": "http://localhost:8000"})())
    captured = capsys.readouterr()

    assert result == 1
    assert "proxy environment blocked:HTTPS_PROXY" in captured.out
    assert "secret" not in captured.out
    assert "proxy.internal" not in captured.out
