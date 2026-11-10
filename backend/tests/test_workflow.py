import asyncio

import pytest
from sqlalchemy import inspect, text

import app.migrate as migrations
from app.models.entities import BehaviorReport, ExerciseSession, FitnessAssessment, FitnessBaseline, KbEntry, Prescription
from app.schemas.dto import SessionFinishIn
from app.services import ai_client, session_completion


def start(client, result):
    response = client.post("/sessions/start", json={
        "user_id": result["user"]["id"], "prescription_id": result["prescription"]["id"],
        "exercise_id": "squat", "exercise_name": "深蹲",
    })
    assert response.status_code == 200, response.text
    return response.json()["session"]["id"]


def test_new_account_must_complete_assessment(client, store, onboard):
    assert client.post("/auth/register", json={"username": "no-consent"}).status_code == 400
    created = client.post("/auth/register", json={"username": "new-user", "privacy_consent": True}).json()
    uid = created["user"]["id"]
    assert not client.get("/onboarding/status", params={"user_id": uid}).json()["onboarding_done"]
    assert client.post("/sessions/start", json={"user_id": uid, "exercise_id": "squat"}).status_code == 409
    assert client.post("/onboarding/complete", json={"user_id": uid, "scale_id": "middle_elder", "privacy_consent": True}).status_code == 422
    with store[1]() as db:
        assert db.query(FitnessBaseline).count() == 0
        assert db.query(FitnessAssessment).count() == 0
    result, body = onboard("complete-user", age="youth")
    assert result["baseline"]["total_score"] == 70
    assert result["user"]["onboarding_done"]
    assert result["prescription"]["version"] == 1
    assert client.post("/onboarding/complete", json=body).status_code == 409
    assert client.get("/onboarding/status", params={"user_id": result["user"]["id"]}).json()["has_baseline"]


@pytest.mark.parametrize("invalid", ["missing", "range", "unknown", "extra", "age-mismatch"])
def test_invalid_scores_never_create_records(client, store, invalid):
    user = client.post("/auth/register", json={"username": "invalid-user", "privacy_consent": True}).json()["user"]
    scale = next(s for s in client.get("/fitness/scales").json() if s["id"] == "middle_elder")
    body = {"user_id": user["id"], "scale_id": scale["id"], "privacy_consent": True,
            "scores": {item["key"]: 70 for item in scale["items"]}}
    if invalid == "missing":
        body["scores"].pop("bmi")
    elif invalid == "range":
        body["scores"]["bmi"] = 101
    elif invalid == "unknown":
        body["scale_id"] = "unknown"
    elif invalid == "extra":
        body["scores"]["unexpected"] = 70
    else:
        body["age_group"] = "youth"
    assert client.post("/onboarding/complete", json=body).status_code == 422
    if invalid != "age-mismatch":
        assert client.post("/fitness/assess", json=body).status_code == 422
    with store[1]() as db:
        assert db.query(FitnessAssessment).count() == 0
        assert db.query(FitnessBaseline).count() == 0
        assert db.query(Prescription).count() == 0


def test_finish_archives_once_and_excludes_demo_scores(client, store, onboard):
    result, _ = onboard()
    sid = start(client, result)
    pose = {"source": "offline_video", "sequences": {"coco17": {"frames": [{"t_ms": 0}]}},
            "motion_analysis": {"status": "ok", "rep_count": 1, "rep_intervals": [{"start_sec": 0, "end_sec": 2}]}}
    response = client.post(f"/sessions/{sid}/finish", json={"video_path": "test.mp4", "pose_summary": pose})
    assert response.status_code == 200, response.text
    first = response.json()
    assert first["analysis"]["status"] == "demo"
    assert first["analysis"]["score"] is None
    assert first["updated_prescription"] is None
    assert first["kb_entry_id"]
    second = client.post(f"/sessions/{sid}/finish", json={"video_path": "should-not-replace.mp4"}).json()
    assert first["report"]["id"] == second["report"]["id"]
    assert second["session"]["video_path"] == "test.mp4"
    assert second["kb_entry_id"] == first["kb_entry_id"]
    uid = result["user"]["id"]
    summary = client.get(f"/users/{uid}/kb/summary").json()
    assert summary["finished_sessions"] == summary["kb_entries"] == 1
    assert summary["avg_score_recent"] is None
    assert summary["scored_entries_recent"] == 0
    assert summary["entries"][0]["score"] is None
    assert summary["entries"][0]["pose_digest"]["motion_analysis"] == pose["motion_analysis"]
    assert client.get(f"/users/{uid}/kb/entries").json()[0]["score"] is None
    assert client.get(f"/reports/{sid}").json()["analysis"] == first["analysis"]
    assert client.get(f"/users/{uid}/sessions").json()[0]["pose_frames"] == 1
    with store[1]() as db:
        assert db.query(BehaviorReport).count() == db.query(KbEntry).count() == 1
        assert db.query(Prescription).count() == 1


def test_model_zero_score_and_comparison_ignore_demo(client, onboard, monkeypatch):
    result, _ = onboard()
    sid = start(client, result)
    client.post(f"/sessions/{sid}/finish", json={})

    async def model(_):
        return {"mode": "remote", "score": 0, "errors": ["test-error"]}

    monkeypatch.setattr(ai_client, "video_cot_evaluate", model)
    sid = start(client, result)
    finished = client.post(f"/sessions/{sid}/finish", json={}).json()
    assert finished["analysis"]["score"] == 0
    uid = result["user"]["id"]
    summary = client.get(f"/users/{uid}/kb/summary", params={"limit": 1}).json()
    assert summary["kb_entries"] == 2
    assert summary["avg_score_recent"] == 0
    assert summary["scored_entries_recent"] == 1
    assert "首次" in summary["entries"][0]["history_note"]
    sid = start(client, result)
    client.post(f"/sessions/{sid}/finish", json={})
    summary = client.get(f"/users/{uid}/kb/summary").json()
    assert "上次（0.0 分）" in summary["entries"][0]["history_note"]
    assert summary["recent_errors"] == {"test-error": 2}


def test_failed_archive_rolls_back_and_can_retry(client, store, onboard, monkeypatch):
    result, _ = onboard()
    sid = start(client, result)
    original = session_completion.append_kb_entry

    def fail(*args, **kwargs):
        raise RuntimeError("simulated archive failure")

    monkeypatch.setattr(session_completion, "append_kb_entry", fail)
    with pytest.raises(RuntimeError, match="simulated archive failure"):
        client.post(f"/sessions/{sid}/finish", json={})
    with store[1]() as db:
        assert db.get(ExerciseSession, sid).status == "running"
        assert db.query(BehaviorReport).count() == db.query(KbEntry).count() == 0
    monkeypatch.setattr(session_completion, "append_kb_entry", original)
    assert client.post(f"/sessions/{sid}/finish", json={}).status_code == 200


def test_simultaneous_finishes_create_one_report(client, store, onboard, monkeypatch):
    result, _ = onboard()
    sid = start(client, result)

    async def run():
        ready = asyncio.Event()
        calls = 0

        async def evaluate(_):
            nonlocal calls
            calls += 1
            if calls == 2:
                ready.set()
            await asyncio.wait_for(ready.wait(), timeout=3)
            return {"mode": "mock", "score": 78}

        monkeypatch.setattr(ai_client, "video_cot_evaluate", evaluate)
        with store[1]() as first, store[1]() as second:
            results = await asyncio.gather(
                session_completion.complete_session(first, sid, SessionFinishIn()),
                session_completion.complete_session(second, sid, SessionFinishIn()),
            )
            assert results[0]["report"].id == results[1]["report"].id

    asyncio.run(run())
    with store[1]() as db:
        assert db.query(BehaviorReport).count() == db.query(KbEntry).count() == 1


def test_foreign_prescription_rejected_and_demo_does_not_change_baseline(client, store, onboard):
    first, _ = onboard("first-user")
    second, _ = onboard("second-user")
    assert client.post("/sessions/start", json={"user_id": first["user"]["id"],
        "prescription_id": second["prescription"]["id"], "exercise_id": "squat"}).status_code == 400
    response = client.post("/demo/run-loop", json={"user_id": first["user"]["id"]})
    assert response.status_code == 200, response.text
    assert response.json()["analysis"]["score"] is None
    with store[1]() as db:
        assert db.query(FitnessAssessment).count() == 2
        assert db.query(Prescription).count() == 2
        assert db.query(KbEntry).count() == 1


def test_old_schema_migrates_without_losing_data(store):
    engine, _ = store
    with engine.begin() as db:
        db.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(64), password VARCHAR(128), role VARCHAR(32), age_group VARCHAR(32), height_cm FLOAT, weight_kg FLOAT, chronic_tags JSON, goal VARCHAR(32), created_at DATETIME)"))
        db.execute(text("INSERT INTO users (id, username) VALUES (10, 'existing-user')"))
        db.execute(text("CREATE TABLE behavior_reports (id INTEGER PRIMARY KEY, session_id INTEGER, user_id INTEGER, tasks JSON, cot JSON, created_at DATETIME)"))
        db.execute(text("INSERT INTO behavior_reports (id, session_id, user_id) VALUES (1, 1, 10)"))
    migrations.migrate_schema()
    migrations.migrate_schema()
    assert {"privacy_consent", "onboarding_done"} <= {c["name"] for c in inspect(engine).get_columns("users")}
    assert "video_understanding" in {c["name"] for c in inspect(engine).get_columns("behavior_reports")}
    with engine.connect() as db:
        assert db.execute(text("SELECT username FROM users WHERE id=10")).scalar() == "existing-user"
        assert db.execute(text("SELECT count(*) FROM behavior_reports")).scalar() == 1


def test_fresh_demo_creates_only_initial_template(client, store):
    user = client.post("/auth/login", json={"username": "demo", "password": "123456"}).json()["user"]
    for _ in range(2):
        response = client.post("/demo/run-loop", json={"user_id": user["id"]})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["prescription"]["version"] == 1
        assert result["updated_prescription"] is None
        assert result["analysis"]["score"] is None
    with store[1]() as db:
        assert db.query(Prescription).count() == 1
        assert db.query(FitnessAssessment).count() == db.query(FitnessBaseline).count() == 0
        assert db.query(BehaviorReport).count() == db.query(KbEntry).count() == 2


def test_resume_saved_input_cancel_and_ownership(client, store, onboard):
    result, _ = onboard()
    other, _ = onboard("other-user")
    uid = result["user"]["id"]
    pose = {"source": "offline_video", "sequences": {"coco17": {"frames": [{"t_ms": 0}]}}}
    response = client.post("/sessions/start", json={"user_id": uid, "exercise_id": "squat",
        "video_path": "uploads/real.mp4", "pose_summary": pose})
    sid = response.json()["session"]["id"]
    assert client.get(f"/sessions/{sid}", params={"user_id": uid}).json()["session"]["pose_summary"] == pose
    foreign = {"user_id": other["user"]["id"]}
    assert client.get(f"/sessions/{sid}", params=foreign).status_code == 404
    assert client.put(f"/sessions/{sid}/draft", params=foreign, json={}).status_code == 404
    assert client.post(f"/sessions/{sid}/cancel", params=foreign).status_code == 404
    pose["sequences"]["coco17"]["frames"].append({"t_ms": 100})
    assert client.put(f"/sessions/{sid}/draft", params={"user_id": uid}, json={
        "video_path": "uploads/replaced.mp4", "pose_summary": pose}).status_code == 200
    # Empty finish after a reload must use the durable saved input.
    finished = client.post(f"/sessions/{sid}/finish", json={}).json()
    assert finished["session"]["video_path"] == "uploads/replaced.mp4"
    assert finished["session"]["pose_summary"] == pose
    assert client.post(f"/sessions/{sid}/cancel", params={"user_id": uid}).status_code == 409
    assert client.put(f"/sessions/{sid}/draft", params={"user_id": uid}, json={}).status_code == 409
    sid = start(client, result)
    for _ in range(2):
        assert client.post(f"/sessions/{sid}/cancel", params={"user_id": uid}).json()["session"]["status"] == "cancelled"
    assert client.post(f"/sessions/{sid}/finish", json={}).status_code == 409
    with store[1]() as db:
        assert db.query(BehaviorReport).count() == db.query(KbEntry).count() == 1


def test_paginated_history_filters_and_scores_outside_summary_window(client, onboard):
    result, _ = onboard()
    uid = result["user"]["id"]
    for i in range(23):
        sid = start(client, result)
        client.post(f"/sessions/{sid}/finish", json={})
    pending = client.post("/sessions/start", json={"user_id": uid, "exercise_id": "squat", "exercise_name": "another squat label"}).json()["session"]["id"]
    cancelled = client.post("/sessions/start", json={"user_id": uid, "exercise_id": "walk", "exercise_name": "walking"}).json()["session"]["id"]
    client.post(f"/sessions/{cancelled}/cancel", params={"user_id": uid})
    url = f"/users/{uid}/sessions/page"
    page = client.get(url, params={"page": 3, "page_size": 10}).json()
    assert page["total"] == 25 and len(page["items"]) == 5
    assert all(item["analysis"]["status"] == "demo" for item in page["items"])
    assert all(item["analysis"]["score"] is None for item in page["items"])
    assert client.get(url, params={"status": "running"}).json()["items"][0]["id"] == pending
    filtered = client.get(url, params={"status": "cancelled", "exercise_id": "walk"}).json()
    assert filtered["total"] == 1 and filtered["items"][0]["id"] == cancelled
    assert {e["id"] for e in filtered["exercises"]} == {"squat", "walk"}
    assert len(filtered["exercises"]) == 2
    assert client.get(url, params={"page": 99}).json()["items"] == []
    assert client.get(url, params={"page": 0}).status_code == 422
    assert client.get(url, params={"status": "invalid"}).status_code == 422
    assert client.get("/users/99999/sessions/page").status_code == 404
    assert isinstance(client.get(f"/users/{uid}/sessions").json(), list)
