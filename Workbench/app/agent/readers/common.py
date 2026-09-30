"""assets 沙箱与文件类型白名单。"""
from pathlib import Path

from app.core.config import settings

# 一期可读取扩展名（其余文件进入不支持清单，不阻塞任务）
SUPPORTED_EXTS = {".xlsx", ".docx", ".csv", ".md", ".txt"}
IGNORE_PREFIXES = ("~$", ".")


def is_ignored_file(name: str) -> bool:
    """过滤 Office 临时锁定文件与隐藏文件。"""
    return any(name.startswith(p) for p in IGNORE_PREFIXES)


def file_kind(ext: str) -> str:
    """返回 excel / word / text / unsupported。"""
    ext = ext.lower()
    if ext == ".xlsx":
        return "excel"
    if ext == ".docx":
        return "word"
    if ext in {".csv", ".md", ".txt"}:
        return "text"
    return "unsupported"


def safe_file_path(rel_path: str | Path) -> Path:
    """把相对 assets 的路径解析为真实文件，拒绝绝对路径与 ../ 越界。"""
    raw = Path(str(rel_path or "").strip())
    if not raw.as_posix() or raw.is_absolute() or ".." in raw.parts:
        raise ValueError("非法文件路径，只允许读取 assets 目录内的相对路径")
    root = settings.assets_root
    target = (root / raw).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("文件超出 assets 目录边界") from exc
    if not target.is_file():
        raise FileNotFoundError(f"assets 中不存在文件：{raw.as_posix()}")
    return target
