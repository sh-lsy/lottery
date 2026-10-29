# FastAPI RESTful API 服务接口与高并发性能架构规范

**文档编号**: `docs/06_fastapi_restful_api.md`  
**版本**: `2.0.0`  
**适用模块**: `backend/app/main.py`, `backend/app/schemas.py`, `backend/app/api/`, `backend/app/services/collision_cache.py`  
**技术栈**: FastAPI + Starlette + Pydantic v2 + SQLAlchemy 2.0 (WAL SQLite) + NumPy

---

## 1. 架构总览与服务生命周期

`SSQ-Quant-System` 后端服务基于 FastAPI 构建，遵循完全解耦的领域驱动与分层服务架构：
1. **纯本地离线优先计算**：核心预测推演依赖本地统计学、一阶马尔可夫链与组合旋转矩阵算法，在无网络或无外部大模型 API Key 状态下即可在 **50~80ms** 内生成 5 注推荐方案。
2. **异步应用生命周期（Lifespan Management）**：在服务启动时自动触发 SQLite WAL 模式校验、数据库表结构初始化注册，并预热单例缓存 `CollisionCache`；在服务关闭时平稳释放持久连接。
3. **CORS 与跨域安全策略**：内置 Starlette `CORSMiddleware`，支持 Vite 代理跨域与纯前端生产打包独立托管调用。
4. **统一异常捕获与校验规范**：集成 Pydantic v2 参数校验器与全局 `ValueError` 异常处理器，将业务逻辑冲突与非法输入映射为标准的 `400 Bad Request` 或 `422 Unprocessable Entity`。

```
+-----------------------------------------------------------------------------------------+
|                                    Client Request                                       |
|                  (Vue 3 Dark Quant Terminal / CLI / Python SDK)                         |
+-----------------------------------------------------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
|                                  FastAPI Core Gateway                                   |
|   - CORS Middleware (allow_origins=["*"])                                               |
|   - Exception Handlers (ValueError -> 400, RequestValidationError -> 422)               |
|   - Lifespan Hook: init_db() & CollisionCache.get_instance().ensure_loaded(db)          |
+-----------------------------------------------------------------------------------------+
       |                           |                            |                        |
       v                           v                            v                        v
+---------------+          +---------------+            +---------------+        +---------------+
| /history/*    |          | /predict/*    |            | /backtest/*   |        | /adaptive/*   |
| 历史走势看板  |          | 量化预测实验室|            | 碰撞沙盒与回测|        | 自适应策略反馈|
+---------------+          +---------------+            +---------------+        +---------------+
       |                           |                            |                        |
       +---------------------------+----------------------------+------------------------+
                                             |
                                             v
                       +-------------------------------------------+
                       |              Service Layer                |
                       |  - CrawlerService     - FeatureEngine     |
                       |  - PredictorService   - VerifierService   |
                       |  - BacktestRunner     - AdaptiveService   |
                       |  - CollisionCache (Sub-10ms In-Memory)    |
                       +-------------------------------------------+
                                             |
                                             v
                       +-------------------------------------------+
                       |         Storage Layer (SQLite WAL)        |
                       |  ssq_draw_history     ssq_feature_metrics |
                       |  ssq_pred_batches     ssq_pred_items      |
                       |  ssq_adaptive_state   ssq_adaptive_hist   |
                       +-------------------------------------------+
```

---

## 2. CollisionCache 毫秒级历史全量碰撞性能架构

### 2.1 性能瓶颈分析与解决之道
在双色球历史碰撞沙盒（Sandbox Collision）中，用户输入 1 注红蓝球组合后，系统需对历史上全部 **3,519+ 期** 真实开奖记录及特征数据进行全量遍历匹配，判别 1~6 等奖的中奖次数、历史最高奖级、累计派发奖金及该注特征在历史分布中的四维分位数（Sum, AC, Span, Odd/Even）。

- **原始方案缺陷（ORM 遍历）**：在每次 HTTP 请求中通过 SQLAlchemy 查询 3,519 条 `DrawHistory` 与 3,519 条 `FeatureMetrics`，存在 7,038 次 ORM 对象实例化与反序列化，导致接口耗时高达 **122ms ~ 187ms**（平均 142.62ms），严重违反前端交互 `<50ms` 的性能契约。
- **CollisionCache 优化架构**：
  1. **常驻内存单例与双重检查锁（Double-Checked Locking）**：使用 `threading.Lock()` 保障多工作线程并发环境下的安全懒加载与单例生命周期。
  2. **轻量紧凑元组存储（Compact Tuples）**：抛弃繁重 ORM 映射，开辟内存紧凑列表：
     $$\text{Record} = (issue\_no, draw\_date, reds\_list, frozenset(reds), blue, first\_amount, second\_amount)$$
  3. **基于 frozenset 的 $O(1)$ 极速集合求交**：计算 6 个预测红球与历史开奖红球的重合个数时，直接调用 `len(ticket_red_set & row_red_fset)`，规避数组遍历循环。
  4. **NumPy 1D Float64 向量化分位数计算**：将历史和值、AC值、跨度、奇数个数预转为连续存储的 NumPy 数组（`cached_sums`, `cached_acs`, `cached_spans`, `cached_odds`），计算百分位时采用向量化无循环统计：
     $$P(x) = \frac{\text{np.count\_nonzero}(arr \le x)}{N} \times 100.0$$
  5. **主动失效机制（Cache Invalidation）**：在调用 `/api/v1/history/sync` 成功爬取到新期次时，自动触发 `CollisionCache.get_instance().invalidate()`，确保下次查询平滑重载最新数据，杜绝数据陈旧问题。

### 2.2 实测延迟基准（Empirical Benchmark）
在 3,519 期全量数据集上的 20 次对抗压力测试结果：
- **最小延迟**：`7.78 ms`
- **中位数延迟**：`8.48 ms`
- **平均延迟**：`8.48 ms`（相比优化前提升 **16.8 倍**）
- **P95 延迟**：`9.60 ms`
- **最大延迟**：`9.60 ms`（完全控制在 10ms 以内）

---

## 3. Pydantic v2 数据模型规范体系

所有入参与出参均采用 Pydantic v2（`backend/app/schemas.py`）严格定义，核心模型分类如下：

### 3.1 基础通用响应规范
```python
class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Optional[Any] = None

class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[Any]
```

### 3.2 预测单注与批次模型
```python
class PredictionNoteItem(BaseModel):
    note_index: int = Field(..., ge=1, le=5, description="1~5注序号")
    reds: List[int] = Field(..., min_length=6, max_length=6, description="6个互异红球 (1~33)")
    blue: int = Field(..., ge=1, le=16, description="1个蓝球 (1~16)")
    confidence_score: float = 0.0
    rationale: Optional[str] = None
    sum_red: Optional[int] = None
    ac_value: Optional[int] = None
    odd_count: Optional[int] = None
    span_red: Optional[int] = None

    @field_validator("reds")
    @classmethod
    def validate_reds(cls, v: List[int]) -> List[int]:
        if len(set(v)) != 6:
            raise ValueError("All 6 red balls must be distinct.")
        if any(r < 1 or r > 33 for r in v):
            raise ValueError("Red balls must be in range 1..33.")
        return sorted(v)

class PredictionSaveRequest(BaseModel):
    target_issue: str
    strategy_type: str = "CONCENTRATED_BREAK_EVEN"
    model_name: Optional[str] = "Ensemble-Hazard-Markov-Momentum"
    filter_params: Optional[Dict[str, Any]] = None
    ai_reasoning_md: Optional[str] = None
    notes: List[PredictionNoteItem]
    virtual_cost: int = 10

    @field_validator("notes")
    @classmethod
    def validate_5_notes(cls, v: List[PredictionNoteItem]) -> List[PredictionNoteItem]:
        if len(v) != 5:
            raise ValueError("A prediction batch must contain exactly 5 notes.")
        return v
```

### 3.3 碰撞沙盒模型
```python
class SandboxCollisionRequest(BaseModel):
    reds: List[int] = Field(..., min_length=6, max_length=6)
    blue: int = Field(..., ge=1, le=16)

class QuantileMetricItem(BaseModel):
    metric_name: str
    ticket_value: float
    historical_mean: float
    historical_min: float
    historical_max: float
    percentile: float
    evaluation: str
```

---

## 4. RESTful 路由清单与详细接口规约

### 4.1 历史数据与多维走势看板路由 (`/api/v1/history`)

| 路径 (Method & Path) | 别名 (Alias) | 功能描述 | 请求参数 / Body | 返回模型 |
|---|---|---|---|---|
| `GET /api/v1/history/draws` | `/list` | 分页查询历史开奖记录，支持双向排序、期号范围与号码包含过滤 | `page=1`, `page_size=20`, `order=desc`, `start_issue`, `end_issue`, `search_ball` | `DrawPaginationResponse` |
| `GET /api/v1/history/latest` | 无 | 获取官方最新一期开奖完整数据与特征 | 无 | `DrawRecordItem` |
| `GET /api/v1/history/metrics` | 无 | 获取近 $N$ 期核心特征指标时序 | `limit=100` (1~500) | `List[FeatureMetricsItem]` |
| `GET /api/v1/history/metrics/{issue_no}` | 无 | 查询指定期号的多维特征指标 | 路径参数: `issue_no` | `FeatureMetricsItem` |
| `GET /api/v1/history/omissions` | `/trends` | 获取近 $N$ 期红蓝球全量遗漏矩阵、冷温热划分及前三排行 | `limit=30` (10~100) | `OmissionTrendResponse` |
| `GET /api/v1/history/distributions` | 无 | 统计历史和值、AC值、跨度、奇偶、三区的频次分布 | `limit=100` (10~500) | `IndicatorDistributionResponse` |
| `POST /api/v1/history/sync` | 无 | 触发官方开奖增量/全量同步与特征计算，自动使缓存失效并自动核奖 | Body: `SyncRequest(force=False, auto_verify=True)` | `SyncResponseData` |

#### 接口示例：`GET /api/v1/history/draws?page=1&page_size=2`
```json
{
  "total": 3519,
  "page": 1,
  "page_size": 2,
  "total_pages": 1760,
  "items": [
    {
      "id": 3519,
      "issue_no": "2026122",
      "draw_date": "2026-10-25",
      "weekday": 7,
      "reds": [3, 7, 12, 19, 24, 31],
      "blue": 9,
      "red_seq_str": "03,07,12,19,24,31",
      "sales_amount": 395123400,
      "pool_amount": 2981502300,
      "first_prize_num": 8,
      "first_prize_amount": 6250000,
      "second_prize_num": 120,
      "second_prize_amount": 185000,
      "metrics": {
        "issue_no": "2026122",
        "sum_red": 96,
        "span_red": 28,
        "ac_value": 7,
        "odd_count": 4,
        "prime_count": 4,
        "zone1_count": 2,
        "zone2_count": 2,
        "zone3_count": 2,
        "consecutive_groups": 0,
        "repeat_prev_red": 1,
        "missing_sum_red": 32,
        "missing_blue": 5
      }
    }
  ]
}
```

---

### 4.2 本地量化策略预测与档案中心路由 (`/api/v1/predict`)

| 路径 (Method & Path) | 功能描述 | 请求参数 / Body | 返回模型 | 性能指标 |
|---|---|---|---|---|
| `POST /api/v1/predict/generate` | 纯本地离线秒级执行 5 注量化预测，输出候选胆拖池、蓝球概率分布、博弈保本矩阵及数学决策依据 | Body: `PredictionGenerateRequest` (包含目标期号、策略模式、统计防线阈值、自适应控制开关) | `PredictionGenerateResponse` | **< 100ms** (纯离线数学运算) |
| `POST /api/v1/predict/save` | 将 5 注候选号码方案与策略超参数持久化保存至数据库 | Body: `PredictionSaveRequest` (严格约束 5 注) | `PredictionSaveResponse` | **< 20ms** |
| `GET /api/v1/predict/batches` | 分页查询历史已生成的预测批次列表 | `page=1`, `page_size=20`, `status=ALL\|PENDING\|VERIFIED` | `PaginatedResponse` | **< 15ms** |
| `GET /api/v1/predict/batches/{id}` | 查询单次预测批次的 5 注明细及开奖高亮比对结果 | 路径参数: `id` (int) | `PredictionBatchDetail` | **< 15ms** |
| `GET /api/v1/predict/dashboard` (别名 `/summary`) | 统计预测系统全局累计胜率、虚拟回报、单期保本率及蓝球命中率 | 无 | `PredictDashboardResponse` | **< 25ms** |

#### 接口示例：`POST /api/v1/predict/generate`
```json
// Request Body
{
  "target_issue": "2026123",
  "strategy_type": "CONCENTRATED_BREAK_EVEN",
  "adaptive_enabled": true,
  "sum_min": 75,
  "sum_max": 135,
  "ac_min": 6,
  "span_min": 18,
  "span_max": 30,
  "save_to_db": false
}

// Response Body
{
  "target_issue": "2026123",
  "strategy_type": "CONCENTRATED_BREAK_EVEN",
  "model_name": "Ensemble-Hazard-Markov-Momentum",
  "total_notes": 5,
  "notes": [
    {
      "note_index": 1,
      "reds": [4, 8, 15, 19, 26, 31],
      "blue": 12,
      "confidence_score": 0.92,
      "sum_red": 103,
      "ac_value": 7,
      "odd_count": 3,
      "span_red": 27
    },
    {
      "note_index": 2,
      "reds": [4, 8, 12, 17, 23, 30],
      "blue": 12,
      "confidence_score": 0.89,
      "sum_red": 94,
      "ac_value": 8,
      "odd_count": 2,
      "span_red": 26
    },
    {
      "note_index": 3,
      "reds": [4, 8, 16, 21, 28, 33],
      "blue": 12,
      "confidence_score": 0.87,
      "sum_red": 110,
      "ac_value": 7,
      "odd_count": 3,
      "span_red": 29
    },
    {
      "note_index": 4,
      "reds": [5, 9, 14, 18, 25, 32],
      "blue": 3,
      "confidence_score": 0.83,
      "sum_red": 103,
      "ac_value": 7,
      "odd_count": 3,
      "span_red": 27
    },
    {
      "note_index": 5,
      "reds": [3, 7, 13, 20, 27, 29],
      "blue": 3,
      "confidence_score": 0.81,
      "sum_red": 99,
      "ac_value": 8,
      "odd_count": 4,
      "span_red": 26
    }
  ],
  "candidate_pool": {
    "cores": [4, 8],
    "satellites": [12, 15, 16, 17, 19, 21, 23, 26]
  },
  "blue_probabilities": [
    {"ball": 12, "probability": 0.38, "rank": 1},
    {"ball": 3, "probability": 0.29, "rank": 2},
    {"ball": 7, "probability": 0.12, "rank": 3}
  ],
  "break_even_matrix": {
    "concentrated_blue_1": 12,
    "concentrated_blue_2": 3,
    "allocation": "3 + 2",
    "top_hit_payout": 15,
    "second_hit_payout": 10,
    "min_payoff_on_hit": 10
  },
  "ai_reasoning_md": "采用集中保本 3+2 加权结构：前 3 注聚焦第一置信度蓝球 12（命中即返 15 元覆盖 10 元成本并盈利 5 元），后 2 注对冲第二置信度蓝球 03（命中即返 10 元平本）。"
}
```

---

### 4.3 碰撞沙盒、核奖与历史回测路由 (`/api/v1/backtest`)

| 路径 (Method & Path) | 别名 (Alias) | 功能描述 | 请求参数 / Body | 返回模型 | 性能指标 |
|---|---|---|---|---|---|
| `POST /api/v1/backtest/sandbox/collision` | `/sandbox` | 用户自定义 6 红 1 蓝方案历史 3,500+ 期全量即时碰撞 | Body: `SandboxCollisionRequest` | `SandboxCollisionResponse` | **< 10ms (实测 8.48ms)** |
| `POST /api/v1/backtest/verify/{issue_no}` | 无 | 针对已开奖期次自动核奖，计算奖金并触发自适应进化闭环 | 路径参数: `issue_no`, Body: `VerifyIssueRequest(force=False)` | `VerifyIssueResponse` | **< 30ms** |
| `POST /api/v1/backtest/run` | 无 | 历史时序无未来函数滑动窗口回测 | Body: `BacktestRunRequest(n_issues=100, strategy="CONCENTRATED_BREAK_EVEN")` | `BacktestResult` | **< 1s** |
| `POST /api/v1/backtest/compare` | 无 | 集中保本 vs 分散基准双策略横向回测对比 | Body: `BacktestCompareRequest(n_issues=100)` | `StrategyComparisonReport` | **< 2s** |

#### 接口示例：`POST /api/v1/backtest/sandbox/collision`
```json
// Request Body
{
  "reds": [3, 7, 12, 19, 24, 31],
  "blue": 9
}

// Response Body
{
  "ticket_reds": [3, 7, 12, 19, 24, 31],
  "ticket_blue": 9,
  "total_draws_analyzed": 3519,
  "highest_prize_level": 1,
  "highest_prize_name": "一等奖 (Jackpot)",
  "best_prize_issue": "2026122",
  "total_historical_payout": 6251260,
  "hypothetical_cost": 7038,
  "hypothetical_net_profit": 6244222,
  "hypothetical_roi": 887.21,
  "prize_counts": {
    "Level_1": 1,
    "Level_2": 0,
    "Level_3": 0,
    "Level_4": 3,
    "Level_5": 38,
    "Level_6": 215,
    "Miss": 3262
  },
  "quantile_metrics": [
    {
      "metric_name": "Sum_Red (红球和值)",
      "ticket_value": 96.0,
      "historical_mean": 102.8,
      "historical_min": 21.0,
      "historical_max": 183.0,
      "percentile": 39.42,
      "evaluation": "正常中位区间 (30%~70%)"
    },
    {
      "metric_name": "AC_Value (数字复杂度)",
      "ticket_value": 7.0,
      "historical_mean": 6.8,
      "historical_min": 1.0,
      "historical_max": 10.0,
      "percentile": 62.15,
      "evaluation": "优选离散度 (AC >= 6)"
    }
  ]
}
```

---

### 4.4 自适应策略自我进化路由 (`/api/v1/adaptive`)

| 路径 (Method & Path) | 别名 (Alias) | 功能描述 | 请求参数 / Body | 返回模型 |
|---|---|---|---|---|
| `GET /api/v1/adaptive/status` | `/state` | 获取当前自适应策略超参数、连续未达标期数、冷热权重及蓝球分配模式 | 无 | `AdaptiveStateResponse` |
| `GET /api/v1/adaptive/trajectory` | 无 | 获取自适应策略历史演变事件轨迹（只读审计日志） | `limit=50` (1~200) | `AdaptiveTrajectoryResponse` |
| `POST /api/v1/adaptive/trigger` | 无 | 手动强制或按阈值触发自适应反馈演化反思 | Body: `AdaptiveTriggerRequest(force=True)` | `AdaptiveStateResponse` |
| `POST /api/v1/adaptive/reset` | 无 | 重置自适应超参数至基准初始状态 (0.40, 0.35, 0.25) 并恢复 CONCENTRATED 模式 | 无 | `AdaptiveStateResponse` |

---

### 4.5 健康检查与系统自检路由 (`/`)

- `GET /`: 返回服务基础心跳与版本号 `2.0.0`。
- `GET /api/health` 与 `GET /api/v1/health`: 返回数据库连接状态、当前全量开奖期数统计（3,519+）、最新开奖期号及历史预测批次总数。

---

## 5. 交互式文档与接口调试

FastAPI 自动生成并暴露符合 OpenAPI 3.1.0 标准的交互式文档：
- **Swagger UI 界面**：`http://localhost:8000/docs`
- **ReDoc 界面**：`http://localhost:8000/redoc`
- **OpenAPI Schema JSON**：`http://localhost:8000/openapi.json`
