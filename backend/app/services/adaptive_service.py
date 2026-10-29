"""
backend/app/services/adaptive_service.py

Adaptive Strategy Self-Evolution Loop and Dynamic Feedback Engine.
Implements:
1. Consecutive underperformance detection (K_t >= 3 consecutive draws with no break-even).
2. Dynamic cold/hot weight shifting between Cold Reversion (w_1) and Hot Momentum (w_3)
   using learning rate eta = 0.05 based on recent 5-draw omission mean m_bar.
3. Dynamic blue allocation mode switching (CONCENTRATED 3+2 <-> DISPERSED 5-distinct).
4. Feature deviation tracking (Sum, Odd/Even, Cold/Hot) and parameter feedback adjustments.
5. Persistent immutable state transitions to ssq_adaptive_history and singleton ssq_adaptive_state.
"""

from datetime import datetime
import json
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models import DrawHistory, PredictionBatch, PredictionItem, AdaptiveState, AdaptiveHistory


class AdaptiveService:
    """
    Adaptive self-evolution feedback service.
    Orchestrates closed-loop parameter adaptation based on prediction verification outcomes.
    """

    LEARNING_RATE: float = 0.05
    DEFAULT_WEIGHTS: Tuple[float, float, float] = (0.40, 0.35, 0.25)  # (hazard, markov, momentum)
    DEFAULT_LOSS_THRESHOLD: int = 3

    def __init__(self, session_factory=None):
        self.session_factory = session_factory or SessionLocal

    def get_or_create_state(self, session: Session) -> AdaptiveState:
        """
        Retrieves the active singleton AdaptiveState row or initializes it if not found.
        """
        state = session.scalar(select(AdaptiveState).filter(AdaptiveState.id == 1))
        if not state:
            state = AdaptiveState(
                id=1,
                consecutive_deficit_count=0,
                current_blue_mode="CONCENTRATED",
                current_strategy_mode="CONCENTRATED_BREAK_EVEN",
                loss_threshold=self.DEFAULT_LOSS_THRESHOLD,
                cold_reversion_weight=self.DEFAULT_WEIGHTS[0],
                markov_weight=self.DEFAULT_WEIGHTS[1],
                hot_momentum_weight=self.DEFAULT_WEIGHTS[2],
                temperature_tau=0.85,
                sum_bias=0.0,
                odd_bias=0.0,
                ac_min_override=6,
                sum_range_min=75,
                sum_range_max=135,
                last_trigger_issue=None,
                last_trigger_reason="INITIALIZED",
                evolution_version=1,
            )
            session.add(state)
            session.flush()
        return state

    def reset_state(self, session: Session) -> AdaptiveState:
        """
        Resets adaptive hyperparameters to baseline defaults and records a RESET event.
        """
        state = self.get_or_create_state(session)
        pre_state = state.to_dict()

        state.consecutive_deficit_count = 0
        state.current_blue_mode = "CONCENTRATED"
        state.current_strategy_mode = "CONCENTRATED_BREAK_EVEN"
        state.cold_reversion_weight = self.DEFAULT_WEIGHTS[0]
        state.markov_weight = self.DEFAULT_WEIGHTS[1]
        state.hot_momentum_weight = self.DEFAULT_WEIGHTS[2]
        state.temperature_tau = 0.85
        state.sum_bias = 0.0
        state.odd_bias = 0.0
        state.ac_min_override = 6
        state.sum_range_min = 75
        state.sum_range_max = 135
        state.last_trigger_reason = "MANUAL_RESET"
        state.evolution_version += 1

        post_state = state.to_dict()

        history_event = AdaptiveHistory(
            trigger_issue=state.last_trigger_issue or "MANUAL",
            trigger_reason="RESET_TO_DEFAULT",
            streak_length=0,
            pre_state_json=json.dumps(pre_state),
            post_state_json=json.dumps(post_state),
            metrics_deviation_json=json.dumps({}),
            reflection_notes="Adaptive parameters manually reset to canonical defaults (0.40, 0.35, 0.25) and CONCENTRATED mode.",
        )
        session.add(history_event)
        session.flush()
        return state

    @staticmethod
    def calculate_recent_blue_omission_mean(session: Session, target_draw_date=None, window: int = 5) -> float:
        """
        Calculates the mean historical omission of winning blue balls over the recent W draws.
        Formula: m_bar = (1/W) * sum(omission(a_blue, t-i))
        """
        stmt = select(DrawHistory).order_by(DrawHistory.issue_no.desc()).limit(window + 100)
        draws = session.scalars(stmt).all()
        if not draws:
            return 8.0  # theoretical mean omission

        recent_draws = draws[:window]
        all_draws_rev = list(reversed(draws))  # chronological

        omissions = []
        for i, d in enumerate(recent_draws):
            # find index in all_draws_rev
            pos = all_draws_rev.index(d)
            if pos <= 0:
                omissions.append(16.0)
                continue
            prev_blues = [all_draws_rev[j].blue_1 for j in range(pos)]
            b_val = d.blue_1
            if b_val in prev_blues:
                last_idx = max(loc for loc, val in enumerate(prev_blues) if val == b_val)
                omission = (len(prev_blues) - 1) - last_idx
            else:
                omission = len(prev_blues)
            omissions.append(float(omission))

        return float(np.mean(omissions)) if omissions else 8.0

    @staticmethod
    def compute_feature_deviations(
        batch: PredictionBatch,
        draw: DrawHistory,
        session: Session,
    ) -> Dict[str, float]:
        """
        Computes signed feature deviations between 5 predicted notes and authentic draw result:
        - delta_sum: mean(pred_sums) - actual_sum
        - delta_odd: mean(pred_odds) - actual_odd
        - delta_cold: mean(pred_colds) - actual_cold
        - delta_hot: mean(pred_hots) - actual_hot
        """
        # Actual draw metrics
        act_reds = set(draw.reds)
        act_sum = float(sum(draw.reds))
        act_odd = float(sum(1 for r in draw.reds if r % 2 == 1))

        # Determine red omissions prior to this draw
        prior_draws = session.scalars(
            select(DrawHistory)
            .filter(DrawHistory.issue_no < draw.issue_no)
            .order_by(DrawHistory.issue_no.asc())
        ).all()

        red_omissions = {}
        n_p = len(prior_draws)
        for b in range(1, 34):
            last_idx = -1
            for idx in range(n_p - 1, -1, -1):
                if b in prior_draws[idx].reds:
                    last_idx = idx
                    break
            red_omissions[b] = (n_p - 1 - last_idx) if last_idx != -1 else n_p

        hot_balls = {b for b, o in red_omissions.items() if o <= 4}
        cold_balls = {b for b, o in red_omissions.items() if o >= 10}

        act_hot = float(len(act_reds & hot_balls))
        act_cold = float(len(act_reds & cold_balls))

        pred_sums = []
        pred_odds = []
        pred_hots = []
        pred_colds = []

        for item in batch.items:
            r_set = set(item.reds)
            pred_sums.append(float(sum(item.reds)))
            pred_odds.append(float(sum(1 for r in item.reds if r % 2 == 1)))
            pred_hots.append(float(len(r_set & hot_balls)))
            pred_colds.append(float(len(r_set & cold_balls)))

        if not pred_sums:
            return {
                "delta_sum": 0.0,
                "delta_odd": 0.0,
                "delta_hot": 0.0,
                "delta_cold": 0.0,
            }

        return {
            "delta_sum": round(float(np.mean(pred_sums)) - act_sum, 2),
            "delta_odd": round(float(np.mean(pred_odds)) - act_odd, 2),
            "delta_hot": round(float(np.mean(pred_hots)) - act_hot, 2),
            "delta_cold": round(float(np.mean(pred_colds)) - act_cold, 2),
        }

    def process_batch_verification(
        self,
        batch: PredictionBatch,
        draw: DrawHistory,
        session: Session,
    ) -> Dict[str, Any]:
        """
        Executes adaptive feedback loop upon prediction batch verification.
        1. Evaluates break-even condition (virtual_reward >= virtual_cost).
        2. Updates consecutive deficit streak.
        3. If streak >= threshold: shifts cold/hot weights and switches blue mode.
        4. Calculates feature deviations and adjusts hyperparameter biases.
        5. Logs state evolution to ssq_adaptive_history.
        """
        state = self.get_or_create_state(session)
        pre_state = state.to_dict()

        is_break_even = bool(batch.virtual_reward >= batch.virtual_cost)
        deviations = self.compute_feature_deviations(batch, draw, session)
        state.last_trigger_issue = draw.issue_no

        action_notes = []
        trigger_reason = ""
        is_triggered = False

        if is_break_even:
            # Positive / Break-Even Feedback
            state.consecutive_deficit_count = 0
            if state.current_blue_mode != "CONCENTRATED":
                state.current_blue_mode = "CONCENTRATED"
                state.current_strategy_mode = "CONCENTRATED_BREAK_EVEN"
                action_notes.append("Break-even achieved. Upgraded blue allocation mode to CONCENTRATED (3+2).")
                trigger_reason = "RECOVERY_UPGRADE"
                is_triggered = True
            else:
                trigger_reason = "BREAK_EVEN_MAINTAINED"

            # Restore sum bias and bounds to canonical baseline upon break-even recovery
            if state.sum_bias != 0.0 or state.sum_range_min != 75 or state.sum_range_max != 135:
                state.sum_bias = 0.0
                state.sum_range_min = 75
                state.sum_range_max = 135
                action_notes.append("Sum bias and range bounds restored to baseline [75, 135].")
        else:
            # Underperformance Feedback
            state.consecutive_deficit_count += 1
            streak = state.consecutive_deficit_count

            if streak >= state.loss_threshold:
                is_triggered = True
                trigger_reason = f"CONSECUTIVE_DEFICIT_TRIGGER_STREAK_{streak}"

                # 1. Mode Switching: CONCENTRATED -> DISPERSED
                if state.current_blue_mode != "DISPERSED":
                    state.current_blue_mode = "DISPERSED"
                    state.current_strategy_mode = "DISPERSED_BASELINE"
                    action_notes.append(f"Streak {streak} reached threshold. Switched blue mode to DISPERSED (5 distinct).")

                # 2. Dynamic Weight Shift based on recent 5-draw omission mean
                m_bar = self.calculate_recent_blue_omission_mean(session, window=5)
                w_hazard = state.cold_reversion_weight
                w_markov = state.markov_weight
                w_momentum = state.hot_momentum_weight

                if m_bar <= 4.0:
                    # Hot Momentum Regime
                    delta_w = self.LEARNING_RATE * (1.0 - m_bar / 4.0)
                    w_momentum = min(0.55, w_momentum + delta_w)
                    w_hazard = max(0.20, w_hazard - delta_w)
                    action_notes.append(f"Hot Regime detected (m_bar={m_bar:.1f}<=4). Shifted +{delta_w:.3f} to Momentum.")
                elif m_bar >= 10.0:
                    # Cold Reversion Regime
                    delta_w = self.LEARNING_RATE * min(1.0, (m_bar - 9.0) / 10.0)
                    w_hazard = min(0.60, w_hazard + delta_w)
                    w_momentum = max(0.15, w_momentum - delta_w)
                    action_notes.append(f"Cold Reversion Regime detected (m_bar={m_bar:.1f}>=10). Shifted +{delta_w:.3f} to Hazard.")
                else:
                    action_notes.append(f"Neutral Regime (m_bar={m_bar:.1f}). Weights stabilized.")

                # Re-normalize weights to sum to 1.0
                total_w = w_hazard + w_markov + w_momentum
                state.cold_reversion_weight = round(w_hazard / total_w, 4)
                state.markov_weight = round(w_markov / total_w, 4)
                state.hot_momentum_weight = round(w_momentum / total_w, 4)

                # 3. Guardrail Feedback Adjustment
                delta_sum = deviations.get("delta_sum", 0.0)
                if abs(delta_sum) >= 15.0:
                    shift = round(delta_sum * 0.25)
                    # Symmetric saturation clamp [-30.0, +30.0]
                    raw_bias = state.sum_bias + shift
                    state.sum_bias = round(float(max(-30.0, min(30.0, raw_bias))), 1)

                    # Bi-directional bounding to guarantee sum_range_min <= sum_range_max
                    raw_min = 75 - int(state.sum_bias * 0.5)
                    raw_max = 135 - int(state.sum_bias * 0.5)
                    state.sum_range_min = min(80, max(65, raw_min))
                    state.sum_range_max = max(115, min(145, raw_max))
                    action_notes.append(
                        f"Sum bias adjusted by {shift:+.1f} (clamped bias={state.sum_bias:+.1f}, range=[{state.sum_range_min}, {state.sum_range_max}])."
                    )

                state.evolution_version += 1
            else:
                trigger_reason = f"UNDERPERFORMANCE_STREAK_{streak}"
                action_notes.append(f"Underperformance recorded. Current streak: {streak}/{state.loss_threshold}.")

        state.last_trigger_reason = trigger_reason
        post_state = state.to_dict()

        # Commit immutable trajectory log when adaptation triggers or significant state changes
        if is_triggered or is_break_even:
            notes_str = "; ".join(action_notes) if action_notes else trigger_reason
            history_log = AdaptiveHistory(
                trigger_issue=draw.issue_no,
                trigger_reason=trigger_reason,
                streak_length=state.consecutive_deficit_count,
                pre_state_json=json.dumps(pre_state),
                post_state_json=json.dumps(post_state),
                metrics_deviation_json=json.dumps(deviations),
                reflection_notes=notes_str,
            )
            session.add(history_log)

        session.flush()

        return {
            "is_triggered": is_triggered,
            "trigger_reason": trigger_reason,
            "streak": state.consecutive_deficit_count,
            "current_mode": state.current_blue_mode,
            "weights": {
                "hazard": state.cold_reversion_weight,
                "markov": state.markov_weight,
                "momentum": state.hot_momentum_weight,
            },
            "deviations": deviations,
            "action_notes": action_notes,
        }


__all__ = ["AdaptiveService"]
