"""
Senior Health Monitoring Voice Agent - Main Application
Local testing version (microphone/speaker based)
"""
import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from src.services.speech_service import SpeechService
from src.services.openai_service import OpenAIService
from src.services.data_service import DataService
from src.services.safety_service import safety_monitor, AlertLevel
from src.senior_health_prompt import SENIOR_HEALTH_SYSTEM_PROMPT
import uuid
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SeniorHealthAgent:
    """Main application class for Senior Health Monitoring"""

    def __init__(self):
        """Initialize all services"""
        print("\n" + "="*60)
        print("🏥 SENIOR HEALTH MONITORING AI")
        print("   Daily Wellness Check-in System")
        print("="*60 + "\n")

        # Validate configuration
        if not config.validate():
            print("\n❌ Configuration validation failed. Please check your .env file.")
            sys.exit(1)

        print("📋 Initializing services...")

        # Initialize Speech Service
        try:
            self.speech = SpeechService(
                speech_key=config.AZURE_SPEECH_KEY,
                speech_region=config.AZURE_SPEECH_REGION,
                voice_name=config.SPEECH_VOICE_NAME
            )
            print("✅ Speech Service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Speech Service: {e}")
            print(f"❌ Speech Service failed: {e}")
            sys.exit(1)

        # Initialize OpenAI Service with Senior Health prompt
        try:
            self.openai = OpenAIService(
                api_key=config.AZURE_OPENAI_KEY,
                endpoint=config.AZURE_OPENAI_ENDPOINT,
                deployment_name=config.AZURE_OPENAI_DEPLOYMENT_NAME,
                api_version=config.AZURE_OPENAI_API_VERSION
            )
            self.openai.set_system_prompt(SENIOR_HEALTH_SYSTEM_PROMPT)
            print("✅ OpenAI Service initialized with Senior Health prompt")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI Service: {e}")
            print(f"❌ OpenAI Service failed: {e}")
            sys.exit(1)

        # Initialize Data Service
        try:
            self.data = DataService(
                cosmos_endpoint=config.AZURE_COSMOS_ENDPOINT,
                cosmos_key=config.AZURE_COSMOS_KEY,
                cosmos_database=config.COSMOS_DATABASE,
                cosmos_container=config.COSMOS_CONTAINER,
                redis_host=config.AZURE_REDIS_HOST,
                redis_key=config.AZURE_REDIS_KEY,
                redis_port=config.REDIS_PORT,
                redis_ssl=config.REDIS_SSL,
                search_endpoint=config.AZURE_SEARCH_ENDPOINT,
                search_key=config.AZURE_SEARCH_KEY,
                search_index=config.SEARCH_INDEX
            )
            print("✅ Data Services initialized (Cosmos DB + Redis + AI Search)")
        except Exception as e:
            logger.error(f"Failed to initialize Data Service: {e}")
            print(f"❌ Data Service failed: {e}")
            sys.exit(1)

        # Session management
        self.current_session_id = None
        self.senior_profile = {}

        print("\n✅ All services ready!\n")
        print("💡 Tip: Use menu option 4 to test service connections\n")

    def test_connections(self):
        """Test all service connections"""
        print("\n🔍 Testing service connections...")
        print("  (This may take a few seconds)\n")

        status = self.data.test_connections()

        for service, is_connected in status.items():
            if is_connected:
                print(f"  ✅ {service.upper()} connected")
            else:
                print(f"  ⚠️  {service.upper()} connection failed")
                if service == "redis":
                    print(f"     Note: Redis has public access disabled - this is expected")
                    print(f"     Redis will still work for local connections")

    def start_new_session(self, senior_name: str = None) -> str:
        """
        Start a new conversation session

        Args:
            senior_name: Optional name of the senior

        Returns:
            Session ID
        """
        try:
            self.current_session_id = str(uuid.uuid4())

            # Create session in Cosmos DB
            self.data.cosmos.create_session(self.current_session_id)

            # Store session state in Redis
            session_state = {
                "session_id": self.current_session_id,
                "senior_name": senior_name or "Unknown",
                "start_time": datetime.utcnow().isoformat(),
                "status": "active"
            }
            self.data.redis.set_session_state(self.current_session_id, session_state)

            logger.info(f"Started new session: {self.current_session_id}")
            return self.current_session_id

        except Exception as e:
            logger.error(f"Error starting session: {e}")
            # Continue even if database fails
            self.current_session_id = str(uuid.uuid4())
            return self.current_session_id

    def save_message(self, role: str, content: str, metadata: dict = None):
        """Save a message to the database with safety monitoring"""
        if not self.current_session_id:
            return

        # Perform safety analysis
        safety_analysis = safety_monitor.analyze_message(content, role)

        # Add safety analysis to metadata
        if metadata is None:
            metadata = {}
        metadata["safety_analysis"] = safety_analysis

        # Log safety alerts
        if safety_analysis["alert_level"] != AlertLevel.NONE.value:
            alert_msg = safety_monitor.format_alert_message(safety_analysis)
            logger.warning(f"SAFETY ALERT in {role} message:\n{alert_msg}")
            print(f"\n⚠️  {alert_msg}\n")

            # For emergency situations, provide immediate guidance
            if safety_analysis["alert_level"] == AlertLevel.EMERGENCY.value:
                print("\n" + "="*60)
                print("🚨 EMERGENCY DETECTED - IMMEDIATE ACTION REQUIRED")
                print("="*60)
                print(f"Recommended Action: {safety_analysis['recommended_action']}")
                print("\nCrisis Resources:")
                for name, contact in safety_monitor.get_crisis_resources().items():
                    print(f"  - {name}: {contact}")
                print("="*60 + "\n")

        try:
            self.data.cosmos.add_message(
                session_id=self.current_session_id,
                role=role,
                content=content,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            # Continue even if save fails

    def run_voice_conversation(self):
        """Run a voice conversation loop with microphone input and speaker output"""
        print("\n" + "="*60)
        print("🎙️  STARTING VOICE CONVERSATION")
        print("="*60)
        print("\nHow to use:")
        print("  - Speak into your microphone when prompted")
        print("  - Say 'goodbye' or 'end call' to end the conversation")
        print("  - Type 'quit' at any prompt to exit\n")
        print("="*60 + "\n")

        # Start new session
        senior_name = input("Enter senior's name (or press Enter to skip): ").strip()
        self.start_new_session(senior_name or None)

        print(f"\n📝 Session ID: {self.current_session_id}")
        print(f"👤 Senior: {senior_name or 'Unknown'}\n")

        # Initial greeting
        greeting = "Hello! This is Sarah, your daily wellness companion. How are you doing today?"
        print(f"\n🤖 Sarah: {greeting}")
        self.speech.synthesize_to_speaker(greeting)
        self.save_message("assistant", greeting)

        # Conversation loop
        turn_count = 0
        while True:
            turn_count += 1
            print(f"\n--- Turn {turn_count} ---")

            # Get user input via speech recognition
            user_text = self.speech.recognize_from_microphone()

            if not user_text:
                print("⚠️  No speech detected. Please try again.")
                continue

            print(f"👤 You: {user_text}")
            self.save_message("user", user_text)

            # Check for end conversation keywords (improved detection)
            exit_phrases = [
                'goodbye', 'good bye', 'bye', 'bye bye',
                'end call', 'hang up', 'gotta go', 'have to go',
                'need to go', 'talk later', 'talk to you later',
                'see you later', 'i\'m done', 'that\'s all',
                'thanks bye', 'okay bye', 'alright bye'
            ]

            user_lower = user_text.lower().strip()

            # Direct exit detection
            if any(phrase in user_lower for phrase in exit_phrases):
                farewell = "Thank you for chatting with me today. Take care!"
                print(f"\n🤖 Sarah: {farewell}")
                self.speech.synthesize_to_speaker(farewell)
                self.save_message("assistant", farewell)
                break

            # Short responses that indicate wanting to end (under 10 chars)
            if len(user_lower) < 10 and any(word in user_lower for word in ['bye', 'done', 'go', 'leave']):
                farewell = "Take care! Goodbye."
                print(f"\n🤖 Sarah: {farewell}")
                self.speech.synthesize_to_speaker(farewell)
                self.save_message("assistant", farewell)
                break

            # Get AI response
            ai_response = self.openai.chat(user_text, temperature=0.7, max_tokens=200)

            if not ai_response:
                print("❌ Failed to get AI response. Ending conversation.")
                break

            print(f"🤖 Sarah: {ai_response}")

            # Speak the response
            self.speech.synthesize_to_speaker(ai_response)
            self.save_message("assistant", ai_response)

            # Check if AI's response is a farewell (safety check)
            ai_lower = ai_response.lower()
            farewell_indicators = [
                'take care', 'goodbye', 'talk to you tomorrow',
                'speak with you tomorrow', 'until tomorrow',
                'see you tomorrow', 'call you tomorrow'
            ]

            if any(indicator in ai_lower for indicator in farewell_indicators):
                # AI has said goodbye, end the call
                print("\n📞 Call ending (farewell detected)")
                break

            # Safety check - limit conversation length for testing
            if turn_count >= 20:
                print("\n⚠️  Maximum turns reached for this session.")
                farewell = "It's been wonderful talking with you. Take care!"
                print(f"\n🤖 Sarah: {farewell}")
                self.speech.synthesize_to_speaker(farewell)
                break

        print("\n" + "="*60)
        print("📞 CONVERSATION ENDED")
        print("="*60)
        print(f"   Session ID: {self.current_session_id}")
        print(f"   Total turns: {turn_count}")
        print("="*60 + "\n")

    def run_text_conversation(self):
        """Run a text-based conversation (no voice, for quick testing)"""
        print("\n" + "="*60)
        print("💬 STARTING TEXT CONVERSATION")
        print("="*60)
        print("\nType 'quit' to exit\n")
        print("="*60 + "\n")

        # Start new session
        senior_name = input("Enter senior's name (or press Enter to skip): ").strip()
        self.start_new_session(senior_name or None)

        print(f"\n📝 Session ID: {self.current_session_id}")
        print(f"👤 Senior: {senior_name or 'Unknown'}\n")

        # Initial greeting
        greeting = "Hello! This is Sarah, your daily wellness companion. How are you doing today?"
        print(f"\n🤖 Sarah: {greeting}\n")
        self.save_message("assistant", greeting)

        # Conversation loop
        while True:
            user_input = input("👤 You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!")
                break

            self.save_message("user", user_input)

            # Get AI response
            ai_response = self.openai.chat(user_input, temperature=0.7, max_tokens=200)

            if not ai_response:
                print("❌ Failed to get AI response.")
                break

            print(f"\n🤖 Sarah: {ai_response}\n")
            self.save_message("assistant", ai_response)

        print(f"\n📝 Session saved: {self.current_session_id}\n")

    def view_conversation_history(self, session_id: str = None):
        """View conversation history for a session"""
        sid = session_id or self.current_session_id
        if not sid:
            print("❌ No session ID provided")
            return

        try:
            session = self.data.cosmos.get_session(sid)
            if not session:
                print(f"❌ Session not found: {sid}")
                return

            print("\n" + "="*60)
            print(f"📋 CONVERSATION HISTORY - Session: {sid}")
            print("="*60)
            print(f"Created: {session.get('createdAt', 'Unknown')}")
            print(f"Updated: {session.get('updatedAt', 'Unknown')}")
            print(f"Messages: {len(session.get('messages', []))}")
            print("="*60 + "\n")

            for i, msg in enumerate(session.get('messages', []), 1):
                role = msg['role'].upper()
                content = msg['content']
                timestamp = msg.get('timestamp', 'Unknown')
                print(f"{i}. [{role}] at {timestamp}")
                print(f"   {content}\n")

        except Exception as e:
            logger.error(f"Error viewing history: {e}")
            print(f"❌ Error: {e}")


def main():
    """Main entry point"""
    try:
        agent = SeniorHealthAgent()

        # Main menu
        while True:
            print("\n" + "="*60)
            print("SENIOR HEALTH MONITORING - MAIN MENU")
            print("="*60)
            print("1. Start Voice Conversation (Microphone + Speaker)")
            print("2. Start Text Conversation (Keyboard only)")
            print("3. View Conversation History")
            print("4. Test Services")
            print("5. Exit")
            print("="*60)

            choice = input("\nSelect an option (1-5): ").strip()

            if choice == '1':
                agent.run_voice_conversation()
            elif choice == '2':
                agent.run_text_conversation()
            elif choice == '3':
                session_id = input("Enter session ID (or press Enter for current): ").strip()
                agent.view_conversation_history(session_id or None)
            elif choice == '4':
                agent.test_connections()
            elif choice == '5':
                print("\n👋 Goodbye!\n")
                break
            else:
                print("\n❌ Invalid option. Please try again.")

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Exiting...\n")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Fatal error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
