"""测试设计器全套后端 API 接口。

验证接口：
- POST /api/designer/signals
- POST /api/designer/preview
- POST /api/designer/compile
- POST /api/designer/finalize
- GET  /api/designer/spec
- PATCH /api/designer/spec (三类微调)
- POST /api/designer/spec/rollback
- POST /api/designer/reset (逃生舱)
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db, require_user
from app.db.base import Base
from app.main import app as fastapi_app
from app.models.user import User


@pytest.fixture
def client_and_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = TestingSessionLocal()

    # 创建测试管理员用户
    admin_user = User(username="admin", password_hash="x", salt="y", role="admin")
    db.add(admin_user)
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_require_user():
        return admin_user

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[require_user] = override_require_user

    client = TestClient(fastapi_app)
    try:
        yield client, db
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()


def test_designer_api_signals(client_and_db):
    client, _ = client_and_db
    resp = client.post("/api/designer/signals")
    assert resp.status_code == 200
    data = resp.json()
    assert "signals" in data
    assert "ranking" in data
    assert "source_level" in data
    assert "sample_data" in data


def test_designer_api_preview(client_and_db):
    client, _ = client_and_db
    resp = client.post("/api/designer/preview", json={"preset_id": "order-entry"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["spec"]["style"]["preset_id"] == "medical-clean"


def test_designer_api_lifecycle(client_and_db):
    client, db = client_and_db

    # 1. 编译
    compile_resp = client.post(
        "/api/designer/compile",
        json={
            "answers": {
                "preset_id": "industrial-dense",
                "brand_color": "#175C8C",
                "sell_mode": "consumable_only",
            }
        },
    )
    assert compile_resp.status_code == 200
    spec = compile_resp.json()["spec"]
    assert spec["style"]["preset_id"] == "industrial-dense"

    # 2. 定稿
    finalize_resp = client.post("/api/designer/finalize", json={"spec": spec})
    assert finalize_resp.status_code == 200
    spec_id = finalize_resp.json()["spec_id"]

    # 3. 读取当前生效 spec
    get_resp = client.get("/api/designer/spec")
    assert get_resp.status_code == 200
    current_spec = get_resp.json()
    assert current_spec["id"] == spec_id
    assert current_spec["payload"]["style"]["preset_id"] == "industrial-dense"

    # 4. 微调 (PATCH) - 切换风格包
    patch_resp = client.patch(
        "/api/designer/spec",
        json={"preset_id": "medical-clean"},
    )
    assert patch_resp.status_code == 200
    patched_spec = client.get("/api/designer/spec").json()
    assert patched_spec["payload"]["style"]["preset_id"] == "medical-clean"

    # 5. 回退 (Rollback)
    rollback_resp = client.post("/api/designer/spec/rollback")
    assert rollback_resp.status_code == 200
    rolled_spec = client.get("/api/designer/spec").json()
    assert rolled_spec["payload"]["style"]["preset_id"] == "industrial-dense"

    # 6. 逃生舱 (Reset)
    reset_resp = client.post("/api/designer/reset")
    assert reset_resp.status_code == 200
    assert client.get("/api/designer/spec").status_code == 404
