import json
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path

import priya_data
import task_store


class DataMigrationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.source = self.root / "source" / "tasks.sqlite3"
        self.archive = self.root / "backup.zip"
        self.restored = self.root / "restored" / "tasks.sqlite3"
        task = task_store.add_task(self.source, {"title": "Private migration fixture", "due": "2026-11-15T10:00:00+00:00"})
        task_store.update_task(self.source, task["id"], {"done": True, "acknowledged": True})

    def test_backup_restore_preserves_tasks_and_does_not_store_source_paths(self):
        self.assertEqual(priya_data.backup_tasks(self.source, self.archive), 1)
        with zipfile.ZipFile(self.archive) as bundle:
            self.assertNotIn(str(self.root), bundle.read("manifest.json").decode())
        self.assertEqual(priya_data.restore_tasks(self.archive, self.restored), 1)
        self.assertEqual(task_store.list_tasks(self.source), task_store.list_tasks(self.restored))
        with self.assertRaises(FileExistsError):
            priya_data.backup_tasks(self.source, self.archive)

    def test_restore_refuses_existing_data_without_changes(self):
        priya_data.backup_tasks(self.source, self.archive)
        before = self.source.read_bytes()
        with self.assertRaises(FileExistsError):
            priya_data.restore_tasks(self.archive, self.source)
        self.assertEqual(self.source.read_bytes(), before)

    def test_restore_rejects_tampered_payload_and_unexpected_archive_paths(self):
        priya_data.backup_tasks(self.source, self.archive)
        with zipfile.ZipFile(self.archive) as bundle:
            content, manifest = bundle.read("tasks.sqlite3"), json.loads(bundle.read("manifest.json"))
        for index, extra in enumerate((False, True)):
            invalid = self.root / f"invalid-{index}.zip"
            with zipfile.ZipFile(invalid, "w") as bundle:
                bundle.writestr("tasks.sqlite3", content if extra else content + b"changed")
                bundle.writestr("manifest.json", json.dumps(manifest))
                if extra:
                    bundle.writestr(f"../{self.root.name}-unexpected", "must not extract")
            with self.assertRaises(ValueError):
                priya_data.restore_tasks(invalid, self.restored)
        self.assertFalse(self.restored.exists())
        self.assertFalse((self.root.parent / f"{self.root.name}-unexpected").exists())

    def test_backup_rejects_missing_or_incompatible_databases(self):
        with self.assertRaises(FileNotFoundError):
            priya_data.backup_tasks(self.root / "missing.sqlite3", self.archive)
        invalid = self.root / "incompatible.sqlite3"
        with closing(sqlite3.connect(invalid)) as database:
            database.execute("CREATE TABLE unrelated (id INTEGER)")
        with self.assertRaises(ValueError):
            priya_data.backup_tasks(invalid, self.archive)
        self.assertFalse(self.archive.exists())
