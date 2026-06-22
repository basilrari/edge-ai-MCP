"""Uniform JSON responses for MCP tools."""

from __future__ import annotations

import json
from typing import Any


def ok(data: Any | None = None) -> str:
    return json.dumps({"ok": True, "data": data if data is not None else {}})


def err(message: str, **extra: Any) -> str:
    body: dict[str, Any] = {"ok": False, "error": message}
    body.update(extra)
    return json.dumps(body)
