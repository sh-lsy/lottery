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
from backend.app.models import DrawHistory, FeatureMetrics
from backend.app.services.crawler import CrawlerService
from backend.app.services.feature_engine import FeatureEngine
from backend.app.services.predictor import PredictionService

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

    # Command: backtest (Milestone 4)
    backtest_parser = subparsers.add_parser("backtest", help="Run historical sliding-window backtest (Milestone 4)")
    backtest_parser.add_argument("--issues", type=int, default=100, choices=[50, 100, 300], help="Number of past issues")
    backtest_parser.add_argument("--compare", action="store_true", help="Compare concentrated vs dispersed strategies")

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
        print("[M4 Notice] Prize Verification Engine scheduled for Milestone 4.")
        return 0
    elif args.subcommand == "backtest":
        print("[M4 Notice] Historical Backtest Engine scheduled for Milestone 4.")
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
