
import os
import json
import threading
import queue
import time
from dotenv import load_dotenv
from flask import Flask, render_template_string, request, jsonify, Response, stream_with_context
from groq import Groq


load_dotenv()


try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False
    print("[WARN] SpeechRecognition not installed. Mic input disabled.")

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    print("[WARN] pyttsx3 not installed. Voice output disabled.")


GROQ_API_KEY  = os.environ.get("GROQ_API_KEY", "")
MODEL         = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_TOKENS    = int(os.environ.get("ARIA_MAX_TOKENS", 1024))
FLASK_PORT    = int(os.environ.get("FLASK_PORT", 5000))
FLASK_DEBUG   = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
SYSTEM_PROMPT = os.environ.get(
    "ARIA_SYSTEM_PROMPT",
    "You are ARIA, a warm, friendly and intelligent female AI assistant. "
    "You speak with kindness, clarity and confidence. "
    "Keep responses conversational and concise — under 3 sentences unless more detail is asked."
)

app    = Flask(__name__)
client = Groq(api_key=GROQ_API_KEY)


chat_history: list[dict] = []
tts_queue: queue.Queue   = queue.Queue()
tts_lock                  = threading.Lock()



def tts_worker():
    """Background thread: speak queued text with a soft female voice."""
    if not TTS_AVAILABLE:
        return
    engine = pyttsx3.init()
    engine.setProperty("rate", 178)       
    engine.setProperty("volume", 1.0)

    
    voices = engine.getProperty("voices")
    female_keywords = ["zira", "samantha", "victoria", "karen",
                       "hazel", "susan", "female", "linda", "jenny",
                       "aria", "eva", "helen", "fiona"]
    chosen = None
    for keyword in female_keywords:
        for v in voices:
            if keyword in v.name.lower() or keyword in v.id.lower():
                chosen = v.id
                break
        if chosen:
            break

    
    if not chosen:
        male_keywords = ["david", "mark", "james", "george", "daniel", "alex"]
        for v in voices:
            if not any(k in v.name.lower() for k in male_keywords):
                chosen = v.id
                break

    
    if not chosen and len(voices) > 1:
        chosen = voices[1].id
    elif not chosen and voices:
        chosen = voices[0].id

    if chosen:
        engine.setProperty("voice", chosen)
        print(f"[TTS] Using voice: {chosen}")
    while True:
        text = tts_queue.get()
        if text is None:
            break
        with tts_lock:
            engine.say(text)
            engine.runAndWait()
        tts_queue.task_done()

if TTS_AVAILABLE:
    tts_thread = threading.Thread(target=tts_worker, daemon=True)
    tts_thread.start()


def speak(text: str):
    """Queue text for TTS."""
    if TTS_AVAILABLE:
        tts_queue.put(text)



def listen_once() -> str | None:
    """Record one utterance from the microphone and return transcript."""
    if not SR_AVAILABLE:
        return None
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.pause_threshold  = 0.8
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=8, phrase_time_limit=15)
            return recognizer.recognize_google(audio)
        except (sr.WaitTimeoutError, sr.UnknownValueError, sr.RequestError):
            return None



def stream_groq(user_message: str):
    """Generator: yield SSE chunks from Groq, accumulate reply."""
    chat_history.append({"role": "user", "content": user_message})
    full_reply = []

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + chat_history

    with client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=messages,
        stream=True,
    ) as stream:
        for chunk in stream:
            delta = chunk.choices[0].delta
            text_chunk = delta.content or ""
            if text_chunk:
                full_reply.append(text_chunk)
                yield f"data: {json.dumps({'chunk': text_chunk})}\n\n"

    reply = "".join(full_reply)
    chat_history.append({"role": "assistant", "content": reply})
    speak(reply)
    yield f"data: {json.dumps({'done': True, 'full': reply})}\n\n"



@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/static/<path:filename>")
def static_files(filename):
    from flask import send_from_directory
    import os
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    return send_from_directory(static_dir, filename)


@app.route("/chat", methods=["POST"])
def chat():
    data    = request.get_json(force=True)
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "empty message"}), 400
    return Response(
        stream_with_context(stream_groq(message)),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/listen", methods=["POST"])
def listen():
    """Trigger microphone capture and return transcript."""
    transcript = listen_once()
    if transcript:
        return jsonify({"transcript": transcript})
    return jsonify({"error": "Could not understand audio"}), 400


@app.route("/history", methods=["GET"])
def history():
    return jsonify(chat_history)


@app.route("/reset", methods=["POST"])
def reset():
    chat_history.clear()
    return jsonify({"status": "cleared"})



HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>ARIA – Voice Assistant</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet"/>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:        #0d0d14;
    --surface:   #14141f;
    --surface2:  #1c1c2e;
    --border:    rgba(255,255,255,0.07);
    --border2:   rgba(255,255,255,0.14);
    --purple:    #7c6af7;
    --purple-lt: #a897ff;
    --purple-bg: rgba(124,106,247,0.12);
    --teal:      #2dd4bf;
    --teal-bg:   rgba(45,212,191,0.1);
    --text:      #e8e6ff;
    --muted:     #7b7a9e;
    --user-bg:   #3d2f9e;
    --ai-bg:     #1c1c2e;
    --danger:    #f87171;
    --font:      'DM Sans', sans-serif;
    --mono:      'Space Mono', monospace;
  }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--font);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1rem;
  }

  /* ── Animated background ── */
  body::before {
    content: '';
    position: fixed; inset: 0;
    background: radial-gradient(ellipse 70% 60% at 20% 20%, rgba(124,106,247,0.08) 0%, transparent 60%),
                radial-gradient(ellipse 50% 50% at 80% 80%, rgba(45,212,191,0.05) 0%, transparent 60%);
    pointer-events: none;
    z-index: 0;
  }

  .pod {
    position: relative; z-index: 1;
    display: flex;
    gap: 20px;
    width: 100%;
    max-width: 820px;
    background: var(--surface);
    border: 1px solid var(--border2);
    border-radius: 24px;
    padding: 24px;
    box-shadow: 0 32px 80px rgba(0,0,0,0.6);
  }

  /* ── Avatar panel ── */
  .avatar-panel {
    width: 200px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
  }

  .avatar-outer {
    width: 110px; height: 110px;
    border-radius: 50%;
    border: 2px solid var(--purple);
    display: flex; align-items: center; justify-content: center;
    position: relative;
    transition: border-color 0.3s;
  }
  .avatar-outer.talking {
    animation: ring-pulse 0.8s ease-in-out infinite alternate;
  }
  .avatar-outer.listening {
    border-color: var(--teal);
    animation: ring-pulse-teal 0.6s ease-in-out infinite alternate;
  }
  @keyframes ring-pulse {
    from { box-shadow: 0 0 0 0 rgba(124,106,247,0.3); }
    to   { box-shadow: 0 0 0 16px rgba(124,106,247,0); }
  }
  @keyframes ring-pulse-teal {
    from { box-shadow: 0 0 0 0 rgba(45,212,191,0.3); }
    to   { box-shadow: 0 0 0 16px rgba(45,212,191,0); }
  }

  .avatar-inner {
    width: 90px; height: 90px;
    border-radius: 50%;
    background: linear-gradient(135deg, #2d2060 0%, #1a1040 100%);
    display: flex; align-items: center; justify-content: center;
    font-size: 42px;
  }

  .avatar-name {
    font-family: var(--mono);
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 4px;
    color: var(--purple-lt);
  }

  .status-badge {
    display: flex; align-items: center; gap: 6px;
    font-size: 12px;
    color: var(--muted);
    background: var(--surface2);
    border: 1px solid var(--border);
    padding: 4px 12px;
    border-radius: 99px;
    font-family: var(--mono);
  }
  .status-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: #4ade80;
    transition: background 0.3s;
  }
  .status-dot.talking { background: var(--purple-lt); animation: blink 0.5s infinite; }
  .status-dot.listening { background: var(--teal); animation: blink 0.4s infinite; }
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.2} }

  /* Wave visualiser */
  .wave { display: flex; align-items: flex-end; gap: 3px; height: 32px; }
  .wave span {
    width: 4px; border-radius: 2px;
    background: var(--purple);
    opacity: 0.25;
    transition: opacity 0.3s;
  }
  .wave.active span { opacity: 1; }
  .wave.active span:nth-child(1) { animation: wv 0.7s 0.0s infinite alternate; }
  .wave.active span:nth-child(2) { animation: wv 0.7s 0.1s infinite alternate; }
  .wave.active span:nth-child(3) { animation: wv 0.7s 0.2s infinite alternate; }
  .wave.active span:nth-child(4) { animation: wv 0.7s 0.15s infinite alternate; }
  .wave.active span:nth-child(5) { animation: wv 0.7s 0.05s infinite alternate; }
  .wave.active span:nth-child(6) { animation: wv 0.7s 0.25s infinite alternate; }
  .wave.active span:nth-child(7) { animation: wv 0.7s 0.1s infinite alternate; }
  @keyframes wv { from { transform: scaleY(0.3); } to { transform: scaleY(1); } }
  .wave span:nth-child(1){height:8px} .wave span:nth-child(2){height:18px}
  .wave span:nth-child(3){height:26px} .wave span:nth-child(4){height:14px}
  .wave span:nth-child(5){height:22px} .wave span:nth-child(6){height:10px}
  .wave span:nth-child(7){height:16px}

  .wave-teal.active span { background: var(--teal); }

  /* ── Chat panel ── */
  .chat-panel { flex: 1; display: flex; flex-direction: column; gap: 12px; min-width: 0; }

  .chat-header {
    display: flex; justify-content: space-between; align-items: center;
  }
  .chat-title { font-size: 13px; color: var(--muted); font-family: var(--mono); letter-spacing: 1px; }
  .btn-reset {
    font-size: 11px; font-family: var(--mono);
    color: var(--muted); background: transparent;
    border: 1px solid var(--border); border-radius: 6px;
    padding: 3px 8px; cursor: pointer;
    transition: color 0.2s, border-color 0.2s;
  }
  .btn-reset:hover { color: var(--danger); border-color: var(--danger); }

  .messages {
    flex: 1;
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 14px;
    height: 300px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 10px;
    scroll-behavior: smooth;
  }
  .messages::-webkit-scrollbar { width: 4px; }
  .messages::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }

  .msg {
    max-width: 82%;
    padding: 9px 14px;
    border-radius: 14px;
    font-size: 14px;
    line-height: 1.6;
    word-break: break-word;
    animation: msg-in 0.2s ease;
  }
  @keyframes msg-in { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

  .msg.user {
    align-self: flex-end;
    background: var(--user-bg);
    color: #ddd6fe;
    border-bottom-right-radius: 4px;
  }
  .msg.ai {
    align-self: flex-start;
    background: var(--ai-bg);
    color: var(--text);
    border: 1px solid var(--border2);
    border-bottom-left-radius: 4px;
  }
  .msg.typing { opacity: 0.6; font-style: italic; color: var(--muted); }

  /* Input row */
  .input-row { display: flex; gap: 8px; }

  .mic-btn {
    width: 44px; height: 44px; border-radius: 12px; flex-shrink: 0;
    border: 1px solid var(--border2);
    background: var(--purple-bg);
    color: var(--purple-lt);
    font-size: 18px;
    cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: background 0.2s, transform 0.1s;
  }
  .mic-btn:hover { background: rgba(124,106,247,0.22); }
  .mic-btn:active { transform: scale(0.95); }
  .mic-btn.recording { background: rgba(248,113,113,0.15); color: var(--danger); border-color: var(--danger); animation: blink 0.6s infinite; }

  .text-input {
    flex: 1; height: 44px;
    background: var(--surface2);
    border: 1px solid var(--border2);
    border-radius: 12px;
    padding: 0 14px;
    font-size: 14px;
    font-family: var(--font);
    color: var(--text);
    outline: none;
    transition: border-color 0.2s;
  }
  .text-input:focus { border-color: var(--purple); }
  .text-input::placeholder { color: var(--muted); }

  .send-btn {
    height: 44px; padding: 0 18px;
    border-radius: 12px;
    border: none;
    background: var(--purple);
    color: #fff;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s, transform 0.1s;
    white-space: nowrap;
  }
  .send-btn:hover { background: var(--purple-lt); }
  .send-btn:active { transform: scale(0.97); }
  .send-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  .feature-pills {
    display: flex; gap: 6px; flex-wrap: wrap;
  }
  .pill {
    font-size: 11px; font-family: var(--mono);
    padding: 3px 8px;
    border-radius: 6px;
    border: 1px solid var(--border);
    color: var(--muted);
  }
  .pill.on { color: var(--teal); border-color: rgba(45,212,191,0.3); background: var(--teal-bg); }

  @media (max-width: 600px) {
    .pod { flex-direction: column; }
    .avatar-panel { width: 100%; flex-direction: row; flex-wrap: wrap; justify-content: center; }
    .messages { height: 220px; }
  }
</style>
</head>
<body>

<div class="pod">

  <!-- ARIA Female Avatar Panel -->
  <div class="avatar-panel">
    <div class="avatar-outer" id="avatarOuter">
      <svg id="face" viewBox="0 0 140 155" xmlns="http://www.w3.org/2000/svg"
           style="width:110px;height:110px;border-radius:50%;overflow:hidden;display:block;">
        <rect width="140" height="155" fill="#f2ece6"/>
        <path d="M0,138 Q20,118 45,116 L55,126 L70,120 L85,126 L95,116 Q120,118 140,138 L140,155 L0,155Z" fill="#f5f0ea"/>
        <path d="M55,116 Q70,128 85,116" fill="none" stroke="#ddd5cc" stroke-width="1"/>
        <path d="M58,104 Q58,118 70,119 Q82,118 82,104" fill="#f5d5b8"/>
        <path d="M28,68 Q26,90 30,104 Q40,124 70,126 Q100,124 110,104 Q114,90 112,68 Q110,44 70,38 Q30,44 28,68Z" fill="#fde8cc"/>
        <ellipse cx="36" cy="84" rx="10" ry="7" fill="#f4a090" opacity="0.18"/>
        <ellipse cx="104" cy="84" rx="10" ry="7" fill="#f4a090" opacity="0.18"/>
        <path d="M28,68 Q20,72 20,82 Q20,92 28,94 Q32,90 32,82 Q32,72 28,68Z" fill="#f0c8a0"/>
        <path d="M112,68 Q120,72 120,82 Q120,92 112,94 Q108,90 108,82 Q108,72 112,68Z" fill="#f0c8a0"/>
        <path d="M26,60 Q28,28 70,22 Q112,28 114,60 Q108,36 70,32 Q32,36 26,60Z" fill="#2e2018"/>
        <path d="M26,62 Q22,78 24,100 Q26,110 30,112 Q26,96 28,76Z" fill="#2e2018"/>
        <path d="M114,62 Q118,78 116,100 Q114,110 110,112 Q114,96 112,76Z" fill="#2e2018"/>
        <path d="M28,62 Q34,30 70,24 Q106,30 112,62 Q102,38 70,34 Q38,38 28,62Z" fill="#332214"/>
        <path d="M50,28 Q70,24 88,30 Q72,26 52,30Z" fill="#4a3222" opacity="0.6"/>
        <path d="M24,100 Q28,118 38,120 Q30,116 26,106Z" fill="#2e2018"/>
        <path d="M116,100 Q112,118 102,120 Q110,116 114,106Z" fill="#2e2018"/>
        <path d="M34,50 Q70,42 106,50 Q100,34 70,30 Q40,34 34,50Z" fill="#fde8cc"/>
        <path d="M40,54 Q52,49 62,52" stroke="#2e2018" stroke-width="2.8" fill="none" stroke-linecap="round"/>
        <path d="M78,52 Q88,49 100,54" stroke="#2e2018" stroke-width="2.8" fill="none" stroke-linecap="round"/>
        <ellipse cx="51" cy="66" rx="10" ry="8.5" fill="white"/>
        <ellipse cx="89" cy="66" rx="10" ry="8.5" fill="white"/>
        <circle cx="51" cy="67" r="6.5" fill="#7a4a28"/>
        <circle cx="89" cy="67" r="6.5" fill="#7a4a28"/>
        <circle cx="51" cy="67" r="4" fill="#1a0e06"/>
        <circle cx="89" cy="67" r="4" fill="#1a0e06"/>
        <ellipse cx="53" cy="64.5" rx="1.8" ry="1.6" fill="white" opacity="0.95"/>
        <ellipse cx="91" cy="64.5" rx="1.8" ry="1.6" fill="white" opacity="0.95"/>
        <path d="M41,61 Q51,57 61,61" stroke="#1a0e06" stroke-width="1.6" fill="none" stroke-linecap="round"/>
        <path d="M79,61 Q89,57 99,61" stroke="#1a0e06" stroke-width="1.6" fill="none" stroke-linecap="round"/>
        <path d="M41,61 Q39,58 41,56" stroke="#1a0e06" stroke-width="1" fill="none" stroke-linecap="round"/>
        <path d="M61,61 Q63,58 62,56" stroke="#1a0e06" stroke-width="1" fill="none" stroke-linecap="round"/>
        <path d="M79,61 Q77,58 78,56" stroke="#1a0e06" stroke-width="1" fill="none" stroke-linecap="round"/>
        <path d="M99,61 Q101,58 100,56" stroke="#1a0e06" stroke-width="1" fill="none" stroke-linecap="round"/>
        <!-- Blink -->
        <g id="blinkG" visibility="hidden">
          <ellipse cx="51" cy="66" rx="10" ry="8.5" fill="#fde8cc"/>
          <ellipse cx="89" cy="66" rx="10" ry="8.5" fill="#fde8cc"/>
          <path d="M41,66 Q51,72 61,66" stroke="#1a0e06" stroke-width="1.6" fill="none" stroke-linecap="round"/>
          <path d="M79,66 Q89,72 99,66" stroke="#1a0e06" stroke-width="1.6" fill="none" stroke-linecap="round"/>
          <path d="M41,66 Q51,62 61,66" stroke="#1a0e06" stroke-width="1.4" fill="none"/>
          <path d="M79,66 Q89,62 99,66" stroke="#1a0e06" stroke-width="1.4" fill="none"/>
        </g>
        <path d="M67,78 Q65,86 66,92 Q70,95 74,92 Q75,86 73,78" stroke="#d4906a" stroke-width="1" fill="none" stroke-linecap="round"/>
        <path d="M64,91 Q67,93 70,92 Q73,93 76,91" stroke="#c8806a" stroke-width="0.8" fill="none" stroke-linecap="round"/>
        <!-- Mouth neutral -->
        <g id="mouthNeutral">
          <path d="M56,104 Q63,100 70,102 Q77,100 84,104 Q77,108 70,107 Q63,108 56,104Z" fill="#e8907a"/>
          <path d="M58,103 Q64,100 70,101 Q76,100 82,103" stroke="#c87060" stroke-width="0.8" fill="none"/>
          <ellipse cx="70" cy="106" rx="8" ry="2" fill="#f0a888" opacity="0.35"/>
        </g>
        <!-- Mouth open -->
        <g id="mouthOpen" visibility="hidden">
          <path d="M56,102 Q63,98 70,100 Q77,98 84,102" stroke="#c87060" stroke-width="1.2" fill="none" stroke-linecap="round"/>
          <path d="M56,102 Q63,98 70,100 Q77,98 84,102 Q82,114 70,115 Q58,114 56,102Z" fill="#8a2828"/>
          <path d="M60,103 Q70,100 80,103 Q80,107 70,107 Q60,107 60,103Z" fill="#f5f0ec" opacity="0.7"/>
          <ellipse cx="70" cy="104" rx="10" ry="3" fill="#f0a888" opacity="0.25"/>
        </g>
        <g id="mouthHalf" visibility="hidden">
          <path d="M56,102 Q63,98 70,100 Q77,98 84,102" stroke="#c87060" stroke-width="1.2" fill="none" stroke-linecap="round"/>
          <path d="M58,102 Q70,100 82,102 Q80,110 70,111 Q60,110 58,102Z" fill="#8a2828"/>
          <path d="M56,102 Q63,98 70,100 Q77,98 84,102 Q77,106 70,105 Q63,106 56,102Z" fill="#e8907a"/>
        </g>
        <path d="M46,34 Q42,46 44,58 Q46,48 50,36Z" fill="#2e2018" opacity="0.9"/>
        <path d="M62,28 Q60,42 62,52 Q65,42 66,30Z" fill="#2e2018" opacity="0.8"/>
        <path d="M78,28 Q80,42 78,52 Q75,42 74,30Z" fill="#2e2018" opacity="0.7"/>
        <path d="M92,34 Q96,46 94,58 Q92,48 88,36Z" fill="#2e2018" opacity="0.9"/>
      </svg>
    </div>
    <div class="avatar-name">ARIA</div>
    <div class="status-badge">
      <div class="status-dot" id="statusDot"></div>
      <span id="statusText">ready</span>
    </div>
    <div class="wave" id="waveEl">
      <span></span><span></span><span></span><span></span>
      <span></span><span></span><span></span>
    </div>
    <div class="feature-pills">
      <div class="pill {% if sr_ok %}on{% endif %}">🎤 mic</div>
      <div class="pill {% if tts_ok %}on{% endif %}">🔊 tts</div>
    </div>
  </div>

  <!-- Chat -->
  <div class="chat-panel">
    <div class="chat-header">
      <span class="chat-title">// conversation</span>
      <button class="btn-reset" onclick="resetChat()">clear</button>
    </div>
    <div class="messages" id="messages">
      <div class="msg ai">Hey! I'm ARIA — ask me anything, or hit the mic to talk.</div>
    </div>
    <div class="input-row">
      <button class="mic-btn" id="micBtn" title="Click to speak" onclick="startListening()">🎤</button>
      <input class="text-input" id="textInput" placeholder="Type a message…"
             onkeydown="if(event.key==='Enter' && !event.shiftKey){ event.preventDefault(); sendMessage(); }"/>
      <button class="send-btn" id="sendBtn" onclick="sendMessage()">Send →</button>
    </div>
  </div>

</div>

<script>
  const messagesEl  = document.getElementById('messages');
  const textInput   = document.getElementById('textInput');
  const sendBtn     = document.getElementById('sendBtn');
  const micBtn      = document.getElementById('micBtn');
  const avatarOuter = document.getElementById('avatarOuter');
  const statusDot   = document.getElementById('statusDot');
  const statusText  = document.getElementById('statusText');
  const waveEl      = document.getElementById('waveEl');
  const blinkOverlay= document.getElementById('blinkG');
  const mNeutral    = document.getElementById('mouthNeutral');
  const mOpen       = document.getElementById('mouthOpen');
  const mHalf       = document.getElementById('mouthHalf');

  let isBusy = false;
  let mouthTimer = null;
  let mouthFrame = 0;

  function startLipSync() {
    stopLipSync();
    mouthTimer = setInterval(() => {
      mouthFrame = (mouthFrame + 1) % 3;
      mNeutral.setAttribute('visibility', mouthFrame === 0 ? 'visible' : 'hidden');
      mOpen.setAttribute('visibility',    mouthFrame === 1 ? 'visible' : 'hidden');
      mHalf.setAttribute('visibility',    mouthFrame === 2 ? 'visible' : 'hidden');
    }, 150);
  }

  function stopLipSync() {
    clearInterval(mouthTimer);
    mNeutral.setAttribute('visibility', 'visible');
    mOpen.setAttribute('visibility',    'hidden');
    mHalf.setAttribute('visibility',    'hidden');
    mouthFrame = 0;
  }

  function scheduleBlink() {
    setTimeout(() => {
      blinkOverlay.setAttribute('visibility', 'visible');
      setTimeout(() => {
        blinkOverlay.setAttribute('visibility', 'hidden');
        scheduleBlink();
      }, 130);
    }, 2500 + Math.random() * 3000);
  }
  scheduleBlink();

  function setStatus(mode) {
    avatarOuter.className = 'avatar-outer';
    statusDot.className   = 'status-dot';
    waveEl.className      = 'wave';
    stopLipSync();

    const map = {
      idle:      ['ready',      '',          '',                         ''],
      thinking:  ['thinking\u2026', '',      '',                         ''],
      talking:   ['speaking',   'talking',   'status-dot talking',       'active'],
      listening: ['listening',  'listening', 'status-dot listening',     'active wave-teal'],
    };
    const [label, ringCls, dotCls, waveCls] = map[mode] || map.idle;
    statusText.textContent = label;
    if (ringCls) avatarOuter.classList.add(ringCls);
    if (dotCls)  statusDot.className = dotCls;
    if (waveCls) waveEl.className = 'wave ' + waveCls;
    if (mode === 'talking') startLipSync();
  }

  function addMessage(role, text, typing=false) {
    const div = document.createElement('div');
    div.className = 'msg ' + role + (typing ? ' typing' : '');
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  async function sendMessage(overrideText) {
    const text = (overrideText || textInput.value).trim();
    if (!text || isBusy) return;
    isBusy = true;
    textInput.value = '';
    sendBtn.disabled = true;
    setStatus('thinking');
    addMessage('user', text);

    const aiDiv = addMessage('ai', '\u258c', true);

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({message: text})
      });
      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullText = '';
      setStatus('talking');

      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, {stream:true});
        const lines = buffer.split('\\n');
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data:')) continue;
          const payload = JSON.parse(line.slice(5).trim());
          if (payload.chunk) {
            fullText += payload.chunk;
            aiDiv.textContent = fullText + '\u258c';
            aiDiv.classList.remove('typing');
            messagesEl.scrollTop = messagesEl.scrollHeight;
          }
          if (payload.done) { aiDiv.textContent = payload.full; }
        }
      }
    } catch(err) {
      aiDiv.textContent = 'Error: ' + err.message;
    } finally {
      isBusy = false;
      sendBtn.disabled = false;
      setStatus('idle');
    }
  }

  async function startListening() {
    if (isBusy) return;
    micBtn.classList.add('recording');
    setStatus('listening');
    try {
      const res  = await fetch('/listen', {method:'POST'});
      const data = await res.json();
      if (data.transcript) { textInput.value = data.transcript; sendMessage(); }
      else setStatus('idle');
    } catch { setStatus('idle'); }
    finally { micBtn.classList.remove('recording'); }
  }

  async function resetChat() {
    await fetch('/reset', {method:'POST'});
    messagesEl.innerHTML = '';
    addMessage('ai', "Chat cleared. What's on your mind?");
  }
</script>
</body>
</html>
"""


@app.context_processor
def inject_flags():
    return {"sr_ok": SR_AVAILABLE, "tts_ok": TTS_AVAILABLE}




if __name__ == "__main__":
    if not GROQ_API_KEY:
        print("\n[ERROR] Set GROQ_API_KEY environment variable before running.\n"
              "  export GROQ_API_KEY=gsk_...\n"
              "  Get a free key at https://console.groq.com\n")
    else:
        print("\n🧑  ARIA Voice Assistant starting…  (Groq · llama-3.3-70b-versatile · Male voice)")
        print("   Open http://localhost:5000  in your browser\n")
    app.run(debug=FLASK_DEBUG, port=FLASK_PORT, threaded=True)
