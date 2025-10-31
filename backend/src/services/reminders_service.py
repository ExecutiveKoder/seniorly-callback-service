"""
Reminders Service
Manages senior reminders, appointments, and upcoming events stored in PostgreSQL
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class RemindersService:
    """Service for managing senior reminders and appointments"""

    def __init__(self):
        """Initialize PostgreSQL connection"""
        try:
            pg_password = os.getenv('AZURE_POSTGRES_PASSWORD', '').strip("'")
            self.pg_conn = psycopg2.connect(
                host=os.getenv('AZURE_POSTGRES_SERVER', '').strip("'"),
                database=os.getenv('AZURE_POSTGRES_DATABASE', '').strip("'"),
                user=os.getenv('AZURE_POSTGRES_USERNAME', '').strip("'"),
                password=pg_password,
                port=os.getenv('AZURE_POSTGRES_PORT', '5432').strip("'"),
                sslmode='require'
            )
            logger.info("✅ RemindersService connected to PostgreSQL")
        except Exception as e:
            logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
            self.pg_conn = None

    def __del__(self):
        """Close connection on cleanup"""
        if self.pg_conn:
            self.pg_conn.close()

    def get_upcoming_reminders(self, senior_id: str, days_ahead: int = 7) -> List[Dict]:
        """
        Get upcoming reminders for a senior

        Args:
            senior_id: Senior's ID
            days_ahead: How many days ahead to look (default 7)

        Returns:
            List of reminder dicts with keys: id, title, description, reminder_date, priority, category, days_until
        """
        if not self.pg_conn:
            return []

        try:
            cursor = self.pg_conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    id,
                    reminder_type,
                    title,
                    description,
                    reminder_date,
                    priority,
                    category,
                    (reminder_date - CURRENT_DATE) as days_until
                FROM senior_reminders
                WHERE senior_id = %s
                    AND completed = false
                    AND reminder_date >= CURRENT_DATE
                    AND reminder_date <= CURRENT_DATE + INTERVAL '%s days'
                ORDER BY reminder_date, priority DESC
            """

            cursor.execute(query, (senior_id, days_ahead))
            reminders = cursor.fetchall()
            cursor.close()

            # Convert to list of dicts
            return [dict(r) for r in reminders]

        except Exception as e:
            logger.error(f"Error getting upcoming reminders: {e}")
            return []

    def get_todays_reminders(self, senior_id: str) -> List[Dict]:
        """Get reminders for today"""
        if not self.pg_conn:
            return []

        try:
            cursor = self.pg_conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    id,
                    reminder_type,
                    title,
                    description,
                    reminder_date,
                    priority,
                    category
                FROM senior_reminders
                WHERE senior_id = %s
                    AND completed = false
                    AND reminder_date = CURRENT_DATE
                ORDER BY priority DESC
            """

            cursor.execute(query, (senior_id,))
            reminders = cursor.fetchall()
            cursor.close()

            return [dict(r) for r in reminders]

        except Exception as e:
            logger.error(f"Error getting today's reminders: {e}")
            return []

    def add_reminder(self, senior_id: str, reminder_type: str, title: str,
                    reminder_date: date, description: str = None,
                    priority: str = 'normal', category: str = None,
                    created_by: str = 'agent') -> bool:
        """
        Add a new reminder

        Args:
            senior_id: Senior's ID
            reminder_type: 'appointment', 'medication_change', 'event', 'task', 'followup'
            title: Short title (e.g., "Doctor appointment")
            reminder_date: Date of the event/appointment
            description: Optional detailed description
            priority: 'low', 'normal', 'high', 'urgent'
            category: 'doctor', 'family', 'social', 'health', 'personal'
            created_by: Who created the reminder ('agent', 'caregiver', 'self')

        Returns:
            True if successful, False otherwise
        """
        if not self.pg_conn:
            return False

        try:
            cursor = self.pg_conn.cursor()

            query = """
                INSERT INTO senior_reminders
                (senior_id, reminder_type, title, description, reminder_date,
                 priority, category, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """

            cursor.execute(query, (
                senior_id, reminder_type, title, description, reminder_date,
                priority, category, created_by
            ))

            reminder_id = cursor.fetchone()[0]
            self.pg_conn.commit()
            cursor.close()

            logger.info(f"✅ Added reminder {reminder_id} for senior {senior_id}: {title}")
            return True

        except Exception as e:
            logger.error(f"Error adding reminder: {e}")
            if self.pg_conn:
                self.pg_conn.rollback()
            return False

    def mark_completed(self, reminder_id: int) -> bool:
        """Mark a reminder as completed"""
        if not self.pg_conn:
            return False

        try:
            cursor = self.pg_conn.cursor()

            query = """
                UPDATE senior_reminders
                SET completed = true, completed_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """

            cursor.execute(query, (reminder_id,))
            self.pg_conn.commit()
            cursor.close()

            logger.info(f"✅ Marked reminder {reminder_id} as completed")
            return True

        except Exception as e:
            logger.error(f"Error marking reminder completed: {e}")
            if self.pg_conn:
                self.pg_conn.rollback()
            return False

    def format_reminders_for_context(self, reminders: List[Dict]) -> str:
        """
        Format reminders for inclusion in conversation context

        Args:
            reminders: List of reminder dicts

        Returns:
            Formatted string to include in AI context
        """
        if not reminders:
            return ""

        lines = ["UPCOMING REMINDERS & APPOINTMENTS:"]

        for reminder in reminders:
            title = reminder['title']
            reminder_date = reminder['reminder_date']
            days_until = reminder.get('days_until')
            priority = reminder.get('priority', 'normal')
            description = reminder.get('description', '')

            # Format the date
            if isinstance(reminder_date, str):
                reminder_date = datetime.fromisoformat(reminder_date).date()

            # Format days until
            if days_until is not None:
                if isinstance(days_until, timedelta):
                    days_until = days_until.days
                else:
                    days_until = int(days_until)

                if days_until == 0:
                    time_str = "TODAY"
                elif days_until == 1:
                    time_str = "TOMORROW"
                else:
                    day_name = reminder_date.strftime('%A')
                    time_str = f"on {day_name} ({days_until} days)"
            else:
                day_name = reminder_date.strftime('%A, %B %d')
                time_str = f"on {day_name}"

            # Build reminder line
            priority_marker = "⚠️ " if priority in ['high', 'urgent'] else ""
            line = f"- {priority_marker}{title} {time_str}"

            if description:
                line += f" - {description}"

            lines.append(line)

        lines.append("\nIMPORTANT: Mention these reminders naturally at the START of the call!")
        lines.append("Example: 'Hi! Just a quick reminder - you have [appointment] [when]. How are you feeling today?'")

        return "\n".join(lines)
