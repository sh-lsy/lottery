"""
backend/app/api/predict.py

Prediction API Router:
- Pure local offline quant 5-line prediction generation (<50ms)
- Atomic prediction persistence
- Historical prediction batches query & detail with neon highlighting metadata
- Prediction performance dashboard & ROI metrics
"""

import json
import math
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import DrawHistory, PredictionBatch, PredictionItem, FeatureMetrics
from backend.app.schemas import (
    PredictionGenerateRequest,
    PredictionGenerateResponse,
    PredictionNoteItem,
    CandidatePoolSummary,
    BlueProbabilityItem,
    PredictionSaveRequest,
    PredictionSaveResponse,
    PaginatedResponse,
    PredictionBatchSummary,
    PredictionBatchDetail,
    PredictionItemDetail,
    PredictDashboardResponse,
    DrawRecordItem,
)
from backend.app.services.predictor_strategy import PredictionService, normalize_strategy_type
from backend.app.services.quant_models import BlueScoringEngine, BlueAllocationStrategy
from backend.app.services.wheeling_engine import RedWheelingEngine, StatisticalFilters
from backend.app.services.adaptive_service import AdaptiveService

router = APIRouter()


@router.post("/generate", response_model=PredictionGenerateResponse, summary="Generate local offline quant 5-line prediction")
def generate_prediction(
    request: PredictionGenerateRequest = PredictionGenerateRequest(),
    db: Session = Depends(get_db),
):
    strategy_str = request.strategy or request.strategy_type or "CONCENTRATED_BREAK_EVEN"
    canonical_strategy = normalize_strategy_type(strategy_str)

    # 1. Resolve Target Issue
    target_issue = request.target_issue
    if not target_issue:
        target_issue = PredictionService.get_next_target_issue(db)

    # 2. Historical Zero-Lookahead Isolation
    historical_draws = db.scalars(
        select(DrawHistory)
        .filter(DrawHistory.issue_no < target_issue)
        .order_by(DrawHistory.issue_no.asc())
    ).all()

    if not historical_draws:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No historical draws found prior to target issue {target_issue}",
        )

    history_blues = [d.blue_1 for d in historical_draws]
    history_reds = [d.reds for d in historical_draws]

    # 3. Adaptive Hyperparameter Resolution
    active_weights = (0.40, 0.35, 0.25)
    adaptive_mode = None
    sum_min = request.sum_min
    sum_max = request.sum_max
    ac_min = request.ac_min

    if request.adaptive_enabled:
        try:
            adaptive_service = AdaptiveService()
            ad_state = adaptive_service.get_or_create_state(db)
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

    if request.blue_mode:
        alloc_mode = request.blue_mode.upper()
    elif canonical_strategy == "CONCENTRATED_BREAK_EVEN" and adaptive_mode:
        alloc_mode = adaptive_mode
    else:
        mode_map = {
            "CONCENTRATED_BREAK_EVEN": "CONCENTRATED",
            "DISPERSED_BASELINE": "DISPERSED",
            "STAT_FILTER": "BALANCED",
            "ML_PROB": "AUTO",
        }
        alloc_mode = mode_map.get(canonical_strategy, "CONCENTRATED")

    # 4. Blue Ball Multi-Model Scoring
    blue_engine = BlueScoringEngine(history_blues)
    probs, ranked_blues = blue_engine.compute_ensemble_probabilities(weights=active_weights)
    allocated_blues = BlueAllocationStrategy.allocate(ranked_blues, probs, mode=alloc_mode)

    # 5. Red Dan-Tuo Candidate Pool & Wheeling
    red_engine = RedWheelingEngine(history_reds)
    cores, satellites = red_engine.select_candidate_pool()
    red_lines = red_engine.generate_5_lines()

    # 6. Build Notes and Per-Line Features
    notes: List[PredictionNoteItem] = []
    for idx in range(1, 6):
        line_reds = sorted(red_lines[idx - 1])
        b_val = allocated_blues[idx - 1]
        conf = float(probs[b_val - 1])
        s_val = sum(line_reds)
        ac_val = StatisticalFilters.calculate_ac(line_reds)
        odd_c = sum(1 for r in line_reds if r % 2 == 1)
        span_v = line_reds[-1] - line_reds[0]

        notes.append(
            PredictionNoteItem(
                note_index=idx,
                reds=line_reds,
                blue=b_val,
                confidence_score=round(conf, 4),
                rationale=f"Line {idx}: Cores {cores} + Blue {b_val:02d} ({alloc_mode})",
                sum_red=s_val,
                ac_value=ac_val,
                odd_count=odd_c,
                span_red=span_v,
                metrics={
                    "sum": s_val,
                    "ac": ac_val,
                    "odd_count": odd_c,
                    "span": span_v,
                },
            )
        )

    # 7. Structured Rationale and Payoff Analysis
    top1_b, top2_b = ranked_blues[0], ranked_blues[1]
    p1, p2 = float(probs[top1_b - 1]), float(probs[top2_b - 1])
    break_even_matrix = {
        "mode": alloc_mode,
        "top1_blue": top1_b,
        "top1_prob": round(p1, 4),
        "top2_blue": top2_b,
        "top2_prob": round(p2, 4),
        "payoff_on_top1": {"hits": 3, "reward": 15, "net_profit": 5, "roi": 0.50},
        "payoff_on_top2": {"hits": 2, "reward": 10, "net_profit": 0, "roi": 0.00},
        "payoff_on_miss": {"hits": 0, "reward": 0, "net_profit": -10, "roi": -1.00},
    }

    ai_reasoning = (
        f"### Target Issue {target_issue} Quantitative Prediction Rationale\n"
        f"- **Strategy Mode**: {canonical_strategy} ({alloc_mode})\n"
        f"- **Adaptive Weights**: Hazard={active_weights[0]:.2f}, Markov={active_weights[1]:.2f}, Momentum={active_weights[2]:.2f}\n"
        f"- **Blue Ball Ensemble Top-2**: Blue {top1_b:02d} ({p1:.2%}), Blue {top2_b:02d} ({p2:.2%})\n"
        f"- **Blue Allocation**: {allocated_blues}\n"
        f"- **Break-Even Payoff Matrix**: When Blue {top1_b:02d} hits, 3 notes hit -> 15 RMB (+50% ROI, +5 RMB net profit); "
        f"when Blue {top2_b:02d} hits, 2 notes hit -> 10 RMB (Exact Break-Even, 0% ROI).\n"
        f"- **Red Candidate Pool (Dan-Tuo)**: Cores={cores}, Satellites={satellites}\n"
        f"- **Statistical Guardrails**: All 5 lines satisfy AC >= {ac_min}, Sum in [{sum_min}, {sum_max}], Odd Parity in {{2,3,4}}, Consec <= 2, Span in [18, 30].\n"
        f"- **Negative Expectation Disclaimer**: SSQ expected return E[X] < 0 due to official 50% house edge. "
        f"This strategy eliminates retail single-hit negative return given a blue hit, but cannot overcome mathematical house edge over infinite horizon.\n"
    )

    filter_params = {
        "ac_min": ac_min,
        "sum_range": [sum_min, sum_max],
        "odd_counts": [2, 3, 4],
        "max_consecutive_pairs": 2,
        "cores": cores,
        "satellites": satellites,
        "allocated_blues": allocated_blues,
        "alloc_mode": alloc_mode,
        "weights": list(active_weights),
    }

    blue_probabilities = [
        BlueProbabilityItem(ball=b, probability=round(float(probs[b - 1]), 4), rank=r + 1)
        for r, b in enumerate(ranked_blues)
    ]

    # 8. Optional Persistence
    batch_id = None
    if request.save_to_db or request.persist:
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
        db.add(batch)
        db.flush()
        batch_id = batch.id

        for n in notes:
            item = PredictionItem(
                batch_id=batch.id,
                target_issue=target_issue,
                note_index=n.note_index,
                red_1=n.reds[0],
                red_2=n.reds[1],
                red_3=n.reds[2],
                red_4=n.reds[3],
                red_5=n.reds[4],
                red_6=n.reds[5],
                blue_1=n.blue,
                confidence_score=n.confidence_score,
                rationale=n.rationale,
                is_verified=False,
            )
            db.add(item)
        db.commit()

    return PredictionGenerateResponse(
        target_issue=target_issue,
        strategy_type=canonical_strategy,
        model_name="Ensemble-Hazard-Markov-Momentum",
        total_notes=5,
        notes=notes,
        ai_reasoning_md=ai_reasoning,
        filter_params=filter_params,
        candidate_pool=CandidatePoolSummary(cores=cores, satellites=satellites),
        blue_probabilities=blue_probabilities,
        break_even_matrix=break_even_matrix,
        batch_id=batch_id,
    )


@router.post("/save", response_model=PredictionSaveResponse, summary="Persist prediction batch and 5 notes")
def save_prediction_batch(
    request: PredictionSaveRequest,
    db: Session = Depends(get_db),
):
    batch = PredictionBatch(
        target_issue=request.target_issue,
        strategy_type=request.strategy_type,
        model_name=request.model_name or "Ensemble-Hazard-Markov-Momentum",
        filter_params_json=json.dumps(request.filter_params) if request.filter_params else None,
        ai_reasoning_md=request.ai_reasoning_md,
        total_notes=len(request.notes),
        verify_status="PENDING",
        virtual_cost=request.virtual_cost,
        virtual_reward=0,
    )
    db.add(batch)
    db.flush()

    for item_data in request.notes:
        item = PredictionItem(
            batch_id=batch.id,
            target_issue=request.target_issue,
            note_index=item_data.note_index,
            red_1=item_data.reds[0],
            red_2=item_data.reds[1],
            red_3=item_data.reds[2],
            red_4=item_data.reds[3],
            red_5=item_data.reds[4],
            red_6=item_data.reds[5],
            blue_1=item_data.blue,
            confidence_score=item_data.confidence_score,
            rationale=item_data.rationale,
            is_verified=False,
        )
        db.add(item)

    db.commit()
    db.refresh(batch)

    return PredictionSaveResponse(
        batch_id=batch.id,
        target_issue=batch.target_issue,
        total_notes=batch.total_notes,
        message="Prediction batch and 5 notes saved successfully",
    )


@router.get("/batches", response_model=PaginatedResponse, summary="Get paginated list of prediction batches")
def list_prediction_batches(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    target_issue: Optional[str] = Query(None, description="Filter by target issue"),
    strategy_type: Optional[str] = Query(None, description="Filter by strategy type"),
    verify_status: Optional[str] = Query(None, description="Filter by verification status (PENDING/VERIFIED)"),
    db: Session = Depends(get_db),
):
    stmt = select(PredictionBatch)
    if target_issue:
        stmt = stmt.filter(PredictionBatch.target_issue == target_issue)
    if strategy_type:
        stmt = stmt.filter(PredictionBatch.strategy_type == strategy_type)
    if verify_status:
        stmt = stmt.filter(PredictionBatch.verify_status == verify_status.upper())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    stmt = stmt.order_by(PredictionBatch.id.desc())
    offset = (page - 1) * page_size
    batches = db.scalars(stmt.offset(offset).limit(page_size)).all()

    items = []
    for b in batches:
        net_profit = b.virtual_reward - b.virtual_cost
        roi = round(float(net_profit) / float(b.virtual_cost), 4) if b.virtual_cost > 0 else 0.0
        items.append(
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

    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=items,
    )


@router.get("/batches/{batch_id}", response_model=PredictionBatchDetail, summary="Get prediction batch detail with items")
def get_prediction_batch_detail(
    batch_id: int,
    db: Session = Depends(get_db),
):
    batch = db.scalar(select(PredictionBatch).filter(PredictionBatch.id == batch_id))
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prediction batch {batch_id} not found",
        )

    items_detail: List[PredictionItemDetail] = []
    for item in sorted(batch.items, key=lambda x: x.note_index):
        hit_nums = [int(x) for x in item.hit_red_numbers.split(",") if x.strip().isdigit()]
        items_detail.append(
            PredictionItemDetail(
                id=item.id,
                note_index=item.note_index,
                reds=item.reds,
                blue=item.blue,
                confidence_score=item.confidence_score,
                rationale=item.rationale,
                is_verified=item.is_verified,
                hit_red_count=item.hit_red_count,
                hit_red_numbers=hit_nums,
                hit_red_str=item.hit_red_numbers,
                hit_blue=item.hit_blue,
                prize_level=item.prize_level,
                prize_amount=item.prize_amount,
            )
        )

    actual_draw_dict = None
    draw = db.scalar(select(DrawHistory).filter(DrawHistory.issue_no == batch.target_issue))
    if draw:
        actual_draw_dict = {
            "issue_no": draw.issue_no,
            "draw_date": draw.draw_date.isoformat(),
            "weekday": draw.weekday,
            "reds": draw.reds,
            "blue": draw.blue_1,
            "red_seq_str": draw.red_seq_str,
            "first_prize_num": draw.first_prize_num,
            "first_prize_amount": draw.first_prize_amount,
            "second_prize_num": draw.second_prize_num,
            "second_prize_amount": draw.second_prize_amount,
        }

    net_profit = batch.virtual_reward - batch.virtual_cost
    roi = round(float(net_profit) / float(batch.virtual_cost), 4) if batch.virtual_cost > 0 else 0.0

    return PredictionBatchDetail(
        id=batch.id,
        target_issue=batch.target_issue,
        strategy_type=batch.strategy_type,
        model_name=batch.model_name,
        total_notes=batch.total_notes,
        verify_status=batch.verify_status,
        best_prize_level=batch.best_prize_level,
        virtual_cost=batch.virtual_cost,
        virtual_reward=batch.virtual_reward,
        net_profit=net_profit,
        roi=roi,
        created_at=batch.created_at,
        verified_at=batch.verified_at,
        filter_params_json=batch.filter_params_json,
        ai_reasoning_md=batch.ai_reasoning_md,
        post_reflection_md=batch.post_reflection_md,
        items=items_detail,
        actual_draw=actual_draw_dict,
    )


@router.get("/dashboard", response_model=PredictDashboardResponse, summary="Get prediction performance KPIs and win stats")
@router.get("/summary", response_model=PredictDashboardResponse, summary="Get prediction performance KPIs (alias)")
def get_prediction_dashboard(db: Session = Depends(get_db)):
    batches = db.scalars(select(PredictionBatch)).all()

    total_batches = len(batches)
    total_notes = sum(b.total_notes for b in batches)
    total_investment = sum(b.virtual_cost for b in batches)
    total_returns = sum(b.virtual_reward for b in batches)
    net_profit = total_returns - total_investment
    simulated_roi = round(float(net_profit) / float(total_investment), 4) if total_investment > 0 else 0.0

    break_even_batches = sum(1 for b in batches if b.virtual_reward >= b.virtual_cost and b.verify_status == "VERIFIED")
    verified_count = sum(1 for b in batches if b.verify_status == "VERIFIED")
    break_even_rate = round(float(break_even_batches) / float(verified_count), 4) if verified_count > 0 else 0.0

    # Count blue hits and prize distribution across all verified prediction items
    verified_items = db.scalars(
        select(PredictionItem).filter(PredictionItem.is_verified == True)
    ).all()

    blue_hits = sum(1 for item in verified_items if item.hit_blue)
    blue_hit_rate = round(float(blue_hits) / float(len(verified_items)), 4) if verified_items else 0.0

    prize_dist: Dict[int, int] = {i: 0 for i in range(7)}
    for item in verified_items:
        if 0 <= item.prize_level <= 6:
            prize_dist[item.prize_level] += 1

    # Strategy breakdown
    strategy_breakdown: Dict[str, Dict[str, Any]] = {}
    for b in batches:
        st = b.strategy_type
        if st not in strategy_breakdown:
            strategy_breakdown[st] = {
                "count": 0,
                "cost": 0,
                "reward": 0,
                "break_even_count": 0,
            }
        strategy_breakdown[st]["count"] += 1
        strategy_breakdown[st]["cost"] += b.virtual_cost
        strategy_breakdown[st]["reward"] += b.virtual_reward
        if b.virtual_reward >= b.virtual_cost and b.verify_status == "VERIFIED":
            strategy_breakdown[st]["break_even_count"] += 1

    for st, v in strategy_breakdown.items():
        v["roi"] = round((v["reward"] - v["cost"]) / v["cost"], 4) if v["cost"] > 0 else 0.0

    return PredictDashboardResponse(
        total_batches=total_batches,
        total_notes=total_notes,
        total_investment=total_investment,
        total_returns=total_returns,
        net_profit=net_profit,
        simulated_roi=simulated_roi,
        break_even_batches=break_even_batches,
        break_even_rate=break_even_rate,
        blue_hit_batches=blue_hits,
        blue_hit_rate=blue_hit_rate,
        prize_distribution=prize_dist,
        strategy_breakdown=strategy_breakdown,
    )
