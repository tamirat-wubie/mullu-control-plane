"""Purpose: make the local MCOI package importable during contract tests.
Governance scope: Milestone 1 test support only.
Dependencies: Python standard library path handling.
Invariants: test imports remain explicit and deterministic across environments.
"""

from __future__ import annotations

import sys
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parent.parent
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))
