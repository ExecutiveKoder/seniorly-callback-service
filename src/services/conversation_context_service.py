"""
Conversation Context Service
Makes conversations more natural and dynamic by adding temporal and historical context
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import calendar
import random

logger = logging.getLogger(__name__)


class ConversationContextService:
    """Provides dynamic conversation context based on time, history, and events"""

    def __init__(self):
        """Initialize the conversation context service"""
        self.holidays_2024 = {
            "2024-01-01": "New Year's Day",
            "2024-01-15": "Martin Luther King Jr. Day",
            "2024-02-19": "Presidents Day",
            "2024-05-27": "Memorial Day",
            "2024-07-04": "Independence Day",
            "2024-09-02": "Labor Day",
            "2024-10-14": "Columbus Day",
            "2024-11-11": "Veterans Day",
            "2024-11-28": "Thanksgiving",
            "2024-12-25": "Christmas Day"
        }

        self.holidays_2025 = {
            "2025-01-01": "New Year's Day",
            "2025-01-20": "Martin Luther King Jr. Day",
            "2025-02-17": "Presidents Day",
            "2025-05-26": "Memorial Day",
            "2025-07-04": "Independence Day",
            "2025-09-01": "Labor Day",
            "2025-10-13": "Columbus Day",
            "2025-11-11": "Veterans Day",
            "2025-11-27": "Thanksgiving",
            "2025-12-25": "Christmas Day"
        }

        logger.info("Conversation Context Service initialized")

    def build_conversation_context(self, senior_profile: Dict, last_sessions: List[Dict]) -> str:
        """
        Build dynamic conversation context based on time, history, and senior profile

        Args:
            senior_profile: Senior's profile data
            last_sessions: Recent conversation sessions

        Returns:
            Context string to inject into AI conversation
        """
        try:
            context_parts = []

            # Temporal context (day of week, holidays, seasons)
            temporal_context = self._get_temporal_context()
            if temporal_context:
                context_parts.append(temporal_context)

            # Historical context from previous conversations
            if last_sessions:
                historical_context = self._get_historical_context(last_sessions)
                if historical_context:
                    context_parts.append(historical_context)

            # Health context patterns
            health_context = self._get_health_context(senior_profile, last_sessions)
            if health_context:
                context_parts.append(health_context)

            # Conversation starters and question suggestions
            conversation_starters = self._get_conversation_starters(senior_profile, last_sessions)
            if conversation_starters:
                context_parts.append(conversation_starters)

            return "\n\n".join(context_parts)

        except Exception as e:
            logger.error(f"Error building conversation context: {e}")
            return ""

    def _get_temporal_context(self) -> str:
        """Get context based on current day, week, season, and holidays"""
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        context_parts = []

        # Day of week context
        day_name = now.strftime("%A")
        context_parts.append(f"TODAY: {day_name}, {now.strftime('%B %d, %Y')}")

        # Weekend/weekday context
        if now.weekday() == 0:  # Monday
            context_parts.append("MONDAY CONTEXT: You can naturally ask about their weekend - 'How was your weekend?' is appropriate")
        elif now.weekday() == 4:  # Friday
            context_parts.append("FRIDAY CONTEXT: You can ask about weekend plans - 'Any plans for the weekend?' is natural")
        elif now.weekday() in [5, 6]:  # Weekend
            context_parts.append("WEEKEND CONTEXT: This is a weekend call - ask about weekend activities or relaxation")
        else:  # Tuesday-Thursday
            context_parts.append("WEEKDAY CONTEXT: Regular weekday - focus on daily routine and wellness")

        # Holiday context
        holiday_context = self._get_holiday_context(now, today_str)
        if holiday_context:
            context_parts.append(holiday_context)

        # Season context
        season_context = self._get_season_context(now)
        if season_context:
            context_parts.append(season_context)

        return "\n".join(context_parts)

    def _get_holiday_context(self, now: datetime, today_str: str) -> str:
        """Get holiday-related context"""
        # Check if today is a holiday
        all_holidays = {**self.holidays_2024, **self.holidays_2025}

        if today_str in all_holidays:
            holiday_name = all_holidays[today_str]
            return f"HOLIDAY TODAY: {holiday_name} - acknowledge this special day naturally in conversation"

        # Check for upcoming holidays (next 7 days)
        for i in range(1, 8):
            future_date = (now + timedelta(days=i)).strftime("%Y-%m-%d")
            if future_date in all_holidays:
                holiday_name = all_holidays[future_date]
                days_until = i
                return f"UPCOMING HOLIDAY: {holiday_name} in {days_until} day{'s' if days_until > 1 else ''} - you can mention this if appropriate"

        # Check for recent holidays (past 3 days)
        for i in range(1, 4):
            past_date = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            if past_date in all_holidays:
                holiday_name = all_holidays[past_date]
                days_ago = i
                return f"RECENT HOLIDAY: {holiday_name} was {days_ago} day{'s' if days_ago > 1 else ''} ago - you can ask how they celebrated"

        return ""

    def _get_season_context(self, now: datetime) -> str:
        """Get seasonal context for natural conversation"""
        month = now.month

        if month in [12, 1, 2]:
            return "WINTER SEASON: You can ask about staying warm, winter activities, or holiday preparations"
        elif month in [3, 4, 5]:
            return "SPRING SEASON: Natural to ask about spring activities, gardening, or warmer weather"
        elif month in [6, 7, 8]:
            return "SUMMER SEASON: Ask about summer activities, staying cool, or outdoor time"
        elif month in [9, 10, 11]:
            return "FALL SEASON: You can ask about fall activities, changing weather, or holiday preparations"

        return ""

    def _get_historical_context(self, last_sessions: List[Dict]) -> str:
        """Extract relevant context from previous conversations"""
        if not last_sessions:
            return ""

        context_parts = ["PREVIOUS CONVERSATIONS CONTEXT:"]

        # Analyze last few sessions
        for i, session in enumerate(last_sessions[:3], 1):
            session_date = session.get('date', '')[:10]  # YYYY-MM-DD
            session_summary = session.get('summary', '')

            if session_summary:
                context_parts.append(f"Call {i} ({session_date}): {session_summary}")

        # Extract patterns and follow-up opportunities
        follow_ups = self._extract_follow_up_opportunities(last_sessions)
        if follow_ups:
            context_parts.append("NATURAL FOLLOW-UPS:")
            context_parts.extend(follow_ups)

        return "\n".join(context_parts)

    def _extract_follow_up_opportunities(self, sessions: List[Dict]) -> List[str]:
        """Extract natural follow-up questions from previous conversations"""
        follow_ups = []

        # Keywords that suggest follow-up opportunities
        follow_up_keywords = {
            'doctor': "You can ask: 'How did your doctor visit go?'",
            'appointment': "Natural to ask: 'How was your appointment?'",
            'family': "You might ask: 'How are your family members doing?'",
            'grandchildren': "Consider asking: 'How are the grandkids?'",
            'medication': "You can check: 'How are you feeling with your medications?'",
            'pain': "Appropriate to ask: 'How has your pain been?'",
            'sleep': "Natural to ask: 'How has your sleep been?'",
            'exercise': "You might ask: 'Have you been able to keep up with your walks?'",
            'worried': "Show care: 'How are you feeling about what was concerning you?'",
            'excited': "Follow up: 'How did that thing you were excited about go?'",
            'planning': "Ask naturally: 'How did your plans work out?'"
        }

        # Look through recent sessions for keywords
        recent_text = ""
        for session in sessions[:2]:  # Last 2 sessions
            if 'messages' in session:
                for message in session['messages']:
                    if message.get('role') == 'user':
                        recent_text += " " + message.get('content', '').lower()

        # Find relevant follow-ups
        for keyword, follow_up in follow_up_keywords.items():
            if keyword in recent_text:
                follow_ups.append(f"- {follow_up}")

        return follow_ups[:3]  # Limit to 3 follow-ups

    def _get_health_context(self, senior_profile: Dict, last_sessions: List[Dict]) -> str:
        """Get health-related context for natural conversation"""
        context_parts = []

        # Medical conditions context
        conditions = senior_profile.get('medicalInformation', {}).get('conditions', [])
        if conditions:
            context_parts.append(f"HEALTH CONDITIONS: {', '.join(conditions)} - be supportive and check how they're managing")

        # Medication context
        medications = senior_profile.get('medicalInformation', {}).get('medications', [])
        if medications:
            med_names = [med.get('name', '') for med in medications if med.get('name')]
            if med_names:
                context_parts.append(f"MEDICATIONS: Taking {', '.join(med_names[:3])} - you can ask about medication routine if natural")

        # Recent health patterns from sessions
        if last_sessions:
            health_patterns = self._analyze_health_patterns(last_sessions)
            if health_patterns:
                context_parts.append(health_patterns)

        return "\n".join(context_parts) if context_parts else ""

    def _analyze_health_patterns(self, sessions: List[Dict]) -> str:
        """Analyze health patterns from recent conversations"""
        # This is where you could add more sophisticated analysis
        # For now, keep it simple

        health_keywords = ['tired', 'pain', 'sleep', 'medication', 'doctor', 'feeling']
        recent_health_mentions = []

        for session in sessions[:2]:
            if 'messages' in session:
                for message in session['messages']:
                    if message.get('role') == 'user':
                        content = message.get('content', '').lower()
                        for keyword in health_keywords:
                            if keyword in content:
                                recent_health_mentions.append(keyword)
                                break

        if recent_health_mentions:
            return f"RECENT HEALTH TOPICS: Mentioned {', '.join(set(recent_health_mentions))} recently - natural to follow up"

        return ""

    def _get_conversation_starters(self, senior_profile: Dict, last_sessions: List[Dict]) -> str:
        """Get dynamic conversation starters and question suggestions"""
        now = datetime.now()
        starters = []

        # Time-based starters
        if now.weekday() == 0:  # Monday
            starters.extend([
                "How was your weekend?",
                "Did you do anything fun this weekend?",
                "How are you feeling to start the new week?"
            ])
        elif now.weekday() == 4:  # Friday
            starters.extend([
                "Any plans for the weekend?",
                "Looking forward to the weekend?",
                "How has your week been?"
            ])
        elif now.weekday() in [5, 6]:  # Weekend
            starters.extend([
                "How are you enjoying your weekend?",
                "Are you having a relaxing weekend?",
                "What have you been up to today?"
            ])

        # General wellness starters (always available)
        starters.extend([
            "How are you feeling today?",
            "How has your week been going?",
            "What's been on your mind lately?",
            "How are you sleeping these days?",
            "Have you been able to get outside at all?"
        ])

        # Select 3-4 random starters
        selected_starters = random.sample(starters, min(4, len(starters)))

        return f"CONVERSATION STARTER OPTIONS: {' | '.join(selected_starters)}"