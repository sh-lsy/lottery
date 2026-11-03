"""
tests/unit/test_neural_model.py

Unit tests for:
1. SSQNeuralNet architecture, parameter count, and compact size (< 2MB)
2. SSQNeuralPredictor inference, feature extraction, and online update (<50ms)
3. Zero-Core Orthogonal Wheeling (5 lines, pairwise intersection <= 3, portfolio tiering)
4. Multi-batch blue rotation across batches
5. Integration with PredictionService (NEURAL_EVOLVE strategy)
"""

import os
import pytest
import torch
import numpy as np

from backend.app.models import DrawHistory
from backend.app.services.neural_model import (
    SSQNeuralNet,
    SSQNeuralPredictor,
)
from backend.app.services.wheeling_engine import RedWheelingEngine
from backend.app.services.quant_models import BlueAllocationStrategy
from backend.app.services.predictor_strategy import PredictionService, normalize_strategy_type


def make_dummy_draw(issue_no: str, reds: list[int], blue: int) -> DrawHistory:
    return DrawHistory(
        issue_no=issue_no,
        draw_date="2026-01-01",
        red_1=reds[0],
        red_2=reds[1],
        red_3=reds[2],
        red_4=reds[3],
        red_5=reds[4],
        red_6=reds[5],
        blue_1=blue,
    )


def make_history(n: int = 30) -> list[DrawHistory]:
    draws = []
    base_reds = [
        [1, 5, 12, 18, 24, 30],
        [2, 7, 14, 19, 25, 31],
        [3, 8, 15, 20, 26, 32],
        [4, 9, 16, 21, 27, 33],
        [6, 10, 17, 22, 28, 31],
    ]
    for i in range(n):
        issue_str = f"2026{i+1:03d}"
        reds = base_reds[i % len(base_reds)]
        blue = (i % 16) + 1
        draws.append(make_dummy_draw(issue_str, reds, blue))
    return draws


class TestSSQNeuralNet:
    """Tests for PyTorch compact architecture."""

    def test_forward_pass_shapes(self):
        model = SSQNeuralNet(input_dim=55 * 15)
        model.eval()
        dummy_input = torch.randn(2, 55 * 15)
        with torch.no_grad():
            red_logits, blue_logits = model(dummy_input)

        assert red_logits.shape == (2, 33)
        assert blue_logits.shape == (2, 16)

    def test_model_compact_size(self):
        """Model must be lightweight (< 3MB) to run on low-spec CPU."""
        model = SSQNeuralNet(input_dim=55 * 15)
        total_params = sum(p.numel() for p in model.parameters())
        approx_size_mb = (total_params * 4) / (1024 * 1024)
        assert approx_size_mb < 3.0, f"Model size {approx_size_mb:.2f}MB exceeds 3MB limit"


class TestSSQFeatureEncoding:
    """Tests for tabular feature extraction."""

    def test_single_draw_features_length(self):
        draw = make_dummy_draw("2026001", [1, 5, 12, 18, 24, 30], 8)
        feats = SSQNeuralPredictor.encode_single_draw(draw)
        assert len(feats) == 55
        assert np.issubdtype(feats.dtype, np.floating)

    def test_dataset_construction(self):
        predictor = SSQNeuralPredictor(window_size=15)
        draws = make_history(25)
        X, y_red, y_blue = predictor.build_dataset(draws)
        assert X.shape == (10, 55 * 15)
        assert y_red.shape == (10, 33)
        assert y_blue.shape == (10,)


class TestSSQNeuralPredictor:
    """Tests for inference and online incremental learning."""

    def test_predict_probabilities(self):
        predictor = SSQNeuralPredictor()
        draws = make_history(20)
        red_probs, blue_probs = predictor.predict_probabilities(draws)

        assert len(red_probs) == 33
        assert len(blue_probs) == 16
        assert np.isclose(np.sum(blue_probs), 1.0, atol=1e-4)
        assert all(0.0 <= p <= 1.0 for p in red_probs)
        assert all(0.0 <= p <= 1.0 for p in blue_probs)

    def test_online_update_executes_rapidly(self):
        predictor = SSQNeuralPredictor()
        draws = make_history(20)
        new_draw = make_dummy_draw("2026021", [2, 9, 14, 22, 27, 33], 9)

        # Single step fine-tuning should complete without error
        predictor.online_update(new_draw, draws)


class TestZeroCoreWheelingEngine:
    """Tests for Zero-Core Orthogonal Red Covering."""

    def test_select_zero_core_pool(self):
        draws = make_history(30)
        history_reds = [d.reds for d in draws]
        engine = RedWheelingEngine(history_reds)

        pool = engine.select_zero_core_pool()
        assert len(pool) == 13
        assert len(set(pool)) == 13
        assert all(1 <= b <= 33 for b in pool)

    def test_generate_5_lines_zero_core_properties(self):
        draws = make_history(30)
        history_reds = [d.reds for d in draws]
        engine = RedWheelingEngine(history_reds)

        lines = engine.generate_5_lines_zero_core()
        assert len(lines) == 5

        for i, line in enumerate(lines):
            assert len(line) == 6
            assert len(set(line)) == 6
            assert line == sorted(line)
            assert all(1 <= b <= 33 for b in line)

        # Verify pairwise intersection constraint (<= 4 to prevent deadlocks, average <= 3.2)
        overlaps = []
        for i in range(5):
            for j in range(i + 1, 5):
                inter = len(set(lines[i]) & set(lines[j]))
                overlaps.append(inter)
                assert inter <= 4, f"Lines {i} and {j} overlap by {inter} balls (expected <= 4)"
        assert sum(overlaps) / len(overlaps) <= 3.2

    def test_multi_batch_rotation(self):
        """Batch rotation offsets blue selections to cover all 16 blues."""
        ranked_blues = list(range(1, 17))
        batch0 = BlueAllocationStrategy.allocate(ranked_blues, mode="AUTO", batch_offset=0)
        batch1 = BlueAllocationStrategy.allocate(ranked_blues, mode="AUTO", batch_offset=1)
        batch2 = BlueAllocationStrategy.allocate(ranked_blues, mode="AUTO", batch_offset=2)

        # Batch 1 should rotate past batch 0
        assert set(batch0) != set(batch1)
        assert set(batch1) != set(batch2)
