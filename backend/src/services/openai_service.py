"""
Azure OpenAI Service integration
Handles GPT-5-CHAT conversational AI
"""
from openai import AzureOpenAI
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class OpenAIService:
    """Manages Azure OpenAI GPT-5-CHAT interactions"""

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        deployment_name: str,
        api_version: str = "2025-04-01-preview"
    ):
        """
        Initialize Azure OpenAI Service

        Args:
            api_key: Azure OpenAI API key
            endpoint: Azure OpenAI endpoint URL
            deployment_name: Name of the GPT-5-CHAT deployment
            api_version: API version to use
        """
        self.deployment_name = deployment_name
        self.api_version = api_version

        # Extract base endpoint (remove the path after /openai/)
        if '/openai/' in endpoint:
            base_endpoint = endpoint.split('/openai/')[0]
        else:
            base_endpoint = endpoint.rstrip('/')

        # Initialize Azure OpenAI client
        self.client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=base_endpoint
        )

        # Conversation history for context (trimmed for performance)
        self.conversation_history: List[Dict[str, str]] = []
        # Full conversation history (kept for summary generation)
        self.full_conversation_history: List[Dict[str, str]] = []

        # System prompt for voice agent
        self.system_prompt = """You are a helpful and friendly AI voice assistant.
You have natural conversations with users and provide accurate, concise responses.
Keep your responses conversational and not too long since they will be spoken aloud.
Be warm, engaging, and professional."""

        logger.info(f"OpenAI Service initialized with deployment: {self.deployment_name}")

    def set_system_prompt(self, prompt: str):
        """
        Set or update the system prompt

        Args:
            prompt: New system prompt
        """
        self.system_prompt = prompt
        logger.info("System prompt updated")

    def trim_conversation_history(self, max_turns: int = 8):
        """
        Trim conversation history to prevent lag and token overflow.
        Keeps the most recent exchanges while preserving initial context.

        Args:
            max_turns: Maximum number of user-assistant turn pairs to keep (default: 8)
        """
        # Separate system messages (context) from conversation
        system_messages = [msg for msg in self.conversation_history if msg["role"] == "system"]
        conversation = [msg for msg in self.conversation_history if msg["role"] != "system"]

        # Keep only the last N turns (each turn = user + assistant message)
        max_messages = max_turns * 2  # 2 messages per turn
        if len(conversation) > max_messages:
            conversation = conversation[-max_messages:]
            logger.info(f"Trimmed conversation history to last {max_turns} turns")

        # Reconstruct: system messages first, then recent conversation
        self.conversation_history = system_messages + conversation

    def chat(self, user_message: str, temperature: float = 0.7, max_tokens: int = 500) -> Optional[str]:
        """
        Send a message to GPT-5-CHAT and get a response

        Args:
            user_message: User's input message
            temperature: Sampling temperature (0-1, higher = more creative)
            max_tokens: Maximum tokens in response

        Returns:
            AI response text or None if error
        """
        try:
            # Add user message to BOTH histories
            user_msg = {"role": "user", "content": user_message}
            self.conversation_history.append(user_msg)
            self.full_conversation_history.append(user_msg)

            # Build messages array with system prompt and history
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(self.conversation_history)

            logger.info(f"Sending message to GPT-5-CHAT: {user_message[:50]}...")
            print(f"\n🤖 Thinking...")

            # Call Azure OpenAI with balanced optimization
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                temperature=temperature,
                max_tokens=min(max_tokens, 120),  # Allow complete sentences
                frequency_penalty=0.0,  # Remove penalty that was cutting responses
                presence_penalty=0.0,   # Remove penalty that was cutting responses
                stream=False
            )

            # Extract assistant response
            assistant_message = response.choices[0].message.content

            # Add assistant response to BOTH histories
            assistant_msg = {"role": "assistant", "content": assistant_message}
            self.conversation_history.append(assistant_msg)
            self.full_conversation_history.append(assistant_msg)

            # Trim working history to prevent lag (keep full history for summary)
            self.trim_conversation_history(max_turns=8)

            logger.info(f"Received response: {assistant_message[:50]}...")
            return assistant_message

        except Exception as e:
            logger.error(f"Error calling Azure OpenAI: {e}")
            print(f"❌ Error: {e}")
            return None

    def chat_stream(self, user_message: str, temperature: float = 0.7, max_tokens: int = 500):
        """
        Send a message and stream the response token by token

        Args:
            user_message: User's input message
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Yields:
            Chunks of the AI response as they arrive
        """
        try:
            # Add user message to conversation history
            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })

            # Build messages array
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(self.conversation_history)

            logger.info(f"Streaming response for: {user_message[:50]}...")
            print(f"\n🤖 Response: ", end="", flush=True)

            # Call Azure OpenAI with streaming
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )

            full_response = ""
            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'content') and delta.content:
                        content = delta.content
                        full_response += content
                        print(content, end="", flush=True)
                        yield content

            print()  # New line after streaming completes

            # Add full response to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": full_response
            })

            logger.info(f"Streaming completed. Full response length: {len(full_response)}")

        except Exception as e:
            logger.error(f"Error during streaming: {e}")
            print(f"\n❌ Error: {e}")
            yield None

    def chat_with_context(
        self,
        user_message: str,
        context: str,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> Optional[str]:
        """
        Send a message with additional context (e.g., from knowledge base search)

        Args:
            user_message: User's input message
            context: Additional context to include (from AI Search, etc.)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            AI response text or None if error
        """
        try:
            # Create enhanced message with context
            enhanced_message = f"""Context information:
{context}

User question: {user_message}

Please answer the user's question using the context provided above. If the context doesn't contain relevant information, use your general knowledge."""

            return self.chat(enhanced_message, temperature, max_tokens)

        except Exception as e:
            logger.error(f"Error in chat_with_context: {e}")
            return None

    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        logger.info("Conversation history cleared")
        print("🗑️  Conversation history cleared")

    def get_conversation_summary(self) -> str:
        """
        Get a summary of the current conversation (simple truncated version)

        Returns:
            Summary text
        """
        if not self.conversation_history:
            return "No conversation history"

        summary = f"Conversation with {len(self.conversation_history)} messages:\n"
        for i, msg in enumerate(self.conversation_history, 1):
            role = msg['role'].capitalize()
            content = msg['content'][:50] + "..." if len(msg['content']) > 50 else msg['content']
            summary += f"{i}. {role}: {content}\n"

        return summary

    def generate_call_summary(self) -> str:
        """
        Generate an AI-powered summary of the call for context in future calls.
        Uses the FULL conversation history (not trimmed) for comprehensive summary.

        Returns:
            AI-generated summary suitable for use in next call's context
        """
        if not self.full_conversation_history:
            return "No conversation occurred"

        # Filter out system messages for summary (use full history for complete summary)
        user_messages = [msg for msg in self.full_conversation_history if msg['role'] in ['user', 'assistant']]

        if len(user_messages) < 2:
            return "Brief call, no significant content to summarize"

        # Build conversation transcript for summarization
        transcript = "\n".join([
            f"{'Senior' if msg['role'] == 'user' else 'AI'}: {msg['content']}"
            for msg in user_messages
        ])

        summary_prompt = f"""You are summarizing a wellness check-in call with a senior for medical record purposes.

Review this conversation and create a COMPREHENSIVE, DETAILED summary (2-3 paragraphs) that will be useful for the NEXT call and for tracking the senior's health over time.

Include ALL relevant details about:
- Physical health: Any pain, symptoms, discomfort, sleep quality, energy levels, appetite
- Medications: What they're taking, adherence, any side effects mentioned
- Mental/Emotional state: Mood, affect, signs of depression/anxiety, social engagement
- Daily activities: What they did, mobility, independence level, physical activity/walking
- Social connections: Family visits, phone calls, social activities
- Upcoming events: Doctor appointments, family visits, plans, reminders
- Concerns expressed: Worries, fears, questions they had
- Cognitive observations: Memory, orientation, coherence of responses
- **PERSONAL DETAILS (CRITICAL - include if mentioned):**
  * Pets: Names, types, if they walked/played with them
  * Family: Names of children, grandchildren, spouse mentioned
  * Hobbies/Interests: Activities they enjoy, TV shows, books
  * Appointments/Reminders: Specific dates for doctor visits, events, family visits
- Any red flags or items requiring follow-up

Write as if you're a healthcare provider documenting the encounter. Be specific and detailed. Include names and specific details that show we remember the person as an individual, not just a patient.

Conversation:
{transcript}

Detailed Summary:"""

        try:
            # Use a simple completion to generate summary
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": "You are a healthcare provider creating detailed clinical summaries of senior wellness check-in calls for continuity of care."},
                    {"role": "user", "content": summary_prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )

            summary = response.choices[0].message.content.strip()
            logger.info(f"Generated call summary: {summary[:100]}...")
            return summary

        except Exception as e:
            logger.error(f"Error generating call summary: {e}")
            return f"Call completed with {len(user_messages)} exchanges"

    def save_conversation(self) -> List[Dict[str, str]]:
        """
        Get conversation history for saving to database

        Returns:
            List of conversation messages
        """
        return self.conversation_history.copy()

    def load_conversation(self, history: List[Dict[str, str]]):
        """
        Load conversation history from database

        Args:
            history: List of conversation messages
        """
        self.conversation_history = history.copy()
        logger.info(f"Loaded conversation with {len(history)} messages")
        print(f"📥 Loaded conversation with {len(history)} messages")
