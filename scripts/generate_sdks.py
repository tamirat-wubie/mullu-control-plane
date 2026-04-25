"""Purpose: run configured SDK generators from the exported OpenAPI document.

Governance scope: Python and TypeScript SDK generation orchestration only.
Dependencies: local generator CLIs declared in sdk/sdk-generation.json.
Invariants: SDKs are generated from OpenAPI; commands are explicit; dry-run is
side-effect free; missing generator tools fail with bounded diagnostics.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "sdk" / "sdk-generation.json"


@dataclass(frozen=True, slots=True)
class SdkGenerator:
    """Configured SDK generator command."""

    language: str
    package_name: str
    spec_path: Path
    output_path: Path
    command: tuple[str, ...]

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> SdkGenerator:
        return cls(
            language=str(payload["language"]),
            package_name=str(payload["package_name"]),
            spec_path=REPO_ROOT / str(payload["spec_path"]),
            output_path=REPO_ROOT / str(payload["output_path"]),
            command=tuple(str(part) for part in payload["command"]),
        )

    def validate(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if not self.spec_path.exists():
            reasons.append("openapi_spec_missing")
        if not self.command:
            reasons.append("generator_command_missing")
        elif shutil.which(self.command[0]) is None:
            reasons.append("generator_executable_missing")
        return tuple(reasons)


def load_generators(manifest_path: Path = MANIFEST_PATH) -> tuple[SdkGenerator, ...]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return tuple(SdkGenerator.from_mapping(item) for item in payload["generators"])


def run_generators(*, languages: set[str] | None = None, dry_run: bool = False) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for generator in load_generators():
        if languages is not None and generator.language not in languages:
            continue
        reasons = generator.validate()
        result = {
            "language": generator.language,
            "package_name": generator.package_name,
            "command": list(generator.command),
            "ready": not reasons,
            "reasons": list(reasons),
            "dry_run": dry_run,
        }
        if not dry_run and not reasons:
            completed = subprocess.run(
                generator.command,
                cwd=REPO_ROOT,
                check=False,
                text=True,
                capture_output=True,
            )
            result["returncode"] = completed.returncode
            result["ready"] = completed.returncode == 0
            if completed.returncode != 0:
                result["reasons"] = ["generator_failed"]
        results.append(result)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Python and TypeScript SDKs from OpenAPI.")
    parser.add_argument("--language", action="append", choices=("python", "typescript"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    results = run_generators(languages=set(args.language) if args.language else None, dry_run=args.dry_run)
    print(json.dumps({"governed": True, "generators": results}, sort_keys=True, indent=2))
    return 0 if all(result["ready"] or args.dry_run for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
