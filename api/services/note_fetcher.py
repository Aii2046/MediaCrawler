# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/services/note_fetcher.py
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
Lightweight note content fetcher service.
Fetches XHS note page HTML via httpx and parses note content
(title, description, images, video) without requiring a full browser session.
"""

import re
import json
from typing import Dict, List, Optional

import httpx
import humps


# Default headers mimicking a real browser
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.xiaohongshu.com/",
    "Sec-Ch-Ua": '"Chromium";v="126", "Google Chrome";v="126", "Not-A.Brand";v="8"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

# XHS domains
XHS_DOMAIN = "https://www.xiaohongshu.com"
XHS_INTL_DOMAIN = "https://www.rednote.com"


def _get_domain(international: bool = False) -> str:
    return XHS_INTL_DOMAIN if international else XHS_DOMAIN


def parse_note_url(url: str) -> Dict:
    """Parse a XHS note URL to extract note_id, xsec_token, xsec_source.

    Args:
        url: Full XHS note URL

    Returns:
        Dict with keys: note_id, xsec_token, xsec_source
    """
    # Extract note_id from path
    path_part = url.split("?")[0]
    note_id = path_part.rstrip("/").split("/")[-1]

    # Extract query params
    xsec_token = ""
    xsec_source = ""
    if "?" in url:
        query_string = url.split("?")[1]
        params = {}
        for pair in query_string.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                params[k] = v
        xsec_token = params.get("xsec_token", "")
        xsec_source = params.get("xsec_source", "")

    return {
        "note_id": note_id,
        "xsec_token": xsec_token,
        "xsec_source": xsec_source,
    }


def extract_note_from_html(html: str, note_id: str) -> Optional[Dict]:
    """Extract note detail from HTML by parsing window.__INITIAL_STATE__.

    Args:
        html: Raw HTML string from XHS explore page
        note_id: The note ID to extract

    Returns:
        Dict with note details or None if parsing fails
    """
    if "noteDetailMap" not in html and "note_detail_map" not in html:
        return None

    # Match the __INITIAL_STATE__ script
    match = re.search(r"window\.__INITIAL_STATE__=({.*?})</script>", html, re.DOTALL)
    if not match:
        return None

    state_str = match.group(1).replace("undefined", '""')
    if state_str == "{}":
        return None

    try:
        state = json.loads(state_str)
        # Convert camelCase to snake_case for consistent access
        state = humps.decamelize(state)
        note_map = state.get("note", {}).get("note_detail_map", {})
        note_data = note_map.get(note_id, {}).get("note")
        return note_data
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def _extract_image_urls(image_list: List[Dict]) -> List[Dict]:
    """Extract usable image URLs from the image_list array.

    Args:
        image_list: Raw image list from note data

    Returns:
        List of dicts with url, width, height
    """
    results = []
    for img in image_list:
        # Prefer url_default, then url, then url_pre
        url = img.get("url_default") or img.get("url") or img.get("url_pre", "")
        if not url:
            # Try info_list for different format URLs
            info_list = img.get("info_list", [])
            for info in info_list:
                if info.get("url"):
                    url = info["url"]
                    break
        if url:
            results.append({
                "url": url,
                "width": img.get("width", 0),
                "height": img.get("height", 0),
            })
    return results


def _extract_video_url(note_item: Dict) -> Optional[str]:
    """Extract video URL from note data.

    Args:
        note_item: Raw note data dict

    Returns:
        Video URL string or None
    """
    if note_item.get("type") != "video":
        return None

    video_dict = note_item.get("video", {})
    if not video_dict:
        return None

    # Try consumer origin_video_key
    consumer = video_dict.get("consumer", {})
    origin_video_key = consumer.get("origin_video_key", "") or consumer.get("originVideoKey", "")
    if origin_video_key:
        return f"http://sns-video-bd.xhscdn.com/{origin_video_key}"

    # Fallback: media.stream.h264
    media = video_dict.get("media", {})
    stream = media.get("stream", {})
    h264_streams = stream.get("h264", [])
    if isinstance(h264_streams, list):
        for v in h264_streams:
            master_url = v.get("master_url")
            if master_url:
                return master_url

    return None


def _sanitize_string(s: str) -> str:
    """Remove surrogate characters that can cause JSON serialization issues."""
    if not isinstance(s, str):
        return s
    try:
        s.encode('utf-8')
        return s
    except UnicodeEncodeError:
        return s.encode('utf-8', errors='replace').decode('utf-8')


def structure_note_content(note_data: Dict) -> Dict:
    """Structure raw note data into a clean response format.

    Args:
        note_data: Raw note dict from HTML parsing

    Returns:
        Structured dict with title, desc, type, images, video, user info, etc.
    """
    user_info = note_data.get("user", {})
    interact_info = note_data.get("interact_info", {})
    image_list_raw = note_data.get("image_list", [])
    tag_list_raw = note_data.get("tag_list", [])

    note_id = note_data.get("note_id", "")
    xsec_token = note_data.get("xsec_token", "")

    # Extract images
    images = _extract_image_urls(image_list_raw)

    # Extract video
    video_url = _extract_video_url(note_data)

    # Extract tags (only topic type)
    tags = [
        _sanitize_string(tag.get("name", ""))
        for tag in tag_list_raw
        if tag.get("type") == "topic" and tag.get("name")
    ]

    return {
        "note_id": note_id,
        "type": note_data.get("type", "normal"),
        "title": _sanitize_string(note_data.get("title", "") or note_data.get("desc", "")[:255]),
        "desc": _sanitize_string(note_data.get("desc", "")),
        "time": note_data.get("time"),
        "last_update_time": note_data.get("last_update_time"),
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
        "ip_location": note_data.get("ip_location", ""),
        "images": images,
        "image_count": len(images),
        "video_url": video_url,
        "tags": tags,
        "note_url": f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source=pc_feed",
        "xsec_token": xsec_token,
    }


async def fetch_note_content(
    note_url: str,
    international: bool = False,
    cookies: str = "",
) -> Dict:
    """Fetch and parse note content from a XHS note URL.

    This is the main entry point for the note content fetch service.

    Args:
        note_url: Full XHS note URL
        international: Whether to use international (rednote.com) domain
        cookies: Optional cookie string for authenticated access

    Returns:
        Dict with structured note content or error info

    Raises:
        ValueError: If URL is invalid or note not found
        httpx.HTTPError: If network request fails
    """
    # Parse URL
    url_info = parse_note_url(note_url)
    note_id = url_info["note_id"]
    xsec_token = url_info["xsec_token"]
    xsec_source = url_info["xsec_source"] or "pc_feed"

    if not note_id:
        raise ValueError("Invalid note URL: could not extract note ID")

    # Build request URL
    domain = _get_domain(international)
    request_url = f"{domain}/explore/{note_id}?xsec_token={xsec_token}&xsec_source={xsec_source}"

    # Build headers
    headers = DEFAULT_HEADERS.copy()
    if cookies:
        headers["Cookie"] = cookies

    # Fetch HTML
    async with httpx.AsyncClient(
        follow_redirects=True,
        verify=False,
        timeout=30.0,
    ) as client:
        response = await client.get(request_url, headers=headers)
        response.raise_for_status()
        # Ensure UTF-8 encoding for Chinese content
        response.encoding = "utf-8"
        html = response.text

    # Parse note content from HTML
    note_data = extract_note_from_html(html, note_id)
    if not note_data:
        raise ValueError(
            f"Could not extract note content for ID: {note_id}. "
            "The note may not exist, may require login, or the page structure has changed."
        )

    # Attach xsec_token to note_data for URL construction
    note_data["xsec_token"] = xsec_token

    # Structure the response
    return structure_note_content(note_data)
