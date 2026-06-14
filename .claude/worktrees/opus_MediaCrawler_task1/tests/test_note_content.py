# -*- coding: utf-8 -*-
import pytest
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient

from api.main import app
from api.schemas.note_content import (
    NoteContentItem,
    NoteImageInfo,
    NoteInteractInfo,
    NoteUserInfo,
    NoteVideoInfo,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_note_item():
    return NoteContentItem(
        note_id="abc123def456",
        note_type="normal",
        title="Test Note Title",
        description="This is a test note description.",
        user=NoteUserInfo(user_id="u001", nickname="testuser", avatar="https://example.com/avatar.jpg"),
        interact_info=NoteInteractInfo(liked_count=100, collected_count=50, comment_count=20, share_count=10),
        images=[
            NoteImageInfo(url="https://cdn.example.com/img1.jpg"),
            NoteImageInfo(url="https://cdn.example.com/img2.jpg"),
        ],
        tags=["travel", "food"],
        ip_location="Shanghai",
        time=1700000000,
        note_url="https://www.xiaohongshu.com/explore/abc123def456?xsec_token=token&xsec_source=pc_feed",
    )


VALID_URL = "https://www.xiaohongshu.com/explore/abc123def456?xsec_token=testtoken&xsec_source=pc_feed"
VALID_COOKIES = "a1=abc123; webId=xyz789; web_session=sess001"


class TestFetchNoteContent:
    def test_rejects_empty_cookies(self, client):
        response = client.post("/api/note/fetch", json={
            "note_urls": [VALID_URL],
            "cookies": "",
        })
        assert response.status_code == 422  # Pydantic validation: min_length=1

    def test_rejects_cookies_without_a1(self, client):
        response = client.post("/api/note/fetch", json={
            "note_urls": [VALID_URL],
            "cookies": "webId=xyz789; web_session=sess001",
        })
        assert response.status_code == 400
        assert "a1" in response.json()["detail"]

    def test_rejects_empty_urls(self, client):
        response = client.post("/api/note/fetch", json={
            "note_urls": [],
            "cookies": VALID_COOKIES,
        })
        assert response.status_code == 422  # Pydantic validation: min_length=1

    def test_successful_fetch(self, client, sample_note_item):
        with patch(
            "api.routers.note_content.note_content_service.fetch_notes",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = ([sample_note_item], [])
            response = client.post("/api/note/fetch", json={
                "note_urls": [VALID_URL],
                "cookies": VALID_COOKIES,
            })
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["notes"]) == 1
            assert data["notes"][0]["note_id"] == "abc123def456"
            assert data["notes"][0]["title"] == "Test Note Title"
            assert len(data["notes"][0]["images"]) == 2
            mock_fetch.assert_called_once()

    def test_partial_failure(self, client, sample_note_item):
        with patch(
            "api.routers.note_content.note_content_service.fetch_notes",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = (
                [sample_note_item],
                ["https://bad-url.com: Failed to fetch"],
            )
            response = client.post("/api/note/fetch", json={
                "note_urls": [VALID_URL, "https://bad-url.com"],
                "cookies": VALID_COOKIES,
            })
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["notes"]) == 1
            assert len(data["errors"]) == 1

    def test_all_failed(self, client):
        with patch(
            "api.routers.note_content.note_content_service.fetch_notes",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = ([], ["url1: error1"])
            response = client.post("/api/note/fetch", json={
                "note_urls": [VALID_URL],
                "cookies": VALID_COOKIES,
            })
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False

    def test_video_note(self, client):
        video_note = NoteContentItem(
            note_id="vid001",
            note_type="video",
            title="Video Note",
            description="A video",
            user=NoteUserInfo(user_id="u1", nickname="user1", avatar=""),
            interact_info=NoteInteractInfo(),
            video=NoteVideoInfo(urls=["https://cdn.example.com/video.mp4"]),
            tags=[],
            note_url="https://www.xiaohongshu.com/explore/vid001",
        )
        with patch(
            "api.routers.note_content.note_content_service.fetch_notes",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = ([video_note], [])
            response = client.post("/api/note/fetch", json={
                "note_urls": [VALID_URL],
                "cookies": VALID_COOKIES,
            })
            assert response.status_code == 200
            data = response.json()
            assert data["notes"][0]["video"]["urls"][0] == "https://cdn.example.com/video.mp4"


class TestServeMedia:
    def test_media_not_found(self, client):
        response = client.get("/api/note/media/abc123/0.jpg")
        assert response.status_code == 404

    def test_invalid_note_id(self, client):
        response = client.get("/api/note/media/../../etc/0.jpg")
        assert response.status_code in (400, 404)  # framework may normalize path

    def test_invalid_filename(self, client):
        response = client.get("/api/note/media/abc123/evil.sh")
        assert response.status_code == 400

    def test_path_traversal_in_note_id(self, client):
        response = client.get("/api/note/media/abc%2F..%2F..%2Fetc/0.jpg")
        assert response.status_code in (400, 404)  # framework may normalize path


class TestNoteContentService:
    def test_parse_cookie_string(self):
        from api.services.note_content_service import NoteContentService
        svc = NoteContentService()
        result = svc._parse_cookie_string("a1=abc; webId=xyz; key=val")
        assert result == {"a1": "abc", "webId": "xyz", "key": "val"}

    def test_parse_cookie_string_empty(self):
        from api.services.note_content_service import NoteContentService
        svc = NoteContentService()
        result = svc._parse_cookie_string("")
        assert result == {}

    def test_parse_cookie_string_with_equals_in_value(self):
        from api.services.note_content_service import NoteContentService
        svc = NoteContentService()
        result = svc._parse_cookie_string("token=abc=def=ghi; a1=val")
        assert result == {"token": "abc=def=ghi", "a1": "val"}


class TestNoteContentPage:
    def test_note_content_page_served(self, client):
        response = client.get("/note-content")
        assert response.status_code == 200
        assert b"Note Content Fetcher" in response.content
