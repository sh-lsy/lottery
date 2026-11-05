"""
scripts/run_walkforward_backtest.py

Rigorous walk-forward backtest script comparing dual models side-by-side across 221 test draws:
- Model 1: 纯量化神经网络优化排序版 (Pure Neural Net with Probability-Ranked Combinations)
- Model 2: 周易八卦五行双轨融合版 (Zhouyi Bagua & Wuxing Metaphysics Dual-Track Fusion)

Dataset Partition:
- Training: First 3,300 draws (2003001 to 2025054)
- Testing : Remaining 221 draws (2025055 to 2026124) with online self-evolution
"""

import sys
import os
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
from typing import Dict, List, Any
import numpy as np
import torch
from sqlalchemy import select

from backend.app.database import SessionLocal
from backend.app.models import DrawHistory
from backend.app.services.neural_model import SSQNeuralPredictor
from backend.app.services.metaphysics_engine import MetaphysicsEngine
from backend.app.services.wheeling_engine import RedWheelingEngine
from backend.app.services.quant_models import BlueScoringEngine, BlueAllocationStrategy
from backend.app.services.verifier import VerificationService


def run_benchmark():
    print("=" * 90)
    print("SSQ DUAL-MODEL WALK-FORWARD BENCHMARK (3300 Train / 221 Test with Online Evolution)")
    print("Version 1: 纯量化神经网络优化版 vs Version 2: 周易八卦五行双轨融合版")
    print("=" * 90)

    torch.manual_seed(42)
    np.random.seed(42)

    session = SessionLocal()
    draws = session.scalars(select(DrawHistory).order_by(DrawHistory.issue_no.asc())).all()
    session.close()

    total_draws = len(draws)
    train_size = 3300
    test_size = total_draws - train_size

    print(f"Total historical draws in database : {total_draws}")
    print(f"Training partition (Draws 1..3300) : {draws[0].issue_no} -> {draws[train_size - 1].issue_no}")
    print(f"Testing partition  (Draws 3301..{total_draws}): {draws[train_size].issue_no} -> {draws[-1].issue_no} ({test_size} draws)")

    # 1. Base Model Pre-training on CPU
    model_path = "data/ssq_neural_model_backtest.pt"
    print("\n[Step 1] Training base neural network model on first 3,300 draws...")
    predictor = SSQNeuralPredictor(model_path=model_path)
    t0 = time.time()
    res = predictor.train_base_model(draws[:train_size], epochs=10, batch_size=64, lr=0.002, verbose=True)
    t_train = time.time() - t0
    model_mb = os.path.getsize(model_path) / (1024 * 1024)
    print(f"Base model ready in {t_train:.1f}s! Size: {model_mb:.2f} MB, Final Loss: {res['final_loss']:.4f}")

    # Trackers for both models
    models = {
        "V1_PURE_QUANT": {
            "name": "纯量化神经网络优化版 (Pure Quant)",
            "total_cost": 0,
            "total_reward": 0,
            "break_even_count": 0,
            "blue_hit_count": 0,
            "prize_counts": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 0: 0},
            "red_hit_max_counts": {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0},
            "rewards_history": [],
        },
        "V2_METAPHYSICS": {
            "name": "周易八卦五行双轨融合版 (Bagua Metaphysics)",
            "total_cost": 0,
            "total_reward": 0,
            "break_even_count": 0,
            "blue_hit_count": 0,
            "prize_counts": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 0: 0},
            "red_hit_max_counts": {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0},
            "rewards_history": [],
        },
    }

    r9 = {
        "V1": {"cost": 0, "reward": 0, "be": 0, "blue": 0, "prizes": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}},
        "V2": {"cost": 0, "reward": 0, "be": 0, "blue": 0, "prizes": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}},
    }

    # 2. Sequential walk-forward evaluation across 221 draws
    print(f"\n[Step 2] Executing sequential walk-forward backtest across {test_size} draws with online self-evolution...")
    history_window = list(draws[:train_size])
    t_eval_start = time.time()

    for idx in range(train_size, total_draws):
        actual_draw = draws[idx]
        target_issue = actual_draw.issue_no
        draw_date = str(actual_draw.draw_date) if actual_draw.draw_date else "2026-01-01"

        # A. Base Neural Inference
        nn_red_probs, nn_blue_probs = predictor.predict_probabilities(history_window)
        history_reds = [d.reds for d in history_window]
        red_engine = RedWheelingEngine(history_reds)

        # B. Metaphysics Inference
        meta_red_probs, meta_blue_probs, meta_info = MetaphysicsEngine.compute_metaphysics_probabilities(
            draw_date, target_issue
        )

        # Blend: 70% Neural Net + 30% Zhouyi Bagua Metaphysics
        meta_fused_red = 0.70 * nn_red_probs + 0.30 * np.array(meta_red_probs)
        meta_fused_blue = 0.70 * nn_blue_probs + 0.30 * np.array(meta_blue_probs)

        # C. Generate 5-line tickets for both models
        # Model 1: Pure Quant (Neural + Dynamic Quant Omission/Momentum)
        history_blues = [d.blue_1 for d in history_window]
        q_blue_engine = BlueScoringEngine(history_blues)
        q_blue_probs, _ = q_blue_engine.compute_ensemble_probabilities(weights=(0.40, 0.25, 0.20, 0.15), tau=0.75)

        omiss_scores = np.zeros(33)
        for b in range(1, 34):
            last_idx = -1
            for h_i in range(len(history_window) - 1, -1, -1):
                if b in history_window[h_i].reds:
                    last_idx = h_i
                    break
            o = (len(history_window) - 1 - last_idx) if last_idx != -1 else len(history_window)
            omiss_scores[b - 1] = np.exp(-((o - 5.5)**2) / 32.0)
        omiss_probs = omiss_scores / np.sum(omiss_scores)

        v1_fused_red = 0.65 * nn_red_probs + 0.35 * omiss_probs
        v1_fused_blue = 0.50 * nn_blue_probs + 0.50 * q_blue_probs
        v1_ranked_blues = (np.argsort(v1_fused_blue)[::-1] + 1).tolist()
        v1_red_lines = red_engine.generate_5_lines_zero_core(red_probs=v1_fused_red)
        v1_blues = BlueAllocationStrategy.allocate(v1_ranked_blues, probs=v1_fused_blue, mode="BALANCED")

        # Model 2: Bagua Metaphysics
        v2_ranked_blues = (np.argsort(meta_fused_blue)[::-1] + 1).tolist()
        v2_red_lines = red_engine.generate_5_lines_zero_core(red_probs=meta_fused_red)
        v2_blues = BlueAllocationStrategy.allocate(v2_ranked_blues, probs=meta_fused_blue, mode="BALANCED")

        # D. Audit Model 1
        m1 = models["V1_PURE_QUANT"]
        m1["total_cost"] += 10
        m1_reward = 0
        m1_blue_hit = False
        m1_max_red = 0
        for note_idx in range(5):
            audit = VerificationService.audit_ticket(
                v1_red_lines[note_idx], v1_blues[note_idx],
                actual_draw.reds, actual_draw.blue_1,
                first_prize_amt=actual_draw.first_prize_amount,
                second_prize_amt=actual_draw.second_prize_amount,
            )
            m1_reward += audit["payout"]
            if audit["payout"] >= 200:
                print(f"!!! V1 BIG PRIZE: Issue {actual_draw.issue_no} (offset {idx-train_size}), Prize Level {audit['prize_level']}, Payout {audit['payout']}, Predicted: {v1_red_lines[note_idx]} + {v1_blues[note_idx]}, Actual: {actual_draw.reds} + {actual_draw.blue_1}")
            if audit["hit_blue"]:
                m1_blue_hit = True
            m1_max_red = max(m1_max_red, audit["hit_red_count"])
            m1["prize_counts"][audit["prize_level"]] += 1

        m1["total_reward"] += m1_reward
        m1["rewards_history"].append(m1_reward)
        if m1_reward >= 10:
            m1["break_even_count"] += 1
        if m1_blue_hit:
            m1["blue_hit_count"] += 1
        m1["red_hit_max_counts"][m1_max_red] += 1

        # E. Audit Model 2
        m2 = models["V2_METAPHYSICS"]
        m2["total_cost"] += 10
        m2_reward = 0
        m2_blue_hit = False
        m2_max_red = 0
        for note_idx in range(5):
            audit = VerificationService.audit_ticket(
                v2_red_lines[note_idx], v2_blues[note_idx],
                actual_draw.reds, actual_draw.blue_1,
                first_prize_amt=actual_draw.first_prize_amount,
                second_prize_amt=actual_draw.second_prize_amount,
            )
            m2_reward += audit["payout"]
            if audit["payout"] >= 200:
                print(f"!!! V2 BIG PRIZE: Issue {actual_draw.issue_no} (offset {idx-train_size}), Prize Level {audit['prize_level']}, Payout {audit['payout']}, Predicted: {v2_red_lines[note_idx]} + {v2_blues[note_idx]}, Actual: {actual_draw.reds} + {actual_draw.blue_1}")
            if audit["hit_blue"]:
                m2_blue_hit = True
            m2_max_red = max(m2_max_red, audit["hit_red_count"])
            m2["prize_counts"][audit["prize_level"]] += 1

        m2["total_reward"] += m2_reward
        m2["rewards_history"].append(m2_reward)
        if m2_reward >= 10:
            m2["break_even_count"] += 1
        if m2_blue_hit:
            m2["blue_hit_count"] += 1
        m2["red_hit_max_counts"][m2_max_red] += 1

        # Track recent 9 issues slice (Issues 2026116 to 2026124)
        if idx >= total_draws - 9:
            r9["V1"]["cost"] += 10
            r9["V1"]["reward"] += m1_reward
            if m1_reward >= 10: r9["V1"]["be"] += 1
            if m1_blue_hit: r9["V1"]["blue"] += 1

            r9["V2"]["cost"] += 10
            r9["V2"]["reward"] += m2_reward
            if m2_reward >= 10: r9["V2"]["be"] += 1
            if m2_blue_hit: r9["V2"]["blue"] += 1

        # F. Online Self-Evolution with actual_draw (calibrated conservative lr to preserve representations)
        _ = predictor.online_update(actual_draw, history_window, lr=1e-4, steps=1)
        history_window.append(actual_draw)

        if (idx - train_size + 1) % 50 == 0 or idx == total_draws - 1:
            curr_n = idx - train_size + 1
            print(f"  Processed {curr_n}/{test_size} issues | V1 Reward: {m1['total_reward']} RMB (BE: {m1['break_even_count']}) | V2 Metaphysics Reward: {m2['total_reward']} RMB (BE: {m2['break_even_count']})")

    t_eval = time.time() - t_eval_start

    # Track recent 9 issues slice (Issues 2026116 to 2026124)
    r9_start_idx = total_draws - 9
    r9_issues = draws[r9_start_idx:]

    # Clean up temp backtest checkpoint
    if os.path.exists(model_path):
        try:
            os.remove(model_path)
        except Exception:
            pass

    # 3. Print Final Comparison Table
    print("\n" + "=" * 90)
    print("DUAL-MODEL 221-ISSUE WALK-FORWARD BENCHMARK RESULTS (2025055 to 2026124)")
    print("=" * 90)
    print(f"{'Performance Metric':<30} | {'V1: 纯量化神经网络优化版':<26} | {'V2: 周易八卦五行双轨版':<26}")
    print("-" * 90)

    for k in ["V1_PURE_QUANT", "V2_METAPHYSICS"]:
        m = models[k]
        m["net_profit"] = m["total_reward"] - m["total_cost"]
        m["roi"] = (m["net_profit"] / m["total_cost"]) * 100.0
        m["be_rate"] = (m["break_even_count"] / test_size) * 100.0
        m["blue_rate"] = (m["blue_hit_count"] / test_size) * 100.0

    m1, m2 = models["V1_PURE_QUANT"], models["V2_METAPHYSICS"]

    print(f"{'Total Cost (总投入)':<30} | {m1['total_cost']:>10,} RMB              | {m2['total_cost']:>10,} RMB")
    print(f"{'Total Reward (总奖金)':<30} | {m1['total_reward']:>10,} RMB              | {m2['total_reward']:>10,} RMB")
    print(f"{'Net Profit (净利润)':<30} | {m1['net_profit']:>+10,} RMB              | {m2['net_profit']:>+10,} RMB")
    print(f"{'Simulated ROI (投资回报率)':<30} | {m1['roi']:>+9.2f}%               | {m2['roi']:>+9.2f}%")
    print(f"{'Break-Even Rate (保本率 >=10元)':<30} | {m1['break_even_count']}/{test_size} ({m1['be_rate']:.1f}%)           | {m2['break_even_count']}/{test_size} ({m2['be_rate']:.1f}%)")
    print(f"{'Blue Hit Rate (蓝球命中率)':<30} | {m1['blue_hit_count']}/{test_size} ({m1['blue_rate']:.1f}%)           | {m2['blue_hit_count']}/{test_size} ({m2['blue_rate']:.1f}%)")
    print("-" * 90)
    print("Prize Tiers Breakdown (Across 1,105 Notes):")
    tier_desc = {
        1: "一等奖 (浮动头奖)",
        2: "二等奖 (浮动二奖)",
        3: "三等奖 (3,000元)",
        4: "四等奖 (200元)",
        5: "五等奖 (10元)",
        6: "六等奖 (5元)",
    }
    for lvl in [1, 2, 3, 4, 5, 6]:
        desc = tier_desc[lvl]
        if lvl >= 3 or m1['prize_counts'][lvl] > 0 or m2['prize_counts'][lvl] > 0:
            print(f"  - {desc:<24} | {m1['prize_counts'][lvl]:>6} 注                 | {m2['prize_counts'][lvl]:>6} 注")

    print("-" * 90)
    print(f"Evaluation finished in {t_eval:.2f}s ({t_eval/test_size*1000:.1f}ms per draw).")
    print("=" * 90)

    # 4. Print Recent 9-Issue Slice (User's Empirical Test Window: Issues 2026116 to 2026124)
    print("\n" + "=" * 90)
    print("RECENT 9-ISSUE SLICE BENCHMARK (User Test Issues: 2026116 to 2026124)")
    print("=" * 90)
    print(f"{'Performance Metric':<30} | {'V1: 纯量化神经网络优化版':<26} | {'V2: 周易八卦五行双轨版':<26}")
    print("-" * 90)
    r1, r2 = r9["V1"], r9["V2"]
    roi_r1 = (r1["reward"] - r1["cost"]) / r1["cost"] * 100.0 if r1["cost"] > 0 else 0.0
    roi_r2 = (r2["reward"] - r2["cost"]) / r2["cost"] * 100.0 if r2["cost"] > 0 else 0.0
    print(f"{'9-Issue Cost (投入 9期)':<30} | {r1['cost']:>10,} RMB              | {r2['cost']:>10,} RMB")
    print(f"{'9-Issue Reward (累计奖金)':<30} | {r1['reward']:>10,} RMB              | {r2['reward']:>10,} RMB")
    print(f"{'9-Issue Net Profit (净盈亏)':<30} | {r1['reward'] - r1['cost']:>+10,} RMB              | {r2['reward'] - r2['cost']:>+10,} RMB")
    print(f"{'9-Issue ROI (投资回报率)':<30} | {roi_r1:>+9.2f}%               | {roi_r2:>+9.2f}%")
    print(f"{'9-Issue Break-Even Rate':<30} | {r1['be']}/9 ({r1['be']/9*100:.1f}%)                 | {r2['be']}/9 ({r2['be']/9*100:.1f}%)")
    print(f"{'9-Issue Blue Hit Rate':<30} | {r1['blue']}/9 ({r1['blue']/9*100:.1f}%)               | {r2['blue']}/9 ({r2['blue']/9*100:.1f}%)")
    print("=" * 90)

    # 5. Consecutive 5-Issue Purchase & Recovery Analysis (User Goal Benchmark)
    print("\n" + "=" * 90)
    print("CONSECUTIVE 5-ISSUE RECOVERY ANALYSIS (5 Draws / 25 Notes / Cost 50 RMB per cycle)")
    print("=" * 90)
    print(f"{'Performance Metric':<30} | {'V1: 纯量化优化版':<26} | {'V2: 周易八卦五行双轨版':<26}")
    print("-" * 90)

    for k in ["V1_PURE_QUANT", "V2_METAPHYSICS"]:
        m = models[k]
        rews = np.array(m["rewards_history"])
        rolling_5 = np.convolve(rews, np.ones(5, dtype=int), 'valid')
        blocks_5 = [int(np.sum(rews[i:i+5])) for i in range(0, len(rews)-4, 5)]
        m["recovery_5_issue"] = {
            "rolling_windows": len(rolling_5),
            "rolling_recovered": int(np.sum(rolling_5 >= 50)),
            "rolling_recovery_rate": float(np.mean(rolling_5 >= 50) * 100.0),
            "block_count": len(blocks_5),
            "blocks_recovered": int(sum(x >= 50 for x in blocks_5)),
            "block_recovery_rate": float(np.mean([x >= 50 for x in blocks_5]) * 100.0),
            "avg_5_issue_reward": float(np.mean(rolling_5)),
            "max_5_issue_reward": int(np.max(rolling_5)),
        }

    rec1 = models["V1_PURE_QUANT"]["recovery_5_issue"]
    rec2 = models["V2_METAPHYSICS"]["recovery_5_issue"]
    print(f"{'5-Issue Rolling Recovery (>=50元)':<28} | {rec1['rolling_recovered']}/{rec1['rolling_windows']} ({rec1['rolling_recovery_rate']:.1f}%)               | {rec2['rolling_recovered']}/{rec2['rolling_windows']} ({rec2['rolling_recovery_rate']:.1f}%)")
    print(f"{'5-Issue Blocks Recovery (>=50元)':<28} | {rec1['blocks_recovered']}/{rec1['block_count']} ({rec1['block_recovery_rate']:.1f}%)                 | {rec2['blocks_recovered']}/{rec2['block_count']} ({rec2['block_recovery_rate']:.1f}%)")
    print(f"{'Average 5-Issue Return (5期均收益)':<28} | {rec1['avg_5_issue_reward']:>9.1f} RMB              | {rec2['avg_5_issue_reward']:>9.1f} RMB")
    print(f"{'Max 5-Issue Return (5期最高收益)':<28} | {rec1['max_5_issue_reward']:>9,} RMB              | {rec2['max_5_issue_reward']:>9,} RMB")
    print("=" * 90)

    return models


if __name__ == "__main__":
    run_benchmark()
