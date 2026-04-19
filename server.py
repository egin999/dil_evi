"""
server.py — FastAPI WebSocket Server
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware


import asyncio
import json
import base64
import os

# Render gibi sunucularda ses kartı hatası almamak için güvenli import
try:
    import sounddevice as sd
    print("Ses kartı başarıyla yüklendi.")
except (OSError, ImportError) as e:
    sd = None
    print(f"Ses kartı bulunamadı (Sunucu modu): {e}")

app = FastAPI(title="Dil Evi")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CHARACTERS = {
    'Amelia': {'voice': 'sage'},
    'Sarah': {'voice': 'shimmer'},
    'James': {'voice': 'echo'},
}

# Serve index.html
@app.get("/")
async def get():
    return FileResponse('index.html', media_type='text/html')

@app.get("/health")
async def health():
    """Health check for Render"""
    return {"status": "ok"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    speaker = SpeakerStream()
    speaker.start()
    
    client = None
    character = None
    
    async def send_ws_message(msg):
        """Helper function to send WebSocket messages safely"""
        try:
            await websocket.send_text(json.dumps(msg))
        except Exception as e:
            print(f"Error sending WebSocket message: {e}")
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message['type'] == 'init':
                character = message.get('character', 'Amelia')
                
                if character not in CHARACTERS:
                    character = 'Amelia'
                
                try:
                    # Create Realtime Client
                    client = RealtimeClient(
                        instructions=f"Sen {character}sin, Türk öğrenciye İngilizce öğret. Her cevapta bir İngilizce cümle olsun.",
                        voice=CHARACTERS[character]['voice'],
                        on_audio_delta=lambda pcm: speaker.write(pcm),
                        on_user_started=lambda: None,
                        on_user_stopped=lambda: None,
                        on_user_transcript=lambda text: asyncio.create_task(
                            send_ws_message({'type': 'transcription', 'text': text})
                        ),
                        on_assistant_transcript=lambda text: asyncio.create_task(
                            send_ws_message({'type': 'response', 'text': text})
                        ),
                        on_response_started=lambda: None,
                        on_response_done=lambda: None,
                        on_error=lambda msg: asyncio.create_task(
                            send_ws_message({'type': 'error', 'message': msg})
                        ),
                    )
                    
                    # Connect to OpenAI Realtime API
                    await client.connect()
                    
                    # Send initial greeting
                    await client.request_response(
                        instructions="Arkadaşını samimi selamla. Kısa cümle."
                    )
                    
                    # Send success
                    await send_ws_message({
                        'type': 'init_success',
                        'character': character
                    })
                    
                except Exception as e:
                    print(f"Client initialization error: {e}")
                    await send_ws_message({
                        'type': 'error',
                        'message': f'Connection failed: {str(e)}'
                    })
            
            elif message['type'] == 'audio':
                if client:
                    try:
                        audio_data = base64.b64decode(message['audio'])
                        await client.send_audio(audio_data)
                    except Exception as e:
                        print(f"Audio processing error: {e}")
                        await send_ws_message({
                            'type': 'error',
                            'message': f'Audio error: {str(e)}'
                        })
    
    except WebSocketDisconnect:
        print(f"Client disconnected: {character}")
    except Exception as e:
        print(f"WebSocket error: {e}")
    
    finally:
        if client:
            try:
                await client.close()
            except:
                pass
        speaker.stop()
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv('PORT', 8000))
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        ws_ping_interval=20,
        ws_ping_timeout=20,
        log_level="info"
    )