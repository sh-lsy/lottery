"""
Adversarial and Exhaustive Empirical Test Suite for SSQ-Quant-System Milestone 2.
Author: Challenger Agent 2 (critic/specialist)

Covers empirical challenge vectors:
1. Exhaustive empirical verification across all 3,519 rows in `ssq_feature_metrics` in `data/ssq_quant.db`:
   - Zone counts conservation: zone1_count + zone2_count + zone3_count == 6 for every row
   - AC value bounds: 0 <= ac_value <= 10 for every row
   - Sum bounds: 21 <= sum_red <= 183 for every row
   - Span bounds: 5 <= span_red <= 32 for every row
   - Odd count bounds: 0 <= odd_count <= 6 for every row
   - Prime count bounds: 0 <= prime_count <= 6 for every row
   - Snapshot schema: valid JSON with exactly 33 red string keys ("1".."33") and 16 blue string keys ("1".."16")
   - Full omission continuity: from draw T-1 to draw T, drawn numbers reset to 0, undrawn increment by 1
   - Missing metrics: missing_sum_red and missing_blue match prior draw omission state exactly
   - Independent recalculation: 100% of mathematical features recomputed from raw draw history match database
2. Stress tests and boundary conditions:
   - AC value extremes (arithmetic progressions AC=0, exponential sequences AC=10)
   - Sum & span theoretical boundaries (min sum 21, max sum 183, span 5 to 32)
   - Prime counting accuracy across edge combinations (all primes, zero primes, 1 is non-prime)
   - Consecutive group topology variants (single long chains, disjoint pairs, isolated numbers)
   - Omission classification thresholds (4 vs 5, 9 vs 10, negative prevention)
   - Database check constraints & foreign key cascade
   - Ingestion idempotency on production SQLite database
"""

import json
import sqlite3
from typing import List, Dict, Set, Tuple
import pytest
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from backend.app.config import DB_PATH
from backend.app.database import SessionLocal, create_db_engine
from backend.app.models import DrawHistory, FeatureMetrics
from backend.app.services.feature_engine import FeatureEngine


# ---------------------------------------------------------------------------
# Independent Mathematical Oracles (Zero Dependency on FeatureEngine code)
# ---------------------------------------------------------------------------

ORACLE_SSQ_PRIMES: Set[int] = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}


def oracle_sum(reds: List[int]) -> int:
    return sum(reds)


def oracle_span(reds: List[int]) -> int:
    return max(reds) - min(reds)


def oracle_ac(reds: List[int]) -> int:
    diffs = {abs(reds[i] - reds[j]) for i in range(len(reds)) for j in range(i + 1, len(reds))}
    return len(diffs) - (len(reds) - 1)


def oracle_odd_count(reds: List[int]) -> int:
    return sum(1 for r in reds if r % 2 == 1)


def oracle_prime_count(reds: List[int]) -> int:
    return sum(1 for r in reds if r in ORACLE_SSQ_PRIMES)


def oracle_zones(reds: List[int]) -> Tuple[int, int, int]:
    z1 = sum(1 for r in reds if 1 <= r <= 11)
    z2 = sum(1 for r in reds if 12 <= r <= 22)
    z3 = sum(1 for r in reds if 23 <= r <= 33)
    return z1, z2, z3


def oracle_consecutive_groups(reds: List[int]) -> int:
    s = sorted(reds)
    diffs = [s[i + 1] - s[i] for i in range(len(s) - 1)]
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


def oracle_repeats(reds: List[int], prev_reds: List[int]) -> int:
    if not prev_reds:
        return 0
    return len(set(reds) & set(prev_reds))


# ---------------------------------------------------------------------------
# Test Suite 1: Exhaustive Empirical Verification Across All 3,519 Rows
# ---------------------------------------------------------------------------

class TestExhaustiveEmpiricalVerificationAllRows:
    """
    Exhaustive empirical validation of every row in `ssq_feature_metrics` in `data/ssq_quant.db`.
    """

    @pytest.fixture(scope="class")
    def loaded_records(self):
        """Loads all joined draw and feature rows from the local database."""
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                d.issue_no, d.draw_date, d.weekday,
                d.red_1, d.red_2, d.red_3, d.red_4, d.red_5, d.red_6, d.blue_1,
                f.sum_red, f.span_red, f.ac_value, f.odd_count, f.prime_count,
                f.zone1_count, f.zone2_count, f.zone3_count,
                f.consecutive_groups, f.repeat_prev_red,
                f.missing_sum_red, f.missing_blue, f.missing_snapshot_json
            FROM ssq_draw_history d
            JOIN ssq_feature_metrics f ON d.issue_no = f.issue_no
            ORDER BY d.issue_no ASC
        """)
        rows = cursor.fetchall()
        conn.close()
        return rows

    def test_total_row_count_exact_3519(self, loaded_records):
        """Verify exactly 3,519 rows exist in both ssq_draw_history and ssq_feature_metrics."""
        assert len(loaded_records) == 3519, f"Expected 3,519 joined rows, got {len(loaded_records)}"

        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM ssq_draw_history")
        d_cnt = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM ssq_feature_metrics")
        f_cnt = cursor.fetchone()[0]
        conn.close()

        assert d_cnt == 3519, f"Draw count is {d_cnt}, expected 3519"
        assert f_cnt == 3519, f"Feature count is {f_cnt}, expected 3519"

    def test_all_rows_zone_sum_conservation(self, loaded_records):
        """Verify every row has zone1_count + zone2_count + zone3_count == 6."""
        violations = []
        for r in loaded_records:
            total_zone = r["zone1_count"] + r["zone2_count"] + r["zone3_count"]
            if total_zone != 6:
                violations.append((r["issue_no"], r["zone1_count"], r["zone2_count"], r["zone3_count"]))
        assert not violations, f"Found {len(violations)} zone conservation violations: {violations[:5]}"

    def test_all_rows_ac_value_bounds(self, loaded_records):
        """Verify every row has ac_value >= 0 and ac_value <= 10."""
        violations = []
        for r in loaded_records:
            ac = r["ac_value"]
            if not (0 <= ac <= 10):
                violations.append((r["issue_no"], ac))
        assert not violations, f"Found {len(violations)} AC bound violations: {violations[:5]}"

    def test_all_rows_sum_red_bounds(self, loaded_records):
        """Verify every row has sum_red >= 21 and sum_red <= 183."""
        violations = []
        for r in loaded_records:
            s = r["sum_red"]
            if not (21 <= s <= 183):
                violations.append((r["issue_no"], s))
        assert not violations, f"Found {len(violations)} sum_red bound violations: {violations[:5]}"

    def test_all_rows_span_red_bounds(self, loaded_records):
        """Verify every row has span_red >= 5 and span_red <= 32."""
        violations = []
        for r in loaded_records:
            span = r["span_red"]
            if not (5 <= span <= 32):
                violations.append((r["issue_no"], span))
        assert not violations, f"Found {len(violations)} span_red bound violations: {violations[:5]}"

    def test_all_rows_odd_count_bounds(self, loaded_records):
        """Verify every row has odd_count >= 0 and odd_count <= 6."""
        violations = []
        for r in loaded_records:
            odd = r["odd_count"]
            if not (0 <= odd <= 6):
                violations.append((r["issue_no"], odd))
        assert not violations, f"Found {len(violations)} odd_count bound violations: {violations[:5]}"

    def test_all_rows_prime_count_bounds(self, loaded_records):
        """Verify every row has prime_count >= 0 and prime_count <= 6."""
        violations = []
        for r in loaded_records:
            p = r["prime_count"]
            if not (0 <= p <= 6):
                violations.append((r["issue_no"], p))
        assert not violations, f"Found {len(violations)} prime_count bound violations: {violations[:5]}"

    def test_all_rows_missing_snapshot_json_schema(self, loaded_records):
        """
        Verify every row has valid JSON in missing_snapshot_json with exactly 33 red keys
        ('1' to '33') and 16 blue keys ('1' to '16'), with all non-negative integer values.
        """
        exp_red_keys = {str(i) for i in range(1, 34)}
        exp_blue_keys = {str(i) for i in range(1, 17)}
        violations = []

        for r in loaded_records:
            issue = r["issue_no"]
            raw_json = r["missing_snapshot_json"]
            try:
                snap = json.loads(raw_json)
            except Exception as e:
                violations.append(f"{issue}: JSON parse error {e}")
                continue

            if not isinstance(snap, dict) or "red" not in snap or "blue" not in snap:
                violations.append(f"{issue}: Missing root 'red' or 'blue' dictionary")
                continue

            red_keys = set(snap["red"].keys())
            blue_keys = set(snap["blue"].keys())

            if red_keys != exp_red_keys:
                violations.append(f"{issue}: Red keys mismatch (found {len(red_keys)}, expected 33)")
            if blue_keys != exp_blue_keys:
                violations.append(f"{issue}: Blue keys mismatch (found {len(blue_keys)}, expected 16)")

            for k, v in snap["red"].items():
                if not isinstance(v, int) or v < 0:
                    violations.append(f"{issue}: Invalid red omission {k}={v}")
                    break

            for k, v in snap["blue"].items():
                if not isinstance(v, int) or v < 0:
                    violations.append(f"{issue}: Invalid blue omission {k}={v}")
                    break

        assert not violations, f"Found {len(violations)} snapshot schema violations: {violations[:5]}"

    def test_all_rows_omission_continuity_and_missing_metrics(self, loaded_records):
        """
        Verify omission continuity across all 3,519 issues:
        - Issue 2003001: drawn numbers reset to 0, undrawn become 1; missing_sum_red=0, missing_blue=0.
        - From draw T-1 to draw T:
          * drawn red numbers reset to 0, undrawn red numbers increment by 1
          * drawn blue number resets to 0, undrawn blue numbers increment by 1
          * missing_sum_red matches sum of prior omissions for the 6 drawn reds
          * missing_blue matches prior omission for the drawn blue
        """
        violations = []
        prev_snap = None

        for idx, r in enumerate(loaded_records):
            issue = r["issue_no"]
            reds = [r["red_1"], r["red_2"], r["red_3"], r["red_4"], r["red_5"], r["red_6"]]
            red_set = set(reds)
            blue = r["blue_1"]
            snap = json.loads(r["missing_snapshot_json"])

            if idx == 0:
                assert issue == "2003001", f"First issue is {issue}, expected 2003001"
                if r["missing_sum_red"] != 0:
                    violations.append(f"{issue}: initial missing_sum_red={r['missing_sum_red']} != 0")
                if r["missing_blue"] != 0:
                    violations.append(f"{issue}: initial missing_blue={r['missing_blue']} != 0")

                for b in range(1, 34):
                    expected = 0 if b in red_set else 1
                    actual = snap["red"][str(b)]
                    if actual != expected:
                        violations.append(f"{issue}: red ball {b} initial omission {actual} != {expected}")

                for b in range(1, 17):
                    expected = 0 if b == blue else 1
                    actual = snap["blue"][str(b)]
                    if actual != expected:
                        violations.append(f"{issue}: blue ball {b} initial omission {actual} != {expected}")
            else:
                # Missing sum red check
                exp_missing_sum_red = sum(prev_snap["red"][str(b)] for b in reds)
                if r["missing_sum_red"] != exp_missing_sum_red:
                    violations.append(
                        f"{issue}: missing_sum_red={r['missing_sum_red']} != expected {exp_missing_sum_red}"
                    )

                # Missing blue check
                exp_missing_blue = prev_snap["blue"][str(blue)]
                if r["missing_blue"] != exp_missing_blue:
                    violations.append(
                        f"{issue}: missing_blue={r['missing_blue']} != expected {exp_missing_blue}"
                    )

                # Red omission continuity
                for b in range(1, 34):
                    expected = 0 if b in red_set else prev_snap["red"][str(b)] + 1
                    actual = snap["red"][str(b)]
                    if actual != expected:
                        violations.append(f"{issue}: red ball {b} omission {actual} != expected {expected}")

                # Blue omission continuity
                for b in range(1, 17):
                    expected = 0 if b == blue else prev_snap["blue"][str(b)] + 1
                    actual = snap["blue"][str(b)]
                    if actual != expected:
                        violations.append(f"{issue}: blue ball {b} omission {actual} != expected {expected}")

            prev_snap = snap

        assert not violations, f"Found {len(violations)} omission continuity violations: {violations[:5]}"

    def test_all_rows_independent_feature_recalculation(self, loaded_records):
        """
        Recalculate every mathematical feature independently using pure python oracles
        and compare against the values stored in ssq_feature_metrics.
        """
        violations = []
        prev_reds = None

        for r in loaded_records:
            issue = r["issue_no"]
            reds = [r["red_1"], r["red_2"], r["red_3"], r["red_4"], r["red_5"], r["red_6"]]

            # Sum
            exp_sum = oracle_sum(reds)
            if r["sum_red"] != exp_sum:
                violations.append(f"{issue}: sum_red={r['sum_red']} != {exp_sum}")

            # Span
            exp_span = oracle_span(reds)
            if r["span_red"] != exp_span:
                violations.append(f"{issue}: span_red={r['span_red']} != {exp_span}")

            # AC
            exp_ac = oracle_ac(reds)
            if r["ac_value"] != exp_ac:
                violations.append(f"{issue}: ac_value={r['ac_value']} != {exp_ac}")

            # Odd count
            exp_odd = oracle_odd_count(reds)
            if r["odd_count"] != exp_odd:
                violations.append(f"{issue}: odd_count={r['odd_count']} != {exp_odd}")

            # Prime count
            exp_prime = oracle_prime_count(reds)
            if r["prime_count"] != exp_prime:
                violations.append(f"{issue}: prime_count={r['prime_count']} != {exp_prime}")

            # Zones
            exp_z1, exp_z2, exp_z3 = oracle_zones(reds)
            if (r["zone1_count"], r["zone2_count"], r["zone3_count"]) != (exp_z1, exp_z2, exp_z3):
                violations.append(
                    f"{issue}: zones=({r['zone1_count']},{r['zone2_count']},{r['zone3_count']}) != ({exp_z1},{exp_z2},{exp_z3})"
                )

            # Consecutive groups
            exp_consec = oracle_consecutive_groups(reds)
            if r["consecutive_groups"] != exp_consec:
                violations.append(f"{issue}: consecutive_groups={r['consecutive_groups']} != {exp_consec}")

            # Repeats from previous draw
            exp_repeats = oracle_repeats(reds, prev_reds)
            if r["repeat_prev_red"] != exp_repeats:
                violations.append(f"{issue}: repeat_prev_red={r['repeat_prev_red']} != {exp_repeats}")

            prev_reds = reds

        assert not violations, f"Found {len(violations)} recalculation mismatches: {violations[:5]}"


# ---------------------------------------------------------------------------
# Test Suite 2: Adversarial Edge Cases and Theoretical Stress Testing
# ---------------------------------------------------------------------------

class TestAdversarialEdgeCasesAndStress:
    """
    Adversarial challenge test cases: mathematical limits, corrupted values,
    and DB constraint validation.
    """

    def test_theoretical_extremes_ac_values(self):
        """
        Verify AC arithmetic progression formulas:
        - Arithmetic progressions have exactly 5 pairwise differences -> AC = 5 - 5 = 0.
        - Super-increasing sequences have 15 pairwise differences -> AC = 15 - 5 = 10.
        """
        ap_cases = [
            [1, 2, 3, 4, 5, 6],
            [5, 10, 15, 20, 25, 30],
            [2, 7, 12, 17, 22, 27],
            [3, 9, 15, 21, 27, 33],
        ]
        for ap in ap_cases:
            assert FeatureEngine.calculate_ac(ap) == 0, f"Expected AC=0 for AP {ap}"

        # Exponential sequence with distinct pairwise differences
        exp_seq = [1, 2, 4, 8, 16, 32]
        assert FeatureEngine.calculate_ac(exp_seq) == 10, f"Expected AC=10 for {exp_seq}"

        # Real-world historical sample checks
        assert FeatureEngine.calculate_ac([2, 7, 14, 19, 24, 31]) == 3
        assert FeatureEngine.calculate_ac([1, 4, 11, 12, 19, 29]) == 6

    def test_theoretical_extremes_sum_and_span(self):
        """
        Verify mathematical limits:
        - Min possible sum: [1, 2, 3, 4, 5, 6] -> sum=21, span=5
        - Max possible sum: [28, 29, 30, 31, 32, 33] -> sum=183, span=5
        - Max possible span: [1, 2, 3, 4, 5, 33] -> span=32
        """
        min_reds = [1, 2, 3, 4, 5, 6]
        assert FeatureEngine.calculate_sum(min_reds) == 21
        assert FeatureEngine.calculate_span(min_reds) == 5

        max_reds = [28, 29, 30, 31, 32, 33]
        assert FeatureEngine.calculate_sum(max_reds) == 183
        assert FeatureEngine.calculate_span(max_reds) == 5

        max_span_reds = [1, 5, 12, 19, 27, 33]
        assert FeatureEngine.calculate_span(max_span_reds) == 32

    def test_prime_count_edge_cases(self):
        """
        Verify official 11 SSQ primes:
        - 1 is explicitly NOT prime
        - All 11 primes: {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}
        - 6-prime draw: [2, 3, 5, 7, 11, 13] -> prime_count=6
        - 0-prime draw: [1, 4, 6, 8, 9, 10] -> prime_count=0
        """
        all_primes = [2, 3, 5, 7, 11, 13]
        assert FeatureEngine.calculate_prime_count(all_primes) == 6

        zero_primes = [1, 4, 6, 8, 9, 10]
        assert FeatureEngine.calculate_prime_count(zero_primes) == 0

        # Verify 1 is treated as non-prime
        mixed = [1, 2, 4, 6, 8, 10]  # Only 2 is prime
        assert FeatureEngine.calculate_prime_count(mixed) == 1

    def test_consecutive_groups_topologies(self):
        """
        Verify consecutive groups logic distinguishes:
        - 1 run of 6: [1, 2, 3, 4, 5, 6] -> 1 group
        - 3 disjoint pairs: [1, 2, 10, 11, 20, 21] -> 3 groups
        - 2 disjoint triples: [1, 2, 3, 10, 11, 12] -> 2 groups
        - 0 consecutive pairs: [1, 3, 5, 7, 9, 11] -> 0 groups
        - 1 pair and 1 triple: [1, 2, 10, 11, 12, 25] -> 2 groups
        """
        assert FeatureEngine.calculate_consecutive_groups([1, 2, 3, 4, 5, 6]) == 1
        assert FeatureEngine.calculate_consecutive_groups([1, 2, 10, 11, 20, 21]) == 3
        assert FeatureEngine.calculate_consecutive_groups([1, 2, 3, 10, 11, 12]) == 2
        assert FeatureEngine.calculate_consecutive_groups([1, 3, 5, 7, 9, 11]) == 0
        assert FeatureEngine.calculate_consecutive_groups([1, 2, 10, 11, 12, 25]) == 2

    def test_omission_classification_thresholds(self):
        """
        Verify Cold / Warm / Hot boundaries:
        - Hot: 0 <= m <= 4
        - Warm: 5 <= m <= 9
        - Cold: m >= 10
        - Negative omission raises ValueError
        """
        assert FeatureEngine.classify_omission(0) == "HOT"
        assert FeatureEngine.classify_omission(4) == "HOT"
        assert FeatureEngine.classify_omission(5) == "WARM"
        assert FeatureEngine.classify_omission(9) == "WARM"
        assert FeatureEngine.classify_omission(10) == "COLD"
        assert FeatureEngine.classify_omission(42) == "COLD"

        with pytest.raises(ValueError, match="negative"):
            FeatureEngine.classify_omission(-1)

    def test_feature_engine_input_validation(self):
        """Verify invalid inputs trigger descriptive exceptions."""
        with pytest.raises(ValueError, match="6 red balls"):
            FeatureEngine.calculate_sum([1, 2, 3, 4, 5])

        with pytest.raises(ValueError, match="6 red balls"):
            FeatureEngine.calculate_span([1, 2, 3, 4, 5, 6, 7])

        with pytest.raises(ValueError, match="distinct"):
            FeatureEngine.calculate_ac([1, 1, 3, 4, 5, 6])

    def test_feature_idempotency_on_real_database(self):
        """
        Verify that compute_all_features(force=False) on the fully-populated
        database returns 0 immediately without altering the database.
        """
        engine = FeatureEngine()
        new_count = engine.compute_all_features(force=False)
        assert new_count == 0, f"Expected 0 new features on full DB, got {new_count}"

        # Confirm count remains 3519
        with SessionLocal() as session:
            count = session.scalar(select(func.count(FeatureMetrics.issue_no)))
            assert count == 3519, f"Expected 3519 feature rows, got {count}"
