"""
Senior Health Monitoring Voice Agent - Main Application
Local testing version (microphone/speaker based)
"""
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from src.services.speech_service import SpeechService
from src.services.openai_service import OpenAIService
from src.services.data_service import DataService
from src.services.safety_service import safety_monitor, AlertLevel
from src.services.cost_tracking_service import CostTrackingService
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

        # Initialize Cost Tracking Service
        try:
            self.cost_tracker = CostTrackingService()
            print("✅ Cost Tracking Service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Cost Tracking Service: {e}")
            print(f"❌ Cost Tracking Service failed: {e}")
            # Continue without cost tracking if it fails
            self.cost_tracker = None

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

    def start_new_session(self, senior_name: str = None, senior_id: str = None) -> str:
        """
        Start a new conversation session

        Args:
            senior_name: Optional name of the senior
            senior_id: Optional senior ID from Cosmos DB

        Returns:
            Session ID
        """
        try:
            self.current_session_id = str(uuid.uuid4())

            # Create session in Cosmos DB
            self.data.cosmos.create_session(self.current_session_id)

            # Store session state in Redis with senior ID, name, AI name, and company
            session_state = {
                "session_id": self.current_session_id,
                "senior_id": senior_id or "Unknown",
                "senior_name": senior_name or "Unknown",
                "ai_name": config.get_ai_name(),
                "company_name": "Seniorly",
                "start_time": datetime.utcnow().isoformat(),
                "status": "active"
            }
            # Use senior_id in Redis key for better data isolation
            self.data.redis.set_session_state(self.current_session_id, session_state, senior_id=senior_id)

            logger.info(f"Started new session: {self.current_session_id} for senior: {senior_id}")
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

    def _load_senior_context(self, phone_number: str) -> bool:
        """
        Load context from previous calls for this senior using phone number

        Args:
            phone_number: Senior's phone number (e.g., "289-324-2125")

        Returns:
            True if context loaded successfully
        """
        try:
            from src.services.profile_service import SeniorProfileService

            # Initialize profile service
            profile_service = SeniorProfileService(
                endpoint=config.AZURE_COSMOS_ENDPOINT,
                key=config.AZURE_COSMOS_KEY,
                database_name=config.COSMOS_DATABASE
            )

            # Get senior profile by phone number
            profile = profile_service.get_senior_by_phone(phone_number)
            if not profile:
                print(f"⚠️  Senior profile not found")
                return False

            print(f"✅ Loaded profile for: {profile['fullName']}")

            # Get last few sessions for context
            sessions = profile['callHistory']['sessions'][-3:]  # Last 3 calls

            if not sessions:
                print("   No previous call history")
                return False

            print(f"   Previous calls: {len(sessions)}")

            # Build context summary - EMPHASIZE MOST RECENT CALL
            context_parts = [
                f"CONTEXT FROM PREVIOUS CALLS:"
            ]

            # Add most recent call with emphasis
            if sessions:
                last_session = sessions[-1]
                if last_session.get('summary'):
                    context_parts.append(f"\n🔵 LAST CALL ({last_session['date'][:10]}):")
                    context_parts.append(f"{last_session['summary']}")
                    context_parts.append(f"\n⚠️ CRITICAL INSTRUCTIONS FOR THIS CALL:")
                    context_parts.append(f"   - Naturally reference relevant information from the last call summary above")
                    context_parts.append(f"   - If they mentioned health issues, ask how they're doing now")
                    context_parts.append(f"   - If they had upcoming appointments/events, ask how they went")
                    context_parts.append(f"   - Show continuity of care by remembering what they shared")
                    context_parts.append(f"   - Do NOT repeat the same questions if they were already answered last time")
                    context_parts.append(f"   - Build on the previous conversation naturally")

            # Add older sessions if available
            if len(sessions) > 1:
                context_parts.append(f"\nPrevious calls: {profile['callHistory']['totalCalls']} total")
                for i, session in enumerate(sessions[:-1], 1):  # Exclude the last one (already shown)
                    if session.get('summary'):
                        context_parts.append(f"  • {session['date'][:10]}: {session['summary']}")

            # Add medical info if available
            conditions = profile['medicalInformation'].get('conditions', [])
            if conditions:
                context_parts.append(f"\nKnown conditions: {', '.join(conditions)}")

            # Add any open safety alerts
            open_alerts = profile['safetyAlerts'].get('openAlerts', [])
            if open_alerts:
                context_parts.append(f"\n⚠️ OPEN SAFETY ALERTS: {len(open_alerts)}")
                for alert in open_alerts[-2:]:  # Last 2 alerts
                    context_parts.append(f"  - {alert['level']}: {', '.join(alert['categories'])}")

            context_summary = "\n".join(context_parts)

            # Add dynamic conversation context
            from src.services.conversation_context_service import ConversationContextService
            context_service = ConversationContextService()

            # Build comprehensive context including temporal and historical info
            dynamic_context = context_service.build_conversation_context(
                senior_profile=profile,
                last_sessions=sessions
            )

            # Load upcoming reminders from PostgreSQL
            reminders_context = ""
            try:
                from src.services.reminders_service import RemindersService
                reminders_service = RemindersService()
                upcoming_reminders = reminders_service.get_upcoming_reminders(senior_id, days_ahead=7)

                if upcoming_reminders:
                    reminders_context = "\n\n" + reminders_service.format_reminders_for_context(upcoming_reminders)
                    print(f"   ✅ Loaded {len(upcoming_reminders)} upcoming reminders")
            except Exception as reminder_error:
                logger.warning(f"Could not load reminders: {reminder_error}")

            # Combine profile context with dynamic context and reminders
            full_context = context_summary + "\n\n" + dynamic_context + reminders_context

            # Inject context into AI's conversation memory
            self.openai.conversation_history.insert(0, {
                "role": "system",
                "content": full_context
            })

            print("   ✅ Context loaded into AI memory")
            print("   ✅ Dynamic conversation context added\n")
            return True

        except Exception as e:
            logger.error(f"Error loading senior context: {e}")
            print(f"   ⚠️  Could not load context: {e}")
            return False

    def _perform_identity_verification(self, phone_number: str) -> bool:
        """
        Perform identity verification using name and date of birth
        Uses Azure Speech Services for recognition and Cosmos DB for verification

        Args:
            phone_number: Phone number to look up senior profile

        Returns:
            True if identity verified successfully
        """
        try:
            from src.services.profile_service import SeniorProfileService
            from src.services.identity_verification_service import IdentityVerificationService

            print("\n🔐 IDENTITY VERIFICATION")
            print("   For your security, I need to verify your identity.")

            # Get senior profile
            profile_service = SeniorProfileService(
                endpoint=config.AZURE_COSMOS_ENDPOINT,
                key=config.AZURE_COSMOS_KEY,
                database_name=config.COSMOS_DATABASE
            )

            profile = profile_service.get_senior_by_phone(phone_number)
            if not profile:
                print("   ❌ Could not find your profile")
                return False

            # Get AI name for consistent messaging
            ai_name = config.get_ai_name()

            # Initialize verification service
            verification_service = IdentityVerificationService()

            # Ask for name verification
            name_prompt = "Please say your full name for verification."
            print(f"\n🤖 {ai_name}: {name_prompt}")
            self.speech.synthesize_to_speaker(name_prompt)

            # Track verification speech synthesis
            if self.cost_tracker:
                self.cost_tracker.track_speech_synthesis(name_prompt)

            spoken_name = self.speech.recognize_from_microphone()
            if not spoken_name:
                print("   ❌ Could not hear your name. Please try again.")
                return False

            print(f"   Heard: {spoken_name}")

            # Ask for date of birth verification
            dob_prompt = "Please say your date of birth - month, day and year."
            print(f"\n🤖 {ai_name}: {dob_prompt}")
            self.speech.synthesize_to_speaker(dob_prompt)

            # Track DOB verification speech synthesis
            if self.cost_tracker:
                self.cost_tracker.track_speech_synthesis(dob_prompt)

            spoken_dob = self.speech.recognize_from_microphone()
            if not spoken_dob:
                print("   ❌ Could not hear your date of birth. Please try again.")
                return False

            print(f"   Heard: {spoken_dob}")

            # Perform verification using Azure data
            verification_result = verification_service.verify_identity(
                senior_profile=profile,
                spoken_name=spoken_name,
                spoken_dob=spoken_dob
            )

            if verification_result['verified']:
                success_msg = "Perfect! Your identity has been verified. Let's continue with your wellness check."
                print(f"\n✅ Identity verified (confidence: {verification_result['confidence_score']:.1%})")
                print(f"🤖 {ai_name}: {success_msg}")
                self.speech.synthesize_to_speaker(success_msg)

                # Track success message speech synthesis
                if self.cost_tracker:
                    self.cost_tracker.track_speech_synthesis(success_msg)
                return True
            else:
                failure_msg = "I'm sorry, but I couldn't verify your identity. For your security, I need to end this call. Please contact support if you need assistance."
                print(f"\n❌ Identity verification failed (confidence: {verification_result['confidence_score']:.1%})")
                print(f"🤖 {ai_name}: {failure_msg}")
                self.speech.synthesize_to_speaker(failure_msg)

                # Track failure message speech synthesis
                if self.cost_tracker:
                    self.cost_tracker.track_speech_synthesis(failure_msg)
                return False

        except Exception as e:
            error_msg = "I'm having technical difficulties with identity verification. For security, I need to end this call."
            print(f"\n❌ Verification error: {e}")
            print(f"🤖 {ai_name}: {error_msg}")
            self.speech.synthesize_to_speaker(error_msg)

            # Track error message speech synthesis
            if self.cost_tracker:
                self.cost_tracker.track_speech_synthesis(error_msg)
            return False

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

        # Make actual outbound call using AWS Connect
        phone_number = "289-324-2125"  # John Wick's number
        senior_name = "John Wick"

        print("📞 INITIATING REAL OUTBOUND CALL")
        print(f"   Calling: {phone_number}")

        # Initialize AWS Connect service and make the call
        try:
            from src.services.aws_connect_service import AWSConnectService

            connect_service = AWSConnectService(
                region=config.AWS_REGION,
                instance_id=config.AWS_CONNECT_INSTANCE_ID,
                access_key=config.AWS_ACCESS_KEY_ID,
                secret_key=config.AWS_SECRET_ACCESS_KEY,
                phone_number=config.AWS_CONNECT_PHONE_NUMBER
            )

            # Make the actual call
            call_result = connect_service.initiate_outbound_call(
                destination_phone=phone_number,
                senior_name=senior_name
            )

            if not call_result['success']:
                print(f"❌ Failed to initiate call: {call_result.get('error')}")
                return

            print(f"✅ Call initiated successfully!")
            print(f"   Contact ID: {call_result['contact_id']}")
            print(f"   📞 Your phone ({phone_number}) should be ringing now...")

            # Wait for call to be answered
            import time
            print("   ⏳ Waiting for call to connect...")
            time.sleep(10)  # Give time for call to connect

            print("   🔍 Identifying caller from database...")

        except Exception as e:
            print(f"❌ Error making outbound call: {e}")
            print("   Falling back to simulation mode...")
            phone_number = "289-324-2125"

        # ALWAYS look up senior name and ID from database first (regardless of call history)
        senior_name = None
        senior_id = None
        try:
            from src.services.profile_service import SeniorProfileService
            profile_service = SeniorProfileService(
                endpoint=config.AZURE_COSMOS_ENDPOINT,
                key=config.AZURE_COSMOS_KEY,
                database_name=config.COSMOS_DATABASE
            )
            print(f"🔍 Looking up profile for phone: {phone_number}")
            profile = profile_service.get_senior_by_phone(phone_number)
            if profile:
                senior_id = profile['seniorId']
                full_name = profile['fullName']
                # Extract only the first name
                senior_name = full_name.split()[0] if full_name else None
                print(f"✅ Found profile: {full_name} (ID: {senior_id[:8]}..., using first name: {senior_name})")
            else:
                print(f"⚠️  No profile found for {phone_number}")
        except Exception as e:
            print(f"❌ Could not get senior name: {e}")

        # Load senior context (call history) if available
        context_loaded = self._load_senior_context(phone_number)

        # Start session with name and ID if available (from phone lookup)
        self.start_new_session(senior_name=senior_name, senior_id=senior_id)

        # Reset cost tracking for new session
        if self.cost_tracker:
            self.cost_tracker.reset_session_costs()

        print(f"\n📝 Session ID: {self.current_session_id}")
        print(f"👤 Senior: {senior_name or 'Unknown'}\n")

        # Get AI name from voice configuration
        ai_name = config.get_ai_name()

        # Update system prompt with senior's name - REPLACE placeholders in the prompt
        if senior_name:
            # Replace [Name] placeholder with actual senior name and [Your AI Name] with actual AI name
            personalized_prompt = SENIOR_HEALTH_SYSTEM_PROMPT.replace("[Name]", senior_name).replace("[Your AI Name]", ai_name)
            personalized_prompt += f"\n\nREMINDER: The senior's name is {senior_name}. Always use their actual name, never use placeholders like [Name]."
            self.openai.set_system_prompt(personalized_prompt)
        else:
            # If no name, remove placeholders entirely
            generic_prompt = SENIOR_HEALTH_SYSTEM_PROMPT.replace("[Name]", "them").replace("[Your AI Name]", ai_name)
            self.openai.set_system_prompt(generic_prompt)

        # Initial greeting (personalized if context loaded)
        if context_loaded and senior_name:
            greeting = f"Hello {senior_name}! This is {ai_name} calling from Seniorly. It's good to talk with you again today. How are you doing?"
        elif senior_name:
            greeting = f"Hello {senior_name}! This is {ai_name} calling from Seniorly. How are you doing today?"
        else:
            greeting = f"Hello! This is {ai_name} calling from Seniorly. How are you doing today?"

        print(f"\n🤖 {ai_name}: {greeting}")
        self.speech.synthesize_to_speaker(greeting)

        # Track initial greeting speech synthesis
        if self.cost_tracker:
            self.cost_tracker.track_speech_synthesis(greeting)

        self.save_message("assistant", greeting)

        # Identity verification step (DISABLED FOR NOW)
        # if context_loaded:
        #     verification_passed = self._perform_identity_verification(phone_number)
        #     if not verification_passed:
        #         print("\n🚫 Identity verification failed. Ending call for security.")
        #         return
        print("   ℹ️  Identity verification disabled - skipping for now\n")

        # Conversation loop with STRICT 5-minute time management
        ai_name = config.get_ai_name()  # Get AI name for conversation loop
        turn_count = 0
        conversation_start_time = datetime.now()
        time_warnings_given = {'4min30sec': False}

        while True:
            turn_count += 1
            print(f"\n--- Turn {turn_count} ---")

            # Check call duration with STRICT enforcement
            elapsed_time = datetime.now() - conversation_start_time
            elapsed_seconds = elapsed_time.total_seconds()
            elapsed_minutes = elapsed_seconds / 60

            # 4 minutes 30 seconds warning (user requirement)
            if elapsed_seconds >= 270 and not time_warnings_given['4min30sec']:
                time_warnings_given['4min30sec'] = True
                warning_message = f"We have about 30 seconds left on our call. Is there anything urgent you need to mention?"
                print(f"\n⚠️  4:30 warning")
                print(f"🤖 {ai_name}: {warning_message}")
                self.speech.synthesize_to_speaker(warning_message)

                # Track warning message
                if self.cost_tracker:
                    self.cost_tracker.track_speech_synthesis(warning_message)

                self.save_message("assistant", warning_message)

            # 5-minute HARD LIMIT (user requirement: strict enforcement)
            elif elapsed_seconds >= 300:
                final_message = f"Our time is up for today. We can continue tomorrow. Take care, {senior_name if senior_name else ''}!"
                print(f"\n🛑 5-MINUTE HARD LIMIT REACHED")
                print(f"🤖 {ai_name}: {final_message}")
                self.speech.synthesize_to_speaker(final_message)

                # Track final message
                if self.cost_tracker:
                    self.cost_tracker.track_speech_synthesis(final_message)

                self.save_message("assistant", final_message)
                break

            print(f"⏱️  Call time: {int(elapsed_seconds)}s ({elapsed_minutes:.1f} min)")

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
                print(f"\n🤖 {ai_name}: {farewell}")
                self.speech.synthesize_to_speaker(farewell)

                # Track farewell speech synthesis
                if self.cost_tracker:
                    self.cost_tracker.track_speech_synthesis(farewell)

                self.save_message("assistant", farewell)
                break

            # Short responses that indicate wanting to end (under 10 chars)
            if len(user_lower) < 10 and any(word in user_lower for word in ['bye', 'done', 'go', 'leave']):
                farewell = "Take care! Goodbye."
                print(f"\n🤖 {ai_name}: {farewell}")
                self.speech.synthesize_to_speaker(farewell)

                # Track short farewell speech synthesis
                if self.cost_tracker:
                    self.cost_tracker.track_speech_synthesis(farewell)

                self.save_message("assistant", farewell)
                break

            # Get AI response
            ai_response = self.openai.chat(user_text, temperature=0.7, max_tokens=200)

            # Track OpenAI token usage (estimated based on text length)
            if self.cost_tracker and ai_response:
                # Rough estimation: ~4 chars per token for English text
                input_tokens = len(user_text) // 4
                output_tokens = len(ai_response) // 4
                self.cost_tracker.track_openai_usage(input_tokens, output_tokens)

            if not ai_response:
                print("❌ Failed to get AI response. Ending conversation.")
                break

            print(f"🤖 {ai_name}: {ai_response}")

            # Speak the response
            self.speech.synthesize_to_speaker(ai_response)

            # Track speech synthesis usage
            if self.cost_tracker:
                self.cost_tracker.track_speech_synthesis(ai_response)

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
                print(f"\n🤖 {ai_name}: {farewell}")
                self.speech.synthesize_to_speaker(farewell)

                # Track max turns farewell speech synthesis
                if self.cost_tracker:
                    self.cost_tracker.track_speech_synthesis(farewell)
                break

        print("\n" + "="*60)
        print("📞 CONVERSATION ENDED")
        print("="*60)
        print(f"   Session ID: {self.current_session_id}")
        print(f"   Total turns: {turn_count}")
        print("="*60 + "\n")

        # Generate AI summary of the call for next time
        print("📝 Generating call summary...")
        call_summary = None
        call_duration = int((datetime.now() - conversation_start_time).total_seconds())

        try:
            call_summary = self.openai.generate_call_summary()
            print(f"✅ Summary: {call_summary}\n")

            # Save summary to Cosmos DB in the senior's profile
            if phone_number and senior_name:
                from src.services.profile_service import SeniorProfileService
                profile_service = SeniorProfileService(
                    endpoint=config.AZURE_COSMOS_ENDPOINT,
                    key=config.AZURE_COSMOS_KEY,
                    database_name=config.COSMOS_DATABASE
                )
                profile = profile_service.get_senior_by_phone(phone_number)
                if profile:
                    senior_id = profile['seniorId']
                    # Add call record with summary
                    call_metadata = {
                        "duration": call_duration,
                        "completed": True,
                        "summary": call_summary
                    }
                    profile_service.add_call_record(senior_id, self.current_session_id, call_metadata)
                    print(f"✅ Call summary saved to profile\n")

                    # Save session metadata to Cosmos DB for easy transcript access
                    try:
                        session_metadata = {
                            'senior_name': senior_name,
                            'senior_id': senior_id,
                            'phone_number': phone_number,
                            'duration': call_duration,
                            'summary': call_summary,
                            'completed': True,
                            'ai_name': config.get_ai_name(),
                            'company_name': 'Seniorly'
                        }
                        self.data.cosmos.add_session_metadata(self.current_session_id, session_metadata)
                        print(f"✅ Session metadata saved (for transcript access)\n")
                    except Exception as meta_error:
                        print(f"⚠️  Failed to save session metadata: {meta_error}\n")

                    # Sync conversation data to PostgreSQL analytics database
                    print("📊 Syncing to PostgreSQL analytics database...")
                    try:
                        from src.services.analytics_sync_service import AnalyticsSyncService
                        sync_service = AnalyticsSyncService()

                        # Get the full session data from Cosmos DB
                        session_data = {
                            'sessionId': self.current_session_id,
                            'createdAt': conversation_start_time.isoformat(),
                            'messages': [],
                            'metadata': {
                                'senior_id': senior_id,
                                'senior_name': senior_name,
                                'phone_number': phone_number,
                                'call_duration': call_duration,
                                'summary': call_summary,
                                'call_completed': True
                            }
                        }

                        # Add messages to session data
                        for msg in self.openai.full_conversation_history:
                            session_data['messages'].append({
                                'role': msg['role'],
                                'content': msg['content'],
                                'timestamp': conversation_start_time.isoformat(),
                                'metadata': {}
                            })

                        # Sync to PostgreSQL
                        success = sync_service.sync_conversation(session_data)

                        if success:
                            print(f"✅ Analytics data synced to PostgreSQL\n")
                        else:
                            print(f"⚠️  Failed to sync analytics data\n")

                    except Exception as analytics_error:
                        print(f"⚠️  PostgreSQL sync failed: {analytics_error}\n")
                        # Don't fail the whole call if analytics fails

        except Exception as e:
            print(f"⚠️  Could not generate/save summary: {e}\n")

        # Display cost summary
        if self.cost_tracker:
            # Track final call duration
            final_duration = (datetime.now() - conversation_start_time).total_seconds()
            self.cost_tracker.track_connect_call(final_duration)

            # Show detailed cost breakdown
            self.cost_tracker.print_cost_summary()

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

        # Reset cost tracking for new session
        if self.cost_tracker:
            self.cost_tracker.reset_session_costs()

        print(f"\n📝 Session ID: {self.current_session_id}")
        print(f"👤 Senior: {senior_name or 'Unknown'}\n")

        # Get AI name from voice configuration
        ai_name = config.get_ai_name()

        # Initial greeting
        greeting = f"Hello! This is {ai_name}, your daily wellness companion. How are you doing today?"
        print(f"\n🤖 {ai_name}: {greeting}\n")
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

            # Track OpenAI token usage (estimated)
            if self.cost_tracker and ai_response:
                input_tokens = len(user_input) // 4
                output_tokens = len(ai_response) // 4
                self.cost_tracker.track_openai_usage(input_tokens, output_tokens)

            if not ai_response:
                print("❌ Failed to get AI response.")
                break

            print(f"\n🤖 {ai_name}: {ai_response}\n")
            self.save_message("assistant", ai_response)

        print(f"\n📝 Session saved: {self.current_session_id}")

        # Display cost summary for text conversation
        if self.cost_tracker:
            self.cost_tracker.print_cost_summary()
        print()

    def dial_phone_number(self):
        """Make actual outbound call using AWS Connect"""
        print("\n" + "="*60)
        print("📞 AWS CONNECT OUTBOUND CALLING")
        print("="*60)

        # Get phone number to dial
        phone_number = input("Enter phone number to call (e.g., 289-324-2125): ").strip()

        if not phone_number:
            print("❌ No phone number entered.")
            return

        try:
            from src.services.aws_connect_service import AWSConnectService

            print(f"\n📞 Initiating call to: {phone_number}")
            print("⚠️  This will make a real phone call using AWS Connect!")

            confirm = input("Continue? (y/N): ").strip().lower()
            if confirm != 'y':
                print("📞 Call cancelled.")
                return

            # Initialize AWS Connect service
            connect_service = AWSConnectService(
                region=config.AWS_REGION,
                instance_id=config.AWS_CONNECT_INSTANCE_ID,
                access_key=config.AWS_ACCESS_KEY_ID,
                secret_key=config.AWS_SECRET_ACCESS_KEY,
                phone_number=config.AWS_CONNECT_PHONE_NUMBER
            )

            # Test connection first
            if not connect_service.test_connection():
                print("❌ AWS Connect connection failed. Check your configuration.")
                return

            # Make the call
            call_result = connect_service.initiate_outbound_call(
                destination_phone=phone_number,
                senior_name="Senior"  # We'll identify them during the call
            )

            if call_result['success']:
                print(f"✅ Call initiated successfully!")
                print(f"   Contact ID: {call_result['contact_id']}")
                print(f"   From: {config.AWS_CONNECT_PHONE_NUMBER}")
                print(f"   To: {phone_number}")
                print("\n📞 The phone should be ringing now...")
                print("⚠️  Note: You'll need a Contact Flow set up in AWS Connect to handle the call.")
            else:
                print(f"❌ Call failed: {call_result.get('error')}")

        except Exception as e:
            print(f"❌ Error making call: {e}")

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

        # Check if direct voice mode was requested
        import sys
        if len(sys.argv) > 1 and sys.argv[1] == '--voice':
            # Skip menu, go directly to voice conversation
            agent.run_voice_conversation()
            return

        # Main menu
        while True:
            print("\n" + "="*60)
            print("SENIOR HEALTH MONITORING - MAIN MENU")
            print("="*60)
            print("1. Start Voice Conversation (Microphone + Speaker)")
            print("2. Start Text Conversation (Keyboard only)")
            print("3. Dial Phone Number (AWS Connect Outbound Call)")
            print("4. View Conversation History")
            print("5. Test Services")
            print("6. Exit")
            print("="*60)

            choice = input("\nSelect an option (1-6): ").strip()

            if choice == '1':
                agent.run_voice_conversation()
            elif choice == '2':
                agent.run_text_conversation()
            elif choice == '3':
                agent.dial_phone_number()
            elif choice == '4':
                session_id = input("Enter session ID (or press Enter for current): ").strip()
                agent.view_conversation_history(session_id or None)
            elif choice == '5':
                agent.test_connections()
            elif choice == '6':
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
