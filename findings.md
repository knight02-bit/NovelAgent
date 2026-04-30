# 研究发现：NovelAgent 设计调研

## MemPalace 分析

**来源：** [MemPalace/mempalace](https://github.com/MemPalace/mempalace)

### 核心能力
- **知识图谱**：带时间窗口的实体-关系图（add_triple, query_entity, timeline, invalidate），SQLite 存储
- **4 层记忆栈**：L0 Identity (~100t), L1 Essential Story (~800t), L2 On-Demand, L3 Deep Search
- **语义搜索**：ChromaDB 后端，RAG 检索
- **结构化存储**：Wing → Room → Drawer 三级索引
- **MCP 工具**：29 个工具覆盖 KG/搜索/存储操作

### 集成方式
直接作为 pip 依赖引入，不修改其内核。映射关系：
- MemPalace Entity → 小说角色/地点/物品/组织
- MemPalace Triple → 角色关系/归属
- MemPalace Temporal → 故事情节时间线
- MemPalace L0-L3 → KG 膨胀控制（热区/温区/冷区）
- MemPalace Drawer → 事件持久化存储

### 注意事项
- MemPalace 的 KG 是通用设计，小说特定实体类型（faction, event_marker, concept）需扩展现有 schema
- L0-L3 的升降级策略是文件级，需要适配到角色/实体级

---

## 外部建议精炼（来自 5 个 AI 模型）

### 高价值采纳项

| 建议 | 来源 | 融入方式 |
|------|------|---------|
| Planner 层（目标驱动） | ChatGPT, DeepSeek, Gemini | 已加入 §4.10 |
| 快照机制 | DeepSeek, Gemini, MiroThinker | 已加入 §7 |
| 结构化输出强制 (Pydantic + Instructor) | Gemini, DeepSeek | 实现 LLM Provider 时整合 |
| 三阶段脑暴漏斗 | MiroThinker, ChatGPT | 实现 Brainstorming 时采用 |
| 叙事模板约束 | ChatGPT, DeepSeek, Gemini | v2 功能 |
| Debug 工具 | ChatGPT | v2 功能 |

### 暂缓项

| 建议 | 暂缓理由 |
|------|---------|
| Neo4j 替代 SQLite | 部署成本高，单机 SQLite 够用 |
| Event Sourcing + CQRS | 单用户无读写冲突问题 |
| Redis 做事件总线 | 单进程内不需要 |
| Docker Compose | v0 阶段启动越简单越好 |
| 读者模拟 Agent | 有趣但非核心功能 |
| GraphRAG | 实现复杂，RAG 在 v0 阶段足够 |

---

## 技术选型调研要点

### 前端可视化库
- **react-flow**：适合 DAG/流程图，轻量，社区活跃 → 分支时间线首选
- **vis-network / cytoscape**：适合知识图谱，支持大规模节点 → KG 面板首选
- **G6 (AntV)**：定制化强但学习成本高 → 暂缓

### 结构化输出库
- **Instructor** (Python)：Pydantic + 多种 LLM 后端，社区活跃 → 首选
- **Outlines**：更底层，支持 JSON Schema 约束 → 备选
- **LiteLLM**：多厂商统一 API → 可作为 LLM Provider 的底层实现

### LLM Cache 策略
- Anthropic: 显式 `cache_control` 标记，5 分钟 TTL
- OpenAI: Prompt Caching (自动)，5-10 分钟 TTL
- 语义缓存：相同语义的 KG 查询 → 直接返回缓存结果
- 批量聚簇：同一场景的 N 个请求同时发出，共享缓存前缀

---

## 测试策略

| 维度 | 要求 |
|------|------|
| 框架 | pytest + pytest-asyncio |
| 核心模块覆盖率 | ≥ 85% |
| 整体覆盖率 | ≥ 75% |
| LLM 调用 | 全部 mock（pytest fixture） |
| 测试数据 | 固定种子，可复现 |
| 提交前检查 | `pytest --cov` 确认不降覆盖率 |

| 决策 | 方案 | 替代考量 | 最终理由 |
|------|------|---------|---------|
| 存储 | MemPalace (ChromaDB + SQLite) | PostgreSQL + pgvector | 一致认证后改为"不用 PG"，回归 MemPalace |
| 分支 | 事件 DAG + 快照 | 纯 Git 式文件 Diff | 事件 DAG 与事件驱动架构自然统一 |
| 脑暴漏斗 | 多模型并行 → 过滤 → 选择 | 单模型多次采样 | 多模型带来更多样性 |
| GUI | Web (FastAPI + React) | Gradio, PyQt | 图可视化生态 + 跨平台 |
