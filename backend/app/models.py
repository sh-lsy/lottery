"""
SQLAlchemy 2.0 ORM models for SSQ-Quant-System.
Defines 4 core tables:
1. DrawHistory (ssq_draw_history): Official draw history records.
2. FeatureMetrics (ssq_feature_metrics): Quantitative features per draw.
3. PredictionBatch (ssq_prediction_batches): 5-line prediction task batches.
4. PredictionItem (ssq_prediction_items): Individual 5-line combination predictions.
"""

from datetime import date, datetime
import json
from typing import List, Optional, Dict, Any

from sqlalchemy import (
    Integer,
    BigInteger,
    String,
    Date,
    DateTime,
    Float,
    Boolean,
    Text,
    ForeignKey,
    CheckConstraint,
    Index,
    desc,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class DrawHistory(Base):
    """
    Main table storing authentic historical Shuangseqiu draw records.
    Covers issue 2003001 to present.
    """
    __tablename__ = "ssq_draw_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_no: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    draw_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    red_1: Mapped[int] = mapped_column(Integer, nullable=False)
    red_2: Mapped[int] = mapped_column(Integer, nullable=False)
    red_3: Mapped[int] = mapped_column(Integer, nullable=False)
    red_4: Mapped[int] = mapped_column(Integer, nullable=False)
    red_5: Mapped[int] = mapped_column(Integer, nullable=False)
    red_6: Mapped[int] = mapped_column(Integer, nullable=False)
    blue_1: Mapped[int] = mapped_column(Integer, nullable=False)
    red_seq_str: Mapped[str] = mapped_column(String(30), nullable=False)
    sales_amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    pool_amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    first_prize_num: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_prize_amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    second_prize_num: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    second_prize_amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "red_1 >= 1 AND red_1 < red_2 AND red_2 < red_3 AND red_3 < red_4 AND red_4 < red_5 AND red_5 < red_6 AND red_6 <= 33",
            name="chk_red_order",
        ),
        CheckConstraint("blue_1 >= 1 AND blue_1 <= 16", name="chk_blue_range"),
        CheckConstraint("weekday IN (1, 2, 3, 4, 5, 6, 7)", name="chk_weekday"),
        Index("idx_draw_issue_desc", desc("issue_no")),
        Index("idx_draw_date_desc", desc("draw_date")),
    )

    # 1:1 Relationship with FeatureMetrics
    feature_metrics: Mapped[Optional["FeatureMetrics"]] = relationship(
        back_populates="draw_history",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def reds(self) -> List[int]:
        """Return red balls as a list of integers."""
        return [self.red_1, self.red_2, self.red_3, self.red_4, self.red_5, self.red_6]

    @property
    def blue(self) -> int:
        """Return blue ball integer."""
        return self.blue_1

    def to_dict(self) -> Dict[str, Any]:
        """Convert model attributes to dictionary."""
        return {
            "id": self.id,
            "issue_no": self.issue_no,
            "draw_date": self.draw_date.isoformat() if self.draw_date else None,
            "weekday": self.weekday,
            "red_1": self.red_1,
            "red_2": self.red_2,
            "red_3": self.red_3,
            "red_4": self.red_4,
            "red_5": self.red_5,
            "red_6": self.red_6,
            "reds": self.reds,
            "blue_1": self.blue_1,
            "blue": self.blue_1,
            "red_seq_str": self.red_seq_str,
            "sales_amount": self.sales_amount,
            "pool_amount": self.pool_amount,
            "first_prize_num": self.first_prize_num,
            "first_prize_amount": self.first_prize_amount,
            "second_prize_num": self.second_prize_num,
            "second_prize_amount": self.second_prize_amount,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<DrawHistory issue={self.issue_no} date={self.draw_date} reds={self.red_seq_str} blue={self.blue_1:02d}>"


class FeatureMetrics(Base):
    """
    Derived quantitative features for each historical draw.
    Includes AC value, sum, span, odd/even, primes, zones, omission counters.
    """
    __tablename__ = "ssq_feature_metrics"

    issue_no: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("ssq_draw_history.issue_no", ondelete="CASCADE"),
        primary_key=True,
    )
    sum_red: Mapped[int] = mapped_column(Integer, nullable=False)
    span_red: Mapped[int] = mapped_column(Integer, nullable=False)
    ac_value: Mapped[int] = mapped_column(Integer, nullable=False)
    odd_count: Mapped[int] = mapped_column(Integer, nullable=False)
    prime_count: Mapped[int] = mapped_column(Integer, nullable=False)
    zone1_count: Mapped[int] = mapped_column(Integer, nullable=False)
    zone2_count: Mapped[int] = mapped_column(Integer, nullable=False)
    zone3_count: Mapped[int] = mapped_column(Integer, nullable=False)
    consecutive_groups: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    repeat_prev_red: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missing_sum_red: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missing_blue: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missing_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("zone1_count + zone2_count + zone3_count = 6", name="chk_zone_sum"),
        CheckConstraint("odd_count >= 0 AND odd_count <= 6", name="chk_odd_range"),
        CheckConstraint("prime_count >= 0 AND prime_count <= 6", name="chk_prime_range"),
        CheckConstraint("ac_value >= 0 AND ac_value <= 10", name="chk_ac_range"),
    )

    draw_history: Mapped["DrawHistory"] = relationship(back_populates="feature_metrics")

    @property
    def missing_snapshot(self) -> Dict[str, Any]:
        """Parsed omission snapshot JSON."""
        return json.loads(self.missing_snapshot_json) if self.missing_snapshot_json else {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert feature metrics to dictionary."""
        return {
            "issue_no": self.issue_no,
            "sum_red": self.sum_red,
            "span_red": self.span_red,
            "ac_value": self.ac_value,
            "odd_count": self.odd_count,
            "prime_count": self.prime_count,
            "zone1_count": self.zone1_count,
            "zone2_count": self.zone2_count,
            "zone3_count": self.zone3_count,
            "consecutive_groups": self.consecutive_groups,
            "repeat_prev_red": self.repeat_prev_red,
            "missing_sum_red": self.missing_sum_red,
            "missing_blue": self.missing_blue,
            "missing_snapshot": self.missing_snapshot,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<FeatureMetrics issue={self.issue_no} sum={self.sum_red} ac={self.ac_value}>"


class PredictionBatch(Base):
    """
    Prediction task batch record.
    Typically encapsulates exactly 5 prediction lines for a target issue.
    """
    __tablename__ = "ssq_prediction_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_issue: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    strategy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="default")
    filter_params_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_reasoning_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_notes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    verify_status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True, nullable=False)
    best_prize_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    virtual_cost: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    virtual_reward: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    post_reflection_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint("verify_status IN ('PENDING', 'VERIFIED')", name="chk_verify_status"),
        Index("idx_pred_batch_issue", desc("target_issue")),
        Index("idx_pred_batch_status", "verify_status"),
    )

    # 1:N Relationship with PredictionItem
    items: Mapped[List["PredictionItem"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="PredictionItem.note_index",
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert prediction batch to dictionary."""
        return {
            "id": self.id,
            "target_issue": self.target_issue,
            "strategy_type": self.strategy_type,
            "model_name": self.model_name,
            "filter_params_json": self.filter_params_json,
            "ai_reasoning_md": self.ai_reasoning_md,
            "total_notes": self.total_notes,
            "verify_status": self.verify_status,
            "best_prize_level": self.best_prize_level,
            "virtual_cost": self.virtual_cost,
            "virtual_reward": self.virtual_reward,
            "post_reflection_md": self.post_reflection_md,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "items": [item.to_dict() for item in self.items] if self.items else [],
        }

    def __repr__(self) -> str:
        return f"<PredictionBatch id={self.id} target={self.target_issue} strategy={self.strategy_type} status={self.verify_status}>"


class PredictionItem(Base):
    """
    Individual ticket line within a prediction batch.
    Includes 6 reds, 1 blue, confidence score, and verification results.
    """
    __tablename__ = "ssq_prediction_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ssq_prediction_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_issue: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    note_index: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    red_1: Mapped[int] = mapped_column(Integer, nullable=False)
    red_2: Mapped[int] = mapped_column(Integer, nullable=False)
    red_3: Mapped[int] = mapped_column(Integer, nullable=False)
    red_4: Mapped[int] = mapped_column(Integer, nullable=False)
    red_5: Mapped[int] = mapped_column(Integer, nullable=False)
    red_6: Mapped[int] = mapped_column(Integer, nullable=False)
    blue_1: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hit_red_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hit_red_numbers: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    hit_blue: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    prize_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prize_amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "red_1 >= 1 AND red_1 < red_2 AND red_2 < red_3 AND red_3 < red_4 AND red_4 < red_5 AND red_5 < red_6 AND red_6 <= 33",
            name="chk_note_red_order",
        ),
        CheckConstraint("blue_1 >= 1 AND blue_1 <= 16", name="chk_note_blue"),
        CheckConstraint("note_index >= 1 AND note_index <= 5", name="chk_note_index"),
        Index("idx_pred_items_batch", "batch_id"),
        Index("idx_pred_items_issue", "target_issue"),
    )

    batch: Mapped["PredictionBatch"] = relationship(back_populates="items")

    @property
    def reds(self) -> List[int]:
        """Return predicted red balls as sorted list of ints."""
        return [self.red_1, self.red_2, self.red_3, self.red_4, self.red_5, self.red_6]

    @property
    def blue(self) -> int:
        """Return predicted blue ball int."""
        return self.blue_1

    def to_dict(self) -> Dict[str, Any]:
        """Convert prediction item to dictionary."""
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "target_issue": self.target_issue,
            "note_index": self.note_index,
            "red_1": self.red_1,
            "red_2": self.red_2,
            "red_3": self.red_3,
            "red_4": self.red_4,
            "red_5": self.red_5,
            "red_6": self.red_6,
            "reds": self.reds,
            "blue_1": self.blue_1,
            "blue": self.blue_1,
            "confidence_score": self.confidence_score,
            "rationale": self.rationale,
            "is_verified": self.is_verified,
            "hit_red_count": self.hit_red_count,
            "hit_red_numbers": self.hit_red_numbers,
            "hit_blue": self.hit_blue,
            "prize_level": self.prize_level,
            "prize_amount": self.prize_amount,
        }

    def __repr__(self) -> str:
        return f"<PredictionItem id={self.id} batch={self.batch_id} note={self.note_index} reds={self.reds} blue={self.blue_1}>"
