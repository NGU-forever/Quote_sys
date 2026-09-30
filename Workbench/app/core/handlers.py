"""全局异常处理器。

统一响应格式（工作台兼容接口 /api/*）：{"error": <错误信息>}
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exc_handler(request: Request, exc: StarletteHTTPException):
        msg = str(exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"error": msg, "detail": msg})

    @app.exception_handler(RequestValidationError)
    async def validation_exc_handler(request: Request, exc: RequestValidationError):
        details = "; ".join(
            f"{'.'.join(str(loc) for loc in err.get('loc', []))}: {err.get('msg')}"
            for err in exc.errors()
        )
        msg = f"参数校验失败：{details}"
        return JSONResponse(status_code=422, content={"error": msg, "detail": msg})


    @app.exception_handler(Exception)
    async def unhandled_exc_handler(request: Request, exc: Exception):
        # 未捕获异常统一返回 500，避免向客户端泄露堆栈
        return JSONResponse(status_code=500, content={"error": "服务器内部错误"})
