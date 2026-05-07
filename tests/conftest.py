"""Top-level test conftest — adds project paths for all test suites."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_MCOI = _ROOT / "mcoi"

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_MCOI) not in sys.path:
    sys.path.insert(0, str(_MCOI))
