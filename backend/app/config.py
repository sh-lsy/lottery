"""
Configuration module for SSQ-Quant-System.
Defines system paths, database connection URLs, crawler endpoints, and HTTP headers.
"""

from pathlib import Path
import os

# Base Directories
# File is located at: backend/app/config.py -> parent.parent.parent is root project dir
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
BACKEND_DIR = BASE_DIR / "backend"

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Database Configuration
DB_NAME = "ssq_quant.db"
DB_PATH = DATA_DIR / DB_NAME
# Cross-platform SQLite URL with forward slashes
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH.as_posix()}")

# Crawler Endpoints & Configuration
CRAWLER_500_BASE_URL = "http://datachart.500.com/ssq/history/newinc/history.php"
CWL_API_BASE_URL = "http://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"

DEFAULT_HEADERS_500 = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

DEFAULT_HEADERS_CWL = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "http://www.cwl.gov.cn/ygfw/cwl_admin/kjxx/findDrawNotice",
    "Accept": "application/json, text/plain, */*",
}

REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
DEFAULT_START_ISSUE_500 = "03001"
DEFAULT_END_ISSUE_500 = "26999"

# SSQ Rules & Constants
TOTAL_RED_BALLS = 33
TOTAL_BLUE_BALLS = 16
REQUIRED_RED_COUNT = 6
REQUIRED_BLUE_COUNT = 1
MIN_RED_VAL = 1
MAX_RED_VAL = 33
MIN_BLUE_VAL = 1
MAX_BLUE_VAL = 16
PRIME_RED_SET = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}
