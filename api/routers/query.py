# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/routers/query.py
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
Query router — database-backed data querying with filtering, sorting, pagination.
"""

from fastapi import APIRouter, HTTPException, Query

from api.schemas.query import (
    ContentQueryRequest,
    ContentQueryResponse,
    CommentQueryResponse,
    QueryStatsResponse,
)
from api.services.query_service import query_service, is_db_backend_available

router = APIRouter(prefix="/query", tags=["query"])


def _check_db_backend():
    """Raise 400 if the current storage backend is not a database."""
    if not is_db_backend_available():
        raise HTTPException(
            status_code=400,
            detail="Query API requires a database backend (sqlite, db, or postgres). "
                   "Current backend is file-based. Please change SAVE_DATA_OPTION in config."
        )


@router.post("/content", response_model=ContentQueryResponse)
async def query_content(request: ContentQueryRequest):
    """
    Query crawled content with multi-dimensional filtering.

    Supports filtering by:
    - **keyword**: searches in title, description, and source keyword
    - **start_time / end_time**: unix timestamp range (seconds)
    - **min_likes / max_likes**: engagement filter
    - **min_comments / max_comments**: engagement filter
    - **min_shares / max_shares**: engagement filter

    Supports sorting by time, liked_count, comment_count, share_count.
    Results are paginated with configurable page and page_size.
    """
    _check_db_backend()
    try:
        return await query_service.query_content(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.get("/content/{platform}/{content_id}")
async def get_content_detail(platform: str, content_id: str):
    """
    Get a single content item by platform and content ID.

    - **platform**: xhs, dy, ks, bili, wb, tieba, zhihu
    - **content_id**: the platform-specific content ID (note_id, aweme_id, video_id, etc.)
    """
    _check_db_backend()
    try:
        result = await query_service.get_content_detail(platform, content_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
    if result is None:
        raise HTTPException(status_code=404, detail="Content not found")
    return {"item": result, "platform": platform}


@router.get("/comments/{platform}/{content_id}", response_model=CommentQueryResponse)
async def get_comments(
    platform: str,
    content_id: str,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size"),
):
    """
    Get paginated comments for a specific content item.

    Comments are sorted by creation time (newest first).
    """
    _check_db_backend()
    try:
        return await query_service.query_comments(platform, content_id, page, page_size)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.get("/stats", response_model=QueryStatsResponse)
async def get_query_stats():
    """
    Get database statistics — content and comment counts per platform.
    """
    _check_db_backend()
    try:
        return await query_service.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats query failed: {str(e)}")
