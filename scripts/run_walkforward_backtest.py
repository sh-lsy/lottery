"""
Rigorous walk-forward backtest script:
- Train base neural model on first 3,300 draws (2003001 to 2025054).
- Sequentially evaluate on remaining 221 draws (2025055 to 2026124).
- For each test draw:
  1. Strictly zero-lookahead prediction (only draws[:t] available).
  2. Evaluates 5-line ticket against actual draw.
  3. Records Break-Even (Reward >= 10 RMB), Blue hits, and Prize levels.
  4. Online incremental fine-tuning (model self-evolves with actual draw before moving to t+1).
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
from typing import Dict, List, Any
import numpy as np
from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models import DrawHistory
from backend.app.services.neural_model import SSQNeuralPredictor
from backend.app.services.wheeling_engine import RedWheelingEngine
from backend.app.services.quant_models import BlueAllocationStrategy
from backend.app.services.verifier import VerificationService


def run_benchmark():
    print("=" * 80)
    print("SSQ-Quant Walk-Forward Backtest Benchmark (3300 Train / 221 Test with Online Evolution)")
    print("=" * 80)

    session = SessionLocal()
    draws = session.scalars(select(DrawHistory).order_by(DrawHistory.issue_no.asc())).all()
    session.close()

    total_draws = len(draws)
    train_size = 3300
    test_size = total_draws - train_size

    print(f"Total historical draws in database : {total_draws}")
    print(f"Training partition (Draws 1..3300) : {draws[0].issue_no} -> {draws[train_size - 1].issue_no}")
    print(f"Testing partition  (Draws 3301..{total_draws}): {draws[train_size].issue_no} -> {draws[-1].issue_no} ({test_size} draws)")

    # 1. Pre-train base model
    model_path = "data/ssq_neural_model_backtest.pt"
    print("\n[Step 1] Training base neural network model on first 3,300 draws...")
    predictor = SSQNeuralPredictor(model_path=model_path)
    t0 = time.time()
    res = predictor.train_base_model(draws[:train_size], epochs=10, batch_size=64, lr=0.002, verbose=True)
    t_train = time.time() - t0
    model_mb = os.path.getsize(model_path) / (1024 * 1024)
    print(f"Base model training complete in {t_train:.1f}s! Model size: {model_mb:.2f} MB, Final Loss: {res['final_loss']:.4f}")

    # 2. Sequential walk-forward evaluation
    print(f"\n[Step 2] Executing sequential walk-forward backtest across {test_size} draws with online self-evolution...")

    total_cost = 0
    total_reward = 0
    break_even_count = 0     # reward >= 10
    any_hit_count = 0        # reward >= 5
    blue_hit_count = 0       # at least 1 blue hit in 5 notes

    prize_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 0: 0}
    red_hit_max_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}

    history_window = list(draws[:train_size])

    t_eval_start = time.time()
    for idx in range(train_size, total_draws):
        actual_draw = draws[idx]
        target_issue = actual_draw.issue_no

        # A. Inference (Strictly using history_window up to t-1)
        red_probs, blue_probs = predictor.predict_probabilities(history_window)
        ranked_blues = (np.argsort(blue_probs)[::-1] + 1).tolist()

        # B. Strategy allocation (Zero-Core Orthogonal Wheel + Break-Even Allocation)
        history_reds = [d.reds for d in history_window]
        red_engine = RedWheelingEngine(history_reds)
        red_lines = red_engine.generate_5_lines_zero_core(red_probs=red_probs)
        allocated_blues = BlueAllocationStrategy.allocate(ranked_blues, probs=blue_probs, mode="DYNAMIC_THRESHOLD")

        # C. Verification against actual draw
        issue_cost = 10
        issue_reward = 0
        issue_blue_hit = False
        issue_max_red = 0

        for note_idx in range(5):
            line_reds = red_lines[note_idx]
            line_blue = allocated_blues[note_idx]
            audit = VerificationService.audit_ticket(
                line_reds,
                line_blue,
                actual_draw.reds,
                actual_draw.blue_1,
                first_prize_amt=actual_draw.first_prize_amount,
                second_prize_amt=actual_draw.second_prize_amount,
            )
            p_lvl = audit["prize_level"]
            payout = audit["payout"]
            issue_reward += payout

            if audit["hit_blue"]:
                issue_blue_hit = True
            issue_max_red = max(issue_max_red, audit["hit_red_count"])
            prize_counts[p_lvl] += 1

        total_cost += issue_cost
        total_reward += issue_reward
        if issue_reward >= 10:
            break_even_count += 1
        if issue_reward >= 5:
            any_hit_count += 1
        if issue_blue_hit:
            blue_hit_count += 1
        red_hit_max_counts[issue_max_red] += 1

        # D. Online Self-Evolution: fine-tune model with actual_draw
        _ = predictor.online_update(actual_draw, history_window, lr=5e-4, steps=1)

        # Slide window forward
        history_window.append(actual_draw)

        if (idx - train_size + 1) % 50 == 0 or idx == total_draws - 1:
            curr_n = idx - train_size + 1
            print(f"  Processed {curr_n}/{test_size} issues... Cumulative Reward: {total_reward} RMB (Cost: {curr_n * 10} RMB, Break-Even: {break_even_count}/{curr_n})")

    t_eval = time.time() - t_eval_start

    # 3. Print Final Summary Report
    net_profit = total_reward - total_cost
    roi = (net_profit / total_cost) * 100.0 if total_cost > 0 else 0.0
    be_rate = (break_even_count / test_size) * 100.0
    any_rate = (any_hit_count / test_size) * 100.0
    blue_rate = (blue_hit_count / test_size) * 100.0

    print("\n" + "=" * 80)
    print("WALK-FORWARD BACKTEST EMPIRICAL RESULTS (221 TEST ISSUES)")
    print("=" * 80)
    print(f"Total Test Issues Tested     : {test_size} issues (2025055 to 2026124)")
    print(f"Total Tickets Evaluated      : {test_size * 5} notes")
    print(f"Total Cost (投入)            : {total_cost:,} RMB (5 notes * 2 RMB * {test_size})")
    print(f"Total Reward (奖金)          : {total_reward:,} RMB")
    print(f"Net Profit (净盈亏)          : {net_profit:+,} RMB")
    print(f"Simulated ROI (投资回报率)   : {roi:+.2f}%")
    print("-" * 80)
    print(f"Break-Even Rate (保本率 >=10元) : {break_even_count}/{test_size} ({be_rate:.2f}%)")
    print(f"Any Win Rate   (中奖率 >=5元)  : {any_hit_count}/{test_size} ({any_rate:.2f}%)")
    print(f"Blue Ball Hit Rate (蓝球命中率) : {blue_hit_count}/{test_size} ({blue_rate:.2f}%) [Theoretical Single Note: 6.25%]")
    print("-" * 80)
    print("Prize Tiers Breakdown (Across 1,105 notes):")
    for lvl in [1, 2, 3, 4, 5, 6]:
        cnt = prize_counts[lvl]
        print(f"  Level {lvl} Prize: {cnt} notes")
    print(f"  Unmatched (Miss): {prize_counts[0]} notes")
    print("-" * 80)
    print("Max Red Hits Per Issue Distribution:")
    for h in range(7):
        print(f"  Max Red {h} Hits: {red_hit_max_counts[h]} issues ({red_hit_max_counts[h]/test_size:.1%})")
    print(f"\nBacktest evaluation completed in {t_eval:.2f}s ({t_eval/test_size*1000:.1f}ms per issue).")
    print("=" * 80)


if __name__ == "__main__":
    run_benchmark()
