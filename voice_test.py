from gtts import gTTS
import pygame
import time

def speak(text):
    print(f"Priya: {text}")
    tts = gTTS(text=text, lang='en', slow=False, tld='co.uk')
    filename = "voice.mp3"
    tts.save(filename)

    # Initialize pygame mixer
    pygame.mixer.init()
    pygame.mixer.music.load(filename)
    pygame.mixer.music.play()

    # Keep program alive until audio finishes
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)

speak("Hello, this is Priya your AI assistant speaking.")
