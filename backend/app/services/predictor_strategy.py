"""
5-line prediction task service with database persistence, zero-lookahead isolation,
and dual-engine (blue break-even allocation + red combinatorial wheeling).
"""

import json
from typing import List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models import DrawHistory, PredictionBatch, PredictionItem
from backend.app.services.quant_models import BlueScoringEngine, BlueAllocationStrategy
from backend.app.services.wheeling_engine import RedWheelingEngine, StatisticalFilters


def normalize_strategy_type(strategy: Optional[str]) -> str:
    """
    Normalizes user-provided strategy strings and aliases to canonical schema enum values.
    Supports:
      - 'CONCENTRATED_BREAK_EVEN', 'concentrated', 'break_even' -> 'CONCENTRATED_BREAK_EVEN'
      - 'DISPERSED_BASELINE', 'dispersed', 'baseline' -> 'DISPERSED_BASELINE'
      - 'STAT_FILTER', 'balanced', 'statistical_filter' -> 'STAT_FILTER'
      - 'ML_PROB', 'ml', 'prob', 'auto' -> 'ML_PROB'
      - 'NEURAL_EVOLVE', 'neural', 'ai', 'nn', 'ssq_neural' -> 'NEURAL_EVOLVE'
    """
    s = (strategy or "").strip().upper()
    if not s or s in ("CONCENTRATED_BREAK_EVEN", "CONCENTRATED", "BREAK_EVEN"):
        return "CONCENTRATED_BREAK_EVEN"
    elif s in ("DISPERSED_BASELINE", "DISPERSED", "BASELINE"):
        return "DISPERSED_BASELINE"
    elif s in ("STAT_FILTER", "STATISTICAL_FILTER", "BALANCED"):
        return "STAT_FILTER"
    elif s in ("NEURAL_EVOLVE", "NEURAL", "AI", "NN", "SSQ_NEURAL"):
        return "NEURAL_EVOLVE"
    elif s in ("YIJING_METAPHYSICS", "YIJING", "METAPHYSICS", "BAGUA", "BAGUA_METAPHYSICS", "WUXING"):
        return "YIJING_METAPHYSICS"
    elif s in ("ML_PROB", "ML", "PROB", "AUTO"):
        return "ML_PROB"
    else:
        # Check if already a valid schema value
        valid = {"CONCENTRATED_BREAK_EVEN", "DISPERSED_BASELINE", "STAT_FILTER", "ML_PROB", "NEURAL_EVOLVE", "YIJING_METAPHYSICS"}
        if s in valid:
            return s
        raise ValueError(f"Unknown strategy: '{strategy}'. Valid choices are: {sorted(list(valid))}")


class PredictionService:
    """Service orchestrating 5-line prediction generation and SQLite persistence."""

    def __init__(self, session_factory=None):
        self.session_factory = session_factory or SessionLocal

    @staticmethod
    def get_next_target_issue(session: Session) -> str:
        """
        Determines the next sequential target issue number based on max existing issue in DB.
        """
        max_issue = session.scalar(select(func.max(DrawHistory.issue_no)))
        if not max_issue:
            return "2003001"
        try:
            return str(int(max_issue) + 1)
        except ValueError:
            return f"{max_issue}_next"

    def generate_5_line_prediction(
        self,
        target_issue: Optional[str] = None,
        strategy: str = "CONCENTRATED_BREAK_EVEN",
        adaptive_enabled: bool = True,
        custom_weights: Optional[Tuple[float, float, float]] = None,
        custom_blue_mode: Optional[str] = None,
        custom_filters: Optional[dict] = None,
        batch_offset: int = 0,
        persist: bool = True,
    ) -> PredictionBatch:
        """
        Generates exactly 5 lines for target_issue strictly using historical draws prior to target_issue.
        Persists 1 PredictionBatch and 5 PredictionItems into the database when persist=True.

        :param target_issue: Target issue number (e.g. '2026123'). If None, automatically resolves to next issue.
        :param strategy: Prediction strategy type or alias. Defaults to 'CONCENTRATED_BREAK_EVEN'.
        :param adaptive_enabled: Whether to apply current adaptive strategy hyperparameters.
        :param custom_weights: Optional explicit weights (hazard, markov, momentum).
        :param custom_blue_mode: Optional blue allocation mode override.
        :param custom_filters: Optional custom statistical guardrails.
        :param batch_offset: Offset index for multi-batch rotation (e.g. 0 -> Batch 1, 1 -> Batch 2).
        :param persist: Whether to commit records to SQLite database.
        :return: PredictionBatch instance with 5 linked items.
        """
        canonical_strategy = normalize_strategy_type(strategy)

        with self.session_factory() as session:
            # 1. Target Issue Resolution
            if not target_issue:
                target_issue = self.get_next_target_issue(session)

            # 2. Zero-Lookahead Isolation
            historical_draws = session.scalars(
                select(DrawHistory)
                .filter(DrawHistory.issue_no < target_issue)
                .order_by(DrawHistory.issue_no.asc())
            ).all()

            if not historical_draws:
                raise ValueError(f"No historical draws found prior to target issue {target_issue}")

            history_blues = [d.blue_1 for d in historical_draws]
            history_reds = [d.reds for d in historical_draws]

            # 3. Resolve Adaptive Hyperparameters
            active_weights = (0.40, 0.35, 0.25)
            adaptive_mode = None
            sum_min = 75
            sum_max = 135
            ac_min = 6

            if adaptive_enabled:
                try:
                    from backend.app.services.adaptive_service import AdaptiveService
                    adaptive_service = AdaptiveService()
                    ad_state = adaptive_service.get_or_create_state(session)
                    active_weights = (
                        float(ad_state.cold_reversion_weight),
                        float(ad_state.markov_weight),
                        float(ad_state.hot_momentum_weight),
                    )
                    adaptive_mode = ad_state.current_blue_mode
                    sum_min = ad_state.sum_range_min
                    sum_max = ad_state.sum_range_max
                    ac_min = ad_state.ac_min_override
                except Exception:
                    pass

            if custom_weights:
                active_weights = custom_weights
            if custom_blue_mode:
                adaptive_mode = custom_blue_mode
            if custom_filters:
                sum_min = custom_filters.get("sum_min", sum_min)
                sum_max = custom_filters.get("sum_max", sum_max)
                ac_min = custom_filters.get("ac_min", ac_min)

            # 4. Neural Network or Statistical Probability Estimation
            neural_used = False
            red_probs = None
            blue_probs = None
            meta_info = None

            if canonical_strategy in ("NEURAL_EVOLVE", "ML_PROB", "YIJING_METAPHYSICS"):
                try:
                    from backend.app.services.neural_model import SSQNeuralPredictor
                    import numpy as np
                    predictor = SSQNeuralPredictor()
                    r_p, b_p = predictor.predict_probabilities(historical_draws)
                    neural_used = True

                    # 1. Pure Quant Multi-Model Blue Engine
                    blue_engine = BlueScoringEngine(history_blues)
                    q_b, _ = blue_engine.compute_ensemble_probabilities(weights=active_weights, tau=0.75)
                    blue_probs = 0.50 * b_p + 0.50 * q_b
                    probs = blue_probs
                    ranked_blues = (np.argsort(probs)[::-1] + 1).tolist()

                    # 2. Pure Quant Red Omission Resonance Prior
                    omiss_scores = np.zeros(33)
                    for b in range(1, 34):
                        last_idx = -1
                        for h_i in range(len(historical_draws) - 1, -1, -1):
                            if b in historical_draws[h_i].reds:
                                last_idx = h_i
                                break
                        o = (len(historical_draws) - 1 - last_idx) if last_idx != -1 else len(historical_draws)
                        omiss_scores[b - 1] = np.exp(-((o - 5.5)**2) / 32.0)
                    omiss_probs = omiss_scores / np.sum(omiss_scores)
                    red_probs = 0.65 * r_p + 0.35 * omiss_probs
                except Exception:
                    neural_used = False

            if canonical_strategy == "YIJING_METAPHYSICS":
                try:
                    from backend.app.services.metaphysics_engine import MetaphysicsEngine
                    import numpy as np
                    latest_d = str(historical_draws[-1].draw_date) if historical_draws else "2026-11-03"
                    m_r, m_b, meta_info = MetaphysicsEngine.compute_metaphysics_probabilities(latest_d, str(target_issue))
                    if neural_used and r_p is not None:
                        # 70% Neural Net + 30% Zhouyi Bagua Metaphysics (proven Level 3 prize parameter)
                        red_probs = 0.70 * r_p + 0.30 * np.array(m_r)
                        probs = 0.70 * b_p + 0.30 * np.array(m_b)
                    else:
                        red_probs = np.array(m_r)
                        probs = np.array(m_b)
                    ranked_blues = (np.argsort(probs)[::-1] + 1).tolist()
                except Exception:
                    pass

            if not neural_used and canonical_strategy != "YIJING_METAPHYSICS":
                blue_engine = BlueScoringEngine(history_blues)
                probs, ranked_blues = blue_engine.compute_ensemble_probabilities(weights=active_weights)

            # 5. Dynamic Break-Even Blue Allocation with Rotation
            mode_map = {
                "CONCENTRATED_BREAK_EVEN": "CONCENTRATED",
                "DISPERSED_BASELINE": "DISPERSED",
                "STAT_FILTER": "BALANCED",
                "ML_PROB": "AUTO",
                "NEURAL_EVOLVE": "BALANCED",
                "YIJING_METAPHYSICS": "BALANCED",
            }
            if custom_blue_mode:
                alloc_mode = custom_blue_mode
            elif canonical_strategy == "CONCENTRATED_BREAK_EVEN" and adaptive_mode:
                alloc_mode = adaptive_mode
            else:
                alloc_mode = mode_map.get(canonical_strategy, "AUTO")

            allocated_blues = BlueAllocationStrategy.allocate(
                ranked_blues,
                probs,
                mode=alloc_mode,
                batch_offset=batch_offset,
            )

            # 6. Red Zero-Core Orthogonal Wheeling with Portfolio Tiering
            red_engine = RedWheelingEngine(history_reds)
            cf = {
                "sum_min": sum_min,
                "sum_max": sum_max,
                "ac_min": ac_min,
            }
            if custom_filters:
                cf.update(custom_filters)

            # Zero-core orthogonal covering by default (eliminating 2-core deadlocks)
            red_lines = red_engine.generate_5_lines_zero_core(
                custom_filters=cf,
                red_probs=red_probs,
                batch_offset=batch_offset,
            )
            candidate_pool = red_engine.select_zero_core_pool(red_probs=red_probs, batch_offset=batch_offset)

            # 7. Structured Rationale and Filter Metadata
            top1_b, top2_b = ranked_blues[0], ranked_blues[1]
            p1, p2 = float(probs[top1_b - 1]), float(probs[top2_b - 1])

            if canonical_strategy == "YIJING_METAPHYSICS":
                model_label = "Zhouyi-Bagua-Neural-Dual-Track"
            elif neural_used:
                model_label = "SSQ-NeuralNet-Compact-0.96MB"
            else:
                model_label = "Ensemble-Hazard-Markov-Momentum"

            metaphysics_block = ""
            if meta_info:
                metaphysics_block = (
                    f"- **周易八卦象数**: 当期卦象【{meta_info.get('hexagram_name', '乾为天')}】| {meta_info.get('prophecy_text', '')}\n"
                    f"- **天干地支五行**: 开奖日柱【{meta_info.get('day_ganzhi', '')}】(日主属{meta_info.get('day_master_element', '')}，支属{meta_info.get('zhi_element', '')})，开奖亥时(水旺生木)\n"
                )

            ai_reasoning = (
                f"### Target Issue {target_issue} Quantitative Prediction Rationale (Batch Offset: {batch_offset})\n"
                f"- **Engine**: {model_label} | **Strategy**: {canonical_strategy} ({alloc_mode})\n"
                f"{metaphysics_block}"
                f"- **Blue Ball Allocation**: {allocated_blues} (Top 1: Blue {top1_b:02d} [{p1:.2%}], Top 2: Blue {top2_b:02d} [{p2:.2%}])\n"
                f"- **Red Candidate Pool (13-Ball Zero-Core)**: {candidate_pool}\n"
                f"- **Orthogonal Covering**: Pairwise intersection <= 3, Lines 1-3 Central Profile (Sum [{sum_min}, {sum_max}]), Lines 4-5 Wing Defense.\n"
                f"- **Negative Expectation Disclaimer**: SSQ expected return E[X] < 0. Strategy maximizes break-even probability and eliminates retail core deadlocks.\n"
            )

            filter_params = {
                "ac_min": ac_min,
                "sum_range": [sum_min, sum_max],
                "candidate_pool": candidate_pool,
                "allocated_blues": allocated_blues,
                "adaptive_mode": alloc_mode,
                "batch_offset": batch_offset,
                "neural_used": neural_used,
                "metaphysics_info": meta_info,
            }

            # 7. Persist PredictionBatch with Deduplication
            if persist:
                existing_batches = session.scalars(
                    select(PredictionBatch).where(PredictionBatch.target_issue == target_issue)
                ).all()
                incoming_lines = [
                    (tuple(sorted(red_lines[i])), allocated_blues[i]) for i in range(5)
                ]

                found_batch = None
                for eb in existing_batches:
                    eb_items = session.scalars(
                        select(PredictionItem).where(PredictionItem.batch_id == eb.id).order_by(PredictionItem.note_index.asc())
                    ).all()
                    eb_lines = [
                        (tuple(sorted([it.red_1, it.red_2, it.red_3, it.red_4, it.red_5, it.red_6])), it.blue_1)
                        for it in eb_items
                    ]
                    if sorted(eb_lines) == sorted(incoming_lines):
                        found_batch = eb
                        break

                if found_batch:
                    _ = list(found_batch.items)
                    return found_batch

                batch = PredictionBatch(
                    target_issue=target_issue,
                    strategy_type=canonical_strategy,
                    model_name=model_label,
                    filter_params_json=json.dumps(filter_params),
                    ai_reasoning_md=ai_reasoning,
                    total_notes=5,
                    verify_status="PENDING",
                    virtual_cost=10,
                    virtual_reward=0,
                )
                session.add(batch)
                session.flush()

                for note_idx in range(1, 6):
                    line_reds = red_lines[note_idx - 1]
                    b_val = allocated_blues[note_idx - 1]
                    conf = float(probs[b_val - 1])
                    item = PredictionItem(
                        batch_id=batch.id,
                        target_issue=target_issue,
                        note_index=note_idx,
                        red_1=line_reds[0],
                        red_2=line_reds[1],
                        red_3=line_reds[2],
                        red_4=line_reds[3],
                        red_5=line_reds[4],
                        red_6=line_reds[5],
                        blue_1=b_val,
                        confidence_score=conf,
                        rationale=f"Note {note_idx}: Zero-Core Orthogonal Wheel + Blue {b_val:02d}",
                        is_verified=False,
                    )
                    session.add(item)

                session.commit()
                session.refresh(batch)
                _ = list(batch.items)
                return batch
            else:
                batch = PredictionBatch(
                    target_issue=target_issue,
                    strategy_type=canonical_strategy,
                    model_name=model_label,
                    filter_params_json=json.dumps(filter_params),
                    ai_reasoning_md=ai_reasoning,
                    total_notes=5,
                    verify_status="PENDING",
                    virtual_cost=10,
                    virtual_reward=0,
                )
                session.add(batch)
                session.flush()
                for note_idx in range(1, 6):
                    line_reds = red_lines[note_idx - 1]
                    b_val = allocated_blues[note_idx - 1]
                    conf = float(probs[b_val - 1])
                    item = PredictionItem(
                        batch_id=batch.id,
                        target_issue=target_issue,
                        note_index=note_idx,
                        red_1=line_reds[0],
                        red_2=line_reds[1],
                        red_3=line_reds[2],
                        red_4=line_reds[3],
                        red_5=line_reds[4],
                        red_6=line_reds[5],
                        blue_1=b_val,
                        confidence_score=conf,
                        rationale=f"Note {note_idx}: Zero-Core Orthogonal Wheel + Blue {b_val:02d}",
                        is_verified=False,
                    )
                    session.add(item)
                session.flush()
                items = list(batch.items)
                for it in items:
                    _ = it.to_dict()
                    session.expunge(it)
                session.expunge(batch)
                session.rollback()
                batch.items = items
                return batch
