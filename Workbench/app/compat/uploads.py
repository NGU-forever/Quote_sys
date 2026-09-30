"""兼容层：上传目录图片清单（供前端启动时同步图片到本地缓存）。

后端可能部署在远程服务器，管理员通过文件管理器/客户端 App 直接往
upload 目录更新图片（不经过工作台接口）。前端据此清单把图片拉取并
缓存到本机，实现「前端开启时同步后端上传的图片、图片保存在前端本地」。

与 /uploads 静态访问一致，本接口公开（无需登录）。
"""
from pathlib import Path

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/uploads")

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


@router.get("/manifest", summary="上传目录图片清单（相对路径/大小/修改时间）")
def upload_manifest():
    """递归枚举 uploads 目录下的所有图片文件。

    返回项：
    - path:  相对 uploads 根的路径（如 products/p1693123456789.jpg）
    - size:  字节数
    - mtime: 最后修改时间（epoch 秒，供前端判断是否重新下载）
    """
    root = Path(settings.upload_dir)
    files = []
    if root.exists():
        for p in root.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in ALLOWED_EXT:
                continue
            stat = p.stat()
            files.append(
                {
                    "path": p.relative_to(root).as_posix(),
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                }
            )
    files.sort(key=lambda f: f["path"])
    return {"data": files, "total": len(files)}
