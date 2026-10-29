# 离散序列量化分析与预测交互终端 (SSQ-Quant-System)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-387%20passed%20(100%25)-brightgreen.svg)]()
[![Frontend](https://img.shields.io/badge/frontend-Vue%203%20%7C%20TypeScript%20%7C%20Vite-61dafb.svg)]()
[![Database](https://img.shields.io/badge/sqlite-WAL%20mode-orange.svg)]()
[![Git](https://img.shields.io/badge/commits-Conventional%20Commits-purple.svg)]()

基于多维统计学、组合数学与博弈论的双色球全量历史数据挖掘系统。涵盖纯本地离线 5 注置信度保本预测策略、自适应自我进化闭环（Adaptive Reflection Loop）、基于 FastAPI 的高性能 RESTful 服务接口（毫秒级 CollisionCache）、以及基于 Vue 3 + TypeScript + Vite + Element Plus + Tailwind CSS + ECharts 的暗黑量化交易交互终端。

---

## 目录

- [核心能力与里程碑全景](#核心能力与里程碑全景)
- [系统架构图](#系统架构图)
- [快速上手指南](#快速上手指南)
  - [1. 依赖环境准备](#1-依赖环境准备)
  - [2. 启动 FastAPI 后端服务](#2-启动-fastapi-后端服务)
  - [3. 启动 Vue 3 暗黑量化终端](#3-启动-vue-3-暗黑量化终端)
  - [4. 命令行核心操作 (CLI)](#4-命令行核心操作-cli)
- [前端暗黑量化终端特性指南](#前端暗黑量化终端特性指南)
- [CLI 命令行工具完整参考手册](#cli-命令行工具完整参考手册)
- [RESTful API 接口概览与交互式文档](#restful-api-接口概览与交互式文档)
- [自动化测试与全栈质量门禁](#自动化测试与全栈质量门禁)
- [理性购彩与数学期望免责声明](#理性购彩与数学期望免责声明)
- [模块化技术文档导航](#模块化技术文档导航)

---

## 核心能力与里程碑全景

SSQ-Quant-System 现已全面完成 **Milestone 1 至 Milestone 9** 全部功能研发与全栈交付：

| 里程碑 | 模块名称 | 核心能力描述 | 交付状态 |
| :---: | :--- | :--- | :---: |
| **M1** | **数据抓取与同步引擎** | 采集 2003001 至今全量 **3,519+ 期** 真实开奖记录；支持 500.com 全量端点与官方福彩网增量接口，具备幂等更新与断点恢复。 | **已交付 (DONE)** |
| **M2** | **多维特征工程引擎** | 预计算 AC 值 ($|D|-5$)、红球和值正态分布、极差跨度、11质数分布、奇偶比、三区比例、连号聚集、全量红蓝球动态遗漏快照与冷温热标签。 | **已交付 (DONE)** |
| **M3** | **5注双轮驱动预测策略** | **防守保底**：蓝球多模型（马尔可夫链 + 遗漏回补风险 + 动量）置信度集中加权（3+2 分配），命中即保本（$\ge 10$ 元覆盖 5 注成本）；<br>**进攻大奖**：红球 2 核心胆码 + 8 卫星候选旋转矩阵（Dan-Tuo Wheeling），结合统计防线剪枝。 | **已交付 (DONE)** |
| **M4** | **核奖比对与回测引擎** | **自动核奖**：严格匹配官方 14 种中奖形态（1~6 等奖及未中奖），支持浮动奖金动态读取；<br>**历史时序回测**：严格单步前向截断（Zero-Lookahead Isolation），度量 ROI、MDD、保本率，支持策略双向横向对照。 | **已交付 (DONE)** |
| **M5** | **工程规范与交付文档** | 建立 `ENVIRONMENT_SETUP.md`，输出详尽模块化架构与实证回测报告，全量 **321 项基础测试通过**，严格执行 Conventional Commits 规范。 | **已交付 (DONE)** |
| **M6** | **FastAPI 服务与自适应进化** | 构建生产级 RESTful API 服务，实现子 10ms 历史碰撞缓存架构（`CollisionCache`），建立 $K_t \ge 3$ 连续赤字反思与冷热权重动态平移闭环。 | **已交付 (DONE)** |
| **M7** | **API 与自适应自动化测试集** | 编写 66 项全新自动化测试覆盖 API 路由与自适应服务，全仓 **387/387 项测试 100% 绿灯**，零回归。 | **已交付 (DONE)** |
| **M8** | **Vue 3 暗黑量化交互终端** | 采用 Vue 3 + TS + Vite + Element Plus Dark + Tailwind + ECharts，交付 4 大核心视图，打造霓虹红 (`#ff4757`) 与电光蓝 (`#00d2d3`) 发光核奖视觉。 | **已交付 (DONE)** |
| **M9** | **系统集成、文档与 Git 发布** | 全流程集成验证、全模块技术文档（06, 07, 08）对齐、master 文档同步并推送到 GitHub 远程仓库 `main` 分支。 | **已交付 (DONE)** |

---

## 系统架构图

```
+-----------------------------------------------------------------------------------------+
|                        Vue 3 暗黑量化交易交互终端 (Dark Quant Terminal)                  |
|  - 走势看板 (/history) : 遗漏热力图、指标分布直方图、增量爬虫同步                       |
|  - 预测实验 (/predict) : 5注策略参数配置、候选池实时推演、持久化入库                    |
|  - 预测档案 (/archive) : 历史批次时间轴、霓虹红/电光蓝发光高亮核奖卡片                  |
|  - 碰撞沙盒 (/sandbox) : 自定义选号 3500+ 期毫秒全量碰撞、四维分位数仪表盘              |
+-----------------------------------------------------------------------------------------+
                                             | HTTP / REST (Vite Proxy /api)
                                             v
+-----------------------------------------------------------------------------------------+
|                               FastAPI RESTful 后端服务网关                               |
|   - backend.app.main (FastAPI 实例, CORS 跨域, lifespan 预热, 统一异常处理)             |
|   - backend.app.api.history  : 开奖分页、最新数据、多维特征、遗漏矩阵热力、增量同步    |
|   - backend.app.api.predict  : 纯本地离线 5 注量化推演、方案入库持久化、预测大盘概览   |
|   - backend.app.api.backtest : 历史碰撞沙盒比对、官方开奖自动核奖、滑动窗口时序回测    |
|   - backend.app.api.adaptive : 当前自适应演进状态、不可变历史轨迹审计、手动重置/触发   |
+-----------------------------------------------------------------------------------------+
       |                           |                            |                        |
       v                           v                            v                        v
+---------------+          +---------------+            +---------------+        +---------------+
| 增量爬虫服务  |          | 特征工程引擎  |            | 量化预测引擎  |        | 高性能缓存    |
| CrawlerService|          | FeatureEngine |            | Predictor     |        | CollisionCache|
| (500.com/CWL) |          | (AC/和值/遗漏)|            | (胆拖/保本3+2)|        | (Sub-10ms 内存)|
+---------------+          +---------------+            +---------------+        +---------------+
                                                                |                        |
                                                                v                        |
                                                     +--------------------+              |
                                                     | 自适应进化闭环引擎 |              |
                                                     | AdaptiveService    |              |
                                                     | - 赤字门限 K_t>=3  |              |
                                                     | - 动量平移 eta=0.05|              |
                                                     | - 蓝球 3+2/5互异切换|             |
                                                     | - 和值防线负反馈漂移|             |
                                                     +--------------------+              |
                                                                |                        |
                                                                v                        v
+-----------------------------------------------------------------------------------------+
|                               SQLite WAL 持久化存储层 (ssq_quant.db)                     |
|  - ssq_draw_history (全量开奖)               - ssq_feature_metrics (多维统计特征)       |
|  - ssq_prediction_batches (预测批次头表)     - ssq_prediction_items (单注预测明细表)     |
|  - ssq_adaptive_state (自适应当前单例状态)   - ssq_adaptive_history (自适应不可变演进流水)|
+-----------------------------------------------------------------------------------------+
```

---

## 快速上手指南

### 1. 依赖环境准备

- **Python**: `>= 3.10`（推荐在本地 `D:\Miniconda3` 或 Python 虚拟环境执行）
- **Node.js**: `>= 20.x` 或 `22.x`（推荐 `v22.19.0`）
- **包管理器**: `pnpm`（推荐 `v11.x`）

```bash
# 1.1 安装 Python 后端依赖
pip install -r requirements.txt

# 1.2 安装前端依赖
cd frontend
pnpm install
cd ..
```

### 2. 启动 FastAPI 后端服务

```bash
# 启动本地开发服务 (支持自动热重载，默认端口 8000)
uvicorn backend.app.main:app --reload --port 8000
```
- API 根服务心跳: `http://localhost:8000/api/health`
- Swagger UI 交互式文档: `http://localhost:8000/docs`
- ReDoc 离线接口规范: `http://localhost:8000/redoc`

### 3. 启动 Vue 3 暗黑量化终端

```bash
cd frontend
pnpm run dev
```
- 访问暗黑量化终端: `http://localhost:5173`
- 前端请求通过 Vite 代理自动转发至后端 `:8000` 端口。

### 4. 命令行核心操作 (CLI)

后端提供全功能独立 CLI 工具链，支持离线全流程操作：

```bash
# 1. 增量抓取最新开奖并写入数据库
python -m backend.app.cli sync

# 2. 增量计算最新期次的 AC 值、和值与遗漏快照
python -m backend.app.cli compute-features

# 3. 纯本地生成最新期 5 注推荐方案（集中保本模式）
python -m backend.app.cli predict-issue

# 4. 在官方开奖后自动比对核奖并计算虚拟收益
python -m backend.app.cli verify

# 5. 执行历史滑动窗口回测并输出双策略对比分析
python -m backend.app.cli backtest --issues 100 --compare
```

---

## 前端暗黑量化终端特性指南

终端包含四大专属量化视图，全面采用暗黑金融交易终端配色方案：

1. **📊 走势看板 (`/history`)**：
   - 4 组 KPI 卡片展示当前期号、奖池滚存金额（`¥29.80 亿`）、前三热号与前三冷号；
   - 33 红球 + 16 蓝球全量遗漏矩阵热力图（支持 30 / 50 / 100 期切换）；
   - 和值、AC 值、奇偶比、跨度等核心数学指标经验分布图；
   - 历史开奖数据表格，支持按号码检索与一键触发增量爬虫同步。
2. **🧪 策略预测实验 (`/predict`)**：
   - 5 注预测超参数控制台：支持切换集中保本、分散基准、统计防线与高阶概率模式；
   - 纯本地离线推演（无需外网或 API Key，耗时 **< 100ms**）；
   - 展示 2 核心胆码 + 8 卫星拖码候选池与蓝球 TOP 3 置信度排名；
   - 3+2 集中加权博弈方案测算卡片，支持一键持久化保存至档案库。
3. **📜 预测档案中心 (`/archive`)**：
   - 预测胜率与投资大盘总览：展示累计投入、累计奖金、净利润、模拟 ROI、单期保本率；
   - 实时监控自适应引擎的当前演进模式与打分权重；
   - 逐注核奖比对卡片：**命中红球呈现高能霓虹红发光 (`#ff4757`)，命中蓝球呈现激光电光蓝发光 (`#00d2d3`)**；
   - 支持一键触发核奖比对并查看 AI 赛后反思记录。
4. **⚡ 历史碰撞沙盒 (`/sandbox`)**：
   - 交互式 33 红 + 16 蓝选号器，严格校验 6 红 1 蓝；
   - 依托 `CollisionCache` 内存矩阵，**在 8.48ms 内完成历史 3,500+ 期全量碰撞比对**；
   - 呈现最高历史战绩徽章、1~6 等奖各级中奖频次与假想历史总回报率；
   - 和值、AC 值、跨度、奇数个数四维数学分位数仪表盘。
5. **🎭 工位伪装模式 (Camouflage Mode)**：
   - 顶部提供一键工位伪装切换，将界面色彩一键重构为低对比度金融 K 线或代码编辑器风格。

---

## CLI 命令行工具完整参考手册

```bash
# --- 数据同步 ---
python -m backend.app.cli sync                 # 增量同步最新开奖
python -m backend.app.cli sync --force         # 全量覆盖重新抓取 3519 期

# --- 特征工程 ---
python -m backend.app.cli compute-features     # 增量计算未计算特征
python -m backend.app.cli compute-features --force # 全量重算特征

# --- 预测推演 ---
python -m backend.app.cli predict-issue        # 最新期集中保本推荐
python -m backend.app.cli predict-issue --strategy dispersed # 分散基准模式
python -m backend.app.cli predict-issue --issue 2026123      # 指定期号

# --- 自动核奖 ---
python -m backend.app.cli verify               # 核对所有待核奖批次
python -m backend.app.cli verify --issue 2026122 # 仅核对指定期号

# --- 策略回测 ---
python -m backend.app.cli backtest             # 默认回测近 100 期
python -m backend.app.cli backtest --issues 50 --strategy break_even
python -m backend.app.cli backtest --issues 300 --compare # 双策略横向对比
```

---

## RESTful API 接口概览与交互式文档

所有 API 均定义于 `backend/app/api/`，遵循统一 RESTful 规范：

- **历史与走势看板**：
  - `GET /api/v1/history/draws`：分页查询历史开奖记录（支持按号码筛选）
  - `GET /api/v1/history/latest`：获取最新一期官方开奖
  - `GET /api/v1/history/metrics`：获取特征指标时序（`limit=100`）
  - `GET /api/v1/history/omissions`：获取遗漏矩阵与冷温热标签
  - `GET /api/v1/history/distributions`：获取特征指标直方图统计
  - `POST /api/v1/history/sync`：触发爬虫同步并自动核奖
- **量化预测与档案**：
  - `POST /api/v1/predict/generate`：秒级离线推演 5 注方案
  - `POST /api/v1/predict/save`：持久化入库预测批次（必须精确 5 注）
  - `GET /api/v1/predict/batches`：分页查询预测批次
  - `GET /api/v1/predict/batches/{id}`：查询单次批次详情与高亮比对
  - `GET /api/v1/predict/dashboard`：查询累计胜率、奖金与收益率总览
- **碰撞沙盒与核奖**：
  - `POST /api/v1/backtest/sandbox/collision`：毫秒级全量历史碰撞（Sub-10ms）
  - `POST /api/v1/backtest/verify/{issue_no}`：官方开奖核验并触发自适应进化
  - `POST /api/v1/backtest/run`：时序滑动窗口回测
  - `POST /api/v1/backtest/compare`：集中保本 vs 分散基准横向回测对比
- **自适应策略自我进化**：
  - `GET /api/v1/adaptive/status`：获取当前自适应超参数与演进版本
  - `GET /api/v1/adaptive/trajectory`：查询自适应历史反思轨迹
  - `POST /api/v1/adaptive/trigger`：手动触发反思演进
  - `POST /api/v1/adaptive/reset`：重置自适应参数至基准初始状态

---

## 自动化测试与全栈质量门禁

项目已建立覆盖全功能模块的 5 层测试金字塔与 API 自动化测试套件，共计 **387 项测试用例，全部 100% 绿灯通过**：

```bash
# 1. 执行全量后端回归与 API 测试套件
python -m pytest

# 2. 执行前端 TypeScript 严格类型检查 (0 errors)
cd frontend
pnpm run type-check

# 3. 执行前端生产打包构建
pnpm run build
```

**测试架构全景 (387 Passed)**：
- `tests/api/test_api_history.py` (20 tests)：开奖分页、最新期、特征、遗漏矩阵热力、增量同步；
- `tests/api/test_api_predict.py` (15 tests)：离线预测生成、5 注约束校验、批次查询、大盘聚合统计；
- `tests/api/test_api_backtest_sandbox.py` (11 tests)：Sub-10ms 历史碰撞、大奖识别、四维分位数、核奖；
- `tests/api/test_api_adaptive.py` (8 tests)：自适应状态查询、轨迹事件、参数重置；
- `tests/unit/test_adaptive_service.py` (12 tests)：赤字门限触发、动态权重平移、蓝球模态切换、饱和截断；
- `tests/unit/test_crawler.py` (14 tests)：数据爬虫解析与断点恢复；
- `tests/unit/test_features.py` (30 tests)：AC值、和值、质合比、三区、遗漏快照精度；
- `tests/unit/test_verifier.py` (18 tests)：官方 14 种奖级判定与浮动奖金兜底；
- `tests/unit/test_backtest.py` (14 tests)：零未来函数时序切片、MDD 与双策略对比；
- `tests/unit/test_adversarial_m1.py` & `test_adversarial_m2.py` (66 tests)：对抗边界测试与网络容灾；
- `tests/unit/test_challenger_m2.py` (20 tests)：特征一致性挑战者校验；
- `tests/e2e/test_e2e_tier1_features.py` ~ `test_e2e_tier4_workloads.py` (159 tests)：黑盒端到端工作流闭环。

---

## 理性购彩与数学期望免责声明

> [!CAUTION]
> ### ⚠️ 概率论警示与理性购彩守则
> 
> 1. **数学期望严格负收益 ($E[X] = -50\%$)**：
>    根据中国福利彩票相关管理法规，双色球彩票销售款中 36% 提取为彩票公益金，13% 为发行维护费，法定返奖率仅为 **49% ~ 50%**。在无偏随机抽取下，**单注 2 元彩票的长期理论期望收益为 -1 元 (ROI = -50%)**。无论使用何种算法（如马尔可夫链、集成学习、组合旋转矩阵），均无法逾越高达 50% 的庄家抽水。
> 2. **量化策略的真实定位**：
>    本系统实现的“集中加权保本策略”是**在假定命中特定高置信度蓝球的先验条件下，优化单期派奖结构的非对称聚集（将 5 注分散的 5 元亏损重构为 3 注 15 元盈利或 2 注 10 元保本）**。回测实证显示，集中策略可将单期保本期次率从分散策略的 **0%~1%** 提升至 **8%~12%**，但这仅是“资金回撤结构的平滑优化”，**绝不意味着可以实现绝对正期望盈利**。
> 3. **公益娱乐与风险防范**：
>    彩票是支持国家社会福利事业的微额慈善娱乐方式，**绝非投资理财或财富增值途径**。请理性购彩，严控娱乐预算，严禁未成年人参与！

---

## 模块化技术文档导航

- [环境配置指南 (ENVIRONMENT_SETUP.md)](ENVIRONMENT_SETUP.md)
- [01. 数据库结构说明 (docs/01_database_schema.md)](docs/01_database_schema.md)
- [02. 数据抓取与增量同步引擎 (docs/02_crawler_service.md)](docs/02_crawler_service.md)
- [03. 多维数学特征工程引擎 (docs/03_feature_engineering.md)](docs/03_feature_engineering.md)
- [04. 5注预测策略与双轮驱动引擎 (docs/04_prediction_strategy.md)](docs/04_prediction_strategy.md)
- [04. Git 提交与协同规范 (docs/04_git_commit_standard.md)](docs/04_git_commit_standard.md)
- [05. 历史滑动窗口回测与核奖审计报告 (docs/05_backtest_report.md)](docs/05_backtest_report.md)
- [06. FastAPI RESTful 服务与 CollisionCache 架构规范 (docs/06_fastapi_restful_api.md)](docs/06_fastapi_restful_api.md)
- [07. 自适应策略自我进化机制与闭环反馈算法设计 (docs/07_adaptive_strategy_loop.md)](docs/07_adaptive_strategy_loop.md)
- [08. 前端暗黑量化终端交互系统架构与操作指南 (docs/08_frontend_quant_terminal.md)](docs/08_frontend_quant_terminal.md)
