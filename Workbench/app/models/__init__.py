"""SQLAlchemy 模型（基于现有表结构）。

导入所有模型，确保 Base.metadata 完整，供 create_all 与 Alembic 使用。
现有表 users / products / packages / device_bindings / app_settings 与数据库字段完全一致；
import_runs / import_run_events 为数据生成 Agent 新增表，只增不改。
"""
from app.models.app_setting import AppSetting
from app.models.device_binding import DeviceBinding
from app.models.import_run import ImportRun
from app.models.import_run_event import ImportRunEvent
from app.models.package import Package
from app.models.product import Product
from app.models.user import User

__all__ = [
    "User",
    "Product",
    "Package",
    "DeviceBinding",
    "AppSetting",
    "ImportRun",
    "ImportRunEvent",
]
