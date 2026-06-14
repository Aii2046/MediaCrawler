# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/services/query_service.py
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
Query service layer.

Builds SQLAlchemy queries with multi-dimensional filtering,
sorting, and pagination using the platform field registry.
"""

import math
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy import select, func, cast, Integer, and_, or_, desc, asc, Column
from sqlalchemy.ext.asyncio import AsyncSession

import config
from database.db_session import get_session
from api.schemas.query import (
    ContentQueryRequest,
    ContentQueryResponse,
    CommentQueryResponse,
    QueryStatsResponse,
)
from api.services.platform_registry import (
    get_platform_mapping,
    get_supported_platforms,
    PlatformFieldMapping,
    PLATFORM_REGISTRY,
)


DB_BACKENDS = {"sqlite", "db", "postgres", "mysql", "mongodb"}


def is_db_backend_available() -> bool:
    """Check if the current SAVE_DATA_OPTION supports database queries."""
    return config.SAVE_DATA_OPTION in DB_BACKENDS


def _get_column(model, field_name: str) -> Optional[Column]:
    """Safely get a column attribute from an ORM model."""
    return getattr(model, field_name, None)


def _make_numeric_expr(column_attr, is_int: bool):
    """
    Return a SQL expression that yields a numeric value for comparison.

    For Integer columns, returns the column directly.
    For Text columns, returns CAST(NULLIF(col, '') AS INTEGER) so that
    empty strings become NULL and don't cause cast errors.
    """
    if is_int:
        return column_attr
    return cast(func.nullif(column_attr, ""), Integer)


def _convert_time_to_field(ts_seconds: int, time_format: str) -> Any:
    """
    Convert a unix-seconds timestamp to the platform's native time field value.

    - "milliseconds": ts * 1000
    - "seconds": ts as-is
    - "string": format as "YYYY-MM-DD HH:MM:SS"
    """
    if time_format == "milliseconds":
        return ts_seconds * 1000
    elif time_format == "seconds":
        return ts_seconds
    else:  # "string"
        return datetime.fromtimestamp(ts_seconds).strftime("%Y-%m-%d %H:%M:%S")


def _normalize_time_from_field(value: Any, time_format: str) -> Optional[int]:
    """
    Convert a platform-native time value back to unix seconds for the API response.
    """
    if value is None:
        return None
    if time_format == "milliseconds":
        return int(value) // 1000
    elif time_format == "seconds":
        return int(value)
    else:  # "string"
        try:
            return int(datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").timestamp())
        except (ValueError, TypeError):
            try:
                return int(datetime.strptime(str(value), "%Y-%m-%d").timestamp())
            except (ValueError, TypeError):
                return None


def _model_to_dict(obj) -> Dict[str, Any]:
    """Convert an ORM object to a plain dict, removing SQLAlchemy internals."""
    d = obj.__dict__.copy()
    d.pop("_sa_instance_state", None)
    return d


class QueryService:

    async def query_content(self, request: ContentQueryRequest) -> ContentQueryResponse:
        """Build and execute a filtered, sorted, paginated content query."""
        mapping = get_platform_mapping(request.platform.value)
        model = mapping.model

        async with get_session() as session:
            if session is None:
                raise RuntimeError("Database session not available")

            # --- Build WHERE clauses ---
            conditions = []

            # 1. Keyword filter (title OR desc OR source_keyword)
            if request.keyword:
                kw = f"%{request.keyword}%"
                keyword_conds = []
                if mapping.title_field:
                    col = _get_column(model, mapping.title_field)
                    if col is not None:
                        keyword_conds.append(col.ilike(kw))
                if mapping.desc_field:
                    col = _get_column(model, mapping.desc_field)
                    if col is not None:
                        keyword_conds.append(col.ilike(kw))
                kw_col = _get_column(model, mapping.keyword_field)
                if kw_col is not None:
                    keyword_conds.append(kw_col.ilike(kw))
                if keyword_conds:
                    conditions.append(or_(*keyword_conds))

            # 2. Time range filter
            time_col = _get_column(model, mapping.time_field)
            if time_col is not None:
                if request.start_time is not None:
                    start_val = _convert_time_to_field(request.start_time, mapping.time_format)
                    conditions.append(time_col >= start_val)
                if request.end_time is not None:
                    end_val = _convert_time_to_field(request.end_time, mapping.time_format)
                    conditions.append(time_col <= end_val)

            # 3. Engagement filters (likes, comments, shares)
            for field_name, is_int, min_val, max_val in [
                (mapping.likes_field, mapping.likes_is_int, request.min_likes, request.max_likes),
                (mapping.comments_field, mapping.comments_is_int, request.min_comments, request.max_comments),
                (mapping.shares_field, mapping.shares_is_int, request.min_shares, request.max_shares),
            ]:
                if field_name is None:
                    continue
                col = _get_column(model, field_name)
                if col is None:
                    continue
                num_expr = _make_numeric_expr(col, is_int)
                if min_val is not None:
                    conditions.append(num_expr >= min_val)
                if max_val is not None:
                    conditions.append(num_expr <= max_val)

            # --- Count query ---
            count_stmt = select(func.count()).select_from(model)
            if conditions:
                count_stmt = count_stmt.where(and_(*conditions))
            total_result = await session.execute(count_stmt)
            total = total_result.scalar() or 0

            # --- Data query with sorting and pagination ---
            data_stmt = select(model)
            if conditions:
                data_stmt = data_stmt.where(and_(*conditions))

            # Sorting
            sort_col_name = request.sort_by
            sort_direction = request.sort_order

            # Map generic sort names to actual field names
            sort_field_map = {
                "time": mapping.time_field,
                "liked_count": mapping.likes_field,
                "comment_count": mapping.comments_field,
                "share_count": mapping.shares_field,
            }
            actual_sort_field = sort_field_map.get(sort_col_name, sort_col_name)

            if actual_sort_field:
                sort_col = _get_column(model, actual_sort_field)
                if sort_col is not None:
                    # Determine if we need CAST for sorting
                    is_int_field = False
                    if actual_sort_field == mapping.likes_field:
                        is_int_field = mapping.likes_is_int
                    elif actual_sort_field == mapping.comments_field:
                        is_int_field = mapping.comments_is_int
                    elif actual_sort_field == mapping.shares_field:
                        is_int_field = mapping.shares_is_int
                    elif actual_sort_field == mapping.time_field and mapping.time_format in ("milliseconds", "seconds"):
                        is_int_field = True  # BigInteger time fields

                    if not is_int_field and actual_sort_field in (
                        mapping.likes_field, mapping.comments_field, mapping.shares_field
                    ):
                        sort_expr = _make_numeric_expr(sort_col, False)
                    else:
                        sort_expr = sort_col

                    if sort_direction == "asc":
                        data_stmt = data_stmt.order_by(asc(sort_expr))
                    else:
                        data_stmt = data_stmt.order_by(desc(sort_expr))

            # Pagination
            offset = (request.page - 1) * request.page_size
            data_stmt = data_stmt.offset(offset).limit(request.page_size)

            result = await session.execute(data_stmt)
            rows = result.scalars().all()

            # Convert to dicts and normalize timestamps
            items = []
            for row in rows:
                d = _model_to_dict(row)
                # Normalize the time field to unix seconds
                time_val = d.get(mapping.time_field)
                d["_normalized_time"] = _normalize_time_from_field(time_val, mapping.time_format)
                items.append(d)

            total_pages = math.ceil(total / request.page_size) if total > 0 else 0

            return ContentQueryResponse(
                items=items,
                total=total,
                page=request.page,
                page_size=request.page_size,
                total_pages=total_pages,
                platform=request.platform.value,
            )

    async def get_content_detail(self, platform: str, content_id: str) -> Optional[Dict[str, Any]]:
        """Get a single content item by its platform-specific ID."""
        mapping = get_platform_mapping(platform)
        model = mapping.model

        async with get_session() as session:
            if session is None:
                raise RuntimeError("Database session not available")

            id_col = _get_column(model, mapping.content_id_field)
            if id_col is None:
                return None

            # Try both string and int matching for the ID
            stmt = select(model).where(
                or_(
                    id_col == content_id,
                    cast(id_col, Integer) == content_id if not isinstance(content_id, int) else id_col == int(content_id),
                )
            )
            result = await session.execute(stmt)
            row = result.scalars().first()

            if row is None:
                return None

            d = _model_to_dict(row)
            time_val = d.get(mapping.time_field)
            d["_normalized_time"] = _normalize_time_from_field(time_val, mapping.time_format)
            return d

    async def query_comments(
        self, platform: str, content_id: str, page: int = 1, page_size: int = 20
    ) -> CommentQueryResponse:
        """Get paginated comments for a specific content item."""
        mapping = get_platform_mapping(platform)
        comment_model = mapping.comment_model

        async with get_session() as session:
            if session is None:
                raise RuntimeError("Database session not available")

            fk_col = _get_column(comment_model, mapping.comment_fk_field)
            if fk_col is None:
                return CommentQueryResponse(
                    items=[], total=0, page=page, page_size=page_size,
                    total_pages=0, platform=platform, content_id=content_id,
                )

            # Count
            count_stmt = select(func.count()).select_from(comment_model).where(fk_col == content_id)
            total_result = await session.execute(count_stmt)
            total = total_result.scalar() or 0

            # Data
            data_stmt = select(comment_model).where(fk_col == content_id)

            # Sort by time if available
            time_col = _get_column(comment_model, "create_time")
            if time_col is None:
                time_col = _get_column(comment_model, "publish_time")
            if time_col is not None:
                data_stmt = data_stmt.order_by(desc(time_col))

            offset = (page - 1) * page_size
            data_stmt = data_stmt.offset(offset).limit(page_size)

            result = await session.execute(data_stmt)
            rows = result.scalars().all()
            items = [_model_to_dict(row) for row in rows]

            total_pages = math.ceil(total / page_size) if total > 0 else 0

            return CommentQueryResponse(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
                platform=platform,
                content_id=content_id,
            )

    async def get_stats(self) -> QueryStatsResponse:
        """Get per-platform content and comment counts."""
        platforms_stats = {}
        total_content = 0
        total_comments = 0

        async with get_session() as session:
            if session is None:
                raise RuntimeError("Database session not available")

            for platform_key, mapping in PLATFORM_REGISTRY.items():
                try:
                    # Content count
                    content_count_stmt = select(func.count()).select_from(mapping.model)
                    content_result = await session.execute(content_count_stmt)
                    content_count = content_result.scalar() or 0

                    # Comment count
                    comment_count_stmt = select(func.count()).select_from(mapping.comment_model)
                    comment_result = await session.execute(comment_count_stmt)
                    comment_count = comment_result.scalar() or 0

                    platforms_stats[platform_key] = {
                        "content_count": content_count,
                        "comment_count": comment_count,
                    }
                    total_content += content_count
                    total_comments += comment_count
                except Exception:
                    # Table may not exist if this platform was never crawled
                    platforms_stats[platform_key] = {
                        "content_count": 0,
                        "comment_count": 0,
                    }

        return QueryStatsResponse(
            platforms=platforms_stats,
            total_content=total_content,
            total_comments=total_comments,
        )


# Singleton instance
query_service = QueryService()
