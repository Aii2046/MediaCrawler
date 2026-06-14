# -*- coding: utf-8 -*-
from typing import List, Optional

from pydantic import BaseModel, Field


class NoteContentRequest(BaseModel):
    """Request to fetch note content from URLs"""
    note_urls: List[str] = Field(..., min_length=1, description="List of Xiaohongshu note URLs")
    cookies: str = Field(..., min_length=1, description="Cookie string (must include 'a1')")
    download_media: bool = Field(default=False, description="Whether to download images/videos to disk")


class NoteImageInfo(BaseModel):
    url: str
    filename: Optional[str] = None


class NoteVideoInfo(BaseModel):
    urls: List[str]
    filename: Optional[str] = None


class NoteUserInfo(BaseModel):
    user_id: str
    nickname: str
    avatar: str


class NoteInteractInfo(BaseModel):
    liked_count: int = 0
    collected_count: int = 0
    comment_count: int = 0
    share_count: int = 0


class NoteContentItem(BaseModel):
    """Full note content"""
    note_id: str
    note_type: str  # "normal" (images) or "video"
    title: str
    description: str
    user: NoteUserInfo
    interact_info: NoteInteractInfo
    images: List[NoteImageInfo] = []
    video: Optional[NoteVideoInfo] = None
    tags: List[str] = []
    ip_location: str = ""
    time: Optional[int] = None
    note_url: str


class NoteContentResponse(BaseModel):
    """Response containing fetched notes"""
    success: bool
    message: str
    notes: List[NoteContentItem] = []
    errors: List[str] = []
