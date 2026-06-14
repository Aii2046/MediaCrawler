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

import asyncio
import random
from typing import List, Optional

import httpx

import config
from media_platform.xhs.extractor import XiaoHongShuExtractor
from media_platform.xhs.help import parse_note_info_from_note_url
from model.m_xiaohongshu import NoteUrlInfo
from store import xhs as xhs_store
from tools import utils
from tools.httpx_util import make_async_client

from ..schemas.note import (
    NoteFetchResponse,
    NoteImageInfo,
    NoteInteractInfo,
    NoteUserInfo,
    NoteVideoInfo,
)


class NoteFetcher:
    """Fetches XHS note content via direct HTTP (no Playwright required).

    Uses the HTML-parsing approach: fetches the note explore page and parses
    window.__INITIAL_STATE__ to extract note data. Avoids the need for API
    signing (xhshow), Playwright browser, and session cookies.
    """

    DOMAIN = "https://www.rednote.com" if config.XHS_INTERNATIONAL else "https://www.xiaohongshu.com"
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
    MAX_RETRIES = 3
    RETRY_WAIT = 1.0

    def __init__(self):
        self._extractor = XiaoHongShuExtractor()

    async def fetch_note(self, url: str, download_media: bool = True) -> NoteFetchResponse:
        """Main entry: parse URL -> fetch HTML -> extract -> optionally download media."""
        # 1. Parse URL
        try:
            note_url_info: NoteUrlInfo = parse_note_info_from_note_url(url)
        except Exception as e:
            return NoteFetchResponse(success=False, error=f"Invalid URL: {e}")

        note_id = note_url_info.note_id
        xsec_token = note_url_info.xsec_token
        xsec_source = note_url_info.xsec_source

        if not note_id:
            return NoteFetchResponse(success=False, error="Could not extract note_id from URL")

        # 2. Fetch HTML with retries
        html = None
        for attempt in range(self.MAX_RETRIES):
            try:
                html = await self._fetch_html(note_id, xsec_token, xsec_source)
                break
            except Exception as e:
                utils.logger.warning(
                    f"[NoteFetcher] Fetch HTML attempt {attempt + 1}/{self.MAX_RETRIES} failed: {e}"
                )
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_WAIT)
                else:
                    return NoteFetchResponse(
                        success=False, note_id=note_id,
                        error=f"Failed to fetch note HTML after {self.MAX_RETRIES} attempts: {e}",
                    )

        # 3. Extract note detail from HTML
        note_detail = self._extractor.extract_note_detail_from_html(note_id, html)
        if not note_detail:
            return NoteFetchResponse(
                success=False, note_id=note_id,
                error="Note not found or CAPTCHA appeared in HTML response",
            )

        # 4. Process images
        image_list = note_detail.get("image_list", [])
        images: List[NoteImageInfo] = []
        if download_media:
            images = await self._download_images(note_id, image_list)
        else:
            for i, img in enumerate(image_list):
                url_default = img.get("url_default", "")
                img_url = url_default if url_default else img.get("url", "")
                images.append(NoteImageInfo(index=i, url=img_url, url_default=url_default))

        # 5. Process videos
        videos: List[NoteVideoInfo] = []
        if download_media:
            videos = await self._download_videos(note_id, note_detail)
        else:
            video_urls = xhs_store.get_video_url_arr(note_detail)
            for i, vurl in enumerate(video_urls):
                videos.append(NoteVideoInfo(index=i, url=vurl))

        # 6. Extract tags
        tag_list = [
            tag.get("name", "")
            for tag in note_detail.get("tag_list", [])
            if tag.get("type") == "topic"
        ]

        # 7. Build user info
        user_data = note_detail.get("user", {})
        user = NoteUserInfo(
            user_id=user_data.get("user_id"),
            nickname=user_data.get("nickname"),
            avatar=user_data.get("avatar"),
        )

        # 8. Build interact info
        interact_data = note_detail.get("interact_info", {})
        interact_info = NoteInteractInfo(
            liked_count=interact_data.get("liked_count"),
            collected_count=interact_data.get("collected_count"),
            comment_count=interact_data.get("comment_count"),
            share_count=interact_data.get("share_count"),
        )

        return NoteFetchResponse(
            success=True,
            note_id=note_id,
            type=note_detail.get("type"),
            title=note_detail.get("title") or note_detail.get("desc", "")[:255],
            desc=note_detail.get("desc", ""),
            time=note_detail.get("time"),
            last_update_time=note_detail.get("last_update_time"),
            ip_location=note_detail.get("ip_location", ""),
            user=user,
            interact_info=interact_info,
            images=images,
            videos=videos,
            tag_list=tag_list,
            xsec_token=xsec_token,
            note_url=f"https://www.xiaohongshu.com/explore/{note_id}",
        )

    async def _fetch_html(self, note_id: str, xsec_token: str, xsec_source: str) -> str:
        """Fetch note explore page HTML. Works without Cookie header."""
        url = f"{self.DOMAIN}/explore/{note_id}?xsec_token={xsec_token}&xsec_source={xsec_source}"
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "user-agent": self.USER_AGENT,
            "referer": f"{self.DOMAIN}/",
        }
        async with make_async_client() as client:
            response = await client.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text

    async def _download_images(self, note_id: str, image_list: list) -> List[NoteImageInfo]:
        """Download all images and save locally."""
        results = []
        for i, img in enumerate(image_list):
            url_default = img.get("url_default", "")
            img_url = url_default if url_default else img.get("url", "")
            if not img_url:
                continue

            content = await self._download_media_binary(img_url)
            if content is None:
                # Still record the image even if download fails
                results.append(NoteImageInfo(
                    index=i, url=img_url, url_default=url_default,
                ))
                continue

            filename = f"{i}.jpg"
            await xhs_store.update_xhs_note_image(note_id, content, filename)
            await asyncio.sleep(random.random())

            results.append(NoteImageInfo(
                index=i,
                url=img.get("url", ""),
                url_default=url_default,
                local_path=f"data/xhs/images/{note_id}/{filename}",
                download_url=f"/api/note/media/images/{note_id}/{filename}",
            ))
        return results

    async def _download_videos(self, note_id: str, note_detail: dict) -> List[NoteVideoInfo]:
        """Download all videos and save locally."""
        video_urls = xhs_store.get_video_url_arr(note_detail)
        results = []
        for i, vurl in enumerate(video_urls):
            content = await self._download_media_binary(vurl)
            if content is None:
                results.append(NoteVideoInfo(index=i, url=vurl))
                continue

            filename = f"{i}.mp4"
            await xhs_store.update_xhs_note_video(note_id, content, filename)
            await asyncio.sleep(random.random())

            results.append(NoteVideoInfo(
                index=i,
                url=vurl,
                local_path=f"data/xhs/videos/{note_id}/{filename}",
                download_url=f"/api/note/media/videos/{note_id}/{filename}",
            ))
        return results

    async def _download_media_binary(self, url: str) -> Optional[bytes]:
        """Download media binary content via httpx."""
        async with make_async_client() as client:
            try:
                response = await client.get(url, timeout=60)
                response.raise_for_status()
                return response.content
            except httpx.HTTPError as e:
                utils.logger.error(f"[NoteFetcher] Download failed for {url}: {e}")
                return None
