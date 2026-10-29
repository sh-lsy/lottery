# Project: SSQ-Quant-System (Discrete Sequence Quantitative Analysis & Prediction Platform)

## Architecture

SSQ-Quant-System is a discrete sequence quantitative analysis and prediction platform for Shuangseqiu lottery data, designed with strict separation of concerns, zero lookahead bias in backtesting, robust data integrity, negative-expectation risk management, and a high-performance Vue 3 dark quant terminal.

```
+-----------------------------------------------------------------------------------+
|               Vue 3 + TypeScript + Element Plus + Tailwind + ECharts              |
|                             Dark Quant Terminal UI                                |
|  - View 1: Panoramic History & Trend Dashboard (/history)                         |
|  - View 2: AI Strategy Prediction Generation Lab (/predict)                       |
|  - View 3: Prediction Archive & Verification Review Center (/archive)              |
|  - View 4: Historical Collision Sandbox Tool (/sandbox)                           |
+-----------------------------------------------------------------------------------+
                                          | HTTP / REST (Vite Proxy /api)
                                          v
+-----------------------------------------------------------------------------------+
|                             FastAPI & CLI Service Layer                           |
|   - backend.app.main (FastAPI app, CORS, lifespan DB init, CollisionCache prewarm)|
|   - backend.app.api.history (draws pagination, features, omissions, sync)         |
|   - backend.app.api.predict (offline 5-line quant prediction, persistence)        |
|   - backend.app.api.backtest (sandbox collision, prize verification, backtest)   |
|   - backend.app.api.adaptive (evolution status, trajectory, trigger/reset)        |
|   - backend.app.cli (sync, compute-features, predict, backtest, verify)           |
+-----------------------------------------------------------------------------------+
          |                                |                               |
          v                                v                               v
+------------------+            +-------------------+           +-------------------+
+  Crawler Engine  |            |  Feature Engine   |           | Prediction Engine |
|  (500.com bulk   |            |  - AC value (|D|-5|           |  - Hazard + Markov|
|   & CWL API inc) |            |  - Sum, Span, Odd |           |    + Momentum     |
|  - Idempotent    |            |  - Prime, Zones   |           |  - Concentrated   |
+------------------+            |  - Omission Snap  |           |    Break-Even     |
          |                     |  - Cold/Warm/Hot  |           |  - Dan-Tuo Wheel  |
          |                     +-------------------+           |  - Guardrails     |
          |                               |                     +-------------------+
          |                               |                                |
          v                               v                                v
+-------------------------------------------------------------------------+         |
|                          Storage Layer (SQLite WAL)                     |         v
|   - ssq_draw_history             - ssq_prediction_batches               |  +-------------------+
|   - ssq_feature_metrics          - ssq_prediction_items                 |  | Adaptive Strategy |
|   - ssq_adaptive_state           - ssq_adaptive_history                 |  | & Reflection Loop |
+-------------------------------------------------------------------------+  | - Deficit trigger |
                                          ^                                  | - Weight shift    |
                                          |                                  | - Blue 3+2 / 5-diff|
                               +---------------------+                       | - Deviation log   |
                               |   Backtest Engine   |                       +-------------------+
                               |   - Chronological   |                                 |
                               |     zero-lookahead  |                                 |
                               |   - Levels 1-6 audit|                                 |
                               |   - CollisionCache  |<--------------------------------+
                               |     (Sub-10ms)      |
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
| 18 | E2E Test Suite (Tiers 1-4) | Comprehensive opaque-box test suite verifying all features via CLI and API (161 tests) | E2E Track | ORIGINAL_REQUEST §Acceptance Criteria |
| 19 | Adversarial Coverage Hardening (Tier 5) | White-box stress testing, corner cases, data corruption resilience, and adversarial challenger verification | Final M | Orchestrator Guidelines |
| 20 | FastAPI Application & CORS Setup | `backend/app/main.py` with lifespan DB init, CORS middleware, API v1 routing | M6 | ORIGINAL_REQUEST §R1 |
| 21 | Pydantic V2 Schemas | `backend/app/schemas.py` defining all requests, responses, pagination, trends, sandboxes | M6 | ORIGINAL_REQUEST §R1 |
| 22 | History & Trend API Router | `backend/app/api/history.py`: draws pagination, feature metrics, omission matrix heatmap, sync trigger | M6 | ORIGINAL_REQUEST §R1 |
| 23 | Prediction Generation API Router | `backend/app/api/predict.py`: pure local offline quant 5-line prediction, persistence, batch archive | M6 | ORIGINAL_REQUEST §R1 |
| 24 | Sandbox Collision & Verification API | `backend/app/api/backtest.py`: sub-10ms collision against 3519 draws via `CollisionCache`, verification, backtest | M6 | ORIGINAL_REQUEST §R1 |
| 25 | Adaptive Strategy State & Trajectory Models | `backend/app/models.py`: additive `AdaptiveState` (`ssq_adaptive_state`) and `AdaptiveHistory` (`ssq_adaptive_history`) | M6 | ORIGINAL_REQUEST §R2 |
| 26 | Adaptive Strategy Feedback Engine | `backend/app/services/adaptive_service.py`: streak trigger ($K_t \ge 3$), dynamic hot/cold weight shifts, blue 3+2 vs 5-diff mode switching, deviation metrics logging, saturation clamps | M6 | ORIGINAL_REQUEST §R2 |
| 27 | Adaptive Reflection API Router | `backend/app/api/adaptive.py`: adaptive status, trajectory events, manual trigger / reset | M6 | ORIGINAL_REQUEST §R2 |
| 28 | Backend API & Adaptive Automated Pytest Suite | `tests/api/` & `tests/unit/test_adaptive_service.py`: 66 new tests, 387 total repo tests 100% green | M7 | ORIGINAL_REQUEST §R4 |
| 29 | Frontend Scaffolding & Toolchain | `frontend/`: Vite 6 + Vue 3.5 + TypeScript + Element Plus (Dark) + Tailwind CSS + ECharts 5.6 | M8 | ORIGINAL_REQUEST §R3 |
| 30 | View 1: History & Trend Dashboard | Omission heatmap chart, key mathematical indicators distribution, paginated draw history table | M8 | ORIGINAL_REQUEST §R3 |
| 31 | View 2: AI Strategy Prediction Lab | Parameter configuration sliders, real-time simulation, candidate numbers generation, DB persistence | M8 | ORIGINAL_REQUEST §R3 |
| 32 | View 3: Archive & Verification Review Center | Prediction timeline, win rate / payout summary, adaptive evolution status, glowing Neon Red (`#ff4757`) and Electric Blue (`#00d2d3`) hit cards | M8 | ORIGINAL_REQUEST §R3 |
| 33 | View 4: Historical Collision Sandbox Tool | 6 red + 1 blue interactive picker, collision against 3500+ draws, highest prize level, quantile gauges | M8 | ORIGINAL_REQUEST §R3 |
| 34 | Frontend Typecheck & Build Gates | `vue-tsc --noEmit` and `npm run build` passing with zero errors | M8 | ORIGINAL_REQUEST §R4 |
| 35 | Full-Stack Integration, Docs & GitHub Sync | Modular documentation update in `docs/` & `README.md`, conventional commits, push to remote `main` branch | M9 | ORIGINAL_REQUEST §R5 |

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Testing Suite Track | Opaque-box test harness, runner, and Tier 1-4 test cases; published `TEST_READY.md` (161 tests) | none | DONE |
| M1 | Historical Data Layer & Synchronization Engine | R1: SQLite schema, 500.com bulk ingestion (3519 draws), CWL incremental sync, CLI sync command | none | DONE |
| M2 | Multi-Dimensional Feature Engineering Engine | R2: AC value, sum, span, odd/even, primes, zones, omissions, cold/warm/hot tables, snapshot JSON | M1 | DONE |
| M3 | 5-Line Strategy Prediction & Break-Even Dual-Engine | R3: Blue 3-model scoring ensemble, confidence-weighted break-even allocation (3-2, 2-2-1), Dan-Tuo wheeling, statistical guardrails, prediction persistence | M1, M2 | DONE |
| M4 | Backtest & Prize Verification Engine | R4: Levels 1-6 prize auditor, zero-lookahead backtest harness (50, 100, 300 issues), comparative strategy evaluation | M1, M2, M3 | DONE |
| M5 | Engineering Standards, Documentation & Git Commits | R5: `ENVIRONMENT_SETUP.md`, `requirements.txt`, modular docs in `docs/`, Conventional Commits audit | M4 | DONE |
| M6 | Backend RESTful API & Adaptive Quant Service Layer | R1 & R2: FastAPI app, schemas, 4 API routers, adaptive models & engine, CollisionCache | M1-M5 | DONE |
| M7 | Backend API & Adaptive Automated Pytest Suite | R4: Full test coverage in `tests/api/` & `tests/unit/test_adaptive_service.py`, 387 tests passing | M6 | DONE |
| M8 | Frontend Dark Quant Terminal Application | R3 & R4: Vue 3 + TS + Vite + Element Plus Dark + Tailwind + ECharts 4 core views, `vue-tsc` & `npm run build` | M6, M7 | DONE |
| M9 | Full-Stack Integration, Docs & GitHub Sync | R5: End-to-end integration verification, docs update, Git commit & push | M7, M8 | DONE |

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

- `ssq_adaptive_state`:
  - `id` INTEGER PRIMARY KEY AUTOINCREMENT
  - `consecutive_deficit_count` INT NOT NULL DEFAULT 0
  - `current_blue_mode` VARCHAR(30) NOT NULL DEFAULT 'CONCENTRATED'
  - `current_strategy_mode` VARCHAR(50) NOT NULL DEFAULT 'CONCENTRATED_BREAK_EVEN'
  - `loss_threshold` INT NOT NULL DEFAULT 3
  - `hot_momentum_weight` FLOAT NOT NULL DEFAULT 0.25
  - `cold_reversion_weight` FLOAT NOT NULL DEFAULT 0.40
  - `markov_weight` FLOAT NOT NULL DEFAULT 0.35
  - `temperature_tau` FLOAT NOT NULL DEFAULT 0.85
  - `sum_bias` FLOAT NOT NULL DEFAULT 0.0 (clamped to [-30.0, +30.0])
  - `odd_bias` FLOAT NOT NULL DEFAULT 0.0
  - `ac_min_override` INT NOT NULL DEFAULT 6
  - `sum_range_min` INT NOT NULL DEFAULT 75 (clamped to [65, 80])
  - `sum_range_max` INT NOT NULL DEFAULT 135 (clamped to [115, 145])
  - `last_trigger_issue` VARCHAR(20)
  - `last_trigger_reason` TEXT
  - `evolution_version` INT NOT NULL DEFAULT 1
  - `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP

- `ssq_adaptive_history`:
  - `id` INTEGER PRIMARY KEY AUTOINCREMENT
  - `trigger_issue` VARCHAR(20) NOT NULL
  - `trigger_reason` VARCHAR(100) NOT NULL
  - `streak_length` INT NOT NULL DEFAULT 0
  - `pre_state_json` TEXT NOT NULL DEFAULT '{}'
  - `post_state_json` TEXT NOT NULL DEFAULT '{}'
  - `metrics_deviation_json` TEXT NOT NULL DEFAULT '{}'
  - `reflection_notes` TEXT
  - `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP

### 2. FastAPI Endpoints
- `GET /api/v1/history/draws` -> Paginated historical draws (alias `/list`)
- `GET /api/v1/history/latest` -> Latest official draw record
- `GET /api/v1/history/metrics` -> Feature metrics sequence (`limit=100`)
- `GET /api/v1/history/metrics/{issue_no}` -> Draw metrics by issue
- `GET /api/v1/history/omissions` -> Red & Blue omission matrices & cold/warm/hot tables (`limit=30`, alias `/trends`)
- `GET /api/v1/history/distributions` -> Feature frequency histograms (`limit=100`)
- `POST /api/v1/history/sync` -> Incremental/full crawl sync, cache invalidation, auto-verify
- `POST /api/v1/predict/generate` -> 5-line local prediction with parameters & offline candidate pool (<100ms)
- `POST /api/v1/predict/save` -> Persist 5-note prediction batch & items
- `GET /api/v1/predict/batches` -> List prediction batches with status filter
- `GET /api/v1/predict/batches/{id}` -> Prediction batch details with item highlights
- `GET /api/v1/predict/dashboard` -> Aggregate win rate, ROI, payout statistics (alias `/summary`)
- `POST /api/v1/backtest/sandbox/collision` -> Sandbox collision for user ticket (sub-10ms via `CollisionCache`, alias `/sandbox`)
- `POST /api/v1/backtest/verify/{issue_no}` -> Audit prediction against actual draw & trigger adaptive feedback
- `POST /api/v1/backtest/run` -> Run point-in-time sliding-window backtest
- `POST /api/v1/backtest/compare` -> Comparative backtest between Concentrated and Dispersed strategies
- `GET /api/v1/adaptive/status` -> Current adaptive hyperparameters & state (alias `/state`)
- `GET /api/v1/adaptive/trajectory` -> Immutable adaptive history audit log
- `POST /api/v1/adaptive/trigger` -> Manual / threshold-based adaptive reflection trigger
- `POST /api/v1/adaptive/reset` -> Reset adaptive weights to canonical baseline (0.40, 0.35, 0.25)

### 3. CLI Command Specifications
- `python -m backend.app.cli sync [--force]` -> Full or incremental synchronization
- `python -m backend.app.cli compute-features` -> Compute all feature metrics and omission snapshots
- `python -m backend.app.cli predict-issue [--issue <issue_no>] [--strategy break_even|dispersed]` -> Generate and store 5-line prediction
- `python -m backend.app.cli verify [--issue <issue_no>] [--batch-id <id>]` -> Audit predictions against actual draw
- `python -m backend.app.cli backtest [--issues <50|100|300>] [--compare]` -> Run point-in-time backtest and output comparative report

## Code Layout

```
d:\sy\lottery\
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI entry point & lifespan setup
│   │   ├── cli.py                      # CLI commands entry point
│   │   ├── config.py                   # Paths, DB URL, constants
│   │   ├── database.py                 # SQLite connection, WAL mode, session maker
│   │   ├── models.py                   # SQLAlchemy 2.0 ORM models (6 tables)
│   │   ├── schemas.py                  # Pydantic v2 schemas for requests/responses
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── history.py              # Draw history, omissions & sync endpoints
│   │   │   ├── predict.py              # Prediction generation & batch archive endpoints
│   │   │   ├── backtest.py             # Sandbox collision, verification & backtest
│   │   │   └── adaptive.py             # Adaptive strategy state & trajectory endpoints
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── crawler.py              # 500.com bulk + CWL incremental crawler
│   │       ├── feature_engine.py       # AC value, sum, span, omissions, cold/hot engine
│   │       ├── quant_models.py         # Blue 3-model scoring ensemble (Hazard, Markov, Momentum)
│   │       ├── wheeling_engine.py      # Dan-Tuo combinatorial wheel & statistical guardrails
│   │       ├── predictor.py            # 5-line break-even allocation & batch persistence
│   │       ├── verifier.py             # Official Level 1-6 prize auditing engine
│   │       ├── backtest_runner.py      # Point-in-time sliding-window backtest simulator
│   │       ├── collision_cache.py      # Thread-safe in-memory cache for sub-10ms collision
│   │       └── adaptive_service.py     # Adaptive evolution loop & feedback engine
│   └── requirements.txt
├── data/
│   └── ssq_quant.db                    # SQLite database file (WAL mode)
├── docs/
│   ├── 01_database_schema.md           # Complete schema DDL & indexes
│   ├── 02_crawler_service.md           # Crawler architecture & sync protocols
│   ├── 03_feature_engineering.md       # AC value, omission, cold/hot formulas
│   ├── 04_git_commit_standard.md       # Conventional Commits guideline
│   ├── 04_prediction_strategy.md       # Blue break-even proof & Dan-Tuo wheeling
│   ├── 05_backtest_report.md           # Backtest methodology & comparative results
│   ├── 06_fastapi_restful_api.md       # OpenAPI specs & CollisionCache architecture
│   ├── 07_adaptive_strategy_loop.md    # Adaptive evolution math & feedback algorithms
│   └── 08_frontend_quant_terminal.md   # Vue 3 Dark Quant Terminal guide & styles
├── frontend/
│   ├── package.json
│   ├── vite.config.ts                  # Vite 6 config with /api proxy to :8000
│   ├── tsconfig.json
│   ├── tailwind.config.js              # Dark terminal color palette
│   ├── index.html
│   └── src/
│       ├── main.ts                     # Vue app initialization
│       ├── App.vue                     # Root layout shell
│       ├── style.css                   # Custom neon glow lottery ball styles
│       ├── router/                     # 4 core routes (/history, /predict, /archive, /sandbox)
│       ├── components/
│       │   ├── layout/                 # SidebarNav.vue, TopHeader.vue
│       │   └── charts/                 # OmissionHeatmap.vue, IndicatorChart.vue
│       └── views/
│           ├── HistoryView.vue         # View 1: History & Trend Dashboard
│           ├── PredictLabView.vue      # View 2: AI Strategy Prediction Lab
│           ├── ArchiveReviewView.vue   # View 3: Archive & Verification Review Center
│           └── SandboxView.vue         # View 4: Historical Collision Sandbox
├── tests/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── test_api_history.py         # History & sync endpoint tests (20 tests)
│   │   ├── test_api_predict.py         # Predict & archive endpoint tests (15 tests)
│   │   ├── test_api_backtest_sandbox.py# Sandbox collision & backtest tests (11 tests)
│   │   └── test_api_adaptive.py        # Adaptive state & trajectory tests (8 tests)
│   ├── unit/
│   │   ├── test_crawler.py
│   │   ├── test_features.py
│   │   ├── test_verifier.py
│   │   ├── test_backtest.py
│   │   ├── test_adaptive_service.py    # Adaptive feedback unit tests (12 tests)
│   │   ├── test_adversarial_m1.py
│   │   ├── test_adversarial_m2.py
│   │   └── test_challenger_m2.py
│   └── e2e/
│       ├── test_e2e_tier1_features.py
│       ├── test_e2e_tier2_boundaries.py
│       ├── test_e2e_tier3_combinations.py
│       └── test_e2e_tier4_workloads.py
├── ENVIRONMENT_SETUP.md                # Python/Miniconda setup documentation
├── PROJECT.md                          # Master project specification
├── TEST_INFRA.md                       # E2E Test Suite design document
└── TEST_READY.md                       # Signal file published when E2E suite is ready
```
