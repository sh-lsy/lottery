"""
5-line prediction task service (re-exported from predictor_strategy).
"""

from backend.app.services.predictor_strategy import (
    PredictionService,
    normalize_strategy_type,
)

__all__ = ["PredictionService", "normalize_strategy_type"]
