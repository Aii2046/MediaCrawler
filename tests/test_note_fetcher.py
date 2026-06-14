# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/tests/test_note_fetcher.py
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

"""Tests for XHS Note Content Fetcher feature."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app
from api.schemas.note import (
    NoteFetchRequest,
    NoteFetchResponse,
    NoteImageInfo,
    NoteVideoInfo,
    NoteUserInfo,
    NoteInteractInfo,
)


# -- A. Schema Validation Tests --

class TestNoteSchemas:
    def test_note_fetch_request_valid(self):
        req = NoteFetchRequest(url="https://www.xiaohongshu.com/explore/abc123")
        assert req.url == "https://www.xiaohongshu.com/explore/abc123"
        assert req.download_media is True  # default

    def test_note_fetch_request_with_options(self):
        req = NoteFetchRequest(
            url="https://www.xiaohongshu.com/explore/abc123",
            download_media=False,
        )
        assert req.download_media is False

    def test_note_fetch_request_missing_url(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            NoteFetchRequest()

    def test_note_fetch_response_defaults(self):
        resp = NoteFetchResponse(success=True, note_id="test")
        assert resp.images == []
        assert resp.videos == []
        assert resp.error is None
        assert resp.type is None

    def test_note_fetch_response_error(self):
        resp = NoteFetchResponse(success=False, error="Something went wrong")
        assert resp.success is False
        assert resp.error == "Something went wrong"

    def test_note_user_info(self):
        user = NoteUserInfo(user_id="u1", nickname="Test", avatar="https://img.jpg")
        assert user.user_id == "u1"

    def test_note_interact_info(self):
        info = NoteInteractInfo(liked_count="100", comment_count="5")
        assert info.liked_count == "100"
        assert info.share_count is None

    def test_note_image_info(self):
        img = NoteImageInfo(index=0, url="https://img.jpg")
        assert img.index == 0
        assert img.local_path is None

    def test_note_video_info(self):
        vid = NoteVideoInfo(index=0, url="https://vid.mp4", download_url="/api/note/media/videos/x/0.mp4")
        assert vid.download_url == "/api/note/media/videos/x/0.mp4"


# -- B. NoteFetcher Service Tests --

class TestNoteFetcherService:
    @pytest.mark.asyncio
    async def test_fetch_html_success(self, sample_note_html):
        """Mock httpx to return sample HTML, verify parsing works."""
        from api.services.note_fetcher import NoteFetcher
        fetcher = NoteFetcher()

        mock_response = MagicMock()
        mock_response.text = sample_note_html
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("api.services.note_fetcher.make_async_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)

            html = await fetcher._fetch_html("test_note_123", "token", "pc_search")
            assert "noteDetailMap" in html

    @pytest.mark.asyncio
    async def test_fetch_note_full_flow_no_media(self, sample_note_html):
        """End-to-end: mock HTML fetch, skip media download."""
        from api.services.note_fetcher import NoteFetcher
        fetcher = NoteFetcher()

        mock_response = MagicMock()
        mock_response.text = sample_note_html
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("api.services.note_fetcher.make_async_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await fetcher.fetch_note(
                url="https://www.xiaohongshu.com/explore/test_note_123?xsec_token=tok&xsec_source=pc_search",
                download_media=False,
            )

            assert result.success is True
            assert result.note_id == "test_note_123"
            assert result.title == "Test Note Title"
            assert result.desc == "This is the note description"
            assert result.type == "normal"
            assert result.ip_location == "Shanghai"
            assert len(result.images) == 2
            assert result.images[0].url_default == "https://sns-img-bd.xhscdn.com/img1?w=1080"
            assert result.images[1].url == "https://sns-img-bd.xhscdn.com/img2?w=1080"  # prefers url_default
            assert result.tag_list == ["travel", "photo"]
            assert result.user.nickname == "TestUser"
            assert result.interact_info.liked_count == "100"
            assert result.interact_info.comment_count == "25"

    @pytest.mark.asyncio
    async def test_fetch_note_with_media_download(self, sample_note_html):
        """End-to-end: mock HTML fetch + mock media downloads."""
        from api.services.note_fetcher import NoteFetcher
        fetcher = NoteFetcher()

        mock_html_response = MagicMock()
        mock_html_response.text = sample_note_html
        mock_html_response.raise_for_status = MagicMock()

        mock_media_response = MagicMock()
        mock_media_response.content = b"\xff\xd8\xff\xe0fake_jpeg"
        mock_media_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()

        async def mock_get(url, **kwargs):
            if "xiaohongshu.com/explore/" in url:
                return mock_html_response
            else:
                return mock_media_response

        mock_client.get = AsyncMock(side_effect=mock_get)

        with patch("api.services.note_fetcher.make_async_client") as mock_make, \
             patch("api.services.note_fetcher.xhs_store.update_xhs_note_image",
                   new_callable=AsyncMock) as mock_img_store:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await fetcher.fetch_note(
                url="https://www.xiaohongshu.com/explore/test_note_123?xsec_token=tok&xsec_source=pc_search",
                download_media=True,
            )

            assert result.success is True
            assert len(result.images) == 2
            assert result.images[0].download_url == "/api/note/media/images/test_note_123/0.jpg"
            assert result.images[0].local_path == "data/xhs/images/test_note_123/0.jpg"
            # Verify store was called
            assert mock_img_store.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_note_invalid_url(self):
        """Invalid URL should return error response."""
        from api.services.note_fetcher import NoteFetcher
        fetcher = NoteFetcher()
        result = await fetcher.fetch_note(url="")
        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_fetch_note_not_found(self):
        """HTML without noteDetailMap returns success=False."""
        from api.services.note_fetcher import NoteFetcher
        fetcher = NoteFetcher()

        mock_response = MagicMock()
        mock_response.text = "<html><body>CAPTCHA page</body></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("api.services.note_fetcher.make_async_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await fetcher.fetch_note(
                url="https://www.xiaohongshu.com/explore/fake_note?xsec_token=t&xsec_source=pc"
            )
            assert result.success is False
            assert "not found" in result.error.lower() or "captcha" in result.error.lower()

    @pytest.mark.asyncio
    async def test_fetch_note_network_error(self):
        """Network failure after retries returns error."""
        from api.services.note_fetcher import NoteFetcher
        import httpx
        fetcher = NoteFetcher()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with patch("api.services.note_fetcher.make_async_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_make.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await fetcher.fetch_note(
                url="https://www.xiaohongshu.com/explore/test?xsec_token=t&xsec_source=pc"
            )
            assert result.success is False
            assert "failed" in result.error.lower() or "attempt" in result.error.lower()


# -- C. API Endpoint Tests --

class TestNoteAPIEndpoints:
    def test_post_fetch_success(self):
        client = TestClient(app)
        mock_response = NoteFetchResponse(
            success=True,
            note_id="test_123",
            title="Test Note",
            type="normal",
            desc="A test note",
        )

        with patch("api.routers.note._note_fetcher.fetch_note",
                    new_callable=AsyncMock, return_value=mock_response):
            resp = client.post("/api/note/fetch", json={
                "url": "https://www.xiaohongshu.com/explore/test_123?xsec_token=t&xsec_source=pc",
                "download_media": False,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["note_id"] == "test_123"
            assert data["title"] == "Test Note"

    def test_post_fetch_missing_url(self):
        client = TestClient(app)
        resp = client.post("/api/note/fetch", json={"download_media": True})
        assert resp.status_code == 422  # Missing required 'url' field

    def test_post_fetch_invalid_body(self):
        client = TestClient(app)
        resp = client.post("/api/note/fetch", json="not a json object")
        assert resp.status_code == 422

    def test_get_media_invalid_type(self):
        client = TestClient(app)
        resp = client.get("/api/note/media/invalid_type/test_id/0.jpg")
        assert resp.status_code == 400
        assert "Invalid media type" in resp.json()["detail"]

    def test_get_media_invalid_note_id(self):
        client = TestClient(app)
        resp = client.get("/api/note/media/images/../etc/0.jpg")
        assert resp.status_code in (400, 404)

    def test_get_media_not_found(self):
        client = TestClient(app)
        resp = client.get("/api/note/media/images/nonexistent_id_999/0.jpg")
        assert resp.status_code == 404

    def test_get_media_image_success(self, tmp_path):
        """Create a temp image file and verify it's served correctly."""
        client = TestClient(app)
        img_dir = tmp_path / "xhs" / "images" / "test_id"
        img_dir.mkdir(parents=True)
        img_file = img_dir / "0.jpg"
        img_file.write_bytes(b"\xff\xd8\xff\xe0fake_jpeg_data")

        with patch("api.routers.note.DATA_DIR", tmp_path):
            resp = client.get("/api/note/media/images/test_id/0.jpg")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/jpeg"

    def test_get_media_video_success(self, tmp_path):
        """Create a temp video file and verify it's served correctly."""
        client = TestClient(app)
        vid_dir = tmp_path / "xhs" / "videos" / "test_id"
        vid_dir.mkdir(parents=True)
        vid_file = vid_dir / "0.mp4"
        vid_file.write_bytes(b"\x00\x00\x00\x1cftypmp42fake_video")

        with patch("api.routers.note.DATA_DIR", tmp_path):
            resp = client.get("/api/note/media/videos/test_id/0.mp4")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "video/mp4"

    def test_get_download_attachment(self, tmp_path):
        """Download endpoint should set Content-Disposition attachment."""
        client = TestClient(app)
        img_dir = tmp_path / "xhs" / "images" / "test_id"
        img_dir.mkdir(parents=True)
        img_file = img_dir / "0.jpg"
        img_file.write_bytes(b"\xff\xd8\xff\xe0fake_jpeg_data")

        with patch("api.routers.note.DATA_DIR", tmp_path):
            resp = client.get("/api/note/download/images/test_id/0.jpg")
            assert resp.status_code == 200
            assert "attachment" in resp.headers.get("content-disposition", "")

    def test_note_page_served(self):
        """The /note page should return HTML."""
        client = TestClient(app)
        resp = client.get("/note")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert "Note Content Fetcher" in resp.text


# -- D. URL Parsing Tests --

class TestURLParsing:
    def test_parse_full_url(self):
        from media_platform.xhs.help import parse_note_info_from_note_url
        url = "https://www.xiaohongshu.com/explore/abc123?xsec_token=tok123&xsec_source=pc_search"
        info = parse_note_info_from_note_url(url)
        assert info.note_id == "abc123"
        assert info.xsec_token == "tok123"
        assert info.xsec_source == "pc_search"

    def test_parse_url_without_params(self):
        from media_platform.xhs.help import parse_note_info_from_note_url
        url = "https://www.xiaohongshu.com/explore/abc123"
        info = parse_note_info_from_note_url(url)
        assert info.note_id == "abc123"
        assert info.xsec_token == ""
        assert info.xsec_source == ""

    def test_parse_url_with_extra_path(self):
        from media_platform.xhs.help import parse_note_info_from_note_url
        url = "https://www.xiaohongshu.com/explore/abc123?xsec_token=tok&xsec_source=pc_search&utm=abc"
        info = parse_note_info_from_note_url(url)
        assert info.note_id == "abc123"


# -- E. Extractor Tests --

class TestExtractor:
    def test_extract_note_from_valid_html(self, sample_note_html):
        from media_platform.xhs.extractor import XiaoHongShuExtractor
        extractor = XiaoHongShuExtractor()
        result = extractor.extract_note_detail_from_html("test_note_123", sample_note_html)
        assert result is not None
        assert result.get("title") == "Test Note Title"
        assert result.get("type") == "normal"
        assert result.get("ip_location") == "Shanghai"

    def test_extract_note_from_html_without_state(self):
        from media_platform.xhs.extractor import XiaoHongShuExtractor
        extractor = XiaoHongShuExtractor()
        result = extractor.extract_note_detail_from_html("fake", "<html>no state here</html>")
        assert result is None
