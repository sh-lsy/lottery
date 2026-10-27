"""
Adversarial and Stress Test Suite for SSQ-Quant-System Milestone 1.
Author: Challenger Agent 1 (critic/specialist)

Covers empirical challenge vectors:
1. Duplicate Issue Numbers (DB integrity, ORM uniqueness, sync idempotency, intra-batch deduplication)
2. Invalid Red Balls (red < 1, red > 33, unsorted reds, duplicate reds, crawler filtering, model check constraints)
3. Invalid Blue Balls (blue < 1, blue > 16, crawler filtering, model check constraints)
4. Concurrency Stress (Multiple rapid concurrent readers while sync/writes occur under SQLite WAL mode)
5. Network Failure & Timeout Simulation (CWL API timeouts, HTTP errors, fallbacks to 500.com, total network failure, rollback safety)
6. Extreme Boundaries & Malformed Input Robustness (boundary values 01/33/16, corrupted payloads)
"""

import concurrent.futures
from datetime import date, datetime
import os
import sqlite3
import tempfile
import time
from typing import List, Dict, Any
from unittest.mock import patch, MagicMock
import pytest
import requests
from sqlalchemy import create_engine, select, func, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError, OperationalError

from backend.app.config import PRIME_RED_SET
from backend.app.database import Base, create_db_engine
from backend.app.models import (
    DrawHistory,
    FeatureMetrics,
    PredictionBatch,
    PredictionItem,
)
from backend.app.services.crawler import CrawlerService, _clean_int


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mem_engine():
    """Create an in-memory SQLite engine with all models initialized."""
    engine = create_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mem_session_factory(mem_engine):
    """Session factory for in-memory engine."""
    return sessionmaker(autocommit=False, autoflush=False, bind=mem_engine)


@pytest.fixture
def temp_disk_db():
    """
    Create a temporary file-based SQLite database with WAL mode and pragmas.
    Crucial for testing true multi-threaded concurrent readers and writers.
    """
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db", prefix="ssq_stress_")
    os.close(tmp_fd)

    db_url = f"sqlite:///{tmp_path.replace(os.sep, '/')}"
    engine = create_db_engine(db_url)
    Base.metadata.create_all(bind=engine)

    # Pre-populate database with 100 historical records
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with session_factory() as session:
        draws = []
        for i in range(1, 101):
            issue_str = f"2026{i:03d}"
            d = DrawHistory(
                issue_no=issue_str,
                draw_date=date(2026, 1, 1),
                weekday=2,
                red_1=1,
                red_2=3,
                red_3=5,
                red_4=7,
                red_5=9,
                red_6=11,
                blue_1=(i % 16) + 1,
                red_seq_str="01,03,05,07,09,11",
                sales_amount=300000000 + i * 1000,
                pool_amount=1000000000 + i * 5000,
                first_prize_num=2,
                first_prize_amount=5000000,
                second_prize_num=50,
                second_prize_amount=100000,
            )
            draws.append(d)
        session.add_all(draws)
        session.commit()

    yield tmp_path, engine, session_factory

    # Teardown
    engine.dispose()
    for ext in ["", "-wal", "-shm"]:
        p = tmp_path + ext
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


# ===========================================================================
# 1. Duplicate Issue Numbers Stress Tests
# ===========================================================================

class TestDuplicateIssueHandling:
    """Stress testing uniqueness and idempotency against duplicate issue numbers."""

    def test_orm_duplicate_issue_rejected(self, mem_session_factory):
        """Ensure inserting identical issue_no via ORM raises IntegrityError."""
        with mem_session_factory() as session:
            d1 = DrawHistory(
                issue_no="2026001",
                draw_date=date(2026, 1, 4),
                weekday=7,
                red_1=1, red_2=2, red_3=3, red_4=4, red_5=5, red_6=6,
                blue_1=1,
                red_seq_str="01,02,03,04,05,06",
            )
            session.add(d1)
            session.commit()

            d2 = DrawHistory(
                issue_no="2026001",  # Exact duplicate issue_no
                draw_date=date(2026, 1, 5),
                weekday=1,
                red_1=7, red_2=8, red_3=9, red_4=10, red_5=11, red_6=12,
                blue_1=2,
                red_seq_str="07,08,09,10,11,12",
            )
            session.add(d2)
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

    def test_raw_sql_duplicate_issue_rejected(self, temp_disk_db):
        """Ensure raw SQLite duplicate INSERT raises sqlite3.IntegrityError."""
        tmp_path, _, _ = temp_disk_db
        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()

        # 2026001 already exists in temp_disk_db
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                """
                INSERT INTO ssq_draw_history 
                (issue_no, draw_date, weekday, red_1, red_2, red_3, red_4, red_5, red_6, blue_1, red_seq_str)
                VALUES ('2026001', '2026-01-01', 2, 1, 2, 3, 4, 5, 6, 1, '01,02,03,04,05,06')
                """
            )
            conn.commit()
        conn.close()

    def test_sync_all_re_run_idempotency(self, mem_session_factory):
        """Verify CrawlerService.sync_all can be executed multiple times without duplicate errors."""
        crawler = CrawlerService(session_factory=mem_session_factory)
        sample_records = [
            {
                "issue_no": "2026010",
                "draw_date": date(2026, 1, 10),
                "weekday": 6,
                "red_1": 2, "red_2": 4, "red_3": 6, "red_4": 8, "red_5": 10, "red_6": 12,
                "blue_1": 5,
                "red_seq_str": "02,04,06,08,10,12",
                "sales_amount": 100000,
                "pool_amount": 500000,
                "first_prize_num": 1,
                "first_prize_amount": 5000000,
                "second_prize_num": 10,
                "second_prize_amount": 50000,
            }
        ]

        with patch.object(crawler, "fetch_500_data", return_value=sample_records):
            # First sync inserts
            added_1 = crawler.sync_all(force=False)
            assert added_1 == 1

            # Second sync without force -> 0 added, no error
            added_2 = crawler.sync_all(force=False)
            assert added_2 == 0

            # Third sync with force -> updates existing row, no error
            added_3 = crawler.sync_all(force=True)
            assert added_3 == 1

            # Verify only 1 row exists
            with mem_session_factory() as session:
                rows = session.scalars(select(DrawHistory).where(DrawHistory.issue_no == "2026010")).all()
                assert len(rows) == 1

    def test_sync_latest_idempotency_on_existing_issue(self, mem_session_factory):
        """Verify sync_latest ignores draws that already exist or are older than max_issue."""
        crawler = CrawlerService(session_factory=mem_session_factory)

        # Pre-insert issue 2026050
        with mem_session_factory() as session:
            session.add(DrawHistory(
                issue_no="2026050",
                draw_date=date(2026, 5, 1),
                weekday=5,
                red_1=1, red_2=2, red_3=3, red_4=4, red_5=5, red_6=6,
                blue_1=1,
                red_seq_str="01,02,03,04,05,06",
            ))
            session.commit()

        # CWL API returns 2026050 and older 2026049
        cwl_records = [
            {
                "issue_no": "2026049",
                "draw_date": date(2026, 4, 28),
                "weekday": 2,
                "red_1": 1, "red_2": 2, "red_3": 3, "red_4": 4, "red_5": 5, "red_6": 6,
                "blue_1": 2,
                "red_seq_str": "01,02,03,04,05,06",
                "sales_amount": 0, "pool_amount": 0,
                "first_prize_num": 0, "first_prize_amount": 0,
                "second_prize_num": 0, "second_prize_amount": 0,
            },
            {
                "issue_no": "2026050",
                "draw_date": date(2026, 5, 1),
                "weekday": 5,
                "red_1": 1, "red_2": 2, "red_3": 3, "red_4": 4, "red_5": 5, "red_6": 6,
                "blue_1": 1,
                "red_seq_str": "01,02,03,04,05,06",
                "sales_amount": 0, "pool_amount": 0,
                "first_prize_num": 0, "first_prize_amount": 0,
                "second_prize_num": 0, "second_prize_amount": 0,
            },
        ]

        with patch.object(crawler, "fetch_cwl_data", return_value=cwl_records):
            added = crawler.sync_latest()
            assert added == 0

            with mem_session_factory() as session:
                count = session.scalar(select(func.count(DrawHistory.id)))
                assert count == 1

    def test_sync_all_intra_batch_duplicates_rejected_by_db_and_rolled_back(self, mem_session_factory):
        """
        Adversarial test: Scraped batch contains duplicate issues within the same response payload.
        Verify that database UNIQUE constraint strictly rejects the batch with IntegrityError,
        and CrawlerService rolls back cleanly without leaving orphan or partial data.
        """
        crawler = CrawlerService(session_factory=mem_session_factory)
        duplicate_batch = [
            {
                "issue_no": "2026300",
                "draw_date": date(2026, 1, 1),
                "weekday": 4,
                "red_1": 1, "red_2": 2, "red_3": 3, "red_4": 4, "red_5": 5, "red_6": 6,
                "blue_1": 1,
                "red_seq_str": "01,02,03,04,05,06",
                "sales_amount": 0, "pool_amount": 0,
                "first_prize_num": 0, "first_prize_amount": 0,
                "second_prize_num": 0, "second_prize_amount": 0,
            },
            {
                "issue_no": "2026300",  # Duplicate issue in same batch
                "draw_date": date(2026, 1, 1),
                "weekday": 4,
                "red_1": 2, "red_2": 3, "red_3": 4, "red_4": 5, "red_5": 6, "red_6": 7,
                "blue_1": 2,
                "red_seq_str": "02,03,04,05,06,07",
                "sales_amount": 0, "pool_amount": 0,
                "first_prize_num": 0, "first_prize_amount": 0,
                "second_prize_num": 0, "second_prize_amount": 0,
            },
        ]

        with patch.object(crawler, "fetch_500_data", return_value=duplicate_batch):
            with pytest.raises(IntegrityError):
                crawler.sync_all()

            # Ensure clean rollback: 0 rows in database
            with mem_session_factory() as session:
                count = session.scalar(select(func.count(DrawHistory.id)))
                assert count == 0


# ===========================================================================
# 2. Invalid Red Balls Stress Tests
# ===========================================================================

class TestInvalidRedBalls:
    """Stress testing red ball range [1, 33] and strictly ascending order constraints."""

    @pytest.mark.parametrize(
        "reds,reason",
        [
            ([0, 2, 3, 4, 5, 6], "red_1 < 1"),
            ([-1, 2, 3, 4, 5, 6], "red_1 negative"),
            ([1, 2, 3, 4, 5, 34], "red_6 > 33"),
            ([1, 2, 3, 4, 5, 99], "red_6 way above 33"),
            ([5, 2, 3, 4, 6, 7], "unsorted: red_1 > red_2"),
            ([1, 4, 3, 5, 6, 7], "unsorted: red_2 > red_3"),
            ([1, 2, 6, 5, 7, 8], "unsorted: red_3 > red_4"),
            ([1, 2, 3, 8, 7, 9], "unsorted: red_4 > red_5"),
            ([1, 2, 3, 4, 9, 8], "unsorted: red_5 > red_6"),
            ([1, 1, 3, 4, 5, 6], "duplicate reds: red_1 == red_2"),
            ([1, 2, 3, 4, 6, 6], "duplicate reds: red_5 == red_6"),
            ([33, 32, 31, 30, 29, 28], "strictly descending order"),
        ],
    )
    def test_db_rejects_invalid_red_balls(self, mem_session_factory, reds, reason):
        """Ensure DrawHistory chk_red_order constraint blocks invalid or unsorted red balls."""
        with mem_session_factory() as session:
            draw = DrawHistory(
                issue_no=f"INV_{hash(str(reds)) % 1000000}",
                draw_date=date(2026, 1, 1),
                weekday=4,
                red_1=reds[0],
                red_2=reds[1],
                red_3=reds[2],
                red_4=reds[3],
                red_5=reds[4],
                red_6=reds[5],
                blue_1=1,
                red_seq_str=",".join(f"{r:02d}" for r in reds),
            )
            session.add(draw)
            with pytest.raises(IntegrityError, match="chk_red_order"):
                session.commit()
            session.rollback()

    @pytest.mark.parametrize(
        "reds",
        [
            [0, 2, 3, 4, 5, 6],
            [1, 2, 3, 4, 5, 34],
            [2, 1, 3, 4, 5, 6],
            [1, 1, 2, 3, 4, 5],
        ],
    )
    def test_prediction_item_rejects_invalid_red_balls(self, mem_session_factory, reds):
        """Ensure PredictionItem chk_note_red_order constraint blocks invalid/unsorted reds."""
        with mem_session_factory() as session:
            batch = PredictionBatch(
                target_issue="2026200",
                strategy_type="CONCENTRATED_BREAK_EVEN",
            )
            session.add(batch)
            session.commit()

            item = PredictionItem(
                batch_id=batch.id,
                target_issue="2026200",
                note_index=1,
                red_1=reds[0], red_2=reds[1], red_3=reds[2],
                red_4=reds[3], red_5=reds[4], red_6=reds[5],
                blue_1=1,
            )
            session.add(item)
            with pytest.raises(IntegrityError, match="chk_note_red_order"):
                session.commit()
            session.rollback()

    def test_crawler_500_filters_invalid_red_balls(self):
        """Ensure CrawlerService._parse_500_html discards rows with invalid red balls."""
        html_with_bad_reds = """
        <html><body><table>
          <!-- Row 1: Valid -->
          <tr class="t_tr1">
            <td>26001</td>
            <td>01</td><td>05</td><td>12</td><td>18</td><td>25</td><td>31</td>
            <td>08</td><td></td>
            <td>1000</td><td>1</td><td>5000000</td><td>10</td><td>100000</td><td>300000000</td>
            <td>2026-01-01</td>
          </tr>
          <!-- Row 2: Red ball 34 > 33 -->
          <tr class="t_tr1">
            <td>26002</td>
            <td>01</td><td>05</td><td>12</td><td>18</td><td>25</td><td>34</td>
            <td>08</td><td></td>
            <td>1000</td><td>1</td><td>5000000</td><td>10</td><td>100000</td><td>300000000</td>
            <td>2026-01-03</td>
          </tr>
          <!-- Row 3: Red ball 0 < 1 -->
          <tr class="t_tr1">
            <td>26003</td>
            <td>00</td><td>05</td><td>12</td><td>18</td><td>25</td><td>31</td>
            <td>08</td><td></td>
            <td>1000</td><td>1</td><td>5000000</td><td>10</td><td>100000</td><td>300000000</td>
            <td>2026-01-05</td>
          </tr>
          <!-- Row 4: Duplicate red ball -->
          <tr class="t_tr1">
            <td>26004</td>
            <td>05</td><td>05</td><td>12</td><td>18</td><td>25</td><td>31</td>
            <td>08</td><td></td>
            <td>1000</td><td>1</td><td>5000000</td><td>10</td><td>100000</td><td>300000000</td>
            <td>2026-01-07</td>
          </tr>
        </table></body></html>
        """
        crawler = CrawlerService()
        parsed = crawler._parse_500_html(html_with_bad_reds)
        assert len(parsed) == 1
        assert parsed[0]["issue_no"] == "2026001"

    def test_crawler_cwl_filters_invalid_red_balls(self):
        """Ensure CrawlerService._parse_cwl_json discards items with invalid red balls."""
        bad_cwl_items = [
            {
                "code": "2026001",
                "date": "2026-01-01",
                "red": "01,05,12,18,25,31",  # Valid
                "blue": "08",
            },
            {
                "code": "2026002",
                "date": "2026-01-03",
                "red": "01,05,12,18,25,34",  # Red > 33
                "blue": "08",
            },
            {
                "code": "2026003",
                "date": "2026-01-05",
                "red": "01,05,12,18,25,25",  # Duplicate red
                "blue": "08",
            },
            {
                "code": "2026004",
                "date": "2026-01-07",
                "red": "01,05,12,18",  # Only 4 reds
                "blue": "08",
            },
        ]
        crawler = CrawlerService()
        parsed = crawler._parse_cwl_json(bad_cwl_items)
        assert len(parsed) == 1
        assert parsed[0]["issue_no"] == "2026001"

    def test_crawler_auto_sorts_unsorted_red_balls(self):
        """Ensure that if upstream data provides unsorted reds, crawler safely sorts them."""
        cwl_unsorted = [
            {
                "code": "2026099",
                "date": "2026-10-01",
                "red": "31,05,25,01,18,12",  # Unsorted
                "blue": "10",
            }
        ]
        crawler = CrawlerService()
        parsed = crawler._parse_cwl_json(cwl_unsorted)
        assert len(parsed) == 1
        assert [parsed[0][f"red_{i}"] for i in range(1, 7)] == [1, 5, 12, 18, 25, 31]
        assert parsed[0]["red_seq_str"] == "01,05,12,18,25,31"


# ===========================================================================
# 3. Invalid Blue Ball Stress Tests
# ===========================================================================

class TestInvalidBlueBall:
    """Stress testing blue ball range [1, 16]."""

    @pytest.mark.parametrize("blue_val", [0, -1, 17, 99])
    def test_db_rejects_invalid_blue_ball(self, mem_session_factory, blue_val):
        """Ensure DrawHistory chk_blue_range constraint blocks blue < 1 or > 16."""
        with mem_session_factory() as session:
            draw = DrawHistory(
                issue_no=f"INV_BLUE_{blue_val}",
                draw_date=date(2026, 1, 1),
                weekday=2,
                red_1=1, red_2=2, red_3=3, red_4=4, red_5=5, red_6=6,
                blue_1=blue_val,
                red_seq_str="01,02,03,04,05,06",
            )
            session.add(draw)
            with pytest.raises(IntegrityError, match="chk_blue_range"):
                session.commit()
            session.rollback()

    @pytest.mark.parametrize("blue_val", [0, -5, 17, 25])
    def test_prediction_item_rejects_invalid_blue_ball(self, mem_session_factory, blue_val):
        """Ensure PredictionItem chk_note_blue constraint blocks blue < 1 or > 16."""
        with mem_session_factory() as session:
            batch = PredictionBatch(
                target_issue="2026201",
                strategy_type="CONCENTRATED_BREAK_EVEN",
            )
            session.add(batch)
            session.commit()

            item = PredictionItem(
                batch_id=batch.id,
                target_issue="2026201",
                note_index=1,
                red_1=1, red_2=2, red_3=3, red_4=4, red_5=5, red_6=6,
                blue_1=blue_val,
            )
            session.add(item)
            with pytest.raises(IntegrityError, match="chk_note_blue"):
                session.commit()
            session.rollback()

    def test_crawler_filters_out_of_range_blue_ball(self):
        """Ensure crawler discards records where blue ball is outside [1, 16]."""
        bad_cwl = [
            {"code": "2026010", "date": "2026-01-10", "red": "01,02,03,04,05,06", "blue": "0"},
            {"code": "2026011", "date": "2026-01-12", "red": "01,02,03,04,05,06", "blue": "17"},
            {"code": "2026012", "date": "2026-01-14", "red": "01,02,03,04,05,06", "blue": "16"},  # Valid boundary
        ]
        crawler = CrawlerService()
        parsed = crawler._parse_cwl_json(bad_cwl)
        assert len(parsed) == 1
        assert parsed[0]["issue_no"] == "2026012"
        assert parsed[0]["blue_1"] == 16


# ===========================================================================
# 4. Concurrency Stress: Rapid Reads During Active Writes
# ===========================================================================

class TestConcurrencyAndWAL:
    """
    Stress-testing SQLite WAL mode concurrency.
    Spawns multiple simultaneous threads performing continuous high-throughput
    read queries while a writer thread performs inserts and updates.
    """

    def test_sqlite_wal_pragmas_active(self, temp_disk_db):
        """Verify WAL mode, busy_timeout, foreign_keys, and synchronous settings."""
        _, engine, _ = temp_disk_db
        with engine.connect() as conn:
            journal_mode = conn.exec_driver_sql("PRAGMA journal_mode;").scalar()
            sync_mode = conn.exec_driver_sql("PRAGMA synchronous;").scalar()
            fk_mode = conn.exec_driver_sql("PRAGMA foreign_keys;").scalar()
            busy_to = conn.exec_driver_sql("PRAGMA busy_timeout;").scalar()

            assert journal_mode.lower() == "wal"
            assert sync_mode in (1, "NORMAL", "1")
            assert fk_mode == 1
            assert busy_to == 5000

    def test_concurrent_rapid_reads_during_writer_sync(self, temp_disk_db):
        """
        Adversarial concurrency test:
        10 reader threads execute 50 fast read queries each (500 total reads).
        Simultaneously, a writer thread inserts 30 new records and performs updates.
        Must execute without 'database is locked' errors and with 100% data integrity.
        """
        tmp_path, engine, session_factory = temp_disk_db

        read_errors = []
        read_successes = [0]
        stop_flag = False

        def reader_worker(thread_idx: int):
            """Continuously queries database until iterations finish."""
            local_session = sessionmaker(bind=engine)()
            try:
                for _ in range(50):
                    # Query 1: Aggregate count and min/max
                    count = local_session.scalar(select(func.count(DrawHistory.id)))
                    assert count >= 100

                    # Query 2: Range query ordered by issue
                    draws = local_session.scalars(
                        select(DrawHistory).order_by(DrawHistory.issue_no.desc()).limit(10)
                    ).all()
                    assert len(draws) == 10

                    # Query 3: Specific record lookup
                    sample = local_session.scalar(
                        select(DrawHistory).where(DrawHistory.issue_no == "2026050")
                    )
                    assert sample is not None

                    read_successes[0] += 1
                    time.sleep(0.005)  # brief yield
            except Exception as e:
                read_errors.append(f"Reader {thread_idx} failed: {type(e).__name__}: {e}")
            finally:
                local_session.close()

        def writer_worker():
            """Writes 30 new records in batches, simulating CrawlerService."""
            local_session = sessionmaker(bind=engine)()
            try:
                for batch in range(1, 4):
                    time.sleep(0.02)
                    new_draws = []
                    for i in range(1, 11):
                        issue_num = 200 + batch * 10 + i
                        d = DrawHistory(
                            issue_no=f"2026{issue_num:03d}",
                            draw_date=date(2026, 6, i),
                            weekday=3,
                            red_1=2, red_2=4, red_3=6, red_4=8, red_5=10, red_6=12,
                            blue_1=7,
                            red_seq_str="02,04,06,08,10,12",
                        )
                        new_draws.append(d)
                    local_session.add_all(new_draws)
                    local_session.commit()
            finally:
                local_session.close()

        # Launch 10 readers and 1 writer concurrently using ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=11) as executor:
            reader_futures = [executor.submit(reader_worker, i) for i in range(10)]
            writer_future = executor.submit(writer_worker)

            # Wait for all to finish
            writer_future.result()
            for rf in reader_futures:
                rf.result()

        # Assertions
        assert len(read_errors) == 0, f"Encountered concurrency read errors: {read_errors}"
        assert read_successes[0] == 500  # 10 threads * 50 queries

        # Verify writer successfully added all 30 rows (100 initial + 30 = 130)
        with session_factory() as session:
            final_count = session.scalar(select(func.count(DrawHistory.id)))
            assert final_count == 130


# ===========================================================================
# 5. Network Failure & Timeout Simulation for CrawlerService Fallback
# ===========================================================================

class TestCrawlerNetworkResilience:
    """Stress-testing network timeouts, HTTP error codes, fallbacks, and rollbacks."""

    def test_cwl_timeout_falls_back_to_500(self, mem_session_factory):
        """Simulate requests.exceptions.Timeout on CWL API, verifying seamless fallback to 500.com."""
        crawler = CrawlerService(session_factory=mem_session_factory)

        # Seed initial draw
        with mem_session_factory() as session:
            session.add(DrawHistory(
                issue_no="2026100",
                draw_date=date(2026, 10, 1),
                weekday=4,
                red_1=1, red_2=2, red_3=3, red_4=4, red_5=5, red_6=6,
                blue_1=1,
                red_seq_str="01,02,03,04,05,06",
            ))
            session.commit()

        fallback_500_records = [
            {
                "issue_no": "2026101",
                "draw_date": date(2026, 10, 3),
                "weekday": 6,
                "red_1": 2, "red_2": 5, "red_3": 8, "red_4": 14, "red_5": 20, "red_6": 28,
                "blue_1": 15,
                "red_seq_str": "02,05,08,14,20,28",
                "sales_amount": 350000000,
                "pool_amount": 1000000000,
                "first_prize_num": 5,
                "first_prize_amount": 7000000,
                "second_prize_num": 100,
                "second_prize_amount": 150000,
            }
        ]

        # Patch CWL to raise Timeout, and 500.com to return fallback records
        with patch.object(crawler, "fetch_cwl_data", side_effect=requests.exceptions.Timeout("Connection timed out")):
            with patch.object(crawler, "fetch_500_data", return_value=fallback_500_records) as mock_500:
                added = crawler.sync_latest()
                assert added == 1
                mock_500.assert_called_once()

                with mem_session_factory() as session:
                    new_draw = session.scalar(select(DrawHistory).where(DrawHistory.issue_no == "2026101"))
                    assert new_draw is not None
                    assert new_draw.blue == 15

    def test_cwl_http_503_error_retries_and_falls_back(self, mem_session_factory):
        """Simulate CWL returning HTTP 503 Service Unavailable, verifying retry and fallback."""
        crawler = CrawlerService(session_factory=mem_session_factory)

        # Pre-seed DB
        with mem_session_factory() as session:
            session.add(DrawHistory(
                issue_no="2026110",
                draw_date=date(2026, 10, 10),
                weekday=6,
                red_1=1, red_2=2, red_3=3, red_4=4, red_5=5, red_6=6,
                blue_1=1,
                red_seq_str="01,02,03,04,05,06",
            ))
            session.commit()

        mock_503_response = MagicMock()
        mock_503_response.status_code = 503

        # Speed up retry sleep during test
        with patch("backend.app.services.crawler.time.sleep", return_value=None):
            with patch("backend.app.services.crawler.requests.get", return_value=mock_503_response):
                # fetch_cwl_data will fail after 3 retries and raise RuntimeError
                with patch.object(crawler, "fetch_500_data") as mock_500:
                    mock_500.return_value = [
                        {
                            "issue_no": "2026111",
                            "draw_date": date(2026, 10, 12),
                            "weekday": 1,
                            "red_1": 3, "red_2": 6, "red_3": 9, "red_4": 12, "red_5": 15, "red_6": 18,
                            "blue_1": 4,
                            "red_seq_str": "03,06,09,12,15,18",
                            "sales_amount": 0, "pool_amount": 0,
                            "first_prize_num": 0, "first_prize_amount": 0,
                            "second_prize_num": 0, "second_prize_amount": 0,
                        }
                    ]
                    added = crawler.sync_latest()
                    assert added == 1

    def test_complete_network_outage_raises_runtime_error_and_rolls_back(self, mem_session_factory):
        """Simulate catastrophic failure of both CWL and 500.com; verify RuntimeError and clean rollback."""
        crawler = CrawlerService(session_factory=mem_session_factory)

        with mem_session_factory() as session:
            session.add(DrawHistory(
                issue_no="2026120",
                draw_date=date(2026, 10, 20),
                weekday=2,
                red_1=1, red_2=2, red_3=3, red_4=4, red_5=5, red_6=6,
                blue_1=1,
                red_seq_str="01,02,03,04,05,06",
            ))
            session.commit()

        with patch.object(crawler, "fetch_cwl_data", side_effect=RuntimeError("CWL Down")):
            with patch.object(crawler, "fetch_500_data", side_effect=RuntimeError("500.com Down")):
                with pytest.raises(RuntimeError, match="500.com Down"):
                    crawler.sync_latest()

                # Verify database session was rolled back cleanly and still operates
                with mem_session_factory() as session:
                    count = session.scalar(select(func.count(DrawHistory.id)))
                    assert count == 1


# ===========================================================================
# 6. Extreme Boundaries & Malformed Input Robustness
# ===========================================================================

class TestBoundaryAndMalformedInputs:
    """Testing extreme edge cases, boundaries, and corrupted input payloads."""

    def test_minimum_boundary_draw(self, mem_session_factory):
        """Draw with absolute minimal red balls [1, 2, 3, 4, 5, 6] and blue 1."""
        with mem_session_factory() as session:
            draw = DrawHistory(
                issue_no="2003000",
                draw_date=date(2003, 1, 1),
                weekday=3,
                red_1=1, red_2=2, red_3=3, red_4=4, red_5=5, red_6=6,
                blue_1=1,
                red_seq_str="01,02,03,04,05,06",
            )
            session.add(draw)
            session.commit()
            assert draw.reds == [1, 2, 3, 4, 5, 6]
            assert draw.blue == 1

    def test_maximum_boundary_draw(self, mem_session_factory):
        """Draw with absolute maximum red balls [28, 29, 30, 31, 32, 33] and blue 16."""
        with mem_session_factory() as session:
            draw = DrawHistory(
                issue_no="2026999",
                draw_date=date(2026, 12, 31),
                weekday=4,
                red_1=28, red_2=29, red_3=30, red_4=31, red_5=32, red_6=33,
                blue_1=16,
                red_seq_str="28,29,30,31,32,33",
            )
            session.add(draw)
            session.commit()
            assert draw.reds == [28, 29, 30, 31, 32, 33]
            assert draw.blue == 16

    @pytest.mark.parametrize("invalid_weekday", [0, 8, -1, 100])
    def test_invalid_weekday_rejected(self, mem_session_factory, invalid_weekday):
        """Ensure weekday is constrained strictly to ISO weekdays 1..7."""
        with mem_session_factory() as session:
            draw = DrawHistory(
                issue_no="2026888",
                draw_date=date(2026, 1, 1),
                weekday=invalid_weekday,
                red_1=1, red_2=2, red_3=3, red_4=4, red_5=5, red_6=6,
                blue_1=1,
                red_seq_str="01,02,03,04,05,06",
            )
            session.add(draw)
            with pytest.raises(IntegrityError, match="chk_weekday"):
                session.commit()
            session.rollback()

    def test_crawler_malformed_html_empty_table(self):
        """Verify CrawlerService handles completely empty HTML without crashing."""
        empty_html = "<html><body><table></table></body></html>"
        crawler = CrawlerService()
        parsed = crawler._parse_500_html(empty_html)
        assert parsed == []

    def test_crawler_cwl_malformed_empty_result(self):
        """Verify CrawlerService handles empty CWL items without crashing."""
        crawler = CrawlerService()
        parsed = crawler._parse_cwl_json([])
        assert parsed == []

    def test_clean_int_extreme_inputs(self):
        """Verify _clean_int resilience against special chars, unicode, scientific notation."""
        assert _clean_int("¥1,056,837,777元") == 1056837777
        assert _clean_int("N/A") == 0
        assert _clean_int("---") == 0
        assert _clean_int(None) == 0
        assert _clean_int(999999999999) == 999999999999
