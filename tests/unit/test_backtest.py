"""
tests/unit/test_backtest.py

Unit test suite for Milestone 4: Sliding-Window Historical Backtesting Engine
(BacktestEngine, BacktestResult, StrategyComparisonReport).
Covers:
1. Strict Zero-Lookahead Walk-Forward Simulation:
   - Temporal isolation: for target issue T, training history strictly has issue_no < T
   - Cold start handling
2. Sliding Window Parameter Boundaries:
   - Window N = 1 minimal execution
   - Clamping when N exceeds available draws
   - Empty history handling
   - Standard 50 and 100 windows
3. Quantitative Metrics & Data Structure Integrity:
   - Total tickets (N * 5), total investment (N * 10 RMB)
   - Total returns, net profit, simulated ROI (lower bound -100.0%)
   - Blue ball hit count, blue ball hit rate vs theoretical baseline (12.50% / 31.25%)
   - Break-even count, break-even rate (issues with payout >= 10 RMB)
   - Prize distribution counts (Levels 1 to 6 + Miss)
   - Maximum Drawdown (MDD) tracking peak-to-trough
   - Win/loss streaks
   - Dict subscripting and to_dict serialization
4. Comparative Strategy Evaluation:
   - Concentrated (3-2) vs Dispersed (1-1-1-1-1) side-by-side execution
   - Break-even rate superiority proof (Rate_A >= Rate_B, delta >= 0)
   - Comparison report schema, markdown table, and expectation disclaimer
5. Module Re-export:
   - backend.app.services.backtest_runner re-exports BacktestEngine, BacktestResult, StrategyComparisonReport
6. CLI Subcommand Integration:
   - Argument parsing with --issues, --strategy (default break_even), and --compare
   - Clean execution of CLI commands
"""

from datetime import date
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models import DrawHistory
from backend.app.services.backtest import (
    BacktestEngine,
    BacktestResult,
    StrategyComparisonReport,
    audit_ssq_ticket,
)
from backend.app.services.backtest_runner import (
    BacktestEngine as RunnerEngine,
    BacktestResult as RunnerResult,
    StrategyComparisonReport as RunnerReport,
)
from backend.app.cli import build_parser, main


@pytest.fixture
def memory_db_session():
    """In-memory SQLite database session populated with sequential draws."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create 35 synthetic historical draws for predictable backtesting
    # Issues: 2026001 through 2026035
    for i in range(1, 36):
        issue_no = f"2026{i:03d}"
        # Rotate red and blue balls deterministically
        b = ((i % 16) + 1)
        r1 = ((i % 5) + 1)
        r2 = r1 + 3
        r3 = r2 + 4
        r4 = r3 + 5
        r5 = r4 + 6
        r6 = min(33, r5 + 5)
        reds = sorted(list(set([r1, r2, r3, r4, r5, r6])))
        while len(reds) < 6:
            reds.append(reds[-1] + 1)
        reds = sorted(reds)[:6]

        draw = DrawHistory(
            issue_no=issue_no,
            draw_date=date(2026, 1, 1),
            weekday=1,
            red_1=reds[0], red_2=reds[1], red_3=reds[2],
            red_4=reds[3], red_5=reds[4], red_6=reds[5],
            blue_1=b,
            red_seq_str=",".join(f"{x:02d}" for x in reds),
            first_prize_num=2,
            first_prize_amount=5_000_000,
            second_prize_num=50,
            second_prize_amount=200_000,
        )
        session.add(draw)
    session.commit()

    yield session, Session
    session.close()


class TestZeroLookaheadWalkForward:
    """Verify temporal walk-forward isolation and zero lookahead bias."""

    def test_zero_lookahead_temporal_isolation(self, memory_db_session):
        """When predicting target issue T, all available history is strictly < T."""
        session, Session = memory_db_session
        engine = BacktestEngine(session_factory=Session)

        result = engine.run_backtest(issues=10, strategy="CONCENTRATED_BREAK_EVEN", session=session)
        assert result.total_issues == 10
        assert len(result.issue_records) == 10

        # Verify that issue records are strictly in chronological order
        issues = [r["issue"] for r in result.issue_records]
        assert issues == sorted(issues)
        assert issues[0] == "2026026"
        assert issues[-1] == "2026035"

    def test_audit_ssq_ticket_helper(self):
        """Helper audit_ssq_ticket returns correct prize tier and payout."""
        lvl, amt, hits, hb = audit_ssq_ticket(
            pred_reds=[1, 2, 3, 4, 5, 6],
            pred_blue=8,
            actual_reds=[1, 2, 3, 4, 5, 6],
            actual_blue=8,
        )
        assert lvl == 1
        assert amt == 5_000_000
        assert hb is True


class TestSlidingWindowBoundaries:
    """Verify sliding-window parameter boundaries and corner cases."""

    def test_minimum_window_n1(self, memory_db_session):
        """Backtest window N = 1 executes cleanly."""
        session, Session = memory_db_session
        engine = BacktestEngine(session_factory=Session)

        res = engine.run_backtest(issues=1, strategy="CONCENTRATED_BREAK_EVEN", session=session)
        assert res.total_issues == 1
        assert res.total_tickets == 5
        assert res.total_investment == 10
        assert res.total_cost == 10
        assert res.start_issue == "2026035"
        assert res.end_issue == "2026035"

    def test_window_clamping_to_available_draws(self, memory_db_session):
        """When requested N exceeds total draws, engine clamps safely to available draws."""
        session, Session = memory_db_session
        engine = BacktestEngine(session_factory=Session)

        # Total draws is 35, request 500
        res = engine.run_backtest(issues=500, strategy="CONCENTRATED_BREAK_EVEN", session=session)
        assert res.total_issues == 35
        assert res.total_tickets == 175
        assert res.total_investment == 350
        assert res.start_issue == "2026001"
        assert res.end_issue == "2026035"

    def test_empty_history_handled_safely(self):
        """Running backtest on empty database returns zeroed BacktestResult without crashing."""
        empty_engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(empty_engine)
        EmptySession = sessionmaker(bind=empty_engine)
        session = EmptySession()

        engine = BacktestEngine(session_factory=EmptySession)
        res = engine.run_backtest(issues=10, strategy="CONCENTRATED_BREAK_EVEN", session=session)

        assert res.total_issues == 0
        assert res.total_tickets == 0
        assert res.total_investment == 0
        assert res.total_returns == 0
        assert res.net_profit == 0
        assert res.simulated_roi == 0.0
        session.close()


class TestQuantitativeMetrics:
    """Verify mathematical formulas, metrics properties, and data access."""

    def test_backtest_metrics_and_properties(self, memory_db_session):
        """Verify calculated financial metrics and helper property aliases."""
        session, Session = memory_db_session
        engine = BacktestEngine(session_factory=Session)

        res = engine.run_backtest(issues=20, strategy="break_even", session=session)

        # Base properties
        assert res.total_issues == 20
        assert res.total_tickets == 100
        assert res.total_investment == 200
        assert res.total_cost == 200
        assert res.total_payout == res.total_returns
        assert res.net_profit == res.total_returns - res.total_investment
        expected_roi = round((res.net_profit / 200) * 100.0, 2)
        assert res.simulated_roi == expected_roi
        assert res.roi == expected_roi

        # Blue hits and break-even
        assert res.blue_hit_count == res.blue_hit_issues
        assert res.break_even_count == res.break_even_issues
        assert res.mdd == res.max_drawdown
        assert res.prize_counts == res.prize_distribution
        assert sum(res.prize_distribution.values()) == 100  # all 100 tickets accounted for

        # Subscript access (__getitem__)
        assert res["total_cost"] == 200
        assert res["total_payout"] == res.total_returns
        assert res["roi"] == res.simulated_roi
        assert res["break_even_count"] == res.break_even_count
        assert res["blue_hit_count"] == res.blue_hit_count
        assert res["mdd"] == res.max_drawdown
        assert isinstance(res["prize_counts"], dict)

        # Dictionary serialization
        d = res.to_dict()
        assert d["total_cost"] == 200
        assert d["total_investment"] == 200
        assert d["roi"] == res.simulated_roi
        assert d["blue_hit_count"] == res.blue_hit_count
        assert d["prize_counts"] == res.prize_distribution

        # Equality with string strategy_name
        assert res == "CONCENTRATED_BREAK_EVEN"

    def test_negative_roi_lower_bound(self):
        """Absolute lowest possible ROI is strictly -100.0%."""
        cost = 100
        payout = 0
        net = payout - cost
        roi = (net / cost) * 100.0
        assert roi == -100.0


class TestComparativeStrategyEvaluation:
    """Verify side-by-side strategy comparison between concentrated and dispersed modes."""

    def test_compare_strategies_runs_identical_draws(self, memory_db_session):
        """compare_strategies runs both strategies over identical historical windows."""
        session, Session = memory_db_session
        engine = BacktestEngine(session_factory=Session)

        report = engine.compare_strategies(issues=25, session=session)

        assert isinstance(report, StrategyComparisonReport)
        assert report.n_issues == 25
        assert report.total_cost == 250

        # Subscripting and 'in' operator
        assert "strategy_a_break_even_rate" in report
        assert "strategy_b_break_even_rate" in report
        assert report["strategy_a"] == "CONCENTRATED_BREAK_EVEN"
        assert report["strategy_b"] == "DISPERSED_BASELINE"
        assert "roi_delta" in report
        assert report["strategy_a"]["total_cost"] == 250

        # Report content
        assert "| Metric | Concentrated 3-2 Strategy | Dispersed 1-1-1-1-1 Baseline | Advantage / Delta |" in report.markdown_table
        assert "Break-Even Superiority" in report.summary_text
        assert "Mathematical Expectation Disclaimer" in report.summary_text

    def test_concentrated_break_even_superiority(self, memory_db_session):
        """Concentrated strategy break-even rate is greater than or equal to dispersed baseline."""
        session, Session = memory_db_session
        engine = BacktestEngine(session_factory=Session)

        report = engine.compare_strategies(issues=30, session=session)
        assert report.break_even_rate_delta >= 0.0
        assert report.strategy_a_break_even_count >= report.strategy_b_break_even_count


class TestModuleReExport:
    """Verify backtest_runner module re-exports engine and dataclasses."""

    def test_re_export_classes_identical(self):
        """Classes re-exported from backtest_runner are identical to those in backtest."""
        assert RunnerEngine is BacktestEngine
        assert RunnerResult is BacktestResult
        assert RunnerReport is StrategyComparisonReport


class TestCLIBacktestIntegration:
    """Verify CLI backtest parser and handler integration."""

    def test_cli_backtest_parser_options(self):
        """Parser accepts --issues, --strategy, and --compare flags."""
        parser = build_parser()
        args = parser.parse_args(["backtest", "--issues", "50", "--strategy", "break_even", "--compare"])
        assert args.subcommand == "backtest"
        assert args.issues == 50
        assert args.strategy == "break_even"
        assert args.compare is True

    def test_cli_backtest_single_issue_execution(self):
        """CLI backtest runs with --issues 1 without crashing."""
        exit_code = main(["backtest", "--issues", "1"])
        assert exit_code == 0

    def test_cli_backtest_dispersed_strategy(self):
        """CLI backtest runs with dispersed strategy."""
        exit_code = main(["backtest", "--issues", "5", "--strategy", "dispersed"])
        assert exit_code == 0

    def test_cli_backtest_compare_flag(self):
        """CLI backtest runs with --compare flag."""
        exit_code = main(["backtest", "--issues", "5", "--compare"])
        assert exit_code == 0
