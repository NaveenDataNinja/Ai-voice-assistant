import sqlite3
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


@contextmanager
def database(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, due TEXT,
                done INTEGER NOT NULL DEFAULT 0,
                acknowledged INTEGER NOT NULL DEFAULT 0
            )
        """)
        with connection:
            yield connection
    finally:
        connection.close()


def validate_task(data):
    if not isinstance(data, dict):
        raise ValueError("A task must be an object.")
    title = data.get("title")
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 160:
        raise ValueError("Task names must be 1 to 160 characters.")
    due = data.get("due")
    if due is not None:
        if not isinstance(due, str):
            raise ValueError("Enter a valid reminder time with a timezone.")
        try:
            parsed = datetime.fromisoformat(due.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("A timezone is required.")
            due = parsed.astimezone(timezone.utc).isoformat()
        except (ValueError, OverflowError) as error:
            raise ValueError("Enter a valid reminder time with a timezone.") from error
    task_id = data.get("id", str(uuid.uuid4()))
    if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", task_id):
        raise ValueError("The task ID is invalid.")
    done = data.get("done", False)
    if not isinstance(done, bool):
        raise ValueError("Task completion must be true or false.")
    return {"id": task_id, "title": title.strip(), "due": due, "done": done}


def as_task(row):
    result = dict(row)
    result["done"] = bool(result["done"])
    result["acknowledged"] = bool(result["acknowledged"])
    return result


def list_tasks(path):
    with database(path) as connection:
        return [as_task(row) for row in connection.execute("SELECT * FROM tasks ORDER BY rowid")]


def insert_task(connection, data):
    existing = connection.execute("SELECT * FROM tasks WHERE id = ?", (data["id"],)).fetchone()
    if existing:
        if existing["title"] != data["title"] or existing["due"] != data["due"]:
            raise ValueError("That task ID is already used by a different task.")
        return as_task(existing)
    if connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] >= 100:
        raise ValueError("The task list is full. Delete a task before adding another.")
    connection.execute(
        "INSERT INTO tasks (id, title, due, done) VALUES (?, ?, ?, ?)",
        (data["id"], data["title"], data["due"], data["done"]),
    )
    return {**data, "acknowledged": False}


def add_task(path, data):
    task = validate_task(data)
    with database(path) as connection:
        return insert_task(connection, task)


def import_tasks(path, items):
    if not isinstance(items, list) or len(items) > 100:
        raise ValueError("Import at most 100 tasks at a time.")
    tasks = [validate_task(item) for item in items]
    with database(path) as connection:
        for task in tasks:
            insert_task(connection, task)


def update_task(path, task_id, changes):
    if not isinstance(changes, dict) or not changes or set(changes) - {"done", "acknowledged"}:
        raise ValueError("Only task completion and reminder acknowledgement can be changed.")
    if any(not isinstance(value, bool) for value in changes.values()):
        raise ValueError("Task changes must be true or false.")
    with database(path) as connection:
        if not connection.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone():
            return None
        for key, value in changes.items():
            connection.execute(f"UPDATE tasks SET {key} = ? WHERE id = ?", (value, task_id))
        return as_task(connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())


def delete_task(path, task_id):
    with database(path) as connection:
        return connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,)).rowcount > 0
