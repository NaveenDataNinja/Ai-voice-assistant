import speech_recognition as sr
from gtts import gTTS
import pygame, time, os, datetime, webbrowser
import matplotlib.pyplot as plt
import pandas as pd
from rapidfuzz import process
import yt_dlp
import urllib.parse

# --- Speak Function ---
def speak(text):
    print(f"Zara: {text}")
    tts = gTTS(text=text, lang='en', slow=False, tld='co.uk')
    filename = "voice.mp3"
    tts.save(filename)
    pygame.mixer.init()
    pygame.mixer.music.load(filename)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)
    pygame.mixer.music.unload()
    pygame.mixer.quit()
    os.remove(filename)

# --- Listen Function ---
def listen(prompt=None):
    if prompt:
        speak(prompt)
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening... 🎤")
        r.adjust_for_ambient_noise(source, duration=1)
        audio = r.listen(source, timeout=5, phrase_time_limit=7)
    try:
        query = r.recognize_google(audio, language="en-IN")
        print(f"You said: {query}")
        return query.lower()
    except:
        return ""

# --- Extra Function (Graph Example) ---
def show_graph():
    speak("Generating a random graph for you.")
    df = pd.DataFrame({"x": range(10), "y": [i**2 for i in range(10)]})
    plt.plot(df["x"], df["y"])
    plt.title("Sample Graph")
    plt.show()

# --- Play Song Offline using yt-dlp + pygame ---
def play_song_offline(song_name):
    speak(f"Fetching {song_name} from YouTube")
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'noplaylist': True,
        'outtmpl': 'song.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{song_name}", download=True)
            if "entries" in info:
                info = info["entries"][0]
            filename = ydl.prepare_filename(info)
            filename = os.path.splitext(filename)[0] + ".mp3"

            speak(f"Now playing {info['title']}")
            pygame.mixer.init()
            pygame.mixer.music.load(filename)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.5)
            pygame.mixer.quit()

            os.remove(filename)
    except Exception as e:
        speak(f"Sorry, I could not play the song. Error: {e}")

# --- Play Song Online via YouTube ---
def play_song_online(song_name):
    speak(f"Finding {song_name} on YouTube")
    ydl_opts = {'quiet': True, 'noplaylist': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{song_name}", download=False)
            if info['entries']:
                video_url = info['entries'][0]['webpage_url']
                speak(f"Playing {info['entries'][0]['title']} on YouTube")
                webbrowser.open(video_url)
            else:
                speak("Sorry, I couldn’t find that song.")
    except Exception as e:
        speak(f"Error opening YouTube: {e}")

# --- Ask user offline or online ---
def play_song(song_name=None):
    if not song_name:
        song_name = listen("Which song would you like me to play?")
    if song_name:
        choice = listen("Do you want to play it offline or online?")
        if "offline" in choice:
            play_song_offline(song_name)
        else:
            play_song_online(song_name)
    else:
        speak("Sorry, I did not catch the song name.")

# --- Command Dictionary ---
commands = {
    "time": lambda cmd: speak(f"The time is {datetime.datetime.now().strftime('%H:%M:%S')}"),
    "open youtube": lambda cmd: (speak("Opening YouTube"), webbrowser.open("https://youtube.com")),
    "play song": lambda cmd: play_song(),
    "open google": lambda cmd: (speak("Opening Google"), webbrowser.open("https://google.com")),
    "open chatgpt": lambda cmd: (speak("Opening ChatGPT"), webbrowser.open("https://chatgpt.com")),
    "show graph": lambda cmd: show_graph(),
    "stop": lambda cmd: (speak("Goodbye Naveen. Zara signing off."), exit())
}

# --- Match Command with Fuzzy Logic ---
def match_command(query):
    best_match, score, _ = process.extractOne(query, commands.keys())
    if score > 70:
        return best_match
    return None

# --- Main Loop ---
speak("Hello Naveen, Zara your AI assistant is  online.")
while True:
    command = listen()
    if command:
        action = match_command(command)
        if action:
            commands[action](command)
        else:
            if "play" in command:
                play_song(command.replace("play", "").strip())
            else:
                speak("Sorry, I don’t know how to do that yet.")
