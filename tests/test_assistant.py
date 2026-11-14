import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "Voice open and play in youtube code.py"
spec = importlib.util.spec_from_file_location("priya_assistant", MODULE_PATH)
assistant = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assistant)


class CommandTests(unittest.TestCase):
    def test_play_command_keeps_song_name(self):
        with patch.object(assistant, "play_song") as play:
            self.assertTrue(assistant.process_command("Priya play song for someone"))
        play.assert_called_once_with("song for someone")

    def test_generic_play_asks_for_song(self):
        with patch.object(assistant, "play_song") as play:
            assistant.process_command("play a song")
        play.assert_called_once_with()

    def test_stop_requires_an_explicit_command(self):
        with patch.object(assistant, "speak") as speak:
            self.assertFalse(assistant.process_command("stop"))
            self.assertTrue(assistant.process_command("stop playing games"))
        self.assertIn("do not know", speak.call_args.args[0])

    def test_unrecognized_playback_choice_does_not_open_browser(self):
        with patch.object(assistant, "listen", return_value=""), \
             patch.object(assistant, "speak") as speak, \
             patch.object(assistant, "play_song_online") as online, \
             patch.object(assistant, "play_song_offline") as offline:
            assistant.play_song("a song")
        online.assert_not_called()
        offline.assert_not_called()
        self.assertIn("online or offline", speak.call_args.args[0])

    def test_browser_failure_is_reported(self):
        with patch.object(assistant.webbrowser, "open", side_effect=OSError("browser unavailable")), \
             patch.object(assistant, "speak") as speak, \
             self.assertLogs(assistant.LOG, level="ERROR"):
            assistant.open_website("Google", "https://google.com")
        self.assertIn("could not open", speak.call_args.args[0])


class PlaybackTests(unittest.TestCase):
    def test_download_uses_and_cleans_temporary_file(self):
        paths = []

        class FakeDownloader:
            def __init__(self, options):
                self.options = options

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def extract_info(self, query, download):
                path = Path(self.options["outtmpl"].replace("%(ext)s", "mp3"))
                path.write_bytes(b"test")
                paths.append(path)
                return {"entries": [{"title": "Test song"}]}

        with tempfile.TemporaryDirectory() as working_dir:
            existing = Path(working_dir) / "song.mp3"
            existing.write_bytes(b"keep")
            with patch.object(assistant.yt_dlp, "YoutubeDL", FakeDownloader), \
                 patch.object(assistant, "speak"), \
                 patch.object(assistant, "play_audio") as play:
                assistant.play_song_offline("test")
            play.assert_called_once_with(paths[0])
            self.assertFalse(paths[0].exists())
            self.assertEqual(existing.read_bytes(), b"keep")

    def test_empty_search_result_is_reported(self):
        with patch.object(assistant.yt_dlp, "YoutubeDL") as downloader, \
             patch.object(assistant, "speak") as speak, \
             patch.object(assistant.webbrowser, "open") as browser:
            downloader.return_value.__enter__.return_value.extract_info.return_value = {"entries": []}
            assistant.play_song_online("unknown")
        browser.assert_not_called()
        self.assertIn("could not find", speak.call_args.args[0])

    def test_timeout_does_not_crash(self):
        with patch.object(assistant.sr, "Microphone"), \
             patch.object(assistant.sr, "Recognizer") as recognizer:
            recognizer.return_value.listen.side_effect = assistant.sr.WaitTimeoutError()
            self.assertEqual(assistant.listen(), "")

    def test_speech_service_error_is_reported(self):
        with patch.object(assistant.sr, "Microphone"), \
             patch.object(assistant.sr, "Recognizer") as recognizer:
            recognizer.return_value.recognize_google.side_effect = assistant.sr.RequestError("network")
            with self.assertRaisesRegex(RuntimeError, "Speech recognition service unavailable"):
                assistant.listen()


if __name__ == "__main__":
    unittest.main()
