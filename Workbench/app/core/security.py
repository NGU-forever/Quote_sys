"""鉴权工具：密码哈希 + JWT 签发/校验。

密码哈希与旧工作台后端（Node scrypt）完全兼容：Node 使用
    scryptSync(password, salt, 64)
其中 salt 为 32 位十六进制字符串（以 UTF-8 编码后作为盐），
参数为 Node 默认值 N=16384, r=8, p=1。这里用 hashlib.scrypt 以相同参数验证，
保证现有 users 表中的 admin 账号可直接登录。
JWT 部分为后续认证预留，结构可扩展（如需刷新令牌、角色等可在此增强）。
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import settings

# ---- 密码：兼容现有 Node scryptSync ----
_SCRYPT_N = 16384
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 64
_SCRYPT_MAXMEM = 64 * 1024 * 1024


def hash_password(password: str, salt_hex: str | None = None) -> dict[str, str]:
    """生成与现有库一致的 {salt, hash}（十六进制字符串）。"""
    salt_hex = salt_hex or secrets.token_hex(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt_hex.encode("utf-8"),
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
        maxmem=_SCRYPT_MAXMEM,
    )
    return {"salt": salt_hex, "hash": digest.hex()}


def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    """校验密码。salt_hex 以 UTF-8 编码后作为盐（与 Node 行为一致）。"""
    try:
        expected = bytes.fromhex(hash_hex)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt_hex.encode("utf-8"),
            n=_SCRYPT_N,
            r=_SCRYPT_R,
            p=_SCRYPT_P,
            dklen=_SCRYPT_DKLEN,
            maxmem=_SCRYPT_MAXMEM,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(expected, actual)


# ---- JWT ----
def create_access_token(subject: int | str, username: str) -> str:
    """签发访问令牌。sub 为用户 id。"""
    expire = datetime.now(timezone.utc) + timedelta(seconds=settings.token_ttl_seconds)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "username": username,
        "exp": expire,
    }
    return jwt.encode(payload, settings.auth_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """校验并解析访问令牌，失败返回 None。"""
    try:
        return jwt.decode(token, settings.auth_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
