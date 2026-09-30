"""assets 清单：扫描根目录与一级子目录、计算 sha256、标注支持状态。"""
import hashlib
from datetime import datetime
from pathlib import Path

from app.agent.readers.common import file_kind, is_ignored_file
from app.core.config import settings


def _scan_dir(current_dir: Path, rel_prefix: str, files: list[dict], current_depth: int, max_depth: int = 3) -> None:
    if current_depth > max_depth:
        return
    try:
        entries = sorted(current_dir.iterdir(), key=lambda p: p.name)
    except (OSError, PermissionError):
        return

    for child in entries:
        if is_ignored_file(child.name):
            continue
        if child.is_symlink():
            # 外部软链接跳过，避免路径穿越
            try:
                resolved = child.resolve()
                resolved.relative_to(settings.assets_root.resolve())
            except Exception:
                continue

        rel = (Path(rel_prefix) / child.name).as_posix() if rel_prefix else child.name
        if child.is_file():
            try:
                stat = child.stat()
                digest = hashlib.sha256()
                with child.open("rb") as fh:
                    for chunk in iter(lambda: fh.read(1024 * 256), b""):
                        digest.update(chunk)
                ext = child.suffix.lower()
                kind = file_kind(ext)
                files.append(
                    {
                        "path": rel,
                        "name": child.name,
                        "type": kind,
                        "supported": kind != "unsupported",
                        "size": stat.st_size,
                        "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        "sha256": digest.hexdigest(),
                    }
                )
            except (OSError, PermissionError):
                continue
        elif child.is_dir():
            _scan_dir(child, rel, files, current_depth + 1, max_depth)


def build_manifest(root: Path | None = None) -> dict:
    """返回 {files, supported_count, unsupported_count, scanned_at}。"""
    root = root or settings.assets_root
    if not root.exists():
        return {
            "files": [],
            "supported_count": 0,
            "unsupported_count": 0,
            "scanned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    files: list[dict] = []
    _scan_dir(root, "", files, current_depth=1, max_depth=3)
    files.sort(key=lambda item: item["path"])
    return {
        "files": files,
        "supported_count": sum(1 for f in files if f["supported"]),
        "unsupported_count": sum(1 for f in files if not f["supported"]),
        "scanned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "root_path": str(root.resolve()),
    }


def supported_files(manifest: dict) -> list[dict]:
    return [f for f in manifest["files"] if f["supported"]]
