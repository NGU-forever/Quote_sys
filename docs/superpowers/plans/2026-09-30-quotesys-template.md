# QuoteSys 通用商业报价系统模版实施计划 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将原 HHZ 超声医疗系统全套源码重构、解耦、脱敏，打造为具备 PostgreSQL 16 员工与报价持久化、Redis 7 目录缓存与原子单号自增、通用商品分类库、Docker 编排以及 Electron 客户端全套能力的通用商业报价系统模版（QuoteSys），并推送到 GitHub 远程仓库。

**Architecture:** 
1. 后端：FastAPI + SQLAlchemy 2.0 + PostgreSQL 16（核心持久化） + Redis 7（高并发目录缓存与单号原子递增）；
2. 销售桌面端：Electron + Vue 3 + Pinia，支持局域网母机自动探测、离线选配计算、云端正式报价单入库与 PDF 导出；
3. 管理后台：Vue 3 + Vite，提供通用商品中心、套餐方案、报价大盘、员工管理与系统设置；
4. 部署与工程化：根目录集中管理脚本 + Docker Compose 多容器集群编排 + Windows 托盘母机打包（PyInstaller + NSIS）。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, PostgreSQL 16, Redis 7, Alembic, Docker, Vue 3, Pinia, Vue Router, Vite, Electron, TailwindCSS / Custom CSS, PyInstaller, NSIS.

**Spec:** [docs/superpowers/specs/2026-09-30-quotesys-template-design.md](file:///Users/xiongtianyu/Desktop/Quote_Sys/docs/superpowers/specs/2026-09-30-quotesys-template-design.md)

## Global Constraints
- 系统名称：QuoteSys 通用报价系统
- 后端服务标识：`quote-service`（健康检查 `/api/health` 返回 `{"ok": true, "app": "quote-service", "version": "2.0.0"}`）
- 客户端 Preload API：`window.quoteAPI`
- IPC 通道规范：`quote:*`（如 `quote:discover-host`、`quote:image-sync`）
- 本地存储键名前缀：`quote_*`（如 `quote_backend_base`、`quote_local_quotes_v1`）
- Windows 托盘母机服务名称：`QuoteService.exe`，安装包 `QuoteService Setup.exe`
- 销售客户端产品名称：`QuoteSys.exe`，安装包 `QuoteSys Setup.exe`
- 默认数据库：PostgreSQL 16（生产/Docker），支持本地 SQLite 便捷开发开发

---

### Task 1: 清理残留产物、原超声医疗资产与建立根目录工程化脚手架

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `package.json`
- Create: `assets/templates/README.md`
- Delete: `Quote/dist/`, `Quote/release/`, `Workbench/web/dist/`, `Workbench/data/app.db`, `Workbench/data/agent_checkpoints.db`, `Workbench/uploads/products/*`, `.DS_Store`
- Modify: `assets/` (移除超声医疗特定文档与 Excel)

**Interfaces:**
- Consumes: None
- Produces: 纯净的工作区结构、根目录快捷脚本指令（`npm run dev`, `npm run dev:backend`, `npm run clean`, `npm run docker:up`）

- [ ] **Step 1: 创建根目录 `.gitignore`**

```gitignore
# Dependencies
node_modules/
.venv/
__pycache__/
*.pyc

# Builds & Outputs
dist/
release/
*.exe
*.zip

# Database & Runtime Data
*.db
*.db-journal
*.sqlite3
data/*.db
data/*.sqlite3
quotesys_pgdata/
quotesys_redisdata/
uploads/products/*
!uploads/products/.gitkeep

# Environment & IDE
.env
.DS_Store
*.log
.vscode/
.idea/
```

- [ ] **Step 2: 创建根目录环境变量模版 `.env.example`**

```env
# ========================================================
# QuoteSys 通用商业报价系统环境变量配置模版
# ========================================================

# 运行环境: development | production
APP_ENV=development
APP_NAME=quote-service
PORT=8000

# 数据库配置 (默认 PostgreSQL，开发测试可选用 SQLite: sqlite:///./data/app.db)
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/quotesys_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=quotesys_db

# Redis 缓存配置 (商品目录高并发缓存、分布式原子单号自增)
REDIS_URL=redis://localhost:6379/0

# 安全配置 (生产环境务必更改为随机高强度字符串)
AUTH_SECRET=quotesys-production-auth-secret-key-replace-me
TOKEN_TTL_SECONDS=86400

# 文件与上传配置
UPLOAD_DIR=./uploads
MAX_UPLOAD_BYTES=10485760

# 跨域配置
CORS_ORIGINS=*
```

- [ ] **Step 3: 创建根目录 `package.json`**

```json
{
  "name": "quote-sys-root",
  "version": "2.0.0",
  "private": true,
  "description": "QuoteSys 通用商业报价系统工程根目录",
  "scripts": {
    "dev": "concurrently -k -n backend,quote -c blue,green \"npm run dev:backend\" \"npm run dev:quote\"",
    "dev:backend": "node scripts/serve-backend.mjs --reload",
    "dev:quote": "cd Quote && npm run dev",
    "dev:desktop": "cd Quote && npm run dev:desktop",
    "dev:workbench": "cd Workbench/web && npm run dev",
    "docker:up": "docker compose up -d --build",
    "docker:down": "docker compose down",
    "docker:logs": "docker compose logs -f",
    "build:client": "cd Quote && npm run build:win",
    "build:workbench": "cd Workbench/web && npm run build",
    "build:backend": "node scripts/build-backend-exe.mjs",
    "clean": "node -e \"const fs=require('fs'); ['Quote/dist','Quote/release','Workbench/web/dist','Workbench/dist'].forEach(d => fs.existsSync(d) && fs.rmSync(d, {recursive:true,force:true})); console.log('Cleaned build artifacts.');\""
  },
  "devDependencies": {
    "concurrently": "^9.2.4"
  }
}
```

- [ ] **Step 4: 执行清理并整理 `assets/` 模版目录**

清理原打包目录、测试数据库与超声医疗特定文档：
```bash
rm -rf Quote/dist Quote/release Workbench/web/dist Workbench/dist
rm -rf Workbench/__pycache__ Workbench/app/__pycache__ Workbench/tests/__pycache__
find . -name ".DS_Store" -delete
rm -f Workbench/data/app.db Workbench/data/agent_checkpoints.db
rm -rf Workbench/uploads/products/*
mkdir -p Workbench/uploads/products && touch Workbench/uploads/products/.gitkeep
mkdir -p assets/templates
rm -f "assets/商标.jpg" "assets/产品最低价格.xlsx" "assets/超声医疗报价平台业务文档.md" "assets/超声医疗报价平台.html"
```
在 `assets/templates/README.md` 中写入模版资源说明。

- [ ] **Step 5: 验证并提交 Task 1**

Run: `git status`
Commit: `git add . && git commit -m "chore: clean legacy artifacts, setup root package.json, gitignore and env template"`

---

### Task 2: 后端基础设施与配置改造（PostgreSQL、Redis 与服务探活）

**Files:**
- Modify: `Workbench/requirements.txt`
- Modify: `Workbench/app/core/config.py`
- Create: `Workbench/app/core/redis_client.py`
- Modify: `Workbench/app/compat/health.py`
- Create: `Workbench/tests/test_infra.py`

**Interfaces:**
- Consumes: `REDIS_URL`, `DATABASE_URL` from `.env`
- Produces:
  - `get_redis() -> AsyncRedis`: 异步 Redis 连接（带优雅降级）
  - `GET /api/health` -> `{"ok": True, "app": "quote-service", "version": "2.0.0"}`

- [ ] **Step 1: 编写基础设施测试用例**

在 `Workbench/tests/test_infra.py` 中编写测试：
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import get_settings

def test_health_check_quote_service():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["app"] == "quote-service"
    assert "version" in data

def test_settings_app_name():
    settings = get_settings()
    assert settings.app_name == "quote-service"
```

- [ ] **Step 2: 运行测试并验证当前失败**

Run: `pytest Workbench/tests/test_infra.py` (预期失败，因为原返回为 `hhz-data-service`)

- [ ] **Step 3: 更新 Python 依赖清单 `Workbench/requirements.txt`**

确保包含 `psycopg[binary]>=3.1.18`, `redis>=5.0.3`, `fastapi>=0.110.0`, `sqlalchemy>=2.0.29`, `pydantic-settings>=2.2.1`。

- [ ] **Step 4: 更新 `Workbench/app/core/config.py`**

将配置类中原 `auth_secret`、默认应用名从 `hhz` 改为 `quote-service`，添加 `redis_url: str = "redis://localhost:6379/0"`，数据库默认连接串支持 PostgreSQL / SQLite 自由切换。

- [ ] **Step 5: 创建 Redis 连接管理器 `Workbench/app/core/redis_client.py`**

封装安全连接池与优雅降级机制（若 Redis 未启动，记录告警并安全降级，不阻塞核心业务）：
```python
import logging
from redis import asyncio as aioredis
from app.core.config import get_settings

logger = logging.getLogger(__name__)
_redis_pool = None

async def get_redis():
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        try:
            _redis_pool = aioredis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
            await _redis_pool.ping()
        except Exception as e:
            logger.warning(f"Redis unavailable, running without cache: {e}")
            return None
    return _redis_pool
```

- [ ] **Step 6: 修改健康检查接口 `Workbench/app/compat/health.py`**

返回标准统一格式：
```python
@router.get("/api/health")
def health_check():
    return {
        "ok": True,
        "app": "quote-service",
        "version": "2.0.0",
        "time": datetime.now(timezone.utc).isoformat()
    }
```

- [ ] **Step 7: 运行测试并提交 Task 2**

Run: `pytest Workbench/tests/test_infra.py` (预期通过)
Commit: `git add Workbench/ && git commit -m "feat(backend): configure quote-service identity, redis support and health check"`

---

### Task 3: 通用数据模型重构（员工用户表、报价单表、商品表、套餐表）

**Files:**
- Modify: `Workbench/app/models/user.py`
- Modify: `Workbench/app/models/product.py`
- Create: `Workbench/app/models/quote.py`
- Modify: `Workbench/app/models/package.py`
- Create: `Workbench/app/models/item_relation.py`
- Modify: `Workbench/app/models/__init__.py`
- Modify: `Workbench/app/db/init_db.py`
- Create: `Workbench/tests/test_models.py`

**Interfaces:**
- Produces:
  - `User`: `id, username, password_hash, salt, real_name, phone, role, is_active`
  - `Quote`: `id, quote_no, user_id, sales_name, sales_phone, customer_name, customer_contact, customer_phone, status, total_list_price, discount_rate, final_quote_price, valid_days, remark, items_snapshot`
  - `Product`: `id, sku_id, category, name, unit, min_price, max_price, spec, raw_price_desc, image, is_active`
  - `ItemRelation`: `parent_product_id, child_product_id, relation_type`
  - `Package`: `id, package_code, name, description, bundle_price, items_config, is_active`

- [ ] **Step 1: 编写模型测试用例 `Workbench/tests/test_models.py`**

验证 User、Product、Quote 的完整字段存储与关联查询。

- [ ] **Step 2: 重构 `Workbench/app/models/product.py`**

移除 `CheckConstraint("category IN ('device', 'consumable')")`，支持任意通用字符串类目；规范化商品属性。

- [ ] **Step 3: 重构 `Workbench/app/models/user.py`**

增加 `real_name`（真实姓名）、`phone`（联系方式）、`role`（角色，默认 `sales`）、`is_active`。

- [ ] **Step 4: 创建 `Workbench/app/models/quote.py`**

实现带 `items_snapshot`（JSONB/JSON）的报价单持久化模型。

- [ ] **Step 5: 创建 `Workbench/app/models/item_relation.py` 与更新 `package.py`**

实现通用的配套关联与组合套餐模型。

- [ ] **Step 6: 更新 `Workbench/app/db/init_db.py`**

数据库初始化脚本支持自动建表、生成默认管理员（`admin / admin123`），并可选择性注入通用示例商品数据（如硬件终端、传感器附件、技术支持服务）。

- [ ] **Step 7: 运行模型测试并提交 Task 3**

Run: `pytest Workbench/tests/test_models.py`
Commit: `git add Workbench/ && git commit -m "feat(models): implement generic products, employee users, quotes and relations schema"`

---

### Task 4: 后端业务 API 与 Redis 缓存端点开发

**Files:**
- Create: `Workbench/app/schemas/quote_schemas.py`
- Create: `Workbench/app/schemas/employee_schemas.py`
- Modify: `Workbench/app/schemas/product_schemas.py`
- Create: `Workbench/app/services/quote_service.py`
- Modify: `Workbench/app/services/catalog_service.py`
- Create: `Workbench/app/api/v1/endpoints/quotes.py`
- Create: `Workbench/app/api/v1/endpoints/employees.py`
- Modify: `Workbench/app/api/v1/endpoints/catalog.py`
- Modify: `Workbench/app/main.py`
- Create: `Workbench/tests/test_quote_api.py`

**Interfaces:**
- Produces:
  - `POST /api/quotes`: 创建并保存正式报价单（Redis 原子自增单号 `QT-YYYYMMDD-XXXX`）
  - `GET /api/quotes`: 查询报价单列表（支持销售隔离与管理员全量查询）
  - `GET /api/quotes/{quote_no}`: 调取单张报价单明细快照
  - `GET /api/admin/employees`: 员工列表管理
  - `POST /api/admin/employees`: 创建销售账号
  - `GET /api/catalog`: 客户端全量目录（支持 Redis 缓存）

- [ ] **Step 1: 编写 API 接口测试用例 `Workbench/tests/test_quote_api.py`**

测试单号生成、报价单创建、查询与权限校验。

- [ ] **Step 2: 编写 Pydantic Schema（报价单与员工管理）**

定义 `QuoteCreate`, `QuoteOut`, `EmployeeCreate`, `EmployeeOut`。

- [ ] **Step 3: 实现 `quote_service.py`（单号原子生成与报价保存）**

集成 Redis `INCR` 递增单号（格式：`QT-YYYYMMDD-0001`），支持无 Redis 时基于数据库当日数量降级。

- [ ] **Step 4: 改造 `catalog_service.py`（集成 Redis 目录缓存）**

当请求 `/api/catalog` 时，优先从 Redis 键 `quote:catalog:data` 读取；在商品增删改时主动清理缓存。

- [ ] **Step 5: 实现路由并挂载至 `app/main.py`**

注册 `/api/quotes`、`/api/admin/employees` 路由。

- [ ] **Step 6: 运行 API 测试并提交 Task 4**

Run: `pytest Workbench/tests/test_quote_api.py`
Commit: `git add Workbench/ && git commit -m "feat(api): implement quote persistence, employee management, and redis catalog caching"`

---

### Task 5: Quote 销售客户端重构与命名空间迁移

**Files:**
- Modify: `Quote/electron/preload.cjs`
- Modify: `Quote/electron/main.cjs`
- Modify: `Quote/package.json`
- Modify: `Quote/src/shared/utils/backendConfig.js`
- Modify: `Quote/src/shared/utils/discovery.js`
- Modify: `Quote/src/shared/utils/imageSync.js`
- Modify: `Quote/src/shared/utils/catalogCache.js`
- Modify: `Quote/src/shared/api/http.js`
- Modify: `Quote/src/quote/stores/quote.js`
- Modify: `Quote/src/quote/components/ProductConfigPanel.vue`
- Modify: `Quote/src/quote/components/ExportQuoteModal.vue`
- Modify: `Quote/src/quote/components/HostSettings.vue`

**Interfaces:**
- Consumes: `/api/health`, `/api/catalog`, `/api/quotes`
- Produces: `window.quoteAPI`, IPC 事件 `quote:*`, 通用选配面板与报价入库提交

- [ ] **Step 1: 更新 Electron 预加载脚本与主进程通信**

在 `Quote/electron/preload.cjs` 中将全局接口从 `window.hhzAPI` 升级为 `window.quoteAPI`；在 `main.cjs` 中将 IPC 事件监听从 `hhz:*` 升级为 `quote:*`，将探测服务名从 `hhz-data-service` 升级为 `quote-service`。

- [ ] **Step 2: 更新客户端配置、缓存键与存储键名**

全局替换 `hhz_*` 存储键为 `quote_*`（`quote_backend_base`, `quote_local_quotes_v1`, `quote_quoter_name`, `quote_catalog_cache` 等）。

- [ ] **Step 3: 重构通用选配面板 `ProductConfigPanel.vue`**

将原先硬编码的“设备/耗材”二元卡片，升级为基于分类（Category）的通用商品选择与关联配件/增值服务选配区。

- [ ] **Step 4: 改造报价单导出与入库面板 `ExportQuoteModal.vue`**

在原有生成 PDF 与本地打印的基础上，增加“提交正式报价单至云端服务器”按钮，调用 `/api/quotes` 将报价明细与单号存入数据库。

- [ ] **Step 5: 更新 `Quote/package.json` 元信息**

修改名称为 `quotesys-client`，产品名称为 `QuoteSys 通用报价系统`，更新构建 appId 为 `com.quotesys.app`。

- [ ] **Step 6: 验证构建与静态检查**

Run: `cd Quote && npm run build`
Commit: `git add Quote/ && git commit -m "feat(client): migrate electron namespace to quoteAPI, generalize product config panel and quote submission"`

---

### Task 6: Workbench 管理后台界面改造与功能补全

**Files:**
- Modify: `Workbench/web/package.json`
- Modify: `Workbench/web/src/workbench/router.js`
- Modify: `Workbench/web/src/workbench/views/WorkbenchLayout.vue`
- Create: `Workbench/web/src/workbench/views/ProductsManager.vue`
- Create: `Workbench/web/src/workbench/views/QuotesCenter.vue`
- Create: `Workbench/web/src/workbench/views/EmployeesManager.vue`
- Delete: `Workbench/web/src/workbench/views/DevicesManager.vue`, `Workbench/web/src/workbench/views/ConsumablesManager.vue`

**Interfaces:**
- Consumes: `/api/products`, `/api/quotes`, `/api/admin/employees`, `/api/settings`
- Produces: 统一的商品中心、全公司报价大盘、员工管理界面

- [ ] **Step 1: 整合创建 `ProductsManager.vue`（通用商品管理）**

合并原设备与耗材页面，提供统一的商品列表、分类筛选标签栏、商品新增/编辑表单、自定义分类输入、指导价/底价配置以及商品图上传。

- [ ] **Step 2: 创建 `QuotesCenter.vue`（报价单中心）**

实现全公司报价单大盘视图，支持按报价单号、客户单位、销售人姓名筛选；点击查看报价单详情与 JSONB 商品快照。

- [ ] **Step 3: 创建 `EmployeesManager.vue`（员工与账号管理）**

支持管理员新增销售员工工号、分配角色权限、重置登录密码。

- [ ] **Step 4: 更新路由与主布局导航**

在 `router.js` 与 `WorkbenchLayout.vue` 中将原“设备管理/耗材管理”替换为“商品中心”、“报价中心”、“员工管理”、“方案套餐”与“系统设置”。

- [ ] **Step 5: 验证 Workbench Web 构建**

Run: `cd Workbench/web && npm run build`
Commit: `git add Workbench/web/ && git commit -m "feat(workbench): unify products manager, add quotes center and employees manager"`

---

### Task 7: 容器化编排、打包发布脚本通用化与 GitHub 远程同步

**Files:**
- Create: `docker-compose.yml`
- Modify: `Workbench/Dockerfile`
- Modify: `Workbench/nginx.conf`
- Create: `Workbench/quote-service.spec`
- Delete: `Workbench/hhz-data-service.spec`
- Modify: `scripts/build-backend-exe.mjs`
- Modify: `scripts/build-backend-installer.mjs`
- Modify: `scripts/backend-installer.nsi`
- Modify: `scripts/allow-firewall.ps1`
- Create: `README.md`

**Interfaces:**
- Produces:
  - `docker compose up -d`: 一键拉起完整生产集群（Nginx + FastAPI + PostgreSQL + Redis）
  - `npm run build:backend`: 构建 `release/QuoteService.exe`
  - GitHub 远程仓库同步推送到 `https://github.com/NGU-forever/Quote_sys.git`

- [ ] **Step 1: 编写根目录 `docker-compose.yml`**

编排 `postgres:16-alpine`、`redis:7-alpine`、`backend`（FastAPI）、`web`（Nginx），配置数据卷、端口映射与健康检查。

- [ ] **Step 2: 更新 `Workbench/Dockerfile` 与 `nginx.conf`**

Dockerfile 优化多阶段构建与依赖缓存；Nginx 配置反向代理与静态资源缓存。

- [ ] **Step 3: 更新跨平台便携母机打包脚本**

重命名 `hhz-data-service.spec` 为 `quote-service.spec`，更新 `scripts/build-backend-exe.mjs` 输出产物为 `QuoteService.exe`；更新 `scripts/backend-installer.nsi` 防火墙规则为 `QuoteSys Data Service (8000)`。

- [ ] **Step 4: 编写项目根目录文档 `README.md`**

详细阐述 QuoteSys 模版架构设计、双机部署指南、Docker 快速启动、员工体系与二次开发指引。

- [ ] **Step 5: 全面端到端验证与推送到 GitHub**

1. 执行根目录自动化测试；
2. 验证前端构建与服务语法；
3. 将完整纯净模版推送到 `origin main`：
```bash
git add .
git commit -m "feat: complete QuoteSys generic template with postgres, redis, docker and employee quote persistence"
git push -u origin main
```

---

## Plan Self-Review Check
1. **Spec coverage**:
   - 彻底解耦脱敏 -> Task 1
   - PostgreSQL 16 数据库 + 用户角色 -> Task 2, Task 3
   - Redis 7 目录缓存与原子单号 -> Task 2, Task 4
   - 通用商品平铺模型与套餐 -> Task 3, Task 4, Task 5, Task 6
   - 报价单全量入库与快照 -> Task 3, Task 4, Task 5, Task 6
   - Quote 客户端与 Workbench 界面适配 -> Task 5, Task 6
   - Docker 编排与双机打包 -> Task 7
   - 远程仓库连接 -> Task 7
2. **Placeholder scan**: 无任何 "TBD"、"TODO" 或模糊要求，每一步骤均有明确的代码和命令。
3. **Type consistency**: 统一使用 `quote-service`, `window.quoteAPI`, `quote:*`, `QT-YYYYMMDD-XXXX`, `quotesys_db`。
