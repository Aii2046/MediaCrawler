# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/schemas/note.py
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

from typing import List, Optional, Literal

from pydantic import BaseModel, Field


class NoteFetchRequest(BaseModel):
    """Request body for fetching a single XHS note"""
    url: str = Field(..., description="Full XHS note URL with xsec_token")
    download_media: bool = Field(default=True, description="Download images and videos locally")


class NoteUserInfo(BaseModel):
    """Note author information"""
    user_id: Optional[str] = None
    nickname: Optional[str] = None
    avatar: Optional[str] = None


class NoteInteractInfo(BaseModel):
    """Note interaction statistics"""
    liked_count: Optional[str] = None
    collected_count: Optional[str] = None
    comment_count: Optional[str] = None
    share_count: Optional[str] = None


class NoteImageInfo(BaseModel):
    """Note image information"""
    index: int
    url: str
    url_default: Optional[str] = None
    local_path: Optional[str] = None
    download_url: Optional[str] = None


class NoteVideoInfo(BaseModel):
    """Note video information"""
    index: int
    url: str
    local_path: Optional[str] = None
    download_url: Optional[str] = None


class NoteFetchResponse(BaseModel):
    """Full note content response"""
    success: bool
    note_id: str = ""
    type: Optional[Literal["normal", "video"]] = None
    title: Optional[str] = None
    desc: Optional[str] = None
    time: Optional[int] = None
    last_update_time: Optional[int] = None
    ip_location: Optional[str] = None
    user: Optional[NoteUserInfo] = None
    interact_info: Optional[NoteInteractInfo] = None
    images: List[NoteImageInfo] = []
    videos: List[NoteVideoInfo] = []
    tag_list: List[str] = []
    note_url: Optional[str] = None
    xsec_token: Optional[str] = None
    error: Optional[str] = None
