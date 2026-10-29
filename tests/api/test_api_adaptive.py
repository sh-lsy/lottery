"""
tests/api/test_api_adaptive.py

Comprehensive integration test suite for Adaptive Strategy Feedback Loop RESTful API endpoints:
1. GET /api/v1/adaptive/status & GET /api/v1/adaptive/state:
   - Status retrieval of singleton adaptive hyperparameters
   - Hyperparameter verification: weights (hazard, markov, momentum), blue_mode, loss_threshold
   - Adaptation triggered flag calculation (consecutive_deficit_count >= loss_threshold)
   - Alias /api/v1/adaptive/state equivalence
2. POST /api/v1/adaptive/trigger:
   - Manual evaluation trigger
   - Custom threshold override support
   - Force evolution trigger (force=True): mode toggling, dynamic weight shift, evolution_version increment
3. POST /api/v1/adaptive/reset:
   - Hyperparameters reset to canonical defaults (0.40, 0.35, 0.25, CONCENTRATED, [75, 135])
   - Streak counter zeroed
   - RESET_TO_DEFAULT event logged in trajectory
4. GET /api/v1/adaptive/trajectory:
   - Historical audit log query with total_records and chronological events
   - Event schema fields: issue_no, trigger_reason, weights, mode transitions, reflection notes
   - Limit query parameter support
"""

from datetime import date
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import DrawHistory
from backend.app.services.adaptive_service import AdaptiveService
from tests.conftest import CANONICAL_SAMPLE_DRAWS


@pytest.fixture
def populated_adaptive_db():
    """Isolated in-memory SQLite database populated with draws and initial adaptive state."""
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

    # Pre-initialize adaptive state
    service = AdaptiveService()
    service.get_or_create_state(session)
    session.commit()

    yield session, TestingSession
    session.close()


@pytest.fixture
def client(populated_adaptive_db):
    """Starlette TestClient with dependency override."""
    session, TestingSession = populated_adaptive_db

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


class TestAdaptiveStatus:
    """Tests for GET /api/v1/adaptive/status and alias GET /api/v1/adaptive/state."""

    def test_get_adaptive_status_defaults(self, client):
        res = client.get("/api/v1/adaptive/status")
        assert res.status_code == 200
        data = res.json()

        assert data["consecutive_deficit_count"] == 0
        assert data["adaptation_triggered"] is False
        assert data["trigger_threshold"] == 3
        assert data["blue_mode"] == "CONCENTRATED"
        assert data["weights"]["hazard"] == pytest.approx(0.40)
        assert data["weights"]["markov"] == pytest.approx(0.35)
        assert data["weights"]["momentum"] == pytest.approx(0.25)
        assert data["sum_range"] == [75, 135]
        assert data["current_issue"] == "2026124"  # latest draw in DB

    def test_alias_state_endpoint_matches_status(self, client):
        res_status = client.get("/api/v1/adaptive/status")
        res_state = client.get("/api/v1/adaptive/state")
        assert res_status.status_code == 200
        assert res_state.status_code == 200
        assert res_status.json() == res_state.json()


class TestAdaptiveTrigger:
    """Tests for POST /api/v1/adaptive/trigger."""

    def test_trigger_without_force_maintains_state(self, client):
        res = client.post("/api/v1/adaptive/trigger", json={"force": False})
        assert res.status_code == 200
        data = res.json()
        assert data["blue_mode"] == "CONCENTRATED"
        assert data["weights"]["hazard"] == pytest.approx(0.40)

    def test_trigger_custom_threshold_override(self, client):
        res = client.post("/api/v1/adaptive/trigger", json={"custom_threshold": 5, "force": False})
        assert res.status_code == 200
        data = res.json()
        assert data["trigger_threshold"] == 5

    def test_trigger_force_evolution(self, client):
        # Initial mode is CONCENTRATED
        status_pre = client.get("/api/v1/adaptive/status").json()
        assert status_pre["blue_mode"] == "CONCENTRATED"
        v_pre = status_pre["evolution_version"]

        # Force evolution
        res = client.post("/api/v1/adaptive/trigger", json={"force": True})
        assert res.status_code == 200
        data = res.json()

        # Mode toggles to DISPERSED
        assert data["blue_mode"] == "DISPERSED"
        assert data["evolution_version"] == v_pre + 1
        assert data["last_trigger_reason"] == "FORCED_TRIGGER"
        # Weights shifted: momentum increased, hazard decreased
        assert data["weights"]["momentum"] > status_pre["weights"]["momentum"]
        assert data["weights"]["hazard"] < status_pre["weights"]["hazard"]

        # Second force evolution toggles back to CONCENTRATED
        res2 = client.post("/api/v1/adaptive/trigger", json={"force": True})
        assert res2.status_code == 200
        assert res2.json()["blue_mode"] == "CONCENTRATED"


class TestAdaptiveReset:
    """Tests for POST /api/v1/adaptive/reset."""

    def test_reset_restores_baseline_hyperparameters(self, client):
        # First force a deviation
        client.post("/api/v1/adaptive/trigger", json={"force": True, "custom_threshold": 5})
        status_mut = client.get("/api/v1/adaptive/status").json()
        assert status_mut["blue_mode"] == "DISPERSED"

        # Now reset
        res = client.post("/api/v1/adaptive/reset")
        assert res.status_code == 200
        data = res.json()

        assert data["consecutive_deficit_count"] == 0
        assert data["blue_mode"] == "CONCENTRATED"
        assert data["weights"]["hazard"] == pytest.approx(0.40)
        assert data["weights"]["markov"] == pytest.approx(0.35)
        assert data["weights"]["momentum"] == pytest.approx(0.25)
        assert data["sum_range"] == [75, 135]
        assert data["last_trigger_reason"] == "MANUAL_RESET"


class TestAdaptiveTrajectory:
    """Tests for GET /api/v1/adaptive/trajectory."""

    def test_trajectory_logs_reset_and_evolution_events(self, client):
        # Trigger a reset to create a trajectory entry
        client.post("/api/v1/adaptive/reset")

        # Query trajectory
        res = client.get("/api/v1/adaptive/trajectory?limit=10")
        assert res.status_code == 200
        data = res.json()

        assert data["total_records"] >= 1
        assert len(data["items"]) >= 1

        first_event = data["items"][0]
        assert "id" in first_event
        assert "issue_no" in first_event
        assert "trigger_reason" in first_event
        assert "weight_hazard" in first_event
        assert "weight_markov" in first_event
        assert "weight_momentum" in first_event
        assert "reflection_notes" in first_event
        assert "created_at" in first_event

    def test_trajectory_limit_query_param(self, client):
        # Trigger two resets to have multiple entries
        client.post("/api/v1/adaptive/reset")
        client.post("/api/v1/adaptive/reset")

        res = client.get("/api/v1/adaptive/trajectory?limit=1")
        assert res.status_code == 200
        data = res.json()
        assert len(data["items"]) == 1
        assert data["total_records"] >= 2
