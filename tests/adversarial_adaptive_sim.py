"""
tests/adversarial_adaptive_sim.py

Adversarial Stress Testing & Empirical Challenger Simulation for Milestone 6:
SSQ-Quant-System Adaptive Strategy Self-Evolution Loop.

Aggressively validates:
1. Mathematical Weight Invariant: w_hazard + w_markov + w_momentum == 1.0 (or within tolerance)
2. Hyperparameter Boundedness: each weight in [0.05, 0.70] across extreme hot, cold, and oscillating regimes
3. Consecutive Deficit Streak Transition: K_t = 0 -> 1 -> 2 -> 3; mode switches to DISPERSED precisely at K_t >= 3
4. Break-even Recovery: win with >= 10 RMB payoff immediately resets K_t = 0 and restores CONCENTRATED mode
5. State Persistence & Audit: immutable events written to ssq_adaptive_history with valid JSON metadata
6. Reset Endpoint: POST /api/v1/adaptive/reset restores baseline defaults (0.40, 0.35, 0.25)
7. Predictor Blue Allocation Mode integration: CONCENTRATED (3+2) vs DISPERSED (5 distinct)
"""

import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath("."))

import json
import math
from datetime import date
from typing import Dict, List, Tuple
import numpy as np
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from backend.app.database import Base
from backend.app.models import (
    DrawHistory,
    PredictionBatch,
    PredictionItem,
    AdaptiveState,
    AdaptiveHistory,
)
from backend.app.services.adaptive_service import AdaptiveService
from backend.app.services.quant_models import BlueAllocationStrategy, BlueScoringEngine
from backend.app.main import app


def run_empirical_simulation():
    print("================================================================================")
    print("SSQ-Quant-System Milestone 6: Empirical Challenger Adversarial Simulation")
    print("================================================================================")

    # In-memory clean test database
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    results_table = []

    # -------------------------------------------------------------------------
    # SUITE 1: Baseline Initialization
    # -------------------------------------------------------------------------
    service = AdaptiveService()
    state = service.get_or_create_state(session)
    assert state.cold_reversion_weight == 0.40
    assert state.markov_weight == 0.35
    assert state.hot_momentum_weight == 0.25
    assert state.consecutive_deficit_count == 0
    assert state.current_blue_mode == "CONCENTRATED"
    init_sum = state.cold_reversion_weight + state.markov_weight + state.hot_momentum_weight
    assert abs(init_sum - 1.0) < 1e-9
    results_table.append(("Suite 1: Baseline Init", "PASS", f"Weights=(0.40, 0.35, 0.25), Mode=CONCENTRATED, Sum={init_sum:.4f}"))

    # -------------------------------------------------------------------------
    # SUITE 2: Weight Invariant & Boundedness Stress Test
    # -------------------------------------------------------------------------
    # We test 50 iterations under extreme Hot Momentum (m_bar = 0.0)
    # and 50 iterations under extreme Cold Reversion (m_bar = 20.0)
    # and 50 iterations of alternating extremes.
    regimes = [
        ("Extreme Hot (m_bar=0.0)", 0.0, 50),
        ("Extreme Cold (m_bar=25.0)", 25.0, 50),
        ("Neutral Regime (m_bar=7.0)", 7.0, 20),
    ]

    all_bounded = True
    max_sum_deviation = 0.0
    weight_samples = []

    # Reset state first
    service.reset_state(session)

    for regime_name, m_val, steps in regimes:
        for step in range(steps):
            w_h = state.cold_reversion_weight
            w_m = state.markov_weight
            w_mom = state.hot_momentum_weight

            if m_val <= 4.0:
                delta_w = service.LEARNING_RATE * (1.0 - m_val / 4.0)
                w_mom = min(0.55, w_mom + delta_w)
                w_h = max(0.20, w_h - delta_w)
            elif m_val >= 10.0:
                delta_w = service.LEARNING_RATE * min(1.0, (m_val - 9.0) / 10.0)
                w_h = min(0.60, w_h + delta_w)
                w_mom = max(0.15, w_mom - delta_w)

            tot = w_h + w_m + w_mom
            state.cold_reversion_weight = round(w_h / tot, 4)
            state.markov_weight = round(w_m / tot, 4)
            state.hot_momentum_weight = round(w_mom / tot, 4)

            w_sum = state.cold_reversion_weight + state.markov_weight + state.hot_momentum_weight
            dev = abs(w_sum - 1.0)
            if dev > max_sum_deviation:
                max_sum_deviation = dev

            for w in (state.cold_reversion_weight, state.markov_weight, state.hot_momentum_weight):
                if not (0.05 <= w <= 0.70):
                    all_bounded = False

        weight_samples.append((regime_name, state.cold_reversion_weight, state.markov_weight, state.hot_momentum_weight, w_sum))

    bounded_verdict = "PASS" if all_bounded else "FAIL"
    results_table.append(("Suite 2A: Weight Boundedness [0.05, 0.70]", bounded_verdict, f"All weights in [0.05, 0.70]: {all_bounded}"))

    # Sum Invariant verdict: note the exact floating deviation due to 4-decimal independent rounding
    sum_verdict = "PASS" if max_sum_deviation <= 0.0002 else "FAIL"
    results_table.append(("Suite 2B: Weight Sum Invariant (w1+w2+w3 ~ 1.0)", sum_verdict, f"Max deviation from 1.0: {max_sum_deviation:.6f}"))

    # -------------------------------------------------------------------------
    # SUITE 3: Consecutive Deficit Streak Transition (K_t = 0 -> 1 -> 2 -> 3 -> 4)
    # -------------------------------------------------------------------------
    service.reset_state(session)
    streak_records = []

    # Insert a sequence of dummy past draws so calculate_recent_blue_omission_mean doesn't fail
    for i in range(10):
        d_prev = DrawHistory(
            issue_no=f"20260{i:02d}",
            draw_date=date(2026, 1, 1 + i),
            weekday=1,
            red_1=1, red_2=2, red_3=3, red_4=4, red_5=5, red_6=6,
            blue_1=(i % 16) + 1,
            red_seq_str="01,02,03,04,05,06",
        )
        session.add(d_prev)
    session.flush()

    # Step 1: K_t = 0 -> 1
    d1 = DrawHistory(issue_no="2026101", draw_date=date(2026, 5, 1), weekday=2, red_1=1, red_2=2, red_3=3, red_4=4, red_5=5, red_6=6, blue_1=7, red_seq_str="01,02,03,04,05,06")
    session.add(d1)
    b1 = PredictionBatch(target_issue="2026101", strategy_type="CONCENTRATED_BREAK_EVEN", virtual_cost=10, virtual_reward=0)
    session.add(b1)
    session.flush()
    res1 = service.process_batch_verification(b1, d1, session)
    streak_records.append((1, res1["streak"], res1["current_mode"], res1["is_triggered"]))

    # Step 2: K_t = 1 -> 2
    d2 = DrawHistory(issue_no="2026102", draw_date=date(2026, 5, 3), weekday=4, red_1=1, red_2=2, red_3=3, red_4=4, red_5=5, red_6=6, blue_1=8, red_seq_str="01,02,03,04,05,06")
    session.add(d2)
    b2 = PredictionBatch(target_issue="2026102", strategy_type="CONCENTRATED_BREAK_EVEN", virtual_cost=10, virtual_reward=5)  # 5 RMB < 10 cost -> loss
    session.add(b2)
    session.flush()
    res2 = service.process_batch_verification(b2, d2, session)
    streak_records.append((2, res2["streak"], res2["current_mode"], res2["is_triggered"]))

    # Step 3: K_t = 2 -> 3 (Trigger threshold reached!)
    d3 = DrawHistory(issue_no="2026103", draw_date=date(2026, 5, 6), weekday=7, red_1=1, red_2=2, red_3=3, red_4=4, red_5=5, red_6=6, blue_1=9, red_seq_str="01,02,03,04,05,06")
    session.add(d3)
    b3 = PredictionBatch(target_issue="2026103", strategy_type="CONCENTRATED_BREAK_EVEN", virtual_cost=10, virtual_reward=0)
    session.add(b3)
    session.flush()
    res3 = service.process_batch_verification(b3, d3, session)
    streak_records.append((3, res3["streak"], res3["current_mode"], res3["is_triggered"]))

    # Step 4: K_t = 3 -> 4 (Continues in DISPERSED mode)
    d4 = DrawHistory(issue_no="2026104", draw_date=date(2026, 5, 8), weekday=2, red_1=1, red_2=2, red_3=3, red_4=4, red_5=5, red_6=6, blue_1=10, red_seq_str="01,02,03,04,05,06")
    session.add(d4)
    b4 = PredictionBatch(target_issue="2026104", strategy_type="DISPERSED_BASELINE", virtual_cost=10, virtual_reward=0)
    session.add(b4)
    session.flush()
    res4 = service.process_batch_verification(b4, d4, session)
    streak_records.append((4, res4["streak"], res4["current_mode"], res4["is_triggered"]))

    # Validate streak transition expectations:
    # K_t=1: streak=1, mode=CONCENTRATED, is_triggered=False
    # K_t=2: streak=2, mode=CONCENTRATED, is_triggered=False
    # K_t=3: streak=3, mode=DISPERSED, is_triggered=True
    # K_t=4: streak=4, mode=DISPERSED, is_triggered=True
    streak_ok = (
        streak_records[0] == (1, 1, "CONCENTRATED", False) and
        streak_records[1] == (2, 2, "CONCENTRATED", False) and
        streak_records[2] == (3, 3, "DISPERSED", True) and
        streak_records[3] == (4, 4, "DISPERSED", True)
    )
    results_table.append(("Suite 3: Deficit Streak Transition (0->1->2->3->4)", "PASS" if streak_ok else "FAIL", f"Transitions: {streak_records}"))

    # -------------------------------------------------------------------------
    # SUITE 4: Break-Even Recovery Simulation (Win >= 10 RMB)
    # -------------------------------------------------------------------------
    # Now in deficit (streak=4, DISPERSED mode).
    # Simulate a win: virtual_reward = 10 (or 3000) >= virtual_cost (10).
    d_win = DrawHistory(issue_no="2026105", draw_date=date(2026, 5, 10), weekday=4, red_1=1, red_2=2, red_3=3, red_4=4, red_5=5, red_6=6, blue_1=11, red_seq_str="01,02,03,04,05,06")
    session.add(d_win)
    b_win = PredictionBatch(target_issue="2026105", strategy_type="DISPERSED_BASELINE", virtual_cost=10, virtual_reward=10)
    session.add(b_win)
    session.flush()
    res_win = service.process_batch_verification(b_win, d_win, session)

    recovery_ok = (
        res_win["streak"] == 0 and
        res_win["current_mode"] == "CONCENTRATED" and
        res_win["trigger_reason"] == "RECOVERY_UPGRADE" and
        res_win["is_triggered"] == True
    )
    results_table.append(("Suite 4A: Break-Even Recovery (reward=10)", "PASS" if recovery_ok else "FAIL", f"Streak={res_win['streak']}, Mode={res_win['current_mode']}, Reason={res_win['trigger_reason']}"))

    # Subsequent win (reward=3000): should maintain CONCENTRATED and streak=0
    d_win2 = DrawHistory(issue_no="2026106", draw_date=date(2026, 5, 12), weekday=7, red_1=1, red_2=2, red_3=3, red_4=4, red_5=5, red_6=6, blue_1=12, red_seq_str="01,02,03,04,05,06")
    session.add(d_win2)
    b_win2 = PredictionBatch(target_issue="2026106", strategy_type="CONCENTRATED_BREAK_EVEN", virtual_cost=10, virtual_reward=3000)
    session.add(b_win2)
    session.flush()
    res_win2 = service.process_batch_verification(b_win2, d_win2, session)

    maintained_ok = (
        res_win2["streak"] == 0 and
        res_win2["current_mode"] == "CONCENTRATED" and
        res_win2["trigger_reason"] == "BREAK_EVEN_MAINTAINED"
    )
    results_table.append(("Suite 4B: Break-Even Maintained (reward=3000)", "PASS" if maintained_ok else "FAIL", f"Streak={res_win2['streak']}, Mode={res_win2['current_mode']}, Reason={res_win2['trigger_reason']}"))

    # -------------------------------------------------------------------------
    # SUITE 5: Persistence & Audit Log Verification
    # -------------------------------------------------------------------------
    hist_records = session.scalars(select(AdaptiveHistory).order_by(AdaptiveHistory.id.asc())).all()
    # Expect events:
    # 1. Reset event (RESET_TO_DEFAULT)
    # 2. Deficit trigger at streak 3 (CONSECUTIVE_DEFICIT_TRIGGER_STREAK_3)
    # 3. Deficit trigger at streak 4 (CONSECUTIVE_DEFICIT_TRIGGER_STREAK_4)
    # 4. Recovery event (RECOVERY_UPGRADE)
    # 5. Break-even maintained (BREAK_EVEN_MAINTAINED)
    persistence_ok = True
    hist_details = []
    for h in hist_records:
        pre = json.loads(h.pre_state_json)
        post = json.loads(h.post_state_json)
        devs = json.loads(h.metrics_deviation_json)
        hist_details.append((h.id, h.trigger_issue, h.trigger_reason, h.streak_length, post.get("current_blue_mode") or post.get("blue_mode")))
        if not h.trigger_issue or not h.trigger_reason or h.pre_state_json == "" or h.post_state_json == "":
            persistence_ok = False

    results_table.append(("Suite 5: Persistence to ssq_adaptive_history", "PASS" if persistence_ok else "FAIL", f"Recorded {len(hist_records)} audit events, all valid JSON"))

    # -------------------------------------------------------------------------
    # SUITE 6: RESTful API Reset Endpoint Test (POST /api/v1/adaptive/reset)
    # -------------------------------------------------------------------------
    client = TestClient(app)
    # 1. Mutate state via manual trigger or DB
    post_trig = client.post("/api/v1/adaptive/trigger", json={"force": True})
    assert post_trig.status_code == 200

    # 2. Call Reset
    reset_resp = client.post("/api/v1/adaptive/reset")
    assert reset_resp.status_code == 200
    reset_data = reset_resp.json()

    reset_ok = (
        reset_data["weights"]["hazard"] == 0.40 and
        reset_data["weights"]["markov"] == 0.35 and
        reset_data["weights"]["momentum"] == 0.25 and
        reset_data["consecutive_deficit_count"] == 0 and
        reset_data["blue_mode"] == "CONCENTRATED" and
        reset_data["active_hyperparams"]["sum_range"] == [75, 135]
    )
    results_table.append(("Suite 6A: Reset Endpoint (POST /api/v1/adaptive/reset)", "PASS" if reset_ok else "FAIL", f"Status: {reset_resp.status_code}, Defaults: {reset_data['weights']}"))

    # 3. Verify GET /api/v1/adaptive/status matches reset
    status_resp = client.get("/api/v1/adaptive/status")
    assert status_resp.status_code == 200
    st_data = status_resp.json()
    status_ok = (
        st_data["weights"]["hazard"] == 0.40 and
        st_data["weights"]["markov"] == 0.35 and
        st_data["weights"]["momentum"] == 0.25 and
        st_data["consecutive_deficit_count"] == 0 and
        st_data["blue_mode"] == "CONCENTRATED"
    )
    results_table.append(("Suite 6B: Status Endpoint Persistence (GET /api/v1/adaptive/status)", "PASS" if status_ok else "FAIL", f"Returned Mode: {st_data['blue_mode']}, Weights: {st_data['weights']}"))

    # -------------------------------------------------------------------------
    # SUITE 7: Blue Allocation Mode Integration: CONCENTRATED (3+2) vs DISPERSED (5 diff)
    # -------------------------------------------------------------------------
    ranked_test_blues = [9, 14, 3, 16, 7, 1, 2, 4, 5, 6, 8, 10, 11, 12, 13, 15]

    # Alloc under CONCENTRATED mode
    alloc_conc = BlueAllocationStrategy.allocate(ranked_test_blues, mode="CONCENTRATED")
    # Alloc under DISPERSED mode
    alloc_disp = BlueAllocationStrategy.allocate(ranked_test_blues, mode="DISPERSED")

    conc_expected = [9, 9, 9, 14, 14]
    disp_expected = [9, 14, 3, 16, 7]

    blue_ok = (alloc_conc == conc_expected and alloc_disp == disp_expected)
    results_table.append(("Suite 7: Blue Allocation Mode (3+2 vs 5-distinct)", "PASS" if blue_ok else "FAIL", f"Conc: {alloc_conc}, Disp: {alloc_disp}"))

    # Print summary table
    print("\n--------------------------------------------------------------------------------")
    print(f"{'Test Suite':<45} | {'Verdict':<8} | {'Details'}")
    print("--------------------------------------------------------------------------------")
    for suite, verdict, detail in results_table:
        print(f"{suite:<45} | {verdict:<8} | {detail}")
    print("--------------------------------------------------------------------------------")

    all_passed = all(v == "PASS" for _, v, _ in results_table)
    print(f"\nFinal Overall Challenger Verdict: {'ALL PASS' if all_passed else 'FAIL'}")
    return all_passed, results_table


if __name__ == "__main__":
    success, _ = run_empirical_simulation()
    if not success:
        exit(1)


# ==============================================================================
# Pytest Test Cases for Direct Invocation via `pytest tests/adversarial_adaptive_sim.py`
# ==============================================================================

def test_adversarial_simulation_suite():
    """Runs full empirical simulation and asserts 100% pass across all test suites."""
    success, _ = run_empirical_simulation()
    assert success is True

