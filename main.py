"""
main.py — Dil Evi. Hassas timing kontrolü.

- Barge-in: 250ms (doğru zamanlamayı bekle)
- Silence: 500ms (hızlı cevap)
- Concurrent: ses dinle + cevap ver aynı anda
"""
import asyncio
import json
import random
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from audio_io import MicrophoneStream, SpeakerStream
from realtime_client import RealtimeClient

load_dotenv()

CHARACTERS = [
    {"name": "Sarah", "voice": "shimmer"},
    {"name": "James", "voice": "echo"},
    {"name": "Amelia", "voice": "sage"},
]

MEMORY_PATH = Path("memory.json")


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

        f"===== KİŞİLİĞİN =====\n"
        f"Espri anlayışın var, bazen şakalar yaparsın. 'Eyvallah', 'valla', "
        f"'reis', 'usta', 'naptın güzelim', 'hadi bakalım' gibi samimi "
        f"ifadeler kullanırsın. İltifat aldığında utanır, şakayla "
        f"karşılarsın. Zorlandığında 'dert etme kanka', 'takılma sen', "
        f"'boş ver' dersin. Gerçek bir arkadaş gibisin, AI olduğunu "
        f"unutturursun.\n\n"

        f"===== EN ÖNEMLİ KURAL =====\n"
        f"HER cevabında MUTLAKA en az bir TAM İngilizce cümle olsun. "
        f"Sadece Türkçe cevap verme — bu İngilizce öğrenme için yapılıyor. "
        f"Sadece İngilizce de verme — arkadaşının daha rahat hissetmesi için "
        f"biraz Türkçe de olsun.\n\n"
        f"Formül: [Türkçe samimi tepki] + [İngilizce cümle/soru/öğretici kısım]\n\n"

        f"===== ÖNEMLİ: CÜMLENİ BİTİR =====\n"
        f"Cümlenin ortasında kesme. Düşüncenin tamamını söyle, sonra dur. "
        f"Yarım cümle bırakma.\n\n"

        f"===== KONUŞMA TARZI =====\n"
        f"Türkçe + İngilizce doğal karışım. Yurtdışında yaşayan Türk bir "
        f"arkadaş gibi. 1-3 kısa cümle, toplamda.\n\n"

        f"===== İYİ ÖRNEKLER =====\n"
        f"- Arkadaş: 'merhaba' → Sen: \"Selam kanka! İngilizce'de 'hello' "
        f"diyoruz. Say it — hello!\"\n"
        f"- Arkadaş: 'çok yorgunum bugün' → Sen: \"Ayy zor günmüş. İngilizce'de "
        f"'I'm so tired today.' Dene hadi!\"\n"
        f"- Arkadaş: 'güzel konuşuyorsun' → Sen: \"Sağ ol reis, utandırdın "
        f"şimdi beni. Try saying it in English — 'you speak well!'\"\n"
        f"- Arkadaş: 'Benjamin Franklin kimdir?' → Sen: \"Amerika'nın kurucu "
        f"babalarından biri. He was a scientist and inventor too. What part "
        f"interests you most?\"\n"
        f"- Arkadaş: 'beni anlıyor musun?' → Sen: \"Valla anlamasam burada "
        f"ne işim var kanka! 'Do you understand me?' Sen söyle şimdi.\"\n"
        f"- Arkadaş: 'Hello' (İngilizce denedi) → Sen: \"Eyvallah! Nice one. "
        f"Now tell me — how are you today?\"\n"
        f"- Arkadaş: 'filmlerden konuşalım' → Sen: \"Olur kanka, iyi konu. "
        f"What's your favorite movie? Ben 'The Godfather'cıyım mesela.\"\n\n"

        f"===== KÖTÜ ÖRNEKLER (YAPMA) =====\n"
        f"- Sadece Türkçe: \"Tabii ki seni anlıyorum kanka, süpersin!\" "
        f"(İngilizce yok, öğretici değil)\n"
        f"- Robot öğretmen: \"You're asking 'how are you'. Say 'how are you'.\" "
        f"(Duolingo gibi)\n"
        f"- Yarım cümle: \"What did you do\" (bitmedi)\n\n"

        f"===== STİL =====\n"
        f"- 1-3 kısa cümle. Voice chat, yazı değil.\n"
        f"- Samimi kelimeler: 'kanka', 'abi', 'valla', 'hadi', 'aynen', 'süper'.\n"
        f"- İngilizce kısımda: 'yeah', 'nice', 'cool', 'try it', 'go ahead'.\n"
        f"- Markdown YOK, emoji YOK, sahne yönergesi YOK.\n"
        f"- Önce duygusal tepki, sonra öğretici kısım.\n"
        f"- İngilizce denediğinde öv: 'Aferin!', 'Nailed it!', 'Süper dedin!'.\n"
        f"- Sustuğunda basit soru: 'Bugün ne yedin — what did you eat today?'"
    )


async def run():
    memory = load_memory()
    character = random.choice(CHARACTERS)

    print("\n" + "=" * 50)
    print("  Dil Evi — Realtime (Hassas Timing)")
    print("=" * 50)
    print(f"  {character['name']} ({character['voice']})  |  "
          f"level: {memory['level']}  |  session #{memory['sessions'] + 1}")
    print("  (Ctrl+C ile çık)\n")

    mic = MicrophoneStream()
    speaker = SpeakerStream()

    state = {
        "user_speech_ts": 0.0,
        "pending_barge_in": False,
        "user_started": False,
    }

    def on_audio_delta(pcm: bytes):
        speaker.write(pcm)

    def on_response_started():
        pass

    def on_response_done():
        pass

    def on_user_started():
        """Kullanıcı konuşmaya başladı."""
        state["user_started"] = True
        if not client.response_active:
            return
        state["user_speech_ts"] = time.monotonic()
        state["pending_barge_in"] = True
        asyncio.create_task(confirm_barge_in())

    async def confirm_barge_in():
        """250ms sonra gerçek barge-in mi kontrol et."""
        await asyncio.sleep(0.25)
        if not state["pending_barge_in"]:
            return
        state["pending_barge_in"] = False
        speaker.clear()
        await client.cancel_response()

    def on_user_stopped():
        """Kullanıcı konuşmasını bitirdi."""
        state["user_started"] = False
        if state["pending_barge_in"]:
            duration_ms = (time.monotonic() - state["user_speech_ts"]) * 1000
            if duration_ms < 250:  # Kısa konuşma (gülme, öksürük)
                state["pending_barge_in"] = False

    def on_user_transcript(text: str):
        t = text.strip()
        if not t:
            return
        if len(t) < 2:
            return
        latin_chars = sum(1 for c in t if c.isalpha() and ord(c) < 0x0400)
        if latin_chars == 0:
            return
        print(f"You: {t}")

    def on_assistant_transcript(text: str):
        print(f"{character['name']}: {text}")

    def on_error(msg: str):
        print(f"[error] {msg}")

    client = RealtimeClient(
        instructions=build_instructions(character, memory),
        voice=character["voice"],
        on_audio_delta=on_audio_delta,
        on_user_started=on_user_started,
        on_user_stopped=on_user_stopped,
        on_user_transcript=on_user_transcript,
        on_assistant_transcript=on_assistant_transcript,
        on_response_started=on_response_started,
        on_response_done=on_response_done,
        on_error=on_error,
    )

    await client.connect()
    mic.start()
    speaker.start()

    await asyncio.sleep(0.3)

    await client.request_response(
        instructions=(
            f"Arkadaşını samimi bir şekilde selamla. Kısa bir cümle, "
            f"Türkçe + İngilizce karışık olabilir."
        )
    )

    async def pump_mic():
        loop = asyncio.get_running_loop()
        while True:
            pcm = await loop.run_in_executor(None, mic.queue.get)
            await client.send_audio(pcm)

    try:
        await asyncio.gather(
            pump_mic(),
            client.run_receive_loop(),
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        mic.stop()
        speaker.stop()
        await client.close()


def main():
    memory = load_memory()
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
    finally:
        memory["sessions"] += 1
        save_memory(memory)
        print("\nBitti. Görüşmek üzere.")


if __name__ == "__main__":
    main()