# NovelAgent 框架设计文档

> 日期: 2026-04-30
> 状态: 设计稿 v1

---

## 1. 设计目标

构建一个 AI Agent 框架，用于辅助乃至主导小说生成。不同于代码 Agent，本框架：

- 输出形式为**事件**（系统事件 + 叙事事件）
- 核心基础设施是**知识图谱**，管理角色、地点、物品、关系
- 具备**故事时间线**管理能力
- 能够主动**推动情节**前进
- 知识图谱达到一定规模时具备自动**剪枝/降级**能力
- 支持**多分支时间线**（类 Git 分支管理）
- 全 **GUI 交互**

---

## 2. 技术选型

| 项目 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.10+ | LLM 生态最成熟 |
| Web 框架 | FastAPI | 异步原生，类型安全 |
| 前端 | React + 图可视化库 | 分支 DAG、知识图谱等复杂交互 |
| 存储 | MemPalace (ChromaDB + SQLite)<br />[MemPalace/mempalace at main](https://github.com/MemPalace/mempalace/tree/main) | KG、L0-L3 栈、语义搜索开箱即用 |
| LLM 接入 | 抽象 Provider 层 | 支持多厂商多模型按场景切换 |
| 分布式 | 不做 | 单机异步并发足够，数据规模小 |

---

## 3. 整体架构

```
                         ┌──────────────────────────┐
                         │          Planner           │
                         │   (叙事目标规划)            │
                         └──────────┬───────────────┘
                                    │ NarrativeIntent
                         ┌──────────▼───────────────┐
                         │       事件总线             │
                         │    (支持分支标记)           │
                         └──┬──┬──┬──┬──┬──┬──┬─────┘
                            │  │  │  │  │  │  │
         ┌──────────────────┘  │  │  │  │  │  └────────────────┐
         │                     │  │  │  │  │                   │
    ┌────▼─────┐        ┌─────▼──▼──▼──▼──▼──────┐     ┌─────▼──────┐
    │ Agent    │        │   事件存储(DAG)          │     │ 情节引擎    │
    │ Core     │        │   可分支/可合并/可重放    │     │ (Plot      │
    └────┬─────┘        └───────────┬──────────────┘     │  Engine)   │
         │                          │                     └────┬───────┘
    ┌────▼──────────────────────────▼──────────────────────────▼───────┐
    │                          MemPalace                                │
    │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐            │
    │  │ 知识图谱  │  │ L0-L3栈  │  │ 语义搜索  │  │ 世界观  │            │
    │  │ (实体关系)│  │(膨胀控制) │  │ (RAG)   │  │ 版本库  │            │
    │  └──────────┘  └──────────┘  └──────────┘  └────────┘            │
    └────────────────────────────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────────┐
    │  新增组件                                         │
    │  ┌────────────────────┐  ┌──────────────────────┐ │
    │  │ Brainstorming      │  │ Consistency Filter   │ │
    │  │ Service            │  │ (一致性校验: KG+世界观)│ │
    │  │ (多模型头脑风暴)    │  └──────────────────────┘ │
    │  └────────────────────┘                             │
    │  ┌────────────────────┐  ┌──────────────────────┐ │
    │  │ LLM Provider       │  │ Conflict Resolver    │ │
    │  │ (模型路由/成本控制)  │  │ (分支合并冲突处理)    │ │
    │  └────────────────────┘  └──────────────────────┘ │
    └──────────────────────────────────────────────────┘
```

---

## 4. 核心组件设计

### 4.1 事件总线 (Event Bus)

所有组件的通信中枢，实现 pub/sub 模式。

```python
# 概念接口
class EventBus:
    async def publish(event: Event, branch_id: str): ...
    async def subscribe(event_type: str, handler: Callable): ...
    async def get_branch_events(branch_id: str) -> List[Event]: ...
```

事件带分支标记、因果链，支持按分支/时间/类型过滤。

### 4.2 事件定义

#### 4.2.1 系统事件

```python
@dataclass
class SystemEvent:
    id: UUID
    type: str                     # 事件类型名
    source: str                   # 发出组件
    payload: dict                 # 数据
    branch_id: str                # 所属分支
    parent_event_id: UUID | None  # 因果链
    metadata: dict = field(default_factory=lambda: {
        "timestamp": datetime.now(),
        "randomness_seed": 0.0,   # 0-1 随机因子
        "importance": 0.5,        # 情节重要性
        "model_used": "",         # 处理该事件的模型
        "cost": 0.0,              # 本次调用的token成本
    })
```

标准事件类型清单：

| 事件类型 | 发出者 | 说明 |
|---------|--------|------|
| `SceneStarted` | 情节引擎 | 新场景开始 |
| `SceneEnded` | 情节引擎 | 场景结束，触发剪枝评估 |
| `NarrativeAdvance` | Agent Core | 故事推进决策 |
| `NarrativeOutput` | Agent Core | 输出叙事文本 |
| `CharacterStateChanged` | Agent Core | 角色状态变化 → 触发KG更新 |
| `RelationChanged` | Agent Core | 关系变化 |
| `BrainstormRequested` | 用户/GUI | 请求头脑风暴 |
| `BrainstormCandidates` | Brainstorming | 多模型生成候选列表 |
| `ConsistencyResult` | Consistency Filter | 过滤结果 |
| `UserSelection` | GUI | 用户选择 |
| `BranchCreated` | 事件存储 | 新分支 |
| `BranchMerged` | 事件存储 | 分支合并 |
| `MergeConflictDetected` | Conflict Resolver | 合并冲突 |
| `MergeConflictResolved` | 用户/GUI | 冲突解决 |
| `KGQueryRequested` | Agent Core | 请求KG查询 |
| `KGQueryResult` | MemPalace | KG查询返回 |
| `MemoryTierChanged` | MemPalace | 实体升降级 |
| `ChapterPlanning` | 情节引擎 | 章节开始，触发 Planner |
| `NarrativeIntent` | Planner | 本章叙事目标（Chapter 级别的 Goals） |
| `PlanStepExecuted` | Agent Core | 单步 Plan 执行完成 |

#### 4.2.2 叙事事件

```python
@dataclass
class NarrativeEvent:
    id: UUID
    chapter: int
    scene: int
    content: str                  # 叙事文本
    involved_entities: List[str]  # 涉及实体
    causal_events: List[UUID]     # 原因事件链
    branch_id: str
    timestamp: datetime
```

### 4.3 Agent Core

事件驱动的 LLM 循环，每次迭代：

1. **监听** — 从事件总线获取当前输入
2. **拼装上下文** — 从 MemPalace 获取 L0+L1 信息 + 当前事件
3. **LLM 推理** — 调用模型，输出结构化决策
4. **发出事件** — 将决策发布到总线

```python
class AgentCore:
    def __init__(self, event_bus: EventBus, llm_provider: LLMProvider, mempalace: MemoryStack):
        ...

    async def step(self, input_event: SystemEvent):
        # 1. 获取上下文
        l0_l1 = self.mempalace.wake_up()
        kg_context = self.mempalace.query_relevant(input_event)

        # 2. 构造 prompt
        prompt = self._build_prompt(l0_l1, kg_context, input_event)

        # 3. 调用 LLM
        response = await self.llm_provider.generate(
            prompt=prompt,
            model_tier=self._select_tier(input_event),  # 按场景选模型档位
        )

        # 4. 处理响应
        for action in response.actions:
            await self.event_bus.publish(action, branch_id=input_event.branch_id)
```

### 4.4 LLM Provider 与模型路由

不同场景使用不同档位的模型以优化成本（具体模型型号后续由使用者决定）：

| 场景 | 推荐档位 | 说明 |
|------|---------|------|
| 头脑风暴（批量创意生成） | 低成本 | 批量调用的核心场景，对成本敏感 |
| 一致性过滤 | 低成本 | 每次候选都需要校验，频率高 |
| 核心叙事生成 | 高成本 | 最核心的产出场景，质量优先 |
| 情节分析/伏笔检测 | 中成本 | 需要一定推理能力 |
| 冲突合并分析 | 中成本 | 需要理解双分支差异 |
| KG 查询/更新 | 低成本 | 结构化操作，量多但简单 |

```python
class LLMProvider:
    # 场景档位配置（具体模型型号由使用者通过 GUI/配置文件设定）
    # 每个场景绑定一个档位，档位绑定具体模型
    def __init__(self):
        # 档位 → 模型映射（由使用者在配置中定义）
        self.tier_models = {
            "high":   None,   # 待使用者配置
            "medium": None,
            "low":    None,
        }
        # 场景 → 档位映射
        self.scene_tiers = {
            "narrative":  "high",      # 核心叙事 → 高成本高质量
            "analysis":   "medium",    # 分析推理 → 中等
            "brainstorm": "low",       # 头脑风暴 → 低成本大批量
            "filter":     "low",       # 一致性过滤 → 低成本
            "kg":         "low",       # KG 操作 → 低成本
        }

    async def generate(self, prompt: str, scene: str = "narrative") -> LLMResponse:
        """按场景档位自动选择模型。"""
        tier = self.scene_tiers.get(scene, "narrative")
        model = self.tier_models[tier]
        # ... 路由到对应厂商API
```

#### 4.4.1 配置文件设计（JSON 格式）

API keys 和模型参数统一保存在 `config/llm.json`，JSON 格式，便于 GUI 读写和版本控制。

```json
{
  "providers": {
    "anthropic": {
      "api_key": "sk-ant-xxxxxxxxxxxx",
      "base_url": "https://api.anthropic.com",
      "default_model": "claude-sonnet-4-6",
      "parameters": {
        "temperature": 0.8,
        "max_tokens": 4096
      }
    },
    "openai": {
      "api_key": "sk-xxxxxxxxxxxx",
      "base_url": "https://api.openai.com/v1",
      "default_model": "gpt-4o",
      "parameters": {
        "temperature": 0.7,
        "max_tokens": 4096
      }
    },
    "ollama": {
      "api_key": null,
      "base_url": "http://localhost:11434",
      "default_model": "qwen2.5:7b",
      "parameters": {
        "temperature": 0.9,
        "max_tokens": 2048
      }
    },
    "deepseek": {
      "api_key": "sk-xxxxxxxxxxxx",
      "base_url": "https://api.deepseek.com",
      "default_model": "deepseek-chat",
      "parameters": {
        "temperature": 0.7,
        "max_tokens": 4096
      }
    }
  },
  "scene_routing": {
    "narrative": {
      "tier": "high",
      "provider": "anthropic",
      "model": "claude-sonnet-4-6",
      "parameters": {
        "temperature": 0.8,
        "max_tokens": 4096
      }
    },
    "analysis": {
      "tier": "medium",
      "provider": "deepseek",
      "model": "deepseek-chat",
      "parameters": {
        "temperature": 0.3,
        "max_tokens": 2048
      }
    },
    "brainstorm": {
      "tier": "low",
      "provider": "openai",
      "model": "gpt-4o-mini",
      "parameters": {
        "temperature": 1.2,
        "max_tokens": 1024
      }
    },
    "filter": {
      "tier": "low",
      "provider": "openai",
      "model": "gpt-4o-mini",
      "parameters": {
        "temperature": 0.0,
        "max_tokens": 512
      }
    },
    "kg": {
      "tier": "low",
      "provider": "ollama",
      "model": "qwen2.5:7b",
      "parameters": {
        "temperature": 0.1,
        "max_tokens": 1024
      }
    }
  }
}
```

**结构说明：**

| 层级 | 字段 | 作用 |
|------|------|------|
| `providers` | `api_key` | 各厂商的 API 密钥，null = 本地模型 |
| | `base_url` | API 端点，支持自定义（代理/自托管） |
| | `default_model` | 该厂商的默认模型 |
| | `parameters` | 厂商级默认参数（被 scene_routing 覆盖） |
| `scene_routing` | `tier` | 成本档位标记（用于 GUI 展示和成本统计） |
| | `provider` | 使用哪个厂商 |
| | `model` | 使用哪个模型 |
| | `parameters` | 场景级参数，覆盖 provider 级默认值 |

**设计要点：**
- `providers` 和 `scene_routing` 解耦——厂商配置只管连接，场景路由管调度
- 每个场景可独立指定 provider + model + parameters，灵活控制成本和效果
- `api_key: null` 表示本地模型（如 Ollama），不报错
- GUI 中提供配置编辑界面，修改后保存到 `config/llm.json`

#### 4.4.2 加载逻辑

```python
class LLMProvider:
    def __init__(self, config_path: str = "config/llm.json"):
        with open(config_path) as f:
            self.config = json.load(f)
        self.providers = self.config["providers"]
        self.scene_routing = self.config["scene_routing"]

    async def generate(self, prompt: str, scene: str = "narrative") -> LLMResponse:
        route = self.scene_routing.get(scene, self.scene_routing["narrative"])
        provider_cfg = self.providers[route["provider"]]
        # 合并参数：provider 默认 + scene 覆盖
        params = {**provider_cfg.get("parameters", {}), **route.get("parameters", {})}
        # 按 provider 类型分发到对应 API
        ...
```

### 4.5 Prompt Cache 策略

本框架的 prompt 结构天然适合 LLM prompt caching（如 Anthropic 的 Prompt Caching、OpenAI 的 Context Caching）。核心思路：将稳定内容前置，使后续调用复用缓存前缀。

#### 4.5.1 Prompt 分层

每次 LLM 调用的 prompt 按稳定度严格分层：

```
[Part 1] 系统身份 + 核心规则    → 几乎不变，缓存命中率最高
[Part 2] L0 世界观设定           → 低频变化（仅世界观版本变更时）
[Part 3] L1 当前章节信息         → 逐章变化，每章内稳定
[Part 4] 当前事件 + 查询内容     → 每次都变，不依赖缓存
```

Part 1+2 可能占整个 prompt 的 60-80% token 量，缓存收益显著。

#### 4.5.2 批量调用聚簇

相同场景的 LLM 调用聚在短时间内并行发出，共享缓存 TTL（如 Claude 的 5 分钟缓存窗口）：

| 场景 | 缓存策略 |
|------|---------|
| 叙事生成 | 共享 Part1+2+3 前缀，主循环内各步复用 |
| 脑暴创意 | 一次脑暴的 N 个请求同时发出，Part1+2 共享缓存 |
| 一致性过滤 | 批量过滤时只换过滤目标，Part1+2+规则共享缓存 |
| 合并冲突分析 | 单次操作，不特殊优化 |

#### 4.5.3 实现层封装

缓存标记由 LLM Provider 内部管理，对上层透明：

```python
class LLMProvider:
    async def generate(self, prompt: str, scene: str = "narrative") -> LLMResponse:
        tier = self.scene_tiers.get(scene, "narrative")
        # 内部自动分割 prompt, 对 Part1+2 添加 cache_control 标记
        # 对同一场景的连续调用, 缓存前缀自动复用
        ...
```

使用者无需关心缓存细节，切换模型厂商时 Provider 层自动适配该厂商的缓存机制。

#### 4.5.4 语义缓存（LLM 之外）

对于 KG 查询、情节分析等场景，在缓存 TTL 内相同输入直接返回缓存结果，不调用 LLM：

- KG 查询缓存：Agent 一次迭代内多次查询同一实体 → 第一次查 LLM，后续返回缓存
- 情节分析缓存：同一章节内多次节奏分析 → 结果不变 → 不重复调用

### 4.6 情节引擎 (Plot Engine)

负责跟踪和维护叙事结构：

- **结构管理**：Volume → Chapter → Scene 层级维护
- **节拍检测**：分析事件流，识别"激励事件"、"转折点"、"高潮"等叙事节拍
- **伏笔追踪**：记录埋下的伏笔，检测到期未回收的伏笔
- **节奏分析**：检测动作/对话/描写的比例是否合理
- **多分支维护**：每个分支独立维护结构状态

```python
@dataclass
class ForeshadowingEntry:
    id: UUID
    hint_text: str
    planted_at: ChapterScene
    expected_payoff: str
    resolved_at: ChapterScene | None = None
    importance: float = 0.5
```

### 4.7 Brainstorming Service（多模型头脑风暴）

多模型并行生成候选事件，经过一致性漏斗后由用户选择：

```
当前故事状态
    │
    ▼
┌──────────────────────────────┐
│  多 LLM 并行生成候选事件       │
│  (每个模型配置不同 prompt/温度) │
└──────────┬───────────────────┘
           │ 原始候选池 (N 个)
┌──────────▼───────────────────┐
│  Consistency Filter           │
│  (KG 校验 + 世界观一致性检查)   │
└──────────┬───────────────────┘
           │ 过滤后选项
┌──────────▼───────────────────┐
│  用户选择 / GUI 展示           │
│  → 选中 → 发布事件到主线       │
│  → 未选中 → 进入待选池         │
│    (可随时从历史点分支)         │
└──────────────────────────────┘
```

### 4.8 Consistency Filter

每次候选事件被选择前，自动校验：

- 候选事件中的角色/物品在当前 KG 中是否存在？状态是否一致？
- 候选事件是否违背当前世界观规则（世界版本 vs 候选行为）？
- 候选事件与已发生事件是否存在因果关系矛盾？

三种结果：
- **通过** → 进入用户选择列表
- **轻微冲突** → 标记冲突点，仍允许用户选择
- **严重冲突** → 自动过滤，标记原因

### 4.9 冲突合并 (Merge/Conflict Resolution)

两条分支合并时：

1. 系统计算**重复度**（KG 相似度 + 事件序列相似度），高于用户设定的阈值提示合并潜力
2. 列出**冲突点清单**（角色状态、关系、时间、因果链）
3. 无冲突部分自动合并
4. 冲突逐一展示给用户解决
5. 生成合并记录（来源、冲突列表、解决方式）

```
合并 A + B → C

合并记录:
  created_at: ...
  sources: [branch_A, branch_B]
  auto_merged: 15 events
  conflicts_resolved: 3
  conflict_log: [
    {entity: "张三", field: "location", A: "京城", B: "江南", resolution: "京城"},
    ...
  ]
```

### 4.10 Planner（叙事规划层）

在 Agent Core 之上增加的规划层，解决"每步反应式决策"导致的短视问题。Planner 让系统从**"LLM 在写故事"**升级为**"系统在导演故事"**。

#### 4.10.1 核心概念

```
Planner (规划器)
  ↑ 设定叙事目标
Agent Core (执行器)
  ↑ 执行计划
事件总线 (反馈)
```

每章开始时，Planner 产出该章的 `NarrativeIntention`（叙事意图），Agent Core 在意图约束下逐步执行。

#### 4.10.2 NarrativeGoal

```python
@dataclass
class NarrativeGoal:
    id: UUID
    description: str                  # "让主角遭遇第一次重大失败"
    target_state: dict                # 期望达成的 KG 状态
    priority: float                   # 0-1，影响 Agent 决策权重
    deadline: int | None              # 多少步/场景内完成
    status: str                       # pending / active / achieved / abandoned
    constraints: List[str]            # 约束条件（如"不能提前揭示反派身份"）
```

示例：
- `priority=0.9` _"让主角获得玄铁剑"_ → Agent 会优先推进这条线
- `priority=0.3` _"引入一个配角"_ → 有余力时再做

#### 4.10.3 工作流程

```
章节开始
  │
  ▼
情节引擎 → ChapterPlanning → Planner
  │
  ├── 1. 分析当前 KG 状态（角色位置、未回收伏笔、冲突积累）
  ├── 2. 查看全局叙事蓝图（英雄之旅 / 自定义模板进度）
  ├── 3. 输出 3~5 个 NarrativeGoal（按 priority 排序）
  │
  ▼
Agent Core 循环:
  1. 取当前 priority 最高的活跃 Goal
  2. 将 Goal 加入 prompt 上下文
  3. 执行一步叙事生成
  4. 检查 Goal 是否达成 → 若达成标记 achieved，取下个 Goal
  5. 若超出 deadline → 标记 abandoned，调整策略
  6. 重复直到所有活跃 Goal 完成 → 章节结束
```

#### 4.10.4 与现有组件的关系

- **情节引擎** 触发规划时机（"该开新章了"）并提供模板约束
- **Planner** 依赖情节引擎的伏笔/节奏分析 + MemPalace 的 KG 查询做决策
- **Agent Core** 是被 Planner"喂养"的执行者——它看到的 prompt 里多了当前 Goal
- **Brainstorming** 也可以绑定 Goal（"围绕`让主角获得玄铁剑`这个目标脑暴候选"）

#### 4.10.5 多分支下的 Goal

每个分支独立维护自己的 Goal 列表。合并分支时，两边的 Goal 也需合并——冲突的 Goal 作为冲突项展示给用户解决。

---

## 5. 知识图谱设计

### 5.1 实体类型

| 类型 | 属性 | 说明 |
|------|------|------|
| `character` | name, age, health, location, personality, status, description | 角色 |
| `location` | name, climate, type, significance | 地点/场景 |
| `item` | name, owner, properties, history | 物品/道具 |
| `faction` | name, members, hierarchy, territory | 组织/门派 |
| `event_marker` | name, involved, outcome, effects | 历史事件标记 |
| `concept` | name, definition, related | 抽象概念（如"天道"） |

### 5.2 关系类型

```
character ──loves/hates/fears/trusts──→ character
character ──belongs_to──→ faction
character ──located_at──→ location
character ──holds──→ item
character ──has_trait──→ trait/value
location ──part_of──→ location
faction ──controls──→ location
faction ──at_war_with/allied_with──→ faction
item ──created_by──→ character
event_marker ──involved──→ character
```

所有关系带时间窗口 (`valid_from`, `valid_to`) 支持状态变化追踪。

### 5.3 KG 膨胀控制 (L0-L3 栈)

直接使用 MemPalace 的四层记忆栈机制：

| 层级 | 容量 | 加载策略 | 包含内容 |
|------|------|---------|---------|
| **L0** | ~100 tokens | 始终加载 | 小说世界观核心规则、风格设定 |
| **L1** | ~800 tokens | 始终加载 | 当前章节活跃角色 + 状态 + 场景 |
| **L2** | 按需检索 | 话题触发 | 过去章节的事件摘要、伏笔回溯 |
| **L3** | 无限制 | 语义搜索 | 全量 KG、完整事件日志 |

**升降级策略**：
- 角色连续 N 章未出现 → L1 → L2（带摘要指针）
- 角色再次出现 → L2 → L1（加载摘要恢复上下文）
- 卷结束后 → L2/L3（整卷摘要化归档）

---

## 6. 世界观版本管理

世界观不是静态的——角色成长和环境变化会导致设定改变。

```
WorldState(v1) ──→ WorldState(v2) ──→ WorldState(v3)
                                                   │
                                              WorldState(v3.1)  ← 分支
```

- 每个 WorldState 是一个快照，包含当前生效的规则列表和关键事实
- 快照不存储全量数据，存储的是"相对上一个版本的变更集"
- 查询"第 X 章时的世界观" = 重放到那个版本 + 查询当时的事件日志
- 旧世界观**不被覆盖**，始终可回溯

---

## 7. 分支时间线 (事件 DAG)

事件存储核心是一个 DAG，所有事件按分支链接：

```python
@dataclass
class EventNode:
    event_id: UUID
    event: SystemEvent | NarrativeEvent
    branch_id: str
    parent_id: UUID | None         # 前一个事件（链式）
    children: List[UUID]           # 后续事件
    branch_point: UUID | None      # 如果这是分支起点，指向被分叉的事件
```

操作：
- **创建分支**：在任意事件节点分叉，继承父节点的 KG 和世界观状态
- **合并分支**：对比两条分支的 KG 差异，逐条解决冲突
#### 快照机制（Snapshot）

随事件日志不断增长，从起点重放整条分支恢复 KG 状态会越来越慢。解决方案：**定期快照 + 增量重放**。

```python
@dataclass
class BranchSnapshot:
    branch_id: str
    snapshot_at_event: UUID         # 对应哪个事件节点
    kg_dump: bytes                  # 序列化的 KG 状态
    world_version: str              # 世界观版本号
    created_at: datetime
```

- **打快照时机**：每章结束时自动打；合并前自动打
- **查询状态**：找到最近快照 → 快照后的增量事件重放
- **分支创建**：从父分支最近的快照开始，而非从头
- **分支合并**：双方各取最近快照 + 各自增量，对比差异

快照存储方式：序列化 KG 状态为 JSON，存在 SQLite 或文件系统。单本书的快照数量为章节数（几百个），查询成本 O(log N)。

---

## 8. GUI 设计概要

### 8.1 技术栈
- 后端：FastAPI (Python)
- 前端：React + 可视化库（分支DAG: react-flow, 知识图谱: vis-network 或 cytoscape）

### 8.2 主布局

```
┌──────────────────────────────────────────────────────────────────┐
│  菜单栏: 文件 | 编辑 | 分支 | 工具 | 设置                        │
├──────────┬─────────────────────────────────┬─────────────────────┤
│          │                                  │                     │
│ 左侧面板  │        中央工作区                 │    右侧面板          │
│          │                                  │                     │
│ ┌──────┐ │  ┌─────────────────────────────┐ │  ┌───────────────┐ │
│ │分支   │ │  │  小说正文 / 事件流            │ │  │ 角色图谱       │ │
│ │DAG   │ │  │  (实时编辑 + timeline)        │ │  │ (KG 可视化)   │ │
│ │      │ │  └─────────────────────────────┘ │  └───────────────┘ │
│ │节点  │ │  ┌─────────────────────────────┐ │  ┌───────────────┐ │
│ │=章/节│ │  │  脑暴/候选人区域              │ │  │ 实体详情       │ │
│ └──────┘ │  │  (多模型候选 → 漏斗 → 选择)  │ │  │ (属性编辑)    │ │
│          │  └─────────────────────────────┘ │  └───────────────┘ │
│ ┌──────┐ │                                  │  ┌───────────────┐ │
│ │章节   │ │                                  │  │ 伏笔追踪       │ │
│ │大纲   │ │                                  │  └───────────────┘ │
│ └──────┘ │                                  │                     │
└──────────┴──────────────────────────────────┴─────────────────────┘
```

### 8.3 核心交互

- **脑暴流程**：用户点击"脑暴" → 后台多模型并行生成 → 候选展示 → 一致性过滤标记 → 用户选择/拖拽到正文区
- **分支操作**：右键事件节点 → 从此分支 / 拖拽到合并区 → 冲突解决弹窗
- **KG 查看**：点击实体 → 高亮关联网络 → 右键查看时间线

---

## 9. 数据流 (一个典型场景)

```
1. [情节引擎]  → 检测到该开新章 → 发布 ChapterPlanning
2. [Planner]  → 分析 KG+伏笔 → 发布 NarrativeIntent (含本章 3~5 个 Goal)
3. [用户] 在GUI点击"推进故事" 或 [Planner] 触发下一步
4. [GUI/Planner]  → 发布 NarrativeAdvance 事件到 EventBus
5. [Agent Core]  → 监听 → 从 MemPalace 获取 L0+L1+KG 上下文 + 当前 Goal
6. [Agent Core]  → 从 LLM Provider 请求叙事生成 (tier: narrative)
7. [LLM]  → 返回叙事文本 + 可能的状态/关系变更
8. [Agent Core]  → 发布 NarrativeOutput + CharacterStateChanged + PlanStepExecuted
9. [MemPalace]  → 监听 → 更新知识图谱
10. [情节引擎]  → 监听 → 更新结构 + 伏笔检查 + 检查 Goal 进度
11. [Planner]  → 监听 PlanStepExecuted → 判断 Goal 是否达成
12. [GUI]  → 监听 → 更新正文 + 图谱显示

--- 脑暴场景 ---
1. [用户] 点击"脑暴"
2. [Brainstorming]  → 多LLM并行生成候选 (tier: brainstorm)
3. [Consistency Filter]  → 逐条校验 → 标记通过/冲突
4. [GUI]  → 展示候选列表
5. [用户] 选择 → 选中事件发布到总线
   未选中 → 进入待选池

--- 分支合并场景 ---
1. [用户] 选择两条分支 → 点击"合并"
2. [Conflict Resolver]  → 计算重复度 → 检测冲突
3. [GUI]  → 弹出冲突解决窗口
4. [用户] 逐条解决 → 确认
5. [事件存储]  → 创建新分支 + 合并记录
```

---

## 10. 项目目录结构

### 10.1 环境与依赖管理

使用 **conda** 管理 Python 环境，**requirements.txt** 管理依赖：

```bash
# 创建环境
conda create -n novel-agent python=3.11
conda activate novel-agent

# 安装依赖
pip install -r requirements.txt
```

依赖分三层管理：

| 层级 | 文件 | 内容 |
|------|------|------|
| 核心 | `requirements.txt` | 生产环境依赖（FastAPI, MemPalace, Instructor 等） |
| 开发 | `requirements-dev.txt` | 开发/测试工具（pytest, black, mypy, ruff 等） |
| 可选 | `requirements-optional.txt` | 可选功能（本地模型 Ollama, 特定 LLM SDK 等） |

```
novel-agent/
├── config/
│   └── llm.json                  # LLM 厂商配置 + 场景路由
├── backend/
│   ├── core/
│   ├── core/
│   │   ├── event_bus.py          # 事件总线
│   │   ├── event_types.py        # 事件类型定义
│   │   ├── event_store.py        # 事件存储 (DAG)
│   │   └── config.py             # 配置
│   ├── agent/
│   │   ├── agent_core.py         # Agent 主循环
│   │   ├── llm_provider.py       # LLM 抽象 + 路由
│   │   └── prompt_builder.py     # Prompt 组装
│   ├── plot/
│   │   ├── plot_engine.py        # 情节引擎
│   │   ├── structure_manager.py  # 卷/章/节管理
│   │   └── foreshadowing.py      # 伏笔追踪
│   │   └── planner.py            # 叙事规划层 (NarrativeGoal)
│   ├── brainstorming/
│   │   ├── brainstorming_service.py  # 头脑风暴
│   │   └── consistency_filter.py     # 一致性过滤
│   ├── merge/
│   │   └── conflict_resolver.py  # 冲突合并
│   ├── gui/
│   │   ├── api.py                # FastAPI 路由
│   │   ├── schemas.py            # API 数据模型
│   │   └── websocket_handler.py  # WebSocket 实时推送
│   └── main.py
├── frontend/                     # React 应用
│   ├── src/
│   │   ├── components/
│   │   │   ├── BranchDAG/        # 分支时间线图
│   │   │   ├── Editor/           # 正文编辑器
│   │   │   ├── Brainstorm/       # 脑暴/选择界面
│   │   │   ├── KnowledgeGraph/   # KG 可视化
│   │   │   ├── Timeline/         # 时间线视图
│   │   │   └── ConflictDialog/   # 冲突解决弹窗
│   │   ├── hooks/
│   │   └── App.tsx
│   └── package.json
├── docs/
│   └── 2026-04-30-novelagent-design.md
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── requirements-optional.txt
└── environment.yml           # conda 环境导出文件
```

---

## 11. 不用做的（非目标）

- **不需要** 分布式系统基础设施
- **不需要** 实时多人协作
- **不需要** NLP 模型训练
- **不需要** 语音识别/合成
- **不需要** 翻译/多语言
- **不需要** 发布/连载平台对接

---

## 12. 项目规范

### 12.1 提交规范

采用 **Conventional Commits** 格式，说明部分使用中文：

```
feat(scope): 中文描述
fix(scope): 中文描述
docs(scope): 中文描述
test(scope): 中文描述
refactor(scope): 中文描述
```

**常见 scope：**

| scope | 对应模块 |
|-------|---------|
| `event-bus` | 事件总线 |
| `event-store` | 事件存储/DAG |
| `agent-core` | Agent 主循环 |
| `llm-provider` | LLM Provider/模型路由 |
| `planner` | 叙事规划层 |
| `plot` | 情节引擎 |
| `kg` | 知识图谱 |
| `brainstorm` | 头脑风暴 |
| `filter` | 一致性过滤 |
| `merge` | 冲突合并 |
| `gui` | 前端/GUI |
| `config` | 配置文件 |
| `docs` | 文档 |
| `test` | 测试 |

**示例：**

```
feat(event-bus): 事件总线支持分支标记和因果链
fix(agent-core): 修复 Planner 空 Goal 列表崩溃
docs(design): 更新 LLM 配置文件格式说明
test(kg): 补充实体 CRUD 边界测试
refactor(plot): 拆分享节结构管理器
```

### 12.2 Review 规范

- **按功能逻辑 review**：不看文件顺序，按"这个 PR 做了什么"分组审查 diff
- **核心模块必看**：`core/`、`agent/`、`plot/` 的改动逐行审查
- **LLM 相关重点关注**：prompt 变更、结构化输出 schema 变更需额外留意
- **测试伴生**：新功能必须有对应测试，bugfix 必须附带回归测试

### 12.3 提交前检查

每次 commit 前自动运行（Git hook 或手动）：

```bash
pytest --cov --cov-fail-under=75  # 覆盖率不低于 75%
ruff check .                       # lint 无新增错误
```

#### 12.3.1 README 同步

每个 task 完成后，同步更新 `README.md` 的**当前进度表**：
- ⏳ 待开始 → ✅ 已完成（或补测后变 ✅）
- 已完成的 task 保留在表中，标记为 ✅
- 确保 README 始终反映项目真实状态
