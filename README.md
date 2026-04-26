# ARIA_chatpod
ARIA — AI Voice Assistant Chat Pod

A fully functional AI voice assistant with an animated SVG avatar, real-time lip-sync, eye blinking, speech recognition, text-to-speech, and Groq AI streaming — all in a single Python file.

Features

🎭Animated SVG Avatar — hand-crafted female face with smooth animations
👄 Real-time Lip-sync — 3-frame mouth animation (closed → half → open) synced to AI speech
👁️ Eye Blinking — randomised natural blink every 2–5 seconds
💜 Status Ring — glowing purple ring when talking, teal when listening
🌊 Wave Visualizer — animated bars showing audio activity
🎤 Voice Input — speak directly via microphone (Google Speech Recognition)
🔊 Female TTS Voice — offline text-to-speech using pyttsx3 (Zira on Windows, Samantha on macOS)
⚡ Groq AI Backend — ultra-fast streaming responses using llama-3.3-70b-versatile
💬 Streaming Chat UI — tokens appear live, word by word
🔐 Secure Config — API keys managed via .env file
🗑️ Chat History — clear conversation anytime



Project Structure
your-project/
├── voice_chat_pod.py   ← entire app (Flask + AI + TTS + frontend)
├── .env                ← your secret keys (never commit this!)
├── .env.example        ← safe template to share
└── .gitignore          ← keeps .env out of git

Quick Start
Install dependencies:
bashpip install groq flask SpeechRecognition pyttsx3 pyaudio python-dotenv

Windows users: If pyaudio fails, install it via:
bashpip install pipwin
pipwin install pyaudio
Set up your .env file:
bashcp .env.example .env
Edit .env and add your Groq API key:
envGROQ_API_KEY=gsk_your_key_here
Get a free Groq API key at console.groq.com
Run the app
bashpython voice:_chat_pod.py
Open your browser at http://localhost:5000 


Changing the Voice:
List all available voices on your system:
pythonimport pyttsx3
engine = pyttsx3.init()
for v in engine.getProperty('voices'):
    print(v.id, '|', v.name)
Set a specific voice in .env:
env# Windows
ARIA_VOICE=zira      # female
ARIA_VOICE=david     # male

Dependencies;
txtgroq
flask
SpeechRecognition
pyttsx3
pyaudio
python-dotenv
Install all at once:
bashpip install groq flask SpeechRecognition pyttsx3 pyaudio python-dotenv


SpeechRecognition — mic input library

