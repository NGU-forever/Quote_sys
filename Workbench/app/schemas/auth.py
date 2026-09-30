"""登录/用户相关请求/响应模型（兼容旧前端）。"""
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str


class ResetPasswordRequest(BaseModel):
    username: str
    new_password: str
