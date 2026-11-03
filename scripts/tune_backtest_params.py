"""
scripts/tune_backtest_params.py

Benchmark script testing different hyperparameter configurations:
1. Pool size (13 vs 14 vs 15 vs 16)
2. Combination sorting by neural probability sum vs unsorted
3. Blue allocation modes: AUTO vs BALANCED (2+2+1) vs CONCENTRATED (3+2) vs DISPERSED (5 distinct)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import itertools
import numpy as np
from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models import DrawHistory
from backend.app.services.neural_model import SSQNeuralPredictor
from backend.app.services.wheeling_engine import RedWheelingEngine, StatisticalFilters
from backend.app.services.quant_models import BlueAllocationStrategy
from backend.app.services.verifier import VerificationService


def run_tuning():
    session = SessionLocal()
    draws = session.scalars(select(DrawHistory).order_by(DrawHistory.issue_no.asc())).all()
    session.close()

    train_draws = draws[:3300]
    test_draws = draws[3300:]
    test_size = len(test_draws)

    predictor = SSQNeuralPredictor(model_path="data/ssq_neural_model.pt")

    configs = [
        {"name": "Config A: Pool 13 (Unsorted Combinations, AUTO Blue)", "pool_size": 13, "sorted_combos": False, "blue_mode": "AUTO"},
        {"name": "Config B: Pool 13 (Sorted by NN Score, AUTO Blue)", "pool_size": 13, "sorted_combos": True, "blue_mode": "AUTO"},
        {"name": "Config C: Pool 14 (Sorted by NN Score, AUTO Blue)", "pool_size": 14, "sorted_combos": True, "blue_mode": "AUTO"},
        {"name": "Config D: Pool 14 (Sorted by NN Score, Concentrated 3+2 Blue)", "pool_size": 14, "sorted_combos": True, "blue_mode": "CONCENTRATED"},
        {"name": "Config E: Pool 15 (Sorted by NN Score, Balanced 2+2+1 Blue)", "pool_size": 15, "sorted_combos": True, "blue_mode": "BALANCED"},
        {"name": "Config F: Pool 15 (Sorted by NN Score, Concentrated 3+2 Blue)", "pool_size": 15, "sorted_combos": True, "blue_mode": "CONCENTRATED"},
    ]

    print("=" * 80)
    print(f"HYPERPARAMETER TUNING BENCHMARK ({test_size} TEST DRAWS: 2025055 to 2026124)")
    print("=" * 80)

    for cfg in configs:
        total_cost = 0
        total_reward = 0
        break_even_count = 0
        prizes = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}

        for i in range(3300, len(draws)):
            hist = draws[:i]
            actual = draws[i]
            r_p, b_p = predictor.predict_probabilities(hist)
            engine = RedWheelingEngine([d.reds for d in hist])
            pool = engine.select_zero_core_pool(red_probs=r_p, pool_size=cfg["pool_size"])

            # Generate and validate combinations
            central_cands = []
            wing_cands = []
            for comb in itertools.combinations(pool, 6):
                c = sorted(comb)
                v_c, _ = StatisticalFilters.is_valid_line(c, hist[-1].reds, profile="CENTRAL")
                if v_c:
                    score = sum(float(r_p[b - 1]) for b in c) if cfg["sorted_combos"] else 0.0
                    central_cands.append((c, score))
                v_w, _ = StatisticalFilters.is_valid_line(c, hist[-1].reds, profile="WING")
                if v_w:
                    score = sum(float(r_p[b - 1]) for b in c) if cfg["sorted_combos"] else 0.0
                    wing_cands.append((c, score))

            if cfg["sorted_combos"]:
                central_cands.sort(key=lambda x: -x[1])
                wing_cands.sort(key=lambda x: -x[1])

            chosen_lines = []
            ball_counts = {b: 0 for b in pool}
            for cand, _ in central_cands:
                if len(chosen_lines) == 3:
                    break
                if any(len(set(cand) & set(prev)) > 3 for prev in chosen_lines):
                    continue
                if any(ball_counts[b] >= 3 for b in cand):
                    continue
                chosen_lines.append(cand)
                for b in cand:
                    ball_counts[b] += 1

            if len(chosen_lines) < 3:
                for cand, _ in central_cands:
                    if len(chosen_lines) == 3:
                        break
                    if cand not in chosen_lines and all(len(set(cand) & set(prev)) <= 4 for prev in chosen_lines):
                        chosen_lines.append(cand)
                        for b in cand:
                            ball_counts[b] += 1

            rem_wing = [c for c, _ in wing_cands if c not in chosen_lines]
            rem_wing.sort(key=lambda c: -sum(1 for b in c if ball_counts[b] < 2))
            for cand in rem_wing:
                if len(chosen_lines) == 5:
                    break
                if any(len(set(cand) & set(prev)) > 4 for prev in chosen_lines):
                    continue
                chosen_lines.append(cand)
                for b in cand:
                    ball_counts[b] += 1

            while len(chosen_lines) < 5:
                chosen_lines.append(sorted(pool[:6]))

            ranked_blues = (np.argsort(b_p)[::-1] + 1).tolist()
            alloc_blues = BlueAllocationStrategy.allocate(ranked_blues, b_p, mode=cfg["blue_mode"])

            issue_reward = 0
            for idx in range(5):
                r_line = chosen_lines[idx]
                b_line = alloc_blues[idx]
                audit_res = VerificationService.audit_ticket(
                    r_line, b_line, actual.reds, actual.blue_1,
                    first_prize_amt=actual.first_prize_amount or 5000000,
                    second_prize_amt=actual.second_prize_amount or 100000,
                )
                issue_reward += audit_res["prize_amount"]
                lvl = audit_res["prize_level"]
                if lvl in prizes:
                    prizes[lvl] += 1

            total_cost += 10
            total_reward += issue_reward
            if issue_reward >= 10:
                break_even_count += 1

        roi = (total_reward - total_cost) / total_cost * 100.0
        be_rate = (break_even_count / test_size) * 100.0
        print(f"\n{cfg['name']}:")
        print(f"  Total Cost   : {total_cost:,} RMB")
        print(f"  Total Reward : {total_reward:,} RMB")
        print(f"  Net Profit   : {total_reward - total_cost:+,} RMB")
        print(f"  Simulated ROI: {roi:+.2f}%")
        print(f"  Break-Even   : {break_even_count}/{test_size} ({be_rate:.2f}%)")
        print(f"  Prizes Hit   : Level 4={prizes[4]}, Level 5={prizes[5]}, Level 6={prizes[6]}")


if __name__ == "__main__":
    run_tuning()
