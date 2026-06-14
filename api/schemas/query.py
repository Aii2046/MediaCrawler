# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/schemas/query.py
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

from typing import Optional, Literal, List, Dict, Any

from pydantic import BaseModel, Field

from .crawler import PlatformEnum


class ContentQueryRequest(BaseModel):
    """Content query request with multi-dimensional filtering"""
    platform: PlatformEnum
    keyword: Optional[str] = Field(default=None, description="Search in title/desc/source_keyword")
    start_time: Optional[int] = Field(default=None, description="Start time (unix timestamp in seconds)")
    end_time: Optional[int] = Field(default=None, description="End time (unix timestamp in seconds)")
    min_likes: Optional[int] = Field(default=None, ge=0, description="Minimum likes count")
    max_likes: Optional[int] = Field(default=None, ge=0, description="Maximum likes count")
    min_comments: Optional[int] = Field(default=None, ge=0, description="Minimum comments count")
    max_comments: Optional[int] = Field(default=None, ge=0, description="Maximum comments count")
    min_shares: Optional[int] = Field(default=None, ge=0, description="Minimum shares count")
    max_shares: Optional[int] = Field(default=None, ge=0, description="Maximum shares count")
    sort_by: Optional[str] = Field(default="time", description="Sort field: time/liked_count/comment_count/share_count")
    sort_order: Literal["asc", "desc"] = Field(default="desc", description="Sort order")
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Page size (1-100)")


class ContentQueryResponse(BaseModel):
    """Paginated content query response"""
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    total_pages: int
    platform: str


class CommentQueryResponse(BaseModel):
    """Paginated comment query response"""
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    total_pages: int
    platform: str
    content_id: str


class QueryStatsResponse(BaseModel):
    """Database statistics response"""
    platforms: Dict[str, Dict[str, int]]
    total_content: int
    total_comments: int
