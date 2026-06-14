# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Query parameters for filtering, sorting, and paginating crawled data."""

    # Pagination
    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    page_size: int = Field(
        default=20, ge=1, le=100, description="Items per page (max 100)"
    )

    # Sorting
    sort_by: Optional[str] = Field(
        default=None, description="Field name to sort by (e.g. liked_count, create_time)"
    )
    sort_order: Literal["asc", "desc"] = Field(
        default="desc", description="Sort direction"
    )

    # Text search
    keyword: Optional[str] = Field(
        default=None, description="Search keyword in title/desc/content fields"
    )
    source_keyword: Optional[str] = Field(
        default=None, description="Exact match on crawl source keyword"
    )

    # Time range (Unix timestamps)
    time_start: Optional[int] = Field(
        default=None, description="Start of time range (Unix timestamp)"
    )
    time_end: Optional[int] = Field(
        default=None, description="End of time range (Unix timestamp)"
    )

    # User filter
    user_id: Optional[str] = Field(default=None, description="Filter by user ID")

    # Interaction minimums
    min_likes: Optional[int] = Field(
        default=None, ge=0, description="Minimum like/voteup count"
    )
    min_comments: Optional[int] = Field(
        default=None, ge=0, description="Minimum comment count"
    )
    min_shares: Optional[int] = Field(
        default=None, ge=0, description="Minimum share count"
    )
    min_collected: Optional[int] = Field(
        default=None, ge=0, description="Minimum collected/favorite count"
    )


class PaginatedResponse(BaseModel):
    """Paginated query response."""

    data: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    total_pages: int
