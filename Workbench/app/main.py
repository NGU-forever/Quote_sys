"""FastAPI 应用入口。

启动时：
1. create_all 仅创建缺失的表（不修改现有 users/products/packages/device_bindings）；
2. 播种 app_settings 默认值；
3. 创建上传目录。

路由：
- /api/*  工作台兼容接口（沿用旧工作台后端接口契约，前端唯一调用入口）
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.agent import router as agent_router
from app.api.designer import router as designer_router
from app.compat.router import compat_router
from app.core.config import settings
from app.core.handlers import register_exception_handlers
from app.db.base import Base, SessionLocal, engine
from app.db.seed import seed_app_settings, seed_reserved_admin
from app.models import *  # noqa: F401,F403  # 注册所有模型到 Base.metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 仅创建缺失的表（checkfirst=True），不动已有表结构
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_reserved_admin(db)
        seed_app_settings(db)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(compat_router)
app.include_router(agent_router, prefix="/api", tags=["agent"])
app.include_router(designer_router)

# 产品照片静态访问（公开）
app.mount(
    "/uploads",
    StaticFiles(directory=settings.upload_dir, check_dir=False),
    name="uploads",
)


# 工作台静态页（主设备浏览器访问 http://127.0.0.1:8000 进入管理界面）。
# 存在 workbench_dir 时托管：/ → workbench.html，/assets → 构建产物 JS/CSS；
# 否则回退 JSON 根信息（开发方便）。
_workbench_dir = Path(settings.workbench_dir).resolve()
if _workbench_dir.exists():
    _assets_dir = _workbench_dir / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

    @app.get("/", include_in_schema=False)
    def workbench_index():
        return FileResponse(str(_workbench_dir / "workbench.html"))
else:

    @app.get("/", tags=["meta"])
    def root():
        return {"app": settings.app_name, "docs": "/docs", "health": "/api/health"}
