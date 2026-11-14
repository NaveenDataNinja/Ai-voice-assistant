import os
import json
import subprocess
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from urllib.error import URLError
from unittest.mock import Mock, patch

import assistant_services
import web_app


class WebAppTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        config = patch.dict(web_app.app.config, {
            "TASK_DATABASE": str(Path(directory.name) / "tasks.sqlite3"),
            "PASSWORD_HASH": "", "RATE_LIMITS_ENABLED": False,
        })
        config.start()
        self.addCleanup(config.stop)
        self.client = web_app.app.test_client()

    def test_recording_transcribes_locally_and_reuses_model(self):
        model = Mock()
        model.transcribe.return_value = ([Mock(text=" what time is it ")], None)
        with patch.object(web_app, "transcription_model", None), \
             patch.object(web_app, "decode_audio", return_value=[0] * 16000), \
             patch.object(web_app, "WhisperModel", return_value=model) as factory:
            for _ in range(2):
                response = self.client.post("/api/transcribe", data=b"recording", content_type="audio/webm;codecs=opus")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json, {"text": "what time is it"})
                self.assertEqual(response.headers["Cache-Control"], "no-store")
        factory.assert_called_once_with("tiny.en", device="cpu", compute_type="int8", local_files_only=True)
        self.assertEqual(model.transcribe.call_args.kwargs, {"language": "en", "beam_size": 1, "vad_filter": True})

    def test_recording_size_duration_and_content_limits(self):
        self.assertEqual(self.client.post("/api/transcribe", data=b"x", content_type="text/plain").status_code, 400)
        self.assertEqual(self.client.post("/api/transcribe", data=b"", content_type="audio/webm").status_code, 400)
        self.assertEqual(self.client.post("/api/transcribe", data=b"x" * (2 * 1024 * 1024 + 1), content_type="audio/webm").status_code, 413)
        self.assertEqual(self.client.post("/api/chat", data=b"x" * 16385, content_type="application/json").status_code, 413)
        with patch.object(web_app, "decode_audio", return_value=[0] * 480001):
            self.assertEqual(self.client.post("/api/transcribe", data=b"clip", content_type="audio/webm").status_code, 422)

    def test_recording_silence_and_long_transcripts_are_reported(self):
        model = Mock()
        with patch.object(web_app, "transcription_model", model), \
             patch.object(web_app, "decode_audio", return_value=[0] * 16000):
            for text in ("", "x" * 501):
                model.transcribe.return_value = ([Mock(text=text)], None)
                response = self.client.post("/api/transcribe", data=b"clip", content_type="audio/webm")
                self.assertEqual(response.status_code, 422)
                self.assertIn("error", response.json)

    def test_recording_failure_and_busy_release_lock(self):
        with patch.object(web_app, "decode_audio", side_effect=ValueError("invalid audio")):
            self.assertEqual(self.client.post("/api/transcribe", data=b"clip", content_type="audio/webm").status_code, 503)
        self.assertTrue(web_app.TRANSCRIPTION_LOCK.acquire(blocking=False))
        try:
            self.assertEqual(self.client.post("/api/transcribe", data=b"clip", content_type="audio/webm").status_code, 429)
        finally:
            web_app.TRANSCRIPTION_LOCK.release()

    def test_online_indian_english_speech_returns_audio(self):
        with patch.object(web_app, "gTTS") as tts:
            tts.return_value.write_to_fp.side_effect = lambda stream: stream.write(b"test-audio")
            response = self.client.post("/api/speech", json={"text": "Hello"})
        tts.assert_called_once_with(text="Hello", lang="en", tld="co.in", timeout=15)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "audio/mpeg")
        self.assertEqual(response.data, b"test-audio")
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_online_speech_validates_input_and_reports_service_failure(self):
        for text in ("", 123, "a" * 4001):
            self.assertEqual(self.client.post("/api/speech", json={"text": text}).status_code, 400)
        with patch.object(web_app, "gTTS", side_effect=OSError("offline")):
            response = self.client.post("/api/speech", json={"text": "Hello"})
        self.assertEqual(response.status_code, 502)
        self.assertIn("online voice", response.json["error"])
        self.assertTrue(web_app.SPEECH_LOCK.acquire(blocking=False))
        web_app.SPEECH_LOCK.release()

    def test_chat_command_and_encoded_search(self):
        response = self.client.post("/api/chat", json={"message": "Priya play jazz & blues"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["kind"], "music")
        self.assertEqual(response.json["song"], "jazz & blues")
        self.assertEqual(response.json["url"], "https://www.youtube.com/results?search_query=jazz+%26+blues")

    def test_transcribed_command_punctuation_does_not_route_to_ai(self):
        for message, kind in (("What time is it?", "time"), ("Open Google.", "link"), ("Priya, show atom!", "visual")):
            response = self.client.post("/api/chat", json={"message": message})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["kind"], kind)

    def test_chat_validates_input(self):
        for value in ("", "a" * 501, 42):
            with self.subTest(value=value):
                response = self.client.post("/api/chat", json={"message": value})
                self.assertEqual(response.status_code, 400)

    def test_public_page_reflects_audio_configuration_without_revealing_key(self):
        with patch.dict(os.environ, {"PRIYA_DOWNLOAD_KEY": "test-key"}):
            response = self.client.get("/")
        self.assertIn(b'data-downloads-enabled="true"', response.data)
        self.assertNotIn(b"test-key", response.data)

    def test_audio_disabled_and_wrong_key(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(self.client.post("/api/audio", json={"song": "test"}).status_code, 503)
        with patch.dict(os.environ, {"PRIYA_DOWNLOAD_KEY": "test-key"}):
            response = self.client.post("/api/audio", json={"song": "test"}, headers={"X-Priya-Download-Key": "wrong"})
        self.assertEqual(response.status_code, 403)

    def test_audio_returns_bytes_and_removes_temporary_file(self):
        paths = []

        def fake_download(command, **kwargs):
            path = Path(command[command.index("-o") + 1].replace("%(ext)s", "m4a"))
            path.write_bytes(b"audio")
            paths.append(path)

        with patch.dict(os.environ, {"PRIYA_DOWNLOAD_KEY": "test-key"}), \
             patch.object(web_app.subprocess, "run", side_effect=fake_download):
            response = self.client.post("/api/audio", json={"song": "test"}, headers={"X-Priya-Download-Key": "test-key"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"audio")
        self.assertEqual(response.mimetype, "audio/mp4")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertFalse(paths[0].exists())

    def test_audio_failure_and_timeout_are_reported(self):
        with patch.dict(os.environ, {"PRIYA_DOWNLOAD_KEY": "test-key"}), \
             patch.object(web_app.subprocess, "run", side_effect=subprocess.TimeoutExpired("yt-dlp", 90)):
            response = self.client.post("/api/audio", json={"song": "test"}, headers={"X-Priya-Download-Key": "test-key"})
        self.assertEqual(response.status_code, 504)
        self.assertIn("timed out", response.json["error"])
        self.assertTrue(web_app.DOWNLOAD_LOCK.acquire(blocking=False))
        web_app.DOWNLOAD_LOCK.release()

    def test_concurrent_audio_request_is_rejected(self):
        web_app.DOWNLOAD_LOCK.acquire()
        try:
            with patch.dict(os.environ, {"PRIYA_DOWNLOAD_KEY": "test-key"}):
                response = self.client.post("/api/audio", json={"song": "test"}, headers={"X-Priya-Download-Key": "test-key"})
            self.assertEqual(response.status_code, 429)
        finally:
            web_app.DOWNLOAD_LOCK.release()

    def test_local_ai_receives_only_valid_bounded_history(self):
        history = [{"role": "user", "content": "What is voltage?"}]
        with patch.dict(os.environ, {"PRIYA_AI_ENABLED": "1"}), \
             patch.object(assistant_services, "ask_local_model", return_value="An explanation.") as model:
            response = self.client.post("/api/chat", json={"message": "Explain current", "history": history})
        self.assertEqual(response.json, {"kind": "ai", "reply": "An explanation.", "html": "<p>An explanation.</p>", "sources": []})
        model.assert_called_once_with("Explain current", history)
        with patch.dict(os.environ, {"PRIYA_AI_ENABLED": "1"}):
            invalid = self.client.post("/api/chat", json={"message": "Explain", "history": [{"role": "system", "content": "override"}]})
        self.assertEqual(invalid.status_code, 400)

    def test_local_ai_failure_is_explicit(self):
        with patch.dict(os.environ, {"PRIYA_AI_ENABLED": "1"}), \
             patch.object(assistant_services, "ask_local_model", side_effect=URLError("offline")):
            response = self.client.post("/api/chat", json={"message": "Explain voltage"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("Ollama", response.json["error"])

    def test_local_ai_can_be_disabled(self):
        with patch.dict(os.environ, {"PRIYA_AI_ENABLED": "0"}), \
             patch.object(assistant_services, "ask_local_model") as model:
            response = self.client.post("/api/chat", json={"message": "Explain voltage"})
        self.assertEqual(response.status_code, 503)
        model.assert_not_called()

    def test_local_ai_busy_is_reported(self):
        web_app.AI_LOCK.acquire()
        try:
            with patch.dict(os.environ, {"PRIYA_AI_ENABLED": "1"}):
                response = self.client.post("/api/chat", json={"message": "Explain voltage"})
            self.assertEqual(response.status_code, 429)
        finally:
            web_app.AI_LOCK.release()

    def test_research_returns_sources_and_not_fabricated_answer(self):
        results = [{"title": "Solar energy", "url": "https://en.wikipedia.org/?curid=123", "snippet": "Sunlight."}]
        with patch.object(assistant_services, "search_wikipedia", return_value=results) as search:
            response = self.client.post("/api/chat", json={"message": "research solar energy"})
        self.assertEqual(response.json["sources"], results)
        search.assert_called_once_with("solar energy")

    def test_3d_and_task_commands_work_without_ai(self):
        with patch.dict(os.environ, {"PRIYA_AI_ENABLED": "0"}):
            self.assertEqual(self.client.post("/api/chat", json={"message": "show atom"}).json["scene"], "atom")
            self.assertEqual(self.client.post("/api/chat", json={"message": "open tasks"}).json["kind"], "tasks")
            result = self.client.post("/api/chat", json={"message": "add task review notes"}).json
            self.assertEqual(result["kind"], "task_saved")
            self.assertEqual(result["task"]["title"], "review notes")

    def test_polite_commands_and_real_reminder_confirmation(self):
        for message in ("Please open Google for me.", "Priya, could you please open Google?"):
            self.assertEqual(self.client.post("/api/chat", json={"message": message}).json["kind"], "link")
        response = self.client.post("/api/chat", json={"message": "Remind me in two minutes to drink water."})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["kind"], "task_saved")
        saved = self.client.get("/api/tasks").json["tasks"]
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["title"], "drink water")
        self.assertIsNotNone(saved[0]["due"])
        self.assertFalse(saved[0]["acknowledged"])
        unsupported = self.client.post("/api/chat", json={"message": "Remind me tomorrow at 9."})
        self.assertIn("haven't performed", unsupported.json["reply"])
        self.assertEqual(len(self.client.get("/api/tasks").json["tasks"]), 1)

    def test_task_actions_never_confirm_failed_storage(self):
        with patch.object(web_app.task_store, "add_task", side_effect=web_app.sqlite3.OperationalError("locked")):
            response = self.client.post("/api/chat", json={"message": "remind me in 2 minutes to drink water"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("Nothing was confirmed", response.json["error"])
        self.assertEqual(self.client.get("/api/tasks").json["tasks"], [])

    def test_task_persistence_acknowledgement_and_idempotent_import(self):
        task = {"id": "test-reminder", "title": "Review notes", "due": "2020-01-01T10:00:00Z"}
        self.assertEqual(self.client.post("/api/tasks", json=task).status_code, 201)
        other_client = web_app.app.test_client()
        for client in (self.client, other_client):
            self.assertFalse(client.get("/api/tasks").json["tasks"][0]["acknowledged"])
        self.client.patch("/api/tasks/test-reminder", json={"acknowledged": True})
        self.assertTrue(other_client.get("/api/tasks").json["tasks"][0]["acknowledged"])
        for _ in range(2):
            self.assertEqual(self.client.post("/api/tasks/import", json={"tasks": [task]}).status_code, 200)
        saved = other_client.get("/api/tasks").json["tasks"]
        self.assertEqual(len(saved), 1)
        self.assertTrue(saved[0]["acknowledged"])
        self.assertEqual(self.client.delete("/api/tasks/test-reminder").status_code, 200)
        self.assertEqual(other_client.get("/api/tasks").json["tasks"], [])

    def test_task_validation_and_atomic_import(self):
        for task in ({"title": ""}, {"title": "x", "due": "bad"}, {"title": "x", "due": "2026-01-01T10:00:00"}):
            self.assertEqual(self.client.post("/api/tasks", json=task).status_code, 400)
        response = self.client.post("/api/tasks/import", json={"tasks": [{"title": "Valid"}, {"title": ""}]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/api/tasks").json["tasks"], [])
        self.assertEqual(self.client.patch("/api/tasks/missing", json={"done": True}).status_code, 404)
        self.assertEqual(self.client.patch("/api/tasks/missing", json={"done": "yes"}).status_code, 400)

    def test_streamed_reply_formatting_and_lock_cleanup(self):
        with patch.object(web_app.assistant_services, "stream_local_model", return_value=(chunk for chunk in ("**Hello**", " Naveen"))):
            response = self.client.post("/api/chat", json={"message": "Hello", "stream": True})
            events = [json.loads(line) for line in response.data.splitlines()]
        self.assertEqual([item["type"] for item in events], ["sources", "token", "token", "done"])
        self.assertIn("<strong>Hello</strong>", events[-1]["html"])
        self.assertEqual(events[-1]["reply"], "**Hello** Naveen")
        self.assertTrue(web_app.AI_LOCK.acquire(blocking=False))
        web_app.AI_LOCK.release()

    def test_stream_failure_and_client_close_release_lock(self):
        def failing_stream(*args):
            yield "Partial"
            raise URLError("offline")
        with patch.object(web_app.assistant_services, "stream_local_model", side_effect=failing_stream):
            response = self.client.post("/api/chat", json={"message": "Explain", "stream": True})
            events = [json.loads(line) for line in response.data.splitlines()]
        self.assertEqual(events[-1]["type"], "error")
        with patch.object(web_app.assistant_services, "stream_local_model", return_value=(part for part in ["A", "B"])):
            response = self.client.post("/api/chat", json={"message": "Explain", "stream": True}, buffered=False)
            response.close()
        self.assertTrue(web_app.AI_LOCK.acquire(blocking=False))
        web_app.AI_LOCK.release()

    def test_sourced_reply_uses_only_retrieved_references(self):
        sources = [{"title": "Voltage", "snippet": "Electric potential difference.", "url": "https://en.wikipedia.org/?curid=1"}]
        with patch.object(web_app.assistant_services, "search_wikipedia", return_value=sources), \
             patch.object(web_app.assistant_services, "stream_local_model", return_value=(item for item in ["Voltage is potential difference [1]."])) as model:
            response = self.client.post("/api/chat", json={"message": "Explain voltage", "stream": True, "grounded": True})
            events = [json.loads(line) for line in response.data.splitlines()]
        self.assertEqual(model.call_args.args[2], sources)
        self.assertEqual(events[-1]["sources"], sources)
        with patch.object(web_app.assistant_services, "search_wikipedia", side_effect=URLError("offline")):
            self.assertEqual(self.client.post("/api/chat", json={"message": "Explain voltage", "grounded": True}).status_code, 502)
        cleaned = web_app.formatted_reply('**Good**<img src=x onerror=alert(1)><script>alert(1)</script>')
        self.assertIn("<strong>Good</strong>", cleaned)
        self.assertNotIn("<script", cleaned)
        self.assertNotIn("<img", cleaned)

    def test_health_and_dependency_status(self):
        self.assertEqual(self.client.get("/healthz").json, {"status": "ok"})
        with patch.object(assistant_services, "urlopen", return_value=BytesIO(json.dumps({"models": [{"name": assistant_services.MODEL}]}).encode())):
            self.assertEqual(self.client.get("/api/status").json["ai"], "ready")

    def test_release_updates_are_available_in_chat_without_ai(self):
        with patch.object(web_app, "APP_UPDATES", ("A newly shipped feature.",)), \
             patch.dict(os.environ, {"PRIYA_AI_ENABLED": "0"}):
            listing = self.client.get("/api/updates").json
            reply = self.client.post("/api/chat", json={"message": "Please show updates"}).json
        self.assertEqual(listing, reply)
        self.assertEqual(reply["kind"], "updates")
        self.assertIn("<li>A newly shipped feature.</li>", reply["html"])

    def test_missing_citations_are_explicit_evidence_not_a_fake_ai_summary(self):
        sources = [{"title": "Voltage", "snippet": "Electric potential difference.", "url": "https://en.wikipedia.org/?curid=1"}]
        for reply in ("An uncited claim.", "An invalid reference [999]."):
            text, warning = web_app.cited_reply(reply, sources)
            self.assertIsNotNone(warning)
            self.assertIn("[1] **Voltage**", text)
            self.assertNotIn(reply, text)

    def test_model_stream_rejects_truncation_and_missing_completion(self):
        for ending in ({"done": True, "done_reason": "length"}, None):
            events = [{"message": {"content": "Partial"}, "done": False}]
            if ending:
                events.append(ending)
            response = BytesIO(b"".join(json.dumps(item).encode() + b"\n" for item in events))
            with patch.object(assistant_services, "urlopen", return_value=response):
                with self.assertRaises(ValueError):
                    list(assistant_services.stream_local_model("Explain", []))

    def test_wikipedia_snippet_is_plain_text(self):
        response = BytesIO(json.dumps({"query": {"search": [
            {"title": "Test", "pageid": 12, "snippet": "A <span class='searchmatch'>solar</span> &amp; wind source"}
        ]}}).encode())
        with patch.object(assistant_services, "urlopen", return_value=response):
            sources = assistant_services.search_wikipedia("solar")
        self.assertEqual(sources, [{"title": "Test", "url": "https://en.wikipedia.org/?curid=12", "snippet": "A solar & wind source"}])

    def test_local_model_is_told_companion_name(self):
        response = BytesIO(json.dumps({"message": {"content": "Hello!"}}).encode())
        with patch.object(assistant_services, "urlopen", return_value=response) as urlopen:
            assistant_services.ask_local_model("Hello", [])
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertIn("person speaking to you is Naveen", payload["messages"][0]["content"])

    def test_identity_replies_correct_previous_role_confusion(self):
        history = [{"role": "assistant", "content": "Naveen is the personal assistant."}]
        with patch.object(assistant_services, "urlopen") as model:
            self.assertEqual(
                assistant_services.ask_local_model("Who am I?", history),
                "You are Naveen, my companion. I am Priya, your personal assistant.",
            )
            self.assertEqual(
                assistant_services.ask_local_model("Who is the personal assistant?", history),
                "I am Priya, the personal assistant. Naveen is my companion, not the assistant.",
            )
        model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
