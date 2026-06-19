#!/usr/bin/env python3
"""Validate the aggregate quantum boundary witness chain.

Purpose: compose the Foundation Mode quantum boundary validators into one
reviewable witness index.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: stdlib JSON parsing and the three focused quantum validators.
Invariants: planning only, read only, no source emission, no simulator or
backend execution, no credential access, no job submission, no result claim,
and no terminal closure.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_non_live_local_quantum_simulator_boundary_witness import (  # noqa: E402
    DEFAULT_EXAMPLE as LOCAL_SIMULATOR_EXAMPLE,
)
from scripts.validate_non_live_local_quantum_simulator_boundary_witness import (  # noqa: E402
    validate_payload as validate_local_simulator_payload,
)
from scripts.validate_non_live_openqasm_export_planning_witness import (  # noqa: E402
    DEFAULT_EXAMPLE as OPENQASM_PLANNING_EXAMPLE,
)
from scripts.validate_non_live_openqasm_export_planning_witness import (  # noqa: E402
    validate_payload as validate_openqasm_planning_payload,
)
from scripts.validate_universal_symbolic_quantum_capability_boundary import (  # noqa: E402
    DEFAULT_EXAMPLE as UNIVERSAL_BOUNDARY_EXAMPLE,
)
from scripts.validate_universal_symbolic_quantum_capability_boundary import (  # noqa: E402
    validate_payload as validate_universal_boundary_payload,
)

UNIVERSAL_BOUNDARY_ID = "universal_symbolic_quantum_capability_boundary"
OPENQASM_PLANNING_ID = "non_live_openqasm_export_planning_witness"
LOCAL_SIMULATOR_BOUNDARY_ID = "non_live_local_quantum_simulator_boundary_witness"

QUANTUM_DENIAL_INVARIANTS = (
    "no live QPU execution",
    "no simulator runtime execution",
    "no OpenQASM or QIR source emission",
    "no simulator engine selection",
    "no state-vector materialization",
    "no measurement shot execution",
    "no measurement histogram emission",
    "no backend network call",
    "no hardware credential access",
    "no quantum job submission",
    "no cryptanalysis execution",
    "no quantum advantage claim",
    "no fault-tolerant readiness claim",
    "no production readiness claim",
    "no terminal closure",
)


@dataclass(frozen=True)
class WitnessValidationTarget:
    binding_id: str
    default_path: pathlib.Path
    validate_payload: Callable[[dict[str, Any]], list[str]]


TARGETS = (
    WitnessValidationTarget(
        binding_id=UNIVERSAL_BOUNDARY_ID,
        default_path=UNIVERSAL_BOUNDARY_EXAMPLE,
        validate_payload=validate_universal_boundary_payload,
    ),
    WitnessValidationTarget(
        binding_id=OPENQASM_PLANNING_ID,
        default_path=OPENQASM_PLANNING_EXAMPLE,
        validate_payload=validate_openqasm_planning_payload,
    ),
    WitnessValidationTarget(
        binding_id=LOCAL_SIMULATOR_BOUNDARY_ID,
        default_path=LOCAL_SIMULATOR_EXAMPLE,
        validate_payload=validate_local_simulator_payload,
    ),
)


def _load_json_object(path: pathlib.Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc.msg}") from exc
    except OSError as exc:
        raise ValueError(f"{path}: unable to read JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _validate_target(
    target: WitnessValidationTarget,
    path_overrides: Mapping[str, pathlib.Path],
) -> dict[str, Any]:
    path = pathlib.Path(path_overrides.get(target.binding_id, target.default_path))
    try:
        payload = _load_json_object(path)
    except ValueError as exc:
        errors = [str(exc)]
    else:
        errors = target.validate_payload(payload)

    return {
        "binding_id": target.binding_id,
        "path": str(path),
        "passed": not errors,
        "errors": errors,
    }


def validate_witnesses(paths: Mapping[str, pathlib.Path] | None = None) -> dict[str, Any]:
    """Validate all quantum boundary witnesses and return a receipt object.

    Input contract: optional path overrides keyed by witness binding id.
    Output contract: JSON-serializable receipt with per-witness records.
    Error contract: malformed or unreadable witness files are returned as
    explicit validation errors instead of raising through the CLI boundary.
    """

    path_overrides = paths or {}
    witnesses = [_validate_target(target, path_overrides) for target in TARGETS]
    errors = [
        f"{witness['binding_id']}: {error}"
        for witness in witnesses
        for error in witness["errors"]
    ]

    return {
        "passed": not errors,
        "witness_count": len(witnesses),
        "witnesses": witnesses,
        "errors": errors,
        "invariants": list(QUANTUM_DENIAL_INVARIANTS),
    }


def _build_path_overrides(args: argparse.Namespace) -> dict[str, pathlib.Path]:
    overrides: dict[str, pathlib.Path] = {}
    if args.universal_boundary:
        overrides[UNIVERSAL_BOUNDARY_ID] = pathlib.Path(args.universal_boundary)
    if args.openqasm_planning:
        overrides[OPENQASM_PLANNING_ID] = pathlib.Path(args.openqasm_planning)
    if args.local_simulator_boundary:
        overrides[LOCAL_SIMULATOR_BOUNDARY_ID] = pathlib.Path(args.local_simulator_boundary)
    return overrides


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable validation result")
    parser.add_argument("--universal-boundary", help="override the universal boundary witness path")
    parser.add_argument("--openqasm-planning", help="override the OpenQASM planning witness path")
    parser.add_argument("--local-simulator-boundary", help="override the local simulator boundary witness path")
    args = parser.parse_args(argv)

    result = validate_witnesses(_build_path_overrides(args))

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["errors"]:
        for error in result["errors"]:
            print(f"ERROR: {error}", file=sys.stderr)
    else:
        print("QUANTUM BOUNDARY WITNESSES VALID")

    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
