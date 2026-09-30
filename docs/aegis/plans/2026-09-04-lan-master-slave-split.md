# 主从局域网拆分 — 实现计划

Goal: 把当前单应用拆成「主设备 `HHZ数据服务.exe`（托盘后台服务 + 工作台网页）+ 客户机 `HHZ报价.exe`（仅报价落地页）」，局域网单向同步目录/公司/报价参数/图片，离线走本地缓存。

Architecture: 见规格 `docs/aegis/specs/2026-09-04-lan-master-slave-split-design.md` §3。

Tech Stack: FastAPI + SQLAlchemy(SQLite) + pystray/PyInstaller（后端）；Vue3 + Vite + Pinia + Electron（前端）。

Baseline/Authority Refs:
- 规格：`docs/aegis/specs/2026-09-04-lan-master-slave-split-design.md`
- 基线：`docs/aegis/baseline/2026-09-04-initial-baseline.md`
- `backend/README.md`（后端接口契约）、`package.json`（打包脚本）

Compatibility Boundary（不得破坏）:
- 现有接口 `/api/catalog`、`/api/products*`、`/api/packages*`、`/api/auth*`、`/api/health`、`/uploads` 保留。
- 现有表 users/products/packages/device_bindings 不改，仅新增 `app_settings`。
- `npm run dev` 与旧前端（单应用网页版）保持可用。

TDD Route:
- Mode: off
- Decision: skipped
- Strict authority: not applicable
- Test posture: post-change regression（curl + vite build + 手动点测）
- Verification: 每阶段末尾的精确命令

---

## 阶段 P0 — 后端接口（纯后端，可独立验证）

### 任务 P0.1 新增 `app_settings` 模型
- Files: 新建 `backend/app/models/app_setting.py`；修改 `backend/app/models/__init__.py`
- Why: 公司信息 + 报价参数需要持久化，且只增表不改旧表。
- 完整代码 `app_setting.py`:
```python
"""新增 app_settings 表（key-value，存公司信息与报价参数，只增表不改旧表）。"""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, now_str


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)  # JSON 字符串
    updated_at: Mapped[str] = mapped_column(String, nullable=False, default=now_str, onupdate=now_str)
```
- `__init__.py` 追加：
```python
from app.models.app_setting import AppSetting
__all__ = ["User", "Product", "Package", "DeviceBinding", "AppVersion", "AppSetting"]
```
- Verification: `cd backend && .venv/bin/python -c "from app.models import AppSetting; print(AppSetting.__tablename__)"` 输出 `app_settings`。

### 任务 P0.2 设置默认值 + 读写服务
- Files: 新建 `backend/app/services/settings_service.py`；修改 `backend/app/db/seed.py`
- Why: 提供 company/pricing 的默认值与 upsert，并构建 `/api/sync` 负载。
- 完整代码 `settings_service.py`:
```python
"""app_settings 读取/写入 + 同步负载构建。"""
import hashlib
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting
from app.services.catalog_service import build_catalog

DEFAULT_COMPANY = {
    "name": "超声医疗报价平台",
    "phone": "400-800-1026",
    "email": "quote@ultrasound-med.cn",
    "address": "上海市徐汇区医疗科技园",
}

DEFAULT_PRICING = {
    "devicePrice": 3200,
    "bagsPerBox": 600,
    "giftRatio": 2,
    "plan2UnitPrice": 5.5,
    "plan2MinBoxes": 2,
    "quoteValidityDays": 30,
    "quotePrefix": "Q",
    "plan1Tiers": [
        {"minBoxes": 1, "price": 3.5, "label": "1箱起订"},
        {"minBoxes": 5, "price": 3.0, "label": "5箱起订"},
        {"minBoxes": 10, "price": 2.5, "label": "10箱起订"},
    ],
}


def _read_map(db: Session) -> dict[str, str]:
    return {s.key: s.value for s in db.scalars(select(AppSetting)).all()}


def get_settings_dict(db: Session) -> dict:
    rows = _read_map(db)
    company = json.loads(rows["company"]) if "company" in rows else DEFAULT_COMPANY
    pricing = json.loads(rows["pricing"]) if "pricing" in rows else DEFAULT_PRICING
    return {"company": company, "pricing": pricing}


def put_settings(db: Session, company: dict | None, pricing: dict | None) -> dict:
    rows = _read_map(db)
    if company is not None:
        db.merge(AppSetting(key="company", value=json.dumps(company, ensure_ascii=False)))
    if pricing is not None:
        db.merge(AppSetting(key="pricing", value=json.dumps(pricing, ensure_ascii=False)))
    db.commit()
    return get_settings_dict(db)


def build_sync_payload(db: Session) -> dict:
    payload = {"catalog": build_catalog(db), "settings": get_settings_dict(db)}
    rev = hashlib.sha1(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {**payload, "rev": rev, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
```
- `seed.py` 追加函数（在 `seed_app_versions` 之后）：
```python
import json
from app.models.app_setting import AppSetting
from app.services.settings_service import DEFAULT_COMPANY, DEFAULT_PRICING


def seed_app_settings(db: Session) -> None:
    """app_settings 缺失时写入默认值（幂等）。"""
    existing = {s.key for s in db.scalars(select(AppSetting)).all()}
    if "company" not in existing:
        db.add(AppSetting(key="company", value=json.dumps(DEFAULT_COMPANY, ensure_ascii=False)))
    if "pricing" not in existing:
        db.add(AppSetting(key="pricing", value=json.dumps(DEFAULT_PRICING, ensure_ascii=False)))
    db.commit()
```
- `main.py` lifespan 中，在 `seed_app_versions(db)` 后加 `seed_app_settings(db)`，并更新 import。
- Verification: `cd backend && .venv/bin/python -c "from app.services.settings_service import get_settings_dict, DEFAULT_COMPANY; print(DEFAULT_COMPANY['name'])"`。

### 任务 P0.3 新增 `/api/sync`、`/api/settings` 接口
- Files: 新建 `backend/app/compat/sync.py`；修改 `backend/app/compat/router.py`
- Why: 客户机同步走 `/api/sync`（公开），管理走 `/api/settings`（登录）。
- 完整代码 `sync.py`:
```python
"""同步接口：/api/sync（公开，客户机单向拉取）+ /api/settings（登录读写）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_user
from app.models.user import User
from app.services.settings_service import build_sync_payload, get_settings_dict, put_settings

router = APIRouter()


@router.get("/sync")
def sync(db: Session = Depends(get_db)):
    return {"data": build_sync_payload(db)}


@router.get("/settings")
def read_settings(db: Session = Depends(get_db), _: User = Depends(require_user)):
    return {"data": get_settings_dict(db)}


@router.put("/settings")
def write_settings(payload: dict, db: Session = Depends(get_db), _: User = Depends(require_user)):
    company = payload.get("company") if isinstance(payload.get("company"), dict) else None
    pricing = payload.get("pricing") if isinstance(payload.get("pricing"), dict) else None
    if company is None and pricing is None:
        raise HTTPException(status_code=400, detail="company 或 pricing 至少提供一个")
    return {"data": put_settings(db, company, pricing)}
```
- `router.py` 追加：
```python
from app.compat import sync
compat_router.include_router(sync.router, tags=["legacy-sync"])
```
- Verification:
```bash
cd backend && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
curl -s http://127.0.0.1:8000/api/sync | python3 -m json.tool | head -40
curl -s -X POST http://127.0.0.1:8000/api/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}'
```

### 任务 P0.4 `/api/health` 加 app 标识
- Files: 修改 `backend/app/compat/health.py`
- Why: 自动发现据此识别主设备，避免误判局域网其他 HTTP 服务。
- 改动：返回体加 `"app": "hhz-data-service"`（保留 `ok`、`time`）。
- Verification: `curl -s http://127.0.0.1:8000/api/health` 含 `"app":"hhz-data-service"`。

**P0 收尾提交**：`feat(sync): 新增 app_settings 表 + /api/sync、/api/settings 接口 + health 标识`

---

## 阶段 P1 — 工作台「基本设置」页 + 多入口构建

### 任务 P1.1 Vite 多入口（index + workbench）
- Files: 修改 `vite.config.js`；新建 `workbench.html`、`src/workbench-main.js`、`src/router/workbench.js`、`src/workbench/WorkbenchApp.vue`
- Why: 一套代码出两份构建，工作台静态页由后端托管。
- `vite.config.js` 增加：
```js
import { resolve } from 'node:path'
// build.rollupOptions.input:
build: {
  rollupOptions: {
    input: {
      index: resolve(__dirname, 'index.html'),
      workbench: resolve(__dirname, 'workbench.html')
    }
  }
}
```
- `workbench.html`：复制 `index.html`，`<script type="module" src="/src/workbench-main.js">`。
- `src/router/workbench.js`：hash history，只含 `/workbench/login` 与 `/workbench/*`（沿用现有 workbench 路由表，去掉 landing）。
- `src/workbench-main.js`：`createApp(WorkbenchApp).use(createPinia()).use(workbenchRouter).mount('#app')`。
- `src/workbench/WorkbenchApp.vue`：仅 `<RouterView />` + toast 栈（不触发目录水合/图片同步）。
- Verification: `npm run build` 产出 `dist/index.html` 与 `dist/workbench.html`。

### 任务 P1.2 路由历史切换（workbench 用 hash）
- Files: 修改 `src/router/index.js`（保留 landing，抽出 workbench 路由到 `workbench.js`）
- Why: workbench 托管在 FastAPI 下用 hash history 免 fallback 重写；报价版 Electron 继续 memory history。
- 注意：`src/router/index.js` 里的 `beforeEach` 登录守卫要一并迁到 `workbench.js`。

### 任务 P1.3 基本设置页 + store
- Files: 新建 `src/views/workbench/SettingsManager.vue`；修改 `src/router/workbench.js`（加 `/workbench/settings`）、`src/api/client.js`（加 `getSettings`/`updateSettings`）
- Why: 管理员在浏览器里改公司信息 + 报价参数，存后端 `app_settings`。
- 表单字段：company（name/phone/email/address）、pricing（devicePrice/bagsPerBox/giftRatio/plan2UnitPrice/plan2MinBoxes/quoteValidityDays/quotePrefix + plan1Tiers 列表编辑）。
- `client.js` 追加：
```js
getSettings: () => request('/settings'),
updateSettings: (payload) => request('/settings', { method: 'PUT', body: JSON.stringify(payload) })
```
- 页面对接 GET/PUT `/api/settings`（已有 token 机制）。
- Verification: `npm run build`；浏览器进工作台 `/workbench/settings` 保存后 `curl -s http://127.0.0.1:8000/api/sync` 能看到改动。

### 任务 P1.4 后端托管工作台静态页
- Files: 修改 `backend/app/main.py`（挂 `StaticFiles` 到 `/`，`html=True`；`/api`、`/uploads` 路由在前不受影响）
- Why: 主设备浏览器开 `http://127.0.0.1:8000` 进工作台。
- 说明：PyInstaller 打包时把 `dist/workbench*` 产物作为 data 打进 exe，运行时从解包目录 serve；dev 下可先指向 `../dist`。
- Verification: 浏览器开 `http://127.0.0.1:8000` 见工作台登录。

**P1 收尾提交**：`feat(workbench): 基本设置页 + Vite 多入口 + 后端托管工作台静态页`

---

## 阶段 P2 — 后端打包成 Windows 托盘 exe

> 注意：本阶段产物需在 Windows 上构建/验证（PyInstaller 需目标平台；当前开发机为 macOS）。

### 任务 P2.1 服务入口脚本（0.0.0.0 + 托盘 + 首次开浏览器）
- Files: 新建 `backend/app/entry.py`（或 `backend/run_server.py`）；依赖加入 `pystray`、`Pillow`
- Why: exe 常驻 8000 且局域网可达，托盘菜单管理。
- 逻辑：
  1. 确定数据目录 `%APPDATA%\HHZ`（不存在则创建），`DATABASE_URL` / `UPLOAD_DIR` 指向该目录。
  2. 后台线程起 uvicorn `0.0.0.0:8000`（import `app.main:app`）。
  3. pystray 托盘图标；菜单：打开工作台(webbrowser→127.0.0.1:8000) / 打开数据目录(os.startfile) / 开机自启(开关，写 HKCU Run) / 退出。
  4. 首次运行（数据目录无标记文件）自动 webbrowser 打开工作台，并写标记。
- Verification（Windows）：双击 exe → 托盘出现 + 浏览器开工作台 + 局域网另一台机 `curl http://<IP>:8000/api/health` 成功。

### 任务 P2.2 防火墙放行
- Files: 新建 `scripts/allow-firewall.ps1`（或安装器内做）
- Why: 否则局域网客户机连不上 8000。
- 内容：`New-NetFirewallRule -DisplayName "HHZ Data Service" -Direction Inbound -Protocol TCP -LocalPort 8000 -Profile Private -Action Allow`
- Verification（Windows）：执行后从另一台机访问 `/api/health` 成功。

### 任务 P2.3 PyInstaller 打包 + 安装器
- Files: 新建 `backend/hhz-data-service.spec`；可选 NSIS/Inno Setup 脚本
- Why: 产出可分发的 `HHZ数据服务.exe`。
- spec 要点：onefile，data 含 `dist/workbench*`、图标；hiddenimports 含 uvicorn 依赖；入口 `entry.py`。
- 绿色版：先出 zip 手动跑；安装器放后续。
- Verification（Windows）：`pyinstaller hhz-data-service.spec` 产出可运行 exe。

**P2 收尾提交**：`feat(packaging): 后端托盘服务入口 + PyInstaller 打包 + 防火墙放行`

---

## 阶段 P3 — 前端拆分：报价 exe 去工作台 + 自动发现 + 目录持久化

### 任务 P3.1 报价版路由只留落地页
- Files: 修改 `src/router/index.js`（删除 `/workbench/*` 与 `/workbench/login`）
- Why: 前端 exe 无登录/工作台入口。
- 注意：`auth` store、`LoginView`、各 `Manager` 仍留代码库供 workbench 版，不进报价版构建（多入口后自然树摇）。
- Verification: `npm run build` 后报价版 `dist/index.html` 无 `/workbench` 路由；`npm run dev` 落地页正常。

### 任务 P3.2 自动发现（Electron 主进程）
- Files: 修改 `electron/main.cjs`；修改 `electron/preload.cjs`（暴露 `discoverHost`）
- Why: 客户机开机自动找到主设备。
- 逻辑（main 进程）：
  - 取本机 IPv4（`os.networkInterfaces()`），推导 `x.y.z.0/24`。
  - 并发（~32 路）`net.fetch` 探测 `http://x.y.z.{1..254}:8000/api/health`，超时 ~120ms。
  - 校验响应含 `"app":"hhz-data-service"`，返回第一个命中地址。
- `preload.cjs` 暴露：`discoverHost: () => ipcRenderer.invoke('hhz:discover-host')`。
- Verification: 两台机（或本机 + 局域网一台）实测发现。

### 任务 P3.3 目录本地持久化
- Files: 新建 `src/utils/catalogCache.js`；修改 `src/stores/catalog.js`、`src/stores/settings.js`
- Why: 离线读「上次同步真实数据」，首次才用内置演示。
- `catalogCache.js`：读/写 `userData` 下 `catalog-cache.json`（Electron 经 IPC 读写；Web 下用 localStorage）。存 `{ rev, updated_at, catalog, settings }`。
- `catalog.js::hydrateFromRemote` 改为拉 `/api/sync`（而非 `/api/catalog`），成功写缓存；失败读缓存；无缓存用内置 + `source='static'`。
- `settings.js` 初始值改为「读缓存 settings → 回退内置 PRICING/company」。
- Verification: 主设备在线同步 → 离线重启 → 显示缓存数据 + 提示。

### 任务 P3.4 「连接主设备」设置页
- Files: 新建 `src/views/SettingsDrawer.vue`（或顶栏齿轮面板）；修改 `src/components/landing/SiteHeader.vue`、`src/utils/backendConfig.js`
- Why: 手动 IP 兜底 + 显示同步状态/来源。
- 内容：自动发现按钮/结果、手动地址输入 + 测试连接 + 保存、最后同步时间、数据来源标识。
- Verification: 手动填 IP 保存后重启，`getApiBase()` 生效。

**P3 收尾提交**：`feat(client): 报价版去工作台 + 自动发现 + 目录持久化 + 连接主设备设置`

---

## 阶段 P4 — 联调 + 文档

### 任务 P4.1 双机联调清单
- 覆盖规格 §6 验收标准全部条目（主设备 exe 自启/局域网可达/基本设置；客户机发现/离线兜底/改数据同步）。
- 产出 `docs/USER-GUIDE.md`（管理员装机 + 客户机连接 + 备份说明）。

### 任务 P4.2 版本号 + 发布脚本
- Files: 修改 `package.json` version、`backend/.env.example` 的 `DEFAULT_LATEST_VERSION`
- Why: 版本检查兜底与实际发布版本一致。

**P4 收尾提交**：`docs(userguide): 双机联调清单 + 使用文档 + 版本号`

---

## 风险 / 回滚 / 退休
- 回滚：P0/P1/P3 均为增量，任一阶段可 `git revert`；后端 exe 只是打包形态，原 `npm run dev:server` / Docker 保留。
- 退休：无旧接口删除；`hydrateFromRemote` 由 `/api/catalog` 切到 `/api/sync`，旧 `/api/catalog` 保留供网页版。

## ADR / 基线同步信号
- 新增契约 `/api/sync`（catalog/settings/rev/updated_at）与 `/api/settings`。
- 新增数据源边界：客户机本地缓存 = 只读离线兜底。
- 新增运行时边界：后端绑定 `0.0.0.0:8000`。
- 实现完成后建议补 ADR 记录上述三处边界。
