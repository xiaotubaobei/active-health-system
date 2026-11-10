from datetime import datetime, timedelta

import pytest

from app import config, migrate
from app.models.entities import AuthSession, BehaviorReport, DeviceReading, ExerciseSession, KbEntry, Prescription, User
from app.passwords import verify_password
from app.security import token_digest
from app.services import ai_client, media_access
from app.routers import demo_videos, pose_infer


def register(client, name="auth-user", **extra):
    return client.post("/auth/register", json={"username": name, "password": "test-password",
                                               "privacy_consent": True, **extra})


def login(client, name="auth-user"):
    response = client.post("/auth/login", json={"username": name, "password": "test-password"})
    assert response.status_code == 200, response.text
    return response.json()


def test_password_storage_cookie_rotation_and_logout(client, store):
    response = register(client)
    assert response.status_code == 200
    auth = response.json()
    token = auth["token"]
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "max-age=28800" in cookie
    assert response.headers["cache-control"] == "no-store"
    assert "password" not in auth["user"]
    assert client.get("/users/me").json() == auth["user"]
    with store[1]() as db:
        user = db.get(User, auth["user"]["id"])
        assert user.password != "test-password" and verify_password("test-password", user.password)
        first_hash = user.password
        assert db.get(AuthSession, token_digest(token)).user_id == user.id
        assert db.get(AuthSession, token) is None
    assert client.post("/auth/login", json={"username": "auth-user", "password": "wrong"}).status_code == 401
    rotated = login(client)["token"]
    assert rotated != token
    assert client.get("/users/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert client.post("/auth/logout").status_code == 200
    assert client.get("/users/me", headers={"Authorization": f"Bearer {rotated}"}).status_code == 401
    assert client.get("/users/me").status_code == 401
    register(client, "second-auth-user")
    with store[1]() as db:
        assert db.query(User).filter_by(username="second-auth-user").one().password != first_hash


def test_expired_forged_and_absent_credentials(client, store):
    assert client.get("/users/me").status_code == 401
    auth = register(client).json()
    for header in ["Bearer dev-1-admin", "Basic anything", "Bearer"]:
        assert client.get("/users/me", headers={"Authorization": header}).status_code == 401
    with store[1]() as db:
        db.get(AuthSession, token_digest(auth["token"])).expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.get("/users/me").status_code == 401
    assert client.post("/devices/readings", json={"user_id": auth["user"]["id"]}).status_code == 401


def test_registration_cannot_grant_roles_or_default_accounts(client, store, monkeypatch):
    assert register(client, role="admin").status_code == 422
    assert register(client, role="physician").status_code == 422
    assert register(client, password="123456").status_code == 422
    assert register(client, privacy_consent=False).status_code == 400
    for name in ["demo", "Demo", "admin", "specialist", "physician"]:
        assert register(client, name).status_code == 400
    for name in ["demo", "admin", "specialist", "physician"]:
        assert client.post("/auth/login", json={"username": name, "password": "123456"}).status_code == 401
    with store[1]() as db:
        assert db.query(User).count() == 0
    monkeypatch.setattr(config, "ENABLE_DEMO_ACCOUNTS", True)
    assert client.post("/auth/login", json={"username": "demo", "password": "123456"}).json()["user"]["role"] == "user"
    assert client.post("/auth/login", json={"username": "admin", "password": "123456"}).status_code == 401


def test_legacy_password_migration_is_repeatable(client, store):
    with store[1]() as db:
        db.add(User(username="legacy-person", password="legacy-password"))
        db.commit()
    migrate.migrate_schema()
    with store[1]() as db:
        hashed = db.query(User).filter_by(username="legacy-person").one().password
        assert verify_password("legacy-password", hashed)
    migrate.migrate_schema()
    with store[1]() as db:
        assert db.query(User).filter_by(username="legacy-person").one().password == hashed
    assert client.post("/auth/login", json={"username": "legacy-person", "password": "legacy-password"}).status_code == 200


def test_csrf_origin_and_cookie_header(client):
    auth = register(client).json()
    uid = auth["user"]["id"]
    client.headers.pop("X-Requested-With")
    assert client.post("/devices/readings", json={"user_id": uid}).status_code == 403
    bearer = {"Authorization": f"Bearer {auth['token']}"}
    assert client.post("/devices/readings", json={"user_id": uid}, headers=bearer).status_code == 200
    assert client.post("/devices/readings", json={"user_id": uid}, headers={**bearer, "Origin": "https://other.example"}).status_code == 403
    assert client.post("/auth/login", json={"username": "auth-user", "password": "test-password"}, headers={"Origin": "https://other.example"}).status_code == 403
    client.headers["X-Requested-With"] = "ActiveHealth"
    assert client.post("/devices/readings", json={"user_id": uid}, headers={"Origin": "http://localhost:5173"}).status_code == 200


def test_private_routes_reject_other_users_and_anonymous_requests(client, store, onboard):
    owner, _ = onboard("record-owner")
    uid = owner["user"]["id"]
    presc = owner["prescription"]["id"]
    finished = client.post("/demo/run-loop", json={"user_id": uid}).json()
    sid = finished["session"]["id"]
    running = client.post("/sessions/start", json={"user_id": uid, "exercise_id": "squat"}).json()["session"]["id"]
    other, _ = onboard("other-person")
    other_uid = other["user"]["id"]
    attempts = [
        ("GET", f"/users/me?user_id={uid}", None),
        ("PUT", f"/users/me?user_id={uid}", {"height_cm": 1}),
        ("GET", f"/users/{uid}/export", None),
        ("GET", f"/onboarding/status?user_id={uid}", None),
        ("POST", "/onboarding/complete", {"user_id": uid}),
        ("POST", "/fitness/assess", {"user_id": uid, "scale_id": "middle_elder"}),
        ("POST", "/body/parse", {"user_id": uid}),
        ("POST", "/prescriptions/generate", {"user_id": uid}),
        ("GET", f"/prescriptions/current?user_id={uid}", None),
        ("GET", f"/prescriptions/history?user_id={uid}", None),
        ("POST", f"/prescriptions/{presc}/advance", None),
        ("POST", "/sessions/start", {"user_id": uid, "exercise_id": "squat"}),
        ("GET", f"/sessions/{running}?user_id={uid}", None),
        ("GET", f"/sessions/{running}?user_id={other_uid}", None),
        ("PUT", f"/sessions/{running}/draft?user_id={other_uid}", {}),
        ("POST", f"/sessions/{running}/cancel?user_id={other_uid}", None),
        ("POST", f"/sessions/{running}/finish", {}),
        ("POST", f"/sessions/{sid}/finish", {}),
        ("GET", f"/reports/{sid}", None),
        ("GET", f"/devices/readings?user_id={uid}", None),
        ("POST", "/devices/readings", {"user_id": uid}),
        ("GET", f"/users/{uid}/sessions", None),
        ("GET", f"/users/{uid}/sessions/page", None),
        ("GET", f"/users/{uid}/kb/summary", None),
        ("GET", f"/users/{uid}/kb/entries", None),
        ("DELETE", f"/users/{uid}/kb?confirm=CLEAR", None),
        ("POST", "/demo/run-loop", {"user_id": uid}),
    ]
    for method, path, body in attempts:
        response = client.request(method, path, json=body)
        assert response.status_code == 404, (method, path, response.text)
    # A browser's cached user object cannot promote an ordinary account.
    assert client.put("/users/me", json={"role": "admin"}).json()["role"] == "user"
    assert client.post(f"/prescriptions/{other['prescription']['id']}/advance").status_code == 403
    client.cookies.clear()
    for method, path, body in attempts:
        assert client.request(method, path, json=body).status_code == 401, (method, path)
    assert client.post("/pose/infer-video", json={"video_path": "demo_videos/test.mp4"}).status_code == 401
    assert client.post("/pose/infer-video-upload", files={"file": ("test.mp4", b"x" * 1001)}).status_code == 401
    with store[1]() as db:
        assert db.get(ExerciseSession, running).status == "running"
        assert db.query(ExerciseSession).count() == 2
        assert db.query(BehaviorReport).count() == db.query(KbEntry).count() == 1
        assert db.query(Prescription).count() == 2
        assert db.query(DeviceReading).count() == 0


def test_media_uploads_are_unique_and_owned(client, store, onboard, tmp_path, monkeypatch):
    monkeypatch.setattr(media_access, "ROOT", tmp_path)
    monkeypatch.setattr(media_access, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(media_access, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(pose_infer, "ROOT", tmp_path)
    monkeypatch.setattr(pose_infer, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(demo_videos, "DEMO_ROOT", tmp_path / "data" / "demo_videos")

    async def infer(_):
        return {"mode": "remote", "coco17_frames": [{"t_ms": 0}]}

    monkeypatch.setattr(ai_client, "pose_infer_video", infer)
    owner, _ = onboard("video-owner")
    uid = owner["user"]["id"]
    paths = []
    for _ in range(2):
        response = client.post("/pose/infer-video-upload", files={"file": ("same.mp4", b"v" * 1001)})
        assert response.status_code == 200, response.text
        paths.append(response.json()["upload_rel"])
    assert paths[0] != paths[1] and all(p.startswith(f"uploads/offline/{uid}/") for p in paths)
    assert client.post("/pose/infer-video", json={"video_path": paths[0]}).status_code == 200
    other, _ = onboard("video-other")
    oid = other["user"]["id"]
    running = client.post("/sessions/start", json={"user_id": oid, "exercise_id": "squat"}).json()["session"]["id"]
    for path in [paths[0], str(tmp_path / paths[0]), "uploads/offline/legacy.mp4", f"uploads/offline/{oid}0/x.mp4", "data/demo_videos_evil/x.mp4"]:
        assert client.post("/pose/infer-video", json={"video_path": path}).status_code == 404
        assert client.post("/sessions/start", json={"user_id": oid, "exercise_id": "squat", "video_path": path}).status_code == 404
        assert client.post("/body/parse", json={"user_id": oid, "image_path": path}).status_code == 404
        assert client.put(f"/sessions/{running}/draft?user_id={oid}", json={"video_path": path}).status_code == 404
        assert client.post(f"/sessions/{running}/finish", json={"video_path": path}).status_code == 404
    with store[1]() as db:
        assert db.get(ExerciseSession, running).status == "running"
        assert db.get(ExerciseSession, running).video_path == ""
        assert db.query(BehaviorReport).count() == db.query(KbEntry).count() == 0
    assert client.post("/pose/infer-video", json={"video_path": "data/demo_videos/../private.mp4"}).status_code == 400
    assert client.post("/pose/infer-video-upload", files={"file": ("test.exe", b"v" * 1001)}).status_code == 400
    sample = tmp_path / "data" / "demo_videos" / "public.mp4"
    sample.parent.mkdir(parents=True)
    sample.write_bytes(b"v" * 1001)
    assert client.post("/pose/infer-video", json={"video_path": "demo_videos/public.mp4"}).status_code == 200
    assert client.post("/pose/infer-video", json={"video_path": "data/demo_videos/public.mp4"}).status_code == 200
    # Public sample streaming must not expose another folder sharing its name prefix.
    sibling = tmp_path / "data" / "demo_videos_evil" / "private.mp4"
    sibling.parent.mkdir(parents=True)
    sibling.write_bytes(b"private-video")
    client.cookies.clear()
    assert client.get("/demo-videos/file", params={"rel": "public.mp4"}).content == sample.read_bytes()
    for path in [str(sibling), str(tmp_path / paths[0]), "../demo_videos_evil/private.mp4"]:
        assert client.get("/demo-videos/file", params={"rel": path}).status_code == 400
