import os
import re
import secrets
import unittest
from unittest.mock import patch

from flask import Flask
from werkzeug.security import generate_password_hash

import web_app
from web_access import configure_access


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.password = secrets.token_urlsafe(24)
        config = patch.dict(web_app.app.config, {
            "PASSWORD_HASH": generate_password_hash(self.password),
            "SECRET_KEY": secrets.token_hex(32),
            "RATE_LIMITS_ENABLED": False, "SESSION_COOKIE_SECURE": True,
        })
        config.start()
        self.addCleanup(config.stop)
        self.client = web_app.app.test_client()

    def token(self):
        response = self.client.get("/login", base_url="https://localhost")
        return re.search(r'name="csrf_token" value="([^"]+)"', response.text)[1]

    def test_login_csrf_logout_and_protected_api(self):
        self.assertEqual(self.client.get("/api/tasks", base_url="https://localhost").status_code, 401)
        self.assertEqual(self.client.get("/api/monitor", base_url="https://localhost").status_code, 401)
        self.assertEqual(self.client.get("/healthz", base_url="https://localhost").status_code, 200)
        token = self.token()
        self.assertEqual(self.client.post("/login", data={"password": self.password}, base_url="https://localhost").status_code, 403)
        response = self.client.post("/login", data={"password": self.password, "csrf_token": token}, base_url="https://localhost")
        self.assertEqual(response.status_code, 302)
        self.assertIn("Secure", response.headers["Set-Cookie"])
        with self.client.session_transaction() as session:
            token = session["csrf"]
        self.assertEqual(self.client.post("/api/chat", json={"message": "time"}, base_url="https://localhost").status_code, 403)
        self.assertEqual(self.client.post("/api/chat", json={"message": "time"}, headers={"X-CSRF-Token": token}, base_url="https://localhost").status_code, 200)
        self.assertEqual(self.client.post("/logout", data={"csrf_token": token}, base_url="https://localhost").status_code, 302)
        self.assertEqual(self.client.get("/api/tasks", base_url="https://localhost").status_code, 401)

    def test_login_attempts_are_bounded(self):
        web_app.app.config["RATE_LIMITS_ENABLED"] = True
        token = self.token()
        for _ in range(5):
            response = self.client.post("/login", data={"password": "incorrect", "csrf_token": token}, base_url="https://localhost", environ_overrides={"REMOTE_ADDR": "192.0.2.83"})
            self.assertEqual(response.status_code, 401)
        response = self.client.post("/login", data={"password": "incorrect", "csrf_token": token}, base_url="https://localhost", environ_overrides={"REMOTE_ADDR": "192.0.2.83"})
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)

    def test_production_refuses_missing_credentials(self):
        with patch.dict(os.environ, {"PRIYA_ENV": "production", "PRIYA_PASSWORD_HASH": "", "PRIYA_SESSION_SECRET": ""}):
            with self.assertRaises(RuntimeError):
                configure_access(Flask(__name__))

    def test_expensive_api_requests_are_rate_limited(self):
        web_app.app.config.update(PASSWORD_HASH="", RATE_LIMITS_ENABLED=True)
        for _ in range(30):
            response = self.client.post("/api/chat", json={"message": "time"}, environ_overrides={"REMOTE_ADDR": "192.0.2.84"})
            self.assertEqual(response.status_code, 200)
        response = self.client.post("/api/chat", json={"message": "time"}, environ_overrides={"REMOTE_ADDR": "192.0.2.84"})
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)
