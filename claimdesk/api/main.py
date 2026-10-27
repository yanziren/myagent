"""Local dev: `.venv/bin/uvicorn claimdesk.api.main:app --reload --port 8000`"""

from __future__ import annotations

import os
from pathlib import Path

from claimdesk.api.app import create_app

_ROOT = Path(__file__).resolve().parents[2]
_db = Path(os.environ.get("CLAIMDESK_DB", _ROOT / "data" / "claims.sqlite"))
_db.parent.mkdir(parents=True, exist_ok=True)

app = create_app(db_path=str(_db))
