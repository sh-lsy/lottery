"""
backend/app/api/backtest.py

Backtest & Historical Collision Sandbox API Router:
- Sub-15ms historical collision sandbox against 3500+ draws
- Verification audit for prediction batches against authentic draw
- Sliding-window walk-forward backtest runner
- Comparative strategy evaluation (Concentrated 3-2 vs Dispersed 5-Distinct)
"""

import json
from typing import Any, Dict, List, Optional
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status, Body
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import DrawHistory, FeatureMetrics, PredictionBatch
from backend.app.schemas import (
    SandboxCollisionRequest,
    SandboxCollisionResponse,
    HistoricalMatchItem,
    QuantileMetricItem,
    VerifyIssueRequest,
    VerifyIssueResponse,
    PredictionBatchSummary,
    BacktestRunRequest,
    BacktestResult as BacktestResultSchema,
    BacktestCompareRequest,
    StrategyComparisonReport as StrategyComparisonReportSchema,
)
from backend.app.services.backtest import BacktestEngine
from backend.app.services.verifier import (
    VerificationService,
    PRIZE_NAMES,
    DEFAULT_FIRST_PRIZE,
    DEFAULT_SECOND_PRIZE,
    FIXED_PRIZES,
)
from backend.app.services.wheeling_engine import StatisticalFilters
from backend.app.services.feature_engine import FeatureEngine
from backend.app.services.collision_cache import CollisionCache

router = APIRouter()


@router.post("/sandbox/collision", response_model=SandboxCollisionResponse, summary="Collide candidate ticket against 3500+ historical draws")
@router.post("/sandbox", response_model=SandboxCollisionResponse, summary="Collide candidate ticket against historical draws (alias)")
def collide_sandbox_ticket(
    request: SandboxCollisionRequest,
    db: Session = Depends(get_db),
):
    ticket_reds = sorted(request.reds)
    ticket_blue = request.blue

    # Retrieve all authentic historical draws via thread-safe cache
    cache = CollisionCache.get_instance()
    cache.ensure_loaded(db)
    all_draws = cache.draw_records
    total_draws = len(all_draws)

    if total_draws == 0:
        return SandboxCollisionResponse(
            ticket_reds=ticket_reds,
            ticket_blue=ticket_blue,
            input_reds=ticket_reds,
            input_blue=ticket_blue,
            total_draws_analyzed=0,
            total_draws_scanned=0,
            highest_prize_level=0,
            highest_prize_name="未中奖 (No Prize)",
            total_historical_payout=0,
            total_payout=0,
            hypothetical_cost=0,
            total_cost=0,
            hypothetical_net_profit=0,
            net_profit=0,
            hypothetical_roi=0.0,
            simulated_roi=0.0,
            prize_counts={f"level_{i}": 0 for i in range(1, 7)},
            prize_distribution={i: 0 for i in range(7)},
            quantile_metrics=[],
            top_matches=[],
        )

    # In-memory single-pass scan with precomputed frozensets
    ticket_red_set = set(ticket_reds)
    prize_counts = {f"level_{i}": 0 for i in range(1, 7)}
    prize_counts["miss"] = 0
    prize_dist = {i: 0 for i in range(7)}
    total_payout = 0
    winning_tiers = []
    best_issue = None
    best_tier = 0
    matches_pool = []

    for issue_no, draw_date, actual_reds, actual_red_fset, actual_blue, f_amt, s_amt in all_draws:
        hit_reds_set = ticket_red_set & actual_red_fset
        h_r = len(hit_reds_set)
        h_b = bool(ticket_blue == actual_blue)

        # Inlined SSQ official rules check (sub-millisecond evaluation across 3500+ draws)
        if h_r == 6 and h_b:
            tier, payout = 1, (f_amt or DEFAULT_FIRST_PRIZE)
        elif h_r == 6 and not h_b:
            tier, payout = 2, (s_amt or DEFAULT_SECOND_PRIZE)
        elif h_r == 5 and h_b:
            tier, payout = 3, FIXED_PRIZES[3]
        elif (h_r == 5 and not h_b) or (h_r == 4 and h_b):
            tier, payout = 4, FIXED_PRIZES[4]
        elif (h_r == 4 and not h_b) or (h_r == 3 and h_b):
            tier, payout = 5, FIXED_PRIZES[5]
        elif h_r in (0, 1, 2) and h_b:
            tier, payout = 6, FIXED_PRIZES[6]
        else:
            tier, payout = 0, 0

        total_payout += payout
        prize_dist[tier] += 1
        if tier > 0:
            prize_counts[f"level_{tier}"] += 1
            winning_tiers.append(tier)
            if best_tier == 0 or tier < best_tier:
                best_tier = tier
                best_issue = issue_no

            if tier <= 4 or len(matches_pool) < 10:
                matches_pool.append(
                    HistoricalMatchItem(
                        issue_no=issue_no,
                        draw_date=draw_date,
                        actual_reds=actual_reds,
                        actual_blue=actual_blue,
                        hit_red_count=h_r,
                        hit_reds=sorted(list(hit_reds_set)),
                        hit_blue=h_b,
                        prize_level=tier,
                        prize_amount=payout,
                    )
                )
        else:
            prize_counts["miss"] += 1

    highest_level = min(winning_tiers) if winning_tiers else 0
    highest_name = PRIZE_NAMES.get(highest_level, "未中奖 (No Prize)")

    total_cost = total_draws * 2
    net_profit = total_payout - total_cost
    simulated_roi = round(float(net_profit) / float(total_cost), 4) if total_cost > 0 else 0.0

    # Calculate mathematical features of ticket
    t_sum = sum(ticket_reds)
    t_span = ticket_reds[-1] - ticket_reds[0]
    t_ac = StatisticalFilters.calculate_ac(ticket_reds)
    t_odd = sum(1 for r in ticket_reds if r % 2 == 1)
    t_prime = FeatureEngine.calculate_prime_count(ticket_reds)
    z1, z2, z3 = FeatureEngine.calculate_zones(ticket_reds)

    # Compute historical quantiles from cached FeatureMetrics
    quantile_metrics: List[QuantileMetricItem] = []
    if cache.stats and len(cache.cached_sums) > 0:
        def _calc_qm(name: str, val: float, arr: np.ndarray, key: str) -> QuantileMetricItem:
            p = float(np.count_nonzero(arr <= val)) / len(arr) * 100.0
            eval_str = "NORMAL"
            if p >= 90.0:
                eval_str = "HIGH_PERCENTILE"
            elif p <= 10.0:
                eval_str = "LOW_PERCENTILE"
            mean_val, min_val, max_val = cache.stats[key]
            return QuantileMetricItem(
                metric_name=name,
                ticket_value=float(val),
                historical_mean=round(mean_val, 2),
                historical_min=min_val,
                historical_max=max_val,
                percentile=round(p, 1),
                evaluation=eval_str,
            )

        quantile_metrics.append(_calc_qm("Sum Value (和值)", float(t_sum), cache.cached_sums, "sum"))
        quantile_metrics.append(_calc_qm("AC Value (复杂度和)", float(t_ac), cache.cached_acs, "ac"))
        quantile_metrics.append(_calc_qm("Span (跨度)", float(t_span), cache.cached_spans, "span"))
        quantile_metrics.append(_calc_qm("Odd Count (奇数个数)", float(t_odd), cache.cached_odds, "odd"))

    # Top matches sorted by prize level ascending (level 1 first)
    matches_pool.sort(key=lambda m: (m.prize_level, -m.hit_red_count, m.issue_no))
    top_matches = matches_pool[:10]

    features_dict = {
        "sum": t_sum,
        "span": t_span,
        "ac": t_ac,
        "odd_count": t_odd,
        "prime_count": t_prime,
        "zones": [z1, z2, z3],
    }

    percentiles_dict = {
        qm.metric_name: qm.percentile for qm in quantile_metrics
    }

    return SandboxCollisionResponse(
        ticket_reds=ticket_reds,
        ticket_blue=ticket_blue,
        input_reds=ticket_reds,
        input_blue=ticket_blue,
        total_draws_analyzed=total_draws,
        total_draws_scanned=total_draws,
        highest_prize_level=highest_level,
        highest_prize_name=highest_name,
        best_prize_level=highest_level,
        best_prize_name=highest_name,
        best_prize_issue=best_issue,
        total_historical_payout=total_payout,
        total_payout=total_payout,
        hypothetical_cost=total_cost,
        total_cost=total_cost,
        hypothetical_net_profit=net_profit,
        net_profit=net_profit,
        hypothetical_roi=simulated_roi,
        simulated_roi=simulated_roi,
        prize_counts=prize_counts,
        prize_distribution=prize_dist,
        features=features_dict,
        percentiles=percentiles_dict,
        quantile_metrics=quantile_metrics,
        top_matches=top_matches,
    )


@router.post("/verify/{issue_no}", response_model=VerifyIssueResponse, summary="Audit prediction batches against authentic draw")
def verify_issue_predictions(
    issue_no: str,
    request: Optional[VerifyIssueRequest] = Body(None),
    force: Optional[bool] = Query(None, description="Force re-verification"),
    db: Session = Depends(get_db),
):
    is_force = force if force is not None else (request.force if request is not None else False)
    draw = db.scalar(select(DrawHistory).filter(DrawHistory.issue_no == issue_no))
    if not draw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Draw history for issue {issue_no} not found in database",
        )

    verifier = VerificationService()
    try:
        verified_batches = verifier.verify_issue(issue_no=issue_no, session=db, force=is_force)
        db.commit()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {str(e)}",
        )

    total_cost = sum(b.virtual_cost for b in verified_batches)
    total_reward = sum(b.virtual_reward for b in verified_batches)
    best_level = min((b.best_prize_level for b in verified_batches if b.best_prize_level > 0), default=0)

    summaries = []
    for b in verified_batches:
        net_profit = b.virtual_reward - b.virtual_cost
        roi = round(float(net_profit) / float(b.virtual_cost), 4) if b.virtual_cost > 0 else 0.0
        summaries.append(
            PredictionBatchSummary(
                id=b.id,
                target_issue=b.target_issue,
                strategy_type=b.strategy_type,
                model_name=b.model_name,
                total_notes=b.total_notes,
                verify_status=b.verify_status,
                best_prize_level=b.best_prize_level,
                virtual_cost=b.virtual_cost,
                virtual_reward=b.virtual_reward,
                net_profit=net_profit,
                roi=roi,
                created_at=b.created_at,
                verified_at=b.verified_at,
            )
        )

    return VerifyIssueResponse(
        issue_no=issue_no,
        verified_batches_count=len(verified_batches),
        total_virtual_cost=total_cost,
        total_virtual_reward=total_reward,
        best_prize_level=best_level,
        verified_batches=summaries,
    )


@router.post("/run", response_model=BacktestResultSchema, summary="Run sliding-window historical backtest")
def run_backtest_simulation(
    request: BacktestRunRequest = BacktestRunRequest(),
    db: Session = Depends(get_db),
):
    engine = BacktestEngine()
    result = engine.run_backtest(n_issues=request.n_issues, strategy=request.strategy, session=db)

    return BacktestResultSchema(
        total_issues=result.total_issues,
        strategy=result.strategy_name,
        total_investment=result.total_investment,
        total_return=result.total_returns,
        net_profit=result.net_profit,
        roi=result.simulated_roi,
        break_even_rate=result.break_even_rate,
        blue_hit_rate=result.blue_hit_rate,
        max_drawdown=float(result.max_drawdown),
        prize_distribution=result.prize_distribution,
    )


@router.post("/compare", response_model=StrategyComparisonReportSchema, summary="Run comparative backtest between Concentrated and Dispersed strategies")
def compare_strategies_simulation(
    request: BacktestCompareRequest = BacktestCompareRequest(),
    db: Session = Depends(get_db),
):
    engine = BacktestEngine()
    report = engine.compare_strategies(n_issues=request.n_issues, session=db)

    strat_a_dict = report.strategy_a.to_dict() if hasattr(report.strategy_a, "to_dict") else dict(report.strategy_a)
    strat_b_dict = report.strategy_b.to_dict() if hasattr(report.strategy_b, "to_dict") else dict(report.strategy_b)

    return StrategyComparisonReportSchema(
        n_issues=report.n_issues,
        concentrated_result=strat_a_dict,
        dispersed_result=strat_b_dict,
        comparison_summary=report.summary_text,
    )
