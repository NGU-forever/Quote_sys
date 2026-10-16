# QuoteSys 报价系统设计器实施计划 (Quote System Designer Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 QuoteSys 报价系统设计器，让不懂技术的老板在 10 分钟内通过第 0 屏可点原型、8 步向导和真实业务数据生成量身定制的报价系统界面与定稿 UiSpec。

**Architecture:** 
前后端解耦与 Spec 驱动。后端通过纯 SQL 计算数据画像指标（Signals），经规则排序并选择真实数据片段，生成 3 套预设与正式 UiSpec；通过三道门校验（枚举门、字段门、结构门）与有界自愈保证合法性。前端基于 Vue 3 SFC 实现固定运行时渲染器（SpecLoader → LayoutEngine → BlockRegistry → ThemeProvider），支持 5 套布局骨架、16 种标准化 Block 和 3 套 Token 风格包，支持一次性定稿与受限微调。

**Tech Stack:** 
- 后端：FastAPI, SQLAlchemy 2.0, PostgreSQL / SQLite (测试支持), Pydantic v2
- 前端：Vue 3 SFC, Pinia, Vite, CSS Variables (Design Tokens), Tailwind/PostCSS
- 测试：pytest, vitest

**Spec:** `docs/superpowers/specs/2026-10-12-quote-system-designer-design.md`

## Global Constraints

- **Spec + 固定渲染器，不生成代码**：模型/规则只产出 `UiSpec` JSON，严禁生成任意 Vue/HTML 代码。
- **一次性定稿**：定稿前可无限重做与对比；点击“定稿”后 Spec 冻结，业务数据永不受影响；微调仅限“模块开关、列加减、风格包替换”。
- **白名单与三道门校验**：所有骨架、block、密度、字段名必须符合白名单；模型产出必须过校验，失败最多 3 次自愈后规则兜底。
- **三层 Design Token**：`primitive → semantic → component`；组件内严禁写死颜色/圆角/阴影，品牌色仅覆盖 `--color-primary`。
- **数据来源三级明示**：第 0 屏必须显式标注数据源：①已有数据、②已上传资料解析、③行业样例。
- **缺失优雅降级**：严禁出现空白、null 或满屏 "—"。

---

### Task 1: 新增设计器数据模型 (ORM & Migration)

**Files:**
- Create: `Workbench/app/models/ui_designer.py`
- Modify: `Workbench/app/models/__init__.py`
- Test: `Workbench/tests/test_ui_designer_models.py`

**Interfaces:**
- Produces: 
  - `UiSpecDraft`: id, created_by, payload_json, signals_json, preview_preset, created_at
  - `UiSpec`: id, spec_version, payload_json, source_level, finalized_by, finalized_at, is_active
  - `UiSignalSnapshot`: id, draft_id, product_count, quote_count, sales_count, consumable_ratio, binding_density, payload_json, created_at
  - `UiStylePreset`: id, preset_id, name, tokens_json, is_builtin, created_at
  - `UiSpecRevision`: id, spec_id, patch_json, created_at

- [x] **Step 1: 编写数据模型失败测试**
编写 `Workbench/tests/test_ui_designer_models.py`，验证 5 张新表的增删改查、`ui_specs.is_active` 单激活约束逻辑及初始风格包数据表结构。

- [x] **Step 2: 运行测试验证失败**
Run: `pytest Workbench/tests/test_ui_designer_models.py -v`
Expected: FAIL (models not found)

- [x] **Step 3: 实现 SQLAlchemy ORM 模型**
创建 `Workbench/app/models/ui_designer.py`，定义 `UiSpecDraft`, `UiSpec`, `UiSignalSnapshot`, `UiStylePreset`, `UiSpecRevision`，并在 `Workbench/app/models/__init__.py` 中导出。

- [x] **Step 4: 运行测试验证通过**
Run: `pytest Workbench/tests/test_ui_designer_models.py -v`
Expected: PASS

- [x] **Step 5: 提交代码**
```bash
git add Workbench/app/models/ui_designer.py Workbench/app/models/__init__.py Workbench/tests/test_ui_designer_models.py
git commit -m "feat(designer): add ui_designer database models"
```

---

### Task 2: UiSpec 数据规范、Pydantic Schema 与三道门校验器

**Files:**
- Create: `Workbench/app/designer/schema.py`
- Create: `Workbench/app/designer/validator.py`
- Test: `Workbench/tests/test_designer_validator.py`

**Interfaces:**
- Consumes: `Product`, `Package`, `Quote`, `User` 字段反射
- Produces:
  - `UiSpecModel`: Pydantic 规范校验模型
  - `ValidationReport`: isValid, issues, fixedSpec
  - `validate_ui_spec(spec: dict, db_fields_registry: dict) -> ValidationReport`
  - `repair_spec_with_rules(spec: dict, issues: list) -> dict`

- [x] **Step 1: 编写校验器与白名单测试**
测试覆盖：
- ① 枚举门：非法 skeleton, density, preset_id, module 回退默认值并记录 issue；
- ② 字段门：`entities.*.list_columns` 非法字段注入自动剔除；
- ③ 结构门：非法 block 放置在不兼容骨架中自动补齐/移除；
- 规则兜底：严重损坏的 spec 回退到合法保底 spec。

- [x] **Step 2: 运行测试验证失败**
Run: `pytest Workbench/tests/test_designer_validator.py -v`
Expected: FAIL

- [x] **Step 3: 编写 Pydantic 模型与三道门校验器**
实现白名单枚举（5 骨架、16 块、3 风格、3 密度等）、字段注册表获取函数和修复策略。

- [x] **Step 4: 运行测试验证通过**
Run: `pytest Workbench/tests/test_designer_validator.py -v`
Expected: PASS

- [x] **Step 5: 提交代码**
```bash
git add Workbench/app/designer/schema.py Workbench/app/designer/validator.py Workbench/tests/test_designer_validator.py
git commit -m "feat(designer): implement UiSpec schemas and 3-gate validator"
```

---

### Task 3: 纯后端画像指标计算（Signals）与排序算法（Ranking）

**Files:**
- Create: `Workbench/app/designer/signals.py`
- Create: `Workbench/app/designer/ranking.py`
- Test: `Workbench/tests/test_designer_signals_and_ranking.py`

**Interfaces:**
- Consumes: SQLAlchemy Session (`Product`, `Package`, `DeviceBinding`, `Quote`, `User`)
- Produces:
  - `compute_signals(db: Session) -> dict`: 包含 consumable_ratio, binding_density, product_count, quote_count, sales_count, min_price_p50 等。
  - `rank_preview_presets(signals: dict) -> list[str]`: 根据 §7.3 条件命中即停规则返回 `['medical-clean', ...]` 或 `['1', '2', '3']`。
  - `determine_source_level(signals: dict) -> str`: 返回 `'database'`, `'assets'`, `'sample'`。

- [x] **Step 1: 编写根据 §13.1 规格的断言测试**
输入固定 seed：30 商品（20 耗材/10 设备）、12 绑定、2 套餐、15 单据、2 销售。
断言：
1. 排序 = [① 开单型, ② 批发型, ③ 管理型]
2. 空库情况：排序固定 [①, ②, ③] 且 source_level = 'sample'
3. consumable_ratio 计算精确度。

- [x] **Step 2: 运行测试验证失败**
Run: `pytest Workbench/tests/test_designer_signals_and_ranking.py -v`
Expected: FAIL

- [x] **Step 3: 实现 SQL 聚合计算与排序规则**
使用纯 SQL 聚合函数实现指标计算，保证单次执行 <200ms；编写命中即停的排序状态机。

- [x] **Step 4: 运行测试验证通过**
Run: `pytest Workbench/tests/test_designer_signals_and_ranking.py -v`
Expected: PASS

- [x] **Step 5: 提交代码**
```bash
git add Workbench/app/designer/signals.py Workbench/app/designer/ranking.py Workbench/tests/test_designer_signals_and_ranking.py
git commit -m "feat(designer): implement signals calculation and preset ranking"
```

---

### Task 4: 真实数据填充选择器与 3 级来源降级

**Files:**
- Create: `Workbench/app/designer/sampler.py`
- Test: `Workbench/tests/test_designer_sampler.py`

**Interfaces:**
- Consumes: SQLAlchemy Session, `source_level`
- Produces:
  - `sample_preview_data(db: Session, signals: dict) -> dict`:
    - 挑选商品列表（6-8 条）：1 有图 + 1 最长名 + 1 最高价 + 1 最低价 + 稳定排序
    - 套餐推荐：差额最大套餐（如省 ¥520）
    - 报价单：真实单据或显式标注的样例单据
    - 底价校验演示：1 条 ✓ + 1 条 ⚠
    - 缺失降级策略：无图降级、无套餐隐藏、无价格显示“面议”

- [x] **Step 1: 编写测试断言数据抽取与降级表现**
测试覆盖 §13.1 断言 2, 3, 6 及降级逻辑（无价格不显示 0，显示“面议”）。

- [x] **Step 2: 运行测试验证失败**
Run: `pytest Workbench/tests/test_designer_sampler.py -v`
Expected: FAIL

- [x] **Step 3: 实现真实数据采样器与内置行业样例包**
实现多维度数据抽取与安全兜底。

- [x] **Step 4: 运行测试验证通过**
Run: `pytest Workbench/tests/test_designer_sampler.py -v`
Expected: PASS

- [x] **Step 5: 提交代码**
```bash
git add Workbench/app/designer/sampler.py Workbench/tests/test_designer_sampler.py
git commit -m "feat(designer): implement sample data extractor and fallbacks"
```

---

### Task 5: 预设包生成、向导答案编译器与定稿管理

**Files:**
- Create: `Workbench/app/designer/compiler.py`
- Create: `Workbench/app/designer/presets.py`
- Test: `Workbench/tests/test_designer_compiler.py`

**Interfaces:**
- Consumes: signals, answers, preset_id
- Produces:
  - `build_preset_draft(preset_id: str, signals: dict, sample_data: dict) -> dict`
  - `compile_wizard_to_spec(answers: dict, signals: dict, base_spec: dict) -> dict`
  - `generate_summary_text(profile: dict) -> str` (§8 模板)

- [x] **Step 1: 编写预设生成与向导编译测试**
测试覆盖：第 0 屏选中预设直接推导第 1/3/4/7 屏；向导答案编译出有效规范；一句话人话摘要生成。

- [x] **Step 2: 运行测试验证失败**
Run: `pytest Workbench/tests/test_designer_compiler.py -v`
Expected: FAIL

- [x] **Step 3: 实现 3 套预设定义与编译器**
实现编译规则，将选项映射为 skeleton, density, blocks, rules 等。

- [x] **Step 4: 运行测试验证通过**
Run: `pytest Workbench/tests/test_designer_compiler.py -v`
Expected: PASS

- [x] **Step 5: 提交代码**
```bash
git add Workbench/app/designer/compiler.py Workbench/app/designer/presets.py Workbench/tests/test_designer_compiler.py
git commit -m "feat(designer): implement preset generation and wizard compiler"
```

---

### Task 6: 设计器后端 API 路由实现与集成

**Files:**
- Create: `Workbench/app/api/designer.py`
- Modify: `Workbench/app/main.py`
- Test: `Workbench/tests/test_designer_api.py`

**Interfaces:**
- Endpoints:
  - `POST /api/designer/signals`
  - `POST /api/designer/preview`
  - `POST /api/designer/answer`
  - `POST /api/designer/compile`
  - `POST /api/designer/finalize`
  - `GET /api/designer/spec`
  - `PATCH /api/designer/spec`
  - `POST /api/designer/spec/rollback`
  - `POST /api/designer/reset`

- [x] **Step 1: 编写 API 接口端到端测试**
测试完整生命周期：获取 signals → 选预设预览 → 提交问卷 → 编译定稿 → 查询激活 Spec → 微调与回退 → 逃生舱 reset。

- [x] **Step 2: 运行测试验证失败**
Run: `pytest Workbench/tests/test_designer_api.py -v`
Expected: FAIL

- [x] **Step 3: 实现 API 路由与管理员鉴权**
挂载到 `/api/designer`，复用 `require_user` 并校验管理员权限。

- [x] **Step 4: 运行测试验证通过**
Run: `pytest Workbench/tests/test_designer_api.py -v`
Expected: PASS

- [x] **Step 5: 提交代码**
```bash
git add Workbench/app/api/designer.py Workbench/app/main.py Workbench/tests/test_designer_api.py
git commit -m "feat(designer): implement designer API endpoints"
```

---

### Task 7: 前端 Token 体系与 3 套风格包 (ThemeProvider)

**Files:**
- Create: `Quote/src/renderer/tokens/presets.js`
- Create: `Quote/src/renderer/tokens/ThemeProvider.vue`
- Create: `Quote/src/renderer/tokens/theme.css`
- Test: `Quote/src/renderer/tokens/__tests__/tokens.spec.js`

**Interfaces:**
- Produces:
  - 3 套风格预设（medical-clean, industrial-dense, brand-premium）
  - CSS 变量动态注入函数 `applyThemeTokens(presetId, customPrimary)`
  - 对比度检测与自动加深 15% 算法

- [x] **Step 1: 编写 Token 变量注入与对比度算法单测**
- [x] **Step 2: 运行测试验证失败**
- [x] **Step 3: 实现 Design Token 映射与 ThemeProvider 组件**
- [x] **Step 4: 运行测试验证通过**
- [x] **Step 5: 提交代码**

---

### Task 8: 前端渲染器核心：SpecLoader、LayoutEngine 与 5 个骨架

**Files:**
- Create: `Quote/src/renderer/SpecLoader.js`
- Create: `Quote/src/renderer/LayoutEngine.vue`
- Create: `Quote/src/renderer/skeletons/CatalogLeftFormRight.vue`
- Create: `Quote/src/renderer/skeletons/FormFirstWizard.vue`
- Create: `Quote/src/renderer/skeletons/ListDetailSplit.vue`
- Create: `Quote/src/renderer/skeletons/DashboardGrid.vue`
- Create: `Quote/src/renderer/skeletons/MobileSingleColumn.vue`
- Test: `Quote/src/renderer/__tests__/layout.spec.js`

**Interfaces:**
- Produces:
  - 槽位分发机制（Slots & Block Placement）
  - 缺失区块默认补齐逻辑

- [x] **Step 1: 编写骨架槽位渲染测试**
- [x] **Step 2: 运行测试验证失败**
- [x] **Step 3: 实现 5 套布局骨架组件与 LayoutEngine**
- [x] **Step 4: 运行测试验证通过**
- [x] **Step 5: 提交代码**

---

### Task 9: 前端 BlockRegistry 与 16 个标准化 Block

**Files:**
- Create: `Quote/src/renderer/BlockRegistry.js`
- Create: `Quote/src/renderer/blocks/CustomerInfoBlock.vue`
- Create: `Quote/src/renderer/blocks/ItemPickerBlock.vue`
- Create: `Quote/src/renderer/blocks/ItemTableEditableBlock.vue`
- Create: `Quote/src/renderer/blocks/ItemTableReadonlyBlock.vue`
- Create: `Quote/src/renderer/blocks/PriceSummaryBlock.vue`
- Create: `Quote/src/renderer/blocks/FloorPriceAlertBlock.vue`
- Create: `Quote/src/renderer/blocks/BundleSuggestionBlock.vue`
- Create: `Quote/src/renderer/blocks/DiscountPanelBlock.vue`
- Create: `Quote/src/renderer/blocks/QuoteMetaBlock.vue`
- Create: `Quote/src/renderer/blocks/NotesAndTermsBlock.vue`
- Create: `Quote/src/renderer/blocks/AttachmentUploadBlock.vue`
- Create: `Quote/src/renderer/blocks/ApprovalStatusBlock.vue`
- Create: `Quote/src/renderer/blocks/ActivityTimelineBlock.vue`
- Create: `Quote/src/renderer/blocks/ExportActionsBlock.vue`
- Create: `Quote/src/renderer/blocks/StatsCardsBlock.vue`
- Create: `Quote/src/renderer/blocks/RecentQuotesBlock.vue`
- Test: `Quote/src/renderer/__tests__/blocks.spec.js`

**Interfaces:**
- Produces: 动态 Block 解析注册器与 16 种无硬编码样式的受限 Block

- [x] **Step 1: 编写 Block 组件渲染与数据绑定单测**
- [x] **Step 2: 运行测试验证失败**
- [x] **Step 3: 实现 16 种 Block 组件与注册表**
- [x] **Step 4: 运行测试验证通过**
- [x] **Step 5: 提交代码**

---

### Task 10: 第 0 屏可点原型与 8 步向导界面交互

**Files:**
- Create: `Quote/src/designer/DesignerContainer.vue`
- Create: `Quote/src/designer/Screen0PreviewCards.vue`
- Create: `Quote/src/designer/ScreenWizard.vue`
- Create: `Quote/src/designer/Screen8SummaryConfirm.vue`
- Modify: `Quote/src/quote/router.js`
- Test: `Quote/src/designer/__tests__/wizard.spec.js`

**Interfaces:**
- 完整贯通从第 0 屏（3 级数据来源标注、异步加载、可点选品、合计联动）到 8 步向导、定稿与业务界面渲染。

- [x] **Step 1: 编写向导与第 0 屏交互测试**
- [x] **Step 2: 运行测试验证失败**
- [x] **Step 3: 实现设计器交互流程界面**
- [x] **Step 4: 运行测试验证通过**
- [x] **Step 5: 提交代码**

---

### Task 11: 全流程端到端集成验证与质量门禁断言

**Files:**
- Test: `Workbench/tests/test_designer_full_lifecycle.py`
- Test: `Quote/src/__tests__/golden_specs.spec.js`

**Interfaces:**
- 校验 §13.1 全部 9 条核心断言，确保规则兜底永不向用户报错，保证业务系统按 Spec 正确切换。

- [x] **Step 1: 编写全流程验收测试**
- [x] **Step 2: 执行全量测试验证**
- [x] **Step 3: 提交代码与集成验收记录**

---

# 补充阶段（2026-10-13）：Spec 表达力接入、黄金屏与 M4

> 上一阶段完成后审计发现：Spec 的 `entities/output/rules` 后端产出但前端零消费；
> 仓库缺少 Tailwind 导致设计器无样式；黄金屏仅有 JSON 断言无截图基准；
> M4（模型接入）未做。以下为本轮补齐项，验收标准见设计文档 §17。

## Task 12: entities / output / rules 接入渲染器

**Files:**
- New: `Quote/src/renderer/SpecContext.js`、`SpecProvider.js`、`SpecRenderer.vue`、`QuotePrintArea.vue`
- Modify: `Quote/src/renderer/blocks/*.vue`（10 个）、`Quote/src/designer/DesignerContainer.vue`
- Test: `Quote/src/renderer/__tests__/spec_context.test.js`

- [x] Spec 上下文（标签/列/规则/打印配置）+ 格式化（面议与空值降级）
- [x] 10 个 block 消费 entities/output/rules（列集合、术语、底价保护、审批、单号规则）
- [x] `QuotePrintArea` 由 `output.quote_pdf` 驱动（纸张/页眉/表格/底价/条款 + @page 注入）
- [x] 宿主改用 `SpecRenderer`，去掉硬编码 `total-amount=98500` / `has-violation=true`
- [x] 补齐 Tailwind 样式链路（preflight 关闭，不影响既有界面）
- [x] 单测 6 项

## Task 13: 黄金屏截图基准与回归门禁

**Files:**
- New: `Quote/visual/{index.html,main.js,seed.js,harness.css,PrintHarness.vue}`、`Quote/vite.visual.config.js`
- New: `Quote/tests/visual/capture.mjs`、`compare.py`、`Quote/visual/baseline/*.png`（18 张）
- Modify: `Quote/package.json`（`test:visual` / `test:visual:update`）、`.gitignore`

- [x] 3 风格 × 5 骨架 = 15 张屏幕基准 + 3 张打印版式基准
- [x] 自包含 HTML + file:// 渲染（绕开受限环境下 Chrome 连 localhost 挂起）
- [x] IIFE 构建显式 define `process.env.NODE_ENV`（否则浏览器 `process is not defined`）
- [x] Pillow 像素比对，默认阈值 0.05%，失败输出差异图
- [x] 双向验证：改主色 token → 5 张失败；还原 → 18/18 通过

## Task 14: M4 大模型接入（画像 + 术语 + 有界自愈）

**Files:**
- New: `Workbench/app/designer/{llm.py,profiles.py,terminology.py}`
- Modify: `Workbench/app/designer/compiler.py`、`Workbench/app/api/designer.py`
- Test: `Workbench/tests/test_designer_llm.py`（18 项）

- [x] 资料 + 库内统计 → 业务画像（未配置模型时纯规则，功能不降级）
- [x] 行业术语本地化（底价/供货价/同行价/批发价 + 促销语气）
- [x] 模型提案过三道门，失败回传具体错误，最多 3 次自愈，仍失败回退规则 Spec
- [x] 新增 `POST /api/designer/profile`；`/compile` 支持 `enrich` 开关
- [x] 顺带修复：5 骨架全部可达、`customers` 模块产出

## Task 15: 文档同步

- [x] 设计文档新增 §17 实现状态与决策记录（含对正文的修订与未完成清单）
- [x] 修正设计文档"4 张新表"笔误（实际 5 张）
- [ ] 待办：`nav` 段接入、`source_level` 语义修正、设计器测试统一到 PostgreSQL、黄金屏接入 CI

