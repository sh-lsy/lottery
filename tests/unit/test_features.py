"""
Unit tests for Milestone 2: Feature Engineering Engine (FeatureEngine).
Covers:
1. Core Mathematical Functions:
   - Sum & Span calculations and boundaries
   - Arithmetic Complexity (AC Value) bounds, proofs, and error validation
   - Odd / Even ratio counting and conservation
   - Prime number counting using strict 11 official SSQ primes
   - 3-Zone partitioning and conservation law
   - Consecutive groups clustering (maximal connected components)
   - Repeat numbers counting from immediately prior draw
2. Dynamic Omission Tracking:
   - Cold / Warm / Hot classification rules and boundaries
   - Initial omission state (issue 2003001)
   - Cumulative step updates for red and blue balls
   - missing_sum_red and missing_blue calculations
   - JSON snapshot serialization and schema verification
3. FeatureEngine Service Ingestion & Synchronization Pipeline:
   - compute_metrics_for_draw model generation
   - compute_all_features full calculation and idempotency
   - compute_latest_features incremental synchronization
4. CLI Subcommand Integration:
   - Argument parsing and handle_compute_features dispatch
"""

from datetime import date
import json
import sqlite3
from typing import List, Dict, Any
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models import DrawHistory, FeatureMetrics
from backend.app.services.feature_engine import FeatureEngine
from backend.app.cli import build_parser, main


class TestCoreMathematicalFormulas:
    """Test suite for mathematical feature computation functions."""

    def test_sum_calculation(self):
        """Verify red ball sum calculation."""
        reds = [2, 7, 14, 19, 24, 31]
        assert FeatureEngine.calculate_sum(reds) == 97

    def test_sum_boundaries(self):
        """Boundary minimum (21) and maximum (183) sum."""
        min_reds = [1, 2, 3, 4, 5, 6]
        max_reds = [28, 29, 30, 31, 32, 33]
        assert FeatureEngine.calculate_sum(min_reds) == 21
        assert FeatureEngine.calculate_sum(max_reds) == 183

    def test_span_calculation(self):
        """Verify red ball span calculation (max - min)."""
        reds = [2, 7, 14, 19, 24, 31]
        assert FeatureEngine.calculate_span(reds) == 29

    def test_span_boundaries(self):
        """Boundary minimum span (5) and maximum span (32)."""
        min_span_reds = [1, 2, 3, 4, 5, 6]
        max_span_reds = [1, 5, 10, 15, 20, 33]
        assert FeatureEngine.calculate_span(min_span_reds) == 5
        assert FeatureEngine.calculate_span(max_span_reds) == 32

    def test_ac_value_arithmetic_progression_zero(self):
        """AC = 0 for arithmetic progression sequences (e.g. step=1 or step=5)."""
        ap_step_1 = [1, 2, 3, 4, 5, 6]
        ap_step_5 = [5, 10, 15, 20, 25, 30]
        assert FeatureEngine.calculate_ac(ap_step_1) == 0
        assert FeatureEngine.calculate_ac(ap_step_5) == 0

    def test_ac_value_maximum_ten(self):
        """AC = 10 for sequences with 15 distinct pairwise differences (e.g. powers of 2)."""
        pow_two = [1, 2, 4, 8, 16, 32]
        assert FeatureEngine.calculate_ac(pow_two) == 10

    def test_ac_value_realistic_draw(self):
        """AC calculation for realistic draw [2, 7, 14, 19, 24, 31]."""
        # Pairwise differences: {5, 7, 10, 12, 17, 22, 24, 29} -> 8 distinct values -> AC = 8 - 5 = 3
        reds = [2, 7, 14, 19, 24, 31]
        assert FeatureEngine.calculate_ac(reds) == 3

    def test_ac_value_rejects_duplicates(self):
        """AC calculation must reject duplicate numbers."""
        duplicate_reds = [1, 1, 3, 4, 5, 6]
        with pytest.raises(ValueError, match="distinct"):
            FeatureEngine.calculate_ac(duplicate_reds)

    def test_ac_value_requires_six_numbers(self):
        """AC calculation must reject input with length != 6."""
        with pytest.raises(ValueError, match="6 red balls"):
            FeatureEngine.calculate_ac([1, 2, 3, 4, 5])

    def test_odd_count(self):
        """Verify odd numbers counting."""
        reds = [2, 7, 14, 19, 24, 31]  # 7, 19, 31 are odd
        assert FeatureEngine.calculate_odd_count(reds) == 3

    def test_odd_count_boundaries(self):
        """Boundary all odds (6) and all evens (0)."""
        all_odd = [1, 3, 5, 7, 9, 11]
        all_even = [2, 4, 6, 8, 10, 12]
        assert FeatureEngine.calculate_odd_count(all_odd) == 6
        assert FeatureEngine.calculate_odd_count(all_even) == 0

    def test_prime_count_official_primes(self):
        """Verify prime counting with strict 11 primes {2,3,5,7,11,13,17,19,23,29,31}."""
        assert FeatureEngine.SSQ_PRIMES == {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}
        assert 1 not in FeatureEngine.SSQ_PRIMES
        assert 2 in FeatureEngine.SSQ_PRIMES

        reds = [1, 2, 9, 15, 17, 21]  # 2, 17 are prime -> 2 primes
        assert FeatureEngine.calculate_prime_count(reds) == 2

    def test_prime_count_boundaries(self):
        """Boundary 6 primes vs 0 primes."""
        all_prime = [2, 3, 5, 7, 11, 13]
        no_prime = [1, 4, 6, 8, 9, 10]
        assert FeatureEngine.calculate_prime_count(all_prime) == 6
        assert FeatureEngine.calculate_prime_count(no_prime) == 0

    def test_zone_partitioning(self):
        """Verify 3-Zone distribution: Zone 1 (01-11), Zone 2 (12-22), Zone 3 (23-33)."""
        reds = [2, 7, 14, 19, 24, 31]
        z1, z2, z3 = FeatureEngine.calculate_zones(reds)
        assert (z1, z2, z3) == (2, 2, 2)
        assert z1 + z2 + z3 == 6

    def test_zone_boundaries(self):
        """Boundary all in zone 1 and all in zone 3."""
        all_z1 = [1, 3, 5, 7, 9, 11]
        all_z3 = [23, 25, 27, 29, 31, 33]
        assert FeatureEngine.calculate_zones(all_z1) == (6, 0, 0)
        assert FeatureEngine.calculate_zones(all_z3) == (0, 0, 6)

    def test_consecutive_groups_clustering(self):
        """Verify consecutive groups counts connected components with adjacent diff=1."""
        # Single 6-number chain -> 1 group
        assert FeatureEngine.calculate_consecutive_groups([10, 11, 12, 13, 14, 15]) == 1

        # Two distinct consecutive pairs -> 2 groups
        assert FeatureEngine.calculate_consecutive_groups([4, 5, 12, 18, 19, 27]) == 2

        # One 3-number chain -> 1 group
        assert FeatureEngine.calculate_consecutive_groups([4, 5, 6, 18, 22, 27]) == 1

        # Zero consecutive numbers -> 0 groups
        assert FeatureEngine.calculate_consecutive_groups([2, 5, 9, 13, 18, 25]) == 0

        # Three pairs -> 3 groups
        assert FeatureEngine.calculate_consecutive_groups([1, 2, 10, 11, 20, 21]) == 3

    def test_repeat_prev_red_counting(self):
        """Verify counting repeats from previous draw."""
        prior = [2, 7, 14, 19, 24, 31]
        curr = [5, 8, 14, 19, 27, 32]
        assert FeatureEngine.calculate_repeats(curr, prior) == 2

        # First draw (no prior)
        assert FeatureEngine.calculate_repeats(curr, None) == 0

        # Full repeat (6)
        assert FeatureEngine.calculate_repeats(prior, prior) == 6

        # Zero repeat
        assert FeatureEngine.calculate_repeats([1, 3, 5, 8, 10, 12], prior) == 0


class TestOmissionTracking:
    """Test suite for omission updates, snapshot serialization, and Cold/Warm/Hot logic."""

    def test_cold_warm_hot_classification(self):
        """Test omission threshold classifications."""
        # Hot: m <= 4
        assert FeatureEngine.classify_omission(0) == "HOT"
        assert FeatureEngine.classify_omission(4) == "HOT"

        # Warm: 5 <= m <= 9
        assert FeatureEngine.classify_omission(5) == "WARM"
        assert FeatureEngine.classify_omission(9) == "WARM"

        # Cold: m >= 10
        assert FeatureEngine.classify_omission(10) == "COLD"
        assert FeatureEngine.classify_omission(55) == "COLD"

        # Negative omission raises ValueError
        with pytest.raises(ValueError):
            FeatureEngine.classify_omission(-1)

    def test_initial_omission_state(self):
        """Initial omission state prior to 2003001 contains 33 reds and 16 blues all 0."""
        reds, blues = FeatureEngine.get_initial_omission_state()
        assert len(reds) == 33
        assert len(blues) == 16
        assert all(v == 0 for v in reds.values())
        assert all(v == 0 for v in blues.values())

    def test_omission_update_step(self):
        """Drawn numbers reset to 0, undrawn increment by 1."""
        reds, blues = FeatureEngine.get_initial_omission_state()
        drawn_reds = [2, 7, 14, 19, 24, 31]
        drawn_blue = 8

        new_reds, new_blues, snapshot_json = FeatureEngine.update_omissions(
            reds, blues, drawn_reds, drawn_blue
        )

        # Check drawn balls reset to 0
        for r in drawn_reds:
            assert new_reds[r] == 0
        assert new_blues[drawn_blue] == 0

        # Check undrawn balls incremented to 1
        assert new_reds[1] == 1
        assert new_reds[33] == 1
        assert new_blues[1] == 1
        assert new_blues[16] == 1

        # Check snapshot JSON schema
        snapshot = json.loads(snapshot_json)
        assert len(snapshot["red"]) == 33
        assert len(snapshot["blue"]) == 16
        assert snapshot["red"]["2"] == 0
        assert snapshot["red"]["1"] == 1
        assert snapshot["blue"]["8"] == 0
        assert snapshot["blue"]["1"] == 1

    def test_cumulative_omission_across_multiple_draws(self):
        """Verify omission incrementing across multiple consecutive draws."""
        reds, blues = FeatureEngine.get_initial_omission_state()

        # Draw 1: reds include 5, blue is 3
        reds, blues, _ = FeatureEngine.update_omissions(reds, blues, [5, 10, 15, 20, 25, 30], 3)
        assert reds[5] == 0
        assert reds[1] == 1
        assert blues[3] == 0
        assert blues[1] == 1

        # Draw 2: reds do NOT include 5, blue is NOT 3
        reds, blues, _ = FeatureEngine.update_omissions(reds, blues, [2, 7, 14, 19, 24, 31], 8)
        assert reds[5] == 1
        assert reds[1] == 2
        assert blues[3] == 1
        assert blues[8] == 0

        # Draw 3: reds include 5 again
        reds, blues, _ = FeatureEngine.update_omissions(reds, blues, [5, 8, 12, 19, 27, 32], 8)
        assert reds[5] == 0  # reset
        assert reds[1] == 3  # incremented to 3
        assert blues[8] == 0  # repeated blue resets to 0
        assert blues[3] == 2  # incremented to 2


class TestFeatureEngineService:
    """Test FeatureEngine ORM computation and ingestion pipeline."""

    @pytest.fixture
    def memory_db_session(self):
        """In-memory SQLite database session with full schema."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session, Session
        session.close()

    def test_compute_metrics_for_draw_first_issue(self):
        """First issue 2003001 has repeat_prev_red=0 and missing_sum_red=0."""
        engine = FeatureEngine()
        draw = DrawHistory(
            issue_no="2003001",
            draw_date=date(2003, 2, 23),
            weekday=7,
            red_1=10, red_2=11, red_3=12, red_4=13, red_5=26, red_6=28,
            blue_1=11,
            red_seq_str="10,11,12,13,26,28",
        )

        fm = engine.compute_metrics_for_draw(draw, prev_draw=None, prior_snapshot=None)

        assert fm.issue_no == "2003001"
        assert fm.sum_red == 10 + 11 + 12 + 13 + 26 + 28  # 100
        assert fm.span_red == 28 - 10  # 18
        assert fm.odd_count == 2  # 11, 13
        assert fm.prime_count == 2  # 11, 13
        assert fm.zone1_count == 2  # 10, 11
        assert fm.zone2_count == 2  # 12, 13
        assert fm.zone3_count == 2  # 26, 28
        assert fm.consecutive_groups == 1  # (10, 11, 12, 13) 4-chain
        assert fm.repeat_prev_red == 0
        assert fm.missing_sum_red == 0
        assert fm.missing_blue == 0
        assert len(fm.missing_snapshot["red"]) == 33
        assert len(fm.missing_snapshot["blue"]) == 16

    def test_compute_all_features_and_idempotency(self, memory_db_session):
        """Test full computation and idempotent re-run."""
        session, Session = memory_db_session

        # Insert 3 sample draws
        draws = [
            DrawHistory(
                issue_no="2026101",
                draw_date=date(2026, 8, 2),
                weekday=7,
                red_1=2, red_2=7, red_3=14, red_4=19, red_5=24, red_6=31,
                blue_1=8,
                red_seq_str="02,07,14,19,24,31",
            ),
            DrawHistory(
                issue_no="2026102",
                draw_date=date(2026, 8, 4),
                weekday=2,
                red_1=5, red_2=8, red_3=12, red_4=19, red_5=27, red_6=32,
                blue_1=3,
                red_seq_str="05,08,12,19,27,32",
            ),
            DrawHistory(
                issue_no="2026103",
                draw_date=date(2026, 8, 6),
                weekday=4,
                red_1=3, red_2=9, red_3=15, red_4=20, red_5=25, red_6=30,
                blue_1=12,
                red_seq_str="03,09,15,20,25,30",
            ),
        ]
        session.add_all(draws)
        session.commit()

        engine = FeatureEngine(session_factory=Session)

        # 1. First run computes all 3 draws
        computed = engine.compute_all_features(force=False)
        assert computed == 3

        count = session.scalar(select(func.count(FeatureMetrics.issue_no)))
        assert count == 3

        # Verify second draw has repeat_prev_red == 1 (19 repeats)
        fm2 = session.get(FeatureMetrics, "2026102")
        assert fm2.repeat_prev_red == 1

        # 2. Re-run without force should be idempotent and return 0
        recomputed = engine.compute_all_features(force=False)
        assert recomputed == 0
        assert session.scalar(select(func.count(FeatureMetrics.issue_no))) == 3

        # 3. Force recomputation recalculates all 3
        forced = engine.compute_all_features(force=True)
        assert forced == 3
        assert session.scalar(select(func.count(FeatureMetrics.issue_no))) == 3

    def test_compute_latest_features_incremental(self, memory_db_session):
        """Test incremental computation when new draw is added."""
        session, Session = memory_db_session

        # Add initial draw
        d1 = DrawHistory(
            issue_no="2026101",
            draw_date=date(2026, 8, 2),
            weekday=7,
            red_1=2, red_2=7, red_3=14, red_4=19, red_5=24, red_6=31,
            blue_1=8,
            red_seq_str="02,07,14,19,24,31",
        )
        session.add(d1)
        session.commit()

        engine = FeatureEngine(session_factory=Session)
        engine.compute_all_features()

        assert session.scalar(select(func.count(FeatureMetrics.issue_no))) == 1

        # Add second draw
        d2 = DrawHistory(
            issue_no="2026102",
            draw_date=date(2026, 8, 4),
            weekday=2,
            red_1=2, red_2=8, red_3=12, red_4=19, red_5=27, red_6=32,
            blue_1=3,
            red_seq_str="02,08,12,19,27,32",
        )
        session.add(d2)
        session.commit()

        # Incremental sync
        new_computed = engine.compute_latest_features()
        assert new_computed == 1

        fm2 = session.get(FeatureMetrics, "2026102")
        assert fm2 is not None
        # Red 2 and 19 were in draw 1, so repeat count is 2
        assert fm2.repeat_prev_red == 2
        # Prior omission for 2 was 0, for 19 was 0, others were 1 -> missing_sum_red = 0 + 1 + 1 + 0 + 1 + 1 = 4
        assert fm2.missing_sum_red == 4
        # Blue 3 prior omission was 1
        assert fm2.missing_blue == 1


class TestFeatureCLI:
    """Test CLI argument parsing and execution dispatch."""

    def test_cli_parser_compute_features(self):
        """Verify CLI parser handles compute-features subcommand and flags."""
        parser = build_parser()
        args = parser.parse_args(["compute-features"])
        assert args.subcommand == "compute-features"
        assert args.force is False

        args_force = parser.parse_args(["compute-features", "--force"])
        assert args_force.subcommand == "compute-features"
        assert args_force.force is True

    def test_cli_main_compute_features_dispatch(self):
        """Verify main() dispatches compute-features successfully."""
        exit_code = main(["compute-features"])
        assert exit_code == 0


class TestAdversarialM2:
    """Adversarial stress and edge-case testing for Milestone 2 features."""

    def test_invalid_reds_count_and_range_rejected(self):
        """FeatureEngine must reject invalid red ball counts or values."""
        engine = FeatureEngine()
        # Less than 6 reds
        with pytest.raises(ValueError):
            engine.calculate_sum([1, 2, 3, 4, 5])
        with pytest.raises(ValueError):
            engine.calculate_span([1, 2, 3, 4, 5])
        with pytest.raises(ValueError):
            engine.calculate_ac([1, 2, 3, 4, 5])
        with pytest.raises(ValueError):
            engine.calculate_odd_count([1, 2, 3, 4, 5])
        with pytest.raises(ValueError):
            engine.calculate_prime_count([1, 2, 3, 4, 5])
        with pytest.raises(ValueError):
            engine.calculate_zones([1, 2, 3, 4, 5])
        with pytest.raises(ValueError):
            engine.calculate_consecutive_groups([1, 2, 3, 4, 5])

        # Out-of-bounds red in draw
        class DummyDraw:
            issue_no = "2026999"
            reds = [0, 2, 3, 4, 5, 6]
            blue = 5
        with pytest.raises(ValueError, match="out of bounds"):
            engine.compute_metrics_for_draw(DummyDraw())

    def test_invalid_blue_rejected(self):
        """FeatureEngine must reject blue ball outside [1, 16]."""
        engine = FeatureEngine()
        class DummyDrawLow:
            issue_no = "2026999"
            reds = [1, 2, 3, 4, 5, 6]
            blue = 0
        with pytest.raises(ValueError, match="Invalid blue ball"):
            engine.compute_metrics_for_draw(DummyDrawLow())

        class DummyDrawHigh:
            issue_no = "2026999"
            reds = [1, 2, 3, 4, 5, 6]
            blue = 17
        with pytest.raises(ValueError, match="Invalid blue ball"):
            engine.compute_metrics_for_draw(DummyDrawHigh())

    def test_feature_metrics_db_constraints(self):
        """Database CHECK constraints must enforce mathematical bounds."""
        engine_db = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine_db)
        Session = sessionmaker(bind=engine_db)
        session = Session()

        draw = DrawHistory(
            issue_no="2026101",
            draw_date=date(2026, 8, 2),
            weekday=7,
            red_1=2, red_2=7, red_3=14, red_4=19, red_5=24, red_6=31,
            blue_1=8,
            red_seq_str="02,07,14,19,24,31",
        )
        session.add(draw)
        session.commit()

        # 1. Zone sum != 6 violation
        bad_fm_zone = FeatureMetrics(
            issue_no="2026101",
            sum_red=97, span_red=29, ac_value=3, odd_count=3, prime_count=2,
            zone1_count=3, zone2_count=3, zone3_count=1,  # 3+3+1 = 7 != 6
            missing_snapshot_json="{}",
        )
        session.add(bad_fm_zone)
        with pytest.raises(Exception):
            session.commit()
        session.rollback()

        # 2. AC value > 10 violation
        bad_fm_ac = FeatureMetrics(
            issue_no="2026101",
            sum_red=97, span_red=29, ac_value=11, odd_count=3, prime_count=2,
            zone1_count=2, zone2_count=2, zone3_count=2,
            missing_snapshot_json="{}",
        )
        session.add(bad_fm_ac)
        with pytest.raises(Exception):
            session.commit()
        session.rollback()

        session.close()

    def test_cascade_delete_draw_removes_features(self):
        """Deleting DrawHistory must cascade delete the corresponding FeatureMetrics."""
        engine_db = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine_db)
        Session = sessionmaker(bind=engine_db)
        session = Session()

        draw = DrawHistory(
            issue_no="2026101",
            draw_date=date(2026, 8, 2),
            weekday=7,
            red_1=2, red_2=7, red_3=14, red_4=19, red_5=24, red_6=31,
            blue_1=8,
            red_seq_str="02,07,14,19,24,31",
        )
        fm = FeatureEngine().compute_metrics_for_draw(draw)
        draw.feature_metrics = fm
        session.add(draw)
        session.commit()

        assert session.scalar(select(func.count(FeatureMetrics.issue_no))) == 1

        # Delete parent draw
        session.delete(draw)
        session.commit()

        assert session.scalar(select(func.count(FeatureMetrics.issue_no))) == 0
        session.close()

