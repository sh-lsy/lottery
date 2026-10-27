"""
Feature Engineering Engine for SSQ-Quant-System.
Computes multi-dimensional quantitative features for Shuangseqiu lottery data:
- Core Red Ball Statistics: Sum, Span, AC Value, Odd/Even Count, Prime Count
- Structural Distribution: 3-Zone Partitioning, Consecutive Clustering, Repeats
- Dynamic Omission Tracking: Absence counters for 33 reds and 16 blues, snapshots, and Cold/Warm/Hot categorization
- Historical Ingestion & Incremental Synchronization
"""

import json
import logging
from typing import Dict, List, Optional, Set, Tuple, Any

from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session, sessionmaker

from backend.app.database import SessionLocal
from backend.app.models import DrawHistory, FeatureMetrics

logger = logging.getLogger("ssq_quant.feature_engine")


class FeatureEngine:
    """
    Engine for multi-dimensional statistical feature extraction and omission tracking.
    """

    # Strictly 11 official prime numbers in 1..33 (1 is neither prime nor composite)
    SSQ_PRIMES: Set[int] = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}

    def __init__(
        self,
        session_factory: Optional[sessionmaker] = None,
        draws: Optional[List[Any]] = None,
    ):
        """
        Initialize FeatureEngine.
        :param session_factory: SQLAlchemy sessionmaker (defaults to SessionLocal).
        :param draws: Optional pre-loaded draws for in-memory operations.
        """
        self.session_factory = session_factory or SessionLocal
        self.draws = draws

    # -----------------------------------------------------------------------
    # Core Mathematical Functions
    # -----------------------------------------------------------------------

    @staticmethod
    def calculate_sum(reds: List[int]) -> int:
        """
        Calculate sum of 6 red numbers.
        Theoretical range: [21, 183].
        """
        if len(reds) != 6:
            raise ValueError(f"Expected exactly 6 red balls, got {len(reds)}")
        return sum(reds)

    @staticmethod
    def calculate_span(reds: List[int]) -> int:
        """
        Calculate span of red numbers: max(reds) - min(reds).
        Theoretical range: [5, 32].
        """
        if len(reds) != 6:
            raise ValueError(f"Expected exactly 6 red balls, got {len(reds)}")
        return max(reds) - min(reds)

    @staticmethod
    def calculate_ac(reds: List[int]) -> int:
        """
        Calculate Arithmetic Complexity (AC value).
        Formula: AC = |D| - (6 - 1) = |D| - 5,
        where D = {|r_i - r_j| | 1 <= i < j <= 6} is the set of unique absolute pairwise differences.
        Theoretical range: [0, 10].
        """
        if len(reds) != 6:
            raise ValueError(f"Expected exactly 6 red balls, got {len(reds)}")
        if len(set(reds)) != 6:
            raise ValueError("Red balls must be distinct")

        diffs = {abs(reds[i] - reds[j]) for i in range(6) for j in range(i + 1, 6)}
        ac = len(diffs) - 5
        if ac < 0 or ac > 10:
            raise ValueError(f"Calculated AC value {ac} out of theoretical bounds [0, 10]")
        return ac

    @staticmethod
    def calculate_odd_count(reds: List[int]) -> int:
        """
        Calculate number of odd red balls.
        Theoretical range: [0, 6].
        """
        if len(reds) != 6:
            raise ValueError(f"Expected exactly 6 red balls, got {len(reds)}")
        return sum(1 for r in reds if r % 2 == 1)

    @staticmethod
    def calculate_prime_count(reds: List[int]) -> int:
        """
        Calculate count of primes among the 6 red balls using the 11 official SSQ primes:
        {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}.
        Theoretical range: [0, 6].
        """
        if len(reds) != 6:
            raise ValueError(f"Expected exactly 6 red balls, got {len(reds)}")
        return sum(1 for r in reds if r in FeatureEngine.SSQ_PRIMES)

    @staticmethod
    def calculate_zones(reds: List[int]) -> Tuple[int, int, int]:
        """
        Calculate distribution across 3 equal-length zones:
        - Zone 1: 01-11
        - Zone 2: 12-22
        - Zone 3: 23-33
        Conservation law: zone1 + zone2 + zone3 == 6.
        """
        if len(reds) != 6:
            raise ValueError(f"Expected exactly 6 red balls, got {len(reds)}")
        z1 = sum(1 for r in reds if 1 <= r <= 11)
        z2 = sum(1 for r in reds if 12 <= r <= 22)
        z3 = sum(1 for r in reds if 23 <= r <= 33)
        if z1 + z2 + z3 != 6:
            raise ValueError(f"Zone counts sum to {z1 + z2 + z3}, expected 6")
        return z1, z2, z3

    @staticmethod
    def calculate_consecutive_groups(reds: List[int]) -> int:
        """
        Count maximal connected components of consecutive red numbers.
        Example: [4, 5, 12, 18, 19, 27] -> 2 groups ((4,5) and (18,19)).
        Example: [4, 5, 6, 18, 22, 27] -> 1 group ((4,5,6) 3-chain).
        Example: [1, 2, 3, 4, 5, 6] -> 1 group.
        """
        if len(reds) != 6:
            raise ValueError(f"Expected exactly 6 red balls, got {len(reds)}")
        sorted_reds = sorted(reds)
        diffs = [sorted_reds[i + 1] - sorted_reds[i] for i in range(5)]

        groups = 0
        in_run = False
        for d in diffs:
            if d == 1:
                if not in_run:
                    groups += 1
                    in_run = True
            else:
                in_run = False
        return groups

    @staticmethod
    def calculate_repeats(reds: List[int], prev_reds: Optional[List[int]]) -> int:
        """
        Calculate count of red numbers repeating from immediately prior draw.
        Range: [0, 6]. Returns 0 if prev_reds is None.
        """
        if not prev_reds:
            return 0
        return len(set(reds) & set(prev_reds))

    @staticmethod
    def classify_omission(omission: int) -> str:
        """
        Classify omission value into Cold / Warm / Hot:
        - Hot: m <= 4
        - Warm: 5 <= m <= 9
        - Cold: m >= 10
        Raises ValueError if omission < 0.
        """
        if omission < 0:
            raise ValueError(f"Omission cannot be negative: {omission}")
        if omission <= 4:
            return "HOT"
        elif 5 <= omission <= 9:
            return "WARM"
        else:
            return "COLD"

    # -----------------------------------------------------------------------
    # Dynamic Omission State Tracking
    # -----------------------------------------------------------------------

    @staticmethod
    def get_initial_omission_state() -> Tuple[Dict[int, int], Dict[int, int]]:
        """
        Initial absence state for all 33 red and 16 blue numbers prior to earliest draw (2003001).
        All values are initialized to 0.
        """
        red_omissions = {b: 0 for b in range(1, 34)}
        blue_omissions = {b: 0 for b in range(1, 17)}
        return red_omissions, blue_omissions

    @staticmethod
    def parse_omission_snapshot(snapshot: Optional[Dict[str, Any]]) -> Tuple[Dict[int, int], Dict[int, int]]:
        """
        Parses omission snapshot dictionary (supporting string or integer keys).
        Returns integer-keyed (red_dict, blue_dict).
        """
        if not snapshot:
            return FeatureEngine.get_initial_omission_state()

        red_raw = snapshot.get("red", {})
        blue_raw = snapshot.get("blue", {})

        red_omissions = {}
        for b in range(1, 34):
            val = red_raw.get(b) if b in red_raw else red_raw.get(str(b), 0)
            red_omissions[b] = int(val)

        blue_omissions = {}
        for b in range(1, 17):
            val = blue_raw.get(b) if b in blue_raw else blue_raw.get(str(b), 0)
            blue_omissions[b] = int(val)

        return red_omissions, blue_omissions

    @staticmethod
    def update_omissions(
        red_omissions: Dict[int, int],
        blue_omissions: Dict[int, int],
        drawn_reds: List[int],
        drawn_blue: int,
    ) -> Tuple[Dict[int, int], Dict[int, int], str]:
        """
        Updates omission state immediately after a draw:
        - Drawn numbers reset to 0.
        - Undrawn numbers increment by 1.
        Returns (new_red_omissions, new_blue_omissions, snapshot_json).
        """
        new_reds: Dict[int, int] = {}
        drawn_reds_set = set(drawn_reds)
        for b in range(1, 34):
            new_reds[b] = 0 if b in drawn_reds_set else red_omissions[b] + 1

        new_blues: Dict[int, int] = {}
        for b in range(1, 17):
            new_blues[b] = 0 if b == drawn_blue else blue_omissions[b] + 1

        snapshot_dict = {
            "red": {str(b): new_reds[b] for b in range(1, 34)},
            "blue": {str(b): new_blues[b] for b in range(1, 17)},
        }
        snapshot_json = json.dumps(snapshot_dict, separators=(",", ":"))
        return new_reds, new_blues, snapshot_json

    # -----------------------------------------------------------------------
    # Single Draw Feature Computation
    # -----------------------------------------------------------------------

    def compute_metrics_for_draw(
        self,
        draw: Any,
        prev_draw: Optional[Any] = None,
        prior_snapshot: Optional[Dict[str, Any]] = None,
    ) -> FeatureMetrics:
        """
        Computes all feature metrics for a single draw.
        :param draw: DrawHistory or compatible draw object.
        :param prev_draw: DrawHistory from immediately prior issue, or None.
        :param prior_snapshot: Omission snapshot dictionary immediately prior to this draw.
        :return: Unsaved FeatureMetrics ORM model instance.
        """
        # Extract reds and blue
        if hasattr(draw, "reds") and callable(getattr(draw, "reds")):
            reds = draw.reds()
        elif hasattr(draw, "reds") and isinstance(draw.reds, list):
            reds = draw.reds
        else:
            reds = [getattr(draw, f"red_{i}") for i in range(1, 7)]

        sorted_reds = sorted(reds)
        if len(sorted_reds) != 6:
            raise ValueError(f"Draw {getattr(draw, 'issue_no', '?')} must have 6 red balls")
        if any(r < 1 or r > 33 for r in sorted_reds):
            raise ValueError(f"Red ball out of bounds [1, 33] in draw {getattr(draw, 'issue_no', '?')}")

        blue = getattr(draw, "blue_1", None)
        if blue is None:
            blue = getattr(draw, "blue", None)
        if blue is None or blue < 1 or blue > 16:
            raise ValueError(f"Invalid blue ball {blue} in draw {getattr(draw, 'issue_no', '?')}")

        issue_no = str(getattr(draw, "issue_no"))

        # Extract prev_reds
        prev_reds = None
        if prev_draw is not None:
            if hasattr(prev_draw, "reds") and isinstance(prev_draw.reds, list):
                prev_reds = prev_draw.reds
            elif hasattr(prev_draw, "reds") and callable(getattr(prev_draw, "reds")):
                prev_reds = prev_draw.reds()
            else:
                prev_reds = [getattr(prev_draw, f"red_{i}") for i in range(1, 7)]

        # 1. Core Red Statistics
        sum_red = self.calculate_sum(sorted_reds)
        span_red = self.calculate_span(sorted_reds)
        ac_value = self.calculate_ac(sorted_reds)
        odd_count = self.calculate_odd_count(sorted_reds)
        prime_count = self.calculate_prime_count(sorted_reds)

        # 2. Structural Features
        zone1_count, zone2_count, zone3_count = self.calculate_zones(sorted_reds)
        consecutive_groups = self.calculate_consecutive_groups(sorted_reds)
        repeat_prev_red = self.calculate_repeats(sorted_reds, prev_reds)

        # 3. Omission Tracking
        prior_red_omissions, prior_blue_omissions = self.parse_omission_snapshot(prior_snapshot)
        missing_sum_red = sum(prior_red_omissions[r] for r in sorted_reds)
        missing_blue = prior_blue_omissions[blue]

        # Update omissions post-draw for snapshot
        _, _, snapshot_json = self.update_omissions(
            prior_red_omissions, prior_blue_omissions, sorted_reds, blue
        )

        return FeatureMetrics(
            issue_no=issue_no,
            sum_red=sum_red,
            span_red=span_red,
            ac_value=ac_value,
            odd_count=odd_count,
            prime_count=prime_count,
            zone1_count=zone1_count,
            zone2_count=zone2_count,
            zone3_count=zone3_count,
            consecutive_groups=consecutive_groups,
            repeat_prev_red=repeat_prev_red,
            missing_sum_red=missing_sum_red,
            missing_blue=missing_blue,
            missing_snapshot_json=snapshot_json,
        )

    # -----------------------------------------------------------------------
    # Ingestion & Synchronization Pipeline
    # -----------------------------------------------------------------------

    def compute_all_features(self, force: bool = False) -> int:
        """
        Chronologically computes and persists feature metrics for all draws in ssq_draw_history.
        :param force: If True, purges ssq_feature_metrics and recomputes all records.
                      If False, computes incrementally or fills empty table.
        :return: Count of newly inserted / updated feature metric records.
        """
        with self.session_factory() as session:
            existing_count = session.scalar(select(func.count(FeatureMetrics.issue_no))) or 0
            total_draws = session.scalar(select(func.count(DrawHistory.id))) or 0

            if not force:
                if existing_count == total_draws and total_draws > 0:
                    logger.info("All %d feature metrics are already up-to-date.", existing_count)
                    return 0
                if existing_count > 0:
                    logger.info("Database has %d features vs %d draws. Running incremental computation.", existing_count, total_draws)
                    return self.compute_latest_features()
            else:
                logger.info("Force recomputation requested: purging existing ssq_feature_metrics...")
                session.execute(delete(FeatureMetrics))
                session.commit()

            # Retrieve all draws strictly in chronological order
            draws = session.scalars(
                select(DrawHistory).order_by(DrawHistory.issue_no.asc())
            ).all()

            if not draws:
                logger.warning("No draws found in ssq_draw_history.")
                return 0

            logger.info("Starting chronological feature calculation for %d draws...", len(draws))
            prior_draw: Optional[DrawHistory] = None
            prior_snapshot: Optional[Dict[str, Any]] = None
            batch: List[FeatureMetrics] = []
            batch_size = 500
            total_computed = 0

            for draw in draws:
                fm = self.compute_metrics_for_draw(
                    draw=draw,
                    prev_draw=prior_draw,
                    prior_snapshot=prior_snapshot,
                )
                batch.append(fm)
                prior_draw = draw
                prior_snapshot = fm.missing_snapshot
                total_computed += 1

                if len(batch) >= batch_size:
                    session.add_all(batch)
                    session.commit()
                    batch.clear()

            if batch:
                session.add_all(batch)
                session.commit()

            logger.info("Successfully computed and committed %d feature metric rows.", total_computed)
            return total_computed

    def compute_latest_features(self) -> int:
        """
        Computes features incrementally for any draws not yet present in ssq_feature_metrics.
        :return: Number of newly computed feature rows.
        """
        with self.session_factory() as session:
            latest_feature = session.scalars(
                select(FeatureMetrics).order_by(FeatureMetrics.issue_no.desc()).limit(1)
            ).first()

            if latest_feature is None:
                # No feature records exist at all -> full run
                return self.compute_all_features(force=False)

            latest_issue_no = latest_feature.issue_no

            uncomputed_draws = session.scalars(
                select(DrawHistory)
                .filter(DrawHistory.issue_no > latest_issue_no)
                .order_by(DrawHistory.issue_no.asc())
            ).all()

            if not uncomputed_draws:
                logger.info("Feature metrics are already up to date with latest issue %s.", latest_issue_no)
                return 0

            logger.info("Found %d uncomputed draws after issue %s.", len(uncomputed_draws), latest_issue_no)

            prior_draw = session.scalars(
                select(DrawHistory).filter(DrawHistory.issue_no == latest_issue_no)
            ).first()
            prior_snapshot = latest_feature.missing_snapshot

            batch: List[FeatureMetrics] = []
            total_computed = 0

            for draw in uncomputed_draws:
                fm = self.compute_metrics_for_draw(
                    draw=draw,
                    prev_draw=prior_draw,
                    prior_snapshot=prior_snapshot,
                )
                batch.append(fm)
                prior_draw = draw
                prior_snapshot = fm.missing_snapshot
                total_computed += 1

            session.add_all(batch)
            session.commit()

            logger.info("Successfully added %d incremental feature metrics.", total_computed)
            return total_computed

    def compute_all_missing_features(self) -> int:
        """
        Convenience alias for computing missing features incrementally.
        """
        return self.compute_latest_features()
