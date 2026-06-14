# -*- coding: utf-8 -*-
from enum import Enum
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorCode(str, Enum):
    """Structured error codes for all failure scenarios."""

    # General errors (1xxx)
    UNKNOWN_ERROR = "ERR_1000"
    VALIDATION_ERROR = "ERR_1001"
    NOT_FOUND = "ERR_1002"
    PERMISSION_DENIED = "ERR_1003"

    # Crawler lifecycle errors (2xxx)
    CRAWLER_ALREADY_RUNNING = "ERR_2001"
    CRAWLER_NOT_RUNNING = "ERR_2002"
    CRAWLER_START_FAILED = "ERR_2003"
    CRAWLER_STOP_FAILED = "ERR_2004"

    # Platform/network errors (3xxx)
    IP_BLOCKED = "ERR_3001"
    RATE_LIMITED = "ERR_3002"
    LOGIN_EXPIRED = "ERR_3003"
    CAPTCHA_REQUIRED = "ERR_3004"
    ACCOUNT_BANNED = "ERR_3005"
    PROXY_FAILED = "ERR_3006"

    # Data errors (4xxx)
    DATA_FETCH_ERROR = "ERR_4001"
    NOTE_NOT_FOUND = "ERR_4002"
    DATA_PARSE_ERROR = "ERR_4003"
    FORBIDDEN_CONTENT = "ERR_4004"

    # File/storage errors (5xxx)
    FILE_NOT_FOUND = "ERR_5001"
    FILE_ACCESS_DENIED = "ERR_5002"
    FILE_TYPE_UNSUPPORTED = "ERR_5003"
    FILE_PARSE_ERROR = "ERR_5004"


# Human-readable descriptions for each error code
ERROR_DESCRIPTIONS = {
    ErrorCode.UNKNOWN_ERROR: "An unexpected error occurred. Please try again or contact support.",
    ErrorCode.VALIDATION_ERROR: "The request parameters are invalid. Please check your input.",
    ErrorCode.NOT_FOUND: "The requested resource was not found.",
    ErrorCode.PERMISSION_DENIED: "Access to the requested resource is denied.",
    ErrorCode.CRAWLER_ALREADY_RUNNING: "A crawler task is already running. Please stop it first or wait for it to finish.",
    ErrorCode.CRAWLER_NOT_RUNNING: "No crawler task is currently running.",
    ErrorCode.CRAWLER_START_FAILED: "Failed to start the crawler. Check logs for details.",
    ErrorCode.CRAWLER_STOP_FAILED: "Failed to stop the crawler. The process may need to be killed manually.",
    ErrorCode.IP_BLOCKED: "Your IP address has been blocked by the target platform. Consider using a proxy or waiting before retrying.",
    ErrorCode.RATE_LIMITED: "Request rate limit exceeded. The crawler will automatically retry after a delay.",
    ErrorCode.LOGIN_EXPIRED: "Login session has expired. Please re-login with fresh cookies or QR code.",
    ErrorCode.CAPTCHA_REQUIRED: "The platform requires CAPTCHA verification. Please complete it manually in the browser.",
    ErrorCode.ACCOUNT_BANNED: "The account has been banned or restricted by the platform.",
    ErrorCode.PROXY_FAILED: "Failed to acquire or connect through proxy IP. Check proxy pool configuration.",
    ErrorCode.DATA_FETCH_ERROR: "Failed to fetch data from the platform API. The request may have been rejected.",
    ErrorCode.NOTE_NOT_FOUND: "The specified note/post does not exist or has been deleted/hidden.",
    ErrorCode.DATA_PARSE_ERROR: "Failed to parse the response data. The platform API format may have changed.",
    ErrorCode.FORBIDDEN_CONTENT: "Access to this content is forbidden. It may be private or restricted.",
    ErrorCode.FILE_NOT_FOUND: "The specified data file was not found on disk.",
    ErrorCode.FILE_ACCESS_DENIED: "Access to this file path is denied for security reasons.",
    ErrorCode.FILE_TYPE_UNSUPPORTED: "This file type is not supported for preview.",
    ErrorCode.FILE_PARSE_ERROR: "Failed to parse the file content. The file may be corrupted.",
}


class ErrorDetail(BaseModel):
    """Structured error information returned to the client."""

    code: ErrorCode
    message: str
    description: Optional[str] = None
    platform: Optional[str] = None
    retry_after_seconds: Optional[int] = None


class ApiResponse(BaseModel):
    """Unified API response envelope."""

    success: bool
    data: Optional[Any] = None
    error: Optional[ErrorDetail] = None

    @classmethod
    def ok(cls, data: Any = None) -> "ApiResponse":
        return cls(success=True, data=data)

    @classmethod
    def fail(
        cls,
        code: ErrorCode,
        message: str,
        description: Optional[str] = None,
        platform: Optional[str] = None,
        retry_after_seconds: Optional[int] = None,
    ) -> "ApiResponse":
        if description is None:
            description = ERROR_DESCRIPTIONS.get(code)
        return cls(
            success=False,
            error=ErrorDetail(
                code=code,
                message=message,
                description=description,
                platform=platform,
                retry_after_seconds=retry_after_seconds,
            ),
        )
