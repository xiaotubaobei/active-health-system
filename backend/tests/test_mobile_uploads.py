"""Upload boundaries use a temporary store; AI responses are isolated fixtures."""
import pytest

from app.models.entities import ExerciseSession
from app.routers import pose_infer
from app.services import ai_client, media_access


@pytest.fixture
def upload_owner(client, onboard, tmp_path, monkeypatch):
    root = tmp_path / "custom-storage"
    monkeypatch.setattr(pose_infer, "UPLOAD_DIR", root)
    monkeypatch.setattr(media_access, "UPLOAD_DIR", root)

    async def infer(_):
        return {"mode": "remote", "coco17_frames": [{"t_ms": 0, "keypoints": []}]}

    monkeypatch.setattr(ai_client, "pose_infer_video", infer)
    owner, _ = onboard("upload-owner")
    return owner["user"]["id"], root


def upload(client, **data):
    return client.post("/pose/infer-video-upload", data=data,
                       files={"file": ("phone.mov", b"v" * 1200, "video/quicktime")})


def test_custom_upload_root_streaming_range_and_private_access(client, upload_owner, onboard):
    uid, root = upload_owner
    response = upload(client)
    assert response.status_code == 200, response.text
    path = response.json()["upload_rel"]
    assert path.startswith(f"uploads/offline/{uid}/")
    assert (root / path.removeprefix("uploads/")).is_file()
    response = client.get("/" + path, headers={"Range": "bytes=0-99"})
    assert response.status_code == 206
    assert response.content == b"v" * 100
    assert "no-store" in response.headers["cache-control"]
    onboard("other-upload-owner")
    assert client.get("/" + path).status_code == 404
    client.cookies.clear()
    assert client.get("/" + path).status_code == 401


def test_session_upload_replaces_video_and_advances_revision(client, upload_owner, store):
    uid, root = upload_owner
    sid = client.post("/sessions/start", json={"user_id": uid, "exercise_id": "squat"}).json()["session"]["id"]
    first = upload(client, session_id=sid, exercise_id="squat")
    assert first.status_code == 200, first.text
    old = first.json()["upload_rel"]
    second = upload(client, session_id=sid, exercise_id="squat")
    assert second.status_code == 200, second.text
    assert second.json()["draft_revision"] == first.json()["draft_revision"] + 1
    assert not (root / old.removeprefix("uploads/")).exists()
    with store[1]() as db:
        row = db.get(ExerciseSession, sid)
        assert row.video_path == second.json()["upload_rel"]
        assert row.draft_revision == second.json()["draft_revision"]
    assert upload(client, session_id=sid, exercise_id="lunge").status_code == 409


@pytest.mark.parametrize("change", ["cancel", "draft"])
def test_video_analysis_cannot_overwrite_a_session_changed_while_waiting(client, upload_owner, store, monkeypatch, change):
    uid, root = upload_owner
    sid = client.post("/sessions/start", json={"user_id": uid, "exercise_id": "squat"}).json()["session"]["id"]

    async def infer(_):
        with store[1]() as db:
            row = db.get(ExerciseSession, sid)
            if change == "cancel":
                row.status = "cancelled"
            else:
                row.draft_revision += 1
            db.commit()
        return {"mode": "remote", "coco17_frames": [{"t_ms": 0}]}

    monkeypatch.setattr(ai_client, "pose_infer_video", infer)
    response = upload(client, session_id=sid, exercise_id="squat")
    assert response.status_code == 409, response.text
    assert not list(root.rglob("*.mov"))
    assert not list(root.rglob("*.part"))
    with store[1]() as db:
        assert db.get(ExerciseSession, sid).video_path == ""


@pytest.mark.parametrize("result,status", [({"mode": "local_fallback"}, 503), ({"mode": "remote", "coco17_frames": []}, 502)])
def test_unusable_analysis_cleans_uploaded_file(client, upload_owner, monkeypatch, result, status):
    _, root = upload_owner

    async def infer(_):
        return result

    monkeypatch.setattr(ai_client, "pose_infer_video", infer)
    assert upload(client).status_code == status
    assert not list(root.rglob("*.mov"))
    assert not list(root.rglob("*.part"))


def test_stream_size_limit_cleans_partial_file_before_calling_ai(client, upload_owner, monkeypatch):
    _, root = upload_owner
    monkeypatch.setattr(pose_infer, "MAX_VIDEO_UPLOAD_BYTES", 1100)

    async def must_not_run(_):
        pytest.fail("Oversized upload reached inference")

    monkeypatch.setattr(ai_client, "pose_infer_video", must_not_run)
    assert upload(client).status_code == 413
    assert not list(root.rglob("*.mov"))
    assert not list(root.rglob("*.part"))


def test_safari_missing_extension_uses_video_mime(client, upload_owner):
    response = client.post("/pose/infer-video-upload", files={"file": ("blob", b"v" * 1200, "video/quicktime")})
    assert response.status_code == 200, response.text
    assert response.json()["upload_rel"].endswith(".mov")
