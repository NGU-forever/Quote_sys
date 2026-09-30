# QuoteSys 通用商业报价系统模版

<p align="center">
  <img src="assets/templates/logo.png" alt="QuoteSys Logo" width="180" onerror="this.style.display='none'"/>
</p>

<p align="center">
  <b>企业级高可靠、轻量化、多品类通用商业报价与协同销售管理平台</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-blue.svg" alt="Python Version"/>
  <img src="https://img.shields.io/badge/FastAPI-0.110+-009688.svg" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/PostgreSQL-16-336791.svg" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/Redis-7-DC382D.svg" alt="Redis"/>
  <img src="https://img.shields.io/badge/Vue-3.5-4FC08D.svg" alt="Vue 3"/>
  <img src="https://img.shields.io/badge/Electron-33+-47848F.svg" alt="Electron"/>
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED.svg" alt="Docker"/>
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License"/>
</p>

---

## 🌟 项目定位与核心特性

**QuoteSys** 是一套开箱即用、面向多行业的通用商业报价模版系统。针对企业在销售报价环节中存在的“品类层级复杂、底价泄露风险、多人单号冲突、离线协同困难、安装部署繁琐”等痛点，提供了一套前后端解耦、架构稳固、可灵活单机亦可云端集群的完整解决方案。

- 📦 **多品类商品中心与定价引擎**：统一纳管标准设备（主品）、配套耗材/辅件、优惠推广套餐，支持阶梯折扣、底价保护线与设备-耗材兼容性动态校验。
- 🛡 **企业级高可靠持久化**：统一采用 **PostgreSQL 16** 高并发关系型数据库（生产、单机离线与测试同一引擎），支撑并发写入、事务一致性与在线备份。
- ⚡ **Redis 7 目录缓存与分布式原子单号**：商品目录与系统设置全量缓存（`quote:catalog:data`），毫秒级极速检索；基于 Redis INCR 实现并发安全的每日单号自增（`QT-YYYYMMDD-XXXX`），杜绝重号漏号。
- 👥 **多角色权限隔离与协同闭环**：
  - **管理端（Admin）**：商品字典维护、底价把控、员工账号启用/停用、全公司报价单归档与导出。
  - **销售端（Sales）**：专属账号登录、报价单草稿暂存、一键生成 PDF/打印预览；行级数据隔离，销售员仅可查阅属于自己的报价单历史。
- 📡 **局域网双机自动探测与离线协同**：销售端集成 UDP 广播智能嗅探母机服务（`0.0.0.0:8000`），无外网环境亦可通过一根网线或移动热点即连即用。
- 🖥 **跨平台全端覆盖**：
  - **后台工作台 (`quotesys-workbench-web`)**：基于 Vue 3 + Pinia + Lucide 的响应式 Web 现代管理后台。
  - **销售客户端 (`quotesys-client`)**：基于 Electron + Vue 3 的跨平台桌面软件，支持一键打印、离线缓存与多窗口托盘运行。

---

## 🏗 系统架构图

```mermaid
flowchart TB
    subgraph ClientLayer["客户端接入层"]
        WebAdmin["💻 Web 管理后台\n(Vue 3 + Vite)"]
        ElectronClient["🖥️ 销售客户端\n(Electron + Vue 3)"]
    end

    subgraph GatewayLayer["服务接入与网关层"]
        Nginx["🌐 Nginx 反向代理\n(端口 80 / 443)"]
    end

    subgraph ServiceLayer["业务后端服务 (FastAPI)"]
        QuoteService["⚙️ Quote-Service 后端 API\n(Uvicorn 端口 8000)"]
        subgraph Modules["核心业务模块"]
            AuthMod["鉴权中心 (JWT)"]
            CatalogMod["商品与套餐中心"]
            QuoteMod["报价单持久化引擎"]
            EmployeeMod["员工与权限管理"]
            AgentMod["AI 资料导入 Agent"]
        end
    end

    subgraph DataLayer["数据存储与缓存层"]
        PostgresDB[("🐘 PostgreSQL 16\n(唯一主库: 5432)")]
        RedisCache[("⚡ Redis 7\n(目录缓存与单号原子计数: 6379)")]
    end

    WebAdmin -->|HTTP / SPA| Nginx
    Nginx -->|/api/* 代理| QuoteService
    ElectronClient -->|局域网 HTTP / UDP 探测| QuoteService

    QuoteService --> Modules
    Modules -->|SQLAlchemy ORM| PostgresDB
    Modules -->|TTL 缓存 / 原子 INCR| RedisCache
```

---

## 🚀 快速启动指南

### 方式 A：Docker Compose 一键启动（完整生产环境）

适用于 Linux 服务器、云主机或支持 Docker 的局域网主机，一键编排并自动完成健康检查与数据库初始化。

1. **克隆代码仓库**：
   ```bash
   git clone https://github.com/NGU-forever/Quote_sys.git
   cd Quote_sys
   ```

2. **启动全栈容器集群**：
   ```bash
   # 启动 PostgreSQL 16 + Redis 7 + FastAPI 后端 + Nginx
   docker compose up -d --build
   ```

3. **服务访问入口**：
   - 🌐 **工作台管理后台**：访问 `http://localhost/` 或 `http://<服务器IP>/`
   - ⚙️ **后端 API 交互文档 (Swagger UI)**：访问 `http://localhost:8000/docs`
   - 🩺 **健康检查端点**：`http://localhost:8000/api/health`

4. **管理容器状态**：
   ```bash
   # 查看实时日志
   docker compose logs -f
   # 停止并移除容器
   docker compose down
   ```

---

### 方式 B：本地开发与联调模式

#### 1. 前置依赖
- **Node.js** >= 18.x
- **Python** >= 3.11
- **PostgreSQL** 16（推荐用 Docker 只启动数据库：`docker compose up -d postgres`）
- **Redis** 7.x（可选，不可用时自动降级；或 `docker run -d -p 6379:6379 redis:7-alpine`）

#### 2. 初始化后端环境 (`Workbench/`)
```bash
cd Workbench
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装 Python 依赖
pip install -r requirements.txt

# 配置数据库连接（默认已指向本机 5432 的 quotesys_db）
cp .env.example .env

# 启动后端服务 (默认监听 127.0.0.1:8000，首次运行自动建表并播种 admin 账号)
uvicorn app.main:app --reload --port 8000
```

#### 3. 启动管理工作台前端 (`Workbench/web/`)
```bash
cd Workbench/web
npm install
npm run dev
# 访问工作台开发服务：http://localhost:5174/workbench.html
```

#### 4. 启动销售客户端 (`Quote/`)
```bash
cd Quote
npm install
# 启动 Vite 开发服务 + Electron 桌面窗口
npm run dev:desktop
```

---

## 📦 生产发布与构建打包

系统提供了全自动化打包脚本，覆盖 Windows 便携母机服务端、安装器及 Electron 客户端：

### 1. 构建 Windows 单机母机服务 (`QuoteService.exe`)
母机可脱离 Docker 在 Windows 主机上直接作为托盘后台服务运行：
```bash
# 执行跨平台打包（Windows 本地原生构建，或 macOS/Linux 自动调用 Docker Wine 容器）
npm run build:backend
```
- **产物位置**：`release/QuoteService.exe`
- **特性**：
  - 托盘图标驻留，右键一键打开工作台、打开数据目录、设置开机自启；
  - 数据目录 `%APPDATA%\QuoteSys` 存放照片与数据库连接配置 `database_url.txt`（连接串优先取环境变量 `DATABASE_URL`）；
  - 命名互斥锁防止重复多开端口冲突。

### 2. 生成 Windows 安装器 (`QuoteSys-Service-Setup.exe`)
```bash
node scripts/build-backend-installer.mjs
```
- **产物位置**：`release/QuoteSys-Service-Setup.exe`
- **特性**：安装时通过 NSIS 自动配置 Windows 防火墙放行 TCP 8000 端口，确保销售客户端在局域网内可顺畅直连。

### 3. 构建 Electron 销售客户端安装包
```bash
npm run build:client
```
- **产物位置**：`Quote/release/`
- **特性**：生成绿色便携版或安装包，开箱支持局域网母机自动探测。

---

## 🔐 账号与权限管理

系统预设开箱即用的管理员账号，首次启动时由数据库播种引擎自动初始化：

| 角色 | 默认用户名 | 默认密码 | 权限说明 |
| :--- | :--- | :--- | :--- |
| **系统管理员 (Admin)** | `admin` | `admin123` | **受保留账号，不可删除或停用**。具有商品管理、员工账号增删改查、全局配置修改、查看并导出全公司所有报价单的最高权限。 |
| **业务销售员 (Sales)** | 由管理员在后台创建 | 自定义初始密码 | 登录销售端 Electron 客户端；录入客户信息、选取商品生成报价单；**行级数据隔离**，仅可查看属于该账号的报价历史。 |

> ⚠️ **生产部署建议**：系统首次上线后，请立即进入管理后台修改默认 `admin` 密码，并在环境变量中配置自定义高强度 `AUTH_SECRET`。

---

## ⚙️ 环境变量与配置字典

创建根目录 `.env` 或在容器编排中注入以下环境变量（参考 `.env.example`）：

| 环境变量名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `APP_ENV` | `development` | 运行环境：`development` 或 `production` |
| `APP_NAME` | `quote-service` | 后端服务名称标识 |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/quotesys_db` | 数据库连接串（**仅支持 PostgreSQL**，`postgresql+psycopg://` 协议）|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接串，用于商品目录全量缓存与单号原子自增 |
| `AUTH_SECRET` | `quotesys-auth-secret-key` | JWT Token 签名密钥（生产环境务必替换为 32 位以上随机强密钥） |
| `TOKEN_TTL_SECONDS`| `43200` (12小时) | 登录凭证有效时长（秒） |
| `UPLOAD_DIR` | `./uploads` | 商品/附件照片上传持久化目录 |
| `MAX_UPLOAD_BYTES`| `5242880` (5MB) | 单文件上传限制大小 |
| `CORS_ORIGINS` | `*` | 跨域允许来源列表，多域名以逗号分隔 |

---

## 📂 项目工程目录概览

```
Quote_Sys/
├── docker-compose.yml              # 根目录生产容器集群编排 (Postgres+Redis+FastAPI+Nginx)
├── package.json                    # 顶层集成脚本与开发调度命令
├── .env.example                    # 环境变量配置参考模版
├── assets/                         # 品牌资产与客制化模版目录
│   └── templates/                  # Logo、条款与商品导入示例
├── scripts/                        # 构建、自动化打包与防火墙脚本
│   ├── build-backend-exe.mjs       # QuoteService.exe 打包驱动脚本
│   ├── build-backend-installer.mjs # NSIS 安装器生成脚本
│   ├── backend-installer.nsi       # NSIS 安装包定义文件
│   └── allow-firewall.ps1          # Windows 防火墙 TCP 8000 放行脚本
├── Quote/                          # 销售端客户端 (Electron + Vue 3)
│   ├── electron/                   # 主进程 (main.cjs) 与预加载脚本 (preload.cjs)
│   ├── src/quote/                  # 报价界面、商品选择器、打印与 PDF 导出
│   └── src/shared/                 # 局域网广播探测、API 客户端与本地缓存
└── Workbench/                      # 管理工作台后端与 Web 前端
    ├── app/                        # FastAPI 现代后端服务架构
    │   ├── api/                    # 路由端点 (quotes, employees, auth, catalog)
    │   ├── core/                   # 核心配置、JWT 鉴权、异常捕获
    │   ├── db/                     # SQLAlchemy 2.0 模型基类、PostgreSQL 连接与种子数据
    │   ├── models/                 # 数据模型 (Product, User, Quote, DeviceBinding)
    │   └── services/               # 业务领域服务 (QuoteService, CatalogService)
    ├── web/                        # Web 管理后台前端 (Vue 3 + Pinia + Lucide)
    │   └── src/workbench/views/    # 商品管理、套餐管理、员工管理、报价中心
    ├── tests/                      # 单元与集成自动化测试套件 (Pytest)
    ├── Dockerfile                  # 后端生产环境多阶构建 Dockerfile
    ├── nginx.conf                  # Nginx 反向代理与前端静态资源配置
    └── quote-service.spec          # PyInstaller 单文件打包规范
```

---

## 📄 自动化测试与持续集成

项目拥有完整的测试套件，全面覆盖数据模型、权限校验、Redis 缓存与单号原子性：

```bash
# 1. 先启动 PostgreSQL（测试库会自动创建，连接串见 Workbench/tests/db_support.py）
docker compose up -d postgres

# 2. 执行全部 68 项自动化测试
cd Workbench && .venv/bin/python -m pytest tests -q
# 自定义测试库：TEST_DATABASE_URL=postgresql+psycopg://user:pwd@host:5432/quotesys_test
```

测试覆盖清单：
- ✅ `test_models.py`：商品、套餐、员工用户、报价单 ORM 映射与级联关系
- ✅ `test_infra.py`：PostgreSQL 连接、健康检查与 Redis 优雅降级探测
- ✅ `test_quote_api.py`：报价创建、底价校验、多角色行级权限隔离、防重复自增号
- ✅ `test_extractors.py` & `test_quality_nodes.py`：AI 资料导入与规则校验

---

## 📜 许可证与免责声明

本项目基于 [MIT License](LICENSE) 开源协议发布，允许商业使用、修改与分发。
如需客制化导入自有行业商品目录或更换企业抬头，请遵循 `assets/templates/README.md` 规范。
