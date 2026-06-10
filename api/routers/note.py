# -*- coding: utf-8 -*-
"""
API router for fetching Xiaohongshu note content.
"""

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from ..services.note_fetcher import fetch_note_content, NoteFetchError

router = APIRouter(prefix="/note", tags=["note"])


class NoteFetchRequest(BaseModel):
    """Request body for note fetch endpoint."""
    url: str = Field(..., description="Xiaohongshu note URL")


@router.post("/fetch")
async def fetch_note(request: NoteFetchRequest):
    """Fetch note content from a Xiaohongshu note URL.

    Returns note details including title, description, images, and video.
    """
    try:
        result = await fetch_note_content(request.url)
        return {"success": True, "data": result}
    except NoteFetchError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {type(e).__name__}: {str(e)}")
