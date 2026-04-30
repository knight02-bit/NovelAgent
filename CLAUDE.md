# NovelAgent

## 项目阶段
当前在 **v0 实现**阶段。详见 `task_plan.md`。

## 核心决策（已定稿，勿重新讨论）
- **架构**：事件驱动 + Planner 层
- **存储**：MemPalace (ChromaDB + SQLite)，不使用 PostgreSQL
- **前端**：FastAPI + React Web 全栈
- **LLM**：抽象 Provider，场景→档位→模型路由，具体模型型号由使用者配置
- **分布式**：不做
- **环境**：conda + requirements.txt（分三层：核心/开发/可选）
- **LLM 配置**：`config/llm.json`，JSON 格式，区分厂商 + 场景路由 + 参数设置

## 关键设计文档
- `docs/2026-04-30-novelagent-design.md` — 完整架构设计
- `task_plan.md` — 实现任务拆分（v0 → v1 → v2）
- `findings.md` — 技术调研与决策记录
- `progress.md` — 进度日志

## v0 任务清单
1. conda 环境 + requirements.txt + 项目脚手架
2. 事件总线 + 事件类型定义
3. MemPalace 集成（基础存储）
4. 基础知识图谱（实体CRUD + 关系CRUD）
5. LLM Provider（单模型，硬编码配置）
6. Agent Core（事件循环 + prompt 组装）
7. 简单情节引擎（卷/章/节结构管理）
8. 基础 GUI（FastAPI + React：正文编辑 + KG 面板）
9. 端到端集成测试

## 测试覆盖要求
- **框架**：pytest + pytest-asyncio
- **覆盖率目标**：核心模块（core/、agent/、plot/）≥ 85%，整体 ≥ 75%
- **覆盖范围**：
  - 单元测试：事件总线、KG CRUD、LLM Provider、Agent Core 循环、Planner、情节引擎
  - 集成测试：事件发 → Agent 响应 → KG 更新 → GUI 展示 端到端流程
  - 分支测试：创建分支、切换分支、合并分支、冲突检测
  - LLM mock：所有 LLM 调用使用 pytest fixture mock，不依赖真实 API
- **每次提交前运行** `pytest --cov` 确认不降覆盖率
- **测试数据**：固定种子，可复现

## 用户偏好
- **commit 风格**：Conventional Commits，说明部分用中文。格式：`type(scope): 中文描述`
- **review 习惯**：按功能逻辑 review，核心模块（core/agent/plot）重点关注
- **提交前检查**：`pytest --cov` 确认不降覆盖率 + ruff lint 无新增错误
