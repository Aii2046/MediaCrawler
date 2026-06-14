# -*- coding: utf-8 -*-
from typing import Optional

from .schemas.response import ErrorCode, ERROR_DESCRIPTIONS


class CrawlerApiException(Exception):
    """Base exception for API-layer errors with structured error codes."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        description: Optional[str] = None,
        platform: Optional[str] = None,
        retry_after_seconds: Optional[int] = None,
        status_code: int = 500,
    ):
        self.code = code
        self.message = message
        self.description = description or ERROR_DESCRIPTIONS.get(code)
        self.platform = platform
        self.retry_after_seconds = retry_after_seconds
        self.status_code = status_code
        super().__init__(message)
