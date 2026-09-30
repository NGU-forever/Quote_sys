"""兼容层路由聚合（挂载在 /api 前缀下，与旧 Node 后端路径一致）。"""
from fastapi import APIRouter

from app.compat import auth, catalog, health, network, packages, products, sync, uploads

compat_router = APIRouter(prefix="/api")
compat_router.include_router(auth.router, tags=["legacy-auth"])
compat_router.include_router(products.router, tags=["legacy-products"])
compat_router.include_router(packages.router, tags=["legacy-packages"])
compat_router.include_router(catalog.router, tags=["legacy-catalog"])
compat_router.include_router(sync.router, tags=["legacy-sync"])
compat_router.include_router(uploads.router, tags=["legacy-uploads"])
compat_router.include_router(health.router, tags=["legacy-health"])
compat_router.include_router(network.router, tags=["network"])
