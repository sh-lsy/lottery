# 04. Git 提交与协同规范 (Git Commit Standards)

为了保证团队多人协同的高可读性与自动化版本管理，本项目严格采用 **Conventional Commits 1.0.0** 规范。

---

## 1. 提交信息结构

```text
<type>(<scope>): <subject>

[optional body]

[optional footer(s)]
```

### 1.1 Type 类型枚举
* `feat`: 新增功能特性（如：新增蓝球马尔可夫转移计算、新增5注保本预测策略）
* `fix`: 修复缺陷或逻辑漏洞（如：修复六等奖兑奖判定规则）
* `docs`: 仅文档变动（如：更新环境配置、表结构说明）
* `style`: 代码格式变动（空格、格式化，不影响代码逻辑）
* `refactor`: 重构（非新增功能也非修复 bug 的代码结构变动）
* `test`: 增加或修改测试用例（如：补充历史回测测试、对抗边界用例）
* `chore`: 杂项、构建流程或辅助工具配置（如：更新 `.gitignore`, `requirements.txt`）

### 1.2 Scope 作用域示例
* `crawler`: 数据抓取与同步模块
* `db`: 数据库模型、迁移与存储
* `features`: AC值、和值与遗漏特征引擎
* `predict`: 5注预测与蓝球置信度分配
* `verifier`: 兑奖比对与奖金核算
* `backtest`: 历史回测框架与报表
* `cli`: 命令行工具

### 1.3 示例示范
* `feat(crawler): 实现历史3519期真实开奖全量采集与断点增量更新`
* `feat(features): 支持AC值/和值/质合比/三区及全量遗漏矩阵快照计算`
* `docs(env): 补充D:\Miniconda3原生复用及新机一键配置说明`
* `test(e2e): 建立161项多层级自动化功能测试与回归测试用例`
