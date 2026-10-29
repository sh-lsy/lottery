"""
tests/api/test_api_backtest_sandbox.py

Comprehensive integration test suite for Backtest & Historical Collision Sandbox API endpoints:
1. POST /api/v1/backtest/sandbox/collision & POST /api/v1/backtest/sandbox:
   - Collision against authentic historical draws (including draw 2026122 jackpot)
   - First prize jackpot detection (6+1: reds [5, 11, 16, 21, 27, 30], blue 8 -> Level 1, payout >= 5,800,000)
   - Non-winning ticket collision and payout accounting
   - Multi-dimensional quantile metrics (Sum, AC, Span, Odd count with historical min/max/mean/percentile)
   - Sub-50ms execution performance benchmark
   - Input validation: duplicate reds, out-of-bounds red/blue, length != 6 (422 response)
   - Empty database handling
2. POST /api/v1/backtest/verify/{issue_no}:
   - Audit prediction batches against authentic draw result
   - Verification status transition from PENDING to VERIFIED
   - Hit count and prize payout calculation
   - 404 response on non-existent draw issue
3. POST /api/v1/backtest/run:
   - Walk-forward historical backtest execution
   - Backtest metrics: ROI, break-even rate, blue hit rate, max drawdown, prize distribution
4. POST /api/v1/backtest/compare:
   - Comparative backtest simulation (Concentrated 3+2 vs Dispersed 5-distinct)
   - Structured comparison report with summary narrative
"""

from datetime import date
import time
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import DrawHistory, PredictionBatch, PredictionItem
from backend.app.services.feature_engine import FeatureEngine
from backend.app.services.collision_cache import CollisionCache
from tests.conftest import CANONICAL_SAMPLE_DRAWS


@pytest.fixture
def populated_sandbox_db():
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

    # Pre-compute feature metrics so CollisionCache loads quantile statistics
    engine_calc = FeatureEngine(session_factory=TestingSession)
    engine_calc.compute_all_features(force=True)

    # Invalidate cache so it refreshes from the test session
    CollisionCache.get_instance().invalidate()

    yield session, TestingSession
    session.close()


@pytest.fixture
def client(populated_sandbox_db):
    """Starlette TestClient with dependency override."""
    session, TestingSession = populated_sandbox_db

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        # Re-initialize CollisionCache with test database after lifespan completes
        cache = CollisionCache.get_instance()
        cache.invalidate()
        cache.ensure_loaded(session)
        yield test_client

    app.dependency_overrides.clear()
    CollisionCache.get_instance().invalidate()


class TestSandboxCollision:
    """Tests for POST /api/v1/backtest/sandbox/collision and alias POST /api/v1/backtest/sandbox."""

    def test_jackpot_collision_against_known_draw_2026122(self, client):
        # Draw 2026122 has reds [5, 11, 16, 21, 27, 30] and blue 8 (first_prize_amount = 5800000)
        payload = {
            "reds": [5, 11, 16, 21, 27, 30],
            "blue": 8,
        }
        res = client.post("/api/v1/backtest/sandbox/collision", json=payload)
        assert res.status_code == 200
        data = res.json()

        assert data["total_draws_analyzed"] == 25
        assert data["highest_prize_level"] == 1
        assert "一等奖" in data["highest_prize_name"] or "First Prize" in data["highest_prize_name"]
        assert data["best_prize_issue"] == "2026122"
        assert data["total_historical_payout"] >= 5800000
        assert data["prize_counts"]["level_1"] >= 1
        assert data["hypothetical_cost"] == 50
        assert data["net_profit"] > 0
        assert data["simulated_roi"] > 1000.0

        # Top matches must include issue 2026122 as the #1 match
        assert len(data["top_matches"]) > 0
        top_match = data["top_matches"][0]
        assert top_match["issue_no"] == "2026122"
        assert top_match["hit_red_count"] == 6
        assert top_match["hit_blue"] is True
        assert top_match["prize_level"] == 1
        assert top_match["prize_amount"] == 5800000

    def test_non_winning_ticket_collision(self, client):
        # Unlikely combination with high balls and uncommon blue
        payload = {
            "reds": [1, 2, 3, 4, 5, 6],
            "blue": 13,
        }
        res = client.post("/api/v1/backtest/sandbox/collision", json=payload)
        assert res.status_code == 200
        data = res.json()

        assert data["total_draws_analyzed"] >= 25
        assert data["hypothetical_cost"] == data["total_draws_analyzed"] * 2
        assert "prize_counts" in data
        assert "features" in data
        assert data["features"]["sum"] == sum(payload["reds"])

    def test_quantile_metrics_presence_and_bounds(self, client):
        payload = {
            "reds": [2, 7, 14, 19, 24, 31],
            "blue": 8,
        }
        res = client.post("/api/v1/backtest/sandbox/collision", json=payload)
        assert res.status_code == 200
        data = res.json()

        assert "quantile_metrics" in data
        qms = data["quantile_metrics"]
        assert len(qms) == 4

        metric_names = [q["metric_name"] for q in qms]
        assert any("Sum" in m for m in metric_names)
        assert any("AC" in m for m in metric_names)
        assert any("Span" in m for m in metric_names)
        assert any("Odd" in m for m in metric_names)

        for q in qms:
            assert 0.0 <= q["percentile"] <= 100.0
            assert q["historical_min"] <= q["historical_max"]
            assert q["evaluation"] in ["NORMAL", "HIGH_PERCENTILE", "LOW_PERCENTILE"]

    def test_speed_benchmark_sub_50ms(self, client):
        payload = {
            "reds": [5, 11, 16, 21, 27, 30],
            "blue": 8,
        }
        # Pre-warm cache call
        client.post("/api/v1/backtest/sandbox/collision", json=payload)

        # Benchmark 10 consecutive requests
        latencies = []
        for _ in range(10):
            t0 = time.perf_counter()
            res = client.post("/api/v1/backtest/sandbox/collision", json=payload)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            assert res.status_code == 200
            latencies.append(elapsed_ms)

        mean_latency = sum(latencies) / len(latencies)
        # Verify sub-50ms constraint
        assert mean_latency < 50.0, f"Expected <50ms, got {mean_latency:.2f}ms"

    def test_alias_endpoint_sandbox(self, client):
        payload = {"reds": [2, 7, 14, 19, 24, 31], "blue": 8}
        res_col = client.post("/api/v1/backtest/sandbox/collision", json=payload)
        res_alias = client.post("/api/v1/backtest/sandbox", json=payload)
        assert res_col.status_code == 200
        assert res_alias.status_code == 200
        assert res_col.json() == res_alias.json()

    def test_input_validation_errors(self, client):
        # Duplicate reds
        res_dup = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [1, 1, 3, 4, 5, 6], "blue": 8})
        assert res_dup.status_code == 422

        # Red out of bounds (> 33)
        res_oob_red = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [1, 2, 3, 4, 5, 34], "blue": 8})
        assert res_oob_red.status_code == 422

        # Blue out of bounds (> 16)
        res_oob_blue = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [1, 2, 3, 4, 5, 6], "blue": 17})
        assert res_oob_blue.status_code == 422

        # Only 5 reds
        res_short = client.post("/api/v1/backtest/sandbox/collision", json={"reds": [1, 2, 3, 4, 5], "blue": 8})
        assert res_short.status_code == 422

    def test_empty_database_sandbox_response(self):
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

        # Mock cache as empty initialized state
        cache = CollisionCache.get_instance()
        cache.draw_records = []
        cache.is_initialized = True

        with TestClient(app) as empty_client:
            res = empty_client.post(
                "/api/v1/backtest/sandbox/collision",
                json={"reds": [1, 2, 3, 4, 5, 6], "blue": 8},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["total_draws_analyzed"] == 0
            assert data["highest_prize_level"] == 0
            assert "No Prize" in data["highest_prize_name"]

        app.dependency_overrides.clear()
        CollisionCache.get_instance().invalidate()


class TestVerifyEndpoint:
    """Tests for POST /api/v1/backtest/verify/{issue_no}."""

    def test_verify_issue_with_pending_batch(self, client, populated_sandbox_db):
        session, TestingSession = populated_sandbox_db

        # Seed a pending prediction batch targeting draw 2026122
        batch = PredictionBatch(
            target_issue="2026122",
            strategy_type="CONCENTRATED_BREAK_EVEN",
            model_name="Ensemble-Hazard-Markov-Momentum",
            total_notes=5,
            verify_status="PENDING",
            virtual_cost=10,
            virtual_reward=0,
        )
        session.add(batch)
        session.flush()

        # Add 5 notes where Note 1 matches 6+1 (First Prize)
        # Draw 2026122 reds: [5, 11, 16, 21, 27, 30], blue: 8
        item1 = PredictionItem(
            batch_id=batch.id,
            target_issue="2026122",
            note_index=1,
            red_1=5, red_2=11, red_3=16, red_4=21, red_5=27, red_6=30,
            blue_1=8,
            confidence_score=0.9,
            is_verified=False,
        )
        session.add(item1)

        for idx in range(2, 6):
            item = PredictionItem(
                batch_id=batch.id,
                target_issue="2026122",
                note_index=idx,
                red_1=1, red_2=2, red_3=3, red_4=4, red_5=5, red_6=idx + 5,
                blue_1=idx,
                confidence_score=0.7,
                is_verified=False,
            )
            session.add(item)
        session.commit()

        # Run verification via API
        res = client.post("/api/v1/backtest/verify/2026122", json={"force": True})
        assert res.status_code == 200
        data = res.json()

        assert data["issue_no"] == "2026122"
        assert data["verified_batches_count"] >= 1
        assert data["best_prize_level"] == 1
        assert data["total_virtual_reward"] >= 5800000

        # Verify DB batch status updated
        b = session.scalar(select(PredictionBatch).filter(PredictionBatch.id == batch.id))
        assert b.verify_status == "VERIFIED"
        assert b.best_prize_level == 1
        assert b.virtual_reward >= 5800000

    def test_verify_non_existent_issue_returns_404(self, client):
        res = client.post("/api/v1/backtest/verify/9999999")
        assert res.status_code == 404
        assert "not found in database" in res.json()["detail"]


class TestBacktestRunAndCompare:
    """Tests for POST /api/v1/backtest/run and POST /api/v1/backtest/compare."""

    def test_run_backtest_simulation(self, client):
        payload = {
            "n_issues": 10,
            "strategy": "CONCENTRATED_BREAK_EVEN",
        }
        res = client.post("/api/v1/backtest/run", json=payload)
        assert res.status_code == 200
        data = res.json()

        assert data["total_issues"] == 10
        assert data["strategy"] == "CONCENTRATED_BREAK_EVEN"
        assert data["total_investment"] == 10 * 10  # 10 issues * 10 RMB
        assert "total_return" in data
        assert "net_profit" in data
        assert "roi" in data
        assert "break_even_rate" in data
        assert "blue_hit_rate" in data
        assert "max_drawdown" in data
        assert "prize_distribution" in data

    def test_compare_strategies_simulation(self, client):
        payload = {
            "n_issues": 10,
        }
        res = client.post("/api/v1/backtest/compare", json=payload)
        assert res.status_code == 200
        data = res.json()

        assert data["n_issues"] == 10
        assert "concentrated_result" in data
        assert "dispersed_result" in data
        assert "comparison_summary" in data

        conc = data["concentrated_result"]
        disp = data["dispersed_result"]
        assert conc["strategy_name"] == "CONCENTRATED_BREAK_EVEN"
        assert disp["strategy_name"] == "DISPERSED_BASELINE"
        assert "roi" in conc or "simulated_roi" in conc
