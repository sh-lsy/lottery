# 环境配置指南 (Environment Setup Guide)

本文档面向本项目开发者，详细说明在不同环境下的运行与依赖配置。

---

## 方式一：当前开发机（极速零配置运行）

当前本地路径已存在完备的科学计算与开发环境：`D:\Miniconda3`。
其 Python 3.13 base 环境中已预装本项目所需的所有核心依赖（`FastAPI`, `SQLAlchemy`, `Pandas`, `NumPy`, `Scikit-learn`, `SciPy`, `Requests`, `Pytest` 等）。

无需新建虚拟环境，直接运行以下命令即可检验或启动项目：

```powershell
# 验证 Python 版本与核心依赖
& "D:\Miniconda3\python.exe" -c "import fastapi, sqlalchemy, pandas, sklearn; print('All core modules loaded successfully!')"

# 执行测试用例
& "D:\Miniconda3\python.exe" -m pytest tests/unit -v

# 启动 CLI 辅助工具
& "D:\Miniconda3\python.exe" -m backend.app.cli --help
```

---

## 方式二：全新机器（从零配置新电脑）

如果代码克隆到了一台全新的电脑，请按照以下标准流程初始化：

### 1. 安装 Miniconda 或 Anaconda
推荐从清华大学镜像源下载并安装 Miniconda（Windows/Linux/macOS 均可）：
* 清华镜像站：https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/

### 2. 创建并激活独立虚拟环境
打开终端（Windows PowerShell 或 CMD），执行：
```bash
# 1. 创建指定 Python 3.10 或 3.11 的虚拟环境
conda create -n lottery python=3.10 -y

# 2. 激活虚拟环境
conda activate lottery

# 3. 进入项目根目录
cd discrete-sequence-quant-platform

# 4. 一键安装全部依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 初始化数据库与数据同步
在新机器上拉取全量历史数据并计算特征：
```bash
# 执行全量爬虫同步
python -m backend.app.cli sync-history

# 批量计算全部历史特征
python -m backend.app.cli compute-features
```

---

## 依赖清单说明

核心依赖已锁定在根目录 [requirements.txt](file:///d:/sy/lottery/requirements.txt) 中：
* `fastapi` & `uvicorn`：异步高性能后端 Web 服务
* `sqlalchemy` & `aiosqlite`：SQLite 关系型 ORM 与异步连接池
* `pandas` & `numpy`：特征矩阵计算与遗漏向量化处理
* `scikit-learn` & `scipy`：马尔可夫转移矩阵计算与统计检验
* `requests` & `httpx`：多数据源开奖数据采集引擎
* `pytest`：全自动 E2E 与单元回归测试框架
