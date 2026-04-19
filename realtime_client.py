"""
realtime_client.py — OpenAI Realtime API

Hassas timing:
- VAD: 0.4 (daha hassas)
- Silence: 500ms (hızlı cevap)
- Prefix: 200ms (ek kontrol)
"""
import asyncio
import base64
import json
import os
from typing import Callable, Optional

import websockets

REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17"


class RealtimeClient:
    def __init__(
        self,
        *,
        instructions: str,
        voice: str,
        on_audio_delta: Callable[[bytes], None],
        on_user_started: Callable[[], None],
        on_user_stopped: Callable[[], None],
        on_user_transcript: Callable[[str], None],
        on_assistant_transcript: Callable[[str], None],
        on_response_started: Callable[[], None],
        on_response_done: Callable[[], None],
        on_error: Callable[[str], None],
    ):
        self.instructions = instructions
        self.voice = voice
        self.on_audio_delta = on_audio_delta
        self.on_user_started = on_user_started
        self.on_user_stopped = on_user_stopped
        self.on_user_transcript = on_user_transcript
        self.on_assistant_transcript = on_assistant_transcript
        self.on_response_started = on_response_started
        self.on_response_done = on_response_done
        self.on_error = on_error

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._assistant_transcript_buffer = ""
        self._response_active: bool = False

    @property
    def response_active(self) -> bool:
        return self._response_active

    async def connect(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY yok")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "OpenAI-Beta": "realtime=v1",
        }
        self._ws = await websockets.connect(REALTIME_URL, additional_headers=headers)

        await self._send({
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": self.instructions,
                "voice": self.voice,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1",
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.4,  # Daha hassas
                    "prefix_padding_ms": 200,  # Ek kontrol
                    "silence_duration_ms": 500,  # Hızlı cevap
                },
                "temperature": 0.8,
                "max_response_output_tokens": 300,
            },
        })

    async def send_audio(self, pcm_bytes: bytes):
        if self._ws is None:
            return
        b64 = base64.b64encode(pcm_bytes).decode("ascii")
        await self._send({
            "type": "input_audio_buffer.append",
            "audio": b64,
        })

    async def cancel_response(self):
        if not self._response_active:
            return
        await self._send({"type": "response.cancel"})

    async def request_response(self, instructions: Optional[str] = None):
        payload: dict = {
            "type": "response.create",
            "response": {"modalities": ["audio", "text"]},
        }
        if instructions:
            payload["response"]["instructions"] = instructions
        await self._send(payload)

    async def _send(self, obj: dict):
        if self._ws is None:
            return
        await self._ws.send(json.dumps(obj))

    async def run_receive_loop(self):
        assert self._ws is not None
        async for raw in self._ws:
            event = json.loads(raw)
            etype = event.get("type", "")

            if etype == "response.audio.delta":
                audio_bytes = base64.b64decode(event["delta"])
                self.on_audio_delta(audio_bytes)

            elif etype == "response.created":
                self._response_active = True
                self.on_response_started()

            elif etype == "response.done":
                self._response_active = False
                self.on_response_done()

            elif etype == "input_audio_buffer.speech_started":
                self.on_user_started()

            elif etype == "input_audio_buffer.speech_stopped":
                self.on_user_stopped()

            elif etype == "conversation.item.input_audio_transcription.completed":
                self.on_user_transcript(event.get("transcript", ""))

            elif etype == "response.audio_transcript.delta":
                self._assistant_transcript_buffer += event.get("delta", "")

            elif etype == "response.audio_transcript.done":
                self.on_assistant_transcript(self._assistant_transcript_buffer)
                self._assistant_transcript_buffer = ""

            elif etype == "error":
                err = event.get("error", {})
                msg = err.get("message", "")
                low = msg.lower()
                if "no active response" in low or "cancellation failed" in low:
                    continue
                self.on_error(f"{err.get('type')}: {msg}")

    async def close(self):
        if self._ws is not None:
            await self._ws.close()
            self._ws = None