# -*- coding: utf-8 -*-
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.schemas.query import PaginatedResponse, QueryRequest
from api.services.query_service import get_model_meta, query_data

router = APIRouter(prefix="/query", tags=["query"])

VALID_PLATFORMS = {"xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu"}


def _parse_query_params(
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page (max 100)"),
    sort_by: Optional[str] = Query(default=None, description="Field name to sort by"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$", description="Sort direction"),
    keyword: Optional[str] = Query(default=None, description="Search keyword in title/desc/content"),
    source_keyword: Optional[str] = Query(default=None, description="Exact match on crawl source keyword"),
    time_start: Optional[int] = Query(default=None, description="Start of time range (Unix timestamp)"),
    time_end: Optional[int] = Query(default=None, description="End of time range (Unix timestamp)"),
    user_id: Optional[str] = Query(default=None, description="Filter by user ID"),
    min_likes: Optional[int] = Query(default=None, ge=0, description="Minimum like count"),
    min_comments: Optional[int] = Query(default=None, ge=0, description="Minimum comment count"),
    min_shares: Optional[int] = Query(default=None, ge=0, description="Minimum share count"),
    min_collected: Optional[int] = Query(default=None, ge=0, description="Minimum collected/favorite count"),
) -> QueryRequest:
    return QueryRequest(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        keyword=keyword,
        source_keyword=source_keyword,
        time_start=time_start,
        time_end=time_end,
        user_id=user_id,
        min_likes=min_likes,
        min_comments=min_comments,
        min_shares=min_shares,
        min_collected=min_collected,
    )


def _validate(platform: str, data_type: str) -> None:
    if platform not in VALID_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid platform '{platform}'. Must be one of: {', '.join(sorted(VALID_PLATFORMS))}",
        )
    meta = get_model_meta(platform, data_type)
    if meta is None:
        raise HTTPException(
            status_code=400,
            detail=f"Data type '{data_type}' is not available for platform '{platform}'",
        )


@router.get("/{platform}/content", response_model=PaginatedResponse)
async def query_content(
    platform: str,
    params: QueryRequest = Depends(_parse_query_params),
):
    """Query content data (notes, videos, articles) for a platform with filtering, sorting, and pagination."""
    _validate(platform, "content")
    try:
        return await query_data(platform, "content", params)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{platform}/comments", response_model=PaginatedResponse)
async def query_comments(
    platform: str,
    params: QueryRequest = Depends(_parse_query_params),
):
    """Query comment data for a platform with filtering, sorting, and pagination."""
    _validate(platform, "comments")
    try:
        return await query_data(platform, "comments", params)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{platform}/creators", response_model=PaginatedResponse)
async def query_creators(
    platform: str,
    params: QueryRequest = Depends(_parse_query_params),
):
    """Query creator data for a platform with filtering, sorting, and pagination."""
    _validate(platform, "creators")
    try:
        return await query_data(platform, "creators", params)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
