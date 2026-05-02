# NovelAgent

一个事件驱动的 AI Agent 框架，用于辅助乃至主导小说生成。不同于代码 Agent，本框架以**事件**为核心输出，搭配知识图谱、多分支时间线、情节规划，全 GUI 交互。

## 当前进度

**阶段：v0 实现（MVP）**

| 任务 | 状态 |
|------|------|
| 0.1 conda 环境 + requirements.txt + 项目脚手架 | ✅ 完成 |
| 0.2 事件总线 + 事件类型定义 | ✅ 完成 |
| 0.3 MemPalace 集成（基础存储） | ✅ 完成 |
| 0.4 基础知识图谱（实体CRUD + 关系CRUD） | ✅ 完成 |
| 0.5 LLM Provider + config/llm.json 配置加载 | ✅ 完成 |
| 0.6 Agent Core（事件循环 + prompt 组装） | ⏳ 待开始 |
| 0.7 简单情节引擎（卷/章/节结构管理） | ⏳ 待开始 |
| 0.8 基础 GUI（FastAPI + React：正文编辑 + KG 面板） | ⏳ 待开始 |
| 0.9 端到端集成测试 | ⏳ 待开始 |

> 完整规划见 [task_plan.md](task_plan.md)，设计文档见 [docs/2026-04-30-novelagent-design.md](docs/2026-04-30-novelagent-design.md)

## 快速开始

```bash
# 1. 创建 conda 环境
conda create -n novel-agent python=3.11
conda activate novel-agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 LLM（复制模板后填入 API Key）
cp config/llm.example.json config/llm.json
# 编辑 config/llm.json 填入你的 API Key

# 4. 启动后端
python backend/main.py

# 5. 启动前端（新终端）
cd frontend && npm install && npm run dev
```

> 详细环境搭建见 `docs/dev-setup.md`（待补充）

## 项目结构

```
novel-agent/
├── config/          ← LLM 厂商配置（API Key / 模型路由）
├── backend/
│   ├── core/        ← 事件总线、事件存储、配置
│   ├── agent/       ← Agent Core、LLM Provider、Prompt 组装
│   ├── plot/        ← 情节引擎、Planner、伏笔追踪
│   ├── brainstorm/  ← 头脑风暴、一致性过滤
│   ├── merge/       ← 冲突合并
│   └── gui/         ← FastAPI 路由、WebSocket
├── frontend/        ← React GUI
├── docs/            ← 设计文档、手册
├── task_plan.md     ← 实现任务规划
├── progress.md      ← 进度日志
└── findings.md      ← 技术决策记录
```

## 架构概要

```
Planner (叙事目标) → 事件总线 → Agent Core → LLM Provider → 事件输出
                                   ↕              ↕
                              情节引擎    MemPalace (KG + 记忆栈)
```

事件驱动 + Planner 层，支持多分支时间线（类 Git）、多模型头脑风暴、知识图谱膨胀自动控制。

详见 [设计文档](docs/2026-04-30-novelagent-design.md)。

## 提交规范

```
feat(scope): 中文描述    # 新功能
fix(scope): 中文描述     # Bug 修复
docs(scope): 中文描述    # 文档
test(scope): 中文描述    # 测试
refactor(scope): 中文描述 # 重构
```

**提交前必做：** `pytest --cov` 确认覆盖率不降 + `ruff check` lint 无新增错误

## License

MIT
