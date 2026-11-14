import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


MAX_DATABASE_BYTES = 8 * 1024 * 1024


def validate_database(path):
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as database:
        if database.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise ValueError("The task database failed its integrity check.")
        columns = {row[1] for row in database.execute("PRAGMA table_info(tasks)")}
        if columns != {"id", "title", "due", "done", "acknowledged"}:
            raise ValueError("This is not a supported Priya task database.")
        count = database.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if not 0 <= count <= 100:
            raise ValueError("The task count is outside the supported range.")
        return count


def backup_tasks(source, archive):
    source, archive = Path(source), Path(archive)
    if not source.is_file():
        raise FileNotFoundError("No task database exists at the selected data directory. No backup was created.")
    if archive.exists():
        raise FileExistsError("The backup destination already exists. Choose a new filename.")
    with tempfile.TemporaryDirectory(prefix="priya-backup-") as directory:
        snapshot = Path(directory) / "tasks.sqlite3"
        with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as original:
            with closing(sqlite3.connect(snapshot)) as destination:
                original.backup(destination)
        count = validate_database(snapshot)
        if snapshot.stat().st_size > MAX_DATABASE_BYTES:
            raise ValueError("The task database exceeds the supported 8 MiB backup size.")
        content = snapshot.read_bytes()
        manifest = {
            "format": "priya-tasks-v1", "created_at": datetime.now(timezone.utc).isoformat(),
            "task_count": count, "sha256": hashlib.sha256(content).hexdigest(),
        }
        archive.parent.mkdir(parents=True, exist_ok=True)
        with archive.open("xb") as output:
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                bundle.writestr("tasks.sqlite3", content)
                bundle.writestr("manifest.json", json.dumps(manifest))
    return count


def restore_tasks(archive, destination):
    archive, destination = Path(archive), Path(destination)
    if destination.exists():
        raise FileExistsError("A task database already exists. Stop the app and choose a new empty PRIYA_DATA_DIR; restore never overwrites existing tasks.")
    with zipfile.ZipFile(archive) as bundle:
        if len(bundle.namelist()) != 2 or set(bundle.namelist()) != {"tasks.sqlite3", "manifest.json"}:
            raise ValueError("The backup must contain only tasks.sqlite3 and manifest.json.")
        if bundle.getinfo("tasks.sqlite3").file_size > MAX_DATABASE_BYTES or bundle.getinfo("manifest.json").file_size > 65536:
            raise ValueError("The backup exceeds the supported size.")
        content = bundle.read("tasks.sqlite3")
        manifest = json.loads(bundle.read("manifest.json"))
    if not isinstance(manifest, dict) or manifest.get("format") != "priya-tasks-v1":
        raise ValueError("The backup format is not supported.")
    if hashlib.sha256(content).hexdigest() != manifest.get("sha256"):
        raise ValueError("The backup checksum does not match. Do not restore this file.")
    with tempfile.TemporaryDirectory(prefix="priya-restore-") as directory:
        snapshot = Path(directory) / "tasks.sqlite3"
        snapshot.write_bytes(content)
        count = validate_database(snapshot)
    if type(manifest.get("task_count")) is not int or count != manifest["task_count"]:
        raise ValueError("The backup task count does not match.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with destination.open("xb") as output:
            created = True
            output.write(content)
    except OSError:
        if created:
            destination.unlink(missing_ok=True)
        raise
    return count


def main():
    parser = argparse.ArgumentParser(description="Back up or restore Priya tasks privately; never upload the backup to Git.")
    actions = parser.add_subparsers(dest="action", required=True)
    for action, option in (("backup", "--output"), ("restore", "--input")):
        command = actions.add_parser(action)
        command.add_argument(option, required=True, type=Path)
        command.add_argument("--data-dir", type=Path, default=Path(os.environ.get("PRIYA_DATA_DIR", str(Path.home() / ".priya"))))
    args = parser.parse_args()
    try:
        if args.action == "backup":
            count = backup_tasks(args.data_dir / "tasks.sqlite3", args.output)
            print(f"Private backup created: {args.output} ({count} tasks). Unencrypted: transfer securely; do not upload to Git.")
        else:
            count = restore_tasks(args.input, args.data_dir / "tasks.sqlite3")
            print(f"Restored {count} tasks. Use this same data directory when starting Priya.")
    except (OSError, ValueError, sqlite3.Error, zipfile.BadZipFile, KeyError) as error:
        parser.exit(1, f"Task migration failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
