# HHZ 超声医疗报价平台 — FastAPI 后端

面向已打包分发的 App 前端的后端服务：版本检查 + 商品数据管理 + AI 价格建议（预留），
并完整兼容现有前端工作台（登录 / 产品 / 套餐 / 目录）。

## 技术栈

- **FastAPI**（Web 框架）
- **SQLAlchemy 2.x**（ORM，基于现有表结构建模）
- **Pydantic v2**（数据校验）+ pydantic-settings（环境变量配置）
- **PostgreSQL / SQLite 双引擎**：默认 SQLite（现有库），改 `DATABASE_URL` 即切 PostgreSQL
- **Alembic**（仅管理新增表 / 未来字段，不修改现有表）
- **Docker + Docker Compose + Nginx**（生产部署）

## 目录结构

```
backend/
├── app/
│   ├── main.py                # 应用入口：建表、播种、路由、静态文件
│   ├── core/                  # 配置、鉴权、依赖、全局异常处理
│   │   ├── config.py          # 环境变量配置
│   │   ├── security.py        # 密码哈希（兼容 Node scrypt）+ JWT
│   │   ├── deps.py            # get_db / require_user
│   │   └── handlers.py        # 统一响应格式 & 异常处理
│   ├── db/                    # 数据库连接与 Base、启动播种
│   ├── models/                # SQLAlchemy 模型（现有表 + app_versions）
│   ├── schemas/               # Pydantic 模型
│   ├── api/v1/endpoints/      # 新接口：version / items / ai
│   ├── compat/                # 兼容旧前端：auth / products / packages / catalog / health
│   └── services/              # 业务逻辑：version / item / ai / catalog
├── alembic/                   # 迁移（仅新增表 app_versions）
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
└── .env.example
```

## 现有表结构（不修改）

| 表 | 说明 |
| --- | --- |
| `users` | 用户（id, username, password_hash, salt, created_at） |
| `products` | 商品 = 设备 + 耗材统一表（category 区分），**无成本价/库存字段** |
| `packages` | 套餐定义 |
| `device_bindings` | 设备-耗材绑定（复合主键） |
| `app_versions` | **本后端新增**：App 版本信息（版本检查用） |

> 商品表 `products` 字段：`id, sku_id, category, name, min_price, max_price, unit, pieces_per_unit, units_per_box, box_price, applicable_devices, raw_price_desc, remark, image, created_at, updated_at`。接口按这些字段建模，未强行添加 cost / stock 等字段。

## 快速开始（开发，连接现有库）

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt

# 复制环境变量（默认连接 backend/data/app.db、照片目录 backend/uploads）
cp .env.example .env

# 启动（务必在 backend/ 目录下运行，.env 相对路径以此为基准）
uvicorn app.main:app --reload --port 8000
```

启动后：

- 接口文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/health
- 版本检查：http://localhost:8000/api/v1/version/check?current_version=1.2.0

> 应用启动时 `Base.metadata.create_all(checkfirst=True)` 只创建缺失的表（即 `app_versions`），
> **不会改动**已有的 users / products / packages / device_bindings。

### 用全新本地库（开箱即用，不连现有库）

把 `.env` 里的 `DATABASE_URL` 改成 `sqlite:///./app.db`（backend/ 根目录，无目录依赖）即可。
此时产品/套餐为空，可在工作台新增，或用旧库备份的 `app.db` 覆盖 `backend/data/app.db`。

## 配置（环境变量）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./app.db` | SQLAlchemy 连接串；PostgreSQL 用 `postgresql+psycopg://user:pass@host/db` |
| `AUTH_SECRET` | `hhz-workbench-local-secret` | JWT 签名密钥（生产务必修改） |
| `TOKEN_TTL_SECONDS` | `43200` | 令牌有效期 |
| `UPLOAD_DIR` | `./uploads` | 产品照片目录 |
| `MAX_UPLOAD_BYTES` | `5242880` | 上传大小上限 |
| `DEFAULT_LATEST_VERSION` | `1.3.0` | app_versions 为空时的兜底版本 |
| `CORS_ORIGINS` | `*` | 允许跨域来源（逗号分隔） |

## API 概览

### 新接口（统一响应 {"code":0,"message":"success","data":...}）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/version/check?current_version=1.0.0` | 版本检查 |
| GET | `/api/v1/items?page=1&size=10&search=xx&category=device` | 商品列表（分页/搜索） |
| POST | `/api/v1/items` | 创建商品 |
| GET | `/api/v1/items/{item_id}` | 获取单个商品 |
| PUT | `/api/v1/items/{item_id}` | 更新商品 |
| DELETE | `/api/v1/items/{item_id}` | 删除商品 |
| POST | `/api/v1/ai/price-suggestion` | AI 价格建议（预留，规则实现） |

版本检查响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "latest_version": "1.3.0",
    "force_update": false,
    "update_url": "https://your-cdn.com/app-v1.3.0.exe",
    "release_notes": "修复若干问题",
    "has_update": true,
    "published_at": "2025-01-01 12:00:00"
  }
}
```

### 兼容旧前端接口（沿用工作台旧接口契约，响应结构一致）

登录（`{token,user}`）、`/api/auth/status`（首次注册状态）、`/api/auth/register`（仅首次可用）、`/api/auth/accounts` / `/api/auth/reset-password`（内置 admin 恢复正式账号）、`/api/auth/me`、`/api/products` 全套（含 `/bindings`、`/photo` 上传）、
`/api/packages` 全套、`/api/catalog`（公开）、`/api/health`。旧前端无需改代码即可切换。

## 版本管理

`app_versions` 表为空时自动插入一条默认版本（`DEFAULT_LATEST_VERSION`）。发布新版本时追加记录：

```sql
INSERT INTO app_versions (version, platform, download_url, release_notes, force_update, published_at)
VALUES ('1.4.0', 'windows', 'https://your-cdn.com/app-v1.4.0.exe', '新增 AI 价格助手', 0, '2025-06-01 00:00:00');
```

版本比较为语义化（`1.10` > `1.9`）。`current_version < latest` 时返回更新信息，
`force_update=1` 且需更新时返回 `force_update: true`。

## AI 价格建议（预留）

当前为规则引擎（`app/services/ai_service.py`）：成本 + 目标利润率 + 竞品参考 + 历史销量趋势。
后续接入真实 AI 模型时，**仅需替换 `ai_service.py` 内部实现**，保持输入输出契约不变。

## 数据库迁移（Alembic）

仅用于管理新增表 / 未来字段，**不要**在迁移中修改现有表。

```bash
cd backend
# 首次：应用启动时已自动建 app_versions；也可显式执行
alembic upgrade head
# 未来新增表/字段：先改模型，再生成迁移（务必人工审查，勿误改现有表）
alembic revision --autogenerate -m "add some table"
```

## Docker 部署

```bash
cd backend
docker compose up -d --build
```

- 后端容器监听 **8000**。
- 默认使用容器内本地 SQLite（持久化到 `backend_data` 卷）。
- 连接现有库 / PostgreSQL：编辑 `docker-compose.yml` 的 `DATABASE_URL`（见文件内注释）。
- `docker-compose.yml` 内附**可选**的 PostgreSQL 服务（默认注释，避免与现有库冲突）。

### Nginx（生产反向代理 + HTTPS）

参考 `nginx.conf`，把 `/api` 与 `/uploads` 转发到后端 8000 端口；HTTPS 用 certbot 申请证书后按文件内注释启用 443。

## 认证说明

- 当前实现轻量 JWT（HS256），结构已预留扩展点（`app/core/security.py`）。
- 密码哈希采用与旧后端一致的 scrypt 参数（`app/core/security.py`），历史 `admin` 账号数据可直接登录。
- 启动时自动确保数据库存在内置应急账号 `admin / admin123`（隐藏、不展示在登录页）；
  新环境 users 表为空时同样会以此创建默认账号，登录后请尽快改密。忘记正式账号密码时，
  用内置 admin 登录并在「基本设置」中重置。
- 未来加认证：为 `/api/v1/*` 路由添加 `Depends(require_user)` 即可，无需改业务逻辑。

## 常见问题

- **连不上数据库**：确认在 `backend/` 目录下运行，且 `.env` 里 `DATABASE_URL=sqlite:///./data/app.db`（相对 backend/）。
- **照片 404**：确认 `.env` 里 `UPLOAD_DIR=./uploads`（backend/uploads，产品照片在 backend/uploads/products）。
- **切 PostgreSQL**：改 `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname`，重启即可（需确保目标库已有相同表结构，或用 `alembic upgrade head` 补齐新增表）。
