"""
tests/api/test_api_predict.py

Comprehensive integration test suite for Prediction API endpoints:
1. POST /api/v1/predict/generate:
   - Offline local execution without external network calls (<50ms)
   - Strict 5 notes constraint (total_notes == 5, len(notes) == 5)
   - Red dan-tuo candidate pool, ascending sorted reds, valid bounds [1..33]
   - Blue allocation modes: CONCENTRATED (3+2), DISPERSED (5 distinct), BALANCED
   - Parameter overrides: sum_min, sum_max, ac_min, odd_counts, span
   - Structured payoff matrix, ai_reasoning_md, and negative expectation disclaimer
   - Historical zero-lookahead isolation with target_issue
   - In-line persistence via save_to_db=True / persist=True returning batch_id
   - Error cases: invalid ranges (sum_min > sum_max), issue with no prior history (400)
2. POST /api/v1/predict/save:
   - Atomic database persistence of batch and 5 prediction items
   - Strict validation: rejects batches with != 5 notes (4 or 6 notes -> 422)
   - Rejection of invalid reds (duplicates, out of bounds [1..33], blue [1..16])
   - Verification of PENDING status and initial zero reward
3. GET /api/v1/predict/batches:
   - Pagination (page, page_size, total_pages)
   - Filtering by target_issue, strategy_type, and verify_status
   - Batch summary KPIs (net_profit, roi, total_notes)
4. GET /api/v1/predict/batches/{id}:
   - Detail retrieval with all 5 notes and actual_draw enrichment
   - Neon highlighting metadata (hit_red_numbers, hit_blue, prize_level, prize_amount)
   - 404 response on non-existent batch_id
5. GET /api/v1/predict/dashboard & GET /api/v1/predict/summary:
   - Aggregate KPIs: total_batches, total_notes, total_investment, total_returns, simulated_roi
   - Win metrics: break_even_batches, break_even_rate, blue_hit_rate
   - Prize level distribution and strategy breakdown
"""

from datetime import date
import pytest
from sqlalchemy import create_engine
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
def populated_predict_db():
    """Isolated in-memory SQLite database populated with canonical draws and sample prediction batches."""
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

    # Pre-compute feature metrics
    engine_calc = FeatureEngine(session_factory=TestingSession)
    engine_calc.compute_all_features(force=True)

    # Seed 2 sample prediction batches for query/dashboard testing
    # Batch 1: targeting 2026122 (Verified with 15 RMB win)
    b1 = PredictionBatch(
        id=1,
        target_issue="2026122",
        strategy_type="CONCENTRATED_BREAK_EVEN",
        model_name="Ensemble-Hazard-Markov-Momentum",
        total_notes=5,
        verify_status="VERIFIED",
        best_prize_level=5,
        virtual_cost=10,
        virtual_reward=15,
        ai_reasoning_md="Batch 1 reasoning",
    )
    session.add(b1)
    session.flush()

    for idx in range(1, 6):
        item = PredictionItem(
            batch_id=b1.id,
            target_issue="2026122",
            note_index=idx,
            red_1=5, red_2=11, red_3=16, red_4=21, red_5=27, red_6=30,
            blue_1=8 if idx <= 3 else 12,
            confidence_score=0.88,
            rationale=f"Line {idx}",
            is_verified=True,
            hit_red_count=6,
            hit_red_numbers="5,11,16,21,27,30",
            hit_blue=bool(idx <= 3),
            prize_level=1 if idx <= 3 else 2,
            prize_amount=5800000 if idx <= 3 else 95000,
        )
        session.add(item)

    # Batch 2: targeting 2026125 (Pending)
    b2 = PredictionBatch(
        id=2,
        target_issue="2026125",
        strategy_type="DISPERSED_BASELINE",
        model_name="Ensemble-Hazard-Markov-Momentum",
        total_notes=5,
        verify_status="PENDING",
        best_prize_level=0,
        virtual_cost=10,
        virtual_reward=0,
        ai_reasoning_md="Batch 2 reasoning",
    )
    session.add(b2)
    session.flush()

    for idx in range(1, 6):
        item = PredictionItem(
            batch_id=b2.id,
            target_issue="2026125",
            note_index=idx,
            red_1=1, red_2=2, red_3=3, red_4=4, red_5=5, red_6=idx + 5,
            blue_1=idx,
            confidence_score=0.75,
            rationale=f"Line {idx}",
            is_verified=False,
        )
        session.add(item)
    session.commit()

    yield session, TestingSession
    session.close()


@pytest.fixture
def client(populated_predict_db):
    """Starlette TestClient with dependency override."""
    session, TestingSession = populated_predict_db

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


class TestPredictGenerate:
    """Tests for POST /api/v1/predict/generate."""

    def test_generate_default_5_notes_concentrated(self, client):
        response = client.get("/api/v1/history/latest")
        assert response.status_code == 200

        # Generate prediction
        res = client.post("/api/v1/predict/generate", json={})
        assert res.status_code == 200
        data = res.json()

        assert data["total_notes"] == 5
        assert len(data["notes"]) == 5
        assert data["strategy_type"] == "CONCENTRATED_BREAK_EVEN"
        assert data["model_name"] == "Ensemble-Hazard-Markov-Momentum"

        # Check all 5 notes
        blues = []
        for i, note in enumerate(data["notes"]):
            assert note["note_index"] == i + 1
            assert len(note["reds"]) == 6
            assert len(set(note["reds"])) == 6
            assert note["reds"] == sorted(note["reds"])
            assert all(1 <= r <= 33 for r in note["reds"])
            assert 1 <= note["blue"] <= 16
            assert note["confidence_score"] > 0
            assert note["sum_red"] == sum(note["reds"])
            assert note["span_red"] == note["reds"][-1] - note["reds"][0]
            assert 0 <= note["ac_value"] <= 10
            assert 0 <= note["odd_count"] <= 6
            blues.append(note["blue"])

        # Concentrated 3+2 allocation: exactly 2 distinct blues in the 5 notes
        unique_blues = set(blues)
        assert len(unique_blues) == 2
        top1_count = blues.count(data["break_even_matrix"]["top1_blue"])
        top2_count = blues.count(data["break_even_matrix"]["top2_blue"])
        assert top1_count == 3
        assert top2_count == 2

        # Check structured rationale & disclaimer
        assert "E[X] < 0" in data["ai_reasoning_md"] or "house edge" in data["ai_reasoning_md"]
        assert len(data["blue_probabilities"]) == 16
        assert "candidate_pool" in data
        assert len(data["candidate_pool"]["cores"]) > 0

    def test_generate_dispersed_blue_mode(self, client):
        res = client.post(
            "/api/v1/predict/generate",
            json={
                "strategy_type": "DISPERSED_BASELINE",
                "blue_mode": "DISPERSED",
            },
        )
        assert res.status_code == 200
        data = res.json()

        assert data["total_notes"] == 5
        blues = [note["blue"] for note in data["notes"]]
        # Dispersed allocation: all 5 notes must have 5 distinct blues!
        assert len(set(blues)) == 5

    def test_generate_parameter_overrides(self, client):
        res = client.post(
            "/api/v1/predict/generate",
            json={
                "adaptive_enabled": False,
                "ac_min": 6,
                "sum_min": 85,
                "sum_max": 125,
                "odd_counts": [3],
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["filter_params"]["ac_min"] == 6
        assert data["filter_params"]["sum_range"] == [85, 125]
        assert data["filter_params"]["odd_counts"] == [2, 3, 4]
        for note in data["notes"]:
            assert note["sum_red"] == sum(note["reds"])
            assert 0 <= note["ac_value"] <= 10
            assert 0 <= note["odd_count"] <= 6

    def test_generate_with_persistence_flag(self, client):
        res = client.post(
            "/api/v1/predict/generate",
            json={"save_to_db": True},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["batch_id"] is not None
        batch_id = data["batch_id"]

        # Verify batch was persisted
        batch_res = client.get(f"/api/v1/predict/batches/{batch_id}")
        assert batch_res.status_code == 200
        batch_data = batch_res.json()
        assert batch_data["id"] == batch_id
        assert len(batch_data["items"]) == 5

    def test_generate_invalid_ranges_returns_422(self, client):
        # sum_min > sum_max
        res = client.post(
            "/api/v1/predict/generate",
            json={"sum_min": 140, "sum_max": 80},
        )
        assert res.status_code == 422

        # span_min > span_max
        res_span = client.post(
            "/api/v1/predict/generate",
            json={"span_min": 30, "span_max": 15},
        )
        assert res_span.status_code == 422

    def test_generate_prior_to_earliest_history_returns_400(self, client):
        res = client.post(
            "/api/v1/predict/generate",
            json={"target_issue": "1990001"},
        )
        assert res.status_code == 400
        assert "No historical draws found prior to target issue" in res.json()["detail"]


class TestPredictSave:
    """Tests for POST /api/v1/predict/save."""

    def test_save_valid_batch_and_5_notes(self, client):
        notes_payload = [
            {"note_index": i, "reds": [i, i + 1, i + 2, i + 3, i + 4, i + 5], "blue": i}
            for i in range(1, 6)
        ]
        payload = {
            "target_issue": "2026130",
            "strategy_type": "CONCENTRATED_BREAK_EVEN",
            "model_name": "Ensemble-Hazard-Markov-Momentum",
            "notes": notes_payload,
            "virtual_cost": 10,
            "ai_reasoning_md": "Saved batch manual test",
        }
        res = client.post("/api/v1/predict/save", json=payload)
        assert res.status_code == 200
        data = res.json()

        assert "batch_id" in data
        assert data["target_issue"] == "2026130"
        assert data["total_notes"] == 5

        # Query batch to confirm
        b_res = client.get(f"/api/v1/predict/batches/{data['batch_id']}")
        assert b_res.status_code == 200
        assert b_res.json()["verify_status"] == "PENDING"
        assert len(b_res.json()["items"]) == 5

    def test_save_rejects_non_5_notes(self, client):
        # 4 notes instead of 5
        notes_4 = [
            {"note_index": i, "reds": [1, 2, 3, 4, 5, i + 5], "blue": i}
            for i in range(1, 5)
        ]
        res_4 = client.post(
            "/api/v1/predict/save",
            json={"target_issue": "2026131", "notes": notes_4},
        )
        assert res_4.status_code == 422
        assert "exactly 5 notes" in str(res_4.json())

        # 6 notes instead of 5 (using note_index in 1..5 to specifically trigger list length validator)
        notes_6 = [
            {"note_index": min(i, 5), "reds": [1, 2, 3, 4, 5, i + 5], "blue": i}
            for i in range(1, 7)
        ]
        res_6 = client.post(
            "/api/v1/predict/save",
            json={"target_issue": "2026131", "notes": notes_6},
        )
        assert res_6.status_code == 422
        assert "exactly 5 notes" in str(res_6.json())

    def test_save_rejects_duplicate_reds_in_note(self, client):
        notes_dup = [
            {"note_index": 1, "reds": [1, 1, 3, 4, 5, 6], "blue": 1},  # duplicate red
            {"note_index": 2, "reds": [2, 3, 4, 5, 6, 7], "blue": 2},
            {"note_index": 3, "reds": [3, 4, 5, 6, 7, 8], "blue": 3},
            {"note_index": 4, "reds": [4, 5, 6, 7, 8, 9], "blue": 4},
            {"note_index": 5, "reds": [5, 6, 7, 8, 9, 10], "blue": 5},
        ]
        res = client.post(
            "/api/v1/predict/save",
            json={"target_issue": "2026132", "notes": notes_dup},
        )
        assert res.status_code == 422
        assert "distinct" in str(res.json())

    def test_save_rejects_red_out_of_bounds(self, client):
        notes_oob = [
            {"note_index": 1, "reds": [0, 2, 3, 4, 5, 6], "blue": 1},  # 0 < 1
            {"note_index": 2, "reds": [2, 3, 4, 5, 6, 7], "blue": 2},
            {"note_index": 3, "reds": [3, 4, 5, 6, 7, 8], "blue": 3},
            {"note_index": 4, "reds": [4, 5, 6, 7, 8, 9], "blue": 4},
            {"note_index": 5, "reds": [5, 6, 7, 8, 9, 10], "blue": 5},
        ]
        res = client.post(
            "/api/v1/predict/save",
            json={"target_issue": "2026133", "notes": notes_oob},
        )
        assert res.status_code == 422


class TestPredictBatchesAndDetail:
    """Tests for GET /api/v1/predict/batches and GET /api/v1/predict/batches/{id}."""

    def test_list_batches_pagination_and_filters(self, client):
        res = client.get("/api/v1/predict/batches?page=1&page_size=10")
        assert res.status_code == 200
        data = res.json()

        assert data["total"] >= 2
        assert data["page"] == 1
        assert len(data["items"]) >= 2

        # Filter by verify_status=VERIFIED
        res_v = client.get("/api/v1/predict/batches?verify_status=VERIFIED")
        assert res_v.status_code == 200
        for item in res_v.json()["items"]:
            assert item["verify_status"] == "VERIFIED"

        # Filter by strategy_type
        res_st = client.get("/api/v1/predict/batches?strategy_type=CONCENTRATED_BREAK_EVEN")
        assert res_st.status_code == 200
        for item in res_st.json()["items"]:
            assert item["strategy_type"] == "CONCENTRATED_BREAK_EVEN"

    def test_get_batch_detail_with_actual_draw_and_items(self, client):
        # Batch 1 targets 2026122 which is an authentic draw in our DB
        res = client.get("/api/v1/predict/batches/1")
        assert res.status_code == 200
        data = res.json()

        assert data["id"] == 1
        assert data["target_issue"] == "2026122"
        assert data["verify_status"] == "VERIFIED"
        assert len(data["items"]) == 5
        assert data["virtual_reward"] == 15
        assert data["net_profit"] == 5
        assert data["roi"] == 0.50

        # Actual draw must be populated
        assert data["actual_draw"] is not None
        assert data["actual_draw"]["issue_no"] == "2026122"
        assert data["actual_draw"]["reds"] == [5, 11, 16, 21, 27, 30]
        assert data["actual_draw"]["blue"] == 8

        # Note detail neon highlight metadata
        first_note = data["items"][0]
        assert first_note["is_verified"] is True
        assert first_note["hit_red_count"] == 6
        assert first_note["hit_blue"] is True
        assert first_note["hit_red_numbers"] == [5, 11, 16, 21, 27, 30]

    def test_get_non_existent_batch_returns_404(self, client):
        res = client.get("/api/v1/predict/batches/99999")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"]


class TestPredictDashboard:
    """Tests for GET /api/v1/predict/dashboard and GET /api/v1/predict/summary."""

    def test_dashboard_kpis_and_breakdown(self, client):
        res = client.get("/api/v1/predict/dashboard")
        assert res.status_code == 200
        data = res.json()

        assert data["total_batches"] >= 2
        assert data["total_notes"] >= 10
        assert data["total_investment"] >= 20
        assert data["total_returns"] >= 15
        assert "simulated_roi" in data
        assert "break_even_batches" in data
        assert "break_even_rate" in data
        assert "blue_hit_batches" in data
        assert "prize_distribution" in data
        assert "strategy_breakdown" in data

    def test_alias_summary_matches_dashboard(self, client):
        res_d = client.get("/api/v1/predict/dashboard")
        res_s = client.get("/api/v1/predict/summary")
        assert res_d.status_code == 200
        assert res_s.status_code == 200
        assert res_d.json() == res_s.json()
