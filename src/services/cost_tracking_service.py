"""
Cost Tracking Service
Tracks costs for AI tokens, speech services, and infrastructure usage
"""
import logging
from typing import Dict, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class CostTrackingService:
    """Tracks and calculates costs for various services used during conversations"""

    def __init__(self):
        """Initialize cost tracking service with current pricing"""

        # Azure OpenAI GPT-5-Chat Pricing (per 1M tokens)
        self.openai_pricing = {
            'input_tokens': 0.003,   # $3 per 1M input tokens
            'output_tokens': 0.015   # $15 per 1M output tokens
        }

        # Azure Speech Services Pricing
        self.speech_pricing = {
            'stt_per_hour': 1.00,      # Speech-to-Text: $1 per hour
            'tts_per_1m_chars': 16.00  # Text-to-Speech: $16 per 1M characters
        }

        # AWS Connect Pricing
        self.connect_pricing = {
            'outbound_per_minute': 0.018  # $0.018 per minute for outbound calls
        }

        # Azure Cosmos DB Pricing (Serverless)
        self.cosmos_pricing = {
            'request_unit': 0.000014,  # $0.000014 per RU
            'storage_per_gb': 0.25     # $0.25 per GB per month
        }

        # Initialize call session tracking
        self.reset_session_costs()

    def reset_session_costs(self):
        """Reset cost tracking for a new session"""
        self.session_costs = {
            'start_time': datetime.now(),
            'openai_input_tokens': 0,
            'openai_output_tokens': 0,
            'speech_chars_synthesized': 0,
            'speech_minutes_recognized': 0,
            'connect_call_minutes': 0,
            'cosmos_request_units': 0,
            'total_messages': 0,
            'call_duration_seconds': 0
        }

    def track_openai_usage(self, input_tokens: int, output_tokens: int):
        """Track OpenAI token usage"""
        self.session_costs['openai_input_tokens'] += input_tokens
        self.session_costs['openai_output_tokens'] += output_tokens
        self.session_costs['total_messages'] += 1

    def track_speech_synthesis(self, text: str):
        """Track text-to-speech character usage"""
        char_count = len(text)
        self.session_costs['speech_chars_synthesized'] += char_count

    def track_speech_recognition(self, duration_seconds: float):
        """Track speech-to-text usage"""
        minutes = duration_seconds / 60.0
        self.session_costs['speech_minutes_recognized'] += minutes

    def track_connect_call(self, duration_seconds: float):
        """Track AWS Connect call duration"""
        minutes = duration_seconds / 60.0
        self.session_costs['connect_call_minutes'] += minutes
        self.session_costs['call_duration_seconds'] += duration_seconds

    def track_cosmos_usage(self, request_units: float):
        """Track Cosmos DB request unit usage"""
        self.session_costs['cosmos_request_units'] += request_units

    def calculate_session_costs(self) -> Dict:
        """Calculate total costs for the current session"""

        # OpenAI costs
        openai_input_cost = (self.session_costs['openai_input_tokens'] / 1_000_000) * self.openai_pricing['input_tokens']
        openai_output_cost = (self.session_costs['openai_output_tokens'] / 1_000_000) * self.openai_pricing['output_tokens']
        total_openai_cost = openai_input_cost + openai_output_cost

        # Speech services costs
        tts_cost = (self.session_costs['speech_chars_synthesized'] / 1_000_000) * self.speech_pricing['tts_per_1m_chars']
        stt_cost = (self.session_costs['speech_minutes_recognized'] / 60) * self.speech_pricing['stt_per_hour']
        total_speech_cost = tts_cost + stt_cost

        # AWS Connect costs
        connect_cost = self.session_costs['connect_call_minutes'] * self.connect_pricing['outbound_per_minute']

        # Cosmos DB costs (estimated)
        cosmos_cost = self.session_costs['cosmos_request_units'] * self.cosmos_pricing['request_unit']

        # Calculate session duration
        session_duration = (datetime.now() - self.session_costs['start_time']).total_seconds()

        total_cost = total_openai_cost + total_speech_cost + connect_cost + cosmos_cost

        return {
            'session_duration_minutes': round(session_duration / 60, 2),
            'call_duration_minutes': round(self.session_costs['call_duration_seconds'] / 60, 2),
            'total_messages': self.session_costs['total_messages'],

            # Token usage
            'openai_input_tokens': self.session_costs['openai_input_tokens'],
            'openai_output_tokens': self.session_costs['openai_output_tokens'],
            'total_tokens': self.session_costs['openai_input_tokens'] + self.session_costs['openai_output_tokens'],

            # Character usage
            'speech_chars_synthesized': self.session_costs['speech_chars_synthesized'],
            'speech_minutes_recognized': round(self.session_costs['speech_minutes_recognized'], 2),

            # Infrastructure usage
            'connect_call_minutes': round(self.session_costs['connect_call_minutes'], 2),
            'cosmos_request_units': round(self.session_costs['cosmos_request_units'], 1),

            # Cost breakdown
            'costs': {
                'openai_input': round(openai_input_cost, 4),
                'openai_output': round(openai_output_cost, 4),
                'openai_total': round(total_openai_cost, 4),
                'speech_tts': round(tts_cost, 4),
                'speech_stt': round(stt_cost, 4),
                'speech_total': round(total_speech_cost, 4),
                'aws_connect': round(connect_cost, 4),
                'cosmos_db': round(cosmos_cost, 4),
                'total': round(total_cost, 4)
            },

            # Cost per minute estimates
            'cost_per_minute': round(total_cost / max(session_duration / 60, 0.1), 4),
            'estimated_monthly_cost': round(total_cost * 30, 2) if total_cost > 0 else 0.0
        }

    def print_cost_summary(self):
        """Print a detailed cost summary for the session"""
        costs = self.calculate_session_costs()

        print("\n" + "="*60)
        print("💰 CALL COST SUMMARY")
        print("="*60)

        print(f"📞 Call Duration: {costs['call_duration_minutes']} minutes")
        print(f"🕒 Session Duration: {costs['session_duration_minutes']} minutes")
        print(f"💬 Total Messages: {costs['total_messages']}")

        print(f"\n🤖 AI USAGE:")
        print(f"   Input Tokens: {costs['openai_input_tokens']:,}")
        print(f"   Output Tokens: {costs['openai_output_tokens']:,}")
        print(f"   Total Tokens: {costs['total_tokens']:,}")

        print(f"\n🎙️ SPEECH SERVICES:")
        print(f"   Characters Synthesized: {costs['speech_chars_synthesized']:,}")
        print(f"   Recognition Minutes: {costs['speech_minutes_recognized']}")

        print(f"\n☁️ INFRASTRUCTURE:")
        print(f"   AWS Connect Minutes: {costs['connect_call_minutes']}")
        print(f"   Cosmos DB RUs: {costs['cosmos_request_units']}")

        print(f"\n💵 COST BREAKDOWN:")
        print(f"   OpenAI (Input): ${costs['costs']['openai_input']:.4f}")
        print(f"   OpenAI (Output): ${costs['costs']['openai_output']:.4f}")
        print(f"   OpenAI Total: ${costs['costs']['openai_total']:.4f}")
        print(f"   Speech Services: ${costs['costs']['speech_total']:.4f}")
        print(f"   AWS Connect: ${costs['costs']['aws_connect']:.4f}")
        print(f"   Cosmos DB: ${costs['costs']['cosmos_db']:.4f}")
        print(f"   ────────────────────────")
        print(f"   TOTAL COST: ${costs['costs']['total']:.4f}")

        print(f"\n📊 ESTIMATES:")
        print(f"   Cost per minute: ${costs['cost_per_minute']:.4f}")
        if costs['estimated_monthly_cost'] > 0:
            print(f"   Est. monthly (30 calls): ${costs['estimated_monthly_cost']:.2f}")

        print("="*60)

    def get_cost_json(self) -> str:
        """Get cost summary as JSON string"""
        costs = self.calculate_session_costs()
        return json.dumps(costs, indent=2)