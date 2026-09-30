"""应用配置。

所有可配置项均通过环境变量（或 .env 文件）注入，不硬编码敏感信息。
数据库采用 SQLAlchemy 双引擎：默认 SQLite（现有库），
把 DATABASE_URL 换成 postgresql+psycopg://... 即切换到 PostgreSQL。
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用设置。字段名小写，环境变量名不区分大小写（DATABASE_URL → database_url）。"""

    # 应用
    app_name: str = "quote-service"
    app_version: str = "2.0.0"
    debug: bool = False

    # 数据库（SQLAlchemy 双引擎：默认 SQLite，配置 PostgreSQL 连接串即可平滑切换）
    database_url: str = "sqlite:///./app.db"

    # Redis 缓存与分布式自增
    redis_url: str = "redis://localhost:6379/0"

    # 鉴权（预留 JWT 密钥）
    auth_secret: str = "quotesys-auth-secret-key"
    token_ttl_seconds: int = 12 * 60 * 60  # 12 小时
    jwt_algorithm: str = "HS256"

    # 产品照片上传目录（默认 backend/uploads，可设 UPLOAD_DIR 覆盖）
    upload_dir: str = "./uploads"
    max_upload_bytes: int = 5 * 1024 * 1024  # 5MB

    # 数据生成 Agent：源资料目录（开发默认仓库根 assets，打包后由 entry.py 注入 %APPDATA%\\QuoteSys\\assets）
    assets_dir: str = "../assets"
    agent_default_mode: str = "apply"
    agent_prompt_version: str = "2026-09-12.1"

    # LLM：provider=auto 时，配置了接口地址+模型（可不带 Key，如 Ollama/LM Studio）走真实接口，否则使用离线 Mock
    llm_provider: str = "auto"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_max_steps: int = 20

    # 工作台静态构建目录（dev 指向 web/dist，相对进程 cwd=Workbench/；打包时设为解包后的目录）
    workbench_dir: str = "web/dist"

    # CORS 允许来源（逗号分隔，* 表示全部）
    cors_origins: str = "*"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def assets_root(self):
        """assets 根目录绝对路径（配置按进程 cwd 解析）。"""
        from pathlib import Path

        return Path(self.assets_dir).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
