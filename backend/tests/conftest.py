"""所有测试使用临时数据库，禁止连接项目演示库。"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.migrate as migrations
from app.config import AI_ENDPOINTS
from app import config
from app.database import get_db
from app.main import app


@pytest.fixture
def store(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(migrations, "engine", engine)
    monkeypatch.setattr(migrations, "DATABASE_URL", url)
    monkeypatch.setattr(config, "ENABLE_DEMO_ACCOUNTS", False)
    for service in AI_ENDPOINTS:
        monkeypatch.setitem(AI_ENDPOINTS, service, "")

    def test_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    yield engine, factory
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def client(store):
    with TestClient(app, headers={"X-Requested-With": "ActiveHealth"}) as client:
        yield client


@pytest.fixture
def onboard(client):
    def create(name="test-user", age="middle_age"):
        response = client.post("/auth/register", json={
            "username": name, "password": "test-password", "privacy_consent": True,
        })
        assert response.status_code == 200, response.text
        user = response.json()["user"]
        scale_id = "youth" if age == "youth" else "middle_elder"
        scale = next(s for s in client.get("/fitness/scales").json() if s["id"] == scale_id)
        body = {"user_id": user["id"], "age_group": age, "scale_id": scale_id,
                "scores": {item["key"]: 70 for item in scale["items"]}, "privacy_consent": True}
        response = client.post("/onboarding/complete", json=body)
        assert response.status_code == 200, response.text
        return response.json(), body
    return create
