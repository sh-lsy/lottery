"""
backend/app/schemas.py

Comprehensive Pydantic v2 schemas for SSQ-Quant-System RESTful API.
Covers:
1. Generic API and pagination responses.
2. History and trend matrices.
3. Local quant prediction requests, candidate pools, 5-line notes, and archives.
4. Official verification audits and dashboard metrics.
5. Historical 3500+ draw collision sandbox and backtesting.
6. Adaptive strategy self-evolution states and trajectory events.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Generic API Responses
# ---------------------------------------------------------------------------

class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Optional[Any] = None


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[Any]


# ---------------------------------------------------------------------------
# History Schemas
# ---------------------------------------------------------------------------

class FeatureMetricsItem(BaseModel):
    issue_no: str
    sum_red: int
    span_red: int
    ac_value: int
    odd_count: int
    prime_count: int
    zone1_count: int
    zone2_count: int
    zone3_count: int
    consecutive_groups: int
    repeat_prev_red: int
    missing_sum_red: int
    missing_blue: int


class DrawRecordItem(BaseModel):
    id: int
    issue_no: str
    draw_date: Union[date, str]
    weekday: int
    reds: List[int] = Field(..., min_length=6, max_length=6)
    blue: int = Field(..., ge=1, le=16)
    red_seq_str: Optional[str] = None
    sales_amount: int = 0
    pool_amount: int = 0
    first_prize_num: int = 0
    first_prize_amount: int = 0
    second_prize_num: int = 0
    second_prize_amount: int = 0
    metrics: Optional[FeatureMetricsItem] = None
    sum_red: Optional[int] = None
    ac_value: Optional[int] = None
    odd_count: Optional[int] = None
    prime_count: Optional[int] = None
    zones: Optional[List[int]] = None


DrawHistoryItem = DrawRecordItem


class DrawPaginationResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[DrawRecordItem]


class SyncRequest(BaseModel):
    force: bool = False
    auto_verify: bool = True


class SyncResponseData(BaseModel):
    success: bool = True
    affected_draws: int = 0
    new_draws: int = 0
    total_draws_in_db: int = 0
    computed_features: int = 0
    new_features: int = 0
    verified_batches: int = 0
    earliest_issue: Optional[str] = None
    latest_issue: Optional[str] = None
    message: Optional[str] = "Sync completed successfully"


SyncResponse = SyncResponseData


class OmissionTrendItem(BaseModel):
    issue_no: str
    draw_date: str
    red_omissions: Dict[str, int]
    blue_omissions: Dict[str, int]
    drawn_reds: List[int]
    drawn_blue: int


class ColdWarmHotSummary(BaseModel):
    hot_reds: List[int]
    warm_reds: List[int]
    cold_reds: List[int]
    hot_blues: List[int]
    warm_blues: List[int]
    cold_blues: List[int]


class OmissionTrendResponse(BaseModel):
    issues: List[str]
    timeline: List[OmissionTrendItem]
    current_red_omissions: Dict[int, int]
    current_blue_omissions: Dict[int, int]
    cold_warm_hot: ColdWarmHotSummary
    top3_hot_reds: List[int]
    top3_cold_reds: List[int]
    top3_hot_blues: List[int]
    top3_cold_blues: List[int]


class TrendMatrixResponse(BaseModel):
    issues: List[str]
    dates: List[str]
    red_omissions: List[Dict[str, int]]
    blue_omissions: List[Dict[str, int]]
    drawn_reds: List[List[int]]
    drawn_blues: List[int]
    statistics: Dict[str, Any]


class IndicatorDistributionResponse(BaseModel):
    sample_size: int
    sum_distribution: Dict[str, int]
    ac_distribution: Dict[int, int]
    odd_even_distribution: Dict[str, int]
    span_distribution: Dict[str, int]
    zone_distribution: Dict[str, int]


# ---------------------------------------------------------------------------
# Prediction Schemas
# ---------------------------------------------------------------------------

class PredictionNoteItem(BaseModel):
    note_index: int = Field(..., ge=1, le=5)
    reds: List[int] = Field(..., min_length=6, max_length=6)
    blue: int = Field(..., ge=1, le=16)
    confidence_score: float = 0.0
    rationale: Optional[str] = None
    sum_red: Optional[int] = None
    ac_value: Optional[int] = None
    odd_count: Optional[int] = None
    span_red: Optional[int] = None
    metrics: Optional[Dict[str, Any]] = None

    @field_validator("reds")
    @classmethod
    def validate_reds(cls, v: List[int]) -> List[int]:
        if len(set(v)) != 6:
            raise ValueError("All 6 red balls must be distinct.")
        if any(r < 1 or r > 33 for r in v):
            raise ValueError("Red balls must be in range 1..33.")
        return sorted(v)


NoteItemSchema = PredictionNoteItem


class PredictionGenerateRequest(BaseModel):
    target_issue: Optional[str] = None
    strategy_type: str = "CONCENTRATED_BREAK_EVEN"
    strategy: Optional[str] = None  # alias
    ac_min: int = 6
    sum_min: int = 75
    sum_max: int = 135
    odd_counts: List[int] = [2, 3, 4]
    max_consecutive_pairs: int = 2
    span_min: int = 18
    span_max: int = 30
    blue_mode: Optional[str] = None
    adaptive_enabled: bool = True
    save_to_db: bool = False
    persist: bool = False  # alias
    custom_filters: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.sum_min > self.sum_max:
            raise ValueError("sum_min must be <= sum_max")
        if self.span_min > self.span_max:
            raise ValueError("span_min must be <= span_max")
        if self.strategy and not self.strategy_type:
            self.strategy_type = self.strategy
        return self


PredictRequest = PredictionGenerateRequest


class CandidatePoolSummary(BaseModel):
    cores: List[int]
    satellites: List[int]


class BlueProbabilityItem(BaseModel):
    ball: int
    probability: float
    rank: int


class PredictionGenerateResponse(BaseModel):
    target_issue: str
    strategy_type: str
    model_name: str
    total_notes: int = 5
    notes: List[PredictionNoteItem]
    ai_reasoning_md: str
    filter_params: Dict[str, Any]
    candidate_pool: Any
    blue_probabilities: Optional[List[BlueProbabilityItem]] = None
    break_even_matrix: Optional[Dict[str, Any]] = None
    batch_id: Optional[int] = None


PredictResponse = PredictionGenerateResponse


class PredictionSaveRequest(BaseModel):
    target_issue: str
    strategy_type: str = "CONCENTRATED_BREAK_EVEN"
    model_name: Optional[str] = "Ensemble-Hazard-Markov-Momentum"
    filter_params: Optional[Dict[str, Any]] = None
    ai_reasoning_md: Optional[str] = None
    notes: List[PredictionNoteItem]
    virtual_cost: int = 10

    @field_validator("notes")
    @classmethod
    def validate_5_notes(cls, v: List[PredictionNoteItem]) -> List[PredictionNoteItem]:
        if len(v) != 5:
            raise ValueError("A prediction batch must contain exactly 5 notes.")
        return v


SavePredictionRequest = PredictionSaveRequest


class PredictionSaveResponse(BaseModel):
    batch_id: int
    target_issue: str
    total_notes: int
    message: str = "Prediction batch saved successfully"


class PredictionBatchSummary(BaseModel):
    id: int
    target_issue: str
    strategy_type: str
    model_name: Optional[str] = None
    total_notes: int
    verify_status: str
    best_prize_level: int
    virtual_cost: int
    virtual_reward: int
    net_profit: int
    roi: float
    created_at: Union[datetime, str]
    verified_at: Optional[Union[datetime, str]] = None


class PredictionItemDetail(BaseModel):
    id: int
    note_index: int
    reds: List[int]
    blue: int
    confidence_score: float
    rationale: Optional[str] = None
    is_verified: bool
    hit_red_count: int
    hit_red_numbers: List[int]
    hit_red_str: Optional[str] = None
    hit_blue: bool
    prize_level: int
    prize_amount: int


class PredictionBatchDetail(PredictionBatchSummary):
    filter_params_json: Optional[str] = None
    ai_reasoning_md: Optional[str] = None
    post_reflection_md: Optional[str] = None
    items: List[PredictionItemDetail]
    actual_draw: Optional[Any] = None


class PredictDashboardResponse(BaseModel):
    total_batches: int
    total_notes: int
    total_investment: int
    total_returns: int
    net_profit: int
    simulated_roi: float
    break_even_batches: int
    break_even_rate: float
    blue_hit_batches: int
    blue_hit_rate: float
    prize_distribution: Dict[int, int]
    strategy_breakdown: Optional[Dict[str, Any]] = None


PredictSummaryResponse = PredictDashboardResponse


# ---------------------------------------------------------------------------
# Verification Schemas
# ---------------------------------------------------------------------------

class VerifyIssueRequest(BaseModel):
    force: bool = False


class VerifyIssueResponse(BaseModel):
    issue_no: str
    verified_batches_count: int
    total_virtual_cost: int
    total_virtual_reward: int
    best_prize_level: int
    verified_batches: List[PredictionBatchSummary]


# ---------------------------------------------------------------------------
# Sandbox Collision & Backtesting Schemas
# ---------------------------------------------------------------------------

class SandboxCollisionRequest(BaseModel):
    reds: List[int] = Field(..., min_length=6, max_length=6)
    blue: int = Field(..., ge=1, le=16)

    @field_validator("reds")
    @classmethod
    def validate_reds(cls, v: List[int]) -> List[int]:
        if len(set(v)) != 6:
            raise ValueError("All 6 red balls must be distinct.")
        if any(r < 1 or r > 33 for r in v):
            raise ValueError("Red balls must be in range 1..33.")
        return sorted(v)


SandboxRequest = SandboxCollisionRequest


class HistoricalMatchItem(BaseModel):
    issue_no: str
    draw_date: Union[date, str]
    actual_reds: List[int]
    actual_blue: int
    hit_red_count: int
    hit_reds: List[int]
    hit_blue: bool
    prize_level: int
    prize_amount: int


class QuantileMetricItem(BaseModel):
    metric_name: str
    ticket_value: float
    historical_mean: float
    historical_min: float
    historical_max: float
    percentile: float
    evaluation: str


class SandboxCollisionResponse(BaseModel):
    ticket_reds: List[int]
    ticket_blue: int
    input_reds: Optional[List[int]] = None
    input_blue: Optional[int] = None
    total_draws_analyzed: int
    total_draws_scanned: Optional[int] = None
    highest_prize_level: int
    highest_prize_name: str
    best_prize_level: Optional[int] = None
    best_prize_name: Optional[str] = None
    best_prize_issue: Optional[str] = None
    total_historical_payout: int
    total_payout: Optional[int] = None
    hypothetical_cost: int
    total_cost: Optional[int] = None
    hypothetical_net_profit: int
    net_profit: Optional[int] = None
    hypothetical_roi: float
    simulated_roi: Optional[float] = None
    prize_counts: Dict[str, int]
    prize_distribution: Optional[Dict[int, int]] = None
    features: Optional[Dict[str, Any]] = None
    percentiles: Optional[Dict[str, float]] = None
    quantile_metrics: Optional[List[QuantileMetricItem]] = None
    top_matches: Optional[List[HistoricalMatchItem]] = None


SandboxResponse = SandboxCollisionResponse


class BacktestRunRequest(BaseModel):
    n_issues: int = Field(50, ge=1, le=500)
    strategy: str = "CONCENTRATED_BREAK_EVEN"


class BacktestResult(BaseModel):
    total_issues: int
    strategy: str
    total_investment: int
    total_return: int
    net_profit: int
    roi: float
    break_even_rate: float
    blue_hit_rate: float
    max_drawdown: float
    prize_distribution: Dict[int, int]


class BacktestCompareRequest(BaseModel):
    n_issues: int = Field(50, ge=1, le=500)


class StrategyComparisonReport(BaseModel):
    n_issues: int
    concentrated_result: Dict[str, Any]
    dispersed_result: Dict[str, Any]
    comparison_summary: str


# ---------------------------------------------------------------------------
# Adaptive Evolution Schemas
# ---------------------------------------------------------------------------

class AdaptiveStateResponse(BaseModel):
    current_issue: Optional[str] = None
    consecutive_deficit_count: int
    consecutive_losses: Optional[int] = None
    adaptation_triggered: bool
    trigger_threshold: int
    loss_threshold: Optional[int] = None
    weights: Dict[str, float]
    current_weights: Optional[Dict[str, float]] = None
    blue_mode: str
    current_strategy_mode: Optional[str] = None
    temperature_tau: Optional[float] = None
    sum_range: Optional[List[int]] = None
    last_deviation: Optional[Dict[str, float]] = None
    active_hyperparams: Optional[Dict[str, Any]] = None
    last_trigger_issue: Optional[str] = None
    last_trigger_reason: Optional[str] = None
    evolution_version: Optional[int] = None
    updated_at: Optional[str] = None


AdaptiveStatusResponse = AdaptiveStateResponse


class AdaptiveTrajectoryItem(BaseModel):
    id: int
    issue_no: str
    trigger_issue: Optional[str] = None
    consecutive_deficit_count: int
    consecutive_losses: Optional[int] = None
    is_triggered: bool
    trigger_event: Optional[str] = None
    trigger_reason: Optional[str] = None
    weight_hazard: float
    weight_markov: float
    weight_momentum: float
    prev_weights: Optional[Dict[str, float]] = None
    new_weights: Optional[Dict[str, float]] = None
    prev_mode: Optional[str] = None
    new_mode: Optional[str] = None
    blue_mode: str
    sum_deviation: float
    odd_deviation: float
    cold_deviation: float
    hot_deviation: float
    bias_metrics: Optional[Dict[str, Any]] = None
    action_taken: Optional[str] = None
    reflection_notes: Optional[str] = None
    created_at: Union[datetime, str]


AdaptiveHistoryItem = AdaptiveTrajectoryItem


class AdaptiveTrajectoryResponse(BaseModel):
    total_records: int
    items: List[AdaptiveTrajectoryItem]


class AdaptiveTriggerRequest(BaseModel):
    force: bool = False
    custom_threshold: Optional[int] = None
