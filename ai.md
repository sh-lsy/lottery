# 基于多维统计与 AI Agent 的双色球分析与预测交互系统 (SSQ-Quant-System)

> **工位开发伪装指南**：
> 1. **项目命名**：建议本地文件夹命名为 `discrete-sequence-quant-platform`（离散序列量化分析平台）。
> 2. **视觉风格**：前端采用深色极客/金融量化终端风格（Dark Mode + 细边框表格 + ECharts 折线/热力图）。避免在界面上出现大红大绿的“福彩大吉”、“中大奖”字样，将红球称为 **`Primary Sequence (P-Seq)`**，蓝球称为 **`Secondary Scalar (S-Val)`**，命中验证称为 **`Backtest Validation (回测校验)`**，路过的同事和领导只会以为你在调试高阶数据分析中台。

---

## 一、 系统定位与业务闭环

本项目旨在构建一个集**“历史数据采集与可视化 + 多模态策略预测生成 + 历史预测档案管理与自动兑奖复盘”**于一体的全栈交互系统。

### 1.1 数学基准与工程目标
双色球由 6 个红球（从 $01 \sim 33$ 中选 6 个）和 1 个蓝球（从 $01 \sim 16$ 中选 1 个）组成，总组合数为：
$$N = C_{33}^6 \times C_{16}^1 = \frac{33!}{6!(33-6)!} \times 16 = 17,721,088$$

尽管每次摇奖在物理上是独立随机事件，但从工程与博弈论角度，本系统通过以下三层逻辑提供辅助决策与技术练手：
1. **大数定律特征过滤**：历史开奖号码在和值、AC值（数字复杂度）、奇偶比、区间分布上呈现高度集中趋势（正态分布区间），过滤掉极端偏态组合可大幅缩减无效选号空间。
2. **历史预测闭环验证**：每次生成的预测方案均持久化存入数据库，待真实开奖后自动触发比对引擎，计算各策略/模型的命中率、虚拟盈亏（ROI），驱动策略迭代。
3. **AI Agent 自动复盘**：引入 LLM 结合历史预测偏差进行反思（Reflection），动态调整下一期的特征过滤权重。

---

## 二、 技术栈选型（轻量级全栈架构）

为了方便你在工位快速搭建、零外部运维依赖地跑通全流程，推荐以下技术栈：

* **前端（Frontend）**：
  * 核心框架：`Vue 3` (Composition API)  + `TypeScript` + `Vite`
  * UI 与样式：`Tailwind CSS` + `Shadcn UI` / `Element Plus` (统一配置为暗黑模式 Dark Theme)
  * 数据可视化：`Apache ECharts`（负责绘制走势图、遗漏热力图、和值分布与预测胜率曲线）
* **后端（Backend）**：
  * 核心框架：`Python FastAPI`（天生契合数据处理与 AI 接口调用，自带 Swagger 接口文档）
  * ORM 与数据迁移：`SQLAlchemy 2.0` + `Alembic`
  * 定时任务：`APScheduler`（用于在每周二、四、日晚 21:30 后自动拉取最新开奖结果并执行历史预测自动兑奖）
* **数据库（Database）**：
  * 开发/工位环境：**`SQLite`**（单文件存储在项目目录下，无需安装数据库服务，极其隐蔽便携）
  * 进阶扩展：随时可通过修改一行数据库连接串无缝切换至 `PostgreSQL` 或 `MySQL`
* **算法与 AI 层（AI & Quant Core）**：
  * 数据与统计：`Pandas` + `NumPy` + `SciPy`
  * 机器学习：`Scikit-learn` / `XGBoost` / `PyTorch`（用于号码出现概率分布拟合与马尔可夫状态转移计算）
  * 大模型接入：`OpenAI SDK`（兼容 DeepSeek / Claude / 本地 Ollama），支持 Function Calling 与流式输出（SSE）

---

## 三、 数据库详细设计 (Database Schema)

数据库共规划 **4 张核心表**，完整支撑“看历史开奖”、“存预测方案”、“自动核对中奖结果”三大核心诉求。

### 3.1 历史开奖主表 (`ssq_draw_history`)
存储官方每一期的原始开奖号码及奖池信息。

```sql
CREATE TABLE ssq_draw_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_no VARCHAR(20) NOT NULL UNIQUE,      -- 期号，如 '2026120'
    draw_date DATE NOT NULL,                   -- 开奖日期，如 '2026-10-25'
    weekday INT NOT NULL,                      -- 星期几 (2, 4, 7)
    red_1 INT NOT NULL,                        -- 红球1 (从小到大排序, 1-33)
    red_2 INT NOT NULL,                        -- 红球2
    red_3 INT NOT NULL,                        -- 红球3
    red_4 INT NOT NULL,                        -- 红球4
    red_5 INT NOT NULL,                        -- 红球5
    red_6 INT NOT NULL,                        -- 红球6
    blue_1 INT NOT NULL,                       -- 蓝球 (1-16)
    red_seq_str VARCHAR(30) NOT NULL,          -- 红球格式化字符串，如 '02,08,15,21,26,31'
    sales_amount BIGINT DEFAULT 0,             -- 本期销售额(元)
    pool_amount BIGINT DEFAULT 0,              -- 奖池滚存金额(元)
    first_prize_num INT DEFAULT 0,             -- 一等奖注数
    first_prize_amount BIGINT DEFAULT 0,       -- 一等奖单注奖金
    second_prize_num INT DEFAULT 0,            -- 二等奖注数
    second_prize_amount BIGINT DEFAULT 0,      -- 二等奖单注奖金
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_draw_issue ON ssq_draw_history(issue_no DESC);
CREATE INDEX idx_draw_date ON ssq_draw_history(draw_date DESC);
```

### 3.2 历史统计特征衍生表 (`ssq_feature_metrics`)
与 `ssq_draw_history` 一对一关联，在入库时预先计算好各项数学特征，供前端图表秒级查询和算法模型直接读取。

```sql
CREATE TABLE ssq_feature_metrics (
    issue_no VARCHAR(20) PRIMARY KEY,          -- 关联期号
    sum_red INT NOT NULL,                      -- 红球和值 (理论范围 21-183，常驻 70-140)
    span_red INT NOT NULL,                     -- 红球跨度 (最大号减最小号, 5-32)
    ac_value INT NOT NULL,                     -- AC值/数字复杂度 (0-10，常驻 6-10)
    odd_count INT NOT NULL,                    -- 奇数个数 (0-6)
    prime_count INT NOT NULL,                  -- 质数个数 (0-6)
    zone1_count INT NOT NULL,                  -- 一区(01-11)个数
    zone2_count INT NOT NULL,                  -- 二区(12-22)个数
    zone3_count INT NOT NULL,                  -- 三区(23-33)个数
    consecutive_groups INT DEFAULT 0,          -- 连号组数
    repeat_prev_red INT DEFAULT 0,             -- 与上一期重号个数 (0-6)
    missing_sum_red INT DEFAULT 0,             -- 6个红球当期遗漏值总和
    missing_blue INT DEFAULT 0,                -- 蓝球当期遗漏期数
    missing_snapshot_json TEXT,                -- 当期开奖后33红+16蓝的完整遗漏计数器快照(JSON)
    FOREIGN KEY (issue_no) REFERENCES ssq_draw_history(issue_no) ON DELETE CASCADE
);
```

### 3.3 预测批次/任务表 (`ssq_prediction_batches`)
记录每一次操作生成的预测任务上下文（例如：用什么策略预测哪一期、AI 给出的分析推演理由是什么）。

```sql
CREATE TABLE ssq_prediction_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_issue VARCHAR(20) NOT NULL,         -- 目标预测期号，如 '2026121'
    strategy_type VARCHAR(50) NOT NULL,        -- 策略类型: 'STAT_FILTER'(统计过滤) / 'ML_PROB'(机器学习) / 'LLM_AGENT'(AI智能体) / 'MANUAL'(手动自选)
    model_name VARCHAR(50),                    -- 模型标识，如 'DeepSeek-V3', 'XGBoost-v1.2'
    filter_params_json TEXT,                   -- 预测时设定的过滤参数快照(JSON: 和值区间、奇偶比限制等)
    ai_reasoning_md TEXT,                      -- AI 生成的当期走势分析与选号逻辑说明(Markdown文本)
    total_notes INT NOT NULL DEFAULT 5,        -- 本批次包含的预测注数
    verify_status VARCHAR(20) DEFAULT 'PENDING',-- 兑奖状态: 'PENDING'(待开奖), 'VERIFIED'(已核对)
    best_prize_level INT DEFAULT 0,            -- 本批次最高中奖等级 (0未中奖, 1-6代表一至六等奖)
    virtual_cost INT DEFAULT 0,                -- 虚拟投入成本 (total_notes * 2元)
    virtual_reward BIGINT DEFAULT 0,           -- 虚拟中奖总金额(元)
    post_reflection_md TEXT,                   -- 开奖后 AI 对本批次预测结果的复盘总结
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    verified_at DATETIME                       -- 兑奖核对时间
);
CREATE INDEX idx_pred_batch_issue ON ssq_prediction_batches(target_issue DESC);
```

### 3.4 预测号码明细与兑奖结果表 (`ssq_prediction_items`)
存储某一次预测批次下的具体每一注号码，以及开奖后的逐球比对结果。

```sql
CREATE TABLE ssq_prediction_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL,                 -- 关联 ssq_prediction_batches.id
    target_issue VARCHAR(20) NOT NULL,         -- 目标期号(冗余字段方便直接查询)
    red_1 INT NOT NULL,                        -- 预测红球1
    red_2 INT NOT NULL,                        -- 预测红球2
    red_3 INT NOT NULL,                        -- 预测红球3
    red_4 INT NOT NULL,                        -- 预测红球4
    red_5 INT NOT NULL,                        -- 预测红球5
    red_6 INT NOT NULL,                        -- 预测红球6
    blue_1 INT NOT NULL,                       -- 预测蓝球
    confidence_score FLOAT DEFAULT 0.0,        -- 算法/模型给出的综合置信度评分 (0-100)
    -- 以下字段在目标期号开奖后由系统自动回填：
    is_verified BOOLEAN DEFAULT 0,             -- 是否已完成开奖比对
    hit_red_count INT DEFAULT 0,               -- 命中红球个数 (0-6)
    hit_red_numbers VARCHAR(30) DEFAULT '',    -- 命中的具体红球列表，如 '08,21' (用于前端高亮渲染)
    hit_blue BOOLEAN DEFAULT 0,                -- 是否命中蓝球 (0或1)
    prize_level INT DEFAULT 0,                 -- 中奖等级 (0:未中, 1:一等奖 ... 6:六等奖)
    prize_amount BIGINT DEFAULT 0,             -- 该注获得的奖金(元)
    FOREIGN KEY (batch_id) REFERENCES ssq_prediction_batches(id) ON DELETE CASCADE
);
CREATE INDEX idx_pred_item_issue ON ssq_prediction_items(target_issue);
```

---

## 四、 前端交互界面规划 (UI/UX 设计)

前端采用经典的**左侧折叠导航栏 + 右侧主工作区**布局，共包含 **4 个核心功能视图**：

### 4.1 视图一：全景历史数据与走势工作台 (`/history`)
满足你**“查看历史开奖与规律”**的需求：
1. **顶部统计卡片**：展示最新一期开奖结果、当前奖池金额、近 30 期最热红球 Top 3、最大遗漏冷球 Top 3。
2. **多维走势图表区（Tab 切换）**：
   * **全号球遗漏热力走势图**：横轴为 $01 \sim 33$ 红球与 $01 \sim 16$ 蓝球，纵轴为最近 $30/50/100$ 期，直观展示号码冷热转换、斜连号、重号规律。
   * **核心数学指标趋势图**：展示近期“红球和值”、“AC值”、“奇偶比/区间比”的折线图及历史正态分布直方图。
3. **历史开奖数据明细表**：支持按期号、日期范围搜索，支持筛选包含特定号码的历史期次，点击任意一行可展开该期的详细数学特征雷达图。
4. **右上角操作按钮**：`[同步最新官方开奖数据]`（触发后端爬虫拉取最新期次并自动入库）。

### 4.2 视图二：AI 预测与策略生成实验室 (`/predict-lab`)
满足你**“生成预测方案并入库”**的需求，分为左右分栏：
* **左侧：策略配置与过滤器面板**
  * **目标期号**：自动默认下一期期号（如 `2026121`），也支持选择历史某期进行“时光机回测预测”。
  * **生成引擎选择**：
    1. `统计特征优选引擎`（蒙特卡洛随机生成 + 严格数学指标过滤）
    2. `机器学习概率加权引擎`（基于马尔可夫转移矩阵与 XGBoost 号码得分抽样）
    3. `LLM Agent 深度推演引擎`（将近 30 期特征矩阵喂给大模型，由 Agent 自主决定过滤条件并选号）
  * **自定义硬性约束滑块**：和值范围（默认 $75 \sim 135$）、AC值下限（默认 $\ge 6$）、奇偶比限定（如仅允许 `3:3`, `4:2`, `2:4`）、手动设胆码（必选球）/杀号（排除球）。
* **右侧：实时推演过程与候选方案预览**
  * **AI 思考流展示框**：当使用 Agent 模式时，通过打字机效果实时展示 AI 对近期奇偶走势、蓝球冷热周期的分析推导过程。
  * **候选号码列表**：展示生成的 $N$ 注号码，同时显示每一注对应的和值、AC值、区间比以及模型评分。
  * **底部入库按钮**：点击 `[保存至历史预测档案]`，将该批次预测方案及 AI 推演逻辑正式写入数据库 `ssq_prediction_batches` 与 `ssq_prediction_items`。

### 4.3 视图三：历史预测档案与兑奖复盘中心 (`/predictions-archive`) ⭐️核心模块
满足你**“查看我们的历史预测、对比真实开奖结果”**的需求：
1. **预测战绩总览看板**：
   * 累计预测期数、累计生成注数、总命中率（蓝球命中率、4红以上命中次数）、各策略模型（统计 vs 机器学习 vs AI Agent）的胜率横向对比柱状图。
2. **历史预测批次时间轴列表**：
   * 按目标期号倒序排列所有我们保存过的预测记录。
   * **状态标识**：若该期尚未开奖，显示 `待开奖 (Pending)`；若已开奖，显示當期真实开奖号码，并标注本批次最佳战绩（如 `命中 4+1 (四等奖)` 或 `命中 1+1 (六等奖)`）。
3. **预测 vs 真实开奖 逐注高亮比对卡片**：
   * 展开任意一个历史预测批次，展示当时预测的每一注号码：
   * **视觉高亮规则**：未命中的预测号码显示为暗灰色（Opacity 40%）；**命中的红球显示为高亮霓虹红并带发光边框，命中的蓝球显示为高亮电光蓝**，右侧直接标明 `命中 3 红 + 1 蓝 | 奖金 ¥10`。
4. **AI 赛后复盘报告（Post-Reflection）**：
   * 点击已开奖批次上的 `[生成 AI 复盘]`，系统将“当期预测时的 AI 理由”与“实际开奖号码”一起发给大模型，生成一份偏差分析报告（例如：“本期预判和值回落正确，但过度排斥了三区冷号，导致漏掉 29、32……”），持久化保存在数据库中。

### 4.4 视图四：模拟沙盒与组合计算器 (`/sandbox`)
* 提供一个随时验证心水号码的工具：手动输入任意 6 红 1 蓝（或复式号码），系统立即扫描数据库全部历史（3000+ 期），告诉你：**这组号码在历史上是否中过一/二等奖？最多中过几个球？它的各项数学特征处于历史前百分之多少的分位点？**

---

## 五、 核心算法与兑奖引擎逻辑设计

### 5.1 多维统计过滤算子 (Statistical Filters)
在生成候选号码时，后端通过流水线（Pipeline）计算以下核心数学公式：

1. **AC 值（Arithmetic Complexity，算术复杂度）**：
   给定 6 个红球 $R = \{r_1, r_2, r_3, r_4, r_5, r_6\}$，计算所有两两之差的绝对值集合 $D = \{|r_i - r_j| \mid 1 \le i < j \le 6\}$，记集合 $D$ 中不重复元素的个数为 $|D|$，则：
   $$AC = |D| - (6 - 1) = |D| - 5$$
   *过滤准则*：历史超过 $92\%$ 的开奖结果满足 $AC \ge 6$，直接剔除 $AC < 6$ 的规律性废号（如等差数列 `05,10,15,20,25,30`）。

2. **遗漏信息熵与冷热均衡度**：
   设每个红球 $i \in [1, 33]$ 当前连续未出现的期数为 $m_i$：
   * **热号**：$m_i \le 4$
   * **温号**：$5 \le m_i \le 9$
   * **冷号**：$m_i \ge 10$
   *过滤准则*：优先保留满足“热:温:冷”比例为 `3:2:1` 或 `4:1:1` 的组合，避免全选大冷号或全选极端热号。

### 5.2 自动兑奖判定矩阵 (Prize Verification Engine)
每当 `ssq_draw_history` 同步了新的一期开奖数据（假设期号为 `issue_no`），后端自动检索 `ssq_prediction_items` 中 `target_issue == issue_no` 且 `is_verified == False` 的所有记录。

设预测红球集合为 $P_{red}$，真实开奖红球集合为 $A_{red}$，预测蓝球为 $p_{blue}$，真实蓝球为 $a_{blue}$：
* 命中红球集合：$H_{red} = P_{red} \cap A_{red}$，命中红球数 $h_r = |H_{red}|$
* 命中蓝球标志：$h_b = \mathbb{I}(p_{blue} == a_{blue}) \in \{0, 1\}$

根据官方规则映射中奖等级 `prize_level`：

| 等级 (`prize_level`) | 命中条件 $(h_r, h_b)$ | 奖金计算逻辑 (`prize_amount`) |
| :--- | :--- | :--- |
| **1 (一等奖)** | $(6, 1)$ | 读取当期 `first_prize_amount` |
| **2 (二等奖)** | $(6, 0)$ | 读取当期 `second_prize_amount` |
| **3 (三等奖)** | $(5, 1)$ | 固定 $3,000$ 元 |
| **4 (四等奖)** | $(5, 0)$ 或 $(4, 1)$ | 固定 $200$ 元 |
| **5 (五等奖)** | $(4, 0)$ 或 $(3, 1)$ | 固定 $10$ 元 |
| **6 (六等奖)** | $(2, 1)$ 或 $(1, 1)$ 或 $(0, 1)$ | 固定 $5$ 元 |
| **0 (未中奖)** | 其他所有情况 | $0$ 元 |

---

## 六、 后端 RESTful API 接口设计

后端 FastAPI 统一提供以下核心接口供前端调用：

| 模块 | 方法 | 路径 | 功能描述 |
| :--- | :--- | :--- | :--- |
| **历史数据** | `POST` | `/api/v1/history/sync` | 爬取/同步最新历史开奖数据，计算特征并自动触发待兑奖预测核对 |
| **历史数据** | `GET` | `/api/v1/history/list` | 分页查询历史开奖列表（含关联的 `ssq_feature_metrics` 指标） |
| **历史数据** | `GET` | `/api/v1/history/trends` | 获取近 $N$ 期号码遗漏矩阵、和值分布、冷热统计数据（供 ECharts 渲染） |
| **预测中心** | `POST` | `/api/v1/predict/generate` | 传入策略类型与过滤参数，执行算法或调用 LLM 生成候选预测号码 |
| **预测中心** | `POST` | `/api/v1/predict/save` | 将生成的候选号码及 AI 分析报告持久化存入数据库 |
| **预测档案** | `GET` | `/api/v1/predict/batches` | 分页查询我们的**历史预测批次列表**（支持按期号、策略、中奖状态筛选） |
| **预测档案** | `GET` | `/api/v1/predict/batches/{id}` | 获取某次历史预测的详情（含每注号码、命中高亮明细、AI 推演与复盘记录） |
| **预测档案** | `POST` | `/api/v1/predict/verify/{issue}`| 手动触发指定期号的开奖结果比对与奖金核算 |
| **预测档案** | `POST` | `/api/v1/predict/reflect/{id}` | 针对已开奖的预测批次，调用 LLM Agent 生成赛后复盘总结并入库 |
| **预测档案** | `GET` | `/api/v1/predict/dashboard` | 获取历史预测总战绩统计（总投入、总回报、各模型命中率分布） |

---

## 七、 推荐项目目录结构 (Monorepo)

在你的 IDE 中新建一个文件夹，按以下结构组织前后端代码，干净清爽：

```text
discrete-sequence-quant-platform/
├── backend/                        # Python FastAPI 后端服务
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口与跨域配置
│   │   ├── database.py             # SQLite 数据库连接与 Session 管理
│   │   ├── models.py               # SQLAlchemy 4张核心表模型定义
│   │   ├── schemas.py              # Pydantic 请求与响应数据校验模型
│   │   ├── api/                    # 路由控制器 (history.py, predict.py)
│   │   └── services/
│   │       ├── crawler.py          # 历史开奖数据抓取与增量同步服务
│   │       ├── feature_engine.py   # AC值、和值、遗漏矩阵计算引擎
│   │       ├── predictor_stat.py   # 统计过滤与机器学习概率选号服务
│   │       ├── predictor_agent.py  # LLM Agent 提示词构建与流式推演服务
│   │       └── verifier.py         # 自动兑奖比对与虚拟盈亏核算引擎
│   ├── data/
│   │   └── ssq_quant.db            # SQLite 本地数据库文件
│   └── requirements.txt
├── frontend/                       # Vue3 前端工程
│   ├── src/
│   │   ├── api/                    # Axios 接口封装
│   │   ├── components/             # 号码球高亮组件、ECharts 图表容器
│   │   └── views/
│   │       ├── HistoryExplorer.vue # 历史开奖与走势分析页
│   │       ├── PredictLab.vue      # AI 预测生成实验室页
│   │       ├── PredictArchive.vue  # 历史预测档案与兑奖复盘页
│   │       └── SandboxCheck.vue    # 历史碰撞沙盒工具页
│   ├── package.json
│   └── vite.config.ts
└── ssq_ai_prediction_system_spec.md # 本规划文档
```

---

## 八、 工位分步实施计划 (Roadmap)

你可以按照以下 4 个阶段循序渐进地开发，每个阶段都能产出一个立竿见影的成果：

* **Phase 1：数据库建表与历史数据入库（约 1~2 小时）**
  * 使用 SQLAlchemy 初始化 `ssq_quant.db` 的 4 张表。
  * 编写 Python 脚本拉取过去 500 期（或全部历史）双色球开奖数据，自动计算出每期的和值、AC值、奇偶比、遗漏快照，填充进 `ssq_draw_history` 和 `ssq_feature_metrics`。
* **Phase 2：后端预测算子与自动兑奖闭环（约 2~3 小时）**
  * 实现统计过滤选号算法、自动兑奖比对函数（`verifier.py`），并通过 FastAPI 暴露出 REST 接口。
  * 用历史某一期做测试：先针对第 `2026100` 期生成一批预测存入数据库，然后调用兑奖接口，测试数据库是否正确更新了 `hit_red_count`、`hit_red_numbers` 和 `prize_level`。
* **Phase 3：前端可视化界面与历史预测看板搭建（约 3~4 小时）**
  * 搭建暗黑量化风格的 Web 界面，实现历史开奖表格、ECharts 走势图，以及最核心的**“历史预测 vs 真实开奖逐球高亮对比”**列表。
* **Phase 4：接入 LLM Agent 实现智能推演与自动复盘（进阶玩法）**
  * 接入 DeepSeek 或其他大模型 API，将近期统计特征序列化为结构化 Prompt，实现前端点击按钮即可实时观看 AI 分析号码走势、自动入库并在开奖后生成复盘反思报告。