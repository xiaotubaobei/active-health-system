"""Offline SQLite + uploads backup, verification and restore (Python standard library only).

Stop the application before create/restore so database references and uploads agree.
Restore only accepts empty destinations; it never overwrites an existing installation.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import sqlite3
import stat
import sys
import tarfile
import tempfile
import time
from uuid import uuid4


TABLES = ("users", "prescriptions", "exercise_sessions", "behavior_reports", "kb_entries")
DB_PATH = "storage/active_health.db"
MANIFEST_LIMIT = 4_000_000


def _database_summary(path):
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("SQLite 完整性检查失败")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("数据库存在失效的关联记录")
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not set(TABLES).issubset(tables):
            raise ValueError("不是本系统的完整数据库，拒绝备份或恢复")
        return {table: db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in TABLES}


def _safe_name(name):
    parts = PurePosixPath(name).parts
    # Portable names avoid traversal and Windows path/alternate-stream aliases.
    if (not parts or PurePosixPath(name).as_posix() != name
            or any(p in {".", ".."} or p.endswith((".", " ")) or PureWindowsPath(p).is_reserved() for p in parts)
            or any(c in name for c in '\\:<>"|?*') or any(ord(c) < 32 for c in name)
            or name.startswith("/")
            or (name != DB_PATH and not (len(parts) > 1 and parts[0] == "uploads"))):
        raise ValueError(f"归档包含不支持的文件路径：{name!r}")
    return name


def _regular(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f"只允许普通文件，不支持链接或特殊文件：{path}")


class _HashReader:
    def __init__(self, source):
        self.source = source
        self.digest = hashlib.sha256()

    def read(self, size=-1):
        data = self.source.read(size)
        self.digest.update(data)
        return data


def create_backup(database, uploads, output_dir, *, label=""):
    database, uploads, output_dir = map(Path, (database, uploads, output_dir))
    _regular(database)
    if uploads.is_symlink() or not uploads.is_dir():
        raise ValueError("上传目录不存在或是符号链接")
    if output_dir.resolve().is_relative_to(uploads.resolve()):
        raise ValueError("备份目录必须放在上传目录之外")
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = output_dir / f"health-{stamp}-{uuid4().hex[:8]}.tar.gz"
    partial = archive.with_suffix(".partial")
    try:
        with tempfile.TemporaryDirectory(prefix=".backup-", dir=output_dir) as temp:
            snapshot = Path(temp) / "active_health.db"
            deadline = time.monotonic() + 60

            def progress(*_):
                if time.monotonic() > deadline:
                    raise ValueError("数据库快照超时，请确认服务已停止后重试")

            # SQLite's backup API includes committed WAL data; copying only .db does not.
            with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as source:
                with closing(sqlite3.connect(snapshot)) as target:
                    source.backup(target, pages=256, progress=progress)
                    target.execute("PRAGMA journal_mode=DELETE")
            manifest = {"format": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                        "label": label, "rows": _database_summary(snapshot), "files": {}}
            files = [(snapshot, DB_PATH)]
            for path in sorted(uploads.rglob("*")):
                if path.is_symlink():
                    raise ValueError(f"上传目录不能包含链接：{path}")
                if not path.is_dir():
                    files.append((path, "uploads/" + path.relative_to(uploads).as_posix()))
            names = set()
            with open(os.open(partial, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as output:
                with tarfile.open(fileobj=output, mode="w:gz") as tar:
                    for path, name in files:
                        _safe_name(name)
                        if name.casefold() in names:
                            raise ValueError("文件名大小写冲突，无法跨系统恢复")
                        names.add(name.casefold())
                        _regular(path)
                        with path.open("rb") as source:
                            before = os.fstat(source.fileno())
                            reader = _HashReader(source)
                            info = tarfile.TarInfo(name)
                            info.size, info.mode = before.st_size, 0o600
                            tar.addfile(info, reader)
                            after = os.fstat(source.fileno())
                        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                            raise ValueError("备份期间文件发生变化，请先停止服务")
                        manifest["files"][name] = {"size": info.size, "sha256": reader.digest.hexdigest()}
                    data = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
                    if len(data) > MANIFEST_LIMIT:
                        raise ValueError("文件清单过大，超出当前试用备份工具的支持范围")
                    info = tarfile.TarInfo("manifest.json")
                    info.size, info.mode = len(data), 0o600
                    tar.addfile(info, io.BytesIO(data))
                output.flush()
                os.fsync(output.fileno())
        verify_backup(partial)
        partial.rename(archive)
        return archive
    finally:
        partial.unlink(missing_ok=True)


def _read_archive(archive, stage):
    """Validate first; copy only regular, explicitly listed files into a private stage."""
    with tarfile.open(archive, "r:gz") as tar:
        members = {}
        folded = set()
        for member in tar:
            if not member.isfile() or member.name in members or member.name.casefold() in folded:
                raise ValueError("归档包含链接、特殊文件或重复路径")
            if member.name != "manifest.json":
                _safe_name(member.name)
            members[member.name] = member
            folded.add(member.name.casefold())
        meta = members.pop("manifest.json", None)
        if not meta or meta.size > MANIFEST_LIMIT:
            raise ValueError("归档缺少有效清单；旧手工归档不支持直接恢复")
        with tar.extractfile(meta) as source:
            manifest = json.loads(source.read(MANIFEST_LIMIT + 1))
        if not isinstance(manifest, dict) or manifest.get("format") != 1:
            raise ValueError("备份格式不受支持")
        files = manifest.get("files")
        if not isinstance(files, dict) or set(files) != set(members) or DB_PATH not in files:
            raise ValueError("备份文件与清单不一致")
        for name, member in members.items():
            expected = files[name]
            if (not isinstance(expected, dict) or type(expected.get("size")) is not int
                    or expected["size"] != member.size
                    or not re.fullmatch(r"[a-f0-9]{64}", str(expected.get("sha256", "")))):
                raise ValueError("备份文件大小或校验信息不正确")
            destination = stage / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as source, destination.open("xb") as output:
                reader = _HashReader(source)
                shutil.copyfileobj(reader, output, length=1024 * 1024)
            if reader.digest.hexdigest() != expected["sha256"]:
                raise ValueError(f"备份文件校验失败：{name}")
        if _database_summary(stage / DB_PATH) != manifest.get("rows"):
            raise ValueError("数据库记录数量与备份清单不一致")
        return manifest


def verify_backup(archive):
    with tempfile.TemporaryDirectory(prefix="health-verify-") as temp:
        return _read_archive(archive, Path(temp))


def restore_backup(archive, storage, uploads):
    storage, uploads = Path(storage).absolute(), Path(uploads).absolute()
    if storage.resolve().is_relative_to(uploads.resolve()) or uploads.resolve().is_relative_to(storage.resolve()):
        raise ValueError("数据库和上传目录不能相同或互相包含")
    for path in (storage, uploads):
        if path.is_symlink() or (path.exists() and (not path.is_dir() or any(path.iterdir()))):
            raise ValueError(f"恢复只允许空目录，现有数据保持不动：{path}")
    # No destination writes until the complete archive and SQLite have passed checks.
    with tempfile.TemporaryDirectory(prefix="health-restore-") as temp:
        stage = Path(temp)
        manifest = _read_archive(archive, stage)
        created_files, created_dirs = [], []
        try:
            for name in manifest["files"]:
                destination = storage / "active_health.db" if name == DB_PATH else uploads.joinpath(*PurePosixPath(name).parts[1:])
                missing = []
                parent = destination.parent
                while not parent.exists():
                    missing.append(parent)
                    parent = parent.parent
                for directory in reversed(missing):
                    directory.mkdir(mode=0o700)
                    created_dirs.append(directory)
                with open(destination, "xb", opener=lambda path, flags: os.open(path, flags, 0o600)) as output:
                    created_files.append(destination)
                    with (stage / name).open("rb") as source:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
            if not uploads.exists():
                uploads.mkdir(parents=True, mode=0o700)
        except BaseException:
            # Only remove files this attempt created; never recursively delete a target.
            for path in reversed(created_files):
                path.unlink(missing_ok=True)
            for path in reversed(created_dirs):
                try:
                    path.rmdir()
                except OSError:
                    pass
            raise
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="停站后备份数据库和上传文件")
    create.add_argument("--database", type=Path, default=Path("/app/storage/active_health.db"))
    create.add_argument("--uploads", type=Path, default=Path("/app/uploads"))
    create.add_argument("--output-dir", type=Path, required=True)
    create.add_argument("--label", default="", help="可记录当前代码提交编号")
    verify = commands.add_parser("verify", help="只检查备份，不修改现有数据")
    verify.add_argument("archive", type=Path)
    restore = commands.add_parser("restore", help="停站后恢复到全新的空目录/空数据卷")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--storage", type=Path, default=Path("/app/storage"))
    restore.add_argument("--uploads", type=Path, default=Path("/app/uploads"))
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            archive = create_backup(args.database, args.uploads, args.output_dir, label=args.label)
            print(f"备份完成并通过校验：{archive}")
        else:
            manifest = verify_backup(args.archive) if args.command == "verify" else restore_backup(args.archive, args.storage, args.uploads)
            print("校验通过。" if args.command == "verify" else "已恢复到空目录；请使用备份时的代码启动并重新验收。")
            print(json.dumps({"created_at": manifest.get("created_at"), "label": manifest.get("label"),
                              "rows": manifest["rows"], "files": len(manifest["files"])}, ensure_ascii=False))
    except (ValueError, OSError, sqlite3.Error, tarfile.TarError, EOFError) as error:
        print(f"操作失败：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
