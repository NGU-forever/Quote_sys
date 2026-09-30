"""pytest 入口：确保任何测试在导入 app 之前指向 PostgreSQL 测试库。

pytest 会先导入 conftest，再收集测试模块；这里显式导入 db_support，
避免某个测试模块漏写 import 时误连开发/生产库。
"""
import sys
from pathlib import Path

_WORKBENCH_DIR = Path(__file__).resolve().parent.parent
if str(_WORKBENCH_DIR) not in sys.path:
    sys.path.insert(0, str(_WORKBENCH_DIR))

from tests import db_support  # noqa: E402,F401
