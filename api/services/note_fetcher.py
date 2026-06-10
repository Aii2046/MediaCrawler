# -*- coding: utf-8 -*-
"""
Xiaohongshu note content fetcher service.
Fetches note content (text, images, video) by parsing the note page HTML.
"""

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs

import httpx
import humps


class NoteFetchError(Exception):
    """Error raised when note fetching fails."""
    pass


def parse_note_url(url: str) -> Dict[str, str]:
    """Parse a Xiaohongshu note URL to extract note_id, xsec_token, xsec_source.

    Supports formats:
      - https://www.xiaohongshu.com/explore/{note_id}?xsec_token=...&xsec_source=...
      - https://www.xiaohongshu.com/discovery/item/{note_id}?...
      - https://xhslink.com/xxx (short links)
    """
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")

    # Extract note_id from path
    note_id = path.split("/")[-1]
    if not note_id:
        raise NoteFetchError(f"Cannot extract note_id from URL: {url}")

    # Extract query parameters
    params = parse_qs(parsed.query)
    xsec_token = params.get("xsec_token", [""])[0]
    xsec_source = params.get("xsec_source", ["pc_feed"])[0]

    return {
        "note_id": note_id,
        "xsec_token": xsec_token,
        "xsec_source": xsec_source,
    }


def _extract_initial_state(html: str) -> Optional[Dict]:
    """Extract window.__INITIAL_STATE__ JSON from HTML."""
    match = re.search(r"window\.__INITIAL_STATE__\s*=\s*({.*?})\s*</script>", html, re.DOTALL)
    if not match:
        return None
    raw = match.group(1).replace("undefined", '""')
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _extract_video_url(note_data: Dict) -> str:
    """Extract video URL from note data."""
    if note_data.get("type") != "video":
        return ""

    video_dict = note_data.get("video")
    if not video_dict:
        return ""

    # Try to get origin video without watermark
    consumer = video_dict.get("consumer", {})
    origin_key = consumer.get("origin_video_key", "") or consumer.get("originVideoKey", "")
    if origin_key:
        return f"http://sns-video-bd.xhscdn.com/{origin_key}"

    # Fallback: get from stream
    media = video_dict.get("media", {})
    stream = media.get("stream", {})
    h264_list = stream.get("h264")
    if isinstance(h264_list, list) and h264_list:
        return h264_list[0].get("master_url", "")

    return ""


def _extract_images(note_data: Dict) -> List[Dict[str, str]]:
    """Extract image list from note data."""
    image_list = note_data.get("image_list", [])
    result = []
    for img in image_list:
        url = img.get("url_default") or img.get("url") or ""
        if not url:
            # Try info_list for higher resolution
            info_list = img.get("info_list", [])
            if info_list:
                url = info_list[-1].get("url", "")
        if url:
            # Try to get original size image
            original_url = img.get("url_size_large") or img.get("original") or url
            result.append({
                "url": url,
                "original_url": original_url,
                "width": img.get("width", 0),
                "height": img.get("height", 0),
            })
    return result


def _build_note_response(note_id: str, note_data: Dict) -> Dict[str, Any]:
    """Build structured note response from raw note data."""
    user_info = note_data.get("user", {})
    interact_info = note_data.get("interact_info", {})
    tag_list = note_data.get("tag_list", [])

    images = _extract_images(note_data)
    video_url = _extract_video_url(note_data)
    note_type = note_data.get("type", "normal")

    return {
        "note_id": note_id,
        "type": note_type,
        "title": note_data.get("title", ""),
        "desc": note_data.get("desc", ""),
        "time": note_data.get("time", ""),
        "last_update_time": note_data.get("last_update_time", ""),
        "ip_location": note_data.get("ip_location", ""),
        "user": {
            "user_id": user_info.get("user_id", ""),
            "nickname": user_info.get("nickname", ""),
            "avatar": user_info.get("avatar", ""),
        },
        "interact_info": {
            "liked_count": interact_info.get("liked_count", "0"),
            "collected_count": interact_info.get("collected_count", "0"),
            "comment_count": interact_info.get("comment_count", "0"),
            "share_count": interact_info.get("share_count", "0"),
        },
        "images": images,
        "video_url": video_url,
        "tags": [tag.get("name", "") for tag in tag_list if tag.get("type") == "topic"],
    }


async def fetch_note_content(url: str) -> Dict[str, Any]:
    """Fetch note content from a Xiaohongshu note URL.

    Args:
        url: Full Xiaohongshu note URL

    Returns:
        Dict containing note content (title, desc, images, video, etc.)

    Raises:
        NoteFetchError: If fetching or parsing fails
    """
    # Parse URL
    url_info = parse_note_url(url)
    note_id = url_info["note_id"]
    xsec_token = url_info["xsec_token"]
    xsec_source = url_info["xsec_source"]

    # Build the explore page URL
    page_url = f"https://www.xiaohongshu.com/explore/{note_id}"
    if xsec_token:
        page_url += f"?xsec_token={xsec_token}&xsec_source={xsec_source}"

    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            response = await client.get(page_url, headers=headers)
            response.raise_for_status()
            html = response.text
    except httpx.HTTPError as e:
        raise NoteFetchError(f"Failed to fetch note page: {e}")

    if not html or "noteDetailMap" not in html:
        raise NoteFetchError(
            "Cannot find note data in page HTML. The note may not exist or a CAPTCHA was triggered."
        )

    # Parse __INITIAL_STATE__
    state = _extract_initial_state(html)
    if not state:
        raise NoteFetchError("Failed to parse __INITIAL_STATE__ from HTML")

    # Convert camelCase keys to snake_case
    state = humps.decamelize(state)

    # Extract note detail from state
    note_detail_map = state.get("note", {}).get("note_detail_map", {})
    note_data = note_detail_map.get(note_id, {}).get("note")
    if not note_data:
        # Try alternative key formats
        for key, val in note_detail_map.items():
            if isinstance(val, dict) and "note" in val:
                note_data = val["note"]
                break

    if not note_data:
        raise NoteFetchError(f"Note {note_id} not found in page data")

    return _build_note_response(note_id, note_data)
