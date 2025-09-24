import speech_recognition as sr
from gtts import gTTS
import pygame, time, os, datetime, webbrowser
import matplotlib.pyplot as plt
import pandas as pd
from rapidfuzz import process
import urllib.parse

def play_song_on_youtube(command):
    words = command.replace("open youtube", "").replace("play", "").strip()
    if words:
        query = urllib.parse.quote(words)
        url = f"https://www.youtube.com/results?search_query={query}"
        speak(f"Playing {words} on YouTube")
        webbrowser.open(url)
    else:
        speak("Please tell me the song name.")


# --- Speak Function ---
def speak(text):
    print(f"JARVIS: {text}")
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
def listen():
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
# --- Play Song ---
def play_song_on_youtube(song_name=None):
    if not song_name:  # if no song passed, ask user
        speak("Which song would you like me to play?")
        song_name = listen()
    if song_name:
        query = urllib.parse.quote(song_name)
        url = f"https://www.youtube.com/results?search_query={query}"
        speak(f"Playing {song_name} on YouTube")
        webbrowser.open(url)
    else:
        speak("Sorry, I did not catch the song name.")

# --- Command Dictionary ---
commands = {
    "time": lambda cmd: speak(f"The time is {datetime.datetime.now().strftime('%H:%M:%S')}"),
    "open youtube": lambda cmd: (speak("Opening YouTube"), webbrowser.open("https://youtube.com")),
    "play song": lambda cmd: play_song_on_youtube(),  # now interactive 🎶
    "open google": lambda cmd: (speak("Opening Google"), webbrowser.open("https://google.com")),
    "open chatgpt": lambda cmd: (speak("Opening ChatGPT"), webbrowser.open("https://chatgpt.com")),
    "show graph": lambda cmd: show_graph(),
    "stop": lambda cmd: (speak("Goodbye Naveen. Jarvis signing off."), exit())
}


# --- Match Command with Fuzzy Logic ---
def match_command(query):
    best_match, score, _ = process.extractOne(query, commands.keys())
    if score > 70:
        return best_match
    return None

# --- Main Loop ---
# --- Main Loop ---
speak("Hello Naveen, Zara your AI assistant is online.")
last_command = ""
while True:
    command = listen()
    if command:
        last_command = command  # store it
        action = match_command(command)
        if action:
            commands[action](command)   # FIXED ✅
        else:
            # Special case for YouTube play
            if "play" in command and "youtube" in command:
                play_song_on_youtube(command)
            else:
                speak("Sorry, I don’t know how to do that yet.")

