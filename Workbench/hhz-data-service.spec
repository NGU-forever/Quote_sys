# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec：把 FastAPI 后端 + 工作台静态页打成单个 Windows exe（托盘后台服务）。
#
# 用法（在 Windows 上）：
#   1. 构建工作台前端：cd web && npm run build   （产出 Workbench/web/dist/workbench.html + assets）
#   2. 打包：          cd Workbench && pyinstaller hhz-data-service.spec --clean --noconfirm
import atexit
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules, copy_metadata

block_cipher = None

backend_dir = Path(SPECPATH)

workbench_build = backend_dir / "web" / "dist"
workbench_dest = "workbench"  # 打进 exe 内的目录名（entry.py 的 resource_dir()/workbench）

datas = []
_seed_tmp = None


def sanitize_seed_db(source: Path) -> Path:
    """复制并清理种子库：不把 AI API Key / Agent 运行历史打进 exe。"""
    global _seed_tmp
    _seed_tmp = Path(tempfile.mkdtemp(prefix="hhz-seed-"))
    target = _seed_tmp / source.name
    shutil.copy2(source, target)
    con = sqlite3.connect(str(target))
    for statement in (
        "DELETE FROM app_settings WHERE key = 'agent_ai';",
        "DELETE FROM import_run_events;",
        "DELETE FROM import_runs;",
    ):
        try:
            con.execute(statement)
        except sqlite3.OperationalError:
            # 旧种子库尚未建对应表时无需清理
            pass
    con.commit()
    con.close()
    print(f"[spec] 种子库已消毒（清除 agent_ai / Agent 运行记录）：{target}")
    return target


def cleanup_seed_tmp() -> None:
    if _seed_tmp is not None:
        shutil.rmtree(_seed_tmp, ignore_errors=True)


atexit.register(cleanup_seed_tmp)

if (workbench_build / "workbench.html").exists():
    datas.append((str(workbench_build / "workbench.html"), workbench_dest))
    if (workbench_build / "assets").exists():
        datas.append((str(workbench_build / "assets"), os.path.join(workbench_dest, "assets")))

# 可选的初始数据：把当前本地库（Workbench/data/app.db）和 uploads 里的图片
# 一并打进 exe。HHZDataService 首次启动且 %APPDATA%\HHZ\app.db 不存在时复制，
# 已有数据不会被覆盖。
seed_db = backend_dir / "data" / "app.db"
seed_uploads = backend_dir / "uploads"
if seed_db.exists():
    datas.append((str(sanitize_seed_db(seed_db)), "seed"))
    print("[spec] 初始数据库已消毒后打入 exe（源 Workbench/data/app.db 不变）")
else:
    print("[spec] 未找到 Workbench/data/app.db，本次打包不含初始数据库")
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

# LangGraph loads checkpoint implementations dynamically and sqlite-vec ships
# a native extension that PyInstaller cannot infer from static imports alone.
binaries = collect_dynamic_libs("sqlite_vec")
datas += copy_metadata("langgraph-checkpoint-sqlite")
langgraph_hiddenimports = collect_submodules("langgraph.checkpoint")
websockets_hiddenimports = collect_submodules("websockets")

a = Analysis(
    ["entry.py"],
    pathex=[str(backend_dir)],
    binaries=binaries,
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
        "aiosqlite",
        "sqlite_vec",
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
    name="HHZDataService",
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
    icon=None,  # 可选：icons/hhz.ico
)
