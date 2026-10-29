"""
backend/app/api/history.py

History & Trend API Router:
- Draws pagination & search
- Latest official draw
- Multi-dimensional feature metrics
- Dynamic omission heatmap matrix & Cold/Warm/Hot statistics
- Mathematical indicator distributions
- Official CWL/500.com crawler incremental sync trigger
"""

import math
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, desc, asc
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import DrawHistory, FeatureMetrics, PredictionBatch
from backend.app.schemas import (
    DrawRecordItem,
    FeatureMetricsItem,
    PaginatedResponse,
    SyncRequest,
    SyncResponseData,
    OmissionTrendResponse,
    OmissionTrendItem,
    ColdWarmHotSummary,
    IndicatorDistributionResponse,
)
from backend.app.services.crawler import CrawlerService
from backend.app.services.feature_engine import FeatureEngine
from backend.app.services.verifier import VerificationService

router = APIRouter()


def _build_draw_item(draw: DrawHistory, fm: Optional[FeatureMetrics] = None) -> DrawRecordItem:
    metrics_item = None
    sum_r = None
    ac_v = None
    odd_c = None
    prime_c = None
    zones = None

    if fm:
        metrics_item = FeatureMetricsItem(
            issue_no=fm.issue_no,
            sum_red=fm.sum_red,
            span_red=fm.span_red,
            ac_value=fm.ac_value,
            odd_count=fm.odd_count,
            prime_count=fm.prime_count,
            zone1_count=fm.zone1_count,
            zone2_count=fm.zone2_count,
            zone3_count=fm.zone3_count,
            consecutive_groups=fm.consecutive_groups,
            repeat_prev_red=fm.repeat_prev_red,
            missing_sum_red=fm.missing_sum_red,
            missing_blue=fm.missing_blue,
        )
        sum_r = fm.sum_red
        ac_v = fm.ac_value
        odd_c = fm.odd_count
        prime_c = fm.prime_count
        zones = [fm.zone1_count, fm.zone2_count, fm.zone3_count]
    else:
        sum_r = sum(draw.reds)
        ac_v = FeatureEngine.calculate_ac(draw.reds)
        odd_c = FeatureEngine.calculate_odd_count(draw.reds)
        prime_c = FeatureEngine.calculate_prime_count(draw.reds)
        z1, z2, z3 = FeatureEngine.calculate_zones(draw.reds)
        zones = [z1, z2, z3]

    return DrawRecordItem(
        id=draw.id,
        issue_no=draw.issue_no,
        draw_date=draw.draw_date,
        weekday=draw.weekday,
        reds=draw.reds,
        blue=draw.blue_1,
        red_seq_str=draw.red_seq_str,
        sales_amount=draw.sales_amount,
        pool_amount=draw.pool_amount,
        first_prize_num=draw.first_prize_num,
        first_prize_amount=draw.first_prize_amount,
        second_prize_num=draw.second_prize_num,
        second_prize_amount=draw.second_prize_amount,
        metrics=metrics_item,
        sum_red=sum_r,
        ac_value=ac_v,
        odd_count=odd_c,
        prime_count=prime_c,
        zones=zones,
    )


@router.get("/draws", response_model=PaginatedResponse, summary="Get paginated historical draws")
@router.get("/list", response_model=PaginatedResponse, summary="Get paginated historical draws (alias)")
def get_draw_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=500, description="Items per page"),
    start_issue: Optional[str] = Query(None, description="Starting issue number"),
    end_issue: Optional[str] = Query(None, description="Ending issue number"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order by issue_no"),
    search_ball: Optional[int] = Query(None, ge=1, le=33, description="Filter draws containing this ball number"),
    db: Session = Depends(get_db),
):
    if start_issue and end_issue and start_issue > end_issue:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_issue cannot be greater than end_issue",
        )

    stmt = select(DrawHistory)

    if start_issue:
        stmt = stmt.filter(DrawHistory.issue_no >= start_issue)
    if end_issue:
        stmt = stmt.filter(DrawHistory.issue_no <= end_issue)

    if search_ball is not None:
        # Check if ball is in any of red_1..red_6 or blue_1
        if search_ball <= 16:
            stmt = stmt.filter(
                (DrawHistory.red_1 == search_ball)
                | (DrawHistory.red_2 == search_ball)
                | (DrawHistory.red_3 == search_ball)
                | (DrawHistory.red_4 == search_ball)
                | (DrawHistory.red_5 == search_ball)
                | (DrawHistory.red_6 == search_ball)
                | (DrawHistory.blue_1 == search_ball)
            )
        else:
            stmt = stmt.filter(
                (DrawHistory.red_1 == search_ball)
                | (DrawHistory.red_2 == search_ball)
                | (DrawHistory.red_3 == search_ball)
                | (DrawHistory.red_4 == search_ball)
                | (DrawHistory.red_5 == search_ball)
                | (DrawHistory.red_6 == search_ball)
            )

    # Count total items matching query
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    # Ordering
    if sort_order == "asc":
        stmt = stmt.order_by(DrawHistory.issue_no.asc())
    else:
        stmt = stmt.order_by(DrawHistory.issue_no.desc())

    # Pagination
    offset = (page - 1) * page_size
    draws = db.scalars(stmt.offset(offset).limit(page_size)).all()

    # Pre-fetch feature metrics for these draws
    issue_nos = [d.issue_no for d in draws]
    fm_map = {}
    if issue_nos:
        fms = db.scalars(
            select(FeatureMetrics).filter(FeatureMetrics.issue_no.in_(issue_nos))
        ).all()
        fm_map = {fm.issue_no: fm for fm in fms}

    items = [_build_draw_item(d, fm_map.get(d.issue_no)) for d in draws]
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=items,
    )


@router.get("/latest", response_model=DrawRecordItem, summary="Get latest authentic draw record")
def get_latest_draw(db: Session = Depends(get_db)):
    draw = db.scalar(select(DrawHistory).order_by(DrawHistory.issue_no.desc()).limit(1))
    if not draw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No draw history records found in database",
        )
    fm = db.scalar(select(FeatureMetrics).filter(FeatureMetrics.issue_no == draw.issue_no))
    return _build_draw_item(draw, fm)


@router.get("/metrics/{issue_no}", response_model=FeatureMetricsItem, summary="Get feature metrics for a specific issue")
def get_metrics_by_issue(issue_no: str, db: Session = Depends(get_db)):
    fm = db.scalar(select(FeatureMetrics).filter(FeatureMetrics.issue_no == issue_no))
    if not fm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature metrics for issue {issue_no} not found",
        )
    return FeatureMetricsItem(
        issue_no=fm.issue_no,
        sum_red=fm.sum_red,
        span_red=fm.span_red,
        ac_value=fm.ac_value,
        odd_count=fm.odd_count,
        prime_count=fm.prime_count,
        zone1_count=fm.zone1_count,
        zone2_count=fm.zone2_count,
        zone3_count=fm.zone3_count,
        consecutive_groups=fm.consecutive_groups,
        repeat_prev_red=fm.repeat_prev_red,
        missing_sum_red=fm.missing_sum_red,
        missing_blue=fm.missing_blue,
    )


@router.get("/metrics", response_model=List[FeatureMetricsItem], summary="Get sequence of feature metrics")
def get_metrics_sequence(
    limit: int = Query(100, ge=1, le=500, description="Number of recent records"),
    db: Session = Depends(get_db),
):
    fms = db.scalars(
        select(FeatureMetrics).order_by(FeatureMetrics.issue_no.desc()).limit(limit)
    ).all()
    # return chronologically ascending for charts
    fms_sorted = sorted(fms, key=lambda x: x.issue_no)
    return [
        FeatureMetricsItem(
            issue_no=fm.issue_no,
            sum_red=fm.sum_red,
            span_red=fm.span_red,
            ac_value=fm.ac_value,
            odd_count=fm.odd_count,
            prime_count=fm.prime_count,
            zone1_count=fm.zone1_count,
            zone2_count=fm.zone2_count,
            zone3_count=fm.zone3_count,
            consecutive_groups=fm.consecutive_groups,
            repeat_prev_red=fm.repeat_prev_red,
            missing_sum_red=fm.missing_sum_red,
            missing_blue=fm.missing_blue,
        )
        for fm in fms_sorted
    ]


@router.get("/omissions", response_model=OmissionTrendResponse, summary="Get omission heatmap and trend matrix")
@router.get("/trends", response_model=OmissionTrendResponse, summary="Get omission heatmap and trend matrix (alias)")
def get_omission_trends(
    limit: Optional[int] = Query(None, ge=10, le=100, description="Number of issues (10-100)"),
    issues: Optional[int] = Query(None, ge=10, le=100, description="Alias for limit"),
    db: Session = Depends(get_db),
):
    n_issues = limit or issues or 30
    if n_issues < 10 or n_issues > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Number of issues must be between 10 and 100",
        )

    # Fetch recent N draws and their feature metrics
    draws = db.scalars(
        select(DrawHistory).order_by(DrawHistory.issue_no.desc()).limit(n_issues)
    ).all()

    if not draws:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No draws available")

    draws_chrono = sorted(draws, key=lambda x: x.issue_no)
    issue_nos = [d.issue_no for d in draws_chrono]

    fms = db.scalars(
        select(FeatureMetrics).filter(FeatureMetrics.issue_no.in_(issue_nos))
    ).all()
    fm_map = {fm.issue_no: fm for fm in fms}

    timeline: List[OmissionTrendItem] = []
    current_red_omissions: Dict[int, int] = {}
    current_blue_omissions: Dict[int, int] = {}

    for d in draws_chrono:
        fm = fm_map.get(d.issue_no)
        if fm and fm.missing_snapshot:
            red_dict, blue_dict = FeatureEngine.parse_omission_snapshot(fm.missing_snapshot)
        else:
            red_dict, blue_dict = FeatureEngine.get_initial_omission_state()

        timeline.append(
            OmissionTrendItem(
                issue_no=d.issue_no,
                draw_date=d.draw_date.isoformat(),
                red_omissions={str(k): v for k, v in red_dict.items()},
                blue_omissions={str(k): v for k, v in blue_dict.items()},
                drawn_reds=d.reds,
                drawn_blue=d.blue_1,
            )
        )
        current_red_omissions = red_dict
        current_blue_omissions = blue_dict

    # Cold / Warm / Hot classification for latest state
    hot_reds = [b for b, o in current_red_omissions.items() if o <= 4]
    warm_reds = [b for b, o in current_red_omissions.items() if 5 <= o <= 9]
    cold_reds = [b for b, o in current_red_omissions.items() if o >= 10]

    hot_blues = [b for b, o in current_blue_omissions.items() if o <= 4]
    warm_blues = [b for b, o in current_blue_omissions.items() if 5 <= o <= 9]
    cold_blues = [b for b, o in current_blue_omissions.items() if o >= 10]

    top3_hot_reds = sorted(current_red_omissions.keys(), key=lambda b: (current_red_omissions[b], b))[:3]
    top3_cold_reds = sorted(current_red_omissions.keys(), key=lambda b: (-current_red_omissions[b], b))[:3]

    top3_hot_blues = sorted(current_blue_omissions.keys(), key=lambda b: (current_blue_omissions[b], b))[:3]
    top3_cold_blues = sorted(current_blue_omissions.keys(), key=lambda b: (-current_blue_omissions[b], b))[:3]

    return OmissionTrendResponse(
        issues=issue_nos,
        timeline=timeline,
        current_red_omissions=current_red_omissions,
        current_blue_omissions=current_blue_omissions,
        cold_warm_hot=ColdWarmHotSummary(
            hot_reds=sorted(hot_reds),
            warm_reds=sorted(warm_reds),
            cold_reds=sorted(cold_reds),
            hot_blues=sorted(hot_blues),
            warm_blues=sorted(warm_blues),
            cold_blues=sorted(cold_blues),
        ),
        top3_hot_reds=top3_hot_reds,
        top3_cold_reds=top3_cold_reds,
        top3_hot_blues=top3_hot_blues,
        top3_cold_blues=top3_cold_blues,
    )


@router.get("/distributions", response_model=IndicatorDistributionResponse, summary="Get mathematical indicator distributions")
def get_indicator_distributions(
    recent_n: int = Query(100, ge=1, le=1000, description="Number of recent draws to evaluate"),
    db: Session = Depends(get_db),
):
    fms = db.scalars(
        select(FeatureMetrics).order_by(FeatureMetrics.issue_no.desc()).limit(recent_n)
    ).all()

    if not fms:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No feature metrics found")

    sum_dist: Dict[str, int] = {}
    ac_dist: Dict[int, int] = {i: 0 for i in range(11)}
    oe_dist: Dict[str, int] = {}
    span_dist: Dict[str, int] = {}
    zone_dist: Dict[str, int] = {}

    for fm in fms:
        # Sum range binning [20-29, 30-39, ..., 180-189]
        bin_start = (fm.sum_red // 10) * 10
        bin_label = f"{bin_start}-{bin_start + 9}"
        sum_dist[bin_label] = sum_dist.get(bin_label, 0) + 1

        # AC distribution
        if 0 <= fm.ac_value <= 10:
            ac_dist[fm.ac_value] += 1

        # Odd-Even
        oe_label = f"{fm.odd_count}:{6 - fm.odd_count}"
        oe_dist[oe_label] = oe_dist.get(oe_label, 0) + 1

        # Span range binning [10-14, 15-19, 20-24, 25-29, 30-34]
        span_bin = f"{(fm.span_red // 5) * 5}-{(fm.span_red // 5) * 5 + 4}"
        span_dist[span_bin] = span_dist.get(span_bin, 0) + 1

        # Zone pattern e.g. "2:2:2"
        z_label = f"{fm.zone1_count}:{fm.zone2_count}:{fm.zone3_count}"
        zone_dist[z_label] = zone_dist.get(z_label, 0) + 1

    return IndicatorDistributionResponse(
        sample_size=len(fms),
        sum_distribution=dict(sorted(sum_dist.items())),
        ac_distribution=ac_dist,
        odd_even_distribution=dict(sorted(oe_dist.items())),
        span_distribution=dict(sorted(span_dist.items())),
        zone_distribution=dict(sorted(zone_dist.items())),
    )


@router.post("/sync", response_model=SyncResponseData, summary="Trigger incremental data synchronization")
def sync_latest_draws(
    request: SyncRequest = SyncRequest(),
    db: Session = Depends(get_db),
):
    try:
        crawler = CrawlerService()
        new_draws = crawler.sync_latest(force=request.force)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Crawler synchronization failed: {str(e)}",
        )

    # Recompute feature metrics for new draws
    try:
        engine = FeatureEngine()
        new_features = engine.compute_latest_features()
    except Exception as e:
        new_features = 0

    # Invalidate collision cache if new draws imported
    if new_draws > 0:
        try:
            from backend.app.services.collision_cache import CollisionCache
            CollisionCache.get_instance().invalidate()
        except Exception:
            pass

    # Optional auto-verify pending prediction batches
    verified_count = 0
    if request.auto_verify:
        try:
            pending_batches = db.scalars(
                select(PredictionBatch).filter(PredictionBatch.verify_status == "PENDING")
            ).all()
            verifier = VerificationService()
            for b in pending_batches:
                # check if target_issue draw is present
                draw = db.scalar(select(DrawHistory).filter(DrawHistory.issue_no == b.target_issue))
                if draw:
                    verifier.verify_batch(b.id, session=db)
                    verified_count += 1
            db.commit()
        except Exception:
            pass

    total_draws = db.scalar(select(func.count(DrawHistory.id))) or 0
    min_issue = db.scalar(select(func.min(DrawHistory.issue_no)))
    max_issue = db.scalar(select(func.max(DrawHistory.issue_no)))

    return SyncResponseData(
        success=True,
        affected_draws=new_draws,
        new_draws=new_draws,
        total_draws_in_db=total_draws,
        computed_features=new_features,
        new_features=new_features,
        verified_batches=verified_count,
        earliest_issue=min_issue,
        latest_issue=max_issue,
        message=f"Sync successful: {new_draws} new draws, {new_features} features computed, {verified_count} batches verified",
    )
