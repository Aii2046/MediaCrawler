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

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

import config
from ..schemas.note import NoteFetchRequest, NoteFetchResponse
from ..services.note_fetcher import NoteFetcher

router = APIRouter(prefix="/note", tags=["note"])

# Resolve data directory (matching existing pattern in store modules)
DATA_DIR = Path(config.SAVE_DATA_PATH) if config.SAVE_DATA_PATH else Path("data")

# Allowed media types (whitelist for path security)
ALLOWED_MEDIA_TYPES = {"images", "videos"}

# Regex for note_id validation (alphanumeric + underscore + hyphen only)
NOTE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

# MIME type mapping
MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".mp4": "video/mp4",
}

# Singleton fetcher instance
_note_fetcher = NoteFetcher()


@router.post("/fetch", response_model=NoteFetchResponse)
async def fetch_note(request: NoteFetchRequest):
    """Fetch XHS note content (text, images, videos) from a note URL.

    Parses the note URL, fetches the HTML page, extracts note data from
    window.__INITIAL_STATE__, and optionally downloads media files locally.
    """
    return await _note_fetcher.fetch_note(
        url=request.url,
        download_media=request.download_media,
    )


@router.get("/media/{media_type}/{note_id}/{filename}")
async def serve_media(media_type: str, note_id: str, filename: str):
    """Serve downloaded media files (images/videos) for inline display."""
    return await _serve_media_file(media_type, note_id, filename, download=False)


@router.get("/download/{media_type}/{note_id}/{filename}")
async def download_media(media_type: str, note_id: str, filename: str):
    """Download media file as attachment."""
    return await _serve_media_file(media_type, note_id, filename, download=True)


async def _serve_media_file(media_type: str, note_id: str, filename: str, download: bool):
    """Shared media serving logic with security validation."""
    # Validate media_type
    if media_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(status_code=400, detail="Invalid media type. Use 'images' or 'videos'.")

    # Validate note_id (prevent path traversal)
    if not NOTE_ID_PATTERN.match(note_id):
        raise HTTPException(status_code=400, detail="Invalid note ID format.")

    # Validate filename
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    # Build full path
    full_path = DATA_DIR / "xhs" / media_type / note_id / filename

    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found.")

    # Security: ensure resolved path is within DATA_DIR
    try:
        full_path.resolve().relative_to(DATA_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied.")

    # Determine MIME type
    mime_type = MIME_MAP.get(full_path.suffix.lower(), "application/octet-stream")

    if download:
        return FileResponse(path=str(full_path), filename=filename, media_type=mime_type)
    else:
        return FileResponse(path=str(full_path), media_type=mime_type)
