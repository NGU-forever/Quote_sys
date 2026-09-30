# HHZ 超声医疗报价平台 — 初始双基线快照

Date: `2026-09-04`
Status: `initial dual-baseline snapshot`

## 1. Purpose
本快照记录「主从局域网拆分」设计启动前，项目的需求与架构边界现状，
供后续 `Baseline Role Alignment` 检查对照，判断实现是否偏离基线。

## 2. Workspace Structure
```
backend/       FastAPI 后端（SQLAlchemy + SQLite/PostgreSQL，端口 8000）
electron/      Electron 主进程 + preload（图片缓存同步、app-img:// 协议）
src/           Vue3 + Vite + Pinia 前端（落地页 + 工作台）
scripts/       dev / server / serve-backend 等启动脚本
dist/          Vite 构建产物
release/       electron-builder 输出
```

## 3. Current Authority Surfaces
- `package.json`（脚本 + electron-builder 配置）
- `backend/README.md`（后端结构与接口契约）
- `backend/app/core/config.py`（环境变量配置）
- 无 docs/aegis、无 ADR（本次初始化补齐）

## 4. Product / Requirement Baseline
### 4.1 Current Truth
- 单一应用：落地页（客户报价）+ 工作台（登录后管理设备/耗材/套餐）。
- 后端部署形态：venv + uvicorn（dev）/ Docker + Nginx（生产），监听 127.0.0.1:8000。
- 同步现状：App 启动时 `hydrateFromRemote()` 拉 `/api/catalog`，失败回退内置静态演示数据（`src/data/productCatalog.js`）；Electron 下 `syncImages()` 把图片同步到 `userData/image-cache`，`app-img://` 本地读取。
- 后端地址配置：`localStorage.hhz_backend_base`，登录页可手动填 + 测试连接。

### 4.2 Non-negotiables
1. 产品/套餐/绑定/登录/照片上传的**现有接口契约不变**（旧前端兼容）。
2. 现有表结构 users / products / packages / device_bindings 不被修改（只增表）。
3. 同步为**单向主→从**，客户机绝不回写服务器。

### 4.3 Product Non-goals
- 报价历史回传与统计、客户信息管理、多主设备、跨网段（跨 VLAN）、macOS 版。

## 5. Architecture / Runtime Boundary Baseline
### 5.1 Current Truth
- 后端：FastAPI，`/api/v1/*`（新接口）+ `/api/*`（兼容旧前端）+ `/uploads` 静态。
- 目录接口 `/api/catalog` 由 `build_catalog` 生成 `{products, packages}`，产品 id 稳定生成，绑定用 `boundConsumables`。
- 前端：`createMemoryHistory` 路由（Electron file:// 专用），落地页 + 工作台共用一个 Vue 工程。

### 5.2 Architecture Non-negotiables
1. 数据源唯一权威 = 后端数据库（主设备）。
2. 客户机本地缓存/内置数据仅作离线兜底，无写入权限。

### 5.3 Architecture Non-goals
- 服务端渲染、微服务拆分、多后端负载均衡。

## 6. Ownership / Contract Snapshot
- 目录构建 → `backend/app/services/catalog_service.py::build_catalog`
- 产品/套餐/绑定接口 → `backend/app/compat/{products,packages,catalog}.py`
- 前端目录水合 → `src/stores/catalog.js::hydrateFromRemote`
- 后端地址 → `src/utils/backendConfig.js`
- 图片同步 → `electron/main.cjs::syncImages` + `src/utils/imageSync.js`

## 7. Current State and Risks
- 阶段：已完成单应用报价 + 工作台 + 图片同步，待做主从拆分。
- 风险：监听地址为 127.0.0.1（局域网不可达）、Windows 防火墙、离线数据是内置演示而非上次真实同步。

## 8. Alignment Use
- 读需求基线：确认"同步范围 / 离线行为 / 管理入口"等产品决策。
- 读架构基线：确认"接口契约 / 数据源边界 / 监听地址"等架构边界。
- 出现既有接口契约变化时，报 `scope: both`。

## 9. Compatibility Boundary
- 不得破坏：`/api/catalog`、`/api/products*`、`/api/packages*`、`/api/auth*`、`/api/health`、`/uploads`。
- 旧前端（单应用网页版）仍须能连旧接口运行。
