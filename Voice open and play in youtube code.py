import datetime
import logging
import re
import tempfile
import time
import webbrowser
from pathlib import Path

import matplotlib.pyplot as plt
import pygame
import speech_recognition as sr
import yt_dlp
from gtts import gTTS
from gtts.tts import gTTSError
from rapidfuzz import process


LOG = logging.getLogger(__name__)
BUNDLED_FFMPEG = (
    Path(__file__).resolve().parent
    / "ffmpeg-8.0-essentials_build"
    / "ffmpeg-8.0-essentials_build"
    / "bin"
)


def play_audio(filename):
    pygame.mixer.init()
    try:
        pygame.mixer.music.load(str(filename))
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        pygame.mixer.music.unload()
    finally:
        pygame.mixer.quit()


def speak(text):
    print(f"Priya: {text}")
    try:
        with tempfile.TemporaryDirectory(prefix="priya-voice-") as directory:
            filename = Path(directory) / "voice.mp3"
            gTTS(text=text, lang="en", slow=False, tld="co.uk").save(str(filename))
            play_audio(filename)
    except (gTTSError, OSError, pygame.error) as error:
        LOG.warning("Voice output unavailable: %s", error)


def listen(prompt=None):
    if prompt:
        speak(prompt)
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("Listening...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=7)
        query = recognizer.recognize_google(audio, language="en-IN")
    except sr.WaitTimeoutError:
        print("No speech detected.")
        return ""
    except sr.UnknownValueError:
        print("Speech was not understood.")
        return ""
    except sr.RequestError as error:
        raise RuntimeError(f"Speech recognition service unavailable: {error}") from error
    except OSError as error:
        raise RuntimeError(f"Microphone unavailable: {error}") from error
    print(f"You said: {query}")
    return query.lower().strip()


def show_graph():
    speak("Generating a sample graph.")
    x = range(10)
    plt.plot(x, [i ** 2 for i in x])
    plt.title("Sample Graph")
    plt.show()


def play_song_offline(song_name):
    speak(f"Downloading {song_name} from YouTube for playback.")
    try:
        with tempfile.TemporaryDirectory(prefix="priya-song-") as directory:
            options = {
                "format": "bestaudio/best",
                "quiet": True,
                "noplaylist": True,
                "outtmpl": str(Path(directory) / "song.%(ext)s"),
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            }
            if (BUNDLED_FFMPEG / "ffmpeg.exe").is_file():
                options["ffmpeg_location"] = str(BUNDLED_FFMPEG)
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(f"ytsearch1:{song_name}", download=True)
            entries = info.get("entries", []) if info else []
            if not entries or not entries[0]:
                speak("Sorry, I could not find that song.")
                return
            speak(f"Now playing {entries[0]['title']}.")
            play_audio(Path(directory) / "song.mp3")
    except (yt_dlp.utils.DownloadError, OSError, pygame.error) as error:
        LOG.error("Song playback failed: %s", error)
        speak("Sorry, I could not download or play that song.")


def play_song_online(song_name):
    speak(f"Finding {song_name} on YouTube.")
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True}) as downloader:
            info = downloader.extract_info(f"ytsearch1:{song_name}", download=False)
        entries = info.get("entries", []) if info else []
        if not entries or not entries[0]:
            speak("Sorry, I could not find that song.")
            return
        if webbrowser.open(entries[0]["webpage_url"]):
            speak(f"Opened {entries[0]['title']} on YouTube.")
        else:
            speak("Sorry, I could not open your browser.")
    except (yt_dlp.utils.DownloadError, OSError, webbrowser.Error) as error:
        LOG.error("YouTube search failed: %s", error)
        speak("Sorry, I could not open that song on YouTube.")


def play_song(song_name=None):
    if not song_name:
        song_name = listen("Which song would you like me to play?")
    if not song_name:
        speak("Sorry, I did not catch the song name.")
        return
    choice = listen("Say online to open YouTube, or offline to download temporarily.")
    if "offline" in choice:
        play_song_offline(song_name)
    elif "online" in choice:
        play_song_online(song_name)
    else:
        speak("Sorry, please say online or offline and try again.")


def open_website(name, url):
    try:
        if webbrowser.open(url):
            speak(f"Opening {name}.")
            return
    except (OSError, webbrowser.Error) as error:
        LOG.error("Could not open %s: %s", name, error)
    speak(f"Sorry, I could not open {name}.")


COMMANDS = {
    "time": lambda: speak(f"The time is {datetime.datetime.now().strftime('%H:%M:%S')}"),
    "open youtube": lambda: open_website("YouTube", "https://youtube.com"),
    "open google": lambda: open_website("Google", "https://google.com"),
    "open chatgpt": lambda: open_website("ChatGPT", "https://chatgpt.com"),
    "show graph": show_graph,
}


def process_command(query):
    query = re.sub(r"^priya[,\s]+", "", query.lower().strip()).strip()
    if query in {"stop", "exit", "quit"}:
        speak("Goodbye. Priya signing off.")
        return False
    if query in {"play", "play song", "play a song"}:
        play_song()
        return True
    if query.startswith("play "):
        play_song(query[5:].strip())
        return True
    match = process.extractOne(query, COMMANDS.keys())
    if match and match[1] > 70:
        COMMANDS[match[0]]()
    else:
        speak("Sorry, I do not know how to do that yet.")
    return True


def main():
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    speak("Hello Naveen, Priya your AI assistant is online.")
    try:
        while True:
            command = listen()
            if command and not process_command(command):
                break
    except RuntimeError as error:
        LOG.error("%s", error)
        return 1
    except KeyboardInterrupt:
        print("\nPriya stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
