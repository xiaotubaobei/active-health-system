"""Maintenance recovery checks use disposable data, never the local application DB."""
from contextlib import closing
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tarfile

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app
from app.services import media_access


spec = importlib.util.spec_from_file_location("backup_data", Path(__file__).resolve().parents[2] / "scripts/backup_data.py")
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


@pytest.fixture
def source(client, onboard, store, tmp_path, monkeypatch):
    owner, _ = onboard("backup-owner")
    result = client.post("/demo/run-loop", json={"user_id": owner["user"]["id"]})
    assert result.status_code == 200
    running = client.post("/sessions/start", json={"user_id": owner["user"]["id"], "exercise_id": "squat"})
    assert running.status_code == 200
    other, _ = onboard("backup-other")
    uploads = tmp_path / "source/uploads"
    video = uploads / "offline" / str(owner["user"]["id"]) / "example.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"synthetic-video-fixture\x00" * 100)
    monkeypatch.setattr(media_access, "ROOT", uploads.parent)
    monkeypatch.setattr(media_access, "UPLOAD_DIR", uploads)
    assert client.post("/auth/login", json={"username": "backup-owner", "password": "test-password"}).status_code == 200
    saved = client.put(f"/sessions/{running.json()['session']['id']}/draft?user_id={owner['user']['id']}", json={
        "expected_revision": 0, "video_path": "uploads/" + video.relative_to(uploads).as_posix()})
    assert saved.status_code == 200
    return {"db": Path(store[0].url.database), "uploads": uploads,
            "owner": owner["user"], "other": other["user"],
            "finished": result.json()["session"]["id"], "running": running.json()["session"]["id"],
            "video": video, "output": tmp_path / "backups"}


def create(source):
    return backup.create_backup(source["db"], source["uploads"], source["output"], label="test-revision")


def test_restore_can_log_in_read_reports_resume_and_keep_media_private(source, tmp_path, monkeypatch):
    archive = create(source)
    metadata = backup.verify_backup(archive)
    assert metadata["rows"] == {"users": 2, "prescriptions": 2, "exercise_sessions": 2,
                                "behavior_reports": 1, "kb_entries": 1}
    assert metadata["label"] == "test-revision"
    restored = tmp_path / "restored"
    storage, uploads = restored / "storage", restored / "uploads"
    backup.restore_backup(archive, storage, uploads)
    # Recovery must be independent of both the source DB and source media files.
    source["video"].unlink()
    video = uploads / source["video"].relative_to(source["uploads"])
    assert video.read_bytes() == b"synthetic-video-fixture\x00" * 100
    monkeypatch.setattr(media_access, "ROOT", restored)
    monkeypatch.setattr(media_access, "UPLOAD_DIR", uploads)
    engine = create_engine(f"sqlite:///{(storage / 'active_health.db').as_posix()}", connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine)

    def restored_db():
        with factory() as db:
            yield db

    original = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = restored_db
    try:
        # Avoid lifespan: recovery is tested against the restored schema before migrations.
        api = TestClient(app, headers={"X-Requested-With": "ActiveHealth"})
        login = api.post("/auth/login", json={"username": "backup-owner", "password": "test-password"})
        assert login.status_code == 200
        uid = source["owner"]["id"]
        assert api.get("/users/me").json()["id"] == uid
        assert api.get(f"/reports/{source['finished']}").status_code == 200
        current = api.get(f"/sessions/{source['running']}?user_id={uid}").json()["session"]
        assert current["status"] == "running"
        saved = api.put(f"/sessions/{source['running']}/draft?user_id={uid}", json={
            "expected_revision": current["draft_revision"], "pose_summary": {"source": "recovery-test"}})
        assert saved.status_code == 200
        assert saved.json()["session"]["draft_revision"] == current["draft_revision"] + 1
        assert api.get(f"/users/{uid}/sessions/page").json()["total"] == 2
        reference = "uploads/" + video.relative_to(uploads).as_posix()
        assert current["video_path"] == reference
        assert media_access.media_path(reference, uid, must_exist=True).read_bytes() == video.read_bytes()
        assert api.post("/auth/login", json={"username": "backup-other", "password": "test-password"}).status_code == 200
        assert api.get(f"/reports/{source['finished']}").status_code == 404
        assert api.get(f"/sessions/{source['running']}?user_id={uid}").status_code == 404
        with pytest.raises(HTTPException) as error:
            media_access.media_path(reference, source["other"]["id"], must_exist=True)
        assert error.value.status_code == 404
        api.close()
    finally:
        app.dependency_overrides[get_db] = original
        engine.dispose()


def test_snapshot_includes_committed_wal_data(source, tmp_path):
    with closing(sqlite3.connect(source["db"])) as db:
        assert db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        db.execute("UPDATE users SET height_cm=181 WHERE username='backup-owner'")
        db.commit()
        archive = create(source)
        backup.restore_backup(archive, tmp_path / "storage", tmp_path / "uploads")
        with closing(sqlite3.connect(tmp_path / "storage/active_health.db")) as restored:
            assert restored.execute("SELECT height_cm FROM users WHERE username='backup-owner'").fetchone()[0] == 181


@pytest.mark.parametrize("target", ["storage", "uploads"])
def test_restore_refuses_existing_data_without_touching_it(source, tmp_path, target):
    archive = create(source)
    destination = tmp_path / "existing" / target
    destination.mkdir(parents=True)
    sentinel = destination / "keep-me"
    sentinel.write_bytes(b"existing-data")
    with pytest.raises(ValueError, match="空目录"):
        backup.restore_backup(archive, tmp_path / "existing/storage", tmp_path / "existing/uploads")
    assert sentinel.read_bytes() == b"existing-data"
    assert not (tmp_path / "existing/storage/active_health.db").exists()


def rewrite(archive, destination, change):
    with tarfile.open(archive) as source, tarfile.open(destination, "w:gz") as target:
        for member in source:
            data = source.extractfile(member).read()
            member, data = change(member, data)
            member.size = len(data)
            target.addfile(member, io.BytesIO(data))


@pytest.mark.parametrize("failure", ["content", "size", "rows", "missing", "format", "invalid-json", "invalid-database"])
def test_invalid_archives_leave_destinations_untouched(source, tmp_path, failure):
    archive = create(source)
    damaged = tmp_path / "damaged.tar.gz"

    def change(member, data):
        if failure == "content" and member.name.startswith("uploads/"):
            return member, b"x" * len(data)
        if failure == "invalid-database" and member.name == backup.DB_PATH:
            return member, b"x" * len(data)
        if member.name == "manifest.json":
            if failure == "invalid-json":
                return member, b"{"
            meta = json.loads(data)
            if failure == "size":
                meta["files"][backup.DB_PATH]["size"] += 1
            elif failure == "rows":
                meta["rows"]["users"] += 1
            elif failure == "missing":
                meta["files"].pop(backup.DB_PATH)
            elif failure == "format":
                meta["format"] = 999
            elif failure == "invalid-database":
                entry = meta["files"][backup.DB_PATH]
                entry["sha256"] = hashlib.sha256(b"x" * entry["size"]).hexdigest()
            return member, json.dumps(meta).encode()
        return member, data

    rewrite(archive, damaged, change)
    storage, uploads = tmp_path / "target/storage", tmp_path / "target/uploads"
    with pytest.raises((ValueError, sqlite3.Error)):
        backup.restore_backup(damaged, storage, uploads)
    assert not storage.exists() and not uploads.exists()


@pytest.mark.parametrize("name,kind", [("../escape", "file"), ("/escape", "file"),
    ("uploads/../escape", "file"), ("uploads/x:y", "file"), ("uploads\\escape", "file"),
    ("uploads/alias", "symlink"), ("uploads/alias", "hardlink"), (backup.DB_PATH, "duplicate"),
    ("uploads/CON.mp4", "file"), ("uploads/x. ", "file"), ("uploads/x\n", "file")])
def test_unsafe_archive_members_are_rejected(source, tmp_path, name, kind):
    archive = create(source)
    unsafe = tmp_path / "unsafe.tar.gz"
    shutil.copyfile(archive, unsafe)
    # Repack instead of append: gzip tar does not support append mode.
    with tarfile.open(archive) as src, tarfile.open(unsafe, "w:gz") as dst:
        for member in src:
            dst.addfile(member, src.extractfile(member))
        extra = tarfile.TarInfo(name)
        if kind in {"symlink", "hardlink"}:
            extra.type = tarfile.SYMTYPE if kind == "symlink" else tarfile.LNKTYPE
            extra.linkname = "../../outside"
        dst.addfile(extra, io.BytesIO(b""))
    with pytest.raises(ValueError):
        backup.restore_backup(unsafe, tmp_path / "target/storage", tmp_path / "target/uploads")
    assert not (tmp_path / "target").exists()


def test_truncated_archive_fails_and_cli_returns_nonzero(source, tmp_path, capsys):
    archive = create(source)
    damaged = tmp_path / "truncated.tar.gz"
    damaged.write_bytes(archive.read_bytes()[:100])
    assert backup.main(["verify", str(damaged)]) == 1
    assert "操作失败" in capsys.readouterr().err


def test_failed_restore_cleans_up_its_own_files(source, tmp_path, monkeypatch):
    archive = create(source)
    storage, uploads = tmp_path / "target/storage", tmp_path / "target/uploads"
    storage.mkdir(parents=True)
    uploads.mkdir()
    original = shutil.copyfileobj

    def fail_on_upload(reader, output, *args, **kwargs):
        if str(output.name).startswith(str(uploads)):
            output.write(b"incomplete")
            raise OSError("simulated disk full")
        return original(reader, output, *args, **kwargs)

    monkeypatch.setattr(backup.shutil, "copyfileobj", fail_on_upload)
    with pytest.raises(OSError, match="disk full"):
        backup.restore_backup(archive, storage, uploads)
    assert list(storage.iterdir()) == list(uploads.iterdir()) == []


def test_empty_uploads_restore_and_backup_does_not_overwrite(source, tmp_path):
    source["video"].unlink()
    first, second = create(source), create(source)
    assert first != second and first.exists() and second.exists()
    backup.restore_backup(first, tmp_path / "storage", tmp_path / "uploads")
    assert (tmp_path / "uploads").is_dir()
    assert backup.main(["verify", str(first)]) == 0


def test_bad_source_and_recursive_destination_do_not_produce_archives(source):
    with pytest.raises(ValueError, match="之外"):
        backup.create_backup(source["db"], source["uploads"], source["uploads"] / "backups")
    source["db"].write_bytes(b"invalid SQLite")
    with pytest.raises(sqlite3.Error):
        create(source)
    assert not list(source["output"].glob("*.tar.gz"))
    assert not list(source["output"].glob("*.partial"))


def test_all_cli_commands_work_without_importing_backend(source, tmp_path):
    def run(*arguments):
        result = subprocess.run([sys.executable, backup.__file__, *map(str, arguments)],
                                cwd=tmp_path, capture_output=True, timeout=30)
        assert result.returncode == 0, result.stderr.decode(errors="replace")

    run("create", "--database", source["db"], "--uploads", source["uploads"], "--output-dir", source["output"])
    archive = next(source["output"].glob("*.tar.gz"))
    run("verify", archive)
    run("restore", archive, "--storage", tmp_path / "cli/storage", "--uploads", tmp_path / "cli/uploads")
    assert (tmp_path / "cli/storage/active_health.db").is_file()
    assert (tmp_path / "cli/uploads" / source["video"].relative_to(source["uploads"])).read_bytes() == source["video"].read_bytes()


@pytest.mark.parametrize("failure", ["changed-file", "read-error"])
def test_interrupted_backup_never_publishes_a_partial_archive(source, monkeypatch, failure):
    original = backup._HashReader.read

    def fail_read(reader, size=-1):
        data = original(reader, size)
        if str(reader.source.name) == str(source["video"]):
            if failure == "read-error":
                raise OSError("simulated read failure")
            with source["video"].open("ab") as output:
                output.write(b"changed-during-backup")
        return data

    monkeypatch.setattr(backup._HashReader, "read", fail_read)
    with pytest.raises((ValueError, OSError)):
        create(source)
    assert list(source["output"].iterdir()) == []
