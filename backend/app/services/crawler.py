"""
CrawlerService for SSQ-Quant-System.
Implements dual-source crawler architecture:
- 500.com tabular endpoint for full historical bulk ingestion (2003001 to present)
- CWL official JSON API for incremental live synchronization with 500.com fallback
- Idempotent upsert logic into SQLite ssq_draw_history
"""

from datetime import datetime, date
import logging
import re
import time
from typing import List, Dict, Any, Optional

import requests
from lxml import etree
from sqlalchemy import select, func
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import (
    CRAWLER_500_BASE_URL,
    CWL_API_BASE_URL,
    DEFAULT_HEADERS_500,
    DEFAULT_HEADERS_CWL,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    DEFAULT_START_ISSUE_500,
    DEFAULT_END_ISSUE_500,
)
from backend.app.database import SessionLocal, init_db
from backend.app.models import DrawHistory

logger = logging.getLogger("ssq_quant.crawler")


def _clean_int(val: Any) -> int:
    """Helper to parse raw scraped text into integer, stripping commas and whitespace."""
    if val is None:
        return 0
    cleaned = re.sub(r"[^0-9]", "", str(val))
    return int(cleaned) if cleaned else 0


class CrawlerService:
    """
    Crawler service handling both bulk historical scraping and real-time incremental updates.
    """

    def __init__(
        self,
        session_factory: Optional[sessionmaker] = None,
        db_session: Optional[Session] = None,
    ):
        """
        Initialize CrawlerService.
        Can accept custom session_factory or db_session for testing/isolation.
        """
        self.session_factory = session_factory or SessionLocal
        self._external_session = db_session

    def _get_session(self) -> Session:
        """Provide an active session (either external or new from factory)."""
        if self._external_session is not None:
            return self._external_session
        return self.session_factory()

    def fetch_500_data(
        self,
        start_issue: str = DEFAULT_START_ISSUE_500,
        end_issue: str = DEFAULT_END_ISSUE_500,
    ) -> List[Dict[str, Any]]:
        """
        Fetch tabular draw history from 500.com.
        Endpoint: http://datachart.500.com/ssq/history/newinc/history.php?start=03001&end=26999
        Returns a chronologically sorted (ascending) list of draw record dictionaries.
        """
        url = f"{CRAWLER_500_BASE_URL}?start={start_issue}&end={end_issue}"
        last_exception = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info("Fetching 500.com data (attempt %d/%d): %s", attempt, MAX_RETRIES, url)
                resp = requests.get(url, headers=DEFAULT_HEADERS_500, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    resp.encoding = "utf-8"
                    return self._parse_500_html(resp.text)
                else:
                    logger.warning("500.com returned HTTP %d, retrying...", resp.status_code)
            except Exception as exc:
                last_exception = exc
                logger.warning("500.com request failed on attempt %d: %s", attempt, exc)
            time.sleep(attempt * 1.0)

        raise RuntimeError(f"Failed to fetch 500.com data after {MAX_RETRIES} attempts: {last_exception}")

    def _parse_500_html(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Parse raw HTML table from 500.com into structured draw records.
        """
        html = etree.HTML(html_content)
        trs = html.xpath("//tr[contains(@class, 't_tr1')]")
        logger.info("Found %d raw table rows from 500.com HTML", len(trs))

        parsed_records: List[Dict[str, Any]] = []

        for tr in trs:
            tds = [td.xpath("string(.)").strip() for td in tr.xpath("./td")]
            if len(tds) < 16:
                continue

            raw_issue = tds[0]
            # Normalize issue: if 5 digits (e.g. '03001' or '26122'), prefix '20'
            issue_no = f"20{raw_issue}" if len(raw_issue) == 5 else raw_issue

            try:
                reds = sorted([int(x) for x in tds[1:7]])
                blue = int(tds[7])
            except (ValueError, IndexError):
                continue

            # Basic validation
            if len(reds) != 6 or not all(1 <= r <= 33 for r in reds):
                continue
            if len(set(reds)) != 6:
                continue
            if not (1 <= blue <= 16):
                continue

            try:
                draw_date = datetime.strptime(tds[15], "%Y-%m-%d").date()
            except (ValueError, IndexError):
                continue

            weekday = draw_date.isoweekday()  # 1=Monday ... 7=Sunday
            red_seq_str = ",".join(f"{r:02d}" for r in reds)

            pool_amount = _clean_int(tds[9])
            first_prize_num = _clean_int(tds[10])
            first_prize_amount = _clean_int(tds[11])
            second_prize_num = _clean_int(tds[12])
            second_prize_amount = _clean_int(tds[13])
            sales_amount = _clean_int(tds[14])

            record = {
                "issue_no": issue_no,
                "draw_date": draw_date,
                "weekday": weekday,
                "red_1": reds[0],
                "red_2": reds[1],
                "red_3": reds[2],
                "red_4": reds[3],
                "red_5": reds[4],
                "red_6": reds[5],
                "blue_1": blue,
                "red_seq_str": red_seq_str,
                "sales_amount": sales_amount,
                "pool_amount": pool_amount,
                "first_prize_num": first_prize_num,
                "first_prize_amount": first_prize_amount,
                "second_prize_num": second_prize_num,
                "second_prize_amount": second_prize_amount,
            }
            parsed_records.append(record)

        # Sort chronologically ascending (2003001 -> latest)
        parsed_records.sort(key=lambda x: x["issue_no"])
        return parsed_records

    def fetch_cwl_data(self, issue_count: int = 30) -> List[Dict[str, Any]]:
        """
        Fetch latest draw notices from official China Welfare Lottery JSON API.
        Endpoint: http://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?name=ssq&issueCount=30
        Returns chronologically sorted list of draw records.
        """
        url = f"{CWL_API_BASE_URL}?name=ssq&issueCount={issue_count}"
        last_exception = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info("Fetching CWL JSON API (attempt %d/%d): %s", attempt, MAX_RETRIES, url)
                resp = requests.get(url, headers=DEFAULT_HEADERS_CWL, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_items = data.get("result", [])
                    if raw_items:
                        return self._parse_cwl_json(raw_items)
                logger.warning("CWL API returned HTTP %d or empty result, retrying...", resp.status_code)
            except Exception as exc:
                last_exception = exc
                logger.warning("CWL API request failed on attempt %d: %s", attempt, exc)
            time.sleep(attempt * 1.0)

        raise RuntimeError(f"Failed to fetch CWL API data after {MAX_RETRIES} attempts: {last_exception}")

    def _parse_cwl_json(self, raw_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse raw CWL JSON draw result items into standardized draw dictionaries.
        """
        parsed_records: List[Dict[str, Any]] = []

        for item in raw_items:
            code = str(item.get("code", "")).strip()
            if not code:
                continue

            # Normalize issue: if 5 digits, prefix '20'
            issue_no = f"20{code}" if len(code) == 5 else code

            date_str = str(item.get("date", "")).strip()[:10]
            try:
                draw_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            weekday = draw_date.isoweekday()

            red_raw = str(item.get("red", "")).strip()
            try:
                reds = sorted([int(x) for x in red_raw.split(",") if x.strip()])
                blue = int(item.get("blue", 0))
            except ValueError:
                continue

            if len(reds) != 6 or not all(1 <= r <= 33 for r in reds):
                continue
            if len(set(reds)) != 6 or not (1 <= blue <= 16):
                continue

            red_seq_str = ",".join(f"{r:02d}" for r in reds)
            sales_amount = _clean_int(item.get("sales", 0))
            pool_amount = _clean_int(item.get("poolmoney", 0))

            first_num = 0
            first_amt = 0
            second_num = 0
            second_amt = 0

            prizegrades = item.get("prizegrades", [])
            if isinstance(prizegrades, list):
                if len(prizegrades) >= 1:
                    first_num = _clean_int(prizegrades[0].get("typenum", 0))
                    first_amt = _clean_int(prizegrades[0].get("typemoney", 0))
                if len(prizegrades) >= 2:
                    second_num = _clean_int(prizegrades[1].get("typenum", 0))
                    second_amt = _clean_int(prizegrades[1].get("typemoney", 0))

            record = {
                "issue_no": issue_no,
                "draw_date": draw_date,
                "weekday": weekday,
                "red_1": reds[0],
                "red_2": reds[1],
                "red_3": reds[2],
                "red_4": reds[3],
                "red_5": reds[4],
                "red_6": reds[5],
                "blue_1": blue,
                "red_seq_str": red_seq_str,
                "sales_amount": sales_amount,
                "pool_amount": pool_amount,
                "first_prize_num": first_num,
                "first_prize_amount": first_amt,
                "second_prize_num": second_num,
                "second_prize_amount": second_amt,
            }
            parsed_records.append(record)

        parsed_records.sort(key=lambda x: x["issue_no"])
        return parsed_records

    def sync_all(self, force: bool = False) -> int:
        """
        Download full history from 500.com and populate SQLite database.
        Returns count of inserted draws.
        Idempotent: does not duplicate records if already present.
        If force=True, overwrites existing records with fresh scraped data.
        """
        init_db()
        records = self.fetch_500_data()
        logger.info("Scraped %d records from 500.com", len(records))

        session = self._get_session()
        owns_session = self._external_session is None

        inserted_count = 0
        try:
            # Load all existing issue numbers
            existing_issues = set(session.scalars(select(DrawHistory.issue_no)).all())

            to_insert: List[DrawHistory] = []
            for rec in records:
                issue = rec["issue_no"]
                if issue in existing_issues:
                    if force:
                        # Update existing row
                        existing_row = session.scalar(
                            select(DrawHistory).where(DrawHistory.issue_no == issue)
                        )
                        if existing_row:
                            for key, val in rec.items():
                                setattr(existing_row, key, val)
                            inserted_count += 1
                else:
                    to_insert.append(DrawHistory(**rec))
                    inserted_count += 1

            if to_insert:
                session.add_all(to_insert)

            session.commit()
            logger.info("sync_all completed. Processed/inserted %d records", inserted_count)
            return inserted_count
        except Exception as exc:
            session.rollback()
            logger.error("sync_all failed: %s", exc)
            raise
        finally:
            if owns_session:
                session.close()

    def sync_latest(self) -> int:
        """
        Fetch latest issues from CWL JSON API with 500.com fallback.
        Returns count of new draws added to the database.
        Idempotent and safe to run anytime.
        """
        init_db()
        session = self._get_session()
        owns_session = self._external_session is None

        try:
            max_issue = session.scalar(select(func.max(DrawHistory.issue_no)))

            # If local database has no records at all, delegate to sync_all
            if not max_issue:
                logger.info("Local database is empty, performing full sync_all")
                if owns_session:
                    session.close()
                return self.sync_all(force=False)

            logger.info("Local database latest issue: %s", max_issue)

            # Attempt live incremental sync via official CWL API first
            records: List[Dict[str, Any]] = []
            try:
                records = self.fetch_cwl_data(issue_count=30)
                logger.info("Fetched %d issues via official CWL JSON API", len(records))
            except Exception as cwl_err:
                logger.warning("CWL API failed (%s), falling back to 500.com range query", cwl_err)
                # Fallback to 500.com for recent draws
                start_range = max_issue[-5:]
                records = self.fetch_500_data(start_issue=start_range)

            # Filter for issues strictly greater than current max_issue
            new_records = [r for r in records if r["issue_no"] > max_issue]

            if not new_records:
                logger.info("Database is already up to date at issue %s. 0 new draws added.", max_issue)
                return 0

            # Insert new draws
            to_insert = [DrawHistory(**rec) for rec in new_records]
            session.add_all(to_insert)
            session.commit()
            logger.info("sync_latest added %d new draw records", len(to_insert))
            return len(to_insert)
        except Exception as exc:
            session.rollback()
            logger.error("sync_latest failed: %s", exc)
            raise
        finally:
            if owns_session:
                session.close()

    def get_draw_by_issue(self, issue_no: str) -> Optional[DrawHistory]:
        """Fetch a single draw record by its issue number."""
        session = self._get_session()
        owns_session = self._external_session is None
        try:
            return session.scalar(select(DrawHistory).where(DrawHistory.issue_no == issue_no))
        finally:
            if owns_session:
                session.close()

    def get_total_draws_count(self) -> int:
        """Return total count of historical draws in database."""
        session = self._get_session()
        owns_session = self._external_session is None
        try:
            return session.scalar(select(func.count(DrawHistory.id))) or 0
        finally:
            if owns_session:
                session.close()
