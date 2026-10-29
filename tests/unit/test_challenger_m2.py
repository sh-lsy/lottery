"""
Challenger 1 Adversarial Test Suite for Milestone 2: Feature Engineering Engine.

This test suite aggressively stress-tests:
1. All 93 Arithmetic Progressions in [1, 33] yielding AC = 0.
2. Maximal spread sets yielding AC = 10.
3. Prime count edge cases: 1 is NOT prime; 2 IS prime; 31 IS prime; 33 is NOT prime.
4. Zone distribution conservation law: z1 + z2 + z3 == 6 invariant under all combinations.
5. Consecutive clusters: [1,2,3,4,5,6] -> 1 cluster, [1,2, 4,5, 7,8] -> 3 clusters, etc.
6. Omission recovery: drawn numbers reset to 0, undrawn increment by 1, initial state is 0.
7. Cold / Warm / Hot classification boundaries (4 -> HOT, 5 -> WARM, 9 -> WARM, 10 -> COLD).
8. Database full history integrity audit across all 3,519 real historical rows.
"""

import json
import random
import pytest
from sqlalchemy import select, func

from backend.app.database import SessionLocal
from backend.app.models import DrawHistory, FeatureMetrics
from backend.app.services.feature_engine import FeatureEngine


class TestArithmeticProgressionsAndAC:
    """Stress test AC value calculation with arithmetic progressions and maximal spread sets."""

    def test_all_93_arithmetic_progressions_yield_ac_zero(self):
        """
        An arithmetic progression of 6 numbers: a, a+d, a+2d, a+3d, a+4d, a+5d
        has pairwise differences that are integer multiples of d: {d, 2d, 3d, 4d, 5d}.
        Because all differences are multiples of d and max multiple is 5, there are
        EXACTLY 5 unique pairwise differences: |D| = 5.
        Therefore: AC = |D| - 5 = 5 - 5 = 0.

        We generate every valid 6-term arithmetic progression in {1..33}.
        """
        ap_count = 0
        for d in range(1, 7):  # step d: max step is (33-1)/5 = 6.4 -> d <= 6
            max_a = 33 - 5 * d
            for a in range(1, max_a + 1):
                ap = [a + i * d for i in range(6)]
                assert len(ap) == 6
                assert ap[-1] <= 33
                ac = FeatureEngine.calculate_ac(ap)
                assert ac == 0, f"AP {ap} with step {d} failed: AC={ac} != 0"
                ap_count += 1

        assert ap_count == 93, f"Expected 93 arithmetic progressions, found {ap_count}"

    def test_maximal_spread_sets_yield_ac_ten(self):
        """
        Maximal spread sets have all 15 pairwise differences distinct: |D| = 15.
        Therefore: AC = 15 - 5 = 10.
        """
        # Powers of 2: differences are {1, 2, 4, 8, 16, 3, 6, 12, 24, 7, 14, 28, 15, 30, 31} -> 15 distinct
        pow_two = [1, 2, 4, 8, 16, 32]
        assert FeatureEngine.calculate_ac(pow_two) == 10

        # Additional maximal spread sets with 15 unique differences
        max_spread_1 = [1, 2, 4, 8, 13, 21]
        diffs_1 = {abs(max_spread_1[i] - max_spread_1[j]) for i in range(6) for j in range(i + 1, 6)}
        assert len(diffs_1) == 15
        assert FeatureEngine.calculate_ac(max_spread_1) == 10

        # Real historical draw from issue 2003006: [1, 3, 10, 21, 26, 27]
        max_spread_hist = [1, 3, 10, 21, 26, 27]
        diffs_hist = {abs(max_spread_hist[i] - max_spread_hist[j]) for i in range(6) for j in range(i + 1, 6)}
        assert len(diffs_hist) == 15
        assert FeatureEngine.calculate_ac(max_spread_hist) == 10

    def test_ac_value_bounds_and_permutations(self):
        """AC value must always lie in [0, 10] regardless of input sorting."""
        sample = [14, 2, 31, 7, 24, 19]  # unsorted
        ac = FeatureEngine.calculate_ac(sample)
        assert 0 <= ac <= 10
        assert ac == FeatureEngine.calculate_ac(sorted(sample))


class TestPrimeCountEdgeCases:
    """Stress test prime number classification with boundary numbers and edge cases."""

    def test_prime_edge_cases_1_2_31_33(self):
        """
        Test the 4 critical edge cases:
        - 1 is NOT prime
        - 2 IS prime
        - 31 IS prime (largest prime <= 33)
        - 33 is NOT prime (composite: 3 * 11)
        """
        primes = FeatureEngine.SSQ_PRIMES

        assert 1 not in primes, "1 must NOT be considered prime"
        assert 2 in primes, "2 MUST be considered prime"
        assert 31 in primes, "31 MUST be considered prime"
        assert 33 not in primes, "33 must NOT be considered prime"

    def test_all_numbers_1_to_33_prime_classification(self):
        """Check all numbers 1..33 against mathematical primality."""
        def is_prime(n: int) -> bool:
            if n < 2:
                return False
            for i in range(2, int(n ** 0.5) + 1):
                if n % i == 0:
                    return False
            return True

        math_primes = {n for n in range(1, 34) if is_prime(n)}
        assert FeatureEngine.SSQ_PRIMES == math_primes
        assert len(FeatureEngine.SSQ_PRIMES) == 11

    def test_prime_count_draw_combinations(self):
        """Test prime count in diverse draw combinations."""
        # Combination containing 1, 2, 31, 33 and composites 4, 6
        combo = [1, 2, 4, 6, 31, 33]
        # Only 2 and 31 are prime
        assert FeatureEngine.calculate_prime_count(combo) == 2

        # All composite + 1
        all_non_prime = [1, 9, 15, 21, 25, 33]
        assert FeatureEngine.calculate_prime_count(all_non_prime) == 0

        # Maximum primes: 6 primes
        all_primes = [2, 3, 5, 7, 11, 13]
        assert FeatureEngine.calculate_prime_count(all_primes) == 6


class TestZoneDistributionConservation:
    """Stress test 3-zone distribution and conservation law."""

    def test_zone_definitions_and_boundaries(self):
        """
        Zone 1: 01-11 (11 numbers)
        Zone 2: 12-22 (11 numbers)
        Zone 3: 23-33 (11 numbers)
        Boundary values: 11, 12, 22, 23.
        """
        # Boundary numbers combo: 10, 11 (Z1), 12, 22 (Z2), 23, 24 (Z3)
        reds = [10, 11, 12, 22, 23, 24]
        z1, z2, z3 = FeatureEngine.calculate_zones(reds)
        assert z1 == 2
        assert z2 == 2
        assert z3 == 2
        assert z1 + z2 + z3 == 6

    def test_zone_conservation_across_5000_random_draws(self):
        """Zone sum conservation invariant z1 + z2 + z3 == 6 across 5,000 random valid draws."""
        rng = random.Random(42)
        for _ in range(5000):
            combo = sorted(rng.sample(range(1, 34), 6))
            z1, z2, z3 = FeatureEngine.calculate_zones(combo)
            assert z1 + z2 + z3 == 6
            assert 0 <= z1 <= 6
            assert 0 <= z2 <= 6
            assert 0 <= z3 <= 6


class TestConsecutiveClusters:
    """Stress test consecutive numbers clustering (connected components)."""

    def test_consecutive_clusters_required_cases(self):
        """
        Verify:
        - [1,2,3,4,5,6] -> 1 cluster
        - [1,2, 4,5, 7,8] -> 3 clusters
        """
        # [1,2,3,4,5,6] is a single connected run of length 6
        assert FeatureEngine.calculate_consecutive_groups([1, 2, 3, 4, 5, 6]) == 1

        # [1,2, 4,5, 7,8] is three disjoint 2-number runs
        assert FeatureEngine.calculate_consecutive_groups([1, 2, 4, 5, 7, 8]) == 3

    def test_consecutive_clusters_edge_cases(self):
        """Test all cluster configurations from 0 to 3."""
        # 0 clusters: no two adjacent numbers differ by 1
        assert FeatureEngine.calculate_consecutive_groups([1, 3, 5, 7, 9, 11]) == 0
        assert FeatureEngine.calculate_consecutive_groups([2, 5, 9, 14, 20, 27]) == 0

        # 1 cluster (2-chain)
        assert FeatureEngine.calculate_consecutive_groups([1, 2, 5, 9, 14, 20]) == 1

        # 1 cluster (3-chain)
        assert FeatureEngine.calculate_consecutive_groups([1, 2, 3, 7, 12, 18]) == 1

        # 1 cluster (4-chain)
        assert FeatureEngine.calculate_consecutive_groups([1, 2, 3, 4, 8, 15]) == 1

        # 1 cluster (5-chain)
        assert FeatureEngine.calculate_consecutive_groups([1, 2, 3, 4, 5, 9]) == 1

        # 2 clusters (two 2-chains)
        assert FeatureEngine.calculate_consecutive_groups([1, 2, 5, 6, 10, 15]) == 2

        # 2 clusters (one 3-chain, one 2-chain)
        assert FeatureEngine.calculate_consecutive_groups([1, 2, 3, 10, 11, 20]) == 2

        # 2 clusters (two 3-chains)
        assert FeatureEngine.calculate_consecutive_groups([1, 2, 3, 10, 11, 12]) == 2

        # Unsorted input handling
        assert FeatureEngine.calculate_consecutive_groups([8, 7, 5, 4, 2, 1]) == 3


class TestOmissionTrackingAndRecovery:
    """Stress test dynamic omission state machine and recovery to 0."""

    def test_drawn_number_omission_resets_to_zero(self):
        """When a number is drawn, its omission resets to 0."""
        reds, blues = FeatureEngine.get_initial_omission_state()
        assert all(v == 0 for v in reds.values())
        assert all(v == 0 for v in blues.values())

        # Draw 1: draw red 5, blue 7
        new_reds, new_blues, _ = FeatureEngine.update_omissions(reds, blues, [5, 10, 15, 20, 25, 30], 7)
        assert new_reds[5] == 0
        assert new_blues[7] == 0

        # Draw 2: red 5 not drawn -> becomes 1
        new_reds, new_blues, _ = FeatureEngine.update_omissions(new_reds, new_blues, [1, 2, 3, 4, 6, 8], 2)
        assert new_reds[5] == 1
        assert new_blues[7] == 1

        # Draw 3: red 5 not drawn -> becomes 2
        new_reds, new_blues, _ = FeatureEngine.update_omissions(new_reds, new_blues, [1, 2, 3, 4, 6, 8], 2)
        assert new_reds[5] == 2
        assert new_blues[7] == 2

        # Draw 4: red 5 DRAWN AGAIN -> resets to 0!
        new_reds, new_blues, _ = FeatureEngine.update_omissions(new_reds, new_blues, [5, 12, 14, 18, 22, 29], 7)
        assert new_reds[5] == 0, "Drawn red number must reset to 0"
        assert new_blues[7] == 0, "Drawn blue number must reset to 0"

    def test_missing_sum_red_and_missing_blue_semantics(self):
        """
        Verify that missing_sum_red is the sum of PRIOR omissions of drawn reds,
        and missing_blue is the PRIOR omission of the drawn blue.
        """
        engine = FeatureEngine()

        # Prior snapshot with specific omissions
        prior_snapshot = {
            "red": {str(b): b for b in range(1, 34)},  # omission = number itself
            "blue": {str(b): b * 2 for b in range(1, 17)},
        }

        class MockDraw:
            issue_no = "2026100"
            red_1, red_2, red_3, red_4, red_5, red_6 = 1, 2, 3, 4, 5, 6
            blue_1 = 8

        fm = engine.compute_metrics_for_draw(MockDraw(), prior_snapshot=prior_snapshot)
        # missing_sum_red should be 1 + 2 + 3 + 4 + 5 + 6 = 21
        assert fm.missing_sum_red == 21
        # missing_blue should be 8 * 2 = 16
        assert fm.missing_blue == 16


class TestColdWarmHotBoundaries:
    """Stress test Cold / Warm / Hot classification thresholds."""

    def test_classification_exact_boundaries(self):
        """
        HOT:  m <= 4  (0, 1, 2, 3, 4)
        WARM: 5 <= m <= 9 (5, 6, 7, 8, 9)
        COLD: m >= 10 (10, 11, ...)
        """
        # HOT boundaries
        assert FeatureEngine.classify_omission(0) == "HOT"
        assert FeatureEngine.classify_omission(1) == "HOT"
        assert FeatureEngine.classify_omission(2) == "HOT"
        assert FeatureEngine.classify_omission(3) == "HOT"
        assert FeatureEngine.classify_omission(4) == "HOT"

        # WARM boundaries
        assert FeatureEngine.classify_omission(5) == "WARM"
        assert FeatureEngine.classify_omission(6) == "WARM"
        assert FeatureEngine.classify_omission(7) == "WARM"
        assert FeatureEngine.classify_omission(8) == "WARM"
        assert FeatureEngine.classify_omission(9) == "WARM"

        # COLD boundaries
        assert FeatureEngine.classify_omission(10) == "COLD"
        assert FeatureEngine.classify_omission(11) == "COLD"
        assert FeatureEngine.classify_omission(50) == "COLD"
        assert FeatureEngine.classify_omission(200) == "COLD"

    def test_negative_omission_rejected(self):
        """Negative omission must raise ValueError."""
        with pytest.raises(ValueError):
            FeatureEngine.classify_omission(-1)
        with pytest.raises(ValueError):
            FeatureEngine.classify_omission(-100)


class TestFullHistoricalIntegrityAudit:
    """Audit all 3,519 actual rows in ssq_feature_metrics from SQLite database."""

    def test_all_3519_rows_satisfy_all_invariants(self):
        """
        Verify every single row in ssq_feature_metrics satisfies:
        1. 21 <= sum_red <= 183
        2. 5 <= span_red <= 32
        3. 0 <= ac_value <= 10
        4. 0 <= odd_count <= 6
        5. 0 <= prime_count <= 6
        6. zone1_count + zone2_count + zone3_count == 6
        7. 0 <= consecutive_groups <= 3
        8. 0 <= repeat_prev_red <= 6
        9. missing_sum_red >= 0
        10. missing_blue >= 0
        11. Snapshot schema: exactly 33 red keys and 16 blue keys
        12. Drawn numbers in that issue have omission 0 in snapshot!
        """
        with SessionLocal() as session:
            total_features = session.scalar(select(func.count(FeatureMetrics.issue_no)))
            total_draws = session.scalar(select(func.count(DrawHistory.id)))
            assert total_features >= 3519, f"Expected 3519 feature rows, found {total_features}"
            assert total_draws >= 3519, f"Expected 3519 draw rows, found {total_draws}"

            # Join DrawHistory and FeatureMetrics to cross-verify
            query = (
                select(DrawHistory, FeatureMetrics)
                .join(FeatureMetrics, DrawHistory.issue_no == FeatureMetrics.issue_no)
                .order_by(DrawHistory.issue_no.asc())
            )
            rows = session.execute(query).all()
            assert len(rows) >= 3519

            prev_snapshot = None
            for draw, fm in rows:
                reds = [draw.red_1, draw.red_2, draw.red_3, draw.red_4, draw.red_5, draw.red_6]
                blue = draw.blue_1

                # Invariant checks
                assert 21 <= fm.sum_red <= 183
                assert 5 <= fm.span_red <= 32
                assert 0 <= fm.ac_value <= 10
                assert 0 <= fm.odd_count <= 6
                assert 0 <= fm.prime_count <= 6
                assert fm.zone1_count + fm.zone2_count + fm.zone3_count == 6
                assert 0 <= fm.consecutive_groups <= 3
                assert 0 <= fm.repeat_prev_red <= 6
                assert fm.missing_sum_red >= 0
                assert fm.missing_blue >= 0

                # Snapshot schema
                snap = fm.missing_snapshot
                assert "red" in snap and "blue" in snap
                assert len(snap["red"]) == 33
                assert len(snap["blue"]) == 16

                # Drawn numbers MUST reset to 0 in post-draw snapshot
                for r in reds:
                    assert snap["red"][str(r)] == 0, f"Drawn red {r} not 0 in issue {fm.issue_no}"
                assert snap["blue"][str(blue)] == 0, f"Drawn blue {blue} not 0 in issue {fm.issue_no}"

                # Cross-check step increment from prior snapshot if available
                if prev_snapshot is not None:
                    for b in range(1, 34):
                        if b in reds:
                            assert snap["red"][str(b)] == 0
                        else:
                            assert snap["red"][str(b)] == prev_snapshot["red"][str(b)] + 1

                    for b in range(1, 17):
                        if b == blue:
                            assert snap["blue"][str(b)] == 0
                        else:
                            assert snap["blue"][str(b)] == prev_snapshot["blue"][str(b)] + 1

                prev_snapshot = snap


class TestAdversarialInputValidationAndExceptions:
    """Aggressively stress test input edge cases, malformed data, and exception behavior."""

    def test_reds_length_validation(self):
        """All red-ball functions must strictly reject len != 6."""
        for invalid_len in [0, 1, 5, 7, 10]:
            invalid_reds = list(range(1, invalid_len + 1))
            with pytest.raises(ValueError):
                FeatureEngine.calculate_sum(invalid_reds)
            with pytest.raises(ValueError):
                FeatureEngine.calculate_span(invalid_reds)
            with pytest.raises(ValueError):
                FeatureEngine.calculate_ac(invalid_reds)
            with pytest.raises(ValueError):
                FeatureEngine.calculate_odd_count(invalid_reds)
            with pytest.raises(ValueError):
                FeatureEngine.calculate_prime_count(invalid_reds)
            with pytest.raises(ValueError):
                FeatureEngine.calculate_zones(invalid_reds)
            with pytest.raises(ValueError):
                FeatureEngine.calculate_consecutive_groups(invalid_reds)

    def test_reds_duplicate_validation(self):
        """calculate_ac must strictly reject duplicate red balls."""
        with pytest.raises(ValueError, match="distinct"):
            FeatureEngine.calculate_ac([1, 1, 2, 3, 4, 5])
        with pytest.raises(ValueError, match="distinct"):
            FeatureEngine.calculate_ac([10, 12, 14, 16, 18, 18])

    def test_draw_out_of_bounds_validation(self):
        """compute_metrics_for_draw must reject out-of-bounds reds or blues."""
        engine = FeatureEngine()

        class DummyDraw:
            issue_no = "2026999"
            red_1, red_2, red_3, red_4, red_5, red_6 = 1, 2, 3, 4, 5, 34  # 34 is invalid
            blue_1 = 10

        with pytest.raises(ValueError, match="out of bounds"):
            engine.compute_metrics_for_draw(DummyDraw())

        class DummyDrawZeroRed:
            issue_no = "2026999"
            red_1, red_2, red_3, red_4, red_5, red_6 = 0, 2, 3, 4, 5, 6  # 0 is invalid
            blue_1 = 10

        with pytest.raises(ValueError, match="out of bounds"):
            engine.compute_metrics_for_draw(DummyDrawZeroRed())

        class DummyDrawBlueZero:
            issue_no = "2026999"
            red_1, red_2, red_3, red_4, red_5, red_6 = 1, 2, 3, 4, 5, 6
            blue_1 = 0  # 0 is invalid

        with pytest.raises(ValueError, match="Invalid blue"):
            engine.compute_metrics_for_draw(DummyDrawBlueZero())

        class DummyDrawBlueSeventeen:
            issue_no = "2026999"
            red_1, red_2, red_3, red_4, red_5, red_6 = 1, 2, 3, 4, 5, 6
            blue_1 = 17  # 17 is invalid

        with pytest.raises(ValueError, match="Invalid blue"):
            engine.compute_metrics_for_draw(DummyDrawBlueSeventeen())

    def test_parse_omission_snapshot_fallbacks(self):
        """parse_omission_snapshot should handle None, empty dict, or integer/string keys."""
        # None snapshot -> initial state
        r1, b1 = FeatureEngine.parse_omission_snapshot(None)
        assert len(r1) == 33 and len(b1) == 16
        assert all(v == 0 for v in r1.values())

        # Empty snapshot -> initial state
        r2, b2 = FeatureEngine.parse_omission_snapshot({})
        assert len(r2) == 33 and len(b2) == 16
        assert all(v == 0 for v in r2.values())

        # Snapshot with integer keys
        snap_int = {"red": {1: 5, 2: 10}, "blue": {1: 3}}
        r3, b3 = FeatureEngine.parse_omission_snapshot(snap_int)
        assert r3[1] == 5 and r3[2] == 10 and r3[3] == 0
        assert b3[1] == 3 and b3[2] == 0


class TestPerformanceStress:
    """Stress test execution speed and O(1) complexity per draw."""

    def test_10000_in_memory_draw_computations(self):
        """Benchmark 10,000 draws computed through FeatureEngine in-memory."""
        import time
        engine = FeatureEngine()
        rng = random.Random(1337)

        class SyntheticDraw:
            def __init__(self, issue: int, reds: list, blue: int):
                self.issue_no = str(issue)
                self.red_1, self.red_2, self.red_3, self.red_4, self.red_5, self.red_6 = reds
                self.blue_1 = blue

        start_time = time.perf_counter()
        prior_draw = None
        prior_snap = None
        for i in range(10000):
            reds = sorted(rng.sample(range(1, 34), 6))
            blue = rng.randint(1, 16)
            draw = SyntheticDraw(2000000 + i, reds, blue)
            fm = engine.compute_metrics_for_draw(draw, prev_draw=prior_draw, prior_snapshot=prior_snap)
            prior_draw = draw
            prior_snap = fm.missing_snapshot

        elapsed = time.perf_counter() - start_time
        # 10,000 draws should compute in under 3.0 seconds (i.e. < 0.3ms per draw)
        assert elapsed < 3.0, f"10,000 draw computations took {elapsed:.2f}s, expected < 3.0s"

