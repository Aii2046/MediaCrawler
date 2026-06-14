# -*- coding: utf-8 -*-
"""
Progress reporting for crawler subprocess -> API communication.

Emits structured JSON lines to stdout with a __progress__ sentinel marker.
The CrawlerManager in the API layer parses these lines to track crawl progress.
"""
import json
import sys
from enum import Enum
from typing import Optional


class CrawlStage(str, Enum):
    """Stages of the crawling lifecycle."""

    INITIALIZING = "initializing"
    LOGIN = "login"
    SEARCHING = "searching"
    FETCHING_DETAILS = "fetching_details"
    FETCHING_COMMENTS = "fetching_comments"
    FETCHING_MEDIA = "fetching_media"
    SAVING_DATA = "saving_data"
    COMPLETED = "completed"
    FAILED = "failed"


# Human-readable stage descriptions (Chinese + English)
STAGE_DESCRIPTIONS = {
    CrawlStage.INITIALIZING: "Initializing browser / 正在初始化浏览器",
    CrawlStage.LOGIN: "Checking login state / 正在检查登录状态",
    CrawlStage.SEARCHING: "Searching keywords / 正在搜索关键词",
    CrawlStage.FETCHING_DETAILS: "Fetching post details / 正在获取帖子详情",
    CrawlStage.FETCHING_COMMENTS: "Fetching comments / 正在获取评论",
    CrawlStage.FETCHING_MEDIA: "Downloading media / 正在下载媒体文件",
    CrawlStage.SAVING_DATA: "Saving data / 正在保存数据",
    CrawlStage.COMPLETED: "Crawl completed / 爬取完成",
    CrawlStage.FAILED: "Crawl failed / 爬取失败",
}


def emit_progress(
    stage: CrawlStage,
    current: int = 0,
    total: int = 0,
    message: str = "",
    keyword: Optional[str] = None,
    page: Optional[int] = None,
    error_code: Optional[str] = None,
) -> None:
    """Emit a structured progress line to stdout for the API to parse.

    Args:
        stage: Current crawl stage
        current: Current item count (e.g., 5 out of 20 notes fetched)
        total: Total expected items (0 if unknown)
        message: Human-readable progress message
        keyword: Current search keyword (if in search mode)
        page: Current page number (if paginating)
        error_code: Error code string (if stage is FAILED)
    """
    payload = {
        "__progress__": True,
        "stage": stage.value,
        "stage_description": STAGE_DESCRIPTIONS.get(stage, ""),
        "current": current,
        "total": total,
        "message": message,
    }
    if keyword is not None:
        payload["keyword"] = keyword
    if page is not None:
        payload["page"] = page
    if error_code is not None:
        payload["error_code"] = error_code

    # Print as a single JSON line to stdout (subprocess communication channel)
    print(json.dumps(payload, ensure_ascii=False), flush=True)
