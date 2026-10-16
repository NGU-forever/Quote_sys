# QuoteSys 报价系统设计器 —— 设计文档

| | |
|---|---|
| 文档版本 | v1.0 |
| 日期 | 2026-10-12 |
| 状态 | 待评审（评审通过即可开工） |
| 目标读者 | 实现的工程师；后续接手的 PM |
| 依赖 | 现有 QuoteSys 后端（FastAPI + PostgreSQL + 现有 Agent 管线） |

---

## 0. 一句话

让一个**不懂技术的企业老板**，在 10 分钟内拿到一套**长得像他家生意**的报价系统前端：先看三个用他自己数据渲染的可点原型，选一个，回答几个问题，定稿——之后这套系统的布局、字段、术语、风格就固定下来，**永远不会变成他维护不起的东西**。

---

## 1. 目标与非目标

### 1.1 目标用户

- 中小企业的**老板 / 销售负责人**，不懂技术，不懂设计，不会写 prompt
- 他**描述不出**自己想要什么，但**一眼能认出**好坏
- 他买这套系统的真实动机：**怕销售乱报价、泄露底价、报价单拿不出手**

### 1.2 成功判据（可量化）

| 指标 | 目标值 | 说明 |
|---|---|---|
| 首屏到点击预览 | ≤ 10 秒 | 超过说明三张预览没有立即可辨的差异 |
| 三张预览选择分布 | 每张 10%–70% | 某张 <10% 说明是废案；>70% 说明另两张没价值 |
| "都不像"点击率 | ≤ 25% | 高于此说明预设答案包没覆盖主流人群 |
| 向导完成率（进入→定稿） | ≥ 85% | 低于说明用户中途不信了 |
| 定稿后 7 日内"换一套方案"使用率 | ≤ 10% | 高于说明第 0 屏说服力不够 |

### 1.3 明确不做（划清边界，避免项目失控）

| 不做 | 原因 |
|---|---|
| 生成 Vue 组件 / 页面代码 | 一客户一分叉，升级/测试/回滚/开源协作全崩 |
| 通用 UI 生成（任意行业的任意系统） | 必败；本项目只做**报价**这一个垂直场景 |
| 持续重生成 Spec | 已定"一次性定稿"；重新生成会作废用户刚建立的认知 |
| 让模型自由生成价格与法律条款文本 | 高风险内容；模型只做**带入与排版** |
| 自定义组件 / 插件化渲染器 | 与"表达力收窄"的核心决策冲突（见 D5） |
| 无限自由布局 | 布局只能从 5 个骨架里选，这是护城河不是限制 |

---

## 2. 核心架构决策（ADR）

### D1 · Spec + 固定渲染器，不生成代码

- **决策**：模型/规则只产出 `UiSpec`（JSON），由一个固定运行时渲染界面。
- **理由**：PPT 类项目的本质是「结构 + 风格 → 产物」，从不生成渲染引擎；生成代码会让每个客户成为独立分叉。
- **代价**：表达力有上限——这是**故意的**（见 D5）。

### D2 · 一次性定稿

- **决策**：定稿前可无限次重做与对比；点击"定稿"后 Spec 冻结，业务数据永不受 Spec 变更影响。
- **理由**：非技术用户无法承受配置漂移；同时它**省掉了整块工程**：Spec 迁移、配置兼容矩阵、回滚链都不需要。
- **代价**：定稿前的体验必须极其可靠 → 三张预览必须是**可点的真原型**，不是静态图。
- **安全阀**：
  - 定稿后仅允许三类微调：**开关模块 / 加减列 / 换风格包**，且均可一键回退
  - 提供"换一套方案"逃生舱：重新走向导，**只替换 Spec，不动业务数据**

### D3 · 骨架由规则决定，模型只做两件事

- **决策**：骨架/密度/模块由向导答案 + 画像指标**确定性映射**；模型只用于 ①资料→业务画像 ②文案与术语本地化。
- **理由**：约 70% 的 Spec 可纯规则生成；把模型限制在两处，成本、延迟、幻觉风险全部大幅下降，并且**不配 API Key 也能用**（对开源项目是决定性的）。

### D4 · 三层 Design Token

- **决策**：`primitive → semantic → component` 三层 CSS 变量；组件内不写死任何颜色/圆角/阴影。
- **理由**：换肤不崩、可做视觉回归、品牌色覆盖有明确边界（见 6.3）。

### D5 · 白名单 + 三道门校验

- **决策**：骨架、block 类型、密度、字段名、绑定路径**全部是白名单**；模型输出必须过校验，失败走有界自愈。
- **理由**：与现有 Agent 的"模型无写库权限、只能产出受校验候选"是同一哲学；前端侧同理——**模型进不了运行时**。
- **复用**：直接复用现有 `app/agent/schema_utils.py`（内联 `$ref`，避免 strict 服务端 400）与校验/自愈模式。

---

## 3. 系统架构与数据流

### 3.1 组件

```
┌────────────────────────── 前端（Vue 3 SFC） ──────────────────────────┐
│  Designer（第0屏 + 8 步向导 + 实时预览）                              │
│  Renderer（SpecLoader → LayoutEngine → BlockRegistry → ThemeProvider）│
│  ThemeProvider（CSS 变量注入）                                        │
└───────────────────────────────┬───────────────────────────────────────┘
                                │ HTTP
┌───────────────────────────────▼───────────────────────────────────────┐
│ 后端（现有 FastAPI）                                                   │
│  designer/  ├ signals.py   画像指标计算（纯 SQL）                      │
│             ├ ranking.py   排序与填充规则（纯函数）                    │
│             ├ compiler.py  向导答案 + 画像 → UiSpec（规则优先）        │
│             ├ validator.py 三道门校验 + 有界自愈                       │
│             └ profiles.py  资料→业务画像（复用现有 Agent）             │
│  renderer/  └ presets/     3 套风格包（token 数据）                    │
└───────────────────────────────┬───────────────────────────────────────┘
                                │
        PostgreSQL（现有表 + 5 张新表，见 §10）
```

### 3.2 一次完整流程

```
① 计算画像 signals（纯 SQL，<200ms）
② 排序列出 3 套预设答案包 → 各自生成 preview spec（含真实数据填充）
③ 用户点一张（可点原型，真数据）           ← 第 0 屏
④ 8 步向导：确认/微调（第 1/3/4/7 屏已被预览预定）
⑤ 生成正式 UiSpec（规则优先，模型补充文案）
⑥ 三道门校验 → 通过则预览整站；失败有界自愈（最多 3 次）
⑦ 用户点「定稿」→ 写 ui_specs（冻结）
⑧ 业务界面按 Spec 渲染；设置页仅开放三类微调
```

### 3.3 与现有系统的接入点

| 接入点 | 用途 |
|---|---|
| `Product / Package / DeviceBinding / Quote / User / AppSetting` | 画像计算的唯一数据源 |
| 现有 Agent 的 assets 解析产物 | 空库时作为第 ② 级预览数据源 |
| `app_settings` | 存 Spec 指针、品牌色、术语表 |
| 现有 JWT 鉴权 / `get_db` 依赖 | 复用，不新建鉴权 |
| `schema_utils.inline_json_schema` | 校验与模型交互的 schema 生成 |
| 现有 Vitest/Pytest 体系 | 单测与黄金屏 |

---

## 4. UiSpec 规范

### 4.1 完整示例

```json
{
  "spec_version": 1,
  "meta": {
    "generated_at": "2026-10-12 19:40:00",
    "generator": "wizard+llm",
    "source_level": "database",
    "prompt_version": "designer-2026-10-12.1"
  },
  "profile": {
    "industry": "medical",
    "sell_mode": "device_with_consumable",
    "scene": "on_site",
    "roles": ["admin", "sales"],
    "pricing_mode": "floor_price",
    "output_targets": ["print_a4"]
  },
  "style": {
    "preset_id": "medical-clean",
    "density": "comfortable",
    "tokens": { "color.primary": "#0B5FA5", "radius.base": "8px" }
  },
  "modules": ["catalog", "quote_editor", "quotes", "employees", "settings"],
  "nav": [
    { "id": "quote_editor", "label": "开单", "route": "/quote/new", "icon": "edit" },
    { "id": "quotes", "label": "报价单", "route": "/quotes", "icon": "file" }
  ],
  "screens": [
    {
      "id": "quote_editor",
      "skeleton": "catalog-left-form-right",
      "blocks": [
        { "type": "customer_info", "props": { "fields": ["customer_name", "customer_phone"] } },
        { "type": "item_picker", "props": { "filters": ["category"], "show_floor_price": false } },
        { "type": "item_table_editable", "props": { "columns": ["name", "unit_price", "qty", "subtotal", "floor_check"] } },
        { "type": "bundle_suggestion", "props": { "max_items": 2, "show_saving": true } },
        { "type": "floor_price_alert", "props": { "blocking": true, "require_approval": true } },
        { "type": "price_summary", "props": { "show_tax": false } },
        { "type": "export_actions", "props": { "actions": ["save_draft", "print_a4"] } }
      ]
    }
  ],
  "entities": {
    "product": {
      "list_columns": ["sku_id", "name", "category", "min_price", "unit"],
      "filters": ["category", "keyword"],
      "form_sections": [
        { "title": "基本信息", "fields": ["sku_id", "category", "name", "unit"] },
        { "title": "价格", "fields": ["min_price", "max_price", "raw_price_desc"] }
      ],
      "labels": { "sku_id": "产品编号", "min_price": "最低底价" }
    }
  },
  "output": {
    "quote_pdf": {
      "paper": "A4",
      "header_style": "logo_left_company_right",
      "table_style": "bordered",
      "show_floor_price": false,
      "terms_block": "company_default"
    }
  },
  "rules": {
    "price_floor_guard": true,
    "bundle_validation": true,
    "quote_no_pattern": "QT-{YYYYMMDD}-{0001}",
    "price_visibility": "internal",
    "approval_required": true
  }
}
```

### 4.2 字段约束

| 段 | 字段 | 类型 | 约束 |
|---|---|---|---|
| `meta` | `spec_version` | int | 必填，当前 1 |
| | `source_level` | enum | `database` / `assets` / `sample`，用于 UI 明示数据来源 |
| `profile` | `industry` | enum | `medical` / `industrial` / `service` / `retail` / `other` |
| | `sell_mode` | enum | `device_only` / `consumable_only` / `device_with_consumable` / `service` / `mixed` |
| | `scene` | enum | `on_site` / `office` / `customer_self` / `mobile` |
| | `pricing_mode` | enum | `floor_price` / `negotiable` / `tiered` / `bundle_fixed` |
| `style` | `preset_id` | enum | `medical-clean` / `industrial-dense` / `brand-premium` |
| | `density` | enum | `comfortable` / `compact` / `spacious` |
| | `tokens` | map | **只允许覆盖 `color.primary` 与 `color.accent`**，其余由 preset 决定 |
| `modules` | — | enum[] | 见 5.3；至少含 `quote_editor` |
| `screens[].skeleton` | — | enum | 5 个骨架之一（见 5.1） |
| `screens[].blocks[].type` | — | enum | 16 个 block 之一（见 5.2） |
| `entities.*.list_columns/fields` | — | string[] | **必须是后端已登记字段名**（见 4.4 第二道门） |
| `output.quote_pdf.paper` | — | enum | `A4` / `A5` / `Letter` |

### 4.3 枚举全集

```
skeleton     : catalog-left-form-right | form-first-wizard | list-detail-split
               | dashboard-grid | mobile-single-column
density      : comfortable | compact | spacious
preset_id    : medical-clean | industrial-dense | brand-premium
modules      : catalog | quote_editor | quotes | employees | settings | approval | customers
block.type   : （16 种，见 5.2）
```

### 4.4 三道门校验（`validator.py`）

| 门 | 校验内容 | 失败处理 |
|---|---|---|
| ① 枚举门 | 所有枚举字段取值在白名单内 | 拒绝该项，回退默认值，记录 issue |
| ② 字段门 | `entities.*.list_columns` / `fields` 必须在**后端字段注册表**里（由 `Product/Package/Quote/User` 模型推导） | 剔除非法字段；若某列表为空则该列集合回退到该实体默认列 |
| ③ 结构门 | `screens[].blocks` 必须是该 `skeleton` 允许的 block（见 5.3 矩阵）；必填 block 缺失时补齐默认 | 补默认；补不齐则该屏回退到该骨架的标准配置 |

**有界自愈**：把三道门的具体错误回传模型，最多 3 次；超过 3 次直接用**规则兜底 Spec**（保证永远能出结果）。

---

## 5. 骨架与 Block 目录

### 5.1 五个骨架与槽位

| id | 用途 | 槽位（block 只能放进对应槽） |
|---|---|---|
| `catalog-left-form-right` | 现场开单主力 | `left_rail` / `main_header` / `main_body` / `main_footer` |
| `form-first-wizard` | 复杂报价、需审批 | `steps_header` / `step_body` / `step_footer` |
| `list-detail-split` | 归档、管理 | `filters` / `list` / `detail_header` / `detail_body` / `detail_actions` |
| `dashboard-grid` | 老板/管理视角 | `stats_row` / `grid_left` / `grid_right` |
| `mobile-single-column` | 手机现场 | `top_bar` / `content` / `bottom_bar` |

### 5.2 Block 白名单（16 种）

| type | 说明 | 关键 props | 允许的骨架 |
|---|---|---|---|
| `customer_info` | 客户信息 | `fields[]`, `collapsible` | ①②③⑤ |
| `item_picker` | 商品选择器 | `filters[]`, `show_floor_price`, `layout` | ①②⑤ |
| `item_table_editable` | 可编辑明细 | `columns[]`, `allow_batch_add` | ①②⑤ |
| `item_table_readonly` | 只读明细 | `columns[]` | ③ |
| `price_summary` | 合计与金额 | `show_tax`, `sticky` | ①②③⑤ |
| `floor_price_alert` | 底价校验提示 | `blocking`, `require_approval` | ①②⑤ |
| `bundle_suggestion` | 套餐推荐 | `max_items`, `show_saving` | ①② |
| `discount_panel` | 折扣与议价 | `max_discount`, `need_approval` | ②③ |
| `quote_meta` | 单号/有效期/销售 | `fields[]` | ①③ |
| `notes_and_terms` | 备注与条款 | `templates[]`, `editable` | ②③ |
| `attachment_upload` | 附件 | `accept[]`, `max_size` | ②③ |
| `approval_status` | 审批状态 | `show_history` | ②③④ |
| `activity_timeline` | 操作时间线 | `max_items` | ③④ |
| `export_actions` | 导出/打印动作 | `actions[]` | ①②③ |
| `stats_cards` | 看板数字卡 | `metrics[]` | ④ |
| `recent_quotes` | 最近单据 | `max_items` | ④ |

> 表中"允许的骨架"①②③④⑤ 对应 5.1 的行序。矩阵是**硬约束**，第三道门按它校验。

### 5.3 骨架 ↔ 模块

| 模块 | 默认块组合 | 何时开启 |
|---|---|---|
| `catalog` | `item_picker` + `item_table_editable`（商品管理页） | `sell_mode != service` |
| `quote_editor` | 依骨架 | **必开** |
| `quotes` | `list-detail-split` + `export_actions` | 恒开 |
| `employees` | 员工列表 | `len(sales_users) > 1` |
| `settings` | 恒开 | 恒开 |
| `approval` | `approval_status` | `pricing_mode != floor_price` 或用户勾选 |
| `customers` | `customer_info` + 历史 | 客户重复度 > 1.5 |

---

## 6. 风格包（Design Tokens）

### 6.1 三层结构

```
primitive   --qs-blue-700: #0B5FA5;  --qs-gray-050: #F6F8FB; ...
semantic    --color-bg: var(--qs-white);  --color-primary: var(--qs-blue-700); ...
component   --btn-bg: var(--color-primary); --table-row-h: 44px; ...
```

**组件只允许使用 component 层变量**；`preset` 提供 primitive + semantic，品牌色只覆盖 semantic 里的 `--color-primary` / `--color-accent`。

### 6.2 三套风格包

| token | medical-clean | industrial-dense | brand-premium |
|---|---|---|---|
| `color.bg` | `#FFFFFF` | `#FFFFFF` | `#FBFAF8` |
| `color.surface` | `#F6F8FB` | `#F2F4F7` | `#FFFFFF` |
| `color.primary` | `#0B5FA5` | `#175C8C` | `#14532D` |
| `color.accent` | `#2E86C1` | `#0E7490` | `#B08D57` |
| `color.text` | `#1B2733` | `#111827` | `#1A1A1A` |
| `color.text-muted` | `#5A6B7B` | `#6B7280` | `#6B6B6B` |
| `color.border` | `#E3E9F0` | `#D7DDE5` | `#EAE6DF` |
| `color.success / warn / danger` | `#12805C` / `#B4761A` / `#C0392B` | 同左 | `#15803D` / `#A16207` / `#B91C1C` |
| `radius.base / card / input` | `8 / 10 / 6 px` | `4 / 4 / 4 px` | `2 / 2 / 2 px` |
| `shadow.card` | `0 8px 24px rgba(16,24,40,.06)` | `0 1px 0 rgba(0,0,0,.06)` | `none` |
| `font.heading` / `font.body` | 系统栈 / 系统栈 | 系统栈 / 系统栈 | 衬线标题 / 系统栈正文 |
| `font.size.base / line` | `14 / 22 px` | `14 / 20 px` | `15 / 26 px` |
| `font.numeric` | 常规 | **`tabular-nums` 等宽** | 常规，字号 +1 |
| `space.scale` | 1.0 | 0.85 | 1.25 |
| `table.row_height` | `44px` | `34px` | `52px` |
| `table.zebra` | `false` | `true` | `false` |
| `table.header` | 仅下边框 | 吸顶 + 底色 `#EEF2F6` | 小字大字距，无底色 |
| `quote_pdf` | 蓝灰页眉，参数表优先 | 全表格线，编号突出 | logo 大、留白、价格弱化居中 |

### 6.3 品牌色覆盖规则

- 用户提供主色 → 只写 `--color-primary`；`accent` 由 preset 决定
- 与 `color.bg` 的对比度 < 3:1 时自动加深 15% 并提示"已为你调整以保证可读性"
- **不允许**用户覆盖任何尺寸/字体/圆角 token（保护风格一致性）

---

## 7. 第 0 屏：三张预览

### 7.1 三套预设答案包

> 点击一张预览 = 一次性答完向导第 1/3/4/7 屏；第 2/5/6 屏仍可确认或修改。

| | ① 开单型 | ② 批发型 | ③ 管理型 |
|---|---|---|---|
| 骨架 | `catalog-left-form-right` | `list-detail-split` | `dashboard-grid` |
| 密度 | comfortable | compact | spacious |
| 风格 | medical-clean | industrial-dense | brand-premium |
| 预设答案 | 设备+耗材 / 现场开单 / 按底价卖 | 耗材为主 / 办公室 / 阶梯价 | 全模块 / 管理视角 / 折扣审批 |
| 文案 | "适合在客户现场开单：左边挑货，右边出单" | "一屏看 20 个商品：适合商品多、走量" | "先看今天卖了多少，再点进去看单据" |

### 7.2 数据来源三级优先（必须在界面明示）

| 优先级 | 来源 | 界面标注 |
|---|---|---|
| ① | 库里已有数据 | "以下是你库里的真实数据" |
| ② | 已上传资料的解析结果（现有 Agent 产出） | "以下用你上传的《产品最低价格.xlsx》渲染" |
| ③ | 行业样例包 | "以下用行业样例演示，导入数据后会替换" |

**第 ③ 级必须显式标注**，否则用户进后台发现是空库，信任立刻崩塌。

### 7.3 排序规则（命中即停）

| 条件 | 排序 |
|---|---|
| `quote_count > 200` 且 `sales_count > 1`，或用户选"管理视角" | ③ → ① → ② |
| `product_count > 200` 或 `consumable_ratio > 0.6` | ② → ① → ③ |
| `binding_density > 0.8`，或用户选"现场开单" | ① → ② → ③ |
| 空库 / 数据不足（走第 ③ 级） | ① → ② → ③（固定） |

### 7.4 真实数据填充规则

| 位置 | 取值规则 | 目的 |
|---|---|---|
| 商品列表（可见 6–8 条） | 有图 1 条 + 名称最长 1 条 + 价格最高/最低各 1 条 + 其余按 `sku_id` 稳定排序 | 一次暴露所有极端排版情况 |
| 套餐推荐 | `std_price` 与明细合计差额**最大**的套餐 | "省 ¥520" 最直观 |
| 报价单 | 最近一张；无则用"示例单据"并**标注为样例** | 空表最伤信任，假单据不标注是欺骗 |
| 客户名 / 销售名 | 历史数据里的真实值；无则中性占位 | "这是我家系统"的最强信号 |
| 底价校验 | 用真实 `min_price` × 数量计算，**同时演示 1 条 ✓ 与 1 条 ⚠** | 让老板看见"它会拦住销售乱报价" |
| 金额合计 | 全部真实计算 | 用户会按计算器核对 |

### 7.5 缺失降级（禁止出现空白 / null / 满屏 "—"）

| 缺失项 | 降级 |
|---|---|
| 无图片 | 品牌名首字母 + 品类色块 |
| 无套餐 | 隐藏套餐区块，布局自动补位 |
| 无历史单据 | 示例单据 + 样例标注 |
| 无客户名 | 中性占位 + 标注 |
| 无 logo | 品牌首字文字标（不放灰色默认图） |
| 无价格 | 显示"面议"，不显示 0 |
| 整库为空 | 整体走第 ③ 级样例 |

### 7.6 交互与埋点

- 预览**可点**（能真选品、看到合计变化），不是截图
- 每张下方一句"适合谁"，不写技术词
- 底部小字："都不太像？回答 8 个问题，我给你重新做"
- **加载策略**：① 在 3 秒内先出，② ③ 依次补，不要等齐
- 埋点：首屏时长、点击分布、"都不像"点击率、向导完成率

---

## 8. 八步向导交互稿

| 屏 | 标题 / 副标题 | 选项（★=默认选中） | 默认值来源 | 跳过兜底 |
|---|---|---|---|---|
| 0 | 先看一眼结果 | 3 张可点原型 | 画像排序 | 进完整问卷 |
| 1 | 你主要卖什么？ | ★设备+配套耗材 / 只有耗材 / 只有服务 / 混着卖 | `sell_mode` 推断 | 全开 |
| 2 | 谁会用它？ | ★老板+销售 / 只有自己 / 加仓管 / 加财务审批 | `sales_count` | 老板+销售 |
| 3 | 一般在哪开单？ | ★客户现场 / 办公室 / 发给客户自己填 / 手机 | `scene` 推断（无数据→现场） | 客户现场 |
| 4 | 价格怎么定？ | ★按底价卖不议价 / 可打折(需审批) / 阶梯价 / 套餐一口价 | `max_price`、`discount_price` 是否非空 | 按底价卖 |
| 5 | 报价单给谁看？ | ★打印 A4 / 导出 PDF / 发链接 | 恒默认 A4 | 打印 A4 |
| 6 | 放上你的品牌 | logo 上传 + 6 个预设色块 | 已有 logo / `app_settings` | 默认蓝 |
| 7 | 选一个风格 | 3 张风格缩略图 ★A | 行业推断 | medical-clean |
| 8 | 确认一下我理解得对不对 | 一句话摘要 → 对 / 我要改 | 画像 + 向导答案 | —— |

**交互约定**

- 每屏一问、有图、可跳过、可返回；返回时**保留已填状态**
- 第 8 屏是**唯一有效的纠错点**（用户判断不了 `density: compact`，但能判断人话对不对）
- 校验失败**不显示错误码**，翻译成人话并给一键修复，例："这一屏元素有点多，我帮你精简一下？"

**第 8 屏摘要模板**

```
我理解你是：向{客户群}销售{主营品类}{，配套耗材}，{销售角色}在{场景}开单，
{定价方式}{，破价需要审批}，报价单{输出方式}给客户，主色用{品牌色}。
```

示例：*"我理解你是：向医院销售超声设备、配套耗材，销售在客户现场用笔记本开单，按底价卖不议价、破价需要审批，报价单打印 A4 发给客户，主色用你的品牌蓝。"*

---

## 9. 画像层（Signal）

**一份指标两用**：既排序三张预览，也渲染第 8 屏摘要。不要写两套。

### 9.1 指标表

**A 品类结构**

| 指标 | 算法 | 影响 |
|---|---|---|
| 耗材占比 `consumable_ratio` | `count(category='consumable')/total` | >0.6 → ② 排第一 |
| 绑定密度 `binding_density` | `count(bindings)/max(device_count,1)` | >0.8 → 自动推荐耗材；开单型排第一 |
| 套餐渗透率 | 套餐涉及商品数 / 商品总数 | >0.3 → 套餐区块前置；=0 → 隐藏套餐入口 |
| 整购占比 | `fixed_bundle=1` 的套餐占比 | 高 → 套餐用"整套加入" |

**B 规模与价格**

| 指标 | 算法 | 影响 |
|---|---|---|
| `product_count` | `count(products)` | >200 → ② 排第一、搜索前置 |
| 价格分位 | `min_price` 的 p25/p50/p75 | 跨度 >50× → 强制等宽数字 |
| 议价空间 | `max_price`/`discount_price` 非空比例 | >0 → 开折扣面板，第 4 屏默认"可打折" |
| 口径不规整度 | `raw_price_desc` 非空比例 | >20% → 列表保留"原始口径"列 |
| 整箱需求 | `box_price`/`pieces_per_unit` 非空比例 | >30% → 开单区显示"整箱/拆零" |

**C 业务量与角色**

| 指标 | 算法 | 影响 |
|---|---|---|
| `quote_count` | `count(quotes)` | >50 归档必开；>200 → ③ 排第一 |
| 近 30 天活跃 | 单据数与金额 | 看板卡片是否有真实数字 |
| 平均行数 | `avg(len(items_snapshot))` | >8 → 需要批量选品入口 |
| `sales_count` | `count(users.role='sales')` | >1 → 显示销售列与行级隔离 |
| 客户重复度 | 去重客户数 / 单据数 | >1.5 → 常用客户快捷选择 |

**D 品牌与语气**

| 指标 | 影响 |
|---|---|
| 是否有 logo | 三张预览都带真实 logo（冲击力最大） |
| 品牌主色 | 覆盖 `--color-primary`（见 6.3） |
| 行业术语词频（底价/供货价/同行价/批发价） | 字段标签用词，如 `min_price` → "最低底价"/"供货价" |
| 促销词（赠机/买赠/满赠/整购） | 套餐区块语气与"省 ¥X"是否显示 |

### 9.2 实现要求

- 全部为**纯 SQL 聚合**，无模型参与，单次 <200ms（`product_count` 用 `COUNT`，禁止全表读入内存）
- 分位数用 `percentile_cont`
- 结果落 `ui_signal_snapshots`（见 §10），便于复现与回归

---

## 10. 数据模型（只新增表，不改现有表）

```sql
-- 草稿：定稿前的无数次尝试，可丢弃
CREATE TABLE ui_spec_drafts (
  id            SERIAL PRIMARY KEY,
  created_by    INTEGER,
  payload_json  TEXT NOT NULL,          -- UiSpec 草稿
  signals_json  TEXT,                   -- 当时的画像快照
  preview_preset VARCHAR(32),           -- 第 0 屏选中的预设包 id
  created_at    VARCHAR(32) NOT NULL
);

-- 正式 Spec：一次性定稿后冻结
CREATE TABLE ui_specs (
  id            SERIAL PRIMARY KEY,
  spec_version  INTEGER NOT NULL DEFAULT 1,
  payload_json  TEXT NOT NULL,
  source_level  VARCHAR(16) NOT NULL,   -- database / assets / sample
  finalized_by  INTEGER,
  finalized_at  VARCHAR(32) NOT NULL,
  is_active     BOOLEAN NOT NULL DEFAULT TRUE
);

-- 画像快照：复现与回归
CREATE TABLE ui_signal_snapshots (
  id            SERIAL PRIMARY KEY,
  draft_id      INTEGER,
  product_count INTEGER, quote_count INTEGER, sales_count INTEGER,
  consumable_ratio REAL, binding_density REAL,
  payload_json  TEXT,
  created_at    VARCHAR(32) NOT NULL
);

-- 风格包：内置 3 套，允许运营侧扩展
CREATE TABLE ui_style_presets (
  id            SERIAL PRIMARY KEY,
  preset_id     VARCHAR(32) UNIQUE NOT NULL,
  name          VARCHAR(64) NOT NULL,
  tokens_json   TEXT NOT NULL,
  is_builtin    BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    VARCHAR(32) NOT NULL
);

-- 定稿后的三类微调（可回退）
CREATE TABLE ui_spec_revisions (
  id            SERIAL PRIMARY KEY,
  spec_id       INTEGER NOT NULL,
  patch_json    TEXT NOT NULL,
  created_at    VARCHAR(32) NOT NULL
);
```

**约束**：`ui_specs.is_active` 同一时刻只允许一条为真（定稿 + 逃生舱切换时用事务保证）。

---

## 11. 接口清单

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/designer/signals` | 计算并返回画像指标 + 三张预览的排序与填充结果（含 `source_level`） |
| POST | `/api/designer/preview` | 传预设包 id，返回该预览的完整 UiSpec（草稿） |
| POST | `/api/designer/answer` | 提交向导某一屏答案（幂等，支持返回修改） |
| POST | `/api/designer/compile` | 汇总答案 → 正式 UiSpec 草稿 + 校验报告 |
| POST | `/api/designer/finalize` | 定稿：写入 `ui_specs`（冻结） |
| GET | `/api/designer/spec` | 读取当前生效 Spec（业务界面渲染用） |
| PATCH | `/api/designer/spec` | 三类微调：`modules` / `columns` / `preset_id`（写 revisions） |
| POST | `/api/designer/spec/rollback` | 回退到上一版 revisions |
| POST | `/api/designer/reset` | 逃生舱：重新走向导，只换 Spec 不动业务数据 |

**鉴权**：全部要求管理员角色（复用现有 `require_user`）。

---

## 12. 渲染器实现要点

```
SpecLoader     读取 + 三道门复核（后端已校验，前端做防御性检查）
   ↓
LayoutEngine   按 skeleton 把 blocks 填进槽位；缺块用该骨架默认值补齐
   ↓
BlockRegistry  type → Vue 组件；每个组件只接受 2–3 个 variant，不接受任意 props
   ↓
ThemeProvider  三层 token → CSS 变量注入根节点
```

- 组件目录建议：`web/src/renderer/blocks/*.vue`，一个 block 一个组件
- **禁止**在组件里写死颜色/圆角/阴影；一律走 `var(--...)`
- 打印样式：`output.quote_pdf` 独立于屏幕样式，单独一套 CSS（`@media print`），保证 A4 分页正确
- 性能：商品 >200 条时列表必须虚拟滚动

---

## 13. 测试与质量门禁

### 13.1 单测断言（必须覆盖）

```
输入固定 seed：30 商品（20 耗材/10 设备）、12 绑定、2 套餐、15 单据、2 销售
断言：
  1) 排序 = [①, ②, ③]
  2) 商品列表 8 条含：1 有图 + 1 最长名 + 1 最高价 + 1 最低价
  3) 套餐卡片 = 省额最大的套餐，省额 = 520
  4) 第 4 屏默认 = "按底价卖不议价"（max_price 全空）
  5) min_price 标签 = "最低底价"（资料词频命中"底价"）
  6) 底价演示产出 1 条 ✓ + 1 条 ⚠
  7) 空库 → 排序固定 [①,②,③] 且 source_level = sample
  8) 非法字段注入 → 被第二道门剔除，且整体仍产出合法 Spec
  9) 连续 3 次校验失败 → 回退规则兜底 Spec（不报错给用户）
```

### 13.2 黄金屏与视觉回归

- 矩阵：3 风格 × 5 骨架 = 15 张基准截图，固定 seed 数据
- 每次改动渲染器或 token → 截图 diff，阈值内自动通过，超阈值人工确认
- 覆盖：桌面 1440 / 笔记本 1280 / 手机 390 三档宽度
- 打印：3 套风格各 1 张 A4 报价单 PDF 基准

### 13.3 人工评分表（每套风格上线前打分）

| 项 | 通过标准 |
|---|---|
| 首屏信息量 | 一屏内能看到"能开单"的全部要素 |
| 开一单的点击次数 | ≤ 12 次（选品 5 项 + 客户 + 提交） |
| 价格是否一眼可见 | 不滚动就能看到合计 |
| 底价提示是否可感知 | 破价时 1 秒内可发现 |
| 打印后可读性 | A4 打印无截断、无灰度不可辨 |

---

## 14. 里程碑

| 阶段 | 内容 | 工期 | 验收标准 |
|---|---|---|---|
| **M0** | Token 体系 + 3 风格包 + 渲染器 + 5 骨架；**手工写 2 份 Spec 跑通** | 1 周 | 手工 Spec 能渲染出可点界面；换 preset 全站变色不变形 |
| **M1** | `signals.py` + `ranking.py` + 填充选择器（纯后端，无 UI） | 1.5 周 | §13.1 断言 1–8 全绿 |
| **M2** | 第 0 屏三张真预览（可点、真数据、分级来源标注） | 1.5 周 | 10 秒内可点；三张差异在骨架与密度上可辨 |
| **M3** | 8 步向导 + 规则生成 Spec + 定稿落库 + 三类微调 | 1.5 周 | 全程不出现技术术语；定稿后业务数据不受影响 |
| **M4** | 接入 LLM：仅"资料→画像"与"文案本地化"；三道门 + 有界自愈 | 1 周 | 不配 API Key 也能出完整 Spec |
| **M5** | 黄金屏 + 视觉回归 + 逃生舱 + 埋点 | 1 周 | 15 张基准稳定；埋点指标可看 |

合计约 **7.5 周**（1–2 人）。**顺序不可调换**：M0/M1 是资产，UI 只是呈现。

---

## 15. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 表达力划太大 → 变成低代码平台 | 项目失控 | 布局固定 5 骨架；block 固定 16 种；组件不接受任意样式 |
| 表达力划太小 → 三张长得一样 | 用户选不出，产品无价值 | 差异落在**骨架 + 密度 + 表格样式**；建立 M2 的选择分布埋点当作验收线 |
| 三张只换配色 | 用户觉得敷衍 | 见上；风格包必须含密度与表格差异 |
| 空库用户看到假数据 | 信任崩塌 | source_level 三级来源**必须在界面明示** |
| 模型幻觉字段/模块 | 界面报错 | 三道门 + 有界自愈 + 规则兜底（永不把错误抛给用户） |
| 品牌色破坏可读性 | 界面不可用 | 只允许覆盖 primary；对比度 <3:1 自动加深并提示 |
| 定稿后用户想改布局 | 无路可走 | 逃生舱 `reset`：换 Spec 不动数据；微调仅开放三类且可回退 |

---

## 16. 待决问题（开工前需拍板）

1. **品牌色**：是否要自动从 logo 取色？取色失败如何降级（当前设计：用预设色块兜底）
2. **多语言**：中英双语是否本期做？（影响 token 与文案层的结构）
3. **Spec 是否对客户可见**：是否支持导出"设计说明 PDF"作为交付物？
4. **多租户/多门店**：一套部署是否可能服务多个独立品牌？（影响 `ui_specs` 的归属维度）
5. **`customers` 模块**：是否本期就做独立客户档案，还是先只做开单时的客户信息块？

---

## 附：本文档与既有系统的关系

- 复用：现有 `Product/Package/DeviceBinding/Quote/User/AppSetting`、现有 Agent 的资料解析、`schema_utils` 校验模式、鉴权与 DB 依赖、测试体系
- 新增：`designer/` 后端模块、`renderer/` 前端模块、5 张新表（§10）、3 套风格包
- 不动：现有业务表结构、现有 Agent 的运行逻辑、报价与权限的业务规则

---

# §17 实现状态与决策记录（2026-10-13 更新）

> 本节是对上面正文的**增量修订**：正文描述目标设计，本节记录实际落地情况、
> 本轮新增的三项工作、以及审计发现的既有问题。若两者冲突，以本节为准。

## 17.1 本轮完成（对应任务）

| # | 任务 | 结果 | 关键产物 |
|---|---|---|---|
| 1 | **entities / output / rules 接进渲染器** | ✅ | `SpecContext.js`、`SpecProvider.js`、`SpecRenderer.vue`、`QuotePrintArea.vue`；10 个 block 改为消费 Spec |
| 2 | **黄金屏截图基准** | ✅ | `Quote/visual/`、`Quote/tests/visual/`、18 张基准（3 风格 × 5 骨架 + 3 打印） |
| 3 | **M4 大模型接入** | ✅ | `designer/llm.py`、`designer/profiles.py`、`designer/terminology.py`；`/api/designer/profile` |

回归结果：后端 **153 passed**（+18 M4），前端 **16 passed**（+6 SpecContext），黄金屏 **18/18 通过**。

## 17.2 决策记录（含对正文的修订）

| 编号 | 决策 | 说明 |
|---|---|---|
| D6 | **渲染器归 `Quote/`（Electron 销售端），管理后台不参与** | 修正正文 §12 中"建议放 `Workbench/web/src/renderer`"的表述；`Workbench/web` 不引入渲染器 |
| D7 | **引入 Tailwind（v3），关闭 preflight** | `renderer/designer` 的 190 处工具类此前**无任何样式系统支撑**（见 17.3-1）。关闭 preflight 以免重置既有 `main.css` 维护的界面样式 |
| D8 | **视觉回归用「自包含 HTML + file://」而非本地 HTTP 服务** | 受限环境下 Chrome 连 `localhost` 会挂起；IIFE + 内联 CSS/JS 更稳，也无端口冲突 |
| D9 | **Spec 消费优先级**：块级 `props` > `entities.<实体>` > 内置默认 | 块级列定义针对"这一屏"，实体级针对"该实体列表页" |
| D10 | **模型只做画像与术语，且必须过三道门** | `enrich_spec_with_llm` 带 3 次有界自愈；3 次不过或调用失败 → 回退规则 Spec，**永不把错误抛给用户** |
| D11 | **不配置模型也必须完全可用** | `resolve_provider` 返回 None 时全程规则；`/compile` 支持 `enrich=false` |

## 17.3 审计发现并修复的既有问题

| 级别 | 问题 | 影响 | 处理 |
|---|---|---|---|
| **P0** | 仓库**没有 Tailwind**（不在依赖、无配置、无指令），而 renderer/designer 有 190 处工具类 | 设计器整体**无样式**，黄金屏任务正是靠这个暴露出来 | 装 `tailwindcss@3` + `postcss`，加 `tailwind.config.js`/`postcss.config.js`/`tailwind.css`，`preflight: false` |
| **P0** | Spec 的 `entities / output / rules / nav / profile` **后端产出并校验，但前端 0 处消费** | "生成一套系统"实际只等于"换骨架换风格" | 本轮接入 `entities`/`output`/`rules`（`nav` 仍待办，见 17.4） |
| **P1** | `form-first-wizard`、`dashboard-grid` **编译路径不可达**（compiler 只按 scene 产出 3 种） | 用户在第 0 屏选"管理型"，走向导后被覆盖成开单型 | `resolve_skeleton()` 5 个骨架全可达 + `wizardState` 增加 `view_mode` |
| **P1** | `customers` 模块**永不产出** | §5.3 规则缺失 | `resolve_modules()` 按 `customer_repeat_rate > 1.5` 产出 |
| **P2** | `source_level` 语义与文档不一致（实现按"有商品无单据"推断） | 手工录商品的客户会被标注成"用你上传的资料渲染" | **未修**，列入 17.4（涉及文案与信任，需要产品口径确认） |
| **P2** | 新增设计器测试用 `sqlite:///:memory:` | 与"SQLite 已彻底移除"的架构约定冲突（依赖 stdlib sqlite3 才没报错） | **未修**，列入 17.4 |
| — | 设计文档自身写"4 张新表"实际 5 张 | 文档错误 | 已修正 |

## 17.4 仍未完成 / 已知问题

1. **`nav` 段未接入**：Spec 的导航定义尚未驱动界面（需要与 Quote 既有路由整合）。
2. **`source_level` 标签语义**：应改为记录"预览数据的真实来源"，而不是从"有单据/无单据"推断。
3. **设计器测试仍用内存 SQLite**：建议统一到 `tests/db_support.py`（PostgreSQL），否则该模块是 SQLite 的唯一残留。
4. **黄金屏未接入 CI**：目前需手动 `npm run test:visual`；基准图 1.3MB 入库。
5. **M4 的实测质量未知**：规则链路已测，真实模型下的画像/术语准确率尚未用真实接口验证（需要额度）。
6. **`/answer` 端点仍未实现**：向导答案保存在前端内存，刷新丢失（正文 §11 列的是 9 个端点，实现 8+1=9 个）。

## 17.5 新增/变更文件

**后端**
```
app/designer/llm.py          # 模型增强 + 三道门 + 有界自愈 + provider 解析
app/designer/profiles.py     # 资料 → 业务画像（规则优先，模型可选）
app/designer/terminology.py  # 术语本地化（底价/供货价/同行价/批发价）
app/designer/compiler.py     # 重写：5 骨架可达、customers 模块、画像与术语注入
app/api/designer.py          # 新增 POST /profile；/compile 支持 enrich 开关
tests/test_designer_llm.py   # 18 项：画像/术语/自愈/编译器/路由
```

**前端（`Quote/`）**
```
src/renderer/SpecContext.js   # 纯逻辑：标签、列解析、规则、格式化（不依赖 vue）
src/renderer/SpecProvider.js  # vue provide/inject 适配层
src/renderer/SpecRenderer.vue # ThemeProvider + LayoutEngine + QuotePrintArea + rules 派生数据
src/renderer/QuotePrintArea.vue # output.quote_pdf 驱动的打印版式（含 @page 注入）
src/renderer/blocks/*.vue     # 10 个 block 改为消费 entities/output/rules
src/renderer/__tests__/spec_context.test.js
visual/                       # 黄金屏种子数据 + 独立打印 harness
tests/visual/capture.mjs      # 构建 + 截图 + 调用比对（--update 生成基准）
tests/visual/compare.py       # Pillow 像素比对（默认阈值 0.05%）
visual/baseline/*.png         # 18 张基准（入库）
tailwind.config.js / postcss.config.js / src/shared/assets/tailwind.css
```

## 17.6 运行方式

```bash
# 后端（含设计器）
cd Workbench && .venv/bin/python -m pytest tests -q

# 前端单测（16 项）
cd Quote && npm test

# 黄金屏回归（需先 npm install；依赖本地 Chrome）
cd Quote
npm run test:visual          # 与基准比对，超阈值失败并输出差异图到 visual/current/diff/
npm run test:visual:update   # 渲染器/token 有意改动后重新生成基准
# 阈值可用 VISUAL_THRESHOLD=0.0002 收紧；CI 无 Chrome 时该步骤应跳过（退出码 2）

# 设计器接口
POST /api/designer/signals   # 画像指标 + 排序 + 采样
POST /api/designer/profile   # 资料 → 业务画像（llm_enabled=false 表示走规则）
POST /api/designer/compile   # {"answers": {...}, "enrich": true}
```

## 17.7 黄金屏判定标准的经验值

- 同一次构建重复渲染：差异 **0.000%**（确定性），因此阈值可设得很紧
- 改一个主色 token：medical-clean 组合产生 **0.11%–0.46%** 差异
- 默认阈值取 **0.05%**：比噪声高、比真实回归低，能拦住配色/间距/文案类改动

