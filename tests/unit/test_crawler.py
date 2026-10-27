"""
Unit tests for SSQ-Quant-System Milestone 1:
- Database schema, models, constraints, and relationships
- SQLite WAL mode and PRAGMA settings
- 500.com HTML parsing and edge case filtering
- CWL JSON API parsing and prize extraction
- CrawlerService sync_all, sync_latest, and fallback handling
- CLI command invocation and argument parsing
"""

from datetime import date, datetime
import json
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from backend.app.database import Base, create_db_engine
from backend.app.models import (
    DrawHistory,
    FeatureMetrics,
    PredictionBatch,
    PredictionItem,
)
from backend.app.services.crawler import CrawlerService, _clean_int
from backend.app.cli import build_parser, main


# Fixtures
@pytest.fixture
def test_engine():
    """Create an isolated in-memory SQLite engine for tests."""
    engine = create_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_session_factory(test_engine):
    """Create a sessionmaker bound to test_engine."""
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture
def test_session(test_session_factory):
    """Create an isolated database session."""
    session = test_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_500_html():
    """Sample raw HTML snippet mimicking 500.com history page."""
    return """
    <html>
      <body>
        <table>
          <tr class="t_tr1">
            <td>26122</td>
            <td>01</td><td>02</td><td>04</td><td>17</td><td>19</td><td>30</td>
            <td>09</td>
            <td></td>
            <td>1,056,837,777</td>
            <td>7</td><td>6,823,202</td>
            <td>115</td><td>138,721</td>
            <td>364,308,228</td>
            <td>2026-10-25</td>
          </tr>
          <tr class="t_tr1">
            <td>03001</td>
            <td>10</td><td>11</td><td>12</td><td>13</td><td>26</td><td>28</td>
            <td>11</td>
            <td></td>
            <td>0</td>
            <td>0</td><td>0</td>
            <td>0</td><td>0</td>
            <td>0</td>
            <td>2003-02-23</td>
          </tr>
          <!-- Malformed row: invalid red ball count -->
          <tr class="t_tr1">
            <td>26121</td>
            <td>01</td><td>02</td><td>03</td>
            <td>05</td>
            <td></td>
            <td>0</td>
            <td>0</td><td>0</td>
            <td>0</td><td>0</td>
            <td>0</td>
            <td>2026-10-23</td>
          </tr>
        </table>
      </body>
    </html>
    """


@pytest.fixture
def sample_cwl_items():
    """Sample raw CWL JSON draw result item list."""
    return [
        {
            "code": "2026122",
            "date": "2026-10-25(日)",
            "red": "01,02,04,17,19,30",
            "blue": "09",
            "sales": "364308228",
            "poolmoney": "1056837777",
            "prizegrades": [
                {"type": 1, "typenum": "7", "typemoney": "6823202"},
                {"type": 2, "typenum": "115", "typemoney": "138721"},
            ],
        },
        {
            "code": "2026123",
            "date": "2026-10-27(二)",
            "red": "05,09,14,21,22,29",
            "blue": "16",
            "sales": "370000000",
            "poolmoney": "1100000000",
            "prizegrades": [
                {"type": 1, "typenum": "5", "typemoney": "8000000"},
                {"type": 2, "typenum": "90", "typemoney": "200000"},
            ],
        },
    ]


# ---------------------------------------------------------------------------
# 1. Database Schema & Model Tests
# ---------------------------------------------------------------------------
class TestDatabaseModels:
    def test_tables_registered(self, test_engine):
        """Verify that all 4 required tables are registered and created."""
        table_names = list(Base.metadata.tables.keys())
        expected_tables = [
            "ssq_draw_history",
            "ssq_feature_metrics",
            "ssq_prediction_batches",
            "ssq_prediction_items",
        ]
        for tbl in expected_tables:
            assert tbl in table_names

    def test_draw_history_crud(self, test_session):
        """Test inserting and querying a DrawHistory record."""
        draw = DrawHistory(
            issue_no="2026120",
            draw_date=date(2026, 10, 20),
            weekday=2,
            red_1=2,
            red_2=8,
            red_3=15,
            red_4=21,
            red_5=26,
            red_6=31,
            blue_1=8,
            red_seq_str="02,08,15,21,26,31",
            sales_amount=350000000,
            pool_amount=1000000000,
            first_prize_num=5,
            first_prize_amount=7000000,
            second_prize_num=100,
            second_prize_amount=150000,
        )
        test_session.add(draw)
        test_session.commit()

        queried = test_session.scalar(select(DrawHistory).where(DrawHistory.issue_no == "2026120"))
        assert queried is not None
        assert queried.reds == [2, 8, 15, 21, 26, 31]
        assert queried.blue == 8
        assert queried.sales_amount == 350000000
        assert queried.to_dict()["issue_no"] == "2026120"

    def test_unique_issue_no_constraint(self, test_session):
        """Verify unique constraint on issue_no."""
        d1 = DrawHistory(
            issue_no="2026100",
            draw_date=date(2026, 10, 1),
            weekday=4,
            red_1=1, red_2=2, red_3=3, red_4=4, red_5=5, red_6=6,
            blue_1=1,
            red_seq_str="01,02,03,04,05,06",
        )
        d2 = DrawHistory(
            issue_no="2026100",  # Duplicate issue_no
            draw_date=date(2026, 10, 1),
            weekday=4,
            red_1=7, red_2=8, red_3=9, red_4=10, red_5=11, red_6=12,
            blue_1=2,
            red_seq_str="07,08,09,10,11,12",
        )
        test_session.add(d1)
        test_session.commit()

        test_session.add(d2)
        with pytest.raises(IntegrityError):
            test_session.commit()
        test_session.rollback()

    def test_feature_metrics_relationship_and_cascade(self, test_session):
        """Verify 1:1 relationship and ON DELETE CASCADE with DrawHistory."""
        draw = DrawHistory(
            issue_no="2026110",
            draw_date=date(2026, 10, 15),
            weekday=4,
            red_1=3, red_2=7, red_3=12, red_4=18, red_5=24, red_6=30,
            blue_1=5,
            red_seq_str="03,07,12,18,24,30",
        )
        test_session.add(draw)
        test_session.commit()

        metrics = FeatureMetrics(
            issue_no="2026110",
            sum_red=94,
            span_red=27,
            ac_value=8,
            odd_count=2,
            prime_count=2,
            zone1_count=2,
            zone2_count=2,
            zone3_count=2,
            consecutive_groups=0,
            repeat_prev_red=1,
            missing_sum_red=25,
            missing_blue=4,
            missing_snapshot_json=json.dumps({"red": {"1": 0}, "blue": {"1": 3}}),
        )
        test_session.add(metrics)
        test_session.commit()

        # Query back and verify back_populates
        queried_draw = test_session.scalar(select(DrawHistory).where(DrawHistory.issue_no == "2026110"))
        assert queried_draw.feature_metrics is not None
        assert queried_draw.feature_metrics.sum_red == 94
        assert queried_draw.feature_metrics.ac_value == 8
        assert queried_draw.feature_metrics.missing_snapshot == {"red": {"1": 0}, "blue": {"1": 3}}

        # Delete parent draw and verify cascade delete of metrics
        test_session.delete(queried_draw)
        test_session.commit()

        queried_metrics = test_session.scalar(select(FeatureMetrics).where(FeatureMetrics.issue_no == "2026110"))
        assert queried_metrics is None

    def test_prediction_batch_and_items_relationship(self, test_session):
        """Verify 1:N relationship between PredictionBatch and PredictionItem."""
        batch = PredictionBatch(
            target_issue="2026130",
            strategy_type="CONCENTRATED_BREAK_EVEN",
            model_name="Ensemble-v1.0",
            total_notes=5,
            virtual_cost=10,
        )
        test_session.add(batch)
        test_session.commit()

        for i in range(1, 6):
            item = PredictionItem(
                batch_id=batch.id,
                target_issue="2026130",
                note_index=i,
                red_1=i, red_2=i + 1, red_3=i + 2, red_4=i + 3, red_5=i + 4, red_6=i + 5,
                blue_1=9 if i <= 3 else 12,
                confidence_score=85.0 - i,
            )
            test_session.add(item)
        test_session.commit()

        queried_batch = test_session.scalar(select(PredictionBatch).where(PredictionBatch.id == batch.id))
        assert len(queried_batch.items) == 5
        assert queried_batch.items[0].note_index == 1
        assert queried_batch.items[0].blue == 9
        assert queried_batch.items[4].blue == 12

        # Delete batch and verify items cascade
        test_session.delete(queried_batch)
        test_session.commit()

        remaining_items = test_session.scalars(select(PredictionItem).where(PredictionItem.target_issue == "2026130")).all()
        assert len(remaining_items) == 0


# ---------------------------------------------------------------------------
# 2. Crawler Parsing Logic Tests
# ---------------------------------------------------------------------------
class TestCrawlerParsing:
    def test_clean_int_utility(self):
        """Test _clean_int helper with various string inputs."""
        assert _clean_int("1,056,837,777") == 1056837777
        assert _clean_int("  364,308,228  ") == 364308228
        assert _clean_int("") == 0
        assert _clean_int(None) == 0
        assert _clean_int("abc") == 0
        assert _clean_int(12345) == 12345

    def test_parse_500_html(self, sample_500_html):
        """Test HTML parsing of 500.com tabular format."""
        crawler = CrawlerService()
        records = crawler._parse_500_html(sample_500_html)

        # 2 valid rows parsed, 1 malformed row skipped
        assert len(records) == 2

        # Ascending order check: 2003001 comes before 2026122
        assert records[0]["issue_no"] == "2003001"
        assert records[1]["issue_no"] == "2026122"

        rec_earliest = records[0]
        assert rec_earliest["draw_date"] == date(2003, 2, 23)
        assert rec_earliest["weekday"] == 7
        assert [rec_earliest[f"red_{i}"] for i in range(1, 7)] == [10, 11, 12, 13, 26, 28]
        assert rec_earliest["blue_1"] == 11

        rec_latest = records[1]
        assert rec_latest["draw_date"] == date(2026, 10, 25)
        assert rec_latest["weekday"] == 7
        assert [rec_latest[f"red_{i}"] for i in range(1, 7)] == [1, 2, 4, 17, 19, 30]
        assert rec_latest["blue_1"] == 9
        assert rec_latest["red_seq_str"] == "01,02,04,17,19,30"
        assert rec_latest["pool_amount"] == 1056837777
        assert rec_latest["first_prize_num"] == 7
        assert rec_latest["first_prize_amount"] == 6823202
        assert rec_latest["second_prize_num"] == 115
        assert rec_latest["second_prize_amount"] == 138721
        assert rec_latest["sales_amount"] == 364308228

    def test_parse_cwl_json(self, sample_cwl_items):
        """Test JSON parsing of official CWL draw items."""
        crawler = CrawlerService()
        records = crawler._parse_cwl_json(sample_cwl_items)

        assert len(records) == 2
        assert records[0]["issue_no"] == "2026122"
        assert records[1]["issue_no"] == "2026123"

        rec1 = records[0]
        assert rec1["draw_date"] == date(2026, 10, 25)
        assert rec1["weekday"] == 7
        assert [rec1[f"red_{i}"] for i in range(1, 7)] == [1, 2, 4, 17, 19, 30]
        assert rec1["blue_1"] == 9
        assert rec1["first_prize_num"] == 7
        assert rec1["first_prize_amount"] == 6823202

        rec2 = records[1]
        assert rec2["draw_date"] == date(2026, 10, 27)
        assert rec2["weekday"] == 2
        assert [rec2[f"red_{i}"] for i in range(1, 7)] == [5, 9, 14, 21, 22, 29]
        assert rec2["blue_1"] == 16
        assert rec2["first_prize_num"] == 5
        assert rec2["first_prize_amount"] == 8000000


# ---------------------------------------------------------------------------
# 3. Crawler Synchronization & Idempotency Tests
# ---------------------------------------------------------------------------
class TestCrawlerSyncEngine:
    def test_sync_all_mocked(self, test_session_factory, sample_500_html):
        """Test sync_all populates database from mocked 500.com response."""
        crawler = CrawlerService(session_factory=test_session_factory)

        with patch.object(crawler, "fetch_500_data") as mock_fetch:
            mock_fetch.return_value = crawler._parse_500_html(sample_500_html)

            # First run: 2 records inserted
            count = crawler.sync_all(force=False)
            assert count == 2

            with test_session_factory() as session:
                total = session.scalar(select(func.count(DrawHistory.id)))
                assert total == 2
                draw = session.scalar(select(DrawHistory).where(DrawHistory.issue_no == "2003001"))
                assert draw is not None
                assert draw.blue == 11

            # Second run without force: 0 new records inserted (idempotency)
            count2 = crawler.sync_all(force=False)
            assert count2 == 0

            with test_session_factory() as session:
                total2 = session.scalar(select(func.count(DrawHistory.id)))
                assert total2 == 2

            # Third run with force: updates existing records
            count3 = crawler.sync_all(force=True)
            assert count3 == 2

    def test_sync_latest_incremental(self, test_session_factory, sample_500_html, sample_cwl_items):
        """Test incremental synchronization adding new draws."""
        crawler = CrawlerService(session_factory=test_session_factory)

        # Pre-populate DB with 2003001 and 2026122 from 500.com
        with patch.object(crawler, "fetch_500_data") as mock_500:
            mock_500.return_value = crawler._parse_500_html(sample_500_html)
            crawler.sync_all(force=False)

        # CWL API returns 2026122 (already in DB) and 2026123 (brand new)
        with patch.object(crawler, "fetch_cwl_data") as mock_cwl:
            mock_cwl.return_value = crawler._parse_cwl_json(sample_cwl_items)

            added = crawler.sync_latest()
            assert added == 1  # Only 2026123 should be added

            with test_session_factory() as session:
                total = session.scalar(select(func.count(DrawHistory.id)))
                assert total == 3
                new_draw = session.scalar(select(DrawHistory).where(DrawHistory.issue_no == "2026123"))
                assert new_draw is not None
                assert new_draw.reds == [5, 9, 14, 21, 22, 29]
                assert new_draw.blue == 16

            # Re-running sync_latest: up-to-date, 0 added
            added_again = crawler.sync_latest()
            assert added_again == 0

    def test_sync_latest_fallback_to_500(self, test_session_factory, sample_500_html):
        """Test that failure in CWL API gracefully falls back to 500.com range fetch."""
        crawler = CrawlerService(session_factory=test_session_factory)

        # Seed database
        with patch.object(crawler, "fetch_500_data") as mock_500:
            mock_500.return_value = crawler._parse_500_html(sample_500_html)
            crawler.sync_all(force=False)

        # Mock CWL to raise RuntimeError, fallback returns 500.com data with new issue
        new_row_html = """
        <html><body><table>
          <tr class="t_tr1">
            <td>26124</td>
            <td>02</td><td>08</td><td>15</td><td>21</td><td>26</td><td>31</td>
            <td>08</td><td></td>
            <td>1000</td><td>1</td><td>5000000</td><td>10</td><td>100000</td><td>350000000</td>
            <td>2026-10-29</td>
          </tr>
        </table></body></html>
        """
        with patch.object(crawler, "fetch_cwl_data", side_effect=RuntimeError("CWL Timeout")):
            with patch.object(crawler, "fetch_500_data") as mock_500_fallback:
                mock_500_fallback.return_value = crawler._parse_500_html(new_row_html)
                added = crawler.sync_latest()
                assert added == 1

                with test_session_factory() as session:
                    draw = session.scalar(select(DrawHistory).where(DrawHistory.issue_no == "2026124"))
                    assert draw is not None
                    assert draw.blue == 8


# ---------------------------------------------------------------------------
# 4. CLI Argument Parser Tests
# ---------------------------------------------------------------------------
class TestCLIParser:
    def test_parser_sync_options(self):
        """Verify CLI parser configuration for sync command."""
        parser = build_parser()

        args = parser.parse_args(["sync"])
        assert args.subcommand == "sync"
        assert args.force is False
        assert args.full is False
        assert args.incremental is False

        args_force = parser.parse_args(["sync", "--force"])
        assert args_force.force is True

        args_full = parser.parse_args(["sync", "--full"])
        assert args_full.full is True

        args_inc = parser.parse_args(["sync", "--incremental"])
        assert args_inc.incremental is True

    def test_parser_future_subcommands(self):
        """Verify future subcommands are recognized."""
        parser = build_parser()

        assert parser.parse_args(["compute-features"]).subcommand == "compute-features"
        assert parser.parse_args(["predict", "--issue", "2026125"]).subcommand == "predict"
        assert parser.parse_args(["verify", "--issue", "2026124"]).subcommand == "verify"
        assert parser.parse_args(["backtest", "--issues", "100"]).subcommand == "backtest"

    def test_cli_main_subcommand_dispatch(self):
        """Verify cli main() dispatches appropriately without errors."""
        assert main(["compute-features"]) == 0
        assert main(["predict"]) == 0
        assert main(["verify"]) == 0
        assert main(["backtest"]) == 0
