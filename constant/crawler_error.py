# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/constant/crawler_error.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

from enum import Enum


class CrawlerErrorCode(str, Enum):
    """Unified crawler error codes shared across all platforms and the API layer."""

    # --- Authentication / Session ---
    LOGIN_EXPIRED = "LOGIN_EXPIRED"
    LOGIN_FAILED = "LOGIN_FAILED"
    COOKIE_INVALID = "COOKIE_INVALID"

    # --- Network / Access ---
    IP_BLOCKED = "IP_BLOCKED"
    RATE_LIMITED = "RATE_LIMITED"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"

    # --- Data ---
    DATA_NOT_FOUND = "DATA_NOT_FOUND"
    DATA_PARSE_ERROR = "DATA_PARSE_ERROR"
    CONTENT_REMOVED = "CONTENT_REMOVED"
    ACCOUNT_BANNED = "ACCOUNT_BANNED"

    # --- Platform API ---
    PLATFORM_ERROR = "PLATFORM_ERROR"
    API_CHANGED = "API_CHANGED"

    # --- Configuration / Input ---
    INVALID_CONFIG = "INVALID_CONFIG"
    INVALID_INPUT = "INVALID_INPUT"

    # --- System ---
    BROWSER_ERROR = "BROWSER_ERROR"
    STORAGE_ERROR = "STORAGE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNKNOWN = "UNKNOWN"


ERROR_DESCRIPTIONS = {
    CrawlerErrorCode.LOGIN_EXPIRED: "登录会话已过期，请重新登录 / Login session expired, please re-login",
    CrawlerErrorCode.LOGIN_FAILED: "登录失败 / Login failed",
    CrawlerErrorCode.COOKIE_INVALID: "Cookie无效或已过期 / Cookie is invalid or expired",
    CrawlerErrorCode.IP_BLOCKED: "IP被平台封禁，请尝试使用代理或等待解封 / IP blocked by platform, try proxy or wait",
    CrawlerErrorCode.RATE_LIMITED: "请求过于频繁，已被限流 / Too many requests, rate limited",
    CrawlerErrorCode.NETWORK_ERROR: "网络连接错误 / Network connection error",
    CrawlerErrorCode.TIMEOUT: "请求超时 / Request timeout",
    CrawlerErrorCode.DATA_NOT_FOUND: "请求的数据未找到 / Requested data not found",
    CrawlerErrorCode.DATA_PARSE_ERROR: "响应数据解析失败 / Failed to parse response data",
    CrawlerErrorCode.CONTENT_REMOVED: "内容已被删除或不可用 / Content removed or unavailable",
    CrawlerErrorCode.ACCOUNT_BANNED: "账号被封禁或受限 / Account banned or restricted",
    CrawlerErrorCode.PLATFORM_ERROR: "平台返回异常错误 / Platform returned unexpected error",
    CrawlerErrorCode.API_CHANGED: "平台接口可能已变更 / Platform API may have changed",
    CrawlerErrorCode.INVALID_CONFIG: "配置参数无效 / Invalid configuration",
    CrawlerErrorCode.INVALID_INPUT: "输入参数无效 / Invalid input parameters",
    CrawlerErrorCode.BROWSER_ERROR: "浏览器启动或连接错误 / Browser launch or connection error",
    CrawlerErrorCode.STORAGE_ERROR: "数据存储错误 / Data storage error",
    CrawlerErrorCode.INTERNAL_ERROR: "爬虫内部错误 / Internal crawler error",
    CrawlerErrorCode.UNKNOWN: "未知错误 / Unknown error",
}
