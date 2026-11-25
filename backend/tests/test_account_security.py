from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app import auth_limits, config, migrate
from app.main import app
from app.models.entities import AuthRateLimit, AuthSession, ExerciseSession, User
from app.passwords import hash_password, verify_password
from app.routers import auth

OLD = "test-password"
NEW = "new-private-password"


def register(client, name="private-account"):
    r = client.post("/auth/register", json={"username": name, "password": OLD, "privacy_consent": True})
    assert r.status_code == 200, r.text
    return r.json()


def login(client, password=OLD, name="private-account", headers=None):
    return client.post("/auth/login", json={"username": name, "password": password}, headers=headers)


def change(client, current=OLD, new=NEW, **kwargs):
    return client.post("/auth/change-password", json={"current_password": current, "new_password": new}, **kwargs)


def test_change_revokes_every_device_keeps_other_accounts_and_training(client, store, onboard):
    user, _ = onboard("private-account")
    uid = user["user"]["id"]
    sid = client.post("/sessions/start", json={"user_id": uid, "exercise_id": "squat"}).json()["session"]["id"]
    first = login(client).json()["token"]
    client.cookies.clear()
    second = login(client).json()["token"]
    client.cookies.clear()
    other = register(client, "unrelated-person")["token"]
    result = change(client, headers={"Authorization": f"Bearer {first}"})
    assert result.status_code == 200, result.text
    assert result.json() == {"ok": True, "reauthenticate": True}
    assert "max-age=0" in result.headers["set-cookie"].lower()
    assert result.headers["cache-control"] == "no-store"
    assert NEW not in result.text and OLD not in result.text
    for token in [first, second]:
        assert client.get("/users/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert client.get("/users/me", headers={"Authorization": f"Bearer {other}"}).status_code == 200
    with store[1]() as db:
        assert verify_password(NEW, db.get(User, uid).password)
        assert not verify_password(OLD, db.get(User, uid).password)
        assert db.query(AuthSession).filter_by(user_id=uid).count() == 0
        assert db.get(ExerciseSession, sid).user_id == uid
    assert login(client).status_code == 401
    assert login(client, NEW).status_code == 200


def test_wrong_password_and_reuse_leave_login_valid(client, store):
    uid = register(client)["user"]["id"]
    with store[1]() as db:
        original = db.get(User, uid).password
    assert change(client, "incorrect-password").status_code == 400
    assert change(client, new=OLD).status_code == 400
    assert client.get("/users/me").status_code == 200
    with store[1]() as db:
        assert db.get(User, uid).password == original
        assert db.query(AuthSession).filter_by(user_id=uid).count() == 1


def test_change_requires_login_csrf_and_allowed_origin(client):
    assert change(client).status_code == 401
    register(client)
    client.headers.pop("X-Requested-With")
    assert change(client).status_code == 403
    assert change(client, headers={"X-Requested-With": "ActiveHealth", "Origin": "https://wrong.example"}).status_code == 403
    assert client.get("/users/me").status_code == 200


def test_demo_password_remains_unchanged(client, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_DEMO_ACCOUNTS", True)
    assert login(client, "123456", "demo").status_code == 200
    assert change(client, "123456").status_code == 403
    assert login(client, "123456", "demo").status_code == 200


def test_password_validation_does_not_echo_credentials(client):
    register(client)
    for current, new in [(OLD, "pZ6!7"), ("s" * 129, NEW), (OLD, "n" * 129)]:
        result = change(client, current, new)
        assert result.status_code == 422
        assert current not in result.text and new not in result.text
        assert all("input" not in row for row in result.json()["detail"])
    r = client.post("/auth/register", json={"username": "another-user", "password": "short"})
    assert r.status_code == 422 and '"input"' not in r.text
    assert client.get("/users/me").status_code == 200


def test_new_password_with_spaces_is_preserved_exactly(client):
    register(client)
    password = "  长密码 with spaces  "
    assert change(client, new=password).status_code == 200
    assert login(client, password.strip()).status_code == 401
    assert login(client, password).status_code == 200


def test_login_pair_limit_retry_header_expiry_and_unknown_accounts(client, monkeypatch, store):
    register(client)
    clock = [datetime(2026, 11, 25, 10)]
    monkeypatch.setattr(auth_limits, "_now", lambda: clock[0])
    for name in ["private-account", "missing-person"]:
        for _ in range(5):
            assert login(client, "incorrect-password", name).status_code == 401
        blocked = login(client, OLD, name)
        assert blocked.status_code == 429
        assert blocked.headers["retry-after"] == "60"
    with store[1]() as db:
        for row in db.query(AuthRateLimit):
            assert len(row.key) == 64 and "private-account" not in row.key
    clock[0] += timedelta(seconds=60)
    assert login(client).status_code == 200
    # Expired rows are removed, not an ever-growing history of usernames/IPs.
    with store[1]() as db:
        assert all(row.expires_at > clock[0] for row in db.query(AuthRateLimit))


def test_success_resets_pair_but_does_not_clear_aggregate_budget(client):
    register(client)
    for _ in range(4):
        assert login(client, "incorrect-password").status_code == 401
    assert login(client).status_code == 200
    for _ in range(4):
        assert login(client, "incorrect-password").status_code == 401
    assert login(client).status_code == 200
    # Correct credentials cannot reset the per-account aggregate allowance.
    for _ in range(10):
        assert login(client).status_code == 200
    assert login(client).status_code == 429


def test_password_attempts_are_limited_without_expiring_cookie(client, monkeypatch):
    register(client)
    clock = [datetime(2026, 11, 25, 10)]
    monkeypatch.setattr(auth_limits, "_now", lambda: clock[0])
    for _ in range(5):
        assert change(client, "incorrect-password").status_code == 400
    assert change(client).status_code == 429
    assert client.get("/users/me").status_code == 200
    clock[0] += timedelta(seconds=60)
    assert change(client).status_code == 200


def test_limits_share_database_ignore_spoofed_headers_and_bound_parallel_requests(client, monkeypatch):
    register(client)
    monkeypatch.setattr(auth, "verify_password", lambda *_: False)
    def attempt(i):
        # Separate clients simulate workers/processes; state is never in their memory.
        with TestClient(app) as independent:
            return login(independent, "wrong", headers={"X-Forwarded-For": f"192.0.2.{i}"}).status_code
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, range(12)))
    assert results.count(401) == 5
    assert results.count(429) == 7


def test_source_limit_cannot_be_bypassed_by_changing_username(client, monkeypatch):
    monkeypatch.setattr(auth, "verify_password", lambda *_: False)
    for i in range(60):
        assert login(client, "wrong", f"unknown-{i}").status_code == 401
    assert login(client, "wrong", "yet-another-name").status_code == 429


def test_old_verified_login_cannot_create_session_after_password_change(client, store, monkeypatch):
    uid = register(client)["user"]["id"]
    real_verify = auth.verify_password
    def race(password, stored):
        correct = real_verify(password, stored)
        with store[1]() as db:
            db.get(User, uid).password = hash_password(NEW)
            db.query(AuthSession).filter_by(user_id=uid).delete()
            db.commit()
        return correct
    monkeypatch.setattr(auth, "verify_password", race)
    assert login(client).status_code == 401
    with store[1]() as db:
        assert db.query(AuthSession).filter_by(user_id=uid).count() == 0


def test_stale_password_change_cannot_overwrite_newer_password(client, store, monkeypatch):
    uid = register(client)["user"]["id"]
    real_hash = auth.hash_password
    def race(password):
        with store[1]() as db:
            db.get(User, uid).password = real_hash("other-new-password")
            db.query(AuthSession).filter_by(user_id=uid).delete()
            db.commit()
        return real_hash(password)
    monkeypatch.setattr(auth, "hash_password", race)
    assert change(client).status_code == 409
    with store[1]() as db:
        assert verify_password("other-new-password", db.get(User, uid).password)


def test_existing_database_creates_rate_limit_table_repeatably(client, store):
    uid = register(client)["user"]["id"]
    AuthRateLimit.__table__.drop(store[0])
    migrate.migrate_schema()
    migrate.migrate_schema()
    assert login(client).status_code == 200
    with store[1]() as db:
        assert db.get(User, uid).username == "private-account"
        assert db.query(AuthRateLimit).count() == 2
