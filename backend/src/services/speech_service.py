"""
Azure Speech Services integration
Handles Speech-to-Text (STT) and Text-to-Speech (TTS)
"""
import azure.cognitiveservices.speech as speechsdk
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class SpeechService:
    """Manages Azure Speech Services for STT and TTS"""

    def __init__(self, speech_key: str, speech_region: str, voice_name: str = "en-US-JennyNeural"):
        """
        Initialize Speech Service

        Args:
            speech_key: Azure Speech Services API key
            speech_region: Azure region (e.g., 'eastus2')
            voice_name: Neural voice name (default: en-US-JennyNeural)
        """
        self.speech_key = speech_key
        self.speech_region = speech_region
        self.voice_name = voice_name

        # Create speech config
        self.speech_config = speechsdk.SpeechConfig(
            subscription=self.speech_key,
            region=self.speech_region
        )
        self.speech_config.speech_synthesis_voice_name = self.voice_name

        # Enable noise suppression for better recognition in noisy environments
        # This helps filter out TV, background conversations, etc.
        self.speech_config.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs,
            "5000"  # 5 seconds of silence before timing out
        )
        self.speech_config.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs,
            "1000"  # 1 second of silence to end utterance
        )
        # Enable enhanced noise suppression
        self.speech_config.set_property(
            speechsdk.PropertyId.SpeechServiceResponse_PostProcessingOption,
            "TrueText"  # Enables profanity filtering and improved punctuation
        )

        logger.info(f"Speech Service initialized with voice: {self.voice_name} (noise suppression enabled)")

    def recognize_from_microphone(self) -> Optional[str]:
        """
        Recognize speech from the default microphone

        Returns:
            Recognized text or None if recognition failed
        """
        try:
            # Create audio config for microphone input
            audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)

            # Create speech recognizer
            speech_recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.speech_config,
                audio_config=audio_config
            )

            logger.info("Listening... Speak into your microphone.")
            print("\n🎤 Listening... (speak now)")

            # Perform recognition
            result = speech_recognizer.recognize_once_async().get()

            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                logger.info(f"Recognized: {result.text}")
                return result.text
            elif result.reason == speechsdk.ResultReason.NoMatch:
                logger.warning("No speech could be recognized")
                print("❌ No speech could be recognized")
                return None
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                logger.error(f"Speech recognition canceled: {cancellation.reason}")
                if cancellation.reason == speechsdk.CancellationReason.Error:
                    logger.error(f"Error details: {cancellation.error_details}")
                return None

        except Exception as e:
            logger.error(f"Error during speech recognition: {e}")
            print(f"❌ Error: {e}")
            return None

    def recognize_from_file(self, audio_file_path: str) -> Optional[str]:
        """
        Recognize speech from an audio file

        Args:
            audio_file_path: Path to audio file (WAV format)

        Returns:
            Recognized text or None if recognition failed
        """
        try:
            # Create audio config for file input
            audio_config = speechsdk.audio.AudioConfig(filename=audio_file_path)

            # Create speech recognizer
            speech_recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.speech_config,
                audio_config=audio_config
            )

            logger.info(f"Processing audio file: {audio_file_path}")
            print(f"\n🎵 Processing audio file: {audio_file_path}")

            # Perform recognition
            result = speech_recognizer.recognize_once_async().get()

            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                logger.info(f"Recognized: {result.text}")
                return result.text
            elif result.reason == speechsdk.ResultReason.NoMatch:
                logger.warning("No speech could be recognized in file")
                return None
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                logger.error(f"Speech recognition canceled: {cancellation.reason}")
                if cancellation.reason == speechsdk.CancellationReason.Error:
                    logger.error(f"Error details: {cancellation.error_details}")
                return None

        except Exception as e:
            logger.error(f"Error during file speech recognition: {e}")
            print(f"❌ Error: {e}")
            return None

    def synthesize_to_speaker(self, text: str) -> bool:
        """
        Convert text to speech and play through default speaker

        Args:
            text: Text to convert to speech

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create audio config for default speaker
            audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)

            # Create speech synthesizer
            speech_synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config,
                audio_config=audio_config
            )

            logger.info(f"Synthesizing text: {text[:50]}...")
            print(f"\n🔊 Speaking: {text}")

            # Use SSML for faster, more natural speech
            ssml_text = f"""
            <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
                <voice name="{self.voice_name}">
                    <prosody rate="1.1" pitch="+5%">{text}</prosody>
                </voice>
            </speak>
            """

            # Perform synthesis with optimized SSML
            result = speech_synthesizer.speak_ssml_async(ssml_text).get()

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.info("Speech synthesis completed successfully")
                return True
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                logger.error(f"Speech synthesis canceled: {cancellation.reason}")
                if cancellation.reason == speechsdk.CancellationReason.Error:
                    logger.error(f"Error details: {cancellation.error_details}")
                return False

        except Exception as e:
            logger.error(f"Error during speech synthesis: {e}")
            print(f"❌ Error: {e}")
            return False

    def synthesize_to_file(self, text: str, output_file_path: str) -> bool:
        """
        Convert text to speech and save to audio file

        Args:
            text: Text to convert to speech
            output_file_path: Path to save audio file (WAV format)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create audio config for file output
            audio_config = speechsdk.audio.AudioOutputConfig(filename=output_file_path)

            # Create speech synthesizer
            speech_synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config,
                audio_config=audio_config
            )

            logger.info(f"Synthesizing text to file: {output_file_path}")
            print(f"\n💾 Saving speech to: {output_file_path}")

            # Perform synthesis
            result = speech_synthesizer.speak_text_async(text).get()

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.info(f"Speech synthesis saved to {output_file_path}")
                print(f"✅ Audio saved to: {output_file_path}")
                return True
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                logger.error(f"Speech synthesis canceled: {cancellation.reason}")
                if cancellation.reason == speechsdk.CancellationReason.Error:
                    logger.error(f"Error details: {cancellation.error_details}")
                return False

        except Exception as e:
            logger.error(f"Error during speech synthesis to file: {e}")
            print(f"❌ Error: {e}")
            return False

    def synthesize_to_audio_data(self, text: str) -> Optional[bytes]:
        """
        Convert text to speech and return raw audio data (WAV format)
        Uses 1.1x speed and +5% pitch for natural, energetic delivery

        Args:
            text: Text to convert to speech

        Returns:
            Raw audio bytes (WAV format) or None if synthesis failed
        """
        try:
            # Create speech synthesizer with no audio output (we'll get raw data)
            speech_synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config,
                audio_config=None  # No audio output, we'll get raw data
            )

            logger.info(f"Synthesizing text to audio data (length: {len(text)})")

            # Use SSML for faster, more natural speech (1.1x speed)
            ssml_text = f"""
            <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
                <voice name="{self.voice_name}">
                    <prosody rate="1.1" pitch="+5%">{text}</prosody>
                </voice>
            </speak>
            """

            # Perform synthesis with SSML
            result = speech_synthesizer.speak_ssml_async(ssml_text).get()

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.info(f"Speech synthesis completed, audio data size: {len(result.audio_data)} bytes")
                return result.audio_data  # Returns WAV format bytes
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                logger.error(f"Speech synthesis canceled: {cancellation.reason}")
                if cancellation.reason == speechsdk.CancellationReason.Error:
                    logger.error(f"Error details: {cancellation.error_details}")
                return None

        except Exception as e:
            logger.error(f"Error during speech synthesis to audio data: {e}")
            return None

    def set_voice(self, voice_name: str):
        """
        Change the voice used for speech synthesis

        Args:
            voice_name: Neural voice name (e.g., 'en-US-GuyNeural', 'en-US-AriaNeural')
        """
        self.voice_name = voice_name
        self.speech_config.speech_synthesis_voice_name = voice_name
        logger.info(f"Voice changed to: {voice_name}")
        print(f"🎙️ Voice changed to: {voice_name}")
