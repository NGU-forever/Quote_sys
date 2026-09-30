# 主从局域网拆分：后端数据服务 exe + 前端报价 exe（设计规格）

Date: `2026-09-04`
Status: `approved for planning`
Branch: `feat/quote-page-redesign`

## 1. 背景与目标

当前是「落地页 + 工作台 + FastAPI 后端」的一个混合应用：后端用 venv/Docker 跑，
前端落地页与工作台共用一个 Vue 工程、一个 Electron 壳。

目标：拆成两个独立 Windows exe，形成**局域网主从（母机/客户机）**架构。

- **主设备（母机）**：`HHZ数据服务.exe` — 托盘后台服务，FastAPI 常驻 `8000`，托管工作台网页，
  存 SQLite + 产品图片；管理员用浏览器进 `http://127.0.0.1:8000` 管理设备/耗材/套餐/公司信息/报价参数。
- **客户机（从机）×N**：`HHZ报价.exe` — 仅报价落地页，启动自动发现主设备，同步目录+公司+报价参数+图片；
  主设备不在线则用本地缓存，从没同步过用内置演示数据。

同步为**单向主→从**，客户机绝不回写服务器。

## 2. 已确认决策（用户逐条批准）

1. **主设备发现 = C**：自动发现（HTTP 网段扫描 `/api/health`）+ 手动 IP 兜底。
2. **工作台 = A**：后端 exe 托管工作台静态页，浏览器打开 `http://127.0.0.1:8000` 管理；前端 exe 无工作台。
3. **离线数据 = C**：优先「上次同步的真实目录」，从没同步过才用内置演示数据。
4. **后端 exe = A**：Windows 系统托盘后台服务，开机自启、常驻 `8000`。
5. **同步范围 = B**：设备 + 耗材 + 套餐 + 绑定 + 产品图片 + 公司信息 + 报价参数。
   （报价历史回传、客户信息、多主设备、跨网段、macOS、推送更新 → 二期不做。）

## 3. 整体架构与数据流

```
┌─ 主设备（母机）──────────────────────────────┐
│  HHZ数据服务.exe (Windows 托盘程序)            │
│   ├─ FastAPI → 常驻 0.0.0.0:8000              │
│   │    /api/sync      目录+公司+报价参数(新增) │
│   │    /api/settings  GET/PUT(登录)           │
│   │    /api/catalog   目录(保留,兼容)          │
│   │    /api/health    健康检查(带 app 标识)    │
│   │    /uploads       产品图片                 │
│   │    /              工作台静态页(浏览器打开)  │
│   ├─ SQLite app.db + uploads/ (%APPDATA%\HHZ) │
│   └─ 托盘: 打开工作台/打开数据目录/自启/退出     │
└───────────────────────────────────────────────┘
          ▲ 同一局域网 · 固定 8000 端口
┌─ 客户机（从机）×N ────────────────────────────┐
│  HHZ报价.exe (Electron)                        │
│   ├─ 报价落地页(无登录/无工作台)               │
│   ├─ 「连接主设备」设置页(齿轮入口)             │
│   ├─ 启动: 自动发现→(失败)手动IP→              │
│   │        (失败)本地缓存→(首次)内置演示数据    │
│   └─ 本地缓存: 目录+公司+参数+图片(app-img://)  │
└───────────────────────────────────────────────┘
```

**同步流程（单向主→从）**

1. 客户机启动 → Electron 主进程自动发现：推导本机网段 `192.168.x.0/24`，并发探测
   `.1–.254` 的 `:8000/api/health`，校验响应含 `"app":"hhz-data-service"`，取第一个命中者。
   极短超时(~120ms) + 并发(~32 路)，约 1–2 秒出结果；未命中用手动保存 IP。
2. 连上后拉 `GET /api/sync`，得到 `catalog + settings + rev + updated_at`；
   图片照现有 `syncImages()` 逻辑增量同步到 `userData/image-cache`。
3. 同步成功 → 覆盖本地缓存 JSON 并应用；失败 → 读本地缓存；无缓存 → 内置演示数据 + 提示「未连接主设备」。
4. 每次成功同步刷新本地缓存，保证主设备离线时仍用最近一次真实数据。

## 4. 后端改动

### 4.1 监听地址与防火墙
- exe 内 uvicorn 绑定 **`0.0.0.0:8000`**（dev 脚本仍保持 127.0.0.1 不变，二者互不影响）。
- 安装器 / 首次运行放行 Windows 防火墙入站规则：TCP 8000，仅「专用网络」。

### 4.2 新增 `app_settings` 表
- `key TEXT PRIMARY KEY, value TEXT(JSON), updated_at TEXT`。只增表，不改旧表。
- 两个 key：`company`（name/phone/email/address）、`pricing`（devicePrice/bagsPerBox/giftRatio/
  plan2UnitPrice/plan2MinBoxes/quoteValidityDays/quotePrefix/plan1Tiers[]）。
- 启动播种默认值 = 现有 `src/stores/settings.js` 的 company + `src/data/pricing.js` 的 PRICING。

### 4.3 新增/调整接口
| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/sync` | 公开 | `data: { catalog, settings, rev, updated_at }`；`catalog` 复用 `build_catalog`；`settings: { company, pricing }`；`rev` 为内容哈希 |
| GET | `/api/settings` | 登录 | 读 `{ company, pricing }` |
| PUT | `/api/settings` | 登录 | 写 `{ company, pricing }`（整体替换） |
| GET | `/api/health` | 公开 | 增加 `"app":"hhz-data-service"` 标识（自动发现用），保留 `ok/time` |

- `/api/catalog` 保留不变（兼容旧前端 / 网页版）；新同步统一走 `/api/sync`。
- `rev` 内容哈希用于「无变化短路」优化；数据量小，默认每次拉全量，不做差量。

### 4.4 工作台静态页 + 「基本设置」页
- 工作台打独立静态构建，由 FastAPI 托管在 `/`，浏览器开 `http://127.0.0.1:8000` 进登录。
- 新增「基本设置」页（`/workbench/settings`），表单为 company + pricing，对接 GET/PUT `/api/settings`。
- 工作台路由历史在浏览器托管下改用 **hash history**（见 §5.1）。

### 4.5 打包（PyInstaller）
- PyInstaller 打 `HHZ数据服务.exe`（Python + uvicorn + pystray）。
- 入口：后台线程起 uvicorn(`0.0.0.0:8000`) → 起托盘 → 首次运行自动开浏览器进工作台。
- 托盘菜单：打开工作台 / 打开数据目录 / 开机自启(开关) / 退出。
- 数据目录 `%APPDATA%\HHZ`（`app.db` + `uploads/`），不随 exe；自启写 `HKCU\...\Run`。
- 分发：先绿色版 zip，后续可选 NSIS/Inno Setup 安装器（放行防火墙 + 快捷方式）。

## 5. 前端改动

### 5.1 一套代码两种构建（Vite 多入口，不复制代码）
| 产物 | 入口 | 路由 | 去向 |
| --- | --- | --- | --- |
| `index.html`（报价版） | 只挂落地页 | 精简 | 前端 exe |
| `workbench.html`（管理版） | 只挂工作台 | 精简 | 后端 exe 托管 |

- 路由历史：报价版（Electron）继续 `createMemoryHistory`；workbench 托管浏览器用 **hash history**（`#/workbench`），FastAPI 托管免 fallback 重写。
- 共享组件/store/api/utils 两边复用，仅入口文件不同。

### 5.2 前端 exe 去登录/工作台
- 移除报价版路由 `/workbench/*`、`/workbench/login`，只留落地页；`auth` store、`LoginView`、各 `Manager` 仍留在代码库供 workbench 版用，不进入报价版构建。

### 5.3 「连接主设备」设置页
- 落地页顶栏齿轮入口；内容：自动发现结果/按钮、手动地址输入(`http://IP:8000`)+测试连接+保存、
  最后同步时间、数据来源标识（主设备/本地缓存/内置演示）。

### 5.4 自动发现（Electron 主进程）
- 本机 IP → 推导 `192.168.x.0/24` → 并发探测 `:8000/api/health` → 校验 `"app":"hhz-data-service"`。
- `net.fetch` + ~120ms 超时 + ~32 并发，1–2 秒出结果；结果回填后端地址。

### 5.5 目录本地持久化
- 新增目录缓存层：把 `/api/sync` 的 `catalog + settings + rev + updated_at` 存 `userData` JSON。
- 启动顺序：自动发现 → `/api/sync` →（成功）覆盖缓存并应用 →（失败）读缓存 →（无缓存）内置演示 + 提示。
- 公司信息/报价参数改「缓存优先、回退内置」，替代 `settings.js` 写死值。
- 图片同步（`syncImages` + `app-img://`）逻辑不变，仅地址来源接到「发现到的地址」。

## 6. 验收标准

**主设备**
- 双击 `HHZ数据服务.exe` → 托盘出现、浏览器自动开工作台登录页。
- 局域网另一台机器访问 `http://主设备IP:8000/api/health` 返回含 `"app":"hhz-data-service"`。
- 工作台可增删改设备/耗材/套餐、传照片；「基本设置」可改并保存公司信息 + 报价参数。
- 关浏览器不影响服务；托盘「退出」才停；勾「开机自启」后重启机器服务自动起来。

**客户机**
- 打开只有报价落地页，无登录/工作台入口。
- 首启且主设备在线：自动发现 ~2 秒完成，显示主设备真实目录/图片/公司抬头/报价参数。
- 主设备离线重启客户机：用本地缓存显示最近一次真实目录，顶栏提示离线；从未同步过的机器显示内置演示 + 「未连接主设备」。
- 主设备改数据后客户机重启（或手动同步）看到最新数据；图片增量不重复下载。

## 7. 风险与回滚

| 风险 | 对策 |
| --- | --- |
| 网段扫描慢/误判 | 极短超时 + 并发 + `app` 标识校验；失败不影响回退链 |
| 防火墙挡 8000 | 安装器自动放行；绿色版附 `netsh` 命令 |
| 0.0.0.0 暴露面 | 仅放行专用网络；管理接口仍须登录 |
| 数据丢失 | 数据目录 `%APPDATA%\HHZ`，托盘「打开数据目录」一键备份 |
| 两套构建路由历史错乱 | workbench 用 hash history，报价版用 memory history |

**回滚**：后端 exe 仅是打包形态，原 `npm run dev:server` / Docker 部署保留；旧前端仍连旧 `/api/catalog`（接口未删）。

## 8. 实施顺序（每阶段可独立验证）

- **P0 后端接口**：`app_settings` 表 + `/api/sync`、`/api/settings` + health 标识。
- **P1 工作台**：基本设置页 + Vite 多入口（`workbench.html` 由后端托管）。
- **P2 后端打包**：PyInstaller + 托盘 + `0.0.0.0` + 防火墙 + 自启 → `HHZ数据服务.exe`。
- **P3 前端拆分**：前端 exe 去工作台 + 连接主设备页 + 自动发现 + 目录持久化 → `HHZ报价.exe`。
- **P4 联调**：双机实测自动发现/离线兜底/改数据同步 + 安装器 + 使用文档。

## 9. 兼容边界（不得破坏）

- 现有接口：`/api/catalog`、`/api/products*`、`/api/packages*`、`/api/auth*`、`/api/health`、`/uploads` 全部保留。
- 现有表结构 users / products / packages / device_bindings 不改，仅新增 `app_settings`。
- 旧前端（单应用网页版）与 dev 链路（`npm run dev`）保持可用。

## 10. ADR 信号（待后续补记）

- 新增跨进程契约：`/api/sync` 返回结构（`catalog/settings/rev/updated_at`）。
- 新增数据源边界：客户机本地缓存为「只读离线兜底」，无写入路径。
- 新增运行时边界：后端 exe 绑定 `0.0.0.0:8000`（局域网可达）。
- 新增打包形态：PyInstaller 托盘服务（后端）、Electron 报价版（前端）两个 exe。

## 11. 附：工作产物摘要

- **TaskIntentDraft**：把单应用拆成「母机数据服务 exe + 客户机报价 exe」，局域网单向同步 + 离线兜底。
- **ImpactStatementDraft**：受影响层 = 后端(接口+表+打包)、前端(入口拆分+发现+持久化)、electron(扫描+缓存)；不破坏旧接口/旧表/dev 链路。
- **Non-goals**：报价历史回传、客户信息、多主设备、跨网段、macOS、推送更新。
