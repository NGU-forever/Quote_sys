"""QuoteSys 数据服务 — Windows 托盘后台服务入口。

职责：
1. 确定数据目录 %APPDATA%\\QuoteSys（uploads + 数据库地址配置）；
2. 后台线程起 uvicorn 0.0.0.0:8000（局域网可达）；
3. 托盘菜单：打开工作台 / 打开数据目录 / 开机自启(开关) / 退出；
4. 首次运行自动用默认浏览器打开工作台（等待服务就绪后再打开）；
5. 首启且数据库中还没有业务表时，自动导入打包时内嵌的 seed/seed.sql。

数据库：仅 PostgreSQL，连接串按「环境变量 DATABASE_URL → 数据目录
database_url.txt → 内置默认值（本机 5432）」的顺序解析。

打包（在 Windows 上）：
    先构建工作台前端：`cd web && npm run build`（产出 web/dist/workbench.html + web/dist/assets）
    再打包：     `cd Workbench && pyinstaller quote-service.spec --clean --noconfirm`
"""
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

HOST = "0.0.0.0"
PORT = 8000
AUTOSTART_NAME = "QuoteService"
# 数据库连接串配置文件（放在数据目录，便于现场修改而不必重新打包）
DB_URL_FILE = "database_url.txt"
DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://quotesys_user:quotesys_secret@127.0.0.1:5432/quotesys_db"
)


def resource_dir() -> Path:
    """PyInstaller onefile 解包目录；开发下为 backend 目录。"""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) if base else Path(__file__).resolve().parent


def data_dir() -> Path:
    root = os.environ.get("APPDATA") or str(Path.home())
    d = Path(root) / "QuoteSys"
    d.mkdir(parents=True, exist_ok=True)
    return d


def configured_database_url() -> str:
    """解析 PostgreSQL 连接串：环境变量 → 数据目录配置 → 内置默认值。"""
    env_value = (os.environ.get("DATABASE_URL") or "").strip()
    if env_value:
        return env_value

    config_file = data_dir() / DB_URL_FILE
    if config_file.exists():
        try:
            file_value = config_file.read_text(encoding="utf-8").strip()
        except OSError:
            file_value = ""
        if file_value:
            return file_value

    return DEFAULT_DATABASE_URL


def provision_initial_data() -> None:
    """首次启动且数据库尚无业务表时，导入打包时内嵌的 seed/seed.sql。

    没有内嵌 dump（或数据库已经建过表）时直接跳过：表结构与管理员账号
    由应用启动时的 create_all + 播种逻辑负责。
    """
    dump = resource_dir() / "seed" / "seed.sql"
    if not dump.exists():
        return

    try:
        import psycopg
        from sqlalchemy.engine import make_url
    except ImportError:  # pragma: no cover - 打包环境必然带有依赖
        return

    conninfo = (
        make_url(configured_database_url())
        .set(drivername="postgresql")
        .render_as_string(hide_password=False)
    )
    try:
        with psycopg.connect(conninfo, autocommit=True, connect_timeout=10) as conn:
            if conn.execute("SELECT to_regclass('public.users')").fetchone()[0] is not None:
                return
            conn.execute(dump.read_text(encoding="utf-8"))
    except Exception as exc:  # 初始数据导入失败不应阻止服务启动
        print(f"[entry] 初始数据导入失败（已跳过）：{exc}")


def ensure_workbench_dir() -> Path:
    """优先使用打进 exe 的 workbench 静态页；开发下回退仓库 Workbench/web/dist。"""
    bundled = resource_dir() / "workbench"
    if (bundled / "workbench.html").exists():
        return bundled
    return Path(__file__).resolve().parent / "web" / "dist"


def apply_env() -> None:
    """在导入 app.main 之前写入运行环境（数据库 / 上传目录 / 工作台静态目录）。"""
    d = data_dir()
    os.environ["DATABASE_URL"] = configured_database_url()
    os.environ["UPLOAD_DIR"] = str(d / "uploads")
    os.environ["WORKBENCH_DIR"] = str(ensure_workbench_dir())
    assets_dir = d / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("ASSETS_DIR", str(assets_dir))


def fix_stdio() -> None:
    """runw（无控制台）模式下 sys.stdout/stderr 为 None，uvicorn 等库会因
    None.isatty() 崩溃。重定向到数据目录日志文件，既修复又保留排障日志。"""
    if sys.stdout is None or sys.stderr is None:
        logf = open(data_dir() / "server.log", "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = logf
        if sys.stderr is None:
            sys.stderr = logf


def start_server() -> None:
    try:
        import uvicorn

        from app.main import app

        uvicorn.run(app, host=HOST, port=PORT, log_level="info")
    except BaseException:
        # runw（无控制台）模式下 stderr 不可见，落盘以便诊断
        import traceback

        log = data_dir() / "server-error.log"
        try:
            with open(log, "a", encoding="utf-8") as f:
                f.write(traceback.format_exc())
                f.write("\n")
        except OSError:
            pass


def wait_for_server(host: str, port: int, timeout: float = 20.0) -> bool:
    """轮询端口直到服务就绪（首次启动需解包 + 建库，避免浏览器先于服务打开）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def is_autostart_enabled() -> bool:
    import winreg

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
        )
        value, _ = winreg.QueryValueEx(key, AUTOSTART_NAME)
        return bool(value)
    except OSError:
        return False


def set_autostart(enable: bool) -> None:
    import winreg

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE,
    )
    if enable:
        winreg.SetValueEx(key, AUTOSTART_NAME, 0, winreg.REG_SZ, f'"{sys.executable}"')
    else:
        try:
            winreg.DeleteValue(key, AUTOSTART_NAME)
        except OSError:
            pass


def acquire_single_instance_lock():
    """Windows 命名互斥锁：防止多开导致 8000 端口 WinError 10048 冲突。
    若已有实例在运行，直接唤起浏览器打开工作台，当前多余进程退出。"""
    if sys.platform != "win32":
        return None
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        mutex_name = "Global\\QuoteService_SingleInstance_Mutex"
        mutex = kernel32.CreateMutexW(None, False, mutex_name)
        last_error = kernel32.GetLastError()
        ERROR_ALREADY_EXISTS = 183
        if last_error == ERROR_ALREADY_EXISTS:
            try:
                webbrowser.open(f"http://127.0.0.1:{PORT}")
            except Exception:
                pass
            sys.exit(0)
        return mutex
    except Exception:
        return None


def main() -> None:
    _mutex = acquire_single_instance_lock()
    apply_env()
    provision_initial_data()
    fix_stdio()

    marker = data_dir() / ".first-run-done"
    first_run = not marker.exists()

    threading.Thread(target=start_server, daemon=True).start()

    import pystray
    from PIL import Image, ImageDraw

    def icon_image():
        img = Image.new("RGB", (64, 64), (30, 136, 229))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([6, 6, 58, 58], radius=14, fill=(13, 71, 161))
        draw.text((22, 20), "Q", fill=(255, 255, 255))
        return img

    menu = pystray.Menu(
        pystray.MenuItem(
            "打开工作台",
            lambda icon, item: webbrowser.open(f"http://127.0.0.1:{PORT}"),
            default=True,
        ),
        pystray.MenuItem("打开数据目录", lambda icon, item: os.startfile(str(data_dir()))),
        pystray.MenuItem(
            "开机自启",
            lambda icon, item: set_autostart(not is_autostart_enabled()),
            checked=lambda item: is_autostart_enabled(),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出", lambda icon, item: icon.stop()),
    )
    icon = pystray.Icon("quote-service", icon_image(), "QuoteSys 数据服务", menu=menu)

    if first_run:
        # 等待服务就绪再打开浏览器，避免出现"无法访问此网站"（首次解包/建库较慢）
        wait_for_server("127.0.0.1", PORT)
        try:
            webbrowser.open(f"http://127.0.0.1:{PORT}")
        except Exception:
            pass
        try:
            marker.touch()
        except OSError:
            pass

    icon.run()


if __name__ == "__main__":
    main()
