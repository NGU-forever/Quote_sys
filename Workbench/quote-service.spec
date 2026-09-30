# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec：把 FastAPI 后端 + 工作台静态页打成单个 Windows exe（托盘后台服务）。
#
# 用法（在 Windows 上）：
#   1. 构建工作台前端：cd web && npm run build   （产出 Workbench/web/dist/workbench.html + assets）
#   2. 打包：          cd Workbench && pyinstaller quote-service.spec --clean --noconfirm
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

block_cipher = None

backend_dir = Path(SPECPATH)

workbench_build = backend_dir / "web" / "dist"
workbench_dest = "workbench"  # 打进 exe 内的目录名（entry.py 的 resource_dir()/workbench）

datas = []

if (workbench_build / "workbench.html").exists():
    datas.append((str(workbench_build / "workbench.html"), workbench_dest))
    if (workbench_build / "assets").exists():
        datas.append((str(workbench_build / "assets"), os.path.join(workbench_dest, "assets")))

# 可选初始数据：把 Workbench/data/seed.sql 与 uploads 图片打进 exe。
# QuoteService 首次启动且数据库中还没有业务表时导入 seed.sql（entry.py 负责），
# 已有数据的库不会被覆盖。
seed_sql = backend_dir / "data" / "seed.sql"
seed_uploads = backend_dir / "uploads"
if seed_sql.exists():
    datas.append((str(seed_sql), "seed"))
    print("[spec] 初始数据 seed.sql 已打入 exe（源 Workbench/data/seed.sql 不变）")
else:
    print("[spec] 未找到 Workbench/data/seed.sql，本次打包不含初始数据")
if seed_uploads.exists():
    for p in seed_uploads.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(seed_uploads)
        dest = "seed/uploads"
        if rel.parent != Path("."):
            dest = str(Path(dest) / rel.parent)
        datas.append((str(p), dest))
    if datas and any("seed/uploads" in d[1] for d in datas):
        print("[spec] uploads 图片已打入作为初始数据")

# LangGraph 动态加载 checkpoint 实现：显式收集子模块与包元数据，
# PyInstaller 仅靠静态导入无法推断 PostgresSaver 的迁移脚本。
datas += copy_metadata("langgraph-checkpoint-postgres")
datas += copy_metadata("psycopg")
langgraph_hiddenimports = collect_submodules("langgraph.checkpoint")
websockets_hiddenimports = collect_submodules("websockets")

a = Analysis(
    ["entry.py"],
    pathex=[str(backend_dir)],
    datas=datas,
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        # Data generation agent (readers / LLM client)
        "openpyxl",
        "docx",
        "lxml",
        "httpx",
        "psycopg",
        "psycopg_pool",
        *websockets_hiddenimports,
        *langgraph_hiddenimports,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 排除 uvicorn[standard] 的可选 C 加速/热重载依赖，避免打包体积与导入问题
    excludes=["uvloop", "httptools", "watchfiles"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="QuoteService",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 托盘程序，无控制台窗口
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
