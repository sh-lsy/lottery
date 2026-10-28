"""
CLI interface for SSQ-Quant-System.
Implements command:
    python -m backend.app.cli sync [--force] [--full] [--incremental]
And placeholders for future milestones (compute-features, predict, verify, backtest).
"""

import argparse
import logging
import sys
from typing import Optional

from sqlalchemy import select, func

from backend.app.database import init_db, SessionLocal
from backend.app.models import DrawHistory, FeatureMetrics, PredictionBatch, PredictionItem
from backend.app.services.crawler import CrawlerService
from backend.app.services.feature_engine import FeatureEngine
from backend.app.services.predictor import PredictionService
from backend.app.services.verifier import VerificationService, PrizeVerifier, PRIZE_NAMES
from backend.app.services.backtest import BacktestEngine, BacktestResult, StrategyComparisonReport

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ssq_quant.cli")


def handle_sync(args: argparse.Namespace) -> int:
    """
    Handle the `sync` command.
    Synchronizes historical or incremental draw data into SQLite.
    """
    init_db()
    crawler = CrawlerService()

    with SessionLocal() as session:
        current_count = session.scalar(select(func.count(DrawHistory.id))) or 0
        min_issue = session.scalar(select(func.min(DrawHistory.issue_no)))
        max_issue = session.scalar(select(func.max(DrawHistory.issue_no)))

    logger.info("Current DB status: %d records (range: %s ~ %s)", current_count, min_issue, max_issue)

    if args.force:
        logger.info("Executing forced full synchronization from 500.com...")
        affected = crawler.sync_all(force=True)
    elif args.full or current_count == 0:
        logger.info("Executing full synchronization from 500.com...")
        affected = crawler.sync_all(force=False)
    else:
        logger.info("Executing incremental synchronization...")
        affected = crawler.sync_latest()

    with SessionLocal() as session:
        total_count = session.scalar(select(func.count(DrawHistory.id))) or 0
        min_issue = session.scalar(select(func.min(DrawHistory.issue_no)))
        max_issue = session.scalar(select(func.max(DrawHistory.issue_no)))

    print(f"\n[Synchronization Complete]")
    print(f"  Records affected/added : {affected}")
    print(f"  Total records in DB    : {total_count}")
    print(f"  Earliest issue         : {min_issue}")
    print(f"  Latest issue           : {max_issue}\n")

    return 0


def handle_compute_features(args: argparse.Namespace) -> int:
    """
    Handle the `compute-features` command.
    Computes statistical feature metrics and omission snapshots into ssq_feature_metrics.
    """
    init_db()
    engine = FeatureEngine()

    force = getattr(args, "force", False)
    if force:
        logger.info("Executing forced full feature re-computation...")
        count = engine.compute_all_features(force=True)
    else:
        logger.info("Executing feature computation...")
        count = engine.compute_all_features(force=False)

    with SessionLocal() as session:
        total_features = session.scalar(select(func.count(FeatureMetrics.issue_no))) or 0
        min_issue = session.scalar(select(func.min(FeatureMetrics.issue_no)))
        max_issue = session.scalar(select(func.max(FeatureMetrics.issue_no)))

    print(f"\n[Feature Engineering Complete]")
    print(f"  Rows computed/added    : {count}")
    print(f"  Total feature rows     : {total_features}")
    print(f"  Earliest feature issue : {min_issue}")
    print(f"  Latest feature issue   : {max_issue}\n")

    return 0


def handle_predict(args: argparse.Namespace) -> int:
    """
    Handle the `predict` and `predict-issue` commands (Milestone 3).
    Generates a 5-line prediction ticket, displays formatted stdout, and persists to SQLite.
    """
    init_db()
    service = PredictionService()

    target_issue = getattr(args, "issue", None)
    strategy = getattr(args, "strategy", "CONCENTRATED_BREAK_EVEN")

    try:
        batch = service.generate_5_line_prediction(target_issue=target_issue, strategy=strategy)
    except Exception as e:
        logger.error("Prediction failed: %s", e)
        print(f"\n[Prediction Error] {e}\n", file=sys.stderr)
        return 1

    print("\n" + "=" * 80)
    print("SSQ-Quant-System 5-Line Strategy Prediction (Milestone 3)")
    print("=" * 80)
    print(f"Target Issue : {batch.target_issue}")
    print(f"Strategy     : {batch.strategy_type}")
    print(f"Model Engine : {batch.model_name}")
    print(f"Batch ID     : {batch.id} | Status: {batch.verify_status} | Total Notes: {batch.total_notes} | Cost: {batch.virtual_cost} RMB")
    print("-" * 80)

    for item in sorted(batch.items, key=lambda x: x.note_index):
        reds_str = f"[{item.red_1:02d}, {item.red_2:02d}, {item.red_3:02d}, {item.red_4:02d}, {item.red_5:02d}, {item.red_6:02d}]"
        blue_str = f"[{item.blue_1:02d}]"
        print(f"Note {item.note_index}: {reds_str} + {blue_str}  (Conf: {item.confidence_score:.2%}) | {item.rationale or ''}")

    print("-" * 80)
    if batch.ai_reasoning_md:
        print(batch.ai_reasoning_md.strip())
    print("=" * 80)
    print(f"[Success] 1 batch and {len(batch.items)} items persisted to SQLite database.\n")
    return 0




def handle_verify(args: argparse.Namespace) -> int:
    """
    Handle the `verify` command (Milestone 4).
    Audits prediction items/batches against authentic draw history in SQLite.
    """
    init_db()
    service = VerificationService()

    target_issue = getattr(args, "issue", None)
    batch_id = getattr(args, "batch_id", None)
    force = getattr(args, "force", False)

    verified_batches = []

    with SessionLocal() as session:
        if batch_id:
            batch = session.scalar(select(PredictionBatch).filter(PredictionBatch.id == batch_id))
            if not batch:
                print(f"\n[Error] Prediction batch with ID {batch_id} not found.\n", file=sys.stderr)
                return 1
            draw = session.scalar(select(DrawHistory).filter(DrawHistory.issue_no == batch.target_issue))
            if not draw:
                print(f"\n[Notice] Issue {batch.target_issue} has not been drawn yet in ssq_draw_history.")
                print("Run 'python -m backend.app.cli sync' to pull latest official draw data.\n")
                return 0
            verified_batches = [service.verify_batch(batch_id)]

        elif target_issue:
            draw = session.scalar(select(DrawHistory).filter(DrawHistory.issue_no == target_issue))
            if not draw:
                print(f"\n[Notice] Issue {target_issue} has not been drawn yet in ssq_draw_history.")
                print("Run 'python -m backend.app.cli sync' to pull latest official draw data.\n")
                return 0
            batches = session.scalars(select(PredictionBatch).filter(PredictionBatch.target_issue == target_issue)).all()
            if not batches:
                print(f"\n[Notice] No prediction batches found for issue {target_issue}.")
                print(f"Run 'python -m backend.app.cli predict --issue {target_issue}' to generate predictions.\n")
                return 0
            verified_batches = service.verify_issue(target_issue, force=force)

        else:
            # Auto-detect pending batches
            pending_issues = session.scalars(
                select(PredictionBatch.target_issue)
                .filter(PredictionBatch.verify_status == "PENDING")
                .distinct()
            ).all()

            if not pending_issues:
                print("\n[Notice] No pending prediction batches to verify.\n")
                return 0

            found_any = False
            for p_issue in pending_issues:
                draw = session.scalar(select(DrawHistory).filter(DrawHistory.issue_no == p_issue))
                if draw:
                    found_any = True
                    verified_batches.extend(service.verify_issue(p_issue, force=False))
                else:
                    print(f"[Info] Pending batch found for issue {p_issue}, but draw has not occurred yet.")

            if not found_any:
                print("\n[Notice] All pending prediction batches are for future un-drawn issues.\n")
                return 0

    if not verified_batches:
        print("\n[Notice] No batches required verification.\n")
        return 0

    # Print Formatted Verification Reports
    for batch in verified_batches:
        print("\n" + "=" * 80)
        print("SSQ-Quant-System Prize Verification Audit Report (Milestone 4)")
        print("=" * 80)
        print(f"Target Issue : {batch.target_issue}")
        print(f"Batch ID     : {batch.id} | Strategy: {batch.strategy_type} | Status: {batch.verify_status}")
        net_profit = batch.virtual_reward - batch.virtual_cost
        roi_str = f"{(net_profit / batch.virtual_cost):+.1%}" if batch.virtual_cost > 0 else "0.0%"
        print(f"Cost         : {batch.virtual_cost} RMB | Reward: {batch.virtual_reward} RMB | Net: {net_profit:+d} RMB | ROI: {roi_str}")
        print("-" * 80)
        for item in sorted(batch.items, key=lambda x: x.note_index):
            reds_str = f"[{item.red_1:02d}, {item.red_2:02d}, {item.red_3:02d}, {item.red_4:02d}, {item.red_5:02d}, {item.red_6:02d}]"
            hit_reds_display = f"[{item.hit_red_numbers}]" if item.hit_red_numbers else "[]"
            blue_display = f"[{item.blue_1:02d}] ({'HIT' if item.hit_blue else 'MISS'})"
            tier_display = PRIZE_NAMES.get(item.prize_level, f"Tier {item.prize_level}") if item.prize_level > 0 else "No Prize"
            print(f"Note {item.note_index}: {reds_str} + {blue_display} -> Hit Reds: {item.hit_red_count} {hit_reds_display} | {tier_display} ({item.prize_amount} RMB)")
        print("-" * 80)
        if batch.post_reflection_md:
            print(batch.post_reflection_md.strip())
        print("=" * 80)

    print(f"\n[Success] Verified {len(verified_batches)} batch(es) and updated SQLite database.\n")
    return 0


def handle_backtest(args: argparse.Namespace) -> int:
    """
    Handle the `backtest` command (Milestone 4).
    Runs sliding-window historical backtest or side-by-side strategy comparison.
    """
    init_db()
    engine = BacktestEngine()
    n_issues = getattr(args, "issues", 100)
    compare = getattr(args, "compare", False)
    strategy = getattr(args, "strategy", "CONCENTRATED_BREAK_EVEN")

    if compare:
        print("\n" + "=" * 80)
        print("SSQ-Quant-System Comparative Strategy Backtest (Milestone 4)")
        print("=" * 80)
        print(f"Simulating past {n_issues} historical issues under Zero-Lookahead Isolation...")
        try:
            report = engine.compare_strategies(issues=n_issues)
        except Exception as e:
            logger.error("Comparative backtest failed: %s", e)
            print(f"\n[Backtest Error] {e}\n", file=sys.stderr)
            return 1

        print("\n" + report.markdown_table)
        print("-" * 80)
        print("### Quantitative Insights & Game Theory Rationale:")
        print(report.summary_text.strip())
        print("=" * 80)
        print("DISCLAIMER: Lottery games carry an official ~50% house edge with strictly negative mathematical expectation (E[X] = -50%).")
        print("Quantitative optimization models improve payout density conditional on hits, but cannot guarantee future profits.")
        print("=" * 80 + "\n")
        return 0

    # Single strategy mode
    print("\n" + "=" * 80)
    print("SSQ-Quant-System Historical Sliding-Window Backtest (Milestone 4)")
    print("=" * 80)
    print(f"Strategy: {strategy} | Window Size: {n_issues} issues")
    try:
        result = engine.run_backtest(issues=n_issues, strategy=strategy)
    except Exception as e:
        logger.error("Backtest failed: %s", e)
        print(f"\n[Backtest Error] {e}\n", file=sys.stderr)
        return 1

    print("-" * 80)
    print(f"Historical Issue Range   : {result.start_issue} ~ {result.end_issue} (Total: {result.total_issues} issues)")
    print(f"Total Notes / Tickets    : {result.total_tickets} notes (5 notes / issue)")
    print(f"Total Virtual Investment : {result.total_investment} RMB (10 RMB / issue)")
    print(f"Total Prize Returns      : {result.total_returns} RMB")
    print(f"Net Profit / Deficit     : {result.net_profit:+d} RMB")
    print(f"Simulated ROI            : {result.simulated_roi:+.2f}%")
    print("-" * 80)
    print(f"Blue Ball Hit Rate       : {result.blue_hit_rate:.1f}% ({result.blue_hit_issues}/{result.total_issues} issues hit)")
    print(f"  Theoretical Baseline   : {result.theoretical_blue_baseline:.2f}%")
    print(f"Break-Even Rate          : {result.break_even_rate:.1f}% ({result.break_even_issues}/{result.total_issues} issues returned >= 10 RMB)")
    print("-" * 80)
    print("Prize Tier Distribution  :")
    print(f"  Level 1 (一等奖, 6+1)  : {result.level_1_count}")
    print(f"  Level 2 (二等奖, 6+0)  : {result.level_2_count}")
    print(f"  Level 3 (三等奖, 5+1)  : {result.level_3_count}")
    print(f"  Level 4 (四等奖, 5+0/4+1): {result.level_4_count}")
    print(f"  Level 5 (五等奖, 4+0/3+1): {result.level_5_count}")
    print(f"  Level 6 (六等奖, Blue) : {result.level_6_count}")
    print(f"  Miss    (未中奖, 0 RMB): {result.prize_distribution.get(0, 0)}")
    print("-" * 80)
    print(f"Maximum Drawdown (MDD)   : {result.max_drawdown} RMB")
    print(f"Max Win / Loss Streaks   : Wins: {result.max_consecutive_wins} | Losses: {result.max_consecutive_losses}")
    print("=" * 80)
    print("DISCLAIMER: Lottery games carry an official ~50% house edge with strictly negative mathematical expectation (E[X] = -50%).")
    print("Quantitative optimization models improve payout density conditional on hits, but cannot guarantee future profits.")
    print("=" * 80 + "\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="ssq-quant",
        description="SSQ-Quant-System: Discrete Sequence Quantitative Analysis & Prediction Platform",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # Command: sync
    sync_parser = subparsers.add_parser("sync", help="Synchronize historical or incremental draw data")
    sync_parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-fetch and update all historical draws from 2003 to present",
    )
    sync_parser.add_argument(
        "--full",
        action="store_true",
        help="Fetch all historical records from 500.com",
    )
    sync_parser.add_argument(
        "--incremental",
        action="store_true",
        help="Fetch only newly drawn issues via official CWL API",
    )

    # Command: compute-features (Milestone 2)
    feat_parser = subparsers.add_parser("compute-features", help="Compute statistical feature metrics (Milestone 2)")
    feat_parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-computation of all features from the beginning",
    )
    feat_parser.add_argument("--from-issue", type=str, default=None, help="Start calculation from specific issue")

    # Command: predict (Milestone 3)
    pred_parser = subparsers.add_parser("predict", help="Generate 5-line prediction ticket (Milestone 3)")
    pred_parser.add_argument("--issue", type=str, required=False, help="Target issue number to predict")
    pred_parser.add_argument(
        "--strategy",
        type=str,
        default="CONCENTRATED_BREAK_EVEN",
        help="Prediction strategy model (e.g. CONCENTRATED_BREAK_EVEN, break_even, DISPERSED_BASELINE, STAT_FILTER, ML_PROB)",
    )

    # Command: predict-issue (Milestone 3 alias)
    pred_issue_parser = subparsers.add_parser("predict-issue", help="Generate 5-line prediction ticket (alias for predict)")
    pred_issue_parser.add_argument("--issue", type=str, required=False, help="Target issue number to predict")
    pred_issue_parser.add_argument(
        "--strategy",
        type=str,
        default="CONCENTRATED_BREAK_EVEN",
        help="Prediction strategy model",
    )

    # Command: verify (Milestone 4)
    verify_parser = subparsers.add_parser("verify", help="Audit predictions against actual draw (Milestone 4)")
    verify_parser.add_argument("--issue", type=str, required=False, help="Issue number to verify")
    verify_parser.add_argument("--batch-id", type=int, required=False, help="Verify specific prediction batch ID")
    verify_parser.add_argument("--force", action="store_true", help="Re-verify already verified batches")

    # Command: backtest (Milestone 4)
    backtest_parser = subparsers.add_parser("backtest", help="Run historical sliding-window backtest (Milestone 4)")
    backtest_parser.add_argument(
        "--issues",
        type=int,
        default=100,
        help="Number of past historical issues to simulate (e.g. 50, 100, 300)",
    )
    backtest_parser.add_argument(
        "--strategy",
        type=str,
        default="break_even",
        choices=["break_even", "dispersed", "CONCENTRATED_BREAK_EVEN", "DISPERSED_BASELINE"],
        help="Prediction strategy model (default: break_even, choices: break_even, dispersed, CONCENTRATED_BREAK_EVEN, DISPERSED_BASELINE)",
    )
    backtest_parser.add_argument(
        "--compare",
        action="store_true",
        help="Run comparative evaluation comparing CONCENTRATED_BREAK_EVEN vs DISPERSED_BASELINE",
    )

    return parser


def main(argv: Optional[list] = None) -> int:
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.subcommand:
        parser.print_help()
        return 1

    if args.subcommand == "sync":
        return handle_sync(args)
    elif args.subcommand == "compute-features":
        return handle_compute_features(args)
    elif args.subcommand in ("predict", "predict-issue"):
        return handle_predict(args)
    elif args.subcommand == "verify":
        return handle_verify(args)
    elif args.subcommand == "backtest":
        return handle_backtest(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())

