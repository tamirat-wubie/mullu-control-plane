#!/usr/bin/env python3
"""Validate a projection-only PR readiness bundle.

Purpose: prove the operator-facing readiness bundle links all Developer
Workflow PR artifacts without executing external effects.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: PR readiness bundle schema and semantic validator.
Invariants: readiness validation does not push branches or open pull requests.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_pr_readiness_bundle import (  # noqa: E402
    DEFAULT_SCHEMA,
    PrReadinessBundleValidation,
    validate_pr_readiness_bundle as validate_bundle_object,
)


DEFAULT_BUNDLE = REPO_ROOT / "examples" / "pr_readiness_bundle.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "pr_readiness_bundle_validation.json"


def validate_pr_readiness_bundle(
    *,
    bundle_path: Path = DEFAULT_BUNDLE,
    schema_path: Path = DEFAULT_SCHEMA,
) -> PrReadinessBundleValidation:
    """Validate a PR readiness bundle file."""

    bundle = _load_json_object(bundle_path)
    return validate_bundle_object(bundle=bundle, schema_path=schema_path, bundle_path=bundle_path)


def write_pr_readiness_bundle_validation(validation: PrReadinessBundleValidation, output_path: Path) -> Path:
    """Write a deterministic validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _load_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"json_parse_failed:{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("json_root_must_be_object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse PR readiness bundle validation arguments."""

    parser = argparse.ArgumentParser(description="Validate PR readiness bundle.")
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for PR readiness bundle validation."""

    args = parse_args(argv)
    validation = validate_pr_readiness_bundle(bundle_path=Path(args.bundle), schema_path=Path(args.schema))
    write_pr_readiness_bundle_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("PR READINESS BUNDLE VALID")
    else:
        print(f"PR READINESS BUNDLE INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
