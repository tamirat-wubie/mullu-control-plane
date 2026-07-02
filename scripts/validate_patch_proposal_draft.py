#!/usr/bin/env python3
"""Validate a standalone patch proposal draft artifact.

Purpose: verify schema and no-authority semantics for patch proposal drafts.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/software_dev_patch_proposal.schema.json and
software_dev.patch_proposal.runner.
Invariants: validation rejects applied diffs, executed tests, rollback
overclaims, source mutation, branch push, PR creation, merge, deployment,
connector calls, external writes, and live execution.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402
from software_dev.patch_proposal.runner import (  # noqa: E402
    ARTIFACT_FILENAME,
    collect_patch_proposal_draft,
    validate_patch_proposal_draft as validate_proposal_semantics,
)


DEFAULT_ARTIFACT = REPO_ROOT / ".change_assurance" / ARTIFACT_FILENAME
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "software_dev_patch_proposal.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "software_dev_patch_proposal_draft_validation.json"


@dataclass(frozen=True, slots=True)
class PatchProposalDraftFileValidation:
    """Validation report for a patch proposal draft file."""

    ok: bool
    errors: tuple[str, ...]
    artifact_path: str
    proposal_id: str
    proposal_status: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_patch_proposal_draft_file(
    *,
    artifact_path: Path,
    schema_path: Path = DEFAULT_SCHEMA,
) -> PatchProposalDraftFileValidation:
    """Validate a patch proposal draft file."""

    errors: list[str] = []
    proposal = _load_json_object(artifact_path)
    schema = _load_json_object(schema_path)
    errors.extend(str(error) for error in _validate_schema_instance(schema, proposal))
    semantic_validation = validate_proposal_semantics(proposal, artifact_path=artifact_path)
    errors.extend(semantic_validation.errors)
    return PatchProposalDraftFileValidation(
        ok=not errors,
        errors=tuple(errors),
        artifact_path=_path_label(artifact_path),
        proposal_id=str(proposal.get("proposal_id") or ""),
        proposal_status=str(proposal.get("proposal_status") or ""),
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse patch proposal validator arguments."""

    parser = argparse.ArgumentParser(description="Validate a patch proposal draft artifact.")
    parser.add_argument("--artifact", default=str(DEFAULT_ARTIFACT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--build-if-missing", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for patch proposal validation."""

    args = parse_args(argv)
    artifact_path = Path(args.artifact)
    if args.build_if_missing and not artifact_path.exists():
        proposal = collect_patch_proposal_draft(repo_root=REPO_ROOT)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    validation = validate_patch_proposal_draft_file(
        artifact_path=artifact_path,
        schema_path=Path(args.schema),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("PATCH PROPOSAL DRAFT VALID")
    else:
        print(f"PATCH PROPOSAL DRAFT INVALID errors={list(validation.errors)}")
    return 0 if validation.ok or not args.strict else 2


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"json_parse_failed:{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"json_root_must_be_object:{path}")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
