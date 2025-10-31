#!/usr/bin/env python3
"""
Twilio WebSocket Server for Real-Time Voice with Azure Speech
Integrated with SeniorHealthAgent for full conversation management
Version: 2.6 - Balanced noise filtering + timeout handling

NOISE FILTERING:
- Layer 1: RMS energy threshold 0.03 (balanced for phone audio levels)
- Layer 2: Zero-crossing rate (detects speech patterns vs TV/music)
- Layer 3: Dynamic range detection (speech has peaks/valleys, noise is uniform)
- Layer 4: Spectral centroid (checks frequency content for human speech range)
- Sustained speech requirement: 1 chunk (2 seconds) before processing

TIMEOUT HANDLING:
- After 20 seconds of silence: Prompts "I'm sorry, I didn't catch that. Could you please speak a bit louder?"
- After 3 failed prompts: Ends call with "I'm having trouble hearing you. Let's try again another time. Goodbye!"
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
import numpy as np
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

def has_significant_audio(pcm_data: bytes, threshold: float = 0.015) -> bool:
    """
    Multi-layer audio detection to filter background noise and ensure close proximity speech.

    Layers:
    1. Volume threshold (RMS energy)
    2. Zero-crossing rate (distinguishes speech from continuous noise like TV)
    3. Peak detection (ensures dynamic range typical of human speech)

    Args:
        pcm_data: Raw PCM audio bytes (16-bit)
        threshold: RMS threshold (0.0-1.0), default 0.05 requires louder audio (closer to mic)

    Returns:
        True if audio appears to be close-proximity human speech, False otherwise
    """
    try:
        # Convert bytes to numpy array of 16-bit integers
        audio_array = np.frombuffer(pcm_data, dtype=np.int16)

        if len(audio_array) == 0:
            return False

        # Normalize to -1.0 to 1.0 range
        normalized = audio_array.astype(np.float32) / 32768.0

        # LAYER 1: RMS Energy (Volume Check)
        # Higher threshold = requires louder audio = must be closer to mic
        rms = np.sqrt(np.mean(normalized ** 2))

        if rms < threshold:
            logger.info(f"❌ Audio too quiet (RMS: {rms:.4f} < {threshold})")
            return False

        # LAYER 2: Zero-Crossing Rate (Speech Pattern Detection)
        # Speech has moderate ZCR (50-200 crossings/sec at 8kHz = 0.006-0.025)
        # TV/music often has higher ZCR, constant noise has very low ZCR
        zero_crossings = np.sum(np.abs(np.diff(np.sign(normalized)))) / 2
        zcr = zero_crossings / len(normalized)

        if zcr < 0.003 or zcr > 0.04:
            logger.info(f"❌ Unusual speech pattern (ZCR: {zcr:.5f}, expected 0.003-0.04)")
            return False

        # LAYER 3: Peak Detection (Dynamic Range)
        # Human speech has clear peaks and valleys
        # Background noise is more uniform
        peak = np.max(np.abs(normalized))
        dynamic_range = peak / (rms + 1e-6)  # Avoid division by zero

        # Speech typically has dynamic range > 2.5
        # Constant noise has lower dynamic range
        if dynamic_range < 2.0:
            logger.info(f"❌ Too uniform, likely background noise (dynamic range: {dynamic_range:.2f})")
            return False

        # LAYER 4: Spectral Centroid (Frequency Check)
        # Human speech is mostly 300-3400 Hz
        # Background noise often has different frequency profile
        # Calculate simple spectral centroid approximation
        fft = np.fft.rfft(normalized)
        magnitude = np.abs(fft)
        freqs = np.fft.rfftfreq(len(normalized), 1/8000)

        if np.sum(magnitude) > 0:
            spectral_centroid = np.sum(freqs * magnitude) / np.sum(magnitude)

            # Speech should be in 300-3400 Hz range
            if spectral_centroid < 200 or spectral_centroid > 3800:
                logger.info(f"❌ Unusual frequency content (centroid: {spectral_centroid:.0f} Hz, expected 200-3800 Hz)")
                return False

        logger.info(f"✅ Valid speech detected (RMS: {rms:.4f}, ZCR: {zcr:.5f}, Dynamic: {dynamic_range:.2f})")
        return True

    except Exception as e:
        logger.error(f"Error checking audio level: {e}")
        return True  # Default to processing if check fails

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

        # Warm up external services to reduce first-call latency
        # - Perform a tiny TTS synthesis
        # - Perform a tiny OpenAI chat
        try:
            async def warm_tts():
                await asyncio.to_thread(agent.speech.synthesize_to_audio_data, "Hello")

            async def warm_openai():
                await asyncio.to_thread(agent.openai.chat, "hi", 0.0, 1)

            logger.info("Warming up Speech and OpenAI services...")
            await asyncio.wait(
                [
                    asyncio.create_task(asyncio.wait_for(warm_tts(), timeout=5)),
                    asyncio.create_task(asyncio.wait_for(warm_openai(), timeout=5)),
                ],
                return_when=asyncio.ALL_COMPLETED,
            )
            logger.info("Warmup complete")
        except Exception as warm_err:
            logger.warning(f"Warmup skipped or partial: {warm_err}")
    except Exception as e:
        logger.error(f"Failed to initialize SeniorHealthAgent: {e}")
        raise

@app.get("/health")
async def health_check():
    """Health check endpoint - verifies all services are initialized and ready"""
    if agent is None:
        logger.warning("Health check failed: Agent not initialized")
        return Response(
            content=json.dumps({"status": "unhealthy", "reason": "Agent not initialized"}),
            status_code=503,
            media_type="application/json"
        )

    # Check if agent's services are ready
    try:
        if not hasattr(agent, 'speech') or agent.speech is None:
            return Response(
                content=json.dumps({"status": "unhealthy", "reason": "Speech service not ready"}),
                status_code=503,
                media_type="application/json"
            )
        if not hasattr(agent, 'openai') or agent.openai is None:
            return Response(
                content=json.dumps({"status": "unhealthy", "reason": "OpenAI service not ready"}),
                status_code=503,
                media_type="application/json"
            )
        if not hasattr(agent, 'data') or agent.data is None:
            return Response(
                content=json.dumps({"status": "unhealthy", "reason": "Data service not ready"}),
                status_code=503,
                media_type="application/json"
            )
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return Response(
            content=json.dumps({"status": "unhealthy", "reason": str(e)}),
            status_code=503,
            media_type="application/json"
        )

    logger.info("Health check passed: All services ready")
    return {
        "status": "healthy",
        "services": {
            "agent": "ready",
            "speech": "ready",
            "openai": "ready",
            "data": "ready"
        }
    }

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
    logger.info("Generating TwiML to start media stream")

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
    silence_counter = 0  # Track consecutive silence chunks
    speech_counter = 0  # Track consecutive speech chunks
    SPEECH_CHUNKS_REQUIRED = 1  # Require 1 chunk of valid speech (reduced from 2)
    no_response_attempts = 0  # Track how many times we've asked user to respond
    MAX_NO_RESPONSE_ATTEMPTS = 3  # End call after 3 failed prompts

    # Get phone number from query params (will be passed by run_app.sh)
    # For now, use a default for testing
    phone_number = "289-324-2125"  # TODO: Get from URL params

    try:
        # Main loop - receive audio from caller
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)

            if data.get('event') == 'start':
                stream_sid = data['start']['streamSid']
                logger.info(f"Stream started: {stream_sid}")
                logger.info("Initializing session after stream start")

                # Initialize session when stream starts (same as original working version)
                from src.services.profile_service import SeniorProfileService
                from src.senior_health_prompt import SENIOR_HEALTH_SYSTEM_PROMPT

                # Look up senior profile
                senior_name = None
                senior_id = None
                context_loaded = False

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

                # Send personalized greeting immediately
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

                    # Convert mulaw to PCM to check audio levels first
                    pcm_data = audioop.ulaw2lin(bytes(audio_buffer), 2)

                    # Check if audio has significant volume (filters background TV noise)
                    # Threshold 0.015 = tuned for actual Twilio phone audio levels
                    if not has_significant_audio(pcm_data, threshold=0.015):
                        logger.info("🔇 Background noise detected, ignoring")
                        audio_buffer.clear()
                        speech_counter = 0  # Reset speech counter
                        silence_counter += 1

                        # After 20 seconds of silence (10 chunks x 2 seconds), prompt user
                        if silence_counter >= 10:
                            no_response_attempts += 1
                            logger.info(f"⏱️ No response detected (attempt {no_response_attempts}/{MAX_NO_RESPONSE_ATTEMPTS})")

                            if no_response_attempts >= MAX_NO_RESPONSE_ATTEMPTS:
                                # End call after 3 attempts
                                goodbye_msg = "I'm having trouble hearing you. Let's try again another time. Goodbye!"
                                logger.info("Ending call due to no response")
                                await send_audio_to_twilio(websocket, stream_sid, goodbye_msg)
                                await asyncio.sleep(3)
                                break
                            else:
                                # Prompt user to speak up
                                prompt_msg = "I'm sorry, I didn't catch that. Could you please speak a bit louder?"
                                logger.info("Prompting user to speak louder")
                                agent_is_speaking = True
                                await send_audio_to_twilio(websocket, stream_sid, prompt_msg)
                                agent_is_speaking = False
                                silence_counter = 0  # Reset after prompting

                        continue

                    # Valid speech detected - increment counter
                    speech_counter += 1
                    silence_counter = 0
                    no_response_attempts = 0  # Reset timeout counter when speech is detected

                    # Require sustained speech before processing (prevents brief background noises)
                    if speech_counter < SPEECH_CHUNKS_REQUIRED:
                        logger.info(f"🎤 Speech detected ({speech_counter}/{SPEECH_CHUNKS_REQUIRED} chunks), continuing...")
                        # Don't clear buffer yet - accumulate more speech
                        continue

                    logger.info(f"✅ Sustained speech confirmed, processing...")

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
                            agent_is_speaking = True
                            await send_audio_to_twilio(websocket, stream_sid, ai_response)
                            agent_is_speaking = False

                    # Clear buffer and reset counters
                    audio_buffer.clear()
                    speech_counter = 0

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
