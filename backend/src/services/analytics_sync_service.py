"""
Analytics Sync Service
Automatically syncs conversation data from Cosmos DB to PostgreSQL analytics database
Call this after every conversation ends and summary is generated
"""
import os
import re
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class AnalyticsSyncService:
    """Syncs health data from conversations to PostgreSQL for analytics"""

    def __init__(self):
        """Initialize PostgreSQL connection"""
        try:
            # Get password from environment (set by Key Vault or .env)
            pg_password = os.getenv('AZURE_POSTGRES_PASSWORD', '').strip("'")

            self.pg_conn = psycopg2.connect(
                host=os.getenv('AZURE_POSTGRES_SERVER', '').strip("'"),
                database=os.getenv('AZURE_POSTGRES_DATABASE', '').strip("'"),
                user=os.getenv('AZURE_POSTGRES_USERNAME', '').strip("'"),
                password=pg_password,
                port=os.getenv('AZURE_POSTGRES_PORT', '5432').strip("'"),
                sslmode='require'
            )
            self.pg_conn.autocommit = False
            logger.info("✅ Connected to PostgreSQL analytics database")
        except Exception as e:
            logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
            self.pg_conn = None

    def __del__(self):
        """Close connection on cleanup"""
        if self.pg_conn:
            self.pg_conn.close()

    # ============================================
    # DATA EXTRACTION METHODS
    # ============================================

    def extract_blood_pressure(self, text: str) -> Optional[Tuple[int, int]]:
        """Extract blood pressure like '120/80' or '120 over 80'"""
        patterns = [
            r'(\d{2,3})\s*/\s*(\d{2,3})',  # 120/80
            r'(\d{2,3})\s+over\s+(\d{2,3})',  # 120 over 80
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                systolic, diastolic = int(match.group(1)), int(match.group(2))
                if 60 <= systolic <= 250 and 40 <= diastolic <= 150:
                    return (systolic, diastolic)
        return None

    def extract_heart_rate(self, text: str) -> Optional[int]:
        """Extract heart rate mentions"""
        if re.search(r'\b(heart rate|pulse|bpm)\b', text, re.IGNORECASE):
            match = re.search(r'\b(\d{2,3})\b', text)
            if match:
                hr = int(match.group(1))
                if 30 <= hr <= 200:
                    return hr
        return None

    def extract_sleep_hours(self, text: str) -> Optional[float]:
        """Extract sleep duration"""
        patterns = [
            r'(\d+\.?\d*)\s*hours?\s+(?:of\s+)?sleep',
            r'slept?\s+(?:for\s+)?(\d+\.?\d*)\s*hours?',
            r'got\s+(?:about\s+)?(\d+\.?\d*)\s*hours?',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                hours = float(match.group(1))
                if 0 <= hours <= 24:
                    return hours
        return None

    def extract_pain_level(self, text: str) -> Optional[int]:
        """Extract pain level (1-10 scale)"""
        if re.search(r'\b(pain|hurt|ache|discomfort)\b', text, re.IGNORECASE):
            match = re.search(r'\b(\d{1,2})\s*(?:out of 10|/10)?\b', text)
            if match:
                pain = int(match.group(1))
                if 0 <= pain <= 10:
                    return pain
        return None

    def extract_medications_taken(self, text: str) -> Optional[bool]:
        """Determine if medications were taken"""
        if re.search(r'\b(took|taken|take|taking)\s+(my\s+)?(meds|medications?|pills?)\b', text, re.IGNORECASE):
            return True
        if re.search(r'\b(yes|yeah|yep|uh-huh),?\s+(I\s+)?(did|took|taken)\b', text, re.IGNORECASE):
            return True
        if re.search(r'\b(didn\'?t|haven\'?t|forgot|missed)\s+(my\s+)?(meds|medications?|pills?)\b', text, re.IGNORECASE):
            return False
        return None

    def extract_reminders(self, messages: List[Dict]) -> List[Dict]:
        """
        Extract reminders, appointments, and upcoming events from conversation
        Returns list of reminder dicts with: type, title, description, date, priority
        """
        from datetime import datetime, timedelta
        import dateparser

        reminders = []

        # Combine all messages into conversation text
        conversation_text = " ".join([msg.get('content', '') for msg in messages])

        # Patterns for appointments and events
        appointment_patterns = [
            r'\b(doctor|dentist|medical|appointment|checkup|visit)\b.*?\b(next|this|on)\s+(\w+day|\w+\s+\d+)',
            r'\b(I have|got)\s+(?:a|an)?\s*(appointment|doctor|dentist|checkup)\b.*?\b(next|this|on)\s+(\w+day|\w+\s+\d+)',
            r'\b(appointment|doctor|dentist)\s+(?:on|this|next)\s+(\w+day|\w+\s+\d+)',
        ]

        event_patterns = [
            r'\b(birthday|anniversary|party|gathering|celebration)\b.*?\b(next|this|on)\s+(\w+day|\w+\s+\d+)',
            r'\b(visiting|visit from|seeing)\s+(?:my\s+)?(family|kids|grandkids|children)\b.*?\b(next|this|on)\s+(\w+day|\w+\s+\d+)',
        ]

        task_patterns = [
            r'\bneed to\s+(.*?)\s+(?:by|before|on)\s+(\w+day|\w+\s+\d+)',
            r'\bremember to\s+(.*?)\s+(?:by|before|on)\s+(\w+day|\w+\s+\d+)',
        ]

        # Extract appointments
        for pattern in appointment_patterns:
            matches = re.finditer(pattern, conversation_text, re.IGNORECASE)
            for match in matches:
                try:
                    date_str = match.group(match.lastindex)
                    parsed_date = dateparser.parse(date_str, settings={'RELATIVE_BASE': datetime.now()})

                    if parsed_date and parsed_date.date() >= datetime.now().date():
                        reminders.append({
                            'type': 'appointment',
                            'title': 'Medical appointment',
                            'description': match.group(0)[:200],
                            'date': parsed_date.date(),
                            'priority': 'high',
                            'category': 'doctor'
                        })
                except:
                    pass

        # Extract events
        for pattern in event_patterns:
            matches = re.finditer(pattern, conversation_text, re.IGNORECASE)
            for match in matches:
                try:
                    date_str = match.group(match.lastindex)
                    parsed_date = dateparser.parse(date_str, settings={'RELATIVE_BASE': datetime.now()})

                    if parsed_date and parsed_date.date() >= datetime.now().date():
                        event_type = match.group(1).lower()
                        reminders.append({
                            'type': 'event',
                            'title': f'{event_type.capitalize()} event',
                            'description': match.group(0)[:200],
                            'date': parsed_date.date(),
                            'priority': 'normal',
                            'category': 'family' if 'family' in event_type or 'visit' in event_type else 'social'
                        })
                except:
                    pass

        return reminders

    def extract_cognitive_indicators(self, messages: List[Dict]) -> Dict[str, any]:
        """
        Analyze conversation for cognitive health indicators
        Returns scores for memory, orientation, language, executive function
        """
        scores = {
            'memory_score': None,
            'orientation_score': None,
            'language_score': None,
            'executive_function_score': None,
            'coherence_score': None,
            'overall_score': None
        }

        total_turns = len([m for m in messages if m['role'] == 'user'])

        if total_turns >= 5:
            user_messages = [m['content'] for m in messages if m['role'] == 'user']

            # Language score: based on response length and coherence
            avg_length = sum(len(m.split()) for m in user_messages) / len(user_messages) if user_messages else 0
            scores['language_score'] = min(100, int(avg_length * 10))

            # Orientation score: assume good if responding appropriately
            scores['orientation_score'] = 85

            # Memory score: check if they reference previous info
            has_memory_refs = any(re.search(r'\b(remember|last time|before|earlier)\b', m, re.IGNORECASE)
                                 for m in user_messages)
            scores['memory_score'] = 90 if has_memory_refs else 75

            # Executive function: check if they can explain decisions/plans
            has_planning = any(re.search(r'\b(will|going to|plan|later|tomorrow)\b', m, re.IGNORECASE)
                              for m in user_messages)
            scores['executive_function_score'] = 85 if has_planning else 70

            # Overall score
            valid_scores = [s for s in [scores['memory_score'], scores['orientation_score'],
                                        scores['language_score'], scores['executive_function_score']] if s]
            scores['overall_score'] = int(sum(valid_scores) / len(valid_scores)) if valid_scores else None

        return scores

    # ============================================
    # SYNC METHODS
    # ============================================

    def sync_conversation(self, session_data: Dict) -> bool:
        """
        Sync a conversation to PostgreSQL analytics database
        Call this after call ends and summary is generated

        Args:
            session_data: Full session dict from Cosmos DB with messages and metadata

        Returns:
            True if sync successful, False otherwise
        """
        if not self.pg_conn:
            logger.error("No PostgreSQL connection available")
            return False

        try:
            cursor = self.pg_conn.cursor()

            session_id = session_data['sessionId']
            messages = session_data.get('messages', [])
            metadata = session_data.get('metadata', {})
            created_at = datetime.fromisoformat(session_data['createdAt'].replace('Z', '+00:00'))

            # Get senior_id
            senior_id = metadata.get('senior_id', session_id.split('-')[0])

            # Check if already synced (avoid duplicates)
            cursor.execute("SELECT 1 FROM call_summary WHERE session_id = %s LIMIT 1", (session_id,))
            if cursor.fetchone():
                logger.info(f"Session {session_id} already synced, skipping")
                return True

            logger.info(f"🔄 Syncing session {session_id} to PostgreSQL...")

            # Extract vitals
            vitals = []
            medications_taken = None

            for message in messages:
                content = message.get('content', '')
                timestamp = datetime.fromisoformat(message['timestamp'].replace('Z', '+00:00'))

                # Blood pressure
                bp = self.extract_blood_pressure(content)
                if bp:
                    vitals.append({
                        'vital_type': 'bp_systolic',
                        'vital_value': bp[0],
                        'unit': 'mmHg',
                        'recorded_at': timestamp
                    })
                    vitals.append({
                        'vital_type': 'bp_diastolic',
                        'vital_value': bp[1],
                        'unit': 'mmHg',
                        'recorded_at': timestamp
                    })

                # Heart rate
                hr = self.extract_heart_rate(content)
                if hr:
                    vitals.append({
                        'vital_type': 'heart_rate',
                        'vital_value': hr,
                        'unit': 'bpm',
                        'recorded_at': timestamp
                    })

                # Sleep hours
                sleep = self.extract_sleep_hours(content)
                if sleep:
                    vitals.append({
                        'vital_type': 'sleep_hours',
                        'vital_value': sleep,
                        'unit': 'hours',
                        'recorded_at': timestamp
                    })

                # Pain level
                pain = self.extract_pain_level(content)
                if pain:
                    vitals.append({
                        'vital_type': 'pain_level',
                        'vital_value': pain,
                        'unit': 'scale',
                        'recorded_at': timestamp
                    })

                # Medications
                meds = self.extract_medications_taken(content)
                if meds is not None:
                    medications_taken = meds

            # Insert vitals
            if vitals:
                vitals_data = [
                    (senior_id, v['recorded_at'], v['vital_type'], v['vital_value'], v['unit'], 'call', session_id)
                    for v in vitals
                ]
                execute_values(
                    cursor,
                    "INSERT INTO senior_vitals (senior_id, recorded_at, vital_type, vital_value, unit, source, session_id) VALUES %s",
                    vitals_data
                )
                logger.info(f"  ✅ Inserted {len(vitals)} vitals")

            # Insert cognitive assessment
            cog = self.extract_cognitive_indicators(messages)
            if cog['overall_score']:
                cursor.execute("""
                    INSERT INTO cognitive_assessments
                    (senior_id, assessment_date, memory_score, orientation_score, language_score,
                     executive_function_score, overall_score, session_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    senior_id,
                    created_at,
                    cog['memory_score'],
                    cog['orientation_score'],
                    cog['language_score'],
                    cog['executive_function_score'],
                    cog['overall_score'],
                    session_id
                ))
                logger.info(f"  ✅ Inserted cognitive assessment (score: {cog['overall_score']})")

            # Generate summary text
            summary_text = metadata.get('summary', '')
            if not summary_text:
                summary_parts = []
                if vitals:
                    summary_parts.append(f"Collected {len(vitals)} vital signs")
                if medications_taken is not None:
                    summary_parts.append("Medications: " + ("Taken" if medications_taken else "Missed"))
                summary_parts.append(f"Conversation had {len([m for m in messages if m['role'] == 'user'])} exchanges")
                summary_text = ". ".join(summary_parts) if summary_parts else "Brief check-in"

            # Insert call summary
            cursor.execute("""
                INSERT INTO call_summary
                (senior_id, call_date, session_id, call_duration, call_completed,
                 medication_adherence, summary_text)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                senior_id,
                created_at,
                session_id,
                metadata.get('call_duration'),
                metadata.get('call_completed', True),
                medications_taken,
                summary_text
            ))
            logger.info(f"  ✅ Inserted call summary")

            # Insert medication log
            if medications_taken is not None:
                cursor.execute("""
                    INSERT INTO medication_adherence
                    (senior_id, log_date, medications_taken, session_id)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (senior_id, log_date) DO UPDATE
                    SET medications_taken = EXCLUDED.medications_taken
                """, (
                    senior_id,
                    created_at.date(),
                    medications_taken,
                    session_id
                ))
                logger.info(f"  ✅ Inserted medication log")

            # Extract and insert reminders
            try:
                extracted_reminders = self.extract_reminders(messages)
                if extracted_reminders:
                    for reminder in extracted_reminders:
                        cursor.execute("""
                            INSERT INTO senior_reminders
                            (senior_id, reminder_type, title, description, reminder_date,
                             priority, category, created_by)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            senior_id,
                            reminder.get('type', 'appointment'),
                            reminder.get('title', 'Reminder'),
                            reminder.get('description'),
                            reminder.get('date'),
                            reminder.get('priority', 'normal'),
                            reminder.get('category', 'health'),
                            'agent'
                        ))
                    logger.info(f"  ✅ Inserted {len(extracted_reminders)} reminders")
            except Exception as reminder_error:
                logger.warning(f"  ⚠️  Could not extract reminders: {reminder_error}")

            self.pg_conn.commit()
            cursor.close()
            logger.info(f"✅ Successfully synced session {session_id} to PostgreSQL")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to sync session {session_id}: {e}")
            if self.pg_conn:
                self.pg_conn.rollback()
            return False
