# 自适应策略自我进化机制与闭环反馈算法设计

**文档编号**: `docs/07_adaptive_strategy_loop.md`  
**版本**: `2.0.0`  
**适用模块**: `backend/app/services/adaptive_service.py`, `backend/app/models.py`, `backend/app/api/adaptive.py`  
**核心概念**: 连续亏损反思触发 ($K_t \ge 3$)、冷热动量动态平移 ($\eta = 0.05$)、蓝球 3+2/5互异双模态切换、统计防线负反馈调节、不可变演进审计轨迹

---

## 1. 理论背景与自适应进化定位

在传统的彩票或随机离散序列推演系统中，模型超参数通常为静态硬编码（如固定冷温热打分权重与固定的红球和值筛选区间）。然而，实际开奖序列在不同历史阶段会呈现交替震荡的微观非对称性：
- **冷态聚集期**：冷码大遗漏频发，遗漏均值显著偏高；
- **动量聚集期**：热码连号集中回显，短遗漏频繁占优；
- **和值漂移期**：开奖号码重心阶段性向低位或高位偏移。

为了防止策略在特定震荡周期内陷入持续回撤，`SSQ-Quant-System` 引入了 **自适应策略自我进化闭环（Adaptive Strategy & Reflection Loop）**。

> [!NOTE]
> **理性数学期望约束**：
> 自适应反思机制并不试图违背彩票独立随机性与法定负期望本质（$E[X] = -50\%$），而是**在有限风险预算内实现对抗性动态再平衡（Adversarial Dynamic Rebalancing）**：当策略连续遭遇回撤时，自动抑制高风险集中配置、调降过拟合特征惩罚、自适应平移打分超参数，并在达成保本目标后即刻恢复稳健基准。

```
                    +------------------------------------+
                    |       官方当期真实开奖结果公布      |
                    +------------------------------------+
                                      |
                                      v
                    +------------------------------------+
                    |    VerifierService 自动化核奖比对   |
                    |   (计算 virtual_reward / cost)     |
                    +------------------------------------+
                                      |
                                      v
                    +------------------------------------+
                    |   Break-Even 判别与连续赤字计数     |
                    +------------------------------------+
                                 /          \
      [virtual_reward >= cost]  /            \  [virtual_reward < cost]
                               v              v
            +----------------------+     +----------------------+
            |    正向保本反馈      |     |     负向赤字反馈     |
            | - K_t 清零 (K_t = 0) |     | - K_t 累加 (K_t++)   |
            | - 恢复 CONCENTRATED  |     | - 判断 K_t >= 3 门限 |
            | - 重置和值防线基准   |     +----------------------+
            +----------------------+                |
                       \                 [触发门限 K_t >= 3]
                        \                           v
                         \               +----------------------+
                          \              |   执行策略自适应调节 |
                           \             | 1. 降级为 DISPERSED  |
                            \            | 2. 冷热权重动态平移  |
                             \           | 3. 和值防线负反馈漂移|
                              \          +----------------------+
                               \                    /
                                v                  v
                     +------------------------------------+
                     |    状态持久化与不可变演进审计日志   |
                     | - 更新 ssq_adaptive_state (单例)   |
                     | - 写入 ssq_adaptive_history (事件) |
                     +------------------------------------+
```

---

## 2. 连续未达标赤字计数器 ($K_t$) 与触发机制

### 2.1 赤字状态定义
设第 $t$ 期生成的 5 注预测方案中，总投入虚拟成本为 $C_t = 10\text{ 元}$，官方开奖核对后获得的派奖总额为 $R_t$。
定义单期保本指示函数：
$$I_t = \begin{cases} 1, & R_t \ge C_t \quad (\text{达成保本或盈利}) \\ 0, & R_t < C_t \quad (\text{未达标赤字}) \end{cases}$$

### 2.2 赤字连续计数更新公式
$$K_t = \begin{cases} 0, & \text{if } I_t = 1 \\ K_{t-1} + 1, & \text{if } I_t = 0 \end{cases}$$
其中 $K_0 = 0$。

### 2.3 自适应反思启动条件
系统维护可配置的赤字容忍门限 $\theta$（系统默认 $\theta = 3$）。
$$\text{Trigger}(t) \iff K_t \ge \theta$$
当 $K_t < \theta$ 时，系统记录常规赤字日志，保持基准策略参数；一旦 $K_t \ge \theta$，系统在核奖完成后即刻启动三大维度的自适应调节。

---

## 3. 动态权重自适应平移算法 ($\eta = 0.05$)

### 3.1 蓝球三模型集成打分结构
系统预设三大底层蓝球预测模型：
1. **冷码回补模型 (Hazard Omission Rate)**：权重记为 $w_1$（默认初始值 $0.40$）；
2. **状态转移模型 (1st-Order Markov Chain)**：权重记为 $w_2$（默认初始值 $0.35$）；
3. **动量趋势模型 (Frequency / MACD Momentum)**：权重记为 $w_3$（默认初始值 $0.25$）。

始终满足凸组合归一化约束：
$$\sum_{j=1}^3 w_j = 1.0, \quad w_j \in [0.15, 0.60]$$

### 3.2 近期开奖遗漏均值度量 ($\bar{m}$)
在第 $t$ 期触发反思时，系统回溯前 $W=5$ 期官方开奖蓝球的先验遗漏值 $m(b_{t-i})$，计算近 5 期中奖蓝球的历史遗漏均值：
$$\bar{m} = \frac{1}{W} \sum_{i=1}^W \text{omission}(b_{t-i})$$
理论随机期望均值 $\bar{m}_{\text{exp}} \approx 8.0$。

### 3.3 状态区间判定与学习率更新公式
设自适应学习率 $\eta = 0.05$。系统依据 $\bar{m}$ 将当前市场环境划分为三种状态机制：

1. **追热动量机制 (Hot Momentum Regime, $\bar{m} \le 4.0$)**：
   近期蓝球高度集中于短遗漏热码，说明热态动量正在持续主导。系统减少冷码权重，加大动量权重：
   $$\Delta w = \eta \cdot \left(1.0 - \frac{\bar{m}}{4.0}\right)$$
   $$w_3 \leftarrow \min(0.55, w_3 + \Delta w)$$
   $$w_1 \leftarrow \max(0.20, w_1 - \Delta w)$$

2. **大冷回补机制 (Cold Reversion Regime, $\bar{m} \ge 10.0$)**：
   近期蓝球呈现多期大冷码出号，说明系统正处于大遗漏破冰周期。系统增加冷态回补权重，削减动量权重：
   $$\Delta w = \eta \cdot \min\left(1.0, \frac{\bar{m} - 9.0}{10.0}\right)$$
   $$w_1 \leftarrow \min(0.60, w_1 + \Delta w)$$
   $$w_3 \leftarrow \max(0.15, w_3 - \Delta w)$$

3. **中性平衡机制 (Neutral Regime, $4.0 < \bar{m} < 10.0$)**：
   遗漏均值处于正常随机波动区间，权重保持稳定不发生跳变。

### 3.4 归一化与保底截断
在完成 $\Delta w$ 平移后，执行全量重归一化，严格保障数学凸组合恒等式：
$$w_j \leftarrow \frac{w_j}{\sum_{k=1}^3 w_k}, \quad \forall j \in \{1, 2, 3\}$$

---

## 4. 蓝球分配模式双向动态切换 (3+2 $\leftrightarrow$ 5-Distinct)

双色球预测中，蓝球命中单注即可派发 5 元（六等奖）。针对 5 注方案（成本 10 元），系统设计了两种博弈对决形态：

### 4.1 集中保本模式 (CONCENTRATED 3+2) —— 进攻防守兼备
- **分配拓扑**：
  - 第 1 置信度蓝球 $B_{(1)}$：分配给 **3 注**；
  - 第 2 置信度蓝球 $B_{(2)}$：分配给 **2 注**。
- **派奖博弈结构**：
  - 若命中 $B_{(1)}$：获得 $3 \times 5 = 15\text{ 元}$，净回报 $+5\text{ 元}$，单期实现稳健盈利；
  - 若命中 $B_{(2)}$：获得 $2 \times 5 = 10\text{ 元}$，净回报 $0\text{ 元}$，单期精准保本；
  - 蓝球覆盖范围仅为 2 个球，覆盖率 $P = 2/16 = 12.5\%$。

### 4.2 最大覆盖模式 (DISPERSED 5-Distinct) —— 避险防守基准
- **分配拓扑**：
  - 从置信度前 5 的蓝球集合 $\{B_{(1)}, B_{(2)}, B_{(3)}, B_{(4)}, B_{(5)}\}$ 中，各自分配给 1 注，互不重复。
- **派奖博弈结构**：
  - 蓝球覆盖率高达 $P = 5/16 = 31.25\%$；
  - 命中任意蓝球时，获得 $1 \times 5 = 5\text{ 元}$，虽亏损 5 元但可回收 50% 成本，显著收窄本金回撤。

### 4.3 动态切换准则
1. **赤字降级切换 (Downshift)**：
   当连续赤字 $K_t \ge 3$ 时，系统判定当前模型对单一蓝球的置信度发生漂移，立即从 `CONCENTRATED` 自动降级为 `DISPERSED` 模式，提高下期蓝球命中概率至 31.25%，优先规避归零风险。
2. **保本升级恢复 (Upshift)**：
   当下期出现 $R_t \ge C_t$（实现保本或更高奖级）时，系统判定策略有效性回归，立刻自动升级恢复为 `CONCENTRATED` 模式，捕获集中派奖的非对称超额收益。

---

## 5. 多维特征偏差负反馈与统计防线自愈

在每期核对后，系统不仅度量中奖等级，还精准计算预测集合与真实开奖之间的四维有向偏差向量：

### 5.1 偏差向量度量
设预测批次中 5 注红球集合为 $\mathbf{P}_1, \dots, \mathbf{P}_5$，真实开奖红球集合为 $\mathbf{A}$：
1. **和值偏差 (Sum Deviation)**：
   $$\Delta_{\text{sum}} = \frac{1}{5} \sum_{j=1}^5 \text{sum}(\mathbf{P}_j) - \text{sum}(\mathbf{A})$$
2. **奇数偏差 (Odd Deviation)**：
   $$\Delta_{\text{odd}} = \frac{1}{5} \sum_{j=1}^5 \text{odd}(\mathbf{P}_j) - \text{odd}(\mathbf{A})$$
3. **热码个数偏差 (Hot Deviation)**：
   $$\Delta_{\text{hot}} = \frac{1}{5} \sum_{j=1}^5 \text{hot}(\mathbf{P}_j) - \text{hot}(\mathbf{A})$$
4. **冷码个数偏差 (Cold Deviation)**：
   $$\Delta_{\text{cold}} = \frac{1}{5} \sum_{j=1}^5 \text{cold}(\mathbf{P}_j) - \text{cold}(\mathbf{A})$$

### 5.2 统计防线负反馈调节与对称饱和截断 (Symmetric Saturation Clamp)
当和值偏差显著超出正常波动（$|\Delta_{\text{sum}}| \ge 15.0$）时，系统自动对红球和值筛选防线 $[S_{\min}, S_{\max}]$ 进行反向漂移修正：

1. **漂移量计算与对称截断**：
   $$\text{shift} = \text{round}(\Delta_{\text{sum}} \times 0.25)$$
   $$\text{sum\_bias} \leftarrow \text{clamp}(\text{sum\_bias} + \text{shift}, -30.0, +30.0)$$
   严格将偏置量约束在 $[-30.0, +30.0]$ 对称饱和区间内。

2. **双向防线区间截断与零倒置数学证明**：
   为彻底杜绝长期单向亏损导致的区间倒置（$S_{\min} > S_{\max}$），系统建立双向界限约束：
   $$S_{\min} = \min(80, \max(65, 75 - \lfloor\text{sum\_bias} \times 0.5\rfloor))$$
   $$S_{\max} = \max(115, \min(145, 135 - \lfloor\text{sum\_bias} \times 0.5\rfloor))$$

   **数学不变性证明 (Invariant Proof)**：
   $$\sup(S_{\min}) = 80 < 115 = \inf(S_{\max})$$
   $$\forall \text{sum\_bias} \in \mathbb{R}, \quad S_{\min} \le 80 < 115 \le S_{\max} \implies S_{\min} < S_{\max}$$
   在任意极限赤字轮数下，和值筛选防线均严格满足区间有效性，永无倒置可能。

3. **自愈复位 (Self-Healing Reset)**：
   一旦单期重新达成保本（$R_t \ge C_t$），系统自动将偏置清零：
   $$\text{sum\_bias} \leftarrow 0.0, \quad S_{\min} \leftarrow 75, \quad S_{\max} \leftarrow 135$$

---

## 6. 存储设计与不可变演进审计轨迹

系统在 SQLite 中采用“**当前工作态 + 历史演进流**”的双表模式，兼顾高频读写性能与完整历史可追溯性。

### 6.1 单例当前状态表 (`ssq_adaptive_state`)
持久化存储系统当前处于生效状态的唯一配置记录（`id=1`）：
```sql
CREATE TABLE IF NOT EXISTS ssq_adaptive_state (
    id INTEGER PRIMARY KEY,
    consecutive_deficit_count INTEGER NOT NULL DEFAULT 0,
    current_blue_mode VARCHAR(30) NOT NULL DEFAULT 'CONCENTRATED',
    current_strategy_mode VARCHAR(50) NOT NULL DEFAULT 'CONCENTRATED_BREAK_EVEN',
    loss_threshold INTEGER NOT NULL DEFAULT 3,
    hot_momentum_weight FLOAT NOT NULL DEFAULT 0.25,
    cold_reversion_weight FLOAT NOT NULL DEFAULT 0.40,
    markov_weight FLOAT NOT NULL DEFAULT 0.35,
    temperature_tau FLOAT NOT NULL DEFAULT 0.85,
    sum_bias FLOAT NOT NULL DEFAULT 0.0,
    odd_bias FLOAT NOT NULL DEFAULT 0.0,
    ac_min_override INTEGER NOT NULL DEFAULT 6,
    sum_range_min INTEGER NOT NULL DEFAULT 75,
    sum_range_max INTEGER NOT NULL DEFAULT 135,
    last_trigger_issue VARCHAR(20),
    last_trigger_reason TEXT,
    evolution_version INTEGER NOT NULL DEFAULT 1,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### 6.2 不可变演进轨迹审计表 (`ssq_adaptive_history`)
每次触发参数调整、模式升降级或基准复位时，向该表插入一条只读不可变记录，完整记录变更前后的 JSON 快照：
```sql
CREATE TABLE IF NOT EXISTS ssq_adaptive_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger_issue VARCHAR(20) NOT NULL,
    trigger_reason VARCHAR(100) NOT NULL,
    streak_length INTEGER NOT NULL DEFAULT 0,
    pre_state_json TEXT NOT NULL DEFAULT '{}',
    post_state_json TEXT NOT NULL DEFAULT '{}',
    metrics_deviation_json TEXT NOT NULL DEFAULT '{}',
    reflection_notes TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_adaptive_hist_issue ON ssq_adaptive_history(trigger_issue DESC);
```

---

## 7. 单元测试与极端对抗验证结论

自适应闭环在 `tests/unit/test_adaptive_service.py` 及 `tests/m6_adversarial_stress.py` 中通过了严格的极限量化断言测试：
1. **$K_t \ge 3$ 触发断言**：在模拟连续 1、2 期亏损时不触发，第 3 期精准触发模式切换并记录历史。
2. **冷热动量平移断言**：在 $\bar{m} \le 4$ 条件下成功向动量平移，在 $\bar{m} \ge 10$ 条件下成功向冷态平移，凸组合和恒为 1.0。
3. **极端 50 轮连续赤字漂移压力测试**：
   - 输入连续 50 轮 $\Delta_{\text{sum}} = +50.0$，`sum_bias` 稳定饱和于 `+30.0`，区间收缩至 `[65, 120]`；
   - 输入连续 50 轮 $\Delta_{\text{sum}} = -50.0$，`sum_bias` 稳定饱和于 `-30.0`，区间收缩至 `[80, 145]`；
   - 全过程无异常抛出，无区间交叉倒置。
4. **单期保本自愈复位断言**：在极端偏置后注入一次保本批次，系统瞬间完成 `sum_bias = 0.0`、防线回归 `[75, 135]` 及蓝球恢复 `CONCENTRATED` 模式。
