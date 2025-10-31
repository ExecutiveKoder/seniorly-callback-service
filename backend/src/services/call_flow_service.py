"""
Call Flow Service
Manages structured todos for each call conversation
Ensures the agent covers all necessary topics
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CallFlowService:
    """Service to manage call todos and ensure complete conversations"""

    def __init__(self):
        """Initialize call flow tracking"""
        self.call_todos = []
        self.completed_todos = []
        self.current_turn = 0

    def initialize_call_todos(self, senior_profile: Dict = None) -> List[Dict]:
        """
        Initialize the todo list for a new call

        Args:
            senior_profile: Optional senior profile to customize todos

        Returns:
            List of todo items with priorities
        """
        base_todos = [
            {
                'id': 'greeting',
                'topic': 'Greeting and small talk',
                'priority': 'critical',
                'completed': False,
                'target_turn': 1,
                'questions': [
                    "Hi [Name]! How are you doing today?",
                    "How have you been feeling since we last talked?"
                ]
            },
            {
                'id': 'reminders',
                'topic': 'Check reminders and appointments',
                'priority': 'critical',
                'completed': False,
                'target_turn': 1,
                'questions': [
                    "Just a reminder - you have [appointment] [when].",
                    "Did you remember your doctor appointment coming up?"
                ]
            },
            {
                'id': 'general_health',
                'topic': 'General health check',
                'priority': 'critical',
                'completed': False,
                'target_turn': 3,
                'questions': [
                    "How have you been feeling overall?",
                    "Any new aches, pains, or concerns?",
                    "Have you been feeling dizzy or lightheaded at all?"
                ]
            },
            {
                'id': 'vitals',
                'topic': 'Vitals - BP, heart rate, weight',
                'priority': 'high',
                'completed': False,
                'target_turn': 5,
                'questions': [
                    "Have you checked your blood pressure recently?",
                    "What was your reading?",
                    "Have you noticed any changes in your weight?"
                ]
            },
            {
                'id': 'sleep',
                'topic': 'Sleep quality',
                'priority': 'high',
                'completed': False,
                'target_turn': 6,
                'questions': [
                    "How have you been sleeping?",
                    "How many hours of sleep did you get last night?",
                    "Any trouble falling or staying asleep?"
                ]
            },
            {
                'id': 'activity',
                'topic': 'Physical activity and mobility',
                'priority': 'critical',
                'completed': False,
                'target_turn': 7,
                'questions': [
                    "Did you get a chance to take a walk today?",
                    "How long did you walk for?",
                    "Did you do any other exercise - stretching, yoga, gardening?",
                    "Did you leave the house at all today?"
                ]
            },
            {
                'id': 'falls_safety',
                'topic': 'Falls and balance check',
                'priority': 'critical',
                'completed': False,
                'target_turn': 8,
                'questions': [
                    "Have you had any falls, stumbles, or moments where you felt unsteady since we last talked?",
                    "Any dizzy spells or loss of balance?"
                ]
            },
            {
                'id': 'chronic_conditions',
                'topic': 'Chronic condition management',
                'priority': 'high',
                'completed': False,
                'target_turn': 9,
                'questions': [
                    "How has your [condition] been doing?",
                    "Any new symptoms or flare-ups?",
                    "Are you keeping up with your treatment plan?"
                ]
            },
            {
                'id': 'medications',
                'topic': 'Medication adherence',
                'priority': 'high',
                'completed': False,
                'target_turn': 10,
                'questions': [
                    "Have you been taking your medications regularly?",
                    "Any issues with your medications?",
                    "Did you take your morning medication today?"
                ]
            },
            {
                'id': 'social_connection',
                'topic': 'Social connections',
                'priority': 'medium',
                'completed': False,
                'target_turn': 11,
                'questions': [
                    "Have you talked to family or friends recently?",
                    "Did you see or call anyone today?"
                ]
            },
            {
                'id': 'cognitive_check',
                'topic': 'Cognitive assessment',
                'priority': 'medium',
                'completed': False,
                'target_turn': 12,
                'questions': [
                    "What day of the week is it today?",
                    "Can you tell me what month and year it is?",
                    "Can you count backwards from 20 by 3s for me?"
                ]
            },
            {
                'id': 'research_offer',
                'topic': 'Offer research and resources',
                'priority': 'medium',
                'completed': False,
                'target_turn': 13,
                'questions': [
                    "Is there anything health-related you'd like me to research for you?",
                    "Would you like me to find information about [condition] management?",
                    "I can search for nearby doctors or educational resources - would that be helpful?"
                ]
            },
            {
                'id': 'concerns_followup',
                'topic': 'Address any concerns',
                'priority': 'high',
                'completed': False,
                'target_turn': 14,
                'questions': [
                    "Is there anything else you'd like to discuss?",
                    "Any questions or concerns for me?"
                ]
            }
        ]

        # Customize based on senior profile
        if senior_profile:
            conditions = senior_profile.get('medicalInformation', {}).get('conditions', [])
            if conditions:
                # Add specific condition check
                for todo in base_todos:
                    if todo['id'] == 'chronic_conditions':
                        todo['questions'] = [
                            f"How has your {', '.join(conditions)} been doing?",
                            "Any new symptoms or changes?",
                            "Are you following your treatment plan?"
                        ]

        self.call_todos = base_todos
        return base_todos

    def mark_todo_completed(self, todo_id: str) -> bool:
        """Mark a todo as completed"""
        for todo in self.call_todos:
            if todo['id'] == todo_id:
                todo['completed'] = True
                self.completed_todos.append({
                    'id': todo_id,
                    'topic': todo['topic'],
                    'completed_at_turn': self.current_turn
                })
                logger.info(f"✅ Completed todo: {todo_id} ({todo['topic']})")
                return True
        return False

    def get_next_todo(self) -> Optional[Dict]:
        """Get the next pending todo based on priority and target turn"""
        pending = [t for t in self.call_todos if not t['completed']]

        if not pending:
            return None

        # Sort by priority and target turn
        priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        pending.sort(key=lambda x: (priority_order.get(x['priority'], 4), x['target_turn']))

        return pending[0]

    def get_completion_status(self) -> Dict:
        """Get overall completion status"""
        total = len(self.call_todos)
        completed = len([t for t in self.call_todos if t['completed']])
        critical_todos = [t for t in self.call_todos if t['priority'] == 'critical']
        critical_completed = len([t for t in critical_todos if t['completed']])

        return {
            'total': total,
            'completed': completed,
            'percentage': round((completed / total) * 100, 1) if total > 0 else 0,
            'critical_total': len(critical_todos),
            'critical_completed': critical_completed,
            'all_critical_done': critical_completed == len(critical_todos),
            'pending': [t for t in self.call_todos if not t['completed']]
        }

    def should_wrap_up(self) -> bool:
        """Determine if call should wrap up"""
        status = self.get_completion_status()

        # All critical topics covered
        if status['all_critical_done']:
            return True

        # Or if we've covered 80%+ of all topics
        if status['percentage'] >= 80:
            return True

        return False

    def get_context_for_ai(self) -> str:
        """
        Generate context string for AI to guide conversation

        Returns:
            Formatted string with todo guidance
        """
        next_todo = self.get_next_todo()
        status = self.get_completion_status()

        lines = [
            "\n═══════════════════════════════════════════════════════",
            "CALL FLOW GUIDANCE (INTERNAL - DO NOT MENTION TO SENIOR)",
            "═══════════════════════════════════════════════════════"
        ]

        if next_todo:
            lines.append(f"\n🎯 NEXT TOPIC TO COVER: {next_todo['topic']}")
            lines.append(f"   Priority: {next_todo['priority'].upper()}")
            lines.append(f"   Example questions:")
            for q in next_todo['questions'][:2]:
                lines.append(f"   - {q}")

        lines.append(f"\n📊 Progress: {status['completed']}/{status['total']} topics covered ({status['percentage']}%)")
        lines.append(f"   Critical topics: {status['critical_completed']}/{status['critical_total']}")

        pending_critical = [t for t in self.call_todos if not t['completed'] and t['priority'] == 'critical']
        if pending_critical:
            lines.append(f"\n⚠️  CRITICAL TOPICS STILL PENDING:")
            for todo in pending_critical:
                lines.append(f"   - {todo['topic']}")

        if self.should_wrap_up():
            lines.append(f"\n✅ All critical topics covered - you can wrap up naturally")

        lines.append("═══════════════════════════════════════════════════════\n")

        return "\n".join(lines)

    def detect_topic_coverage(self, user_message: str, ai_message: str) -> List[str]:
        """
        Detect which topics were covered in this exchange

        Args:
            user_message: What the senior said
            ai_message: What the AI asked/said

        Returns:
            List of todo IDs that were covered
        """
        covered = []
        combined_text = (user_message + " " + ai_message).lower()

        # Detection patterns
        patterns = {
            'vitals': ['blood pressure', 'bp', 'heart rate', 'pulse', 'weight'],
            'sleep': ['sleep', 'sleeping', 'slept', 'hours of sleep', 'insomnia'],
            'activity': ['walk', 'walked', 'walking', 'exercise', 'gardening', 'yoga', 'stretching'],
            'falls_safety': ['fall', 'fell', 'fallen', 'stumbled', 'dizzy', 'balance', 'unsteady'],
            'medications': ['medication', 'medicine', 'pills', 'prescr'],
            'social_connection': ['family', 'friend', 'visitor', 'talked to', 'call', 'visit'],
            'chronic_conditions': ['arthritis', 'diabetes', 'copd', 'hypertension', 'condition', 'symptoms'],
            'cognitive_check': ['day of the week', 'what month', 'count backwards', 'remember'],
            'reminders': ['reminder', 'appointment', 'doctor', 'dentist']
        }

        for todo_id, keywords in patterns.items():
            if any(keyword in combined_text for keyword in keywords):
                covered.append(todo_id)

        return covered

    def increment_turn(self):
        """Increment conversation turn counter"""
        self.current_turn += 1
