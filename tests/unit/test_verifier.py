"""
tests/unit/test_verifier.py

Unit test suite for Milestone 4: SSQ Prize Verification Engine (PrizeVerifier & VerificationService).
Covers:
1. Official Prize Rules (Levels 1 to 6 + Miss):
   - Level 1: 6+1 (floating jackpot, custom amount & default fallback 5,000,000 RMB)
   - Level 2: 6+0 (floating jackpot, custom amount & default fallback 200,000 RMB)
   - Level 3: 5+1 (fixed 3,000 RMB)
   - Level 4: 5+0 and 4+1 dual-channel (fixed 200 RMB)
   - Level 5: 4+0 and 3+1 dual-channel (fixed 10 RMB)
   - Level 6: 2+1, 1+1, 0+1 three-channel (fixed 5 RMB)
   - Tier 0: 3+0, 2+0, 1+0, 0+0 Miss combinations (0 RMB, critical boundary: 3+0 is 0 RMB)
2. Class and Method Interfaces:
   - PrizeVerifier.audit_ticket -> dict with all required and legacy keys
   - VerificationService.verify_ticket -> tuple contract
   - Input robustness: unsorted reds, duplicate handling
3. Batch Verification Pipeline:
   - VerificationService.verify_batch with database persistence
   - VerificationService.verify_issue targeting pending batches
   - Idempotency, missing draw errors, non-existent batch handling
4. CLI verify subcommand execution
"""

from datetime import date, datetime
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models import DrawHistory, PredictionBatch, PredictionItem
from backend.app.services.verifier import (
    PrizeVerifier,
    VerificationService,
    DEFAULT_FIRST_PRIZE,
    DEFAULT_SECOND_PRIZE,
    FIXED_PRIZES,
    PRIZE_NAMES,
)
from backend.app.cli import build_parser, main


@pytest.fixture
def memory_db_session():
    """In-memory SQLite database session with full schema."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session, Session
    session.close()


class TestOfficialPrizeRules:
    """Test all 14 official Chinese Shuangseqiu prize combinations."""

    def test_level_1_first_prize_jackpot(self):
        """Level 1 (6 reds + 1 blue): floating payout and default fallback (5,000,000 RMB)."""
        actual_reds = [1, 2, 3, 4, 5, 6]
        actual_blue = 8

        # With custom jackpot
        res = PrizeVerifier.audit_ticket(
            pred_reds=[1, 2, 3, 4, 5, 6],
            pred_blue=8,
            actual_reds=actual_reds,
            actual_blue=actual_blue,
            first_prize_amt=8_888_888,
        )
        assert res["prize_level"] == 1
        assert res["tier"] == 1
        assert res["prize_amount"] == 8_888_888
        assert res["payout"] == 8_888_888
        assert res["hit_red_count"] == 6
        assert res["hit_blue"] is True

        # Default fallback (first_prize_amt is 0 or None)
        res_fallback = PrizeVerifier.audit_ticket(
            pred_reds=[1, 2, 3, 4, 5, 6],
            pred_blue=8,
            actual_reds=actual_reds,
            actual_blue=actual_blue,
            first_prize_amt=0,
        )
        assert res_fallback["prize_level"] == 1
        assert res_fallback["prize_amount"] == DEFAULT_FIRST_PRIZE
        assert res_fallback["prize_amount"] == 5_000_000

    def test_level_2_second_prize_jackpot(self):
        """Level 2 (6 reds + 0 blue): floating payout and default fallback (200,000 RMB)."""
        actual_reds = [1, 2, 3, 4, 5, 6]
        actual_blue = 8

        # With custom jackpot
        res = PrizeVerifier.audit_ticket(
            pred_reds=[1, 2, 3, 4, 5, 6],
            pred_blue=9,  # blue miss
            actual_reds=actual_reds,
            actual_blue=actual_blue,
            second_prize_amt=350_000,
        )
        assert res["prize_level"] == 2
        assert res["tier"] == 2
        assert res["prize_amount"] == 350_000
        assert res["hit_red_count"] == 6
        assert res["hit_blue"] is False

        # Default fallback
        res_fallback = PrizeVerifier.audit_ticket(
            pred_reds=[1, 2, 3, 4, 5, 6],
            pred_blue=9,
            actual_reds=actual_reds,
            actual_blue=actual_blue,
            second_prize_amt=None,
        )
        assert res_fallback["prize_level"] == 2
        assert res_fallback["prize_amount"] == DEFAULT_SECOND_PRIZE
        assert res_fallback["prize_amount"] == 200_000

    def test_level_3_third_prize(self):
        """Level 3 (5 reds + 1 blue): fixed 3,000 RMB."""
        actual_reds = [1, 2, 3, 4, 5, 6]
        actual_blue = 8

        res = PrizeVerifier.audit_ticket(
            pred_reds=[1, 2, 3, 4, 5, 10],  # 5 reds
            pred_blue=8,  # blue hit
            actual_reds=actual_reds,
            actual_blue=actual_blue,
        )
        assert res["prize_level"] == 3
        assert res["tier"] == 3
        assert res["prize_amount"] == FIXED_PRIZES[3]
        assert res["prize_amount"] == 3000
        assert res["hit_red_count"] == 5
        assert res["hit_blue"] is True

    def test_level_4_dual_channel(self):
        """Level 4: (5 reds + 0 blue) OR (4 reds + 1 blue) -> fixed 200 RMB."""
        actual_reds = [1, 2, 3, 4, 5, 6]
        actual_blue = 8

        # Channel 4A: 5 reds + 0 blue
        res_4a = PrizeVerifier.audit_ticket(
            pred_reds=[1, 2, 3, 4, 5, 10],
            pred_blue=9,
            actual_reds=actual_reds,
            actual_blue=actual_blue,
        )
        assert res_4a["prize_level"] == 4
        assert res_4a["prize_amount"] == 200
        assert res_4a["hit_red_count"] == 5
        assert res_4a["hit_blue"] is False

        # Channel 4B: 4 reds + 1 blue
        res_4b = PrizeVerifier.audit_ticket(
            pred_reds=[1, 2, 3, 4, 10, 11],
            pred_blue=8,
            actual_reds=actual_reds,
            actual_blue=actual_blue,
        )
        assert res_4b["prize_level"] == 4
        assert res_4b["prize_amount"] == 200
        assert res_4b["hit_red_count"] == 4
        assert res_4b["hit_blue"] is True

    def test_level_5_dual_channel(self):
        """Level 5: (4 reds + 0 blue) OR (3 reds + 1 blue) -> fixed 10 RMB."""
        actual_reds = [1, 2, 3, 4, 5, 6]
        actual_blue = 8

        # Channel 5A: 4 reds + 0 blue
        res_5a = PrizeVerifier.audit_ticket(
            pred_reds=[1, 2, 3, 4, 10, 11],
            pred_blue=9,
            actual_reds=actual_reds,
            actual_blue=actual_blue,
        )
        assert res_5a["prize_level"] == 5
        assert res_5a["prize_amount"] == 10
        assert res_5a["hit_red_count"] == 4
        assert res_5a["hit_blue"] is False

        # Channel 5B: 3 reds + 1 blue
        res_5b = PrizeVerifier.audit_ticket(
            pred_reds=[1, 2, 3, 10, 11, 12],
            pred_blue=8,
            actual_reds=actual_reds,
            actual_blue=actual_blue,
        )
        assert res_5b["prize_level"] == 5
        assert res_5b["prize_amount"] == 10
        assert res_5b["hit_red_count"] == 3
        assert res_5b["hit_blue"] is True

    def test_level_6_three_channels(self):
        """Level 6: (2 reds + 1 blue), (1 red + 1 blue), OR (0 reds + 1 blue) -> fixed 5 RMB."""
        actual_reds = [1, 2, 3, 4, 5, 6]
        actual_blue = 8

        # 2 reds + 1 blue
        res_2_1 = PrizeVerifier.audit_ticket(
            pred_reds=[1, 2, 10, 11, 12, 13],
            pred_blue=8,
            actual_reds=actual_reds,
            actual_blue=actual_blue,
        )
        assert res_2_1["prize_level"] == 6
        assert res_2_1["prize_amount"] == 5
        assert res_2_1["hit_red_count"] == 2
        assert res_2_1["hit_blue"] is True

        # 1 red + 1 blue
        res_1_1 = PrizeVerifier.audit_ticket(
            pred_reds=[1, 10, 11, 12, 13, 14],
            pred_blue=8,
            actual_reds=actual_reds,
            actual_blue=actual_blue,
        )
        assert res_1_1["prize_level"] == 6
        assert res_1_1["prize_amount"] == 5
        assert res_1_1["hit_red_count"] == 1
        assert res_1_1["hit_blue"] is True

        # 0 reds + 1 blue
        res_0_1 = PrizeVerifier.audit_ticket(
            pred_reds=[10, 11, 12, 13, 14, 15],
            pred_blue=8,
            actual_reds=actual_reds,
            actual_blue=actual_blue,
        )
        assert res_0_1["prize_level"] == 6
        assert res_0_1["prize_amount"] == 5
        assert res_0_1["hit_red_count"] == 0
        assert res_0_1["hit_blue"] is True

    def test_miss_combinations(self):
        """Tier 0 (Miss): 3+0, 2+0, 1+0, 0+0 yield strictly 0 RMB."""
        actual_reds = [1, 2, 3, 4, 5, 6]
        actual_blue = 8

        # CRITICAL BOUNDARY: 3 reds + 0 blue is NOT a prize in Chinese SSQ!
        res_3_0 = PrizeVerifier.audit_ticket(
            pred_reds=[1, 2, 3, 10, 11, 12],
            pred_blue=9,
            actual_reds=actual_reds,
            actual_blue=actual_blue,
        )
        assert res_3_0["prize_level"] == 0
        assert res_3_0["prize_amount"] == 0
        assert res_3_0["tier"] == 0
        assert res_3_0["payout"] == 0
        assert res_3_0["hit_red_count"] == 3
        assert res_3_0["hit_blue"] is False

        # 2 reds + 0 blue
        res_2_0 = PrizeVerifier.audit_ticket([1, 2, 10, 11, 12, 13], 9, actual_reds, actual_blue)
        assert res_2_0["prize_level"] == 0 and res_2_0["prize_amount"] == 0

        # 1 red + 0 blue
        res_1_0 = PrizeVerifier.audit_ticket([1, 10, 11, 12, 13, 14], 9, actual_reds, actual_blue)
        assert res_1_0["prize_level"] == 0 and res_1_0["prize_amount"] == 0

        # 0 reds + 0 blue
        res_0_0 = PrizeVerifier.audit_ticket([10, 11, 12, 13, 14, 15], 9, actual_reds, actual_blue)
        assert res_0_0["prize_level"] == 0 and res_0_0["prize_amount"] == 0


class TestVerifierInterfaces:
    """Test method signatures and contracts."""

    def test_verify_ticket_tuple_contract(self):
        """VerificationService.verify_ticket returns (prize_level, prize_amount, hit_red_numbers, hit_blue)."""
        ret = VerificationService.verify_ticket(
            pred_reds=[1, 2, 3, 4, 5, 6],
            pred_blue=8,
            actual_reds=[1, 2, 3, 4, 5, 6],
            actual_blue=8,
            first_prize_amt=6_000_000,
        )
        assert isinstance(ret, tuple)
        assert len(ret) == 4
        prize_level, prize_amount, hit_reds, hit_blue = ret
        assert prize_level == 1
        assert prize_amount == 6_000_000
        assert hit_reds == [1, 2, 3, 4, 5, 6]
        assert hit_blue is True

    def test_audit_ticket_dict_contract(self):
        """PrizeVerifier.audit_ticket returns complete dictionary with both standard and legacy keys."""
        res = PrizeVerifier.audit_ticket(
            pred_reds=[3, 1, 5, 2, 11, 12],  # unsorted
            pred_blue=7,
            actual_reds=[1, 2, 3, 4, 5, 6],
            actual_blue=7,
        )
        # Required keys
        assert "hit_red_count" in res
        assert "hit_red_numbers" in res
        assert "hit_blue" in res
        assert "prize_level" in res
        assert "prize_amount" in res
        # E2E test keys
        assert "tier" in res
        assert "payout" in res

        assert res["hit_red_count"] == 4
        assert res["hit_red_numbers"] == [1, 2, 3, 5]  # strictly sorted
        assert res["hit_red_str"] == "01,02,03,05"
        assert res["hit_blue"] is True
        assert res["prize_level"] == 4  # 4+1 -> Level 4
        assert res["prize_amount"] == 200

    def test_class_level_aliases(self):
        """PrizeVerifier is an alias for VerificationService."""
        assert PrizeVerifier is VerificationService


class TestDatabaseBatchVerification:
    """Test full database batch verification workflows and edge cases."""

    def _setup_draw(self, session, issue_no="2026101") -> DrawHistory:
        draw = DrawHistory(
            issue_no=issue_no,
            draw_date=date(2026, 8, 15),
            weekday=6,
            red_1=2, red_2=7, red_3=13, red_4=18, red_5=24, red_6=29,
            blue_1=8,
            red_seq_str="02,07,13,18,24,29",
            first_prize_num=5,
            first_prize_amount=6_500_000,
            second_prize_num=80,
            second_prize_amount=180_000,
        )
        session.add(draw)
        session.commit()
        return draw

    def test_verify_batch_success(self, memory_db_session):
        """Verify that verify_batch updates items and parent batch correctly."""
        session, Session = memory_db_session
        self._setup_draw(session, "2026101")

        # Create batch with 5 prediction items
        batch = PredictionBatch(
            target_issue="2026101",
            strategy_type="CONCENTRATED_BREAK_EVEN",
            total_notes=5,
            virtual_cost=10,
            verify_status="PENDING",
        )
        session.add(batch)
        session.commit()

        # Item 1: 6+1 -> Level 1 (6,500,000)
        i1 = PredictionItem(batch_id=batch.id, target_issue="2026101", note_index=1,
                            red_1=2, red_2=7, red_3=13, red_4=18, red_5=24, red_6=29, blue_1=8)
        # Item 2: 4+1 -> Level 4 (200)
        i2 = PredictionItem(batch_id=batch.id, target_issue="2026101", note_index=2,
                            red_1=2, red_2=7, red_3=13, red_4=18, red_5=30, red_6=31, blue_1=8)
        # Item 3: 3+1 -> Level 5 (10)
        i3 = PredictionItem(batch_id=batch.id, target_issue="2026101", note_index=3,
                            red_1=2, red_2=7, red_3=13, red_4=30, red_5=31, red_6=32, blue_1=8)
        # Item 4: 0+1 -> Level 6 (5)
        i4 = PredictionItem(batch_id=batch.id, target_issue="2026101", note_index=4,
                            red_1=1, red_2=3, red_3=5, red_4=9, red_5=11, red_6=15, blue_1=8)
        # Item 5: 1+0 -> Miss (0)
        i5 = PredictionItem(batch_id=batch.id, target_issue="2026101", note_index=5,
                            red_1=2, red_2=3, red_3=5, red_4=9, red_5=11, red_6=15, blue_1=9)
        session.add_all([i1, i2, i3, i4, i5])
        session.commit()

        service = VerificationService(session_factory=Session)
        updated_batch = service.verify_batch(batch.id, session=session)

        assert updated_batch.verify_status == "VERIFIED"
        assert updated_batch.best_prize_level == 1
        expected_total = 6_500_000 + 200 + 10 + 5 + 0
        assert updated_batch.virtual_reward == expected_total
        assert updated_batch.verified_at is not None
        assert "Target Issue 2026101 Prize Verification" in updated_batch.post_reflection_md

        # Verify individual items
        items = session.scalars(select(PredictionItem).filter(PredictionItem.batch_id == batch.id).order_by(PredictionItem.note_index)).all()
        assert len(items) == 5
        assert all(i.is_verified for i in items)

        assert items[0].prize_level == 1 and items[0].prize_amount == 6_500_000
        assert items[0].hit_red_count == 6 and items[0].hit_blue is True
        assert items[0].hit_red_numbers == "02,07,13,18,24,29"

        assert items[1].prize_level == 4 and items[1].prize_amount == 200
        assert items[1].hit_red_count == 4 and items[1].hit_blue is True
        assert items[1].hit_red_numbers == "02,07,13,18"

        assert items[2].prize_level == 5 and items[2].prize_amount == 10
        assert items[2].hit_red_count == 3 and items[2].hit_blue is True

        assert items[3].prize_level == 6 and items[3].prize_amount == 5
        assert items[3].hit_red_count == 0 and items[3].hit_blue is True
        assert items[3].hit_red_numbers == ""

        assert items[4].prize_level == 0 and items[4].prize_amount == 0
        assert items[4].hit_red_count == 1 and items[4].hit_blue is False
        assert items[4].hit_red_numbers == "02"

    def test_verify_batch_all_miss(self, memory_db_session):
        """Batch where all 5 notes miss results in best_prize_level = 0 and virtual_reward = 0."""
        session, Session = memory_db_session
        self._setup_draw(session, "2026102")

        batch = PredictionBatch(target_issue="2026102", strategy_type="DISPERSED_BASELINE", total_notes=5, virtual_cost=10)
        session.add(batch)
        session.commit()

        for idx in range(1, 6):
            item = PredictionItem(
                batch_id=batch.id, target_issue="2026102", note_index=idx,
                red_1=1, red_2=3, red_3=5, red_4=9, red_5=11, red_6=15, blue_1=9
            )
            session.add(item)
        session.commit()

        service = VerificationService(session_factory=Session)
        updated_batch = service.verify_batch(batch.id, session=session)

        assert updated_batch.verify_status == "VERIFIED"
        assert updated_batch.best_prize_level == 0
        assert updated_batch.virtual_reward == 0

    def test_verify_batch_idempotency(self, memory_db_session):
        """Calling verify_batch multiple times produces deterministic idempotent results."""
        session, Session = memory_db_session
        self._setup_draw(session, "2026103")

        batch = PredictionBatch(target_issue="2026103", strategy_type="CONCENTRATED_BREAK_EVEN", total_notes=1, virtual_cost=2)
        session.add(batch)
        session.commit()

        item = PredictionItem(
            batch_id=batch.id, target_issue="2026103", note_index=1,
            red_1=2, red_2=7, red_3=13, red_4=18, red_5=24, red_6=29, blue_1=8
        )
        session.add(item)
        session.commit()

        service = VerificationService(session_factory=Session)
        b1 = service.verify_batch(batch.id, session=session)
        reward_1 = b1.virtual_reward

        b2 = service.verify_batch(batch.id, session=session)
        assert b2.virtual_reward == reward_1
        assert b2.verify_status == "VERIFIED"

    def test_verify_batch_missing_draw_raises_error(self, memory_db_session):
        """Target issue not found in DrawHistory raises ValueError."""
        session, Session = memory_db_session
        batch = PredictionBatch(target_issue="2099999", strategy_type="CONCENTRATED_BREAK_EVEN")
        session.add(batch)
        session.commit()

        service = VerificationService(session_factory=Session)
        with pytest.raises(ValueError, match="Draw history for issue 2099999 not found"):
            service.verify_batch(batch.id, session=session)

    def test_verify_batch_nonexistent_batch_raises_error(self, memory_db_session):
        """Non-existent batch ID raises ValueError."""
        session, Session = memory_db_session
        service = VerificationService(session_factory=Session)
        with pytest.raises(ValueError, match="PredictionBatch with ID 999999 not found"):
            service.verify_batch(999999, session=session)

    def test_verify_issue_pending_and_force(self, memory_db_session):
        """verify_issue audits pending batches, and respects force flag."""
        session, Session = memory_db_session
        self._setup_draw(session, "2026104")

        # Batch A: PENDING
        b_a = PredictionBatch(target_issue="2026104", strategy_type="CONCENTRATED_BREAK_EVEN", verify_status="PENDING")
        # Batch B: already VERIFIED
        b_b = PredictionBatch(target_issue="2026104", strategy_type="DISPERSED_BASELINE", verify_status="VERIFIED", virtual_reward=50)
        session.add_all([b_a, b_b])
        session.commit()

        # Add notes for both
        for b in [b_a, b_b]:
            for i in range(1, 6):
                session.add(PredictionItem(batch_id=b.id, target_issue="2026104", note_index=i, red_1=2, red_2=7, red_3=13, red_4=18, red_5=24, red_6=29, blue_1=8))
        session.commit()

        service = VerificationService(session_factory=Session)
        # Without force: only audits b_a
        verified_default = service.verify_issue("2026104", session=session, force=False)
        assert len(verified_default) == 1
        assert verified_default[0].id == b_a.id

        # With force: audits both
        verified_force = service.verify_issue("2026104", session=session, force=True)
        assert len(verified_force) == 2


class TestCLIIntegration:
    """Test CLI verify command invocation and parameter parsing."""

    def test_cli_verify_parser_registration(self):
        """verify subcommand is registered in argument parser."""
        parser = build_parser()
        args = parser.parse_args(["verify", "--issue", "2026122"])
        assert args.subcommand == "verify"
        assert args.issue == "2026122"

    def test_cli_verify_default_invocation(self):
        """python -m backend.app.cli verify executes cleanly without errors."""
        exit_code = main(["verify"])
        assert exit_code == 0
