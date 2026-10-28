"""
backend/app/services/verifier.py

Official Shuangseqiu (SSQ) Level 1-6 prize auditing engine and prediction batch verification service.
Implements official Chinese Welfare Lottery prize tiers, dynamic floating jackpot extraction,
safe fallback defaults (5M for 1st, 200k for 2nd), atomic SQLite persistence, and post-reflections.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models import DrawHistory, PredictionBatch, PredictionItem

# Standard Fallback Floating Prize Constants (RMB)
DEFAULT_FIRST_PRIZE: int = 5_000_000
DEFAULT_SECOND_PRIZE: int = 200_000

# Official Fixed Prize Amounts (RMB)
FIXED_PRIZES: Dict[int, int] = {
    3: 3_000,
    4: 200,
    5: 10,
    6: 5,
}

PRIZE_NAMES: Dict[int, str] = {
    1: "一等奖 (Level 1)",
    2: "二等奖 (Level 2)",
    3: "三等奖 (Level 3)",
    4: "四等奖 (Level 4)",
    5: "五等奖 (Level 5)",
    6: "六等奖 (Level 6)",
    0: "未中奖 (No Prize)",
}


class VerificationService:
    """
    Official SSQ Prize Verification Engine and persistence service.
    Evaluates individual tickets or full 5-line prediction batches against authentic draw results.
    """

    def __init__(self, session_factory=None):
        self.session_factory = session_factory or SessionLocal

    @staticmethod
    def verify_ticket(
        pred_reds: List[int],
        pred_blue: int,
        actual_reds: List[int],
        actual_blue: int,
        first_prize_amt: Optional[int] = None,
        second_prize_amt: Optional[int] = None,
        first_amount: Optional[int] = None,
        second_amount: Optional[int] = None,
        **kwargs: Any,
    ) -> Tuple[int, int, List[int], bool]:
        """
        Calculates official prize level and payout for a single ticket.

        Official Chinese SSQ Rules:
        - Level 1: 6 reds + 1 blue -> Floating (fallback 5,000,000 RMB)
        - Level 2: 6 reds + 0 blue -> Floating (fallback 200,000 RMB)
        - Level 3: 5 reds + 1 blue -> Fixed 3,000 RMB
        - Level 4: 5 reds + 0 blue OR 4 reds + 1 blue -> Fixed 200 RMB
        - Level 5: 4 reds + 0 blue OR 3 reds + 1 blue -> Fixed 10 RMB
        - Level 6: 2 reds + 1 blue OR 1 red + 1 blue OR 0 reds + 1 blue -> Fixed 5 RMB
        - Tier 0 (Miss): 3+0, 2+0, 1+0, 0+0 -> 0 RMB

        :return: (prize_level: int, prize_amount: int, hit_red_numbers: List[int], hit_blue: bool)
                 where prize_level is in 0..6 (0 = no prize).
        """
        hit_reds = sorted(list(set(pred_reds) & set(actual_reds)))
        h_r = len(hit_reds)
        h_b = bool(pred_blue == actual_blue)

        # Resolve floating jackpots with fallbacks
        f_p = first_prize_amt if first_prize_amt is not None else first_amount
        s_p = second_prize_amt if second_prize_amt is not None else second_amount

        first_p = f_p if (f_p is not None and f_p > 0) else DEFAULT_FIRST_PRIZE
        second_p = s_p if (s_p is not None and s_p > 0) else DEFAULT_SECOND_PRIZE

        if h_r == 6 and h_b:
            return 1, first_p, hit_reds, h_b
        elif h_r == 6 and not h_b:
            return 2, second_p, hit_reds, h_b
        elif h_r == 5 and h_b:
            return 3, FIXED_PRIZES[3], hit_reds, h_b
        elif (h_r == 5 and not h_b) or (h_r == 4 and h_b):
            return 4, FIXED_PRIZES[4], hit_reds, h_b
        elif (h_r == 4 and not h_b) or (h_r == 3 and h_b):
            return 5, FIXED_PRIZES[5], hit_reds, h_b
        elif h_r in (0, 1, 2) and h_b:
            return 6, FIXED_PRIZES[6], hit_reds, h_b
        else:
            return 0, 0, hit_reds, h_b

    @classmethod
    def audit_ticket(
        cls,
        pred_reds: List[int],
        pred_blue: int,
        actual_reds: List[int],
        actual_blue: int,
        first_prize_amt: Optional[int] = None,
        second_prize_amt: Optional[int] = None,
        first_amount: Optional[int] = None,
        second_amount: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Ticket auditing returning a dictionary compatible with both E2E test suites and CLI.
        Returns:
            {
                "tier": int,
                "payout": int,
                "prize_level": int,
                "prize_amount": int,
                "hit_red_count": int,
                "hit_red_numbers": List[int],
                "hit_red_str": str,
                "hit_reds": List[int],
                "hit_blue": bool,
            }
        """
        tier, payout, hit_reds, hit_blue = cls.verify_ticket(
            pred_reds=pred_reds,
            pred_blue=pred_blue,
            actual_reds=actual_reds,
            actual_blue=actual_blue,
            first_prize_amt=first_prize_amt,
            second_prize_amt=second_prize_amt,
            first_amount=first_amount,
            second_amount=second_amount,
            **kwargs,
        )
        return {
            "tier": tier,
            "payout": payout,
            "prize_level": tier,
            "prize_amount": payout,
            "hit_red_count": len(hit_reds),
            "hit_red_numbers": hit_reds,
            "hit_red_str": ",".join(f"{x:02d}" for x in hit_reds),
            "hit_reds": hit_reds,
            "hit_blue": hit_blue,
        }

    def verify_batch(
        self,
        batch_id: int,
        session: Optional[Session] = None,
    ) -> PredictionBatch:
        """
        Audits all prediction items in batch_id against authentic draw results and updates SQLite.
        Updates item records (`is_verified`, `hit_red_count`, `hit_red_numbers`, `hit_blue`, `prize_level`, `prize_amount`)
        and parent batch records (`verify_status='VERIFIED'`, `best_prize_level`, `virtual_reward`, `verified_at`).
        """
        if isinstance(self, type):
            return self().verify_batch(batch_id, session=session)

        if session is not None:
            batch = self._verify_batch_in_session(batch_id, session)
            session.flush()
            return batch

        with self.session_factory() as s:
            batch = self._verify_batch_in_session(batch_id, s)
            s.commit()
            s.refresh(batch)
            _ = list(batch.items)
            return batch

    def _verify_batch_in_session(
        self,
        batch_id: int,
        session: Session,
    ) -> PredictionBatch:
        batch = session.scalar(
            select(PredictionBatch).filter(PredictionBatch.id == batch_id)
        )
        if not batch:
            raise ValueError(f"PredictionBatch with ID {batch_id} not found.")

        draw = session.scalar(
            select(DrawHistory).filter(DrawHistory.issue_no == batch.target_issue)
        )
        if not draw:
            raise ValueError(
                f"Draw history for issue {batch.target_issue} not found in database. "
                f"Cannot verify until draw record is fetched."
            )

        total_reward = 0
        winning_tiers: List[int] = []

        for item in batch.items:
            tier, payout, hit_reds, hit_blue = self.verify_ticket(
                pred_reds=item.reds,
                pred_blue=item.blue_1,
                actual_reds=draw.reds,
                actual_blue=draw.blue_1,
                first_amount=draw.first_prize_amount,
                second_amount=draw.second_prize_amount,
            )
            item.is_verified = True
            item.hit_red_count = len(hit_reds)
            item.hit_red_numbers = ",".join(f"{x:02d}" for x in hit_reds)
            item.hit_blue = hit_blue
            item.prize_level = tier
            item.prize_amount = payout

            total_reward += payout
            if tier > 0:
                winning_tiers.append(tier)

        batch.virtual_reward = total_reward
        batch.best_prize_level = min(winning_tiers) if winning_tiers else 0
        batch.verify_status = "VERIFIED"
        batch.verified_at = datetime.now()
        batch.post_reflection_md = self.generate_post_reflection(batch, draw)

        return batch

    def verify_issue(
        self,
        issue_no: str,
        session: Optional[Session] = None,
        force: bool = False,
    ) -> List[PredictionBatch]:
        """
        Audits prediction batches targeting `issue_no`.
        By default audits batches with verify_status == 'PENDING'. If force=True, audits all batches.
        """
        if isinstance(self, type):
            return self().verify_issue(issue_no, session=session, force=force)

        def _execute(s: Session) -> List[PredictionBatch]:
            stmt = select(PredictionBatch).filter(PredictionBatch.target_issue == issue_no)
            if not force:
                stmt = stmt.filter(PredictionBatch.verify_status == "PENDING")
            batches = s.scalars(stmt).all()
            verified = []
            for b in batches:
                verified.append(self._verify_batch_in_session(b.id, s))
            return verified

        if session is not None:
            result = _execute(session)
            session.flush()
            return result

        with self.session_factory() as s:
            result = _execute(s)
            s.commit()
            for b in result:
                s.refresh(b)
                _ = list(b.items)
            return result

    def generate_post_reflection(
        self,
        batch: PredictionBatch,
        draw: DrawHistory,
    ) -> str:
        """
        Generates structured Markdown post-reflection summarizing prediction performance vs actual draw.
        """
        net_profit = batch.virtual_reward - batch.virtual_cost
        roi = (net_profit / batch.virtual_cost) if batch.virtual_cost > 0 else 0.0
        break_even_status = "YES (Break-Even or Profit)" if batch.virtual_reward >= batch.virtual_cost else "NO (Deficit)"

        lines = [
            f"### Target Issue {batch.target_issue} Prize Verification & Post-Reflection",
            f"- **Actual Draw**: Reds [{draw.red_seq_str}] + Blue [{draw.blue_1:02d}] (Date: {draw.draw_date})",
            f"- **Strategy Mode**: {batch.strategy_type}",
            f"- **Virtual Cost**: {batch.virtual_cost} RMB ({batch.total_notes} notes)",
            f"- **Virtual Reward**: {batch.virtual_reward} RMB | Net: {net_profit:+d} RMB | ROI: {roi:+.1%}",
            f"- **Break-Even Achieved**: {break_even_status}",
            f"- **Best Prize Level**: {PRIZE_NAMES.get(batch.best_prize_level, 'None')}",
            "",
            "#### Note Auditing Breakdown:",
        ]

        for item in sorted(batch.items, key=lambda x: x.note_index):
            pred_reds = f"[{item.red_1:02d}, {item.red_2:02d}, {item.red_3:02d}, {item.red_4:02d}, {item.red_5:02d}, {item.red_6:02d}]"
            hits_str = f"[{item.hit_red_numbers}]" if item.hit_red_numbers else "None"
            blue_status = "HIT" if item.hit_blue else "MISS"
            tier_str = PRIZE_NAMES.get(item.prize_level, "0")
            lines.append(
                f"- Note {item.note_index}: {pred_reds} + [{item.blue_1:02d}] -> "
                f"Red Hits: {item.hit_red_count} ({hits_str}), Blue: {blue_status} -> "
                f"**{tier_str}**: {item.prize_amount} RMB"
            )

        return "\n".join(lines) + "\n"


# Aliases for cross-module & test-suite compatibility
PrizeVerifier = VerificationService
PrizeAuditor = VerificationService

__all__ = [
    "VerificationService",
    "PrizeVerifier",
    "PrizeAuditor",
    "DEFAULT_FIRST_PRIZE",
    "DEFAULT_SECOND_PRIZE",
    "FIXED_PRIZES",
    "PRIZE_NAMES",
]
