# HHZ 报价平台 — 双模式构建与部署手册（开发 / 交付）

本手册回答一句话需求：**前后端都要既能「本地用代码直跑」，也能「本地打包成 exe 后部署到 Windows」**。
平台形态是两个独立 Windows 程序（主从局域网架构，详见 `docs/USER-GUIDE.md`）：

- **主设备** `HHZDataService.exe`：后端数据服务（FastAPI + SQLite + 托盘）+ 托管的工作台网页；
- **客户机** `超声医疗报价平台.exe`：报价落地页桌面壳（Electron），开机向主设备同步。

> 本仓库两套系统、同一仓库：`Quote/`（副系统·报价版，含 Electron 壳、报价计算器与只读同步层）与 `Workbench/`（主系统·FastAPI 后端 + `Workbench/web` 工作台前端）。
> 下述 npm 命令按系统在对应子目录下执行：报价版 `cd Quote`，工作台前端 `cd Workbench/web`，后端用 `scripts/serve-backend.mjs`（`npm run dev:server`，在 Quote 下）。

---

## 0. 总览

| 组件 | 模式 A：代码直跑（本机联调） | 模式 B：打包 exe（Windows 交付） |
| --- | --- | --- |
| 前端报价页（客户机桌面壳） | `npm run dev`（浏览器）／`npm run dev:desktop:all`（Electron） | `npm run build:win` → `Quote/release/超声医疗报价平台 Setup <版本>.exe` |
| 前端工作台（管理页，被后端托管） | 已构建 `Workbench/web/dist/workbench.html` 由后端直接托管，浏览器开 `http://localhost:8000` | 随 `HHZDataService.exe` 内嵌（`Workbench/web/dist/` 打进 exe） |
| 后端数据服务（FastAPI） | `npm run dev` 自带；或 `npm run dev:server` | `node scripts/build-backend-exe.mjs` → `release/HHZDataService.exe`（绿色版）+ `release/HHZDataService Setup <版本>.exe`（NSIS 安装版，安装时自动放行防火墙 TCP 8000） |

工作台前端开发态（可选）：`cd Workbench/web && npm run dev` → `http://localhost:5174/workbench.html#/workbench/login`；日常直接由后端托管已构建产物（`http://localhost:8000`）。

---

## 1. 前置条件（一次性）

### Node 侧（前端）
```bash
node -v        # 建议 Node 18+（开发机为 22）
cd Quote    # 前端依赖、命令与构建产物统一在 Quote/ 下
npm ci
```

### Python 侧（后端）
```bash
cd Workbench
python3 -m venv .venv
# macOS/Linux： source .venv/bin/activate
# Windows：    .venv\Scripts\activate
cd Workbench/web
npm install
# 部署主机端的npm
pip install -r requirements.txt
cp .env.example .env     # 默认连 Workbench/data/app.db、照片目录 Workbench/uploads
```

> 代码直跑时后端数据在 `Workbench/data/app.db`；打成 exe 后在 `%APPDATA%\HHZ\app.db`（见 §4 数据迁移）。

---

## 2. 模式 A：本地用代码部署（直跑）

### A1. 网页版（报价页 + 工作台），一键
```bash
cd Quote
npm run dev
```
- 同时启动：`dev:server`（FastAPI，`127.0.0.1:8000`）与 `dev:web`（Vite，`http://localhost:5173`，自动开浏览器）；
- Vite 把 `/api`、`/uploads` 代理到后端，报价页即连本机后端；
- 工作台（设备/耗材/套餐/基本设置）由后端托管已构建的 `Workbench/web/dist/workbench.html`：浏览器开 `http://localhost:8000`，首次进入需先注册工作台账号；内置应急账号 `admin / admin123` 保留在数据库，但不在登录页展示；
- 工作台前端有改动时：`cd Workbench/web && npm run build` 后刷新 `http://localhost:8000` 即可。

### A2. Electron 桌面版（客户机壳），代码直跑
```bash
cd Quote
npm run dev:desktop:all     # 后端 + Vite + Electron 一起起，端口冲突自动退出
```
如需分离（例如后端已另起）：
```bash
npm run dev:server          # 终端 1：后端
npm run dev:desktop         # 终端 2：Electron 加载 Vite dev server（5173）
```

### A3. 自检清单
```bash
curl -s http://127.0.0.1:8000/api/health      # {"ok":true,"app":"hhz-data-service",...}
curl -s http://127.0.0.1:8000/api/sync | head  # 目录 + 设置同步负载
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5173/        # 200（报价页）
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5173/workbench.html  # 200
```
> 以上在 macOS 与 Windows 开发机上命令一致（Windows 下 venv 激活路径略有差异，见 §1）。

---

## 3. 模式 B：本地打包 exe → Windows 部署

### B1. 前端 exe（报价版 Electron）—— macOS / Windows 均可构建

```bash
# macOS（Apple Silicon / Intel 均可；首次会下载 Electron 与 NSIS/wine 工具，可复用仓库根目录 .electron-cache 缓存加速）
ELECTRON_BUILDER_CACHE=$PWD/../.electron-cache npx electron-builder --win --x64

# 或者最简单（等价：先 vite build 再 electron-builder）
npm run build:win

# Windows 原生：直接（同样在 Quote/ 下）
npm run build:win
```

产物：`Quote/release/超声医疗报价平台 Setup <版本>.exe`（NSIS 安装版）与 `…-win.zip`（绿色版）。

> macOS 上 electron-builder 打 NSIS 安装包需要 wine（工具自动下载到缓存）；仓库根目录 `.electron-cache/` 是本地缓存（已 gitignore），保留可避免重复下载。若 Electron 二进制下载慢，可用 `-c.electronDist=<本地缓存目录>` 指向已缓存的 `electron-v*.zip`。

### B2. 后端 exe（HHZDataService.exe，主设备数据服务）

```bash
node scripts/build-backend-exe.mjs
```
- **Windows 原生（推荐，已验证路径）**：脚本自动委托 `scripts\build-backend.bat`（前端构建 → 安装依赖 → PyInstaller → 复制到 `release\`，再自动调 `scripts\build-backend-installer.mjs` 生成 NSIS 安装版）。发布后端 exe 时请优先在任意 Windows 机器执行。
- **macOS / Linux（可选备选，Docker + Wine）**：PyInstaller 不支持跨平台，无法在 mac 上原生出 Windows exe，本机有 Docker 时可用容器等效构建：
  1. 需要 Docker Desktop 已启动（首次自动拉取 `batonogov/pyinstaller-windows`，约 1.5 GB）；
  2. 容器内为 Windows Python 3.13 + PyInstaller 6.x，自动 `pip install -r Workbench/requirements.txt` 并执行 `hhz-data-service.spec`；
  3. 产物复制为 `release/HHZDataService.exe`；
  4. Apple Silicon 走 amd64 模拟，首次构建较慢（数分钟～半小时属正常）；
  5. pip 慢时换国内源：`PYPI_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple node scripts/build-backend-exe.mjs`。
- **初始数据随包**：打包时会读取当前本地库 `Workbench/data/app.db` 及 `Workbench/uploads/` 中已有图片，一并内嵌进 `HHZDataService.exe`。在 Windows 主设备上**首次运行**（`%APPDATA%\HHZ\app.db` 不存在）时自动复制到数据目录；已运行过/已有数据的机器不会被覆盖。若未找到 `Workbench/data/app.db`，构建脚本会提示，产出的将是不带初始数据的空库包。

> **安装版（NSIS）与防火墙**：`release/HHZDataService Setup <版本>.exe` 安装时以管理员身份自动放行 Windows 防火墙 **TCP 8000 入站（仅专用网络）**，无需再手动关闭防火墙或执行 netsh 命令；卸载时自动移除该规则。绿色版 `HHZDataService.exe` 不含安装器放行，需手动执行 `scripts\allow-firewall.ps1` 或 netsh（见 §B2 下方说明）。安装器由 `scripts/backend-installer.nsi` + `scripts/build-backend-installer.mjs` 生成，本机需有 makensis（NSIS 编译器）：Windows 可 `winget install NSIS.NSIS`；macOS 可 `brew install nsis`；或直接复用仓库 `.electron-cache/nsis/` 与 electron-builder 系统缓存中已有的 NSIS（自动探测）。
>
> **网络受限时的兜底**：macOS/Linux 走 Docker 需要能拉取 `batonogov/pyinstaller-windows` 镜像（如本机 Docker 镜像源返回 403、ghcr 不可达，需先修复 Docker registry 配置或改用 Docker Hub 直连）。任何情况下，后端 exe 都可在任意 Windows 机器执行 `scripts\build-backend.bat` 原生构建，产物与 Docker 路线一致。

### B3. 全量出包（前端 exe + 后端 exe）

两系统拆分后已移除原 `npm run build:all` 一键脚本，前后端分别出包：

```bash
# 前端报价版 exe（Quote/release/）
cd Quote && npm run build:win
# 后端数据服务 exe + NSIS 安装版（根目录 release/）
node scripts/build-backend-exe.mjs
```
依次产出 `Quote/release/` 下的前端安装包，与根目录 `release/` 下的 `HHZDataService.exe` 及其 NSIS 安装版。发布前确认版本号一致（§5）。

---

## 4. 数据与目录（dev vs exe 形态差异）

| 项 | 代码直跑（dev） | exe（Windows 主设备） |
| --- | --- | --- |
| 数据库 | `Workbench/data/app.db`（`.env` 可改） | `%APPDATA%\HHZ\app.db`（`entry.py` 固定） |
| 产品图片 | `Workbench/uploads/products` | `%APPDATA%\HHZ\uploads` |
| 工作台静态页 | 指向仓库 `Workbench/web/dist/` | 内嵌 exe 解包目录 |
| 监听 | `127.0.0.1:8000`（dev:server） | `0.0.0.0:8000`（局域网可达，托盘管理） |

**首次部署带数据**：按 §B2 打包时已自动内嵌 `Workbench/data/app.db` 与 `Workbench/uploads/` 图片，新主设备首启会自动写入 `%APPDATA%\HHZ\`，无需再手工拷库；首启会自动建缺失表并播种默认设置，老数据不受影响。

如需升级**已经用过的旧主设备**（目标 `%APPDATA%\HHZ\app.db` 已存在），安装包不会覆盖旧库，应通过托盘「打开数据目录」手动替换或备份恢复。

---

## 5. 发版一致性检查（改版本号时）

- `Quote/package.json` 的 `version`（决定前端 exe 文件名与版本检查比对）；
- `Workbench/.env.example` 与 `.env` 的 `DEFAULT_LATEST_VERSION`（`app_versions` 表为空时的兜底）；
- `docs/USER-GUIDE.md` 等文档中的版本字样。

---

## 6. 部署到 Windows 现场

主从安装步骤、防火墙放行（TCP 8000）、开机自启、备份恢复见 `docs/USER-GUIDE.md`（装机指南）。
本手册只负责「如何从本仓库得到可分发的 exe」。

---

## 7. 相关文件速查

| 文件 | 作用 |
| --- | --- |
| `scripts/serve-backend.mjs` | 代码直跑：自动定位 `Workbench/.venv` 启动 FastAPI（`npm run dev:server`） |
| `scripts/dev.mjs` | 代码直跑：Vite dev server + Electron（`npm run dev:desktop`） |
| `scripts/build-backend-exe.mjs` | 打包：跨平台后端 exe 一键脚本（`node scripts/build-backend-exe.mjs`，结尾自动附带 NSIS 安装版） |
| `scripts/build-backend.bat` | 打包：Windows 原生后端 exe（含前端构建，末尾自动生成 NSIS 安装版） |
| `scripts/build-backend-installer.mjs` | 打包：把 `release/HHZDataService.exe` 包成 NSIS 安装版（定位 makensis + 版本号） |
| `scripts/backend-installer.nsi` | NSIS 规格：安装时自动放行防火墙 TCP 8000（专用网络），卸载时移除 |
| `scripts/allow-firewall.ps1` | 手工放行防火墙 TCP 8000（绿色版 exe 无安装器时使用） |
| `Workbench/hhz-data-service.spec` | PyInstaller 规格：内嵌 `Workbench/web/dist/workbench*` + 当前库 `data/app.db`/`uploads`，产物 `HHZDataService.exe` |
| `Workbench/app/entry.py` | exe 入口：`%APPDATA%\HHZ` 数据目录 + 首启自动导入随包初始数据 + 托盘 + `0.0.0.0:8000` |
| `Quote/electron/main.cjs` | 客户机壳：局域网发现主设备、图片/目录缓存、app-img 协议 |
| `Quote/release/` | 前端构建产物（gitignore，不入库）；后端产物在根目录 `release/` |
