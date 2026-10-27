# E2E Test Infra: SSQ-Quant-System

## Test Philosophy
- Opaque-box, requirement-driven. Derived strictly from `ORIGINAL_REQUEST.md` and user-facing CLI/API contracts.
- Independent of internal implementation details.
- Methodology: Category-Partition + Boundary Value Analysis + Pairwise Combinatorial + Real-World Workload Testing.
- Test runner: `pytest` executable from `D:\Miniconda3` or system environment.

## Feature Inventory Under Test

| # | Feature Code | Feature Name | Source | Tier 1 Target | Tier 2 Target | Tier 3 Target |
|---|--------------|--------------|--------|:-------------:|:-------------:|:-------------:|
| 1 | F01_DB_SCHEMA | SQLite 4-Table Normalized Schema & Constraints | R1, ai.md §3 | 5 | 5 | ✓ |
| 2 | F02_BULK_CRAWL | Full Historical Data Crawl (2003001 to latest) | R1 | 5 | 5 | ✓ |
| 3 | F03_INC_SYNC | Idempotent Incremental Sync | R1 | 5 | 5 | ✓ |
| 4 | F04_RED_STATS | Core Red Ball Stats (Sum, Span, AC Value, Odd/Even, Primes) | R2 | 5 | 5 | ✓ |
| 5 | F05_STRUCT_STATS | 3-Zone Distribution, Consecutive Groups, Repeats | R2 | 5 | 5 | ✓ |
| 6 | F06_OMISSIONS | Red/Blue Dynamic Omissions & Cold/Warm/Hot Tables | R2 | 5 | 5 | ✓ |
| 7 | F07_BLUE_SCORING | Blue Multi-Model Scoring (Hazard, Markov, Momentum) | R3 | 5 | 5 | ✓ |
| 8 | F08_BLUE_ALLOC | Confidence-Weighted Blue Break-Even (>= 10 RMB Payoff) | R3 | 5 | 5 | ✓ |
| 9 | F09_RED_WHEEL | Red Dan-Tuo Combinatorial Wheeling Coverage | R3 | 5 | 5 | ✓ |
| 10 | F10_GUARDRAILS | Statistical Guardrails (AC >= 6, Sum 80% CI, Odd/Even) | R3 | 5 | 5 | ✓ |
| 11 | F11_PRED_STORE | 5-Line Prediction Persistence with Metadata & Rationale | R3 | 5 | 5 | ✓ |
| 12 | F12_PRIZE_AUDIT | Official Levels 1-6 Prize Verification Engine | R4 | 5 | 5 | ✓ |
| 13 | F13_BACKTEST | Historical Chronological Backtesting (50, 100, 300 issues) | R4 | 5 | 5 | ✓ |
| 14 | F14_COMPARE_ROI | Comparative Evaluation: Concentrated vs Dispersed Strategies | R4 | 5 | 5 | ✓ |

## Test Architecture
- **Directory Layout**:
  ```
  tests/
  ├── conftest.py                      # Shared fixtures (temp test DB, mock HTTP responses)
  ├── e2e/
  │   ├── test_e2e_tier1_features.py   # Tier 1: 14 features x 5 = 70 test cases
  │   ├── test_e2e_tier2_boundaries.py # Tier 2: 14 features x 5 = 70 test cases
  │   ├── test_e2e_tier3_combinations.py # Tier 3: 14 pairwise interaction test cases
  │   └── test_e2e_tier4_workloads.py  # Tier 4: 7 comprehensive real-world application scenarios
  ```
- **Test Invocation**:
  ```powershell
  pytest tests/e2e/ -v
  ```
- **Pass / Fail Semantics**:
  - Exit code 0 indicates all tests pass.
  - Zero crashes, zero unhandled exceptions.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Cold Start to Full Ingestion | F01, F02, F03 | Medium |
| 2 | End-to-End Feature Pipeline Validation | F01, F04, F05, F06 | High |
| 3 | Single-Issue Prediction Generation & Verification Cycle | F07, F08, F09, F10, F11, F12 | High |
| 4 | Blue Break-Even Proof Empirical Simulation | F08, F11, F12 | High |
| 5 | Rolling 50-Issue Historical Backtest Workflow | F01, F06, F07, F08, F13, F14 | Very High |
| 6 | 300-Issue Long-Term Strategy Comparison Report | F11, F12, F13, F14 | Very High |
| 7 | Idempotent Re-Run & Data Integrity Resiliency | F01, F02, F03, F06, F11 | High |

## Coverage Thresholds
- Tier 1: 70 test cases (5 per feature across 14 features)
- Tier 2: 70 test cases (5 boundary cases per feature across 14 features)
- Tier 3: 14 test cases (pairwise cross-feature interactions)
- Tier 4: 7 test cases (end-to-end real-world workload pipelines)
- Total E2E test suite: >= 161 test cases
