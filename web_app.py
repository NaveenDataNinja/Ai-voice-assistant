from io import BytesIO
import hmac
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import quote_plus
from urllib.error import URLError

from flask import Flask, Response, jsonify, render_template, request, send_file, stream_with_context
import bleach
import markdown
from gtts import gTTS
from gtts.tts import gTTSError
from av.error import FFmpegError
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio

import assistant_services
import action_router
import task_store
from web_access import configure_access
from app_monitor import AppMonitor


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16384
app.config["TASK_DATABASE"] = str(Path(os.environ.get("PRIYA_DATA_DIR", str(Path.home() / ".priya"))) / "tasks.sqlite3")
app.logger.setLevel(logging.INFO)
monitor = AppMonitor(app)
configure_access(app)
DOWNLOAD_LOCK = threading.BoundedSemaphore(1)
AI_LOCK = threading.BoundedSemaphore(1)
SPEECH_LOCK = threading.BoundedSemaphore(1)
TRANSCRIPTION_LOCK = threading.BoundedSemaphore(1)
transcription_model: WhisperModel | None = None
MAX_AUDIO_BYTES = 25 * 1024 * 1024
MAX_MESSAGE_LENGTH = 500
APP_RELEASE = "2026.11.14.3"
APP_UPDATES = (
    "New-laptop setup: Windows Python 3.11 setup/start scripts, tested dependency version constraints, and a private task backup/restore tool are included. Models are provisioned separately; personal data and credentials stay out of Git.",
    "Reliable actions: polite commands work; reminders and tasks are saved before confirmation.",
    "Persistent reminders: overdue banners survive refreshes and server restarts until acknowledged.",
    "Voice queue: spoken or typed messages wait visibly while Priya is answering; unsent drafts are retained.",
    "Streaming replies: text appears incrementally; Stop cancels the current reply, audio, recording, and queue.",
    "Readable answers: formatted paragraphs, lists, tables, and code blocks replace raw Markdown.",
    "Optional sources: enable Wikipedia grounding or ask 'Explain voltage with sources'. Invalid citations are replaced with explicitly labelled source excerpts, not a fictional summary.",
    "Private deployment: single-password login, session protection, rate limits, persistent storage, health checks, and request/error logs are available. Production requires credentials and HTTPS; local loopback mode stays passwordless unless configured.",
    "Soft Indian-English replies and local microphone transcription remain available. Closed-browser reminders appear when you return; email alerts and physical AR/VR testing are not included.",
    "Live Developer Monitor: inspect request stages, timings, errors, safe file-change notices, developer progress and actual automated test results. No private prompts or hidden reasoning are shown.",
)


def formatted_reply(text):
    return bleach.clean(
        markdown.markdown(text, extensions=["fenced_code", "tables"]),
        tags={"p", "br", "strong", "em", "code", "pre", "blockquote", "ul", "ol", "li",
              "h1", "h2", "h3", "h4", "hr", "table", "thead", "tbody", "tr", "th", "td"},
        attributes={}, protocols=[], strip=True,
    )


def cited_reply(text, sources):
    if not sources:
        return text, None
    citations = [int(value) for value in re.findall(r"\[(\d+)\]", text)]
    if citations and all(1 <= value <= len(sources) for value in citations):
        return text, None
    warning = "The model did not produce valid source citations. These are retrieved excerpts, not a verified AI summary."
    excerpts = "\n\n".join(f"[{i}] **{source['title']}**: {source['snippet']}" for i, source in enumerate(sources, 1))
    return f"{warning}\n\n{excerpts}", warning


@app.get("/healthz")
def health():
    return jsonify(status="ok")


def updates_payload():
    text = f"## What's new in Priya - {APP_RELEASE}\n\n" + "\n\n".join(f"- {item}" for item in APP_UPDATES)
    return {"kind": "updates", "release": APP_RELEASE, "reply": text, "html": formatted_reply(text)}


@app.get("/api/updates")
def application_updates():
    return jsonify(updates_payload())


@app.get("/api/status")
def service_status():
    task_store.list_tasks(app.config["TASK_DATABASE"])
    ai_enabled = os.environ.get("PRIYA_AI_ENABLED", "1") == "1"
    ai_ready = False
    if ai_enabled:
        try:
            with assistant_services.urlopen(assistant_services.OLLAMA_URL + "/api/tags", timeout=3) as response:
                models = json.load(response).get("models", [])
            ai_ready = any(item.get("name") == assistant_services.MODEL for item in models)
        except (URLError, OSError, ValueError) as error:
            app.logger.warning("AI readiness check failed: %s", type(error).__name__)
    return jsonify(status="ok" if not ai_enabled or ai_ready else "degraded", tasks="ready",
                   ai="ready" if ai_ready else ("unavailable" if ai_enabled else "disabled"),
                   transcription="loaded" if transcription_model else "loads on first recording")


@app.route("/api/tasks", methods=["GET", "POST"])
def tasks():
    if request.method == "GET":
        return jsonify(tasks=task_store.list_tasks(app.config["TASK_DATABASE"]))
    try:
        task = task_store.add_task(app.config["TASK_DATABASE"], request.get_json(silent=True))
    except ValueError as error:
        return jsonify(error=str(error)), 400
    monitor.record("tool.task_saved", "Task committed to SQLite before confirmation.", "ok")
    return jsonify(task=task), 201


@app.post("/api/tasks/import")
def import_tasks():
    data = request.get_json(silent=True)
    try:
        task_store.import_tasks(app.config["TASK_DATABASE"], data.get("tasks") if isinstance(data, dict) else None)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    return jsonify(tasks=task_store.list_tasks(app.config["TASK_DATABASE"]))


@app.route("/api/tasks/<task_id>", methods=["PATCH", "DELETE"])
def change_task(task_id):
    if request.method == "DELETE":
        if not task_store.delete_task(app.config["TASK_DATABASE"], task_id):
            return jsonify(error="That task was not found. Refresh the list."), 404
        return jsonify(deleted=True)
    try:
        task = task_store.update_task(app.config["TASK_DATABASE"], task_id, request.get_json(silent=True))
    except ValueError as error:
        return jsonify(error=str(error)), 400
    if task is None:
        return jsonify(error="That task was not found. Refresh the list."), 404
    return jsonify(task=task)


@app.errorhandler(sqlite3.Error)
def database_failure(error):
    app.logger.error("Task storage failed: %s", type(error).__name__)
    return jsonify(error="Task storage is unavailable. Nothing was confirmed as saved; please retry."), 503


@app.errorhandler(OSError)
def storage_os_failure(error):
    app.logger.error("Server I/O failed: %s", type(error).__name__)
    return jsonify(error="Server storage or I/O is unavailable. Please check the server logs."), 503


@app.before_request
def limit_request_size():
    request.max_content_length = 2 * 1024 * 1024 if request.path == "/api/transcribe" else 16384


@app.post("/api/transcribe")
def transcribe():
    global transcription_model
    if request.mimetype not in {"audio/webm", "audio/ogg", "audio/mp4", "audio/wav"}:
        return jsonify(error="Send a supported microphone audio recording."), 400
    content = request.get_data()
    if not content:
        return jsonify(error="The microphone recording is empty."), 400
    if not TRANSCRIPTION_LOCK.acquire(blocking=False):
        return jsonify(error="Voice recognition is busy. Please try again shortly."), 429
    try:
        try:
            monitor.record("transcription.started", "Decoding the recording in memory; no cloud speech-recognition request.")
            samples = decode_audio(BytesIO(content), sampling_rate=16000)
            if not 0 < len(samples) <= 30 * 16000:
                return jsonify(error="Record a nonempty clip of at most 30 seconds."), 422
            if transcription_model is None:
                monitor.record("transcription.loading", "Loading the local tiny.en CPU model.")
                transcription_model = WhisperModel(
                    "tiny.en", device="cpu", compute_type="int8", local_files_only=True
                )
            segments, _info = transcription_model.transcribe(
                samples, language="en", beam_size=1, vad_filter=True
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
        except (ValueError, RuntimeError, OSError, FFmpegError) as error:
            app.logger.warning("Local transcription failed: %s", type(error).__name__)
            return jsonify(error="Local voice recognition is unavailable. Check the recording and install the tiny.en model as described in the README."), 503
        if not text:
            return jsonify(error="No speech detected. Speak clearly near the microphone and try again."), 422
        if len(text) > MAX_MESSAGE_LENGTH:
            return jsonify(error="The recording is too long to use as a message. Please say a shorter command."), 422
        monitor.record("transcription.completed", "Recognized text is ready for command routing; the transcript is not logged.", "ok")
        response = jsonify(text=text)
        response.headers["Cache-Control"] = "no-store"
        return response
    finally:
        TRANSCRIPTION_LOCK.release()


@app.get("/")
def index():
    return render_template("index.html", downloads_enabled=bool(os.environ.get("PRIYA_DOWNLOAD_KEY")), release=APP_RELEASE)


@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("message"), str):
        return jsonify(error="Please enter a message."), 400
    message = data["message"].strip()
    if not message or len(message) > MAX_MESSAGE_LENGTH:
        return jsonify(error=f"Messages must be 1 to {MAX_MESSAGE_LENGTH} characters."), 400

    command = action_router.normalize_command(message)
    monitor.record("routing.started", "Normalizing polite phrasing and checking supported deterministic actions before AI.")
    lowered = command.lower().rstrip(".?!").strip()
    if lowered in {"show updates", "updates", "what's new", "what is new", "show application updates"}:
        monitor.record("routing.updates", "Returning the maintained release notes without calling the model.")
        return jsonify(updates_payload())
    try:
        reminder = action_router.reminder_task(command)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    if reminder:
        if "action_id" in data:
            reminder["id"] = data["action_id"]
        try:
            monitor.record("tool.task_saving", "Saving a validated reminder in SQLite.")
            saved = task_store.add_task(app.config["TASK_DATABASE"], reminder)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        monitor.record("tool.task_saved", "Reminder committed to SQLite; confirmation is now allowed.", "ok")
        return jsonify(kind="task_saved", reply=f'Reminder saved for "{saved["title"]}". It stays overdue until acknowledged in Tasks.', task=saved)
    if lowered in {"time", "what time is it", "what is the time"}:
        monitor.record("routing.local_time", "Using the browser's local clock; no AI request.")
        return jsonify(kind="time", reply="Here is your local time.")
    if lowered in {"help", "what can you do"}:
        return jsonify(kind="text", reply="Ask me to explain a concept, say 'research' followed by a topic, or use the tools for tasks and 3D visualizations. I can also tell the time, open websites, and find music.")
    if lowered in {"stop", "exit", "quit"}:
        return jsonify(kind="text", reply="I'm here whenever you need me. You can close this tab when you're done.")
    websites = {
        "open youtube": ("YouTube", "https://www.youtube.com"),
        "open google": ("Google", "https://www.google.com"),
        "open chatgpt": ("ChatGPT", "https://chatgpt.com"),
    }
    if lowered in websites:
        monitor.record("routing.website_link", "Returning an allowlisted website link; no external tab is controlled.")
        name, url = websites[lowered]
        return jsonify(kind="link", reply=f"Here's {name} for you.", label=f"Open {name}", url=url)
    if lowered == "show graph":
        return jsonify(kind="graph", reply="Here's a sample graph of x squared.")
    if lowered in {"open tasks", "show tasks", "open reminders"}:
        return jsonify(kind="tasks", reply="Opening your tasks and reminders.")
    if lowered.startswith("add task "):
        task = command[9:].strip()
        if not task or len(task) > 160:
            return jsonify(error="Task names must be 1 to 160 characters."), 400
        item = {"title": task}
        if "action_id" in data:
            item["id"] = data["action_id"]
        try:
            saved = task_store.add_task(app.config["TASK_DATABASE"], item)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        monitor.record("tool.task_saved", "Task committed to SQLite; confirmation is now allowed.", "ok")
        return jsonify(kind="task_saved", reply=f'Added "{saved["title"]}" to your saved tasks.', task=saved)
    scenes = {
        "show atom": ("atom", "Here's a stylized atom. It is an illustration, not a scale model."),
        "show solar system": ("solar", "Here's a simplified solar system. Sizes and distances are not to scale."),
        "show water molecule": ("water", "Here's a simplified water molecule, H₂O."),
        "open 3d studio": ("avatar", "Opening the 3D studio."),
    }
    if lowered in scenes:
        scene, reply = scenes[lowered]
        return jsonify(kind="visual", reply=reply, scene=scene)
    if lowered == "research":
        return jsonify(kind="text", reply="Type 'research' followed by a topic to search Wikipedia.")
    if lowered.startswith("research "):
        query = command[9:].strip()
        if not query:
            return jsonify(error="Please provide a topic to research."), 400
        try:
            monitor.record("research.started", "Retrieving public Wikipedia search excerpts.")
            sources = assistant_services.search_wikipedia(query)
        except (URLError, TimeoutError, OSError, ValueError) as error:
            app.logger.warning("Wikipedia search failed: %s", type(error).__name__)
            return jsonify(error="Wikipedia search is unavailable. Check your internet connection and try again."), 502
        monitor.record("research.completed", f"Retrieved {len(sources)} reference excerpts.", "ok")
        return jsonify(
            kind="sources",
            reply="Here are Wikipedia starting points. Check the original sources and publication dates for important decisions." if sources else "I couldn't find Wikipedia results for that topic.",
            sources=sources,
        )
    if lowered in {"play", "play song", "play a song"}:
        return jsonify(kind="ask_song", reply="What song would you like to find?")
    if lowered.startswith("play "):
        song = command[5:].strip()
        if song:
            return jsonify(
                kind="music",
                reply=f'Here are your options for "{song}".',
                song=song,
                url=f"https://www.youtube.com/results?search_query={quote_plus(song)}",
            )
    if action_router.unsupported_action(command):
        monitor.record("routing.unsupported_action", "Unsupported action was not executed or passed to the model as a tool.", "info")
        return jsonify(kind="text", reply="I haven't performed that action. For reminders, say 'remind me in 2 minutes to drink water', or choose a time in Tasks. To save a task, say 'add task review my notes'. I cannot send emails, access an inbox, or control devices.")
    if os.environ.get("PRIYA_AI_ENABLED", "1") != "1":
        return jsonify(error="Local AI is disabled on this server. See the setup instructions."), 503
    history = data.get("history", [])
    if not isinstance(history, list) or len(history) > 6:
        return jsonify(error="Conversation history is invalid."), 400
    if any(
        not isinstance(item, dict)
        or item.get("role") not in {"user", "assistant"}
        or not isinstance(item.get("content"), str)
        or len(item["content"]) > 1500
        for item in history
    ):
        return jsonify(error="Conversation history is invalid."), 400
    sources = []
    if data.get("grounded") is True or re.search(r"\bwith sources$", command, re.IGNORECASE):
        query = re.sub(r"\s+with sources$", "", command, flags=re.IGNORECASE)
        query = re.sub(r"^(?:explain|what is|what are|tell me about)\s+", "", query, flags=re.IGNORECASE)
        try:
            monitor.record("research.started", "Retrieving Wikipedia excerpts for an optional grounded answer.")
            sources = assistant_services.search_wikipedia(query)
        except (URLError, TimeoutError, OSError, ValueError) as error:
            app.logger.warning("Grounding lookup failed: %s", type(error).__name__)
            return jsonify(error="Could not retrieve sources. No sourced answer was generated; try again or turn source lookup off."), 502
        if not sources:
            return jsonify(kind="text", reply="I couldn't retrieve supporting Wikipedia sources. Try a more specific topic; I haven't generated a sourced answer.")
        monitor.record("research.completed", f"Retrieved {len(sources)} reference excerpts for grounding.", "ok")
    if not AI_LOCK.acquire(blocking=False):
        return jsonify(error="Local AI is busy. Please try again shortly."), 429
    if data.get("stream") is True:
        def events():
            chunks = assistant_services.stream_local_model(command, history, sources)
            started = time.monotonic()
            outcome = "cancelled"
            monitor.stream_started()
            try:
                yield json.dumps({"type": "sources", "sources": sources}) + "\n"
                parts = []
                for chunk in chunks:
                    if not parts:
                        monitor.record("ai.first_token", "First model text received; streaming draft to the browser.", "ok")
                    parts.append(chunk)
                    yield json.dumps({"type": "token", "text": chunk}) + "\n"
                text, warning = cited_reply("".join(parts).strip(), sources)
                monitor.record("ai.validation", "Citations were missing or invalid; explicitly showing retrieved excerpts." if warning else "Generation completed; preparing sanitized Markdown.")
                outcome = "completed"
                yield json.dumps({"type": "done", "kind": "sources" if warning else "ai", "reply": text,
                                  "html": formatted_reply(text), "sources": sources, "warning": warning}) + "\n"
            except assistant_services.ReplyLimitError as error:
                outcome = "failed"
                app.logger.warning("AI reply reached generation limit")
                yield json.dumps({"type": "error", "error": str(error)}) + "\n"
            except (URLError, TimeoutError, OSError, ValueError) as error:
                outcome = "failed"
                app.logger.warning("AI stream failed: %s", type(error).__name__)
                yield json.dumps({"type": "error", "error": "The AI reply was interrupted. Check Ollama and try again."}) + "\n"
            finally:
                try:
                    chunks.close()
                finally:
                    AI_LOCK.release()
                    monitor.stream_finished(outcome, round((time.monotonic() - started) * 1000))
        response = Response(stream_with_context(events()), mimetype="application/x-ndjson")
        response.headers["X-Accel-Buffering"] = "no"
        return response
    try:
        monitor.record("ai.started", "Generating a non-streaming local AI answer.")
        try:
            reply = "".join(assistant_services.stream_local_model(command, history, sources)) if sources else assistant_services.ask_local_model(command, history)
        except assistant_services.ReplyLimitError as error:
            return jsonify(error=str(error)), 422
        except (URLError, TimeoutError, OSError, ValueError) as error:
            app.logger.warning("Local AI request failed: %s", type(error).__name__)
            return jsonify(error="Local AI is unavailable. Start Ollama and install the configured model; see the README."), 503
    finally:
        AI_LOCK.release()
    if sources:
        reply, warning = cited_reply(reply, sources)
        return jsonify(kind="sources" if warning else "ai", reply=reply, html=formatted_reply(reply), sources=sources, warning=warning)
    return jsonify(kind="ai", reply=reply, html=formatted_reply(reply), sources=sources)


@app.post("/api/audio")
def audio():
    key = os.environ.get("PRIYA_DOWNLOAD_KEY", "")
    if not key:
        return jsonify(error="Temporary audio is not enabled on this server."), 503
    provided_key = request.headers.get("X-Priya-Download-Key", "")
    if not hmac.compare_digest(key.encode("utf-8"), provided_key.encode("utf-8")):
        return jsonify(error="The audio access key is incorrect."), 403
    data = request.get_json(silent=True)
    song = data.get("song") if isinstance(data, dict) else None
    if not isinstance(song, str) or not song.strip() or len(song) > 120:
        return jsonify(error="Enter a song name of up to 120 characters."), 400
    if not DOWNLOAD_LOCK.acquire(blocking=False):
        return jsonify(error="Audio preparation is busy. Please try again shortly."), 429
    try:
        with tempfile.TemporaryDirectory(prefix="priya-web-audio-") as directory:
            command = [
                sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-playlist",
                "--no-warnings", "--quiet", "--socket-timeout", "10",
                "--retries", "1", "--max-filesize", "25M",
                "--match-filter", "duration > 0 & duration <= 600",
                "-f", "bestaudio[ext=m4a]/bestaudio[ext=mp3]",
                "-o", str(Path(directory) / "song.%(ext)s"),
                f"ytsearch1:{song.strip()}",
            ]
            try:
                subprocess.run(command, check=True, capture_output=True, timeout=90)
            except subprocess.TimeoutExpired:
                app.logger.warning("Audio preparation timed out")
                return jsonify(error="Audio preparation timed out. Try opening YouTube instead."), 504
            except subprocess.CalledProcessError as error:
                app.logger.warning("Audio preparation failed with exit code %s", error.returncode)
                return jsonify(error="Could not prepare audio. Try opening YouTube instead."), 502
            except OSError as error:
                app.logger.warning("Audio preparation failed: %s", error)
                return jsonify(error="Could not prepare audio. Try opening YouTube instead."), 502
            files = [path for path in Path(directory).iterdir() if path.is_file() and path.suffix in {".m4a", ".mp3"}]
            if len(files) != 1 or files[0].stat().st_size > MAX_AUDIO_BYTES:
                return jsonify(error="No playable audio under the size limit was found."), 422
            content = files[0].read_bytes()
            mime = "audio/mp4" if files[0].suffix == ".m4a" else "audio/mpeg"
            response = send_file(BytesIO(content), mimetype=mime)
            response.headers["Cache-Control"] = "no-store"
            return response
    finally:
        DOWNLOAD_LOCK.release()


@app.post("/api/speech")
def speech():
    data = request.get_json(silent=True)
    text = data.get("text") if isinstance(data, dict) else None
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        return jsonify(error="Speech text must be 1 to 4000 characters."), 400
    if not SPEECH_LOCK.acquire(blocking=False):
        return jsonify(error="Voice generation is busy. Please try again shortly."), 429
    try:
        monitor.record("speech.started", "Requesting online Google Indian-English speech; spoken reply text is sent to Google.")
        audio = BytesIO()
        try:
            gTTS(text=text.strip(), lang="en", tld="co.in", timeout=15).write_to_fp(audio)
        except (gTTSError, OSError) as error:
            app.logger.warning("Online speech failed: %s", type(error).__name__)
            return jsonify(error="The online voice is unavailable. Check internet access and try again."), 502
        if audio.tell() == 0:
            app.logger.warning("Online speech returned no audio")
            return jsonify(error="The online voice returned no audio."), 502
        audio.seek(0)
        response = send_file(audio, mimetype="audio/mpeg")
        response.headers["Cache-Control"] = "no-store"
        monitor.record("speech.completed", "MP3 audio generated; browser playback and speaker settings are separate.", "ok")
        return response
    finally:
        SPEECH_LOCK.release()


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify(error="The request is too large."), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")))
