import argparse
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from flask import g, has_request_context, jsonify, request


ROOT = Path(__file__).resolve().parent
WATCHED_FILES = (
    "web_app.py", "assistant_services.py", "action_router.py", "task_store.py",
    "web_access.py", "app_monitor.py", "web-requirements.txt", "Dockerfile", "README.md",
    "templates\\index.html", "templates\\login.html", "static\\app.js", "static\\api.js",
    "static\\tasks.js", "static\\studio.js", "static\\style.css", "static\\monitor.js",
    "tests\\test_web_app.py", "tests\\test_access.py", "tests\\test_monitor.py",
    "development_status.json",
    "setup.ps1", "start.ps1", "priya_data.py", "requirements-windows-py311.lock.txt",
    "tests\\test_priya_data.py", "docs\\NEW_LAPTOP_WINDOWS.md",
    ".github\\workflows\\windows-checks.yml",
)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def read_status(path, missing):
    try:
        with Path(path).open(encoding="utf-8") as source:
            content = source.read(65537)
        if len(content) > 65536:
            return {"status": "error", "message": "The monitoring report exceeds its size limit."}
        result = json.loads(content)
        if not isinstance(result, dict) or not isinstance(result.get("status"), str):
            return {"status": "error", "message": "The monitoring report must be an object with a status."}
        if "steps" in result and (
            not isinstance(result["steps"], list)
            or any(not isinstance(step, dict) or any(not isinstance(step.get(key), str) for key in ("name", "status", "evidence")) for step in result["steps"])
        ):
            return {"status": "error", "message": "The development steps have an invalid format."}
        if "limitations" in result and (
            not isinstance(result["limitations"], list)
            or any(not isinstance(item, str) for item in result["limitations"])
        ):
            return {"status": "error", "message": "The development limitations have an invalid format."}
        return result
    except FileNotFoundError:
        return missing
    except (OSError, ValueError):
        return {"status": "error", "message": "The monitoring report could not be read."}


class AppMonitor:
    def __init__(self, app, root=ROOT):
        self.root = Path(root)
        self.report_path = Path(app.config["TASK_DATABASE"]).parent / "verification.json"
        self.lock = threading.RLock()
        self.events = deque(maxlen=200)
        self.sequence = 0
        self.started_at = timestamp()
        self.requests = 0
        self.errors = 0
        self.setup_ms = 0
        self.active_streams = 0
        self.file_state = {}
        self.changed_files = {}
        self.scan_files(initial=True)
        self.record("server.started", "Monitoring started. The file baseline is this server start, not historical edit history.")

        @app.before_request
        def monitor_request():
            g.request_id = uuid.uuid4().hex[:12]
            g.monitor_started = time.monotonic()
            if self.tracked_request():
                self.record("request.received", f"{request.method} {self.route_name()}")

        @app.after_request
        def monitor_response(response):
            response.headers["X-Request-ID"] = getattr(g, "request_id", "")
            if self.tracked_request():
                duration = round((time.monotonic() - g.monitor_started) * 1000)
                streaming = response.mimetype == "application/x-ndjson"
                with self.lock:
                    self.requests += 1
                    self.errors += int(response.status_code >= 400)
                    self.setup_ms += duration
                self.record(
                    "response.streaming" if streaming else "request.finished",
                    f"{request.method} {self.route_name()} HTTP {response.status_code}; "
                    f"{duration} ms {'to stream headers' if streaming else 'to response'}",
                    "error" if response.status_code >= 400 else "ok",
                )
            return response

        @app.get("/api/monitor")
        def monitor_state():
            return jsonify(self.snapshot())

    @staticmethod
    def route_name():
        return request.url_rule.rule if request.url_rule else "/unknown"

    @staticmethod
    def tracked_request():
        return request.path.startswith("/api/") and request.endpoint not in {"monitor_state", "session_token", "service_status"}

    def record(self, stage, detail, status="info"):
        with self.lock:
            self.sequence += 1
            self.events.append({
                "id": self.sequence, "time": timestamp(), "stage": stage, "detail": detail,
                "status": status, "request_id": getattr(g, "request_id", None) if has_request_context() else None,
            })

    def stream_started(self):
        with self.lock:
            self.active_streams += 1
        self.record("ai.started", "Local model generation started; displayed tokens are a draft until completion.")

    def stream_finished(self, outcome, duration):
        with self.lock:
            self.active_streams -= 1
        self.record(f"ai.{outcome}", f"Model stream {outcome}; {duration} ms total generation time.",
                    "error" if outcome == "failed" else ("ok" if outcome == "completed" else "info"))

    def scan_files(self, initial=False):
        with self.lock:
            for name in WATCHED_FILES:
                # The allowlist uses portable components; no arbitrary client paths are accepted.
                path = self.root.joinpath(*name.split("\\"))
                try:
                    stat = path.stat()
                    state = (stat.st_mtime_ns, stat.st_size)
                except FileNotFoundError:
                    state = None
                except OSError:
                    self.record("development.scan_error", f"Could not inspect allowlisted file {name}.", "error")
                    continue
                if not initial and self.file_state.get(name) != state:
                    change = "removed" if state is None else ("added" if self.file_state.get(name) is None else "modified")
                    self.changed_files[name] = {"file": name, "change": change, "detected_at": timestamp()}
                    self.record("development.file_changed", f"{name} {change}. Server-side Python changes require a restart.")
                self.file_state[name] = state

    def snapshot(self):
        self.scan_files()
        with self.lock:
            runtime = {
                "started_at": self.started_at, "requests": self.requests, "errors": self.errors,
                "average_setup_ms": round(self.setup_ms / self.requests, 1) if self.requests else None,
                "active_ai_streams": self.active_streams,
            }
            events = list(self.events)
            changes = list(self.changed_files.values())
        return {
            "observed_at": timestamp(),
            "runtime": runtime, "events": events, "files": changes,
            "development": read_status(self.root / "development_status.json", {"status": "not_configured"}),
            "verification": read_status(self.report_path, {"status": "not_run", "message": "No automated run has been recorded yet."}),
            "privacy": "No prompts, replies, recordings, credentials, source contents, or hidden AI reasoning are collected.",
        }


def write_report(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix="verification-", suffix=".json", delete=False) as target:
            temporary = Path(target.name)
            json.dump(data, target)
        for attempt in range(6):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 5:
                    raise
                # Windows readers or antivirus can briefly block an atomic replacement.
                time.sleep(0.05 * (attempt + 1))
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def run_tests():
    path = Path(os.environ.get("PRIYA_DATA_DIR", str(Path.home() / ".priya"))) / "verification.json"
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT / "tests"))
    report = {
        "status": "running", "started_at": timestamp(), "total": suite.countTestCases(),
        "completed": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0,
        "last_test": None, "command": "python -m app_monitor --test", "recent": [],
    }

    class LiveResult(unittest.TextTestResult):
        def startTest(self, test):
            super().startTest(test)
            report["last_test"] = test.id()
            write_report(path, report)

        def stopTest(self, test):
            super().stopTest(test)
            report.update(
                completed=self.testsRun, failed=len(self.failures), errors=len(self.errors),
                skipped=len(self.skipped),
                passed=self.testsRun - len(self.failures) - len(self.errors) - len(self.skipped),
            )
            report["recent"] = (report["recent"] + [test.id()])[-10:]
            write_report(path, report)

    write_report(path, report)
    try:
        result = unittest.TextTestRunner(verbosity=1, resultclass=LiveResult).run(suite)
    except (KeyboardInterrupt, OSError):
        report.update(status="interrupted", finished_at=timestamp())
        write_report(path, report)
        raise
    report.update(status="passed" if result.wasSuccessful() else "failed", finished_at=timestamp())
    write_report(path, report)
    return result.wasSuccessful()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Priya's existing unittest suite with live, non-sensitive progress reporting.")
    parser.add_argument("--test", action="store_true", required=True)
    parser.parse_args()
    sys.exit(0 if run_tests() else 1)
