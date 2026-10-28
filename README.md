# 离散序列量化分析与预测平台 (SSQ-Quant-System)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-321%20passed%20(100%25)-brightgreen.svg)]()
[![Database](https://img.shields.io/badge/sqlite-WAL%20mode-orange.svg)]()
[![Git](https://img.shields.io/badge/commits-Conventional%20Commits-purple.svg)]()

基于多维统计学、组合数学与博弈论的双色球全量历史数据挖掘、5注置信度保本优化预测策略、自动化核奖审计与零未来函数历史滑动窗口回测系统。

---

## 目录

- [核心能力与里程碑全景](#核心能力与里程碑全景)
- [系统架构图](#系统架构图)
- [快速上手](#快速上手)
  - [1. 环境准备](#1-环境准备)
  - [2. 命令行核心操作 (CLI)](#2-命令行核心操作-cli)
- [CLI 命令完整参考手册](#cli-命令完整参考手册)
  - [1. 数据采集与增量同步 (sync)](#1-数据采集与增量同步-sync)
  - [2. 多维特征工程计算 (compute-features)](#2-多维特征工程计算-compute-features)
  - [3. 5注策略预测推荐 (predict-issue / predict)](#3-5注策略预测推荐-predict-issue--predict)
  - [4. 官方开奖自动核奖比对 (verify)](#4-官方开奖自动核奖比对-verify)
  - [5. 历史时序滑动窗口回测 (backtest)](#5-历史时序滑动窗口回测-backtest)
- [自动化测试与质量保障](#自动化测试与质量保障)
- [理性购彩与数学期望免责声明](#理性购彩与数学期望免责声明)
- [模块化技术文档导航](#模块化技术文档导航)

---

## 核心能力与里程碑全景

SSQ-Quant-System 现已全面完成 **Milestone 1 至 Milestone 5** 全部技术交付：

| 里程碑 | 模块名称 | 核心能力描述 | 状态 |
| :---: | :--- | :--- | :---: |
| **M1** | **数据抓取与同步引擎** | 采集 2003001 至今全量 **3,519 期** 真实开奖记录；支持 500.com 全量端点与官方中国福彩网增量接口，具备幂等更新与异常重试。 | **已交付 (DONE)** |
| **M2** | **多维特征工程引擎** | 全量预计算 AC 值 ($|D|-5$)、红球和值正态分布、极差跨度、11质数分布、奇偶比、三区比例、连号聚集、全量红蓝球动态遗漏快照与冷温热标签。 | **已交付 (DONE)** |
| **M3** | **5注双轮驱动预测策略** | **防守保底层**：蓝球多模型（马尔可夫链 + 遗漏回补风险 + 动量）置信度集中加权（3+2 分配），命中即保本（$\ge 10$ 元覆盖 5 注成本）；<br>**进攻大奖层**：红球 2 核心胆码 + 8 卫星候选旋转矩阵（Dan-Tuo Wheeling），结合统计防线剪枝。 | **已交付 (DONE)** |
| **M4** | **核奖比对与回测引擎** | **自动核奖**：严格匹配官方 14 种排列规则（1~6 等奖及未中奖），支持浮动奖金动态读取与兜底；<br>**历史时序回测**：严格单步前向截断（Zero-Lookahead Isolation），度量 ROI、MDD、保本率，支持策略双向横向对照。 | **已交付 (DONE)** |
| **M5** | **工程规范与交付文档** | 建立 `ENVIRONMENT_SETUP.md`，输出详尽模块化架构与实证回测报告，全量 **321/321 项测试通过**，严格执行 Conventional Commits 规范。 | **已交付 (DONE)** |

---

## 系统架构图

```
+-----------------------------------------------------------------------------------+
|                                  用户终端 / CLI 控制层                            |
|     python -m backend.app.cli {sync, compute-features, predict-issue, verify, backtest}  |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                                业务领域服务层 (Services)                           |
+------------------+     +-------------------+     +--------------------------------+
|  Crawler Engine  |     |  Feature Engine   |     |    Predictor Strategy Engine   |
|  - 500.com 全量  |     |  - AC值 (|D|-5)   |     |  - 蓝球 3 模型置信度集成评分   |
|  - 福彩网 增量   |     |  - 和值 / 跨度    |     |  - 集中加权 3+2 保本博弈分配   |
|  - 幂等入库      |     |  - 11质数/奇偶/三区|    |  - 2胆8拖红球旋转矩阵组合      |
+------------------+     |  - 全量遗漏矩阵   |     |  - 统计防线剪枝 (AC>=6, CI80%) |
         |               +-------------------+     +--------------------------------+
         |                         |                                |
         v                         v                                v
+-----------------------------------------------------------------------------------+
|                           SQLite WAL 存储持久层 (ssq_quant.db)                    |
|   - ssq_draw_history (开奖记录)          - ssq_prediction_batches (预测批次)      |
|   - ssq_feature_metrics (特征指标)       - ssq_prediction_items (单注预测明细)    |
+-----------------------------------------------------------------------------------+
                                           ^
                                           |
                   +-----------------------------------------------+
                   |        Prize Verification & Backtest Engine   |
                   |   - 官方 14 种中奖形态精确判级 (1~6 等奖 + Miss) |
                   |   - 严格单步前向无未来函数切片 (all_draws[:i])   |
                   |   - ROI / 保本率 / MDD / 连胜连负量化评估        |
                   +-----------------------------------------------+
```

---

## 快速上手

### 1. 环境准备

推荐直接在已包含标准科学计算库的环境（如本地 `D:\Miniconda3`）或通过虚拟环境执行。详细环境部署说明见 [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md)。

```bash
# 1. 安装核心依赖
pip install -r requirements.txt

# 2. 验证环境与运行全量测试套件
pytest tests/
```

### 2. 命令行核心操作 (CLI)

```bash
# 增量同步最新开奖数据（如遇新期号自动下载）
python -m backend.app.cli sync

# 增量计算新一期统计特征与遗漏快照
python -m backend.app.cli compute-features

# 生成最新一期 5 注推荐（默认集中保本模式，生成 3+2 蓝球与旋转矩阵红球）
python -m backend.app.cli predict-issue

# 在官方公布当期结果后，一键自动核对中奖状态与计算模拟回报
python -m backend.app.cli verify

# 执行历史 100 期滑动窗口策略回测与横向对照评测
python -m backend.app.cli backtest --issues 100 --compare
```

---

## CLI 命令完整参考手册

系统通过统一模块入口 `python -m backend.app.cli <command> [options]` 调用：

### 1. 数据采集与增量同步 (sync)

从公开稳定数据源采集双色球真实开奖记录并存入 SQLite `ssq_draw_history`。

```bash
# 默认增量同步（若数据库已有数据则只拉取最新期号，若为空则自动触发全量初始化）
python -m backend.app.cli sync

# 强制全量同步并覆盖历史数据（从 2003001 开始全量重新爬取）
python -m backend.app.cli sync --force

# 明确仅执行增量同步
python -m backend.app.cli sync --incremental
```

### 2. 多维特征工程计算 (compute-features)

计算并更新开奖数据的 AC 值、和值、跨度、奇偶比、质合比、三区比例以及每期 33 红球 + 16 蓝球全量遗漏矩阵快照。

```bash
# 智能计算未计算特征的期次
python -m backend.app.cli compute-features

# 强制全量重新计算所有历史特征
python -m backend.app.cli compute-features --force

# 从指定期号开始增量计算
python -m backend.app.cli compute-features --from-issue 2026100
```

### 3. 5注策略预测推荐 (predict-issue / predict)

执行“防守保底 + 进攻大奖”双轮驱动预测算法，生成 5 注号码，控制台打印直观分析并持久化至 `ssq_prediction_batches` 和 `ssq_prediction_items`。

```bash
# 生成最新期预测（默认集中保本加权模式 CONCENTRATED_BREAK_EVEN）
python -m backend.app.cli predict-issue

# 指定策略生成预测：集中保本模式 (break_even)
python -m backend.app.cli predict-issue --strategy break_even

# 指定策略生成预测：分散基准模式 (dispersed)
python -m backend.app.cli predict-issue --strategy dispersed

# 为指定历史期号或未来期号生成预测
python -m backend.app.cli predict-issue --issue 2026123 --strategy break_even
```

### 4. 官方开奖自动核奖比对 (verify)

自动比对已生成的预测批次与官方真实开奖号码，判定 1~6 等奖及未中奖，核算虚拟奖金与单期 ROI，写入复盘分析。

```bash
# 自动检测并核验所有待核奖 (PENDING) 且官方已开奖的批次
python -m backend.app.cli verify

# 仅核对指定期号的预测记录
python -m backend.app.cli verify --issue 2026122

# 仅核对指定批次 ID
python -m backend.app.cli verify --batch-id 7

# 强制重新核验已核奖批次 (覆盖原有核奖数据)
python -m backend.app.cli verify --issue 2026122 --force
```

### 5. 历史时序滑动窗口回测 (backtest)

在零未来函数严格隔离下，模拟历史前 $N$ 期的连续投注表现，度量收益率、保本率与资金曲线。

```bash
# 默认回测最近 100 期（使用集中保本策略）
python -m backend.app.cli backtest

# 指定回测期数与策略
python -m backend.app.cli backtest --issues 50 --strategy break_even
python -m backend.app.cli backtest --issues 300 --strategy dispersed

# 双策略横向对照回测：对比 CONCENTRATED_BREAK_EVEN vs DISPERSED_BASELINE
python -m backend.app.cli backtest --issues 100 --compare
python -m backend.app.cli backtest --issues 300 --compare
```

---

## 自动化测试与质量保障

项目建立了覆盖全功能模块的 5 层测试金字塔与对抗边界测试集，共计 **321 项测试用例**，全部通过：

```bash
# 运行全部单元测试与端到端测试
pytest tests/ -v
```

**测试架构全景 (321 Passed)**：
* `tests/unit/test_crawler.py` (14 tests)：官方数据爬虫解析、增量更新与断点恢复；
* `tests/unit/test_features.py` (30 tests)：AC值、和值、质合比、三区、遗漏快照计算精度；
* `tests/unit/test_verifier.py` (18 tests)：官方 14 种奖级排列判定、$(3,0)$ 边界防御、浮动奖金兜底；
* `tests/unit/test_backtest.py` (14 tests)：零未来函数隔离断言、窗口截断边界、双策略对比与 MDD；
* `tests/unit/test_adversarial_m1.py` & `test_adversarial_m2.py` (66 tests)：对抗边界测试、极端网络异常、并发重试；
* `tests/unit/test_challenger_m2.py` (20 tests)：挑战者特征一致性校验；
* `tests/e2e/test_e2e_tier1_features.py` ~ `test_e2e_tier4_workloads.py` (159 tests)：黑盒端到端工作流闭环。

---

## 理性购彩与数学期望免责声明

> [!CAUTION]
> ### ⚠️ 概率论警示与理性购彩守则
> 
> 1. **数学期望严格负收益 ($E[X] = -50\%$)**：
>    根据中国福利彩票相关管理法规，双色球彩票销售款中 36% 提取为彩票公益金，13% 为发行维护费，法定返奖率仅为 **49% ~ 50%**。
>    在无偏随机抽取下，**单注 2 元彩票的长期理论期望收益为 -1 元 (ROI = -50%)**。无论使用何种前沿算法（如马尔可夫链、集成学习、旋转矩阵），均无法逾越高达 50% 的庄家抽水。
> 2. **量化策略的真实定位**：
>    本系统实现的“集中加权保本策略”是**在假定命中特定高置信度蓝球的先验条件下，优化单期派奖结构的非对称聚集（将 5 注分散的 5 元亏损重构成 3 注 15 元盈利或 2 注 10 元保本）**。回测实证显示，集中策略可将单期保本期次率从分散策略的 **0%~1%** 提升至 **8%~12%**，但这仅是“资金回撤结构的平滑优化”，**并不意味着可以实现绝对正期望盈利**。
> 3. **公益娱乐与风险防范**：
>    彩票是支持国家社会福利事业的微额慈善娱乐方式，**绝非投资理财或财富增值途径**。请理性购彩，严控娱乐预算，严禁未成年人参与！

---

## 模块化技术文档导航

* [环境配置指南 (ENVIRONMENT_SETUP.md)](ENVIRONMENT_SETUP.md)
* [01. 数据库结构说明 (docs/01_database_schema.md)](docs/01_database_schema.md)
* [02. 数据抓取与增量同步引擎 (docs/02_crawler_service.md)](docs/02_crawler_service.md)
* [03. 多维数学特征工程引擎 (docs/03_feature_engineering.md)](docs/03_feature_engineering.md)
* [04. 5注预测策略与双轮驱动引擎 (docs/04_prediction_strategy.md)](docs/04_prediction_strategy.md)
* [04. Git 提交与协同规范 (docs/04_git_commit_standard.md)](docs/04_git_commit_standard.md)
* [05. 历史滑动窗口回测与核奖审计报告 (docs/05_backtest_report.md)](docs/05_backtest_report.md)
