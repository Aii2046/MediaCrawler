# -*- coding: utf-8 -*-
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tenacity import RetryError

from api.schemas.note_content import (
    NoteContentItem,
    NoteImageInfo,
    NoteInteractInfo,
    NoteUserInfo,
    NoteVideoInfo,
)
from media_platform.xhs.client import XiaoHongShuClient
from media_platform.xhs.help import parse_note_info_from_note_url
from store.xhs import get_video_url_arr
from store.xhs.xhs_store_media import XiaoHongShuImage, XiaoHongShuVideo

logger = logging.getLogger(__name__)


class NoteContentService:
    """Lightweight service for fetching XHS note content without a browser."""

    def _parse_cookie_string(self, cookie_str: str) -> Dict[str, str]:
        """Parse 'key1=val1; key2=val2' into dict."""
        result = {}
        for item in cookie_str.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                result[key.strip()] = value.strip()
        return result

    def _create_xhs_client(self, cookie_str: str) -> XiaoHongShuClient:
        """Create XiaoHongShuClient with cookies only (no Playwright page needed)."""
        cookie_dict = self._parse_cookie_string(cookie_str)
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://www.xiaohongshu.com",
            "pragma": "no-cache",
            "priority": "u=1, i",
            "referer": "https://www.xiaohongshu.com/",
            "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "Cookie": cookie_str,
        }
        # playwright_page=None is safe: signing uses pure Python xhshow library,
        # the page parameter is vestigial and never used for signing or API calls.
        return XiaoHongShuClient(
            headers=headers,
            playwright_page=None,  # type: ignore[arg-type]
            cookie_dict=cookie_dict,
        )

    def _extract_images(self, note_detail: Dict) -> List[NoteImageInfo]:
        """Extract image info from note detail."""
        image_list = note_detail.get("image_list", [])
        images = []
        for img in image_list:
            url = img.get("url_default") or img.get("url", "")
            if url:
                images.append(NoteImageInfo(url=url))
        return images

    def _extract_video(self, note_detail: Dict) -> Optional[NoteVideoInfo]:
        """Extract video info from note detail."""
        video_urls = get_video_url_arr(note_detail)
        if video_urls:
            return NoteVideoInfo(urls=video_urls)
        return None

    def _build_note_content_item(self, note_detail: Dict, note_url: str) -> NoteContentItem:
        """Build NoteContentItem from raw note detail dict."""
        user_info = note_detail.get("user", {})
        interact_info = note_detail.get("interact_info", {})
        tag_list = note_detail.get("tag_list", [])

        return NoteContentItem(
            note_id=note_detail.get("note_id", ""),
            note_type=note_detail.get("type", "normal"),
            title=note_detail.get("title", ""),
            description=note_detail.get("desc", ""),
            user=NoteUserInfo(
                user_id=user_info.get("user_id", ""),
                nickname=user_info.get("nickname", ""),
                avatar=user_info.get("avatar", ""),
            ),
            interact_info=NoteInteractInfo(
                liked_count=int(interact_info.get("liked_count", 0)),
                collected_count=int(interact_info.get("collected_count", 0)),
                comment_count=int(interact_info.get("comment_count", 0)),
                share_count=int(interact_info.get("share_count", 0)),
            ),
            images=self._extract_images(note_detail),
            video=self._extract_video(note_detail),
            tags=[tag.get("name", "") for tag in tag_list if tag.get("type") == "topic"],
            ip_location=note_detail.get("ip_location", ""),
            time=note_detail.get("time"),
            note_url=note_url,
        )

    async def _download_media(self, client: XiaoHongShuClient, note_id: str,
                              item: NoteContentItem) -> None:
        """Download images and videos for a note."""
        img_store = XiaoHongShuImage()
        for i, img in enumerate(item.images):
            content = await client.get_note_media(img.url)
            if content:
                filename = f"{i}.jpg"
                await img_store.store_image({
                    "notice_id": note_id,
                    "pic_content": content,
                    "extension_file_name": filename,
                })
                img.filename = filename

        if item.video and item.video.urls:
            vid_store = XiaoHongShuVideo()
            for i, url in enumerate(item.video.urls):
                content = await client.get_note_media(url)
                if content:
                    filename = f"{i}.mp4"
                    await vid_store.store_video({
                        "notice_id": note_id,
                        "video_content": content,
                        "extension_file_name": filename,
                    })
                    item.video.filename = filename

    async def fetch_note(self, note_url: str, cookies: str,
                         download_media: bool = False) -> NoteContentItem:
        """Fetch a single note's content."""
        note_info = parse_note_info_from_note_url(note_url)
        client = self._create_xhs_client(cookies)

        note_detail = {}
        try:
            note_detail = await client.get_note_by_id(
                note_info.note_id, note_info.xsec_source, note_info.xsec_token
            )
        except RetryError:
            logger.warning(f"API fetch failed for {note_info.note_id}, trying HTML fallback")

        if not note_detail:
            note_detail = await client.get_note_by_id_from_html(
                note_info.note_id, note_info.xsec_source, note_info.xsec_token,
                enable_cookie=True,
            )

        if not note_detail:
            raise ValueError(f"Failed to fetch note: {note_info.note_id}")

        note_detail["xsec_token"] = note_info.xsec_token
        note_detail["xsec_source"] = note_info.xsec_source

        item = self._build_note_content_item(note_detail, note_url)

        if download_media:
            await self._download_media(client, note_info.note_id, item)

        return item

    async def fetch_notes(self, note_urls: List[str], cookies: str,
                          download_media: bool = False) -> Tuple[List[NoteContentItem], List[str]]:
        """Fetch multiple notes, collecting per-URL errors."""
        notes = []
        errors = []
        for url in note_urls:
            try:
                item = await self.fetch_note(url, cookies, download_media)
                notes.append(item)
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                errors.append(f"{url}: {str(e)}")
        return notes, errors


    async def fetch_cookies_from_browser(self) -> str:
        """Connect to a running Chrome via CDP and extract XHS cookies."""
        from playwright.async_api import async_playwright
        from tools.cdp_browser import CDPBrowserManager
        from tools.crawler_util import convert_browser_context_cookies

        async with async_playwright() as playwright:
            mgr = CDPBrowserManager()
            try:
                browser_context = await mgr.launch_and_connect(playwright)
                cookie_str, _ = await convert_browser_context_cookies(
                    browser_context, urls=["https://www.xiaohongshu.com"]
                )
                return cookie_str
            finally:
                # Disconnect but don't kill the user's browser
                if mgr.browser:
                    try:
                        mgr.browser.close()
                    except Exception:
                        pass
                    mgr.browser = None
                mgr.browser_context = None


# Module-level singleton
note_content_service = NoteContentService()
