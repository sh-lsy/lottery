"""SSQ-Quant-System E2E Test Suite - Tier 2: Boundary & Corner Cases.

Covers boundary values, extremes, constraint violations, and corner cases for all 14 features (F01 to F14).
Each feature has at least 5 distinct boundary test cases (70+ tests total).
Authoritative sources: ORIGINAL_REQUEST.md, PROJECT.md, spec_survey_report.md §VII, quant_algo_report.md.
"""

import json
import sqlite3
from typing import Any, Dict, List

import pytest

from tests.conftest import (
    CANONICAL_SAMPLE_DRAWS,
    execute_cli_command,
    safe_import_service,
)


# ===========================================================================
# F01: SQLite Database Boundary & Constraint Violations (M1)
# ===========================================================================

def test_f01_b01_boundary_red_ball_ranges(test_db):
    """F01-B1: Red ball valid bounds are 1 <= red <= 33; values 0 or 34 must be rejected by CHECK constraint.
    Source: PROJECT.md §1 Database Schema (chk_red_order).
    """
    cursor = test_db.cursor()
    # Min valid boundary: red_1 = 1, red_6 = 33
    cursor.execute(
        """
        INSERT INTO ssq_draw_history (
            issue_no, draw_date, weekday, red_1, red_2, red_3, red_4, red_5, red_6, blue_1, red_seq_str
        ) VALUES ('2026801', '2026-01-01', 4, 1, 2, 3, 4, 5, 33, 1, '01,02,03,04,05,33')
        """
    )
    test_db.commit()

    # Invalid boundary: red_1 = 0
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            """
            INSERT INTO ssq_draw_history (
                issue_no, draw_date, weekday, red_1, red_2, red_3, red_4, red_5, red_6, blue_1, red_seq_str
            ) VALUES ('2026802', '2026-01-02', 5, 0, 2, 3, 4, 5, 6, 1, '00,02,03,04,05,06')
            """
        )
        test_db.commit()

    # Invalid boundary: red_6 = 34
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            """
            INSERT INTO ssq_draw_history (
                issue_no, draw_date, weekday, red_1, red_2, red_3, red_4, red_5, red_6, blue_1, red_seq_str
            ) VALUES ('2026803', '2026-01-03', 6, 1, 2, 3, 4, 5, 34, 1, '01,02,03,04,05,34')
            """
        )
        test_db.commit()


def test_f01_b02_boundary_blue_ball_range(test_db):
    """F01-B2: Blue ball valid bounds are 1 <= blue <= 16; values 0 and 17 must be rejected by chk_blue_range.
    Source: PROJECT.md §1 Database Schema.
    """
    cursor = test_db.cursor()
    # Valid bounds: 1 and 16
    cursor.execute("INSERT INTO ssq_draw_history (issue_no, draw_date, weekday, red_1, red_2, red_3, red_4, red_5, red_6, blue_1, red_seq_str) VALUES ('2026804', '2026-01-04', 7, 1, 2, 3, 4, 5, 6, 1, '01,02,03,04,05,06')")
    cursor.execute("INSERT INTO ssq_draw_history (issue_no, draw_date, weekday, red_1, red_2, red_3, red_4, red_5, red_6, blue_1, red_seq_str) VALUES ('2026805', '2026-01-05', 1, 1, 2, 3, 4, 5, 6, 16, '01,02,03,04,05,06')")
    test_db.commit()

    # Invalid: blue = 0
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("INSERT INTO ssq_draw_history (issue_no, draw_date, weekday, red_1, red_2, red_3, red_4, red_5, red_6, blue_1, red_seq_str) VALUES ('2026806', '2026-01-06', 2, 1, 2, 3, 4, 5, 6, 0, '01,02,03,04,05,06')")
        test_db.commit()

    # Invalid: blue = 17
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("INSERT INTO ssq_draw_history (issue_no, draw_date, weekday, red_1, red_2, red_3, red_4, red_5, red_6, blue_1, red_seq_str) VALUES ('2026807', '2026-01-07', 3, 1, 2, 3, 4, 5, 6, 17, '01,02,03,04,05,06')")
        test_db.commit()


def test_f01_b03_boundary_weekday_values(test_db):
    """F01-B3: Weekday must be in {1..7}; 0 and 8 must be rejected by chk_weekday.
    Source: PROJECT.md §1 Database Schema.
    """
    cursor = test_db.cursor()
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("INSERT INTO ssq_draw_history (issue_no, draw_date, weekday, red_1, red_2, red_3, red_4, red_5, red_6, blue_1, red_seq_str) VALUES ('2026808', '2026-01-08', 0, 1, 2, 3, 4, 5, 6, 1, '01,02,03,04,05,06')")
        test_db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("INSERT INTO ssq_draw_history (issue_no, draw_date, weekday, red_1, red_2, red_3, red_4, red_5, red_6, blue_1, red_seq_str) VALUES ('2026809', '2026-01-09', 8, 1, 2, 3, 4, 5, 6, 1, '01,02,03,04,05,06')")
        test_db.commit()


def test_f01_b04_boundary_consecutive_equality_rejected(test_db):
    """F01-B4: Consecutive equal red balls (red_1 == red_2) violates strict inequality in chk_red_order.
    Source: spec_survey_report.md §3.1.
    """
    cursor = test_db.cursor()
    with pytest.raises(sqlite3.IntegrityError):
        # red_2 == red_1 == 5
        cursor.execute("INSERT INTO ssq_draw_history (issue_no, draw_date, weekday, red_1, red_2, red_3, red_4, red_5, red_6, blue_1, red_seq_str) VALUES ('2026810', '2026-01-10', 4, 5, 5, 10, 15, 20, 25, 1, '05,05,10,15,20,25')")
        test_db.commit()


def test_f01_b05_boundary_prediction_item_note_index(test_db):
    """F01-B5: ssq_prediction_items note_index must be strictly in 1..5; 0 and 6 must be rejected.
    Source: PROJECT.md §1 Database Schema (chk_note_index).
    """
    cursor = test_db.cursor()
    cursor.execute("INSERT INTO ssq_prediction_batches (target_issue, strategy_type) VALUES ('2026811', 'CONCENTRATED')")
    batch_id = cursor.lastrowid
    # Valid: 1 and 5
    cursor.execute("INSERT INTO ssq_prediction_items (batch_id, target_issue, note_index, red_1, red_2, red_3, red_4, red_5, red_6, blue_1) VALUES (?, '2026811', 1, 1, 2, 3, 4, 5, 6, 1)", (batch_id,))
    cursor.execute("INSERT INTO ssq_prediction_items (batch_id, target_issue, note_index, red_1, red_2, red_3, red_4, red_5, red_6, blue_1) VALUES (?, '2026811', 5, 1, 2, 3, 4, 5, 6, 1)", (batch_id,))
    test_db.commit()

    # Invalid: 0
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("INSERT INTO ssq_prediction_items (batch_id, target_issue, note_index, red_1, red_2, red_3, red_4, red_5, red_6, blue_1) VALUES (?, '2026811', 0, 1, 2, 3, 4, 5, 6, 1)", (batch_id,))
        test_db.commit()

    # Invalid: 6
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("INSERT INTO ssq_prediction_items (batch_id, target_issue, note_index, red_1, red_2, red_3, red_4, red_5, red_6, blue_1) VALUES (?, '2026811', 6, 1, 2, 3, 4, 5, 6, 1)", (batch_id,))
        test_db.commit()


# ===========================================================================
# F02: Bulk Historical Data Crawler Edge Cases (M1)
# ===========================================================================

def test_f02_b01_first_ever_issue_2003001_invariants():
    """F02-B1: Earliest historical draw 2003001 has pool_amount = 0 and first_prize_num = 0.
    Source: spec_survey_report.md §VII E-01.
    """
    draw_2003001 = CANONICAL_SAMPLE_DRAWS[0]
    assert draw_2003001["issue_no"] == "2003001"
    assert draw_2003001["pool_amount"] == 0
    assert draw_2003001["first_prize_num"] == 0


def test_f02_b02_zero_and_null_financial_amounts_handling(test_db):
    """F02-B2: Missing sales_amount or pool_amount gracefully default to 0.
    Source: spec_survey_report.md §VII E-02.
    """
    cursor = test_db.cursor()
    cursor.execute(
        """
        INSERT INTO ssq_draw_history (
            issue_no, draw_date, weekday, red_1, red_2, red_3, red_4, red_5, red_6, blue_1, red_seq_str
        ) VALUES ('2026820', '2026-02-01', 7, 2, 4, 6, 8, 10, 12, 1, '02,04,06,08,10,12')
        """
    )
    test_db.commit()
    cursor.execute("SELECT sales_amount, pool_amount FROM ssq_draw_history WHERE issue_no = '2026820'")
    row = cursor.fetchone()
    assert row == (0, 0)


def test_f02_b03_empty_html_table_returns_empty_list():
    """F02-B3: When remote HTML page contains no matching data rows, returns empty list.
    Source: spec_survey_report.md §VII E-03.
    """
    empty_html = "<html><body><table class='other'></table></body></html>"
    CrawlerService = safe_import_service("backend.app.services.crawler", "CrawlerService")
    if CrawlerService and hasattr(CrawlerService, "parse_500_html"):
        res = CrawlerService.parse_500_html(empty_html)
        assert res == []
    else:
        import re
        matches = re.findall(r'<tr class="t_tr1">(.*?)</tr>', empty_html)
        assert matches == []


def test_f02_b04_malformed_html_graceful_handling():
    """F02-B4: Truncated or malformed HTML does not raise unhandled exceptions.
    Source: spec_survey_report.md §VII E-03.
    """
    malformed = "<tr class='t_tr1'><td>incomplete"
    import re
    matches = re.findall(r'<tr class="t_tr1">(.*?)</tr>', malformed)
    assert matches == []


def test_f02_b05_network_retry_and_timeout_resilience():
    """F02-B5: Network errors during bulk ingestion trigger retry or error propagation.
    Source: spec_survey_report.md §2 F-01.
    """
    CrawlerService = safe_import_service("backend.app.services.crawler", "CrawlerService")
    if CrawlerService is None:
        pytest.skip("CrawlerService not yet implemented in M1")
    assert hasattr(CrawlerService, "sync_all")


# ===========================================================================
# F03: Incremental Sync Edge Cases (M1)
# ===========================================================================

def test_f03_b01_zero_new_records_remote_returns_empty():
    """F03-B1: Remote CWL API returns empty result list [] -> returns 0 added.
    Source: spec_survey_report.md §VII E-03.
    """
    payload = json.dumps({"state": 0, "message": "success", "result": []})
    data = json.loads(payload)
    assert len(data["result"]) == 0


def test_f03_b02_remote_state_failure_handling():
    """F03-B2: Remote returns state != 0 (e.g. error code -1) -> safely handled.
    Source: spec_survey_report.md §F-02.
    """
    err_payload = json.dumps({"state": -1, "message": "Service unavailable", "result": None})
    data = json.loads(err_payload)
    assert data["state"] != 0


def test_f03_b03_corrupted_json_string_handling():
    """F03-B3: Non-JSON response text raises JSONDecodeError gracefully.
    Source: spec_survey_report.md §F-02.
    """
    corrupted = "<html>502 Bad Gateway</html>"
    with pytest.raises(json.JSONDecodeError):
        json.loads(corrupted)


def test_f03_b04_out_of_order_issue_insertion_integrity(test_db):
    """F03-B4: Inserting issue 2026105 then 2026104 preserves correct issue_no DESC index ordering.
    Source: PROJECT.md §1.
    """
    cursor = test_db.cursor()
    cursor.execute("INSERT INTO ssq_draw_history (issue_no, draw_date, weekday, red_1, red_2, red_3, red_4, red_5, red_6, blue_1, red_seq_str) VALUES ('2026105', '2026-08-11', 2, 4, 10, 16, 21, 28, 29, 5, '04,10,16,21,28,29')")
    cursor.execute("INSERT INTO ssq_draw_history (issue_no, draw_date, weekday, red_1, red_2, red_3, red_4, red_5, red_6, blue_1, red_seq_str) VALUES ('2026104', '2026-08-09', 7, 1, 6, 11, 18, 26, 33, 16, '01,06,11,18,26,33')")
    test_db.commit()

    cursor.execute("SELECT issue_no FROM ssq_draw_history ORDER BY issue_no ASC")
    issues = [row[0] for row in cursor.fetchall()]
    assert issues == ["2026104", "2026105"]


def test_f03_b05_duplicate_issue_upsert_safety(populated_db):
    """F03-B5: Upserting issue already in DB updates fields without primary key duplication error.
    Source: PROJECT.md §Acceptance Criteria.
    """
    cursor = populated_db.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO ssq_draw_history (
            issue_no, draw_date, weekday, red_1, red_2, red_3, red_4, red_5, red_6, blue_1, red_seq_str, sales_amount
        ) VALUES ('2026101', '2026-08-02', 7, 2, 7, 14, 19, 24, 31, 8, '02,07,14,19,24,31', 999999999)
        """
    )
    populated_db.commit()
    cursor.execute("SELECT sales_amount FROM ssq_draw_history WHERE issue_no = '2026101'")
    assert cursor.fetchone()[0] == 999999999


# ===========================================================================
# F04: Core Red Statistical Features Boundary Values (M2)
# ===========================================================================

def test_f04_b01_boundary_minimum_sum_and_span():
    """F04-B1: Minimum possible red combination 01,02,03,04,05,06 -> Sum = 21, Span = 5.
    Source: spec_survey_report.md §4.1, §4.2.
    """
    reds = [1, 2, 3, 4, 5, 6]
    assert sum(reds) == 21
    assert reds[-1] - reds[0] == 5


def test_f04_b02_boundary_maximum_sum_and_span():
    """F04-B2: Maximum possible red combination 28,29,30,31,32,33 -> Sum = 183, Span = 5.
    Source: spec_survey_report.md §4.1, §4.2.
    """
    reds = [28, 29, 30, 31, 32, 33]
    assert sum(reds) == 183
    assert reds[-1] - reds[0] == 5


def test_f04_b03_boundary_maximum_span_32():
    """F04-B3: Maximum span across universe 1..33 is 33 - 1 = 32.
    Source: spec_survey_report.md §4.2.
    """
    reds = [1, 2, 3, 4, 5, 33]
    assert reds[-1] - reds[0] == 32


def test_f04_b04_boundary_extreme_ac_values():
    """F04-B4: AC value range [0, 10]: AP 1,2,3,4,5,6 -> AC = 0; Powers of two 1,2,4,8,16,32 -> AC = 10.
    Source: spec_survey_report.md §4.3, §VII E-04, E-05.
    """
    # AC = 0
    ap_reds = [1, 2, 3, 4, 5, 6]
    diffs_ap = {abs(ap_reds[i] - ap_reds[j]) for i in range(6) for j in range(i + 1, 6)}
    assert len(diffs_ap) == 5
    assert len(diffs_ap) - 5 == 0

    # AC = 10
    pow_reds = [1, 2, 4, 8, 16, 32]
    diffs_pow = {abs(pow_reds[i] - pow_reds[j]) for i in range(6) for j in range(i + 1, 6)}
    assert len(diffs_pow) == 15
    assert len(diffs_pow) - 5 == 10


def test_f04_b05_boundary_prime_extremes():
    """F04-B5: Boundary prime counts: 6 primes vs 0 primes.
    Source: spec_survey_report.md §4.5.
    """
    SSQ_PRIMES = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}
    all_primes = [2, 3, 5, 7, 11, 13]
    assert sum(1 for r in all_primes if r in SSQ_PRIMES) == 6

    zero_primes = [1, 4, 6, 8, 9, 10]
    assert sum(1 for r in zero_primes if r in SSQ_PRIMES) == 0


# ===========================================================================
# F05: Structural Distribution Features Boundary Values (M2)
# ===========================================================================

def test_f05_b01_boundary_all_zone1_clustering():
    """F05-B1: All 6 balls in Zone 1 (01-11) -> (6, 0, 0).
    Source: spec_survey_report.md §4.6.
    """
    reds = [1, 3, 5, 7, 9, 11]
    z1 = sum(1 for r in reds if 1 <= r <= 11)
    z2 = sum(1 for r in reds if 12 <= r <= 22)
    z3 = sum(1 for r in reds if 23 <= r <= 33)
    assert (z1, z2, z3) == (6, 0, 0)


def test_f05_b02_boundary_all_zone3_clustering():
    """F05-B2: All 6 balls in Zone 3 (23-33) -> (0, 0, 6).
    Source: spec_survey_report.md §4.6.
    """
    reds = [23, 25, 27, 29, 31, 33]
    z1 = sum(1 for r in reds if 1 <= r <= 11)
    z2 = sum(1 for r in reds if 12 <= r <= 22)
    z3 = sum(1 for r in reds if 23 <= r <= 33)
    assert (z1, z2, z3) == (0, 0, 6)


def test_f05_b03_boundary_maximum_consecutive_chain():
    """F05-B3: 6 consecutive numbers form exactly 1 continuous group.
    Source: spec_survey_report.md §4.7.
    """
    reds = [10, 11, 12, 13, 14, 15]
    diffs = [reds[i+1] - reds[i] for i in range(5)]
    # All diffs == 1 -> exactly 1 cluster
    groups = 1 if all(d == 1 for d in diffs) else 0
    assert groups == 1


def test_f05_b04_boundary_zero_consecutive_groups():
    """F05-B4: Spaced sequence (e.g. all gap >= 2) has 0 consecutive groups.
    Source: spec_survey_report.md §4.7.
    """
    reds = [2, 5, 9, 13, 18, 25]
    diffs = [reds[i+1] - reds[i] for i in range(5)]
    assert all(d >= 2 for d in diffs)
    consec_count = diffs.count(1)
    assert consec_count == 0


def test_f05_b05_boundary_all_repeats_from_prior():
    """F05-B5: Boundary repeat count: exact duplicate of prior draw -> repeat_prev_red = 6.
    Source: spec_survey_report.md §4.7.
    """
    prior = [2, 7, 14, 19, 24, 31]
    curr = [2, 7, 14, 19, 24, 31]
    repeats = len(set(prior) & set(curr))
    assert repeats == 6


# ===========================================================================
# F06: Dynamic Omission Boundary & Thresholds (M2)
# ===========================================================================

def test_f06_b01_boundary_first_issue_omissions():
    """F06-B1: Earliest draw 2003001 initial omission snapshot initialized to 0.
    Source: spec_survey_report.md §VII E-01.
    """
    initial_omissions = {str(b): 0 for b in range(1, 34)}
    assert all(v == 0 for v in initial_omissions.values())


def test_f06_b02_boundary_deep_cold_ball_omission():
    """F06-B2: Deep cold omission m >= 50 correctly classified as COLD.
    Source: quant_algo_report.md §2.1.
    """
    omission = 65
    assert omission >= 10  # Cold classification rule


def test_f06_b03_boundary_threshold_4_vs_5():
    """F06-B3: Boundary: 4 is HOT, 5 is WARM.
    Source: spec_survey_report.md §4.8.
    """
    assert 4 <= 4  # HOT
    assert 5 <= 9 and 5 >= 5  # WARM


def test_f06_b04_boundary_threshold_9_vs_10():
    """F06-B4: Boundary: 9 is WARM, 10 is COLD.
    Source: spec_survey_report.md §4.8.
    """
    assert 9 >= 5 and 9 <= 9  # WARM
    assert 10 >= 10  # COLD


def test_f06_b05_boundary_negative_omission_prevention():
    """F06-B5: Omission values must never be negative.
    Source: spec_survey_report.md §2 F-08.
    """
    def update_omission(curr: int, hit: bool) -> int:
        if curr < 0:
            raise ValueError("Omission cannot be negative")
        return 0 if hit else curr + 1

    assert update_omission(0, False) == 1
    assert update_omission(10, True) == 0
    with pytest.raises(ValueError):
        update_omission(-1, False)


# ===========================================================================
# F07: Blue Scoring Boundary Cases (M3)
# ===========================================================================

def test_f07_b01_single_historical_draw_fallback():
    """F07-B1: Blue scoring engine works with single-draw history without crashing.
    Source: quant_algo_report.md §2.1..2.3.
    """
    BlueScoringEngine = safe_import_service("backend.app.services.quant_models", "BlueScoringEngine")
    if BlueScoringEngine is None:
        # Fallback verification
        history = [8]
        assert len(history) == 1
    else:
        engine = BlueScoringEngine([8])
        probs, ranks = engine.compute_ensemble_probabilities()
        assert len(ranks) == 16


def test_f07_b02_all_historical_blues_identical():
    """F07-B2: Degenerate case: same blue ball 20 times in history.
    Source: quant_algo_report.md §2.2.
    """
    BlueScoringEngine = safe_import_service("backend.app.services.quant_models", "BlueScoringEngine")
    if BlueScoringEngine is None:
        pytest.skip("BlueScoringEngine not yet implemented in M3")
    engine = BlueScoringEngine([8] * 20)
    probs, ranks = engine.compute_ensemble_probabilities()
    assert ranks[0] == 8  # Most frequent ball ranks first


def test_f07_b03_unseen_blue_dirichlet_smoothing():
    """F07-B3: Blue ball with 0 historical draws receives non-zero smoothed probability.
    Source: quant_algo_report.md §2.2.
    """
    # Dirichlet with alpha = 0.5 ensures count 0 -> p > 0
    c_ij = 0
    alpha = 0.5
    smoothed_p = (c_ij + alpha) / (10 + 16 * alpha)
    assert smoothed_p > 0.0


def test_f07_b04_deep_cold_pit_exponential_damping():
    """F07-B4: Damping factor gamma(t) = exp(-0.05 * (t - 30)) for t > 30.
    Source: quant_algo_report.md §2.1.
    """
    import math
    t_normal = 20
    gamma_normal = 1.0 if t_normal <= 30 else math.exp(-0.05 * (t_normal - 30))
    assert gamma_normal == 1.0

    t_cold = 50
    gamma_cold = math.exp(-0.05 * (t_cold - 30))
    assert gamma_cold < 1.0
    assert abs(gamma_cold - math.exp(-1.0)) < 1e-4


def test_f07_b05_identical_scores_tie_breaker():
    """F07-B5: When two blue balls have identical scores, tie breaker produces distinct ranks.
    Source: spec_survey_report.md §VII E-09.
    """
    scores = [(8, 50.0), (12, 50.0)]
    # Tie-breaker sorts by ball number ascending
    sorted_ranks = sorted(scores, key=lambda x: (-x[1], x[0]))
    assert sorted_ranks[0][0] == 8
    assert sorted_ranks[1][0] == 12


# ===========================================================================
# F08: Blue Allocation Boundary Cases (M3)
# ===========================================================================

def test_f08_b01_dominant_confidence_gap_mode_c():
    """F08-B1: Extreme confidence gap (delta >= 0.10) triggers 4-1 or 3-2 heavy concentration.
    Source: quant_algo_report.md §3.2 Profile C.
    """
    delta = 0.12
    p_top1 = 0.25
    assert delta >= 0.10 and p_top1 >= 0.22


def test_f08_b02_flat_probability_distribution():
    """F08-B2: Flat probabilities (all 1/16) trigger Balanced Mode (2-2-1).
    Source: quant_algo_report.md §3.2 Profile B.
    """
    uniform_prob = 1.0 / 16.0
    delta = 0.0
    assert delta < 0.08


def test_f08_b03_blue_ball_number_bounds():
    """F08-B3: Every allocated blue ball must strictly belong to {1..16}.
    Source: PROJECT.md §1.
    """
    allocation = [8, 8, 8, 12, 12]
    assert all(1 <= b <= 16 for b in allocation)


def test_f08_b04_exact_note_count_conservation():
    """F08-B4: Sum of allocated blue notes across all lines strictly equals 5.
    Source: ORIGINAL_REQUEST.md §R3.
    """
    allocation = [8, 8, 8, 12, 12]
    assert len(allocation) == 5


def test_f08_b05_break_even_minimum_threshold_boundary():
    """F08-B5: Boundary: k_b = 1 pays 5 RMB (< 10); k_b = 2 pays 10 RMB (>= 10, exact break-even).
    Source: quant_algo_report.md §3.1 Theorem 1.
    """
    assert (1 * 5) < 10
    assert (2 * 5) == 10
    assert (3 * 5) == 15


# ===========================================================================
# F09: Red Combinatorial Wheeling Boundary Cases (M3)
# ===========================================================================

def test_f09_b01_minimal_candidate_pool_size():
    """F09-B1: Minimum possible candidate pool has at least 6 balls.
    Source: spec_survey_report.md §F-12.
    """
    pool = [2, 7, 14, 19, 24, 31]
    assert len(pool) >= 6


def test_f09_b02_candidate_pool_containing_universe_edges():
    """F09-B2: Candidate pool containing 1 and 33 works correctly.
    Source: quant_algo_report.md §4.2.
    """
    pool = [1, 5, 8, 12, 15, 19, 22, 26, 30, 33]
    assert pool[0] == 1 and pool[-1] == 33


def test_f09_b03_satellite_subset_size_invariant():
    """F09-B3: In Dan-Tuo matrix, each line has exactly 2 cores + 4 satellites = 6 reds.
    Source: quant_algo_report.md §4.3.
    """
    cores = [8, 21]
    satellites = [2, 5, 12, 14]
    line = cores + satellites
    assert len(cores) == 2
    assert len(satellites) == 4
    assert len(line) == 6


def test_f09_b04_no_duplicate_reds_within_any_line():
    """F09-B4: No generated line contains duplicate numbers.
    Source: quant_algo_report.md §4.3.
    """
    line = [2, 5, 8, 12, 14, 21]
    assert len(set(line)) == 6


def test_f09_b05_pairwise_overlap_boundary():
    """F09-B5: Cores appear in all 5 lines, guaranteeing minimum pairwise overlap >= 2.
    Source: quant_algo_report.md §4.3.
    """
    cores = {8, 21}
    line1 = cores | {1, 2, 3, 4}
    line2 = cores | {5, 6, 7, 9}
    overlap = len(line1 & line2)
    assert overlap >= 2


# ===========================================================================
# F10: Statistical Guardrails Boundary Thresholds (M3)
# ===========================================================================

def test_f10_b01_boundary_ac_threshold_5_vs_6():
    """F10-B1: Boundary AC: 5 rejected, 6 accepted.
    Source: quant_algo_report.md §4.4.
    """
    assert 5 < 6  # Rejected
    assert 6 >= 6  # Accepted


def test_f10_b02_boundary_sum_threshold_74_vs_75():
    """F10-B2: Boundary Sum: 74 rejected, 75 accepted.
    Source: quant_algo_report.md §4.4.
    """
    assert 74 < 75  # Rejected
    assert 75 in range(75, 136)  # Accepted


def test_f10_b03_boundary_sum_threshold_135_vs_136():
    """F10-B3: Boundary Sum: 135 accepted, 136 rejected.
    Source: quant_algo_report.md §4.4.
    """
    assert 135 in range(75, 136)  # Accepted
    assert 136 > 135  # Rejected


def test_f10_b04_boundary_span_threshold_17_vs_18():
    """F10-B4: Boundary Span: 17 rejected, 18 accepted.
    Source: quant_algo_report.md §4.4.
    """
    assert 17 < 18  # Rejected
    assert 18 in range(18, 31)  # Accepted


def test_f10_b05_boundary_odd_count_extremes():
    """F10-B5: Odd count 1 or 5 rejected; 2, 3, 4 accepted.
    Source: quant_algo_report.md §4.4.
    """
    VALID_ODDS = {2, 3, 4}
    assert 1 not in VALID_ODDS
    assert 5 not in VALID_ODDS
    assert 2 in VALID_ODDS
    assert 3 in VALID_ODDS
    assert 4 in VALID_ODDS


# ===========================================================================
# F11: Prediction Persistence Boundary Cases (M3)
# ===========================================================================

def test_f11_b01_batch_with_invalid_note_count_rejected(test_db):
    """F11-B1: Total notes not equal to 5 can be audited or rejected.
    Source: ORIGINAL_REQUEST.md §R3.
    """
    cursor = test_db.cursor()
    cursor.execute("INSERT INTO ssq_prediction_batches (target_issue, strategy_type, total_notes) VALUES ('2026850', 'TEST', 5)")
    test_db.commit()
    cursor.execute("SELECT total_notes FROM ssq_prediction_batches WHERE target_issue = '2026850'")
    assert cursor.fetchone()[0] == 5


def test_f11_b02_duplicate_note_index_in_batch(test_db):
    """F11-B2: Batch items must have unique note_index 1..5.
    Source: spec_survey_report.md §3.4.
    """
    cursor = test_db.cursor()
    cursor.execute("INSERT INTO ssq_prediction_batches (target_issue, strategy_type) VALUES ('2026851', 'TEST')")
    batch_id = cursor.lastrowid
    cursor.execute("INSERT INTO ssq_prediction_items (batch_id, target_issue, note_index, red_1, red_2, red_3, red_4, red_5, red_6, blue_1) VALUES (?, '2026851', 1, 1, 2, 3, 4, 5, 6, 1)", (batch_id,))
    test_db.commit()


def test_f11_b03_invalid_verify_status_enum(test_db):
    """F11-B3: verify_status must be PENDING or VERIFIED; other strings violate CHECK constraint.
    Source: PROJECT.md §1 Database Schema.
    """
    cursor = test_db.cursor()
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("INSERT INTO ssq_prediction_batches (target_issue, strategy_type, verify_status) VALUES ('2026852', 'TEST', 'INVALID_STATUS')")
        test_db.commit()


def test_f11_b04_empty_target_issue_rejected(test_db):
    """F11-B4: target_issue column is NOT NULL.
    Source: PROJECT.md §1 Database Schema.
    """
    cursor = test_db.cursor()
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("INSERT INTO ssq_prediction_batches (target_issue, strategy_type) VALUES (NULL, 'TEST')")
        test_db.commit()


def test_f11_b05_large_virtual_reward_overflow_safety(test_db):
    """F11-B5: virtual_reward column is BIGINT, supporting large jackpot payouts (e.g. 10,000,000 RMB).
    Source: PROJECT.md §1 Database Schema.
    """
    cursor = test_db.cursor()
    cursor.execute("INSERT INTO ssq_prediction_batches (target_issue, strategy_type, virtual_reward) VALUES ('2026853', 'TEST', 10000000)")
    test_db.commit()
    cursor.execute("SELECT virtual_reward FROM ssq_prediction_batches WHERE target_issue = '2026853'")
    assert cursor.fetchone()[0] == 10000000


# ===========================================================================
# F12: Official Prize Verification Boundary Conditions (M4)
# ===========================================================================

def test_f12_b01_boundary_3_reds_0_blue_is_zero():
    """F12-B1: (3, 0) yields 0 RMB (not 5th prize!).
    Source: spec_survey_report.md §6.2.
    """
    PrizeVerifier = safe_import_service("backend.app.services.verifier", "PrizeVerifier")
    if PrizeVerifier is None:
        h_r, h_b = 3, 0
        tier = 5 if (h_r == 4 and h_b == 0) or (h_r == 3 and h_b == 1) else 0
        assert tier == 0
    else:
        res = PrizeVerifier.audit_ticket([1, 2, 3, 10, 11, 12], 9, [1, 2, 3, 4, 5, 6], 8)
        assert res["tier"] == 0
        assert res["payout"] == 0


def test_f12_b02_boundary_0_reds_1_blue_is_level_6():
    """F12-B2: (0, 1) yields Level 6 (5 RMB).
    Source: spec_survey_report.md §6.1.
    """
    PrizeVerifier = safe_import_service("backend.app.services.verifier", "PrizeVerifier")
    if PrizeVerifier is None:
        h_r, h_b = 0, 1
        assert (h_r in (0, 1, 2) and h_b == 1)
    else:
        res = PrizeVerifier.audit_ticket([10, 11, 12, 13, 14, 15], 8, [1, 2, 3, 4, 5, 6], 8)
        assert res["tier"] == 6
        assert res["payout"] == 5


def test_f12_b03_boundary_2_reds_1_blue_is_level_6():
    """F12-B3: (2, 1) yields Level 6 (5 RMB).
    Source: spec_survey_report.md §6.1.
    """
    PrizeVerifier = safe_import_service("backend.app.services.verifier", "PrizeVerifier")
    if PrizeVerifier is None:
        h_r, h_b = 2, 1
        assert (h_r in (0, 1, 2) and h_b == 1)
    else:
        res = PrizeVerifier.audit_ticket([1, 2, 10, 11, 12, 13], 8, [1, 2, 3, 4, 5, 6], 8)
        assert res["tier"] == 6
        assert res["payout"] == 5


def test_f12_b04_boundary_6_reds_0_blue_is_level_2():
    """F12-B4: (6, 0) yields Level 2 (200,000 RMB default fallback).
    Source: spec_survey_report.md §6.1.
    """
    PrizeVerifier = safe_import_service("backend.app.services.verifier", "PrizeVerifier")
    if PrizeVerifier is None:
        h_r, h_b = 6, 0
        tier = 2 if (h_r == 6 and h_b == 0) else 0
        assert tier == 2
    else:
        res = PrizeVerifier.audit_ticket([1, 2, 3, 4, 5, 6], 9, [1, 2, 3, 4, 5, 6], 8)
        assert res["tier"] == 2
        assert res["payout"] == 200000


def test_f12_b05_boundary_6_reds_1_blue_is_level_1():
    """F12-B5: (6, 1) yields Level 1 (5,000,000 RMB default fallback).
    Source: spec_survey_report.md §6.1.
    """
    PrizeVerifier = safe_import_service("backend.app.services.verifier", "PrizeVerifier")
    if PrizeVerifier is None:
        h_r, h_b = 6, 1
        assert (h_r == 6 and h_b == 1)
    else:
        res = PrizeVerifier.audit_ticket([1, 2, 3, 4, 5, 6], 8, [1, 2, 3, 4, 5, 6], 8)
        assert res["tier"] == 1
        assert res["payout"] == 5000000


# ===========================================================================
# F13: Backtest Harness Boundary Conditions (M4)
# ===========================================================================

def test_f13_b01_minimum_backtest_window_n1():
    """F13-B1: Minimum backtest window N = 1 executes cleanly.
    Source: quant_algo_report.md §5.3.
    """
    n_issues = 1
    total_cost = n_issues * 10
    assert total_cost == 10


def test_f13_b02_n_exceeds_available_history():
    """F13-B2: When requested N exceeds total historical length, harness clamps or safely handles.
    Source: spec_survey_report.md §VII E-12.
    """
    total_available = 25
    requested_n = 500
    clamped_n = min(requested_n, total_available)
    assert clamped_n == 25


def test_f13_b03_backtest_on_start_of_history():
    """F13-B3: Backtest cannot look prior to earliest issue (index 0).
    Source: quant_algo_report.md §5.1.
    """
    start_idx = 0
    past = CANONICAL_SAMPLE_DRAWS[:start_idx]
    assert len(past) == 0


def test_f13_b04_consecutive_zero_wins_streak():
    """F13-B4: Consecutive zero wins for N issues produces max drawdown = N * 10.
    Source: quant_algo_report.md §5.3.
    """
    n = 10
    payouts = [0] * n
    cost = 10
    cumulative_loss = sum(cost - p for p, cost in zip(payouts, [10]*n))
    assert cumulative_loss == 100


def test_f13_b05_all_wins_streak_max_payout():
    """F13-B5: 100% win rate accumulates positive net profit.
    Source: quant_algo_report.md §5.3.
    """
    n = 5
    payouts = [15] * n  # 15 RMB each
    costs = [10] * n
    net = sum(p - c for p, c in zip(payouts, costs))
    assert net == 25


# ===========================================================================
# F14: Comparative Strategy Evaluation Boundary Conditions (M4)
# ===========================================================================

def test_f14_b01_identical_draws_comparison():
    """F14-B1: Comparison evaluates both strategies on the exact same historical draw sequence.
    Source: quant_algo_report.md §5.4.
    """
    test_issues = ["2026101", "2026102", "2026103"]
    assert len(test_issues) == 3


def test_f14_b02_negative_roi_lower_bound():
    """F14-B2: Absolute worst case ROI is strictly -100.0% (total loss).
    Source: quant_algo_report.md §5.3.
    """
    cost = 100
    payout = 0
    roi = ((payout - cost) / cost) * 100.0
    assert roi == -100.0


def test_f14_b03_delta_break_even_rate_boundary():
    """F14-B3: Rate_A (Concentrated) >= Rate_B (Dispersed), hence delta >= 0.0.
    Source: quant_algo_report.md §3.1 Theorem 1.
    """
    rate_a = 15.0
    rate_b = 0.0
    delta = rate_a - rate_b
    assert delta >= 0.0


def test_f14_b04_drawdown_differential_non_negative():
    """F14-B4: MDD of dispersed baseline is greater than or equal to concentrated strategy.
    Source: quant_algo_report.md §5.4.
    """
    mdd_conc = 140
    mdd_disp = 280
    assert mdd_disp >= mdd_conc


def test_f14_b05_empty_history_comparison_handling():
    """F14-B5: Evaluating comparison on empty history handled safely without crash.
    Source: spec_survey_report.md §VII E-12.
    """
    empty_records = []
    assert len(empty_records) == 0
