# Project: SSQ-Quant-System (Discrete Sequence Quantitative Analysis & Prediction Platform)

## Architecture

SSQ-Quant-System is a discrete sequence quantitative analysis and prediction platform for Shuangseqiu lottery data, designed with strict separation of concerns, zero lookahead bias in backtesting, robust data integrity, and negative-expectation risk management.

```
+-----------------------------------------------------------------------------------+
|                                  User / CLI / API                                 |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                             FastAPI & CLI Controller Layer                        |
|   - backend.app.cli (sync, compute-features, predict, backtest, verify, report)   |
|   - backend.app.api (history, features, predict, backtest, archive)               |
+-----------------------------------------------------------------------------------+
         |                                |                               |
         v                                v                               v
+------------------+            +-------------------+           +-------------------+
|  Crawler Engine  |            |  Feature Engine   |           | Prediction Engine |
|  (500.com bulk   |            |  - AC value (|D|-5|           |  - Blue 3-Model   |
|   & CWL API inc) |            |  - Sum, Span, Odd |           |    Ensemble       |
|  - Idempotent    |            |  - Prime, Zones   |           |  - Concentrated   |
+------------------+            |  - Omission Snap  |           |    Break-Even     |
         |                      |  - Cold/Warm/Hot  |           |  - Dan-Tuo Wheel  |
         |                      +-------------------+           |  - Guardrails     |
         |                                |                     +-------------------+
         v                                v                               |
+-------------------------------------------------------------------------+         |
|                          Storage Layer (SQLite WAL)                     |         |
|   - ssq_draw_history       - ssq_prediction_batches                     |<--------+
|   - ssq_feature_metrics    - ssq_prediction_items                       |
+-------------------------------------------------------------------------+
                                          ^
                                          |
                               +---------------------+
                               |   Backtest Engine   |
                               |   - Chronological   |
                               |     zero-lookahead  |
                               |   - Levels 1-6 audit|
                               |   - Comparative ROI |
                               +---------------------+
```

## Feature Inventory

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | SQLite Normalized Database Setup | 4 core tables (`ssq_draw_history`, `ssq_feature_metrics`, `ssq_prediction_batches`, `ssq_prediction_items`) with constraints, indexes, and WAL mode | M1 | ORIGINAL_REQUEST §R1, ai.md §3 |
| 2 | Full Historical Data Crawler | Automated ingestion of all 3,519+ authentic draws (2003001 to present) via 500.com bulk endpoint | M1 | ORIGINAL_REQUEST §R1, survey |
| 3 | Idempotent Incremental Sync | Querying latest draws via official CWL JSON API with 500.com fallback, safe to run anytime | M1 | ORIGINAL_REQUEST §R1, survey |
| 4 | Core Red Statistical Features | Computation of Red ball sum, span, AC value ($|D| - 5$), odd/even count, prime count (11 primes) | M2 | ORIGINAL_REQUEST §R2, ai.md §5.1 |
| 5 | Structural Distribution Features | 3-Zone distribution (01-11, 12-22, 23-33), consecutive number clustering, repeat from prior draw | M2 | ORIGINAL_REQUEST §R2, ai.md §3.2 |
| 6 | Full Omission & Cold/Hot Tables | Dynamic omission matrices for 33 reds & 16 blues, JSON snapshot per draw, Cold/Warm/Hot classification | M2 | ORIGINAL_REQUEST §R2, ai.md §5.1 |
| 7 | Multi-Model Blue Scoring Engine | Hazard omission recovery rate, 1st & 2nd-order Markov transition matrices, and Frequency/MACD momentum | M3 | ORIGINAL_REQUEST §R3, survey |
| 8 | Confidence-Weighted Blue Break-Even | Dynamic blue allocation (3-2, 2-2-1) guaranteeing $\ge 10$ RMB payoff on Top blue hit vs Dispersed baseline | M3 | ORIGINAL_REQUEST §R3, survey |
| 9 | Red Combinatorial Wheeling Coverage | Candidate pool selection + 2-Core/8-Satellite Dan-Tuo wheeling maximizing multi-line prize clustering | M3 | ORIGINAL_REQUEST §R3, survey |
| 10 | Red Statistical Guardrails Filter | Pruning irrational combinations using AC $\ge 6$, Red sum in 80% CI [75, 135], Odd-Even balance, Consecutive $\le 2$ | M3 | ORIGINAL_REQUEST §R3, survey |
| 11 | Prediction Persistence Layer | Saving 5-line combinations into `ssq_prediction_batches` and `ssq_prediction_items` with rationale and parameters | M3 | ORIGINAL_REQUEST §R3, ai.md §3.3 |
| 12 | Official Prize Verification Engine | Auditing prediction tickets against draw results according to official rules (Levels 1 to 6) and floating prize amounts | M4 | ORIGINAL_REQUEST §R4, ai.md §5.2 |
| 13 | Historical Backtest Harness | Chronological sliding window backtesting over past $N \in \{50, 100, 300\}$ issues without lookahead bias | M4 | ORIGINAL_REQUEST §R4, survey |
| 14 | Comparative Strategy Evaluation | Empirical backtest report contrasting Concentrated High-Confidence Blue Strategy vs Dispersed Strategy (ROI, Break-Even %, Drawdown) | M4 | ORIGINAL_REQUEST §R4, survey |
| 15 | Environment & Setup Guide | `ENVIRONMENT_SETUP.md` covering direct `D:\Miniconda3` execution and fresh virtualenv setup with `requirements.txt` | M5 | ORIGINAL_REQUEST §R5, survey |
| 16 | Modular Documentation in docs/ | Technical documentation covering Architecture, Data Schema, Feature Engineering, Prediction Strategies, and Backtesting | M5 | ORIGINAL_REQUEST §R5 |
| 17 | Git Conventional Commits | Enforcing Conventional Commits across git history for all milestones | M5 | ORIGINAL_REQUEST §R5 |
| 18 | E2E Test Suite (Tiers 1-4) | Comprehensive opaque-box test suite verifying all features via CLI and API | E2E Track | ORIGINAL_REQUEST §Acceptance Criteria |
| 19 | Adversarial Coverage Hardening (Tier 5) | White-box stress testing, corner cases, data corruption resilience, and adversarial challenger verification | Final M | Orchestrator Guidelines |

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Testing Suite Track | Opaque-box test harness, runner, and Tier 1-4 test cases; published `TEST_READY.md` (161 tests) | none | DONE |
| M1 | Historical Data Layer & Synchronization Engine | R1: SQLite schema, 500.com bulk ingestion (3519 draws), CWL incremental sync, CLI sync command | none | DONE |
| M2 | Multi-Dimensional Feature Engineering Engine | R2: AC value, sum, span, odd/even, primes, zones, omissions, cold/warm/hot tables, snapshot JSON | M1 | IN_PROGRESS |
| M3 | 5-Line Strategy Prediction & Break-Even Dual-Engine | R3: Blue 3-model scoring ensemble, confidence-weighted break-even allocation (3-2, 2-2-1), Dan-Tuo wheeling, statistical guardrails, prediction persistence | M1, M2 | PLANNED |
| M4 | Backtest & Prize Verification Engine | R4: Levels 1-6 prize auditor, zero-lookahead backtest harness (50, 100, 300 issues), comparative strategy evaluation | M1, M2, M3 | PLANNED |
| M5 | Engineering Standards, Documentation & Git Commits | R5: `ENVIRONMENT_SETUP.md`, `requirements.txt`, modular docs in `docs/`, Conventional Commits audit | M4 | PLANNED |
| Final | Full E2E Test Pass & Adversarial Hardening | Phase 1: 100% pass of E2E test suite (Tiers 1-4); Phase 2: Adversarial coverage hardening (Tier 5) | E2E, M1-M5 | PLANNED |

## Interface Contracts

### 1. Database Schema (`data/ssq_quant.db`)
- `ssq_draw_history`:
  - `issue_no` VARCHAR(20) PRIMARY KEY (e.g. '2026122')
  - `draw_date` DATE NOT NULL
  - `weekday` INT NOT NULL (1-7)
  - `red_1` .. `red_6` INT NOT NULL (1-33, strictly sorted $r_1 < r_2 < \dots < r_6$)
  - `blue_1` INT NOT NULL (1-16)
  - `red_seq_str` VARCHAR(30) NOT NULL ('01,02,04,17,19,30')
  - `sales_amount` BIGINT DEFAULT 0
  - `pool_amount` BIGINT DEFAULT 0
  - `first_prize_num` INT DEFAULT 0, `first_prize_amount` BIGINT DEFAULT 0
  - `second_prize_num` INT DEFAULT 0, `second_prize_amount` BIGINT DEFAULT 0
  - `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP

- `ssq_feature_metrics`:
  - `issue_no` VARCHAR(20) PRIMARY KEY REFERENCES ssq_draw_history(issue_no) ON DELETE CASCADE
  - `sum_red` INT NOT NULL, `span_red` INT NOT NULL, `ac_value` INT NOT NULL
  - `odd_count` INT NOT NULL, `prime_count` INT NOT NULL
  - `zone1_count` INT NOT NULL, `zone2_count` INT NOT NULL, `zone3_count` INT NOT NULL
  - `consecutive_groups` INT DEFAULT 0, `repeat_prev_red` INT DEFAULT 0
  - `missing_sum_red` INT DEFAULT 0, `missing_blue` INT DEFAULT 0
  - `missing_snapshot_json` TEXT NOT NULL (JSON: `{"red": {"1": m1, ..., "33": m33}, "blue": {"1": b1, ..., "16": b16}}`)

- `ssq_prediction_batches`:
  - `id` INTEGER PRIMARY KEY AUTOINCREMENT
  - `target_issue` VARCHAR(20) NOT NULL
  - `strategy_type` VARCHAR(50) NOT NULL ('CONCENTRATED_BREAK_EVEN', 'DISPERSED_BASELINE', 'STAT_FILTER', 'ML_PROB')
  - `model_name` VARCHAR(50)
  - `filter_params_json` TEXT
  - `ai_reasoning_md` TEXT
  - `total_notes` INT DEFAULT 5
  - `verify_status` VARCHAR(20) DEFAULT 'PENDING' ('PENDING', 'VERIFIED')
  - `best_prize_level` INT DEFAULT 0
  - `virtual_cost` INT DEFAULT 10
  - `virtual_reward` BIGINT DEFAULT 0
  - `post_reflection_md` TEXT
  - `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP
  - `verified_at` DATETIME

- `ssq_prediction_items`:
  - `id` INTEGER PRIMARY KEY AUTOINCREMENT
  - `batch_id` INTEGER NOT NULL REFERENCES ssq_prediction_batches(id) ON DELETE CASCADE
  - `target_issue` VARCHAR(20) NOT NULL
  - `red_1` .. `red_6` INT NOT NULL
  - `blue_1` INT NOT NULL
  - `confidence_score` FLOAT DEFAULT 0.0
  - `is_verified` BOOLEAN DEFAULT 0
  - `hit_red_count` INT DEFAULT 0, `hit_red_numbers` VARCHAR(30) DEFAULT ''
  - `hit_blue` BOOLEAN DEFAULT 0
  - `prize_level` INT DEFAULT 0, `prize_amount` BIGINT DEFAULT 0

### 2. Python Service Interfaces
- `CrawlerService`:
  - `sync_all(force: bool = False) -> int`: downloads full history from 500.com and populates SQLite. Returns count of inserted draws.
  - `sync_latest() -> int`: fetches latest issues from CWL JSON API with 500.com fallback. Returns count of new draws added.
- `FeatureEngine`:
  - `compute_metrics_for_draw(draw: DrawHistory, prev_draw: Optional[DrawHistory], prior_snapshot: Optional[dict]) -> FeatureMetrics`
  - `compute_all_missing_features() -> int`
- `PredictionService`:
  - `generate_5_line_prediction(target_issue: str, strategy: str = "CONCENTRATED_BREAK_EVEN") -> PredictionBatch`
- `VerificationService`:
  - `verify_ticket(pred_reds: List[int], pred_blue: int, actual_reds: List[int], actual_blue: int, first_amount: int, second_amount: int) -> Tuple[int, int, List[int], bool]`
  - `verify_batch(batch_id: int) -> PredictionBatch`
- `BacktestEngine`:
  - `run_backtest(n_issues: int, strategy: str) -> BacktestResult`
  - `compare_strategies(n_issues: int) -> StrategyComparisonReport`

### 3. CLI Command Specifications
- `python -m backend.app.cli sync [--force]` -> Full or incremental synchronization
- `python -m backend.app.cli compute-features` -> Compute all feature metrics and omission snapshots
- `python -m backend.app.cli predict --issue <issue_no> [--strategy CONCENTRATED_BREAK_EVEN|DISPERSED_BASELINE]` -> Generate and store 5-line prediction
- `python -m backend.app.cli verify --issue <issue_no>` -> Audit predictions against actual draw
- `python -m backend.app.cli backtest --issues <50|100|300> [--compare]` -> Run point-in-time backtest and output comparative report

## Code Layout

```
d:\sy\lottery\
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI entry point
│   │   ├── cli.py                      # CLI commands entry point
│   │   ├── config.py                   # Paths, DB URL, constants
│   │   ├── database.py                 # SQLite connection, WAL mode, session maker
│   │   ├── models.py                   # SQLAlchemy 2.0 ORM models (4 core tables)
│   │   ├── schemas.py                  # Pydantic schemas for requests/responses
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── history.py              # Draw history and sync endpoints
│   │   │   ├── features.py             # Feature metrics, omission and cold/hot endpoints
│   │   │   ├── predict.py              # Prediction generation and batch archive endpoints
│   │   │   └── backtest.py             # Backtest and strategy comparison endpoints
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── crawler.py              # 500.com bulk + CWL incremental crawler
│   │       ├── feature_engine.py       # AC value, sum, span, omissions, cold/hot engine
│   │       ├── quant_models.py         # Blue 3-model scoring ensemble (Hazard, Markov, Momentum)
│   │       ├── wheeling_engine.py      # Dan-Tuo combinatorial wheel & statistical guardrails
│   │       ├── predictor.py            # 5-line break-even allocation & batch persistence
│   │       ├── verifier.py             # Official Level 1-6 prize auditing engine
│   │       └── backtest_runner.py      # Point-in-time sliding-window backtest simulator
│   └── requirements.txt
├── data/
│   └── ssq_quant.db                    # SQLite database file (WAL mode)
├── docs/
│   ├── 01_architecture.md              # System architecture & data flow
│   ├── 02_data_schema.md               # Complete schema DDL & indexes
│   ├── 03_feature_engineering.md       # AC value, omission, cold/hot formulas
│   ├── 04_prediction_strategies.md     # Blue break-even proof & Dan-Tuo wheeling
│   └── 05_backtest_reports.md          # Backtest methodology & comparative results
├── tests/
│   ├── __init__.py
│   ├── e2e/
│   │   ├── test_e2e_tier1_features.py  # Tier 1: Feature Coverage (>=5 per feature)
│   │   ├── test_e2e_tier2_boundaries.py# Tier 2: Boundary & Corner Cases (>=5 per feature)
│   │   ├── test_e2e_tier3_combinations.py # Tier 3: Cross-Feature Interactions
│   │   └── test_e2e_tier4_workloads.py # Tier 4: Real-World Workload Scenarios
│   └── unit/
│       ├── test_crawler.py
│       ├── test_features.py
│       ├── test_quant_models.py
│       ├── test_wheeling.py
│       ├── test_verifier.py
│       └── test_backtest.py
├── ENVIRONMENT_SETUP.md                # Python/Miniconda setup documentation
├── PROJECT.md                          # Master project specification
├── TEST_INFRA.md                       # E2E Test Suite design document
└── TEST_READY.md                       # Signal file published when E2E suite is ready
```
