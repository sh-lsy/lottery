"""Shared pytest fixtures, database setups, and test helpers for SSQ-Quant-System E2E tests."""

import importlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

import pytest

# ---------------------------------------------------------------------------
# Authoritative SQLite DDL matching PROJECT.md and spec_survey_report.md
# ---------------------------------------------------------------------------
SCHEMA_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS ssq_draw_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_no VARCHAR(20) NOT NULL UNIQUE,
    draw_date DATE NOT NULL,
    weekday INT NOT NULL,
    red_1 INT NOT NULL,
    red_2 INT NOT NULL,
    red_3 INT NOT NULL,
    red_4 INT NOT NULL,
    red_5 INT NOT NULL,
    red_6 INT NOT NULL,
    blue_1 INT NOT NULL,
    red_seq_str VARCHAR(30) NOT NULL,
    sales_amount BIGINT DEFAULT 0,
    pool_amount BIGINT DEFAULT 0,
    first_prize_num INT DEFAULT 0,
    first_prize_amount BIGINT DEFAULT 0,
    second_prize_num INT DEFAULT 0,
    second_prize_amount BIGINT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_red_order CHECK (
        red_1 >= 1 AND red_1 < red_2 AND
        red_2 < red_3 AND red_3 < red_4 AND
        red_4 < red_5 AND red_5 < red_6 AND
        red_6 <= 33
    ),
    CONSTRAINT chk_blue_range CHECK (blue_1 >= 1 AND blue_1 <= 16),
    CONSTRAINT chk_weekday CHECK (weekday IN (1, 2, 3, 4, 5, 6, 7))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_draw_issue ON ssq_draw_history(issue_no);
CREATE INDEX IF NOT EXISTS idx_draw_issue_desc ON ssq_draw_history(issue_no DESC);
CREATE INDEX IF NOT EXISTS idx_draw_date_desc ON ssq_draw_history(draw_date DESC);

CREATE TABLE IF NOT EXISTS ssq_feature_metrics (
    issue_no VARCHAR(20) PRIMARY KEY,
    sum_red INT NOT NULL,
    span_red INT NOT NULL,
    ac_value INT NOT NULL,
    odd_count INT NOT NULL,
    prime_count INT NOT NULL,
    zone1_count INT NOT NULL,
    zone2_count INT NOT NULL,
    zone3_count INT NOT NULL,
    consecutive_groups INT DEFAULT 0,
    repeat_prev_red INT DEFAULT 0,
    missing_sum_red INT DEFAULT 0,
    missing_blue INT DEFAULT 0,
    missing_snapshot_json TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_zone_sum CHECK (zone1_count + zone2_count + zone3_count = 6),
    CONSTRAINT chk_odd_range CHECK (odd_count >= 0 AND odd_count <= 6),
    CONSTRAINT chk_prime_range CHECK (prime_count >= 0 AND prime_count <= 6),
    CONSTRAINT chk_ac_range CHECK (ac_value >= 0 AND ac_value <= 10),
    FOREIGN KEY (issue_no) REFERENCES ssq_draw_history(issue_no) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ssq_prediction_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_issue VARCHAR(20) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL,
    model_name VARCHAR(50) DEFAULT 'default',
    filter_params_json TEXT,
    ai_reasoning_md TEXT,
    total_notes INT NOT NULL DEFAULT 5,
    verify_status VARCHAR(20) DEFAULT 'PENDING',
    best_prize_level INT DEFAULT 0,
    virtual_cost INT DEFAULT 10,
    virtual_reward BIGINT DEFAULT 0,
    post_reflection_md TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    verified_at DATETIME,
    CONSTRAINT chk_verify_status CHECK (verify_status IN ('PENDING', 'VERIFIED'))
);

CREATE INDEX IF NOT EXISTS idx_pred_batch_issue ON ssq_prediction_batches(target_issue DESC);
CREATE INDEX IF NOT EXISTS idx_pred_batch_status ON ssq_prediction_batches(verify_status);

CREATE TABLE IF NOT EXISTS ssq_prediction_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL,
    target_issue VARCHAR(20) NOT NULL,
    note_index INT NOT NULL,
    red_1 INT NOT NULL,
    red_2 INT NOT NULL,
    red_3 INT NOT NULL,
    red_4 INT NOT NULL,
    red_5 INT NOT NULL,
    red_6 INT NOT NULL,
    blue_1 INT NOT NULL,
    confidence_score FLOAT DEFAULT 0.0,
    rationale VARCHAR(255),
    is_verified BOOLEAN DEFAULT 0,
    hit_red_count INT DEFAULT 0,
    hit_red_numbers VARCHAR(30) DEFAULT '',
    hit_blue BOOLEAN DEFAULT 0,
    prize_level INT DEFAULT 0,
    prize_amount BIGINT DEFAULT 0,
    FOREIGN KEY (batch_id) REFERENCES ssq_prediction_batches(id) ON DELETE CASCADE,
    CONSTRAINT chk_note_red_order CHECK (
        red_1 >= 1 AND red_1 < red_2 AND
        red_2 < red_3 AND red_3 < red_4 AND
        red_4 < red_5 AND red_5 < red_6 AND
        red_6 <= 33
    ),
    CONSTRAINT chk_note_blue CHECK (blue_1 >= 1 AND blue_1 <= 16),
    CONSTRAINT chk_note_index CHECK (note_index >= 1 AND note_index <= 5)
);

CREATE INDEX IF NOT EXISTS idx_pred_items_batch ON ssq_prediction_items(batch_id);
CREATE INDEX IF NOT EXISTS idx_pred_items_issue ON ssq_prediction_items(target_issue);
"""

# ---------------------------------------------------------------------------
# Canonical Sample Draws (25 draws for deterministic testing)
# ---------------------------------------------------------------------------
CANONICAL_SAMPLE_DRAWS: List[Dict[str, Any]] = [
    {
        "issue_no": "2003001",
        "draw_date": "2003-02-23",
        "weekday": 7,
        "red_1": 10, "red_2": 11, "red_3": 12, "red_4": 13, "red_5": 26, "red_6": 28,
        "blue_1": 11,
        "red_seq_str": "10,11,12,13,26,28",
        "sales_amount": 21743770, "pool_amount": 0,
        "first_prize_num": 0, "first_prize_amount": 0,
        "second_prize_num": 1, "second_prize_amount": 3465991
    },
    {
        "issue_no": "2026101",
        "draw_date": "2026-08-02",
        "weekday": 7,
        "red_1": 2, "red_2": 7, "red_3": 14, "red_4": 19, "red_5": 24, "red_6": 31,
        "blue_1": 8,
        "red_seq_str": "02,07,14,19,24,31",
        "sales_amount": 385420000, "pool_amount": 2410000000,
        "first_prize_num": 5, "first_prize_amount": 7500000,
        "second_prize_num": 88, "second_prize_amount": 165000
    },
    {
        "issue_no": "2026102",
        "draw_date": "2026-08-04",
        "weekday": 2,
        "red_1": 5, "red_2": 8, "red_3": 12, "red_4": 19, "red_5": 27, "red_6": 32,
        "blue_1": 3,
        "red_seq_str": "05,08,12,19,27,32",
        "sales_amount": 372100000, "pool_amount": 2450000000,
        "first_prize_num": 8, "first_prize_amount": 6200000,
        "second_prize_num": 120, "second_prize_amount": 110000
    },
    {
        "issue_no": "2026103",
        "draw_date": "2026-08-06",
        "weekday": 4,
        "red_1": 3, "red_2": 9, "red_3": 15, "red_4": 20, "red_5": 25, "red_6": 30,
        "blue_1": 12,
        "red_seq_str": "03,09,15,20,25,30",
        "sales_amount": 368900000, "pool_amount": 2490000000,
        "first_prize_num": 3, "first_prize_amount": 9100000,
        "second_prize_num": 75, "second_prize_amount": 195000
    },
    {
        "issue_no": "2026104",
        "draw_date": "2026-08-09",
        "weekday": 7,
        "red_1": 1, "red_2": 6, "red_3": 11, "red_4": 18, "red_5": 26, "red_6": 33,
        "blue_1": 16,
        "red_seq_str": "01,06,11,18,26,33",
        "sales_amount": 395100000, "pool_amount": 2520000000,
        "first_prize_num": 6, "first_prize_amount": 7100000,
        "second_prize_num": 105, "second_prize_amount": 140000
    },
    {
        "issue_no": "2026105",
        "draw_date": "2026-08-11",
        "weekday": 2,
        "red_1": 4, "red_2": 10, "red_3": 16, "red_4": 21, "red_5": 28, "red_6": 29,
        "blue_1": 5,
        "red_seq_str": "04,10,16,21,28,29",
        "sales_amount": 371200000, "pool_amount": 2560000000,
        "first_prize_num": 4, "first_prize_amount": 8300000,
        "second_prize_num": 90, "second_prize_amount": 155000
    },
    {
        "issue_no": "2026106",
        "draw_date": "2026-08-13",
        "weekday": 4,
        "red_1": 6, "red_2": 13, "red_3": 17, "red_4": 22, "red_5": 27, "red_6": 31,
        "blue_1": 9,
        "red_seq_str": "06,13,17,22,27,31",
        "sales_amount": 369800000, "pool_amount": 2590000000,
        "first_prize_num": 7, "first_prize_amount": 6800000,
        "second_prize_num": 115, "second_prize_amount": 125000
    },
    {
        "issue_no": "2026107",
        "draw_date": "2026-08-16",
        "weekday": 7,
        "red_1": 2, "red_2": 8, "red_3": 14, "red_4": 20, "red_5": 24, "red_6": 30,
        "blue_1": 1,
        "red_seq_str": "02,08,14,20,24,30",
        "sales_amount": 391400000, "pool_amount": 2610000000,
        "first_prize_num": 2, "first_prize_amount": 10000000,
        "second_prize_num": 60, "second_prize_amount": 240000
    },
    {
        "issue_no": "2026108",
        "draw_date": "2026-08-18",
        "weekday": 2,
        "red_1": 7, "red_2": 12, "red_3": 15, "red_4": 23, "red_5": 28, "red_6": 32,
        "blue_1": 4,
        "red_seq_str": "07,12,15,23,28,32",
        "sales_amount": 374500000, "pool_amount": 2640000000,
        "first_prize_num": 9, "first_prize_amount": 5900000,
        "second_prize_num": 130, "second_prize_amount": 105000
    },
    {
        "issue_no": "2026109",
        "draw_date": "2026-08-20",
        "weekday": 4,
        "red_1": 5, "red_2": 9, "red_3": 18, "red_4": 22, "red_5": 26, "red_6": 33,
        "blue_1": 8,
        "red_seq_str": "05,09,18,22,26,33",
        "sales_amount": 367200000, "pool_amount": 2670000000,
        "first_prize_num": 4, "first_prize_amount": 8400000,
        "second_prize_num": 85, "second_prize_amount": 160000
    },
    {
        "issue_no": "2026110",
        "draw_date": "2026-08-23",
        "weekday": 7,
        "red_1": 3, "red_2": 11, "red_3": 16, "red_4": 19, "red_5": 25, "red_6": 29,
        "blue_1": 15,
        "red_seq_str": "03,11,16,19,25,29",
        "sales_amount": 393800000, "pool_amount": 2700000000,
        "first_prize_num": 5, "first_prize_amount": 7600000,
        "second_prize_num": 98, "second_prize_amount": 145000
    },
    {
        "issue_no": "2026111",
        "draw_date": "2026-08-25",
        "weekday": 2,
        "red_1": 1, "red_2": 4, "red_3": 13, "red_4": 17, "red_5": 24, "red_6": 31,
        "blue_1": 10,
        "red_seq_str": "01,04,13,17,24,31",
        "sales_amount": 372900000, "pool_amount": 2720000000,
        "first_prize_num": 6, "first_prize_amount": 7200000,
        "second_prize_num": 110, "second_prize_amount": 130000
    },
    {
        "issue_no": "2026112",
        "draw_date": "2026-08-27",
        "weekday": 4,
        "red_1": 8, "red_2": 10, "red_3": 15, "red_4": 21, "red_5": 27, "red_6": 30,
        "blue_1": 6,
        "red_seq_str": "08,10,15,21,27,30",
        "sales_amount": 369100000, "pool_amount": 2750000000,
        "first_prize_num": 3, "first_prize_amount": 9200000,
        "second_prize_num": 80, "second_prize_amount": 175000
    },
    {
        "issue_no": "2026113",
        "draw_date": "2026-08-30",
        "weekday": 7,
        "red_1": 2, "red_2": 6, "red_3": 14, "red_4": 18, "red_5": 23, "red_6": 32,
        "blue_1": 14,
        "red_seq_str": "02,06,14,18,23,32",
        "sales_amount": 396500000, "pool_amount": 2780000000,
        "first_prize_num": 7, "first_prize_amount": 6900000,
        "second_prize_num": 125, "second_prize_amount": 115000
    },
    {
        "issue_no": "2026114",
        "draw_date": "2026-09-01",
        "weekday": 2,
        "red_1": 7, "red_2": 11, "red_3": 19, "red_4": 22, "red_5": 28, "red_6": 33,
        "blue_1": 2,
        "red_seq_str": "07,11,19,22,28,33",
        "sales_amount": 376000000, "pool_amount": 2810000000,
        "first_prize_num": 5, "first_prize_amount": 7700000,
        "second_prize_num": 95, "second_prize_amount": 150000
    },
    {
        "issue_no": "2026115",
        "draw_date": "2026-09-03",
        "weekday": 4,
        "red_1": 3, "red_2": 8, "red_3": 12, "red_4": 20, "red_5": 26, "red_6": 29,
        "blue_1": 7,
        "red_seq_str": "03,08,12,20,26,29",
        "sales_amount": 368400000, "pool_amount": 2830000000,
        "first_prize_num": 4, "first_prize_amount": 8500000,
        "second_prize_num": 88, "second_prize_amount": 165000
    },
    {
        "issue_no": "2026116",
        "draw_date": "2026-09-06",
        "weekday": 7,
        "red_1": 5, "red_2": 9, "red_3": 16, "red_4": 21, "red_5": 25, "red_6": 31,
        "blue_1": 13,
        "red_seq_str": "05,09,16,21,25,31",
        "sales_amount": 394200000, "pool_amount": 2860000000,
        "first_prize_num": 8, "first_prize_amount": 6300000,
        "second_prize_num": 135, "second_prize_amount": 100000
    },
    {
        "issue_no": "2026117",
        "draw_date": "2026-09-08",
        "weekday": 2,
        "red_1": 4, "red_2": 10, "red_3": 15, "red_4": 24, "red_5": 27, "red_6": 30,
        "blue_1": 11,
        "red_seq_str": "04,10,15,24,27,30",
        "sales_amount": 373800000, "pool_amount": 2880000000,
        "first_prize_num": 3, "first_prize_amount": 9300000,
        "second_prize_num": 72, "second_prize_amount": 185000
    },
    {
        "issue_no": "2026118",
        "draw_date": "2026-09-10",
        "weekday": 4,
        "red_1": 1, "red_2": 6, "red_3": 13, "red_4": 18, "red_5": 23, "red_6": 28,
        "blue_1": 8,
        "red_seq_str": "01,06,13,18,23,28",
        "sales_amount": 370500000, "pool_amount": 2900000000,
        "first_prize_num": 6, "first_prize_amount": 7300000,
        "second_prize_num": 102, "second_prize_amount": 138000
    },
    {
        "issue_no": "2026119",
        "draw_date": "2026-09-13",
        "weekday": 7,
        "red_1": 2, "red_2": 7, "red_3": 14, "red_4": 17, "red_5": 22, "red_6": 32,
        "blue_1": 4,
        "red_seq_str": "02,07,14,17,22,32",
        "sales_amount": 398100000, "pool_amount": 2920000000,
        "first_prize_num": 5, "first_prize_amount": 7800000,
        "second_prize_num": 92, "second_prize_amount": 152000
    },
    {
        "issue_no": "2026120",
        "draw_date": "2026-09-15",
        "weekday": 2,
        "red_1": 8, "red_2": 12, "red_3": 19, "red_4": 25, "red_5": 29, "red_6": 33,
        "blue_1": 3,
        "red_seq_str": "08,12,19,25,29,33",
        "sales_amount": 375200000, "pool_amount": 2940000000,
        "first_prize_num": 7, "first_prize_amount": 6700000,
        "second_prize_num": 118, "second_prize_amount": 122000
    },
    {
        "issue_no": "2026121",
        "draw_date": "2026-09-17",
        "weekday": 4,
        "red_1": 3, "red_2": 9, "red_3": 15, "red_4": 20, "red_5": 26, "red_6": 31,
        "blue_1": 12,
        "red_seq_str": "03,09,15,20,26,31",
        "sales_amount": 371900000, "pool_amount": 2960000000,
        "first_prize_num": 4, "first_prize_amount": 8600000,
        "second_prize_num": 82, "second_prize_amount": 170000
    },
    {
        "issue_no": "2026122",
        "draw_date": "2026-09-20",
        "weekday": 7,
        "red_1": 5, "red_2": 11, "red_3": 16, "red_4": 21, "red_5": 27, "red_6": 30,
        "blue_1": 8,
        "red_seq_str": "05,11,16,21,27,30",
        "sales_amount": 395900000, "pool_amount": 2980000000,
        "first_prize_num": 9, "first_prize_amount": 5800000,
        "second_prize_num": 140, "second_prize_amount": 95000
    },
    {
        "issue_no": "2026123",
        "draw_date": "2026-09-22",
        "weekday": 2,
        "red_1": 4, "red_2": 10, "red_3": 17, "red_4": 23, "red_5": 28, "red_6": 32,
        "blue_1": 16,
        "red_seq_str": "04,10,17,23,28,32",
        "sales_amount": 374000000, "pool_amount": 3000000000,
        "first_prize_num": 2, "first_prize_amount": 10000000,
        "second_prize_num": 65, "second_prize_amount": 230000
    },
    {
        "issue_no": "2026124",
        "draw_date": "2026-09-24",
        "weekday": 4,
        "red_1": 2, "red_2": 7, "red_3": 13, "red_4": 18, "red_5": 24, "red_6": 29,
        "blue_1": 5,
        "red_seq_str": "02,07,13,18,24,29",
        "sales_amount": 372500000, "pool_amount": 3020000000,
        "first_prize_num": 5, "first_prize_amount": 7900000,
        "second_prize_num": 96, "second_prize_amount": 148000
    }
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_db_path():
    """Provides a fresh temporary SQLite database path, cleaned up after test."""
    fd, path = tempfile.mkstemp(suffix="_test_ssq.db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


@pytest.fixture
def test_db(temp_db_path):
    """Initializes isolated SQLite database with full schema and WAL mode."""
    conn = sqlite3.connect(temp_db_path)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA_DDL)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def sample_draws() -> List[Dict[str, Any]]:
    """Returns canonical 25 sample draw records."""
    return CANONICAL_SAMPLE_DRAWS


@pytest.fixture
def populated_db(test_db, sample_draws):
    """Initializes and populates SQLite database with 25 canonical draws."""
    cursor = test_db.cursor()
    for d in sample_draws:
        cursor.execute(
            """
            INSERT OR REPLACE INTO ssq_draw_history (
                issue_no, draw_date, weekday,
                red_1, red_2, red_3, red_4, red_5, red_6,
                blue_1, red_seq_str, sales_amount, pool_amount,
                first_prize_num, first_prize_amount,
                second_prize_num, second_prize_amount
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                d["issue_no"], d["draw_date"], d["weekday"],
                d["red_1"], d["red_2"], d["red_3"], d["red_4"], d["red_5"], d["red_6"],
                d["blue_1"], d["red_seq_str"], d["sales_amount"], d["pool_amount"],
                d["first_prize_num"], d["first_prize_amount"],
                d["second_prize_num"], d["second_prize_amount"]
            )
        )
    test_db.commit()
    return test_db


@pytest.fixture
def mock_500_html():
    """Mock HTML response from 500.com bulk data endpoint."""
    return """
    <html>
    <body>
    <table class="chart">
        <tr class="t_tr1">
            <td class="td_title">2003001</td>
            <td class="chartBall01">10</td>
            <td class="chartBall01">11</td>
            <td class="chartBall01">12</td>
            <td class="chartBall01">13</td>
            <td class="chartBall01">26</td>
            <td class="chartBall01">28</td>
            <td class="chartBall02">11</td>
            <td>2003-02-23</td>
            <td>21743770</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
            <td>1</td>
            <td>3465991</td>
        </tr>
        <tr class="t_tr1">
            <td class="td_title">2003002</td>
            <td class="chartBall01">04</td>
            <td class="chartBall01">09</td>
            <td class="chartBall01">19</td>
            <td class="chartBall01">20</td>
            <td class="chartBall01">21</td>
            <td class="chartBall01">26</td>
            <td class="chartBall02">12</td>
            <td>2003-02-27</td>
            <td>22874120</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
            <td>2</td>
            <td>1827400</td>
        </tr>
    </table>
    </body>
    </html>
    """


@pytest.fixture
def mock_cwl_json():
    """Mock JSON response from official CWL API."""
    return json.dumps({
        "state": 0,
        "message": "success",
        "result": [
            {
                "code": "2026125",
                "date": "2026-09-27(日)",
                "red": "01,05,12,19,25,30",
                "blue": "08",
                "sales": "395200000",
                "poolmoney": "3050000000",
                "prizegrades": [
                    {"type": 1, "typenum": "6", "typemoney": "7500000"},
                    {"type": 2, "typenum": "110", "typemoney": "135000"}
                ]
            },
            {
                "code": "2026126",
                "date": "2026-09-29(二)",
                "red": "03,08,14,20,27,33",
                "blue": "11",
                "sales": "374800000",
                "poolmoney": "3080000000",
                "prizegrades": [
                    {"type": 1, "typenum": "4", "typemoney": "8800000"},
                    {"type": 2, "typenum": "95", "typemoney": "155000"}
                ]
            }
        ]
    })


# ---------------------------------------------------------------------------
# Dynamic Service & CLI Helpers for Progressive Testability
# ---------------------------------------------------------------------------

def safe_import_service(module_path: str, class_name: str) -> Optional[Any]:
    """Safely attempts to import a service class from the backend.
    Returns the class if found, otherwise None (allowing milestone isolation).
    """
    try:
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name, None)
    except (ImportError, AttributeError, ModuleNotFoundError):
        return None


def execute_cli_command(args: List[str], db_path: Optional[str] = None) -> subprocess.CompletedProcess:
    """Executes a backend CLI command in a subprocess with custom DB environment."""
    env = os.environ.copy()
    if db_path:
        env["SSQ_DB_PATH"] = db_path
        env["DATABASE_URL"] = f"sqlite:///{db_path}"

    cmd = [sys.executable, "-m", "backend.app.cli"] + args
    return subprocess.run(
        cmd,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        capture_output=True,
        text=True,
        env=env,
        timeout=60
    )
