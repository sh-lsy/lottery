"""
backend/app/services/collision_cache.py

Thread-safe in-memory cache for historical draws and feature metrics.
Enables sub-15ms collision sandbox queries across 3,500+ draws with zero DB overhead.
"""

import threading
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import DrawHistory, FeatureMetrics


class CollisionCache:
    _instance: Optional["CollisionCache"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.is_initialized: bool = False
        self.draw_records: List[Tuple[str, str, List[int], frozenset, int, Optional[int], Optional[int]]] = []
        self.cached_sums: np.ndarray = np.empty(0, dtype=np.float64)
        self.cached_acs: np.ndarray = np.empty(0, dtype=np.float64)
        self.cached_spans: np.ndarray = np.empty(0, dtype=np.float64)
        self.cached_odds: np.ndarray = np.empty(0, dtype=np.float64)
        self.stats: Dict[str, Tuple[float, float, float]] = {}

    @classmethod
    def get_instance(cls) -> "CollisionCache":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def ensure_loaded(self, session: Session) -> None:
        if self.is_initialized:
            return

        with self._lock:
            if self.is_initialized:
                return

            # 1. Fetch draws via lightweight scalar tuples
            draw_tuples = session.execute(
                select(
                    DrawHistory.issue_no,
                    DrawHistory.draw_date,
                    DrawHistory.red_1,
                    DrawHistory.red_2,
                    DrawHistory.red_3,
                    DrawHistory.red_4,
                    DrawHistory.red_5,
                    DrawHistory.red_6,
                    DrawHistory.blue_1,
                    DrawHistory.first_prize_amount,
                    DrawHistory.second_prize_amount,
                ).order_by(DrawHistory.issue_no.asc())
            ).all()

            self.draw_records = [
                (
                    row[0],
                    str(row[1]),
                    [row[2], row[3], row[4], row[5], row[6], row[7]],
                    frozenset(row[2:8]),
                    row[8],
                    row[9],
                    row[10],
                )
                for row in draw_tuples
            ]

            # 2. Fetch feature metrics via lightweight scalar tuples
            fm_tuples = session.execute(
                select(
                    FeatureMetrics.sum_red,
                    FeatureMetrics.ac_value,
                    FeatureMetrics.span_red,
                    FeatureMetrics.odd_count,
                )
            ).all()

            if fm_tuples:
                self.cached_sums = np.array([f[0] for f in fm_tuples], dtype=np.float64)
                self.cached_acs = np.array([f[1] for f in fm_tuples], dtype=np.float64)
                self.cached_spans = np.array([f[2] for f in fm_tuples], dtype=np.float64)
                self.cached_odds = np.array([f[3] for f in fm_tuples], dtype=np.float64)

                self.stats = {
                    "sum": (float(np.mean(self.cached_sums)), float(np.min(self.cached_sums)), float(np.max(self.cached_sums))),
                    "ac": (float(np.mean(self.cached_acs)), float(np.min(self.cached_acs)), float(np.max(self.cached_acs))),
                    "span": (float(np.mean(self.cached_spans)), float(np.min(self.cached_spans)), float(np.max(self.cached_spans))),
                    "odd": (float(np.mean(self.cached_odds)), float(np.min(self.cached_odds)), float(np.max(self.cached_odds))),
                }
            else:
                self.cached_sums = np.empty(0, dtype=np.float64)
                self.cached_acs = np.empty(0, dtype=np.float64)
                self.cached_spans = np.empty(0, dtype=np.float64)
                self.cached_odds = np.empty(0, dtype=np.float64)
                self.stats = {}

            self.is_initialized = True

    def invalidate(self) -> None:
        with self._lock:
            self.is_initialized = False
            self.draw_records = []
            self.cached_sums = np.empty(0, dtype=np.float64)
            self.cached_acs = np.empty(0, dtype=np.float64)
            self.cached_spans = np.empty(0, dtype=np.float64)
            self.cached_odds = np.empty(0, dtype=np.float64)
            self.stats = {}
