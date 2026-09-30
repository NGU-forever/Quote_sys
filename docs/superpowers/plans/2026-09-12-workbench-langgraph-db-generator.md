# Workbench LangGraph 数据生成 Agent 实施方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Workbench 数据生成 Agent 从单 ReAct 循环重构为基于 LangGraph 的多专职节点有向状态图，实现完全离线自治、异构资料自适应嗅探与已有商业套餐的受控精确提取。

**Architecture:** 采用“内容嗅探（Profiler）+ 自适应并行萃取（Products / Packages / Bindings）+ 跨源仲裁对齐（Reconcile）+ 服务端硬质检门禁（Validate）+ 定向自愈循环（Correction）+ 受控单事务持久化（Apply）”的状态图架构。检查点使用本地 SQLite，严格关闭外部遥测。

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0, SQLite, LangGraph, Pydantic 2.x, openpyxl, python-docx, httpx.

**Spec:** `docs/superpowers/specs/2026-09-12-workbench-langgraph-db-generator-design.md`

## Global Constraints
- 必须保持完全离线自治：设置 `LANGSMITH_TRACING=false`，不产生任何外网遥测调用。
- 必须保持 OpenAI 兼容接口标准，并保留确定性 `MockProvider` 保障测试与无 Key 环境。
- 商业套餐严格遵循防发散规则：仅识别并结构化已有方案，禁止模型主观推测或延伸套餐。
- 数据库业务表结构（`products`, `packages`, `device_bindings`）与前端 API 契约完全保持不变。
- 节点执行流水实时映射写入 `import_run_events` 表，确保 `AgentManager.vue` 零修改无缝对接。

---

### Task 1: 依赖与离线环境基础配置

**Files:**
- Modify: `Workbench/requirements.txt`
- Create: `Workbench/app/agent/graph/config.py`
- Test: `Workbench/tests/test_agent_graph_env.py`

**Interfaces:**
- Produces: `get_checkpointer() -> SqliteSaver`, `is_offline_telemetry_disabled() -> bool`

- [ ] **Step 1: 编写环境与配置测试**

```python
# Workbench/tests/test_agent_graph_env.py
import os
import unittest
from app.agent.graph.config import init_offline_env, get_checkpointer
from app.core.config import settings

class TestGraphEnv(unittest.TestCase):
    def test_offline_flag_is_enforced(self):
        init_offline_env()
        self.assertEqual(os.environ.get("LANGSMITH_TRACING"), "false")

    def test_checkpointer_creates_sqlite(self):
        checkpointer = get_checkpointer()
        self.assertIsNotNone(checkpointer)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd Workbench && .venv/bin/python -m unittest tests.test_agent_graph_env -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.agent.graph'`

- [ ] **Step 3: 更新依赖并安装 LangGraph**

在 `Workbench/requirements.txt` 中添加：
```text
langgraph>=0.2.0,<1.0.0
```
并在虚拟环境中执行 `pip install langgraph`。
编写 `Workbench/app/agent/graph/config.py`：
```python
import os
from pathlib import Path
from langgraph.checkpoint.sqlite import SqliteSaver
from app.core.config import settings

def init_offline_env():
    os.environ["LANGSMITH_TRACING"] = "false"

def get_checkpointer() -> SqliteSaver:
    init_offline_env()
    db_path = settings.data_dir / "agent_checkpoints.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver.from_conn_string(f"sqlite:///{db_path}")
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd Workbench && .venv/bin/python -m unittest tests.test_agent_graph_env -v`
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add Workbench/requirements.txt Workbench/app/agent/graph/config.py Workbench/tests/test_agent_graph_env.py
git commit -m "feat(agent): add langgraph dependency and offline config"
```

---

### Task 2: 图状态定义（State）与内容嗅探节点（Profiler）

**Files:**
- Create: `Workbench/app/agent/graph/state.py`
- Create: `Workbench/app/agent/graph/nodes/profiler.py`
- Test: `Workbench/tests/test_profiler_node.py`

**Interfaces:**
- Produces: `AgentGraphState`, `profiler_node(state: AgentGraphState) -> dict`

- [ ] **Step 1: 编写嗅探节点单元测试**

```python
# Workbench/tests/test_profiler_node.py
import unittest
from pathlib import Path
from app.agent.graph.state import AgentGraphState
from app.agent.graph.nodes.profiler import profiler_node

class TestProfilerNode(unittest.TestCase):
    def test_profiler_detects_excel_and_doc(self):
        state: AgentGraphState = {
            "run_id": 1,
            "mode": "apply",
            "manifest": {
                "files": [
                    {"path": "产品最低价格.xlsx", "type": "excel", "supported": True},
                    {"path": "超声医疗报价平台业务文档.md", "type": "markdown", "supported": True}
                ]
            },
            "db_stats": {},
            "sources_plan": {},
            "products_extracted": [],
            "packages_extracted": [],
            "bindings_extracted": [],
            "issues": [],
            "candidates": None,
            "validation_errors": [],
            "retry_count": 0,
            "status": "running",
        }
        res = profiler_node(state)
        self.assertIn("sources_plan", res)
        self.assertTrue(len(res["sources_plan"].get("products", [])) > 0)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd Workbench && .venv/bin/python -m unittest tests.test_profiler_node -v`
Expected: FAIL

- [ ] **Step 3: 实现 State 与 Profiler 逻辑**

在 `state.py` 中声明 `AgentGraphState`。
在 `profiler.py` 中读取 manifest 中的支持文件，使用轻量 header / heading 检测：
- 识别含 SKU、价格、规格的工作表/表格标记为 `products` 来源；
- 识别含“套餐”、“方案”、“买赠”、“整购”标记为 `packages` 来源；
- 识别含“适用机型”、“搭配”标记为 `bindings` 来源。

- [ ] **Step 4: 运行测试验证通过**

Run: `cd Workbench && .venv/bin/python -m unittest tests.test_profiler_node -v`
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add Workbench/app/agent/graph/state.py Workbench/app/agent/graph/nodes/profiler.py Workbench/tests/test_profiler_node.py
git commit -m "feat(agent): implement graph state and profiler node"
```

---

### Task 3: 专职提取节点（Products, Packages, Bindings）

**Files:**
- Create: `Workbench/app/agent/graph/nodes/extractors.py`
- Test: `Workbench/tests/test_extractors.py`

**Interfaces:**
- Produces: `extract_products_node`, `extract_packages_node`, `extract_bindings_node`

- [ ] **Step 1: 编写提取节点单元测试（特别验证套餐防发散规则）**

```python
# Workbench/tests/test_extractors.py
import unittest
from app.agent.graph.nodes.extractors import extract_packages_node

class TestExtractors(unittest.TestCase):
    def test_extract_packages_returns_empty_when_no_package_in_source(self):
        state = {
            "sources_plan": {"packages": []},
            "packages_extracted": [],
            "issues": [],
        }
        result = extract_packages_node(state)
        self.assertEqual(result["packages_extracted"], [])
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd Workbench && .venv/bin/python -m unittest tests.test_extractors -v`
Expected: FAIL

- [ ] **Step 3: 实现专职提取节点逻辑**

在 `extractors.py` 中实现：
- `extract_products_node`：从 Excel/Word 表格解析设备与耗材统一字段。
- `extract_packages_node`：注入严格 Prompt（“只识别已有方案，严禁主观延伸或自行设计，无套餐时返回空”），解析固定整购与买赠方案。
- `extract_bindings_node`：解析 `(device_sku_id, consumable_sku_id)` 适用关系。

- [ ] **Step 4: 运行测试验证通过**

Run: `cd Workbench && .venv/bin/python -m unittest tests.test_extractors -v`
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add Workbench/app/agent/graph/nodes/extractors.py Workbench/tests/test_extractors.py
git commit -m "feat(agent): implement specialized extractor nodes"
```

---

### Task 4: 仲裁、质检门禁与自愈节点（Reconcile, Validate & Correct）

**Files:**
- Create: `Workbench/app/agent/graph/nodes/quality.py`
- Test: `Workbench/tests/test_quality_nodes.py`

**Interfaces:**
- Produces: `reconcile_node`, `validate_node`, `correction_node`, `should_continue_correction`

- [ ] **Step 1: 编写仲裁与质检门禁测试**

```python
# Workbench/tests/test_quality_nodes.py
import unittest
from app.agent.graph.nodes.quality import validate_node, should_continue_correction

class TestQualityNodes(unittest.TestCase):
    def test_validate_node_passes_good_candidates(self):
        # 验证符合条件的候选顺利通过
        pass

    def test_branch_routing(self):
        # 验证存在错误且未超限时路由到 correction_node
        self.assertEqual(should_continue_correction({"validation_errors": ["err"], "retry_count": 1}), "correction_node")
        self.assertEqual(should_continue_correction({"validation_errors": ["err"], "retry_count": 3}), "fail_node")
        self.assertEqual(should_continue_correction({"validation_errors": [], "retry_count": 0}), "apply_node")
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd Workbench && .venv/bin/python -m unittest tests.test_quality_nodes -v`
Expected: FAIL

- [ ] **Step 3: 实现仲裁、质检与条件路由**

- `reconcile_node`：外键关联对齐，组装规范候选结构。
- `validate_node`：调用现有 `validation.validate_candidates` 执行纯 Python 硬校验。
- `correction_node`：接收 `validation_errors` 引导 LLM 定向微调并递增 `retry_count`。
- 条件判断函数 `should_continue_correction`。

- [ ] **Step 4: 运行测试验证通过**

Run: `cd Workbench && .venv/bin/python -m unittest tests.test_quality_nodes -v`
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add Workbench/app/agent/graph/nodes/quality.py Workbench/tests/test_quality_nodes.py
git commit -m "feat(agent): implement reconcile, validate, and correction loop"
```

---

### Task 5: 状态图装配与 AgentService 适配器

**Files:**
- Create: `Workbench/app/agent/graph/builder.py`
- Modify: `Workbench/app/agent/agent_service.py`
- Test: `Workbench/tests/test_agent.py`

**Interfaces:**
- Produces: `build_import_graph() -> CompiledStateGraph`
- Integrates with: `agent_service.execute_run(run_id: int)`

- [ ] **Step 1: 检查现有端到端测试**

确认 `tests/test_agent.py` 中的 11 个测试用例：
Run: `cd Workbench && .venv/bin/python -m unittest tests.test_agent -v`

- [ ] **Step 2: 实现状态图编译与事件广播适配**

在 `builder.py` 中用 `StateGraph` 连接所有节点，设置 `SqliteSaver`。
在 `agent_service.py` 中将原本的 `while step < max_steps` ReAct 循环替换为 `compiled_graph.stream(...)` 迭代，每进入一个节点时写入 `import_run_events` 并更新 `import_runs.stage`。

- [ ] **Step 3: 升级 MockProvider 支持节点模拟**

确保在 `LLM_PROVIDER=mock` 环境下，Mock 节点直接返回已结构化的合法测试数据，保证无网无 Key 环境完全测试通过。

- [ ] **Step 4: 运行全部回归测试**

Run: `cd Workbench && .venv/bin/python -m unittest tests.test_agent -v`
Expected: 11 tests passed.

- [ ] **Step 5: 提交代码**

```bash
git add Workbench/app/agent/graph/builder.py Workbench/app/agent/agent_service.py Workbench/app/agent/mock_provider.py
git commit -m "feat(agent): refactor agent_service to use LangGraph with full test pass"
```

---

### Task 6: 端到端全形态资料与防发散验收

**Files:**
- Create: `Workbench/tests/test_agent_langgraph_e2e.py`

- [ ] **Step 1: 编写多形态资料导入测试**
  - 测试形态 A：仅 Excel 多 Sheet 包含产品与已有套餐。
  - 测试形态 B：Word 包含产品列表与两段话套餐说明。
  - 测试形态 C：只有一段无套餐的纯文本，验证输出套餐列表严格为空（不凭空推测）。

- [ ] **Step 2: 运行端到端验收**

Run: `cd Workbench && .venv/bin/python -m unittest tests.test_agent_langgraph_e2e -v`
Expected: PASS

- [ ] **Step 3: 提交代码与实施报告**

```bash
git add Workbench/tests/test_agent_langgraph_e2e.py
git commit -m "test(agent): add multi-format and anti-hallucination E2E tests"
```
