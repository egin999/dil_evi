"""
app.py — Dil Evi Web Interface
Works on desktop + mobile + tablet (responsive)
Real-time voice with Gradio
"""
import gradio as gr
import asyncio
import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
import base64
import io

from audio_io import MicrophoneStream, SpeakerStream
from realtime_client import RealtimeClient

load_dotenv()

CHARACTERS = [
    {"name": "Sarah", "voice": "shimmer"},
    {"name": "James", "voice": "echo"},
    {"name": "Amelia", "voice": "sage"},
]

MEMORY_PATH = Path("memory.json")

# Global state
client = None
speaker = None
chat_history = []
current_character = None
is_running = False
audio_buffer = None

def load_memory() -> dict:
    if MEMORY_PATH.exists():
        try:
            return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"level": "A2", "sessions": 0}

def save_memory(m: dict) -> None:
    MEMORY_PATH.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")

def build_instructions(character: dict, memory: dict) -> str:
    return (
        f"Sen {character['name']}, Türk bir arkadaşın İngilizce öğrenmesine "
        f"yardım eden bir abi/kardeş gibisin. Seviye: CEFR {memory['level']}. "
        f"Sen iki dili de akıcı konuşuyorsun. Resmi öğretmen DEĞİLSİN — "
        f"samimi, rahat, dost gibisin.\n\n"
        f"Espri anlayışın var. 'Eyvallah', 'valla', 'reis' gibi samimi ifadeler.\n\n"
        f"HER cevabında en az bir TAM İngilizce cümle olsun.\n\n"
        f"Formül: [Türkçe samimi tepki] + [İngilizce cümle]\n\n"
        f"1-3 kısa cümle. Türkçe + İngilizce doğal karışım."
    )

async def run_realtime_session(character_name):
    """Realtime session çalıştır."""
    global client, speaker, chat_history, current_character, is_running, audio_buffer
    
    memory = load_memory()
    character = next((c for c in CHARACTERS if c["name"] == character_name), CHARACTERS[0])
    current_character = character
    chat_history = []
    is_running = True
    
    speaker = SpeakerStream()
    mic = MicrophoneStream()
    
    def on_audio_delta(pcm: bytes):
        speaker.write(pcm)
    
    def on_user_transcript(text: str):
        t = text.strip()
        if not t or len(t) < 2:
            return
        latin_chars = sum(1 for c in t if c.isalpha() and ord(c) < 0x0400)
        if latin_chars == 0:
            return
        chat_history.append(("👤 You", t))
    
    def on_assistant_transcript(text: str):
        if text.strip():
            chat_history.append((f"🤖 {character['name']}", text))
    
    def on_error(msg: str):
        print(f"Error: {msg}")
    
    client = RealtimeClient(
        instructions=build_instructions(character, memory),
        voice=character["voice"],
        on_audio_delta=on_audio_delta,
        on_user_started=lambda: None,
        on_user_stopped=lambda: None,
        on_user_transcript=on_user_transcript,
        on_assistant_transcript=on_assistant_transcript,
        on_response_started=lambda: None,
        on_response_done=lambda: None,
        on_error=on_error,
    )
    
    await client.connect()
    mic.start()
    speaker.start()
    
    await asyncio.sleep(0.3)
    
    await client.request_response(
        instructions="Arkadaşını samimi bir şekilde selamla. Kısa bir cümle."
    )
    
    async def pump_mic():
        loop = asyncio.get_running_loop()
        while is_running:
            try:
                pcm = await loop.run_in_executor(None, mic.queue.get, True)
                if pcm:
                    await client.send_audio(pcm)
            except:
                await asyncio.sleep(0.01)
    
    try:
        await asyncio.gather(
            pump_mic(),
            client.run_receive_loop(),
        )
    except asyncio.CancelledError:
        pass
    finally:
        is_running = False
        mic.stop()
        speaker.stop()
        await client.close()

def start_conversation(character_name):
    """Konuşmayı başlat."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_realtime_session(character_name))
    except Exception as e:
        return f"❌ Hata: {e}"
    
    return f"✅ {character_name} ile konuşma bitti!"

def get_chat_display():
    """Chat'i göster."""
    if not chat_history:
        return "Henüz sohbet başlamadı..."
    
    text = ""
    for speaker_name, message in chat_history:
        text += f"**{speaker_name}:** {message}\n\n"
    return text

def refresh_chat():
    """Chat'i refresh et."""
    return get_chat_display()

# Custom CSS for mobile responsive design
css = """
@media (max-width: 768px) {
    .gradio-container {
        max-width: 100% !important;
        padding: 0 !important;
    }
    
    .chat-box {
        min-height: 400px !important;
        max-height: 60vh !important;
    }
    
    button {
        font-size: 16px !important;
        padding: 12px !important;
    }
    
    .character-button {
        padding: 10px !important;
        font-size: 14px !important;
    }
}

@media (max-width: 480px) {
    .gradio-container {
        width: 100vw !important;
        margin: 0 !important;
    }
    
    button {
        font-size: 14px !important;
        height: auto !important;
        min-height: 50px !important;
    }
    
    .chat-message {
        font-size: 13px !important;
    }
}

.header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 20px;
    border-radius: 10px;
    margin-bottom: 20px;
    text-align: center;
}

.header h1 {
    margin: 0;
    font-size: 2em;
}

.status-box {
    background-color: #e3f2fd;
    border-left: 4px solid #2196F3;
    padding: 12px;
    border-radius: 4px;
    margin-bottom: 16px;
}

.chat-container {
    background-color: #fafafa;
    border-radius: 8px;
    padding: 12px;
}

.character-row {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
    flex-wrap: wrap;
}

.character-button {
    flex: 1;
    min-width: 100px;
}

.record-button {
    background-color: #4CAF50 !important;
    color: white !important;
    font-weight: bold !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 16px !important;
    font-size: 18px !important;
    cursor: pointer !important;
    transition: all 0.3s ease !important;
    width: 100% !important;
}

.record-button:hover {
    background-color: #45a049 !important;
    transform: scale(1.02) !important;
}

.record-button:active {
    transform: scale(0.98) !important;
}

.start-button {
    background-color: #2196F3 !important;
    color: white !important;
    font-weight: bold !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 16px !important;
    font-size: 16px !important;
    width: 100% !important;
}

.start-button:hover {
    background-color: #0b7dda !important;
}
"""

# Gradio Interface
demo = gr.Blocks(
    title="Dil Evi - Web",
    css=css,
)

with demo:
    with gr.Group(elem_classes="header"):
        gr.Markdown("""
        # 🎓 Dil Evi - Real-time Voice Chat
        
        **Sesli konuşma ile doğal İngilizce pratik yap!**
        
        - 🎤 Real-time voice recognition
        - 🤖 AI konuşma ortağı
        - 📱 Mobile-friendly (responsive)
        - 🌍 Shareable link
        """)
    
    with gr.Group():
        gr.Markdown("### 👥 Öğretmeni Seç")
        with gr.Row(elem_classes="character-row"):
            character_radio = gr.Radio(
                choices=[c["name"] for c in CHARACTERS],
                value="Amelia",
                label="",
                scale=1
            )
    
    with gr.Group(elem_classes="status-box"):
        status_output = gr.Textbox(
            label="📡 Durum",
            value="✅ Hazır! Başlayabilirsin.",
            interactive=False,
            lines=1
        )
    
    with gr.Group():
        start_btn = gr.Button(
            "🎙️ Başla (5 dakika)",
            size="lg",
            elem_classes="start-button"
        )
    
    with gr.Group(elem_classes="chat-container"):
        gr.Markdown("### 💬 Sohbet")
        chat_output = gr.Textbox(
            label="",
            interactive=False,
            lines=15,
            max_lines=30,
            value="Konuşma başladığında burada görünecek...",
            elem_classes="chat-box"
        )
    
    with gr.Group():
        refresh_btn = gr.Button("🔄 Güncelle")
    
    # Events
    start_btn.click(
        start_conversation,
        inputs=[character_radio],
        outputs=[status_output]
    ).then(
        refresh_chat,
        outputs=[chat_output]
    )
    
    refresh_btn.click(
        refresh_chat,
        outputs=[chat_output]
    )

if __name__ == "__main__":
    demo.launch(
        share=True,
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
        # Mobile optimization
        inbrowser=True,
    )