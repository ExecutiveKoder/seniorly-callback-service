#!/usr/bin/env python3
"""
Twilio WebSocket Server for Real-Time Voice with Azure Speech
Handles bidirectional audio streaming with sub-second latency
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
import websockets
import json
import base64
import logging
import audioop
import wave
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import Response
import uvicorn

from src.config import config
from src.services.speech_service import SpeechService
from src.services.openai_service import OpenAIService
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Twilio WebSocket Server")

# Initialize services
speech_service = None
openai_service = None

def convert_mulaw_to_pcm_wav(mulaw_data: bytes, output_file: str):
    """Convert Twilio's mulaw 8kHz audio to PCM 16kHz WAV for Azure Speech"""
    # Twilio sends mulaw 8kHz, Azure needs PCM 16kHz
    # Step 1: Convert mulaw to PCM
    pcm_8khz = audioop.ulaw2lin(mulaw_data, 2)  # 2 bytes per sample (16-bit)

    # Step 2: Resample from 8kHz to 16kHz
    pcm_16khz, _ = audioop.ratecv(pcm_8khz, 2, 1, 8000, 16000, None)

    # Step 3: Write as proper WAV file with headers
    with wave.open(output_file, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(16000)  # 16kHz
        wav_file.writeframes(pcm_16khz)

@app.on_event("startup")
async def startup():
    """Initialize Azure services"""
    global speech_service, openai_service

    logger.info("Initializing services...")

    speech_service = SpeechService(
        speech_key=config.AZURE_SPEECH_KEY,
        speech_region=config.AZURE_SPEECH_REGION,
        voice_name=config.SPEECH_VOICE_NAME
    )

    openai_service = OpenAIService(
        api_key=config.AZURE_OPENAI_KEY,
        endpoint=config.AZURE_OPENAI_ENDPOINT,
        deployment_name=config.AZURE_OPENAI_DEPLOYMENT_NAME,
        api_version=config.AZURE_OPENAI_API_VERSION
    )

    logger.info(f"✅ Services ready - AI: {config.get_ai_name()}, Voice: {config.SPEECH_VOICE_NAME}")

@app.post("/voice")
async def voice_webhook(request: Request):
    """
    Twilio voice webhook - called when the call is answered
    Returns TwiML to start media streaming
    """
    logger.info("Incoming call - starting media stream")

    # Create TwiML response to start media streaming
    response = VoiceResponse()

    # Start the media stream to our WebSocket endpoint
    connect = Connect()
    connect.stream(url=f'wss://{request.headers.get("host")}/media-stream')
    response.append(connect)

    logger.info(f"TwiML response: {str(response)}")

    return Response(content=str(response), media_type="application/xml")

@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Streams
    Handles real-time bidirectional audio
    """
    await websocket.accept()
    logger.info("WebSocket connection established")

    ai_name = config.get_ai_name()
    conversation_buffer = []
    audio_buffer = bytearray()

    try:
        # Send initial greeting
        greeting = f"Hello! This is {ai_name} from Seniorly. How are you doing today?"
        logger.info(f"Sending greeting: {greeting}")

        # Generate audio with Azure Speech Services (Jason's voice)
        greeting_audio_file = "/tmp/greeting.wav"
        speech_service.synthesize_to_file(greeting, greeting_audio_file)

        # Read audio and send to Twilio
        with open(greeting_audio_file, 'rb') as f:
            audio_data = f.read()
            # Convert to base64 and send via WebSocket
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            await websocket.send_json({
                "event": "media",
                "media": {
                    "payload": audio_b64
                }
            })

        # Main loop - receive audio from caller
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)

            if data.get('event') == 'start':
                logger.info(f"Stream started: {data}")

            elif data.get('event') == 'media':
                # Received audio from the caller
                payload = data['media']['payload']
                audio_chunk = base64.b64decode(payload)
                audio_buffer.extend(audio_chunk)

                # Process when we have enough audio (~1 second)
                if len(audio_buffer) >= 8000:
                    logger.info(f"Processing audio chunk ({len(audio_buffer)} bytes)")

                    # Convert Twilio mulaw to PCM WAV for Azure
                    temp_audio = "/tmp/caller_audio.wav"
                    convert_mulaw_to_pcm_wav(bytes(audio_buffer), temp_audio)

                    # Transcribe using Azure Speech
                    transcribed_text = speech_service.recognize_from_file(temp_audio)

                    if transcribed_text:
                        logger.info(f"Caller said: {transcribed_text}")

                        # Generate AI response
                        ai_response = openai_service.chat(
                            message=transcribed_text,
                            temperature=0.7,
                            max_tokens=150
                        )

                        if ai_response:
                            logger.info(f"{ai_name} responding: {ai_response}")

                            # Synthesize response with Jason's voice
                            response_audio_file = "/tmp/response.wav"
                            speech_service.synthesize_to_file(ai_response, response_audio_file)

                            # Send audio back to caller
                            with open(response_audio_file, 'rb') as f:
                                response_audio = f.read()
                                response_b64 = base64.b64encode(response_audio).decode('utf-8')
                                await websocket.send_json({
                                    "event": "media",
                                    "media": {
                                        "payload": response_b64
                                    }
                                })

                    # Clear buffer
                    audio_buffer.clear()

            elif data.get('event') == 'stop':
                logger.info("Stream stopped")
                break

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        logger.info("WebSocket connection closed")

if __name__ == "__main__":
    logger.info("="*60)
    logger.info("🎙️  TWILIO WEBSOCKET SERVER")
    logger.info(f"   AI Agent: {config.get_ai_name()}")
    logger.info(f"   Voice: {config.SPEECH_VOICE_NAME}")
    logger.info("="*60)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5000,
        log_level="info"
    )
