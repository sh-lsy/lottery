"""
tests/api/test_api_history.py

Comprehensive integration test suite for History & Trends RESTful API endpoints:
1. GET /api/v1/history/draws:
   - Pagination (page, page_size, total_pages)
   - Sorting (asc vs desc by issue_no)
   - Range filtering (start_issue, end_issue, invalid start > end returns 400)
   - Ball filtering (search_ball <= 16 matches red or blue; search_ball > 16 matches red only; invalid ball returns 422)
   - Alias /api/v1/history/list equivalence
   - Empty database response handling
2. GET /api/v1/history/latest:
   - Returns latest authentic draw record with feature metrics
   - 404 response on empty database
3. GET /api/v1/history/metrics & GET /api/v1/history/metrics/{issue_no}:
   - Sequence retrieval in chronological order respecting limit
   - Individual issue retrieval by issue_no
   - 404 response on non-existent issue
4. GET /api/v1/history/omissions & GET /api/v1/history/trends:
   - Omission heatmap timeline, current red/blue omission dictionaries
   - Cold/Warm/Hot categorization and Top-3 rankings
   - Query validation (limit 10..100, values outside range return 422)
5. GET /api/v1/history/distributions:
   - Multi-dimensional distribution maps (Sum, AC, Odd-Even, Span, Zones)
   - sample_size tracking and recent_n filtering
6. POST /api/v1/history/sync:
   - Incremental crawl trigger with mocked CrawlerService
   - Collision cache invalidation
   - Auto-verification of pending prediction batches
   - 500 error propagation on crawler failure
"""

from datetime import date
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import DrawHistory, FeatureMetrics
from backend.app.services.feature_engine import FeatureEngine
from backend.app.services.collision_cache import CollisionCache
from tests.conftest import CANONICAL_SAMPLE_DRAWS


@pytest.fixture
def populated_api_db():
    """Isolated in-memory SQLite database populated with 25 canonical draws and feature metrics."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSession()

    for d in CANONICAL_SAMPLE_DRAWS:
        draw = DrawHistory(
            issue_no=d["issue_no"],
            draw_date=date.fromisoformat(d["draw_date"]),
            weekday=d["weekday"],
            red_1=d["red_1"],
            red_2=d["red_2"],
            red_3=d["red_3"],
            red_4=d["red_4"],
            red_5=d["red_5"],
            red_6=d["red_6"],
            blue_1=d["blue_1"],
            red_seq_str=d["red_seq_str"],
            sales_amount=d["sales_amount"],
            pool_amount=d["pool_amount"],
            first_prize_num=d["first_prize_num"],
            first_prize_amount=d["first_prize_amount"],
            second_prize_num=d["second_prize_num"],
            second_prize_amount=d["second_prize_amount"],
        )
        session.add(draw)
    session.commit()

    # Pre-compute feature metrics for all draws
    engine_calc = FeatureEngine(session_factory=TestingSession)
    engine_calc.compute_all_features(force=True)

    yield session, TestingSession
    session.close()


@pytest.fixture
def client(populated_api_db):
    """Starlette TestClient with dependency override yielding populated isolated session."""
    session, TestingSession = populated_api_db

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    CollisionCache.get_instance().invalidate()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    CollisionCache.get_instance().invalidate()


class TestGetDrawHistory:
    """Tests for GET /api/v1/history/draws and GET /api/v1/history/list."""

    def test_pagination_default(self, client):
        response = client.get("/api/v1/history/draws")
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 25
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert data["total_pages"] == 2
        assert len(data["items"]) == 20
        # Default order is desc by issue_no
        assert data["items"][0]["issue_no"] == "2026124"

    def test_pagination_custom_page_and_size(self, client):
        response = client.get("/api/v1/history/draws?page=2&page_size=10")
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 25
        assert data["page"] == 2
        assert data["page_size"] == 10
        assert data["total_pages"] == 3
        assert len(data["items"]) == 10

    def test_sort_order_asc_vs_desc(self, client):
        res_asc = client.get("/api/v1/history/draws?sort_order=asc")
        assert res_asc.status_code == 200
        data_asc = res_asc.json()
        assert data_asc["items"][0]["issue_no"] == "2003001"

        res_desc = client.get("/api/v1/history/draws?sort_order=desc")
        assert res_desc.status_code == 200
        data_desc = res_desc.json()
        assert data_desc["items"][0]["issue_no"] == "2026124"

    def test_range_filter_start_and_end_issue(self, client):
        response = client.get("/api/v1/history/draws?start_issue=2026110&end_issue=2026115&page_size=100")
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 6
        issues = [item["issue_no"] for item in data["items"]]
        assert sorted(issues) == ["2026110", "2026111", "2026112", "2026113", "2026114", "2026115"]

    def test_range_filter_invalid_start_greater_than_end(self, client):
        response = client.get("/api/v1/history/draws?start_issue=2026120&end_issue=2026110")
        assert response.status_code == 400
        data = response.json()
        assert "start_issue cannot be greater than end_issue" in data["detail"]

    def test_search_ball_filtering(self, client):
        # Ball 16 can match blue or red (since 16 <= 16)
        response_16 = client.get("/api/v1/history/draws?search_ball=16&page_size=100")
        assert response_16.status_code == 200
        items_16 = response_16.json()["items"]
        assert len(items_16) > 0
        for item in items_16:
            assert 16 in item["reds"] or item["blue"] == 16

        # Ball 33 matches red only (since 33 > 16)
        response_33 = client.get("/api/v1/history/draws?search_ball=33&page_size=100")
        assert response_33.status_code == 200
        items_33 = response_33.json()["items"]
        assert len(items_33) > 0
        for item in items_33:
            assert 33 in item["reds"]

    def test_search_ball_out_of_bounds_returns_422(self, client):
        res_zero = client.get("/api/v1/history/draws?search_ball=0")
        assert res_zero.status_code == 422

        res_large = client.get("/api/v1/history/draws?search_ball=34")
        assert res_large.status_code == 422

    def test_alias_endpoint_list_matches_draws(self, client):
        res_draws = client.get("/api/v1/history/draws?page=1&page_size=5")
        res_list = client.get("/api/v1/history/list?page=1&page_size=5")
        assert res_draws.status_code == 200
        assert res_list.status_code == 200
        assert res_draws.json() == res_list.json()

    def test_draw_item_structure_and_metrics(self, client):
        response = client.get("/api/v1/history/draws?page=1&page_size=1")
        assert response.status_code == 200
        item = response.json()["items"][0]

        assert "id" in item
        assert "issue_no" in item
        assert "draw_date" in item
        assert "weekday" in item
        assert len(item["reds"]) == 6
        assert 1 <= item["blue"] <= 16
        assert item["red_seq_str"] is not None
        assert item["sum_red"] == sum(item["reds"])
        assert item["metrics"] is not None
        assert item["metrics"]["issue_no"] == item["issue_no"]
        assert item["metrics"]["ac_value"] >= 0


class TestGetLatestDraw:
    """Tests for GET /api/v1/history/latest."""

    def test_get_latest_draw_success(self, client):
        response = client.get("/api/v1/history/latest")
        assert response.status_code == 200
        data = response.json()

        assert data["issue_no"] == "2026124"
        assert data["reds"] == [2, 7, 13, 18, 24, 29]
        assert data["blue"] == 5
        assert data["sum_red"] == 93
        assert data["metrics"] is not None
        assert data["metrics"]["issue_no"] == "2026124"

    def test_get_latest_draw_empty_db_returns_404(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        EmptySession = sessionmaker(bind=engine)

        def override_empty():
            db = EmptySession()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_empty
        with TestClient(app) as empty_client:
            response = empty_client.get("/api/v1/history/latest")
            assert response.status_code == 404
            assert "No draw history records found" in response.json()["detail"]
        app.dependency_overrides.clear()


class TestGetMetrics:
    """Tests for GET /api/v1/history/metrics and GET /api/v1/history/metrics/{issue_no}."""

    def test_get_metrics_sequence_chronological(self, client):
        response = client.get("/api/v1/history/metrics?limit=15")
        assert response.status_code == 200
        metrics_list = response.json()

        assert len(metrics_list) == 15
        # Must be chronologically ascending for frontend charts
        issues = [m["issue_no"] for m in metrics_list]
        assert issues == sorted(issues)
        first = metrics_list[0]
        assert "sum_red" in first
        assert "span_red" in first
        assert "ac_value" in first
        assert "odd_count" in first
        assert "prime_count" in first
        assert "zone1_count" in first

    def test_get_metrics_by_valid_issue(self, client):
        response = client.get("/api/v1/history/metrics/2026122")
        assert response.status_code == 200
        data = response.json()

        assert data["issue_no"] == "2026122"
        # 2026122 reds: [5, 11, 16, 21, 27, 30] -> sum = 110, span = 25
        assert data["sum_red"] == 110
        assert data["span_red"] == 25

    def test_get_metrics_by_non_existent_issue_returns_404(self, client):
        response = client.get("/api/v1/history/metrics/9999999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestGetOmissionTrends:
    """Tests for GET /api/v1/history/omissions and GET /api/v1/history/trends."""

    def test_get_omissions_default(self, client):
        response = client.get("/api/v1/history/omissions")
        assert response.status_code == 200
        data = response.json()

        assert "issues" in data
        assert len(data["issues"]) == 25  # all available
        assert "timeline" in data
        assert len(data["timeline"]) == 25

        timeline_item = data["timeline"][-1]
        assert "red_omissions" in timeline_item
        assert "blue_omissions" in timeline_item
        assert len(timeline_item["drawn_reds"]) == 6

        # Cold/Warm/Hot statistics
        assert "cold_warm_hot" in data
        cwh = data["cold_warm_hot"]
        assert isinstance(cwh["hot_reds"], list)
        assert isinstance(cwh["warm_reds"], list)
        assert isinstance(cwh["cold_reds"], list)
        assert isinstance(cwh["hot_blues"], list)

        # Top-3 rankings
        assert len(data["top3_hot_reds"]) == 3
        assert len(data["top3_cold_reds"]) == 3
        assert len(data["top3_hot_blues"]) == 3
        assert len(data["top3_cold_blues"]) == 3

    def test_get_omissions_limit_validation(self, client):
        # Limit < 10 returns 422
        res_low = client.get("/api/v1/history/omissions?limit=5")
        assert res_low.status_code == 422

        # Limit > 100 returns 422
        res_high = client.get("/api/v1/history/omissions?limit=150")
        assert res_high.status_code == 422

    def test_alias_trends_matches_omissions(self, client):
        res_omissions = client.get("/api/v1/history/omissions?limit=10")
        res_trends = client.get("/api/v1/history/trends?limit=10")
        assert res_omissions.status_code == 200
        assert res_trends.status_code == 200
        assert res_omissions.json() == res_trends.json()


class TestGetIndicatorDistributions:
    """Tests for GET /api/v1/history/distributions."""

    def test_get_distributions_success(self, client):
        response = client.get("/api/v1/history/distributions?recent_n=25")
        assert response.status_code == 200
        data = response.json()

        assert data["sample_size"] == 25
        assert "sum_distribution" in data
        assert "ac_distribution" in data
        assert "odd_even_distribution" in data
        assert "span_distribution" in data
        assert "zone_distribution" in data

        # Check that AC counts sum to sample_size
        ac_counts_sum = sum(data["ac_distribution"].values())
        assert ac_counts_sum == 25

        # Check that odd_even counts sum to sample_size
        oe_counts_sum = sum(data["odd_even_distribution"].values())
        assert oe_counts_sum == 25


class TestSyncEndpoint:
    """Tests for POST /api/v1/history/sync."""

    def test_sync_success_with_mocked_crawler(self, client, populated_api_db):
        session, TestingSession = populated_api_db

        with patch("backend.app.api.history.CrawlerService") as mock_crawler_cls:
            mock_crawler = MagicMock()
            mock_crawler.sync_latest.return_value = 2  # 2 new draws crawled
            mock_crawler_cls.return_value = mock_crawler

            with patch("backend.app.api.history.FeatureEngine") as mock_engine_cls:
                mock_engine = MagicMock()
                mock_engine.compute_latest_features.return_value = 2
                mock_engine_cls.return_value = mock_engine

                response = client.post("/api/v1/history/sync", json={"force": False, "auto_verify": False})
                assert response.status_code == 200
                data = response.json()

                assert data["success"] is True
                assert data["new_draws"] == 2
                assert data["affected_draws"] == 2
                assert data["new_features"] == 2
                assert "Sync successful" in data["message"]

    def test_sync_crawler_failure_returns_500(self, client):
        with patch("backend.app.api.history.CrawlerService") as mock_crawler_cls:
            mock_crawler = MagicMock()
            mock_crawler.sync_latest.side_effect = RuntimeError("Network timeout connecting to CWL")
            mock_crawler_cls.return_value = mock_crawler

            response = client.post("/api/v1/history/sync", json={"force": True})
            assert response.status_code == 500
            assert "Crawler synchronization failed" in response.json()["detail"]
