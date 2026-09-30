# QuoteSys 通用商业报价系统工程模版架构设计规范 (Design Spec)

- **文档版本**: 1.0.0
- **创建日期**: 2026-09-30
- **项目路径**: `/Users/xiongtianyu/Desktop/Quote_Sys`
- **目标**: 将原特定业务系统（HHZ 超声医疗系统）重构脱敏为纯净、高通用性、生产级的商业报价系统模版（QuoteSys），支持后续快速衍生开发多行业定制版本。

---

## 1. 背景与目标 (Context & Goals)

### 1.1 背景
本项目源码由特定垂直领域项目（HHZ 超声医疗报价系统）复制而来。原系统内包含大量特定业务的硬编码（如医疗设备、超声耗材二元划分，HHZ 品牌与专属接口命名，特定价格表与本地测试数据库）。

### 1.2 核心目标 (Goals)
1. **彻底解耦与脱敏**：清理所有历史打包残留（`dist/`、`release/`）、临时文件与特定业务文档/数据（超声医疗商品、历史 `app.db`）。
2. **通用平铺数据模型**：移除“设备/耗材”二元约束，建立通用的商品（Products/Items）、自定义分类（Categories）、方案包（Packages）、关联推荐（Item Relations）业务模型。
3. **企业级员工与报价持久化**：
   - 数据库全面支持员工管理与角色权限（管理员、销售主管、销售员工）。
   - 突破原项目“报价仅存本地 LocalStorage”限制，支持报价单全链路入库、历史追溯、JSONB 明细快照冻结与 PDF 导出。
4. **现代化高并发存储架构**：
   - 核心数据库采用 **PostgreSQL 16**；
   - 引入 **Redis 7** 作为缓存中间件，支撑多销售终端高并发读取商品目录、秒级原子单号生成（`INCR`）与会话限流。
5. **统一命名与工程规范**：
   - 全链路重构标识为 `QuoteSys` / `quote-service` / `quoteAPI` / `quote:*` / `QuoteSys.exe`。
   - 增加根目录统一管理（`package.json`、`.gitignore`、`.env.example`），提供一键启动与一键构建指令。
6. **双轨部署形态支持**：
   - **云端/集中式部署**：支持 Docker Compose 一键拉起 Nginx + FastAPI + PostgreSQL + Redis。
   - **单机/局域网母机部署**：保留原系统出色的便携母机托盘打包（PyInstaller `QuoteService.exe` + NSIS 安装器）与销售客户端桌面打包（Electron `QuoteSys.exe`）。

### 1.3 非目标 (Non-Goals)
- 本次模版化改造不引入特定行业的特定计价插件（如医疗耗材专有阶梯换算公式），仅保留通用可配置的基础定价与单件/阶梯算法框架。
- 原预留的 AI 价格预测模块保留接口框架与规则引擎基线，不强依赖外部大模型 API Key 即可独立运行。

---

## 2. 总体架构与系统拓扑 (Architecture Topology)

系统支持两种无缝切换的部署形态：

```mermaid
graph TD
    subgraph "形态 A：云端 / 私有化集中部署 (Docker Compose)"
        ClientA["Quote 销售客户端 (Electron / Web)"] -->|HTTPS / WSS| Gateway["Nginx 网关 (Port 80/443)"]
        BrowserA["管理后台 Workbench (Web 浏览器)"] -->|HTTPS| Gateway
        Gateway -->|/api 反向代理| API["QuoteService (FastAPI)"]
        Gateway -->|静态托管| WebDist["Workbench Web 静态资源"]
        API -->|ORM 读写| PG[("PostgreSQL 16<br/>(员工/商品/报价单持久化)")]
        API -->|缓存与单号原子自增| R[("Redis 7<br/>(目录缓存/单号生成)")]
    end

    subgraph "形态 B：单机 / 便携母机局域网部署 (Windows 离线/展会)"
        SalesTerminal["销售终端机 QuoteSys.exe"] -->|LAN 局域网探活 (:8000/api/health)| MotherMachine["母机托盘服务 QuoteService.exe"]
        AdminBrowser["母机浏览器 (管理端)"] -->|http://localhost:8000| MotherMachine
        MotherMachine --> LocalDB[("本地 PostgreSQL / SQLite 数据库")]
    end
```

---

## 3. 工程目录与清理规划 (Directory Structure & Cleanup)

### 3.1 资产清理与归档规则
1. **删除构建残留**：
   - `Quote/dist/`, `Quote/release/`
   - `Workbench/web/dist/`, `Workbench/dist/`
   - `Workbench/__pycache__/`, `Workbench/app/__pycache__/`, `Workbench/tests/__pycache__/`
   - 全局 `.DS_Store`
2. **清理业务特定资产**：
   - 移除 `assets/` 下的原超声医疗业务文件（`超声医疗报价平台业务文档.md`、`超声医疗报价平台.html`、`产品最低价格.xlsx`、`商标.jpg`）。
   - 创建标准的 `assets/templates/` 目录，存放通用的公司 Logo 占位图、报价单默认落款与 Excel 导入样表。
3. **清理旧测试库**：
   - 移除 `Workbench/data/app.db`、`Workbench/data/agent_checkpoints.db` 以及 `Workbench/uploads/products/*`，在 `uploads/` 保留 `.gitkeep`。

### 3.2 最终根目录骨架
```
Quote_Sys/
├── .env.example              # 根目录全局环境变量示例
├── .gitignore                # 根目录统一 git 忽略配置
├── package.json              # 根目录全局工程管理脚本
├── docker-compose.yml        # Docker 生产与开发编排 (PG + Redis + FastAPI + Nginx)
├── README.md                 # QuoteSys 模版使用与二次开发指南
├── assets/                   # 通用资源与模版
│   └── templates/            # 占位 Logo、示例导入表格等
├── scripts/                  # 跨平台构建与维护脚本
│   ├── serve-backend.mjs     # 启动后端开发服务（带热载）
│   ├── dev.mjs               # 启动桌面端联调
│   ├── build-backend-exe.mjs # PyInstaller 构建 QuoteService.exe
│   ├── build-backend-installer.mjs # NSIS 构建服务安装器
│   ├── backend-installer.nsi # NSIS 脚本（防火墙规则与安装流）
│   └── allow-firewall.ps1    # 防火墙端口放行脚本
├── Quote/                    # 销售报价终端 (Electron + Vue 3)
│   ├── electron/             # Electron 主进程与预加载脚本 (main.cjs, preload.cjs)
│   ├── src/                  # 客户端 Vue 3 源码 (选配面板、报价单生成、历史记录)
│   ├── package.json          # 客户端依赖与构建配置
│   └── vite.config.js
└── Workbench/                # 主系统后端与运营管理后台
    ├── app/                  # FastAPI 核心业务 (models, schemas, api, services)
    ├── web/                  # 管理后台 Vue 3 源码 (商品中心、套餐管理、报价大盘、员工管理)
    ├── data/                 # 本地持久化挂载目录
    ├── uploads/              # 商品图片与附件上传目录
    ├── Dockerfile            # 后端 Dockerfile
    ├── requirements.txt      # Python 依赖清单
    └── alembic.ini           # 数据库迁移配置
```

---

## 4. 数据库与业务模型设计 (Database & Models)

以 **PostgreSQL 16** 为基准建模，兼顾 SQLAlchemy 2.0 ORM。

### 4.1 表结构详细规范

#### (1) `users`（员工与用户表）
| 字段 | 类型 | 约束 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, 自增 | 唯一标识 |
| `username` | String(64) | Unique, Not Null | 登录工号/账号 |
| `password_hash` | String(256) | Not Null | 密码哈希（PBKDF2/scrypt） |
| `salt` | String(64) | Not Null | 密码加盐 |
| `real_name` | String(64) | Not Null | 员工真实姓名（自动填入报价单） |
| `phone` | String(32) | Nullable | 员工联系电话（自动填入报价单） |
| `email` | String(128) | Nullable | 员工邮箱 |
| `role` | String(32) | Not Null, 默认 'sales' | 角色枚举：`admin`、`manager`、`sales` |
| `is_active` | Boolean | Not Null, 默认 True | 账号是否可用 |
| `created_at` | DateTime | Not Null, 默认当前时间 | 创建时间 |
| `updated_at` | DateTime | Not Null, 默认当前时间 | 更新时间 |

#### (2) `quotes`（报价单主表）
| 字段 | 类型 | 约束 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, 自增 | 唯一标识 |
| `quote_no` | String(64) | Unique, Not Null | 格式：`QT-YYYYMMDD-XXXX`（Redis 生成） |
| `user_id` | Integer | FK(`users.id`), Nullable | 报价员工 ID（访客/离线为 Null） |
| `sales_name` | String(64) | Not Null | 报价员姓名快照 |
| `sales_phone` | String(32) | Nullable | 报价员联系方式快照 |
| `customer_name` | String(128) | Not Null | 客户单位 / 客户姓名 |
| `customer_contact` | String(64) | Nullable | 客户联系人 |
| `customer_phone` | String(32) | Nullable | 客户联系电话 |
| `status` | String(32) | Not Null, 默认 'active'| 状态：`draft`、`active`、`signed`、`expired` |
| `total_list_price` | Numeric(12, 2) | Not Null | 指导标价合计 |
| `discount_rate` | Numeric(5, 2) | Not Null, 默认 1.0 | 综合折扣率 |
| `final_quote_price`| Numeric(12, 2) | Not Null | 最终报价总金额 |
| `valid_days` | Integer | Not Null, 默认 30 | 报价有效期（天） |
| `remark` | Text | Nullable | 特殊说明 / 交付条款 |
| `items_snapshot` | JSONB | Not Null | **全量明细快照**（包含选定商品清单与计算明细） |
| `created_at` | DateTime | Not Null, 默认当前时间 | 报价单创建时间 |
| `updated_at` | DateTime | Not Null, 默认当前时间 | 更新时间 |

`items_snapshot` JSONB 结构范例：
```json
[
  {
    "sku_id": "PRD-001",
    "name": "智能工业网关 A型",
    "category": "硬件终端",
    "spec": "4核/8G/双千兆网口",
    "unit": "台",
    "unit_price": 3200.0,
    "quantity": 2,
    "subtotal": 6400.0,
    "remark": "含标准安装支架"
  }
]
```

#### (3) `products`（通用商品/项目库）
| 字段 | 类型 | 约束 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, 自增 | 唯一标识 |
| `sku_id` | String(64) | Unique, Not Null | 商品唯一 SKU（如 `PRD-001`） |
| `category` | String(64) | Not Null | 通用分类（如“标准硬件”、“配套配件”、“服务实施”） |
| `name` | String(128) | Not Null | 商品/项目名称 |
| `unit` | String(16) | Not Null, 默认 '件' | 计量单位 |
| `min_price` | Numeric(12, 2) | Nullable | 底价（权限控制：低于底价报警） |
| `max_price` | Numeric(12, 2) | Nullable | 公开指导售价 / 目录标价 |
| `spec` | Text | Nullable | 规格参数 / 详细说明 |
| `raw_price_desc`| Text | Nullable | 阶梯价或计价规则描述 |
| `image` | String(256) | Nullable | 商品主图相对路径 |
| `is_active` | Boolean | Not Null, 默认 True | 是否上架可用 |
| `created_at` | DateTime | Not Null | 创建时间 |
| `updated_at` | DateTime | Not Null | 更新时间 |

#### (4) `packages`（组合套餐/方案包）
| 字段 | 类型 | 约束 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, 自增 | 唯一标识 |
| `package_code`| String(64) | Unique, Not Null | 套餐编码 |
| `name` | String(128) | Not Null | 套餐名称（如“标准企业上云起步包”） |
| `description` | Text | Nullable | 套餐简介与适用场景 |
| `bundle_price`| Numeric(12, 2) | Not Null | 套餐打包总售价 |
| `items_config`| JSONB | Not Null | 套餐包含的 SKU 及对应数量列表 |
| `is_active` | Boolean | Not Null, 默认 True | 是否启用 |

#### (5) `item_relations`（通用商品配套与推荐关系表）
| 字段 | 类型 | 约束 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, 自增 | 唯一标识 |
| `parent_product_id` | Integer | FK(`products.id`), Not Null | 主商品 ID |
| `child_product_id` | Integer | FK(`products.id`), Not Null | 关联/配套商品 ID |
| `relation_type` | String(32) | Not Null, 默认 'accessory' | 关系类型：`accessory`（配套）、`recommended`（推荐搭配） |

#### (6) `app_settings`（企业报价基础配置）
采用 Key-Value 或单行结构存储：
- `company_name`: 企业名称（默认 "通用商业科技有限公司"）
- `quote_title`: 报价单抬头标题
- `default_valid_days`: 默认有效天数（30天）
- `quote_disclaimer`: 报价单法定免责与说明条款
- `logo_path`: 企业印鉴/Logo 路径

---

## 5. API 接口体系与 Redis 缓存集成 (API & Redis)

### 5.1 核心 RESTful 端点
* **服务探活**：
  * `GET /api/health` -> `{"ok": true, "app": "quote-service", "version": "2.0.0"}`
* **鉴权与员工**：
  * `POST /api/auth/login`：工号密码登录，生成 JWT Token。
  * `GET /api/auth/me`：获取当前登录员工信息与权限。
  * `GET /api/admin/employees`：管理员查看员工列表。
  * `POST /api/admin/employees`：管理员新建员工账号。
  * `PUT /api/admin/employees/{id}/reset-password`：重置员工密码。
* **商品与类目**：
  * `GET /api/products`：获取商品列表（支持分页、按 category、关键词搜索）。
  * `POST /api/products`：创建商品。
  * `PUT /api/products/{id}`：修改商品。
  * `DELETE /api/products/{id}`：删除商品。
  * `POST /api/products/photo`：上传商品图片。
  * `GET /api/categories`：获取系统当前所有动态分类。
* **套餐与关联**：
  * `GET /api/packages` / `POST /api/packages`
  * `GET /api/relations/{product_id}`：获取某商品的所有配套与关联商品。
* **目录全量同步（Quote 客户端专用）**：
  * `GET /api/catalog`：返回全量上架商品、关联关系、套餐与企业配置。
* **报价单中心（新增）**：
  * `POST /api/quotes`：提交并保存正式报价单（支持入库）。
  * `GET /api/quotes`：获取报价列表（销售仅看自己的，管理员查看全员）。
  * `GET /api/quotes/{quote_no}`：查看报价详情快照。

### 5.2 Redis 高并发协同策略
1. **目录缓存**：
   - Key: `quote:catalog:data`
   - TTL: 3600 秒
   - 策略：Quote 客户端高并发同步时优先读 Redis；当后台商品、套餐、企业设置变更时，异步调用 `redis.delete("quote:catalog:data")` 清理缓存。
2. **原子报价单号生成**：
   - Key: `quote:no:seq:YYYYMMDD`
   - 逻辑：通过 `INCR` 递增获取序号，格式化为 `QT-20261001-0001`，保证绝对无重复、高并发安全。

---

## 6. 前端与桌面客户端设计 (Frontend & Client Design)

### 6.1 Quote 客户端（销售桌面端）
* **Electron 进程通信标准化**：
  * `preload.cjs` 统一注入 `window.quoteAPI`。
  * IPC 事件名规范化：
    * `quote:discover-host`：局域网广播探测 `quote-service`。
    * `quote:image-sync`：同步母机商品图片至本地磁盘缓存。
    * `quote:catalog-cache-read` / `quote:catalog-cache-write`：本地目录离线缓存。
* **选配界面通用化改造**：
  * 改造 `ProductConfigPanel.vue`：
    * 提供“主选项目”分类选择器与规格筛选；
    * 选定主商品后，下方联动展示配套选件（配件、实施服务等），支持加购计数器与自定义报价；
    * 提供套餐选配页签，一键选用预设优惠组合；
  * **报价单导出与提交**：
    * 改造 `ExportQuoteModal.vue`：支持自动提取当前登录销售姓名与电话，填入客户单位、联系人，一键“提交入库”并可本地直接打印/另存为防伪 PDF。

### 6.2 Workbench 管理端（Web 运营后台）
* 改造 `Workbench/web`：
  * **商品管理（`ProductsManager.vue`）**：合并原分散的设备与耗材页面，支持动态分类标签过滤、商品快速新增/编辑、规格属性录入、底价与建议价设定、图片拖拽上传。
  * **报价中心（`QuotesCenter.vue`，新增）**：全公司报价大盘，展示报价单号、客户单位、销售人、总金额、创建时间与状态，支持一键预览明细快照。
  * **员工管理（`EmployeesManager.vue`，新增）**：工号管理与角色分配。
  * **系统设置（`SettingsManager.vue`）**：企业信息与报价单落款设置。

---

## 7. 生产部署与容器编排 (Docker Architecture)

### 7.1 `docker-compose.yml` 拓扑编排
包含 4 个核心容器服务：
1. **`postgres`**：
   - 镜像：`postgres:16-alpine`
   - 挂载卷：`quotesys_pgdata:/var/lib/postgresql/data`
   - 健康检查：`pg_isready -U postgres`
2. **`redis`**：
   - 镜像：`redis:7-alpine`
   - 挂载卷：`quotesys_redisdata:/data`
   - 命令：`redis-server --appendonly yes`
3. **`backend`**：
   - 镜像：构建自 `Workbench/Dockerfile`（Python 3.11-slim）
   - 依赖：`postgres` 与 `redis` 启动就绪后拉起
   - 启动流程：执行 `alembic upgrade head` 自动完成数据库结构初始化，启动 Uvicorn (Port 8000)
   - 挂载卷：商品图片上传目录 `quotesys_uploads:/app/uploads`
4. **`web` (Nginx 网关)**：
   - 镜像：`nginx:alpine`
   - 暴露端口：`80`（支持扩展 443 SSL）
   - 路由规则：
     - `/` 代理 Workbench Web 管理前端静态文件；
     - `/api/` 反向代理至 `backend:8000/api/`；
     - `/uploads/` 反向代理至静态文件卷；
     - 启用 WebSockets 支持与 Gzip 压缩。

---

## 8. 实施与分步验证策略 (Implementation & Verification)

实施将划分为以下逻辑步骤：
1. **工程大扫除与初始化**：清理旧产物、旧超声资产、测试数据库，建立 `.gitignore`、`package.json`、`.env.example`。
2. **后端服务重构**：配置更新、PostgreSQL 与 Redis 接入、通用数据模型（User, Quote, Product, Package, Setting）创建、Alembic 迁移初始化、RESTful API 适配。
3. **前端与客户端重构**：命名空间全量迁移（`quoteAPI` / `quote:*`）、Quote 选配面板通用化、Workbench 商品管理合并、报价中心与员工管理界面集成。
4. **Docker 编排配置与联调**：编写全套 Dockerfile 与 `docker-compose.yml`，验证一键部署容器全链路畅通。
5. **打包脚本通用化**：更新 Windows 托盘后台构建（`QuoteService.exe`）与 Electron 客户端安装包构建脚本。
6. **最终端到端全链路测试与交付**：验证登录、商品管理、客户端发现、报价单生成入库、PDF 导出、Docker 一键启动。
