# 进度日志

## 会话：2026-04-30（头脑风暴 + 设计）

### 阶段：设计（头脑风暴完成）

- **状态：** complete
- **开始时间：** 2026-04-30 12:05
- 执行的操作：
  - 探索项目目录（空项目）
  - 与用户讨论需求：事件输出、知识图谱、故事时间线、情节推动、KG 膨胀控制
  - 提出 3 种架构方案，选定**事件驱动型 Agent**
  - 分析 MemPalace 项目并决定集成
  - 讨论并确定：事件系统设计、Agent Core 交互、世界观版本化、分支时间线（Git 式）、多模型头脑风暴 + 漏斗机制、冲突合并
  - 确定 GUI 全交互、技术栈为 Web (FastAPI + React)
  - 讨论分布式：不需要，保持单体 + 接口清晰
  - 存储选型：PG→放弃→回归 MemPalace (ChromaDB + SQLite)
  - 补充：多模型按场景档位路由
  - 输出设计文档 `docs/2026-04-30-novelagent-design.md` v1
  - 撰写自审 + 用户审核
  - 分析 5 个外部 AI 模型提供的建议 → 提炼采纳 Planner 和快照机制
  - 更新设计文档：§4.10 Planner、§7 快照机制、§4.4 模型档位去具体型号、§4.5 Prompt Cache
  - 用户确认后进入实现规划阶段
- 创建/修改的文件：
  - `docs/2026-04-30-novelagent-design.md`（设计文档）
  - `task_plan.md`（实现任务规划）
  - `findings.md`（研究发现记录）
  - `progress.md`（本进度日志）
  - `tmp/mempalace/`（MemPalace 源码参考，调研用，可删除）

### 会话：2026-04-30（实现规划 + 文档完善）

- **状态：** complete
- **开始时间：** 2026-04-30（设计阶段后）
- 执行的操作：
  - 创建 `task_plan.md`，拆分 v0/v1/v2 三阶段实施计划
  - 创建 `findings.md`，记录 MemPalace 调研和外部建议精炼
  - 创建 `CLAUDE.md`，固化核心决策和项目配置
  - 补充设计文档：conda 环境管理、config/llm.json 配置格式、§12 项目规范（commit/review/测试/README 同步）
  - 创建 `README.md`，含当前进度表和快速开始
  - 创建 `.gitignore`
  - 创建 `memory/novelagent_project.md` 持久记忆
  - 分析 5 个外部模型建议 → 提炼高价值项写入文档
  - 定义 commit 规范：Conventional Commits + 中文描述
  - 定义测试规范：pytest + 核心模块 ≥85% 覆盖 + 提交前必跑
- 创建/修改的文件：
  - `CLAUDE.md`
  - `README.md`
  - `.gitignore`
  - `docs/2026-04-30-novelagent-design.md`（更新：conda、llm.json 配置、§12 项目规范）
  - `task_plan.md`（更新：测试规范、v0.5 任务调整）
  - `findings.md`（更新：测试策略）
  - `progress.md`（本次更新）
  - `memory/novelagent_project.md`

### v0：核心基础设施
- **状态：** 进行中（v0.1 完成）
- **v0.1 完成时间：** 2026-04-30
- **v0.1 执行的操作：**
  - 创建 `environment.yaml`（conda 环境定义，Python 3.11）
  - 创建三层 requirements（core.txt / dev.txt / optional.txt）
  - 创建 `pyproject.toml`（包配置 + pytest/ruff/mypy 设置）
  - 创建 9 个模块包目录 + `__init__.py` 入口
  - 创建 `tests/` 测试目录结构 + `conftest.py`
  - 创建 `config/llm.json` 配置模板（4 厂商 + 5 场景路由）
  - 完善 `.gitignore` 规则
  - 更新 `README.md` 进度状态
- 创建/修改的文件：
  - `environment.yaml`（新建）
  - `requirements/core.txt`（新建）
  - `requirements/dev.txt`（新建）
  - `requirements/optional.txt`（新建）
  - `pyproject.toml`（新建）
  - `src/novelagent/__init__.py` + 8 子包 `__init__.py`（新建）
  - `tests/__init__.py` + `conftest.py` + 4 个子目录 `__init__.py`（新建）
  - `config/llm.json`（新建）
  - `.gitignore`（更新）
  - `README.md`（更新进度状态）

---

## 测试结果
| 测试 | 输入 | 预期结果 | 实际结果 | 状态 |
|------|------|---------|---------|------|
| — | — | — | — | — |

## 错误日志
| 时间戳 | 错误 | 尝试次数 | 解决方案 |
|--------|------|---------|---------|
| — | — | — | — |

## 五问重启检查
| 问题 | 答案 |
|------|------|
| 我在哪里？ | v0.1 完成（conda 环境 + 脚手架 + requirements）|
| 我要去哪里？ | 下一步 v0.2：事件总线 + 事件类型定义 |
| 目标是什么？ | 构建 NovelAgent 小说生成框架 |
| 我学到了什么？ | 见 findings.md |
| 我做了什么？ | conda env + requirements 三层 + pyproject + 项目包结构 + 测试目录 + llm.json 配置模板 + .gitignore + README 更新 |

---

*每个阶段完成后或遇到错误时更新此文件*
