import hmac
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta

from flask import g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash


def configure_access(app):
    production = os.environ.get("PRIYA_ENV", "local") == "production"
    password_hash = os.environ.get("PRIYA_PASSWORD_HASH", "")
    secret = os.environ.get("PRIYA_SESSION_SECRET", "")
    if (production or password_hash) and (not password_hash or len(secret) < 32):
        raise RuntimeError("Set PRIYA_PASSWORD_HASH and a PRIYA_SESSION_SECRET of at least 32 characters.")
    if password_hash and not password_hash.startswith(("scrypt:", "pbkdf2:")):
        raise RuntimeError("PRIYA_PASSWORD_HASH must be a Werkzeug scrypt or PBKDF2 hash, not a plaintext password.")
    app.config.update(
        PASSWORD_HASH=password_hash,
        SECRET_KEY=secret or secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=production,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        RATE_LIMITS_ENABLED=True,
    )
    buckets = defaultdict(deque)
    lock = threading.Lock()

    def limited(key, maximum, window):
        now = time.monotonic()
        with lock:
            for old_key in list(buckets):
                if not buckets[old_key] or buckets[old_key][-1] <= now - 300:
                    del buckets[old_key]
            if key not in buckets and len(buckets) >= 1024:
                return True
            bucket = buckets[key]
            while bucket and bucket[0] <= now - window:
                bucket.popleft()
            if len(bucket) >= maximum:
                return True
            bucket.append(now)
        return False

    def csrf_token():
        if not app.config["PASSWORD_HASH"]:
            return ""
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]

    @app.context_processor
    def access_context():
        return {"csrf_token": csrf_token, "login_enabled": bool(app.config["PASSWORD_HASH"])}

    @app.before_request
    def protect_request():
        g.request_started = time.monotonic()
        if request.endpoint in {"static", "health"}:
            return None
        authenticated = session.get("authenticated", False)
        if app.config["PASSWORD_HASH"]:
            if request.endpoint != "login" and not authenticated:
                if request.path.startswith("/api/"):
                    return jsonify(error="Please sign in again."), 401
                return redirect(url_for("login"))
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
                if not token or not hmac.compare_digest(token, session.get("csrf", "")):
                    return jsonify(error="The session token is invalid. Refresh and try again.", code="csrf"), 403
        if app.config["RATE_LIMITS_ENABLED"] and request.endpoint != "monitor_state":
            identity = "owner" if authenticated else request.remote_addr
            key = ("login", identity) if request.endpoint == "login" and request.method == "POST" else ("api", identity)
            maximum, window = (5, 300) if key[0] == "login" else (120, 60)
            if limited(key, maximum, window):
                response = jsonify(error="Too many requests. Please wait before trying again.")
                response.headers["Retry-After"] = str(window)
                return response, 429
            if request.method == "POST" and request.path in {"/api/chat", "/api/speech", "/api/transcribe", "/api/audio"}:
                if limited(("expensive", identity), 30, 60):
                    response = jsonify(error="Voice and AI request limit reached. Try again in a minute.")
                    response.headers["Retry-After"] = "60"
                    return response, 429

    @app.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        if app.config["SESSION_COOKIE_SECURE"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        app.logger.info(
            "%s %s status=%s duration_ms=%d", request.method, request.path, response.status_code,
            int((time.monotonic() - getattr(g, "request_started", time.monotonic())) * 1000),
        )
        return response

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if not app.config["PASSWORD_HASH"]:
            return redirect(url_for("index"))
        error = None
        if request.method == "POST":
            if check_password_hash(app.config["PASSWORD_HASH"], request.form.get("password", "")):
                session.clear()
                session["authenticated"] = True
                session.permanent = True
                csrf_token()
                return redirect(url_for("index"))
            app.logger.warning("Sign-in rejected")
            error = "The password is incorrect."
        return render_template("login.html", error=error), 401 if error else 200

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/api/session")
    def session_token():
        return jsonify(csrf_token=csrf_token())
