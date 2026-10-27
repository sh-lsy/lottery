# 01. 数据库表结构设计说明 (Database Schema)

系统采用轻量高效的单文件 SQLite 数据库，持久化存储于 `data/ssq_quant.db`。采用 SQLAlchemy 2.0 ORM 进行规范化建模，目前已落地 4 张核心表。

---

## 1. 历史开奖主表 (`ssq_draw_history`)

存储官方历史原始开奖数据及奖池销售额信息。

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `id` | INTEGER PRIMARY KEY | 自增主键 |
| `issue_no` | VARCHAR(20) UNIQUE | 期号（如 `2026122`），建立倒序索引 |
| `draw_date` | DATE | 开奖日期，建立倒序索引 |
| `weekday` | INT | 星期几 (2, 4, 7) |
| `red_1` ~ `red_6` | INT | 红球1至红球6（升序排列，范围 01~33） |
| `blue_1` | INT | 蓝球号码（范围 01~16） |
| `red_seq_str` | VARCHAR(30) | 格式化红球字符串（如 `02,08,15,21,26,31`） |
| `sales_amount` | BIGINT | 本期销售额(元) |
| `pool_amount` | BIGINT | 奖池累积金额(元) |
| `first_prize_num` | INT | 一等奖注数 |
| `first_prize_amount`| BIGINT | 一等奖单注奖金(元) |
| `second_prize_num`| INT | 二等奖注数 |
| `second_prize_amount`| BIGINT | 二等奖单注奖金(元) |
| `created_at` | DATETIME | 数据入库时间 |

---

## 2. 统计特征指标表 (`ssq_feature_metrics`)

与 `ssq_draw_history` 以 `issue_no` 一对一关联，存储预计算好的衍生统计与数学特征。

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `issue_no` | VARCHAR(20) PRIMARY KEY | 外键关联开奖主表期号 |
| `sum_red` | INT | 红球和值（理论范围 21~183，常态 75~135） |
| `span_red` | INT | 红球跨度（最大红球 - 最小红球） |
| `ac_value` | INT | 算术复杂度（AC值，公式为 $\|D\| - 5$） |
| `odd_count` | INT | 奇数个数（0~6） |
| `prime_count` | INT | 质数个数（01~33 中包含的 11 个质数个数） |
| `zone1_count` | INT | 一区(01~11)出球个数 |
| `zone2_count` | INT | 二区(12~22)出球个数 |
| `zone3_count` | INT | 三区(23~33)出球个数 |
| `consecutive_groups`| INT | 连号组数（如 07,08 算 1 组） |
| `repeat_prev_red` | INT | 较上一期重号个数（0~6） |
| `missing_sum_red` | INT | 当期 6 个红球在开奖前的遗漏值总和 |
| `missing_blue` | INT | 当期蓝球在开奖前的遗漏期数 |
| `missing_snapshot_json`| TEXT | 当期开奖后 33红 + 16蓝的完整遗漏计数器快照 (JSON) |

---

## 3. 预测批次表 (`ssq_prediction_batches`)

管理每一次预测任务的元数据与宏观兑奖结果。

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `id` | INTEGER PRIMARY KEY | 自增主键 |
| `target_issue` | VARCHAR(20) | 目标预测期号，建立索引 |
| `strategy_type` | VARCHAR(50) | 策略类型（如 `BREAK_EVEN_TOP_BLUE` / `WHEEL_MATRIX` 等） |
| `model_name` | VARCHAR(50) | 模型标识 |
| `filter_params_json` | TEXT | 过滤参数快照（JSON） |
| `ai_reasoning_md` | TEXT | 选号推演说明 |
| `total_notes` | INT | 预测总注数（默认 5 注） |
| `verify_status` | VARCHAR(20) | 状态：`PENDING`(待开奖), `VERIFIED`(已核对) |
| `best_prize_level` | INT | 本批次最高中奖等级 (1~6, 0为未中) |
| `virtual_cost` | INT | 成本（如 5注=10元） |
| `virtual_reward` | BIGINT | 获得奖金总额(元) |

---

## 4. 预测注项明细表 (`ssq_prediction_items`)

存储每注具体号码及开奖后的逐球比对判定。

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `id` | INTEGER PRIMARY KEY | 自增主键 |
| `batch_id` | INTEGER | 外键关联 `ssq_prediction_batches.id` |
| `target_issue` | VARCHAR(20) | 目标预测期号 |
| `red_1` ~ `red_6` | INT | 预测红球1~6 |
| `blue_1` | INT | 预测蓝球 |
| `confidence_score`| FLOAT | 模型置信度评分 |
| `is_verified` | BOOLEAN | 是否已完成自动比对 |
| `hit_red_count` | INT | 命中红球个数 (0~6) |
| `hit_red_numbers`| VARCHAR(30) | 命中的红球字符串（高亮渲染用） |
| `hit_blue` | BOOLEAN | 是否命中蓝球 (0/1) |
| `prize_level` | INT | 中奖等级 (1~6, 0为未中) |
| `prize_amount` | BIGINT | 该注中奖金额(元) |
