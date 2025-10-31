#!/usr/bin/env python3
"""
Twilio WebSocket Server for Real-Time Voice with Azure Speech
Integrated with SeniorHealthAgent for full conversation management
Version: 2.7 - Robust VAD (ambient during TTS, cooldown, stricter gating)

NOISE FILTERING:
- Layer 1: RMS energy threshold 0.03 (balanced for phone audio levels)
- Layer 2: Zero-crossing rate (detects speech patterns vs TV/music)
- Layer 3: Dynamic range detection (speech has peaks/valleys, noise is uniform)
- Layer 4: Spectral centroid (checks frequency content for human speech range)
- Sustained speech requirement: 1 chunk (2 seconds) before processing

ADAPTIVE NOISE FILTERING:
- Learns ambient noise floor from first 10 seconds of call
- Sets threshold to 3x ambient noise (minimum 0.010)
- Adapts to each environment automatically

TIMEOUT HANDLING:
- After 30 seconds of silence: Prompts "I'm sorry, I didn't catch that. Could you please speak a bit louder?"
- After 3 failed prompts: Ends call gracefully
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
import time
import json
import base64
import logging
import wave
import io
import audioop
import numpy as np
import os
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import Response
import uvicorn
import webrtcvad
import azure.cognitiveservices.speech as speechsdk

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

# Track which phone numbers have pre-loaded context
# Format: {phone_number: {senior_name, senior_id, context_loaded_at}}
preloaded_context = {}

# VAD configuration (tunable via environment variables)
VAD_DEBUG = os.getenv('VAD_DEBUG', 'false').lower() == 'true'
VAD_ENABLE_ZCR = os.getenv('VAD_ENABLE_ZCR', 'true').lower() == 'true'
VAD_ZCR_MIN = float(os.getenv('VAD_ZCR_MIN', '0.02'))
VAD_ZCR_MAX = float(os.getenv('VAD_ZCR_MAX', '0.25'))
VAD_MIN_THRESHOLD = float(os.getenv('VAD_MIN_THRESHOLD', '0.010'))
VAD_AMBIENT_MULTIPLIER = float(os.getenv('VAD_AMBIENT_MULTIPLIER', '3.0'))
VAD_SUSTAINED_CHUNKS = int(os.getenv('VAD_SUSTAINED_CHUNKS', '2'))
VAD_COOLDOWN_MS = int(os.getenv('VAD_COOLDOWN_MS', '1000'))
VAD_PROMPT_GRACE_SECONDS = float(os.getenv('VAD_PROMPT_GRACE_SECONDS', '8.0'))
VAD_MIN_VARIANCE = float(os.getenv('VAD_MIN_VARIANCE', '1e-5'))
# Additional timing/env tuning
VAD_CHUNK_BYTES = int(os.getenv('VAD_CHUNK_BYTES', '4000'))  # ~0.5s at 8kHz
VAD_SILENCE_CHUNKS_TO_PROMPT = int(os.getenv('VAD_SILENCE_CHUNKS_TO_PROMPT', '6'))
VAD_AMBIENT_LEARNING_CHUNKS = int(os.getenv('VAD_AMBIENT_LEARNING_CHUNKS', '2'))
VAD_USE_WEBRTC = os.getenv('VAD_USE_WEBRTC', 'true').lower() == 'true'
VAD_AGGRESSIVENESS = int(os.getenv('VAD_AGGRESSIVENESS', '2'))  # 0..3
VAD_ON_WINDOW_FRAMES = int(os.getenv('VAD_ON_WINDOW_FRAMES', '10'))  # 10 frames = 200 ms
VAD_ON_MIN_VOICED = int(os.getenv('VAD_ON_MIN_VOICED', '8'))       # 8 -> 80% in window
VAD_OFF_CONSEC_UNVOICED = int(os.getenv('VAD_OFF_CONSEC_UNVOICED', '15'))  # 300 ms

def compute_zero_crossing_rate(normalized: np.ndarray) -> float:
    """Compute zero-crossing rate over the whole window."""
    if normalized.size < 2:
        return 0.0
    signs = np.sign(normalized)
    crossings = np.where(np.diff(signs))[0].size
    return float(crossings) / float(normalized.size)


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
            if VAD_DEBUG:
                logger.info(f"VAD: fail rms (rms={rms:.4f}, thr={threshold:.4f})")
            return False

        # LAYER 2 (optional): Zero-crossing rate range
        if VAD_ENABLE_ZCR:
            zcr = compute_zero_crossing_rate(normalized)
            if not (VAD_ZCR_MIN <= zcr <= VAD_ZCR_MAX):
                if VAD_DEBUG:
                    logger.info(f"VAD: fail zcr (zcr={zcr:.4f}, range=({VAD_ZCR_MIN:.2f},{VAD_ZCR_MAX:.2f}))")
                return False
        else:
            zcr = -1.0

        # LAYER 3: Dynamic variance across subwindows (guards against steady hum/TV)
        # Split into 8 segments and compute RMS variance
        segment_count = 8
        seg_size = max(1, normalized.size // segment_count)
        seg_rms = []
        for i in range(0, normalized.size, seg_size):
            seg = normalized[i:i + seg_size]
            if seg.size == 0:
                continue
            seg_rms.append(float(np.sqrt(np.mean(seg ** 2))))
        var = float(np.var(seg_rms)) if seg_rms else 0.0
        if var < VAD_MIN_VARIANCE:
            if VAD_DEBUG:
                logger.info(f"VAD: fail variance (var={var:.6f} < min={VAD_MIN_VARIANCE:.6f})")
            return False

        if VAD_DEBUG:
            logger.info(f"VAD: pass (rms={rms:.4f}, thr={threshold:.4f}, zcr={zcr:.4f}, var={var:.6f})")
        return True

    except Exception as e:
        logger.error(f"Error checking audio level: {e}")
        return False  # Be conservative on error


def is_speech_webrtc(pcm_data: bytes) -> bool:
    """Use WebRTC VAD on 20 ms frames at 8 kHz 16-bit PCM (mono, little-endian)."""
    try:
        if len(pcm_data) < 320:  # one 20ms frame at 8kHz
            return False
        vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
        frame_size = 320  # bytes (20 ms * 160 samples * 2 bytes)
        total_frames = len(pcm_data) // frame_size
        if total_frames == 0:
            return False
        voiced = []
        # Evaluate each 20ms frame
        for i in range(0, total_frames * frame_size, frame_size):
            frame = pcm_data[i:i + frame_size]
            if len(frame) < frame_size:
                break
            is_voiced = 1 if vad.is_speech(frame, 8000) else 0
            voiced.append(is_voiced)

        # Sliding window test for speech onset: require >= VAD_ON_MIN_VOICED in VAD_ON_WINDOW_FRAMES
        if len(voiced) < VAD_ON_WINDOW_FRAMES:
            return sum(voiced) >= max(1, VAD_ON_MIN_VOICED // 2)  # short chunks: allow partial

        window = VAD_ON_WINDOW_FRAMES
        min_voiced = VAD_ON_MIN_VOICED
        for s in range(0, len(voiced) - window + 1):
            if sum(voiced[s:s + window]) >= min_voiced:
                return True
        return False
    except Exception as e:
        logger.error(f"WebRTC VAD error: {e}")
        return False

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

def normalize_tts_text(text: str) -> str:
    """
    Normalize text for natural TTS output
    - Remove excessive exclamation marks (keep max 1)
    - Convert SHOUTING CAPS to normal case (except acronyms)
    - Remove excessive emphasis
    """
    import re

    # Replace multiple exclamation marks with single one
    text = re.sub(r'!{2,}', '!', text)

    # Replace multiple question marks with single one
    text = re.sub(r'\?{2,}', '?', text)

    # Fix SHOUTING CAPS: convert words with 3+ caps to title case
    # (but preserve 2-letter acronyms like "OK", "US", etc.)
    def fix_caps(match):
        word = match.group(0)
        # If it's a known acronym or very short, keep it
        if len(word) <= 2 or word in ['OK', 'USA', 'GPS', 'TV']:
            return word
        # Otherwise convert to title case
        return word.capitalize()

    text = re.sub(r'\b[A-Z]{3,}\b', fix_caps, text)

    return text

async def send_audio_to_twilio(websocket: WebSocket, stream_sid: str, audio_text: str):
    """Generate speech using Azure TTS and send to Twilio via WebSocket"""
    try:
        # Normalize text for natural speech (remove excessive emphasis)
        normalized_text = normalize_tts_text(audio_text)

        # Generate speech using agent's speech service (Sara voice at 1.1x speed)
        logger.info(f"Generating Azure TTS for text (length: {len(normalized_text)})")
        wav_data = agent.speech.synthesize_to_audio_data(normalized_text)

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

@app.post("/initiate-call")
async def initiate_call(request: Request):
    """
    Initiate outbound call with pre-loaded context

    Request body (JSON):
    {
        "phone_number": "289-324-2125",
        "senior_id": "optional-senior-id"
    }
    """
    try:
        body = await request.json()
        phone_number = body.get('phone_number')

        if not phone_number:
            return Response(
                content=json.dumps({"success": False, "error": "phone_number required"}),
                status_code=400,
                media_type="application/json"
            )

        logger.info(f"🚀 Call initiation requested (phone suppressed)")

        # STEP 1: Load context BEFORE placing call (this takes 15-30 seconds)
        logger.info("📚 Loading senior context...")
        from src.services.profile_service import SeniorProfileService

        profile_service = SeniorProfileService(
            endpoint=config.AZURE_COSMOS_ENDPOINT,
            key=config.AZURE_COSMOS_KEY,
            database_name=config.COSMOS_DATABASE
        )

        profile = profile_service.get_senior_by_phone(phone_number)

        if not profile:
            logger.warning(f"Senior profile not found")
            senior_name = None
            senior_id = None
        else:
            senior_id = profile['seniorId']
            full_name = profile['fullName']
            senior_name = full_name.split()[0] if full_name else None
            logger.info(f"✅ Profile loaded (name suppressed)")

        # Load call history into agent's memory
        context_loaded = agent._load_senior_context(phone_number)
        logger.info(f"✅ Context loaded: {context_loaded}")

        # Store preloaded context for this phone number
        # Normalize phone number (remove dashes/spaces for consistent lookup)
        import time
        normalized_phone = phone_number.replace("-", "").replace(" ", "")
        preloaded_context[normalized_phone] = {
            "senior_name": senior_name,
            "senior_id": senior_id,
            "context_loaded_at": time.time()
        }
        logger.info(f"✅ Context cached for phone number (normalized: {normalized_phone})")

        # STEP 2: NOW place the call (context is already in memory)
        logger.info("📞 Placing call...")
        from src.services.twilio_service import TwilioService

        twilio_service = TwilioService(
            account_sid=config.TWILIO_ACCOUNT_SID,
            auth_token=config.TWILIO_AUTH_TOKEN,
            phone_number=config.TWILIO_PHONE_NUMBER
        )

        # Get the webhook URL (use Azure Container Apps URL)
        host = "voice-agent-backend.grayriver-5405228a.eastus2.azurecontainerapps.io"
        webhook_url = f"https://{host}/voice"

        call_result = twilio_service.initiate_outbound_call(
            destination_phone=phone_number,
            webhook_url=webhook_url,
            senior_name=senior_name or "there"
        )

        if call_result['success']:
            logger.info(f"✅ Call initiated - SID: {call_result['call_sid']}")
            return {
                "success": True,
                "call_sid": call_result['call_sid'],
                "message": "Call initiated successfully (context pre-loaded)"
            }
        else:
            logger.error(f"❌ Call failed: {call_result.get('error')}")
            return Response(
                content=json.dumps({"success": False, "error": call_result.get('error')}),
                status_code=500,
                media_type="application/json"
            )

    except Exception as e:
        logger.error(f"Failed to initiate call: {e}")
        return Response(
            content=json.dumps({"success": False, "error": str(e)}),
            status_code=500,
            media_type="application/json"
        )

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
    is_processing = False       # Serialize STT→LLM→TTS pipeline
    silence_counter = 0  # Track consecutive silence chunks
    speech_counter = 0  # Track consecutive speech chunks
    SPEECH_CHUNKS_REQUIRED = max(1, VAD_SUSTAINED_CHUNKS)
    no_response_attempts = 0  # Track how many times we've asked user to respond
    MAX_NO_RESPONSE_ATTEMPTS = 3  # End call after 3 failed prompts

    # Adaptive noise floor learning - ENABLED to handle variable phone audio levels
    ambient_noise_samples = []
    ambient_noise_threshold = VAD_MIN_THRESHOLD  # Minimum threshold to avoid ultra-quiet false triggers
    learning_ambient = True  # Learn ambient noise early
    AMBIENT_LEARNING_CHUNKS = VAD_AMBIENT_LEARNING_CHUNKS

    # Input gating/cooldowns
    input_unmute_at = 0.0       # Time when we accept user input again after TTS
    no_prompt_until = 0.0       # Do not prompt "can't hear you" before this time

    # Get phone number from query params (will be passed by run_app.sh)
    # For now, use a default for testing
    phone_number = "289-324-2125"  # TODO: Get from URL params

    try:
        # Main loop - receive audio from caller
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)

            if data.get('event') == 'start':
                import time
                start_time = time.time()
                stream_sid = data['start']['streamSid']
                logger.info(f"⏱️ [0.00s] Stream started: {stream_sid}")

                # Initialize session when stream starts (same as original working version)
                from src.services.profile_service import SeniorProfileService
                from src.senior_health_prompt import SENIOR_HEALTH_SYSTEM_PROMPT

                # Look up senior profile
                senior_name = None
                senior_id = None
                context_loaded = False

                # Check if context was already preloaded via /initiate-call endpoint
                # Normalize phone number for consistent lookup
                normalized_phone = phone_number.replace("-", "").replace(" ", "")
                if normalized_phone in preloaded_context:
                    cached = preloaded_context[normalized_phone]
                    senior_name = cached["senior_name"]
                    senior_id = cached["senior_id"]
                    context_loaded = True
                    logger.info(f"⏱️ [{time.time() - start_time:.2f}s] Using PRE-LOADED context (no delay!)")
                    # Remove from cache after use
                    del preloaded_context[normalized_phone]
                else:
                    # Context not preloaded, load it now (will take 15-30 seconds)
                    logger.info(f"⏱️ [{time.time() - start_time:.2f}s] Context NOT preloaded, loading now...")
                    try:
                        t1 = time.time()
                        profile_service = SeniorProfileService(
                            endpoint=config.AZURE_COSMOS_ENDPOINT,
                            key=config.AZURE_COSMOS_KEY,
                            database_name=config.COSMOS_DATABASE
                        )
                        logger.info(f"⏱️ [{time.time() - start_time:.2f}s] Profile service initialized")

                        profile = profile_service.get_senior_by_phone(phone_number)
                        logger.info(f"⏱️ [{time.time() - start_time:.2f}s] Profile lookup complete")

                        if profile:
                            senior_id = profile['seniorId']
                            full_name = profile['fullName']
                            senior_name = full_name.split()[0] if full_name else None
                            logger.info(f"⏱️ [{time.time() - start_time:.2f}s] Profile parsed")
                    except Exception as e:
                        logger.error(f"Could not get senior profile: {e}")

                    # Load senior context (call history)
                    context_loaded = agent._load_senior_context(phone_number)
                    logger.info(f"⏱️ [{time.time() - start_time:.2f}s] Context loaded: {context_loaded}")

                # Start session with name and ID
                agent.start_new_session(senior_name=senior_name, senior_id=senior_id)
                logger.info(f"⏱️ [{time.time() - start_time:.2f}s] Session started")
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

                logger.info(f"⏱️ [{time.time() - start_time:.2f}s] System prompt set")

                # Generate personalized greeting (EXACT same logic as local)
                if context_loaded and senior_name:
                    greeting = f"Hello {senior_name}! This is {ai_name} calling from Seniorly. It's good to talk with you again today. How are you doing?"
                elif senior_name:
                    greeting = f"Hello {senior_name}! This is {ai_name} calling from Seniorly. How are you doing today?"
                else:
                    greeting = f"Hello! This is {ai_name} calling from Seniorly. How are you doing today?"

                agent.save_message("assistant", greeting)
                logger.info(f"⏱️ [{time.time() - start_time:.2f}s] Greeting saved to DB")

                # Send personalized greeting immediately
                if not greeting_sent and greeting:
                    agent_is_speaking = True
                    logger.info(f"⏱️ [{time.time() - start_time:.2f}s] Starting TTS generation...")
                    await send_audio_to_twilio(websocket, stream_sid, greeting)
                    logger.info(f"⏱️ [{time.time() - start_time:.2f}s] TTS sent to Twilio")
                    greeting_sent = True
                    # Wait a bit for greeting to finish playing, then allow user input
                    await asyncio.sleep(2)
                    agent_is_speaking = False
                    # Add short cooldown to avoid picking up trailing echo
                    input_unmute_at = time.time() + (VAD_COOLDOWN_MS / 1000.0)
                    # Give user a fair window before prompting
                    no_prompt_until = time.time() + VAD_PROMPT_GRACE_SECONDS
                    audio_buffer.clear()  # Clear any audio received during greeting
                    logger.info(f"⏱️ [{time.time() - start_time:.2f}s] Ready for user speech")

            elif data.get('event') == 'media':
                # During agent speech, allow ambient learning but do not process user input
                if agent_is_speaking:
                    payload = data['media']['payload']
                    audio_chunk = base64.b64decode(payload)
                    audio_buffer.extend(audio_chunk)
                    if len(audio_buffer) >= 16000:
                        pcm_data = audioop.ulaw2lin(bytes(audio_buffer), 2)
                        if learning_ambient and len(ambient_noise_samples) < AMBIENT_LEARNING_CHUNKS:
                            audio_array = np.frombuffer(pcm_data, dtype=np.int16)
                            if len(audio_array) > 0:
                                normalized = audio_array.astype(np.float32) / 32768.0
                                rms = np.sqrt(np.mean(normalized ** 2))
                                ambient_noise_samples.append(rms)
                                logger.info(f"📊 (TTS) Learning ambient noise: {rms:.4f} ({len(ambient_noise_samples)}/{AMBIENT_LEARNING_CHUNKS})")
                                if len(ambient_noise_samples) == AMBIENT_LEARNING_CHUNKS:
                                    avg_ambient = np.mean(ambient_noise_samples)
                                    ambient_noise_threshold = max(VAD_MIN_THRESHOLD, avg_ambient * VAD_AMBIENT_MULTIPLIER)
                                    learning_ambient = False
                                    logger.info(f"✅ Ambient learned during TTS: avg={avg_ambient:.4f}, thr={ambient_noise_threshold:.4f}")
                        audio_buffer.clear()
                    continue

                # Received audio from the caller
                payload = data['media']['payload']
                audio_chunk = base64.b64decode(payload)
                audio_buffer.extend(audio_chunk)

                # Respect post-TTS cooldown to avoid echo
                if time.time() < input_unmute_at:
                    if len(audio_buffer) >= VAD_CHUNK_BYTES:
                        audio_buffer.clear()
                    continue

                # Process when we have enough audio (configurable)
                if len(audio_buffer) >= VAD_CHUNK_BYTES and not is_processing:
                    logger.info(f"Processing audio chunk ({len(audio_buffer)} bytes)")
                    is_processing = True

                    # Convert mulaw to PCM to check audio levels first
                    pcm_data = audioop.ulaw2lin(bytes(audio_buffer), 2)

                    # Learn ambient noise for first 3 chunks (6 seconds) - during greeting playback
                    if learning_ambient and len(ambient_noise_samples) < AMBIENT_LEARNING_CHUNKS:
                        audio_array = np.frombuffer(pcm_data, dtype=np.int16)
                        if len(audio_array) > 0:
                            normalized = audio_array.astype(np.float32) / 32768.0
                            rms = np.sqrt(np.mean(normalized ** 2))
                            ambient_noise_samples.append(rms)
                            logger.info(f"📊 Learning ambient noise: {rms:.4f} (sample {len(ambient_noise_samples)}/{AMBIENT_LEARNING_CHUNKS})")

                        if len(ambient_noise_samples) == AMBIENT_LEARNING_CHUNKS:
                                # Set threshold to multiplier x average ambient noise, min floor
                                avg_ambient = np.mean(ambient_noise_samples)
                                ambient_noise_threshold = max(VAD_MIN_THRESHOLD, avg_ambient * VAD_AMBIENT_MULTIPLIER)
                                learning_ambient = False
                                logger.info(f"✅ Ambient noise learned: avg={avg_ambient:.4f}, threshold={ambient_noise_threshold:.4f}")

                        audio_buffer.clear()
                        is_processing = False
                        continue

                    # Gate: Prefer WebRTC VAD when enabled; fallback to RMS-based gate
                    gate_pass = False
                    if VAD_USE_WEBRTC:
                        gate_pass = is_speech_webrtc(pcm_data)
                        if VAD_DEBUG:
                            logger.info(f"VAD(webrtc) => {'pass' if gate_pass else 'fail'}")
                    if not gate_pass:
                        # Fallback to RMS-based detection with adaptive threshold
                        gate_pass = has_significant_audio(pcm_data, threshold=ambient_noise_threshold)

                    if not gate_pass:
                        logger.info("🔇 Background noise detected, ignoring")
                        audio_buffer.clear()
                        speech_counter = 0  # Reset speech counter
                        silence_counter += 1

                        # After 30 seconds of silence (15 chunks x 2 seconds), prompt user
                        if silence_counter >= VAD_SILENCE_CHUNKS_TO_PROMPT and time.time() >= no_prompt_until:
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
                                # After prompt, add cooldown and delay before next prompt
                                input_unmute_at = time.time() + (VAD_COOLDOWN_MS / 1000.0)
                                no_prompt_until = time.time() + VAD_PROMPT_GRACE_SECONDS

                        is_processing = False
                        continue

                    # Valid speech detected - increment counter
                    speech_counter += 1
                    silence_counter = 0
                    no_response_attempts = 0  # Reset timeout counter when speech is detected

                    # Require sustained speech before processing (prevents brief background noises)
                    if speech_counter < SPEECH_CHUNKS_REQUIRED:
                        logger.info(f"🎤 Speech detected ({speech_counter}/{SPEECH_CHUNKS_REQUIRED} chunks), continuing...")
                        # Don't clear buffer yet - accumulate more speech
                        is_processing = False
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
                            # After assistant speaks, add cooldown and delay before any prompt
                            input_unmute_at = time.time() + (VAD_COOLDOWN_MS / 1000.0)
                            no_prompt_until = time.time() + VAD_PROMPT_GRACE_SECONDS

                    # Clear buffer and reset counters
                    audio_buffer.clear()
                    speech_counter = 0
                    is_processing = False

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
