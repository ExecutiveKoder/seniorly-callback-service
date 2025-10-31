#!/usr/bin/env python3
"""
FastAPI Webhook Server for AWS Connect Integration
Handles incoming calls from AWS Connect and provides AI-powered conversations
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
import logging
from typing import Dict, Any
import uvicorn

from src.config import config
from src.services.speech_service import SpeechService
from src.services.openai_service import OpenAIService
from src.services.data_service import DataService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Seniorly Voice Agent Webhook")

# Initialize services
speech_service = None
openai_service = None
data_service = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global speech_service, openai_service, data_service

    logger.info("Initializing Seniorly Voice Agent services...")

    try:
        speech_service = SpeechService(
            speech_key=config.AZURE_SPEECH_KEY,
            speech_region=config.AZURE_SPEECH_REGION,
            voice_name=config.SPEECH_VOICE_NAME
        )
        logger.info("✅ Speech Service initialized")

        openai_service = OpenAIService(
            api_key=config.AZURE_OPENAI_KEY,
            endpoint=config.AZURE_OPENAI_ENDPOINT,
            deployment_name=config.AZURE_OPENAI_DEPLOYMENT_NAME,
            api_version=config.AZURE_OPENAI_API_VERSION
        )
        logger.info("✅ OpenAI Service initialized")

        data_service = DataService(
            cosmos_endpoint=config.AZURE_COSMOS_ENDPOINT,
            cosmos_key=config.AZURE_COSMOS_KEY,
            database_name=config.COSMOS_DATABASE,
            container_name=config.COSMOS_CONTAINER,
            redis_host=config.AZURE_REDIS_HOST,
            redis_key=config.AZURE_REDIS_KEY,
            redis_port=config.REDIS_PORT,
            redis_ssl=config.REDIS_SSL,
            search_endpoint=config.AZURE_SEARCH_ENDPOINT,
            search_key=config.AZURE_SEARCH_KEY,
            search_index=config.SEARCH_INDEX
        )
        logger.info("✅ Data Service initialized")

        logger.info("🚀 All services ready!")

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Seniorly Voice Agent Webhook",
        "status": "operational",
        "ai_agent": config.get_ai_name(),
        "voice": config.SPEECH_VOICE_NAME
    }

@app.post("/webhook/connect")
async def connect_webhook(request: Request):
    """
    Main webhook endpoint for AWS Connect
    Receives call events and returns AI responses
    """
    try:
        # Get the request body (do not log raw content to prevent PHI leakage)
        body = await request.json()
        logger.info("Received AWS Connect webhook (content suppressed)")

        # Extract call details
        contact_id = body.get('ContactId', 'unknown')
        customer_phone = body.get('CustomerEndpoint', {}).get('Address', 'unknown')
        attributes = body.get('Attributes', {})

        senior_name = attributes.get('senior_name', 'there')
        ai_name = config.get_ai_name()

        logger.info(f"Processing call - Contact ID: {contact_id}")

        # Generate greeting using OpenAI
        greeting_prompt = f"Generate a warm, friendly greeting for {senior_name}. Keep it brief (1-2 sentences). You are {ai_name} from Seniorly calling for a daily wellness check."

        greeting = openai_service.chat(
            message=greeting_prompt,
            temperature=0.7,
            max_tokens=50
        )

        if not greeting:
            greeting = f"Hello {senior_name}! This is {ai_name} from Seniorly. How are you doing today?"

        logger.info("Generated greeting (content suppressed)")

        # Return response in AWS Connect format
        return JSONResponse({
            "greeting": greeting,
            "ai_name": ai_name,
            "senior_name": senior_name,
            "status": "success"
        })

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return JSONResponse({
            "error": str(e),
            "status": "error"
        }, status_code=500)

@app.post("/webhook/voice")
async def voice_webhook(request: Request):
    """
    Endpoint that returns voice audio for AWS Connect
    Takes text input and returns audio file
    """
    try:
        body = await request.json()
        text = body.get('text', '')

        if not text:
            return JSONResponse({
                "error": "No text provided"
            }, status_code=400)

        logger.info("Generating speech (content suppressed)")

        # Generate speech using Azure Speech Services
        audio_data = speech_service.synthesize_to_bytes(text)

        if audio_data:
            # Return audio as binary response
            return Response(
                content=audio_data,
                media_type="audio/wav",
                headers={
                    "Content-Disposition": "attachment; filename=speech.wav"
                }
            )
        else:
            return JSONResponse({
                "error": "Failed to generate speech"
            }, status_code=500)

    except Exception as e:
        logger.error(f"Error generating voice: {e}")
        return JSONResponse({
            "error": str(e)
        }, status_code=500)

if __name__ == "__main__":
    # Run the webhook server
    logger.info("Starting Seniorly Voice Agent Webhook Server...")
    logger.info(f"AI Agent: {config.get_ai_name()}")
    logger.info(f"Voice: {config.SPEECH_VOICE_NAME}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )