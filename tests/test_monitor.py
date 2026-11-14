import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask, jsonify

from app_monitor import AppMonitor, read_status, write_report


class MonitorTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        app = Flask(__name__)
        app.config["TASK_DATABASE"] = str(self.root / "tasks.sqlite3")
        self.monitor = AppMonitor(app, root=self.root)

        @app.post("/api/example")
        def example():
            return jsonify(ok=True)

        @app.patch("/api/tasks/<task_id>")
        def task(task_id):
            return jsonify(ok=True)

        self.client = app.test_client()

    def test_request_stages_are_correlated_without_recording_payloads(self):
        private_text = "private-recording-and-chat-content"
        response = self.client.post("/api/example", json={"message": private_text})
        snapshot = self.client.get("/api/monitor").json
        self.assertEqual(snapshot["runtime"]["requests"], 1)
        self.assertEqual(self.client.get("/api/monitor").json["runtime"]["requests"], 1)
        request_events = [event for event in snapshot["events"] if event["request_id"] == response.headers["X-Request-ID"]]
        self.assertEqual([event["stage"] for event in request_events], ["request.received", "request.finished"])
        self.assertNotIn(private_text, json.dumps(snapshot))
        self.assertNotIn(str(self.root), json.dumps(snapshot))
        self.client.patch("/api/tasks/private-task-identifier", json={"title": private_text})
        snapshot = self.client.get("/api/monitor").json
        self.assertIn("/api/tasks/<task_id>", json.dumps(snapshot))
        self.assertNotIn("private-task-identifier", json.dumps(snapshot))

    def test_file_changes_are_allowlisted_and_events_are_bounded(self):
        (self.root / "static").mkdir()
        (self.root / "static" / "app.js").write_text("private source content", encoding="utf-8")
        (self.root / ".env").write_text("private credentials", encoding="utf-8")
        snapshot = self.monitor.snapshot()
        self.assertEqual([item["file"] for item in snapshot["files"]], ["static\\app.js"])
        self.assertNotIn("private source content", json.dumps(snapshot))
        self.assertNotIn("private credentials", json.dumps(snapshot))
        for _ in range(220):
            self.monitor.record("test.event", "Non-sensitive fixture event")
        self.assertEqual(len(self.monitor.snapshot()["events"]), 200)

    def test_verification_reports_are_explicit_and_persistent(self):
        path = self.root / "verification.json"
        self.assertEqual(self.monitor.snapshot()["verification"]["status"], "not_run")
        write_report(path, {"status": "running", "completed": 2, "total": 3})
        self.assertEqual(self.monitor.snapshot()["verification"]["completed"], 2)
        write_report(path, {"status": "failed", "completed": 3, "total": 3, "failed": 1})
        self.assertEqual(self.monitor.snapshot()["verification"]["status"], "failed")
        path.write_text("{invalid", encoding="utf-8")
        self.assertEqual(read_status(path, {})["status"], "error")
        for malformed in [{}, {"status": "running", "steps": {}}, {"status": "running", "steps": [None]}, {"status": "running", "limitations": [1]}]:
            write_report(path, malformed)
            self.assertEqual(read_status(path, {})["status"], "error")

    def test_report_updates_retry_temporary_windows_locks_but_surface_permanent_errors(self):
        path = self.root / "verification.json"
        replace = os.replace
        attempts = []

        def temporarily_locked(source, destination):
            attempts.append(destination)
            if len(attempts) == 1:
                raise PermissionError("Temporary test reader lock")
            return replace(source, destination)

        with patch("app_monitor.os.replace", side_effect=temporarily_locked), patch("app_monitor.time.sleep"):
            write_report(path, {"status": "passed"})
        self.assertEqual(read_status(path, {})["status"], "passed")
        self.assertEqual(len(attempts), 2)
        with patch("app_monitor.os.replace", side_effect=PermissionError("Permanent test permission error")) as failing_replace, patch("app_monitor.time.sleep"):
            with self.assertRaises(PermissionError):
                write_report(path, {"status": "failed"})
        self.assertEqual(failing_replace.call_count, 6)
        self.assertEqual(list(self.root.glob("verification-*.json")), [])
