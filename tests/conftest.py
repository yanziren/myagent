"""Make `claimdesk` importable when pytest is run without `pip install -e .`."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_root = str(_ROOT)
if _root not in sys.path:
    sys.path.insert(0, _root)
