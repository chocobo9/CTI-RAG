# Harness 审计 Handoff — 给重审 + 修改 agent

> 来源：一次**静态代码审查**(只读，未跑测试/eval/live)。你（接手的 agent）**不要盲信本清单**——
> 每条都附了 `文件:行号` 证据，请独立复核；标了「未验证」的结论，动手前必须自己确认。

## 0. 工作区

- worktree 根：`D:/proj/CTI-RAG/.claude/worktrees/optimization/rag_cti`
- 分支：`feat/optimization`，HEAD `7869011`
- ⚠️ **工作树脏**：HEAD 之外约 26 个文件已改但未 commit，外加未跟踪的新文件
  （`src/rag_cti/generation/limiter.py`、`knowledge/tool_cache.py`、`knowledge/agentic_effort.py` 等）。
  **先 `git status` + `git stash`/commit 落盘当前进度，再动手**，否则审计期改动会和已有改动混在一起。

## 1. 审计覆盖范围（诚实边界）

**已审（8 个核心文件 + 接线）**：`knowledge/agent_graph.py`、`agentic_graph.py`、`agentic_nodes.py`、
`supervisor_graph.py`、`supervisor_nodes.py`、`evidence_ledger.py`、`agent_tools.py`、`__init__.py`(片段)、`cli.py`(grep)。

**未审（可能藏同类问题，请补审）**：`config.py`(疑似 `agentic_*` settings 爆炸)、
`generation/*` 的改动(`client.py`/`context_builder.py`/`generator.py`/`prompts.py`)、
`knowledge/agentic_state.py`、`agentic_effort.py`、`tool_cache.py`、`generation/limiter.py`、`knowledge/composer.py`。

**质量好、不要动**：`evidence_ledger.py`(frozen dataclass + RLock + union 语义，写得干净)、
`agentic_nodes.py` 的纯逻辑分支（可单测）、`agent_tools.py` 的分层、Model B 对 `build_agentic_graph` 的复用。
问题不是"到处烂"，是集中在下面几处。

## 2. 根因（元判断 —— 先读这条，能省一半功夫）

所有问题同源：**每代演进都"新增实现并接上入口"，但从不"退役旧路径 / 抽出公共部分"——缺了收口这一步。**
演进线：`v1 create_react_agent (agent_graph)` → `v2 gather-only 硬轨 (agentic_graph)` → `Model B 多agent (supervisor)`，
每一代都是被上一代缺陷逼出来的，但旧的都没下线。**所以收口一次能同时消掉一大半问题**（见 §4 建议顺序）。

## 3. 问题清单（按严重度）

### 🔴 P0-1 三套 agent loop 并存，已知劣化的 v1 仍挂在 CLI 入口，核心工厂寄生其中
- **位置**：
  - v1：`knowledge/agent_graph.py`(155 行，`create_react_agent`)←入口 `cli.py:107` → `__init__.py:340 ask` → `agent_graph.ask`
  - v2：`knowledge/agentic_graph.py`(488 行，主力)←入口 `cli.py:127` → `__init__.py:158 agentic_answer`
  - Model B：`knowledge/supervisor_graph.py`(274 行)←入口 `cli.py:154` → `__init__.py:201 supervised_answer`
- **问题**：
  1. v1 的 `create_react_agent` 是**已知会 recursion-starve（撞 recursion_limit 不产 draft）的旧实现**——
     `agentic_graph.py` 模块 docstring 自述 v2 存在就是为取代它（"so it cannot over-explore into a recursion stub the way `create_react_agent` did"）。但 v1 仍对用户开放（CLI `ask`）。
  2. `build_model()` 和 `_LimitedChatModel`（全项目的 model 工厂 + 并发限流）定义在**最该淘汰的 v1 文件** `agent_graph.py:40-75`，却被两条新路径反向 import（`__init__.py:168` 和 `:212`）→ 想删 v1 会扯断 v2/ModelB。
- **建议**：把 `build_model`/`_LimitedChatModel` 抽到 `knowledge/model_factory.py`（或 generation 层）；CLI `ask` 改指向 `agentic_answer`；`agent_graph.py` 退役/删除。
- **⚠️ 未验证**：「v1 比 v2 差」依据是 v2 docstring + 项目 memory（eval F1：agentic 0.32–0.49 vs single-shot 0.12–0.16），**我没在本轮 live 跑对比**。退役前请自己确认 v1 没有 v2 不具备的独有行为/被依赖路径。

### 🔴 P0-2 手写 ReAct 驱动循环实现了两遍，且两版健壮性不对称（Model B 缺 wall-clock 守卫）
- **位置**：`run_gather_loop`(`agentic_nodes.py:171`) vs `run_supervisor_loop`(`supervisor_nodes.py:55`)
- **问题**：两者骨架几乎逐字相同（`for _ in range(max_steps)` → `model.invoke` → `tool_calls` → 无则 break → serial/parallel dispatch），连并行分发分支都各写一份。但 **`run_supervisor_loop` 缺了 `run_gather_loop` 有的**：
  - `deadline` wall-clock 守卫（gather 版有，见 `agentic_nodes.py:178, 208, 220, 255`）
  - `on_model_error` 优雅降级（gather 版有；supervisor 版直接 `break`，见 `supervisor_nodes.py:92`）
  - 即 **Model B 编排层缺少 v2 精心加的"跨整个循环的 wall-clock 总预算"兜底**（项目历史上栽过的 burst-跑飞 教训没回流到新层）。
- **建议**：抽一个统一的 `run_react_tool_loop(model, dispatch, messages, *, max_steps, deadline=None, on_model_error=None, render_state=None, parallel=...)`，gather 和 supervisor 都调它——加固只此一份，不再漂移。
- **风险注意**：两版的 ToolMessage / tool_call_id 配对逻辑要保持一致，抽取时别破坏 AIMessage→ToolMessage 配对（chat API 要求）。

### 🟠 P1-1 `decide_next` 圈复杂度过高，是收敛行为最易出 bug 处
- **位置**：`agentic_nodes.py:385-450`（`decide_next`）+ `agentic_graph.py:318-387`（`sufficiency_gate`，`open_cat_stall` 状态机内联在 `:347-349`）
- **问题**：`decide_next` 有 **14 个参数、8 个 return 分支、7 种 stop_reason**，停机优先级**完全靠 `if` 书写顺序隐式编码**；改一条顺序行为就变。跨轮状态 `open_cat_stall` 的推导又内联在另一个文件的 graph node 里，两处耦合。这是项目 memory 反复记录"收敛难调 / cap 校准跑飞 / judge 过度保守"的根因聚集地。
- **建议**：把停机判定抽成**有序、命名的规则列表**（`STOP_RULES: list[(predicate, reason)]` 逐条短路），让优先级显式、可逐行核对；把 `open_cat_stall` 推导挪进纯函数。分支数不变，可推理性大增。
- **注意**：这是高敏感区，**改前先有 golden 测试**锁住当前各 stop_reason 的触发条件，再重构（行为等价重构，不是改逻辑）。

### 🟠 P1-2 每个工具有 summary-only / to-ledger 两个版本（随 v1 退役清理）
- **位置**：`agent_tools.py` —— `summarize_*` + `*_summary`(`:56-161`) vs `*_to_ledger`(`:169-233`)
- **问题**：同 5 个工具各两套适配器，根因同 P0-1（v1 还活着所以养着它的 summary-only 适配器）。
- **⚠️ 删除时的坑**：`outline_summary`/`query_summary`/`facts_for_evidence_summary` **还被 `facts` CLI 路径和单测用**（见 `agent_tools.py:130` 注释），**不能跟 v1 一起删**。只有 `vector_search_summary`（`:160`）和 `agent_graph.py` 里的 `@tool` 定义是纯 v1，可随 v1 退役清掉。

### 🟡 P2-1 chat thin-wrapper 逐字重复
- **位置**：`build_judge`(`agentic_graph.py:73`) 与 `build_composer`(`supervisor_graph.py:63`) 函数体逐字相同（`build_composer` docstring 自承 "Mirrors build_judge"）。
- **建议**：抽 `build_chat_fn(client, model, max_tokens) -> Callable[[str,str],str]`，两处复用。低风险。

### 🟡 P2-2 recursion_limit 公式复制
- **位置**：`outer_limit = max(25, settings.agentic_max_iterations * 4)` 在 `agentic_graph.py:478` 和 `supervisor_graph.py:115` 各写一遍。
- **建议**：提到 `Settings` 的 property 或模块常量。低风险。

### 🟡 P2-3 `agentic_nodes.py` 708 行，混 4 个关注点
- **位置**：`agentic_nodes.py`（逼近项目自定的 800 行上限）
- **问题**：inner gather loop(`:171-264`) + judge/parse(`:272-377`) + router `decide_next`(`:385-450`) + synthesize/citation/assembly(`:595-708`) 四块塞一个文件。
- **建议**：按这 4 块拆成 `gather_loop.py` / `sufficiency.py` / `router.py` / `synthesis.py`（或类似）。配合 P0-2、P1-1 一起做。

### ⚪ P3-1 工作树大量未提交改动（卫生）
- 见 §0。先落盘再动手。

## 4. 建议收口顺序（一刀切多债）

1. **退役 v1**（P0-1 + P1-2）：抽 `build_model` → CLI `ask` 切 v2 → 删 `agent_graph.py` + 纯 v1 工具适配器。一步消掉「三套 loop」「双工具适配器」「工厂寄生」三笔债。**动前确认 §P0-1 的「未验证」项。**
2. **统一 ReAct 循环**（P0-2）：抽 `run_react_tool_loop`，给 supervisor 补上 deadline/error 守卫。修掉真实健壮性缺口 + 双循环重复。
3. **抽 chat-fn / recursion 常量**（P2-1/P2-2）：顺手低风险。
4. **重构 `decide_next` 为规则表**（P1-1）：先加 golden 测试再行为等价重构。
5. **拆 `agentic_nodes.py`**（P2-3）：和 2/4 一并。
6. **补审 §1 未覆盖文件**（config / generation 改动）。

## 5. 对你（接手 agent）的明确要求

- 不要盲信本清单：每条按 `文件:行号` 独立复核；**P0-1 的「v1 更差」请跑 eval 或 trace 自证**后再退役。
- 先补审 §1 列的未覆盖文件，确认那里没有同级问题，再给最终修改计划。
- 每一步改动都要：跑现有单测 + 关键 integration（`tests/integration/test_agentic_answer.py`、`test_supervised_answer.py`）；行为敏感区（decide_next）先补 golden 测试。
- 收口类删除（删 v1）务必先确认无反向依赖（grep `agent_graph`、`build_model`、`*_summary`）。
