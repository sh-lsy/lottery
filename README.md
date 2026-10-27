# 离散序列量化分析与预测平台 (SSQ-Quant-System)

基于多维统计学、机器学习与博弈论的双色球全量历史数据挖掘、5注保本预测策略与自动兑奖回测系统。

---

## 核心特性

1. **真实数据全量采集**：内置稳定官方/公开双数据源同步爬虫，已完整持久化自 2003 年创刊至今全部 **3,519 期** 真实开奖记录。
2. **多维统计特征工程**：全量预计算 AC 值（算术复杂度）、和值正态区间、跨度、11质数分布、奇偶比、三区比例及全量红蓝球动态遗漏快照。
3. **5注保本优化预测引擎**（进行中）：
   * **防守保底**：根据蓝球多模型置信度动态加权分配（如 3+2 分布），命中即回本（奖金 $\ge 10$ 元覆盖 5 注成本）；
   * **进攻大奖**：红球采用空间剪枝结合旋转矩阵（Wheel Matrix）聚集进攻一等奖与二等奖。
4. **历史时光机回测系统**（进行中）：支持任意历史期次自动兑奖核算与真实 ROI 策略对比评测。
5. **严谨工程标准**：单文件 SQLite 零运维依赖、Conventional Commits 提交规范、完备的模块化技术文档。

---

## 快速上手

### 1. 环境准备
使用本地现有环境（推荐 `D:\Miniconda3`）或通过虚拟环境运行，详见 [ENVIRONMENT_SETUP.md](file:///d:/sy/lottery/ENVIRONMENT_SETUP.md)：
```bash
pip install -r requirements.txt
```

### 2. 命令行操作
```bash
# 同步最新开奖数据
python -m backend.app.cli sync-history

# 重新计算特征矩阵
python -m backend.app.cli compute-features

# 执行全量自动化测试
pytest tests/
```

---

## 文档导航

* [环境配置指南 (ENVIRONMENT_SETUP.md)](file:///d:/sy/lottery/ENVIRONMENT_SETUP.md)
* [01. 数据库结构说明 (docs/01_database_schema.md)](file:///d:/sy/lottery/docs/01_database_schema.md)
* [02. 数据抓取与增量同步引擎 (docs/02_crawler_service.md)](file:///d:/sy/lottery/docs/02_crawler_service.md)
* [03. 多维数学特征工程引擎 (docs/03_feature_engineering.md)](file:///d:/sy/lottery/docs/03_feature_engineering.md)
* [04. Git 提交与协同规范 (docs/04_git_commit_standard.md)](file:///d:/sy/lottery/docs/04_git_commit_standard.md)
* [今日收尾与明日复工交接清单 (docs/CHECKPOINT_20261027.md)](file:///d:/sy/lottery/docs/CHECKPOINT_20261027.md)
