# -*- coding: utf-8 -*-
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Type

from sqlalchemy import Integer, cast, func, or_, select
from sqlalchemy.sql import Select

from api.schemas.query import PaginatedResponse, QueryRequest
from database.db_session import create_tables, get_async_engine, get_session
from database.models import (
    Base,
    BilibiliUpInfo,
    BilibiliVideo,
    BilibiliVideoComment,
    DouyinAweme,
    DouyinAwemeComment,
    DyCreator,
    KuaishouVideo,
    KuaishouVideoComment,
    TiebaComment,
    TiebaCreator,
    TiebaNote,
    WeiboCreator,
    WeiboNote,
    WeiboNoteComment,
    XhsCreator,
    XhsNote,
    XhsNoteComment,
    ZhihuComment,
    ZhihuContent,
    ZhihuCreator,
)


@dataclass
class ModelMeta:
    """Metadata describing how to query a specific model."""

    model: Type[Base]
    # Fields to search with keyword (LIKE)
    text_search_fields: List[str] = field(default_factory=list)
    # Time field name for range filtering (BigInteger Unix timestamp fields only)
    time_field: Optional[str] = None
    # Whether the time field is a numeric timestamp (False = string, skip numeric range filter)
    time_is_numeric: bool = True
    # Interaction field mappings (field_name on the model). None means not available.
    likes_field: Optional[str] = None
    comments_field: Optional[str] = None
    shares_field: Optional[str] = None
    collected_field: Optional[str] = None
    # Whether each interaction field is stored as Text (needs cast) vs Integer
    text_numeric_fields: List[str] = field(default_factory=list)
    # Source keyword field
    source_keyword_field: Optional[str] = "source_keyword"
    # User ID field
    user_id_field: Optional[str] = "user_id"


# Registry: (platform, data_type) -> ModelMeta
MODEL_REGISTRY: Dict[Tuple[str, str], ModelMeta] = {
    # --- Xiaohongshu ---
    ("xhs", "content"): ModelMeta(
        model=XhsNote,
        text_search_fields=["title", "desc"],
        time_field="time",
        likes_field="liked_count",
        comments_field="comment_count",
        shares_field="share_count",
        collected_field="collected_count",
        text_numeric_fields=["liked_count", "comment_count", "share_count", "collected_count"],
    ),
    ("xhs", "comments"): ModelMeta(
        model=XhsNoteComment,
        text_search_fields=["content"],
        time_field="create_time",
        likes_field="like_count",
        text_numeric_fields=["like_count"],
        source_keyword_field=None,
    ),
    ("xhs", "creators"): ModelMeta(
        model=XhsCreator,
        text_search_fields=["nickname"],
        time_field=None,
        likes_field=None,
        source_keyword_field=None,
    ),
    # --- Douyin ---
    ("dy", "content"): ModelMeta(
        model=DouyinAweme,
        text_search_fields=["title", "desc"],
        time_field="create_time",
        likes_field="liked_count",
        comments_field="comment_count",
        shares_field="share_count",
        collected_field="collected_count",
        text_numeric_fields=["liked_count", "comment_count", "share_count", "collected_count"],
    ),
    ("dy", "comments"): ModelMeta(
        model=DouyinAwemeComment,
        text_search_fields=["content"],
        time_field="create_time",
        likes_field="like_count",
        text_numeric_fields=["like_count"],
        source_keyword_field=None,
    ),
    ("dy", "creators"): ModelMeta(
        model=DyCreator,
        text_search_fields=["nickname"],
        time_field=None,
        likes_field=None,
        source_keyword_field=None,
    ),
    # --- Kuaishou ---
    ("ks", "content"): ModelMeta(
        model=KuaishouVideo,
        text_search_fields=["title", "desc"],
        time_field="create_time",
        likes_field="liked_count",
        text_numeric_fields=["liked_count"],
    ),
    ("ks", "comments"): ModelMeta(
        model=KuaishouVideoComment,
        text_search_fields=["content"],
        time_field="create_time",
        source_keyword_field=None,
    ),
    # --- Bilibili ---
    ("bili", "content"): ModelMeta(
        model=BilibiliVideo,
        text_search_fields=["title", "desc"],
        time_field="create_time",
        likes_field="liked_count",
        comments_field="video_comment",
        shares_field="video_share_count",
        collected_field="video_favorite_count",
        text_numeric_fields=["video_comment", "video_share_count", "video_favorite_count"],
    ),
    ("bili", "comments"): ModelMeta(
        model=BilibiliVideoComment,
        text_search_fields=["content"],
        time_field="create_time",
        likes_field="like_count",
        text_numeric_fields=["like_count"],
        source_keyword_field=None,
    ),
    ("bili", "creators"): ModelMeta(
        model=BilibiliUpInfo,
        text_search_fields=["nickname"],
        time_field=None,
        likes_field="total_liked",
        source_keyword_field=None,
    ),
    # --- Weibo ---
    ("wb", "content"): ModelMeta(
        model=WeiboNote,
        text_search_fields=["content"],
        time_field="create_time",
        likes_field="liked_count",
        comments_field="comments_count",
        shares_field="shared_count",
        text_numeric_fields=["liked_count", "comments_count", "shared_count"],
    ),
    ("wb", "comments"): ModelMeta(
        model=WeiboNoteComment,
        text_search_fields=["content"],
        time_field="create_time",
        likes_field="comment_like_count",
        text_numeric_fields=["comment_like_count"],
        source_keyword_field=None,
    ),
    ("wb", "creators"): ModelMeta(
        model=WeiboCreator,
        text_search_fields=["nickname"],
        time_field=None,
        likes_field=None,
        source_keyword_field=None,
    ),
    # --- Tieba ---
    ("tieba", "content"): ModelMeta(
        model=TiebaNote,
        text_search_fields=["title", "desc"],
        time_field="publish_time",
        time_is_numeric=False,
        comments_field="total_replay_num",
        user_id_field=None,
    ),
    ("tieba", "comments"): ModelMeta(
        model=TiebaComment,
        text_search_fields=["content"],
        time_field="publish_time",
        time_is_numeric=False,
        source_keyword_field=None,
        user_id_field=None,
    ),
    ("tieba", "creators"): ModelMeta(
        model=TiebaCreator,
        text_search_fields=["nickname", "user_name"],
        time_field=None,
        likes_field=None,
        source_keyword_field=None,
    ),
    # --- Zhihu ---
    ("zhihu", "content"): ModelMeta(
        model=ZhihuContent,
        text_search_fields=["title", "desc", "content_text"],
        time_field="created_time",
        time_is_numeric=False,
        likes_field="voteup_count",
        comments_field="comment_count",
    ),
    ("zhihu", "comments"): ModelMeta(
        model=ZhihuComment,
        text_search_fields=["content"],
        time_field="publish_time",
        time_is_numeric=False,
        likes_field="like_count",
        source_keyword_field=None,
    ),
    ("zhihu", "creators"): ModelMeta(
        model=ZhihuCreator,
        text_search_fields=["user_nickname"],
        time_field=None,
        likes_field=None,
        source_keyword_field=None,
        user_id_field="user_id",
    ),
}


def get_model_meta(platform: str, data_type: str) -> Optional[ModelMeta]:
    """Look up model metadata for a given platform and data type."""
    return MODEL_REGISTRY.get((platform, data_type))


def _get_column(model: Type[Base], field_name: str):
    """Get a SQLAlchemy column object from a model by field name."""
    return getattr(model, field_name, None)


def _apply_numeric_filter(
    stmt: Select, model: Type[Base], field_name: str, min_value: int, meta: ModelMeta
) -> Select:
    """Apply a >= filter on a field, casting from Text to Integer if needed."""
    col = _get_column(model, field_name)
    if col is None:
        return stmt
    if field_name in meta.text_numeric_fields:
        stmt = stmt.where(col.isnot(None), col != "")
        stmt = stmt.where(cast(col, Integer) >= min_value)
    else:
        stmt = stmt.where(col >= min_value)
    return stmt


def build_query(meta: ModelMeta, params: QueryRequest) -> Tuple[Select, Select]:
    """Build data and count queries from the model metadata and request params.

    Returns (data_query, count_query).
    """
    model = meta.model
    base_stmt = select(model)

    # --- WHERE clauses ---

    # Keyword search (OR across text search fields)
    if params.keyword and meta.text_search_fields:
        like_pattern = f"%{params.keyword}%"
        conditions = []
        for fname in meta.text_search_fields:
            col = _get_column(model, fname)
            if col is not None:
                conditions.append(col.like(like_pattern))
        if conditions:
            base_stmt = base_stmt.where(or_(*conditions))

    # Source keyword exact match
    if params.source_keyword and meta.source_keyword_field:
        col = _get_column(model, meta.source_keyword_field)
        if col is not None:
            base_stmt = base_stmt.where(col == params.source_keyword)

    # Time range filter (only for numeric timestamp fields)
    if meta.time_field and meta.time_is_numeric:
        col = _get_column(model, meta.time_field)
        if col is not None:
            if params.time_start is not None:
                base_stmt = base_stmt.where(col >= params.time_start)
            if params.time_end is not None:
                base_stmt = base_stmt.where(col <= params.time_end)

    # User ID filter
    if params.user_id and meta.user_id_field:
        col = _get_column(model, meta.user_id_field)
        if col is not None:
            base_stmt = base_stmt.where(col == params.user_id)

    # Interaction minimum filters
    if params.min_likes is not None and meta.likes_field:
        base_stmt = _apply_numeric_filter(base_stmt, model, meta.likes_field, params.min_likes, meta)
    if params.min_comments is not None and meta.comments_field:
        base_stmt = _apply_numeric_filter(base_stmt, model, meta.comments_field, params.min_comments, meta)
    if params.min_shares is not None and meta.shares_field:
        base_stmt = _apply_numeric_filter(base_stmt, model, meta.shares_field, params.min_shares, meta)
    if params.min_collected is not None and meta.collected_field:
        base_stmt = _apply_numeric_filter(base_stmt, model, meta.collected_field, params.min_collected, meta)

    # --- Count query (before sorting/pagination) ---
    count_stmt = select(func.count()).select_from(base_stmt.subquery())

    # --- Sorting ---
    if params.sort_by:
        col = _get_column(model, params.sort_by)
        if col is not None:
            sort_expr = cast(col, Integer) if params.sort_by in meta.text_numeric_fields else col
            if params.sort_order == "asc":
                base_stmt = base_stmt.order_by(sort_expr.asc())
            else:
                base_stmt = base_stmt.order_by(sort_expr.desc())
    else:
        # Default sort: by id descending (newest records first)
        base_stmt = base_stmt.order_by(model.id.desc())

    # --- Pagination ---
    offset = (params.page - 1) * params.page_size
    data_stmt = base_stmt.offset(offset).limit(params.page_size)

    return data_stmt, count_stmt


def _model_to_dict(instance) -> Dict[str, Any]:
    """Convert a SQLAlchemy model instance to a dict, excluding internal state."""
    d = {}
    for col in instance.__table__.columns:
        d[col.name] = getattr(instance, col.name)
    return d


async def query_data(platform: str, data_type: str, params: QueryRequest) -> PaginatedResponse:
    """Execute a query against the database for the given platform and data type."""
    meta = get_model_meta(platform, data_type)
    if meta is None:
        raise ValueError(f"Unsupported platform '{platform}' or data type '{data_type}'")

    engine = get_async_engine()
    if engine is None:
        raise RuntimeError(
            "No database engine configured. Query API requires a database backend "
            "(sqlite, db, or postgres). Current save option uses file-based storage."
        )

    await create_tables()

    data_stmt, count_stmt = build_query(meta, params)

    async with get_session() as session:
        if session is None:
            raise RuntimeError("Could not create database session")

        count_result = await session.execute(count_stmt)
        total = count_result.scalar() or 0

        data_result = await session.execute(data_stmt)
        rows = [_model_to_dict(row) for row in data_result.scalars().all()]

    total_pages = max(1, math.ceil(total / params.page_size))

    return PaginatedResponse(
        data=rows,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages,
    )
