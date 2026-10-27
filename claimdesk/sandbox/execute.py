from __future__ import annotations

import json
import os
import re
import subprocess
import sys

_NETWORK = re.compile(r"169\.254\.169\.254|socket|(?:^|[^0-9])10\.\d")
_IMPORT = re.compile(r"__import__|(^|\n)\s*import\s+|os\.environ")
_RUNNER = r"""
import json
import sys
payload = json.loads(sys.stdin.read())
safe_builtins = {
    "sum": sum,
    "len": len,
    "min": min,
    "max": max,
    "range": range,
    "list": list,
    "dict": dict,
    "int": int,
    "float": float,
}
scope = {"__builtins__": safe_builtins, "invoices": payload["invoices"]}
try:
    exec(payload["code"], scope, scope)
except Exception:
    sys.stdout.write(json.dumps({"ok": False, "reason": "import"}))
else:
    sys.stdout.write(json.dumps({"ok": True, "total": scope.get("total")}))
"""


def _rejected(reason: str) -> dict:
    return {"ok": False, "reason": reason}


def execute_python(code: str, invoices: list[int]) -> dict:
    if _NETWORK.search(code):
        return _rejected("network")
    if _IMPORT.search(code):
        return _rejected("import")
    env = {
        key: value
        for key, value in os.environ.items()
        if "SECRET" not in key and "KEY" not in key and "TOKEN" not in key
    }
    try:
        completed = subprocess.run(
            [sys.executable, "-c", _RUNNER],
            input=json.dumps({"code": code, "invoices": invoices}),
            text=True,
            capture_output=True,
            timeout=1,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _rejected("timeout")
    secret = os.environ.get("CLAIMDESK_SECRET", "")
    if secret and secret in (completed.stdout or ""):
        return _rejected("import")
    if not completed.stdout:
        return _rejected("import")
    return json.loads(completed.stdout)


def sum_invoices(invoices: list[int]) -> dict:
    if not all(isinstance(item, int) for item in invoices):
        return _rejected("import")
    return execute_python("total = sum(invoices)", invoices)
