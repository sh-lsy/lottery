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
    """
    s = (strategy or "").strip().upper()
    if not s or s in ("CONCENTRATED_BREAK_EVEN", "CONCENTRATED", "BREAK_EVEN"):
        return "CONCENTRATED_BREAK_EVEN"
    elif s in ("DISPERSED_BASELINE", "DISPERSED", "BASELINE"):
        return "DISPERSED_BASELINE"
    elif s in ("STAT_FILTER", "STATISTICAL_FILTER", "BALANCED"):
        return "STAT_FILTER"
    elif s in ("ML_PROB", "ML", "PROB", "AUTO"):
        return "ML_PROB"
    else:
        # Check if already a valid schema value
        valid = {"CONCENTRATED_BREAK_EVEN", "DISPERSED_BASELINE", "STAT_FILTER", "ML_PROB"}
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
    ) -> PredictionBatch:
        """
        Generates exactly 5 lines for target_issue strictly using historical draws prior to target_issue.
        Persists 1 PredictionBatch and 5 PredictionItems into the database.

        :param target_issue: Target issue number (e.g. '2026123'). If None, automatically resolves to next issue.
        :param strategy: Prediction strategy type or alias. Defaults to 'CONCENTRATED_BREAK_EVEN'.
        :return: Persisted PredictionBatch instance with 5 linked items.
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

            # 3. Blue Multi-Model Ensemble Scoring
            blue_engine = BlueScoringEngine(history_blues)
            probs, ranked_blues = blue_engine.compute_ensemble_probabilities()

            # 4. Dynamic Break-Even Blue Allocation
            mode_map = {
                "CONCENTRATED_BREAK_EVEN": "CONCENTRATED",
                "DISPERSED_BASELINE": "DISPERSED",
                "STAT_FILTER": "BALANCED",
                "ML_PROB": "AUTO",
            }
            alloc_mode = mode_map.get(canonical_strategy, "CONCENTRATED")
            allocated_blues = BlueAllocationStrategy.allocate(ranked_blues, probs, mode=alloc_mode)

            # 5. Red Dan-Tuo Combinatorial Wheeling with Guardrails
            red_engine = RedWheelingEngine(history_reds)
            cores, satellites = red_engine.select_candidate_pool()
            red_lines = red_engine.generate_5_lines()

            # 6. Structured Rationale and Filter Metadata
            top1_b, top2_b = ranked_blues[0], ranked_blues[1]
            p1, p2 = float(probs[top1_b - 1]), float(probs[top2_b - 1])

            ai_reasoning = (
                f"### Target Issue {target_issue} Quantitative Prediction Rationale\n"
                f"- **Strategy Mode**: {canonical_strategy} ({alloc_mode})\n"
                f"- **Blue Ball Ensemble Top-2**: Blue {top1_b:02d} ({p1:.2%}), Blue {top2_b:02d} ({p2:.2%})\n"
                f"- **Blue Allocation**: {allocated_blues}\n"
                f"- **Break-Even Payoff Matrix**: When Blue {top1_b:02d} hits, 3 notes hit -> 15 RMB (+50% ROI, +5 RMB net profit); "
                f"when Blue {top2_b:02d} hits, 2 notes hit -> 10 RMB (Exact Break-Even, 0% ROI).\n"
                f"- **Red Candidate Pool (Dan-Tuo)**: Cores={cores}, Satellites={satellites}\n"
                f"- **Statistical Guardrails**: All 5 lines satisfy AC >= 6, Sum in [75, 135], Odd Parity in {{2,3,4}}, Consec <= 2, Span in [18, 30].\n"
                f"- **Negative Expectation Disclaimer**: SSQ expected return E[X] < 0 due to official 50% house edge. "
                f"This strategy eliminates retail single-hit negative return given a blue hit, but cannot overcome mathematical house edge over infinite horizon.\n"
            )

            filter_params = {
                "ac_min": 6,
                "sum_range": [75, 135],
                "odd_counts": [2, 3, 4],
                "max_consecutive_pairs": 2,
                "cores": cores,
                "satellites": satellites,
                "allocated_blues": allocated_blues,
            }

            # 7. Persist PredictionBatch
            batch = PredictionBatch(
                target_issue=target_issue,
                strategy_type=canonical_strategy,
                model_name="Ensemble-Hazard-Markov-Momentum",
                filter_params_json=json.dumps(filter_params),
                ai_reasoning_md=ai_reasoning,
                total_notes=5,
                verify_status="PENDING",
                virtual_cost=10,
                virtual_reward=0,
            )
            session.add(batch)
            session.flush()

            # 8. Persist 5 PredictionItems
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
                    rationale=f"Note {note_idx}: Cores {cores} + Blue {b_val:02d}",
                    is_verified=False,
                )
                session.add(item)

            session.commit()
            session.refresh(batch)
            _ = list(batch.items)
            return batch
