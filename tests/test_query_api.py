# -*- coding: utf-8 -*-
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app
from api.schemas.query import PaginatedResponse, QueryRequest
from api.services.query_service import (
    MODEL_REGISTRY,
    build_query,
    get_model_meta,
)


client = TestClient(app)

MOCK_PAGINATED = PaginatedResponse(
    data=[{"id": 1, "title": "test"}],
    total=1,
    page=1,
    page_size=20,
    total_pages=1,
)


# ---- Model registry tests ----

def test_registry_covers_all_platforms():
    platforms = {key[0] for key in MODEL_REGISTRY}
    assert platforms == {"xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu"}


def test_get_model_meta_valid():
    meta = get_model_meta("xhs", "content")
    assert meta is not None
    assert meta.model.__tablename__ == "xhs_note"


def test_get_model_meta_invalid():
    assert get_model_meta("invalid", "content") is None
    assert get_model_meta("ks", "creators") is None


# ---- build_query unit tests ----

def test_build_query_default_pagination():
    meta = get_model_meta("xhs", "content")
    params = QueryRequest()
    data_stmt, count_stmt = build_query(meta, params)
    # Statements should compile without error
    assert data_stmt is not None
    assert count_stmt is not None


def test_build_query_with_keyword():
    meta = get_model_meta("xhs", "content")
    params = QueryRequest(keyword="python")
    data_stmt, _ = build_query(meta, params)
    compiled = str(data_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "LIKE" in compiled
    assert "%python%" in compiled


def test_build_query_with_time_range():
    meta = get_model_meta("xhs", "content")
    params = QueryRequest(time_start=1700000000, time_end=1800000000)
    data_stmt, _ = build_query(meta, params)
    compiled = str(data_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "1700000000" in compiled
    assert "1800000000" in compiled


def test_build_query_skips_time_for_string_fields():
    meta = get_model_meta("tieba", "content")
    assert meta.time_is_numeric is False
    params = QueryRequest(time_start=1700000000)
    data_stmt, _ = build_query(meta, params)
    compiled = str(data_stmt.compile(compile_kwargs={"literal_binds": True}))
    # Should NOT have the timestamp filter since time_is_numeric is False
    assert "1700000000" not in compiled


def test_build_query_with_source_keyword():
    meta = get_model_meta("dy", "content")
    params = QueryRequest(source_keyword="travel")
    data_stmt, _ = build_query(meta, params)
    compiled = str(data_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "source_keyword" in compiled
    assert "travel" in compiled


def test_build_query_with_user_id():
    meta = get_model_meta("xhs", "content")
    params = QueryRequest(user_id="user_123")
    data_stmt, _ = build_query(meta, params)
    compiled = str(data_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "user_id" in compiled
    assert "user_123" in compiled


def test_build_query_with_min_likes():
    meta = get_model_meta("xhs", "content")
    params = QueryRequest(min_likes=100)
    data_stmt, _ = build_query(meta, params)
    compiled = str(data_stmt.compile(compile_kwargs={"literal_binds": True}))
    # liked_count is Text, so should have CAST
    assert "CAST" in compiled or "cast" in compiled.lower()


def test_build_query_sorting_asc():
    meta = get_model_meta("xhs", "content")
    params = QueryRequest(sort_by="time", sort_order="asc")
    data_stmt, _ = build_query(meta, params)
    compiled = str(data_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "ASC" in compiled


def test_build_query_pagination_offset():
    meta = get_model_meta("xhs", "content")
    params = QueryRequest(page=3, page_size=10)
    data_stmt, _ = build_query(meta, params)
    compiled = str(data_stmt.compile(compile_kwargs={"literal_binds": True}))
    # offset should be (3-1)*10 = 20
    assert "20" in compiled


# ---- API endpoint tests ----

@patch("api.routers.query.query_data", new_callable=AsyncMock)
def test_query_content_success(mock_query):
    mock_query.return_value = MOCK_PAGINATED
    response = client.get("/api/query/xhs/content")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert len(data["data"]) == 1


@patch("api.routers.query.query_data", new_callable=AsyncMock)
def test_query_comments_success(mock_query):
    mock_query.return_value = MOCK_PAGINATED
    response = client.get("/api/query/dy/comments")
    assert response.status_code == 200
    assert response.json()["total"] == 1


@patch("api.routers.query.query_data", new_callable=AsyncMock)
def test_query_creators_success(mock_query):
    mock_query.return_value = MOCK_PAGINATED
    response = client.get("/api/query/bili/creators")
    assert response.status_code == 200


@patch("api.routers.query.query_data", new_callable=AsyncMock)
def test_query_with_all_params(mock_query):
    mock_query.return_value = MOCK_PAGINATED
    response = client.get("/api/query/xhs/content", params={
        "page": 2,
        "page_size": 10,
        "sort_by": "liked_count",
        "sort_order": "desc",
        "keyword": "python",
        "source_keyword": "test",
        "time_start": 1700000000,
        "time_end": 1800000000,
        "user_id": "user_123",
        "min_likes": 50,
        "min_comments": 10,
        "min_shares": 5,
        "min_collected": 20,
    })
    assert response.status_code == 200
    call_args = mock_query.call_args
    params = call_args[0][2]
    assert params.page == 2
    assert params.page_size == 10
    assert params.keyword == "python"
    assert params.min_likes == 50


def test_query_invalid_platform():
    response = client.get("/api/query/invalid_platform/content")
    assert response.status_code == 400
    assert "Invalid platform" in response.json()["detail"]


def test_query_invalid_data_type():
    response = client.get("/api/query/ks/creators")
    assert response.status_code == 400
    assert "not available" in response.json()["detail"]


def test_query_invalid_page():
    response = client.get("/api/query/xhs/content", params={"page": 0})
    assert response.status_code == 422


def test_query_page_size_too_large():
    response = client.get("/api/query/xhs/content", params={"page_size": 200})
    assert response.status_code == 422


def test_query_invalid_sort_order():
    response = client.get("/api/query/xhs/content", params={"sort_order": "random"})
    assert response.status_code == 422


def test_query_negative_min_likes():
    response = client.get("/api/query/xhs/content", params={"min_likes": -1})
    assert response.status_code == 422


@patch("api.routers.query.query_data", new_callable=AsyncMock)
def test_query_db_not_configured(mock_query):
    mock_query.side_effect = RuntimeError("No database engine configured")
    response = client.get("/api/query/xhs/content")
    assert response.status_code == 400
    assert "database" in response.json()["detail"].lower()


@pytest.mark.parametrize("platform,data_type", [
    ("xhs", "content"), ("xhs", "comments"), ("xhs", "creators"),
    ("dy", "content"), ("dy", "comments"), ("dy", "creators"),
    ("ks", "content"), ("ks", "comments"),
    ("bili", "content"), ("bili", "comments"), ("bili", "creators"),
    ("wb", "content"), ("wb", "comments"), ("wb", "creators"),
    ("tieba", "content"), ("tieba", "comments"), ("tieba", "creators"),
    ("zhihu", "content"), ("zhihu", "comments"), ("zhihu", "creators"),
])
@patch("api.routers.query.query_data", new_callable=AsyncMock)
def test_all_valid_routes(mock_query, platform, data_type):
    mock_query.return_value = MOCK_PAGINATED
    response = client.get(f"/api/query/{platform}/{data_type}")
    assert response.status_code == 200
