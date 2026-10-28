"""
backend/app/services/backtest_runner.py

Dual-module re-export for BacktestEngine, BacktestResult, StrategyComparisonReport,
and audit_ssq_ticket to satisfy both project layout and E2E test suites.
"""

from backend.app.services.backtest import (
    BacktestEngine,
    BacktestResult,
    StrategyComparisonReport,
    audit_ssq_ticket,
)

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "StrategyComparisonReport",
    "audit_ssq_ticket",
]
