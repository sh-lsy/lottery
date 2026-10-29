"""
backend/app/api/adaptive.py

Adaptive Strategy Feedback Loop API Router:
- Active adaptive state & hyperparameter status
- Chronological trajectory history of state transitions & reflections
- Manual parameter reset to canonical baseline
- Manual adaptive evolution trigger
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import AdaptiveState, AdaptiveHistory, DrawHistory
from backend.app.schemas import (
    AdaptiveStateResponse,
    AdaptiveTrajectoryResponse,
    AdaptiveTrajectoryItem,
    AdaptiveTriggerRequest,
)
from backend.app.services.adaptive_service import AdaptiveService

router = APIRouter()


def _build_state_response(state: AdaptiveState, current_issue: Optional[str]) -> AdaptiveStateResponse:
    w_hazard = round(float(state.cold_reversion_weight), 4)
    w_markov = round(float(state.markov_weight), 4)
    w_momentum = round(float(state.hot_momentum_weight), 4)

    weights_dict = {
        "hazard": w_hazard,
        "markov": w_markov,
        "momentum": w_momentum,
    }

    triggered = bool(state.consecutive_deficit_count >= state.loss_threshold)

    return AdaptiveStateResponse(
        current_issue=current_issue or state.last_trigger_issue,
        consecutive_deficit_count=state.consecutive_deficit_count,
        consecutive_losses=state.consecutive_deficit_count,
        adaptation_triggered=triggered,
        trigger_threshold=state.loss_threshold,
        loss_threshold=state.loss_threshold,
        weights=weights_dict,
        current_weights=weights_dict,
        blue_mode=state.current_blue_mode,
        current_strategy_mode=state.current_strategy_mode,
        temperature_tau=state.temperature_tau,
        sum_range=[state.sum_range_min, state.sum_range_max],
        last_deviation={
            "sum_bias": state.sum_bias,
            "odd_bias": state.odd_bias,
        },
        active_hyperparams={
            "ac_min": state.ac_min_override,
            "sum_range": [state.sum_range_min, state.sum_range_max],
            "temperature_tau": state.temperature_tau,
        },
        last_trigger_issue=state.last_trigger_issue,
        last_trigger_reason=state.last_trigger_reason,
        evolution_version=state.evolution_version,
        updated_at=state.updated_at.isoformat() if state.updated_at else None,
    )


@router.get("/status", response_model=AdaptiveStateResponse, summary="Get current adaptive evolution state & hyperparameters")
@router.get("/state", response_model=AdaptiveStateResponse, summary="Get current adaptive evolution state (alias)")
def get_adaptive_status(db: Session = Depends(get_db)):
    service = AdaptiveService()
    state = service.get_or_create_state(db)
    max_issue = db.scalar(select(func.max(DrawHistory.issue_no)))
    return _build_state_response(state, max_issue)


@router.get("/trajectory", response_model=AdaptiveTrajectoryResponse, summary="Get chronological log of adaptive evolution events")
def get_adaptive_trajectory(
    limit: int = Query(20, ge=1, le=100, description="Maximum history items to return"),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count(AdaptiveHistory.id))) or 0
    records = db.scalars(
        select(AdaptiveHistory).order_by(AdaptiveHistory.id.desc()).limit(limit)
    ).all()

    items: List[AdaptiveTrajectoryItem] = []
    for r in records:
        d = r.to_dict()
        items.append(
            AdaptiveTrajectoryItem(
                id=r.id,
                issue_no=r.trigger_issue,
                trigger_issue=r.trigger_issue,
                consecutive_deficit_count=r.streak_length,
                consecutive_losses=r.streak_length,
                is_triggered=bool(r.streak_length >= 3),
                trigger_event=r.trigger_reason,
                trigger_reason=r.trigger_reason,
                weight_hazard=d["new_weights"].get("hazard", 0.40),
                weight_markov=d["new_weights"].get("markov", 0.35),
                weight_momentum=d["new_weights"].get("momentum", 0.25),
                prev_weights=d["prev_weights"],
                new_weights=d["new_weights"],
                prev_mode=d["prev_mode"],
                new_mode=d["new_mode"],
                blue_mode=d["new_mode"],
                sum_deviation=d["sum_deviation"],
                odd_deviation=d["odd_deviation"],
                cold_deviation=d["cold_deviation"],
                hot_deviation=d["hot_deviation"],
                bias_metrics=d["bias_metrics"],
                action_taken=d["action_taken"],
                reflection_notes=r.reflection_notes,
                created_at=r.created_at,
            )
        )

    return AdaptiveTrajectoryResponse(
        total_records=total,
        items=items,
    )


@router.post("/reset", response_model=AdaptiveStateResponse, summary="Reset adaptive hyperparameters to baseline defaults")
def reset_adaptive_state(db: Session = Depends(get_db)):
    service = AdaptiveService()
    state = service.reset_state(db)
    db.commit()
    max_issue = db.scalar(select(func.max(DrawHistory.issue_no)))
    return _build_state_response(state, max_issue)


@router.post("/trigger", response_model=AdaptiveStateResponse, summary="Manually trigger adaptive parameter evaluation")
def trigger_adaptive_evaluation(
    request: AdaptiveTriggerRequest = AdaptiveTriggerRequest(),
    db: Session = Depends(get_db),
):
    service = AdaptiveService()
    state = service.get_or_create_state(db)

    if request.custom_threshold:
        state.loss_threshold = request.custom_threshold

    if request.force:
        # Force a mode switch and weight shift for demonstration or testing
        if state.current_blue_mode == "CONCENTRATED":
            state.current_blue_mode = "DISPERSED"
            state.current_strategy_mode = "DISPERSED_BASELINE"
        else:
            state.current_blue_mode = "CONCENTRATED"
            state.current_strategy_mode = "CONCENTRATED_BREAK_EVEN"

        # Shift weights slightly towards momentum
        delta = 0.05
        state.hot_momentum_weight = min(0.55, state.hot_momentum_weight + delta)
        state.cold_reversion_weight = max(0.20, state.cold_reversion_weight - delta)
        total = state.cold_reversion_weight + state.markov_weight + state.hot_momentum_weight
        state.cold_reversion_weight = round(state.cold_reversion_weight / total, 4)
        state.markov_weight = round(state.markov_weight / total, 4)
        state.hot_momentum_weight = round(state.hot_momentum_weight / total, 4)
        state.evolution_version += 1
        state.last_trigger_reason = "FORCED_TRIGGER"
        db.commit()

    max_issue = db.scalar(select(func.max(DrawHistory.issue_no)))
    return _build_state_response(state, max_issue)
