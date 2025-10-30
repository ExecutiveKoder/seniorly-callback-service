#!/usr/bin/env python3
"""
Kinesis Video Streams Audio Processor
Handles real-time audio streaming from AWS Connect calls
Uses Azure Speech Services for consistent voice (Jason)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import boto3
import io
import wave
import logging
from typing import Optional
import time

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


class KinesisAudioProcessor:
    """Processes audio streams from AWS Connect via Kinesis Video Streams"""

    def __init__(self):
        """Initialize the audio processor with all services"""

        logger.info("Initializing Kinesis Audio Processor...")

        # Initialize AWS clients
        self.kinesis_video_client = boto3.client(
            'kinesisvideo',
            region_name=config.AWS_REGION,
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY
        )

        # Initialize Azure services
        self.speech_service = SpeechService(
            speech_key=config.AZURE_SPEECH_KEY,
            speech_region=config.AZURE_SPEECH_REGION,
            voice_name=config.SPEECH_VOICE_NAME
        )

        self.openai_service = OpenAIService(
            api_key=config.AZURE_OPENAI_KEY,
            endpoint=config.AZURE_OPENAI_ENDPOINT,
            deployment_name=config.AZURE_OPENAI_DEPLOYMENT_NAME,
            api_version=config.AZURE_OPENAI_API_VERSION
        )

        self.data_service = DataService(
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

        self.ai_name = config.get_ai_name()
        logger.info(f"✅ Services initialized - AI Agent: {self.ai_name}")

    def get_stream_endpoint(self, stream_name: str) -> str:
        """Get the data endpoint for a Kinesis Video Stream"""
        try:
            response = self.kinesis_video_client.get_data_endpoint(
                StreamName=stream_name,
                APIName='GET_MEDIA'
            )
            return response['DataEndpoint']
        except Exception as e:
            logger.error(f"Failed to get stream endpoint: {e}")
            raise

    def process_audio_chunk(self, audio_data: bytes) -> Optional[str]:
        """
        Process an audio chunk:
        1. Transcribe using Azure Speech (STT)
        2. Generate response using GPT-5
        3. Synthesize response using Azure Speech (TTS) - Jason voice

        Args:
            audio_data: Raw audio bytes from the call

        Returns:
            Audio response bytes (TTS from Jason)
        """
        try:
            # Save audio chunk to temporary file for Azure Speech
            temp_audio_file = "/tmp/incoming_audio.wav"
            with wave.open(temp_audio_file, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(8000)  # 8kHz (phone quality)
                wav_file.writeframes(audio_data)

            # Transcribe using Azure Speech Services
            logger.info("Transcribing audio...")
            transcribed_text = self.speech_service.recognize_from_file(temp_audio_file)

            if not transcribed_text:
                logger.warning("No speech recognized in audio chunk")
                return None

            logger.info(f"Transcribed: {transcribed_text}")

            # Generate AI response using GPT-5
            logger.info("Generating AI response...")
            ai_response = self.openai_service.chat(
                message=transcribed_text,
                temperature=0.7,
                max_tokens=150
            )

            if not ai_response:
                logger.warning("No AI response generated")
                return None

            logger.info(f"AI Response: {ai_response}")

            # Synthesize response using Azure Speech (Jason's voice)
            logger.info(f"Synthesizing response with {self.ai_name}'s voice...")
            response_audio = self.speech_service.synthesize_to_file(
                text=ai_response,
                output_file="/tmp/response_audio.wav"
            )

            if response_audio:
                # Read the audio file and return bytes
                with open("/tmp/response_audio.wav", 'rb') as f:
                    return f.read()

            return None

        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")
            return None

    def start_processing(self, stream_name: str = "seniorly-voice-agent-audio"):
        """
        Start processing audio from the Kinesis Video Stream

        Args:
            stream_name: Name of the Kinesis Video Stream
        """
        logger.info(f"Starting audio processor for stream: {stream_name}")
        logger.info(f"Using AI Agent: {self.ai_name} with voice: {config.SPEECH_VOICE_NAME}")

        try:
            # Get the data endpoint
            endpoint = self.get_stream_endpoint(stream_name)
            logger.info(f"Stream endpoint: {endpoint}")

            # Create media client for the stream
            kinesis_video_media = boto3.client(
                'kinesis-video-media',
                endpoint_url=endpoint,
                region_name=config.AWS_REGION,
                aws_access_key_id=config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY
            )

            logger.info("🎧 Listening for incoming audio streams...")
            logger.info("💬 Will respond with Jason's voice via Azure Speech Services")

            # Get media from stream
            response = kinesis_video_media.get_media(
                StreamName=stream_name,
                StartSelector={'StartSelectorType': 'NOW'}
            )

            # Process the streaming payload
            payload = response['Payload']
            audio_buffer = bytearray()
            chunk_size = 8000  # Process chunks of ~1 second at 8kHz

            for chunk in payload.iter_chunks():
                audio_buffer.extend(chunk)

                # Process when we have enough audio
                if len(audio_buffer) >= chunk_size:
                    logger.info(f"Processing audio chunk ({len(audio_buffer)} bytes)")

                    # Process the audio and get response
                    response_audio = self.process_audio_chunk(bytes(audio_buffer))

                    # Clear buffer
                    audio_buffer.clear()

                    # TODO: Send response_audio back to the caller
                    # This requires setting up the output stream back to AWS Connect
                    if response_audio:
                        logger.info(f"Generated response audio ({len(response_audio)} bytes)")

        except KeyboardInterrupt:
            logger.info("\n🛑 Stopping audio processor...")
        except Exception as e:
            logger.error(f"Error in audio processing loop: {e}")
            raise


def main():
    """Main entry point"""
    print("="*60)
    print("🎙️  SENIORLY VOICE AGENT - KINESIS AUDIO PROCESSOR")
    print("="*60)
    print(f"AI Agent: {config.get_ai_name()}")
    print(f"Voice: {config.SPEECH_VOICE_NAME}")
    print("="*60 + "\n")

    processor = KinesisAudioProcessor()
    processor.start_processing()


if __name__ == "__main__":
    main()
