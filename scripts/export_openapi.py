"""Purpose: export the governed FastAPI OpenAPI document deterministically.

Governance scope: SDK source-spec generation only.
Dependencies: mcoi_runtime.app.server and Python standard-library JSON output.
Invariants: the exported spec is sorted, stable, and derived from the runtime
application object rather than a hand-maintained copy.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
MCOI_ROOT = REPO_ROOT / "mcoi"
DEFAULT_OUTPUT = REPO_ROOT / "sdk" / "openapi" / "mullu.openapi.json"


def export_openapi(output_path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    """Export the runtime OpenAPI document to a deterministic JSON file."""
    os.environ.setdefault("MULLU_ENV", "local_dev")
    os.environ.setdefault("MULLU_DB_BACKEND", "memory")
    if str(MCOI_ROOT) not in sys.path:
        sys.path.insert(0, str(MCOI_ROOT))
    from mcoi_runtime.app.server import app

    spec = app.openapi()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(spec, sort_keys=True, indent=2, separators=(",", ": ")) + "\n",
        encoding="utf-8",
    )
    return spec


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Mullu OpenAPI spec for SDK generation.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="OpenAPI JSON output path.",
    )
    args = parser.parse_args()
    spec = export_openapi(args.output)
    operation_count = sum(
        1
        for methods in spec.get("paths", {}).values()
        for method in methods
        if method in {"get", "post", "put", "patch", "delete"}
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "paths": len(spec.get("paths", {})),
                "operations": operation_count,
                "governed": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
