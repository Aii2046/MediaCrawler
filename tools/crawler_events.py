# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/tools/crawler_events.py
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

"""
Event emitter helpers for the crawler subprocess.

Structured events are emitted as JSON lines prefixed with [CRAWLER_EVENT].
The API server's CrawlerManager parses these lines to update progress state
and broadcast events via WebSocket. Regular log lines (without the prefix)
continue to work exactly as before.
"""

import json
from typing import Optional

from constant.crawler_error import CrawlerErrorCode, ERROR_DESCRIPTIONS

EVENT_PREFIX = "[CRAWLER_EVENT]"


def _emit(event: dict) -> None:
    """Emit a structured event as a prefixed JSON line to stdout."""
    line = EVENT_PREFIX + json.dumps(event, ensure_ascii=False)
    print(line, flush=True)


def emit_progress(phase: str, current: int, total: int, message: str = "") -> None:
    """Emit a progress update event.

    Args:
        phase: Current phase name (e.g. "search", "comments", "detail").
        current: Current progress count.
        total: Total expected count (0 if unknown).
        message: Optional human-readable progress message.
    """
    _emit({
        "type": "progress",
        "phase": phase,
        "current": current,
        "total": total,
        "message": message,
    })


def emit_error(
    code: CrawlerErrorCode,
    message: str = "",
    details: Optional[dict] = None,
) -> None:
    """Emit an error event.

    Args:
        code: The unified error code.
        message: Optional custom message (falls back to ERROR_DESCRIPTIONS).
        details: Optional extra context dict.
    """
    _emit({
        "type": "error",
        "code": code.value,
        "message": message or ERROR_DESCRIPTIONS.get(code, ""),
        "details": details,
    })


def emit_phase(phase: str, message: str = "") -> None:
    """Emit a phase change event.

    Args:
        phase: The new phase name (e.g. "login", "search", "comments").
        message: Optional description of the phase.
    """
    _emit({
        "type": "phase_change",
        "phase": phase,
        "message": message,
    })


def emit_complete(stats: Optional[dict] = None) -> None:
    """Emit a crawl completion event.

    Args:
        stats: Optional summary statistics dict (e.g. {"notes": 20, "comments": 150}).
    """
    _emit({
        "type": "complete",
        "stats": stats or {},
    })
