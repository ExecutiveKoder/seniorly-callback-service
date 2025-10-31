#!/usr/bin/env python3
"""
Twilio WebSocket Server for Real-Time Voice with Azure Speech
Integrated with SeniorHealthAgent for full conversation management
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
import json
import base64
import logging
import wave
import io
import audioop
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import Response
import uvicorn

from src.config import config
from src.main import SeniorHealthAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Twilio WebSocket Server")

# Initialize SeniorHealthAgent (same as local version)
agent = None

def convert_mulaw_to_pcm_wav(mulaw_data: bytes, output_file: str):
    """Convert Twilio's mulaw 8kHz audio to PCM WAV for Azure Speech"""
    try:
        # Convert mulaw to 16-bit PCM
        pcm_data = audioop.ulaw2lin(mulaw_data, 2)  # 2 = 16-bit samples

        # Write as proper WAV file
        with wave.open(output_file, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit PCM
            wav_file.setframerate(8000)  # 8kHz (Twilio's rate)
            wav_file.writeframes(pcm_data)

        logger.info(f"Converted {len(mulaw_data)} bytes mulaw to {len(pcm_data)} bytes PCM")
    except Exception as e:
        logger.error(f"Error converting mulaw to PCM: {e}")

def convert_wav_to_mulaw_base64(wav_data: bytes) -> str:
    """Convert Azure Speech WAV output to Twilio's mulaw format"""
    # Parse WAV file to get PCM data
    with io.BytesIO(wav_data) as wav_io:
        with wave.open(wav_io, 'rb') as wav_file:
            # Get WAV parameters
            channels = wav_file.getnchannels()
            sampwidth = wav_file.getsampwidth()
            framerate = wav_file.getframerate()
            pcm_data = wav_file.readframes(wav_file.getnframes())

            # Convert to mono if stereo
            if channels == 2:
                pcm_data = audioop.tomono(pcm_data, sampwidth, 0.5, 0.5)

            # Resample to 8kHz if needed (Twilio requires 8kHz)
            if framerate != 8000:
                pcm_data, _ = audioop.ratecv(pcm_data, sampwidth, 1, framerate, 8000, None)

            # Convert to 16-bit if not already
            if sampwidth != 2:
                pcm_data = audioop.lin2lin(pcm_data, sampwidth, 2)

            # Convert PCM to mulaw
            mulaw_data = audioop.lin2ulaw(pcm_data, 2)

            # Encode to base64
            base64_audio = base64.b64encode(mulaw_data).decode('ascii')

            return base64_audio

async def send_audio_to_twilio(websocket: WebSocket, stream_sid: str, audio_text: str):
    """Generate speech using Azure TTS and send to Twilio via WebSocket"""
    try:
        # Generate speech using agent's speech service (Sara voice at 1.1x speed)
        logger.info(f"Generating Azure TTS for text (length: {len(audio_text)})")
        wav_data = agent.speech.synthesize_to_audio_data(audio_text)

        if not wav_data:
            logger.error("Failed to generate Azure TTS audio")
            return

        # Convert to mulaw base64
        mulaw_base64 = convert_wav_to_mulaw_base64(wav_data)
        mulaw_bytes = base64.b64decode(mulaw_base64)

        logger.info(f"Sending {len(mulaw_bytes)} bytes of audio to Twilio")

        # Send audio in chunks
        chunk_size = 640  # bytes of mulaw data (80ms chunks)

        for i in range(0, len(mulaw_bytes), chunk_size):
            chunk = mulaw_bytes[i:i + chunk_size]
            chunk_base64 = base64.b64encode(chunk).decode('ascii')

            await websocket.send_json({
                "event": "media",
                "streamSid": stream_sid,
                "media": {
                    "payload": chunk_base64
                }
            })

            await asyncio.sleep(0.005)

        logger.info("Finished sending audio to Twilio")

    except Exception as e:
        logger.error(f"Error sending audio to Twilio: {e}")

@app.on_event("startup")
async def startup():
    """Initialize SeniorHealthAgent"""
    global agent

    logger.info("Initializing SeniorHealthAgent...")

    try:
        agent = SeniorHealthAgent()
        logger.info(f"✅ SeniorHealthAgent ready - AI: {config.get_ai_name()}, Voice: {config.SPEECH_VOICE_NAME}")
    except Exception as e:
        logger.error(f"Failed to initialize SeniorHealthAgent: {e}")
        raise

@app.post("/voice/status")
async def voice_status(request: Request):
    """Handle Twilio status callbacks"""
    form_data = await request.form()
    logger.info(f"Status callback received: {form_data.get('CallStatus')}")
    return Response(content="", status_code=204)

@app.post("/voice")
async def voice_webhook(request: Request):
    """Twilio voice webhook - called when the call is answered"""
    form_data = await request.form()
    digits = form_data.get('Digits', None)

    logger.info("Incoming webhook received (content suppressed)")

    # Create TwiML response
    from twilio.twiml.voice_response import VoiceResponse, Connect

    response = VoiceResponse()

    if digits or digits is None:
        logger.info("Starting media stream (trial key pressed or paid account)")

        # Start the media stream to our WebSocket endpoint
        host = request.headers.get("host")
        connect = Connect()
        connect.stream(url=f'wss://{host}/media-stream')
        response.append(connect)
    else:
        logger.warning("Unexpected state - no digits and not None")
        response.say("Sorry, something went wrong. Goodbye.", voice='Polly.Joanna')

    logger.info(f"TwiML response: {str(response)}")
    return Response(content=str(response), media_type="application/xml")

@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    """WebSocket endpoint for Twilio Media Streams - uses SeniorHealthAgent"""
    await websocket.accept()
    logger.info("WebSocket connection established")

    audio_buffer = bytearray()
    greeting_sent = False
    stream_sid = None
    agent_is_speaking = False  # Flag to ignore incoming audio while agent speaks
    initialized = False  # Track if we've done initialization

    # Get phone number from query params (will be passed by run_app.sh)
    # For now, use a default for testing
    phone_number = "289-324-2125"  # TODO: Get from URL params

    # Variables for initialization
    senior_name = None
    senior_id = None
    context_loaded = False
    greeting = None

    try:
        # Main loop - receive audio from caller
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)

            if data.get('event') == 'start':
                stream_sid = data['start']['streamSid']
                logger.info(f"Stream started: {stream_sid}")

                # Do initialization on first start event
                if not initialized:
                    # Look up senior profile and load context (EXACT same flow as local)
                    from src.services.profile_service import SeniorProfileService
                    from src.senior_health_prompt import SENIOR_HEALTH_SYSTEM_PROMPT

                    try:
                        profile_service = SeniorProfileService(
                            endpoint=config.AZURE_COSMOS_ENDPOINT,
                            key=config.AZURE_COSMOS_KEY,
                            database_name=config.COSMOS_DATABASE
                        )
                        logger.info(f"Looking up profile for phone: {phone_number}")
                        profile = profile_service.get_senior_by_phone(phone_number)
                        if profile:
                            senior_id = profile['seniorId']
                            full_name = profile['fullName']
                            senior_name = full_name.split()[0] if full_name else None
                            logger.info(f"Found profile (ID: {senior_id[:8]}...)")
                        else:
                            logger.warning(f"No profile found for {phone_number}")
                    except Exception as e:
                        logger.error(f"Could not get senior profile: {e}")

                    # Load senior context (call history)
                    context_loaded = agent._load_senior_context(phone_number)

                    # Start session with name and ID
                    agent.start_new_session(senior_name=senior_name, senior_id=senior_id)
                    logger.info(f"Started session {agent.current_session_id}")

                    # Update system prompt with senior's name
                    ai_name = config.get_ai_name()
                    if senior_name:
                        personalized_prompt = SENIOR_HEALTH_SYSTEM_PROMPT.replace("[Name]", senior_name).replace("[Your AI Name]", ai_name)
                        personalized_prompt += f"\n\nREMINDER: The senior's name is {senior_name}. Always use their actual name, never use placeholders like [Name]."
                        agent.openai.set_system_prompt(personalized_prompt)
                    else:
                        generic_prompt = SENIOR_HEALTH_SYSTEM_PROMPT.replace("[Name]", "them").replace("[Your AI Name]", ai_name)
                        agent.openai.set_system_prompt(generic_prompt)

                    # Generate personalized greeting (EXACT same logic as local)
                    if context_loaded and senior_name:
                        greeting = f"Hello {senior_name}! This is {ai_name} calling from Seniorly. It's good to talk with you again today. How are you doing?"
                    elif senior_name:
                        greeting = f"Hello {senior_name}! This is {ai_name} calling from Seniorly. How are you doing today?"
                    else:
                        greeting = f"Hello! This is {ai_name} calling from Seniorly. How are you doing today?"

                    agent.save_message("assistant", greeting)
                    initialized = True

                # Send personalized greeting
                if not greeting_sent and greeting:
                    agent_is_speaking = True
                    await send_audio_to_twilio(websocket, stream_sid, greeting)
                    greeting_sent = True
                    # Wait a bit for greeting to finish playing, then allow user input
                    await asyncio.sleep(2)
                    agent_is_speaking = False
                    audio_buffer.clear()  # Clear any audio received during greeting

            elif data.get('event') == 'media':
                # Ignore incoming audio while agent is speaking
                if agent_is_speaking:
                    continue

                # Received audio from the caller
                payload = data['media']['payload']
                audio_chunk = base64.b64decode(payload)
                audio_buffer.extend(audio_chunk)

                # Process when we have enough audio (~2 seconds)
                if len(audio_buffer) >= 16000:
                    logger.info(f"Processing audio chunk ({len(audio_buffer)} bytes)")

                    # Convert Twilio mulaw to PCM WAV for Azure
                    temp_audio = "/tmp/caller_audio.wav"
                    convert_mulaw_to_pcm_wav(bytes(audio_buffer), temp_audio)

                    # Transcribe using agent's speech service
                    transcribed_text = agent.speech.recognize_from_file(temp_audio)

                    if transcribed_text:
                        logger.info("Caller speech transcribed (content suppressed)")

                        # Save user message
                        agent.save_message("user", transcribed_text)

                        # Get AI response (same as local - uses OpenAI with full context)
                        ai_response = agent.openai.chat(
                            user_message=transcribed_text,
                            temperature=0.7,
                            max_tokens=150
                        )

                        if ai_response:
                            logger.info("AI response generated (content suppressed)")

                            # Save assistant message
                            agent.save_message("assistant", ai_response)

                            # Send AI response using Azure TTS
                            await send_audio_to_twilio(websocket, stream_sid, ai_response)

                    # Clear buffer
                    audio_buffer.clear()

            elif data.get('event') == 'stop':
                logger.info("Stream stopped")
                break

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Session is automatically saved to Cosmos DB via save_message calls
        # No need to explicitly end the session
        logger.info("WebSocket connection closed")

if __name__ == "__main__":
    logger.info("="*60)
    logger.info("🎙️  TWILIO WEBSOCKET SERVER WITH SENIORHEALTHAGENT")
    logger.info(f"   AI Agent: {config.get_ai_name()}")
    logger.info(f"   Voice: {config.SPEECH_VOICE_NAME}")
    logger.info("="*60)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5000,
        log_level="info"
    )
