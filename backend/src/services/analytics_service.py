"""
Analytics Service
Extracts metrics from call summaries and stores in Azure SQL for dashboard analytics
"""
import pyodbc
import logging
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from src.config import config

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Extracts health metrics from AI-generated call summaries
    and stores them in Azure SQL for analytics and dashboards
    """

    def __init__(self, connection_string: str = None):
        """
        Initialize Analytics Service

        Args:
            connection_string: Azure SQL connection string (uses config if not provided)
        """
        if connection_string:
            self.connection_string = connection_string
        else:
            # Build from config
            server = config.AZURE_SQL_SERVER
            database = config.AZURE_SQL_DATABASE
            username = config.AZURE_SQL_USERNAME
            password = config.AZURE_SQL_PASSWORD

            self.connection_string = (
                f"Driver={{ODBC Driver 18 for SQL Server}};"
                f"Server=tcp:{server},1433;"
                f"Database={database};"
                f"Uid={username};"
                f"Pwd={password};"
                f"Encrypt=yes;"
                f"TrustServerCertificate=no;"
                f"Connection Timeout=30;"
            )

        logger.info("Analytics Service initialized")

    def _get_connection(self):
        """Get database connection"""
        return pyodbc.connect(self.connection_string)

    def extract_and_save_metrics(
        self,
        senior_id: str,
        session_id: str,
        call_summary: str,
        conversation_history: List[Dict],
        call_duration: int,
        call_completed: bool = True
    ) -> bool:
        """
        Extract all metrics from a completed call and save to analytics database

        Args:
            senior_id: Senior's ID
            session_id: Call session ID
            call_summary: AI-generated call summary
            conversation_history: Full conversation messages
            call_duration: Duration in seconds
            call_completed: Whether call completed successfully

        Returns:
            True if successful
        """
        try:
            # Extract metrics from summary and conversation
            vitals = self._extract_vitals(call_summary, conversation_history)
            cognitive = self._extract_cognitive_metrics(call_summary, conversation_history)
            wellness = self._extract_wellness_scores(call_summary)
            medication = self._extract_medication_info(call_summary, conversation_history)
            alerts = self._detect_health_alerts(call_summary, vitals, cognitive)

            call_date = datetime.utcnow()

            # Save to database
            conn = self._get_connection()
            cursor = conn.cursor()

            # 1. Save vitals
            if vitals:
                self._save_vitals(cursor, senior_id, session_id, call_date, vitals)

            # 2. Save cognitive assessment
            if cognitive:
                self._save_cognitive_assessment(cursor, senior_id, session_id, call_date, cognitive)

            # 3. Save call summary
            self._save_call_summary(
                cursor, senior_id, session_id, call_date,
                call_duration, call_completed, wellness, medication, call_summary, alerts
            )

            # 4. Save medication adherence
            if medication:
                self._save_medication_adherence(cursor, senior_id, session_id, call_date, medication)

            # 5. Save health alerts
            if alerts:
                self._save_health_alerts(cursor, senior_id, session_id, call_date, alerts)

            conn.commit()
            conn.close()

            logger.info(f"Successfully saved analytics for senior {senior_id}, session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving analytics: {e}")
            return False

    def _extract_vitals(self, summary: str, conversation: List[Dict]) -> Dict[str, Dict]:
        """
        Extract vital signs from conversation

        Returns dict like:
        {
            'bp_systolic': {'value': 120, 'unit': 'mmHg'},
            'heart_rate': {'value': 72, 'unit': 'bpm'}
        }
        """
        vitals = {}

        # Combine summary and conversation text
        full_text = summary + " " + " ".join([msg['content'] for msg in conversation])

        # Blood pressure pattern: "120/80", "blood pressure 135 over 85", "BP: 140/90"
        bp_pattern = r'(?:blood pressure|BP|bp)[:\s]+(\d{2,3})[/\s]*(?:over|/)?\s*(\d{2,3})'
        bp_match = re.search(bp_pattern, full_text, re.IGNORECASE)
        if bp_match:
            vitals['bp_systolic'] = {'value': int(bp_match.group(1)), 'unit': 'mmHg'}
            vitals['bp_diastolic'] = {'value': int(bp_match.group(2)), 'unit': 'mmHg'}

        # Heart rate: "heart rate 72", "pulse 68 bpm", "HR: 75"
        hr_pattern = r'(?:heart rate|pulse|HR)[:\s]+(\d{2,3})'
        hr_match = re.search(hr_pattern, full_text, re.IGNORECASE)
        if hr_match:
            vitals['heart_rate'] = {'value': int(hr_match.group(1)), 'unit': 'bpm'}

        # Weight: "weight 165 pounds", "weighs 170 lbs", "weight: 68 kg"
        weight_pattern = r'weigh[ts]*[:\s]+(\d{2,3})\s*(lbs|pounds|kg)'
        weight_match = re.search(weight_pattern, full_text, re.IGNORECASE)
        if weight_match:
            unit = 'lbs' if 'lb' in weight_match.group(2).lower() or 'pound' in weight_match.group(2).lower() else 'kg'
            vitals['weight'] = {'value': int(weight_match.group(1)), 'unit': unit}

        # Blood sugar: "blood sugar 95", "glucose 110 mg/dL"
        glucose_pattern = r'(?:blood sugar|glucose)[:\s]+(\d{2,3})'
        glucose_match = re.search(glucose_pattern, full_text, re.IGNORECASE)
        if glucose_match:
            vitals['blood_sugar'] = {'value': int(glucose_match.group(1)), 'unit': 'mg/dL'}

        # Sleep hours: "slept 7 hours", "sleep: 8.5 hours", "got 6 hours of sleep"
        sleep_pattern = r'(?:slept|sleep|got)[:\s]+(\d+\.?\d*)\s*hours?'
        sleep_match = re.search(sleep_pattern, full_text, re.IGNORECASE)
        if sleep_match:
            vitals['sleep_hours'] = {'value': float(sleep_match.group(1)), 'unit': 'hours'}

        # Pain level: "pain level 5", "pain: 3 out of 10", "rate pain 7/10"
        pain_pattern = r'pain[:\s]+(\d{1,2})'
        pain_match = re.search(pain_pattern, full_text, re.IGNORECASE)
        if pain_match:
            vitals['pain_level'] = {'value': int(pain_match.group(1)), 'unit': 'scale'}

        return vitals

    def _extract_cognitive_metrics(self, summary: str, conversation: List[Dict]) -> Optional[Dict]:
        """
        Extract cognitive health indicators from conversation patterns

        Returns dict with cognitive scores
        """
        # This is a simplified version - in production, use more sophisticated NLP
        cognitive = {}

        full_text = summary.lower()

        # Look for cognitive keywords in summary
        memory_keywords = ['memory', 'remember', 'recall', 'forgot', 'forgetful']
        confusion_keywords = ['confused', 'disoriented', 'unclear', 'lost track']
        coherence_keywords = ['coherent', 'clear', 'lucid', 'oriented']

        # Basic scoring (in production, use actual conversation analysis)
        memory_mentions = sum(1 for kw in memory_keywords if kw in full_text)
        confusion_mentions = sum(1 for kw in confusion_keywords if kw in full_text)
        coherence_mentions = sum(1 for kw in coherence_keywords if kw in full_text)

        if memory_mentions > 0 or confusion_mentions > 0 or coherence_mentions > 0:
            # Simple heuristic scoring (0-100)
            base_score = 85
            if 'memory issues' in full_text or 'forgetful' in full_text:
                base_score -= 15
            if 'confused' in full_text or 'disoriented' in full_text:
                base_score -= 20
            if 'coherent' in full_text or 'oriented' in full_text:
                base_score += 10

            cognitive['overall_score'] = max(0, min(100, base_score))
            cognitive['notes'] = summary[:500]  # First 500 chars

        return cognitive if cognitive else None

    def _extract_wellness_scores(self, summary: str) -> Dict[str, int]:
        """
        Extract wellness scores from summary

        Returns dict with wellness scores (1-10 scale)
        """
        wellness = {}

        # Look for sentiment indicators
        positive_keywords = ['good', 'great', 'well', 'better', 'fine', 'excellent']
        negative_keywords = ['bad', 'poor', 'worse', 'not well', 'sick', 'pain']

        full_text = summary.lower()

        positive_count = sum(1 for kw in positive_keywords if kw in full_text)
        negative_count = sum(1 for kw in negative_keywords if kw in full_text)

        # Simple heuristic (in production, use sentiment analysis model)
        base_wellness = 7
        if positive_count > negative_count:
            wellness['overall_wellness'] = min(10, base_wellness + (positive_count - negative_count))
        else:
            wellness['overall_wellness'] = max(1, base_wellness - (negative_count - positive_count))

        return wellness

    def _extract_medication_info(self, summary: str, conversation: List[Dict]) -> Optional[Dict]:
        """
        Extract medication adherence information

        Returns dict with medication info
        """
        full_text = summary.lower()

        medication = {}

        # Check for medication adherence
        if 'medication' in full_text or 'medicine' in full_text or 'pills' in full_text:
            if 'took' in full_text or 'taken' in full_text:
                medication['medications_taken'] = True
                medication['medications_missed_count'] = 0
            elif 'missed' in full_text or 'forgot' in full_text or 'not taken' in full_text:
                medication['medications_taken'] = False
                medication['medications_missed_count'] = 1

            # Check for side effects
            if 'side effect' in full_text or 'adverse' in full_text:
                medication['side_effects_reported'] = True
                medication['side_effects_description'] = summary[:200]
            else:
                medication['side_effects_reported'] = False

        return medication if medication else None

    def _detect_health_alerts(
        self,
        summary: str,
        vitals: Dict,
        cognitive: Optional[Dict]
    ) -> List[Dict]:
        """
        Detect health alerts that need caregiver attention

        Returns list of alert dicts
        """
        alerts = []
        full_text = summary.lower()

        # Check vital abnormalities
        if 'bp_systolic' in vitals:
            systolic = vitals['bp_systolic']['value']
            if systolic >= 140:
                alerts.append({
                    'alert_type': 'vital_abnormal',
                    'severity': 'high' if systolic >= 160 else 'medium',
                    'description': f'Elevated blood pressure: {systolic} mmHg (systolic)',
                    'related_metric_value': systolic
                })
            elif systolic < 90:
                alerts.append({
                    'alert_type': 'vital_abnormal',
                    'severity': 'high',
                    'description': f'Low blood pressure: {systolic} mmHg (systolic)',
                    'related_metric_value': systolic
                })

        # Check for cognitive concerns
        if cognitive and cognitive.get('overall_score', 100) < 70:
            alerts.append({
                'alert_type': 'cognitive_decline',
                'severity': 'high' if cognitive['overall_score'] < 60 else 'medium',
                'description': f'Cognitive score below threshold: {cognitive["overall_score"]}/100',
                'related_metric_value': cognitive['overall_score']
            })

        # Check for emergency keywords
        emergency_keywords = ['emergency', 'urgent', 'severe pain', 'chest pain', 'can\'t breathe', 'fell', 'fall']
        if any(kw in full_text for kw in emergency_keywords):
            alerts.append({
                'alert_type': 'emergency',
                'severity': 'critical',
                'description': 'Emergency situation detected in conversation',
                'related_metric_value': None
            })

        # Check for isolation indicators
        isolation_keywords = ['lonely', 'alone', 'no one to talk', 'isolated', 'depressed']
        if any(kw in full_text for kw in isolation_keywords):
            alerts.append({
                'alert_type': 'isolation_detected',
                'severity': 'medium',
                'description': 'Social isolation indicators detected',
                'related_metric_value': None
            })

        return alerts

    def _save_vitals(self, cursor, senior_id: str, session_id: str, call_date: datetime, vitals: Dict):
        """Save vitals to database"""
        for vital_type, data in vitals.items():
            cursor.execute("""
                INSERT INTO senior_vitals
                (senior_id, recorded_at, vital_type, vital_value, unit, source, session_id)
                VALUES (?, ?, ?, ?, ?, 'call', ?)
            """, senior_id, call_date, vital_type, data['value'], data['unit'], session_id)

    def _save_cognitive_assessment(self, cursor, senior_id: str, session_id: str, call_date: datetime, cognitive: Dict):
        """Save cognitive assessment to database"""
        cursor.execute("""
            INSERT INTO cognitive_assessments
            (senior_id, assessment_date, overall_score, notes, session_id)
            VALUES (?, ?, ?, ?, ?)
        """, senior_id, call_date, cognitive.get('overall_score'), cognitive.get('notes'), session_id)

    def _save_call_summary(
        self, cursor, senior_id: str, session_id: str, call_date: datetime,
        call_duration: int, call_completed: bool, wellness: Dict, medication: Optional[Dict],
        summary_text: str, alerts: List[Dict]
    ):
        """Save call summary to database"""
        cursor.execute("""
            INSERT INTO call_summary
            (senior_id, call_date, session_id, call_duration, call_completed, call_answered,
             overall_wellness, medication_adherence, medication_missed_count,
             red_flags_count, red_flags, summary_text)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
        """,
            senior_id, call_date, session_id, call_duration, call_completed,
            wellness.get('overall_wellness'),
            medication.get('medications_taken') if medication else None,
            medication.get('medications_missed_count', 0) if medication else 0,
            len(alerts),
            str([a['alert_type'] for a in alerts]) if alerts else None,
            summary_text
        )

    def _save_medication_adherence(self, cursor, senior_id: str, session_id: str, call_date: datetime, medication: Dict):
        """Save medication adherence to database"""
        cursor.execute("""
            MERGE medication_adherence AS target
            USING (SELECT ? AS senior_id, ? AS log_date) AS source
            ON (target.senior_id = source.senior_id AND target.log_date = source.log_date)
            WHEN MATCHED THEN
                UPDATE SET
                    medications_taken = ?,
                    medications_missed_count = ?,
                    side_effects_reported = ?,
                    side_effects_description = ?,
                    session_id = ?
            WHEN NOT MATCHED THEN
                INSERT (senior_id, log_date, medications_taken, medications_missed_count,
                        side_effects_reported, side_effects_description, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
            senior_id, call_date.date(),
            medication.get('medications_taken'),
            medication.get('medications_missed_count', 0),
            medication.get('side_effects_reported', False),
            medication.get('side_effects_description'),
            session_id,
            senior_id, call_date.date(),
            medication.get('medications_taken'),
            medication.get('medications_missed_count', 0),
            medication.get('side_effects_reported', False),
            medication.get('side_effects_description'),
            session_id
        )

    def _save_health_alerts(self, cursor, senior_id: str, session_id: str, call_date: datetime, alerts: List[Dict]):
        """Save health alerts to database"""
        for alert in alerts:
            cursor.execute("""
                INSERT INTO health_alerts
                (senior_id, alert_date, alert_type, severity, description,
                 related_session_id, related_metric_value)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                senior_id, call_date, alert['alert_type'], alert['severity'],
                alert['description'], session_id, alert.get('related_metric_value')
            )
