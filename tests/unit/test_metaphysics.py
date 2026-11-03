"""
tests/unit/test_metaphysics.py

Unit tests for Zhouyi Bagua, Hetu-Luoshu Wuxing Metaphysics Engine:
1. Solar date to Sixty Jiazi GanZhi conversion.
2. Hetu-Luoshu number Wuxing classification.
3. Ten Gods and Wuxing affinity calculations.
4. Meihua Yishu hexagram generation and prophecy.
5. PredictionService integration with YIJING_METAPHYSICS strategy.
"""

from datetime import date
import pytest
import numpy as np

from backend.app.services.metaphysics_engine import (
    MetaphysicsEngine,
    get_ball_wuxing,
    JIUGONG_BAGUA,
)
from backend.app.services.predictor_strategy import PredictionService, normalize_strategy_type


class TestMetaphysicsEngine:
    """Tests for core astrological and Wuxing calculations."""

    def test_get_day_ganzhi_known_dates(self):
        # 2000-01-01 was 戊午 (Index 54)
        gz, gan, zhi = MetaphysicsEngine.get_day_ganzhi(date(2000, 1, 1))
        assert gz == "戊午"
        assert gan == "戊"
        assert zhi == "午"

        # 2024-02-10 (Chinese New Year 2024) was 甲辰
        gz_cny, gan_cny, zhi_cny = MetaphysicsEngine.get_day_ganzhi(date(2024, 2, 10))
        assert gz_cny == "甲辰"
        assert gan_cny == "甲"
        assert zhi_cny == "辰"

    def test_ball_wuxing_mapping(self):
        assert get_ball_wuxing(1) == "水"
        assert get_ball_wuxing(6) == "水"
        assert get_ball_wuxing(16) == "水"
        assert get_ball_wuxing(2) == "火"
        assert get_ball_wuxing(7) == "火"
        assert get_ball_wuxing(3) == "木"
        assert get_ball_wuxing(8) == "木"
        assert get_ball_wuxing(4) == "金"
        assert get_ball_wuxing(9) == "金"
        assert get_ball_wuxing(5) == "土"
        assert get_ball_wuxing(10) == "土"

    def test_ten_gods_relations(self):
        # Day master Jia Wood (甲木) controls Earth (土) -> Wealth (偏正财星)
        name, mult = MetaphysicsEngine.calculate_ten_gods_relation("甲", 5)  # 5 is Earth
        assert "财" in name
        assert mult >= 1.20

        # Water (水) generates Wood (甲木) -> Resource (印绶生身)
        name_r, mult_r = MetaphysicsEngine.calculate_ten_gods_relation("甲", 1)  # 1 is Water
        assert "印" in name_r
        assert mult_r >= 1.15

    def test_compute_metaphysics_probabilities(self):
        r_probs, b_probs, meta = MetaphysicsEngine.compute_metaphysics_probabilities("2026-11-03", "2026125")
        assert len(r_probs) == 33
        assert len(b_probs) == 16
        assert np.isclose(sum(r_probs), 1.0, atol=1e-4)
        assert np.isclose(sum(b_probs), 1.0, atol=1e-4)

        assert "day_ganzhi" in meta
        assert "day_master_element" in meta
        assert "hexagram_name" in meta
        assert "prophecy_text" in meta
        assert len(meta["hexagram_name"]) > 0

    def test_ticket_wuxing_breakdown(self):
        reds = [1, 6, 8, 14, 22, 27]  # 水(1,6), 木(8), 金(14), 火(22,27)
        blue = 3  # 木
        bd = MetaphysicsEngine.get_ticket_wuxing_breakdown(reds, blue)

        assert bd["counts"]["水"] == 2
        assert bd["counts"]["木"] == 2
        assert bd["counts"]["火"] == 2
        assert bd["counts"]["金"] == 1
        assert bd["counts"]["土"] == 0
        assert sum(bd["percentages"].values()) == pytest.approx(100.0, abs=0.5)

    def test_strategy_normalization(self):
        assert normalize_strategy_type("YIJING_METAPHYSICS") == "YIJING_METAPHYSICS"
        assert normalize_strategy_type("bagua") == "YIJING_METAPHYSICS"
        assert normalize_strategy_type("metaphysics") == "YIJING_METAPHYSICS"
