# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/tests/test_query_api.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

"""
Tests for the query API — schemas, platform registry, query service, and endpoints.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from contextlib import asynccontextmanager

import config
from fastapi.testclient import TestClient
from api.main import app
from api.schemas.query import ContentQueryRequest, ContentQueryResponse, CommentQueryResponse
from api.schemas.crawler import PlatformEnum
from api.services.platform_registry import (
    get_platform_mapping,
    get_supported_platforms,
    PLATFORM_REGISTRY,
)
from api.services.query_service import (
    is_db_backend_available,
    _convert_time_to_field,
    _normalize_time_from_field,
    _make_numeric_expr,
    QueryService,
)


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------

class TestContentQueryRequestSchema:

    def test_valid_minimal_request(self):
        req = ContentQueryRequest(platform=PlatformEnum.XHS)
        assert req.platform == PlatformEnum.XHS
        assert req.page == 1
        assert req.page_size == 20
        assert req.sort_by == "time"
        assert req.sort_order == "desc"
        assert req.keyword is None
        assert req.min_likes is None

    def test_valid_full_request(self):
        req = ContentQueryRequest(
            platform=PlatformEnum.DOUYIN,
            keyword="python",
            start_time=1700000000,
            end_time=1710000000,
            min_likes=100,
            max_likes=10000,
            min_comments=10,
            max_comments=500,
            min_shares=5,
            max_shares=200,
            sort_by="liked_count",
            sort_order="asc",
            page=3,
            page_size=50,
        )
        assert req.keyword == "python"
        assert req.min_likes == 100
        assert req.page == 3
        assert req.page_size == 50

    def test_invalid_page_zero(self):
        with pytest.raises(Exception):
            ContentQueryRequest(platform=PlatformEnum.XHS, page=0)

    def test_invalid_page_size_zero(self):
        with pytest.raises(Exception):
            ContentQueryRequest(platform=PlatformEnum.XHS, page_size=0)

    def test_invalid_page_size_too_large(self):
        with pytest.raises(Exception):
            ContentQueryRequest(platform=PlatformEnum.XHS, page_size=101)

    def test_invalid_negative_min_likes(self):
        with pytest.raises(Exception):
            ContentQueryRequest(platform=PlatformEnum.XHS, min_likes=-1)

    def test_invalid_sort_order(self):
        with pytest.raises(Exception):
            ContentQueryRequest(platform=PlatformEnum.XHS, sort_order="invalid")


# ---------------------------------------------------------------------------
# Platform registry tests
# ---------------------------------------------------------------------------

class TestPlatformRegistry:

    def test_all_seven_platforms_registered(self):
        platforms = get_supported_platforms()
        assert set(platforms) == {"xhs", "dy", "bili", "ks", "wb", "tieba", "zhihu"}

    def test_get_mapping_valid_platform(self):
        mapping = get_platform_mapping("xhs")
        assert mapping.content_id_field == "note_id"
        assert mapping.time_field == "time"
        assert mapping.time_format == "milliseconds"
        assert mapping.likes_field == "liked_count"
        assert mapping.likes_is_int is False

    def test_get_mapping_bilibili(self):
        mapping = get_platform_mapping("bili")
        assert mapping.content_id_field == "video_id"
        assert mapping.likes_field == "liked_count"
        assert mapping.likes_is_int is True  # Bilibili likes are Integer
        assert mapping.comments_field == "video_comment"

    def test_get_mapping_zhihu(self):
        mapping = get_platform_mapping("zhihu")
        assert mapping.likes_field == "voteup_count"
        assert mapping.likes_is_int is True
        assert mapping.comments_is_int is True

    def test_get_mapping_weibo_no_title(self):
        mapping = get_platform_mapping("wb")
        assert mapping.title_field is None
        assert mapping.desc_field == "content"

    def test_get_mapping_kuaishou_limited_engagement(self):
        mapping = get_platform_mapping("ks")
        assert mapping.comments_field is None
        assert mapping.shares_field is None

    def test_get_mapping_tieba_no_engagement(self):
        mapping = get_platform_mapping("tieba")
        assert mapping.likes_field is None
        assert mapping.comments_field is None
        assert mapping.shares_field is None
        assert mapping.time_format == "string"

    def test_get_mapping_unknown_platform_raises(self):
        with pytest.raises(ValueError, match="Unknown platform"):
            get_platform_mapping("unknown")

    def test_every_platform_has_content_and_comment_models(self):
        for key, mapping in PLATFORM_REGISTRY.items():
            assert mapping.model is not None, f"{key} missing content model"
            assert mapping.comment_model is not None, f"{key} missing comment model"


# ---------------------------------------------------------------------------
# Time conversion tests
# ---------------------------------------------------------------------------

class TestTimeConversion:

    def test_milliseconds_forward(self):
        assert _convert_time_to_field(1700000000, "milliseconds") == 1700000000000

    def test_seconds_forward(self):
        assert _convert_time_to_field(1700000000, "seconds") == 1700000000

    def test_string_forward(self):
        result = _convert_time_to_field(1700000000, "string")
        assert isinstance(result, str)
        assert "2023" in result  # 1700000000 is Nov 2023

    def test_milliseconds_normalize(self):
        assert _normalize_time_from_field(1700000000000, "milliseconds") == 1700000000

    def test_seconds_normalize(self):
        assert _normalize_time_from_field(1700000000, "seconds") == 1700000000

    def test_string_normalize(self):
        result = _normalize_time_from_field("2023-11-14 22:13:20", "string")
        assert isinstance(result, int)
        assert result > 0

    def test_none_normalize(self):
        assert _normalize_time_from_field(None, "seconds") is None

    def test_invalid_string_normalize(self):
        assert _normalize_time_from_field("not-a-date", "string") is None


# ---------------------------------------------------------------------------
# DB backend check tests
# ---------------------------------------------------------------------------

class TestDbBackendCheck:

    def test_jsonl_is_not_db(self):
        with patch.object(config, "SAVE_DATA_OPTION", "jsonl"):
            assert is_db_backend_available() is False

    def test_csv_is_not_db(self):
        with patch.object(config, "SAVE_DATA_OPTION", "csv"):
            assert is_db_backend_available() is False

    def test_json_is_not_db(self):
        with patch.object(config, "SAVE_DATA_OPTION", "json"):
            assert is_db_backend_available() is False

    def test_sqlite_is_db(self):
        with patch.object(config, "SAVE_DATA_OPTION", "sqlite"):
            assert is_db_backend_available() is True

    def test_mysql_is_db(self):
        with patch.object(config, "SAVE_DATA_OPTION", "db"):
            assert is_db_backend_available() is True

    def test_postgres_is_db(self):
        with patch.object(config, "SAVE_DATA_OPTION", "postgres"):
            assert is_db_backend_available() is True


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestQueryEndpoints:

    def test_query_content_returns_400_for_file_backend(self):
        """When SAVE_DATA_OPTION is file-based, query endpoints should return 400."""
        client = TestClient(app)
        with patch.object(config, "SAVE_DATA_OPTION", "jsonl"):
            response = client.post("/api/query/content", json={
                "platform": "xhs",
                "keyword": "test",
            })
        assert response.status_code == 400
        assert "database backend" in response.json()["detail"].lower()

    def test_query_stats_returns_400_for_file_backend(self):
        client = TestClient(app)
        with patch.object(config, "SAVE_DATA_OPTION", "jsonl"):
            response = client.get("/api/query/stats")
        assert response.status_code == 400

    def test_query_comments_returns_400_for_file_backend(self):
        client = TestClient(app)
        with patch.object(config, "SAVE_DATA_OPTION", "jsonl"):
            response = client.get("/api/query/comments/xhs/some_id")
        assert response.status_code == 400

    def test_query_content_detail_returns_400_for_file_backend(self):
        client = TestClient(app)
        with patch.object(config, "SAVE_DATA_OPTION", "csv"):
            response = client.get("/api/query/content/xhs/some_id")
        assert response.status_code == 400

    def test_query_content_invalid_page(self):
        """Pydantic validation should reject invalid page."""
        client = TestClient(app)
        with patch.object(config, "SAVE_DATA_OPTION", "sqlite"):
            response = client.post("/api/query/content", json={
                "platform": "xhs",
                "page": 0,
            })
        assert response.status_code == 422

    def test_query_content_invalid_page_size(self):
        """Pydantic validation should reject page_size > 100."""
        client = TestClient(app)
        with patch.object(config, "SAVE_DATA_OPTION", "sqlite"):
            response = client.post("/api/query/content", json={
                "platform": "xhs",
                "page_size": 200,
            })
        assert response.status_code == 422

    def test_query_content_unknown_platform(self):
        """Pydantic validation should reject unknown platform enum."""
        client = TestClient(app)
        with patch.object(config, "SAVE_DATA_OPTION", "sqlite"):
            response = client.post("/api/query/content", json={
                "platform": "unknown_platform",
            })
        assert response.status_code == 422

    def test_query_content_success_with_mocked_service(self):
        """Successful query with mocked query service."""
        client = TestClient(app)
        mock_response = ContentQueryResponse(
            items=[{"id": 1, "title": "Test"}],
            total=1,
            page=1,
            page_size=20,
            total_pages=1,
            platform="xhs",
        )
        with patch.object(config, "SAVE_DATA_OPTION", "sqlite"):
            with patch(
                "api.routers.query.query_service.query_content",
                new_callable=AsyncMock,
                return_value=mock_response,
            ):
                response = client.post("/api/query/content", json={
                    "platform": "xhs",
                    "keyword": "test",
                })
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["platform"] == "xhs"
        assert len(data["items"]) == 1

    def test_query_comments_success_with_mocked_service(self):
        """Successful comments query with mocked service."""
        client = TestClient(app)
        mock_response = CommentQueryResponse(
            items=[{"id": 1, "content": "Nice!"}],
            total=1,
            page=1,
            page_size=20,
            total_pages=1,
            platform="xhs",
            content_id="abc123",
        )
        with patch.object(config, "SAVE_DATA_OPTION", "sqlite"):
            with patch(
                "api.routers.query.query_service.query_comments",
                new_callable=AsyncMock,
                return_value=mock_response,
            ):
                response = client.get("/api/query/comments/xhs/abc123")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["content_id"] == "abc123"

    def test_content_detail_not_found(self):
        """404 when content doesn't exist."""
        client = TestClient(app)
        with patch.object(config, "SAVE_DATA_OPTION", "sqlite"):
            with patch(
                "api.routers.query.query_service.get_content_detail",
                new_callable=AsyncMock,
                return_value=None,
            ):
                response = client.get("/api/query/content/xhs/nonexistent")
        assert response.status_code == 404
