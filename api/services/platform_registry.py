# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/services/platform_registry.py
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
Platform field mapping registry.

Abstracts cross-platform differences in ORM model field names, types,
and time formats so the query service can build uniform queries.
"""

from dataclasses import dataclass
from typing import Optional, Type, Dict

from sqlalchemy import Column

from database.models import (
    Base,
    BilibiliVideo,
    BilibiliVideoComment,
    DouyinAweme,
    DouyinAwemeComment,
    KuaishouVideo,
    KuaishouVideoComment,
    WeiboNote,
    WeiboNoteComment,
    XhsNote,
    XhsNoteComment,
    TiebaNote,
    TiebaComment,
    ZhihuContent,
    ZhihuComment,
)


@dataclass
class PlatformFieldMapping:
    """Describes how a platform's content/comment models map to query concepts."""
    model: Type[Base]
    comment_model: Type[Base]
    content_id_field: str          # e.g., "note_id", "aweme_id", "video_id"
    comment_fk_field: str          # FK column on comment model pointing to content
    time_field: str                # e.g., "time", "create_time", "publish_time"
    time_format: str               # "milliseconds" | "seconds" | "string"
    likes_field: Optional[str]     # column name or None
    comments_field: Optional[str]
    shares_field: Optional[str]
    likes_is_int: bool             # True = Integer column, False = Text (needs CAST)
    comments_is_int: bool
    shares_is_int: bool
    title_field: Optional[str]     # None for platforms without title (e.g., Weibo)
    desc_field: Optional[str]      # "desc" or "content" for Weibo
    keyword_field: str             # always "source_keyword"


PLATFORM_REGISTRY: Dict[str, PlatformFieldMapping] = {
    "xhs": PlatformFieldMapping(
        model=XhsNote,
        comment_model=XhsNoteComment,
        content_id_field="note_id",
        comment_fk_field="note_id",
        time_field="time",
        time_format="milliseconds",
        likes_field="liked_count",
        comments_field="comment_count",
        shares_field="share_count",
        likes_is_int=False,
        comments_is_int=False,
        shares_is_int=False,
        title_field="title",
        desc_field="desc",
        keyword_field="source_keyword",
    ),
    "dy": PlatformFieldMapping(
        model=DouyinAweme,
        comment_model=DouyinAwemeComment,
        content_id_field="aweme_id",
        comment_fk_field="aweme_id",
        time_field="create_time",
        time_format="seconds",
        likes_field="liked_count",
        comments_field="comment_count",
        shares_field="share_count",
        likes_is_int=False,
        comments_is_int=False,
        shares_is_int=False,
        title_field="title",
        desc_field="desc",
        keyword_field="source_keyword",
    ),
    "bili": PlatformFieldMapping(
        model=BilibiliVideo,
        comment_model=BilibiliVideoComment,
        content_id_field="video_id",
        comment_fk_field="video_id",
        time_field="create_time",
        time_format="seconds",
        likes_field="liked_count",
        comments_field="video_comment",
        shares_field="video_share_count",
        likes_is_int=True,
        comments_is_int=False,
        shares_is_int=False,
        title_field="title",
        desc_field="desc",
        keyword_field="source_keyword",
    ),
    "ks": PlatformFieldMapping(
        model=KuaishouVideo,
        comment_model=KuaishouVideoComment,
        content_id_field="video_id",
        comment_fk_field="video_id",
        time_field="create_time",
        time_format="seconds",
        likes_field="liked_count",
        comments_field=None,
        shares_field=None,
        likes_is_int=False,
        comments_is_int=False,
        shares_is_int=False,
        title_field="title",
        desc_field="desc",
        keyword_field="source_keyword",
    ),
    "wb": PlatformFieldMapping(
        model=WeiboNote,
        comment_model=WeiboNoteComment,
        content_id_field="note_id",
        comment_fk_field="note_id",
        time_field="create_time",
        time_format="seconds",
        likes_field="liked_count",
        comments_field="comments_count",
        shares_field="shared_count",
        likes_is_int=False,
        comments_is_int=False,
        shares_is_int=False,
        title_field=None,
        desc_field="content",
        keyword_field="source_keyword",
    ),
    "tieba": PlatformFieldMapping(
        model=TiebaNote,
        comment_model=TiebaComment,
        content_id_field="note_id",
        comment_fk_field="note_id",
        time_field="publish_time",
        time_format="string",
        likes_field=None,
        comments_field=None,
        shares_field=None,
        likes_is_int=False,
        comments_is_int=False,
        shares_is_int=False,
        title_field="title",
        desc_field="desc",
        keyword_field="source_keyword",
    ),
    "zhihu": PlatformFieldMapping(
        model=ZhihuContent,
        comment_model=ZhihuComment,
        content_id_field="content_id",
        comment_fk_field="content_id",
        time_field="created_time",
        time_format="string",
        likes_field="voteup_count",
        comments_field="comment_count",
        shares_field=None,
        likes_is_int=True,
        comments_is_int=True,
        shares_is_int=False,
        title_field="title",
        desc_field="desc",
        keyword_field="source_keyword",
    ),
}


def get_platform_mapping(platform: str) -> PlatformFieldMapping:
    """Get the field mapping for a platform, raising ValueError if unknown."""
    mapping = PLATFORM_REGISTRY.get(platform)
    if mapping is None:
        raise ValueError(f"Unknown platform: {platform}")
    return mapping


def get_supported_platforms() -> list:
    """Return list of supported platform keys."""
    return list(PLATFORM_REGISTRY.keys())
