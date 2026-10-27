from __future__ import annotations

from pydantic import BaseModel


class ToolError(BaseModel):
    code: str
    message: str
    retryable: bool
    suggestion: str
    kind: str  # param | execution


class ToolFailure(Exception):
    """Transient or execution failures (5xx, timeout). Day 10 adds retry."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        self.message = message or f"工具执行失败 ({code})"
        super().__init__(self.message)
