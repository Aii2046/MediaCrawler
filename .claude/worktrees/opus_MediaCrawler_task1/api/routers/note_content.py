# -*- coding: utf-8 -*-
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

import config
from api.schemas.note_content import NoteContentRequest, NoteContentResponse
from api.services.note_content_service import note_content_service

router = APIRouter(prefix="/note", tags=["note_content"])

# Media data directories
_IMAGES_DIR = Path(config.SAVE_DATA_PATH or "data") / "xhs" / "images"
_VIDEOS_DIR = Path(config.SAVE_DATA_PATH or "data") / "xhs" / "videos"


@router.post("/fetch", response_model=NoteContentResponse)
async def fetch_note_content(request: NoteContentRequest):
    """Fetch note content from one or more Xiaohongshu URLs."""
    # Validate cookies contain 'a1'
    if "a1=" not in request.cookies:
        raise HTTPException(status_code=400, detail="Cookie must contain 'a1' key for signing")

    notes, errors = await note_content_service.fetch_notes(
        request.note_urls, request.cookies, request.download_media
    )

    return NoteContentResponse(
        success=len(notes) > 0,
        message=f"Fetched {len(notes)} note(s)" + (f", {len(errors)} error(s)" if errors else ""),
        notes=notes,
        errors=errors,
    )


@router.get("/cookies")
async def fetch_cookies_from_browser():
    """Extract XHS cookies from a running Chrome browser via CDP."""
    try:
        cookie_str = await note_content_service.fetch_cookies_from_browser()
        if not cookie_str:
            raise HTTPException(status_code=404, detail="No XHS cookies found in browser")
        return {"success": True, "cookies": cookie_str}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to browser via CDP: {str(e)}. "
                   "Make sure Chrome is running with --remote-debugging-port=9222",
        )


@router.get("/media/{note_id}/{filename}")
async def serve_media_file(note_id: str, filename: str):
    """Serve a downloaded media file (image or video)."""
    # Validate parameters to prevent path traversal
    if not re.match(r'^[a-zA-Z0-9]+$', note_id):
        raise HTTPException(status_code=400, detail="Invalid note_id")
    if not re.match(r'^\d+\.(jpg|mp4)$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Check images directory first, then videos
    for base_dir in [_IMAGES_DIR, _VIDEOS_DIR]:
        file_path = base_dir / note_id / filename
        if file_path.exists() and file_path.is_file():
            # Security check: ensure within base directory
            try:
                file_path.resolve().relative_to(base_dir.resolve())
            except ValueError:
                raise HTTPException(status_code=403, detail="Access denied")

            media_type = "image/jpeg" if filename.endswith(".jpg") else "video/mp4"
            return FileResponse(str(file_path), media_type=media_type)

    raise HTTPException(status_code=404, detail="Media file not found")
