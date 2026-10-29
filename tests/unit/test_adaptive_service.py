"""
tests/unit/test_adaptive_service.py

Comprehensive unit test suite for AdaptiveService and self-evolution feedback loop.
Validates:
1. Singleton state initialization & get_or_create_state behavior.
2. Streak counting (K_t = 0 -> 1 -> 2 -> 3) and trigger thresholding.
3. Blue allocation mode switching: CONCENTRATED (3+2) <-> DISPERSED (5-distinct).
4. Dynamic weight shifting (eta = 0.05) across Hot, Cold, and Neutral omission regimes.
5. Invariant normalization: cold_reversion_weight + markov_weight + hot_momentum_weight == 1.0.
6. Guardrail feedback adjustments and symmetric saturation clamps on sum_bias ([-30.0, +30.0]).
7. Bounds clamping on sum_range_min ([65, 80]) and sum_range_max ([115, 145]) ensuring min <= max.
8. Break-even recovery reset: streak reset to 0, mode restored to CONCENTRATED, bias cleared.
9. Immutable audit trail logging into ssq_adaptive_history with valid JSON metadata and reflection notes.
10. Manual reset_state restoring canonical defaults.
"""

from datetime import date
import json
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models import (
    DrawHistory,
    PredictionBatch,
    PredictionItem,
    AdaptiveState,
    AdaptiveHistory,
)
from backend.app.services.adaptive_service import AdaptiveService


@pytest.fixture
def memory_db():
    """Isolated in-memory SQLite database session with full schema."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _create_sample_draw(session, issue_no: str, reds: list[int], blue: int) -> DrawHistory:
    draw = DrawHistory(
        issue_no=issue_no,
        draw_date=date(2026, 9, 20),
        weekday=7,
        red_1=reds[0],
        red_2=reds[1],
        red_3=reds[2],
        red_4=reds[3],
        red_5=reds[4],
        red_6=reds[5],
        blue_1=blue,
        red_seq_str=",".join(f"{r:02d}" for r in reds),
        sales_amount=390000000,
        pool_amount=2500000000,
        first_prize_num=5,
        first_prize_amount=7000000,
        second_prize_num=100,
        second_prize_amount=150000,
    )
    session.add(draw)
    session.flush()
    return draw


def _create_prediction_batch(
    session,
    target_issue: str,
    virtual_cost: int = 10,
    virtual_reward: int = 0,
    pred_reds: list[list[int]] = None,
    pred_blues: list[int] = None,
) -> PredictionBatch:
    if pred_reds is None:
        pred_reds = [
            [1, 2, 3, 4, 5, 6],
            [1, 2, 3, 4, 5, 7],
            [1, 2, 3, 4, 5, 8],
            [1, 2, 3, 4, 5, 9],
            [1, 2, 3, 4, 5, 10],
        ]
    if pred_blues is None:
        pred_blues = [1, 1, 1, 2, 2]

    batch = PredictionBatch(
        target_issue=target_issue,
        strategy_type="CONCENTRATED_BREAK_EVEN",
        model_name="Ensemble-Hazard-Markov-Momentum",
        total_notes=5,
        verify_status="PENDING",
        virtual_cost=virtual_cost,
        virtual_reward=virtual_reward,
    )
    session.add(batch)
    session.flush()

    for idx in range(1, 6):
        item = PredictionItem(
            batch_id=batch.id,
            target_issue=target_issue,
            note_index=idx,
            red_1=pred_reds[idx - 1][0],
            red_2=pred_reds[idx - 1][1],
            red_3=pred_reds[idx - 1][2],
            red_4=pred_reds[idx - 1][3],
            red_5=pred_reds[idx - 1][4],
            red_6=pred_reds[idx - 1][5],
            blue_1=pred_blues[idx - 1],
            confidence_score=0.85,
        )
        session.add(item)
    session.flush()
    return batch


class TestAdaptiveStateLifecycle:
    """Tests state initialization, persistence, and reset."""

    def test_get_or_create_state_initializes_singleton_defaults(self, memory_db):
        service = AdaptiveService()
        state = service.get_or_create_state(memory_db)

        assert state.id == 1
        assert state.consecutive_deficit_count == 0
        assert state.current_blue_mode == "CONCENTRATED"
        assert state.current_strategy_mode == "CONCENTRATED_BREAK_EVEN"
        assert state.loss_threshold == 3
        assert state.cold_reversion_weight == pytest.approx(0.40)
        assert state.markov_weight == pytest.approx(0.35)
        assert state.hot_momentum_weight == pytest.approx(0.25)
        assert state.temperature_tau == pytest.approx(0.85)
        assert state.sum_bias == pytest.approx(0.0)
        assert state.odd_bias == pytest.approx(0.0)
        assert state.ac_min_override == 6
        assert state.sum_range_min == 75
        assert state.sum_range_max == 135
        assert state.evolution_version == 1

        # Second call returns the exact same record without creating duplicates
        state2 = service.get_or_create_state(memory_db)
        assert state2.id == state.id
        total_states = memory_db.scalar(select(func.count(AdaptiveState.id)))
        assert total_states == 1

    def test_reset_state_restores_canonical_defaults_and_logs_history(self, memory_db):
        service = AdaptiveService()
        state = service.get_or_create_state(memory_db)

        # Mutate state to non-default values
        state.consecutive_deficit_count = 5
        state.current_blue_mode = "DISPERSED"
        state.cold_reversion_weight = 0.20
        state.hot_momentum_weight = 0.50
        state.sum_bias = 25.0
        state.sum_range_min = 65
        state.sum_range_max = 145
        memory_db.commit()

        # Execute reset
        reset_state = service.reset_state(memory_db)
        assert reset_state.consecutive_deficit_count == 0
        assert reset_state.current_blue_mode == "CONCENTRATED"
        assert reset_state.cold_reversion_weight == pytest.approx(0.40)
        assert reset_state.markov_weight == pytest.approx(0.35)
        assert reset_state.hot_momentum_weight == pytest.approx(0.25)
        assert reset_state.sum_bias == pytest.approx(0.0)
        assert reset_state.sum_range_min == 75
        assert reset_state.sum_range_max == 135
        assert reset_state.evolution_version == 2

        # Verify AdaptiveHistory audit entry created
        history = memory_db.scalars(select(AdaptiveHistory)).all()
        assert len(history) == 1
        entry = history[0]
        assert entry.trigger_reason == "RESET_TO_DEFAULT"
        assert entry.streak_length == 0
        assert "canonical defaults" in entry.reflection_notes


class TestStreakCountingAndModeSwitching:
    """Tests underperformance tracking, streak counting, and mode switching."""

    def test_streak_progression_and_threshold_trigger(self, memory_db):
        service = AdaptiveService()

        # Set up 3 consecutive underperformance draws and batches
        for i in range(1, 4):
            issue_no = f"202610{i}"
            draw = _create_sample_draw(memory_db, issue_no, [2, 8, 14, 20, 26, 32], 16)
            batch = _create_prediction_batch(memory_db, issue_no, virtual_cost=10, virtual_reward=0)

            result = service.process_batch_verification(batch, draw, memory_db)

            if i < 3:
                assert result["streak"] == i
                assert result["is_triggered"] is False
                assert result["current_mode"] == "CONCENTRATED"
                assert "UNDERPERFORMANCE_STREAK" in result["trigger_reason"]
            else:
                # Milestone reached: K_t = 3 >= 3 threshold
                assert result["streak"] == 3
                assert result["is_triggered"] is True
                assert result["current_mode"] == "DISPERSED"
                assert result["trigger_reason"] == "CONSECUTIVE_DEFICIT_TRIGGER_STREAK_3"

        # Check DB state
        state = service.get_or_create_state(memory_db)
        assert state.consecutive_deficit_count == 3
        assert state.current_blue_mode == "DISPERSED"
        assert state.current_strategy_mode == "DISPERSED_BASELINE"

        # Verify history log was created for the trigger event
        history_records = memory_db.scalars(
            select(AdaptiveHistory).order_by(AdaptiveHistory.id.asc())
        ).all()
        assert len(history_records) == 1
        trigger_log = history_records[0]
        assert trigger_log.trigger_issue == "2026103"
        assert trigger_log.streak_length == 3
        assert "Switched blue mode to DISPERSED" in trigger_log.reflection_notes


class TestDynamicWeightShifting:
    """Tests dynamic weight shift based on recent blue omission regimes."""

    def test_hot_momentum_regime_shifts_weight_to_momentum(self, memory_db):
        service = AdaptiveService()

        # Seed 10 draws where blue ball has very low omission (Hot Regime: m_bar <= 4)
        for i in range(1, 11):
            _create_sample_draw(memory_db, f"20260{i:02d}", [1, 2, 3, 4, 5, 6], 8)

        # Trigger adaptation with streak = 3
        state = service.get_or_create_state(memory_db)
        state.consecutive_deficit_count = 2  # next deficit makes it 3

        draw = _create_sample_draw(memory_db, "2026020", [10, 11, 12, 13, 14, 15], 8)
        batch = _create_prediction_batch(memory_db, "2026020", virtual_cost=10, virtual_reward=0)

        result = service.process_batch_verification(batch, draw, memory_db)
        assert result["is_triggered"] is True

        # In hot regime, momentum weight should increase above 0.25, hazard weight decrease below 0.40
        weights = result["weights"]
        assert weights["momentum"] > 0.25
        assert weights["hazard"] < 0.40
        # Invariant: weights must sum to 1.0 within floating tolerance
        total_w = weights["hazard"] + weights["markov"] + weights["momentum"]
        assert total_w == pytest.approx(1.0, abs=1e-3)

    def test_cold_reversion_regime_shifts_weight_to_hazard(self, memory_db):
        service = AdaptiveService()

        # Seed 20 prior draws with blue=1 so subsequent draws have omissions >= 20 (Cold Regime: m_bar >= 10)
        for i in range(1, 21):
            _create_sample_draw(memory_db, f"20260{i:02d}", [1, 2, 3, 4, 5, 6], 1)

        # Recent draws with distinct blues not seen in the 20 prior draws
        for i in range(21, 26):
            _create_sample_draw(memory_db, f"20260{i:02d}", [1, 2, 3, 4, 5, 6], i - 19)

        state = service.get_or_create_state(memory_db)
        state.consecutive_deficit_count = 2  # next deficit makes it 3

        draw = _create_sample_draw(memory_db, "2026030", [10, 11, 12, 13, 14, 15], 16)
        batch = _create_prediction_batch(memory_db, "2026030", virtual_cost=10, virtual_reward=0)

        result = service.process_batch_verification(batch, draw, memory_db)
        assert result["is_triggered"] is True

        weights = result["weights"]
        # In cold regime, hazard weight should increase above 0.40, momentum weight decrease below 0.25
        assert weights["hazard"] > 0.40
        assert weights["momentum"] < 0.25
        total_w = weights["hazard"] + weights["markov"] + weights["momentum"]
        assert total_w == pytest.approx(1.0, abs=1e-3)


class TestGuardrailSaturationClampsAndBounds:
    """Tests symmetric saturation clamp [-30.0, +30.0] on sum_bias and range bounds."""

    def test_large_positive_sum_deviation_clamps_to_positive_30(self, memory_db):
        service = AdaptiveService()
        state = service.get_or_create_state(memory_db)
        state.consecutive_deficit_count = 2  # next failure reaches streak 3

        # Actual draw with low sum = 30 (reds 1,2,3,4,5,15)
        draw = _create_sample_draw(memory_db, "2026150", [1, 2, 3, 4, 5, 15], 7)

        # Batch with predicted notes having very high sum = 170 (reds 25,26,27,28,31,33)
        # delta_sum = 170 - 30 = 140 -> shift = 140 * 0.25 = 35 -> clamped to +30.0
        high_reds = [[25, 26, 27, 28, 31, 33]] * 5
        batch = _create_prediction_batch(
            memory_db, "2026150", virtual_cost=10, virtual_reward=0, pred_reds=high_reds
        )

        result = service.process_batch_verification(batch, draw, memory_db)
        assert result["is_triggered"] is True

        memory_db.refresh(state)
        assert state.sum_bias == 30.0  # saturated at +30.0
        assert state.sum_range_min <= state.sum_range_max
        assert 65 <= state.sum_range_min <= 80
        assert 115 <= state.sum_range_max <= 145

    def test_large_negative_sum_deviation_clamps_to_negative_30(self, memory_db):
        service = AdaptiveService()
        state = service.get_or_create_state(memory_db)
        state.consecutive_deficit_count = 2  # next failure reaches streak 3

        # Actual draw with high sum = 170
        draw = _create_sample_draw(memory_db, "2026151", [25, 26, 27, 28, 31, 33], 7)

        # Batch with predicted notes having very low sum = 25
        # delta_sum = 25 - 170 = -145 -> shift = -36 -> clamped to -30.0
        low_reds = [[1, 2, 3, 4, 5, 10]] * 5
        batch = _create_prediction_batch(
            memory_db, "2026151", virtual_cost=10, virtual_reward=0, pred_reds=low_reds
        )

        result = service.process_batch_verification(batch, draw, memory_db)
        assert result["is_triggered"] is True

        memory_db.refresh(state)
        assert state.sum_bias == -30.0  # saturated at -30.0
        assert state.sum_range_min <= state.sum_range_max
        assert 65 <= state.sum_range_min <= 80
        assert 115 <= state.sum_range_max <= 145


class TestBreakEvenRecovery:
    """Tests break-even recovery behavior and parameter restoration."""

    def test_break_even_resets_streak_and_restores_concentrated_mode(self, memory_db):
        service = AdaptiveService()
        state = service.get_or_create_state(memory_db)

        # Put system into triggered deficit state: streak=4, DISPERSED mode, non-zero sum_bias
        state.consecutive_deficit_count = 4
        state.current_blue_mode = "DISPERSED"
        state.current_strategy_mode = "DISPERSED_BASELINE"
        state.sum_bias = 15.0
        state.sum_range_min = 68
        state.sum_range_max = 128
        memory_db.commit()

        # Draw occurs and batch achieves Break-Even (virtual_reward = 15 >= virtual_cost = 10)
        draw = _create_sample_draw(memory_db, "2026160", [2, 7, 14, 19, 24, 31], 8)
        batch = _create_prediction_batch(
            memory_db, "2026160", virtual_cost=10, virtual_reward=15
        )

        result = service.process_batch_verification(batch, draw, memory_db)

        # Streak resets to 0
        assert result["streak"] == 0
        assert result["is_triggered"] is True
        assert result["trigger_reason"] == "RECOVERY_UPGRADE"
        assert result["current_mode"] == "CONCENTRATED"

        # Check DB state restoration
        memory_db.refresh(state)
        assert state.consecutive_deficit_count == 0
        assert state.current_blue_mode == "CONCENTRATED"
        assert state.current_strategy_mode == "CONCENTRATED_BREAK_EVEN"
        assert state.sum_bias == 0.0
        assert state.sum_range_min == 75
        assert state.sum_range_max == 135

        # Check recovery logged in history
        history = memory_db.scalars(
            select(AdaptiveHistory).order_by(AdaptiveHistory.id.desc())
        ).first()
        assert history is not None
        assert history.trigger_reason == "RECOVERY_UPGRADE"
        assert history.streak_length == 0
        assert "Upgraded blue allocation mode to CONCENTRATED" in history.reflection_notes

    def test_break_even_maintained_when_already_concentrated(self, memory_db):
        service = AdaptiveService()
        state = service.get_or_create_state(memory_db)
        assert state.current_blue_mode == "CONCENTRATED"
        state.consecutive_deficit_count = 1

        draw = _create_sample_draw(memory_db, "2026161", [2, 7, 14, 19, 24, 31], 8)
        batch = _create_prediction_batch(
            memory_db, "2026161", virtual_cost=10, virtual_reward=10
        )

        result = service.process_batch_verification(batch, draw, memory_db)
        assert result["streak"] == 0
        assert result["current_mode"] == "CONCENTRATED"
        assert result["trigger_reason"] == "BREAK_EVEN_MAINTAINED"


class TestAdversarialAndEdgeCases:
    """Adversarial tests for feature deviations, history serialization, and custom thresholds."""

    def test_compute_feature_deviations_signed_deltas(self, memory_db):
        service = AdaptiveService()

        # Prior draw with some hot/cold balls
        _create_sample_draw(memory_db, "2026101", [1, 2, 3, 4, 5, 6], 1)
        _create_sample_draw(memory_db, "2026102", [1, 2, 3, 7, 8, 9], 2)

        # Actual draw
        act_draw = _create_sample_draw(memory_db, "2026103", [10, 15, 20, 25, 30, 31], 5)
        act_sum = sum(act_draw.reds)  # 131

        # Prediction batch with 5 identical notes of sum 100
        notes = [[10, 11, 12, 13, 24, 30]] * 5
        batch = _create_prediction_batch(
            memory_db, "2026103", virtual_cost=10, virtual_reward=0, pred_reds=notes
        )

        devs = service.compute_feature_deviations(batch, act_draw, memory_db)
        assert "delta_sum" in devs
        assert "delta_odd" in devs
        assert "delta_hot" in devs
        assert "delta_cold" in devs
        expected_delta_sum = 100 - act_sum  # 100 - 131 = -31
        assert devs["delta_sum"] == pytest.approx(expected_delta_sum, abs=0.1)

    def test_history_entry_to_dict_properties(self, memory_db):
        pre_state = {"blue_mode": "CONCENTRATED", "weights": {"hazard": 0.4, "markov": 0.35, "momentum": 0.25}}
        post_state = {"blue_mode": "DISPERSED", "weights": {"hazard": 0.35, "markov": 0.35, "momentum": 0.30}}
        deviations = {"delta_sum": 25.5, "delta_odd": -1.0, "delta_hot": 2.0, "delta_cold": -1.0}

        hist = AdaptiveHistory(
            trigger_issue="2026199",
            trigger_reason="TEST_REASON",
            streak_length=3,
            pre_state_json=json.dumps(pre_state),
            post_state_json=json.dumps(post_state),
            metrics_deviation_json=json.dumps(deviations),
            reflection_notes="Test reflection message",
        )
        memory_db.add(hist)
        memory_db.commit()

        d = hist.to_dict()
        assert d["trigger_issue"] == "2026199"
        assert d["issue_no"] == "2026199"
        assert d["streak_length"] == 3
        assert d["consecutive_losses"] == 3
        assert d["prev_mode"] == "CONCENTRATED"
        assert d["new_mode"] == "DISPERSED"
        assert d["sum_deviation"] == 25.5
        assert d["action_taken"] == "Test reflection message"
        assert hist.trigger_event == "TEST_REASON"

    def test_custom_loss_threshold_trigger(self, memory_db):
        service = AdaptiveService()
        state = service.get_or_create_state(memory_db)
        state.loss_threshold = 2  # custom strict threshold
        memory_db.commit()

        draw1 = _create_sample_draw(memory_db, "2026180", [1, 2, 3, 4, 5, 6], 1)
        batch1 = _create_prediction_batch(memory_db, "2026180", virtual_cost=10, virtual_reward=0)
        res1 = service.process_batch_verification(batch1, draw1, memory_db)
        assert res1["streak"] == 1
        assert res1["is_triggered"] is False

        # Streak 2 triggers because threshold = 2
        draw2 = _create_sample_draw(memory_db, "2026181", [1, 2, 3, 4, 5, 7], 2)
        batch2 = _create_prediction_batch(memory_db, "2026181", virtual_cost=10, virtual_reward=0)
        res2 = service.process_batch_verification(batch2, draw2, memory_db)
        assert res2["streak"] == 2
        assert res2["is_triggered"] is True
        assert res2["current_mode"] == "DISPERSED"

