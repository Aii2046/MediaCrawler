# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/routers/note.py
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
Note content fetch API router.
Provides endpoints for fetching XHS note content (images, text, video).
"""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..services.note_fetcher import fetch_note_content

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/note", tags=["note"])


# ─────────────────── Request / Response schemas ───────────────────


class NoteFetchRequest(BaseModel):
    """Request body for fetching note content."""
    url: str = Field(..., description="XHS note URL")
    cookies: str = Field(default="", description="Optional cookie string for authenticated access")
    international: bool = Field(default=False, description="Use international (rednote.com) domain")


class NoteFetchResponse(BaseModel):
    """Response for note content fetch."""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


# ─────────────────── Endpoints ───────────────────


@router.post("/fetch", response_model=NoteFetchResponse)
async def fetch_note(request: NoteFetchRequest):
    """Fetch note content (title, description, images, video) from a XHS note URL.

    This endpoint fetches the note page HTML, parses the embedded note data,
    and returns structured content including text, image URLs, and video URLs.
    """
    try:
        result = await fetch_note_content(
            note_url=request.url,
            international=request.international,
            cookies=request.cookies,
        )
        return NoteFetchResponse(success=True, data=result)
    except ValueError as e:
        logger.warning(f"[note/fetch] Value error: {e}")
        return NoteFetchResponse(success=False, error=str(e))
    except httpx.HTTPStatusError as e:
        logger.error(f"[note/fetch] HTTP error {e.response.status_code}: {e}")
        return NoteFetchResponse(
            success=False,
            error=f"HTTP request failed (status {e.response.status_code}). "
                  "The note may require authentication or the URL may be invalid.",
        )
    except httpx.RequestError as e:
        logger.error(f"[note/fetch] Request error: {e}")
        return NoteFetchResponse(
            success=False,
            error=f"Network request failed: {str(e)}",
        )
    except Exception as e:
        logger.error(f"[note/fetch] Unexpected error: {e}", exc_info=True)
        return NoteFetchResponse(
            success=False,
            error=f"Unexpected error: {str(e)}",
        )


@router.get("/media-proxy")
async def media_proxy(url: str = Query(..., description="Media URL to proxy")):
    """Proxy media content (images/video) from XHS CDN.

    Streams the media content from the original URL, allowing the frontend
    to display images and videos without CORS restrictions.
    """
    # Basic security: only allow XHS CDN domains
    allowed_domains = [
        "xhscdn.com",
        "xiaohongshu.com",
        "rednote.com",
        "xhscdn.cn",
    ]
    url_lower = url.lower()
    if not any(domain in url_lower for domain in allowed_domains):
        raise HTTPException(
            status_code=403,
            detail="Media proxy only supports XHS CDN URLs",
        )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.xiaohongshu.com/",
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, verify=False, timeout=60.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "application/octet-stream")
            content_length = response.headers.get("content-length")

            resp_headers = {"Content-Type": content_type}
            if content_length:
                resp_headers["Content-Length"] = content_length

            return StreamingResponse(
                iter([response.content]),
                headers=resp_headers,
            )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="Failed to fetch media")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch media: {str(e)}")
